-- ============================================================================
-- Manufacturer links stop living in a CSV.
--
-- The register takes an item's manufacturer page from datasheets.json, which
-- is written at build time from tools/maker-links.csv. That is fine for a link
-- that never changes and useless for the 53 still being confirmed: every one
-- of them needs a rebuild and a redeploy before anybody else can see it.
--
-- The confirmation tool moves onto the register site at /links, and this is
-- where it writes. Same shape as item_picture: the table is the override, the
-- build-time value is the fallback, and removing a row falls back again.
--
-- SEEDED WITH ALL 94 ALREADY CONFIRMED, not just the 53 outstanding. A table
-- holding half the record is a second source of truth to reconcile later; this
-- way tools/maker-links.csv becomes a snapshot of it rather than a rival to
-- it. They are stamped 'system' because nobody confirmed them here - they were
-- confirmed in the audit artifact over three days in September, and borrowing
-- a colleague's name for them would be a lie in a field people will trust.
-- ============================================================================

set local search_path = gp1, public;

create table gp1.maker_link (
  item_key text primary key,
  url      text not null,
  at       timestamptz not null default now(),
  by_email text not null
);

comment on table gp1.maker_link is
  'The manufacturer product page for an item, preferred over the build-time '
  'maker_url in datasheets.json. Remove the row to fall back to the build. '
  'Written by /links.';

create trigger maker_link_stamp
  before insert on gp1.maker_link
  for each row execute function gp1.stamp_email();

alter table gp1.maker_link enable row level security;

-- NOT anon. The table carries by_email; anonymous readers get the view.
grant select                 on gp1.maker_link to authenticated;
grant insert, update, delete on gp1.maker_link to authenticated;
grant all                    on gp1.maker_link to service_role;

create policy maker_link_read on gp1.maker_link for select
  to authenticated using (gp1.role_at_least('viewer'));
create policy maker_link_write on gp1.maker_link for insert
  to authenticated with check (gp1.role_at_least('admin'));
create policy maker_link_edit on gp1.maker_link for update
  to authenticated using (gp1.role_at_least('admin'))
  with check (gp1.role_at_least('admin'));
create policy maker_link_del on gp1.maker_link for delete
  to authenticated using (gp1.role_at_least('admin'));

-- ----------------------------------------------------------------------------
-- A link is on a page anybody can open, so anybody may read it. The address of
-- whoever confirmed it is not, which is the pair item_note_public and
-- item_discontinued_public already established.
-- ----------------------------------------------------------------------------
create view gp1.maker_link_public with (security_invoker = false) as
  select item_key, url, at from gp1.maker_link;

grant select on gp1.maker_link_public to anon, authenticated;

comment on view gp1.maker_link_public is
  'maker_link without the address. The write path still uses the table.';

-- ----------------------------------------------------------------------------
-- Orphan checks see the new table, or a renamed item leaves a link behind that
-- nothing reports. DROP first: this changes the return type.
-- ----------------------------------------------------------------------------
drop function if exists gp1.orphan_item_state(text[]);

create function gp1.orphan_item_state(live text[])
  returns table (item_key text, notes bigint, invoices bigint,
                 status gp1.submittal, picture boolean, discontinued boolean,
                 maker_link boolean) as $fn$
  select k.item_key,
         (select count(*) from gp1.item_note    n where n.item_key = k.item_key),
         (select count(*) from gp1.item_invoice v where v.item_key = k.item_key),
         (select s.status from gp1.item_state   s where s.item_key = k.item_key),
         exists (select 1 from gp1.item_picture      p where p.item_key = k.item_key),
         exists (select 1 from gp1.item_discontinued d where d.item_key = k.item_key),
         exists (select 1 from gp1.maker_link        m where m.item_key = k.item_key)
    from (
      select item_key from gp1.item_state
      union select item_key from gp1.item_note
      union select item_key from gp1.item_invoice
      union select item_key from gp1.item_picture
      union select item_key from gp1.item_discontinued
      union select item_key from gp1.maker_link
    ) k
   where not (k.item_key = any (live))
   order by 1;
$fn$ language sql stable security definer set search_path = gp1, public;

revoke execute on function gp1.orphan_item_state(text[]) from public, anon;
grant  execute on function gp1.orphan_item_state(text[]) to authenticated;

