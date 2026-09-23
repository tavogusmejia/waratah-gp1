"""Draw a curated summary page and put the manufacturer's sheet behind it.

The register's item pages are read off these summary pages, so a datasheet
without one enters the register as a raw filename with no specs. This builds
one that matches the existing template exactly - measured off
"A1 - Cartridge Filter (Clean & Clear CC150).pdf" and
"A - Pool Light L09 (CW16005DI).pdf", which are the two shapes in use.

    python tools/make_curated.py <spec.json> [--out DIR]

Each entry: code, manufacturer, title, specs [{label, value}], notes, source.
"""
import io, json, sys
from pathlib import Path

import fitz

REPO = Path(__file__).resolve().parent.parent

# The template's palette, read back off the existing sheets rather than
# guessed: the extractor keys on these exact values to find each field.
ORANGE = (156 / 255, 90 / 255, 0)          # 10245888 - manufacturer
NAVY = (31 / 255, 58 / 255, 100 / 255)     # 2046052  - code, title, labels
BLACK = (0, 0, 0)                          #          - values

PAGE = (612, 792)
X_MAKER, Y_MAKER, S_MAKER = 75.6, 51.5, 9.5
X_CODE_R, Y_CODE, S_CODE = 535.5, 51.4, 12.0      # right-aligned
X_TITLE, Y_TITLE, S_TITLE = 56.4, 92.2, 14.0
X_LABEL, X_VALUE, Y_SPEC, S_SPEC = 81.6, 218.4, 118.6, 8.5
ROW, WRAP = 17.0, 11.0                             # row pitch, wrapped line
X_NOTEH, S_NOTEH = 56.4, 9.5
X_NOTE = 83.6
VALUE_W = 612 - 56.4 - X_VALUE                     # room before the margin

HELV = fitz.Font("helv")
HEBO = fitz.Font("hebo")


def baseline(top, size):
    """The template was measured from the top of each line; fitz draws from
    the baseline."""
    return top + HELV.ascender * size


def wrapped(text, size, width):
    """The value column wraps rather than running off the page - the pool
    light's luminaire line does exactly that in the original."""
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if HELV.text_length(trial, size) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw(page, rec):
    def put(x, y, text, size, colour, bold=False):
        page.insert_text((x, y), text, fontname="hebo" if bold else "helv",
                         fontsize=size, color=colour)

    if rec.get("manufacturer"):
        put(X_MAKER, baseline(Y_MAKER, S_MAKER), rec["manufacturer"],
            S_MAKER, ORANGE, True)
    code = rec["code"]
    put(X_CODE_R - HEBO.text_length(code, S_CODE), baseline(Y_CODE, S_CODE),
        code, S_CODE, NAVY, True)
    put(X_TITLE, baseline(Y_TITLE, S_TITLE), rec["title"], S_TITLE, NAVY, True)

    y = Y_SPEC
    for spec in rec.get("specs", []):
        put(X_LABEL, baseline(y, S_SPEC), spec["label"], S_SPEC, NAVY, True)
        lines = wrapped(spec["value"], S_SPEC, VALUE_W)
        for i, line in enumerate(lines):
            put(X_VALUE, baseline(y + i * WRAP, S_SPEC), line, S_SPEC, BLACK)
        y += ROW + (len(lines) - 1) * WRAP

    if rec.get("notes"):
        y += 2.9
        put(X_NOTEH, baseline(y, S_NOTEH), "Notes", S_NOTEH, NAVY, True)
        y += 21.1
        for line in wrapped(rec["notes"], S_SPEC, 612 - 56.4 - X_NOTE):
            put(X_NOTE, baseline(y, S_SPEC), line, S_SPEC, BLACK)
            y += WRAP


def build(rec, out_dir, source_root):
    doc = fitz.open()
    doc.new_page(width=PAGE[0], height=PAGE[1])
    draw(doc[0], rec)
    src = Path(source_root) / rec["source"]
    if not src.exists():
        raise SystemExit("manufacturer sheet missing: " + str(src))
    doc.insert_pdf(fitz.open(src))
    dest = Path(out_dir) / rec["filename"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc.save(dest, garbage=3, deflate=True)
    doc.close()
    return dest


def main():
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_dir = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else REPO / "_curated"
    root = spec["source_root"]
    log = io.open(1, "w", encoding="utf-8", closefd=False)
    for rec in spec["items"]:
        dest = build(rec, out_dir, root)
        log.write("  %-10s %7.0f KB  %s\n"
                  % (rec["code"], dest.stat().st_size / 1024, dest.name[:62]))
    log.write("%d sheets -> %s\n" % (len(spec["items"]), out_dir))


if __name__ == "__main__":
    main()
