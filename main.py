#!/usr/bin/env python3
"""Golden honey — a picture that tastes of one ingredient.

Draws, from scratch in pure code, a wooden honey dipper dripping a thick
glossy ribbon of honey into a swirling pool of honey, on a dark slate
background. One ingredient (honey) dominates the frame.

Runs with no network and no input files. Writes /output/entry.png
(1024x1024). Fully deterministic: every value is computed from fixed
constants, so repeated runs produce byte-identical output.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFilter

# Supersample factor: draw at 2048 and downscale for smooth edges.
S = 2
W = H = 1024 * S
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


def lerp(a, b, t):
    """Linear interpolation between two RGB tuples."""
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def rgba(rgb, alpha):
    return (rgb[0], rgb[1], rgb[2], alpha)


def vertical_gradient(size, top, bottom):
    """RGB image with a smooth top-to-bottom gradient."""
    w, h = size
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        px[0, y] = lerp(top, bottom, y / max(1, h - 1))
    return img.resize((w, h))


def radial_glow(size, centre, radius, colour, peak_alpha):
    """RGBA layer: a soft radial glow fading to transparent."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    steps = 48
    for i in range(steps, 0, -1):
        t = i / steps
        r = radius * t
        a = int(peak_alpha * (1 - t) * (1 - t))
        d.ellipse(
            [centre[0] - r, centre[1] - r, centre[0] + r, centre[1] + r],
            fill=rgba(colour, a),
        )
    return layer.filter(ImageFilter.GaussianBlur(18 * S))


