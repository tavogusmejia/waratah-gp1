#!/usr/bin/env python3
"""
Generate supabase/import-seed.sql - import.sql with the seed payload inlined.

The payload is ~154 KB. Committing it would duplicate web/data/seed.json in the
repo and guarantee the two drift apart, so the file is generated and gitignored.
Regenerate it whenever the seed changes.

Usage:
    python supabase/make_import.py
    # then paste supabase/import-seed.sql into the Supabase SQL editor
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = HERE.parent / "web" / "data" / "seed.json"
TEMPLATE = HERE / "import.sql"
OUT = HERE / "import-seed.sql"


def main() -> None:
    data = json.loads(SEED.read_text(encoding="utf-8"))
    items = data["items"]

    # Postgres string literals: the only character that needs escaping inside
    # a single-quoted literal is the single quote itself, doubled. The JSON is
    # already valid UTF-8 text and jsonb will parse it as-is.
    payload = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    literal = payload.replace("'", "''")

    sql = TEMPLATE.read_text(encoding="utf-8")
    marker = "'[]'::jsonb"
    if sql.count(marker) != 1:
        raise SystemExit("FAIL: import.sql must contain exactly one %s" % marker)

    sql = sql.replace(marker, "'" + literal + "'::jsonb")
    OUT.write_text(sql, encoding="utf-8")

    documented = sum(1 for i in items if i["spec_url"] or i["folder_url"])
    trades = len({i["discipline_code"] for i in items})
    print("OK: wrote %s (%.0f KB)" % (OUT.name, len(sql.encode("utf-8")) / 1024))
    print("  items      : %d" % len(items))
    print("  documented : %d" % documented)
    print("  trades     : %d" % trades)
    print("\nPaste it into the Supabase SQL editor, or:")
    print("  psql \"$DATABASE_URL\" -f supabase/import-seed.sql")


if __name__ == "__main__":
    main()
