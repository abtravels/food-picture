#!/usr/bin/env python3
"""Golden honey — a picture that tastes of one ingredient.

Draws, from scratch in pure code, a wooden honey dipper dripping a thick
glossy ribbon of honey into a swirling pool of honey, on a dark slate
background. One ingredient (honey) dominates the frame.

Standard library ONLY (math, os, struct, zlib): the canvas is a bytearray
rasterised by hand (scanline spans, per-row blended colours) and the PNG
is encoded by hand (signature + IHDR/IDAT/IEND, zlib, CRCs). No third
party imports, no network, no input files. Writes /output/entry.png
(1024x1024). Fully deterministic: every value is computed from fixed
constants, so repeated runs produce byte-identical output.
"""

import math
import os
import struct
import zlib

W = H = 1024
OUT = "/output/entry.png"

# ---- palette -------------------------------------------------------------
SLATE_TOP = (26, 32, 40)
SLATE_BOT = (13, 16, 21)
GLOW = (255, 176, 32)          # warm halo behind the pool
POOL_EDGE = (122, 66, 0)
POOL_MID = (216, 138, 8)
POOL_CORE = (255, 190, 56)
POOL_DEEP = (160, 96, 4)
HONEY_TOP = (255, 196, 66)
HONEY_BOT = (214, 128, 6)
WOOD = (139, 90, 43)
WOOD_DARK = (96, 58, 24)
WOOD_LIGHT = (178, 122, 62)
CREAM = (255, 232, 170)
BLACK = (0, 0, 0)

# The canvas: W*H*3 bytes of RGB, row-major.
px = bytearray(W * H * 3)

# Precomputed background gradient, one RGB tuple per row.
BG_ROWS = []
for _y in range(H):
    _t = _y / (H - 1)
    BG_ROWS.append((
        int(round(SLATE_TOP[0] + (SLATE_BOT[0] - SLATE_TOP[0]) * _t)),
        int(round(SLATE_TOP[1] + (SLATE_BOT[1] - SLATE_TOP[1]) * _t)),
        int(round(SLATE_TOP[2] + (SLATE_BOT[2] - SLATE_TOP[2]) * _t)),
    ))


def clamp(v):
    return 0 if v < 0 else (255 if v > 255 else v)


def lerp3(a, b, t):
    """Linear interpolation between two RGB tuples."""
    return (
        clamp(int(round(a[0] + (b[0] - a[0]) * t))),
        clamp(int(round(a[1] + (b[1] - a[1]) * t))),
        clamp(int(round(a[2] + (b[2] - a[2]) * t))),
    )


def blend3(src, dst, alpha):
    """src over dst at the given alpha (0-255)."""
    inv = 255 - alpha
    return (
        (src[0] * alpha + dst[0] * inv) // 255,
        (src[1] * alpha + dst[1] * inv) // 255,
        (src[2] * alpha + dst[2] * inv) // 255,
    )


def set_span(y, x0, x1, rgb):
    """Fill a horizontal run of pixels on row y with a solid colour."""
    if y < 0 or y >= H or x1 <= x0:
        return
    x0 = max(0, x0)
    x1 = min(W, x1)
    if x1 <= x0:
        return
    base = y * W * 3
    px[base + x0 * 3: base + x1 * 3] = bytes(rgb) * (x1 - x0)


def blend_span(y, x0, x1, rgb, alpha):
    """Blend a horizontal run of pixels with a translucent colour."""
    if y < 0 or y >= H or x1 <= x0 or alpha <= 0:
        return
    if alpha >= 255:
        set_span(y, x0, x1, rgb)
        return
    x0 = max(0, x0)
    x1 = min(W, x1)
    if x1 <= x0:
        return
    r, g, b = rgb
    inv = 255 - alpha
    i = y * W * 3 + x0 * 3
    end = y * W * 3 + x1 * 3
    while i < end:
        px[i] = (r * alpha + px[i] * inv) // 255
        px[i + 1] = (g * alpha + px[i + 1] * inv) // 255
        px[i + 2] = (b * alpha + px[i + 2] * inv) // 255
        i += 3


