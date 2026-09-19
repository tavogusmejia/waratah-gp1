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

import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import fitz
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT_JSON = REPO / "web" / "data" / "datasheets.json"
OUT_PDFS = REPO / "web" / "datasheets"

# Anything under a "(reference)" folder is a transmittal or an index - the
# paperwork the datasheets came wrapped in, not a datasheet. Those folders were
# deleted (10.2 MB that said nothing the register shows); the rule stays so
# that dropping a fresh submittal in here, transmittal and all, still works.
SKIP = ("reference", "Item Index & Links", "Mockup Room 1 - Electrical Distribution")

# The eight groups, in the order the register should read them. The letters are
# the submittal's own, which is why D exists and C and I do not.
GROUPS = {
    "A": ("Pump Room Equipment", "Pool", "JANU-SUB-003"),
    "B": ("In-Pool Fittings", "Pool", "JANU-SUB-004"),
    "D": ("Pool Lighting", "Pool", "JANU-SUB-009"),
    "E": ("Electrical", "Electrical", "JANU-SUB-011"),
    "F": ("Balancing Tank Accessories", "Pool", None),
    "G": ("Piping and Valves", "Pool", None),
    "H": ("Electrical - Pool Bonding", "Pool", None),
    "J": ("Plumbing", "Plumbing", None),
}


# Optional. Two columns, item code and URL, with or without a header:
#
#     A1,https://drive.google.com/file/d/..../view
#
# If it exists, each matching item gets a `drive_url` and the register opens
# that instead of the file shipped beside the page. It is the escape hatch for
# the 40 MB of PDFs in the deploy: fill this in, stop shipping web/datasheets/,
# and nothing in the page's code has to change.
LINKS = HERE / "drive-links.csv"


def drive_links():
    if not LINKS.exists():
        return {}
    import csv
    out = {}
    with LINKS.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < 2:
                continue
            code, url = row[0].strip(), row[1].strip()
            if not url.lower().startswith("http"):
                continue          # skips a header row without needing to know
            out[code.lower()] = url
    return out


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
            return None
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


def pick_image(doc, code):
    """The picture for one item: an override if there is one, else the best
    candidate found in the first few pages."""
    if OVERRIDE.is_dir():
        for ext in ("jpg", "jpeg", "png", "webp"):
            f = OVERRIDE / (code + "." + ext)
            if f.exists():
                return Image.open(f).convert("RGB"), "override"

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


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return re.sub(r"-{2,}", "-", s)


def spans(page):
    """Every text span on the page, in reading order, with what it is set in."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for sp in line["spans"]:
                text = sp["text"].strip()
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

    rec = {"manufacturer": "", "code": "", "title": "",
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
    pdfs = sorted(
        p for p in (HERE).rglob("*.pdf")
        if not any(k in str(p) for k in SKIP)
    )
    items, problems = [], []
    links = drive_links()

    for p in pdfs:
        rel = p.relative_to(HERE)
        group = rel.parts[1][0] if len(rel.parts) > 1 else "?"
        name, discipline, submittal = GROUPS.get(
            group, ("Uncategorised", "Other", None))

        doc = fitz.open(p)
        rec = parse_summary(doc[0])
        pages = doc.page_count
        code_for_img = (rec or {}).get("code") or p.stem.split(" ")[0]
        picture, how = pick_image(doc, code_for_img)
        doc.close()

        if rec is None:
            problems.append(str(rel))
            rec = {"manufacturer": "", "code": "", "title": p.stem,
                   "specs": [], "notes": "", "banner": ""}
            curated = False
        else:
            curated = True

        code = rec["code"] or p.stem.split(" ")[0]
        items.append({
            "id": slug(group + "-" + code + "-" + rec["title"][:40]),
            "code": code,
            "group": group,
            "group_name": name,
            "discipline": discipline,
            "submittal": submittal,
            "manufacturer": rec["manufacturer"],
            "title": rec["title"],
            "specs": rec["specs"],
            "notes": rec["notes"],
            "status": classify(rec["banner"], rec["notes"]),
            "status_text": rec["banner"],
            "curated": curated,
            "pdf": "datasheets/" + slug(p.stem) + ".pdf",
            "pages": pages,
            "bytes": p.stat().st_size,
            "source": str(rel).replace("\\", "/"),
            "drive_url": links.get(code.lower(), ""),
            "image": "img/" + slug(p.stem) + ".webp" if picture else "",
            "_pic": picture,
            "_pic_how": how,
        })

    items.sort(key=lambda r: (list(GROUPS).index(r["group"])
                              if r["group"] in GROUPS else 99,
                              r["code"].zfill(3)))

    by_status = {}
    for r in items:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    print("%d datasheets across %d groups" % (
        len(items), len({r["group"] for r in items})))
    for k in ("as_specified", "substitution", "deviation", "to_review",
              "not_stated"):
        if by_status.get(k):
            print("  %-14s %d" % (k, by_status[k]))
    print("  %-14s %d" % ("no summary", sum(1 for r in items if not r["curated"])))
    n_links = sum(1 for r in items if r["drive_url"])
    if n_links or LINKS.exists():
        print("  %-14s %d of %d  (%s)"
              % ("drive links", n_links, len(items), LINKS.name))
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
    img_bytes = n_auto = n_over = 0
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
    for old in OUT_PDFS.glob("*.pdf"):
        old.unlink()
    # Copy from the path recorded ON each item, never by zipping the two
    # lists: `items` is sorted into reading order after it is built and `pdfs`
    # is not, so zipping them pairs the wrong file with the wrong record. It
    # did exactly that once - 38 of the 45 shipped as somebody else's
    # datasheet, under a slug that looked perfectly correct.
    total = 0
    for r in items:
        src = HERE / r["source"]
        dest = OUT_PDFS / Path(r["pdf"]).name
        shutil.copy2(src, dest)
        got = dest.stat().st_size
        if got != r["bytes"]:
            sys.exit("copied the wrong file for %s: %s is %d bytes, expected %d"
                     % (r["code"], dest.name, got, r["bytes"]))
        total += got

    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "GP1-MUR",
        "title": "Material & Hardware Register",
        "groups": [{"key": k, "name": v[0], "discipline": v[1],
                    "submittal": v[2],
                    "count": sum(1 for r in items if r["group"] == k)}
                   for k, v in GROUPS.items()],
        "items": items,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                        encoding="utf-8")
    print("  %-28s %2d auto + %d override, %.1f MB"
          % (str(OUT_IMGS.relative_to(REPO)), n_auto, n_over, img_bytes/1048576))
    missing = [r["code"] for r in items if not r["image"]]
    if missing:
        print("  no picture found for: " + ", ".join(missing))
        print("  (drop a file at \"Data Sheets/images/<CODE>.jpg\" to supply one)")
    print()
    print("  %s  %.0f KB" % (OUT_JSON.relative_to(REPO),
                             OUT_JSON.stat().st_size / 1024))
    print("  %s  %d files, %.1f MB" % (OUT_PDFS.relative_to(REPO),
                                       len(items), total / 1048576))


if __name__ == "__main__":
    main()