def ellipse_gradient(draw, box, steps, outer, mid, inner):
    """Fill an ellipse with a radial gradient (outer -> mid -> inner)."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for i in range(steps, 0, -1):
        t = i / steps
        if t < 0.55:
            col = lerp(mid, inner, t / 0.55)
        else:
            col = lerp(outer, mid, (t - 0.55) / 0.45)
        rx = (x1 - x0) / 2 * t
        ry = (y1 - y0) / 2 * t
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=col)


def main():
    img = vertical_gradient((W, H), SLATE_TOP, SLATE_BOT)
    img = img.convert("RGBA")

    # Warm halo behind the pool so the honey glows against the slate.
    img.alpha_composite(
        radial_glow((W, H), (1024 * S // 2, 1180 * S // 2), 950 * S // 2,
                    GLOW, 110)
    )

    # Soft shadow under the pool.
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([330, 1560, 1718, 1830], fill=(0, 0, 0, 150))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(30 * S)))

    # ---- honey pool ------------------------------------------------------
    pool_box = (240, 1080, 1808, 1900)
    pool = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pool)
    ellipse_gradient(pd, pool_box, 90, POOL_EDGE, POOL_MID, POOL_CORE)

    # Swirl ridges: concentric elliptical arcs, alternating light/dark.
    cx, cy = 1024, 1490
    for k in range(7):
        rx = 640 - k * 82
        ry = 300 - k * 38
        if rx <= 40 or ry <= 20:
            break
        col = POOL_DEEP if k % 2 == 0 else (255, 205, 92)
        a = 45 if k % 2 == 0 else 45
        start = 200 + k * 38
        pd.arc([cx - rx, cy - ry, cx + rx, cy + ry],
               start=start, end=start + 235, fill=rgba(col, a), width=7 * S)
    # Inner bright swirl core.
    for k in range(3):
        rx, ry = 300 - k * 70, 130 - k * 30
        pd.arc([cx - rx, cy - ry, cx + rx, cy + ry],
               start=40 + k * 50, end=250 + k * 50,
               fill=rgba((255, 214, 110), 80), width=8 * S)
    img.alpha_composite(pool.filter(ImageFilter.GaussianBlur(2 * S)))

    # ---- honey ribbon + falling drop -------------------------------------
    # Ribbon: a wavy vertical band from the dipper head down to the pool.
    ribbon = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ribbon)
    y0, y1 = 700, 1330
    left, right = [], []
    for y in range(y0, y1 + 1, 6):
        f = (y - y0) / (y1 - y0)
        sway = 46 * math.sin(f * math.pi * 1.6) + 18 * math.sin(f * 9.0)
        # Ribbon narrows as it falls, then bulges into a drop at the pool.
        half = 96 - 26 * f + 110 * (f ** 7)
        x = 1130 + sway
        left.append((x - half, y))
        right.append((x + half, y))
    rd.polygon(left + right[::-1], fill=rgba((238, 158, 24), 255),
               outline=rgba(HONEY_BOT, 255))
    # Gradient bands over the solid ribbon, top light to bottom deep.
    for y in range(y0, y1 + 1, 6):
        f = (y - y0) / (y1 - y0)
        sway = 46 * math.sin(f * math.pi * 1.6) + 18 * math.sin(f * 9.0)
        half = 96 - 26 * f + 110 * (f ** 7)
        x = 1130 + sway
        col = lerp(HONEY_TOP, HONEY_BOT, f)
        rd.line([(x - half, y), (x + half, y)], fill=rgba(col, 255),
                width=7)
    # Bulging drop where the ribbon meets the pool.
    rd.ellipse([1020, 1240, 1320, 1460], fill=rgba(POOL_MID, 255))
    rd.ellipse([1060, 1270, 1280, 1400], fill=rgba(POOL_CORE, 255))
    # Small falling droplet halfway down, with a thin tail.
    rd.polygon([(1152, 1010), (1178, 1010), (1170, 1090), (1160, 1090)],
               fill=rgba(HONEY_BOT, 255))
    rd.ellipse([1124, 950, 1206, 1040], fill=rgba(HONEY_TOP, 255))
    rd.ellipse([1136, 962, 1176, 1004], fill=rgba((255, 226, 140), 255))
    # Gloss stripe down the ribbon's lit edge.
    gloss = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gloss)
    pts = []
    for y in range(y0, y1, 8):
        f = (y - y0) / (y1 - y0)
        sway = 46 * math.sin(f * math.pi * 1.6) + 18 * math.sin(f * 9.0)
        half = 96 - 26 * f + 110 * (f ** 7)
        pts.append((1130 + sway - half + 30, y))
    gd.line(pts, fill=rgba((255, 240, 190), 200), width=16 * S)
    gd.ellipse([1050, 1270, 1150, 1370], fill=rgba((255, 240, 190), 170))
    ribbon.alpha_composite(gloss.filter(ImageFilter.GaussianBlur(4 * S)))
    img.alpha_composite(ribbon)

    # Ripples where the ribbon lands in the pool.
    rip = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rpd = ImageDraw.Draw(rip)
    for k, (rx, ry, a) in enumerate([(150, 52, 120), (260, 88, 90),
                                     (380, 126, 60)]):
        rpd.ellipse([1170 - rx, 1370 - ry, 1170 + rx, 1370 + ry],
                    outline=rgba((255, 222, 130), a), width=7 * S)
    img.alpha_composite(rip.filter(ImageFilter.GaussianBlur(3 * S)))

    # ---- wooden honey dipper ---------------------------------------------
    dip = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dip)
    # Handle: from top-right corner down to the grooved head.
    hx0, hy0, hx1, hy1 = 1560, 130, 1230, 640
    dd.line([(hx0, hy0), (hx1, hy1)], fill=rgba(WOOD_DARK, 255),
            width=92 * S)
    dd.line([(hx0, hy0), (hx1, hy1)], fill=rgba(WOOD, 255), width=72 * S)
    dd.line([(hx0 - 8, hy0 + 4), (hx1 - 8, hy1 + 4)],
            fill=rgba(WOOD_LIGHT, 255), width=12 * S)
    # Wood grain streaks along the handle.
    for off, a in [(-22, 110), (14, 90), (28, 70)]:
        dd.line([(hx0 + off, hy0), (hx1 + off, hy1)],
                fill=rgba(WOOD_DARK, a), width=5 * S)
    # Grooved head: stacked rounded discs, honey-coated.
    head_cx, head_top = 1180, 600
    for i in range(5):
        y = head_top + i * 52
        wdt = 330 - abs(i - 2) * 26
        dd.rounded_rectangle([head_cx - wdt // 2, y, head_cx + wdt // 2,
                              y + 78], radius=38,
                             fill=rgba(WOOD if i % 2 == 0 else WOOD_DARK,
                                       255))
        dd.line([(head_cx - wdt // 2 + 18, y + 74),
                 (head_cx + wdt // 2 - 18, y + 74)],
                fill=rgba((60, 34, 12), 160), width=6 * S)
    # Honey coating over the head: amber sheen + drips hanging off it.
    coat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(coat)
    cd.rounded_rectangle([head_cx - 150, head_top + 10, head_cx + 150,
                          head_top + 150], radius=60,
                         fill=rgba((255, 176, 40), 105))
    for dx, dl in [(-110, 96), (-30, 128), (60, 84), (120, 110)]:
        x = head_cx + dx
        cd.rounded_rectangle([x - 16, head_top + 220, x + 16,
                              head_top + 220 + dl], radius=16,
                             fill=rgba((240, 158, 20), 235))
        cd.ellipse([x - 17, head_top + 210 + dl, x + 17,
                    head_top + 244 + dl], fill=rgba((240, 158, 20), 235))
    cd.ellipse([head_cx - 118, head_top + 30, head_cx - 20, head_top + 110],
               fill=rgba((255, 230, 150), 130))
    dip.alpha_composite(coat.filter(ImageFilter.GaussianBlur(2 * S)))
    img.alpha_composite(dip)

    # ---- pool gloss, droplets, bubbles -----------------------------------
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(top)
    # Broad glossy sheen across the upper pool.
    td.ellipse([560, 1150, 1500, 1420], fill=rgba((255, 226, 150), 46))
    td.ellipse([700, 1200, 1240, 1360], fill=rgba((255, 240, 190), 60))
    # Small honey droplets resting on the pool.
    for (dx, dy, r) in [(700, 1560, 42), (1520, 1520, 34),
                        (1420, 1660, 26), (820, 1680, 22)]:
        td.ellipse([dx - r, dy - r, dx + r, dy + r],
                   fill=rgba((255, 186, 60), 235))
        td.ellipse([dx - r + 8, dy - r + 6, dx - r + r // 2 + 8,
                    dy - r + r // 2 + 6], fill=rgba((255, 240, 200), 220))
    # Tiny bubbles caught in the honey.
    for (bx, by, br) in [(900, 1420, 12), (1330, 1500, 9),
                         (1050, 1600, 14), (1240, 1660, 8),
                         (760, 1480, 7)]:
        td.ellipse([bx - br, by - br, bx + br, by + br],
                   outline=rgba((255, 230, 160), 150), width=3 * S)
    img.alpha_composite(top.filter(ImageFilter.GaussianBlur(2 * S)))

    # ---- vignette ---------------------------------------------------------
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    vd.rectangle([0, 0, W, H], outline=rgba((0, 0, 0), 0))
    for i in range(40, 0, -1):
        t = i / 40
        a = int(120 * (1 - t) * (1 - t))
        vd.rectangle([0, 0, W, H], outline=rgba((0, 0, 0), a),
                     width=26 * S)
    img.alpha_composite(vig.filter(ImageFilter.GaussianBlur(24 * S)))

    # Downscale to the required 1024x1024 and save.
    out = img.convert("RGB").resize((1024, 1024), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT, format="PNG", optimize=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
