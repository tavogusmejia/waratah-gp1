"""One command for each thing this project does.

Before this, every task was a path to a script that had to be remembered or
looked up, and half of them were only ever run by me. They are all here now.

    python tools/run.py                 what the options are
    python tools/run.py build           rebuild the two side pages
    python tools/run.py probe           every browser probe, headless
    python tools/run.py rls             the live row-level-security suite
    python tools/run.py links           are the register's links still alive
    python tools/run.py orphans         state attached to items that are gone
    python tools/run.py changelog       regenerate CHANGELOG.md
    python tools/run.py check           build + probe + rls, which is what to
                                        run before pushing

`probe` serves web/ on a free port and drives each __probe_*.html through
headless Chrome, reading the verdict out of document.title. It exits non-zero
if any of them fails, so it can be the thing CI runs.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB = os.path.join(ROOT, "web")
PY = sys.executable

CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
          "/usr/bin/google-chrome", "/usr/bin/chromium",
          "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]


def chrome():
    for c in CHROME:
        if os.path.exists(c):
            return c
    found = shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("chromium")
    if not found:
        sys.exit("No Chrome found. The probes need one; set one of: " + ", ".join(CHROME))
    return found


def run(args, **kw):
    print("  $ " + " ".join(str(a) for a in args))
    return subprocess.call(args, **kw)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def serve(port):
    """A server rooted at web/ and nowhere else.

    --directory is not optional here. Starting it with a cd and a background &
    left stale servers from other directories holding the port, and one of them
    served an older copy of a page for three runs before anybody noticed.
    """
    p = subprocess.Popen(
        [PY, "-m", "http.server", str(port), "--directory", WEB],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/index.html" % port, timeout=1)
            return p
        except Exception:                                    # noqa: BLE001
            time.sleep(0.2)
    p.kill()
    sys.exit("the test server would not start")


def cmd_build():
    return run([PY, os.path.join(HERE, "build_site_pages.py")])


def cmd_probe():
    probes = sorted(f for f in os.listdir(WEB)
                    if f.startswith("__probe_") and f.endswith(".html")
                    and f not in ("__probe_workflow.html", "__probe_register.html"))
    port = free_port()
    srv = serve(port)
    exe = chrome()
    bad = 0
    try:
        for f in probes:
            out = subprocess.run(
                [exe, "--headless", "--disable-gpu", "--no-sandbox",
                 "--virtual-time-budget=30000", "--window-size=1500,1000",
                 "--dump-dom", "http://127.0.0.1:%d/%s" % (port, f)],
                capture_output=True, timeout=120).stdout.decode("utf-8", "replace")
            m = re.search(r"<title[^>]*>(.*?)</title>", out, re.S)
            title = re.sub(r"\s+", " ", m.group(1)).strip() if m else "(no title)"
            ok = title.startswith("R:PASS")
            if not ok:
                bad += 1
            print("  %-26s %s" % (f, ("PASS  " if ok else "FAIL  ") + title[:90]))
    finally:
        srv.kill()
    print("  %d probes, %d failed" % (len(probes), bad))
    return 1 if bad else 0


def cmd_rls():
    return run([PY, os.path.join(HERE, "test_rls.py")])


def cmd_links():
    return run([PY, os.path.join(HERE, "check_links.py")])


def cmd_orphans():
    return run([PY, os.path.join(HERE, "orphans.py")])


def cmd_changelog():
    return run([PY, os.path.join(HERE, "changelog.py")])


def cmd_check():
    for fn in (cmd_build, cmd_probe, cmd_rls):
        rc = fn()
        if rc:
            print("\n  stopped: %s failed" % fn.__name__[4:])
            return rc
    print("\n  all green")
    return 0


TASKS = {"build": cmd_build, "probe": cmd_probe, "rls": cmd_rls, "links": cmd_links,
         "orphans": cmd_orphans, "changelog": cmd_changelog, "check": cmd_check}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in TASKS:
        print(__doc__)
        sys.exit(0 if len(sys.argv) < 2 else 2)
    sys.exit(TASKS[sys.argv[1]]() or 0)
