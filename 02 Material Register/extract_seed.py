#!/usr/bin/env python3
"""
GP1-MUR Material & Hardware Register - seed extractor.

Reads the master procurement workbook and emits seed.json: one flat, typed
item list that the web register renders from and that maps 1:1 onto the
Supabase `register_item` table.

Python 3.12 standard library only (openpyxl is not installed here).

Rules that matter - getting any of these wrong corrupts the data silently:
  * Sheets are resolved through xl/_rels/workbook.xml.rels, NOT by sheetN.xml
    filename order; those do not necessarily match tab order.
  * Never decode XML manually. zipfile returns bytes; ElementTree reads the
    declaration and decodes UTF-8 itself. A manual .decode() under the Windows
    codepage is where mojibake comes from.
  * A shared string <si> may be split into formatting runs; concatenate every
    descendant <t> in document order.
  * Empty cells are ABSENT from the XML, so a column is read from the cell's
    own @r reference, never from its index within the row.

Usage:
    python extract_seed.py            # write seed.json
    python extract_seed.py --check F  # validate an existing seed/export file
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKBOOK = HERE.parent / "01 GP1 Procurement Tracker" / (
    "GP1-MUR Procurement Tracker - MASTER (By Discipline).xlsx"
)
OUT = HERE / "seed.json"

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# The 14 labels every discipline sheet carries on row 4.
EXPECTED_HEADER = [
    "#", "Sub-Category", "Code / Tag", "Item / Description", "Location / Zone",
    "Manufacturer / Brand", "Model / SKU", "Qty", "Unit", "Spec Ref",
    "Spec Sheet", "Approved", "Procured", "Notes",
]

C_SUBCAT, C_CODE, C_ITEM, C_LOC = 1, 2, 3, 4
C_MFR, C_MODEL, C_QTY, C_UNIT = 5, 6, 7, 8
C_SPECREF, C_SPECSTATUS, C_APPROVED, C_PROCURED, C_NOTES = 9, 10, 11, 12, 13

HEADER_ROW = 4

# Per-discipline row counts, from the workbook's own Contents sheet.
EXPECTED_COUNTS = {
    "01": 4, "02": 7, "03": 16, "04": 9, "05": 40, "06": 9, "07": 1,
    "08": 5, "09": 34, "10": 14, "11": 1, "12": 42, "13": 17,
}
EXPECTED_TOTAL = 199
EXPECTED_SPEC_URLS = 15

STATUS_TOKENS = {
    "complete": "complete",
    "in progress": "in_progress",
    "not started": "not_started",
}

URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)


def die(msg):
    print("FAIL: " + msg, file=sys.stderr)
    raise SystemExit(1)


# --------------------------------------------------------------------------
# workbook plumbing
# --------------------------------------------------------------------------

def col_index(ref):
    """'D12' -> 3. Zero-based column index from a cell reference."""
    m = re.match(r"([A-Z]+)", ref or "")
    if not m:
        die("cell has no column in its reference: %r" % (ref,))
    n = 0
    for ch in m.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def load_shared_strings(zf):
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    # Concatenate every descendant <t>: Excel splits hand-edited text into <r>
    # formatting runs, and taking only the first would drop content.
    return ["".join(t.text or "" for t in si.iter(M + "t"))
            for si in root.findall(M + "si")]


def resolve_sheets(zf):
    """[(tab name, 'xl/worksheets/sheetN.xml')] in tab order, resolved via rels."""
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    targets = {r.get("Id"): r.get("Target") for r in rels}
    out = []
    for s in wb.iter(M + "sheet"):
        target = targets[s.get(REL + "id")]
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        out.append((s.get("name"), target))
    return out


def cell_value(c, shared):
    t = c.get("t")
    if t == "s":
        v = c.find(M + "v")
        return shared[int(v.text)] if v is not None else ""
    if t == "inlineStr":
        is_el = c.find(M + "is")
        if is_el is None:
            return ""
        return "".join(x.text or "" for x in is_el.iter(M + "t"))
    if t == "e":
        return ""  # error cell reads as empty
    v = c.find(M + "v")
    if v is None or v.text is None:
        return ""
    if t == "b":
        return "TRUE" if v.text == "1" else "FALSE"
    return v.text


def read_rows(zf, target, shared):
    """{row number: {column index: cleaned text}} - absent cells stay absent."""
    root = ET.fromstring(zf.read(target))
    rows = {}
    for row in root.iter(M + "row"):
        cells = {}
        for c in row.findall(M + "c"):
            val = clean(cell_value(c, shared))
            if val:
                cells[col_index(c.get("r"))] = val
        rows[int(row.get("r"))] = cells
    return rows


# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------

def clean(s):
    """NFC, no non-breaking spaces, collapsed whitespace, trimmed.

    Em dashes and degree signs are correct content and are kept as-is.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = s.replace(chr(0x00A0), " ")  # non-breaking space -> space
    return re.sub(r"\s+", " ", s).strip()


