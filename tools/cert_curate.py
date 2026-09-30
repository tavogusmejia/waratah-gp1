"""Turn the raw scan into an answer a person can act on.

The automatic pass cannot be trusted on its own for two reasons, and both
appear in this set:

  A STANDARD IS NOT A LISTING. "Standards compliance: CSA C22.2 no. 223" and
  "Safety standards ... UL8750 UL1310" say what a product was DESIGNED to.
  Anyone may write that. A listing is a body saying it tested the thing, and
  it comes with a mark and usually a file number.

  THE MARKS ARE PICTURES. Most of these sheets carry their marks as logos, so
  a text search finds nothing on a sheet that plainly shows CE and UL. Every
  row below marked "logo" was read off the rendered page or the extracted
  artwork by eye.

So the verdict column is curated, the evidence column says where it came
from, and anything not established says "Not stated" rather than "No".
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# key = the code of the first item sharing that source PDF; applies to all of
# them. (ce, nrtl, marks, evidence, note)
CURATED = {
    # ---- LedFlex flexible strip. Badge strip on page 2 of each sheet. ----
    "LUM3":  ("Yes", "UL badge shown, no file number",
              "CE, UL, RoHS, LM79/80, TM66, CRI90+, IP20",
              "Badge strip, page 2 (logos)",
              "The UL badge is a bare logo with no listing wording or file number. Ask LedFlex for the UL file/report before relying on it."),
    "LUM4":  ("Yes", "UL badge shown, no file number",
              "CE, UL, RoHS, LM79/80, TM66, CRI90+, IP20",
              "Badge strip, page 2 (logos)", "As LUM3."),
    "LUM5":  ("Yes", "UL badge shown, no file number",
              "CE, UL, RoHS, LM79/80, TM66, CRI90+, IP20",
              "Badge strip, page 2 (logos)", "As LUM3."),
    "LUM6":  ("Yes", "UL badge shown, no file number",
              "CE, UL, RoHS, LM79/80, TM66, CRI90+, IP20",
              "Badge strip, page 2 (logos)", "As LUM3."),
    "LUM9":  ("Yes", "UL badge shown, no file number",
              "CE, UL, RoHS, LM79/80, IP67, CRI90+, TM66",
              "Badge strip, page 2 (logos)", "As LUM3."),

    # ---- EcoPac drivers ----
    "LUM3.1": ("Yes", "Not stated", "CE, DALI-2", "Mark strip, page 2 (logos)",
               "UK driver. CE and DALI-2 only; no NRTL mark on the sheet."),
    "LUM3.2": ("Yes", "Not stated", "CE, DALI-2", "Mark strip, page 2 (logos)", ""),
    "LUM4.1": ("Yes", "Not stated", "CE, DALI-2", "Mark strip, page 2 (logos)", ""),
    "LUM4.2": ("Yes", "Not stated", "CE, DALI-2", "Mark strip, page 2 (logos)", ""),
    "LUM5.1": ("Yes", "Not stated", "CE, DALI-2", "Mark strip, page 2 (logos)", ""),
    "LUM6.1": ("Yes", "Not stated", "CE, DALI-2", "Mark strip, page 2 (logos)", ""),
    "LUM9.1": ("Yes", "Not stated", "CE, DALI-2", "Mark strip, page 2 (logos)", ""),

    # ---- bare extrusions ----
    "LUM3.3": ("n/a", "n/a", "None", "Whole sheet",
               "A bare aluminium extrusion. It carries no electrical listing because it is not an electrical product. Also flagged discontinued."),
    "LUM4.3": ("n/a", "n/a", "None", "Whole sheet", "As LUM3.3."),
    "LUM5.2": ("n/a", "n/a", "None", "Whole sheet", "As LUM3.3."),
    "LUM6.2": ("n/a", "n/a", "None", "Whole sheet", "As LUM3.3."),
    "LUM9.2": ("n/a", "n/a", "None", "Whole sheet", "As LUM3.3."),

    # ---- TCI drivers ----
    "LUM7": ("Not stated", "UL Recognized Component (cURus)",
             "cURus, RCM (AU), PSE (JP)",
             "CERTIFICATIONS column, page 2, row CC30-D-350-NL",
             "RECOGNIZED COMPONENT, not Listed: valid only inside other listed equipment, not as a standalone device. The CERTIFICATIONS column shows no CE, though TCI is an EU maker and CE is compulsory for EU sale."),
    "LUM8.1": ("Not stated", "Not stated - CSA quoted as a STANDARD only",
               "Declared to CSA C22.2 no. 223, EN 55015, EN 61000-3-2/3-3, EN 61347",
               "\"Standards compliance\" block, page 2 (text)",
               "Designed-to, not listed-by. No mark or file number on the sheet."),
    "LUM11.2": ("Yes", "Not stated", "ENEC 05, KEMA KEUR, RCM, EAC, EL, SELV 60V",
                "Mark strip, page 2 (logos)",
                "ENEC is the European third-party certification for control gear - stronger than a self-declared CE. No NRTL mark."),

    # ---- Simes ----
    "LUM8": ("Yes", "Not stated", "CE, RoHS, IP65", "Mark strip, page 2 (logos)", ""),

    # ---- LedsC4 ----
    "LUM10": ("Not stated", "Not stated",
              "IP66 IK10, Class I, RF 850C glow wire, EU energy label D",
              "Technical features, page 2 (read by eye)",
              "The sheet prints performance pictograms but NO certification mark at all. LedsC4 is a Spanish maker, so CE is compulsory for EU sale - but this datasheet does not state it. Ask for the Declaration of Conformity."),
    "LUM11": ("Not stated", "Not stated", "BREEAM, Class II, LED replaceable",
              "Technical features, page 2 (read by eye)", "As LUM10."),
    "LUM11.1": ("Not stated", "Not stated", "IP67, Class II, driver replaceable",
                "Technical features, page 2 (read by eye)", "As LUM10."),

    # ---- Vibia ----
    "LUM13": ("Not stated", "Not stated", "None printed",
              "Pages 2-3 (read by eye)",
              "The specified reference is the 120 V / 60 Hz US variant (1A334-FOIL-US02), so an NRTL listing would be expected - the sheet does not show one. Ask Vibia."),

    # ---- Visual Comfort / WAC / Bover ----
    "LUM12": ("Not stated", "ETL / cETL Listed",
              "ETL, cETL, Wet Location Listed, ADA, Title 24 JA8",
              "\"Standards\" line, page 2 (text)",
              "ETL (Intertek) is an NRTL - equivalent standing to UL for code purposes."),
    "LUM14": ("Not stated", "cETLus Listed", "cETLus, DRY location",
              "Mark strip, page 2 (logo)", "Dry location only."),
    "LUM15": ("Yes", "cETLus Listed", "cETLus, CE, EAC",
              "\"Certifications\" block, page 2 (logos)",
              "120 V 60 Hz, WET, IP-44. Supplied through Bover USA."),
    "LUM16": ("Yes", "cETLus Listed", "cETLus, CE, EAC",
              "\"Certifications\" block, page 2 (logos)", "Battery/USB-C portable lamp."),

    # ---- Luce & Light fixtures ----
    "L&L12": ("Yes", "cULus Listed, file E495946",
              "cULus Listed E495946, CE, ENEC, FCC, SAA, CB, RoHS, DALI-2",
              "Mark strip, page 6 (logos)",
              "The strongest evidence in the set: a listing mark WITH a file number."),
    "L&L13": ("Yes", "cULus Listed, file E495946",
              "cULus Listed E495946, CE, ENEC, FCC, RoHS, DALI-2",
              "Mark strip, page 7 (logos)", ""),
    "L&L14": ("Yes", "Not stated", "CE, UKCA, CB, EAC, IP66, IK06, Class III",
              "Mark strip, page 2 (logos)", "EU/UK marks only. No NRTL mark."),
    "L&L17": ("Yes", "Not stated", "CE, UKCA, EAC, IP65, IK08, Class I",
              "Mark strip, page 2 (logos)",
              "EU/UK marks only. The sheet is also annotated \"DALI driver under review\"."),

    # ---- Luce & Light power supplies ----
    "L&L12.1": ("Yes", "PENDING - not yet granted",
                "SAA, CE, CB, RoHS granted; UL, cUL, FCC and ENEC all marked \"pending\"",
                "\"Certificate\" row, page 3 (text)",
                "READ THIS ONE. The sheet itself says UL and cUL are PENDING, so this driver is NOT UL listed today. It feeds L&L12, which is."),
    "L&L12.2": ("Yes", "cUL / UL listed per the certificate row",
                "CE, ENEC, UL, cUL, FCC, SELV, DALI-2",
                "\"Certificate\" row, page 3 (text)",
                "Model AV0D024V06066. Its safety-standards line also cites UL8750 and CAN/CSA-C22.2 No. 250.13."),
    "L&L13.1": ("Yes", "cUL / UL listed per the certificate row",
                "CE, ENEC, UL, cUL, FCC, SELV, DALI-2",
                "\"Certificate\" row, page 3 (text)", "Same driver as L&L12.2."),
    "L&L17.1": ("Not stated", "Not stated - UL/CSA quoted as STANDARDS only",
                "Declared to UL8750 + UL1310, CAN/CSA-C22.2 No.250.13",
                "Safety standards line, page 3 (text)",
                "Designed-to, not listed-by. No mark or file number."),

    # ---- pool lighting (Luce & Light, same families as L&L12/13) ----
    "A": ("Yes", "cULus Listed, file E495946",
          "cULus Listed E495946, CE, ENEC, FCC, SAA, CB, RoHS, DALI-2",
          "Mark strip, page 5 (logos)",
          "Submersible pool fixture. Same listing as L&L12 - a listing mark WITH a file number."),
    "B": ("Yes", "cULus Listed, file E495946",
          "cULus Listed E495946, CE, ENEC, FCC, RoHS, DALI-2",
          "Mark strip, page 6 (logos)",
          "Submersible pool fixture. Same listing as L&L13."),

    # ---- iGuzzini ----
    "iGL6": ("Not checked", "Not checked", "No manufacturer sheet attached",
             "Source PDF is one page",
             "The datasheet behind this item is the curated summary page only - there is no iGuzzini page behind it to read. The other seven iGuzzini items are cULus listed."),
}

# The Lutron package: controls, receptacles, shades and drapery rather than
# luminaires. Left on the automatic verdict, with the type said plainly.
LTRN_KIND = {
    "LTRN9": "Keypad", "LTRN10": "Wallbox", "LTRN18": "Warranty document",
    "LTRN19": "Receptacle", "LTRN20": "Receptacle", "LTRN21": "Faceplate",
    "LTRN25": "Roller shade", "LTRN25.1": "Shade bracketry",
    "LTRN26": "Drapery track", "LTRN26.1": "Power supply",
}

STRONG_NRTL = {"UL listing", "cULus mark", "UL file number", "ETL / Intertek",
               "NRTL wording"}
STRONG_EU = {"CE marking", "CE in a mark list", "EU declaration", "ENEC",
             "UKCA", "EU directive"}


def kind(it):
    t = (it["title"] + " " + it["code"]).lower()
    if "driver" in t or "power supply" in t or "transformer" in t:
        return "Driver / power supply"
    if "profile" in t:
        return "Profile (extrusion)"
    if it["code"] in LTRN_KIND:
        return LTRN_KIND[it["code"]]
    if it["group"] == "LTRN":
        return "Control"
    return "Luminaire"


def auto(found):
    n = sorted({h["mark"] for h in found.get("nrtl", [])} & STRONG_NRTL)
    e = sorted({h["mark"] for h in found.get("eu", [])} & STRONG_EU)
    where = []
    for b in ("nrtl", "eu"):
        for h in found.get(b, []):
            if h["mark"] in STRONG_NRTL or h["mark"] in STRONG_EU:
                where.append("%s p%s" % (h["mark"], ",".join(map(str, h["pages"]))))
    ce = "Yes" if e else "Not stated"
    ul = ", ".join(n) if n else "Not stated"
    marks = ", ".join(n + e) if (n or e) else "None found in the text"
    return ce, ul, marks, ("; ".join(where[:4]) + " (text)") if where else "Text search, whole sheet"


def main():
    rows = json.load(io.open(os.path.join(HERE, "audit", "_certs.json"),
                             encoding="utf-8"))
    uniq = json.load(io.open(os.path.join(HERE, "audit", "_unique.json"),
                             encoding="utf-8"))
    # code -> the code that owns the curated entry for its shared PDF
    owner = {}
    for v in uniq.values():
        for c in v["codes"]:
            owner[c] = v["codes"][0]

    out = []
    for r in rows:
        o = owner.get(r["code"], r["code"])
        if o in CURATED:
            ce, ul, marks, ev, note = CURATED[o]
            how = "Read by eye" if "logo" in ev or "eye" in ev else "Curated from the text"
        else:
            ce, ul, marks, ev = auto(r["found"])
            note = ""
            how = "Automatic text scan"
        out.append({
            "code": r["code"], "group": r["group"], "group_name": r["group_name"],
            "type": kind(r), "title": r["title"],
            "manufacturer": r["manufacturer"] or "Not stated",
            "ce": ce, "nrtl": ul, "marks": marks, "evidence": ev,
            "how": how, "note": note,
            "drive_url": r["drive_url"], "source": r["source"],
        })

    p = os.path.join(HERE, "audit", "_certs_final.json")
    io.open(p, "w", encoding="utf-8").write(json.dumps(out, indent=1, ensure_ascii=False))
    print("%d rows -> %s" % (len(out), p))
    for r in out:
        if r["type"] == "Luminaire":
            print("  %-9s %-12s CE:%-11s NRTL:%s" % (r["code"], r["group"], r["ce"], r["nrtl"][:44]))


if __name__ == "__main__":
    main()
