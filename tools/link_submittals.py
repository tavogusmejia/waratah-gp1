"""Read the submittal record and say where each register item stands.

The register knows what an item IS. The submittal folders know what happened
to it: which package it went out in, when, and what came back. This joins the
two, and with --apply writes the result into gp1.item_state so the status
pills on the register are the real ones rather than something typed in again.

    python tools/link_submittals.py            # report only
    python tools/link_submittals.py --apply

WHERE THE VERDICT COMES FROM

A returned submittal carries a review PDF per item with a stamp in its text:

    Date: 27 August 2026  Remarks: No objection  Reviewed: BSD

That remark is the whole verdict, in the reviewer's own words, and it maps
onto the five states the register already has. "No objection" on its own is
an approval. "No objection" followed by a condition is an approval as noted,
and the condition becomes the note - which is exactly what "approved as
noted" is for, and why that field exists. Anything that is not a form of no
objection is a question or an objection, and goes back as revise and
resubmit; the remark is kept verbatim either way, because a paraphrase of a
reviewer's words is not a record.

An item in 01 Sent has gone out and nothing has come back: submitted.

HOW A SHEET FINDS ITS ITEM

By the item code where the submittal uses one - "JANU-SUB-003 A1 MDS - ..."
is A1 - and otherwise by the MODEL NUMBER in the title.

The model number, not the position in the list. JANU-SUB-011 numbers its
sheets 01 to 11 and skips 08, so its ninth sheet is the register's E8 and
every sheet after it is offset by one. Matching on position would have put
nine of the ten electrical items on the wrong row, quietly, and each one
would have looked plausible.
"""
import argparse, io, json, re, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SUBS = Path(r"C:\Users\gus\Documents\Claude Projects\JANU"
            r"\04 Project Documents\06 Submittals")
REF = "iygkonfuyslvgezgofby"
BASE = "https://%s.supabase.co" % REF
OUT = io.open(1, "w", encoding="utf-8", closefd=False)

STAMP = re.compile(r"Date:\s*(.{0,28}?)\s*Remarks:\s*(.{0,200}?)\s*Reviewed:\s*(\S+)")
# The other format the record uses. SUB-003 and SUB-004 came back as a stamp
# on each item's own sheet; SUB-009 came back through a review platform, whose
# export writes one verdict for the whole package as "Final Response <verdict>".
# Reading only the stamp left an entire returned submittal looking unanswered.
FINAL = re.compile(r"Final Response\s+(Approved as noted|Approved|"
                   r"Revise and resubmit|Revise & resubmit|Rejected|"
                   r"No objection)", re.I)
SHEET = re.compile(r"JANU-SUB-(\d{3})\s+([A-Za-z0-9.]+)\s")
# A model number is the distinctive run of letters and digits in a title -
# PCC4022R, THQL2160GFT2, CW16005DI. Four or more characters with at least one
# digit and one letter, which is specific enough not to match "Pool" or "120V".
MODEL = re.compile(r"\b(?=[A-Za-z0-9-]*\d)(?=[A-Za-z0-9-]*[A-Za-z])[A-Za-z0-9-]{5,}\b")


def package_verdict(pdfs, fitz):
    """One verdict for a whole submittal, for packages reviewed as a package
    rather than sheet by sheet. Only consulted when no sheet carries a stamp."""
    for f in sorted(pdfs, key=lambda x: -x.stat().st_size):
        try:
            d = fitz.open(f)
            txt = " ".join(" ".join(d[p].get_text().split())
                           for p in range(d.page_count))
            d.close()
        except Exception:
            continue
        m = FINAL.search(txt)
        if m:
            return m.group(1)
    return ""


def verdict(remark):
    """The reviewer's words -> one of the register's five states."""
    r = " ".join((remark or "").split())
    low = r.lower().rstrip(". ")
    if not r:
        return "submitted", ""
    if low in ("no objection", "no objections"):
        return "approved", ""
    if low in ("approved as noted", "approved-as-noted"):
        return "approved_as_noted", ""
    if low in ("revise and resubmit", "revise & resubmit"):
        return "revise_resubmit", ""
    if low == "rejected":
        return "rejected", ""
    if low == "approved":
        return "approved", ""
    if low.startswith(("no objection", "approved")):
        # Approved, with something attached. The condition IS the note.
        rest = re.sub(r"^(no objections?|approved)[.,;:\s]*", "", r, flags=re.I)
        return "approved_as_noted", rest.strip()
    return "revise_resubmit", r


