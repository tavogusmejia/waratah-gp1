#!/usr/bin/env python3
"""
GP1-MUR datasheet register - extractor.

Reads the 45 curated datasheet PDFs and emits:

    web/data/datasheets.json    the register's data
    web/datasheets/*.pdf        the PDFs, renamed to safe slugs

    python extract_datasheets.py            # write both
    python extract_datasheets.py --check    # parse and report, write nothing

Each curated PDF opens with a summary page the rest of this project can rely
on: manufacturer, item code, title, then a run of label/value pairs, then
notes and sometimes a status banner. The manufacturer's own datasheet follows
on later pages and is not parsed.

WHY IT PARSES BY FONT, NOT BY LINE ORDER
A value wraps onto as many lines as it needs, so "label, value, label, value"
down the lines is wrong the moment a value runs long - and it does, in about a
third of these. Labels and values are set differently, though: labels are bold
and coloured, values are regular and black. That distinction is what the
summary page is actually built on, so it is what this reads.

    9.5 bold, orange   manufacturer
    12  bold, navy     item code
    14  bold, navy     title
    8.5 bold, navy     field label
    8.5 regular, black field value (one or more lines)
    9.5 bold, navy     section heading - Notes, or a status banner

PDFs are renamed to slugs on the way out. The source names carry spaces,
ampersands and parentheses, and every one of those has to be percent-encoded
in a URL; a slug cannot be got wrong by a browser, a server or a person typing
a link into a message.

Python 3.12 + PyMuPDF.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
from html.entities import html5
from datetime import datetime, timezone
from pathlib import Path

import fitz
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT_JSON = REPO / "web" / "data" / "datasheets.json"
OUT_PDFS = REPO / "web" / "datasheets"

# THE DATASHEET REPOSITORY. The one canonical place the curated PDFs live, and
# deliberately OUTSIDE this git repo: the submittal folder is where they are
# filed and maintained, and a second copy in here is how the two silently drift
# apart - which had already started (B2 and B3 differed between the two before
# this was pointed at the real one).
#
# Forward slashes on purpose: pathlib handles them on Windows, and they keep a
# literal path free of backslash escapes. Override with GP1_DATASHEETS.
SOURCE = Path(os.environ.get(
    "GP1_DATASHEETS",
    "C:/Users/gus/Documents/Claude Projects/JANU"
    "/04 Project Documents/03 Datasheets/GP1 Datasheets"))

# Anything under a "(reference)" folder is a transmittal or an index - the
# paperwork the datasheets came wrapped in, not a datasheet. Those folders were
# deleted (10.2 MB that said nothing the register shows); the rule stays so
# that dropping a fresh submittal in here, transmittal and all, still works.
# "- Comparison -" marks a document that weighs two products against each
# other rather than specifying one. Useful paperwork, but it is not any single
# item's datasheet, so it stays in the submittal folder and out of the
# register - J9 had it sitting beside the two sheets it compares.
SKIP = ("reference", "Item Index & Links",
        "Mockup Room 1 - Electrical Distribution", "- Comparison -")

# The groups, in the order the register reads them. The letters are the
# submittal's own, which is why there is no C or I - and why D now means Doors
# while pool lighting moved to L. They were renumbered at the source; this
# follows the source.
GROUPS = {
    "A": ("Pump Room Equipment", "Pool", "JANU-SUB-003"),
    "B": ("In-Pool Fittings", "Pool", "JANU-SUB-004"),
    "D": ("Doors & Hardware", "Doors", None),
    "E": ("Electrical", "Electrical", "JANU-SUB-011"),
    "F": ("Balancing Tank Accessories", "Pool", None),
    "G": ("Piping and Valves", "Pool", None),
    "C": ("Cables and Bonding", "Pool", None),
    "H": ("Bathroom and Shower Fixtures", "Plumbing", None),
    "P": ("Plumbing", "Plumbing", None),
    "L": ("Lighting", "Lighting", None),
    "L&L": ("Luminaires", "Lighting", None),
    "LTRN": ("Lutron Controls", "Lighting", None),
    "PL": ("Pool Lighting", "Pool", "JANU-SUB-009"),
}


def group_of(rel):
    """The submittal letter, taken from the first folder named like one.

    Read from the folder name rather than a fixed depth: the source tree was
    two levels deep when it lived inside this repo and is one level deep now,
    and two folders can share a letter - "D - Doors" holds the tracker
    workbook, "D - Doors Hardware" holds the datasheets.
    """
    # GROUPS decides what counts as a group, and the INNERMOST folder it
    # names wins: "L - Lighting/LTRN - Lutron Lighting" is LTRN, because
    # LTRN is in GROUPS, while "D - Doors/DH - Doors Hardware" stays D,
    # because DH is not. Anything matching but unnamed falls back to the
    # outermost, where the stray-group check will catch it.
    # The & is for "L&L - Luminaires", which no plain [A-Z] run matches.
    seen = [m.group(1) for part in rel.parts[:-1]
            for m in [re.match(r"([A-Z][A-Z&0-9]{0,5})\s*-\s", part)] if m]
    named = [g for g in seen if g in GROUPS]
    if named:
        return named[-1]
    return seen[0] if seen else "?"


# Optional. Two columns, item code and URL, with or without a header:
#
#     A1,https://drive.google.com/file/d/..../view
#
# If it exists, each matching item gets a `drive_url` and the register opens
# that instead of the file shipped beside the page. It is the escape hatch for
# the 40 MB of PDFs in the deploy: fill this in, stop shipping web/datasheets/,
# and nothing in the page's code has to change.
LINKS = HERE / "drive-links.csv"

# Optional, same two-column shape: item code, manufacturer page URL. This is
# the PRODUCT PAGE, not the datasheet - somewhere to go for current pricing,
# finishes, or whatever the submittal PDF has stopped being current about.
MAKER_LINKS = HERE / "maker-links.csv"


def drive_links(path=None):
    """A two-column CSV as {key: url}, keys lowercased.

    The key may be an item code OR a datasheet slug. The slug is the one to
    publish: codes are not unique (83 items, 82 distinct codes) and the
    installation guides and vendor datasheets carried in `extras` have no code
    at all. Same precedence as the picture overrides, for the same reason.
    """
    path = path or LINKS
    if not path.exists():
        return {}
    import csv
    out = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < 2:
                continue
            key, url = row[0].strip(), row[1].strip()
            if not url.lower().startswith("http"):
                continue          # skips a header row without needing to know
            out[key.lower()] = url
    return out


# The short form of each attachment kind, for the key that carries its link.
# Without it a code names both the item and everything hanging off it.
KINDKEY = {"Manufacturer datasheet": "ds",
           "Installation guide": "ig",
           "Installation note": "ig-note"}


def key_for(group, code, kind=""):
    """The stable key for one file: its group, its code, and for an
    attachment, which kind it is - "L&L-L&L12", "D-DH15-ig".

    The code is the key rather than the filename slug because the filename
    moves. Four renames this week detached pictures, manufacturer links and
    Drive URLs from their items, every time silently. The code is what the
    folder is organised by and what you fix when the numbering changes.
    """
    k = group + "-" + code
    if kind:
        k += "-" + KINDKEY.get(kind, slug(kind))
    return k.lower()


def link_for(table, key, stem="", code=""):
    """The link for one file: by its code key first, then by the filename
    slug, then by bare code - the last two only so a table written before
    the key change still resolves."""
    for k in (key.lower(), slug(stem), (code or "").lower()):
        if k and k in table:
            return table[k]
    return ""


# ------------------------------------------------------------- pictures

OUT_IMGS = REPO / "web" / "img"
OVERRIDE = HERE / "images"      # drop A1.jpg / J4.png here to override a pick
IMG_W = 720                     # plenty for the panel it appears in

# What a product photo looks like, versus everything else a datasheet contains.
#
# Two measurements do most of the work. A product shot is a cutout on a
# seamless background, so the BORDER of the image is nearly all one colour -
# which is what rejects the lifestyle photographs these PDFs are full of
# (someone swimming, a pool at dusk): those have grass and water at the edges.
# And line art is two colours, so a minimum on distinct colours rejects the
# hatched section drawings.
#
# It is not reliable enough to trust blindly, and it is not worth making more
# elaborate - a third measurement to separate a chrome tap on white from a line
# drawing on white scored them identically. So the rule is: pick the best
# candidate, and let a human override it by dropping a file in images/.
MIN_PX = 170
MIN_COLORS = 25
MIN_UNIFORM = 0.42


def load_image(doc, xref, smask):
    """One embedded image, flattened onto white.

    THE SOFT MASK IS THE WHOLE POINT. A PDF keeps a cutout's transparency in a
    separate image - the smask - and `extract_image` hands back only the base
    layer. Convert that to RGB and every transparent pixel becomes BLACK, so a
    product photographed on a white studio sweep arrives as a product on a
    black rectangle. Every image in the pump room submittal has a mask, which
    is why that whole group came out black, and the cartridge filter - the one
    item with no mask - looked correct.

    So the image is rebuilt from pixmaps instead: base, converted out of CMYK
    if it is in it, recombined with its mask, then composited onto white
    because the page it lands on is white.
    """
    try:
        pix = fitz.Pixmap(doc, xref)
    except Exception:
        return None
    try:
        if pix.colorspace is None:
            # A STENCIL MASK: one bit of alpha and no colour of its own, meant
            # to be painted in whatever fill the page sets. Rejecting it
            # outright loses real artwork - the Hayward fittings are drawn
            # entirely this way. Composite it as ink on white and let the
            # colour test judge it like anything else.
            if not pix.alpha:
                return None
            a = Image.frombytes("L", (pix.width, pix.height), pix.samples)
            flat = Image.new("RGB", a.size, (255, 255, 255))
            flat.paste(Image.new("RGB", a.size, (20, 20, 20)), mask=a)
            return flat
        if pix.colorspace.n == 4:                    # CMYK -> RGB
            pix = fitz.Pixmap(fitz.csRGB, pix)
        if smask:
            try:
                pix = fitz.Pixmap(pix, fitz.Pixmap(doc, smask))
            except Exception:
                pass                                  # no mask is still usable
        mode = "RGBA" if pix.alpha else "RGB"
        if pix.n - (1 if pix.alpha else 0) == 1:      # greyscale
            mode = "LA" if pix.alpha else "L"
        im = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    except Exception:
        return None
    finally:
        pix = None
    if im.mode in ("RGBA", "LA"):
        im = im.convert("RGBA")
        flat = Image.new("RGB", im.size, (255, 255, 255))
        flat.paste(im, mask=im.split()[3])
        return flat
    return im.convert("RGB")


def _looks_like_product(im):
    """(uniformity, colour count, PIL image) or None."""
    if im is None:
        return None
    a = im.copy()
    a.thumbnail((300, 300))
    w, h = a.size
    if w < 8 or h < 8:
        return None
    px = a.load()
    m = max(3, int(min(w, h) * 0.04))
    border = [px[x, y] for x in range(w)
              for y in list(range(m)) + list(range(h - m, h))]
    border += [px[x, y] for y in range(h)
               for x in list(range(m)) + list(range(w - m, w))]
    q = {}
    for c in border:
        k = (c[0] // 24, c[1] // 24, c[2] // 24)
        q[k] = q.get(k, 0) + 1
    uniform = max(q.values()) / len(border)
    colors = len({(px[x, y][0] // 8, px[x, y][1] // 8, px[x, y][2] // 8)
                  for x in range(0, w, 2) for y in range(0, h, 2)})
    return uniform, colors, im


USED_OVERRIDES = set()


def pick_image(doc, key, code, stem, pdf):
    """The picture for one item, in order of who said so most deliberately:
    an override in tools/images/, a picture filed beside the datasheet, then
    the best candidate the PDF itself yields.

    A picture BESIDE THE DATASHEET is the natural place to put one - the doors
    folder does exactly that, DH4.jpg next to DH4 - Salto LA1T17 .... Named by
    the item code or by the datasheet's own filename prefix.

    An override in tools/images/ is named by the item's KEY - slug(group-code)
    - because that survives a rename, which the filename slug does not. The
    slug and the bare code are still read so that overrides written before
    the key change keep working; the build prints anything left over.
    """
    if OVERRIDE.is_dir():
        for name in (slug(key), slug(stem), code):
            if not name:
                continue
            for ext in ("jpg", "jpeg", "png", "webp"):
                f = OVERRIDE / (name + "." + ext)
                if f.exists():
                    USED_OVERRIDES.add(f.name)
                    return Image.open(f).convert("RGB"), "override"

    for name in (code, code_prefix(stem)):
        if not name:
            continue
        for ext in ("jpg", "jpeg", "png", "webp", "JPG", "PNG"):
            f = pdf.parent / (name + "." + ext)
            if f.exists():
                return Image.open(f).convert("RGB"), "beside"

    best = None
    for pno in range(min(doc.page_count, 6)):
        for im in doc[pno].get_images(full=True):
            xref, smask = im[0], im[1]
            try:
                info = doc.extract_image(xref)
            except Exception:
                continue
            w, h = info["width"], info["height"]
            if w < MIN_PX or h < MIN_PX:
                continue
            if not (0.45 <= w / h <= 2.4):       # banners, rules, strips
                continue
            got = _looks_like_product(load_image(doc, xref, smask))
            if not got:
                continue
            uniform, colors, img = got
            if uniform < MIN_UNIFORM or colors < MIN_COLORS:
                continue
            # Earlier pages first: the hero shot is near the front, the
            # exploded diagrams are near the back.
            score = (w * h) ** 0.5 * (0.5 + uniform) / (1 + pno * 0.4)
            if not best or score > best[0]:
                best = (score, img)
    return (best[1], "auto") if best else (None, None)


def code_key(code):
    """Sort key for an item code, so 2.2 lands between 2 and 3.

    Zero-padding the string cannot do this: "2.2" is already three characters,
    so it padded to nothing and sorted after "007". Codes here are a letter
    and/or dotted numbers - A1, J14, 09, 6.1 - so split them into their parts
    and compare the numbers as numbers.
    """
    m = re.match(r"([A-Za-z]*)\s*([\d.]*)", code.strip())
    alpha, nums = (m.group(1).upper(), m.group(2)) if m else (code, "")
    parts = [int(n) for n in nums.split(".") if n.isdigit()]
    return (alpha, parts, code)


def code_prefix(stem):
    """The item code a filename announces, before the first " - "."""
    return stem.split(" - ")[0].strip()


KIND = {" - IG Note - ": "Installation note",
        " - IG - ": "Installation guide",
        " - DS - ": "Manufacturer datasheet"}

# When every file for a code is marked, this is the one that becomes the item
# and the rest ride along as attachments. The vendor datasheet describes the
# product; an installation guide describes fitting it.
LEADS = (" - DS - ",)


def split_supplements(pdfs, root):
    """One file per item, with the rest kept as attachments.

    The source ships several files per item: "DH4 - Salto LA1T17 ..." is the
    curated sheet, "DH4 - DS - ..." the vendor's own datasheet, "DH4 - IG - ..."
    its installation guide. Only the curated one should be the item - but the
    other two are worth having, so they ride along on the item rather than
    being thrown away. An installation guide is exactly what someone standing
    at the door wants.

    A file is only demoted to an attachment when some OTHER file shares its
    code. That matters: every Lutron sheet is a DS with no sibling at all and
    would vanish under a blunter rule, and P9 carries two genuinely different
    insulations under one code, which a dedupe-by-code would silently halve.

    Which file leads depends on what is there. Where the source carries a
    curated sheet - an unmarked file - that is the item, as in Doors. Where it
    carries only vendor files, as in the bathroom fixtures, the DS leads and
    the installation guides ride along: without this every H code appeared
    twice, once as its datasheet and once as its installation guide, and
    "IG Note" became an item title.
    """
    groups = {}
    for f in pdfs:
        groups.setdefault(
            (group_of(f.relative_to(root)), code_prefix(f.stem)), []).append(f)

    def marker(f):
        return next((m for m in KIND if m in f.name), None)

    lead = {}
    for key, fs in groups.items():
        if len(fs) < 2:
            continue
        plain = [f for f in fs if not marker(f)]
        if len(plain) == 1:
            lead[key] = plain[0]
        elif not plain:
            heads = [f for f in fs for m in LEADS if m in f.name]
            if len(heads) == 1:
                lead[key] = heads[0]
        # More than one unmarked file under a code means two real items
        # sharing it - P9's two insulations. Leave them both alone.

    keep, extras = [], {}
    for f in pdfs:
        key = (group_of(f.relative_to(root)), code_prefix(f.stem))
        if key in lead and f is not lead[key] and marker(f):
            extras.setdefault(lead[key], []).append((KIND[marker(f)], f))
        else:
            keep.append(f)
    return keep, extras


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return re.sub(r"-{2,}", "-", s)


# Some source sheets carry `L&L;` where they mean `L&L`: an entity fixer
# somewhere upstream closed `&L` as though it were an HTML entity, and the
# stray semicolon is now baked into the PDF. Undo exactly that, and nothing
# else - a real entity like `&amp;` is left alone.
_ENTITY = re.compile(r"&([A-Za-z][A-Za-z0-9]*);")


def unmangle(text):
    def fix(m):
        return m.group(0) if m.group(1) + ";" in html5 else "&" + m.group(1)
    return _ENTITY.sub(fix, text)


def spans(page):
    """Every text span on the page, in reading order, with what it is set in."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for sp in line["spans"]:
                text = unmangle(sp["text"].strip())
                if text:
                    out.append({
                        "text": text,
                        "size": round(sp["size"], 1),
                        "bold": bool(sp["flags"] & 16),
                        "color": sp["color"],
                    })
    return out


