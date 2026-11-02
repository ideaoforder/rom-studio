"""Capture from the running game (stable-retro / Snes9x): Mario's poses, sprites' OAM groups, level screens.
Everything is mapped back to ROM sources (graphics file + tile) by matching VRAM tile bytes against the decoded files."""
import os, json, tempfile
from smw import ROM, ROM_PATH, F, provenance_index
from emu import SNES
OBJ_VRAM = 0xC000              # sprite tiles (OBSEL): tile T at byte 0xC000 + 32*T
OW_CACHE = os.environ.get("SMW_OW_STATE", "/tmp/smw_ow.state")
def boot_ow(path=ROM_PATH):
    """title -> file A -> 1 player -> through the intro message -> overworld; cached as a save state"""
    if path != ROM_PATH:   # a scratch copy: reach the map with the real ROM, then carry the save state over
        st = boot_ow().save(); s = SNES(path); s.load(st); return s
    s = SNES(path)
    if os.path.exists(OW_CACHE): s.load(open(OW_CACHE, "rb").read()); return s
    s.run(300); s.run(5, "START"); s.run(90)
    for _ in range(3): s.run(5, "START"); s.run(60)
    for _ in range(60):
        s.run(5, "A"); s.run(25)
        if s.ram[0x100] == 0x0E: break
    s.run(60); assert s.ram[0x100] == 0x0E, "didn't reach the overworld"
    open(OW_CACHE, "wb").write(s.save())
    return s
def warp(s, v):  # force-load a level from the overworld: $0109 = translevel; $25+ are levels $101+ when on a submap
    if v >= 0x25: s.poke(0x1F11, 1)
    s.poke(0x109, v); s.poke(0x100, 0x0B); s.run(140)
    for _ in range(60):
        if s.ram[0x100] == 0x14: break
        s.run(5)
    return s.ram[0x100] == 0x14
def oam(ram):
    """RAM OAM buffer ($0200 + $0420 sizes) as (x, y, tile, pal, prio, hflip, vflip, large)"""
    out = []
    for k in range(128):
        x, y, t, a = ram[0x200 + 4 * k:0x204 + 4 * k]; sz = ram[0x420 + k]
        x = x - 256 if sz & 1 else x
        out.append((x, y, t | (a & 1) << 8, (a >> 1) & 7, (a >> 4) & 3, a >> 6 & 1, a >> 7, sz >> 1 & 1))
    return out
class Prov:
    def __init__(self): self.idx = provenance_index()
    def tile(self, vram, t):
        """sprite tile 0-511 -> (file, tile, hi) or None"""
        b = vram[OBJ_VRAM + 32 * t:OBJ_VRAM + 32 * t + 32]
        if not any(b): return ("blank",)
        return self.idx.get(b)
    def parts(self, vram, entries, ox, oy):
        """OAM entries -> 8x8 parts [file, tile, dx, dy, pal, flip, hi] (16x16 sprites split the way the PPU does)"""
        out, miss = [], 0
        for x, y, t, p, pr, h, v, big in entries:
            n = 2 if big else 1
            for j in range(n):
                for i in range(n):
                    tt = (t & 0x100) | ((t & 0xF0) + 16 * j) & 0xF0 | ((t & 0x0F) + i) & 0x0F
                    src = self.tile(vram, tt)
                    if src is None: miss += 1; continue
                    if src[0] == "blank": continue
                    di = (n - 1 - i) if h else i; dj = (n - 1 - j) if v else j
                    out.append([src[0], src[1], x - ox + 8 * di, y - oy + 8 * dj, p, h | v << 1, src[2]])
        return out, miss

BG_VRAM, L1_MAP, L2_MAP = 0x0000, 0x4000, 0x6000     # BG tiles (char base 0), layer 1 / layer 2 tilemaps (64x32 each)
def bg_tile(prov, vram, t):
    b = vram[BG_VRAM + 32 * t:BG_VRAM + 32 * t + 32]
    if not any(b): return ("blank",)
    return prov.idx.get(b)