def models(text):
    out = set()
    for m in MODEL.finditer(text or ""):
        w = m.group(0).upper().strip("-")
        if w.startswith("JANU") or w in ("MDS",):
            continue
        out.add(w)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    import fitz
    reg = json.loads((REPO / "web/data/datasheets.json").read_text(encoding="utf-8"))
    items = reg["items"]
    by_code = {}
    for it in items:
        by_code.setdefault(it["code"].upper(), []).append(it)
    by_model = {}
    for it in items:
        for w in models(it["title"]):
            by_model.setdefault(w, []).append(it)

    found, unmatched, no_items = [], [], []
    for state in ("01 Sent", "02 Returned"):
        root = SUBS / state
        if not root.is_dir():
            continue
        for sub in sorted(p for p in root.iterdir() if p.is_dir()):
            num = re.search(r"JANU-SUB-(\d{3})", sub.name)
            num = num.group(1) if num else "???"
            pdfs = list(sub.rglob("*.pdf"))
            reviews = {}
            for f in pdfs:
                if "Review" not in f.name:
                    continue
                m = SHEET.search(f.name)
                if m:
                    reviews[m.group(2).upper()] = f
            sheets = [f for f in pdfs
                      if " MDS " in f.name or re.search(r"SUB-\d{3} \d\d ", f.name)]
            if not sheets:
                no_items.append((state, sub.name, len(pdfs)))
                continue
            # Only when no sheet carries its own stamp, so a package verdict
            # can never overrule a reviewer's note on one item.
            pkg = "" if reviews else package_verdict(pdfs, fitz)
            for f in sheets:
                m = SHEET.search(f.name)
                tag = m.group(2).upper() if m else ""
                hits, how = by_code.get(tag, []), "code"
                if len(hits) != 1:
                    # Fall back to the model number in the filename.
                    cand = {}
                    for w in models(f.stem):
                        for it in by_model.get(w, []):
                            cand[it["key"]] = it
                    hits, how = list(cand.values()), "model"
                if len(hits) != 1:
                    unmatched.append((num, state, f.name, len(hits)))
                    continue
                it = hits[0]
                rf = reviews.get(tag)
                remark = date = ""
                if rf:
                    d = fitz.open(rf)
                    txt = " ".join(" ".join(d[p].get_text().split())
                                   for p in range(d.page_count))
                    d.close()
                    sm = STAMP.search(txt)
                    if sm:
                        date, remark = sm.group(1), sm.group(2)
                if not remark and pkg:
                    remark = pkg
                st, note = verdict(remark)
                found.append(dict(key=it["key"], code=it["group"] + "-" + it["code"],
                                  title=it["title"], sub="JANU-SUB-" + num,
                                  state=state, status=st, note=note,
                                  remark=remark, date=date, how=how))

    # One row per item. The record carries the same item more than once on
    # purpose - the sheet as submitted, the sheet as reviewed, and sometimes an
    # "As Specified" beside a "Proposed Substitute" - and all of them name the
    # same register item. The one that answers "where does this stand" is the
    # one carrying a verdict.
    best = {}
    for r in found:
        cur = best.get(r["key"])
        if cur is None:
            best[r["key"]] = r
        elif (bool(r["remark"]), r["state"] == "02 Returned") > (
              bool(cur["remark"]), cur["state"] == "02 Returned"):
            best[r["key"]] = r
    dropped = len(found) - len(best)
    found = list(best.values())
    found.sort(key=lambda r: (r["sub"], r["code"]))
    OUT.write(("%d register items matched, %d duplicate sheets collapsed" + chr(10) + chr(10)) % (len(found), dropped))
    cur = None
    for r in found:
        if r["sub"] != cur:
            cur = r["sub"]
            OUT.write("\n%s   (%s)\n" % (cur, [x for x in found if x["sub"] == cur][0]["state"]))
        OUT.write("  %-8s %-20s %-46s %s\n"
                  % (r["code"], r["status"], r["title"][:46],
                     ("[" + r["how"] + "] " + (r["note"] or r["remark"])[:40]).strip()))

    if unmatched:
        OUT.write("\n--- sheets that matched no single item (%d) ---\n" % len(unmatched))
        for num, state, n, c in unmatched:
            OUT.write("  SUB-%s %-52s %d candidates\n" % (num, n[:52], c))
    if no_items:
        OUT.write("\n--- submittals with no item sheets, so nothing to link (%d) ---\n"
                  % len(no_items))
        for state, n, c in no_items:
            OUT.write("  %-12s %-52s %d pdfs\n" % (state, n[:52], c))

    import collections
    OUT.write("\n--- what would be written ---\n")
    for st, n in collections.Counter(r["status"] for r in found).most_common():
        OUT.write("  %-20s %d\n" % (st, n))

    (REPO / "tools/submittal-map.json").write_text(
        json.dumps(found, indent=1, ensure_ascii=False), encoding="utf-8")
    OUT.write("\nwrote tools/submittal-map.json\n")

    if not args.apply:
        OUT.write("report only - pass --apply to write these into item_state\n")
        return

    key = subprocess.run(["supabase", "projects", "api-keys", "--project-ref", REF,
                          "-o", "json"], capture_output=True, text=True).stdout
    rows = json.loads(key)
    rows = rows if isinstance(rows, list) else rows.get("api_keys", rows)
    svc = next(k.get("api_key") or k.get("apiKey") for k in rows
               if k.get("name") == "service_role")

    body = [dict(item_key=r["key"], status=r["status"], status_note=r["note"])
            for r in found]
    req = urllib.request.Request(
        BASE + "/rest/v1/item_state", method="POST",
        data=json.dumps(body).encode())
    for h, v in (("apikey", svc), ("Authorization", "Bearer " + svc),
                 ("Content-Type", "application/json"),
                 ("Content-Profile", "gp1"),
                 ("Prefer", "resolution=merge-duplicates,return=representation")):
        req.add_header(h, v)
    try:
        with urllib.request.urlopen(req) as r:
            got = json.loads(r.read().decode())
        OUT.write("wrote %d rows to gp1.item_state\n" % len(got))
    except urllib.error.HTTPError as e:
        OUT.write("FAILED %s: %s\n" % (e.code, e.read().decode()[:300]))
        sys.exit(1)


if __name__ == "__main__":
    main()
