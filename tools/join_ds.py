"""One file per item: the created summary with the manufacturer's sheet behind it.

That is how 41 of the items were already filed - A1, the electrical, the
plumbing - and it is the pattern to match. Two ways it had drifted:

  - The luminaires and the iGuzzini sheets ARE joined, but a "- DS -" copy of
    the manufacturer pages was left beside them. Two files per item, reading
    as though nothing had been joined.
  - Four door sheets were never joined: a one-page summary and a separate
    manufacturer sheet.

Installation guides ("- IG -", "- IG Note -") stay as they are. A guide is a
different document from a datasheet, and someone fitting the thing wants it
on its own.

Nothing is deleted: a superseded file is moved to _Removed from GP1 register.

    python tools/join_ds.py            # report only
    python tools/join_ds.py --apply
"""
import io, json, shutil, sys
from pathlib import Path

import fitz

REPO = Path(__file__).resolve().parent.parent
SRC = Path(r"C:\Users\gus\Documents\Claude Projects\JANU\04 Project Documents"
           r"\03 Datasheets\GP1 Datasheets")
BIN = SRC.parent / "_Removed from GP1 register"
OUT = io.open(1, "w", encoding="utf-8", closefd=False)


def pages(p):
    d = fitz.open(p)
    n, first = d.page_count, " ".join(d[0].get_text().split())[:120]
    last = " ".join(d[-1].get_text().split())[:120]
    d.close()
    return n, first, last


def contains(item, ds):
    """Is the manufacturer's sheet already inside the item file?

    Compared on page count and on the text of its first and last page, not on
    the file being bigger - a joined file is the summary plus exactly those
    pages, and that is what makes the separate copy redundant."""
    ni, fi, li = pages(item)
    nd, fd, ld = pages(ds)
    if ni != nd + 1:
        return False
    d = fitz.open(item)
    at = " ".join(d[1].get_text().split())[:120]
    end = " ".join(d[-1].get_text().split())[:120]
    d.close()
    return at == fd and end == ld


def main():
    apply = "--apply" in sys.argv
    data = json.loads((REPO / "web/data/datasheets.json").read_text(encoding="utf-8"))
    drop, join, keep = [], [], []
    for it in data["items"]:
        ds = next((x for x in it.get("extras", [])
                   if x["kind"] == "Manufacturer datasheet"), None)
        if not ds:
            continue
        item_p, ds_p = SRC / it["source"], SRC / ds["source"]
        if not (item_p.exists() and ds_p.exists()):
            continue
        if contains(item_p, ds_p):
            drop.append((it, ds_p))
        else:
            join.append((it, item_p, ds_p))

    OUT.write("already joined, the separate copy is redundant : %d\n" % len(drop))
    OUT.write("not joined, the summary stands alone           : %d\n" % len(join))
    for it, a, b in join:
        OUT.write("    %-6s %s\n" % (it["group"] + "-" + it["code"], it["title"][:58]))
    if not apply:
        OUT.write("\nreport only - pass --apply to carry it out\n")
        return

    BIN.mkdir(parents=True, exist_ok=True)
    for it, item_p, ds_p in join:
        doc = fitz.open(item_p)
        doc.insert_pdf(fitz.open(ds_p))
        doc.save(str(item_p) + ".tmp", garbage=3, deflate=True)
        doc.close()
        Path(str(item_p) + ".tmp").replace(item_p)
        shutil.move(str(ds_p), BIN / ds_p.name)
    for it, ds_p in drop:
        shutil.move(str(ds_p), BIN / ds_p.name)
    OUT.write("\njoined %d, removed %d redundant copies -> %s\n"
              % (len(join), len(drop), BIN.name))


if __name__ == "__main__":
    main()
