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

import base64
import json
import re
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


# The payload is base64 here, and that is not paranoia.
#
# The JSON contains 23 semicolons - "Lever handle set; NE-Black Chrome" and
# friends. The Supabase web SQL editor splits a script on semicolons WITHOUT
# respecting string literals, so it cut the statement in the middle of the
# payload and handed Postgres the remainder as if it were SQL. The fragment
# held "Sliding glazed door into pocket (19 ft ...", which is how the error
# came back as: relation "pocket" does not exist.
#
# Base64 is [A-Za-z0-9+/=] only. No semicolons, no quotes, no backslashes, no
# comment markers - nothing any splitter or lexer can trip over. decode() turns
# it back into bytes, convert_from() into text, and ::jsonb into the same value
# it always was.
PASTE_TEMPLATE = """-- GP1-MUR register import: part {n} of {total} ({count} items, seq {lo}-{hi}).
-- Paste into a NEW query tab. Safe to re-run.
-- Payload is base64 so it holds no punctuation the editor can split on.

insert into gp1.register_item (
  id, seq, discipline_code, discipline, sub_category,
  code_tag, code_new, item, location, manufacturer, model,
  qty, qty_raw, unit, drawing_ref, spec_url, folder_url,
  spec_status, approved, procured, notes, source_sheet, source_row
)
select
  id, seq, discipline_code, discipline, sub_category,
  code_tag, code_new, item, location, manufacturer, model,
  qty, qty_raw, unit, drawing_ref, spec_url, folder_url,
  spec_status, approved, procured, notes, source_sheet, source_row
from jsonb_populate_recordset(
  null::gp1.register_item,
  convert_from(decode('{b64}', 'base64'), 'UTF8')::jsonb
)
on conflict (id) do update set
  seq             = excluded.seq,
  discipline_code = excluded.discipline_code,
  discipline      = excluded.discipline,
  sub_category    = excluded.sub_category,
  code_tag        = excluded.code_tag,
  item            = excluded.item,
  location        = excluded.location,
  manufacturer    = excluded.manufacturer,
  model           = excluded.model,
  qty             = excluded.qty,
  qty_raw         = excluded.qty_raw,
  unit            = excluded.unit,
  drawing_ref     = excluded.drawing_ref,
  source_sheet    = excluded.source_sheet,
  source_row      = excluded.source_row;

select count(*) as items_loaded_so_far from gp1.register_item;
"""


def write_paste_files(items: list, total: int) -> None:
    """Lean, single-statement files sized for the browser SQL editor."""
    out_dir = HERE / "paste"
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("*.sql"):
        old.unlink()

    size = -(-len(items) // total)
    written = []
    for n in range(total):
        part = items[n * size:(n + 1) * size]
        if not part:
            continue
        payload = json.dumps(part, ensure_ascii=False, separators=(",", ":"))
        b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        sql = PASTE_TEMPLATE.format(
            n=n + 1, total=total, count=len(part),
            lo=part[0]["seq"], hi=part[-1]["seq"],
            b64=b64,
        )
        # The whole point is that nothing in the payload can be mis-lexed, so
        # assert it rather than trust it. Exactly two semicolons may exist in
        # the file: the two statement terminators.
        if b64 != re.sub(r"[^A-Za-z0-9+/=]", "", b64):
            raise SystemExit("FAIL: base64 payload is not base64-clean")
        if sql.count(";") != 2:
            raise SystemExit("FAIL: part %d has %d semicolons, expected 2"
                             % (n + 1, sql.count(";")))
        # Six quotes exactly: around the payload, around 'base64', around 'UTF8'.
        if sql.count("'") != 6:
            raise SystemExit("FAIL: part %d has %d quotes, expected 6"
                             % (n + 1, sql.count("'")))
        path = out_dir / ("%d.sql" % (n + 1))
        path.write_text(sql, encoding="utf-8")
        written.append((path, len(part), len(sql.encode("utf-8"))))

    print("OK: wrote %d paste files to supabase/paste/" % len(written))
    for path, n, size_b in written:
        print("  %-28s %3d items  %4.0f KB" % (path.name, n, size_b / 1024))


def main() -> None:
    chunks = 1
    if "--paste" in sys.argv:
        total = int(sys.argv[sys.argv.index("--paste") + 1])
        data = json.loads(SEED.read_text(encoding="utf-8"))
        write_paste_files(data["items"], total)
        return
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
