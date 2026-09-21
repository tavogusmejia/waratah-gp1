# GP1-MUR — Waratah GP1

Procurement records for the GP1-MUR villa. The published site is the
**Material & Hardware Register**: the 45 curated datasheets for mockup room 1,
each with the manufacturer's sheet attached. Read-only.

```
Data Sheets/                  the 45 curated datasheet PDFs + the extractor
Waratah Info/                 brand artwork + the logo tracer
web/                          the register - static site, deployed to Vercel
01 GP1 Procurement Tracker/   the Excel masters
02 Material Register/         no longer wired to anything - see below
supabase/                     no longer wired to anything - see below
```

The older 199-item procurement schedule that used to live at `/schedule` was
**deleted**. It covered 13 trades and carried 40 manufacturer datasheet links
the register does not have — Lighting 16, HVAC 15, FF&E 6, Doors 3 — and all of
it is recoverable from git history (`31d0679` is the last commit that has it).
`02 Material Register/` and `supabase/` are what remain of it: the extractor,
the seed, the research log, the schema and its access policies. Nothing on the
site reads them any more, and nothing here deletes them yet.

---

## The site

`web/` is a plain static site — no build step, no bundler, no framework.

| File | Role |
|---|---|
| `index.html` | The landing, then the register. All markup below the landing is rendered by `register.js`. |
| `assets/register.css` | The design system. Brand-led: two colours and a lot of white. |
| `assets/register.js` | The register. Read-only, no backend. |
| `assets/brand/*.svg` | The traced marks. See *Brand*. |
| `data/datasheets.json` | The 45 items, generated from the PDFs. |
| `img/*.webp` | One photograph per item, lifted out of the PDFs. |
| `datasheets/*.pdf` | The datasheets themselves, shipped with the site. |
| `__probe_landing.html` | Measures the landing: paint timing, render-blocking requests, whether it fits. |
| `__probe_register.html` | Drives the register at a given width and theme, for screenshots and layout checks. |

Both probes are excluded from deploys. See *Testing*.

---

## The Material & Hardware Register

45 curated datasheets across 8 submittal groups. It is **read-only**: there is
no sign-in, no backend and nothing to save. The whole register is
`data/datasheets.json`, generated from the PDFs — change a datasheet, re-run
the extractor, and the page is correct again. There is no second place to
update.

```bash
python "Data Sheets/extract_datasheets.py" --check   # parse and report
python "Data Sheets/extract_datasheets.py"           # write json + copy pdfs
```

### It is a repository, not a workflow

There are no alerts, no status badges and no review state. The submittals are
settled; if something about the project changes it gets changed at the source
and re-extracted. What the page owes a reader is a fast way to find an item,
see what it looks like, read its specification and open its datasheet — so
that is all it does.

Red is spent on exactly one thing, the button that opens a datasheet, plus
focus rings. Everything else is slate on white.

Finding things: a search box over every field (code, title, manufacturer,
notes, and every specification label and value), a manufacturer filter built
from the data itself, and the group rail. Items are always shown grouped,
because the submittal letters are how the team refers to them out loud.

**Two views, remembered between visits.** *Cards* carry a thumbnail — for
recognising something by sight. *List* drops the pictures and fits roughly
twice as many rows on screen — for when you know what you are after. The
eleven items with no photograph show their item code on the tile instead of a
placeholder icon: it keeps every card the same shape and says "no
photograph" rather than miming one.

### The picture

Each item's panel opens with a photograph of the thing, because often that is
the only reason someone opened it — they know the item, they just want to see
it. 34 of the 45 have one, at 720px WebP, under half a megabyte for the set.

**The soft mask is the whole point of how they are loaded.** A PDF keeps a
cutout's transparency in a separate image, and PyMuPDF's `extract_image` hands
back only the base layer — convert that to RGB and every transparent pixel
becomes *black*, so a product shot on a white studio sweep arrives as a product
on a black rectangle. Every image in the pump room submittal has a mask, which
is exactly why that group came out black while the cartridge filter, the one
item with no mask, looked right. So each picture is rebuilt from pixmaps: base,
out of CMYK if it is in it, recombined with its mask, then composited onto
white.

Telling a product shot from everything else a datasheet contains is the other
half. Two measurements do most of it:

- **A uniform border.** A product shot is a cutout on a seamless background, so
  the edge of the image is nearly all one colour. This is what rejects the
  lifestyle photography these PDFs are full of — someone swimming, a pool at
  dusk — which has grass and water at its edges.
- **A minimum colour count**, which rejects the hatched section drawings.

It is not reliable enough to trust blindly and it was not worth making more
elaborate: a third measurement to separate a chrome tap on white from a line
drawing on white scored them identically. So when a pick is wrong, **drop a
replacement at `Data Sheets/images/<CODE>.jpg`** and re-run the extractor —
it wins over anything automatic. Eleven items found nothing and simply show no
picture rather than a wrong one; the extractor names them on every run.

**Photographs keep a light ground in both themes** (`--photo-bg`). Every
picture here is a cutout on white, so a dark tile only letterboxes a white
rectangle inside it — and because the ground stays light, `mix-blend-mode:
multiply` melts the cutout into the tile and never has to be switched off for
dark mode.

### Why the extractor reads fonts, not lines

Each curated PDF opens with a summary page: manufacturer, item code, title,
then label/value pairs. Reading those as alternating lines is wrong the moment
a value wraps — and it wraps in about a third of them.

They were all made from one template with an exact palette, so the extractor
keys on that instead:

```
orange   manufacturer        navy 8.5 bold   field label
navy 12  item code           black           field value
navy 14  title               navy 9.5 bold   Notes / status banner
```

