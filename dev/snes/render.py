"""Draw profile-style parts ([file, tile, dx, dy, pal, flip, hi]) for checking captures. Nothing drawn here is committed."""
from PIL import Image
def tile_px(data, t, bpp):
    n = {3: 24, 4: 32}[bpp]; o = t * n; px = []
    for y in range(8):
        row = []
        for x in range(8):
            v = 0
            planes = [(o + 2 * y, 0), (o + 2 * y + 1, 1), ((o + 16 + y) if bpp == 3 else (o + 16 + 2 * y), 2)] + ([(o + 17 + 2 * y, 3)] if bpp == 4 else [])
            for at, p in planes: v |= ((data[at] >> (7 - x)) & 1) << p
            row.append(v)
        px.append(row)
    return px
def rgb(w): return ((w & 31) * 255 // 31, (w >> 5 & 31) * 255 // 31, (w >> 10 & 31) * 255 // 31)
def draw(parts, files, bpp, cgram, row_base=8, size=None, bg=(90, 140, 200)):
    xs = [p[2] for p in parts] or [0]; ys = [p[3] for p in parts] or [0]
    x0, y0 = min(xs), min(ys); w, h = size or (max(xs) - x0 + 8, max(ys) - y0 + 8)
    im = Image.new("RGB", (max(w, 8), max(h, 8)), bg); px = im.load()
    for f, t, dx, dy, pal, flip, hi in parts:
        tp = tile_px(files[f][0], t, bpp[f])
        for y in range(8):
            for x in range(8):
                c = tp[7 - y if flip & 2 else y][7 - x if flip & 1 else x]
                if not c: continue
                if bpp[f] == 3 and hi: c += 8
                i = (row_base + pal) * 16 + c; w16 = cgram[2 * i] | cgram[2 * i + 1] << 8
                X, Y = dx - x0 + x, dy - y0 + y
                if 0 <= X < im.width and 0 <= Y < im.height: px[X, Y] = rgb(w16)
    return im
def sheet(images, cols=16, scale=2):
    W = max(i.width for i in images) + 2; H = max(i.height for i in images) + 2
    out = Image.new("RGB", (W * cols, H * ((len(images) + cols - 1) // cols)), (30, 30, 30))
    for k, im in enumerate(images): out.paste(im, ((k % cols) * W, (k // cols) * H))
    return out.resize((out.width * scale, out.height * scale), Image.NEAREST)