def split_spec_ref(raw):
    """'Spec Ref' carries two unrelated things. -> (spec_url, drawing_ref)."""
    if not raw:
        return "", ""
    m = URL_RE.search(raw)
    if not m:
        return "", raw
    url = m.group(0).rstrip(".,;)")
    if url.lower().startswith("www."):
        url = "https://" + url
    return url, clean(raw[:m.start()] + " " + raw[m.end():])


def status_token(raw, default):
    key = clean(raw).lower()
    if not key:
        return default
    return STATUS_TOKENS.get(key, "unknown")


def parse_qty(raw):
    if not raw:
        return None, None
    try:
        f = float(raw)
    except ValueError:
        return None, raw
    return (int(f) if f.is_integer() else f), None


def make_id(sheet, row):
    """Deterministic identity, so re-running reproduces the same ids."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "gp1:%s:%d" % (sheet, row)))


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def extract_items():
    if not WORKBOOK.exists():
        die("workbook not found: %s" % WORKBOOK)

    items = []
    seq = 0

    with zipfile.ZipFile(WORKBOOK) as zf:
        shared = load_shared_strings(zf)

        for name, target in resolve_sheets(zf):
            m = re.match(r"^(\d{2})\s+(.*)$", name)
            if not m:
                continue  # Contents, and anything else without an NN prefix
            code, discipline = m.group(1), m.group(2)

            rows = read_rows(zf, target, shared)

            header = rows.get(HEADER_ROW, {})
            got = [header.get(i, "") for i in range(len(EXPECTED_HEADER))]
            if got != EXPECTED_HEADER:
                die("%s: row %d header mismatch\n  expected %s\n  got      %s"
                    % (name, HEADER_ROW, EXPECTED_HEADER, got))

            for rnum in sorted(r for r in rows if r > HEADER_ROW):
                cells = rows[rnum]
                item_text = cells.get(C_ITEM, "")
                code_tag = cells.get(C_CODE, "")
                if not item_text and not code_tag:
                    continue  # spacer or trailing formatting row

                spec_url, drawing_ref = split_spec_ref(cells.get(C_SPECREF, ""))
                qty, qty_raw = parse_qty(cells.get(C_QTY, ""))
                seq += 1

                items.append({
                    "id": make_id(name, rnum),
                    "seq": seq,
                    "discipline_code": code,
                    "discipline": discipline,
                    "sub_category": cells.get(C_SUBCAT, ""),
                    "code_tag": code_tag,
                    "code_new": None,
                    "item": item_text,
                    "location": cells.get(C_LOC, ""),
                    "manufacturer": cells.get(C_MFR, ""),
                    "model": cells.get(C_MODEL, ""),
                    "qty": qty,
                    "qty_raw": qty_raw,
                    "unit": cells.get(C_UNIT, ""),
                    "drawing_ref": drawing_ref,
                    "spec_url": spec_url,
                    "folder_url": "",
                    "spec_status": status_token(cells.get(C_SPECSTATUS, ""), "unknown"),
                    "approved": status_token(cells.get(C_APPROVED, ""), "not_started"),
                    "procured": status_token(cells.get(C_PROCURED, ""), "not_started"),
                    "notes": cells.get(C_NOTES, ""),
                    "source_sheet": name,
                    "source_row": rnum,
                })

    return items


def envelope(items):
    return {
        "schema": 1,
        "meta": {
            "project": "GP1-MUR",
            "title": "Material & Hardware Register",
            "rev": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": WORKBOOK.name,
            "seed_notes": (
                "Approved and Procured were unpopulated in the source workbook "
                "except on 17 HVAC rows (all 'Not Started'); every item is seeded "
                "as not_started. 'Spec Ref' carried both drawing references and "
                "datasheet URLs and has been split into drawing_ref and spec_url. "
                "code_tag is verbatim from the workbook and is NOT unique - "
                "identity is the uuid5 id."
            ),
        },
        "items": items,
    }


# --------------------------------------------------------------------------
# validation - the gate; nothing is written unless every check passes
# --------------------------------------------------------------------------

def validate(items, expect_urls=EXPECTED_SPEC_URLS):
    problems = []

    if len(items) != EXPECTED_TOTAL:
        problems.append("expected %d items, got %d" % (EXPECTED_TOTAL, len(items)))

    counts = {}
    for it in items:
        counts[it["discipline_code"]] = counts.get(it["discipline_code"], 0) + 1
    for code in sorted(EXPECTED_COUNTS):
        got = counts.get(code, 0)
        if got != EXPECTED_COUNTS[code]:
            problems.append("discipline %s: expected %d items, got %d"
                            % (code, EXPECTED_COUNTS[code], got))
    for code in sorted(counts):
        if code not in EXPECTED_COUNTS:
            problems.append("unexpected discipline %s" % code)

    if expect_urls is not None:
        n = sum(1 for it in items if it["spec_url"])
        if n != expect_urls:
            problems.append("expected %d spec_url values, got %d" % (expect_urls, n))

    for it in items:
        for k, v in it.items():
            if not isinstance(v, str):
                continue
            if chr(0xFFFD) in v:  # replacement char = the decode went wrong
                problems.append("item %s field %s: U+FFFD (mojibake)" % (it["seq"], k))
            if "</script" in v.lower():
                problems.append("item %s field %s: contains '</script'" % (it["seq"], k))

    ids = [it["id"] for it in items]
    if len(set(ids)) != len(ids):
        problems.append("duplicate item ids")

    if problems:
        die("validation failed:\n  - " + "\n  - ".join(problems))


def report(items):
    n_url = sum(1 for it in items if it["spec_url"])
    n_folder = sum(1 for it in items if it["folder_url"])
    n_mfr = sum(1 for it in items if it["manufacturer"])
    n_model = sum(1 for it in items if it["model"])
    print("%d items across %d disciplines" % (
        len(items), len({it["discipline_code"] for it in items})))
    print("  datasheet URLs : %d" % n_url)
    print("  drive folders  : %d" % n_folder)
    print("  manufacturer   : %d" % n_mfr)
    print("  model / SKU    : %d" % n_model)
    print("  documented     : %d / %d" % (
        sum(1 for it in items if it["spec_url"] or it["folder_url"]), len(items)))


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if len(argv) > 2 and argv[1] == "--check":
        data = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        items = data["items"] if isinstance(data, dict) else data
        validate(items, expect_urls=None)
        print("OK: %s" % argv[2])
        report(items)
        return

    items = extract_items()
    validate(items)
    OUT.write_text(
        json.dumps(envelope(items), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("OK: wrote %s" % OUT.name)
    report(items)


if __name__ == "__main__":
    main(sys.argv)
