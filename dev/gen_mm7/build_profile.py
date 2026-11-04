"""Build snes/profiles/mm7.js from your ROM plus the emulator captures.

    export MM7_ROM=/path/to/Mega Man 7 (USA).sfc
    python3 capture_player.py /tmp/mm7_player.json   # Mega Man's poses
    python3 capture_stages.py /tmp/mm7_stages.json   # the 8 stages: objects, backgrounds, colours
    python3 capture_bosses.py /tmp/mm7_bosses.json   # the 8 robot masters' intro poses
    python3 build_profile.py                         # -> ../../snes/profiles/mm7.js
"""
import json, os
from mm7 import ROM, SETS, SETS_TABLE
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(HERE, "..", "..")
PLAYER = json.load(open(os.environ.get("MM7_PLAYER", "/tmp/mm7_player.json")))
STAGES = json.load(open(os.environ.get("MM7_STAGES", "/tmp/mm7_stages.json")))
BOSSES = json.load(open(os.environ.get("MM7_BOSSES", "/tmp/mm7_bosses.json")))

# ---------------------------------------------------------------- graphics files: every compressed set, plus raw banks in use
def used_raw():
    banks = set()
    def scan(parts):
        for p in parts:
            if p[0].startswith("raw:"): banks.add(int(p[0][4:], 16))
    for v in PLAYER.values(): scan(v)
    for b in BOSSES.values():
        for parts in b["frames"]: scan(parts)
    for st in STAGES["stages"].values():
        scan(st["bg1"]); scan(st["bg2"])
        for fr in st["objects"].values():
            for parts in fr.values(): scan(parts)
    return sorted(banks)
FILES = [{"id": f"SET{i:02X}", "bpp": 4, "codec": "clz", "at": at, "unpacked": n, "ptrs": [[SETS_TABLE + 5 * i, "long"]]}
         for i, (at, n, _, _) in sorted(SETS.items(), key=lambda kv: kv[1][0])]
REGION = [FILES[0]["at"], max(f["at"] + SETS[int(f["id"][3:], 16)][3] for f in FILES)]
assert all(FILES[k + 1]["at"] == FILES[k]["at"] + SETS[int(FILES[k]["id"][3:], 16)][3] for k in range(len(FILES) - 1)), "sets aren't contiguous"
FILES += [{"id": f"RAW{b:02X}", "bpp": 4, "codec": "raw", "at": b << 16, "len": 0x10000} for b in used_raw()]
FI = {f["id"]: i for i, f in enumerate(FILES)}
def fid(src): k, n = src.split(":"); return FI[("SET" if k == "set" else "RAW") + n]

# ---------------------------------------------------------------- palettes: each CGRAM row found back in the ROM
PALS, PAL_KEY = [], {}
def find_run(words):
    b = b"".join(w.to_bytes(2, "little") for w in words); i = ROM.find(b)
    return i if i >= 0 else None
def palette(cgram_hex, row, label):
    cg = bytes.fromhex(cgram_hex); words = [cg[2 * (16 * row + i)] | cg[2 * (16 * row + i) + 1] << 8 for i in range(16)]
    cols = [None] * 16
    for lo, hi in [(1, 16), (1, 8), (8, 16), (1, 5), (5, 9), (9, 13), (13, 16)]:   # the whole row, else smaller pieces
        if any(cols[i] is not None for i in range(lo, hi)) or not any(words[lo:hi]): continue
        o = find_run(words[lo:hi])
        if o is not None:
            for i in range(lo, hi): cols[i] = o + 2 * (i - lo)
    seen = [None if cols[i] is not None or not words[i] else f"{words[i]:04X}" for i in range(16)]
    seen[0] = None
    key = (tuple(cols), tuple(seen))
    if key not in PAL_KEY: PAL_KEY[key] = len(PALS); PALS.append({"label": label, "colors": cols, "seen": seen})
    return PAL_KEY[key]
def part(p, cg, sprite=True, label=None):
    src, t, x, y, pal, flip = p
    row = (8 + pal) if sprite else pal
    return [fid(src), t, x, y, palette(cg, row, label or (f"Sprite {pal}" if sprite else f"BG {pal}")), flip]

def pick_frames(cands, cap=12):
    kept, sets = [], []
    for parts in sorted(cands, key=lambda ps: -len(ps)):
        ts = {(p[0], p[1]) for p in parts}
        if any(ts <= s for s in sets): continue
        kept.append(parts); sets.append(ts)
        if len(kept) == cap: break
    return kept
