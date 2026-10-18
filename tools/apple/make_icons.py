#!/usr/bin/env python3
"""Generate the app's asset catalog icons (app/Resources/Assets.xcassets).

The icon is an original, neutral mark for this port: a pale feather (a wing,
after the game's name) on a dark night-blue gradient with a soft warm glow.
It is drawn from scratch with plain Python (no Pillow, no external tools) and
contains nothing from the game: no character, logo, or artwork.

Writes the iOS icon (1024 px), the visionOS layered icon, the launch
background colour and their Contents.json files.

usage: make_icons.py [ASSETS_DIR]
"""
import json
import math
import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "app", "Resources", "Assets.xcassets")

# Night sky: deep blue at the top, almost black at the bottom.
SKY_TOP = (11, 16, 34)
SKY_BOTTOM = (4, 5, 10)
GLOW = (255, 196, 128)      # warm light behind the feather
FEATHER = (238, 233, 221)   # pale ivory
FEATHER_EDGE = (206, 196, 178)


# --------------------------------------------------------------------------
# a tiny PNG writer (RGBA, no filtering) - keeps the project dependency-free
# --------------------------------------------------------------------------

def write_png(path, width, height, pixels, with_alpha=True):
    """pixels: bytearray of width*height*4 (RGBA)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: none
        raw.extend(pixels[y * stride:(y + 1) * stride])
    color_type = 6 if with_alpha else 2
    if not with_alpha:
        rgb = bytearray()
        for i in range(0, len(pixels), 4):
            rgb.extend(pixels[i:i + 3])
        raw = bytearray()
        for y in range(height):
            raw.append(0)
            raw.extend(rgb[y * width * 3:(y + 1) * width * 3])

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", header))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


# --------------------------------------------------------------------------
# a small raster canvas
# --------------------------------------------------------------------------

class Canvas:
    def __init__(self, width, height, opacity=0.0):
        self.w = width
        self.h = height
        self.px = bytearray(width * height * 4)
        if opacity > 0:
            for i in range(0, len(self.px), 4):
                self.px[i + 3] = int(opacity * 255)

    def blend(self, x, y, color, alpha):
        if alpha <= 0 or x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        if alpha > 1:
            alpha = 1.0
        i = (y * self.w + x) * 4
        a = alpha
        da = self.px[i + 3] / 255.0
        oa = a + da * (1 - a)
        if oa <= 0:
            return
        for k in range(3):
            sc = color[k]
            dc = self.px[i + k]
            self.px[i + k] = int(round((sc * a + dc * da * (1 - a)) / oa))
        self.px[i + 3] = int(round(oa * 255))

    def to_rgba(self):
        return self.px


def gradient(canvas):
    """Vertical night gradient, filling the whole canvas opaque."""
    w, h, px = canvas.w, canvas.h, canvas.px
    for y in range(h):
        t = y / max(h - 1, 1)
        # ease the gradient so the light stays in the upper half
        e = t ** 1.35
        r = int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * e)
        g = int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * e)
        b = int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * e)
        row = y * w * 4
        for x in range(w):
            i = row + x * 4
            px[i] = r
            px[i + 1] = g
            px[i + 2] = b
            px[i + 3] = 255


def glow(canvas, strength):
    """A soft warm light behind the feather."""
    w, h = canvas.w, canvas.h
    cx, cy = 0.58 * w, 0.38 * h
    radius = 0.55 * min(w, h)
    for y in range(h):
        dy = (y - cy) / radius
        for x in range(w):
            dx = (x - cx) / radius
            d = math.sqrt(dx * dx + dy * dy)
            if d >= 1.8:
                continue
            a = strength * math.exp(-(d * d) * 2.6)
            if a > 0.004:
                canvas.blend(x, y, GLOW, a)


# --------------------------------------------------------------------------
# the feather
# --------------------------------------------------------------------------

def bezier(t):
    # bottom-left quill to the upper-right tip, gently bowed
    x = (1 - t) ** 2 * 0.24 + 2 * (1 - t) * t * 0.42 + t * t * 0.74
    y = (1 - t) ** 2 * 0.84 + 2 * (1 - t) * t * 0.50 + t * t * 0.17
    return x, y


def bezier_tangent(t):
    dx = 2 * (1 - t) * (0.42 - 0.24) + 2 * t * (0.74 - 0.42)
    dy = 2 * (1 - t) * (0.50 - 0.84) + 2 * t * (0.17 - 0.50)
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def fill_polygon(canvas, points, color, alpha=1.0, samples=4):
    """Scanline-fill a polygon given in normalised coordinates, with coverage
    antialiasing (4 vertical samples per row, fractional row ends)."""
    w, h = canvas.w, canvas.h
    pts = [(x * w, y * h) for x, y in points]
    n = len(pts)
    if n < 3:
        return
    ys = [p[1] for p in pts]
    ymin = max(int(math.floor(min(ys))), 0)
    ymax = min(int(math.ceil(max(ys))), h - 1)
    for y in range(ymin, ymax + 1):
        coverage = {}
        for s in range(samples):
            sy = y + (s + 0.5) / samples
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if y0 == y1:
                    continue
                if (y0 <= sy < y1) or (y1 <= sy < y0):
                    xs.append(x0 + (sy - y0) / (y1 - y0) * (x1 - x0))
            if len(xs) < 2:
                continue
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa, xb = xs[k], xs[k + 1]
                if xb <= 0 or xa >= w:
                    continue
                xa = max(xa, 0.0)
                xb = min(xb, float(w))
                if xb <= xa:
                    continue
                ia, ib = int(xa), int(xb)
                share = 1.0 / samples
                if ia == ib:
                    coverage[ia] = coverage.get(ia, 0.0) + (xb - xa) * share
                else:
                    coverage[ia] = coverage.get(ia, 0.0) + (ia + 1 - xa) * share
                    for px in range(ia + 1, min(ib, w)):
                        coverage[px] = coverage.get(px, 0.0) + share
                    if ib < w:
                        coverage[ib] = coverage.get(ib, 0.0) + (xb - ib) * share
        for px, cov in coverage.items():
            if cov > 0:
                canvas.blend(px, y, color, alpha * min(cov, 1.0))


def stroke(canvas, p0, p1, width, color, alpha=1.0, soft=1.0):
    """A round-capped line with one-pixel-ish antialiasing."""
    w, h = canvas.w, canvas.h
    x0, y0 = p0[0] * w, p0[1] * h
    x1, y1 = p1[0] * w, p1[1] * h
    r = max(width * min(w, h) * 0.5, 0.5)
    reach = r + soft
    minx = max(int(math.floor(min(x0, x1) - reach)), 0)
    maxx = min(int(math.ceil(max(x0, x1) + reach)), w - 1)
    miny = max(int(math.floor(min(y0, y1) - reach)), 0)
    maxy = min(int(math.ceil(max(y0, y1) + reach)), h - 1)
    vx, vy = x1 - x0, y1 - y0
    length2 = vx * vx + vy * vy
    for y in range(miny, maxy + 1):
        py = y + 0.5
        for x in range(minx, maxx + 1):
            px = x + 0.5
            if length2 <= 0:
                t = 0.0
            else:
                t = ((px - x0) * vx + (py - y0) * vy) / length2
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
            dx = px - (x0 + t * vx)
            dy = py - (y0 + t * vy)
            d = math.sqrt(dx * dx + dy * dy)
            cov = (r - d) / soft + 0.5
            if cov > 1:
                cov = 1
            if cov > 0:
                canvas.blend(x, y, color, alpha * cov)


def vane(t):
    px, py = bezier(t)
    tx, ty = bezier_tangent(t)
    nx, ny = -ty, tx
    width = 0.205 * (math.sin(math.pi * (0.09 + 0.86 * t)) ** 0.7) * (1.0 - 0.55 * t ** 2.2)
    return (px, py), (nx, ny), width


def feather(canvas):
    w, h = canvas.w, canvas.h
    # the vane: a lens-shaped polygon around the quill curve
    left, right = [], []
    steps = 56
    for i in range(steps + 1):
        t = 0.055 + 0.945 * i / steps
        (px, py), (nx, ny), width = vane(t)
        if i == steps:
            left.append((px, py))
            right.append((px, py))
        else:
            left.append((px + nx * width, py + ny * width))
            right.append((px - nx * width, py - ny * width))
    fill_polygon(canvas, left + right[::-1], FEATHER, alpha=1.0)

    # barb lines inside the vane, for texture
    count = 21
    for i in range(count):
        t = 0.12 + 0.80 * i / (count - 1)
        (px, py), (nx, ny), width = vane(t)
        for side in (1.0, -1.0):
            inner = (px + nx * side * width * 0.18, py + ny * side * width * 0.18)
            outer = (px + nx * side * width * 0.95, py + ny * side * width * 0.95)
            stroke(canvas, inner, outer, 0.0016, FEATHER_EDGE, alpha=0.55)

    # the quill: bare below the vane, then the shaft through the vane to the tip
    stroke(canvas, (0.175, 0.94), bezier(0.055), 0.0075, FEATHER_EDGE, alpha=0.95)
    for i in range(30):
        t0, t1 = i / 30, (i + 1) / 30
        stroke(canvas, bezier(t0), bezier(t1), 0.0050, FEATHER_EDGE, alpha=0.80)


def composite(*canvases):
    """Source-over several canvases of the same size into a new one."""
    base = Canvas(canvases[0].w, canvases[0].h)
    base.px[:] = canvases[0].px
    for layer in canvases[1:]:
        for i in range(0, len(base.px), 4):
            a = layer.px[i + 3] / 255.0
            if a <= 0:
                continue
            base.blend((i // 4) % base.w, (i // 4) // base.w,
                       (layer.px[i], layer.px[i + 1], layer.px[i + 2]), a)
    return base


def flat_icon(width, height):
    back = Canvas(width, height)
    gradient(back)
    middle = Canvas(width, height)
    glow(middle, 0.30)
    front = Canvas(width, height)
    feather(front)
    return composite(back, middle, front)


def vision_layers(size):
    back = Canvas(size, size)
    gradient(back)
    middle = Canvas(size, size)
    glow(middle, 0.55)
    front = Canvas(size, size)
    feather(front)
    return back, middle, front


# --------------------------------------------------------------------------
# asset catalog
# --------------------------------------------------------------------------

INFO = {"author": "xcode", "version": 1}


def contents(path, data):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "Contents.json"), "w") as f:
        json.dump(data, f, indent=2)


def ios_icon():
    d = os.path.join(ASSETS, "AppIcon.appiconset")
    icon = flat_icon(1024, 1024)
    write_png(os.path.join(d, "icon-1024.png"), 1024, 1024, icon.to_rgba(), with_alpha=False)
    contents(d, {"images": [{"filename": "icon-1024.png", "idiom": "universal",
                             "platform": "ios", "size": "1024x1024"}], "info": INFO})


def vision_icon():
    stack = os.path.join(ASSETS, "AppIconVision.solidimagestack")
    back, middle, front = vision_layers(1024)
    order = [("Front", front), ("Middle", middle), ("Back", back)]
    contents(stack, {"info": INFO,
                     "layers": [{"filename": f"{n}.solidimagestacklayer"} for n, _ in order]})
    for name, canvas in order:
        layer_dir = os.path.join(stack, f"{name}.solidimagestacklayer")
        contents(layer_dir, {"info": INFO})
        imageset = os.path.join(layer_dir, "Content.imageset")
        file_name = f"{name.lower()}.png"
        write_png(os.path.join(imageset, file_name), 1024, 1024, canvas.to_rgba())
        contents(imageset, {"images": [{"filename": file_name, "idiom": "vision", "scale": "2x"}],
                            "info": INFO})


def launch_color():
    d = os.path.join(ASSETS, "LaunchBackground.colorset")
    contents(d, {"colors": [{"color": {
        "color-space": "srgb",
        "components": {"red": "0.043", "green": "0.063", "blue": "0.133", "alpha": "1.000"}},
        "idiom": "universal"}], "info": INFO})


if __name__ == "__main__":
    contents(ASSETS, {"info": INFO})
    ios_icon()
    vision_icon()
    launch_color()
    print("icons written to", ASSETS)
