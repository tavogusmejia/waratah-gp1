"""Match crawled Drive files to register items, and name everything that misses.

A wrong link is worse than a missing one, so this reports rather than guesses:
every Drive file with no home and every item with no link is printed.
"""
import json, io, sys, re
from pathlib import Path

REPO = Path(r"C:\Users\gus\Dropbox\06 Apps\Waratah-gp1")
sys.path.insert(0, str(REPO / "tools"))
from extract_datasheets import slug, SKIP           # the same normalisation

out = io.open(1, "w", encoding="utf-8", closefd=False)
drive = json.load(open("_drive.json", encoding="utf-8"))["files"]
data = json.load(open(REPO / "web/data/datasheets.json", encoding="utf-8"))
items = data["items"] if isinstance(data, dict) else data


def skipped(path):
    low = path.lower()
    return any(s.lower() in low for s in SKIP)


pdfs = [f for f in drive
        if f["name"].lower().endswith(".pdf") and not skipped(f["path"])]

# what the register wants a link for: each item, plus each attachment
wanted = {}
for it in items:
    stem = it["pdf"].split("/")[-1].rsplit(".", 1)[0]
    wanted[stem] = {"kind": "item", "code": it["code"],
                    "src": Path(it["source"]).name}
    for x in it.get("extras", []):
        xs = x["pdf"].split("/")[-1].rsplit(".", 1)[0]
        wanted[xs] = {"kind": "extra", "code": it["code"], "src": x.get("file", "")}

# Drive files keyed by the slug of their own filename
by_slug = {}
for f in pdfs:
    by_slug.setdefault(slug(f["name"].rsplit(".", 1)[0]), []).append(f)

matched, missing, ambiguous = {}, [], []
for stem, meta in wanted.items():
    keys = [slug(stem)]
    if meta["src"]:
        keys.append(slug(Path(meta["src"]).stem))
    hit = None
    for k in keys:
        if k in by_slug:
            hit = by_slug[k]
            break
    if hit is None:
        missing.append((stem, meta))
    elif len(hit) > 1:
        ambiguous.append((stem, meta, hit))
    else:
        matched[stem] = hit[0]

used = {f["id"] for f in matched.values()}
orphans = [f for f in pdfs if f["id"] not in used]

out.write("Drive PDFs outside the reference folders : %d\n" % len(pdfs))
out.write("Register needs a link for                : %d "
          "(%d items + %d attachments)\n"
          % (len(wanted),
             sum(1 for m in wanted.values() if m["kind"] == "item"),
             sum(1 for m in wanted.values() if m["kind"] == "extra")))
out.write("MATCHED                                  : %d\n" % len(matched))
out.write("NO DRIVE FILE                            : %d\n" % len(missing))
out.write("AMBIGUOUS                                : %d\n" % len(ambiguous))
out.write("Drive files with no item                 : %d\n\n" % len(orphans))

if missing:
    out.write("--- items with no Drive file ---\n")
    for stem, meta in sorted(missing, key=lambda x: x[1]["code"]):
        out.write("  %-8s %-7s %s\n" % (meta["code"], meta["kind"], stem))
    out.write("\n")
if ambiguous:
    out.write("--- more than one Drive file matches ---\n")
    for stem, meta, hit in ambiguous:
        out.write("  %-8s %s\n" % (meta["code"], stem))
        for f in hit:
            out.write("        %s\n" % f["path"])
    out.write("\n")
if orphans:
    out.write("--- Drive files nothing in the register wants ---\n")
    for f in sorted(orphans, key=lambda x: x["path"]):
        out.write("  %s\n" % f["path"])

json.dump({s: {"id": f["id"], "path": f["path"]} for s, f in matched.items()},
          open("_matched.json", "w", encoding="utf-8"), indent=1,
          ensure_ascii=False)