def blend_pixel(x, y, rgb, alpha):
    """Blend a single pixel with a translucent colour."""
    if x < 0 or x >= W or y < 0 or y >= H or alpha <= 0:
        return
    if alpha >= 255:
        i = (y * W + x) * 3
        px[i], px[i + 1], px[i + 2] = rgb
        return
    i = (y * W + x) * 3
    inv = 255 - alpha
    px[i] = (rgb[0] * alpha + px[i] * inv) // 255
    px[i + 1] = (rgb[1] * alpha + px[i + 1] * inv) // 255
    px[i + 2] = (rgb[2] * alpha + px[i + 2] * inv) // 255


def ellipse_spans(cx, cy, rx, ry):
    """Yield (y, x0, x1) scanline spans of a filled ellipse."""
    if rx <= 0 or ry <= 0:
        return
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        t = dy / ry
        hw = int(rx * math.sqrt(max(0.0, 1.0 - t * t)))
        yield y, cx - hw, cx + hw + 1


def fill_ellipse(cx, cy, rx, ry, rgb):
    for y, x0, x1 in ellipse_spans(cx, cy, rx, ry):
        set_span(y, x0, x1, rgb)


def blend_ellipse(cx, cy, rx, ry, rgb, alpha, row_base):
    """Translucent ellipse whose backdrop colour depends only on the row
    (row_base(y) -> rgb): blend per row, then fill solid spans."""
    for y, x0, x1 in ellipse_spans(cx, cy, rx, ry):
        set_span(y, x0, x1, blend3(rgb, row_base(y), alpha))


def ring_ellipse(cx, cy, rx, ry, thick, rgb):
    """Ellipse outline: the ring between the outer ellipse and a smaller
    inner ellipse."""
    ry2 = ry - thick
    rx2 = rx - thick
    if ry2 <= 0 or rx2 <= 0:
        fill_ellipse(cx, cy, rx, ry, rgb)
        return
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        t = dy / ry
        hw = int(rx * math.sqrt(max(0.0, 1.0 - t * t)))
        if abs(dy) <= ry2:
            t2 = dy / ry2
            hw2 = int(rx2 * math.sqrt(max(0.0, 1.0 - t2 * t2)))
        else:
            hw2 = 0
        set_span(y, cx - hw, cx - hw2, rgb)
        set_span(y, cx + hw2 + 1, cx + hw + 1, rgb)


