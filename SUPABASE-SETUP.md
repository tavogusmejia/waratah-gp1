# Turning the workflow layer on

Everything on the page side is built and tested. What is left is the part only
you can do, because it needs the two dashboards.

Until step 5 is done the register behaves exactly as it always has: public,
read-only, no sign-in control, and not one network call to anywhere. That is
deliberate — the layer is off, not broken.

The project is already linked (`waratah`, ref `iygkonfuyslvgezgofby`) and the
CLI here is already signed in, so the steps marked **me** need nothing from
you.

---

## 1. Unpause the project — you

<https://supabase.com/dashboard/project/iygkonfuyslvgezgofby> → **Restore
project**. Takes a couple of minutes. Nothing else can happen until it is
active.

## 2. Apply the schema — me

```bash
supabase db push
```

Applies both migrations: the roles, statuses, notes, invoices, storage bucket
and policies; then the heartbeat that stops the project pausing again.

**Expect this to fail the first time.** 580 lines of SQL have never met a real
Postgres — there is no Docker here to start one — so there will be a typo or
two. The errors are specific and I will fix them.

## 3. Expose the `gp1` schema — you

Supabase → **Settings → API → Exposed schemas** → add **`gp1`** → Save.

Dashboard-only. Miss it and every query returns `PGRST106`, which the page and
the keep-alive endpoint both name in plain words if it happens.

## 4. Send me the anon key — you

Supabase → **Settings → API → Project API keys** → the one labelled **`anon`
`public`** (newer projects call it **Publishable key**, `sb_publishable_…` —
same thing).

Paste it here and I will wire it up, or set it yourself on line 29 of
`web/assets/config.js`. The URL is already filled in.

**Not** the `service_role` key. It bypasses every policy and must never reach
a browser or a deployment.

## 5. Make yourself super admin — you

Supabase → **SQL Editor**:

```sql
insert into gp1.register_user (email, role, name, note) values
  ('tavogusmejia@gmail.com', 'super_admin', 'Gus', 'Project lead')
on conflict (email) do update set role = 'super_admin';
```

Change the address if you will sign in with a different one — it has to match
the address you request the magic link with.

This one row goes in by hand because of the chicken-and-egg: the policies let
an admin appoint people and there is nobody yet. Everyone after you is added
from the page.

## 6. Point auth at the register — you

Supabase → **Authentication → URL Configuration** → **Site URL** = the
deployed register address, from your Vercel dashboard.

Get this wrong and the magic link sends fine and lands on the wrong page.

## 7. Give Vercel the key — you

Vercel → the project → **Settings → Environment Variables**, for Production:

| Name | Value |
|---|---|
| `SUPABASE_ANON_KEY` | the same anon key from step 4 |
| `CRON_SECRET` | any long random string you invent |

`SUPABASE_URL` is optional — the function defaults to the right project.

`CRON_SECRET` is what tells the endpoint a request really came from Vercel's
scheduler rather than from someone poking the URL. Without it the keep-alive
still works, but anyone could trigger the writing path.

Then **redeploy** so the cron job registers.

## 8. Sign in and check

Open the register → **Sign in** → your email → click the link.

You should get a `gus  SUPER ADMIN` pill in the header, a status dropdown on
every item, notes, invoices, and **Manage people** in your menu.

---

## The keep-alive

A free-tier project pauses after seven days of inactivity, and a paused
project fails in the worst possible shape: the register keeps rendering,
because the catalogue is a static file, while every status, note and invoice
silently fails. The page looks fine and saves nothing.

So `web/api/keepalive.js` runs daily at 07:00 UTC and calls `gp1.beat()`.

Two things make it a verification rather than a ping:

- **It writes.** A read might or might not count as activity depending on how
  Supabase measures it; an insert is not ambiguous. It also exercises the path
  that matters — a read-only ping would keep reporting success on a database
  that had stopped accepting writes.
- **It counts.** The reply carries how many items have a status and how many
  notes, invoices and people exist, so it answers "is this alive and still
  holding my data", not just "did something respond".

**To check it by hand, open `/api/keepalive` on the deployed site.** An
unauthenticated visit calls `gp1.beat_status()`, which writes nothing:

```json
{ "mode": "status", "ok": true, "last_beat": "2026-09-28T07:00:11Z",
  "hours_ago": 4.2, "beats": 37,
  "counts": { "with_status": 61, "notes": 18, "invoices": 4, "people": 5 } }
```

`hours_ago` is the number that matters. Under 24 means the cron is running.
Over 48 means it has stopped and the clock is ticking toward a pause.

If something is wrong the endpoint says which half, rather than just failing:
a missing function means the migration has not run, `PGRST106` means the
schema is not exposed, and a 503 means the project is already paused.

The endpoint is safe to leave public because the write is rate-limited inside
the database — one row an hour however often it is called. That is what lets
the whole deployment hold no secret beyond `CRON_SECRET`: there is no
`service_role` key anywhere, and adding one just to keep a project awake would
be a poor trade.

**Vercel Hobby runs cron jobs once a day at most**, and only on production
deployments. Both are fine here: the pause window is seven days.

---

## What each role gets

|                            | public | viewer | commenter | admin | super admin |
|----------------------------|:--:|:--:|:--:|:--:|:--:|
| Items, datasheets, pictures | ✓ | ✓ | ✓ | ✓ | ✓ |
| Submittal status            | ✓ | ✓ | ✓ | ✓ | ✓ |
| Who set it, and when        | – | ✓ | ✓ | ✓ | ✓ |
| Read notes                  | – | ✓ | ✓ | ✓ | ✓ |
| Write notes                 | – | – | ✓ | ✓ | ✓ |
| Set status                  | – | – | – | ✓ | ✓ |
| Invoices                    | – | – | – | ✓ | ✓ |
| Manage viewers & commenters | – | – | – | ✓ | ✓ |
| Manage admins               | – | – | – | – | ✓ |

Signing in on its own grants nothing. Anyone can request a magic link; without
a row in `register_user` they have exactly the public's rights.

Two narrowings of "everything public", both one line to change:

- **Invoices are admin-only.** They carry prices and suppliers' terms.
- **Emails are not public.** Anonymous readers get `gp1.item_status_public`,
  the status without the address book.

Two lock-outs are refused by database trigger, not by the page: removing the
last super admin, and changing your own role.

---

## Later, not now

**Email sending.** Supabase's built-in sender is rate-limited to a handful an
hour — fine for setting up, not for a team. **Authentication → Emails** to
point it at real SMTP before you add people.

**P9 needs renumbering.** Two different products share that code (JM Micro-Lok
fibreglass and poly pipe insulation). A code naming two items cannot carry one
item's record, so the page refuses to attach status, notes or invoices to
either and says why. Give one its own number in the source folder and
re-extract.

---

## Testing without a project

```bash
python tools/probe_workflow.py       # regenerates web/__probe_workflow.html
```

Serve `web/` and open:

- `__probe_workflow.html?role=admin&open=1` — the panel against a fake
  Supabase, one role at a time (`out`, `none`, `viewer`, `commenter`,
  `admin`, `super_admin`).
- `__probe_roles.html` — drives all six and asserts each sees exactly the
  controls its role allows. 50 checks.

The stub is written against the shapes supabase-js actually returns, including
the one that matters most: **an RLS refusal comes back as a resolved promise
with `error` set, never as a rejection.** Code that only catches rejections
would miss every permission failure.
