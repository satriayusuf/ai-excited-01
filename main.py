#!/usr/bin/env python3
"""NEON PHOENIX RISING -- a procedural celebration for ai-excited-01.

A phoenix of flame and neon bursts upward through a midnight festival
sky: layered feather wings in a white-gold-to-magenta flame ramp, long
flowing tail ribbons, fireworks, ember sparks and a starfield, all
rendered from pure math with the Python standard library only.

The picture is fully deterministic: integer-hash noise and a fixed-seed
PRNG only, no wall clock, no network. Running it twice writes exactly
the same bytes. Output: <MAKEFUN_OUTPUT_DIR or /output>/entry.png
"""

import math
import os
import random
import struct
import zlib
from array import array

W = 768
H = 768
CX = W * 0.5
CY = H * 0.5

# ---------------------------------------------------------------------------
# Deterministic noise: integer lattice hash -> smooth value noise.
# ---------------------------------------------------------------------------

def _hash2(ix, iy):
    """Splitmix-style integer hash of a lattice point -> float in [0, 1)."""
    n = (ix * 0x27D4EB2D) ^ (iy * 0x165667B1) ^ 0x9E3779B9
    n &= 0xFFFFFFFF
    n = (n ^ (n >> 15)) * 0x85EBCA6B & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 0xC2B2AE35 & 0xFFFFFFFF
    n ^= n >> 16
    return n / 4294967296.0


def value_noise(x, y):
    """Bilinear value noise with smoothstep interpolation."""
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy
    sx = fx * fx * (3.0 - 2.0 * fx)
    sy = fy * fy * (3.0 - 2.0 * fy)
    a = _hash2(ix, iy)
    b = _hash2(ix + 1, iy)
    c = _hash2(ix, iy + 1)
    d = _hash2(ix + 1, iy + 1)
    return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy


def fbm(x, y, octaves=4):
    """Fractal Brownian motion in roughly [0, 1]."""
    total = 0.0
    amp = 0.5
    freq = 1.0
    norm = 0.0
    for _ in range(octaves):
        total += amp * value_noise(x * freq, y * freq)
        norm += amp
        amp *= 0.5
        freq *= 2.03
    return total / norm


# ---------------------------------------------------------------------------
# Colour: the flame ramp, white-hot core to deep violet edge.
# ---------------------------------------------------------------------------

_RAMP_STOPS = (
    (0.00, (0.13, 0.01, 0.38)),   # deep violet
    (0.22, (0.55, 0.04, 0.62)),   # purple
    (0.42, (0.92, 0.10, 0.55)),   # magenta pink
    (0.60, (1.00, 0.26, 0.10)),   # ember red-orange
    (0.76, (1.00, 0.55, 0.05)),   # orange
    (0.90, (1.00, 0.83, 0.24)),   # gold
    (1.00, (1.00, 0.99, 0.94)),   # white hot
)


