"""Does everything the register points at still exist?

Three kinds of link, three different ways of being dead:

  MANUFACTURER PAGES  A 200 proves nothing on its own. A maker who withdraws a
      product often redirects to the family page or the home page and answers
      200 the whole way, so this records the FINAL url and says when it is no
      longer the one we stored. It also reads the page title, because
      "Product archive" and "Page not found" arrive with a 200 more often than
      they should.

  DRIVE LINKS  Google answers 200 with a request-access wall, so a status code
      is worthless here. The only honest test is the page title: a readable
      file puts its own name in it.

  WHAT WE SHIP  Images and data files referenced by the catalogue, checked on
      disk. A missing one currently shows as a blank tile and says nothing.

    python tools/check_links.py              everything
    python tools/check_links.py --maker      just the manufacturer pages
    python tools/check_links.py --local      just what we ship, no network
"""
import argparse
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB = os.path.join(ROOT, "web")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

# Titles that mean "gone" while the server says 200.
DEAD = re.compile(r"page not found|not found|404|no longer available|"
                  r"product archive|discontinued|doesn.t exist|"
                  r"page introuvable|pagina non trovata", re.I)


def fetch(url, timeout=25):
    """Final url, status, title. Never raises."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(200000)
            final = r.geturl()
            code = r.getcode()
    except urllib.error.HTTPError as e:
        return {"final": url, "code": e.code, "title": "", "err": ""}
    except Exception as e:                                   # noqa: BLE001
        return {"final": url, "code": 0, "title": "", "err": type(e).__name__}
    try:
        text = body.decode("utf-8", "replace")
    except Exception:                                        # noqa: BLE001
        text = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    title = re.sub(r"\s+", " ", m.group(1)).strip()[:160] if m else ""
    return {"final": final, "code": code, "title": title, "err": ""}


CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]


def browser(url, timeout=45):
    """Second opinion, through a real browser.

    A third of these hosts answer 403 to anything that is not a browser -
    Hafele, Assa Abloy, Lutron, Ferguson all do - and ABB simply drops the
    connection. That is a bot check, not a dead page, and reporting it as
    "worth a look" 24 times teaches whoever reads this to ignore the report.
    Chrome gets through, so the ones that cannot be settled cheaply get
    settled expensively instead of being left ambiguous.
    """
    exe = next((c for c in CHROME if os.path.exists(c)), None)
    if not exe:
        return None
    import subprocess
    try:
        out = subprocess.run(
            [exe, "--headless", "--disable-gpu", "--no-sandbox",
             "--virtual-time-budget=12000", "--dump-dom", url],
            capture_output=True, timeout=timeout).stdout.decode("utf-8", "replace")
    except Exception:                                        # noqa: BLE001
        return None
    m = re.search(r"<title[^>]*>(.*?)</title>", out, re.S | re.I)
    return {"title": re.sub(r"\s+", " ", m.group(1)).strip()[:160] if m else "",
            "bytes": len(out)}


def same_page(a, b):
    """Is the final url still the page we stored, ignoring noise?"""
    def norm(u):
        u = re.sub(r"[?#].*$", "", u.lower()).rstrip("/")
        return re.sub(r"^https?://(www\.)?", "", u)
    return norm(a) == norm(b)


def live_links():
    """The manufacturer links as they are NOW: the table overrides the build."""
    out = {}
    d = json.load(io.open(os.path.join(WEB, "data/datasheets.json"), encoding="utf-8"))
    for it in d["items"]:
        if it.get("maker_url"):
            out[it["key"]] = it["maker_url"]
    cfg = io.open(os.path.join(WEB, "assets/config.js"), encoding="utf-8").read()
    base = re.search(r"https://[a-z0-9]+\.supabase\.co", cfg)
    key = re.search(r"[A-Za-z0-9._-]{80,}", cfg)
    if base and key:
        req = urllib.request.Request(
            base.group(0) + "/rest/v1/maker_link_public?select=item_key,url&limit=1000")
        req.add_header("apikey", key.group(0))
        req.add_header("Accept-Profile", "gp1")
        try:
            for r in json.load(urllib.request.urlopen(req, timeout=30)):
                out[r["item_key"]] = r["url"]
        except Exception as e:                               # noqa: BLE001
            sys.stderr.write("  (could not read the live links: %s)\n" % e)
    return d, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maker", action="store_true")
    ap.add_argument("--drive", action="store_true")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    everything = not (a.maker or a.drive or a.local)

    data, makers = live_links()
    items = {it["key"]: it for it in data["items"]}
    report = {"maker": [], "drive": [], "local": []}

    # ---- what we ship, checked on disk ----
    if everything or a.local:
        print("\nWHAT WE SHIP")
        miss = []
        for it in data["items"]:
            for rel in ([it["image"]] if it.get("image") else []):
                if not os.path.exists(os.path.join(WEB, rel)):
                    miss.append((it["code"], rel))
        for code, rel in miss:
            print("  MISSING  %-9s %s" % (code, rel))
            report["local"].append({"code": code, "path": rel})
        print("  %d image paths, %d missing" %
              (sum(1 for x in data["items"] if x.get("image")), len(miss)))
        # and anything in img/ that nothing references
        used = {x["image"] for x in data["items"] if x.get("image")}
        orphan = [f for f in os.listdir(os.path.join(WEB, "img"))
                  if ("img/" + f) not in used]
        if orphan:
            print("  %d images in web/img that no item references: %s%s" %
                  (len(orphan), ", ".join(orphan[:6]), " ..." if len(orphan) > 6 else ""))
            report["local"].append({"orphan_images": orphan})

    # ---- manufacturer pages ----
    if everything or a.maker:
        print("\nMANUFACTURER PAGES  (%d)" % len(makers))
        keys = sorted(makers)
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            res = list(ex.map(lambda k: (k, fetch(makers[k])), keys))
        for k, r in res:
            it = items.get(k, {})
            flag = ""
            if r["code"] == 0:
                flag = "UNREACHABLE (%s)" % r["err"]
            elif r["code"] == 403:
                flag = "403 - blocked to us, not necessarily dead"
            elif r["code"] >= 400:
                flag = "%d" % r["code"]
            elif DEAD.search(r["title"] or ""):
                flag = "200 but the title says gone: %s" % r["title"][:70]
            elif not same_page(r["final"], makers[k]):
                flag = "redirected -> %s" % r["final"][:90]
            if flag:
                print("  %-9s %-22s %s" % (it.get("code", k),
                                           (it.get("manufacturer") or "")[:22], flag))
                report["maker"].append({"key": k, "code": it.get("code"),
                                        "url": makers[k], **r, "flag": flag})
        # Settle the ones a script cannot judge.
        hard = [r for r in report["maker"]
                if r["code"] in (0, 403) or r["code"] >= 500]
        if hard:
            print("  re-checking %d through a browser…" % len(hard))
            settled = 0
            for r in hard:
                b = browser(r["url"])
                if not b:
                    r["browser"] = "could not run a browser"
                    continue
                r["browser_title"] = b["title"]
                if b["title"] and not DEAD.search(b["title"]):
                    r["flag"] = "fine in a browser: " + b["title"][:70]
                    settled += 1
                elif DEAD.search(b["title"] or ""):
                    r["flag"] = "GONE - " + b["title"][:70]
                else:
                    r["flag"] = "still unreadable (%d bytes, no title)" % b["bytes"]
            print("  %d of them are fine, the browser just had to ask" % settled)
            for r in report["maker"]:
                if r.get("browser_title") and not r["flag"].startswith("fine"):
                    print("    %-9s %s" % (r.get("code2") or r.get("code"), r["flag"]))
        real = [r for r in report["maker"] if not r["flag"].startswith("fine")]
        print("  %d checked, %d healthy, %d worth a look" %
              (len(keys), len(keys) - len(real), len(real)))

    # ---- drive ----
    if everything or a.drive:
        urls = []
        for it in data["items"]:
            if it.get("drive_url"):
                urls.append((it["code"], it["drive_url"]))
            for x in (it.get("extras") or []):
                if x.get("drive_url"):
                    urls.append((it["code"] + "/" + x.get("kind", "extra"), x["drive_url"]))
        print("\nDRIVE LINKS  (%d)" % len(urls))
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            res = list(ex.map(lambda t: (t[0], fetch(t[1])), urls))
        for code, r in res:
            t = r["title"] or ""
            # A readable file names itself. The wall says so in the title too.
            ok = t and not re.search(r"request access|sign in|accounts\.google", t, re.I)
            if not ok:
                print("  %-14s %s" % (code, (t or "no title, status %s" % r["code"])[:80]))
                report["drive"].append({"code": code, **r})
        print("  %d checked, %d not readable" % (len(urls), len(report["drive"])))

    # ---- one url doing duty for several items ----
    if everything or a.maker:
        print("
ONE PAGE, SEVERAL ITEMS")
        print("  A product page names a product. A url shared by five items is")
        print("  a family page, which is sometimes right and always worth knowing.")
        share = {}
        for k, u in makers.items():
            share.setdefault(u, []).append(k)
        n = 0
        for u, keys in sorted(share.items(), key=lambda t: -len(t[1])):
            if len(keys) < 2:
                continue
            n += 1
            titles = {items[k]["title"] for k in keys if k in items}
            codes = [items[k]["code"] for k in sorted(keys) if k in items]
            kind = ("THE SAME PRODUCT under two codes" if len(titles) == 1
                    else "a family page")
            print("  %d items - %s" % (len(keys), kind))
            print("      %s" % u[:96])
            print("      %s" % ", ".join(codes))
            report.setdefault("shared", []).append(
                {"url": u, "codes": codes, "same_product": len(titles) == 1})
        print("  %d shared urls" % n)

    out = os.path.join(HERE, "audit", "_links_health.json")
    io.open(out, "w", encoding="utf-8").write(
        json.dumps(report, indent=1, ensure_ascii=False))
    print("\nwrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
