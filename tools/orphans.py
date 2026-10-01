"""What is attached to an item the register no longer has?

gp1.orphan_item_state() exists for this and had never been called once - it
could not be, because execute was granted to `authenticated` and the only
caller who wants it holds the service key, which is not `authenticated`. On
its first run it found ten invoice rows left behind by the RLS suite's own
cleanup.

    python tools/orphans.py

Reads the live keys out of web/data/datasheets.json, which is what the page
itself loads, so "live" means exactly what a visitor sees.
"""
import io
import json
import os
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = "iygkonfuyslvgezgofby"
BASE = "https://%s.supabase.co" % REF


def service_key():
    out = subprocess.run(
        ["supabase", "projects", "api-keys", "--project-ref", REF, "-o", "json"],
        capture_output=True, timeout=120).stdout.decode("utf-8", "replace")
    try:
        return next(k["api_key"] for k in json.loads(out) if k["name"] == "service_role")
    except Exception:                                        # noqa: BLE001
        sys.exit("Could not read the service key. Is the Supabase CLI logged in?")


def main():
    key = service_key()
    d = json.load(io.open(os.path.join(ROOT, "web/data/datasheets.json"), encoding="utf-8"))
    live = [x["key"] for x in d["items"]]
    req = urllib.request.Request(BASE + "/rest/v1/rpc/orphan_item_state",
                                 data=json.dumps({"live": live}).encode(),
                                 method="POST")
    for k, v in {"apikey": key, "Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "Accept-Profile": "gp1", "Content-Profile": "gp1"}.items():
        req.add_header(k, v)
    rows = json.load(urllib.request.urlopen(req, timeout=60))

    print("%d live item keys" % len(live))
    if not rows:
        print("CLEAN - every note, status, invoice, picture, flag and link "
              "belongs to an item that still exists.")
        return 0
    print("%d keys carry state and are not in the register:\n" % len(rows))
    for r in rows:
        bits = []
        if r["notes"]:
            bits.append("%d notes" % r["notes"])
        if r["invoices"]:
            bits.append("%d invoices" % r["invoices"])
        if r["status"]:
            bits.append("status %s" % r["status"])
        if r["picture"]:
            bits.append("a picture")
        if r["discontinued"]:
            bits.append("a discontinued flag")
        if r.get("maker_link"):
            bits.append("a manufacturer link")
        print("  %-34s %s" % (r["item_key"], ", ".join(bits)))
    print("\nNothing is deleted here. A key that looks orphaned may be an item "
          "mid-rename, and losing somebody's note to a tidy-up is worse than "
          "carrying a stale row.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
