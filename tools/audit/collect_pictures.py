"""Turn pictures staged in the audit artifact into files in tools/images/.

The page stages a replacement picture one of two ways, depending on what the
viewer granted it:

    {"asset": "<id>", ...}   in the artifact's asset store
    {"data":  "data:image/jpeg;base64,...", ...}   in the row itself

The second exists because the asset store is not always there, and a page
that cannot take a picture is no use at all. Both end up in the same place:
tools/images/<item key>.jpg, which is where pick_image looks first.

    # read the staged rows into a directory
    ArtifactData list  collection "staged"  out_dir <dir>
    # then
    python tools/audit/collect_pictures.py <dir>

Rows carrying an asset id are named rather than fetched: the asset store is
reached through the Artifact tool, not from here, and printing the ids is
more use than failing halfway through.
"""
import base64, glob, io, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
IMAGES = REPO / "tools/images"
OUT = io.open(1, "w", encoding="utf-8", closefd=False)
URI = re.compile(r"^data:(image/[a-z+]+);base64,(.+)$", re.S)

EXT = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif",
       "image/webp": "webp", "image/svg+xml": "svg"}


def main(src):
    rows = sorted(glob.glob(os.path.join(src, "**", "*.json"), recursive=True))
    if not rows:
        OUT.write("no staged rows under %s\n" % src)
        return
    IMAGES.mkdir(parents=True, exist_ok=True)
    wrote, need_asset, bad = [], [], []
    for f in rows:
        slug = os.path.basename(f)[:-5]
        try:
            rec = json.load(io.open(f, encoding="utf-8"))
        except Exception as e:
            bad.append((slug, str(e)[:50]))
            continue
        # A saved document may be wrapped in its own metadata.
        rec = rec.get("data", rec) if isinstance(rec.get("data"), dict) else rec

        data = rec.get("data")
        if isinstance(data, str) and data.startswith("data:"):
            m = URI.match(data)
            if not m:
                bad.append((slug, "unreadable data uri"))
                continue
            ext = EXT.get(m.group(1), "jpg")
            raw = base64.b64decode(m.group(2))
            # The filename the page promised, so what lands matches what it
            # said would land.
            name = rec.get("filename") or (slug + "." + ext)
            (IMAGES / name).write_bytes(raw)
            wrote.append((name, len(raw)))
        elif rec.get("asset"):
            need_asset.append((slug, rec["asset"], rec.get("filename", "")))
        else:
            bad.append((slug, "neither data nor asset"))

    for name, n in sorted(wrote):
        OUT.write("  wrote  %-52s %6.1f KB\n" % (name, n / 1024))
    OUT.write("\n%d written into tools/images/\n" % len(wrote))
    if need_asset:
        OUT.write("\n%d are in the asset store - fetch each with the Artifact "
                  "tool, action read, path <id>:\n" % len(need_asset))
        for slug, aid, name in need_asset:
            OUT.write("  %-28s %s  -> %s\n" % (slug, aid, name or slug))
    if bad:
        OUT.write("\n%d could not be read:\n" % len(bad))
        for slug, why in bad:
            OUT.write("  %-28s %s\n" % (slug, why))
    if wrote:
        OUT.write("\nRe-run the extractor to pick them up:\n"
                  "  python tools/extract_datasheets.py\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        OUT.write(__doc__)
        sys.exit(2)
    main(sys.argv[1])
