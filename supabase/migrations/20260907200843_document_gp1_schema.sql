-- Document the schema in the database itself.
--
-- These comments show up in the Supabase table editor and in psql's \d+, which
-- is where someone will be standing when they need them - not in a README in a
-- repo they may not have. The two that matter most are the warnings: code_tag
-- looks like a key and is not one, and updated_by is set by a trigger from the
-- JWT rather than by the client.
--
-- Also the first real exercise of `supabase db push`, on a change that cannot
-- damage anything: comments touch no data, no constraints and no permissions.

comment on schema gp1 is
  'GP1-MUR villa procurement. One schema per Waratah project so several can '
  'share this database without colliding in public.';

comment on table gp1.register_item is
  'Material and hardware register: 199 line items across 13 trades, extracted '
  'from the GP1-MUR master workbook. Structure comes from the workbook via '
  'extract_seed.py; spec_url, folder_url, approved, procured and notes are '
  'maintained by the project team in the web register and must survive a '
  're-import.';

comment on column gp1.register_item.id is
  'Identity. Deterministic uuid5 of source sheet and row, so a re-extract of '
  'the same workbook row produces the same id.';

comment on column gp1.register_item.code_tag is
  'Display tag verbatim from the workbook. NOT unique and not a key: "Cable" '
  'appears 8 times, "PVC elbows" 4 times, and bare 1/2/3 restart per '
  'sub-category in Millwork and Electrical.';

comment on column gp1.register_item.qty_raw is
  'Set when the workbook quantity was not a number ("lot", "TBC"). Exactly one '
  'of qty and qty_raw is non-null.';

comment on column gp1.register_item.drawing_ref is
  'Drawing reference such as A11-02/03/04. Split out of the workbook Spec Ref '
  'column, which carried both drawing references and datasheet URLs.';

comment on column gp1.register_item.spec_url is
  'Manufacturer datasheet. Official manufacturer domains only - where one '
  'could not be confirmed the field is left blank rather than guessed.';

comment on column gp1.register_item.folder_url is
  'Google Drive folder. Empty on every row so far; the register hides the '
  'folder half of its coverage model until something fills this in.';

comment on column gp1.register_item.updated_by is
  'Set by the register_item_stamp trigger from the JWT email. Never accept '
  'this from a client - it is the one version that cannot be forged.';

comment on table gp1.register_editor is
  'The write allowlist. Membership here is the only thing that permits an '
  'update to register_item. Managed from the dashboard or with service_role, '
  'never from the page.';

comment on view gp1.register_coverage is
  'Documentation coverage per trade - the figure the register leads with. '
  'Documented means a datasheet OR a folder, matching what the page computes.';
