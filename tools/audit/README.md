# The picture-audit page

The page at <https://claude.ai/artifact/9dF3DeNeQtkse2s8B4fepG> is built from
here. It lived in a session scratchpad until a round of pasted manufacturer
links was lost; the point of this folder is that neither the page nor the work
it collects depends on a session staying alive.

```bash
python tools/audit/build_audit.py     # -> tools/audit/picture-audit.html
python tools/audit/make_linktest.py   # -> tools/audit/_linktest.html
```

| File | What it is |
|---|---|
| `build_audit.py` | Builds the page. Reads `audit.json`, `links.json` and `web/data/datasheets.json`. |
| `page.js` | The page's behaviour, inlined by the builder. |
| `audit.json` | The picture flags — one row per item worth a second look. |
| `links.json` | The manufacturer links, keyed by **slug**. |
| `make_linktest.py` | Wraps the built page in a fake artifact store and drives it. |

## Slugs, not codes

`links.json` and the `maker` collection are keyed on the item slug, because
`group+code` is not unique (82 distinct for 83 items) and the slug is (83/83).
Renumbering a folder changes slugs, and a stale key saves into a document
nothing will ever read. After any renumbering, re-run `build_audit.py` and
check that every `data-slug` still matches an item.

## Testing the saving

`make_linktest.py` is the guard on the thing that failed. It stands a fake
store in front of the real page and drives the rows: typing, blurring, bad
input, clearing, a store that refuses, a store that answers a read before the
write lands, hiding the tab, and both buttons. Run it after any change to the
link code.

```
24 passed, 0 failed
```

## How saving works now

A link writes itself a second after you stop typing, and again on blur. The
row turns green only after the value has been **read back out of the store** —
green means the database holds it, not that a call returned. A write that
fails turns the row red and stays red; the status line counts what is saved,
what is not a URL, and what would not save. `Copy every link` puts every link
on the clipboard as CSV, so the work survives even a store that is completely
unreachable.
