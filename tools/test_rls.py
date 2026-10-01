"""End-to-end test of the permission model, against the live project.

Everything else in this repo tests the PAGE - that it offers the right
controls to the right role. That is the second line of defence. This tests the
first one: what the database itself allows, with a real signed-in session and
a real JWT, which is the only thing standing between a curious person with the
public anon key and your invoices.

The page's own test suite would pass in full against a database with row level
security switched off. This one would not.

It works by creating a throwaway account, walking it up through every role,
and asserting at each step what it can and cannot do - then deleting it and
everything it wrote. Nothing it touches uses a real item key.

    python tools/test_rls.py

Needs the service_role key to create and delete the test account, taken from
the Supabase CLI, never stored.
"""
import io, json, os, subprocess, sys, urllib.error, urllib.request, uuid

REF = "iygkonfuyslvgezgofby"
BASE = "https://%s.supabase.co" % REF
ITEM = "zz-rls-test"          # deliberately not a real item key
OUT = io.open(1, "w", encoding="utf-8", closefd=False)

passed = failed = 0


def keys():
    r = subprocess.run(["supabase", "projects", "api-keys", "--project-ref", REF,
                        "-o", "json"], capture_output=True, text=True)
    rows = json.loads(r.stdout)
    rows = rows if isinstance(rows, list) else rows.get("api_keys", rows)
    out = {}
    for k in rows:
        out[k.get("name")] = k.get("api_key") or k.get("apiKey")
    return out["anon"], out["service_role"]


ANON, SVC = keys()


def call(method, path, token, body=None, prefer=None, schema="gp1"):
    """Returns (status, parsed-or-text). A refusal is a status, not an
    exception - which is the whole point: PostgREST answers a forbidden write
    with 401/403, and an RLS-filtered read with 200 and an empty list."""
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("apikey", ANON)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    if schema:
        req.add_header("Accept-Profile", schema)
        req.add_header("Content-Profile", schema)
    if prefer:
        req.add_header("Prefer", prefer)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            try:
                return r.status, json.loads(raw)
            except ValueError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw


