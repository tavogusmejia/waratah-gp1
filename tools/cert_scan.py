"""What certification does each light's datasheet actually claim?

Reads the SOURCE PDF behind every lighting item in the register and pulls out
the evidence for a safety listing, rather than guessing from the manufacturer's
address. The question it answers is a compliance one: a luminaire carrying only
a CE mark is not listed for installation in a jurisdiction that wants an NRTL
mark (UL, ETL/Intertek, CSA), and vice versa.

IT REPORTS EVIDENCE, NOT A VERDICT. Every hit carries the phrase it matched and
the page it was on, because "UL" appears inside words, "CE" appears inside more
of them, and a datasheet that says "designed to UL standards" is not a listing.
The classifier below is deliberately conservative and says SO when it is
unsure - an unchecked box is cheap, a wrong tick is not.

    python tools/cert_scan.py            writes tools/audit/_certs.json
"""
import io
import json
import os
import re
import sys

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.environ.get(
    "GP1_DATASHEETS",
    r"C:/Users/gus/Documents/Claude Projects/JANU/04 Project Documents"
    r"/03 Datasheets/GP1 Datasheets")

LIGHT_GROUPS = ("LUM", "L&L", "iGL", "PL", "LTRN")

# --------------------------------------------------------------------------
# What counts as evidence.
#
# Ordered most-specific first. A mark that names a listing body AND the word
# listed is worth more than the bare letters, and the two are kept apart so a
# reader can see which one they got.
# --------------------------------------------------------------------------
NRTL = [
    ("UL listing",      r"\bc?UL(?:us)?\s*(?:®|\(R\))?\s*(?:Listed|Listing|Recognized|Classified)\b"),
    ("cULus mark",      r"\bc\s?UL\s?us\b|\bcULus\b|\bUL\s?us\b"),
    ("UL file number",  r"\b(?:File\s*(?:No\.?|Number)?\s*)?E\d{5,6}\b"),
    ("UL standard",     r"\bUL\s?(?:STD\.?\s*)?(?:8750|1598|1598A|2108|962|924|153|1993|48|879|1012|60950|62368)\b"),
    ("ETL / Intertek",  r"\bc?ETL(?:us)?\b|\bIntertek\b"),
    ("CSA",             r"\bc?CSA(?:us)?\b|\bCAN/CSA\b"),
    ("NRTL wording",    r"\bNRTL\b|\bNationally Recognized Testing\b"),
    ("NOM / Mexico",    r"\bNOM-\d+\b"),
]

EU = [
    ("CE marking",      r"\bCE[\s-]?(?:mark(?:ed|ing)?|conformity|certified|compliant|approved)\b"),
    ("CE in a mark list", r"(?<![A-Za-z])CE(?![A-Za-z])(?=[^\n]{0,40}(?:RoHS|ENEC|IP\d|TUV|T[ÜU]V|VDE|EMC|marking))"),
    ("EU declaration",  r"\b(?:EU|EC)\s+Declaration of Conformity\b|\bDeclaration of Conformity\b"),
    ("EU directive",    r"\b201[0-9]/\d{1,3}/E[UC]\b|\b2014/35/EU\b|\b2014/30/EU\b"),
    ("ENEC",            r"\bENEC\b"),
    ("EN / IEC standard", r"\b(?:EN|IEC|BS EN)\s?6\d{4}(?:-\d+)?\b"),
    ("TUV / VDE",       r"\bT[ÜU]V\b|\bVDE\b|\bGS\s?mark\b"),
    ("UKCA",            r"\bUKCA\b"),
    ("RoHS / REACH",    r"\bRoHS\b|\bREACH\b"),
]

OTHER = [
    ("DLC",   r"\bDesignLights\b|\bDLC\b"),
    ("FCC",   r"\bFCC\b"),
    ("SAA",   r"\bSAA\b|\bAS/NZS\b"),
    ("CCC",   r"\bCCC\b"),
    ("IECEE / CB", r"\bCB\s?Scheme\b|\bIECEE\b"),
]

