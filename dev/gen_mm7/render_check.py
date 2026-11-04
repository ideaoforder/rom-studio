"""Contact sheet of captured frames (for checking only; nothing drawn is committed)."""
import json, sys
from PIL import Image
from mm7 import ROM, SETS
def tile_px(src, t):
    kind, n = src.split(":"); n = int(n, 16)
    d = SETS[n][2] if kind == "set" else ROM[n << 16:(n << 16) + 0x10000]
    o = 32 * t; return [[sum(((d[o + (16 if p > 1 else 0) + 2 * y + (p & 1)] >> (7 - x)) & 1) << p for p in range(4)) for x in range(8)] for y in range(8)]
def draw(parts, cg, size=None):
    xs = [p[2] for p in parts]; ys = [p[3] for p in parts]; x0, y0 = min(xs), min(ys)
    W, H = size or (max(xs) - x0 + 8, max(ys) - y0 + 8)
    im = Image.new("RGB", (W, H), (60, 60, 80)); px = im.load()
    for src, t, dx, dy, pal, flip in reversed(parts):
        tp = tile_px(src, t)
        for y in range(8):
            for x in range(8):
                c = tp[7 - y if flip & 2 else y][7 - x if flip & 1 else x]
                if not c: continue
                i = (8 + pal) * 16 + c; w16 = cg[2 * i] | cg[2 * i + 1] << 8
                X, Y = dx - x0 + x, dy - y0 + y
                if 0 <= X < W and 0 <= Y < H: px[X, Y] = ((w16 & 31) * 8, (w16 >> 5 & 31) * 8, (w16 >> 10 & 31) * 8)
    return im
def sheet(images, cols=16, scale=2):
    W = max(i.width for i in images) + 2; H = max(i.height for i in images) + 2
    out = Image.new("RGB", (W * cols, H * ((len(images) + cols - 1) // cols)), (20, 20, 20))
    for k, im in enumerate(images): out.paste(im, ((k % cols) * W, (k // cols) * H))
    return out.resize((out.width * scale, out.height * scale), Image.NEAREST)