def ok(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        OUT.write("  PASS  %s\n" % name)
    else:
        failed += 1
        OUT.write("  FAIL  %s   %s\n" % (name, detail))


def admin(method, path, body=None, prefer=None, schema="gp1"):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("apikey", SVC)
    req.add_header("Authorization", "Bearer " + SVC)
    req.add_header("Content-Type", "application/json")
    if schema:
        req.add_header("Accept-Profile", schema)
        req.add_header("Content-Profile", schema)
    if prefer:
        req.add_header("Prefer", prefer)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def make_user(email, password):
    st, body = admin("POST", "/auth/v1/admin/users", schema=None, body={
        "email": email, "password": password, "email_confirm": True})
    if st not in (200, 201):
        OUT.write("could not create %s: %s %s\n" % (email, st, body))
        sys.exit(1)
    return body["id"]


def sign_in(email, password):
    st, body = call("POST", "/auth/v1/token?grant_type=password", ANON,
                    {"email": email, "password": password}, schema=None)
    if st != 200:
        OUT.write("could not sign in as %s: %s %s\n" % (email, st, body))
        sys.exit(1)
    return body["access_token"]


def set_role(email, **patch):
    admin("PATCH", "/rest/v1/register_user?email=eq." + email, body=patch)


def put_row(email, role):
    admin("POST", "/rest/v1/register_user", body={"email": email, "role": role},
          prefer="resolution=merge-duplicates")


def main():
    tag = uuid.uuid4().hex[:8]
    neutral = "gp1-rls-%s@example.com" % tag        # no domain rule covers this
    company = "gp1-rls-%s@waratahtci.com" % tag     # the domain rule does
    pw = "TestPassword%s1" % tag[:4].upper()
    uids = []

    try:
        OUT.write("creating two throwaway accounts\n")
        uids.append(make_user(neutral, pw))
        uids.append(make_user(company, pw))
        tok = sign_in(neutral, pw)

        # -- signed in, no role at all -------------------------------------
        OUT.write("\nsigned in, no role  (the default for anyone who signs up)\n")
        st, b = call("GET", "/rest/v1/item_status_public?select=item_key&limit=1", tok)
        ok("reads the public status view", st == 200, "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/item_note?select=id&limit=1", tok)
        ok("cannot read notes", st == 200 and b == [], "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/item_invoice?select=id&limit=1", tok)
        ok("cannot read invoices", st == 200 and b == [], "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/item_note", tok,
                     {"item_key": ITEM, "body": "should not land"})
        ok("cannot write a note", st in (401, 403), "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/item_state", tok,
                     {"item_key": ITEM, "status": "approved"})
        ok("cannot set a status", st in (401, 403), "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/item_discontinued", tok,
                     {"item_key": ITEM, "note": "should not land"})
        ok("nor flag one discontinued", st in (401, 403), "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/maker_link", tok,
                     {"item_key": ITEM, "url": "https://example.com/nope"})
        ok("nor save a manufacturer link", st in (401, 403), "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/register_user?select=email", tok)
        ok("sees only their own roster row", st == 200 and len(b) <= 1,
           "%s saw %s rows" % (st, len(b) if isinstance(b, list) else b))

        # -- viewer ---------------------------------------------------------
        put_row(neutral, "viewer")
        tok = sign_in(neutral, pw)
        OUT.write("\nviewer\n")
        st, b = call("GET", "/rest/v1/item_note?select=id&limit=1", tok)
        ok("reads notes", st == 200, "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/item_note", tok,
                     {"item_key": ITEM, "body": "should not land"})
        ok("still cannot write a note", st in (401, 403), "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/item_invoice?select=id&limit=1", tok)
        ok("still cannot read invoices", st == 200 and b == [], "%s %s" % (st, b))

        # -- commenter ------------------------------------------------------
        set_role(neutral, role="commenter")
        tok = sign_in(neutral, pw)
        OUT.write("\ncommenter\n")
        st, b = call("POST", "/rest/v1/item_note", tok,
                     {"item_key": ITEM, "body": "written by the rls test"},
                     prefer="return=representation")
        ok("writes a note", st in (200, 201), "%s %s" % (st, b))
        ok("the note is stamped with the JWT email, not what was sent",
           isinstance(b, list) and b and b[0].get("by_email") == neutral,
           str(b)[:120])
        st, b = call("POST", "/rest/v1/item_state", tok,
                     {"item_key": ITEM, "status": "approved"})
        ok("cannot set a status", st in (401, 403), "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/item_discontinued", tok,
                     {"item_key": ITEM, "note": "should not land"})
        ok("nor flag one discontinued", st in (401, 403), "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/maker_link", tok,
                     {"item_key": ITEM, "url": "https://example.com/nope"})
        ok("nor save a manufacturer link", st in (401, 403), "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/item_invoice?select=id&limit=1", tok)
        ok("cannot read invoices", st == 200 and b == [], "%s %s" % (st, b))

        # -- admin ----------------------------------------------------------
        set_role(neutral, role="admin")
        tok = sign_in(neutral, pw)
        OUT.write("\nadmin\n")
        st, b = call("POST", "/rest/v1/item_state", tok,
                     {"item_key": ITEM, "status": "approved_as_noted",
                      "status_note": "by the rls test"},
                     prefer="return=representation,resolution=merge-duplicates")
        ok("sets a status", st in (200, 201), "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/item_status_log?select=status&item_key=eq." + ITEM, tok)
        ok("the change logged itself", st == 200 and isinstance(b, list) and len(b) >= 1,
           "%s %s" % (st, b))
        # Discontinued sits on the same rung as the picture and the status.
        st, b = call("POST", "/rest/v1/item_discontinued", tok,
                     {"item_key": ITEM, "note": "out of production"},
                     prefer="return=representation,resolution=merge-duplicates")
        ok("flags an item discontinued", st in (200, 201), "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/item_discontinued?select=note,by_email&item_key=eq."
                     + ITEM, tok)
        ok("and reads it back",
           st == 200 and isinstance(b, list) and len(b) == 1, "%s %s" % (st, b))
        ok("stamped with who did it",
           isinstance(b, list) and b and "@" in str(b[0].get("by_email", "")),
           str(b)[:120])
        st, b = call("DELETE", "/rest/v1/item_discontinued?item_key=eq." + ITEM, tok)
        ok("and can clear it again", st in (200, 204), "%s %s" % (st, b))
        # Manufacturer links, written from /links on the register site.
        st, b = call("POST", "/rest/v1/maker_link", tok,
                     {"item_key": ITEM, "url": "https://example.com/product"},
                     prefer="return=representation,resolution=merge-duplicates")
        ok("saves a manufacturer link", st in (200, 201), "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/maker_link?select=url,by_email&item_key=eq." + ITEM, tok)
        ok("and reads it back",
           st == 200 and isinstance(b, list) and len(b) == 1, "%s %s" % (st, b))
        ok("stamped with who saved it",
           isinstance(b, list) and b and "@" in str(b[0].get("by_email", "")),
           str(b)[:120])
        # Putting the original back: the row goes, and the item falls back to
        # whatever the build put in datasheets.json.
        st, b = call("DELETE", "/rest/v1/maker_link?item_key=eq." + ITEM, tok)
        ok("and can put the original back", st in (200, 204), "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/maker_link?select=url&item_key=eq." + ITEM, tok)
        ok("the override is really gone", st == 200 and b == [], "%s %s" % (st, b))
        # Invoices no longer follow the rung. An admin is an admin and sees
        # no prices until somebody ticks the flag - which is the whole point
        # of separating them, so it is worth asserting in both directions.
        st, b = call("GET", "/rest/v1/item_invoice?select=id&limit=1", tok)
        ok("an admin does NOT see invoices", st == 200 and b == [], "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/rpc/is_commercial", tok, {})
        ok("and is not commercial", b is False, "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/item_invoice", tok,
                     {"item_key": ITEM, "drive_url": "https://example.com/i.pdf"})
        ok("nor may add one", st in (401, 403), "%s %s" % (st, b))
        st, b = call("PATCH", "/rest/v1/register_user?email=eq." + neutral, tok,
                     {"commercial": True}, prefer="return=representation")
        ok("an admin cannot grant themselves commercial access",
           st in (401, 403) or b == [] or "super admin" in str(b), "%s %s" % (st, b))

        # With the flag, granted the only way it can be.
        admin("PATCH", "/rest/v1/register_user?email=eq." + neutral,
              body={"commercial": True})
        tok = sign_in(neutral, pw)
        # Seed one as the server, so "can read" means a row comes back. A
        # SELECT under row-level security answers 200 with an EMPTY LIST when
        # it is refused, and asserting on the status alone reads that as
        # access - which is exactly how the guard bug got a passing test.
        admin("POST", "/rest/v1/item_invoice",
              body={"item_key": ITEM, "drive_url": "https://example.com/seed.pdf",
                    "by_email": "system"})
        st, b = call("GET", "/rest/v1/item_invoice?select=id&item_key=eq." + ITEM, tok)
        ok("with commercial access, invoices open",
           st == 200 and isinstance(b, list) and len(b) >= 1, "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/rpc/is_commercial", tok, {})
        ok("is_commercial agrees", b is True, "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/item_invoice", tok,
                     {"item_key": ITEM, "drive_url": "https://example.com/i.pdf"},
                     prefer="return=representation")
        ok("and can be added", st in (200, 201), "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/item_picture", tok,
                     {"item_key": ITEM, "storage_path": "x/y.png",
                      "url": "https://example.com/y.png"},
                     prefer="return=representation")
        ok("replaces a picture", st in (200, 201), "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/register_user", tok,
                     {"email": "gp1-escalation-%s@example.com" % tag, "role": "super_admin"})
        ok("an admin cannot mint a super admin", st in (401, 403), "%s %s" % (st, b))
        st, b = call("PATCH", "/rest/v1/register_user?email=eq." + neutral, tok,
                     {"role": "super_admin"}, prefer="return=representation")
        ok("an admin cannot promote themselves", st in (401, 403) or b == [],
           "%s %s" % (st, b))

        # -- the domain rule ------------------------------------------------
        OUT.write("\ndomain rule  (@waratahtci.com, no roster row of its own)\n")
        tok2 = sign_in(company, pw)
        st, b = call("GET", "/rest/v1/item_note?select=id&limit=1", tok2)
        ok("inherits enough to read notes", st == 200, "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/item_note", tok2,
                     {"item_key": ITEM, "body": "written via the domain rule"},
                     prefer="return=representation")
        ok("inherits commenter, and can write", st in (200, 201), "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/item_invoice?select=id&limit=1", tok2)
        ok("inherits no more than commenter", st == 200 and b == [], "%s %s" % (st, b))

        # -- blocked beats the domain rule ----------------------------------
        put_row(company, "viewer")
        set_role(company, blocked=True)
        tok2 = sign_in(company, pw)
        OUT.write("\nblocked\n")
        st, b = call("POST", "/rest/v1/item_note", tok2,
                     {"item_key": ITEM, "body": "should not land"})
        ok("blocked beats the domain rule", st in (401, 403), "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/item_note?select=id&limit=1", tok2)
        ok("blocked cannot even read notes", st == 200 and b == [], "%s %s" % (st, b))

        # -- the anon path, which is most of the traffic ---------------------
        OUT.write("\nnot signed in at all\n")
        st, b = call("GET", "/rest/v1/item_status_public?select=item_key&limit=1", ANON)
        ok("reads the public status view", st == 200, "%s %s" % (st, b))
        # Notes are public now. This is the pair that matters: the VIEW opens
        # and the TABLE stays shut. If the table ever starts answering, every
        # note's author address is public and nothing else would say so.
        st, b = call("GET", "/rest/v1/item_note_public?select=author,body&item_key=eq."
                     + ITEM, ANON)
        ok("reads notes through the public view",
           st == 200 and isinstance(b, list) and len(b) >= 1, "%s %s" % (st, b))
        ok("the author is a name, not an address",
           isinstance(b, list) and b and "@" not in str(b[0].get("author", "")),
           str(b)[:120])
        st, b = call("GET", "/rest/v1/item_note?select=by_email&limit=1", ANON)
        ok("cannot read the notes table itself",
           st in (401, 403) or b == [], "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/item_invoice?select=id&limit=1", ANON)
        ok("cannot read invoices", st in (401, 403) or b == [], "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/register_user?select=email", ANON)
        ok("cannot read the address book", st in (401, 403) or b == [],
           "%s %s" % (st, b))
        # The replaced pictures ARE public - they are what the page shows
        # everybody, and a reader who could not see this row would be looking
        # at the old picture while everyone else saw the new one. But the
        # TABLE carries by_email, so it is the view that is public, and this
        # is the pair that says so.
        admin("POST", "/rest/v1/item_picture",
              body={"item_key": ITEM, "storage_path": "x/y.png",
                    "url": "https://example.com/y.png", "by_email": "system"},
              prefer="return=representation,resolution=merge-duplicates")
        st, b = call("GET", "/rest/v1/item_picture_public?select=item_key,url&item_key=eq."
                     + ITEM, ANON)
        ok("reads replaced pictures through the public view",
           st == 200 and isinstance(b, list) and len(b) == 1, "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/item_picture?select=by_email&limit=1", ANON)
        ok("cannot read the pictures table itself",
           st in (401, 403) or b == [], "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/item_picture", ANON,
                     {"item_key": ITEM, "storage_path": "x", "url": "x"})
        ok("cannot replace one", st in (401, 403), "%s %s" % (st, b))

        # Discontinued, the same pair. The red card is for everyone - that is
        # the point of flagging it - and the address behind it is for nobody.
        admin("POST", "/rest/v1/item_discontinued",
              body={"item_key": ITEM, "note": "seeded by the rls test",
                    "by_email": "system"},
              prefer="return=representation,resolution=merge-duplicates")
        st, b = call("GET", "/rest/v1/item_discontinued_public?select=note,author&item_key=eq."
                     + ITEM, ANON)
        ok("reads the discontinued flag through the public view",
           st == 200 and isinstance(b, list) and len(b) == 1, "%s %s" % (st, b))
        ok("a seeded row says the build did it, not a person",
           isinstance(b, list) and b and b[0].get("author") == "the register build",
           str(b)[:140])
        st, b = call("GET", "/rest/v1/item_discontinued?select=by_email&limit=1", ANON)
        ok("cannot read the discontinued table itself",
           st in (401, 403) or b == [], "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/item_discontinued", ANON,
                     {"item_key": ITEM, "note": "should not land"})
        ok("cannot flag anything", st in (401, 403), "%s %s" % (st, b))

        # Manufacturer links, the same pair. /links has to be readable by
        # somebody with no login at all - that is why it is on the site.
        admin("POST", "/rest/v1/maker_link",
              body={"item_key": ITEM, "url": "https://example.com/seed",
                    "by_email": "system"},
              prefer="return=representation,resolution=merge-duplicates")
        st, b = call("GET", "/rest/v1/maker_link_public?select=item_key,url&item_key=eq."
                     + ITEM, ANON)
        ok("reads manufacturer links through the public view",
           st == 200 and isinstance(b, list) and len(b) == 1, "%s %s" % (st, b))
        st, b = call("GET", "/rest/v1/maker_link?select=by_email&limit=1", ANON)
        ok("cannot read the links table itself",
           st in (401, 403) or b == [], "%s %s" % (st, b))
        st, b = call("POST", "/rest/v1/maker_link", ANON,
                     {"item_key": ITEM, "url": "https://example.com/nope"})
        ok("cannot save a link", st in (401, 403), "%s %s" % (st, b))
        # The 94 already confirmed were seeded by the migration. A reader with
        # no login must see them: that is the page's whole job.
        st, b = call("GET", "/rest/v1/maker_link_public?select=item_key", ANON)
        ok("the 94 seeded links are public",
           st == 200 and isinstance(b, list) and len(b) >= 94,
           "%s %s" % (st, len(b) if isinstance(b, list) else b))

    finally:
        OUT.write("\ncleaning up\n")
        # item_invoice FIRST, and it was missing until the orphan check
        # found ten rows of it on 1 Oct - every run of this suite had been
        # leaving its invoices behind since the commercial flag landed.
        admin("DELETE", "/rest/v1/item_invoice?item_key=eq." + ITEM)
        admin("DELETE", "/rest/v1/item_picture?item_key=eq." + ITEM)
        admin("DELETE", "/rest/v1/item_discontinued?item_key=eq." + ITEM)
        admin("DELETE", "/rest/v1/maker_link?item_key=eq." + ITEM)
        admin("DELETE", "/rest/v1/item_note?item_key=eq." + ITEM)
        admin("DELETE", "/rest/v1/item_state?item_key=eq." + ITEM)
        admin("DELETE", "/rest/v1/item_status_log?item_key=eq." + ITEM)
        admin("DELETE", "/rest/v1/register_user?email=like.gp1-rls-*")
        admin("DELETE", "/rest/v1/register_user?email=like.gp1-escalation-*")
        for uid in uids:
            admin("DELETE", "/auth/v1/admin/users/" + uid, schema=None)
        st, b = admin("GET", "/rest/v1/item_note?select=id&item_key=eq." + ITEM)
        OUT.write("  test rows left behind: %s\n"
                  % (len(b) if isinstance(b, list) else b))

    OUT.write("\n%d passed, %d failed\n" % (passed, failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