def screen(prov, s, layer=1):
    """the visible 32x28 tiles of a layer's tilemap as parts [file, tile, x, y, pal, flip, hi]"""
    r, v = s.ram, s.vram
    sx = (r[0x1A] | r[0x1B] << 8) if layer == 1 else (r[0x1E] | r[0x1F] << 8)
    sy = (r[0x1C] | r[0x1D] << 8) if layer == 1 else (r[0x20] | r[0x21] << 8)
    base = L1_MAP if layer == 1 else L2_MAP; parts, miss = [], 0
    for ty in range(28):
        for tx in range(32):
            X = (sx // 8 + tx) % 64; Y = (sy // 8 + ty) % 64          # 64x64 tilemaps: four 32x32 screens
            o = base + 2 * ((Y // 32) * 2048 + (X // 32) * 1024 + (Y % 32) * 32 + X % 32); e = v[o] | v[o + 1] << 8
            src = bg_tile(prov, v, e & 0x3FF)
            if src is None: miss += 1; continue
            if src[0] == "blank": continue
            parts.append([src[0], src[1], 8 * tx - sx % 8, 8 * ty - sy % 8, (e >> 10) & 7, (e >> 14) & 3, src[2]])
    return parts, miss

def play_level(s, prov, frames=1500, every=3):
    """run right (and jump) through a level, collecting each live sprite's OAM tiles as parts"""
    seen = {}
    script = lambda f: ("RIGHT", "Y")
    f = 0; r = s.ram; hover = (r[0x96] | r[0x97] << 8) - 40
    while f < frames:
        s.run(every, *script(f)); f += every
        s.poke(0x1497, 0x40)                      # flashing invincibility, so walking into enemies doesn't end the run
        s.poke(0x96, hover & 255, hover >> 8); s.poke(0x7D, 0)   # hover above the ground (no pits)
        r = s.ram
        if r[0x71] == 9 or r[0x100] != 0x14: break
        cx, cy = r[0x1A] | r[0x1B] << 8, r[0x1C] | r[0x1D] << 8
        ents = oam(r); groups = []
        used = sorted((r[0x15EA + x], x) for x in range(12) if r[0x14C8 + x] >= 8)
        for k, (idx, x) in enumerate(used):
            end = used[k + 1][0] if k + 1 < len(used) else 0x100
            sx = (r[0xE4 + x] | r[0x14E0 + x] << 8) - cx; sy = (r[0xD8 + x] | r[0x14D4 + x] << 8) - cy
            mine = [e for e in ents[64 + idx // 4:64 + min(end, idx + 64) // 4] if e[1] < 0xE0 and -48 < e[0] - sx < 64 and -64 < e[1] - sy < 48]
            if mine: groups.append((r[0x9E + x], mine, sx, sy))
        if not groups: continue
        s.run(1); f += 1; v = s.vram
        for num, mine, sx, sy in groups:
            parts, miss = prov.parts(v, mine, sx, sy)
            if not parts or miss: continue
            key = json.dumps(sorted(map(tuple, parts)))
            seen.setdefault(num, {}).setdefault(key, parts)
    return seen

def spawn(s, prov, num, frames=150, every=3):
    """put sprite `num` in slot 9 near Mario and collect its frames (for items that only appear when spawned)"""
    r = s.ram; mx = r[0x94] | r[0x95] << 8; my = r[0x96] | r[0x97] << 8
    x, y = mx + 48, my - 8
    for a, v in [(0x9E + 9, num), (0x14C8 + 9, 1), (0xE4 + 9, x & 255), (0x14E0 + 9, x >> 8), (0xD8 + 9, y & 255), (0x14D4 + 9, y >> 8)]: s.poke(a, v)
    seen = {}
    for f in range(0, frames, every):
        s.run(every); s.poke(0x1497, 0x40); r = s.ram
        if r[0x14C8 + 9] < 8 or r[0x9E + 9] != num: continue
        cx, cy = r[0x1A] | r[0x1B] << 8, r[0x1C] | r[0x1D] << 8
        sx = (r[0xE4 + 9] | r[0x14E0 + 9] << 8) - cx; sy = (r[0xD8 + 9] | r[0x14D4 + 9] << 8) - cy; idx = r[0x15EA + 9]
        mine = [e for e in oam(r)[64 + idx // 4:64 + min(0x100, idx + 32) // 4] if e[1] < 0xE0 and -48 < e[0] - sx < 64 and -64 < e[1] - sy < 48]
        if not mine: continue
        s.run(1); parts, miss = prov.parts(s.vram, mine, sx, sy)
        if parts and not miss: seen.setdefault(json.dumps(sorted(map(tuple, parts))), parts)
    return seen
