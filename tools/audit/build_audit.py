#!/usr/bin/env python3
"""Build the picture-audit page from _audit.json."""
import json, html, re
from urllib.parse import quote_plus
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
rows = json.load(open(HERE / "audit.json", encoding="utf-8"))
links = json.load(open(HERE / "links.json", encoding="utf-8"))
e = html.escape
NL, TAB = chr(10), chr(9)

SECTIONS = [
    ("wrong", "Wrong", "The picture is not the product. Fix these first."),
    ("weak", "Weak", "Related to the item, but a poor showing of it."),
    ("missing", "No picture",
     "The datasheet embeds none that passed the filter. The register shows the "
     "item code on a tile, which is correct behaviour rather than a fault."),
    ("note", "Probably fine", "Flagged only so the decision is yours."),
]


THUMBS = json.loads((HERE / "thumbs.json").read_text(encoding="utf-8"))


def card(r):
    # The page is served from claude.ai, so a relative "img/x.webp" resolves
    # to nothing. Everything shown here has to travel inside the page.
    shot = THUMBS.get(r["slug"])
    if shot:
        thumb = '<img class="shot" src="%s" alt="Current picture for %s">' % (
            shot, e(r["key"]))
    else:
        thumb = '<span class="shot none">%s</span>' % e(r["code"])
    maker = ('<span class="maker">%s</span>' % e(r["manufacturer"])
             if r["manufacturer"] else "")
    return (
        '<li class="item" data-slug="' + e(r["slug"]) + '" '
        'data-verdict="' + r["verdict"] + '">'
        '<div class="figure">' + thumb + '</div>'
        '<div class="detail">'
        '<p class="ident"><span class="chip">' + e(r["key"]) + '</span>' + maker +
        '<span class="okmark">Fine as is</span></p>'
        '<h3>' + e(r["title"]) + '</h3>'
        '<p class="why">' + e(r["why"]) + '</p>'
        '</div>'
        '<div class="target">'
        '<span class="lbl">Save as</span>'
        '<button class="fname" type="button" data-copy="' + e(r["file"]) + '">'
        '<code>' + e(r["file"]) + '</code><span class="act">Copy</span></button>'
        '<button class="fine" type="button" data-slug="' + e(r["slug"]) + '">'
        'This one is fine</button>'
        '<div class="drop" data-slug="' + e(r["slug"]) + '">'
        '<input class="pick" type="file" accept="image/png,image/jpeg,image/gif,'
        'image/webp,image/svg+xml" id="pick-' + e(r["slug"]) + '">'
        '<label class="pickface" for="pick-' + e(r["slug"]) + '">'
        'Drop a picture here <span>or choose one</span></label>'
        '</div>'
        '</div></li>')


body = []
for key, title, blurb in SECTIONS:
    mine = [r for r in rows if r["verdict"] == key]
    if not mine:
        continue
    names = "\n".join(r["file"] for r in mine)
    body.append(
        '<section class="block ' + key + '">'
        '<header class="blockhead">'
        '<h2>' + title + '<span class="tally" data-tally="' + key + '">' +
        str(len(mine)) + '</span></h2>'
        '<p>' + e(blurb) + ' <span class="cleared-n"></span></p>'
        '<button class="all" type="button" data-copy="' + e(names) + '">'
        'Copy all ' + str(len(mine)) + ' filenames</button>'
        '</header><ul class="items">' + "".join(card(r) for r in mine) +
        '</ul></section>')


def term(r):
    """The whole item name, as the card shows it - "Pool Controller - Pentair
    IntelliCenter Lite i5P", not just the model half. The only thing dropped
    is the filing prefix on the Lutron sheets ("LTRN7 - DS - "), which is a
    document marker rather than anything a search should carry."""
    t = re.sub(r"^[A-Z]{1,6}[0-9.]*\s*-\s*(?:DS|IG)\s*-\s*", "", r["title"])
    m = (r["manufacturer"] or "").split(" (")[0].strip()
    if m and m.split()[0].lower() not in t.lower():
        t = m + " " + t
    return " ".join(t.split())


