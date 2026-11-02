"""Build snes/profiles/smw.js from your ROM plus the emulator captures.

    export SMW_ROM=/path/to/Super Mario World (USA).sfc
    python3 capture_mario.py /tmp/smw_mario.json     # Mario's poses (scratch ROM, see the file)
    python3 capture_levels.py /tmp/smw_levels.json   # sprites + level screens (a few minutes)
    python3 build_profile.py                          # writes ../../snes/profiles/smw.js
"""
import json, os, sys
from smw import ROM, F, FILES, BPP, GFX_LO, GFX_HI, GFX_BANK, LOAD_32_33, BACK_AREA, cgram_sources
from names import NAMES
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, "..", "..")
MARIO = json.load(open(os.environ.get("SMW_MARIO", "/tmp/smw_mario.json")))
LEVELS = json.load(open(os.environ.get("SMW_LEVELS", "/tmp/smw_levels.json")))

# ---------------------------------------------------------------- graphics files
ORDER = ["GFX32", "GFX33"] + [f"GFX{f:02X}" for f in range(0x32)]   # as they sit in the ROM, from $08:8000
FI = {k: i for i, k in enumerate(ORDER)}
def files():
    out = []
    lda32 = ROM.find(bytes.fromhex("A90080858A"), F(LOAD_32_33)); assert lda32 == F(0x00B8D7)
    for k in ORDER:
        f = {"id": k, "bpp": BPP[k], "at": F({"GFX32": 0x088000, "GFX33": 0x08BFC0}.get(k, 0) or
                                              ROM[F(GFX_BANK) + int(k[3:], 16)] << 16 | ROM[F(GFX_HI) + int(k[3:], 16)] << 8 | ROM[F(GFX_LO) + int(k[3:], 16)])}
        if k == "GFX32":   # LDA.W #GFX32 (its bank is whatever GFX33's read ended in, so GFX32 stays first in bank 08)
            f["ptrs"] = [[lda32 + 1, "word"], [F(0x00B885), "long"]]
        elif k == "GFX33":  # LDY.W #GFX33 / LDA.B #bank in CODE_00B888, and the dl table before it
            f["ptrs"] = [[F(LOAD_32_33) + 3, "word"], [F(LOAD_32_33) + 8, "bank"], [F(0x00B882), "long"]]
            f["max_end"] = 0x47FFF   # its last byte must stay in bank 08 so the GFX32 read that follows stays there too
        else:
            n = int(k[3:], 16); f["ptrs"] = [[F(GFX_LO) + n, "lo"], [F(GFX_HI) + n, "hi"], [F(GFX_BANK) + n, "bank"]]
        assert FILES[k][1] and f["at"] >= 0x40000
        out.append(f)
    ends = [f["at"] + FILES[f["id"]][1] for f in out]
    assert all(out[i + 1]["at"] == ends[i] for i in range(len(out) - 1)), "files aren't contiguous"
    return out, [out[0]["at"], ends[-1]]

# ---------------------------------------------------------------- palettes
WHITE_SPR = ROM.find(bytes.fromhex("A9FF7F8504")) + 1   # LoadPalette's LDA #$7FFF: colour 1 of every sprite palette
WHITE_BG = ROM.find(bytes.fromhex("A9DD7F8504")) + 1    # LDA #$7FDD: colour 1 of every background palette
PALS, PAL_KEY = [], {}
SPRITE_ROW_NAMES = {8: "Mario", 9: "Sprite 1", 10: "Sprite 2", 11: "Sprite 3", 12: "Sprite 4", 13: "Sprite 5", 14: "Sprite 6", 15: "Sprite 7"}
def palette(level, row, player=0, label=None):
    lv = LEVELS["levels"][level]; p = lv["pal"]
    src = cgram_sources(p["sprite"], p["fg"], p["bg"], player)
    cols = [src.get(16 * row + i) for i in range(16)]
    cols[0] = None; cols[1] = WHITE_SPR if row >= 8 else WHITE_BG
    cg = bytes.fromhex(lv["cgram"])
    seen = [None if cols[i] is not None else (f"{cg[2 * (16 * row + i)] | cg[2 * (16 * row + i) + 1] << 8:04X}" if any(cg[2 * (16 * row + i):2 * (16 * row + i) + 2]) else None) for i in range(16)]
    key = (row, tuple(cols), tuple(seen))
    if key not in PAL_KEY:
        if label is None:
            label = SPRITE_ROW_NAMES[row] if row >= 8 else f"BG {row}"
            if row in (14, 15): label += f" · set {p['sprite']}"
            if row in (0, 1): label += f" · back {p['bg']}"
            if row in (2, 3): label += f" · front {p['fg']}"
        PAL_KEY[key] = len(PALS); PALS.append({"label": label, "colors": cols, "seen": seen})
    return PAL_KEY[key]
def backdrop(level):   # BackAreaColors[header]
    o = F(BACK_AREA) + 2 * LEVELS["levels"][level]["pal"]["back"]; return f"{ROM[o] | ROM[o + 1] << 8:04X}"

# ---------------------------------------------------------------- sprites
def part(p, level, sprite=True, player=0):
    f, t, dx, dy, pal, flip, hi = p
    return [FI[f], t, dx, dy, palette(level, (8 + pal) if sprite else pal, player), flip | (hi << 2)]
def pick_frames(cands, cap=12):
    """distinct-looking frames: biggest first, skipping ones whose tiles another kept frame already shows"""
    kept, sets = [], []
    for parts in sorted(cands, key=lambda ps: -len(ps)):
        ts = {(p[0], p[1]) for p in parts}
        if any(ts <= s for s in sets): continue
        kept.append(parts); sets.append(ts)
        if len(kept) == cap: break
    return kept
