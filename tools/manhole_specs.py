"""The seven access covers on the manhole concept sheet, one item each.

"Manhole & Access Covers - Concept Sheet.pdf" is a single two-page document
covering seven different covers, which is how it was issued and the wrong
shape for a register: one entry called "Concept Sheet" says nothing about
which cover is where, and none of the seven can carry its own status, its own
note or its own approval.

So each becomes an item, with the concept-sheet page it appears on behind it.
Page 1 carries the Fortis infill run and the Electrical, Sewer and
Communications covers; page 2 carries the drainage grate and the water-valve
and HVAC-drain covers.

WHAT IS NOT KNOWN, AND SAYS SO. The sheet is issued for concept and
appearance approval only - there are no dimensions, no load tables and no
order codes on it, and inventing any would be worse than leaving them out.
Only the Fortis run names a maker. The drainage grate has no service cast
into it at all, which is a question for somebody rather than a specification.

    python tools/manhole_specs.py > _mh.json
    python tools/make_curated.py _mh.json --out "<the MH folder>"
"""
import io, json

SRC = (r"C:\Users\gus\Documents\Claude Projects\JANU\04 Project Documents"
       r"\03 Datasheets\GP1 Datasheets\M - Manholes & Tanks")
# Under "_Concept (reference)" so the extractor skips it: it is the source
# for all seven and would otherwise sit in the unfiled report forever.
SHEET = (r"MH - Manholes and Access Covers\_Concept (reference)"
         r"\Manhole & Access Covers - Concept Sheet.pdf")

CONCEPT = ("Issued for concept and appearance approval only, on 11 September "
           "2026, under JANU-SUB-008. The sheet carries no dimensions, load "
           "tables or order codes; those are to follow with the product "
           "submittal.")

# The curated-sheet parser identifies a summary page by its orange
# manufacturer line, so a sheet with none is read as a raw datasheet and its
# title, code and specs are all thrown away. Six of these name no maker, and
# the honest thing to put there is that fact - which also makes the gap
# visible in the register's manufacturer filter, where somebody has to close
# it before any of them can be ordered.
UNKNOWN = "Not stated"

ITEMS = [
 dict(code="MH1", page=1, maker="Fortis",
      file="MH1 - Recessed Infill Cover - Fortis EN 124 D400.pdf",
      title="Recessed Infill Cover - Fortis, EN 124 D400",
      specs=[("Standard", "EN 124, Class D400"),
             ("Type", "Recessed block-paviour cover, to receive the surface finish"),
             ("Legend", "Branded FORTIS"),
             ("Shown as", "A triple run"),
             ("Material", "Cast iron"),
             ("Service", "Site service chambers")],
      notes=CONCEPT),
 dict(code="MH2", page=1, maker=UNKNOWN,
      file="MH2 - Square Access Cover - Electrical.pdf",
      title="Square Access Cover - Electrical",
      specs=[("Standard", "EN 124"),
             ("Type", "Square recessed-pattern cover"),
             ("Legend", "Cast ELECTRICAL"),
             ("Material", "Cast iron"),
             ("Service", "Electrical chamber")],
      notes=CONCEPT + " No manufacturer is named on the sheet for this cover."),
 dict(code="MH3", page=1, maker=UNKNOWN,
      file="MH3 - Square Access Cover - Sewer.pdf",
      title="Square Access Cover - Sewer",
      specs=[("Standard", "EN 124"),
             ("Type", "Square recessed-pattern cover"),
             ("Legend", "Cast SEWER"),
             ("Material", "Cast iron"),
             ("Service", "Foul drainage chamber")],
      notes=CONCEPT + " No manufacturer is named on the sheet for this cover."),
 dict(code="MH4", page=1, maker=UNKNOWN,
      file="MH4 - Circular Access Cover - Communications.pdf",
      title="Circular Access Cover - Communications",
      specs=[("Standard", "EN 124"),
             ("Type", "Circular recessed-pattern cover"),
             ("Legend", "Cast COMMUNICATIONS"),
             ("Material", "Cast iron"),
             ("Service", "Communications chamber")],
      notes=CONCEPT + " No manufacturer is named on the sheet for this cover."),
 dict(code="MH5", page=2, maker=UNKNOWN,
      file="MH5 - Circular Drainage Grate - Unmarked.pdf",
      title="Circular Drainage Grate - Heavy Duty, Slotted",
      specs=[("Type", "Circular heavy-duty slotted grate"),
             ("Legend", "None - the cover is unmarked"),
             ("Material", "Cast iron"),
             ("Service", "To be confirmed")],
      notes=CONCEPT + " This grate has no service name cast into it, so what "
                      "it covers cannot be told from the cover. Confirm the "
                      "service before it is set, or specify a legend: an "
                      "unmarked grate on a finished site is a chamber nobody "
                      "can identify without opening it."),
 dict(code="MH6", page=2, maker=UNKNOWN,
      file="MH6 - Circular Access Cover with Riser - Water Valve.pdf",
      title="Circular Access Cover with Riser - Water Valve",
      specs=[("Type", "Circular access cover with riser"),
             ("Legend", "Cast Water Valve"),
             ("Material", "Cast iron"),
             ("Service", "Water valve chamber"),
             ("Shown as", "Two views - lid, and lid with riser")],
      notes=CONCEPT + " No manufacturer is named on the sheet for this cover."),
 dict(code="MH7", page=2, maker=UNKNOWN,
      file="MH7 - Circular Access Cover with Riser - HVAC Drain.pdf",
      title="Circular Access Cover with Riser - HVAC Drain",
      specs=[("Type", "Circular access cover with riser"),
             ("Legend", "Cast HVAC Drain"),
             ("Material", "Cast iron"),
             ("Service", "HVAC condensate drain chamber"),
             ("Shown as", "Two views - lid, and lid with riser")],
      notes=CONCEPT + " No manufacturer is named on the sheet for this cover."),
]


def main():
    out = []
    for it in ITEMS:
        out.append({"code": it["code"], "manufacturer": it["maker"],
                    "title": it["title"],
                    "specs": [{"label": a, "value": b} for a, b in it["specs"]],
                    "notes": it["notes"], "source": SHEET,
                    "pages": [it["page"], it["page"]],
                    "filename": "MH - Manholes and Access Covers\\" + it["file"]})
    json.dump({"source_root": SRC, "items": out},
              io.open(1, "w", encoding="utf-8", closefd=False),
              indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
