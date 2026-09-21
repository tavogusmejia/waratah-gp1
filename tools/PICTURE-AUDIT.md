# Picture audit — GP1-MUR Material & Hardware Register

83 items, 81 with a picture. Nothing is plainly wrong.

## Where a picture can come from

1. **`tools/images/<slug>.jpg`** — an override; always wins.
2. **Beside the datasheet** — `DH4.jpg` next to `DH4 - Salto LA1T17 ....pdf`.
3. **Lifted out of the PDF** — border uniformity and colour count.

An override is matched on the **slug**, so it stops applying the moment a
folder is renumbered. When the plumbing group went J → P, seven pictures
quietly fell off and two items lost theirs entirely. The extractor now prints
`OVERRIDES THAT MATCHED NOTHING` — treat that list as an error, not a notice.

## How to replace one

**The quick way.** <https://claude.ai/artifact/9dF3DeNeQtkse2s8B4fepG> — drag a
photograph onto an item, `×` removes one dropped by mistake, *This one is fine*
clears a call you disagree with. The same page carries the manufacturer-page
links, which save themselves a second after you stop typing. Hand the batch
over and ask Claude to collect it.

**By hand.** Name the file as below, put it in `tools/images/`, re-run
`python tools/extract_datasheets.py`.

## Worth a second look (3)

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `C-C1` | Burndy — Pool Equipotential Bonding (NEC 680) - Burndy BWB680IG In-Ground Pool Water Bonding Kit | `c1-burndy-bwb680ig-in-ground-pool-water-bonding-kit.jpg` | Grey CAD render rather than a photograph — worth confirming it is the BWB680IG. |
| `L-LTRN3` | LTRN3 - DS - Lutron Feed-Through DIN Panel PD4-36F-120 | `ltrn3-ds-lutron-feed-through-din-panel-pd4-36f-120.jpg` | Dimension drawings rather than a product shot — your pick, flagged only so it is not a surprise. |
| `L-LTRN18` | LTRN18 - DS - Lutron Comercial System Warranty LSC-L2-P8LTD | `ltrn18-ds-lutron-comercial-system-warranty-lsc-l2-p8ltd.jpg` | A page of the warranty text rather than a product shot. Reasonable for a warranty document, flagged so you can swap it if you would rather show the panel it covers. |

## No picture (2)

Both Lutron. Their sheets are spec submittals of dimension drawings and text
with no product photograph to lift, so these need a source outside the
submittal folder — Lutron's own brochures carry photography, which is where
LTRN15's came from.

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `L-LTRN9` | LTRN9 - DS - Lutron Alisse Keypad Base HW-QS-B-S1 | `ltrn9-ds-lutron-alisse-keypad-base-hw-qs-b-s1.jpg` | No picture — the datasheet embeds none that passed the filter. |
| `L-LTRN21` | LTRN21 - DS - Lutron Palladiom Faceplate LWT-U-P-SB | `ltrn21-ds-lutron-palladiom-faceplate-lwt-u-p-sb.jpg` | No picture — the datasheet embeds none that passed the filter. |

## Probably fine (1)

| Item | What it is | File to drop in `tools/images/` | Why |
|---|---|---|---|
| `A-A3` | Pentair — Infinity-Edge Pump - Pentair IntelliFlo3 VSF | `a3-infinity-edge-pump-intelliflo3-vsf.jpg` | Identical file to A-A2. Same IntelliFlo3 VSF model, so defensible. |

## Duplicates worth knowing about

- `L-LTRN7` and `L-LTRN8` share the same Alisse finishes shot — one keypad
  image was staged for both.
- `L-LTRN25.2` and `L-LTRN26.1` are the same QS Link power supply, so the same
  picture is correct.
