"""Render metasprites with the in-game palettes (for picking object codes; nothing rendered is committed)."""
import numpy as np
from PIL import Image, ImageDraw
from gfx import ROM, fixed, ppu_map, tile_px, stage_set
from sprites import sprite
NES = [(84,84,84),(0,30,116),(8,16,144),(48,0,136),(68,0,100),(92,0,48),(84,4,0),(60,24,0),(32,42,0),(8,58,0),(0,64,0),(0,60,0),(0,50,60),(0,0,0),(0,0,0),(0,0,0),
(152,150,152),(8,76,196),(48,50,236),(92,30,228),(136,20,176),(160,20,100),(152,34,32),(120,60,0),(84,90,0),(40,114,0),(8,124,0),(0,118,40),(0,102,120),(0,0,0),(0,0,0),(0,0,0),
(236,238,236),(76,154,236),(120,124,236),(176,98,236),(228,84,236),(236,88,180),(236,106,100),(212,136,32),(160,170,0),(116,196,0),(76,208,32),(56,204,108),(56,180,204),(60,60,60),(0,0,0),(0,0,0),
(236,238,236),(168,204,236),(188,188,236),(212,178,236),(236,174,236),(236,174,212),(236,180,176),(228,196,144),(204,210,120),(180,222,120),(168,226,144),(152,226,180),(160,214,228),(160,162,160),(0,0,0),(0,0,0)]
def string_data(k):
    p = ROM[fixed(0xCCF9 + 2 * k)] | ROM[fixed(0xCCFA + 2 * k)] << 8; return fixed(p) + 2
SPRITE_PAL = string_data(6)
def block_bg(stage): return string_data(ROM[fixed(0xFB9B + stage)])
BLOCK_STAGE = {"B1": 1, "B2": 4, "B3": 7, "B4": 10, "B5": 13, "B6": 16, "B7": 18}
def area_map(a): return ppu_map([3, stage_set(BLOCK_STAGE[a])]) if a != "B1" else ppu_map([3])
def draw(code, m, pals=None, scale=2):
    pals = pals or [ROM[SPRITE_PAL + 4 * k:SPRITE_PAL + 4 * k + 4] for k in range(4)]
    parts = sprite(code) or []
    if not parts: return None
    xs = [dx for dy, t, a, dx in parts]; ys = [dy for dy, t, a, dx in parts]
    x0, y0 = min(xs), min(ys); W = max(xs) - x0 + 8; H = max(ys) - y0 + 16
    img = np.zeros((H, W, 3), np.uint8); img[:] = (40, 40, 48)
    for dy, t, a, dx in reversed(parts):
        top = (t & 0xFE) + (0x100 if t & 1 else 0); h = a & 0x40; v = a & 0x80; pal = pals[a & 3]
        for half, tt in enumerate((top, top + 1) if not v else (top + 1, top)):
            if tt not in m: continue
            px = tile_px(m[tt])
            for y in range(8):
                for x in range(8):
                    c = px[7 - y if v else y][7 - x if h else x]
                    if c: img[dy - y0 + half * 8 + y, dx - x0 + x] = NES[pal[c]]
    return Image.fromarray(img).resize((W * scale, H * scale), Image.NEAREST)
def sheet(codes, m, path, cols=16):
    cells = [(c, draw(c, m)) for c in codes]; cells = [(c, i) for c, i in cells if i]
    cw = max(i.width for _, i in cells) + 4; ch = max(i.height for _, i in cells) + 14
    cw = min(cw, 140); ch = min(ch, 160)
    rows = (len(cells) + cols - 1) // cols; out = Image.new("RGB", (cols * cw, rows * ch), (0, 0, 0)); d = ImageDraw.Draw(out)
    for k, (c, i) in enumerate(cells):
        x, y = (k % cols) * cw, (k // cols) * ch; out.paste(i.crop((0, 0, cw - 4, ch - 14)), (x, y + 12)); d.text((x, y), f"{c:02X}", fill=(255, 255, 0))
    out.save(path)
