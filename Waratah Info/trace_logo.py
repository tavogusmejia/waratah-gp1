#!/usr/bin/env python3
"""
Waratah brand marks - PNG to SVG tracer.

The brand arrived as PNG only. This traces the artwork back to vector so the
register can carry the mark at any size, in either theme, as inline SVG with no
raster asset and no build step.

    python trace_logo.py            # -> web/assets/brand/*.svg

The pipeline, in order, because each stage exists for a reason:

  1. THRESHOLD. The source is anti-aliased, so a pixel is "in" at >=50% of the
     way from the background to the ink colour. Measured against the actual
     brand colours (#DB3837 red, #65768E slate) rather than luminance, because
     the two are within 0.03 of each other in perceived lightness and a
     luminance threshold cannot tell them apart.

  2. SUPERSAMPLE 2x before tracing. Costs nothing and halves the amplitude of
     the staircase the contour follower produces.

  3. CONTOUR FOLLOW along pixel cracks, not pixel centres. Every boundary edge
     is emitted directed so that ink is on its right, which makes outer
     contours and holes wind in opposite directions automatically - so the
     nonzero fill rule renders the counters of A and R as holes with no extra
     bookkeeping.

  4. CORNER DETECT, then fit each smooth span separately. The petal tips are
     cusps and the bract has hard corners; a fitter that is not told about them
     rounds them off, which is the most visible way a traced logo looks wrong.

  5. FIT cubic Beziers (Schneider: least-squares fit, Newton-Raphson
     reparameterisation, recursive split at the worst point). Fitting curves -
     rather than simplifying to line segments - is what removes the residual
     staircase, because a smooth curve cannot follow one.

Crops are hard-coded because they were measured off the source by row/column
ink profile, not guessed. If the source art is ever replaced, re-measure: a
crop that clips a letter by even a few pixels silently splits it into extra
contours, and the fit still "succeeds".

Python 3.12 + Pillow. No numpy, no potrace.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
STACKED = HERE / "Logos" / "302611879_194455022965838_7842807474640252843_n.png"
OUT_DIR = HERE.parent / "web" / "assets" / "brand"

RED = (0xDB, 0x38, 0x37)
SLATE = (0x65, 0x76, 0x8E)

# Measured ink extents in the stacked source, padded by a few pixels.
CROP_MARK = (710, 375, 1338, 877)
CROP_WORD = (120, 966, 1901, 1239)
CROP_SUB = (473, 1344, 1572, 1425)

SS = 2           # supersample factor
CORNER_DEG = 62  # interior turn sharper than this is a corner, not a curve
FIT_TOL = 0.9    # max fit error, supersampled pixels
SMOOTH = 2       # vertex smoothing passes over the raw staircase

NL = chr(10)


# ---------------------------------------------------------------- mask

def ink_mask(im, target, bbox, supersample=SS):
    """Binary mask of pixels at least half-way from white to `target`."""
    region = im.crop(bbox)
    if supersample != 1:
        region = region.resize(
            (region.width * supersample, region.height * supersample),
            Image.LANCZOS,
        )
    w, h = region.size
    px = region.load()
    tr, tg, tb = target
    # Position along the white -> target axis.
    dr, dg, db = tr - 255, tg - 255, tb - 255
    denom = dr * dr + dg * dg + db * db
    grid = bytearray(w * h)
    for y in range(h):
        row = y * w
        for x in range(w):
            r, g, b = px[x, y][:3]
            t = ((r - 255) * dr + (g - 255) * dg + (b - 255) * db) / denom
            # Reject colours that project far along the axis but sit well off
            # it - that is what keeps the red mask from catching slate, and
            # the slate mask from catching red.
            pr, pg, pb = 255 + dr * t, 255 + dg * t, 255 + db * t
            off = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            grid[row + x] = 1 if (t >= 0.5 and off < 3000) else 0
    return grid, w, h


# ------------------------------------------------------- contour follow

def contours(grid, w, h):
    """Closed polygons along pixel cracks, ink on the right of travel."""
    def at(x, y):
        return grid[y * w + x] if 0 <= x < w and 0 <= y < h else 0

    edges = {}
    for y in range(h):
        for x in range(w):
            if not at(x, y):
                continue
            if not at(x, y - 1):
                edges.setdefault((x, y), []).append((x + 1, y))
            if not at(x + 1, y):
                edges.setdefault((x + 1, y), []).append((x + 1, y + 1))
            if not at(x, y + 1):
                edges.setdefault((x + 1, y + 1), []).append((x, y + 1))
            if not at(x - 1, y):
                edges.setdefault((x, y + 1), []).append((x, y))

    loops = []
    while edges:
        start = next(iter(edges))
        loop = [start]
        cur = start
        prev_dir = None
        while True:
            outs = edges.get(cur)
            if not outs:
                break
            if len(outs) == 1 or prev_dir is None:
                nxt = outs[0]
            else:
                # At a diagonal pinch two edges leave the same point. Take the
                # sharpest turn: that keeps the loop tight against the ink
                # instead of jumping across the pinch.
                def turn(p, cur=cur, prev_dir=prev_dir):
                    d = (p[0] - cur[0], p[1] - cur[1])
                    return math.atan2(
                        prev_dir[0] * d[1] - prev_dir[1] * d[0],
                        prev_dir[0] * d[0] + prev_dir[1] * d[1],
                    )
                nxt = min(outs, key=turn)
            outs.remove(nxt)
            if not outs:
                del edges[cur]
            prev_dir = (nxt[0] - cur[0], nxt[1] - cur[1])
            cur = nxt
            if cur == start:
                break
            loop.append(cur)
        if len(loop) >= 8:
            loops.append([(float(x), float(y)) for x, y in loop])
    return loops


def smooth_closed(pts, passes=SMOOTH):
    """Average each vertex with its neighbours - takes the edge off the
    staircase without moving the contour off the shape."""
    n = len(pts)
    for _ in range(passes):
        out = []
        for i in range(n):
            x0, y0 = pts[(i - 1) % n]
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            out.append(((x0 + 2 * x1 + x2) / 4, (y0 + 2 * y1 + y2) / 4))
        pts = out
    return pts


def dedupe(pts, eps=1e-9):
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    return out


# ------------------------------------------------------------ geometry

def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def mul(a, s):
    return (a[0] * s, a[1] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def norm(a):
    d = math.hypot(*a)
    return (a[0] / d, a[1] / d) if d else (0.0, 0.0)


def corners(pts, deg=CORNER_DEG):
    """Indices where the contour genuinely turns rather than curves.

    Measured over a window, not between adjacent vertices: adjacent vertices on
    a traced staircase always sit at 90 degrees to each other, so every one of
    them would read as a corner.
    """
    n = len(pts)
    win = max(2, int(n / 120) + 2)
    thresh = math.radians(180 - deg)
    idx = []
    for i in range(n):
        a = norm(sub(pts[i], pts[(i - win) % n]))
        b = norm(sub(pts[(i + win) % n], pts[i]))
        if a == (0.0, 0.0) or b == (0.0, 0.0):
            continue
        ang = math.acos(max(-1.0, min(1.0, dot(a, b))))
        if ang > thresh:
            idx.append((i, ang))
    # Collapse runs of adjacent hits to the sharpest one in each run.
    out = []
    run = []
    for i, ang in idx:
        if run and i - run[-1][0] <= win:
            run.append((i, ang))
        else:
            if run:
                out.append(max(run, key=lambda t: t[1])[0])
            run = [(i, ang)]
    if run:
        out.append(max(run, key=lambda t: t[1])[0])
    return sorted(set(out))


# ------------------------------------------------- Schneider curve fit

def bezier(c, t):
    mt = 1 - t
    return (
        c[0][0] * mt ** 3 + 3 * c[1][0] * mt * mt * t
        + 3 * c[2][0] * mt * t * t + c[3][0] * t ** 3,
        c[0][1] * mt ** 3 + 3 * c[1][1] * mt * mt * t
        + 3 * c[2][1] * mt * t * t + c[3][1] * t ** 3,
    )


def chord_params(pts):
    u = [0.0]
    for i in range(1, len(pts)):
        u.append(u[-1] + math.hypot(*sub(pts[i], pts[i - 1])))
    total = u[-1] or 1.0
    return [v / total for v in u]


def fit_one(pts, u, t1, t2):
    """Least-squares cubic with fixed endpoints and fixed tangent directions."""
    a1 = [mul(t1, 3 * (1 - t) ** 2 * t) for t in u]
    a2 = [mul(t2, 3 * (1 - t) * t * t) for t in u]
    c11 = c12 = c22 = x1 = x2 = 0.0
    p0, p3 = pts[0], pts[-1]
    for i, t in enumerate(u):
        mt = 1 - t
        base = add(mul(p0, mt ** 3 + 3 * mt * mt * t),
                   mul(p3, 3 * mt * t * t + t ** 3))
        d = sub(pts[i], base)
        c11 += dot(a1[i], a1[i])
        c12 += dot(a1[i], a2[i])
        c22 += dot(a2[i], a2[i])
        x1 += dot(d, a1[i])
        x2 += dot(d, a2[i])
    det = c11 * c22 - c12 * c12
    seg = math.hypot(*sub(p3, p0))
    if abs(det) < 1e-12:
        alpha1 = alpha2 = seg / 3
    else:
        alpha1 = (x1 * c22 - c12 * x2) / det
        alpha2 = (c11 * x2 - x1 * c12) / det
    if alpha1 < 1e-6 or alpha2 < 1e-6:
        alpha1 = alpha2 = seg / 3
    return [p0, add(p0, mul(t1, alpha1)), add(p3, mul(t2, alpha2)), p3]


def max_error(pts, u, c):
    worst = 0.0
    at = len(pts) // 2
    for i in range(1, len(pts) - 1):
        d = sub(bezier(c, u[i]), pts[i])
        e = dot(d, d)
        if e > worst:
            worst, at = e, i
    return math.sqrt(worst), at


def reparam(pts, u, c):
    d1 = [mul(sub(c[i + 1], c[i]), 3) for i in range(3)]
    d2 = [mul(sub(d1[i + 1], d1[i]), 2) for i in range(2)]
    out = []
    for i, t in enumerate(u):
        mt = 1 - t
        q = sub(bezier(c, t), pts[i])
        qp = add(add(mul(d1[0], mt * mt), mul(d1[1], 2 * mt * t)),
                 mul(d1[2], t * t))
        qpp = add(mul(d2[0], mt), mul(d2[1], t))
        den = dot(qp, qp) + dot(q, qpp)
        out.append(t if abs(den) < 1e-12
                   else min(1.0, max(0.0, t - dot(q, qp) / den)))
    return out


def fit_span(pts, t1, t2, tol, depth=0):
    if len(pts) < 3:
        seg = math.hypot(*sub(pts[-1], pts[0])) / 3
        return [[pts[0], add(pts[0], mul(t1, seg)),
                 add(pts[-1], mul(t2, seg)), pts[-1]]]
    u = chord_params(pts)
    c = fit_one(pts, u, t1, t2)
    err, at = max_error(pts, u, c)
    if err < tol:
        return [c]
    if err < tol * 4 and depth < 12:
        for _ in range(4):
            u = reparam(pts, u, c)
            c = fit_one(pts, u, t1, t2)
            err, at = max_error(pts, u, c)
            if err < tol:
                return [c]
    if depth > 14 or at <= 0 or at >= len(pts) - 1:
        return [c]
    tc = norm(sub(pts[at + 1], pts[at - 1]))
    return (fit_span(pts[:at + 1], t1, (-tc[0], -tc[1]), tol, depth + 1)
            + fit_span(pts[at:], tc, t2, tol, depth + 1))


def fit_closed(pts, tol=FIT_TOL):
    pts = dedupe(pts)
    n = len(pts)
    cs = corners(pts)
    if not cs:
        # No corners: cut anywhere and fit the loop with matching tangents.
        seq = pts + [pts[0]]
        t1 = norm(sub(seq[1], seq[-2]))
        return fit_span(seq, t1, (-t1[0], -t1[1]), tol)
    curves = []
    for k in range(len(cs)):
        i, j = cs[k], cs[(k + 1) % len(cs)]
        # `or n` is load-bearing: with exactly one corner, i == j and the span
        # is the whole loop coming back to that corner, not a single point.
        # Without it such a contour fits to nothing and silently disappears -
        # which is how the counter of R went missing and the letter filled in.
        span = dedupe([pts[(i + s) % n] for s in range((((j - i) % n) or n) + 1)])
        if len(span) < 2:
            continue
        t1 = norm(sub(span[1], span[0]))
        t2 = norm(sub(span[-2], span[-1]))
        curves += fit_span(span, t1, t2, tol)
    return curves


# -------------------------------------------------------------- trace

def trace(im, target, bbox, tol=FIT_TOL):
    """Trace one ink colour inside `bbox`, returned in SOURCE pixel space.

    Everything lands back in the coordinates of the stacked lockup, so the
    three pieces compose into the stacked logo with no measuring - the artwork
    already holds the relationship between them.
    """
    grid, w, h = ink_mask(im, target, bbox)
    loops = contours(grid, w, h)
    loops.sort(key=len, reverse=True)
    ox, oy = bbox[0], bbox[1]
    out = []
    for poly in loops:
        curves = fit_closed(smooth_closed(poly), tol)
        out.append([[(ox + x / SS, oy + y / SS) for x, y in c]
                    for c in curves])
    return out


def bounds(groups):
    xs, ys = [], []
    for loops in groups:
        for curves in loops:
            for c in curves:
                for x, y in c:
                    xs.append(x)
                    ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def fmt(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def path_d(loops, tx):
    """Path data for one colour. `tx` maps source pixels to viewBox units."""
    out = []
    for curves in loops:
        if not curves:
            continue
        x, y = tx(*curves[0][0])
        out.append("M" + fmt(x) + " " + fmt(y))
        for c in curves:
            (x1, y1), (x2, y2), (x3, y3) = (tx(*q) for q in c[1:])
            out.append("C" + fmt(x1) + " " + fmt(y1) + " "
                       + fmt(x2) + " " + fmt(y2) + " "
                       + fmt(x3) + " " + fmt(y3))
        out.append("Z")
    return "".join(out)


# --------------------------------------------------------------- emit

LIGHT = {"m": "#DB3837", "w": "#65768E"}
# Same hue angles, lifted in OKLCH lightness only: red 0.590 -> 0.660 and
# slate 0.561 -> 0.800. That takes them from 4.04:1 and 3.95:1 on a near-black
# ground to 5.39:1 and 9.81:1. Hue is untouched, so it is still the brand.
DARK = {"m": "#EE5952", "w": "#B0BFD5"}

STYLE = """  <style>
    /* Bare `svg` selectors on purpose: any page rule is more specific and
       wins, so a page that inlines this themes it from its own tokens and
       keeps an explicit light/dark toggle working. The media query below is
       only the standalone fallback, for img elements and direct viewing.
       Keep angle brackets out of this comment entirely: an SVG is parsed as
       XML, so one in here makes the whole file fail to render - as a broken
       image, with no console error to go on. */
    svg .m{fill:LM}
    svg .w{fill:LW}
    @media (prefers-color-scheme:dark){
      svg .m{fill:DM}
      svg .w{fill:DW}
    }
  </style>"""


def svg(groups, title, auto):
    """Assemble one SVG. `groups` is [(class, loops), ...]."""
    x0, y0, x1, y1 = bounds([g for _, g in groups])
    w, h = x1 - x0, y1 - y0
    # Normalise to a 1000-unit tall canvas: round numbers in the markup, and
    # every file stays directly comparable in scale.
    k = 1000.0 / h

    def tx(x, y):
        return ((x - x0) * k, (y - y0) * k)

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '
        + fmt(w * k) + ' 1000" role="img" aria-label="' + title + '">',
        "  <title>" + title + "</title>",
    ]
    if auto:
        parts.append(STYLE.replace("LM", LIGHT["m"]).replace("LW", LIGHT["w"])
                          .replace("DM", DARK["m"]).replace("DW", DARK["w"]))
    for cls, loops in groups:
        fill = "" if auto else ' fill="' + DARK[cls] + '"'
        parts.append('  <path class="' + cls + '"' + fill
                     + ' d="' + path_d(loops, tx) + '"/>')
    parts.append("</svg>")
    return NL.join(parts) + NL


def horizontal(mark, word):
    """Lay the mark beside the wordmark using the ratios the horizontal
    artwork actually uses - measured off it, not invented:

        mark height = 1.534 x cap height
        gap         = 0.328 x cap height
        the mark rides 0.092 cap heights above the wordmark's centre
    """
    mx0, my0, mx1, my1 = bounds([mark])
    wx0, wy0, wx1, wy1 = bounds([word])
    cap = wy1 - wy0
    scale = (1.534 * cap) / (my1 - my0)
    gap = 0.328 * cap
    dx = (wx0 - gap) - mx1 * scale
    dy = ((wy0 + wy1) / 2 - 0.092 * cap) - ((my0 + my1) / 2) * scale
    return [[[(x * scale + dx, y * scale + dy) for x, y in c]
             for c in curves] for curves in mark]


INDEX = OUT_DIR.parents[1] / "index.html"

# The landing is traced a second time, coarsely. At the size it paints - a
# 370px lockup - a 4px fit error over a 255px cap height lands at about a
# third of a pixel, which nobody can see, and it halves the bytes. The landing
# is the one place in this project where "close enough" is the right answer,
# because the whole point of it is arriving in a single round trip.
LANDING_TOL = 4.0


def path_el(pid, loops, box_h):
    """One <path> with an id, normalised to a box `box_h` units tall."""
    x0, y0, x1, y1 = bounds([loops])
    k = box_h / (y1 - y0)

    def tx(x, y):
        return ((x - x0) * k, (y - y0) * k)

    return ('<path id="' + pid + '" d="' + path_d(loops, tx) + '"/>',
            fmt((x1 - x0) * k))


def inline_landing(im, mark):
    """Write the copy of the artwork that index.html paints from.

    The landing must not fetch anything, so the artwork is inline in the HTML -
    which makes it a second copy of something already traced. It is written
    from here so the copy cannot drift from the file it came from, the same way
    the seed and the SQL import are generated rather than kept in step by hand.

    It goes in ONCE, as two <path>s in a hidden <defs>, and both the landing
    and the page header reach it with <use>. Inlining it twice would be about
    16 KB more HTML and would push the page out of the single round trip that
    is the whole point of the landing. The defs live outside #splash on
    purpose: the landing deletes itself, and it must not take the header's
    logo with it.
    """
    if not INDEX.exists():
        print("  (no index.html; skipping the landing)")
        return
    word = trace(im, SLATE, CROP_WORD, tol=LANDING_TOL)
    check("landing wordmark", [word])

    p_mark, w_mark = path_el("wm", mark, 1000.0)
    p_word, w_word = path_el("ww", word, 142.0)
    el = ('<svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" '
          'style="position:absolute;width:0;height:0;overflow:hidden">'
          "<defs>" + p_mark + p_word + "</defs></svg>")

    # The file as a whole is HTML and will not parse as XML, but this fragment
    # is SVG and must - it is the same trap that made the standalone marks
    # render as broken images.
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(el)
    except ET.ParseError as e:
        sys.exit("the inline brand defs are not well-formed: " + str(e))

    html = INDEX.read_text(encoding="utf-8")
    a, b = html.find("<!-- brand:defs"), html.find("<!-- /brand:defs -->")
    if a < 0 or b < 0:
        sys.exit("index.html has lost its brand:defs markers")
    a = html.index("-->", a) + 3
    html = html[:a] + NL + el + NL + html[b:]

    # The <use> wrappers carry their own viewBox, and a wrong one is the kind
    # of mistake that looks like a design choice: the logo simply sits a few
    # per cent small, or off centre, and nothing anywhere reports it. So the
    # widths are asserted rather than trusted.
    for pid, w, h in (("#wm", w_mark, "1000"), ("#ww", w_word, "142")):
        want = 'viewBox="0 0 ' + w + " " + h + '"'
        used = html.count('href="' + pid + '"')
        if used and html.count(want) < used:
            sys.exit("index.html: every svg using " + pid + " needs "
                     + want + " (found " + str(html.count(want))
                     + " of " + str(used) + ")")

    INDEX.write_text(html, encoding="utf-8")
    print("  index.html   brand:defs %5.1f KB   mark 0 0 %s 1000, word 0 0 %s 142"
          % (len(el) / 1024, w_mark, w_word))


def check(name, groups):
    """Both of these have shipped as silently wrong output before.

    An empty contour is the dangerous one: nothing raises, the file is valid,
    and a counter just quietly fills in. Compare the contour count against the
    source instead of trusting the run.
    """
    for loops in groups:
        for i, curves in enumerate(loops):
            if not curves:
                sys.exit(name + ": contour " + str(i) + " fitted to nothing")


def check_xml(path):
    import xml.etree.ElementTree as ET
    try:
        ET.parse(path)
    except ET.ParseError as e:
        sys.exit(path.name + " is not well-formed XML: " + str(e))


def main():
    if not STACKED.exists():
        sys.exit("missing source: " + str(STACKED))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    im = Image.open(STACKED).convert("RGB")

    pieces = []
    for name, target, crop in (("mark", RED, CROP_MARK),
                               ("WARATAH", SLATE, CROP_WORD),
                               ("CONSTRUCTION", SLATE, CROP_SUB)):
        print("tracing " + name + " ...")
        g = trace(im, target, crop)
        check(name, [g])
        x0, y0, x1, y1 = bounds([g])
        print("  %2d contours  %3d curves  %7.1f x %6.1f"
              % (len(g), sum(len(c) for c in g), x1 - x0, y1 - y0))
        pieces.append(g)
    mark, word, sub_ = pieces

    files = {
        "waratah-mark": ([("m", mark)], "Waratah"),
        "waratah-logo": ([("m", horizontal(mark, word)), ("w", word)],
                         "Waratah"),
        "waratah-logo-stacked": ([("m", mark), ("w", word), ("w", sub_)],
                                 "Waratah Construction"),
    }
    print()
    for stem, (groups, title) in files.items():
        for suffix, auto in ((".svg", True), ("-dark.svg", False)):
            out = OUT_DIR / (stem + suffix)
            out.write_text(svg(groups, title, auto), encoding="utf-8")
            check_xml(out)
            print("  %-34s %5.1f KB"
                  % (out.name, len(out.read_bytes()) / 1024))
    inline_landing(im, mark)


if __name__ == "__main__":
    main()