# The curated pages were all made from one template, and the template uses an
# exact palette. Keying on colour rather than on size is what separates a
# curated summary from a manufacturer's own sheet that happens to open with a
# big bold heading - and what stops a manufacturer's body prose being read as
# a field value, since that prose is grey and real values are black.
ORANGE = 10245888   # manufacturer
NAVY = 2046052      # item code, title, field labels, section headings
BLACK = 0           # field values
GREY = 5989490      # #5B6472 - the category line on the door sheets


def parse_summary(page):
    """The curated summary page, or None if this PDF has not got one.

    One of the 45 is the manufacturer's raw sheet with no summary in front of
    it. It is still a real datasheet and still belongs in the register - it
    just has nothing to parse, and saying so is better than inventing fields
    for it.
    """
    sp = spans(page)
    if len(sp) < 4:
        return None
    head = sp[:6]
    if not any(s["color"] == ORANGE and s["bold"] for s in head):
        return None
    if not any(s["color"] == NAVY and s["size"] >= 13.5 for s in head):
        return None

    rec = {"manufacturer": "", "code": "", "title": "", "category": "",
           "specs": [], "notes": "", "banner": ""}

    def run(pred):
        """The first run of consecutive matching spans, joined.

        Not the first span: a title too long for one line is set as two spans,
        and taking only the first silently truncates it mid-phrase - "Salt
        Chlorine Generator - Pentair IntelliChlor LT25 Power Bundle (P/N".
        It reads like a real title, which is what makes it dangerous.
        """
        out, started = [], False
        for s in sp:
            if pred(s):
                out.append(s["text"])
                started = True
            elif started:
                break
        return " ".join(out)

    rec["manufacturer"] = run(lambda s: s["color"] == ORANGE)
    rec["code"] = run(lambda s: s["color"] == NAVY and 11.5 <= s["size"] <= 13.0)
    rec["title"] = run(lambda s: s["color"] == NAVY and s["size"] >= 13.5)
    # Door sheets carry a category above the title - HINGES, HANDLES. Nothing
    # else uses this colour, and without reading it the word is thrown away.
    rec["category"] = run(lambda s: s["color"] == GREY and s["bold"]).title()

    label = None
    for s in sp:
        if s["color"] == NAVY and s["size"] >= 13.5:
            continue                                    # the title
        if s["color"] == NAVY and 11.5 <= s["size"] <= 13.0:
            continue                                    # the code
        if s["color"] == NAVY and s["bold"] and s["size"] >= 9.2:
            # A section heading. Only two kinds carry anything the register
            # wants; the rest ("Introduction", "Specifications") just mean the
            # next field is starting.
            low = s["text"].lower()
            if low.startswith("note") or low.startswith("status"):
                label = "__notes"
            elif "substitution" in low or "deviation" in low:
                rec["banner"] = s["text"]
                label = "__notes"
            else:
                label = None
        elif s["color"] == NAVY and s["bold"]:
            label = s["text"]
            rec["specs"].append({"label": label, "value": ""})
        elif s["color"] == BLACK and label == "__notes":
            rec["notes"] = (rec["notes"] + " " + s["text"]).strip()
        elif s["color"] == BLACK and rec["specs"] and label:
            cur = rec["specs"][-1]
            cur["value"] = (cur["value"] + " " + s["text"]).strip()

    # "Notes" and "Status" arrive as ordinary fields about as often as they
    # arrive as headings; normalise both into their own slots.
    keep = []
    for f in rec["specs"]:
        low = f["label"].lower()
        if low.startswith("note"):
            rec["notes"] = (rec["notes"] + " " + f["value"]).strip()
        elif low == "status":
            rec["banner"] = f["value"]
        else:
            keep.append(f)
    rec["specs"] = keep
    return rec


