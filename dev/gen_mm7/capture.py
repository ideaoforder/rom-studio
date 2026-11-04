"""Capture Mega Man 7 from the running game: boot through the password screen to stage select, enter stages, and
collect each object's OAM tiles, mapped back to ROM sources (graphics set + tile, or uncompressed bank + tile)."""
import os, json
from mm7 import ROM, ROM_PATH, OAM_BUF, CAM_X, CAM_Y, PLAYER, HEALTH, PASSWORD, provenance_index, raw_lookup  # noqa: F401
from emu import SNES
OBJ_VRAM = 0xC000
SEL_CACHE = os.environ.get("MM7_SELECT_STATE", "/tmp/mm7_select.state")
ALL_BEATEN = "7235785618478453"     # a published password: the 8 robot masters beaten, the weapons and some upgrades
STAGES = {"Spring Man": ["UP", "LEFT"], "Freeze Man": ["UP"], "Slash Man": ["UP", "RIGHT"], "Cloud Man": ["LEFT"],
          "Junk Man": ["RIGHT"], "Turbo Man": ["DOWN", "LEFT"], "Burst Man": ["DOWN"], "Shade Man": ["DOWN", "RIGHT"]}
w = lambda r, a: r[a] | r[a + 1] << 8
def title_menu(sc): return sc[130:145, 90:190].mean() > 15 and sc[10:100, 40:220].mean() > 40
def stage_select(path=ROM_PATH, password=ALL_BEATEN, unbeat=()):
    """`unbeat`: weapon numbers to take away while the password loads, so those stages count as not beaten and play
    their boss intro (that also needs $0B7C, a fortress-progress flag, kept at 0)"""
    s = SNES(path)
    if path == ROM_PATH and password == ALL_BEATEN and not unbeat and os.path.exists(SEL_CACHE): s.load(open(SEL_CACHE, "rb").read()); return s
    for f in range(120):
        s.run(30) if f % 2 else s.run(4, "START")
        if title_menu(s.screen()): break
    s.run(40); s.run(4, "DOWN"); s.run(30); s.run(4, "START"); s.run(120)      # PASS WORD
    s.poke(PASSWORD, *[int(c) for c in password]); s.run(10); s.run(4, "START")
    for _ in range(150):
        s.run(1)
        for k in unbeat: s.poke(0x0B83 + 2 * k, 0); s.poke(0x0B7C, 0)
    if path == ROM_PATH and password == ALL_BEATEN and not unbeat: open(SEL_CACHE, "wb").write(s.save())
    return s
def enter(s, stage):
    for m in STAGES[stage]: s.run(4, m); s.run(12)
    s.run(4, "START")
    for _ in range(30): s.run(30)
def oam(r):
    out = []
    for k in range(128):
        x, y, t, a = r[OAM_BUF + 4 * k:OAM_BUF + 4 * k + 4]; hi = (r[OAM_BUF + 0x200 + k // 4] >> (2 * (k % 4))) & 3
        out.append((x - 256 if hi & 1 else x, y, t | (a & 1) << 8, (a >> 1) & 7, (a >> 4) & 3, a >> 6 & 1, a >> 7, hi >> 1))
    return out
class Prov:
    def __init__(self): self.idx = provenance_index(); self.raw = {}
    def tile(self, vram, t):
        b = vram[OBJ_VRAM + 32 * t:OBJ_VRAM + 32 * t + 32]
        if not any(b): return ("blank",)
        m = self.idx.get(b)
        if m: return m
        if b not in self.raw: self.raw[b] = raw_lookup(b)
        return self.raw[b]
    def parts(self, vram, entries, ox, oy):
        """OAM entries -> 8x8 parts [src, tile, dx, dy, pal, flip] with src "set:N" or "raw:BB" (16x16 sprites split)"""
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
                    out.append([f"{src[0]}:{src[1]:02X}", src[2], x - ox + 8 * di, y - oy + 8 * dj, p, h | v << 1])
        return out, miss
def slots(r):
    """live objects: 32-byte slots from $0E00 with +0 = 1; (base, type +$0A, sub +$0B, screen x, screen y)"""
    cx, cy = w(r, CAM_X), w(r, CAM_Y); out = []
    for b in range(0x0E00, 0x1D80, 0x20):
        if r[b] != 1: continue
        x, y = w(r, b + 5) - cx, w(r, b + 8) - cy
        if -48 < x < 304 and -48 < y < 272: out.append((b, r[b + 0x0A], r[b + 0x0B], x, y))
    return out
def groups(r):
    """OAM split into runs of neighbouring entries, each given to the nearest live object (or the player)"""
    ents = [(k, e) for k, e in enumerate(oam(r)) if e[1] < 224]
    runs, cur = [], []
    for k, e in ents:
        if cur and (k != cur[-1][0] + 1 or abs(e[0] - cur[-1][1][0]) > 40 or abs(e[1] - cur[-1][1][1]) > 40): runs.append(cur); cur = []
        cur.append((k, e))
    if cur: runs.append(cur)
    cx, cy = w(r, CAM_X), w(r, CAM_Y); px, py = w(r, PLAYER + 5) - cx, w(r, PLAYER + 8) - cy
    objs = [("player", 0, 0, px, py)] + [(f"{b:04X}", t, st, x, y) for b, t, st, x, y in slots(r)]
    out = {}
    d2 = lambda o, e: (o[3] - e[0] - 8) ** 2 + (o[4] - e[1] - 8) ** 2
    for run in runs:
        # each entry goes to the nearest object; a run that mostly agrees goes whole to that object
        near = [min(objs, key=lambda o: d2(o, e)) for _, e in run]
        top = max(set(near), key=near.count)
        for (_, e), o in zip(run, near):
            o = top if near.count(top) >= 0.7 * len(near) else o
            if d2(o, e) > 64 ** 2: continue
            out.setdefault(o[:3], (o[3], o[4], []))[2].append(e)
    return out
def play(s, prov, frames=1800, every=3, step=3, hover=48):
    """fly right through the stage (no clipping, can't be hurt), collecting objects' frames"""
    seen = {}; r = s.ram; hy = w(r, PLAYER + 8) - hover; f = 0
    while f < frames:
        s.run(every, "RIGHT", *(("Y",) if f % 30 < 15 else ())); f += every
        r = s.ram; x = w(r, PLAYER + 5) + step * every
        s.poke(PLAYER + 5, x & 255, x >> 8); s.poke(PLAYER + 8, hy & 255, hy >> 8)
        for h in HEALTH: s.poke(h, 28)
        r = s.ram; gs = groups(r)
        if not gs: continue
        s.run(1); f += 1; v = s.vram
        for (who, t, st), (ox, oy, es) in gs.items():
            parts, miss = prov.parts(v, es, ox, oy)
            if not parts or miss: continue
            key = "player" if who == "player" else f"{t:02X}"
            seen.setdefault(key, {}).setdefault(json.dumps(sorted(map(tuple, parts))), parts)
    return seen
