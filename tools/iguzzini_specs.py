"""The iGuzzini package, from your own schedule.

Content comes from iGuzzini_Lighting_Items_JANU_GP1_MUR.xlsx - the eight line
items, their order codes, quantities and circuits - and from its Model Notes
sheet, which carries five verification flags. Those flags belong ON the
sheets: a code that does not match a real product, or a finish that differs
from the cut sheet, is exactly what someone reads a datasheet to find out.

Three items share the Laser 25 cut sheet and four share the Laser 38 one,
because that is how iGuzzini publish them: the frame, the driver and the
fixture are one document. The projector has no cut sheet at all.

    python tools/iguzzini_specs.py > _igl.json
    python tools/make_curated.py _igl.json --out "<the iGL folder>"
"""
import io, json, sys
from pathlib import Path

SRC = (r"C:\Users\gus\Documents\Claude Projects\JANU\04 Project Documents"
       r"\03 Datasheets\GP1 Datasheets\L - Lighting")
L25 = r"LUM - Luminaires\LUM1 - DS - Recessed Downlight Ceiling 14deg DALI - L01 - Laser-25mm.pdf"
L38 = r"LUM - Luminaires\LUM2 - DS - Recessed Downlight Ceiling 26deg DALI - L02 - Laser-38mm.pdf"

