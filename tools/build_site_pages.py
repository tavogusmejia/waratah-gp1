"""Build the two side pages the register links to.

    python tools/build_site_pages.py

`web/certification.html`  <- tools/site/certification.template.html + audit/_certs_final.json
`web/links.html`          <- tools/site/links.template.html        + audit/_links53.json

WHY THERE ARE TWO SETS OF TEMPLATES. The originals in tools/audit/ build the
claude.ai artifacts and are kept as the published snapshot. These build the
pages on the register site, and the two runtimes genuinely differ: the artifact
versions talk to the artifact database and ask claude.ai's permission to hand
over a file, while these talk to Supabase and use an ordinary download. Trying
to serve both from one file would mean a switch in every one of those places.
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def build(template, data_file, out, pick=None):
    rows = json.load(io.open(os.path.join(HERE, "audit", data_file), encoding="utf-8"))
    if pick:
        rows = [{k: r[k] for k in pick} for r in rows]
    t = io.open(os.path.join(HERE, "site", template), encoding="utf-8").read()
    if "__DATA__" not in t:
        raise SystemExit("no __DATA__ placeholder in " + template)
    body = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    if "</script>" in body:
        raise SystemExit("data would close the script tag early")
    p = os.path.join(ROOT, "web", out)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t.replace("__DATA__", body))
    print("%-24s %5d rows  %7d bytes" % (out, len(rows), os.path.getsize(p)))


build("certification.template.html", "_certs_final.json", "certification.html")
build("links.template.html", "_links53.json", "links.html",
      pick=("key", "code", "maker", "title", "guess", "drive", "pages"))
