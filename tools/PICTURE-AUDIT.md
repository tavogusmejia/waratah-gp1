# Picture audit — GP1-MUR Material & Hardware Register

Audited by eye against the 35 pictures the register currently ships, plus the
21 items that have none. 56 items in total.

## How to replace one

1. Download a clean product photograph — ideally a cutout on a plain white
   ground, since the register composites them onto a light tile.
2. Rename it to the **file** name in the table below. The extension may be
   `.jpg`, `.jpeg`, `.png` or `.webp`.
3. Drop it in `tools/images/`.
4. Re-run `python tools/extract_datasheets.py`.

A file there always wins over whatever the extractor would pick by itself.
The names are the datasheet's own slug rather than the item code, because
three plumbing items all carry the code `J9` — a file named `J9.jpg` would
silently apply to all three.

## Wrong — the picture is not the product (9)

These are the ones to fix first.

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `B-B5` | Spears — Infinity-Edge Trough Drain + Pool Pipe & Fittings - Spears Schedule 40 PVC | `b5-spears-sch-40-pvc.jpg` | Blue catalogue-cover artwork, not the product. Same file as G-G3. |
| `E-03` | ABB — Load Center, Meter Socket PAMS3022TRNUS | `janu-sub-011-03-meter-socket-pams3022trnus.jpg` | Wiring/connection diagram, not the meter socket. |
| `E-04` | ABB — Surge Protection Device, Wall Mount, RG Series - RGWMSP120S08T14 | `janu-sub-011-04-surge-protection-device-rgwmsp120s08t14.jpg` | Small outline drawings of enclosures, not the SPD. |
| `F-F1` | Robert Manufacturing — Make-up Float Valve, 3/4 in NPT - Robert Mfg BOB R400 (brass) | `f1-robert-mfg-bob-r400-brass-float-valve.jpg` | Manufacturer brand graphic (chevron), not the float valve. |
| `F-F2` | Bonomi (Valveman) — Foot Valve, 2.5 in brass with strainer - Bonomi 100102 series | `f2-valveman-brass-foot-valves.jpg` | Dimension line drawings, not the foot valve. |
| `G-G3` | Spears — PVC Pipe and Sch 40 Fittings (all sizes) - Spears Schedule 40 PVC | `g3-spears-pvc-sch-40-fittings-unions-and-saddles-technical-catalog.jpg` | Blue catalogue-cover artwork, not the product. Same file as B-B5. |
| `J-J3` | Taco — Timer / Aquastat - Taco 00 Series Recirculation Control | `j3-taco-timer-and-aquastat.jpg` | Line drawing of a pipe connection, not the timer/aquastat. |
| `L-A` | L&L; Luce&Light; — Pool Light L09 - L&L; Bright 1.6 316L | `a-pool-light-l09-cw16005di.jpg` | Shows the LED driver, not the L09 luminaire. |
| `L-B` | L&L; Luce&Light; — Pool Light L09.1 - L&L; Bright 3.0 316L | `b-pool-light-l09-1-cw300005wi.jpg` | Shows the outer casing, not the L09.1 luminaire. |

## Weak — related, but a poor showing of the item (4)

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `B-B2` | Color Match Pool Fittings — Pool Shallow Floor Return - Color Match Pebble Top PTFR-03 (Light Gray) | `b2-color-match-floor-return-ptfr-03.jpg` | Exploded component parts rather than the finished fitting. |
| `G-G1` | Aquaram — PVC Ball Valves - Aquaram PVC-U 2-way, type PE (solvent socket) | `g1-aquaram-valves.jpg` | Exploded parts render rather than an assembled valve. |
| `H-H1` | Burndy — Pool Equipotential Bonding (NEC 680) - Burndy BWB680IG In-Ground Pool Water Bonding Kit | `h1-burndy-bwb680ig-in-ground-pool-water-bonding-kit.jpg` | Grey CAD render rather than a photograph - worth confirming it is the BWB680IG. |
| `J-J2` | Taco — Recirculation Pump - Taco 2400 Series High-Capacity Circulator | `j2-taco-2400-series-recirculation-pump.jpg` | Product is right but sits on a black rectangle, which reads oddly on the light tile. |

## Missing — no picture at all (21)

