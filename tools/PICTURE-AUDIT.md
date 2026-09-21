# Picture audit — GP1-MUR Material & Hardware Register

67 items, 43 with a picture. The nine that were plainly wrong have been
replaced from the audit page. What follows is what is left.

## How to replace one

**The quick way.** <https://claude.ai/artifact/9dF3DeNeQtkse2s8B4fepG> — drag a
photograph onto an item and it is stored against that item under the right
name. `×` removes one dropped by mistake. *This one is fine* clears a call you
disagree with, and the count drops. When the batch is ready, hand it over and
ask Claude to collect it.

**By hand.** Name the file as below, put it in `tools/images/`, and re-run
`python tools/extract_datasheets.py`. `.jpg`, `.jpeg`, `.png` and `.webp` all
work, and a file there always beats the automatic pick.

> A slug-named override only matches while that datasheet keeps its filename.
> Two overrides were orphaned when the electrical sheets were renamed at the
> source; the extractor now lists any that match nothing.

## Worth a second look (3)

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `B-B2` | Color Match Pool Fittings — Pool Shallow Floor Return - Color Match Pebble Top PTFR-03 (Light Gray) | `b2-color-match-floor-return-ptfr-03.jpg` | The new picture sits on black with a yellow block - it will read as a dark rectangle on the light tile. |
| `H-H1` | Burndy — Pool Equipotential Bonding (NEC 680) - Burndy BWB680IG In-Ground Pool Water Bonding Kit | `h1-burndy-bwb680ig-in-ground-pool-water-bonding-kit.jpg` | Grey CAD render rather than a photograph - worth confirming it is the BWB680IG. |
| `J-J2` | Taco — Recirculation Pump - Taco 2400 Series High-Capacity Circulator | `j2-taco-2400-series-recirculation-pump.jpg` | The new picture sits on a solid green ground rather than a plain one. |

## No picture (24)

The datasheet embeds none that passed the filter. The register shows the item code on a tile, which is correct behaviour rather than a fault.

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `B-B3` | Hayward — Pool Wall & Infinity-Edge Return Inlets, 2 in - Hayward SP1419D (Gray: SP1419DGR) | `b3-hayward-sp1419d.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `B-B4` | Hayward — Vacuum Fitting - Hayward SP1022 (Gray: SP1022GR) | `b4-hayward-sp1022.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `B-B6` | Pentair — Automatic Water Filler - Pentair T40-F | `b6-pentair-t40-f-automatic-water-filler.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-1` | Häfele — Concealed Mortise Hinge - Häfele 3D-Adjustable (927.91.833) | `dh-01-hafele-startec-concealed-hinge.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-2` | Salto — Lever Handle Set - Salto Standard Line, London | `dh-02-salto-london-lever-handle.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-3` | Salto — Electronic Lockset - Salto Ælement Fusion (ANSI) | `dh-03-salto-aelement-fusion-lockset-ring-reader.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-4` | Salto — Mechanical Privacy Thumbturn - Salto LA1T17 Mortise Lock | `dh-04-salto-la1t17-privacy-thumbturn.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-5` | Häfele — Door Viewer - Häfele Startec 200° (959.01.042) | `dh-05-hafele-startec-door-viewer.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-6` | Häfele — Sliding Door Fitting - Häfele Hawa Junior 80/100B (941.04.012) | `dh-06-hafele-hawa-junior-80b-pocket.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-6.1` | Häfele — Sliding Door Hardware - Häfele Slido D-Line11 160P (941.62.018) | `dh-07-hafele-slido-d-line11-160p.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-7` | Assa Abloy — Automatic Drop-Down Seal - Assa Abloy Planet X3 RD | `dh-08-assa-abloy-planet-x3-rd-drop-seal.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-7.1` | Reflect — Door-Jamb Weatherstrip - Reflect Silicone Bulb Seal | `dh-09-reflect-door-jamb-weatherstrip.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-DH-02` | DH-02 - IG - Salto London Lever Handle | `dh-02-ig-salto-london-lever-handle.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-DH-03` | DH-03 - IG - Salto AElement Fusion Lockset & Ring Reader | `dh-03-ig-salto-aelement-fusion-lockset-ring-reader.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-DH-04` | DH-04 - IG - Salto LA1T17 Privacy Thumbturn | `dh-04-ig-salto-la1t17-privacy-thumbturn.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `D-DH-07` | DH-07 - DS - Hafele Slido D-Line11 160P | `dh-07-ds-hafele-slido-d-line11-160p.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `E-09` | ABB — Circuit Breaker, Ground Fault Plug-In - THQL2160GFT2 | `e8-ground-fault-breaker-thql2160gft2.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `G-G2` | Jandy (Fluidra) — PVC Check Valves - Jandy positive-seal check valve | `g2-jandy-check-valves.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J11` | Charlotte Pipe — Cold Water Service - PVC Schedule 40 Pressure Pipe & Fittings | `j11-charlotte-pvc-sch-40-cold-water-service.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J12` | Charlotte Pipe — Cold Water Distribution - CPVC FlowGuard Gold CTS (SDR 11) | `j12-charlotte-flowguard-cpvc-cold-water-distribution.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J13` | Charlotte Pipe — Hot Water Distribution - CPVC FlowGuard Gold CTS (SDR 11) | `j13-charlotte-flowguard-cpvc-hot-water-distribution.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J5` | U.S. Solid — Angle / Isolation Valve - U.S. Solid 1/2 in 316 SS Mini Ball Valve | `j5-us-solid-316-ss-mini-ball-valve-angle-valve.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J6` | BrassCraft — Angle Valves - BrassCraft KTCR19 Compression Angle Supply Stop (Chrome) | `j6-brasscraft-ktcr19-angle-stop-valve.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `J-J9` | Comparative Datasheet — Pipe Insulation - Micro-Lok HP vs Poly Pipe Insulation | `j9-comparison-micro-lok-hp-vs-poly-pipe-insulation.jpg` | No picture - the datasheet embeds none that passed the filter. |

## Probably fine (1)

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `A-A3` | Pentair — Infinity-Edge Pump - Pentair IntelliFlo3 VSF | `a3-infinity-edge-pump-intelliflo3-vsf.jpg` | Identical file to A-A2. Same IntelliFlo3 VSF model, so defensible - replace only if you want the two told apart. |
