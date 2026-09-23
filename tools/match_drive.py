"""Match crawled Drive files to register items by their CODE.

Drive mirrors the source tree, so a Drive file announces the same group and
the same code as the local one - and the code survives the renames that kept
detaching links from items. Matching on it means a file can be retitled on
either side without breaking anything.

This reports rather than guesses: every Drive file with no home and every
item left without a link is printed. A wrong link is worse than a missing one.
"""
import json, io, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
from extract_datasheets import (KINDKEY, SKIP, code_prefix, group_of,  # noqa
                                key_for, slug)

OUT = io.open(1, "w", encoding="utf-8", closefd=False)
MARKS = {" - IG Note - ": "Installation note",
         " - IG - ": "Installation guide",
         " - DS - ": "Manufacturer datasheet"}


def keyed(paths):
    """Keys for a set of Drive paths, deciding which file leads each code the
    same way split_supplements does locally: the unmarked file where there is
    one, otherwise the DS, with the rest riding along as attachments.

    Without this, a code whose only file is a DS - every bathroom fixture,
    every Lutron sheet - gets keyed as its own attachment and matches nothing.
    """
    bycode, out = {}, {}
    for p in paths:
        rel = Path(p)
        bycode.setdefault((group_of(rel), code_prefix(rel.stem)), []).append(p)
    for (group, code), ps in bycode.items():
        plain = [x for x in ps if not any(m in Path(x).name for m in MARKS)]
        lead = None
        if len(plain) == 1:
            lead = plain[0]
        elif not plain:
            ds = [x for x in ps if " - DS - " in Path(x).name]
            if len(ds) == 1:
                lead = ds[0]
        for x in ps:
            kind = next((MARKS[m] for m in MARKS if m in Path(x).name), "")
            out[x] = key_for(group, code, "" if x == lead else kind)
    return out


def main():
    here = Path.cwd()
    drive = json.loads((here / "_drive.json").read_text(encoding="utf-8"))["files"]
    data = json.loads((REPO / "web/data/datasheets.json").read_text(encoding="utf-8"))

    # A key usually names one item, but P9 carries two different pipe
    # insulations under one code, so the filename slug is kept as the
    # tiebreak for the rare code that covers more than one thing.
    wanted = {}
    for it in data["items"]:
        stem = it["pdf"].split("/")[-1].rsplit(".", 1)[0]
        wanted.setdefault(it["key"], []).append(
            (it["group"] + "-" + it["code"], stem))
        for x in it.get("extras", []):
            xs = x["pdf"].split("/")[-1].rsplit(".", 1)[0]
            wanted.setdefault(x["key"], []).append(
                (it["group"] + "-" + it["code"] + " " + x["kind"], xs))

    pdfs = [f for f in drive
            if f["name"].lower().endswith(".pdf")
            and not any(s.lower() in f["path"].lower() for s in SKIP)]

    keys = keyed([f["path"] for f in pdfs])
    seen = {}
    for f in pdfs:
        seen.setdefault(keys[f["path"]], []).append(f)

    matched, missing, ambiguous = {}, [], []
    for key, claims in sorted(wanted.items()):
        hits = seen.get(key, [])
        for label, stem in claims:
            mine = hits
            if len(claims) > 1 or len(hits) > 1:
                mine = [f for f in hits
                        if slug(Path(f["path"]).stem) == stem] or hits
            ident = key if len(claims) == 1 else key + "|" + stem
            if not mine:
                missing.append((ident, label))
            elif len(mine) > 1:
                ambiguous.append((ident, label, mine))
            else:
                matched[ident] = mine[0]

    used = {f["id"] for f in matched.values()}
    orphans = [f for f in pdfs if f["id"] not in used]

    OUT.write("Drive PDFs in scope      : %d\n" % len(pdfs))
    OUT.write("Register needs a link for: %d\n" % len(wanted))
    OUT.write("MATCHED                  : %d\n" % len(matched))
    OUT.write("NO DRIVE FILE            : %d\n" % len(missing))
    OUT.write("AMBIGUOUS                : %d\n" % len(ambiguous))
    OUT.write("Drive files with no item : %d\n\n" % len(orphans))

    if missing:
        OUT.write("--- items with no Drive file ---\n")
        for key, label in missing:
            OUT.write("  %-22s %s\n" % (key, label))
        OUT.write("\n")
    if ambiguous:
        OUT.write("--- more than one Drive file claims this key ---\n")
        for key, label, hits in ambiguous:
            OUT.write("  %-22s %s\n" % (key, label))
            for f in hits:
                OUT.write("        %s\n" % f["path"])
        OUT.write("\n")
    if orphans:
        OUT.write("--- Drive files nothing in the register wants ---\n")
        for f in sorted(orphans, key=lambda x: x["path"]):
            OUT.write("  %-22s %s\n" % (keys[f["path"]], f["path"]))

    json.dump({k: {"id": v["id"], "path": v["path"]} for k, v in matched.items()},
              open("_matched.json", "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)


if __name__ == "__main__":
    main()
