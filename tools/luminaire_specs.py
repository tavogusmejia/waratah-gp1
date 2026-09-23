"""The curated content for every luminaire, and the spec file that builds them.

Each figure here was read off the manufacturer's own sheet in context, not
lifted from a regex sweep - a mined "CRI 930" is iGuzzini's colour code and a
mined "beam 700" is a milliamp rating, and either would have gone onto a
drawing-office document as fact. Where a number could not be confirmed it is
left out rather than guessed.

    python tools/luminaire_specs.py > _lum.json
    python tools/make_curated.py _lum.json --out <dir>
"""
import io, json, re, sys
from pathlib import Path

SRC = (r"C:\Users\gus\Documents\Claude Projects\JANU\04 Project Documents"
       r"\03 Datasheets\GP1 Datasheets\L - Lighting\L&L - Luminaires")

# code: (manufacturer, title, [(label, value)...], notes)
# Drivers and profiles carry what a driver or profile is asked for; fixtures
# carry lumens, beam, colour temperature, CRI, power and ingress rating.
L = {
"LUM1": ("iGuzzini", "Recessed Ceiling Downlight 14\u00b0 - iGuzzini Laser 25 mm", [
    ("Lumen output", "Up to 121 lm"), ("Beam", "14\u00b0 spot"),
    ("Colour temperature", "3000 K"), ("CRI", "90"),
    ("Efficacy", "Up to 60 lm/W"), ("Ingress", "IP20"),
    ("Control", "DALI"), ("Mounting", "Recessed in ceiling, fixed optic"),
    ("Body", "Die-cast aluminium optical assembly"),
    ("Lumen maintenance", "L80 at 69,000 h (LM-79 / LM-80)"),
    ("Supplied by", "Sistemalux (iGuzzini, Canada)")], ""),
"LUM2": ("iGuzzini", "Recessed Ceiling Downlight 26\u00b0 - iGuzzini Laser 38 mm", [
    ("Lumen output", "125 lm to 430 lm"), ("Beam", "26\u00b0 medium"),
    ("Colour temperature", "3000 K"), ("CRI", "90"),
    ("Efficacy", "Up to 75 lm/W"), ("Ingress", "IP20"),
    ("Control", "DALI"),
    ("Mounting", "Recessed in ceiling; adjustable, medium, flood and wall-washer optics"),
    ("Lumen maintenance", "L80 at 50,000 h (LM-79 / LM-80)"),
    ("Supplied by", "Sistemalux (iGuzzini, Canada)")], ""),
"LUM3": ("LedFlex Group", "Indirect LED Strip - Eco Flex 240, 2700 K", [
    ("Lumen output", "1012 lm/m"), ("Colour temperature", "2700 K"),
    ("CRI", "90"), ("Power", "9.6 W/m (2.93 W/ft)"),
    ("Efficacy", "105 lm/W"), ("Supply", "24 Vdc"), ("Ingress", "IP20"),
    ("Cut length", "33.33 mm"), ("Width", "10 mm"), ("Control", "DALI")],
    "Runs with driver LUM3.1 or LUM3.2 and profile LUM3.3."),
"LUM3.1": ("EcoPac Power", "Indirect LED Strip Driver, 30 W - EcoPac ELED-30-24DP2", [
    ("Output", "24 Vdc, 30 W"), ("Control", "DALI dimmable"),
    ("Ingress", "IP20"), ("Serves", "LUM3 - Eco Flex 240 indirect strip")], ""),
"LUM3.2": ("EcoPac Power", "Indirect LED Strip Driver, 100 W - EcoPac ELED-100-24DP2", [
    ("Output", "24 Vdc, 100 W"), ("Control", "DALI dimmable"),
    ("Serves", "LUM3 - Eco Flex 240 indirect strip")], ""),
"LUM3.3": ("LedFlex Group", "Indirect LED Strip Profile - Pro 0209", [
    ("Profile", "Pro 0209 (021-0202)"),
    ("Serves", "LUM3 - Eco Flex 240 indirect strip")], ""),
"LUM4": ("LedFlex Group", "LED Strip in Furniture, 2.93 W/ft - Eco Flex 240, 2700 K", [
    ("Lumen output", "1012 lm/m"), ("Colour temperature", "2700 K"),
    ("CRI", "90"), ("Power", "9.6 W/m (2.93 W/ft)"),
    ("Efficacy", "105 lm/W"), ("Supply", "24 Vdc"), ("Ingress", "IP20"),
    ("Control", "DALI")],
    "Runs with driver LUM4.1 or LUM4.2 and profile LUM4.3."),
"LUM4.1": ("EcoPac Power", "Furniture Strip Driver, 30 W - EcoPac ELED-30-24DP2", [
    ("Output", "24 Vdc, 30 W"), ("Control", "DALI dimmable"),
    ("Ingress", "IP20"), ("Serves", "LUM4 - furniture strip, tag L05.1")], ""),
"LUM4.2": ("EcoPac Power", "Furniture Strip Driver, 60 W - EcoPac ELED-60-24DP2", [
    ("Output", "24 Vdc, 60 W"), ("Control", "DALI dimmable"),
    ("Ingress", "IP20"), ("Serves", "LUM4 - furniture strip, tag L05.1")], ""),
"LUM4.3": ("LedFlex Group", "Furniture Strip Profile - Pro 0209", [
    ("Profile", "Pro 0209 (021-0202)"),
    ("Serves", "LUM4 - furniture strip, tag L05.1")], ""),
"LUM5": ("LedFlex Group", "LED Strip in Furniture, 0.73 W/ft - Eco Flex 240, 2700 K", [
    ("Lumen output", "254 lm/m"), ("Colour temperature", "2700 K"),
    ("CRI", "90"), ("Power", "2.4 W/m (0.73 W/ft)"),
    ("Efficacy", "106 lm/W"), ("Supply", "24 Vdc"), ("Ingress", "IP20"),
    ("Control", "DALI")],
    "Runs with driver LUM5.1 and profile LUM5.2."),
"LUM5.1": ("EcoPac Power", "Furniture Strip Driver, 30 W - EcoPac ELED-30-24DP2", [
    ("Output", "24 Vdc, 30 W"), ("Control", "DALI dimmable"),
    ("Ingress", "IP20"), ("Serves", "LUM5 - furniture strip, tag L05.2")], ""),
"LUM5.2": ("LedFlex Group", "Furniture Strip Profile - Pro 0209", [
    ("Profile", "Pro 0209 (021-0202)"),
    ("Serves", "LUM5 - furniture strip, tag L05.2")], ""),
"LUM6": ("LedFlex Group", "LED Strip in Furniture, IP65 - Eco Flex 240, 2700 K", [
    ("Lumen output", "254 lm/m"), ("Colour temperature", "2700 K"),
    ("CRI", "90"), ("Power", "2.4 W/m (0.73 W/ft)"),
    ("Efficacy", "106 lm/W"), ("Supply", "24 Vdc"), ("Control", "DALI")],
    "The schedule calls this the IP65 run, but the sheet supplied is the "
    "IP20 EF240272002 - the same tape as LUM5. Confirm the ingress rating "
    "before ordering."),
"LUM6.1": ("EcoPac Power", "Furniture Strip Driver, 30 W - EcoPac ELED-30-24DP2", [
    ("Output", "24 Vdc, 30 W"), ("Control", "DALI dimmable"),
    ("Ingress", "IP20"), ("Serves", "LUM6 - furniture strip, tag L05.4")], ""),
"LUM6.2": ("LedFlex Group", "Furniture Strip Profile - Pro 0409", [
    ("Profile", "Pro 0409 (021-0402)"),
    ("Serves", "LUM6 - furniture strip, tag L05.4")], ""),
"LUM7": ("TCI", "Integrated Mini Downlight Driver, 350 mA - CC20-D-350-N", [
    ("Output", "350 mA constant current"), ("Control", "DALI dimmable"),
    ("Ingress", "IP20"),
    ("Serves", "Integrated mini downlight, tag L06.1")], ""),
"LUM8": ("Simes", "Courtesy Wall Light - Profilo 1.0 BORTOP02-2K7", [
    ("Power", "1.5 W"), ("Colour temperature", "2700 K"),
    ("Efficacy", "86 lm/W"), ("Beam", "0\u00b0 to 45\u00b0"),
    ("Ingress", "IP65"), ("Control", "DALI"),
    ("Ambient", "Max 40 \u00b0C (Ta 25 \u00b0C)"),
    ("Body", "Aluminium profile, LED on board")],
    "Runs with driver LUM8.1."),
"LUM8.1": ("TCI", "Courtesy Wall Light Driver - Mini Jolly DALI 20", [
    ("Output", "20 W, 250-400 mA"), ("Control", "DALI dimmable"),
    ("Serves", "LUM8 - courtesy wall light, tag L07")], ""),
"LUM9": ("LedFlex Group", "Exterior Step LED Strip, IP67 - Eco Flex 240, 2700 K", [
    ("Lumen output", "249 lm/m"), ("Colour temperature", "2700 K"),
    ("CRI", "90"), ("Power", "2.4 W/m"), ("Efficacy", "104 lm/W"),
    ("Supply", "24 Vdc"), ("Ingress", "IP67"), ("Control", "DALI")],
    "Runs with driver LUM9.1 and profile LUM9.2."),
"LUM9.1": ("EcoPac Power", "Exterior Step Strip Driver, 30 W - EcoPac ELED-30-24DP2", [
    ("Output", "24 Vdc, 30 W"), ("Control", "DALI dimmable"),
    ("Serves", "LUM9 - exterior step strip, tag L07.2")], ""),
"LUM9.2": ("LedFlex Group", "Exterior Step Strip Profile - Pro 0409", [
    ("Profile", "Pro 0409 (021-0402)"),
    ("Serves", "LUM9 - exterior step strip, tag L07.2")], ""),
"LUM10": ("LEDS C4", "Exterior Courtesy Wall Light - Tiny Short 05-E146-Z5-CL", [
    ("Lumen output", "20 lm"), ("Colour temperature", "3000 K"),
    ("CRI", "80"), ("Power", "2.9 W"), ("Efficacy", "7 lm/W"),
    ("Ingress", "IP66"), ("Impact", "IK10"), ("Control", "ON-OFF"),
    ("Finish", "Urban grey"), ("Mounting", "Recessed in wall")], ""),
"LUM11": ("LEDS C4", "Path Light - Sinia 600 mm Bollard 10-E033-60-CK", [
    ("Lumen output", "212 lm"), ("Colour temperature", "2700 K warm white"),
    ("CRI", "92"), ("Power", "3.4 W"), ("Efficacy", "62 lm/W"),
    ("Ingress", "IP65"), ("Impact", "IK05"), ("Height", "600 mm"),
    ("Finish", "Black"), ("Control", "DALI")],
    "Runs with driver LUM11.2. LUM11.1 is the alternate head."),
"LUM11.1": ("LEDS C4", "Path Light, Alternate - 71-E649-60-OU", [
    ("Power", "4.3 W"), ("Ingress", "IP67"), ("Control", "DALI"),
    ("Serves", "Path light, tag L11")], ""),
"LUM11.2": ("TCI", "Path Light Driver - Maxi Jolly SV DALI IPR1-70", [
    ("Output", "70 W, 350-1400 mA"), ("Control", "DALI dimmable"),
    ("Ingress", "IP68"), ("Serves", "LUM11 - path light, tag L11")], ""),
"LUM12": ("WAC Lighting", "Surface-Mounted Service Downlight - WAC FM-05RN", [
    ("Power", "12 W"), ("Colour temperature", "3000 K / 3500 K selectable"),
    ("Diameter", "5 in round"), ("Control", "ON-OFF"),
    ("Mounting", "Surface, ceiling or wall"),
    ("Ambient", "-40 \u00b0F to 122 \u00b0F (-40 \u00b0C to 50 \u00b0C)")], ""),
"LUM13": ("Vibia", "Indirect Wall Lamp - Foil 1A334-FOIL-US02", [
    ("Control", "Phase dimming"),
    ("Mounting", "Wall and ceiling, architectural"),
    ("Design", "967 Design, 2011")],
    "Lumen output, wattage and colour temperature are not stated on the "
    "sheet supplied. Confirm with the manufacturer before ordering."),
"LUM14": ("Visual Comfort", "Table Lamp for Minibar - Kelly Wearstler Una Small KW 3901ALB", [
    ("Lamping", "1200 lm, 10 W"), ("Height", "12.75 in"),
    ("Width", "12.5 in"), ("Designer", "Kelly Wearstler")], ""),
"LUM15": ("Bover", "Floor Lamp, Pool Terrace - Kando P111", [
    ("Power", "39 W"),
    ("Colour temperature", "2200 K / 2400 K / 2700 K"),
    ("CRI", "90"), ("Control", "Phase dimming"),
    ("Use", "Outdoor, pool terrace")], ""),
"LUM16": ("Bover", "Portable Lamp - Kando M40R", [
    ("Power", "5 W"),
    ("Colour temperature", "2200 K / 2400 K / 2700 K"),
    ("CRI", "90"), ("Power source", "Rechargeable, portable"),
    ("Use", "Outdoor")], ""),
"L&L12": ("L&L Luce&Light", "Submersible Pool Fixture, Steps - L&L Bright 1.6 316L", [
    ("Lumen output", "195 lm"), ("Beam", "21\u00b0"),
    ("Colour temperature", "3000 K"), ("Power", "2 W"),
    ("Supply", "24 Vdc"), ("Ingress", "IP65 / IP68"), ("Impact", "IK10"),
    ("Body", "316L stainless steel"), ("Control", "DALI"),
    ("Mounting", "Recessed underwater, pool steps")],
    "Runs with driver L&L12.1 or L&L12.2. Same fixture as PL-A."),
"L&L12.1": ("L&L Luce&Light", "Pool Fixture Driver, 30 W - AV0D024V03066", [
    ("Output", "24 Vdc, 30 W"), ("Control", "DALI-2 dimmable"),
    ("Ingress", "IP66"), ("Serves", "L&L12 - pool step fixture, tag L09")], ""),
"L&L12.2": ("L&L Luce&Light", "Pool Fixture Driver, 60 W - AV0D024V06066", [
    ("Output", "24 Vdc, 60 W"), ("Control", "DALI-2 dimmable"),
    ("Ingress", "IP66"), ("Serves", "L&L12 - pool step fixture, tag L09")], ""),
"L&L13": ("L&L Luce&Light", "Submersible Pool Fixture - L&L Bright 3.0 316L", [
    ("Lumen output", "683 lm"), ("Beam", "34\u00b0"),
    ("Colour temperature", "3000 K"), ("Power", "7 W"),
    ("Supply", "24 Vdc"), ("Ingress", "IP66 / IP68"), ("Impact", "IK10"),
    ("Body", "316L stainless steel"), ("Control", "DALI"),
    ("Mounting", "Recessed underwater")],
    "Runs with driver L&L13.1. Same fixture as PL-B."),
"L&L13.1": ("L&L Luce&Light", "Pool Fixture Driver, 60 W - AV0D024V06066", [
    ("Output", "24 Vdc, 60 W"), ("Control", "DALI-2 dimmable"),
    ("Ingress", "IP66"), ("Serves", "L&L13 - pool fixture, tag L09.1")], ""),
"L&L14": ("L&L Luce&Light", "Vegetation Projector - L&L Pivot Mini", [
    ("Lumen output", "150 lm"), ("Beam", "15\u00b0 / 25\u00b0 / 35\u00b0"),
    ("Colour temperature", "3000 K"), ("CRI", "90"), ("Power", "2.5 W"),
    ("Ingress", "IP66"), ("Impact", "IK06"), ("Control", "DALI"),
    ("Model", "cp0100100150lt-4"), ("Use", "Vegetation and landscape")], ""),
"L&L17": ("L&L Luce&Light", "Sconce - L&L Ella OUT 1.0", [
    ("Lumen output", "954 lm"), ("Beam", "25\u00b0"),
    ("Colour temperature", "3000 K (2700 K available)"), ("Power", "7 W"),
    ("Ingress", "IP65"), ("Impact", "IK08"), ("Control", "DALI"),
    ("Model", "ea1010fdtt"), ("Mounting", "Wall")],
    "Runs with driver L&L17.1."),
"L&L17.1": ("Wago", "Sconce Driver, 5-Protocol - WSDDV225PA", [
    ("Output", "36 W"), ("Control", "5-protocol dimming"),
    ("Ingress", "IP20"), ("Serves", "L&L17 - sconce, tag D01")],
    "The driver is not an L&L part; it keeps the L&L17 number because it "
    "belongs to that fixture."),
}


def main():
    src = Path(SRC)
    items, missing = [], []
    for p in sorted(src.glob("*.pdf")):
        code = p.stem.split(" - ")[0]
        if code not in L:
            missing.append(p.name)
            continue
        maker, title, specs, notes = L[code]
        tag = re.search(r" - ([A-Z]\d[\d.]*) - ", p.stem)
        rows = [{"label": "Fixture tag", "value": tag.group(1)}] if tag else []
        rows += [{"label": a, "value": b} for a, b in specs]
        # the item sheet drops the " - DS - " marker: it is the item, and the
        # manufacturer's own sheet stays beside it as the attachment
        items.append({
            "code": code, "manufacturer": maker, "title": title,
            "specs": rows, "notes": notes,
            "source": p.name,
            "filename": p.name.replace(" - DS - ", " - ", 1),
        })
    if missing:
        sys.stderr.write("NO CONTENT FOR: %s\n" % ", ".join(missing))
    json.dump({"source_root": SRC, "items": items},
              io.open(1, "w", encoding="utf-8", closefd=False),
              indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