ITEMS = [
 dict(code="iGL1", tag="L01", qty=13, src=L25,
      file="iGL1 - Recessed Downlight Ceiling 14deg DALI - L01 - Laser-25mm.pdf",
      title="Recessed Ceiling Downlight 14\u00b0 - iGuzzini Laser 25 Fixed Round",
      specs=[("Order code", "ILAS25RTNC-927-SCFSP-REM-31"),
             ("Quantity", "13 (all interior; circuits 1.10, 1.11, 2.1, 2.7, 2.8, 3.1, 3.2)"),
             ("Lumen output", "Up to 121 lm at 3000 K reference"),
             ("Beam", "Super Comfort fixed spot 14\u00b0, UGR < 16"),
             ("Colour temperature", "2700 K"), ("CRI", "90"), ("Power", "2 W"),
             ("Ingress", "IP20; IP43 visible parts"),
             ("Finish", "31 white / white"),
             ("Cut-out", "\u00d8 1 in (25 mm); clearance 2\u00bd in (64 mm)"),
             ("Control", "DALI, remote driver (iGL7)"),
             ("Listing", "cULus damp location, interior use only")],
      notes="Model Note 5: LD2-02 schedules circuits 2.1, 3.1 and 3.2 as L01 "
            "(8 pcs), while the control schedules on LD4-01 and LD4-03 call "
            "the same circuits surface-mounted downlights. The quantity of 13 "
            "depends on which is right. Confirm with the lighting designer."),
 dict(code="iGL2", tag="L01", qty=13, src=L25,
      file="iGL2 - Downlight Plaster Frame NC - L01 - BN-LAS25RT-NC.pdf",
      title="Laser 25 Plaster Frame, New Construction - iGuzzini BN-LAS25RT-NC",
      specs=[("Order code", "BN-LAS25RT-NC"), ("Quantity", "13"),
             ("Serves", "iGL1 - Laser 25 downlight, tag L01"),
             ("Overall", "7\u215c in x 7\u215c in (186 x 186 mm)"),
             ("Hanger bars", "14\u00bc in to 26 in (362 to 660 mm)"),
             ("Ceiling thickness", "\u215b in to 1\u215c in")],
      notes="The spec book marks this TBC by brand."),
 dict(code="iGL3", tag="L02", qty=12, src=L38,
      file="iGL3 - Recessed Downlight Ceiling 26deg DALI - L02 - Laser-38mm.pdf",
      title="Recessed Ceiling Downlight 26\u00b0 - iGuzzini Laser 38 Fixed Round, Base Output",
      specs=[("Order code", "ILAS38RTNC-BO-927-FMD-REM-02"),
             ("Quantity", "12 (10 interior + 2 exterior; circuits 1.1, 1.3, 1.9, 2.1, 2.4, 3.4)"),
             ("Lumen output", "Approx. 265 lm at 3000 K reference"),
             ("Beam", "Fixed medium 26\u00b0, UGR < 16"),
             ("Colour temperature", "2700 K"), ("CRI", "90"),
             ("Power", "4 W (4.2 W per cut sheet)"),
             ("Ingress", "IP20; IP43 under ceiling"),
             ("Finish", "02 black / black"),
             ("Cut-out", "\u00d8 1\u00bd in (38 mm); clearance 3 9/16 in (91 mm)"),
             ("Control", "DALI, remote driver (iGL8)"),
             ("Listing", "cULus damp location, interior use only")],
      notes="Two flags. Model Note 2: the spec book code ends -02 (black / "
            "black) but the received cut sheet has 01 (white / black) ticked "
            "- confirm the finish and have the cut sheet reissued. Model Note "
            "3: this is an interior-only fixture and 2 pcs are listed in the "
            "Exterior chapter - confirm they sit under a covered soffit, or "
            "reselect."),
 dict(code="iGL4", tag="L02", qty=12, src=L38,
      file="iGL4 - Downlight Plaster Frame NC - L02 - BN-LAS38RT-NC.pdf",
      title="Laser 38 Plaster Frame, New Construction - iGuzzini BN-LAS38RT-NC",
      specs=[("Order code", "BN-LAS38RT-NC"),
             ("Quantity", "12 (10 interior + 2 exterior)"),
             ("Serves", "iGL3 - Laser 38 downlight, tag L02")],
      notes="The spec book marks this TBC by brand. See also iGL5: the Laser "
            "38 takes EITHER this plaster frame OR a Chicago Plenum housing, "
            "not both."),
 dict(code="iGL5", tag="L02", qty=12, src=L38,
      file="iGL5 - Downlight Chicago Plenum Housing - L02 - BN-LAS38RT-CP.pdf",
      title="Laser 38 Chicago Plenum Housing - iGuzzini BN-LAS38RT-CP",
      specs=[("Order code", "BN-LAS38RT-CP (as written in the spec book)"),
             ("Quantity", "12 (10 interior + 2 exterior)"),
             ("Serves", "iGL3 - Laser 38 downlight, tag L02")],
      notes="Model Note 1: this code is not on the cut sheet, and it "
            "duplicates the NC frame at iGL4. iGuzzini's own documentation "
            "says the Laser 38 is installed EITHER with the NC plaster frame "
            "OR with a housing for insulated ceiling / Chicago Plenum, code "
            "BI-LAS38RT-IC/CP. Confirm whether CP is required: if not, delete "
            "this line (12 pcs); if yes, order BI-LAS38RT-IC/CP instead."),
 dict(code="iGL6", tag="L02.1", qty=4, src="",
      file="iGL6 - Recessed Projector Ceiling 24deg DALI - L02.1 - Palco 19.pdf",
      title="Recessed Ceiling Projector 24\u00b0 - iGuzzini Palco \u00d8 19 mm",
      specs=[("Order code", "IPLC-LV1-M-19-927-MD-REM-02 (as written in the spec book)"),
             ("Quantity", "4 (all interior; circuits 1.4, 1.12)"),
             ("Beam", "24\u00b0"), ("Colour temperature", "2700 K"),
             ("Power", "2 W"), ("Ingress", "IP20"), ("Finish", "Black"),
             ("Control", "DALI, remote driver"),
             ("Cut sheet", "None received")],
      notes="Model Note 4, and the reason this sheet has no manufacturer "
            "pages behind it: no cut sheet was received, and the code does "
            "not match a recessed projector. IPLC-LV1 is the Palco Low "
            "Voltage spotlight for the 48V track system - 3.4 W, about 127 lm "
            "- with no remote driver. Ask iGuzzini for the correct recessed "
            "Palco 19 code and cut sheet, and confirm whether the Laser 25 "
            "driver at iGL7 is compatible. L02.1 IS on the drawings "
            "(LD1-02, LD2-02, LD4-01, LD4-02, LD5-01)."),
 dict(code="iGL7", tag="L01", qty=10, src=L25,
      file="iGL7 - Remote DALI Driver 30W - L01 - 4450-0700-030-UNV-EDA.pdf",
      title="Remote DALI Driver, 30 W - eldoLED ECOdrive 4450-0700-030-UNV-EDA",
      specs=[("Order code", "4450-0700-030-UNV-EDA"),
             ("Quantity", "10 (8 for L01 + 2 for L02.1)"),
             ("Output", "30 W, 120-277 V"),
             ("Drives", "1 to 12 Laser 25 units"),
             ("Dimming", "DALI, down to 1%"),
             ("Max remote distance", "118 ft (36 m) on 16 AWG"),
             ("Connection box", "8 in x 8 in x 4 in (203 x 203 x 102 mm)"),
             ("Serves", "iGL1 - Laser 25 downlight, tag L01")],
      notes="The 2 pcs allocated to L02.1 are unconfirmed: this is a Laser 25 "
            "driver and the projector's own code is in question. See Model "
            "Note 4 and iGL6."),
 dict(code="iGL8", tag="L02", qty=6, src=L38,
      file="iGL8 - Remote DALI Driver 19W - L02 - 4450-0350-019-UNV-EDA.pdf",
      title="Remote DALI Driver, 19 W - eldoLED ECOdrive 4450-0350-019-UNV-EDA",
      specs=[("Order code", "4450-0350-019-UNV-EDA"),
             ("Quantity", "6 (4 interior + 2 exterior, one per L02 circuit)"),
             ("Output", "19 W, 120-277 V, indoor rated"),
             ("Drives", "1 to 4 Laser 38 base-output fixed units"),
             ("Dimming", "DALI, down to 1%"),
             ("Max remote distance", "118 ft (36 m) on 16 AWG"),
             ("Connection box", "8 in x 8 in x 4 in (203 x 203 x 102 mm)"),
             ("Serves", "iGL3 - Laser 38 downlight, tag L02")],
      notes="Indoor rated, and 2 pcs serve the exterior L02 circuits. See "
            "Model Note 3."),
]


def main():
    out = []
    for it in ITEMS:
        specs = [{"label": "Fixture tag", "value": it["tag"]}]
        specs += [{"label": a, "value": b} for a, b in it["specs"]]
        out.append({"code": it["code"], "manufacturer": "iGuzzini",
                    "title": it["title"], "specs": specs,
                    "notes": it["notes"], "source": it["src"],
                    "filename": it["file"]})
    json.dump({"source_root": SRC, "items": out},
              io.open(1, "w", encoding="utf-8", closefd=False),
              indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
