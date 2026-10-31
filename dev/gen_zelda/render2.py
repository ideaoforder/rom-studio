import sys
from PIL import Image, ImageDraw
from render import draw_pair, spr_pals
from gfx import ppu_map
from anims import frames, N_ANIMS, mirrored_guess
area, out = sys.argv[1], sys.argv[2]; m = ppu_map(area); pals = spr_pals(area)
rows = [(a, frames(a)) for a in range(N_ANIMS)]
cols = 12; per = 52
im = Image.new("RGB", (cols * (60 + 8 * per), ((len(rows) + cols - 1) // cols) * 0 + 1), (0, 0, 0))
# simple grid: each anim one cell row-wrapped
cellw = 60 + 8 * per; rowsN = (len(rows) + 2) // 3
im = Image.new("RGB", (3 * cellw, rowsN * per)); d = ImageDraw.Draw(im)
for i, (a, fr) in enumerate(rows):
    X = (i // rowsN) * cellw; Y = (i % rowsN) * per
    d.text((X + 2, Y + 18), f"{a:02X}", fill=(255, 255, 0))
    for k, (t, at, _) in enumerate(fr[:8]):
        im.paste(draw_pair(m, pals, t, at, mirrored_guess(t)), (X + 60 + k * per, Y))
im.save(out)
