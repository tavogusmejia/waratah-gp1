#!/usr/bin/env python3
"""
Apply the GP1-MUR schema, policies and seed to Supabase over a direct
connection, and verify the result.

Pasting a 117 KB statement into the browser SQL editor turned out to be the
fragile part of this setup - a partial select-all silently merges the paste
with whatever was in the tab and the payload stops being valid SQL. A real
connection has no such failure mode, and it can check its own work afterwards,
which a paste cannot.

The script is idempotent: it looks at what already exists and applies only the
missing pieces, so it is safe to run against a fresh project, a half-finished
one, or a fully populated one.

Reads DATABASE_URL from .env.local at the repo root (gitignored) or from the
environment. Nothing is printed that would reveal the password.

Usage:
    python supabase/apply.py            # apply what is missing, then verify
    python supabase/apply.py --verify   # verify only, change nothing
    python supabase/apply.py --reset    # DROP SCHEMA gp1 CASCADE first
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:
    import psycopg
except ModuleNotFoundError:
    raise SystemExit(
        "FAIL: psycopg is not installed.\n"
        "      python -m pip install \"psycopg[binary]\""
    )

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ENV = ROOT / ".env.local"


def die(msg: str) -> None:
    raise SystemExit("FAIL: " + msg)


def redact(text: str) -> str:
    """Never let a password reach the terminal, including inside an error."""
    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", text)


def dsn() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url and ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not url:
        die("no DATABASE_URL. Put it in .env.local - see the comments in that file.")
    if "[YOUR-PASSWORD]" in url or "PASSWORD@" in url:
        die("DATABASE_URL still has the placeholder password in it.")
    if ":6543" in url:
        print("  ! port 6543 is the transaction pooler, which cannot run this DDL.")
        print("    Use the session pooler or direct connection (port 5432).")
    return url


def sql_file(name: str) -> str:
    p = HERE / name
    if not p.exists():
        die("missing %s - run: python supabase/make_import.py" % name)
    return p.read_text(encoding="utf-8")


def state(cur) -> dict:
    cur.execute("""
        select
          to_regnamespace('gp1')               is not null,
          to_regclass('gp1.register_item')     is not null,
          to_regclass('gp1.register_editor')   is not null,
          to_regclass('gp1.register_coverage') is not null,
          (select count(*) from pg_policies where schemaname = 'gp1')
    """)
    schema, item, editor, cov, policies = cur.fetchone()
    items = 0
    if item:
        cur.execute("select count(*) from gp1.register_item")
        items = cur.fetchone()[0]
    return {"schema": schema, "item": item, "editor": editor,
            "coverage": cov, "policies": policies, "items": items}


def report(cur) -> bool:
    s = state(cur)
    print("\n  current state")
    print("    gp1 schema        : %s" % ("yes" if s["schema"] else "NO"))
    print("    register_item     : %s" % ("yes" if s["item"] else "NO"))
    print("    register_editor   : %s" % ("yes" if s["editor"] else "NO"))
    print("    register_coverage : %s" % ("yes" if s["coverage"] else "NO"))
    print("    policies          : %d" % s["policies"])
    print("    items             : %d" % s["items"])

    if not s["item"]:
        return False

    cur.execute("""
        select count(*),
               count(*) filter (where spec_url <> '' or folder_url <> ''),
               count(distinct discipline_code),
               count(*) filter (where updated_at is null)
        from gp1.register_item
    """)
    n, documented, trades, null_dates = cur.fetchone()

    print("\n  data")
    print("    items      : %d   %s" % (n, "OK" if n == 199 else "EXPECTED 199"))
    print("    documented : %d   %s" % (documented, "OK" if documented == 71 else "EXPECTED 71"))
    print("    trades     : %d   %s" % (trades, "OK" if trades == 13 else "EXPECTED 13"))
    print("    null updated_at : %d   %s" % (null_dates, "OK" if not null_dates else "SHOULD BE 0"))

    cur.execute("""
        select tablename, policyname, cmd from pg_policies
        where schemaname = 'gp1' order by tablename, policyname
    """)
    print("\n  policies")
    for t, p, c in cur.fetchall():
        print("    %-16s %-28s %s" % (t, p, c))

    # The grants that decide whether the anon key can see anything at all.
    cur.execute("""
        select grantee, privilege_type
        from information_schema.role_table_grants
        where table_schema = 'gp1' and table_name = 'register_item'
          and grantee in ('anon', 'authenticated')
        order by grantee, privilege_type
    """)
    print("\n  grants on register_item")
    for g, p in cur.fetchall():
        print("    %-14s %s" % (g, p))

    return n == 199 and documented == 71 and trades == 13 and s["policies"] >= 3


def main() -> None:
    verify_only = "--verify" in sys.argv
    do_reset = "--reset" in sys.argv

    url = dsn()
    print("connecting ...")
    try:
        conn = psycopg.connect(url, connect_timeout=20)
    except Exception as e:
        die("could not connect: " + redact(str(e)))

    conn.autocommit = False
    with conn, conn.cursor() as cur:
        cur.execute("select current_database(), current_user, version()")
        db, user, ver = cur.fetchone()
        print("  database %s as %s" % (db, user))
        print("  %s" % ver.split(",")[0])

        if verify_only:
            ok = report(cur)
            print("\n%s" % ("ALL CHECKS PASSED" if ok else "not complete yet"))
            return

        if do_reset:
            print("\n  --reset: dropping schema gp1 ...")
            cur.execute("drop schema if exists gp1 cascade")
            conn.commit()

        s = state(cur)

        if not s["item"]:
            print("\n  applying schema.sql ...")
            cur.execute(sql_file("schema.sql"))
            conn.commit()
            print("    done")
        else:
            print("\n  schema.sql already applied, skipping")

        if not s["editor"] or s["policies"] < 3:
            print("  applying policies.sql ...")
            cur.execute(sql_file("policies.sql"))
            conn.commit()
            print("    done")
        else:
            print("  policies.sql already applied, skipping")

        print("  applying import-seed.sql ...")
        cur.execute(sql_file("import-seed.sql"))
        conn.commit()
        print("    done")

        ok = report(cur)
        print("\n%s" % ("ALL CHECKS PASSED" if ok else "SOMETHING IS OFF - see above"))
        if ok:
            print("\nNext: Settings -> API -> Exposed schemas -> add `gp1`,")
            print("      then send the project URL and anon key.")


if __name__ == "__main__":
    main()