def _build_ramp():
    lut = []
    for i in range(1024):
        t = i / 1023.0
        for k in range(len(_RAMP_STOPS) - 1):
            t0, c0 = _RAMP_STOPS[k]
            t1, c1 = _RAMP_STOPS[k + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                lut.append((c0[0] + (c1[0] - c0[0]) * f,
                            c0[1] + (c1[1] - c0[1]) * f,
                            c0[2] + (c1[2] - c0[2]) * f))
                break
    return lut


RAMP = _build_ramp()


def ramp(t):
    if t <= 0.0:
        return RAMP[0]
    if t >= 1.0:
        return RAMP[1023]
    return RAMP[int(t * 1023.0)]


# ---------------------------------------------------------------------------
# Frame buffer: three float channels, additive light accumulation.
# ---------------------------------------------------------------------------

class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.r = array("f", bytes(4 * w * h))
        self.g = array("f", bytes(4 * w * h))
        self.b = array("f", bytes(4 * w * h))

    def add(self, x, y, cr, cg, cb, strength):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = y * self.w + x
            self.r[i] += cr * strength
            self.g[i] += cg * strength
            self.b[i] += cb * strength

    def stamp_disc(self, cx, cy, radius, color, intensity):
        """Soft additive disc with cosine falloff."""
        r = max(1, int(math.ceil(radius)))
        x0 = max(0, int(cx) - r)
        x1 = min(self.w - 1, int(cx) + r)
        y0 = max(0, int(cy) - r)
        y1 = min(self.h - 1, int(cy) + r)
        cr, cg, cb = color
        inv = 1.0 / (radius * radius)
        for y in range(y0, y1 + 1):
            dy = y - cy
            row = y * self.w
            for x in range(x0, x1 + 1):
                dx = x - cx
                d2 = dx * dx + dy * dy
                if d2 < radius * radius:
                    f = 0.5 + 0.5 * math.cos(math.pi * math.sqrt(d2 * inv))
                    s = intensity * f * f
                    i = row + x
                    self.r[i] += cr * s
                    self.g[i] += cg * s
                    self.b[i] += cb * s


# ---------------------------------------------------------------------------
# Background: midnight gradient, nebula blobs, halo -- rendered small,
# upscaled smooth, then stars and fireworks stamped on top.
# ---------------------------------------------------------------------------

def paint_background(cv):
    sw, sh = 192, 192
    small = Canvas(sw, sh)
    blobs = (
        # (x, y, radius, colour, strength) in small-canvas coords
        (96, 118, 95, (0.95, 0.35, 0.10), 0.55),   # phoenix halo, warm
        (96, 108, 55, (1.00, 0.62, 0.16), 0.75),   # halo core
        (30, 40, 55, (0.10, 0.35, 0.75), 0.50),    # teal-blue nebula
        (165, 55, 60, (0.62, 0.10, 0.70), 0.50),   # violet nebula
        (150, 160, 65, (0.85, 0.15, 0.45), 0.38),  # magenta low right
        (35, 165, 60, (0.05, 0.45, 0.55), 0.36),   # teal low left
    )
    for y in range(sh):
        ty = y / (sh - 1)
        # vertical gradient: deep indigo -> royal purple -> warm horizon
        top = (0.015, 0.004, 0.075)
        mid = (0.075, 0.012, 0.235)
        low = (0.235, 0.035, 0.315)
        if ty < 0.62:
            f = ty / 0.62
            base = tuple(top[i] + (mid[i] - top[i]) * f for i in range(3))
        else:
            f = (ty - 0.62) / 0.38
            base = tuple(mid[i] + (low[i] - mid[i]) * f for i in range(3))
        for x in range(sw):
            i = y * sw + x
            small.r[i], small.g[i], small.b[i] = base
    for bx, by, br, col, strength in blobs:
        small.stamp_disc(bx, by, br, col, strength)
    # Bilinear upscale into the main canvas.
    for y in range(cv.h):
        fy = y * (sh - 1) / (cv.h - 1)
        iy = int(fy)
        fy -= iy
        iy2 = min(sh - 1, iy + 1)
        for x in range(cv.w):
            fx = x * (sw - 1) / (cv.w - 1)
            ix = int(fx)
            fx -= ix
            ix2 = min(sw - 1, ix + 1)
            i00 = iy * sw + ix
            i10 = iy * sw + ix2
            i01 = iy2 * sw + ix
            i11 = iy2 * sw + ix2
            w00 = (1 - fx) * (1 - fy)
            w10 = fx * (1 - fy)
            w01 = (1 - fx) * fy
            w11 = fx * fy
            j = y * cv.w + x
            cv.r[j] = (small.r[i00] * w00 + small.r[i10] * w10 +
                       small.r[i01] * w01 + small.r[i11] * w11)
            cv.g[j] = (small.g[i00] * w00 + small.g[i10] * w10 +
                       small.g[i01] * w01 + small.g[i11] * w11)
            cv.b[j] = (small.b[i00] * w00 + small.b[i10] * w10 +
                       small.b[i01] * w01 + small.b[i11] * w11)


def paint_stars(cv, rng):
    for _ in range(650):
        x = rng.uniform(0, cv.w - 1)
        y = rng.uniform(0, cv.h - 1)
        # keep the centre a little clearer so the phoenix owns it
        d = math.hypot(x - CX, y - CY * 0.92)
        if d < 120 and rng.random() < 0.75:
            continue
        bright = rng.uniform(0.25, 1.0) ** 2
        tint = rng.random()
        if tint < 0.62:
            col = (0.85, 0.90, 1.00)
        elif tint < 0.85:
            col = (1.00, 0.88, 0.66)
        else:
            col = (0.66, 0.95, 1.00)
        r = 1.0 if bright < 0.75 else 1.8
        cv.stamp_disc(x, y, r, col, bright * 0.85)
        if bright > 0.93:  # a few heroes get a cross flare
            for k in range(1, 6):
                f = (1.0 - k / 6.0) * bright * 0.5
                cv.add(int(x) + k, int(y), *col, f)
                cv.add(int(x) - k, int(y), *col, f)
                cv.add(int(x), int(y) + k, *col, f)
                cv.add(int(x), int(y) - k, *col, f)


def paint_fireworks(cv, rng):
    bursts = (
        (118, 128, (1.00, 0.78, 0.30), 26, 118),   # gold, top left
        (652, 104, (0.40, 0.95, 1.00), 24, 104),   # cyan, top right
        (628, 262, (1.00, 0.45, 0.85), 22, 88),    # pink, mid right
        (96, 300, (0.65, 0.80, 1.00), 20, 76),     # pale blue, mid left
    )
    for bx, by, col, rays, reach in bursts:
        cv.stamp_disc(bx, by, 7, (1.0, 1.0, 1.0), 0.9)
        cv.stamp_disc(bx, by, 16, col, 0.35)
        for ray in range(rays):
            ang = (ray / rays) * math.tau + rng.uniform(-0.05, 0.05)
            speed = reach * rng.uniform(0.55, 1.0)
            steps = int(speed / 5)
            for s in range(1, steps + 1):
                t = s / steps
                dist = speed * t
                droop = 14.0 * t * t
                x = bx + math.cos(ang) * dist
                y = by + math.sin(ang) * dist + droop
                fade = (1.0 - t) ** 1.6
                cv.stamp_disc(x, y, 1.7, col, 0.75 * fade + 0.05)


# ---------------------------------------------------------------------------
# The phoenix: everything is a "feather" -- a tapered, curved sliver of
# flame stamped along its own spine. Wings are fans of feathers, the tail
# is five long ribbons, the crest is three small feathers.
# ---------------------------------------------------------------------------

def stamp_feather(cv, x, y, length, width, angle, bend,
                  temp_root, temp_tip, seed, intensity=1.0):
    """Stamp one flame feather.

    The spine starts at (x, y) heading along `angle` (radians, y down),
    curving by `bend` radians over its length. Width profile swells then
    tapers to a point. Colour follows the flame ramp from temp_root to
    temp_tip with fbm flicker; a bright core line runs down the middle.
    """
    steps = max(8, int(length / 1.5))
    # Walk the spine, collecting points and headings.
    spine = []
    px, py, heading = x, y, angle
    step_len = length / steps
    for s in range(steps + 1):
        spine.append((px, py, heading))
        heading += bend / steps
        px += math.cos(heading) * step_len
        py += math.sin(heading) * step_len
    cw = cv.w
    chh = cv.h
    for s in range(steps):
        u = s / steps
        x0, y0, h0 = spine[s]
        x1, y1, _ = spine[s + 1]
        # half thickness: quick swell, long taper to a point
        prof = math.sin(math.pi * min(1.0, 0.18 + 0.82 * u)) ** 0.65
        half = width * 0.5 * prof * (1.0 - 0.25 * u)
        if half < 0.7:
            continue
        nx = -math.sin(h0)
        ny = math.cos(h0)
        mx = (x0 + x1) * 0.5
        my = (y0 + y1) * 0.5
        temp = temp_root + (temp_tip - temp_root) * u
        # cross-section sampled at sub-pixel steps, splatted 2x2 bilinear
        n_off = max(1, int(half / 0.75))
        for oi in range(-n_off, n_off + 1):
            o = oi * 0.75
            v = o / half  # -1..1 across the feather
            fx = mx + nx * o
            fy = my + ny * o
            edge = max(0.0, 1.0 - abs(v))
            flick = fbm(fx * 0.020 + seed * 13.7, fy * 0.020 - seed * 7.1, 3)
            core = max(0.0, 1.0 - abs(v) * 2.6) ** 2
            # edges burn cooler (redder) than the core -- classic flame
            t = temp - (1.0 - edge) * 0.26 + (flick - 0.5) * 0.30 + core * 0.20
            cr, cg, cb = ramp(t)
            s_add = intensity * (0.50 + 0.50 * edge) * (0.72 + 0.50 * core)
            if s_add <= 0.004:
                continue
            ix = int(fx)
            iy = int(fy)
            wx = fx - ix
            wy = fy - iy
            for dy in (0, 1):
                yy = iy + dy
                if not (0 <= yy < chh):
                    continue
                wyy = (1.0 - wy) if dy == 0 else wy
                row = yy * cw
                for dx in (0, 1):
                    xx = ix + dx
                    if not (0 <= xx < cw):
                        continue
                    wgt = ((1.0 - wx) if dx == 0 else wx) * wyy
                    i = row + xx
                    s2 = s_add * wgt
                    cv.r[i] += cr * s2
                    cv.g[i] += cg * s2
                    cv.b[i] += cb * s2


def paint_wing(cv, sign, root_x, root_y, seed):
    """One wing: three fanned rows of feathers sweeping up and out."""
    # Membrane: three huge faint feathers unify the wing silhouette.
    for k, (ang_deg, ln) in enumerate(((-64, 250), (-44, 242), (-24, 224))):
        a = ang_deg if sign > 0 else 180.0 - ang_deg
        stamp_feather(cv, root_x, root_y + 6, ln, 128, math.radians(a),
                      -0.20 * sign, 0.74, 0.40, seed + 90.0 + k * 3.3,
                      intensity=0.16)
    rows = (
        # (count, len0, len1, wid, ang0_deg, ang1_deg, bend, t_root, t_tip)
        (10, 236, 106, 47, -80, 4, -0.30, 0.88, 0.42),   # primaries
        (10, 168, 104, 43, -92, -8, -0.27, 0.93, 0.52),  # secondaries
        (9, 118, 72, 37, -102, -20, -0.24, 0.97, 0.62),  # coverts
    )
    for ri, (count, l0, l1, wid, a0, a1, bend, tr, tt) in enumerate(rows):
        for k in range(count):
            f = k / (count - 1)
            ang_deg = a0 + (a1 - a0) * f
            if sign < 0:
                ang_deg = 180.0 - ang_deg
            length = l0 + (l1 - l0) * f
            # bases step along the wing's leading edge, out and up
            bx = root_x + sign * (6 + 128 * f) - sign * ri * 6
            by = root_y - 4 - 50 * math.sin(f * math.pi * 0.66) + ri * 21
            ang = math.radians(ang_deg)
            # wide faint underglow first, then the feather itself
            stamp_feather(cv, bx, by, length, wid * 1.7, ang, bend * sign,
                          tr - 0.16, tt - 0.16, seed + ri * 3.1 + k * 0.77,
                          intensity=0.30)
            stamp_feather(cv, bx, by, length, wid, ang, bend * sign,
                          tr, tt, seed + ri * 3.1 + k * 0.77,
                          intensity=0.95)


def paint_tail(cv):
    """Five long ribbons flowing down and out from the body."""
    ribbons = (
        # (end_x, sway, width, t_root, t_tip, seed)
        (140, -38, 30, 0.82, 0.28, 3.0),
        (242, -18, 34, 0.87, 0.36, 5.0),
        (384, 0, 38, 0.91, 0.42, 7.0),
        (526, 18, 34, 0.87, 0.36, 11.0),
        (628, 38, 30, 0.82, 0.28, 13.0),
    )
    sx, sy = CX, 486
    ey = 744
    for end_x, sway, width, tr, tt, seed in ribbons:
        steps = 58
        pts = []
        for s in range(steps + 1):
            u = s / steps
            # quadratic bezier: start -> control (straight down) -> end
            cxp = CX + (end_x - CX) * 0.18 + sway * math.sin(u * math.pi)
            x = (1 - u) ** 2 * sx + 2 * (1 - u) * u * cxp + u * u * end_x
            y = (1 - u) ** 2 * sy + 2 * (1 - u) * u * (sy + 150) + u * u * ey
            pts.append((x, y, u))
        # wide soft body of the ribbon, then a brighter thinner core;
        # both fade in over the first stretch so the roots stay hidden
        # behind the torso instead of converging on one bright point
        for x, y, u in pts:
            w_here = width * (1.0 - 0.70 * u)
            fade = 0.25 + 0.75 * min(1.0, u / 0.18)
            flick = fbm(x * 0.02 + seed * 9.1, y * 0.02, 3)
            t = tr + (tt - tr) * u + (flick - 0.5) * 0.22
            cv.stamp_disc(x, y, w_here * 0.62, ramp(t), 0.34 * fade)
        for x, y, u in pts:
            w_here = width * (1.0 - 0.70 * u)
            fade = 0.25 + 0.75 * min(1.0, u / 0.18)
            flick = fbm(x * 0.03 - seed * 5.7, y * 0.03, 3)
            t = tr + (tt - tr) * u + 0.13 + (flick - 0.5) * 0.2
            cv.stamp_disc(x, y, w_here * 0.30, ramp(min(1.0, t)), 0.42 * fade)


def paint_body(cv):
    # Tail first (behind), then wings, then the bright body on top.
    paint_tail(cv)
    paint_wing(cv, -1, CX - 26, 376, 21.0)
    paint_wing(cv, +1, CX + 26, 376, 47.0)
    # Shoulders blend the torso into the wing roots.
    stamp_feather(cv, CX - 30, 436, 138, 46, math.radians(-128), -0.1,
                  0.92, 0.60, 17.3, intensity=0.85)
    stamp_feather(cv, CX + 30, 436, 138, 46, math.radians(-52), 0.1,
                  0.92, 0.60, 19.8, intensity=0.85)
    # Body: one fat upward feather as the torso, plus a chest glow.
    stamp_feather(cv, CX, 490, 238, 108, math.radians(-90), 0.0,
                  0.97, 0.86, 3.3, intensity=0.88)
    stamp_feather(cv, CX - 20, 474, 190, 52, math.radians(-97), 0.05,
                  0.93, 0.78, 8.9, intensity=0.8)
    stamp_feather(cv, CX + 20, 474, 190, 52, math.radians(-83), -0.05,
                  0.93, 0.78, 12.4, intensity=0.8)
    cv.stamp_disc(CX, 424, 38, ramp(0.95), 0.55)
    cv.stamp_disc(CX, 360, 26, ramp(0.98), 0.5)
    # Neck: a bright column joining the chest to the head.
    stamp_feather(cv, CX + 2, 336, 138, 36, math.radians(-88), 0.02,
                  0.98, 0.93, 23.7, intensity=1.0)
    cv.stamp_disc(CX + 2, 316, 27, ramp(0.96), 0.65)


def paint_head(cv):
    hx, hy = CX + 6, 192
    # Crest: feathers sweeping up and back like a flame plume.
    for k, (ang, ln) in enumerate(((-146, 60), (-120, 78), (-94, 82), (-70, 58))):
        stamp_feather(cv, hx - 5, hy - 16, ln, 16, math.radians(ang),
                      -0.30, 0.93, 0.50, 31.0 + k * 2.2, intensity=0.95)
    # Head: warm golden mass, brightest at the crown.
    cv.stamp_disc(hx, hy, 34, ramp(0.90), 1.0)
    cv.stamp_disc(hx + 4, hy - 9, 20, ramp(0.97), 0.8)
    cv.stamp_disc(hx - 6, hy + 12, 16, ramp(0.80), 0.7)
    # Beak: a wedge of three short fat feathers fanning right, in
    # saturated gold-orange (kept off the white end of the ramp).
    for k, ang in enumerate((2, 14, 27)):
        stamp_feather(cv, hx + 24, hy + 1, 42 - k * 3, 13, math.radians(ang),
                      0.06, 0.90, 0.74, 55.0 + k * 1.7, intensity=1.1)
    # Eye: dark jewel in a gold ring, with a white sparkle.
    ex, ey = hx + 12, hy - 6
    cv.stamp_disc(ex, ey, 8.6, ramp(0.88), 0.55)
    for yy in range(int(ey) - 7, int(ey) + 8):
        for xx in range(int(ex) - 7, int(ex) + 8):
            if 0 <= xx < cv.w and 0 <= yy < cv.h:
                d = math.hypot(xx - ex, yy - ey)
                if d < 5.6:
                    i = yy * cv.w + xx
                    cv.r[i], cv.g[i], cv.b[i] = 0.030, 0.006, 0.06
    cv.stamp_disc(ex + 1.8, ey - 2.0, 1.9, (1.0, 1.0, 1.0), 1.5)
    cv.stamp_disc(ex - 1.4, ey + 2.2, 1.0, (0.75, 0.9, 1.0), 0.9)


def paint_sparks(cv, rng):
    """Embers rising around the phoenix + confetti glints everywhere."""
    for _ in range(850):
        # gaussian-ish cluster around the bird, biased low (rising embers)
        x = CX + rng.gauss(0, 165)
        y = CY + 60 + rng.gauss(0, 185)
        if not (4 <= x < cv.w - 4 and 4 <= y < cv.h - 4):
            continue
        pick = rng.random()
        if pick < 0.55:
            col = ramp(rng.uniform(0.62, 1.0))
        elif pick < 0.8:
            col = (1.0, 0.45, 0.85)
        else:
            col = (0.45, 0.95, 1.0)
        size = rng.uniform(0.9, 2.6)
        cv.stamp_disc(x, y, size, col, rng.uniform(0.35, 1.0))
    for _ in range(120):  # sparse confetti over the whole sky
        x = rng.uniform(4, cv.w - 4)
        y = rng.uniform(4, cv.h - 4)
        col = ramp(rng.uniform(0.3, 1.0))
        cv.stamp_disc(x, y, rng.uniform(0.8, 1.7), col, rng.uniform(0.3, 0.8))


# ---------------------------------------------------------------------------
# Soften: one gentle 3x3 blur over the whole frame -- melts the stamp
# banding into continuous plumage before the bloom pass.
# ---------------------------------------------------------------------------

def soften(cv):
    w, h = cv.w, cv.h
    for chan in (cv.r, cv.g, cv.b):
        src = chan
        dst = array("f", bytes(4 * w * h))
        for y in range(h):
            y0 = y - 1 if y > 0 else 0
            y2 = y + 1 if y < h - 1 else h - 1
            r0 = y0 * w
            r1 = y * w
            r2 = y2 * w
            for x in range(w):
                x0 = x - 1 if x > 0 else 0
                x2 = x + 1 if x < w - 1 else w - 1
                dst[r1 + x] = (
                    src[r0 + x0] + src[r0 + x] * 2 + src[r0 + x2] +
                    src[r1 + x0] * 2 + src[r1 + x] * 4 + src[r1 + x2] * 2 +
                    src[r2 + x0] + src[r2 + x] * 2 + src[r2 + x2]) / 16.0
        chan[:] = dst


# ---------------------------------------------------------------------------
# Bloom: downsample, box-blur twice, add back -- cheap radiant glow.
# ---------------------------------------------------------------------------

def add_bloom(cv, strength=0.55):
    bw, bh = 96, 96
    small = [array("f", bytes(4 * bw * bh)) for _ in range(3)]
    chans = (cv.r, cv.g, cv.b)
    block = cv.w // bw
    for by in range(bh):
        for bx in range(bw):
            acc = [0.0, 0.0, 0.0]
            for yy in range(by * block, (by + 1) * block):
                row = yy * cv.w
                for xx in range(bx * block, (bx + 1) * block):
                    j = row + xx
                    for c in range(3):
                        acc[c] += chans[c][j]
            n = float(block * block)
            i = by * bw + bx
            for c in range(3):
                small[c][i] = acc[c] / n
    for _ in range(2):  # two box-blur passes
        for c in range(3):
            src = small[c]
            dst = array("f", bytes(4 * bw * bh))
            for y in range(bh):
                for x in range(bw):
                    tot = 0.0
                    cnt = 0
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            xx, yy = x + dx, y + dy
                            if 0 <= xx < bw and 0 <= yy < bh:
                                tot += src[yy * bw + xx]
                                cnt += 1
                    dst[y * bw + x] = tot / cnt
            small[c] = dst
    for y in range(cv.h):
        fy = y * (bh - 1) / (cv.h - 1)
        iy = int(fy)
        fy -= iy
        iy2 = min(bh - 1, iy + 1)
        for x in range(cv.w):
            fx = x * (bw - 1) / (cv.w - 1)
            ix = int(fx)
            fx -= ix
            ix2 = min(bw - 1, ix + 1)
            i00 = iy * bw + ix
            i10 = iy * bw + ix2
            i01 = iy2 * bw + ix
            i11 = iy2 * bw + ix2
            w00 = (1 - fx) * (1 - fy)
            w10 = fx * (1 - fy)
            w01 = (1 - fx) * fy
            w11 = fx * fy
            j = y * cv.w + x
            for c in range(3):
                s = small[c]
                glow = (s[i00] * w00 + s[i10] * w10 +
                        s[i01] * w01 + s[i11] * w11)
                chans[c][j] += glow * strength


# ---------------------------------------------------------------------------
# Tonemap + PNG encode (8-bit RGB, per-row filter heuristic, zlib).
# ---------------------------------------------------------------------------

def tonemap(cv):
    out = bytearray(cv.w * cv.h * 3)
    for j in range(cv.w * cv.h):
        for c, chan in enumerate((cv.r, cv.g, cv.b)):
            v = chan[j]
            v = v / (1.0 + v)              # soft filmic shoulder
            v = v ** 0.82                  # gentle lift
            out[j * 3 + c] = min(255, int(v * 255.0 + 0.5))
    return out


def encode_png(w, h, rgb):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = bytearray()
    stride = w * 3
    prev = bytearray(stride)
    for y in range(h):
        row = rgb[y * stride:(y + 1) * stride]
        # choose between filter 0 (none), 1 (sub), 2 (up) by residual energy
        best_filter = 0
        best_data = bytes(row)
        best_score = sum(abs(b - 256 if b > 127 else b) for b in row)
        sub = bytearray(stride)
        for i in range(stride):
            left = row[i - 3] if i >= 3 else 0
            sub[i] = (row[i] - left) & 0xFF
        score = sum(abs(b - 256 if b > 127 else b) for b in sub)
        if score < best_score:
            best_filter, best_data, best_score = 1, bytes(sub), score
        up = bytearray(stride)
        for i in range(stride):
            up[i] = (row[i] - prev[i]) & 0xFF
        score = sum(abs(b - 256 if b > 127 else b) for b in up)
        if score < best_score:
            best_filter, best_data = 2, bytes(up)
        raw.append(best_filter)
        raw.extend(best_data)
        prev = bytearray(row)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
            chunk(b"IEND", b""))


# ---------------------------------------------------------------------------

def render():
    cv = Canvas(W, H)
    rng = random.Random(20261116)
    paint_background(cv)
    paint_stars(cv, rng)
    paint_fireworks(cv, rng)
    paint_body(cv)
    paint_head(cv)
    paint_sparks(cv, rng)
    soften(cv)
    add_bloom(cv, 0.55)
    return encode_png(W, H, tonemap(cv))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = render()
    with open(os.path.join(out_dir, "entry.png"), "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
