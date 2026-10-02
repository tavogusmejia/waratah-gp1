"""The curated content for the Lutron items, and the spec file that builds them.

Twenty-nine of the register's forty-five uncurated items are Lutron, and until
now each one entered as its own FILENAME - "LTRN25.2 - DS - Lutron QS Link
Shading Power Supply - QSPS-P1-1-35V" - with no specs behind it. That is how
three pairs came to look like duplicates: you cannot tell whether two items are
the same product when both are a PDF name.

Every figure here was read off Lutron's own sheet, in context. Where one sheet
covers a family - and most of these do - the entry carries the line for THIS
model, not the family's range, because the range is what made them
indistinguishable in the first place.

WHAT THE THREE "DUPLICATE" PAIRS ACTUALLY ARE, now that they can be read:

  LTRN25.2 / LTRN26.1  The same power supply, correctly listed twice. Its own
      sheet says it powers "any one Lutron QS window treatment drive", and
      there are two drives on this job - the roller shade and the drapery
      track. Two drives, two power supplies. Not a duplicate.

  LTRN7 / LTRN8  One sheet covers the 1-, 2- and 3-column Alisse keypad, and
      the power figures differ per column count. Different products.

  LTRN19 / LTRN20  One "New Architectural Accessories" sheet covers the whole
      receptacle family. LTR-15-CCTR is USB Type C + C; LTR-15-TR is a duplex.
      Different products.

    python tools/lutron_specs.py > _ltrn.json
    python tools/make_curated.py _ltrn.json --out <dir>
"""
import io
import json
import sys
from pathlib import Path

SRC = (r"C:\Users\gus\Documents\Claude Projects\JANU\04 Project Documents"
       r"\03 Datasheets\GP1 Datasheets\L - Lighting\LTRN - Lutron Lighting")

