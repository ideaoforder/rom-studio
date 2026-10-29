"""Walk Simon through a stage (kept alive) and log which sprite codes the game draws, with their palette override."""
from emu import *
import json, sys
def explore(stage, frames=3000, pattern=None):
    nes, f = warp(stage); seen = {}; shots = {}
    for t in range(frames):
        k = C.NES_INPUT_RIGHT
        if t % 40 < 3: k |= C.NES_INPUT_B
        if t % 120 == 60: k |= C.NES_INPUT_A
        if pattern: k = pattern(t)
        nes.controller = k; fr = nes.step(1)
        nes[0x45] = 0x40
        for x in range(1, 0x1C):
            if nes[0x300 + x]: continue
            c = nes[0x31C + x]
            if not c: continue
            key = (c, nes[0x338 + x])
            if key not in seen:
                seen[key] = (t, nes[0x38C + x], nes[0x354 + x], x)
                shots[key] = np.asarray(fr).copy()
    return seen, shots, nes
if __name__ == "__main__":
    from PIL import Image
    st = int(sys.argv[1]); S = sys.argv[2]
    seen, shots, nes = explore(st, int(sys.argv[3]) if len(sys.argv) > 3 else 3000)
    print("stage", st, "now", nes[0x28], "crashed", nes.has_crashed)
    for (c, o), (t, x, y, slot) in sorted(seen.items()):
        print(f"  {c:02X} ovr {o:02X} t{t} x{x} y{y} slot{slot}")
        im = shots[(c, o)]; x0 = max(0, x - 40); y0 = max(0, y - 56)
        Image.fromarray(im[y0:y0 + 80, x0:x0 + 80]).resize((160, 160), Image.NEAREST).save(f"{S}/obj_{st}_{c:02X}_{o:02X}.png")
