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
    print()
    print("  %s  %.0f KB" % (OUT_JSON.relative_to(REPO),
                             OUT_JSON.stat().st_size / 1024))
    print("  %s  %d files, %.1f MB" % (OUT_PDFS.relative_to(REPO),
                                       len(items), total / 1048576))


if __name__ == "__main__":
    main()
