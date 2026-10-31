"""Contact sheets of every animation in an area (for picking objects; nothing rendered is committed)."""
import sys, json
from PIL import Image, ImageDraw
from gfx import ROM, ppu_map, palettes, tile_px
from anims import frames, N_ANIMS
NES = [(84,84,84),(0,30,116),(8,16,144),(48,0,136),(68,0,100),(92,0,48),(84,4,0),(60,24,0),(32,42,0),(8,58,0),(0,64,0),(0,60,0),(0,50,60),(0,0,0),(0,0,0),(0,0,0),
(152,150,152),(8,76,196),(48,50,236),(92,30,228),(136,20,176),(160,20,100),(152,34,32),(120,60,0),(84,90,0),(40,114,0),(8,124,0),(0,118,40),(0,102,120),(0,0,0),(0,0,0),(0,0,0),
(236,238,236),(76,154,236),(120,124,236),(176,98,236),(228,84,236),(236,88,180),(236,106,100),(212,136,32),(160,170,0),(116,196,0),(76,208,32),(56,204,108),(56,180,204),(60,60,60),(0,0,0),(0,0,0),
(236,238,236),(168,204,236),(188,188,236),(212,178,236),(236,174,236),(236,174,212),(236,180,176),(228,196,144),(204,210,120),(180,222,120),(168,226,144),(152,226,180),(160,214,228),(160,162,160),(0,0,0),(0,0,0)]
def spr_pals(area):
    o = palettes(area) + 16; return [ROM[o + 4 * k:o + 4 * k + 4] for k in range(4)]
def draw_pair(m, pals, t, attr, mirrored, sc=3):
    img = Image.new("RGB", (16 * sc, 16 * sc), (40, 40, 48)); pal = pals[attr & 3]
    parts = [(t, False), (t, True)] if mirrored else [(t, False), (t + 2, False)]
    for side, (tt, fl) in enumerate(parts):
        for half in (0, 1):
            q = (tt & 0xFE) + half
            if q not in m: continue
            px = tile_px(m[q])
            for y in range(8):
                for x in range(8):
                    c = px[y][7 - x if fl else x]
                    if attr & 0x80: c = tile_px(m[(tt & 0xFE) + 1 - half])[7 - y][7 - x if fl else x]
                    if c: 
                        for dy in range(sc):
                            for dx in range(sc): img.putpixel(((side * 8 + x) * sc + dx, (half * 8 + y) * sc + dy), NES[pal[c]])
    return img
if __name__ == "__main__":
    area, out = sys.argv[1], sys.argv[2]; m = ppu_map(area); pals = spr_pals(area)
    rows = [(a, frames(a)) for a in range(N_ANIMS)]
    W = 2 + max(len(f) for _, f in rows) * 2; im = Image.new("RGB", (60 + W * 52, len(rows) * 52)); d = ImageDraw.Draw(im)
    for i, (a, fr) in enumerate(rows):
        d.text((2, i * 52 + 18), f"{a:02X} t{a-1:02X}", fill=(255, 255, 0))
        for k, (t, at, _) in enumerate(fr):
            im.paste(draw_pair(m, pals, t, at, False), (60 + k * 104, i * 52)); im.paste(draw_pair(m, pals, t, at, True), (60 + k * 104 + 50, i * 52))
    im.save(out)