def linkrow(r):
    state = {"exact": "exact", "site": "site", "none": "none"}[r["kind"]]
    tag = {"exact": "Product page",
           "site": "Manufacturer site only",
           "none": "Nothing yet"}[r["kind"]]
    return (
        '<li class="lrow ' + state + '" data-slug="' + e(r["slug"]) + '" '
        'data-code="' + e(r["key"]) + '">'
        '<div class="lident">'
        '<button class="chip cp" type="button" data-copy="' + e(r["code"]) + '" '
        'title="Copy the code">' + e(r["key"]) + '</button>'
        + ('<span class="maker">' + e(r["manufacturer"]) + '</span>'
           if r["manufacturer"] else '') +
        '<span class="ltag">' + tag + '</span></div>'
        '<a class="ltitle" target="_blank" rel="noopener noreferrer" '
        'href="https://www.google.com/search?q=' + e(quote_plus(term(r))) + '" '
        'title="Search Google for ' + e(term(r)) + '">'
        + e(r["title"]) +
        '<span class="act">Search Google</span></a>'
        '<div class="lfield">'
        '<input class="lurl" type="url" inputmode="url" spellcheck="false" '
        'placeholder="https://… the product page" '
        'value="' + e(r["url"]) + '" '
        'aria-label="Manufacturer page for ' + e(r["key"]) + '">'
        '<button class="lok" type="button">This one is right</button>'
        '</div>'
        '</li>')


_d = json.loads((REPO / "web/data/datasheets.json").read_text(encoding="utf-8"))
TOTAL_ITEMS = len(_d["items"])
TOTAL_PICS = sum(1 for i in _d["items"] if i["image"])



PICS = json.loads((HERE / "pics.json").read_text(encoding="utf-8"))


def prow(it):
    """One item still needing a better picture: what the register shows now,
    the name it shows it under, and the two marks.

    Keyed on `mk` - the item code, or the filename slug for the one code that
    covers two items. The grid used to key on the filename, which is how the
    same mark ended up saved twice under two different names."""
    slug = it["mk"]
    shot = THUMBS.get(it["_stem"])
    face = ('<img class="pshot" src="' + shot + '" alt="" loading="lazy">'
            if shot else
            '<span class="pshot none">No picture</span>')
    return (
        '<li class="prow marked" data-slug="' + e(slug) + '">'
        '<div class="pcard">'
        + face +
        '<span class="pmeta">'
        '<span class="pcode">' + e(it["group"] + "-" + it["code"]) + '</span>'
        '<span class="pname">' + e(it["title"]) + '</span>'
        '</span>'
        '<span class="pacts">'
        '<button class="ptick pok" type="button" '
        'title="This one turned out to be fine after all">Fine after all</button>'
        '</span>'
        # The card IS the drop target now. Everything on this list is here
        # because it needs a better picture, so the next thing anyone wants
        # is somewhere to put one.
        '<div class="target">'
        '<button class="fname cp" type="button" data-copy="' + e(it["want"]) + '">'
        '<code>' + e(it["want"]) + '</code><span class="act">Copy the name</span>'
        '</button>'
        '<div class="drop" data-slug="' + e(slug) + '">'
        '<input class="pick" type="file" accept="image/png,image/jpeg,'
        'image/gif,image/webp,image/svg+xml" id="pick-' + e(slug) + '">'
        '<label class="pickface" for="pick-' + e(slug) + '">'
        'Drop a picture here <span>or choose one</span></label>'
        '</div>'
        '</div>'
        '</div></li>')


def dupegroups():
    """Items whose source PDFs are byte for byte the same file.

    Some are legitimate - one Salto datasheet covers three products - and
    some want reconciling: the two pool lights are filed under both PL and
    the luminaires folder, so each appears twice under different codes.
    """
    by = {}
    for it in _d["items"]:
        by.setdefault(it.get("sha", ""), []).append(it)
    return [v for k, v in sorted(by.items()) if k and len(v) > 1]


_dupes = dupegroups()