def classify(banner: str, notes: str) -> str:
    """The one judgement this script makes, and the one that matters most: a
    substitution or a deviation is something an engineer has to sign off
    before it is built, and the register exists to put those in front of
    somebody rather than leave them in a transmittal nobody reopens.

    The banner alone will not do it. Seven sheets carry the same generic
    heading - "Substitution / Deviation - engineer confirmation required" -
    and which of the two it actually is, or whether it is simply not reviewed
    yet, is only stated in the note underneath. So the banner decides that
    confirmation is needed and the note decides what kind.
    """
    b, n = banner.lower(), notes.lower()

    if "engineer confirmation" in b or "substitution / deviation" in b:
        if n.startswith("deviation") or "deviation:" in n:
            return "deviation"
        if "tbr" in n or "to be reviewed" in n:
            return "to_review"
        return "substitution"
    if b.strip() == "sub" or b.startswith("substitut"):
        return "substitution"
    if "as specified" in b:
        return "as_specified"
    return "not_stated"


def main():
    check = "--check" in sys.argv
    if not SOURCE.is_dir():
        sys.exit("the datasheet repository is not there: " + str(SOURCE))
    pdfs = sorted(
        p for p in SOURCE.rglob("*.pdf")
        if not any(k.lower() in str(p).lower() for k in SKIP)
    )
    pdfs, extras = split_supplements(pdfs, SOURCE)

    # A datasheet announces its item code in its filename - "L7 - DS - ...",
    # "DH4 - Salto ...", "A - Pool Light ...". One that does not is a vendor
    # download nobody has filed yet, and it would otherwise enter the register
    # carrying a part number as its item code ("085329_qs_link_power_supply").
    # Held out and named, rather than shown as an item or dropped in silence.
    filed, unfiled = [], []
    for f in pdfs:
        pre = code_prefix(f.stem)
        (filed if (" - " in f.stem and
                   re.fullmatch(r"[A-Z&]{1,6}[0-9.]*", pre)) else unfiled).append(f)
    pdfs = filed
    items, problems = [], []
    links = drive_links()
    makers = drive_links(MAKER_LINKS)

    for p in pdfs:
        rel = p.relative_to(SOURCE)
        group = group_of(rel)
        name, discipline, submittal = GROUPS.get(
            group, ("Uncategorised", "Other", None))

        doc = fitz.open(p)
        rec = parse_summary(doc[0])
        pages = doc.page_count

        if rec is None:
            problems.append(str(rel))
            rec = {"manufacturer": "", "code": "", "title": p.stem,
                   "category": "", "specs": [], "notes": "", "banner": ""}
            curated = False
        else:
            curated = True

        # The FILENAME carries the item code, not the summary page. The two
        # drift: the door sheets say "4" inside while the file is called
        # "DH4 - ...", and the electrical ones say "03" while the file is
        # "E3 - ...". The filename is what the folder is organised by and
        # what anyone reads off a folder listing, so it wins - but only when
        # it actually looks like a code (letters then digits), which leaves
        # the pool lights, filed as plain "A" and "B", alone.
        prefix = code_prefix(p.stem)
        code = (prefix if re.fullmatch(r"[A-Z&]{1,6}[0-9][0-9.]*", prefix)
                else (rec["code"] or prefix))
        key = key_for(group, code)
        picture, how = pick_image(doc, key, code, p.stem, p)
        doc.close()
        items.append({
            "id": slug(group + "-" + code + "-" + rec["title"][:40]),
            "code": code,
            "group": group,
            "group_name": name,
            "discipline": discipline,
            "submittal": submittal,
            "manufacturer": rec["manufacturer"],
            "category": rec["category"],
            "title": rec["title"],
            "specs": rec["specs"],
            "notes": rec["notes"],
            "status": classify(rec["banner"], rec["notes"]),
            "status_text": rec["banner"],
            "curated": curated,
            "pdf": "datasheets/" + slug(p.stem) + ".pdf",
            "pages": pages,
            "bytes": p.stat().st_size,
            # The same PDF is sometimes filed under two codes - the pool
            # lights are in both PL and the luminaires folder, and one Salto
            # datasheet covers three products. The hash is what lets the
            # audit page group them so they can be reconciled.
            "sha": hashlib.sha256(p.read_bytes()).hexdigest()[:16],
            "source": str(rel).replace("\\", "/"),
            "key": key,
            "drive_url": link_for(links, key, p.stem, code),
            "maker_url": link_for(makers, key, p.stem, code),
            "extras": [
                {"kind": kind,
                 "pdf": "datasheets/" + slug(f.stem) + ".pdf",
                 "source": str(f.relative_to(SOURCE)).replace("\\", "/"),
                 "bytes": f.stat().st_size,
                 "key": key_for(group, code, kind),
                 "drive_url": link_for(links, key_for(group, code, kind),
                                       f.stem)}
                for kind, f in sorted(extras.get(p, []), key=lambda t: t[0])
            ],
            "image": "img/" + slug(p.stem) + ".webp" if picture else "",
            "_pic": picture,
            "_pic_how": how,
        })

    items.sort(key=lambda r: (list(GROUPS).index(r["group"])
                              if r["group"] in GROUPS else 99,
                              code_key(r["code"])))

    by_status = {}
    for r in items:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    print("%d datasheets across %d groups" % (
        len(items), len({r["group"] for r in items})))
    n_extra = sum(len(v) for v in extras.values())
    if n_extra:
        print("  %-14s %d attached to %d items (installation guides and "
              "vendor datasheets)" % ("extras", n_extra, len(extras)))
    if unfiled:
        print("  NOT FILED UNDER AN ITEM CODE, so left out (%d):" % len(unfiled))
        for f in unfiled:
            print("      " + str(f.relative_to(SOURCE)))
        print("      Rename each as \"<CODE> - <name>.pdf\" to bring it in.")
    for k in ("as_specified", "substitution", "deviation", "to_review",
              "not_stated"):
        if by_status.get(k):
            print("  %-14s %d" % (k, by_status[k]))
    print("  %-14s %d" % ("no summary", sum(1 for r in items if not r["curated"])))
    n_links = sum(1 for r in items if r["drive_url"])
    if n_links or LINKS.exists():
        print("  %-14s %d of %d  (%s)"
              % ("drive links", n_links, len(items), LINKS.name))
    n_maker = sum(1 for r in items if r["maker_url"])
    if n_maker or MAKER_LINKS.exists():
        print("  %-14s %d of %d  (%s)"
              % ("maker links", n_maker, len(items), MAKER_LINKS.name))
    thin = [r for r in items if r["curated"] and len(r["specs"]) < 2]
    if thin:
        print("  thin (under 2 fields):")
        for r in thin:
            print("      %s %s" % (r["code"], r["title"][:56]))
    if problems:
        print("  no curated summary page:")
        for q in problems:
            print("      " + q)

    if check:
        return

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_PDFS.mkdir(parents=True, exist_ok=True)
    OUT_IMGS.mkdir(parents=True, exist_ok=True)
    for old in OUT_IMGS.glob("*.webp"):
        old.unlink()

    # WebP, not JPEG: most of these are product cutouts on flat white or flat
    # black, and JPEG rings visibly around those hard edges at any size worth
    # shipping.
    img_bytes = n_auto = n_over = n_beside = 0
    for r in items:
        pic = r.pop("_pic", None)
        how = r.pop("_pic_how", None)
        if pic is None:
            r["image"] = ""
            continue
        if pic.width > IMG_W:
            pic = pic.resize((IMG_W, round(pic.height * IMG_W / pic.width)),
                             Image.LANCZOS)
        dest = OUT_IMGS / Path(r["image"]).name
        pic.save(dest, "WEBP", quality=82, method=5)
        img_bytes += dest.stat().st_size
        n_auto += how == "auto"
        n_over += how == "override"
        n_beside += how == "beside"
    # The PDFs live in Google Drive now. Nothing is copied: web/datasheets/
    # is ignored by git and by Vercel, so a copy here never reaches the
    # deploy, and the register was handing out "./datasheets/x.pdf" links
    # that 404. An item with no Drive link shows as not linked instead.
    if OUT_PDFS.exists():
        for old in OUT_PDFS.glob("*.pdf"):
            old.unlink()
    unlinked = [(r, spec) for r in items for spec in [r] + r["extras"]
                if not spec.get("drive_url")]
    total = 0

    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "GP1-MUR",
        "title": "Material & Hardware Register",
        # Only groups that have something in them. A folder letter that
        # GROUPS has not caught up with is a bug, not an empty group, so it
        # is named below rather than shipped as a phantom filter.
        "groups": [{"key": k, "name": v[0], "discipline": v[1],
                    "submittal": v[2], "count": n}
                   for k, v in GROUPS.items()
                   for n in [sum(1 for r in items if r["group"] == k)] if n],
        "items": items,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                        encoding="utf-8")
    print("  %-28s %2d auto + %d beside + %d override, %.1f MB"
          % (str(OUT_IMGS.relative_to(REPO)), n_auto, n_beside, n_over,
             img_bytes / 1048576))
    # An override that matches nothing is the quiet failure here: the file
    # sits in the folder looking done while the register still shows the
    # picture it was meant to replace. Renaming a datasheet at the source is
    # all it takes - the slug moves and the override is orphaned.
    if OVERRIDE.is_dir():
        orphans = sorted(
            f.name for f in OVERRIDE.iterdir()
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
            and f.name not in USED_OVERRIDES)
        if orphans:
            print("  OVERRIDES THAT MATCHED NOTHING (%d):" % len(orphans))
            for o in orphans:
                print("      " + o)
            print("      Rename each to a current datasheet slug or item code.")

    missing = [r["code"] for r in items if not r["image"]]
    stray = sorted({r["group"] for r in items} - set(GROUPS))
    if stray:
        sys.exit("items are in groups GROUPS does not name: %s. "
                 "  The register renders no tile for them. Add them to "
                 "GROUPS in this file." % ", ".join(stray))
    if missing:
        print("  no picture found for: " + ", ".join(missing))
        print("  (drop a file at \"tools/images/<CODE>.jpg\" to supply one)")
    print()
    print("  %s  %.0f KB" % (OUT_JSON.relative_to(REPO),
                             OUT_JSON.stat().st_size / 1024))
    if unlinked:
        print("  %d WITHOUT A DRIVE LINK - these show as not linked:"
              % len(unlinked))
        for r, spec in unlinked:
            print("      %-10s %s" % (r["code"], Path(spec["source"]).name))
    else:
        print("  every datasheet and attachment opens from Drive")


if __name__ == "__main__":
    main()