def fill_polygon(pts, rgb):
    """Scanline fill of a simple polygon given as [(x, y), ...]."""
    ys = [p[1] for p in pts]
    y0 = max(0, min(ys))
    y1 = min(H - 1, max(ys))
    n = len(pts)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x1, yy1 = pts[i]
            x2, yy2 = pts[(i + 1) % n]
            if yy1 == yy2:
                continue
            if (yy1 <= y < yy2) or (yy2 <= y < yy1):
                xs.append(x1 + (y - yy1) * (x2 - x1) / (yy2 - yy1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            set_span(y, int(round(xs[k])), int(round(xs[k + 1])), rgb)


def fill_round_rect(x0, y0, x1, y1, r, rgb):
    """Filled rectangle with rounded corners."""
    for y in range(y0, y1 + 1):
        if y < y0 + r:
            dy = (y0 + r) - y
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            xa, xb = x0 + r - dx, x1 - r + dx
        elif y > y1 - r:
            dy = y - (y1 - r)
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            xa, xb = x0 + r - dx, x1 - r + dx
        else:
            xa, xb = x0, x1
        set_span(y, xa, xb, rgb)


def arc_dots(cx, cy, rx, ry, start_deg, end_deg, r, rgb):
    """An arc drawn as a chain of small filled circles."""
    span = end_deg - start_deg
    n = max(2, int(span / 2))  # ~2 degrees between dots: continuous arcs
    for k in range(n + 1):
        a = math.radians(start_deg + span * k / n)
        fill_ellipse(int(cx + rx * math.cos(a)),
                     int(cy + ry * math.sin(a)), r, r, rgb)


def ribbon_geometry(y):
    """Centre x, half-width and fall fraction of the honey ribbon at row y."""
    y0, y1 = 350, 665
    f = (y - y0) / (y1 - y0)
    sway = 23 * math.sin(f * math.pi * 1.6) + 9 * math.sin(f * 9.0)
    half = 48 - 13 * f + 55 * (f ** 7)
    return 565 + sway, half, f


def _chunk(typ, data):
    return (struct.pack(">I", len(data)) + typ + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))


def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter type 0 (none) for every scanline
        raw += px[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + _chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def main():
    # ---- background: vertical slate gradient -----------------------------
    for y in range(H):
        px[y * W * 3:(y + 1) * W * 3] = bytes(BG_ROWS[y]) * W

    # Warm halo behind the pool so the honey glows against the slate.
    # Many thin layers keep the falloff smooth (no visible banding).
    for i in range(40, 0, -1):
        t = i / 40
        a = int(110 * (1 - t) * (1 - t))
        if a <= 0:
            continue
        blend_ellipse(512, 590, int(475 * t), int(475 * t), GLOW, a,
                      lambda y: BG_ROWS[y])

    # Soft shadow under the pool.
    blend_ellipse(512, 847, 347, 67, BLACK, 150, lambda y: BG_ROWS[y])

    # ---- honey pool ------------------------------------------------------
    for i in range(96, 0, -1):
        t = i / 96
        if t < 0.55:
            col = lerp3(POOL_MID, POOL_CORE, t / 0.55)
        else:
            col = lerp3(POOL_EDGE, POOL_MID, (t - 0.55) / 0.45)
        fill_ellipse(512, 745, int(392 * t), int(205 * t), col)

    # Broad glossy sheen across the upper pool, laid down BEFORE the
    # swirls so the swirl ridges read over it instead of under a flat lid.
    fill_ellipse(515, 642, 200, 55, blend3((255, 226, 150), POOL_MID, 26))
    fill_ellipse(485, 640, 120, 34, blend3((255, 240, 190), POOL_CORE, 34))

    # Swirl ridges: concentric elliptical arcs, alternating light/dark.
    cx, cy = 512, 745
    for k in range(7):
        rx = 320 - k * 41
        ry = 150 - k * 19
        if rx <= 20 or ry <= 10:
            break
        col = POOL_DEEP if k % 2 == 0 else (255, 205, 92)
        arc_dots(cx, cy, rx, ry, 200 + k * 38, 200 + k * 38 + 235, 5,
                 blend3(col, POOL_MID, 45))
    # Inner bright swirl core.
    for k in range(3):
        arc_dots(cx, cy, 150 - k * 35, 65 - k * 15,
                 40 + k * 50, 250 + k * 50, 5,
                 blend3((255, 214, 110), POOL_CORE, 80))

    # ---- honey ribbon + falling drop -------------------------------------
    for y in range(350, 666):
        x, half, f = ribbon_geometry(y)
        set_span(y, int(x - half), int(x + half),
                 lerp3(HONEY_TOP, HONEY_BOT, f))
    # Bulging drop where the ribbon meets the pool.
    fill_ellipse(585, 675, 75, 55, POOL_MID)
    fill_ellipse(585, 667, 55, 32, POOL_CORE)
    # Small falling droplet halfway down, with a thin tail.
    fill_polygon([(576, 505), (589, 505), (585, 545), (580, 545)],
                 HONEY_BOT)
    fill_ellipse(565, 495, 20, 22, HONEY_TOP)
    fill_ellipse(556, 483, 10, 10, (255, 226, 140))
    # Gloss stripe down the ribbon's lit edge.
    for y in range(350, 666, 2):
        x, half, f = ribbon_geometry(y)
        col = blend3((255, 240, 190), lerp3(HONEY_TOP, HONEY_BOT, f), 200)
        set_span(y, int(x - half + 15), int(x - half + 23), col)
    fill_ellipse(550, 660, 25, 25,
                 blend3((255, 240, 190), POOL_MID, 170))

    # Ripples where the ribbon lands in the pool.
    for (rx, ry, a) in [(75, 26, 120), (130, 44, 90), (190, 63, 60)]:
        ring_ellipse(585, 685, rx, ry, 4,
                     blend3((255, 222, 130), POOL_MID, a))

    # ---- wooden honey dipper ---------------------------------------------
    hx0, hy0, hx1, hy1 = 780, 65, 615, 320
    dx, dy = hx1 - hx0, hy1 - hy0
    length = math.hypot(dx, dy)
    # Unit perpendicular to the handle.
    ux, uy = dy / length, -dx / length

    def handle_poly(centre, half_w, off):
        ox, oy = off * ux, off * uy
        hw_x, hw_y = half_w * ux, half_w * uy
        return [
            (int(centre[0] + ox - hw_x), int(centre[1] + oy - hw_y)),
            (int(centre[0] + ox + hw_x), int(centre[1] + oy + hw_y)),
            (int((hx1, hy1)[0] + ox + hw_x),
             int((hx1, hy1)[1] + oy + hw_y)),
            (int((hx1, hy1)[0] + ox - hw_x),
             int((hx1, hy1)[1] + oy - hw_y)),
        ]

    # Handle: dark edge, wood body, light stripe, grain streaks.
    fill_polygon(handle_poly((hx0, hy0), 46, 0), WOOD_DARK)
    fill_polygon(handle_poly((hx0, hy0), 36, 0), WOOD)
    fill_polygon(handle_poly((hx0, hy0), 6, -22), WOOD_LIGHT)
    for off, a in [(18, 110), (-12, 90), (26, 70)]:
        fill_polygon(handle_poly((hx0, hy0), 3, off),
                     blend3(WOOD_DARK, WOOD, a))

    # Grooved head: stacked rounded discs, honey-coated.
    head_cx, head_top = 590, 300
    for i in range(5):
        y = head_top + i * 26
        wdt = 165 - abs(i - 2) * 13
        fill_round_rect(head_cx - wdt // 2, y, head_cx + wdt // 2, y + 39,
                        19, WOOD if i % 2 == 0 else WOOD_DARK)
        # Dark groove line near the bottom of each disc.
        set_span(y + 36, head_cx - wdt // 2 + 9, head_cx + wdt // 2 - 9,
                 blend3((60, 34, 12), WOOD, 160))
    # Honey coating over the head: amber sheen + drips hanging off it.
    fill_round_rect(head_cx - 75, head_top + 5, head_cx + 75,
                    head_top + 75, 30,
                    blend3((255, 176, 40), WOOD, 105))
    for ddx, dl in [(-55, 48), (-15, 64), (30, 42), (60, 55)]:
        x = head_cx + ddx
        fill_round_rect(x - 8, head_top + 110, x + 8,
                        head_top + 110 + dl, 8, (240, 158, 20))
        fill_ellipse(x, head_top + 110 + dl, 9, 9, (240, 158, 20))
    fill_ellipse(head_cx - 40, head_top + 35, 40, 20,
                 blend3((255, 230, 150), WOOD, 130))

    # ---- pool gloss, droplets, bubbles -----------------------------------
    # (The broad sheen is drawn with the pool, before the swirls.)
    # Small honey droplets resting on the pool.
    for (dx_, dy_, r) in [(350, 780, 21), (760, 760, 17),
                          (710, 830, 13), (410, 840, 11)]:
        fill_ellipse(dx_, dy_, r, r, (255, 186, 60))
        fill_ellipse(dx_ - r // 3, dy_ - r // 3, r // 3, r // 4,
                     (255, 240, 200))
    # Tiny bubbles caught in the honey.
    for (bx, by, br) in [(450, 710, 6), (665, 750, 5), (525, 800, 7),
                         (620, 830, 4), (380, 740, 4)]:
        ring_ellipse(bx, by, br, br, 2,
                     blend3((255, 230, 160), POOL_MID, 150))

    # ---- vignette ---------------------------------------------------------
    for k in range(48):
        inset = k
        a = int(110 * (1 - k / 48) ** 2) + 1
        blend_span(inset, inset, W - inset, BLACK, a)              # top
        blend_span(H - 1 - inset, inset, W - inset, BLACK, a)      # bottom
        for y in range(inset, H - inset):
            blend_pixel(inset, y, BLACK, a)                        # left
            blend_pixel(W - 1 - inset, y, BLACK, a)                # right

    write_png(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