# code: (manufacturer, title, [(label, value)...], notes)
L = {
"LTRN7": ("Lutron", "Wired Keypad, 1 column - Alisse HW-NW-KP-S1-E", [
    ("Model", "HW-NW-KP-S1-E"),
    ("System", "HomeWorks wired, QS link"),
    ("Supply", "24-36 V\u2393, 30 mA per base unit"),
    ("Power consumption", "370 mW at 24 V\u2393 (keypad + base)"),
    ("QS link load", "1 device, 1 power draw unit per base"),
    ("Wiring", "SELV / PELV / NEC Class 2"),
    ("Backbox", "Square 75 x 75 x 35 mm, or round 68 mm dia x 35 mm"),
    ("Environment", "0 \u00b0C to 40 \u00b0C, 0-90% RH, indoor only"),
    ("Approvals", "cULus, CE, NOM, FCC, ICES-003, RoHS; ADA compliant"),
    ("Fixture tag", "FIX-18-27")],
    "Shares one datasheet with LTRN8. The sheet covers the 1-, 2- and "
    "3-column keypad; this is the 1-column, and the power figure above is "
    "the one for that column count."),

"LTRN8": ("Lutron", "Wired Keypad, 2 column - Alisse HW-NW-KP-S2-E", [
    ("Model", "HW-NW-KP-S2-E"),
    ("System", "HomeWorks wired, QS link"),
    ("Supply", "24-36 V\u2393, 30 mA per base unit"),
    ("Power consumption", "449 mW at 24 V\u2393 (keypad + base)"),
    ("QS link load", "1 device, 1 power draw unit per base"),
    ("Wiring", "SELV / PELV / NEC Class 2"),
    ("Backbox", "Square 75 x 75 x 35 mm, or round 68 mm dia x 35 mm"),
    ("Environment", "0 \u00b0C to 40 \u00b0C, 0-90% RH, indoor only"),
    ("Approvals", "cULus, CE, NOM, FCC, ICES-003, RoHS; ADA compliant"),
    ("Fixture tag", "FIX-18-27")],
    "Shares one datasheet with LTRN7. Two columns rather than one, which is "
    "the 449 mW figure above against LTRN7's 370 mW."),

"LTRN19": ("Lutron", "USB Receptacle, Type C + C - Palladiom LTR-15-CCTR-BL", [
    ("Model", "LTR-15-CCTR-BL"),
    ("Type", "15 A, USB Type C + C receptacle"),
    ("Supply", "125 V~ only (US-style wallbox)"),
    ("Protection", "Tamper resistant"),
    ("Installation", "Side or back wire"),
    ("Finish", "Black plastic receptacle, behind a new architectural faceplate"),
    ("Compatibility", "New architectural faceplates only; gangs with "
                      "Palladiom keypads"),
    ("Document", "Lutron 369921p, New Architectural Accessories")],
    "Shares one datasheet with LTRN20. That sheet covers the whole receptacle "
    "family - 15 A duplex, 15 A USB A+C, 15 A USB C+C and 20 A duplex - and "
    "this is the USB Type C + C. For a GFCI version see Lutron application "
    "note 681."),

"LTRN20": ("Lutron", "Architectural Receptacle, 15 A - Palladiom LTR-15-TR-BL", [
    ("Model", "LTR-15-TR-BL"),
    ("Type", "15 A duplex receptacle"),
    ("Supply", "125 V~ only (US-style wallbox)"),
    ("Protection", "Tamper resistant"),
    ("Installation", "Side or back wire"),
    ("Finish", "Black plastic receptacle, behind a new architectural faceplate"),
    ("Compatibility", "New architectural faceplates only; gangs with "
                      "Palladiom keypads"),
    ("Document", "Lutron 369921p, New Architectural Accessories")],
    "Shares one datasheet with LTRN19. A plain duplex rather than the USB "
    "version."),

"LTRN25.2": ("Lutron", "QS Link Plug-In Power Supply - QSPS-P1-1-35V", [
    ("Model", "QSPS-P1-1-35V"),
    ("Input", "120-240 V~, 50/60 Hz, 1.2 A"),
    ("Output", "35 V\u2393, 0.143 A, 5 W"),
    ("Capacity", "One QS window treatment drive, or up to 8 QS PDUs"),
    ("Input wiring", "AC cord with IEC C13 connector, 1.83 m supplied"),
    ("Output wiring", "0.5-4.0 mm\u00b2 solid or stranded, 6 mm strip"),
    ("Environment", "0 \u00b0C to 40 \u00b0C, 0-90% RH, indoor only; not for plenum"),
    ("Approvals", "cULus Listed, CE, NOM, FCC, CCC, PSE; DOE Level VI"),
    ("Serves", "LTRN25 - Sivoia QS roller shade")],
    "NOT A DUPLICATE OF LTRN26.1, though the datasheet is the same file. "
    "The supply powers ANY ONE window treatment drive, and this job has two "
    "- the roller shade and the drapery track - so two are required, one per "
    "drive."),

"LTRN26.1": ("Lutron", "QS Link Plug-In Power Supply - QSPS-P1-1-35V", [
    ("Model", "QSPS-P1-1-35V"),
    ("Input", "120-240 V~, 50/60 Hz, 1.2 A"),
    ("Output", "35 V\u2393, 0.143 A, 5 W"),
    ("Capacity", "One QS window treatment drive, or up to 8 QS PDUs"),
    ("Input wiring", "AC cord with IEC C13 connector, 1.83 m supplied"),
    ("Output wiring", "0.5-4.0 mm\u00b2 solid or stranded, 6 mm strip"),
    ("Environment", "0 \u00b0C to 40 \u00b0C, 0-90% RH, indoor only; not for plenum"),
    ("Approvals", "cULus Listed, CE, NOM, FCC, CCC, PSE; DOE Level VI"),
    ("Serves", "LTRN26 - Sivoia drapery track D145")],
    "The same product as LTRN25.2 and correctly listed twice: one supply per "
    "window treatment drive, and there are two drives on this job."),
}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:                                        # noqa: BLE001
        pass
    root = Path(SRC)
    out = []
    missing = []
    for code, (maker, title, rows, notes) in L.items():
        hits = sorted(root.glob(code + " - *.pdf"))
        # "LTRN2 - ..." must not match "LTRN25 - ..."
        hits = [h for h in hits if h.name.split(" - ")[0] == code]
        if not hits:
            missing.append(code)
            continue
        out.append({
            "code": code, "manufacturer": maker, "title": title,
            "specs": [{"label": a, "value": b} for a, b in rows],
            "notes": notes, "source": hits[0].name,
            "filename": hits[0].name,
        })
    if missing:
        sys.stderr.write("no source PDF for: %s\n" % ", ".join(missing))
    # The shape make_curated.py reads: a root plus the items, not a
    # bare list.
    json.dump({"source_root": SRC, "items": out}, sys.stdout,
              ensure_ascii=False, indent=1)
    sys.stderr.write("%d entries\n" % len(out))


if __name__ == "__main__":
    main()
