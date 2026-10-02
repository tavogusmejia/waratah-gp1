"""Carry the manufacturer links from the retired H items to their PD successors.

Matched on the PART NUMBER, which both the saved url and the new source
filename carry. Where the part changed, nothing is carried: a link to the old
thermostat sitting on the new one is worse than no link at all.

A fuzzy name fallback was tried and removed. It matched h-h5 and h-h5.2 - the
two parts that CHANGED - onto PD5A, on the shared words "xtool concealed
thermostat", which is precisely the mistake the part-number rule exists to
prevent. It also still missed the one case it was written for. One explicit
exception, with its reason, beats a heuristic that is wrong in both directions.
"""
import json, io, os, re, subprocess, sys, urllib.request

ROOT = r"C:\Users\gus\Dropbox\06 Apps\Waratah-gp1"
REF = "iygkonfuyslvgezgofby"
BASE = "https://%s.supabase.co" % REF
APPLY = "--apply" in sys.argv

# The one link whose part number is not in its url. TOTO's page is
# /neorest-wx1-wall-hung-toilet and carries no code at all, while PD8 is
# "TOTO Neorest WX1 Wall-Hung Toilet - CWT9538CEMFG" - the same product under
# the same name. Written down rather than guessed at by a matcher.
BY_HAND = {"h-h8": "pd-pd8"}


def svc():
    out = subprocess.run(["supabase", "projects", "api-keys", "--project-ref", REF,
                          "-o", "json"], capture_output=True, timeout=120
                         ).stdout.decode("utf-8", "replace")
    return next(k["api_key"] for k in json.loads(out) if k["name"] == "service_role")


def call(method, path, key, body=None, prefer=None):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 method=method)
    for k, v in {"apikey": key, "Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "Accept-Profile": "gp1", "Content-Profile": "gp1"}.items():
        req.add_header(k, v)
    if prefer:
        req.add_header("Prefer", prefer)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.getcode(), (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def part(text):
    m = re.search(r"(\d{8}-\d{2,6}|\d{10}|CWT\d+[A-Z]+)", text)
    return m.group(1) if m else None


key = svc()
d = json.load(io.open(os.path.join(ROOT, "web/data/datasheets.json"), encoding="utf-8"))
_, links = call("GET", "/rest/v1/maker_link_public?select=item_key,url&limit=1000", key)
old = {r["item_key"]: r["url"] for r in links if r["item_key"].startswith("h-h")}
new = {x["key"]: x for x in d["items"] if x["group"] == "PD"}
by_part = {}
for k, x in new.items():
    pn = part(x["source"])
    if pn:
        by_part[pn] = k

moved, left = [], []
for hk, url in sorted(old.items()):
    pn = part(url)
    dest = by_part.get(pn) if pn else None
    how = "part " + (pn or "")
    if not dest and hk in BY_HAND:
        dest, how = BY_HAND[hk], "by hand, same product"
    (moved if dest else left).append((hk, how, dest, url))

print("CARRIED OVER")
for hk, how, dest, url in moved:
    print("  %-10s -> %-10s  (%s)" % (hk, dest, how))
print("\nLEFT BEHIND - the part changed, so the old link does not describe the new item")
for hk, how, dest, url in left:
    print("  %-10s %s" % (hk, url[:78]))

if not APPLY:
    print("\nDry run. Pass --apply to write.")
    raise SystemExit

for hk, how, dest, url in moved:
    st, b = call("POST", "/rest/v1/maker_link", key,
                 {"item_key": dest, "url": url, "by_email": "system"},
                 prefer="return=representation,resolution=merge-duplicates")
    if st in (200, 201):
        st2, _ = call("DELETE", "/rest/v1/maker_link?item_key=eq." + hk, key)
        print("  %-10s -> %-10s written, old row %s"
              % (hk, dest, "removed" if st2 in (200, 204) else "DELETE FAILED %s" % st2))
    else:
        print("  %-10s FAILED %s %s" % (hk, st, str(b)[:80]))
print("\n%d carried, %d left for a person." % (len(moved), len(left)))
