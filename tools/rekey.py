"""Move every lookup table from filename slugs to item codes.

Four renames this week detached pictures, manufacturer links and Drive URLs
from their items, each time in silence, because everything was keyed on a
slug derived from the filename. The code is what the folders are organised
by and what gets fixed when the numbering changes, so the code is the key.

This carries the existing tables across. It never guesses: a slug is only
followed to a code when the two describe the same thing, and every pairing -
and every refusal - is printed. DH9 was the Reflect weatherstrip and is now
the Assa Abloy drop seal; a bare code match put one item's photograph on the
other earlier this week, and this is the check that stops that.
"""
import csv, io, json, os, re, sys, unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
from extract_datasheets import slug                     # noqa: E402

OUT = io.open(1, "w", encoding="utf-8", closefd=False)
STOP = {"ds", "ig", "note", "the", "and", "for", "in", "of"}


def words(s):
    """The descriptive tokens of a slug, without its leading code."""
    parts = s.split("-")[1:]
    return {w for w in parts if w and not w.isdigit() and w not in STOP}


def agrees(old, new):
    """Do two slugs describe the same product? Renames insert and reorder
    tokens, so this asks for overlap rather than equality."""
    a, b = words(old), words(new)
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= 0.5


def load_items():
    d = json.loads((REPO / "web/data/datasheets.json").read_text(encoding="utf-8"))
    rows = []
    for it in d["items"]:
        rows.append({"key": it["key"],
                     "slug": it["pdf"].split("/")[-1].rsplit(".", 1)[0],
                     "code": it["code"], "group": it["group"],
                     "title": it["title"]})
        for x in it.get("extras", []):
            rows.append({"key": x["key"],
                         "slug": x["pdf"].split("/")[-1].rsplit(".", 1)[0],
                         "code": it["code"], "group": it["group"],
                         "title": it["title"] + " (" + x["kind"] + ")"})
    return rows


def resolve(old_key, rows):
    """The item an old slug-or-code key belongs to, or None with a reason."""
    byslug = {r["slug"]: r for r in rows}
    if old_key in byslug:
        return byslug[old_key], "exact slug"
    bykey = {r["key"]: r for r in rows}
    if old_key in bykey:
        return bykey[old_key], "already a key"
    m = re.match(r"^([a-z&]+[0-9]*(?:-[0-9]+)?)-", old_key)
    if not m:
        return None, "no code in the name"
    stem = m.group(1)
    hits = [r for r in rows if slug(r["code"]) == stem
            or slug(r["group"] + "-" + r["code"]) == stem]
    hits = [r for r in hits if agrees(old_key, r["slug"])]
    if len(hits) == 1:
        return hits[0], "code + description"
    if not hits:
        return None, "no item with that code describes the same thing"
    return None, "%d items share that code" % len(hits)


def main():
    rows = load_items()
    OUT.write("%d items and attachments\n\n" % len(rows))
    plan = {"images": [], "csv": {}, "db": {}}

    # ---- picture overrides ----
    OUT.write("=== tools/images ===\n")
    d = REPO / "tools/images"
    for f in sorted(os.listdir(d)):
        stem, ext = os.path.splitext(f)
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        r, why = resolve(stem, rows)
        want = slug(r["key"]) + ext if r else None
        if r is None:
            OUT.write("  KEEP    %-58s %s\n" % (stem, why))
        elif want == f:
            OUT.write("  ok      %s\n" % stem)
        else:
            plan["images"].append((f, want))
            OUT.write("  ->      %-58s %-22s (%s)\n"
                      % (stem, slug(r["key"]), why))

    # ---- the two link tables ----
    for name in ("drive-links.csv", "maker-links.csv"):
        OUT.write("\n=== tools/%s ===\n" % name)
        out, kept, moved, lost = [], 0, 0, []
        for row in csv.reader(io.open(REPO / "tools" / name,
                                      encoding="utf-8-sig", newline="")):
            if len(row) < 2 or not row[1].lower().startswith("http"):
                continue
            r, why = resolve(row[0], rows)
            if r is None:
                lost.append((row[0], why))
                continue
            out.append([r["key"], row[1]])
            if r["key"] == row[0]:
                kept += 1
            else:
                moved += 1
        plan["csv"][name] = out
        OUT.write("  %d rows: %d already keyed, %d carried across\n"
                  % (len(out), kept, moved))
        for k, why in lost:
            OUT.write("  DROPPED %-58s %s\n" % (k, why))

    # ---- the artifact database ----
    for coll in ("maker", "fixpic"):
        src = Path(sys.argv[1]) / coll if len(sys.argv) > 1 else None
        if not src or not src.is_dir():
            continue
        OUT.write("\n=== db/%s ===\n" % coll)
        writes, lost = [], []
        for f in sorted(src.glob("*.json")):
            body = json.loads(f.read_text(encoding="utf-8"))
            r, why = resolve(f.stem, rows)
            if r is None:
                lost.append((f.stem, why))
                continue
            new = slug(r["key"])
            if new != f.stem:
                writes.append({"op": "set", "collection": coll,
                               "doc_id": new, "data": body})
                writes.append({"op": "delete", "collection": coll,
                               "doc_id": f.stem})
        plan["db"][coll] = writes
        OUT.write("  %d moves (%d writes)\n" % (len(writes) // 2, len(writes)))
        for k, why in lost:
            OUT.write("  LEFT    %-58s %s\n" % (k, why))

    (REPO / "_rekey.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    OUT.write("\nplan written to _rekey.json - run with --apply to carry it out\n")

    if "--apply" in sys.argv:
        for old, new in plan["images"]:
            os.replace(d / old, d / new)
        for name, out in plan["csv"].items():
            with io.open(REPO / "tools" / name, "w", encoding="utf-8",
                         newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["key", "url"])
                w.writerows(sorted(out))
        OUT.write("applied: %d pictures renamed, %d tables rewritten\n"
                  % (len(plan["images"]), len(plan["csv"])))


if __name__ == "__main__":
    main()