FIRST = "Freeze Man"
def megaman():
    cg = STAGES["stages"][FIRST]["cgram"]
    poses = list(PLAYER.values()) + [p for st in STAGES["stages"].values() for p in st["objects"].get("player", {}).values()]
    # Mega Man's own tiles are the uncompressed ones streamed in per pose; anything else nearby (Rush, smoke, shots) isn't him
    poses = [[q for q in p if q[0].startswith("raw:")] for p in poses]; poses = [p for p in poses if p]
    full = sorted(len(p) for p in poses)[len(poses) // 2]
    poses = [p for p in poses if len(p) >= 0.6 * full]   # drop the half-drawn frames (charge flashing, flicker)
    frames = [{"name": f"pose {i + 1}", "parts": [part(p, cg, label="Mega Man") for p in ps]} for i, ps in enumerate(pick_frames(poses, cap=48))]
    return [{"name": "Mega Man", "group": "Mega Man", "frames": frames}]

def bosses():
    """each robot master's intro poses; the name lettering (a font set every intro shares) is left out"""
    from collections import Counter
    common = Counter(src for b in BOSSES.values() for src in {p[0] for parts in b["frames"] for p in parts})
    font = {src for src, n in common.items() if n >= 6}
    out = []
    for name, b in BOSSES.items():
        if not b["cgram"]: continue
        frames = [[p for p in parts if p[0] not in font] for parts in b["frames"]]
        full = max(len(f) for f in frames); frames = [f for f in frames if len(f) >= 0.8 * full]
        fr = [{"name": f"pose {i + 1}", "parts": [part(p, b["cgram"], label=name) for p in ps]} for i, ps in enumerate(pick_frames(frames, cap=8))]
        out.append({"name": name, "group": "Robot masters", "frames": fr, "note": "the poses from the stage intro"})
    return out
def stage_objects():
    out = []
    for name, st in STAGES["stages"].items():
        cg = st["cgram"]
        for t, frs in sorted(st["objects"].items()):
            if t == "player": continue
            fr = [{"name": f"frame {i + 1}", "parts": [part(p, cg) for p in ps]} for i, ps in enumerate(pick_frames(list(frs.values())))]
            if not fr: continue
            label = "Shots" if t == "04" else f"type {t}"
            out.append({"name": f"{name.split()[0]} stage: {label}", "group": name, "type": t, "frames": fr})
    return out
def blocks():
    out = []
    for name, st in STAGES["stages"].items():
        cg = st["cgram"]
        front = [part(p, cg, False) for p in st["bg1"]]; back = [part(p, cg, False) for p in st["bg2"]]
        frames = [{"name": "room", "parts": front + back, "w": 256, "h": 256}]
        use = {}
        for p in front + back: use.setdefault((p[0], p[1]), (p[4], p[5] & 0))
        # a sheet of every background tile this stage's screen uses (each in the colours it's used with)
        tiles = sorted(use)
        if tiles:
            frames.append({"name": "tiles", "w": 128, "h": 8 * ((len(tiles) + 15) // 16),
                           "parts": [[fi, t, 8 * (k % 16), 8 * (k // 16), use[(fi, t)][0], 0] for k, (fi, t) in enumerate(tiles)]})
        out.append({"name": name.replace(" Man", " Man's stage"), "group": "Stages", "category": "blocks", "frames": frames})
    return out
def build():
    from mech import mechanics, presets
    objects = megaman() + bosses() + stage_objects() + blocks()
    return {"format": "snes-profile/1", "id": "mm7", "game": "Mega Man 7 (USA)",
            "rom": {"size": len(ROM), "map": "hirom", "checksum": 0xFFDC,
                    "check": [[0xFFC0, ROM[0xFFC0:0xFFD5].hex().upper()], [0xFFD9, ROM[0xFFD9:0xFFDB].hex().upper()],
                              [SETS_TABLE, ROM[SETS_TABLE:SETS_TABLE + 10].hex().upper()]]},
            "gfx": {"codec": "clz", "region": REGION, "files": FILES},
            "palettes": PALS, "objects": objects, "mechanics": mechanics(), "mechanics_presets": presets()}
if __name__ == "__main__":
    P = build()
    js = ("// Mega Man 7 (USA): built by dev/gen_mm7/build_profile.py from the ROM and emulator captures. Don't edit by hand.\n"
          "window.SNES_PROFILES.push(" + json.dumps(P, separators=(",", ":")) + ");\n")
    out = os.path.join(REPO, "snes", "profiles", "mm7.js"); open(out, "w").write(js)
    print(f"{out}: {len(js) // 1024} KB, {len(P['objects'])} objects, {len(PALS)} palettes, {len(FILES)} graphics files")