# RoHS and an EN standard are NOT a CE mark - RoHS is a separate directive and
# an EN number is the standard a product is tested to, which anyone may cite.
# They are recorded, and they do not on their own make the CE column true.
CE_WEAK = {"RoHS / REACH", "EN / IEC standard"}
# Likewise: a UL standard number is what a product was designed to. Only a
# listing, a file number or a mark says somebody actually listed it.
NRTL_WEAK = {"UL standard"}


def snippets(text, pattern, limit=3):
    out = []
    for m in re.finditer(pattern, text, re.I):
        a = max(0, m.start() - 70)
        b = min(len(text), m.end() + 70)
        s = re.sub(r"\s+", " ", text[a:b]).strip()
        if s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def scan(path):
    """Every hit in one PDF, with the page it was on."""
    try:
        doc = fitz.open(path)
    except Exception as e:                      # noqa: BLE001
        return {"error": str(e)}
    pages, chars = [], 0
    for p in doc:
        t = p.get_text("text") or ""
        chars += len(t.strip())
        pages.append(t)
    doc.close()
    whole = "\n".join(pages)

    found = {}
    for bucket, rules in (("nrtl", NRTL), ("eu", EU), ("other", OTHER)):
        hits = []
        for name, pat in rules:
            sn = snippets(whole, pat)
            if not sn:
                continue
            where = [i + 1 for i, t in enumerate(pages) if re.search(pat, t, re.I)]
            hits.append({"mark": name, "pages": where[:4], "evidence": sn})
        found[bucket] = hits
    found["pages"] = len(pages)
    found["text_chars"] = chars
    # A scanned sheet has no text to search. Saying "no certification found"
    # about one would be a lie by omission - there may be a mark printed on it
    # that nothing here can read.
    found["searchable"] = chars > 200
    return found


def verdict(f):
    """Conservative. Anything short of a real mark says so in words."""
    if not f.get("searchable"):
        return "Not searchable", "The PDF has no text layer - a mark may be printed on it"
    strong_n = [h["mark"] for h in f["nrtl"] if h["mark"] not in NRTL_WEAK]
    weak_n = [h["mark"] for h in f["nrtl"] if h["mark"] in NRTL_WEAK]
    strong_e = [h["mark"] for h in f["eu"] if h["mark"] not in CE_WEAK]
    weak_e = [h["mark"] for h in f["eu"] if h["mark"] in CE_WEAK]

    if strong_n and strong_e:
        return "Both", "NRTL: %s / EU: %s" % (", ".join(strong_n), ", ".join(strong_e))
    if strong_n:
        return "UL / NRTL", ", ".join(strong_n)
    if strong_e:
        return "CE / EU", ", ".join(strong_e)
    if weak_n or weak_e:
        return "Unclear", ("only indirect signs: " +
                           ", ".join(weak_n + weak_e))
    return "None found", "nothing in the sheet names a listing"


def main():
    data = json.load(io.open(os.path.join(ROOT, "web/data/datasheets.json"),
                             encoding="utf-8"))
    rows = []
    for it in data["items"]:
        if it["group"] not in LIGHT_GROUPS:
            continue
        src = it.get("source") or ""
        path = os.path.join(SOURCE, src.replace("/", os.sep))
        rec = {
            "key": it["key"], "code": it["code"], "group": it["group"],
            "group_name": it["group_name"], "title": it["title"],
            "manufacturer": it.get("manufacturer", ""),
            "source": src, "drive_url": it.get("drive_url", ""),
            "maker_url": it.get("maker_url", ""),
        }
        if not os.path.exists(path):
            rec.update(found={"error": "source PDF not found"},
                       verdict="Not checked", why="the source PDF is not on this machine")
        else:
            f = scan(path)
            v, why = verdict(f)
            rec.update(found=f, verdict=v, why=why)
        rows.append(rec)
        sys.stdout.write("%-9s %-28s %s\n" % (rec["code"], rec["verdict"], rec["why"][:60]))

    out = os.path.join(HERE, "audit", "_certs.json")
    io.open(out, "w", encoding="utf-8").write(
        json.dumps(rows, indent=1, ensure_ascii=False))
    print("\n%d lighting items -> %s" % (len(rows), out))


if __name__ == "__main__":
    main()
