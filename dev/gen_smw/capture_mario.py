"""Mario's poses: a scratch copy of the ROM whose player-drawing routine reads the pose from $1B97 (unused RAM)
instead of $13E0, so every pose can be drawn on demand for each power-up and both directions."""
import json, tempfile, os, sys
from smw import ROM, F
from capture import boot_ow, warp, oam, Prov
DRAW = (F(0x00E2BD), F(0x00E4B9))          # the player graphics routine
def scratch_rom():
    b = bytearray(ROM); n = 0
    for i in range(*DRAW):
        if b[i] in (0xAD, 0xAE) and b[i + 1:i + 3] == b"\xE0\x13": b[i + 1:i + 3] = b"\x97\x1B"; n += 1
    p = os.path.join(tempfile.mkdtemp(), "pose.sfc"); open(p, "wb").write(b); return p, n
def capture():
    path, n = scratch_rom(); s = boot_ow(path); warp(s, 0x15); s.run(30); prov = Prov(); out = {}
    base = s.save()
    for power in range(4):
        for pose in range(0x46):
            s.load(base); s.poke(0x19, power); s.poke(0x76, 1); s.poke(0x1B97, pose); s.poke(0x13E0, pose)
            s.run(2); r = s.ram; mx, my = r[0x7E] | r[0x7F] << 8, r[0x80] | r[0x81] << 8
            ents = [e for e in oam(r)[64:96] if e[1] < 0xE0 and abs(e[0] - mx) < 48 and abs(e[1] - my) < 48]
            s.run(1); v = s.vram
            parts, miss = prov.parts(v, ents, mx, my)
            out[f"{power}:{pose:02X}"] = {"parts": parts, "miss": miss, "oam": ents}
    return out, n
if __name__ == "__main__":
    out, n = capture(); print("patched reads:", n)
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/smw_mario.json", "w"))
    print(sum(1 for v in out.values() if v["parts"]), "poses with parts;", sum(v["miss"] for v in out.values()), "unmatched tiles")
