# cdmacquarrie.com

A static personal site — no framework, no build step, no dependencies.
Three files do the work: `index.html`, `css/`, `js/`. Everything else is
tooling that keeps the content current on its own.

Designed and built with [Claude](https://claude.com/claude-code).

---

## Run it locally

The page fetches `py/*.py` at runtime, so `file://` will not work. Use a server:

```bash
python -m http.server 8080
```

Then open <http://localhost:8080>.

---

## Deploy to GitHub Pages

One-time setup:

```bash
git add -A && git commit -m "Initial site"
git branch -M main
git remote add origin https://github.com/USERNAME/cdmacquarrie.com.git
git push -u origin main
```

Then in the repo: **Settings → Pages → Build and deployment → Source → GitHub Actions**.

The workflow in `.github/workflows/deploy.yml` runs on every push, refreshes
publications, rebuilds the gallery, and deploys.

### Custom domain

`CNAME` already contains `www.cdmacquarrie.com`. At your DNS provider, point
`www` at `USERNAME.github.io` with a CNAME record. For the apex domain, add A
records to GitHub's four IPs (`185.199.108.153`, `.109.153`, `.110.153`,
`.111.153`). Then tick **Enforce HTTPS** in Settings → Pages.

---

## Does it update itself?

Partly, and honestly: **new publications, yes. Everything else, no.**

`.github/workflows/deploy.yml` runs every Monday at 06:20 UTC. It calls
`scripts/update_publications.py`, which:

1. reads `data/manual.json` — the source of truth;
2. asks Crossref for anything new under your ORCID iD, plus anything under
   the Arcadia DOI prefix with your surname on it;
3. adds what it finds, **never overwriting or deleting** your manual entries;
4. writes `data/publications.json` and rewrites the block in `index.html`
   between `<!-- PUBS:START -->` and `<!-- PUBS:END -->`;
5. commits and redeploys only if something actually changed.

If Crossref is down, the manual list renders unchanged, so the page cannot regress.

**The catch:** Crossref only knows about work with a registered DOI that has
your ORCID attached. Arcadia pubs and meeting abstracts often will not appear.
Two things make this dramatically better:

- Turn on auto-updates in your ORCID record (Account settings → trusted
  parties → allow Crossref/DataCite to add works). Then anything with a DOI
  flows in automatically. **Your ORCID currently stops at 2019**, so this is
  worth ten minutes.
- For anything Crossref cannot see, add it to `data/manual.json` by hand.

Run it yourself any time:

```bash
python scripts/update_publications.py
```

Add `--offline` to re-render from the manual list without hitting the network.

### Adding a publication by hand

Add an object to `entries` in `data/manual.json`:

```json
{
  "title": "Title, with <em>species names</em> in italics",
  "authors": "Surname AB, <b>MacQuarrie CD</b>, Other CD",
  "venue": "Arcadia Science",
  "year": 2026,
  "kind": "arcadia",
  "doi": null,
  "url": "https://research.arcadiascience.com/pub/some-slug"
}
```

`kind` is one of `journal`, `arcadia`, `preprint`, `abstract`, `dataset` —
it drives the filter chips. Every entry gets a link: `url` wins, then `doi`,
and failing both it falls back to a Google Scholar title search so nothing is
ever a dead end. Then run the script to regenerate the HTML.

---

## Images

Drop files into `images/gallery/` and run:

```bash
python scripts/build_gallery.py
```

That regenerates `js/gallery.js`. Captions come from `data/captions.json`,
keyed by filename; anything unlisted gets a caption derived from its filename.
The gallery section hides itself while the folder is empty. CI runs this on
every push, so committing an image file is enough.

The captions file is pre-filled with the captions from the old Google Sites
galleries — save the files under those names and the captions attach themselves.

---

## The playground

`js/playground.js` loads [Pyodide](https://pyodide.org/) from a CDN the first
time a visitor presses the button (~10 MB, cached afterward), then runs the
Python in `py/` directly in the browser. The Python is the simulation; JavaScript
only draws the shapes it returns and forwards slider values back.

`py/endocytosis.py` is the fission yeast endocytosis sandbox. Its rate constants
are tuned so that each genotype reproduces the measured phenotype: 0.5 um
internalisation in wild type, 1.0 um in *bbc1D*, ~330 nm in *vrp1D*, a normal
distance in *myo1-dCA*, and the *bbc1D myo1-SH3-LCA* rescue back to 0.5 um.
If you change a constant, re-run the calibration before trusting it.

To add one, write `py/yourthing.py` exposing a `Sim` class with:

| member | purpose |
| --- | --- |
| `name`, `blurb`, `cite` | shown in the side panel |
| `controls()` | sliders (`id`, `label`, `min`, `max`, `step`, `value`, `hint`) or dropdowns (`type: "select"`, `options`) |
| `set_param(key, value)` | called when a slider moves |
| `set_choice(key, value)` | called when a dropdown changes |
| `set_pointer(x, y, down)` | pointer position in simulation coordinates |
| `reset()` | restore initial state |
| `step(dt)` | advance by `dt` seconds |
| `scene()` | `{"shapes": [...], "readout": [...], "status": "..."}` |

Shape types the renderer understands: `line`, `curve`, `dot`, `glow`, `band`,
`text`. Colours are named (`accent`, `accent2`, `dim`, `warm`) so they follow
the light/dark theme automatically.

Then add an entry to `SIMS` in `js/playground.js` and a tab button in
`index.html`. Stick to the standard library — no packages means a much faster load.

Each sim is testable headlessly, which is how they were tuned:

```bash
python -c "import importlib.util as u; s=u.spec_from_file_location('m','py/actin.py'); m=u.module_from_spec(s); s.loader.exec_module(m); x=m.Sim(900,560); [x.step(0.02) for _ in range(900)]; print(x.scene()['readout'])"
```

---

## Layout

```
index.html              the whole page
css/style.css           tokens, layout, sections
css/playground.css      simulation panel
js/main.js              theme, nav, reveal, filters, lightbox, hero canvas
js/playground.js        Pyodide harness and canvas renderer
js/gallery.js           generated — do not edit
py/endocytosis.py       the thesis sandbox
py/hunt.py              the chlorarachniophyte model
data/manual.json        publications, source of truth
data/captions.json      gallery captions
scripts/                the two generators
```
