-- ============================================================================
-- A domain rule says who someone works for, as well as what they may do.
--
-- Everyone at waratahtci.com works for Waratah TCI, and typing that into the
-- company field 120 times is not work anybody should do. The rule already
-- knows the domain; it can carry the company name too.
--
-- FILLED, NOT FORCED. The company is written only when the row leaves it
-- blank. Somebody at the company domain who is actually seconded from
-- elsewhere can be given their real employer and it will stick - a default
-- that cannot be overridden is not a default, it is a constraint, and this
-- is not one.
-- ============================================================================

set local search_path = gp1, public;

alter table gp1.register_domain
  add column company text not null default '';

comment on column gp1.register_domain.company is
  'Filled into a new roster row at this domain when it names no company of '
  'its own. Never overwrites one that does.';

update gp1.register_domain
   set company = 'Waratah TCI'
 where domain = 'waratahtci.com';

-- ----------------------------------------------------------------------------
-- The email is normalised and the company defaulted in the same trigger,
-- because the second needs the first: the domain can only be read off an
-- address that has already been lower-cased and trimmed.
-- ----------------------------------------------------------------------------
create or replace function gp1.normalise_email() returns trigger as $fn$
declare d text;
begin
  new.email = lower(btrim(new.email));
  if coalesce(btrim(new.company), '') = '' then
    select r.company into d
      from gp1.register_domain r
     where r.domain = split_part(new.email, '@', 2)
       and r.company <> '';
    if d is not null then
      new.company = d;
    end if;
  end if;
  return new;
end;
$fn$ language plpgsql;

-- ----------------------------------------------------------------------------
-- And the people already on the roster, who were added before the rule could
-- say this. Same test: only the ones naming no company.
-- ----------------------------------------------------------------------------
update gp1.register_user u
   set company = r.company
  from gp1.register_domain r
 where r.domain = split_part(u.email, '@', 2)
   and r.company <> ''
   and coalesce(btrim(u.company), '') = '';
