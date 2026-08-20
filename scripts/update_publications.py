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
                              if e.get("source") == "crossref"]
        except (ValueError, OSError):
            remembered = []

    offline = "--offline" in sys.argv
    fresh = [] if offline else discover(orcid, surname)
    if not offline:
        print("Crossref returned %d candidate record(s)." % len(fresh))
    discovered = remembered + fresh

    entries, added = merge(cfg["entries"], discovered, cfg.get("exclude", []))

    known = {norm_doi(e.get("doi")) for e in remembered}
    brand_new = [e for e in added if e.get("doi") not in known]
    for e in brand_new:
        print("  + new: %s (%s) doi:%s" % (e["title"][:70], e["year"], e["doi"]))
    if not brand_new:
        print("  nothing new to add (%d previously discovered kept)." % len(remembered))

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
