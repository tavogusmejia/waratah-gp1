-- ============================================================================
-- GP1-MUR Material Register - access control.
--
-- Run AFTER schema.sql, which enables row level security and grants nothing.
--
-- The model the register needs:
--   read   anyone with the link, signed in or not. The schedule is shared with
--          consultants and trades who will never have an account.
--   write  the project team, by email address, listed in register_editor.
--
-- This replaces the single-owner policy the first draft carried
-- (`current_setting('app.owner_email')`). A database setting is one address and
-- cannot be changed without superuser rights; procurement is several people and
-- the list changes as trades come and go.
-- ============================================================================

create table if not exists register_editor (
  email      text primary key,
  note       text,
  added_at   timestamptz not null default now()
);

alter table register_editor enable row level security;

-- The allowlist is readable only by the people on it. A public register should
-- not also publish the team's email addresses.
create policy register_editor_self_read
  on register_editor for select
  using (auth.jwt() ->> 'email' = email);

-- Membership is managed in the Supabase dashboard or with the service_role key,
-- never from the page. No insert/update/delete policy exists here on purpose.

-- ----------------------------------------------------------------------------
-- register_item
-- ----------------------------------------------------------------------------

-- Anyone with the link reads. This is what makes the register shareable.
create policy register_item_read_all
  on register_item for select
  using (true);

-- Only a listed address writes. `for update` rather than `for all`: rows are
-- created by the seed import and deleted by nobody, so the page needs no
-- insert or delete path and should not be handed one.
create policy register_item_team_updates
  on register_item for update
  using      (auth.jwt() ->> 'email' in (select email from register_editor))
  with check (auth.jwt() ->> 'email' in (select email from register_editor));

-- Stamp who made the change. The page never sends updated_by - taking it from
-- the JWT is the only version a client cannot lie about.
create or replace function stamp_register_editor() returns trigger as $$
begin
  new.updated_by = coalesce(auth.jwt() ->> 'email', 'system');
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists register_item_stamp on register_item;
create trigger register_item_stamp
  before update on register_item
  for each row execute function stamp_register_editor();

-- ----------------------------------------------------------------------------
-- Seed the team. Replace these with the real addresses before running.
-- ----------------------------------------------------------------------------

-- insert into register_editor (email, note) values
--   ('someone@example.com', 'Project manager'),
--   ('someone.else@example.com', 'Procurement')
-- on conflict (email) do nothing;