That also does two things a size-based read cannot. It tells a curated summary
apart from a manufacturer's own sheet that merely opens with a big bold
heading — one of the 45 is exactly that, and it is carried with no fields
rather than fabricated ones. And it stops manufacturers' body prose being
swallowed as a field value, because that prose is grey and real values are
black.

**A title is a run of spans, not one span.** Taking the first one truncates
mid-phrase — *"Salt Chlorine Generator — Pentair IntelliChlor LT25 Power Bundle
(P/N"* — which reads like a real title, and that is what makes it dangerous.

### White is the canvas

There is deliberately no `prefers-color-scheme` rule in `register.css`. The
landing is always white — mark, wordmark and waves on paper — and a register
that flipped to dark on a system preference handed a dark-mode reader a white
landing that dissolved into a dark page. The brand is two colours on white;
following the OS would have meant following something other than the brand.

Dark is still there as an explicit choice, and it is the same hues lifted in
OKLCH lightness only. The theme control has two states rather than three,
because an "auto" that can only ever resolve to light is a control at a
permanent zero.

### The PDFs ship with the site

40.3 MB of them, in `web/datasheets/`, renamed to slugs. The source names carry
spaces, ampersands and parentheses; every one has to be percent-encoded in a
URL, and a slug cannot be got wrong by a browser, a server, or a person pasting
a link into a message.

The reference transmittals and submittal indexes were **deleted** — 10.2 MB of
paperwork that said nothing the register shows. The extractor still skips any
`(reference)` folder, so dropping a fresh submittal in here, transmittal and
all, still works.

> The `00 Datasheet Downloads (clickable).html` index that came with the
> folder has all 45 of its links broken: they omit the `Pool/` and
> `Electrical/` prefix, so not one of them resolves. That index is superseded
> by this register and is not deployed.

**If they ever need to come out of the deploy**, each item carries an optional
`drive_url`, and the register opens that in preference to the file beside the
page. Drop a two-column `Data Sheets/drive-links.csv` (item code, URL), re-run
the extractor, and add `datasheets/` to `.vercelignore` — a data change, not a
code change. Links have to be "anyone with the link can view", or the register
shows 45 buttons that lead to a sign-in wall.

Lossless recompression was measured and **rejected**: PyMuPDF's `garbage=4`
`deflate` `clean` pass saves only 9% (40.3 MB to 36.9 MB), which is not worth
rewriting 45 submittal documents for. Do not downsample them — people zoom into
the dimension drawings and print them.

### The landing

`index.html` paints a Waratah landing before it paints anything else: the mark
and wordmark on white, over three drifting wave layers in the two brand
colours. It covers the page until the register is ready, then fades out.

**It is the first paint of `index.html`, not a page of its own.** A separate
landing page would mean two navigations to reach the register, which is the
opposite of what it is for.

Everything it needs is inline in the HTML — the CSS, the two traced marks, the
twenty lines of script. It fetches nothing. The marks go in **once**, as two
paths in a hidden `<defs>` that both the landing and the page header reach with
`<use>`; inlining them twice would be ~16 KB more HTML and would push the page
out of the single round trip that is the whole point — and that single round
trip is the trick: the browser can paint the brand from the first response,
with nothing else to wait on.

Which is also why the two stylesheets are loaded `media="print"` and flipped to
`all` on load. A render-blocking `<link>` is a promise to show the reader
nothing until it arrives, and one of them is a **third-party** round trip to
Google Fonts. The landing covers the register while both land, so neither needs
to block — and the flash of unstyled register they would otherwise cause
happens behind it, where nobody sees it.

```
first contentful paint      ~55ms
render-blocking requests    0          (was 2, one of them third-party)
html transferred            29.2 KB    13.1 KB gzipped - one round trip
register ready              ~316ms     including the 53 KB dataset
landing gone                ~1.4s      900ms of which is deliberate
```

`HOLD_MS` is the one intentionally slow thing in the file. A cached load is
ready in well under a tenth of a second, and a brand that appears and vanishes
inside 80ms reads as a glitch rather than as a landing.

The landing is a **cover, not a gate**. It comes down when `register.js` fires
`gp1:ready`, and comes down anyway on a 6s failsafe, on a keypress, or on a
click. `gp1:ready` fires from both of the register's exits, success and failure —
if it only fired on success, a reader whose register failed to load would be
left watching a brand animation instead of reading the reason.

`?hold` pins it open; it is the only way to inspect something that removes
itself.

**Every class in the landing is prefixed `sp-`.** The landing paints before
`register.css` arrives and then keeps rendering underneath it, so the two
stylesheets share a document and a plain class name in one reaches into the
other. `.bar` did exactly that: the register styles its search toolbar
`.bar { display:flex; padding:18px 0 }`, and because `#splash .bar` declared a
height but no padding, 36px of it leaked in — with `box-sizing:border-box` the
2px progress line became a grey block and the red sweep inside it, sized
`height:100%` of a now-zero content box, disappeared.

It shipped unnoticed because the landing is *correct* for the first ~50ms and
only breaks once the stylesheet lands, so a screenshot taken at first paint —
which is how the landing had been verified — looks perfect. `__probe_landing`
now measures the progress line's height and flags anything over 6px.

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

The landing has its own probe, which loads `index.html` in an iframe rather
than copying it:

```powershell
chrome --headless=new --dump-dom --virtual-time-budget=20000 `
       "http://127.0.0.1:8000/__probe_landing.html?w=400"
```

`?w=` sets the width, `&pin=0` lets the landing run its real course instead of
being held open.

**Measure narrow widths there, not with `--window-size`.** Chrome on Windows
will not make a window narrower than about 500px, so `--window-size=400` lays
the page out at ~500 and crops the screenshot to 400 — which counterfeits a
clipped right edge that is not really there. That cost an hour once already.

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
