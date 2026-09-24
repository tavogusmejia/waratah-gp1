"""Read the picture marks out of the artifact and say which still need work.

Marks have been written under two keyings: the filename slug, and the item
code. Rather than migrate 244 documents, this resolves them - an item's mark
is whichever of picok/fixpic carries the later timestamp, whatever key it
arrived under. New marks are written under the mark key below, so the mixed
state drains away on its own.

Run `Artifact read_db` for picok and fixpic into a directory first, then:

    python tools/audit/collect_marks.py <that directory>

It writes tools/audit/pics.json - the items still needing a better picture,
which is what the audit page renders.
"""
import glob, io, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools"))
from extract_datasheets import slug                          # noqa: E402

OUT = io.open(1, "w", encoding="utf-8", closefd=False)


def mark_keys(items):
    """One stable key per item. The item code, except where a code covers
    more than one item - P9's two insulations - where the filename slug is
    the only thing that tells them apart."""
    seen = {}
    for it in items:
        seen[it["key"]] = seen.get(it["key"], 0) + 1
    out = {}
    for it in items:
        stem = it["pdf"].split("/")[-1].rsplit(".", 1)[0]
        out[id(it)] = stem if seen[it["key"]] > 1 else slug(it["key"])
    return out


def main(src):
    data = json.loads((REPO / "web/data/datasheets.json").read_text(encoding="utf-8"))
    items = data["items"]
    mk = mark_keys(items)
    for it in items:
        it["_mk"] = mk[id(it)]

    lookup = {}
    for it in items:
        stem = it["pdf"].split("/")[-1].rsplit(".", 1)[0]
        for k in (it["_mk"], slug(it["key"]), stem):
            lookup.setdefault(k, it)

    # A mark written before a folder moved carries the old group in its key -
    # "lum-l-l12" for what is now "l-l-l-l12". The code did not move, so fall
    # back to it, and only when it names exactly one item.
    bycode = {}
    for it in items:
        bycode.setdefault(slug(it["code"]), []).append(it)
    for code, hits in bycode.items():
        if len(hits) == 1:
            lookup.setdefault(code, hits[0])
            for g in {i["group"] for i in items}:
                lookup.setdefault(slug(g + "-" + hits[0]["code"]), hits[0])

    latest, orphan = {}, []
    for coll in ("picok", "fixpic"):
        for f in glob.glob(os.path.join(src, coll, "*.json")):
            k = os.path.basename(f)[:-5]
            it = lookup.get(k)
            if it is None:
                orphan.append(coll + "/" + k)
                continue
            body = json.load(open(f, encoding="utf-8"))
            when = body.get("at", "")
            if it["_mk"] not in latest or when > latest[it["_mk"]][0]:
                latest[it["_mk"]] = (when, coll)

    # The list is everything still wanting a decision: marked for replacement,
    # or never looked at. A new item that appeared since the last pass - the
    # eight iGuzzini sheets did - otherwise shows up in no list anywhere.
    rows = []
    for it in items:
        where = latest.get(it["_mk"], ("", ""))[1]
        if where == "picok":
            continue
        rows.append({"mk": it["_mk"], "key": it["group"] + "-" + it["code"],
                     "group": it["group"], "code": it["code"],
                     "title": it["title"], "image": it.get("image", ""),
                     "seen": where == "fixpic"})
    fine = sum(1 for v in latest.values() if v[1] == "picok")
    unseen = [it["_mk"] for it in items if it["_mk"] not in latest]

    io.open(HERE / "pics.json", "w", encoding="utf-8", newline="\n").write(
        json.dumps(rows, indent=1, ensure_ascii=False))
    OUT.write("%d items: %d fine, %d need a better picture, %d not looked at\n"
              % (len(items), fine, len(rows), len(unseen)))
    if unseen:
        OUT.write("  not looked at: %s\n" % ", ".join(unseen))
    if orphan:
        OUT.write("  marks matching no item (%d): %s\n"
                  % (len(orphan), ", ".join(orphan[:6])))


if __name__ == "__main__":
    main(sys.argv[1])