DUPES = ("" if not _dupes else
    '<section class="block dupes" id="dupes">'
    '<header class="blockhead">'
    '<h2>The same file, twice<span class="tally">' + str(len(_dupes)) +
    '</span></h2>'
    '<p>These items point at PDFs that are byte for byte identical. Some of '
    'that is correct &mdash; one Salto datasheet covers three products, and '
    'the same QS Link supply serves two shades. The pool lights are the ones '
    'to look at: they are filed under both <code>PL</code> and the '
    'luminaires folder, so each appears twice under a different code. '
    'Nothing here changes anything; it is a list for you to reconcile.</p>'
    '</header><ul class="items dgrid">'
    + "".join(
        '<li class="drow">'
        + "".join('<span class="dpair"><span class="pcode">'
                  + e(x["group"] + "-" + x["code"]) + '</span>'
                  '<span class="pname">' + e(x["title"]) + '</span></span>'
                  for x in g)
        + '<code class="dsha">' + e(g[0].get("sha", "")) + '</code></li>'
        for g in _dupes) +
    '</ul></section>')


PICTURES = (
    '<section class="block pics" id="pics">'
    '<header class="blockhead">'
    '<h2>Pictures to replace<span class="tally" id="ptally">0</span></h2>'
    '<p>The ' + str(len(PICS)) + ' you marked as needing a better picture; '
    'the other ' + str(TOTAL_ITEMS - len(PICS)) + ' you passed. Drop a '
    'replacement straight onto a card and it is staged against that item '
    '&mdash; hand the batch over and I collect it. The filename under each '
    'card is what it gets saved as, if you would rather do it by hand.</p>'
    '<p style="margin-top:8px">If one turns out to be all right after all, '
    'mark it <em>Fine after all</em> and press Save, and it leaves the list. '
    'A dropped picture saves itself; the marks wait for Save.</p>'
    '<p class="lstate" id="pstate">Connecting&hellip;</p>'
    '<div class="lbtns">'
    '<button class="all" type="button" id="psave">Save</button>'
    '<button class="all" type="button" id="phide">Hide the ones now marked fine</button>'
    '<button class="all" type="button" id="pnone">Put them all back</button>'
    '</div>'
    '</header>'
    '<ul class="items pgrid">'
    + "".join(prow(it) for it in PICS) +
    '</ul></section>')


LINKS = (
    '<section class="block links" id="links">'
    '<header class="blockhead">'
    '<h2>Links to confirm<span class="tally" id="ltally">0</span></h2>'
    '<p>The ones still open. ' + str(TOTAL_ITEMS - len(links)) + ' are '
    'already confirmed and have left this list. Each row wants the product '
    'page &mdash; where the item lives now, for current finishes, options '
    'and pricing &mdash; rather than the datasheet. What is in the box is a '
    'guess, usually just the manufacturer&rsquo;s site: paste over it, or '
    'press <em>This one is right</em> if the guess already points where it '
    'should. Either way it saves itself, and the row turns green once the '
    'database has read it back.</p>'
    '<p class="lstate" id="lstate">Connecting&hellip;</p>'
    '<div class="lbtns">'
    '<button class="all" type="button" id="lsave">Save every link</button>'
    '<button class="all" type="button" id="lcopy">Copy every link</button>'
    '<button class="all cp" type="button" data-copy="'
    + e(NL.join(r["key"] + TAB + term(r) for r in links)) +
    '">Copy every item name</button>'
    '</div>'
    '</header>'
    '<ul class="items lrows">' + "".join(linkrow(r) for r in links) + '</ul>'
    '</section>')

n = {k: sum(1 for r in rows if r["verdict"] == k)
     for k in ("wrong", "weak", "missing", "note")}
_reg = json.load(open(HERE.parents[0] / "reg.json", encoding="utf-8")) if False else None

