"""Write the certification review as a workbook people can filter and send on."""
import io
import json
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = json.load(io.open(os.path.join(HERE, "audit", "_certs_final.json"),
                         encoding="utf-8"))

COLS = [
    ("Item", "code", 10),
    ("Group", "group", 8),
    ("Type", "type", 20),
    ("Description", "title", 52),
    ("Manufacturer", "manufacturer", 18),
    ("CE", "ce", 12),
    ("UL / NRTL", "nrtl", 34),
    ("Marks on the sheet", "marks", 52),
    ("Where the evidence is", "evidence", 40),
    ("How established", "how", 20),
    ("What to do / watch", "note", 70),
    ("Datasheet", "drive_url", 16),
]

INK = "1C2530"
HEAD = PatternFill("solid", fgColor="1C2530")
GOOD = PatternFill("solid", fgColor="E9F5EE")
WARN = PatternFill("solid", fgColor="FCF1E2")
BAD = PatternFill("solid", fgColor="FBEDEC")
NA = PatternFill("solid", fgColor="F2F3F5")
THIN = Side(style="thin", color="D8DEE6")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def tone(r):
    """Green where a body has listed it, red where nothing is stated."""
    if r["ce"] == "n/a":
        return NA
    stated_n = r["nrtl"] not in ("Not stated", "Not checked") and "PENDING" not in r["nrtl"]
    stated_e = r["ce"] == "Yes"
    if "PENDING" in r["nrtl"]:
        return BAD
    if stated_n and stated_e:
        return GOOD
    if stated_n or stated_e:
        return WARN
    return BAD


wb = Workbook()
ws = wb.active
ws.title = "Lighting certification"

TITLE = ("GP1-MUR lighting - CE and UL/NRTL review, read off the submitted datasheets")
ws.cell(1, 1, TITLE).font = Font(bold=True, size=13, color=INK)
ws.cell(2, 1, "A standard quoted in a spec is not a listing. Where a sheet only says "
              "\"designed to UL8750\" or \"CSA C22.2\", this reads Not stated. Most marks "
              "are logos, not words, so every row marked \"Read by eye\" was checked on the "
              "rendered page. Checked 30 Sep 2026.").font = Font(size=10, color="5A6675")
ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(COLS))
ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(COLS))
ws.row_dimensions[2].height = 30
ws.cell(2, 1).alignment = Alignment(wrap_text=True, vertical="center")

HR = 4
for i, (label, _, w) in enumerate(COLS, start=1):
    c = ws.cell(HR, i, label)
    c.fill = HEAD
    c.font = Font(bold=True, color="FFFFFF", size=10)
    c.alignment = Alignment(vertical="center", wrap_text=True)
    c.border = BOX
    ws.column_dimensions[get_column_letter(i)].width = w
ws.row_dimensions[HR].height = 26

for n, r in enumerate(ROWS, start=HR + 1):
    fill = tone(r)
    for i, (label, key, _) in enumerate(COLS, start=1):
        v = r.get(key, "")
        c = ws.cell(n, i, v)
        c.border = BOX
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.font = Font(size=10)
        if key in ("ce", "nrtl", "code"):
            c.fill = fill
        if key == "code":
            c.font = Font(size=10, bold=True)
        if key == "drive_url" and v:
            c.value = "Open"
            c.hyperlink = v
            c.font = Font(size=10, color="1155CC", underline="single")

ws.freeze_panes = ws.cell(HR + 1, 4)
ws.auto_filter.ref = "A%d:%s%d" % (HR, get_column_letter(len(COLS)), HR + len(ROWS))

# ---- a second sheet holding the key, so the colours are not folklore ----
k = wb.create_sheet("How to read it")
notes = [
    ("Column", "What it means"),
    ("CE", "Yes = a CE mark or an EU/UKCA declaration appears on the sheet. "
           "Not stated = it does not, which is not the same as 'not CE marked'."),
    ("UL / NRTL", "A Nationally Recognized Testing Laboratory listing: UL, ETL (Intertek) "
                  "or CSA. Only a LISTING counts here. cURus = Recognized Component, "
                  "which is valid only inside other listed equipment."),
    ("Green", "Both a CE/EU mark and an NRTL listing are stated."),
    ("Amber", "One of the two is stated."),
    ("Red", "Neither is stated, or a listing is marked pending."),
    ("Grey", "Not an electrical product - a bare extrusion carries no listing."),
    ("", ""),
    ("Two traps this review was built to avoid", ""),
    ("A standard is not a listing",
     "\"Standards compliance: CSA C22.2 no. 223\" and \"Safety standards ... UL8750 UL1310\" "
     "say what a product was designed to. Anyone may write that. A listing is a body saying "
     "it tested the thing, and it comes with a mark and usually a file number."),
    ("The marks are pictures",
     "Most of these sheets carry their marks as logos, so searching the text finds nothing "
     "on a sheet that plainly shows CE and UL. Rows marked 'Read by eye' were checked on "
     "the rendered page."),
]
for i, (a, b) in enumerate(notes, start=1):
    ca, cb = k.cell(i, 1, a), k.cell(i, 2, b)
    ca.font = Font(bold=True, size=10, color=INK)
    cb.font = Font(size=10)
    cb.alignment = Alignment(wrap_text=True, vertical="top")
k.column_dimensions["A"].width = 34
k.column_dimensions["B"].width = 96

out = os.path.join(HERE, "audit", "GP1-MUR lighting certification review.xlsx")
wb.save(out)
print("wrote", out, "-", len(ROWS), "rows")
