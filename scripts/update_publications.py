#!/usr/bin/env python3
"""
Keep the publications section current without touching HTML by hand.

What it does
------------
1. Reads data/manual.json, which is the source of truth.
2. Asks Crossref whether anything new has appeared with this ORCID iD,
   or under the Arcadia DOI prefix with this surname on it.
3. Merges anything new in (manual entries always win on conflict).
4. Writes data/publications.json and rewrites the block in index.html
   between the PUBS:START and PUBS:END markers.

It only ever adds. If Crossref is down or returns nothing, the manual
list is rendered unchanged, so the page cannot regress.

Run locally:  python scripts/update_publications.py
CI runs it weekly; see .github/workflows/publications.yml
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANUAL = os.path.join(ROOT, "data", "manual.json")
OUTPUT = os.path.join(ROOT, "data", "publications.json")
INDEX = os.path.join(ROOT, "index.html")

START = "<!-- PUBS:START -->"
END = "<!-- PUBS:END -->"

MAILTO = "cameron.macquarrie@arcadiascience.com"
UA = "cdmacquarrie.com publication sync (mailto:%s)" % MAILTO
ARCADIA_PREFIX = "10.57844"
STACKS = "https://thestacks.org"
STACKS_USER = "4227"

KIND_LABEL = {
    "journal": "Journal articles",
    "arcadia": "Arcadia Science",
    "preprint": "Preprints & thesis",
    "abstract": "Conference abstracts",
    "dataset": "Data",
}


# ---------------------------------------------------------------- helpers
def norm_title(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def norm_doi(doi):
    if not doi:
        return None
    doi = doi.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi or None


def esc(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ------------------------------------------------------------- crossref
def crossref_queries(orcid, surname):
    base = "https://api.crossref.org/works"
    yield base + "?" + urllib.parse.urlencode({
        "filter": "orcid:" + orcid, "rows": "200", "mailto": MAILTO})
    yield base + "?" + urllib.parse.urlencode({
        "query.author": surname, "filter": "prefix:" + ARCADIA_PREFIX,
        "rows": "200", "mailto": MAILTO})


def format_authors(authors, surname):
    out = []
    for a in authors or []:
        family = (a.get("family") or "").strip()
        given = (a.get("given") or "").strip()
        if not family:
            continue
        initials = "".join(p[0].upper() for p in re.split(r"[\s.\-]+", given) if p)
        name = (family + " " + initials).strip()
        if family.lower() == surname.lower():
            name = "<b>" + name + "</b>"
        out.append(name)
    return ", ".join(out)


def guess_kind(item):
    doi = norm_doi(item.get("DOI")) or ""
    if doi.startswith(ARCADIA_PREFIX):
        return "arcadia"
    t = item.get("type", "")
    venue = " ".join(item.get("container-title") or []).lower()
    if t in ("dataset", "database", "component") or "biostudies" in venue or "bioimage" in venue:
        return "dataset"
    if t == "posted-content":
        return "preprint"
    if t in ("dissertation", "thesis"):
        return "preprint"
    if t in ("proceedings-article",):
        return "abstract"
    return "journal"


def year_of(item):
    for key in ("issued", "published-print", "published-online", "created"):
        parts = (item.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def item_to_entry(item, surname):
    titles = item.get("title") or []
    if not titles:
        return None
    venue = (item.get("container-title") or [""])[0]
    if not venue:
        venue = item.get("institution", [{}])[0].get("name", "") if item.get("institution") else ""
    if not venue and (norm_doi(item.get("DOI")) or "").startswith(ARCADIA_PREFIX):
        venue = "Arcadia Science"
    return {
        "title": esc(titles[0]),
        "authors": format_authors(item.get("author"), surname),
        "venue": esc(venue) or "Preprint",
        "year": year_of(item),
        "kind": guess_kind(item),
        "doi": norm_doi(item.get("DOI")),
        "url": None,
        "source": "crossref",
    }


def discover_stacks(surname, known_slugs):
    """Most of this work is published on The Stacks, and Crossref only sees
    items that carry the ORCID or list the person as a formal author. So read
    the author page directly, and split what it finds: entries where the
    surname is in the citation metadata are publications; the rest are
    contributions, reported but never added automatically.
    """
    found, contributed = [], []
    try:
        page = fetch_html("%s/users/%s" % (STACKS, STACKS_USER))
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print("  ! The Stacks is unreachable (%s) - skipping" % exc, file=sys.stderr)
        return found, contributed

    cards = re.findall(r'href="/publications/([a-z0-9][a-z0-9\-]{6,})"[^>]*>\s*<div><p>(.*?)</p>',
                       page, re.S)
    seen = set()
    for slug, title in cards:
        if slug in seen or slug in known_slugs:
            continue
        seen.add(slug)
        url = "%s/publications/%s" % (STACKS, slug)
        try:
            pub = fetch_html(url)
        except (urllib.error.URLError, OSError, TimeoutError):
            continue
        authors = re.findall(r'<meta name="citation_author" content="([^"]+)"', pub)
        doi = norm_doi((re.findall(r'<meta name="citation_doi" content="([^"]+)"', pub) or [None])[0])
        date = (re.findall(r'<meta name="citation_date" content="([^"]+)"', pub) or [""])[0]
        year = int(date.split("/")[0]) if date[:4].isdigit() else None
        title = re.sub(r'\s+', " ", title).strip()

        if not any(surname.lower() in a.lower() for a in authors):
            contributed.append((title, url))
            continue
        found.append({
            "title": title,
            "authors": stacks_authors(authors, surname),
            "venue": "Arcadia Science",
            "year": year,
            "kind": "arcadia",
            "doi": doi,
            "url": url,
            "source": "stacks",
        })
    return found, contributed


def stacks_authors(names, surname):
    out = []
    for full in names:
        bits = full.split()
        if not bits:
            continue
        family, given = bits[-1], bits[:-1]
        initials = "".join(g[0].upper() for g in given if g)
        name = (family + " " + initials).strip()
        if family.lower() == surname.lower():
            name = "<b>" + name + "</b>"
        out.append(name)
    return ", ".join(out)


def discover(orcid, surname):
    found = []
    for url in crossref_queries(orcid, surname):
        try:
            payload = fetch_json(url)
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            print("  ! Crossref query failed (%s) - continuing" % exc, file=sys.stderr)
            continue
        for item in payload.get("message", {}).get("items", []):
            names = [(a.get("family") or "").lower() for a in item.get("author") or []]
            if surname.lower() not in names:
                continue
            entry = item_to_entry(item, surname)
            if entry and entry["year"]:
                found.append(entry)
    return found


# --------------------------------------------------------------- merging
def merge(manual_entries, discovered, exclude):
    excluded = {norm_doi(d) for d in exclude if d}
    merged = []
    seen_doi = set()
    seen_title = set()

    for e in manual_entries:
        e = dict(e)
        e.setdefault("source", "manual")
        doi = norm_doi(e.get("doi"))
        e["doi"] = doi
        merged.append(e)
        if doi:
            seen_doi.add(doi)
        seen_title.add(norm_title(e.get("title")))

    added = []
    for e in discovered:
        doi = e.get("doi")
        if not doi or doi in excluded or doi in seen_doi:
            continue
        if norm_title(e.get("title")) in seen_title:
            continue
        seen_doi.add(doi)
        seen_title.add(norm_title(e.get("title")))
        merged.append(e)
        added.append(e)

    merged.sort(key=lambda x: (-(x.get("year") or 0), norm_title(x.get("title"))))
    return merged, added


# -------------------------------------------------------------- rendering
def render_entry(e):
    bits = ['        <li class="pub" data-kind="%s">' % e.get("kind", "journal")]
    bits.append('          <p class="pub-title">%s</p>' % e["title"])
    if e.get("authors"):
        bits.append('          <p class="pub-authors">%s</p>' % e["authors"])

    meta = ['<span class="venue">%s</span>' % e.get("venue", "")]
    badge = e.get("badge") or ("Dataset" if e.get("kind") == "dataset" else None)
    if badge:
        meta.append('<span class="badge">%s</span>' % badge)
    # Everything here is open access, so every entry gets a way through.
    # Direct URL first, then DOI, then a Scholar title search as a last resort
    # (never a dead link, and never a URL we invented).
    if e.get("url"):
        meta.append('<a class="pub-link" href="%s" target="_blank" rel="noopener">Read</a>' % e["url"])
        if e.get("doi"):
            meta.append('<a class="pub-link pub-doi" href="https://doi.org/%s" target="_blank" rel="noopener">doi:%s</a>'
                        % (e["doi"], e["doi"]))
    elif e.get("doi"):
        meta.append(
            '<a class="pub-link" href="https://doi.org/%s" target="_blank" rel="noopener">doi:%s</a>'
            % (e["doi"], e["doi"]))
    else:
        q = urllib.parse.quote_plus(re.sub(r"<[^>]+>", "", e["title"]))
        meta.append('<a class="pub-link pub-search" href="https://scholar.google.com/scholar?q=%s" '
                    'target="_blank" rel="noopener">Find it</a>' % q)

    bits.append('          <p class="pub-meta">%s</p>' % "\n            ".join(meta))

    # A summary figure sits with the paper it came from. The SVG is inlined so
    # its colours follow the site's light/dark toggle.
    for fig in e.get("figures") or []:
        path = os.path.join(ROOT, "figures", fig["file"] + ".svg")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            svg = fh.read().strip()
        bits.append('          <figure class="pub-fig">')
        bits.append('            <figcaption>%s</figcaption>' % fig.get("caption", ""))
        bits.append("            " + svg)
        bits.append("          </figure>")

    bits.append("        </li>")
    return "\n".join(bits)


def render(entries):
    years = []
    for e in entries:
        y = e.get("year")
        if y not in years:
            years.append(y)

    out = []
    for y in years:
        group = [e for e in entries if e.get("year") == y]
        out.append('    <div class="pub-year reveal" data-year="%s">' % y)
        out.append('      <h3 class="year-label">%s</h3>' % y)
        out.append('      <ol class="pub-list">')
        out.extend(render_entry(e) for e in group)
        out.append("      </ol>")
        out.append("    </div>")
    return "\n".join(out)


def splice(html, block):
    if START not in html or END not in html:
        raise SystemExit("index.html is missing the %s / %s markers." % (START, END))
    head, rest = html.split(START, 1)
    _, tail = rest.split(END, 1)
    return head + START + "\n" + block + "\n    " + END + tail


# ------------------------------------------------------------------ main
def main():
    with open(MANUAL, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    orcid = cfg["orcid"]
    surname = cfg.get("author_surname", "MacQuarrie")

    # Anything Crossref found on a previous run is remembered, so an offline
    # run re-renders identically instead of dropping entries on the floor.
    remembered = []
    if os.path.exists(OUTPUT):
        try:
            with open(OUTPUT, "r", encoding="utf-8") as fh:
                remembered = [e for e in json.load(fh).get("entries", [])
                              if e.get("source") in ("crossref", "stacks")]
        except (ValueError, OSError):
            remembered = []

    offline = "--offline" in sys.argv
    known_slugs = set()
    for e in list(cfg["entries"]) + remembered:
        u = e.get("url") or ""
        if "/publications/" in u:
            known_slugs.add(u.rstrip("/").rsplit("/", 1)[-1])

    fresh, contributed = [], []
    if not offline:
        fresh = discover(orcid, surname)
        print("Crossref returned %d candidate record(s)." % len(fresh))
        s_found, contributed = discover_stacks(surname, known_slugs)
        print("The Stacks returned %d new authored record(s)." % len(s_found))
        fresh = fresh + s_found
    discovered = remembered + fresh

    entries, added = merge(cfg["entries"], discovered, cfg.get("exclude", []))

    known = {norm_doi(e.get("doi")) for e in remembered}
    brand_new = [e for e in added if e.get("doi") not in known]
    for e in brand_new:
        print("  + new: %s (%s) doi:%s" % (e["title"][:70], e["year"], e["doi"]))
    if not brand_new:
        print("  nothing new to add (%d previously discovered kept)." % len(remembered))
    for title, url in contributed:
        print("  ~ contributor only, not added: %s" % title[:66])
        print("      %s" % url)

    with open(OUTPUT, "w", encoding="utf-8") as fh:
        json.dump({"count": len(entries), "entries": entries}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    with open(INDEX, "r", encoding="utf-8") as fh:
        html = fh.read()

    updated = splice(html, render(entries))
    if updated != html:
        with open(INDEX, "w", encoding="utf-8") as fh:
            fh.write(updated)
        print("index.html updated (%d publications)." % len(entries))
    else:
        print("index.html already current (%d publications)." % len(entries))


if __name__ == "__main__":
    main()