-- ----------------------------------------------------------------------------
-- The 94 confirmed so far, exactly as tools/maker-links.csv holds them.
-- ----------------------------------------------------------------------------
insert into gp1.maker_link (item_key, url)
values
  ('a-a1', 'https://www.pentair.com/en-us/pool-spa/products/filters/clean-and-clear-cartridge-filters.html'),
  ('a-a2', 'https://www.pentair.com/en-us/pool-spa/products/pumps/intelliflo3-vsf-pool-pump.html'),
  ('a-a3', 'https://www.pentair.com/en-us/pool-spa/products/pumps/intelliflo3-vsf-pool-pump.html'),
  ('a-a4', 'https://www.pentair.com/en-us/products/residential/pool-spa-equipment/pool-automation/intellicenter-lite-control-system.html'),
  ('a-a5', 'https://www.pentair.com/en-us/pool-spa/products/water-treatment/intellichlor-plus-lt-salt-chlorine-generators.html'),
  ('a-a6', 'https://www.poolheatpumps.com/pool-heat-pumps/gulfstream-he150ra-pool-heat-pump.html?srsltid=AU7gw4U6ZPi8waD_DH1t3pIE6RPNxRFDHV9fVmIm6_9DuKsKK92dNvUf'),
  ('b-b1', 'https://www.aquastarpoolproducts.com/draincoverspecifications/wav9wrxxxf'),
  ('b-b3', 'https://www.inyopools.com/Products/02200022061653.htm'),
  ('b-b4', 'https://www.hayward.com/threaded-return-fitting-for-concrete-1-1-2-fip-open-line-sp1022.html'),
  ('b-b5', 'https://www.spearsmfg.com/'),
  ('d-dh9', 'https://dach.assaabloy.com/ch/en/product-catalogue/planet-t611079-p371898-planet-x3'),
  ('d-dh10', 'https://www.hafele.com/th/en/product/door-hinge-concealed-for-flush-interior-doors-up-to-80-100-kg/92791833/?MasterSKU=P-00862553'),
  ('d-dh11', 'https://www.hafele.com/us/en/product/door-hinge-center-hung-top-pivot/P-01498889/'),
  ('d-dh12', 'https://www.hafele.si/en/product/door-viewer-up-to-door-thickness-82-mm-startec/95901042/?MasterSKU=P-00873696'),
  ('d-dh13', 'https://www.hafele.co.uk/en/product/fitting-set-for-sliding-interior-pocket-doors-hawa-junior-100-b-pocket/P-01580146/'),
  ('d-dh14', 'https://www.hafele.com/us/en/product/sliding-door-hardware-haefele-slido-d-line11-160p-set/94162018/?MasterSKU=P-01499186'),
  ('d-dh15', 'https://mylock.saltosystems.com/en/custom/aelement-fusion#2,285,14,41,131,78,82,91'),
  ('d-dh16', 'https://mylock.saltosystems.com/en/custom/aelement-fusion#2,285,14,41,131,78,82,91'),
  ('d-dh17', 'https://mylock.saltosystems.com/en/custom/aelement-fusion#2,285,14,41,131,78,82,91'),
  ('e-e1', 'https://new.abb.com/products/1TQP340109A0000/pcc4022'),
  ('e-e2', 'https://new.abb.com/products/1TQP316106A0000/pcc1612'),
  ('e-e3', 'https://new.abb.com/products/1TQS100000A1058/pams3022trnus'),
  ('e-e4', 'https://new.abb.com/products/2CJC108120S1400/rgwmsp120s08t14'),
  ('e-e5', 'https://new.abb.com/products/1TQQ011020X1400/thql1120paf2'),
  ('e-e6', 'https://new.abb.com/products/de/1TQQ021080X0000/thql2180'),
  ('e-e7', 'https://new.abb.com/products/1TQQ021040X0100/thql2140'),
  ('e-e8', 'https://electrification.us.abb.com/products/circuit-breakers/ground-fault-circuit-interrupter-self-test-gfci'),
  ('e-e9', 'https://empower.abb.com/ecatalog/ec/EN_NA/p/THQL2120'),
  ('e-e10', 'https://new.abb.com/products/1TQQ021030X0100/thql2130'),
  ('f-f1', 'https://www.cdivalve.com/products/detail/r400-series-bob-float-valves'),
  ('f-f2', 'https://www.bonominorthamerica.com/en/product/rubinetterie-bresciane/euroblock/100102_18335'),
  ('g-g1', 'https://www.akvalvesltd.com/products/pvc-ball-valve-double-union-ch-aquaram?srsltid=AU7gw4U2YNKOct-rUK3J9y8I-E_k5YURXhnzyILklGieHhzL8DUIl9PY'),
  ('g-g2', 'https://www.jandy.com/en/products/pool-valves/check-valves/check'),
  ('g-g3', 'https://spearsmfg.com/'),
  ('c-c1', 'https://www.hubbell.com/burndy/en/products/bwb680ig-in-ground-pool-water-bonding-kit/p/484312'),
  ('c-c2', 'https://www.southwire.com/categories/c-wire-cable'),
  ('c-c3', 'https://www.southwire.com/categories/c-wire-cable'),
  ('c-c4', 'https://www.cantexinc.com/products/pvc-pipe-conduit'),
  ('c-c5', 'https://www.southwire.com/categories/c-electrical-components'),
  ('c-c6', 'https://www.abb.com/global/en/areas/electrification/low-voltage/connectors-grounding-terminations/grounding'),
  ('h-h1', 'https://www.dornbracht.com/en-fi/products/13716882-42/deck-mounted-basin-spout-without-pop-up-waste-brushed-bronze-pvd-'),
  ('h-h2', 'https://www.dornbracht.com/en/products/20000740-46/deck-valve-clockwise-closing-cold-brushed-champagne-22kt-gold-'),
  ('h-h3', 'https://www.dornbracht.com/en-gb/products/27812660-420010/hand-shower-set-with-integrated-shower-holder-flowreduce-brushed-bronze-pvd-'),
  ('h-h5', 'https://www.dornbracht.com/en-gb/products/36503979-42/xtool-concealed-thermostat-without-volume-control-brushed-bronze-pvd-'),
  ('h-h5.1', 'https://www.dornbracht.com/en-gb/products/36607740-42/wall-valve-clockwise-closing-brushed-bronze-pvd-'),
  ('h-h5.2', 'https://www.dornbracht.com/en-gb/products/3551197090/xtool-concealed-thermostat-module-with-1-valve'),
  ('h-h6', 'https://www.dornbracht.com/en/products/83251220-42/hooks-brushed-bronze-pvd-'),
  ('h-h7', 'https://www.dornbracht.com/en/products/83500979-42/tissue-holder-without-cover-brushed-bronze-pvd-'),
  ('h-h8', 'https://www.totousa.com/neorest-wx1-wall-hung-toilet?color=cotton'),
  ('p-p1', 'https://www.bradfordwhite.com/commercial-electric-water-heaters/'),
  ('p-p2', 'https://www.tacocomfort.com/product/2400-series-high-capacity-circulators/'),
  ('p-p3', 'https://www.tacocomfort.com/product/00-timer-aquastat/'),
  ('p-p4', 'https://www.fergusonhome.com/proflo-pf71dc/s992408?srsltid=AU7gw4UFa0IrxLYTS3-szHn523O4-Z5-y7YKqygFt6Va_FV7Q655Mfr-'),
  ('p-p5', 'https://ussolid.com/products/1-2-mini-ball-valve-316-stainless-steel-female-male-thread-2pcs?srsltid=AU7gw4WUctDMPdGZjQ8tsreluaxlCTQazpajeXI182qGaBRZtBLE6lM1'),
  ('p-p6', 'https://www.brasscraft.com/product/12-in-nom-comp-x-38-in-o-d-comp-6/'),
  ('p-p7', 'https://www.ferguson.com/product/proflo-pfx146-3%2F8-in.-compression-x-1%2F2-in.-fip-x-16-in.-stainless-steel-and-pvc-reinforced-sink-flexible-water-connector-pfx146023/3866359.html?srsltid=AU7gw4WE85N4QB5vxUDlzE1CibVWMnniH4avF1hLDSwEiytkFlljbZfU'),
  ('p-p8', 'https://www.ferguson.com/product/proflo-100-series-1-1%2F2-in.-brass-p-trap-in-polished-chrome-pfptb112/4055901.html?srsltid=AU7gw4VrN7xrTnndbwdOGfo8gylOyD2uWO5R86thnq5gC6p0TD0s_8t1'),
  ('p-p9', 'https://www.jm.com/en/insulation-systems/mechanical-insulation/micro-lok-hp-pipe-insulation/'),
  ('p-p10', 'https://www.jonesstephens.com/poly-insulation'),
  ('p-p11', 'https://www.charlottepipe.com/products/plastics/flowguard-gold-copper-tube-size-cts-cpvc-pipe-and-fittings-system'),
  ('p-p12', 'https://www.charlottepipe.com/products/plastics/flowguard-gold-copper-tube-size-cts-cpvc-pipe-and-fittings-system'),
  ('p-p13', 'https://www.charlottepipe.com/products/plastics/flowguard-gold-copper-tube-size-cts-cpvc-pipe-and-fittings-system'),
  ('p-p14', 'https://www.ferguson.com/product/proflo-3-in.-plastic-roof-drain-pf42870/1333313.html?srsltid=AU7gw4Uy-KLjctMOAsrGurZOsStjbjCV64N99XG_ORQQ_rmvObrt1Hv-'),
  ('ltrn-ltrn1', 'https://support.lutron.com/uk/en/product/myroom-xc/component/processors-and-interfaces/guest-room-edge-processor/mp-1l-gcu/documents'),
  ('ltrn-ltrn2', 'https://support.lutron.com/us/en/product/myroom-xc/component/power-supplies/myroom-qs-link/mqsps-dh-1-30'),
  ('ltrn-ltrn3', 'https://support.lutron.com/us/en/product/homeworks/component/panels/pd4/pd4-36f-120/documents'),
  ('ltrn-ltrn4', 'https://support.lutron.com/us/en/product/myroom-xc/component/load-controllers/phase-dimming/mqse-4a1-d'),
  ('ltrn-ltrn5', 'https://support.lutron.com/us/en/product/myroom-xc/component/load-controllers/non-dim/mqse-2s1-d'),
  ('ltrn-ltrn6', 'https://support.lutron.com/us/en/product/myroom-xc/component/load-controllers/dali/qsn-1dalunv-d'),
  ('ltrn-ltrn7', 'https://luxury.lutron.com/uk/en/controls/alisse-keypad'),
  ('ltrn-ltrn8', 'https://luxury.lutron.com/uk/en/controls/alisse-keypad'),
  ('ltrn-ltrn9', 'https://luxury.lutron.com/uk/en/controls/alisse-keypad'),
  ('ltrn-ltrn10', 'https://support.lutron.com/us/en/product/homeworks/article/dimmers-and-keypads/app-note-705-international-palladiom-keypad-installation-best-practices'),
  ('ltrn-ltrn11', 'https://support.lutron.com/us/en/product/vive/component/sensors/radio-powr-savr-ceiling/lrf2-ocr2b-p'),
  ('ltrn-ltrn12', 'https://support.lutron.com/us/en/product/myroom-xc/component/processors/qs-sensor-module/qsm2-xw-c'),
  ('ltrn-ltrn13', 'https://www.lutron.com/us/en/control/occupancy-sensors-timers/in-wall-motion-sensor-switches?sku=ms-ops2-wh'),
  ('ltrn-ltrn14', 'https://www.lutron.com/us/en/controls/wallplates-accessories/designer-style'),
  ('ltrn-ltrn15', 'https://support.lutron.com/us/en/product/myroom-xc/component/temperature-control/palladiom-thermostat/mwp-t-ohw/documents'),
  ('ltrn-ltrn16', 'https://support.lutron.com/us/en/product/myroom-xc/component/temperature-control/fan-coil-unit-controller/smc55-myrm'),
  ('ltrn-ltrn17', 'https://support.lutron.com/us/en/product/homeworks/component/control-interfaces/qse-io'),
  ('ltrn-ltrn18', 'https://support.lutron.com/us/en/warranty'),
  ('ltrn-ltrn19', 'https://support.lutron.com/us/en/product/receptacles/component/new-architectural/usb/ltr-15-cctr/documents/installation-guide'),
  ('ltrn-ltrn20', 'https://support.lutron.com/us/en/product/receptacles/component/new-architectural/tamper-resistant/ltr-15-tr'),
  ('ltrn-ltrn21', 'https://www.lutron.com/us/en/controls/wallplates-accessories/palladiom-wallplates'),
  ('ltrn-ltrn22', 'https://support.lutron.com/us/en/product/receptacles/component/designer/gfci/documents/installation-guide'),
  ('ltrn-ltrn23', 'https://assets.lutron.com/a/documents/Spec%20Guide%20Volume%201%20Custom%20Architectural%20Wallplates.pdf'),
  ('ltrn-ltrn24', 'https://assets.lutron.com/a/documents/GRX_CBL_DMX_Cable_Accessories.pdf'),
  ('ltrn-ltrn25', 'https://luxury.lutron.com/uk/en/blinds/sivoiaqs-roller-blinds'),
  ('ltrn-ltrn25.1', 'https://luxury.lutron.com/uk/en/blinds/sivoiaqs-roller-blinds'),
  ('ltrn-ltrn25.2', 'https://www.lutron.com/us/en/window-treatments/drapery/sivoia-drapery?sku=sivoia-ripplefold-straight-d145-nopts-drapery'),
  ('ltrn-ltrn26', 'https://www.lutron.com/us/en/window-treatments/drapery/sivoia-drapery?sku=sivoia-ripplefold-straight-d145-nopts-drapery'),
  ('ltrn-ltrn26.1', 'https://support.lutron.com/us/en/product/homeworks/component/power-supplies/qsps-p1-1-35v'),
  ('pl-a', 'https://www.lucelight.it/en/prodotto.php/3686'),
  ('pl-b', 'https://www.lucelight.it/en/prodotto.php/108089')
on conflict (item_key) do nothing;
