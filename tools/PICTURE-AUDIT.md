# Picture audit — GP1-MUR Material & Hardware Register

82 items, 60 with a picture. Everything that was plainly wrong has been
replaced. What is left is below.

## Where a picture can come from

In order of who said so most deliberately:

1. **`tools/images/<slug>.jpg`** — an override; always wins.
2. **Beside the datasheet** — `DH4.jpg` next to `DH4 - Salto LA1T17 ....pdf`,
   named by item code. The natural place to put one.
3. **Lifted out of the PDF** — border uniformity and colour count, enough to
   reject lifestyle photography and most line art.

## How to replace one

**The quick way.** <https://claude.ai/artifact/9dF3DeNeQtkse2s8B4fepG> — drag a
photograph onto an item, `×` removes one dropped by mistake, *This one is fine*
clears a call you disagree with. Hand the batch over and ask Claude to collect it.

**By hand.** Name the file as below, put it in `tools/images/`, re-run
`python tools/extract_datasheets.py`.

> A slug-named override only matches while the datasheet keeps its filename.
> The extractor lists any that match nothing — that folder gets reorganised.

## Worth a second look (1)

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `H-H1` | Burndy — Pool Equipotential Bonding (NEC 680) - Burndy BWB680IG In-Ground Pool Water Bonding Kit | `h1-burndy-bwb680ig-in-ground-pool-water-bonding-kit.jpg` | Grey CAD render rather than a photograph - worth confirming it is the BWB680IG. |

## No picture (22)

The datasheet embeds none that passed the filter. Mostly Lutron lighting sheets, which are the vendor's own PDFs with nothing to lift. The register shows the item code on a tile, which is correct behaviour rather than a fault.

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `B-B3` | Hayward — Pool Wall & Infinity-Edge Return Inlets, 2 in - Hayward SP1419D (Gray: SP1419DGR) | `b3-hayward-sp1419d.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `B-B4` | Hayward — Vacuum Fitting - Hayward SP1022 (Gray: SP1022GR) | `b4-hayward-sp1022.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `B-B6` | Pentair — Automatic Water Filler - Pentair T40-F | `b6-pentair-t40-f-automatic-water-filler.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L1` | L1 - DS - Lutron myRoom XC Processor MP-1L-GCU | `l1-ds-lutron-myroom-xc-processor-mp-1l-gcu.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L10` | L10 - DS - Lutron Wallbox EBB-1-SQ | `l10-ds-lutron-wallbox-ebb-1-sq.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L11` | L11 - DS - Lutron Radio Powr Savr Occupancy Sensor LRF2-OCR2B-P-WH | `l11-ds-lutron-radio-powr-savr-occupancy-sensor-lrf2-ocr2b-p-wh.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L13` | L13 - DS - Lutron Maestro Occupancy Switch MS-OPS2-WH | `l13-ds-lutron-maestro-occupancy-switch-ms-ops2-wh.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L15` | L15 - DS - Lutron Palladiom Thermostat MWP-T-OHW-WH-A | `l15-ds-lutron-palladiom-thermostat-mwp-t-ohw-wh-a.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L16` | L16 - DS - Lutron Fan-Coil Controller SMC55-MYRM | `l16-ds-lutron-fan-coil-controller-smc55-myrm.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L18` | L18 - DS - Lutron Comercial System Warranty LSC-L2-P8LTD | `l18-ds-lutron-comercial-system-warranty-lsc-l2-p8ltd.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L19` | L19 - DS - Lutron Palladiom USB Receptacle LTR-15-CCTR-BL | `l19-ds-lutron-palladiom-usb-receptacle-ltr-15-cctr-bl.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L20` | L20 - DS - Lutron Architectural Receptacle LTR-15-TR-BL | `l20-ds-lutron-architectural-receptacle-ltr-15-tr-bl.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L21` | L21 - DS - Lutron Palladiom Faceplate LWT-U-P-SB | `l21-ds-lutron-palladiom-faceplate-lwt-u-p-sb.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L22` | L22 - DS - Lutron Nova T GFCI Receptacle NTR-15-GFST-BL | `l22-ds-lutron-nova-t-gfci-receptacle-ntr-15-gfst-bl.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L24` | L24 - DS - Lutron Grafik Eye Control Cable GRX-CBL-46L-500 | `l24-ds-lutron-grafik-eye-control-cable-grx-cbl-46l-500.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L25.1` | L25.1 - DS - Lutron Sivoia QS Dual Shade Bracketry Kits WIN-BRK | `l25-1-ds-lutron-sivoia-qs-dual-shade-bracketry-kits-win-brk.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L26` | L26 - DS - Lutron D145 Drapery Track System | `l26-ds-lutron-d145-drapery-track-system.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L27` | L27 - DS - Lutron QS Link Plug-In Power Supply (Shading) | `l27-ds-lutron-qs-link-plug-in-power-supply-shading.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L3` | L3 - DS - Lutron Feed-Through DIN Panel PD4-36F-120 | `l3-ds-lutron-feed-through-din-panel-pd4-36f-120.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L7` | L7 - DS - Lutron Alisse 1-Column Keypad HW-NW-KP-S1-E | `l7-ds-lutron-alisse-1-column-keypad-hw-nw-kp-s1-e.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L8` | L8 - DS - Lutron Alisse 2-Column Keypad HW-NW-KP-S2-E | `l8-ds-lutron-alisse-2-column-keypad-hw-nw-kp-s2-e.jpg` | No picture - the datasheet embeds none that passed the filter. |
| `L-L9` | L9 - DS - Lutron Alisse Keypad Base HW-QS-B-S1 | `l9-ds-lutron-alisse-keypad-base-hw-qs-b-s1.jpg` | No picture - the datasheet embeds none that passed the filter. |

## Probably fine (1)

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `A-A3` | Pentair — Infinity-Edge Pump - Pentair IntelliFlo3 VSF | `a3-infinity-edge-pump-intelliflo3-vsf.jpg` | Identical file to A-A2. Same IntelliFlo3 VSF model, so defensible - replace only if you want the two told apart. |