CSS = """
:root{
  --red:#DB3837; --amber:#9A6212; --slate:#65768E; --green:#2E7D5B;
  --bg:#FFFFFF; --sunk:#F4F6F8; --raise:#FFFFFF;
  --ink:#1C2530; --ink2:#55637A; --ink3:#8A97AA;
  --line:#E3E7ED; --line2:#EDF0F4;
  --photo:#F4F6F8; --photoline:#E6EAF0; --photoink:#55637A;
  --sans:"IBM Plex Sans",ui-sans-serif,system-ui,"Segoe UI",Helvetica,Arial,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --red:#EE5952; --amber:#D9A441; --slate:#B0BFD5; --green:#57B98A;
    --bg:#11151C; --sunk:#0C1015; --raise:#171D26;
    --ink:#E8ECF2; --ink2:#A7B3C5; --ink3:#6E7C91;
    --line:#242C38; --line2:#1C232D;
    --photo:#EDF0F4; --photoline:#2A3340; --photoink:#55637A;
  }
}
:root[data-theme="dark"]{
  --red:#EE5952; --amber:#D9A441; --slate:#B0BFD5; --green:#57B98A;
  --bg:#11151C; --sunk:#0C1015; --raise:#171D26;
  --ink:#E8ECF2; --ink2:#A7B3C5; --ink3:#6E7C91;
  --line:#242C38; --line2:#1C232D;
  --photo:#EDF0F4; --photoline:#2A3340; --photoink:#55637A;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:400 15px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding-block:40px 72px;
  padding-left:clamp(16px,4vw,40px);padding-right:clamp(16px,4vw,40px)}
.lede{border-bottom:1px solid var(--line);padding-bottom:28px}
.eyebrow{margin:0 0 8px;font-size:11px;font-weight:600;letter-spacing:.16em;
  text-transform:uppercase;color:var(--ink3)}
h1{margin:0 0 10px;font-size:clamp(28px,4vw,40px);font-weight:300;
  letter-spacing:-.02em;line-height:1.1;text-wrap:balance}
.lede>p{margin:0;max-width:64ch;color:var(--ink2);font-size:14.5px}
.tallies{display:flex;gap:26px;flex-wrap:wrap;margin-top:22px}
.tallies div{display:flex;flex-direction:column;gap:2px}
.tallies b{font-size:26px;font-weight:500;line-height:1;font-variant-numeric:tabular-nums}
.tallies span{font-size:12px;color:var(--ink3)}
.tallies .w b{color:var(--red)}
.tallies .k b{color:var(--amber)}
.tallies .m b{color:var(--slate)}
.how{margin-top:26px;background:var(--sunk);border:1px solid var(--line2);
  border-radius:10px;padding:18px 20px}
.how h2{margin:0 0 10px;font-size:12px;font-weight:600;letter-spacing:.1em;
  text-transform:uppercase;color:var(--ink3)}
.how ol{margin:0;padding-left:20px;display:grid;gap:6px;font-size:14px;
  color:var(--ink2);max-width:66ch}
.how code{font:500 12.5px/1 var(--mono);background:var(--raise);
  border:1px solid var(--line);padding:2px 5px;border-radius:4px;color:var(--ink)}
.how em{font-style:normal;color:var(--ink)}
.block{margin-top:44px}
.blockhead{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;
  padding-bottom:12px;border-bottom:2px solid var(--line)}
.blockhead h2{margin:0;font-size:19px;font-weight:600;letter-spacing:-.01em;
  display:flex;align-items:center;gap:10px}
.tally{font:500 12px/1 var(--mono);color:var(--ink2);background:var(--sunk);
  border:1px solid var(--line);border-radius:99px;padding:5px 9px;
  font-variant-numeric:tabular-nums}
.blockhead>p{margin:0;flex:1 1 280px;min-width:0;font-size:13.5px;color:var(--ink3)}
.wrong .blockhead{border-bottom-color:var(--red)}
.weak .blockhead{border-bottom-color:var(--amber)}
.all{font:inherit;font-size:12.5px;color:var(--ink2);background:var(--raise);
  border:1px solid var(--line);border-radius:7px;padding:7px 12px;cursor:pointer}
.all:hover{border-color:var(--slate);color:var(--ink)}
.items{list-style:none;margin:0;padding:0;display:grid;gap:1px;
  background:var(--line2);border:1px solid var(--line2);border-radius:10px;overflow:hidden}
.item{display:grid;grid-template-columns:96px minmax(0,1fr) minmax(0,290px);
  gap:20px;align-items:center;background:var(--raise);padding:16px 18px}
/* The tile carries the light ground and the picture multiplies against IT.
   Both on one element blends the tile with the dark page behind it, which
   turns every thumbnail into a dark smudge. `isolation` keeps the blend in. */
.figure{display:grid;place-items:center;width:84px;height:84px;padding:6px;
  background:var(--photo);border:1px solid var(--photoline);border-radius:7px;
  isolation:isolate;overflow:hidden}
/* width/height 100% + contain, not max-*: a max-height alone does not hold a
   tall drawing inside a fixed tile, and it spills below the border. */
.shot{width:100%;height:100%;object-fit:contain;mix-blend-mode:multiply}
.shot.none{font:500 13px/1 var(--mono);color:var(--photoink)}
.detail{min-width:0}
.ident{margin:0 0 5px;display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.chip{font:500 11px/1 var(--mono);color:var(--ink2);background:var(--sunk);
  border:1px solid var(--line);padding:4px 6px;border-radius:4px}
.maker{font-size:12px;color:var(--ink3)}
.detail h3{margin:0 0 5px;font-size:14.5px;font-weight:500;line-height:1.35;
  text-wrap:balance}
.why{margin:0;font-size:13px;color:var(--ink3);max-width:56ch}
.target{display:grid;gap:5px;justify-items:stretch}
.lbl{font-size:10.5px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;
  color:var(--ink3)}
.fname{display:flex;align-items:center;gap:10px;width:100%;text-align:left;
  cursor:pointer;font:inherit;background:var(--sunk);border:1px solid var(--line);
  border-radius:7px;padding:9px 11px;color:var(--ink)}
.fname:hover{border-color:var(--slate);background:var(--raise)}
.fname code{font:400 12px/1.4 var(--mono);word-break:break-all;flex:1;min-width:0}
.fname .act{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
  color:var(--ink3);flex:0 0 auto}
.fname.done{border-color:var(--slate)}
.fname.done .act{color:var(--slate)}
:focus-visible{outline:2px solid var(--red);outline-offset:2px;border-radius:4px}
.foot{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);
  font-size:13px;color:var(--ink3);max-width:66ch}
.foot code{font:400 12px/1 var(--mono)}

/* ---- cleared as a false positive ------------------------------------ */
.fine{margin-top:6px;width:100%;font:inherit;font-size:11.5px;cursor:pointer;
  color:var(--ink3);background:transparent;border:1px solid transparent;
  border-radius:6px;padding:5px 8px;text-align:center}
.fine:hover{color:var(--ink);border-color:var(--line);background:var(--sunk)}
.item.cleared{opacity:.55}
.item.cleared .figure{filter:grayscale(1)}
.item.cleared .why{text-decoration:line-through;text-decoration-thickness:1px}
.item.cleared .drop{display:none}
.item.cleared .fine{color:var(--slate);border-color:var(--slate);
  background:var(--sunk);font-weight:500}
.item.cleared .fname{opacity:.5}
.okmark{display:none}
.item.cleared .okmark{display:inline-block;font:600 10px/1 var(--sans);
  letter-spacing:.1em;text-transform:uppercase;color:var(--slate);
  border:1px solid var(--slate);border-radius:4px;padding:4px 6px}
.blockhead .cleared-n{font-size:12px;color:var(--slate)}

/* ---- manufacturer links --------------------------------------------- */
.lrows { gap: 1px; }
.lrow { display: grid; gap: 7px; background: var(--raise); padding: 14px 18px; }
.lident { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.ltag { font-size: 10.5px; font-weight: 600; letter-spacing: .08em;
  text-transform: uppercase; color: var(--ink3);
  border: 1px solid var(--line); border-radius: 4px; padding: 3px 6px; }
.lrow.exact .ltag { color: var(--slate); border-color: var(--slate); }
.lrow.none  .ltag { color: var(--amber); border-color: var(--amber); }
/* The title opens a Google search for the product in a new tab: this
   section exists to hunt product pages, and that search is the first step.
   The code chip still copies. */
.ltitle { display: block; width: 100%; margin: 0; padding: 0; text-align: left;
  font: 500 14px/1.35 var(--sans); color: var(--ink);
  background: none; border: 0; text-decoration: none; cursor: pointer; }
.ltitle:hover { color: var(--red); }
.ltitle .act { display: block; margin-top: 3px; font-size: 11px;
  font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
  color: var(--ink3); opacity: .5; transition: opacity .12s; }
/* Faint rather than hidden: there is no hover on a phone, and an affordance
   nobody can find is not an affordance. */
.ltitle:hover .act, .ltitle:focus-visible .act { opacity: 1; }
.ltitle:hover .act { color: var(--red); }
button.chip { cursor: copy; font: inherit; }
button.chip.done { color: var(--green); border-color: var(--green); }
.ltitle:focus-visible, button.chip:focus-visible {
  outline: 2px solid var(--red); outline-offset: 2px; }
.lurl { width: 100%; font: 400 12.5px/1.4 var(--mono); color: var(--ink);
  background: var(--sunk); border: 1px solid var(--line);
  border-radius: 7px; padding: 9px 11px; }
.lurl:focus { outline: 2px solid var(--red); outline-offset: 1px; }
.lurl::placeholder { color: var(--ink3); font-family: var(--sans); }
.lrow.dirty .lurl { border-color: var(--slate); background: var(--raise); }
.lrow.bad .lurl { border-color: var(--red); }
.lrow.kept { box-shadow: inset 3px 0 0 var(--green); }
.lrow.kept .lurl { border-color: var(--green); }
.lrow.lost { box-shadow: inset 3px 0 0 var(--red); }
.lrow.lost .lurl { border-color: var(--red); }
/* ---- byte-identical items ---- */
.dgrid { display: grid; gap: 1px; }
.drow { display: grid; gap: 8px; background: var(--raise); padding: 14px 18px; }
.dpair { display: grid; gap: 3px; }
.dsha { justify-self: start; font: 400 11px/1 var(--mono); color: var(--ink3); }
@media (min-width: 760px) {
  .drow { grid-template-columns: repeat(auto-fit, minmax(0, 1fr)) auto;
          align-items: center; gap: 8px 22px; }
}

/* ---- the picture review grid ---- */
.pgrid { display: grid; gap: 1px;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); }
.prow { background: var(--raise); }
.pcard { display: grid; gap: 10px; padding: 14px;
  height: 100%; align-content: start; }
.pacts { display: flex; gap: 6px; flex-wrap: wrap; }
.prow .target { display: grid; gap: 8px; margin-top: 2px; }
.prow .fname { font: 400 11px/1.3 var(--mono); color: var(--ink2);
  background: var(--sunk); border: 1px solid var(--line); border-radius: 7px;
  padding: 8px 9px; text-align: left; cursor: copy; word-break: break-all; }
.prow .fname .act { display: block; margin-top: 4px; font: 600 9.5px var(--sans);
  letter-spacing: .07em; text-transform: uppercase; color: var(--ink3); }
.prow .fname.done, .prow .fname.done .act { color: var(--green); }
.prow .drop { min-height: 62px; }
.pshot { display: block; width: 100%; aspect-ratio: 4 / 3;
  object-fit: contain; background: var(--photo); border-radius: 8px;
  border: 1px solid var(--photoline); padding: 8px; }
.pshot.none { display: grid; place-items: center; font: 500 12px var(--mono);
  color: var(--photoink); }
.pmeta { display: grid; gap: 5px; }
.pcode { font: 500 11px/1 var(--mono); color: var(--ink2); }
.pname { font-size: 13px; line-height: 1.35; color: var(--ink); }
.ptick { font: 600 10.5px/1 var(--sans); letter-spacing: .06em;
  text-transform: uppercase; color: var(--ink3); background: none;
  border: 1px solid var(--line); border-radius: 5px; padding: 7px 9px;
  cursor: pointer; }
/* Draw the box. Without one the label reads as a statement about the item
   rather than something you can tick. */
.ptick::before { content: ""; display: inline-block; width: 10px;
  height: 10px; margin-right: 7px; vertical-align: -1px;
  border: 1.5px solid currentColor; border-radius: 3px; }
.ptick:hover { color: var(--ink2); border-color: var(--slate); }
.prow.marked .pbad { color: var(--red); border-color: var(--red); }
.prow.marked .pbad::before { background: var(--red);
  box-shadow: inset 0 0 0 2px var(--raise); }
.prow.okay .pok { color: var(--green); border-color: var(--green); }
.prow.okay .pok::before { background: var(--green);
  box-shadow: inset 0 0 0 2px var(--raise); }
.prow.okay { box-shadow: inset 3px 0 0 var(--green); }
/* Hiding what you have passed is what makes the grid finishable. */
.pgrid.hideok .prow.okay { display: none; }
.prow.marked { background: var(--sunk); box-shadow: inset 3px 0 0 var(--red); }
.ptick:focus-visible { outline: 2px solid var(--red); outline-offset: 2px; }

.lfield { display: flex; gap: 8px; align-items: center; }
.lfield .lurl { flex: 1 1 auto; min-width: 0; }
.lok { flex: 0 0 auto; font: inherit; font-size: 11.5px; white-space: nowrap;
  color: var(--ink2); background: var(--raise); border: 1px solid var(--line);
  border-radius: 7px; padding: 8px 10px; cursor: pointer; }
.lok:hover { border-color: var(--green); color: var(--green); }
.lrow.kept .lok { border-color: var(--green); color: var(--green); }
.lstate { margin: 10px 0 0; font: 500 12.5px/1.5 var(--mono); color: var(--green); }
.lstate.warn { color: var(--amber); }
.lbtns { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
@media (min-width: 760px) {
  .lrow { grid-template-columns: minmax(0, 1fr) minmax(0, 420px);
          align-items: center; gap: 8px 20px; }
  .lident { grid-column: 1; }
  .ltitle { grid-column: 1; grid-row: 2; }
  .lfield { grid-column: 2; grid-row: 1 / span 2; }
}

/* ---- drop target ---------------------------------------------------- */
.drop{position:relative;margin-top:6px;border:1px dashed var(--line);border-radius:7px;
  background:transparent;transition:border-color .12s,background .12s}
.drop.over{border-color:var(--slate);background:var(--sunk)}
.drop.busy{opacity:.6;pointer-events:none}
.pick{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}
.pickface{display:block;padding:9px 11px;font-size:12px;color:var(--ink3);cursor:pointer;
  text-align:center;line-height:1.4}
.pickface span{display:block;font-size:11px;opacity:.75}
.pick:focus-visible+.pickface{outline:2px solid var(--red);outline-offset:2px;border-radius:5px}
.staged{display:flex;align-items:center;gap:10px;padding:8px 9px}
.staged img{width:40px;height:40px;flex:0 0 auto;object-fit:contain;border-radius:5px;
  background:var(--photo);border:1px solid var(--photoline);padding:3px;
  mix-blend-mode:multiply}
.staged .as{flex:1;min-width:0;font:400 11.5px/1.35 var(--mono);color:var(--ink2);
  word-break:break-all}
.staged .as b{display:block;font:600 10px/1 var(--sans);letter-spacing:.1em;
  text-transform:uppercase;color:var(--slate);margin-bottom:3px}
.drop.done{border-style:solid;border-color:var(--slate);background:var(--sunk)}
.rm{flex:0 0 auto;width:24px;height:24px;display:grid;place-items:center;cursor:pointer;
  border:1px solid var(--line);border-radius:5px;background:var(--raise);color:var(--ink3);
  font:400 14px/1 var(--sans)}
.rm:hover{border-color:var(--red);color:var(--red)}
.err{padding:8px 10px;font-size:11.5px;color:var(--red)}

/* ---- the batch bar -------------------------------------------------- */
.bar{position:sticky;bottom:0;z-index:5;margin-top:40px;display:none;
  align-items:center;gap:16px;flex-wrap:wrap;
  background:var(--raise);border:1px solid var(--line);border-radius:12px;
  padding:14px 18px;box-shadow:0 -2px 24px -14px rgba(0,0,0,.5)}
.bar.on{display:flex}
.bar .n{font:500 22px/1 var(--sans);font-variant-numeric:tabular-nums}
.bar .t{flex:1 1 220px;min-width:0;font-size:13px;color:var(--ink2)}
.bar button{font:inherit;font-size:13px;font-weight:500;cursor:pointer;border-radius:8px;
  padding:10px 16px;border:1px solid var(--red);background:var(--red);color:#fff}
.bar button:hover{filter:brightness(1.07)}
.bar .clear{background:var(--raise);border-color:var(--line);color:var(--ink2);font-weight:400}
.bar .clear:hover{border-color:var(--slate);color:var(--ink);filter:none}
.handoff{margin-top:14px;border:1px solid var(--slate);border-radius:10px;
  background:var(--sunk);padding:16px 18px;display:none}
.handoff.on{display:block}
.handoff h3{margin:0 0 6px;font-size:14px;font-weight:600}
.handoff p{margin:0 0 10px;font-size:13px;color:var(--ink2);max-width:62ch}
.say{display:flex;gap:10px;align-items:center;width:100%;text-align:left;cursor:pointer;
  font:inherit;background:var(--raise);border:1px solid var(--line);border-radius:7px;
  padding:10px 12px;color:var(--ink)}
.say:hover{border-color:var(--slate)}
.say code{flex:1;min-width:0;font:400 12px/1.4 var(--mono)}
.offline{margin-top:10px;font-size:12px;color:var(--ink3)}

@media (max-width:760px){
  .item{grid-template-columns:70px minmax(0,1fr);gap:14px}
  .target{grid-column:1/-1}
  .figure{width:64px;height:64px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

JS = (HERE / "page.js").read_text(encoding="utf-8")

doc = (
    "<title>GP1 Picture Audit</title>\n"
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600'
    '&display=swap">\n'
    "<style>" + CSS + "</style>\n"
    '<div class="wrap">\n'
    '<header class="lede">\n'
    '<p class="eyebrow">GP1-MUR &middot; Material &amp; Hardware Register</p>\n'
    "<h1>Picture audit</h1>\n"
    "<p>Every picture the register shows, checked by eye against the item it "
    "belongs to. Nothing is plainly wrong. What is left is " +
    str(n["missing"]) + " Lutron items - their sheets are spec submittals of "
    "dimension drawings and text, with no product photograph in them to lift, "
    "so these need a source outside the submittal folder. Lutron&rsquo;s own "
    "brochures carry photography, which is where LTRN15&rsquo;s came from.</p>"
    "<p style=\"margin-top:10px;font-size:13.5px;color:var(--ink3);max-width:64ch\">"
    "Disagree with a call? <em style=\"font-style:normal;color:var(--ink2)\">"
    "This one is fine</em> clears it and the count drops - the audit is one "
    "person&rsquo;s eye and overruling it is the point.</p>"
    '<div class="tallies">'
    '<div class="k"><b data-tally="weak">' + str(n["weak"]) + "</b><span>worth a look</span></div>"
    '<div class="m"><b data-tally="missing">' + str(n["missing"]) + "</b><span>no picture</span></div>"
    "<div><b>" + str(TOTAL_PICS) + "</b><span>pictures in the register</span></div>"
    "<div><b>" + str(TOTAL_ITEMS) + "</b><span>items</span></div>"
    "</div>\n"
    '<div class="how"><h2>To replace one</h2><ol>'
    "<li>Find a clean product photograph &mdash; ideally a cutout on a plain "
    "white ground, since the register composites it onto a light tile.</li>"
    "<li>Rename it to the filename shown against the item. <em>Any of</em> "
    "<code>.jpg</code> <code>.jpeg</code> <code>.png</code> <code>.webp</code> "
    "works.</li>"
    "<li>Put it in <code>tools/images/</code>.</li>"
    "<li>Run <code>python tools/extract_datasheets.py</code>.</li>"
    "</ol></div>\n</header>\n" + PICTURES + DUPES + LINKS +
    '<div class="bar" id="bar">'
    '<span class="n" id="barn">0</span>'
    '<span class="t" id="bart">pictures staged.</span>'
    '<button class="clear" type="button" id="clear">Remove all</button>'
    '<button type="button" id="hand">Hand the batch over</button>'
    '</div>'
    '<div class="handoff" id="handoff">'
    '<h3><span id="handn">0</span> pictures are waiting in this page</h3>'
    '<p>They are stored with the artifact under their new names. Say this to '
    'Claude and they go into <code>tools/images/</code> and the register is '
    'rebuilt:</p>'
    '<button class="say" type="button" data-copy="Collect the staged pictures from the picture audit artifact and rebuild the register.">'
    '<code>Collect the staged pictures from the picture audit artifact and rebuild the register.</code><span class="said">Copy</span></button>'
    '<p class="offline" id="handlist" style="white-space:pre-line"></p>'
    '</div>'
    '<p class="offline" id="offline"></p>'
    '<p class="foot">Filenames are each datasheet&rsquo;s own slug rather than '
    "its item code, because three plumbing items all carry the code "
    "<code>J9</code> &mdash; a file named <code>J9.jpg</code> would silently "
    "apply to all three. A file in <code>tools/images/</code> always wins over "
    "whatever the extractor picks by itself.</p>\n"
    "</div>\n<script>" + JS + "</script>\n")

out = HERE / "picture-audit.html"
out.write_text(doc, encoding="utf-8")
print("wrote %s  %.0f KB" % (out, out.stat().st_size / 1024))
