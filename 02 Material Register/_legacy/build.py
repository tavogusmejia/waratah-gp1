#!/usr/bin/env python3
"""
Build register.html from register.template.html + seed.json.

The template/build split is a local authoring convenience only. Once the page
is published it maintains itself: it rebuilds its own complete document from
the three id-addressed payloads and republishes. So this script seeds the
FIRST version - after that, the live artifact is the master record.

IMPORTANT: before regenerating and republishing over a live artifact, export
the current JSON from the page and put it in seed.json first, or the owner's
edits are replaced by whatever this seed holds.

Usage:
    python build.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "register.template.html"
SEED = HERE / "seed.json"
OUT = HERE / "register.html"

PLACEHOLDER = "__DATA_JSON__"

# A value carrying any of these would terminate the data block or the script
# and break the published page permanently, with no way to repair it in place.
UNSAFE = {
    chr(0x2028): "U+2028 line separator",
    chr(0x2029): "U+2029 paragraph separator",
}


def die(msg):
    print("FAIL: " + msg, file=sys.stderr)
    raise SystemExit(1)


def escape_for_html(payload: str) -> str:
    """Escape the characters that could break out of the data block."""
    out = []
    for ch in payload:
        if ch in "<>&" or ch in UNSAFE:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if not TEMPLATE.exists():
        die("missing %s" % TEMPLATE.name)
    if not SEED.exists():
        die("missing %s - run extract_seed.py first" % SEED.name)

    template = TEMPLATE.read_text(encoding="utf-8")
    data = json.loads(SEED.read_text(encoding="utf-8"))

    if template.count(PLACEHOLDER) != 1:
        die("template must contain exactly one %s" % PLACEHOLDER)

    # The structural invariant the page depends on to save itself: exactly one
    # real element per id. The app source also *mentions* these ids - it has to,
    # since it rebuilds the document - so match only elements at column 0, where
    # the template writes its real markup.
    for pattern, ident in (
        (r'^<style id="gp1-style">', "gp1-style"),
        (r'^<script type="application/json" id="gp1-data">', "gp1-data"),
        (r'^<script id="gp1-app">', "gp1-app"),
    ):
        n = len(re.findall(pattern, template, re.M))
        if n != 1:
            die('template has %d top-level elements with id="%s"; exactly 1 required'
                % (n, ident))

    payload = escape_for_html(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    html = template.replace(PLACEHOLDER, payload)

    # Nothing may close the script or data block early.
    closers = len(re.findall(r"</script>", html))
    if closers != 2:
        die("expected exactly 2 literal </script> closers, found %d" % closers)

    OUT.write_text(html, encoding="utf-8")

    items = data["items"]
    documented = sum(1 for i in items if i["spec_url"] or i["folder_url"])
    print("OK: wrote %s  (%.0f KB)" % (OUT.name, len(html.encode("utf-8")) / 1024))
    print("  items      : %d" % len(items))
    print("  documented : %d / %d" % (documented, len(items)))
    print("  rev        : %s" % data["meta"].get("rev"))


if __name__ == "__main__":
    main()
