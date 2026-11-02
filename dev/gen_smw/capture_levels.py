"""Visit levels (forced through $0109), collecting sprite frames and each level's first screen, with the level's
graphics and palette settings. Writes a JSON cache that build_profile.py reads."""
import json, sys
from capture import boot_ow, warp, Prov, play_level, screen
ITEMS = [0x21, 0x2C, 0x2D, 0x2F, 0x3E, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7B, 0x7D, 0x80, 0x0F, 0x10, 0x1C, 0x1E, 0x2A,
         0x33, 0x4F, 0x50, 0x51, 0x6A, 0x7E, 0x7F]
def submap_rom():
    """scratch ROM where a forced level number always gets the submap high byte ($101-$13B)"""
    import tempfile, os
    from smw import ROM, F
    b = bytearray(ROM); i = b.find(bytes.fromhex("B9111FF002A901"), F(0x05D8A2), F(0x05D8B7)); assert i > 0   # CODE_05D8A2's submap check
    b[i + 3:i + 5] = b"\xEA\xEA"; p = os.path.join(tempfile.mkdtemp(), "submap.sfc"); open(p, "wb").write(b); return p
def capture(levels, path=None, out=None):
    s = boot_ow(path) if path else boot_ow(); base = s.save(); prov = Prov(); out = out or {"levels": {}, "sprites": {}}
    for v in levels:
        s.load(base)
        if not warp(s, v): continue
        s.run(30); r = s.ram
        info = {"sprite_gfx": list(r[0x101:0x105]), "bg_gfx": list(r[0x105:0x109]), "tileset": r[0x1931], "sprite_tileset": r[0x192B],
                "pal": {"sprite": r[0x192E], "fg": r[0x192D], "bg": r[0x1930], "back": r[0x192F]}, "cgram": s.cgram.hex()}
        info["screen"], info["screen_miss"] = screen(prov, s, 1)
        info["layer2"], _ = screen(prov, s, 2)
        out["levels"][f"{v + (0xDC if path else 0):03X}" if path else f"{v:02X}"] = info
        for num, frames in play_level(s, prov).items():
            d = out["sprites"].setdefault(f"{num:02X}", {"levels": [], "frames": {}})
            d["levels"].append(f"{v + 0xDC:03X}" if path else f"{v:02X}")
            for k, p in frames.items(): d["frames"].setdefault(k, p)
        print(f"level {v:02X}: {len(out['sprites'])} sprite kinds so far", flush=True)
    return out
if __name__ == "__main__":
    out = capture(list(range(1, 0x25)))
    out = capture(list(range(0x25, 0x60)), submap_rom(), out)   # levels $101-$13B
    # power-ups and other items use the always-loaded sprite graphics, so spawn them next to Mario in one level
    from capture import boot_ow, warp, spawn, Prov
    s = boot_ow(); warp(s, 0x05); s.run(30); base = s.save(); prov = Prov()
    for num in ITEMS:
        s.load(base); fr = spawn(s, prov, num)
        if fr:
            d = out["sprites"].setdefault(f"{num:02X}", {"levels": ["05"], "frames": {}})
            for k, p in fr.items(): d["frames"].setdefault(k, p)
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/smw_levels.json", "w"))
