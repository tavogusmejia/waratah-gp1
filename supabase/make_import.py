#!/usr/bin/env python3
"""
Generate supabase/import-seed.sql - import.sql with the seed payload inlined.

The payload is ~154 KB. Committing it would duplicate web/data/seed.json in the
repo and guarantee the two drift apart, so the file is generated and gitignored.
Regenerate it whenever the seed changes.

Usage:
    python supabase/make_import.py
    python supabase/make_import.py --chunks 4     # split for the web SQL editor

One 117 KB statement is fine for psql and can be slow or unresponsive in the
browser editor, which is a textarea in a Monaco instance rather than a file
upload. --chunks writes N numbered files to paste one after another. The insert
is an idempotent upsert on the primary key, so the chunks are order-independent
and safe to re-run.

Usage:
    python supabase/make_import.py
    # then paste supabase/import-seed.sql into the Supabase SQL editor
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = HERE.parent / "web" / "data" / "seed.json"
TEMPLATE = HERE / "import.sql"
OUT = HERE / "import-seed.sql"

MARKER = "'[]'::jsonb"


def render(template: str, items: list) -> str:
    # Postgres string literals: the only character that needs escaping inside
    # a single-quoted literal is the single quote itself, doubled. The JSON is
    # already valid UTF-8 text and jsonb will parse it as-is.
    payload = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    return template.replace(MARKER, "'" + payload.replace("'", "''") + "'::jsonb")


def main() -> None:
    chunks = 1
    if "--chunks" in sys.argv:
        chunks = int(sys.argv[sys.argv.index("--chunks") + 1])
        if chunks < 1:
            raise SystemExit("FAIL: --chunks must be 1 or more")

    data = json.loads(SEED.read_text(encoding="utf-8"))
    items = data["items"]

    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(MARKER) != 1:
        raise SystemExit("FAIL: import.sql must contain exactly one %s" % MARKER)

    documented = sum(1 for i in items if i["spec_url"] or i["folder_url"])
    trades = len({i["discipline_code"] for i in items})

    if chunks == 1:
        sql = render(template, items)
        OUT.write_text(sql, encoding="utf-8")
        print("OK: wrote %s (%.0f KB)" % (OUT.name, len(sql.encode("utf-8")) / 1024))
    else:
        size = -(-len(items) // chunks)          # ceiling division
        written = []
        for n in range(chunks):
            part = items[n * size:(n + 1) * size]
            if not part:
                continue
            path = HERE / ("import-seed-%dof%d.sql" % (n + 1, chunks))
            sql = render(template, part)
            path.write_text(sql, encoding="utf-8")
            written.append((path.name, len(part), len(sql.encode("utf-8"))))
        print("OK: wrote %d files" % len(written))
        for name, n, size_b in written:
            print("  %-26s %3d items  %4.0f KB" % (name, n, size_b / 1024))
        print("\nRun them in order. Each ends with a running count, so the last\n"
              "one should report items = %d." % len(items))

    print("  items      : %d" % len(items))
    print("  documented : %d" % documented)
    print("  trades     : %d" % trades)
    print("\nPaste into the Supabase SQL editor, or:")
    print("  psql \"$DATABASE_URL\" -f supabase/import-seed.sql")


if __name__ == "__main__":
    main()