POWER = {0: "small", 1: "big", 2: "cape", 3: "fire"}
def mario_objects():
    out = []
    for who, player_of in [("Mario", {0: 0, 1: 0, 2: 0, 3: 2}), ("Luigi", {0: 1, 1: 1, 2: 1, 3: 3})]:
        for power in range(4):
            frames, seen = [], set()
            for key, v in MARIO.items():
                pw, pose = key.split(":")
                if int(pw) != power or not v["parts"]: continue
                sig = json.dumps(sorted(map(tuple, v["parts"])))
                if sig in seen: continue
                seen.add(sig)
                frames.append({"name": f"pose {pose}", "parts": [part(p, "15", True, player_of[power]) for p in v["parts"]], "bg": backdrop("15")})
            if who == "Luigi" and power in (2, 3): frames = frames[:24]
            out.append({"name": f"{who} ({POWER[power]})", "group": "Mario & Luigi", "frames": frames})
    return out
GROUPS = {"Yoshi & items": {0x35, 0x2C, 0x2D, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7B, 0x7D, 0x7E, 0x7F, 0x80, 0x21, 0x3E, 0x2F, 0x81, 0x33},
          "Bosses": {0x29, 0xA0, 0xA9, 0xC5, 0x7A}}
def group_of(num, name):
    for g, s in GROUPS.items():
        if num in s: return g
    if any(w in name.lower() for w in ("platform", "block", "bridge", "info box", "pipe", "spring", "switch", "door", "key", "rope", "chain", "net", "lift")): return "Platforms & things"
    return "Enemies"
def sprite_objects():
    out = []
    for k, v in sorted(LEVELS["sprites"].items()):
        num = int(k, 16); name = NAMES.get(num, f"Sprite {k}"); lv = v["levels"][0]
        frames = [{"name": f"frame {i + 1}", "parts": [part(p, lv) for p in ps], "bg": backdrop(lv)} for i, ps in enumerate(pick_frames(list(v["frames"].values())))]
        if frames: out.append({"name": name, "group": group_of(num, name), "sprite": num, "frames": frames})
    order = ["Mario & Luigi", "Yoshi & items", "Enemies", "Bosses", "Platforms & things"]
    return sorted(out, key=lambda o: (order.index(o["group"]), o["name"]))

# ---------------------------------------------------------------- blocks (one per object tileset)
TILESETS = ["Normal 1", "Castle 1", "Rope 1", "Underground 1", "Switch Palace 1", "Ghost House 1", "Rope 2", "Normal 2", "Rope 3",
            "Underground 2", "Switch Palace 2", "Castle 2", "Cloud/Forest", "Ghost House 2", "Underground 3"]
def block_objects():
    out, done = [], {}
    for lv, info in sorted(LEVELS["levels"].items()):
        ts = info["tileset"]
        if ts in done or not info["screen"]: continue
        done[ts] = lv
        scr = [part(p, lv, False) for p in info["screen"]] + [part(p, lv, False) for p in info["layer2"]]
        # a tile sheet per front graphics file, each tile in the palette the screen first uses it with (else BG 6)
        use = {}
        for p in scr: use.setdefault((p[0], p[1]), (p[4], p[5] & 4))
        frames = [{"name": "first screen", "parts": scr, "w": 256, "h": 224, "bg": backdrop(lv)}]
        common = max(set(p[4] for p in scr), key=lambda pi: sum(1 for p in scr if p[4] == pi)) if scr else palette(lv, 6)
        for f in [f"GFX{x:02X}" for x in info["bg_gfx"][::-1]]:
            if f not in FI: continue
            fi = FI[f]; n = len(FILES[f][0]) // 24; parts = []
            for t in range(n):
                pi, hi = use.get((fi, t), (common, 0))
                parts.append([fi, t, 8 * (t % 16), 8 * (t // 16), pi, hi])
            frames.append({"name": f"tiles {f}", "parts": parts, "w": 128, "h": 8 * ((n + 15) // 16), "bg": backdrop(lv)})
        out.append({"name": TILESETS[ts] if ts < len(TILESETS) else f"Tileset {ts}", "group": "Level tilesets", "category": "blocks", "level": lv, "frames": frames})
    return out

def build():
    gfx_files, region = files()
    objects = mario_objects() + sprite_objects() + block_objects()
    from mech import mechanics, presets
    P = {"format": "snes-profile/1", "id": "smw", "game": "Super Mario World (USA)",
         "rom": {"size": len(ROM), "map": "lorom", "checksum": 0x7FDC,
                 "check": [[0x7FC0, ROM[0x7FC0:0x7FD5].hex().upper()], [F(GFX_BANK), ROM[F(GFX_BANK):F(GFX_BANK) + 8].hex().upper()],
                           [F(LOAD_32_33), ROM[F(LOAD_32_33):F(LOAD_32_33) + 11].hex().upper()]]},
         "gfx": {"codec": "lz2", "region": region, "files": gfx_files},
         "palettes": PALS, "objects": objects, "mechanics": mechanics(), "mechanics_presets": presets()}
    return P
if __name__ == "__main__":
    P = build()
    js = ("// Super Mario World (USA): built by dev/gen_smw/build_profile.py from the ROM and emulator captures. Don't edit by hand.\n"
          "window.SNES_PROFILES.push(" + json.dumps(P, separators=(",", ":")) + ");\n")
    out = os.path.join(REPO, "snes", "profiles", "smw.js"); open(out, "w").write(js)
    n = {c: sum(1 for o in P["objects"] if o.get("category", "sprites") == c) for c in ("sprites", "blocks")}
    print(f"{out}: {len(js) // 1024} KB, {n['sprites']} sprite objects, {n['blocks']} tilesets, {len(PALS)} palettes, {len(P['mechanics'])} mechanics")
