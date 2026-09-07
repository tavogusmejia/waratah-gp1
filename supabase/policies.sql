-- ============================================================================
-- GP1-MUR Material Register - access control.
--
-- Run AFTER schema.sql, which creates the gp1 schema, enables row level
-- security and grants nothing at the row level.
--
-- The model the register needs:
--   read   anyone with the link, signed in or not. The schedule is shared with
--          consultants and trades who will never have an account.
--   write  the project team, by email address, listed in gp1.register_editor.
--
-- This replaces the single-owner policy the first draft carried
-- (`current_setting('app.owner_email')`). A database setting is one address and
-- cannot be changed without superuser rights; procurement is several people and
-- the list changes as trades come and go.
--
-- register_editor is deliberately scoped to gp1, not shared across the Waratah
-- database. Being allowed to edit the GP1-MUR schedule should not imply
-- anything about any other project that later lands in this database.
-- ============================================================================

create table if not exists gp1.register_editor (
  email      text primary key,
  note       text,
  added_at   timestamptz not null default now()
);

alter table gp1.register_editor enable row level security;

grant select on gp1.register_editor to authenticated;
grant all    on gp1.register_editor to service_role;

-- The allowlist is readable only by the people on it. A public register should
-- not also publish the team's email addresses.
create policy register_editor_self_read
  on gp1.register_editor for select
  to authenticated
  using (auth.jwt() ->> 'email' = email);

-- Membership is managed in the Supabase dashboard or with the service_role key,
-- never from the page. No insert/update/delete policy exists here on purpose.

-- ----------------------------------------------------------------------------
-- register_item
-- ----------------------------------------------------------------------------

-- Anyone with the link reads. This is what makes the register shareable.
create policy register_item_read_all
  on gp1.register_item for select
  using (true);

-- Only a listed address writes. `for update` rather than `for all`: rows are
-- created by the seed import and deleted by nobody, so the page needs no
-- insert or delete path and should not be handed one.
--
-- The subquery reads register_editor as the caller, whose own RLS lets them
-- see only their own row - which is all this test needs.
create policy register_item_team_updates
  on gp1.register_item for update
  to authenticated
  using      (auth.jwt() ->> 'email' in (select email from gp1.register_editor))
  with check (auth.jwt() ->> 'email' in (select email from gp1.register_editor));

-- Stamp who made the change. The page never sends updated_by - taking it from
-- the JWT is the only version a client cannot lie about.
create or replace function gp1.stamp_register_editor() returns trigger as $$
begin
  new.updated_by = coalesce(auth.jwt() ->> 'email', 'system');
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists register_item_stamp on gp1.register_item;
create trigger register_item_stamp
  before update on gp1.register_item
  for each row execute function gp1.stamp_register_editor();

-- ----------------------------------------------------------------------------
-- Seed the team. Replace these with the real addresses before running.
-- ----------------------------------------------------------------------------

-- insert into gp1.register_editor (email, note) values
--   ('someone@example.com', 'Project manager'),
--   ('someone.else@example.com', 'Procurement')
-- on conflict (email) do nothing;
