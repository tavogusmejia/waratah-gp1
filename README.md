# GP1-MUR — Waratah GP1

Procurement records for the GP1-MUR villa: the master workbooks, and the
**Material & Hardware Register** that is generated from them and published on
the web.

```
01 GP1 Procurement Tracker/   the Excel masters (source of truth for the schedule)
02 Material Register/         extractor + seed data + research log
web/                          the register itself — static site, deployed to Vercel
supabase/                     schema, access policies, first import
```

199 line items across 13 trades. 71 carry a manufacturer datasheet (36%); the
other 128 are the chase list, which is what the register exists to make visible.

---

## The register

`web/` is a plain static site — no build step, no bundler, no framework.

| File | Role |
|---|---|
| `index.html` | Shell and mount point only. All markup is rendered by `app.js`, so there is exactly one description of it. |
| `assets/styles.css` | The design system: tokens, three-state theming, type scale, 13 discipline hues. |
| `assets/app.js` | Data shaping, filter/sort, the three views, the detail sheet. |
| `assets/store.js` | The only file that knows about a backend. |
| `assets/config.js` | Supabase URL + anon key. Committed on purpose — see below. |
| `data/seed.json` | A complete copy of the schedule. The register renders from this first, always. |
| `__probe.html` | Layout regression harness (excluded from deploys). See *Testing*. |

### Two rules the code is built around

**Seed first.** The register renders from `data/seed.json` before the network is
consulted, and stays complete and readable if Supabase is unreachable,
unconfigured, or slow. A procurement schedule that shows a spinner on site wifi
is worse than one that is a few minutes stale.

**The only honest signal is a rejected write.** Who may edit is not knowable in
the browser. The page does not infer permission from a session — it attempts the
write and believes the answer.

### Running it locally

```bash
cd web
python -m http.server 8000
# http://127.0.0.1:8000
```

That is the full local setup. With `config.js` left empty — which is how it
ships — the register runs entirely from `data/seed.json` and makes no
third-party request at all.

---

## Deploying to Vercel

1. Push the repo to GitHub.
2. Import it in Vercel.
3. **Set Root Directory to `web`.** There is no build command and no output
   directory; it is served as static files.

`web/vercel.json` only sets cache and security headers.

---

## Supabase (optional)

The register works without it. Connect it when the team needs to edit the
schedule in the page rather than in the workbook.

```
supabase/schema.sql     table, indexes, coverage view, updated_at trigger
supabase/policies.sql   RLS: anyone reads, listed editors write
supabase/import.sql     first import from data/seed.json
```

Run them in that order, add the team's addresses to `register_editor`, then put
the project URL and anon key in `web/assets/config.js`.

The item JSON uses snake_case keys that match the `register_item` columns 1:1,
deliberately, so the import needs no mapping layer to get wrong.

### About the anon key in `config.js`

It is a public credential. It identifies the project; it grants nothing. Every
permission is decided by row level security: anyone may read the register,
only an address in `register_editor` may write to it. There is no build step
that could inject it, and hiding it would buy nothing.

**Never put the `service_role` key in that file** — it bypasses RLS entirely.

---

## Regenerating the seed from the workbook

```bash
cd "02 Material Register"
python extract_seed.py          # workbook -> seed.json
python extract_seed.py --check seed.json
cp seed.json ../web/data/seed.json
```

`extract_seed.py` uses only the Python 3.12 standard library — it reads the
xlsx as a zip and parses the XML directly, because openpyxl is not installed
here. The rules that matter are documented at the top of that file; getting any
of them wrong corrupts the data silently.

**If Supabase is live, re-importing must not clobber the team's work.**
`import.sql` deliberately updates only the columns that come from the workbook
and leaves `spec_url`, `folder_url`, `approved`, `procured` and `notes` alone.

---

## Testing

There is no test runner. Layout is checked by rendering the page in headless
Chrome and measuring it:

```powershell
# with the local server running
chrome --headless=new --dump-dom --virtual-time-budget=20000 `
       --window-size=1440,1000 "http://127.0.0.1:8000/__probe.html?theme=light&filters=1"
```

`__probe.html` appends a `<pre id="probe">` reporting horizontal overflow, the
active column set and its widths, the measured toolbar height, and whether the
sticky table head is flush at scroll-zero and pinned under the toolbar when
scrolled.

Query parameters: `?theme=light|dark`, `&filters=1` to open the filter panel.

Two sticky failures this catches, both of which have happened:

- a stale hard-coded offset hides the column head behind an open filter panel;
- an overflow container makes the head offset itself *inside* the wrapper,
  leaving a gap above it and hiding the first row of the table.

Checking the computed `top` value catches only the first, which is why the
probe measures geometry instead.

---

## Design notes

**Colour carries meaning, or it is not spent.** Documentation state is green for
held and a hollow ring for absent. The 13 trades each own a hue — evenly split
around the circle, then interleaved so two trades adjacent in the rail are never
adjacent in hue — carried on the rail swatch, the row's left edge and the sheet
header, never on text. One lightness/chroma pair per theme, thirteen hue angles
shared: two numbers change between light and dark, the hues do not.

**Columns appear only when they have something to say.** A column renders when
at least one *visible* row carries a value and the viewport is wide enough for
it. `approved` and `procured` read `not_started` on all 199 items, so they are
not columns today and come back the moment anyone fills one in. This is also
what keeps the table off a horizontal scrollbar.

**`folder_url` degrades to nothing.** No item has a Drive folder yet, so the
"datasheet + folder" split, its bar segment and its filter chips do not render.
The concept stays in the schema and the editor; a control at a permanent zero
is a dead control.

**Offsets are measured, never guessed.** `--toolbar-h` and `--thead-h` are
written from real geometry, which is what lets the discipline band stack
correctly under a column head whose height depends on whether the web font
arrived.

---

## History

The register began as a self-hosting Claude Artifact that rebuilt and
republished its own document to save. That machinery — `buildDocument`,
`validateDocument`, and the invariant that exactly one element carried each of
three ids — is in `02 Material Register/_legacy/` and is not used here. The
`Store` seam it was written around is the reason the move to Supabase touched
no render, filter or edit code.
