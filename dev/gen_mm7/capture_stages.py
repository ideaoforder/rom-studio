"""Visit the eight robot master stages (from the published all-masters password) and record, per stage: colours, the
two background tilemaps mapped back to ROM tiles, and every object's frames; plus Mega Man's colours for each weapon.
Writes a JSON cache for build_profile.py."""
import json, sys
import capture as C
BG1_MAP, BG2_MAP = 0xA800, 0xB800       # 32x32 tilemaps in VRAM (found by rendering candidates against the screen)
def bg_tile(prov, v, t):
    b = v[32 * t:32 * t + 32]
    if not any(b): return ("blank",)
    return prov.idx.get(b)   # sets only: background art isn't streamed from the uncompressed banks
def tilemap(prov, v, base):
    parts, miss = [], 0
    for ty in range(32):
        for tx in range(32):
            o = base + 2 * (ty * 32 + tx); e = v[o] | v[o + 1] << 8; src = bg_tile(prov, v, e & 0x3FF)
            if src is None: miss += 1; continue
            if src[0] == "blank": continue
            parts.append([f"{src[0]}:{src[1]:02X}", src[2], 8 * tx, 8 * ty, (e >> 10) & 7, (e >> 14) & 3])
    return parts, miss
def weapons(s, n=13):
    """Mega Man's colours (CGRAM row 9) for each weapon, picked through the pause menu"""
    out = []
    for k in range(n):
        s.run(4, "START"); s.run(50)
        if k: s.run(4, "DOWN"); s.run(16)
        s.run(4, "START"); s.run(50)
        out.append((s.ram[0x0B73], s.cgram.hex()))
    return out
def capture():
    s = C.stage_select(); sel = s.save(); prov = C.Prov(); out = {"stages": {}, "weapons": None}
    for name in C.STAGES:
        s.load(sel); C.enter(s, name); s.run(20); r = s.ram; v = s.vram
        bg1, m1 = tilemap(prov, v, BG1_MAP); bg2, m2 = tilemap(prov, v, BG2_MAP)
        st = {"cgram": s.cgram.hex(), "bg1": bg1, "bg2": bg2, "miss": m1 + m2}
        if out["weapons"] is None: out["weapons"] = weapons(s); s.load(sel); C.enter(s, name); s.run(20)
        st["objects"] = C.play(s, prov, frames=2400)
        out["stages"][name] = st
        print(name, {k: len(x) for k, x in st["objects"].items()}, "tile misses", m1 + m2, flush=True)
    return out
if __name__ == "__main__":
    json.dump(capture(), open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mm7_stages.json", "w"))
