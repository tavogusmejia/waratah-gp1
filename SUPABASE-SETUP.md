# Turning the workflow layer on

Everything on the page side is built and tested. What is left is the part only
you can do, because it needs the dashboard.

Until step 4 is done the register behaves exactly as it always has: public,
read-only, no sign-in control, and not one network call to anywhere. That is
deliberate — the layer is off, not broken.

---

## 1. Unpause the project

Supabase dashboard → the `Waratah-gp1` project → **Restore**. It takes a
couple of minutes.

While you are there: a free-tier project pauses again after a week of
inactivity. If this becomes the team's live submittal log, that is an argument
for the paid tier — a paused project means nobody can approve anything.

## 2. Apply the schema

```bash
supabase link --project-ref <the ref from the dashboard URL>
supabase db push
```

This applies `supabase/migrations/20260928120000_gp1_submittals.sql`: four
roles, the submittal states, notes, invoices, the private storage bucket and
every row-level policy.

**Expect it to fail the first time.** It has never been run against a real
Postgres — there is no Docker here to start one — so there is likely a typo or
two in 480 lines of SQL. The errors will be specific and I will fix them.

## 3. Expose the schema

Dashboard → **Settings → API → Exposed schemas** → add `gp1`.

Miss this and every query returns `PGRST106` and the page looks broken for no
visible reason. The page does name this error in plain words if it happens.

## 4. Point the page at it

Dashboard → **Settings → API**, then fill in `web/assets/config.js`:

```js
window.GP1_CONFIG = {
  url: "https://<ref>.supabase.co",
  anonKey: "<the anon / public key>"
};
```

The **anon** key, never the `service_role` key. The anon key is meant to be
public — it identifies the project and nothing else, and row-level security is
what decides who may read and write. The service_role key bypasses every
policy and must never reach a browser.

## 5. Make yourself the super admin

Chicken and egg: the policies let an admin appoint people, and there is nobody
yet. Seed exactly one row by hand — dashboard → **SQL Editor**:

```sql
insert into gp1.register_user (email, role, name, note) values
  ('<your email>', 'super_admin', 'Gus', 'Project lead')
on conflict (email) do update set role = 'super_admin';
```

Use the address you will sign in with. Every other account is then made from
the page: **your name in the header → Manage people**.

## 6. Check the email settings

Sign-in is a magic link, so Supabase has to be able to send mail. The built-in
sender is rate-limited to a handful an hour, which is fine for setting up and
not for a team. Dashboard → **Authentication → Emails** to point it at a real
SMTP sender when you are ready.

Also **Authentication → URL Configuration**: the Site URL must be the deployed
register's address, or the link in the mail comes back to the wrong place.

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

Two narrowings of "everything public", both one line to change if you want
them changed:

- **Invoices are admin-only.** They carry prices and suppliers' terms.
- **Emails are not public.** Anonymous readers get `gp1.item_status_public`,
  which is the status without the address book.

Two lock-outs are refused by database trigger, not by the page: removing the
last super admin, and changing your own role.

---

## Testing it without a project

```bash
python tools/probe_workflow.py       # regenerates web/__probe_workflow.html
```

Then serve `web/` and open:

- `__probe_workflow.html?role=admin&open=1` — the panel against a fake
  Supabase, one role at a time (`out`, `none`, `viewer`, `commenter`,
  `admin`, `super_admin`).
- `__probe_roles.html` — drives all six and asserts each sees exactly the
  controls its role allows. 50 checks.

The stub is written against the shapes supabase-js actually returns, including
the one that matters most: **an RLS refusal comes back as a resolved promise
with `error` set, never as a rejection.** Code that only catches rejections
would miss every permission failure.

---

## One thing to fix in the source folder

`P9` is on two different items — JM Micro-Lok fibreglass and poly pipe
insulation. A code that names two items cannot carry one item's record, so the
page refuses to attach status, notes or invoices to either and says why.

Give one of them its own number in the source folder and re-extract, and both
start working.