The datasheet embeds none that passed the filter. The register shows the item code on a tile instead, which is correct behaviour, not a fault.

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `B-B3` | Hayward — Pool Wall & Infinity-Edge Return Inlets, 2 in - Hayward SP1419D (Gray: SP1419DGR) | `b3-hayward-sp1419d.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `B-B4` | Hayward — Vacuum Fitting - Hayward SP1022 (Gray: SP1022GR) | `b4-hayward-sp1022.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `B-B6` | Pentair — Automatic Water Filler - Pentair T40-F | `b6-pentair-t40-f-automatic-water-filler.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-1` | Häfele — Concealed Mortise Hinge - Häfele Startec 3D-Adjustable | `01-hafele-startec-concealed-hinge.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-2` | Salto — Lever Handle Set - Salto Standard Line, London | `02-salto-london-lever-handle.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-2.2` | CBMmart — Teak Wood Pull Handle - CBMmart (Custom) | `02-2-cbmmart-teak-wood-handle.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-3` | Salto — Electronic Lockset - Salto AElement Fusion (ANSI) | `03-salto-aelement-fusion-lockset.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-4` | Sargent — Privacy Thumb-Turn - Sargent 8200 Series (8266) | `04-sargent-8200-privacy-thumb-turn.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-5` | Häfele — Door Viewer - Häfele Startec 200°, up to 82 mm | `05-hafele-startec-door-viewer.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-6` | Häfele — Sliding Door Fitting - Häfele Hawa Junior 80/B-Pocket | `06-hafele-hawa-junior-80b-pocket.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-6.1` | Häfele — Sliding Door Hardware - Häfele Slido D-Line11 160P | `06-1-hafele-slido-d-line11-160p.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-7` | Assa Abloy — Automatic Drop-Down Seal - Assa Abloy Planet X3 RD | `07-assa-abloy-planet-x3-rd-drop-seal.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-7.1` | Reflect — Door-Jamb Weatherstrip - Reflect Silicone Bulb Seal | `07-1-reflect-door-jamb-weatherstrip.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `E-09` | ABB — Circuit Breaker, Ground Fault Plug-In - THQL2160GFT2 | `janu-sub-011-09-ground-fault-breaker-thql2160gft2.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `G-G2` | Jandy (Fluidra) — PVC Check Valves - Jandy positive-seal check valve | `g2-jandy-check-valves.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J11` | Charlotte Pipe — Cold Water Service - PVC Schedule 40 Pressure Pipe & Fittings | `j11-charlotte-pvc-sch-40-cold-water-service.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J12` | Charlotte Pipe — Cold Water Distribution - CPVC FlowGuard Gold CTS (SDR 11) | `j12-charlotte-flowguard-cpvc-cold-water-distribution.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J13` | Charlotte Pipe — Hot Water Distribution - CPVC FlowGuard Gold CTS (SDR 11) | `j13-charlotte-flowguard-cpvc-hot-water-distribution.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J5` | U.S. Solid — Angle / Isolation Valve - U.S. Solid 1/2 in 316 SS Mini Ball Valve | `j5-us-solid-316-ss-mini-ball-valve-angle-valve.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J6` | BrassCraft — Angle Valves - BrassCraft KTCR19 Compression Angle Supply Stop (Chrome) | `j6-brasscraft-ktcr19-angle-stop-valve.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J9` | Comparative Datasheet — Pipe Insulation - Micro-Lok HP vs Poly Pipe Insulation | `j9-comparison-micro-lok-hp-vs-poly-pipe-insulation.jpg` | No picture - the datasheet embeds none that passed the filter. |

## Noted — probably fine (1)

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `A-A3` | Pentair — Infinity-Edge Pump - Pentair IntelliFlo3 VSF | `a3-infinity-edge-pump-intelliflo3-vsf.jpg` | Identical file to A-A2. Same IntelliFlo3 VSF model, so defensible - replace only if you want the two told apart. |

---

Regenerated by hand after looking at every picture; there is no script that
decides these. The automatic picker is documented in the README under
*The picture* — it measures border uniformity and colour count, which is
enough to reject lifestyle photography and most line art, and not enough to
tell a chrome tap on white from a line drawing on white.
