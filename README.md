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

## Supabase

Project **`waratah`**, ref `iygkonfuyslvgezgofby`. It is expected to carry other
Waratah projects in time, so everything here lives in a dedicated **`gp1`
schema**, not `public` — otherwise the next project to land in this database
brings its own `register_item` or `editor` table and collides.

The register still runs without it: with `config.js` emptied it renders from
`web/data/seed.json` and never touches the network.

```
supabase/migrations/     the schema, under version control
supabase/make_import.py  generates the data import
supabase/import.sql      import template (empty payload - do not run directly)
supabase/config.toml     CLI project config
```

### Changing the schema

Migrations, never the SQL editor:

```bash
supabase migration new add_supplier_column
# edit supabase/migrations/<timestamp>_add_supplier_column.sql
supabase db push
```

`db push`, `migration list` and `migration repair` all work over the network.
**Docker is only needed for `db pull`, `db diff` and local dev** (`supabase
start`) — none of which this project requires.

The CLI is installed at `%LOCALAPPDATA%\supabase\supabase.exe` and is on PATH.
`supabase link --project-ref iygkonfuyslvgezgofby` if a fresh clone needs it.

### The baseline

`20260907120000_gp1_baseline.sql` is the schema as first applied by hand, and
is recorded as already applied on the live database, so it never re-runs there.
On a fresh database it builds everything from nothing. It was hand-written
rather than produced by `supabase db pull`, because that needs Docker and
because the exact SQL applied was known.

### Loading the data

Data is not in the migrations; `web/data/seed.json` is the record of it.

```bash
python supabase/make_import.py --paste 3   # -> supabase/paste/1..3.sql
```

**The payload is base64 on purpose.** The Supabase web SQL editor splits a
script on semicolons *without respecting string literals*, and the data holds
23 of them (`"Lever handle set; NE-Black Chrome"`). Raw JSON gets cut
mid-payload and the remainder is parsed as SQL, which surfaces as nonsense like
`relation "pocket" does not exist` — "pocket" being a word in item 28.

Re-importing is safe: it updates only the columns that come from the workbook
and leaves `spec_url`, `folder_url`, `approved`, `procured` and `notes` alone,
because those are what the team edits in the page.

### Two things a non-public schema needs

`public` gets both from Supabase's default privileges; a hand-made schema does
not.

1. **Exposed to the API** — *Settings → API → Exposed schemas* must list `gp1`.
   Without it every query returns `PGRST106`, the register falls back to the
   seed, and the page looks like it is working. `store.js` names the reason on
   the console rather than failing silently — check there first if the footer
   says *"From the committed seed"* unexpectedly.

2. **Explicit grants** — in the baseline migration. Without them PostgREST
   reports the table as *missing* rather than *forbidden*, which is a
   confusing way to spend an afternoon.

### Who can edit

`gp1.register_editor` is the entire write allowlist — membership in it is the
only thing that permits an update.

```sql
insert into gp1.register_editor (email, note)
values ('someone@example.com', 'Procurement')
on conflict (email) do nothing;
```

Sign-in is a magic link. *Authentication → URL Configuration* must list the
deployed URL as a redirect target, or the link bounces with "requested path is
invalid".

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

## Brand

```
Waratah Info/Logos/     the supplied artwork - PNG only, no vector
Waratah Info/trace_logo.py   traces it to SVG
web/assets/brand/       the traced marks, which is what the site uses
```

The brand is **two colours and a lot of white**:

| | Hex | OKLCH | On white |
|---|---|---|---|
| Waratah red | `#DB3837` | `0.590 0.200 26.1` | 4.53:1 |
| Waratah slate | `#65768E` | `0.561 0.043 257.0` | 4.63:1 |

Sampled from the artwork, not eyeballed; both supplied files agree exactly.

**The two brand colours can never touch.** They are within 0.03 of each other
in perceived lightness, which puts red on slate at **1.02:1** - to a contrast
algorithm they are the same colour. Side by side on white is the only
arrangement that works, and it is the one the logo uses. Both also sit right at
4.5:1 on white, so neither can carry small text on a dark ground.

### The files

`waratah-mark` is the flower alone; `waratah-logo` is the horizontal lockup;
`waratah-logo-stacked` adds CONSTRUCTION. Each has a `-dark` twin.

The plain files **theme themselves** and the `-dark` files are **fixed**. Use
the plain ones anywhere CSS reaches; use `-dark` where it does not - email, a
README served through a theme switch, anything that rasterises.

Colour is applied by class: `.m` is the mark, `.w` is the wordmark. The file's
own rules are written as bare `svg .m` / `svg .w`, which is the lowest
specificity that works, **so any page rule beats them**:

```css
.brand svg .m { fill: var(--brand-red); }
.brand svg .w { fill: var(--brand-ink); }
```

That matters because the register has a three-state theme. The file's internal
`prefers-color-scheme` query only knows what the OS thinks; an explicit
light/dark toggle has to be able to override it, and this is what lets it.

### The dark palette

`#EE5952` and `#B0BFD5` - the same hue angles, lifted in OKLCH lightness only
(red 0.590 to 0.660, slate 0.561 to 0.800). That takes them from 4.04:1 and
3.95:1 on the dark ground to **5.39:1 and 9.81:1**. Hue is untouched, so it is
still the brand rather than a different red.

### Two things the tracer has already got wrong once

Both are in `trace_logo.py` as assertions now, because both produce a file that
is perfectly valid and quietly incorrect:

- **An angle bracket in a CSS comment.** An SVG is parsed as XML. A `<` inside
  `<style>` makes the whole file fail to render, as a broken image, with
  nothing on the console.
- **A contour with exactly one detected corner fitting to nothing.** The span
  from that corner to itself is the whole loop, not a single point. Getting it
  wrong dropped the counter of `R` and filled the letter in solid.

The traced mark is within **0.987 IoU** of the source artwork, with the
remaining disagreement balanced between the two directions - about 0.4px of
antialiasing threshold, not drift.

### Its limits

The mark has no outline: the petals are separated by negative space, so it
needs a clear ground either side of it. It stops being legible below about
**32px** - at 24px and under the gaps close and it reads as a blob. Anything
smaller (a favicon, a table glyph) needs a simplified mark, which does not
exist yet.

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
