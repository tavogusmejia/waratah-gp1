"""Pull the numbers that matter off each luminaire sheet.

For a light, the things anyone actually asks are lumens, beam angle, colour
temperature, CRI, wattage and the IP rating. Every manufacturer writes them
differently, so this gathers candidates per sheet rather than pretending to
one schema - the assembly step decides what goes on the curated page.

    python tools/mine_lighting.py > _mined.json
"""
import io, json, re, sys
from pathlib import Path

import fitz

SRC = Path(r"C:\Users\gus\Documents\Claude Projects\JANU\04 Project Documents"
           r"\03 Datasheets\GP1 Datasheets\L - Lighting\L&L - Luminaires")

# Deliberately loose: a candidate list a human reads, not a parser's verdict.
PATTERNS = {
    "lumens": r"(\d[\d,.]*)\s*(?:lm\b|lumens?\b)",
    "beam": r"(\d{1,3}(?:[.,]\d)?)\s*(?:°|deg\b|degrees?\b)",
    "cct": r"(\d{4})\s*K\b",
    "cri": r"(?:CRI|Ra)\s*[:>=\s]*(\d{2,3})",
    "watts": r"(\d[\d.,]*)\s*W\b(?!/)",
    "volts": r"(\d[\d.,]*)\s*V(?:dc|ac|DC|AC)?\b",
    "ip": r"\bIP\s?(\d{2}[KX]?)\b",
    "ik": r"\bIK\s?(\d{2})\b",
    "ma": r"(\d{3,4})\s*mA\b",
    "lmw": r"(\d[\d.,]*)\s*lm\s*/\s*W",
}
PROTOCOL = ("DALI-2", "DALI", "PHASE-DIM", "PHASE DIM", "TRIAC", "0-10V",
            "1-10V", "ON-OFF", "CASAMBI", "PUSH")


def mine(p):
    d = fitz.open(p)
    text = "\n".join(pg.get_text() for pg in d)
    d.close()
    flat = re.sub(r"\s+", " ", text)
    found = {}
    for key, pat in PATTERNS.items():
        hits, seen = [], set()
        for m in re.finditer(pat, flat, re.I):
            v = m.group(1)
            if v in seen:
                continue
            seen.add(v)
            hits.append(v)
            if len(hits) >= 8:
                break
        if hits:
            found[key] = hits
    found["protocol"] = [k for k in PROTOCOL if k.lower() in flat.lower()][:3]
    found["chars"] = len(flat)
    return found


def main():
    out = {}
    for p in sorted(SRC.glob("*.pdf")):
        stem = p.stem
        code = stem.split(" - ")[0]
        tag = re.search(r" - ([A-Z]\d[\d.]*) - ", stem)
        out[code] = {"file": p.name, "tag": tag.group(1) if tag else "",
                     "model": stem.rsplit(" - ", 1)[-1], **mine(p)}
    json.dump(out, io.open(1, "w", encoding="utf-8", closefd=False),
              indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
