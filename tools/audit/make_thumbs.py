"""Inline thumbnails of every item picture, for the review grid.

The audit page is served from claude.ai, so a relative "img/x.webp" resolves
to nothing - two cards in the older builds carried exactly that and showed a
broken image. Everything shown in the artifact has to travel inside it, so
each picture is shrunk to a review size and written as a data URI.
"""
import base64, io, json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
WIDE = 260                      # enough to judge a product shot at a glance


def thumb(path):
    im = Image.open(path).convert("RGB")
    if im.width > WIDE:
        im = im.resize((WIDE, round(im.height * WIDE / im.width)),
                       Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=72, method=5)
    return ("data:image/webp;base64,"
            + base64.b64encode(buf.getvalue()).decode("ascii"))


def main():
    items = json.loads((REPO / "web/data/datasheets.json")
                       .read_text(encoding="utf-8"))["items"]
    out, total = {}, 0
    for it in items:
        if not it.get("image"):
            continue
        p = REPO / "web" / it["image"]
        if not p.exists():
            continue
        slug = it["pdf"].split("/")[-1].rsplit(".", 1)[0]
        out[slug] = thumb(p)
        total += len(out[slug])
    (HERE / "thumbs.json").write_text(
        json.dumps(out, indent=0), encoding="utf-8")
    print("%d thumbnails, %.1f MB inline" % (len(out), total / 1048576))


if __name__ == "__main__":
    main()
