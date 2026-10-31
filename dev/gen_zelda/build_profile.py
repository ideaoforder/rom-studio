import sys, os, json, collections; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfx import ROM, ppu_map, palettes, LEVELINFO, F, blocks as area_blocks
from anims import frames, mirrored_guess
from objects_def import OBJECTS
from mech import mechanics
VBASE = 0x1000000
AREAS = ["ow"] + [f"L{i}" for i in range(1, 10)]
LABEL = {"ow": "Overworld", **{f"L{i}": f"Level {i}" for i in range(1, 10)}}
maps = {a: ppu_map(a) for a in AREAS}
def find1(hexs):
    p = bytes.fromhex(hexs); i = ROM.find(p); assert i > 0 and ROM.find(p, i + 1) == -1, hexs; return i
ITEM_OFFS = find1("0003070A0B0C0D0E0F11121314151617"); ITEM_TILES = ITEM_OFFS + 37
assert ROM[ITEM_TILES:ITEM_TILES + 4] == bytes([0x20, 0x82, 0x3C, 0x34])
ITEM_PALS = find1("FF01FF0000020200010002000002020102")
AQUA = find1("CCC4C8C2C6CACCC4C8CED0D2")
GANON = find1("060807090000010102020303040005010404050500040105")
def tok(t, h=False):
    return f"{(t & 0xFE):02X}" + ("h" if h else ""), f"{(t & 0xFE) + 1:02X}" + ("h" if h else "")
def pair(t, attr, mode, dx=0, dy=0):
    """mode: 'wide' T|T+2, 'mirror' T|T flipped, 'narrow' one 8x16 centred, 'slim' mirrored 7 px apart."""
    p = attr & 3; a, b = tok(t)
    if mode == "narrow": return [[a, dx + 4, dy, p], [b, dx + 4, dy + 8, p]]
    if mode in ("mirror", "slim"):
        ah, bh = tok(t, True); sep = 7 if mode == "slim" else 8
        return [[a, dx, dy, p], [b, dx, dy + 8, p], [ah, dx + sep, dy, p], [bh, dx + sep, dy + 8, p]]
    c, d = tok(t + 2); return [[a, dx, dy, p], [b, dx, dy + 8, p], [c, dx + 8, dy, p], [d, dx + 8, dy + 8, p]]
def item_mode(t):
    if t == 0xF3 or 0x20 <= t < 0x62: return "narrow"
    if t < 0x6C: return "slim"
    if t < 0x7C: return "mirror"
    return "wide"
ITEM_SLOT_NAMES = ["Sword", "Bomb", "Arrow", "Bow", "Candle", "Recorder", "Food", "Potion", "Magic rod", "Raft", "Book", "Ring", "Stepladder",
                   "Magic key", "Power bracelet", "Letter", "Compass", "Map", "Compass (level 9)", "Map (level 9)", "Fairy", "Clock", "Rupee", "Key",
                   "Heart container", "Heart", "Triforce", "Triforce (big)", "Rupees (5)", "Boomerang", "Magic boomerang", "Magic shield", "Master sword",
                   "Slot 21", "Slot 22", "Slot 23", "Slot 24"]
used = set(); objects = []
for name, group, area, (kind, typ, names) in OBJECTS:
    m = maps[area]; fr = {}
    if kind == "anim":
        for k, (t, at, _) in enumerate(frames(typ + 1)):
            if names and len(names) == 1 and k: break  # a single named frame: just that one
            fr[names[k] if names and k < len(names) else f"frame {k + 1}"] = {"sprites": pair(t, at, "mirror" if mirrored_guess(t) else "wide")}
    elif kind == "link":
        for k, (t, at, _) in enumerate(frames(0)): fr[names[k]] = {"sprites": pair(t, at, "wide")}
    elif kind == "aquamentus":
        for f in range(2):
            sp = []
            for i in range(6): sp += pair(ROM[AQUA + 6 * f + i], 3, "narrow", dx=8 * (i % 3) - 4, dy=16 * (i // 3))
            fr[names[f]] = {"sprites": sp}
    elif kind == "ganon":
        imgs = frames(0x3E + 1)
        for f in range(6):
            sp = []
            for q in range(4):
                t, at, _ = imgs[ROM[GANON + 4 * f + q]]
                dy = 16 * (q // 2)
                if q % 2 == 0: sp += pair(t, at, "wide", dx=0, dy=dy)
                else:  # GanonSpriteHFlips: the right column is the image flipped (right half first)
                    p = at & 3; (a, c), (e, g) = tok(t + 2, True), tok(t, True)
                    sp += [[a, 16, dy, p], [c, 16, dy + 8, p], [e, 24, dy, p], [g, 24, dy + 8, p]]
            fr[names[f]] = {"sprites": sp}
    elif kind == "items":
        for slot, nm in enumerate(ITEM_SLOT_NAMES):
            s, e = ROM[ITEM_OFFS + slot], (ROM[ITEM_OFFS + slot + 1] if slot + 1 < 37 else 0x30)
            pv = ROM[ITEM_PALS + slot] if slot < 32 else 1
            pal = 1 if pv == 0xFF else pv & 3
            for k in range(s, e):
                t = ROM[ITEM_TILES + k]
                fr[nm + ("" if e - s == 1 else f" {k - s + 1}")] = {"sprites": pair(t, pal, item_mode(t))}
    for f in fr.values():
        for s in f["sprites"]:
            q = int(s[0][:2], 16); assert q in m, (name, s); used.add(m[q])
    pals = collections.Counter(s[3] for f in fr.values() for s in f["sprites"])
    objects.append({"name": name, "group": group, "chr_area": area, "home": area, "palette": [pals.most_common(1)[0][0]], "frames": fr})
# blocks: screens captured in cynes (screens.py; cached), plus a sheet of each area's background tiles
CACHE = os.environ.get("ZELDA_SCREENS", "/tmp/zelda_screens.json")
if not os.path.exists(CACHE):
    from screens import all_screens
    json.dump({k: v for k, v in all_screens().items() if not k.endswith(":chr")}, open(CACHE, "w"))
SCR = json.load(open(CACHE))
for a in AREAS:
    m = maps[a]; fr = {}; use = collections.defaultdict(collections.Counter)
    keys = [k for k in SCR if k.startswith("ow:")] if a == "ow" else [a]
    for k in keys:
        t, p = SCR[k]; fr["entrance" if a != "ow" else f"room {k[3:]}"] = {"cols": 32, "tiles": " ".join(f"{x:03X}" for x in t), "palettes": " ".join(f"bg{x}" for x in p)}
        for x, q in zip(t, p): use[x][q] += 1; used.add(m[x])
    toks = [f"{0x100 + i:03X}" if 0x100 + i in m else "." for i in range(256)]
    pals = [f"bg{use[0x100 + i].most_common(1)[0][0]}" if use[0x100 + i] else "bg0" for i in range(256)]
    fr["tiles"] = {"cols": 16, "tiles": " ".join(toks), "palettes": " ".join(pals)}
    objects.append({"name": LABEL[a], "category": "blocks", "group": "World", "chr_area": a, "home": a, "palette": ["bg0"], "frames": fr})
print(len(objects), "objects")
# palettes: sprite rows 0-2 are the same in every LevelInfo, so one entry with mirrors; row 3 and the background rows per area
palettes_ = {}; areas = {}
spr_rows = {k: [palettes(a) + 16 + 4 * k + 1 for a in AREAS] for k in range(4)}
NAMES = ["Link", "Blue enemies", "Red enemies", "Level color"]
own = set()  # (area, row) whose colors differ from the overworld's copy (Level 3's Link row does)
for k in range(3):
    offs = spr_rows[k]; same = [o for o in offs[1:] if ROM[o:o + 3] == ROM[offs[0]:offs[0] + 3]]
    own |= {(AREAS[i], k) for i, o in enumerate(offs) if i and o not in same}
    palettes_[f"spr.{k}"] = {"offset": offs[0], "mirror": same, "label": f"Sprite palette {k} · {NAMES[k]}"}
for a in AREAS:
    areas[a] = {"label": LABEL[a], "sky": f"{ROM[palettes(a)]:02X}"}
    for k in range(3):
        palettes_[f"{a}.{k}"] = {"offset": spr_rows[k][AREAS.index(a)], "label": f"{LABEL[a]} · {NAMES[k]}"} if (a, k) in own else {"same_as": f"spr.{k}"}
    palettes_[f"{a}.3"] = {"offset": spr_rows[3][AREAS.index(a)], "label": f"{LABEL[a]} · sprite palette 3"}
    for k in range(4): palettes_[f"{a}.bg{k}"] = {"offset": palettes(a) + 4 * k + 1, "label": f"{LABEL[a]} · background palette {k}"}
def runs(m):
    out = []
    for t in sorted(m):
        o = m[t]
        if out and out[-1][0] + out[-1][1] == t and out[-1][2] + out[-1][1] * 16 == o: out[-1][1] += 1
        else: out.append([t, 1, o])
    return out
P = {"format": "nes-sprite-profile/1", "game": "The Legend of Zelda (USA) (Rev 1)", "objects_label": "Sprites",
     "rom": {"size": len(ROM), "chr_offset": 0, "check": [[0, "4E45531A0800"], [ITEM_TILES, ROM[ITEM_TILES:ITEM_TILES + 8].hex().upper()], [LEVELINFO["ow"], ROM[LEVELINFO["ow"]:LEVELINFO["ow"] + 8].hex().upper()]]},
     "chr_ram": {"vbase": VBASE, "blocks": {}, "free": {}, "areas": {a: runs(m) for a, m in maps.items()}},
     "areas": areas, "palettes": palettes_, "objects": objects, "mechanics": mechanics(),
     "mechanics_presets": {"Normal": {}, "Ready to go": {"kit_sword": 1, "kit_hearts": 0x44, "kit_bombs": 8, "kit_rupees": 100, "kit_boomerang": True},
       "Easy mode": {"damage": 0, "beam": True, "kit_sword": 2, "kit_hearts": 0x77, "kit_ring": 1, "kit_candle": 1, "kit_bombs": 8, "kit_rupees": 255},
       "Super Link": {"invincible": True, "beam": True, "bombs": True, "speed": 0xC0, "kit_sword": 3, "kit_hearts": 0xFF, "kit_ring": 2, "kit_candle": 2,
         "kit_arrow": 2, "kit_bow": True, "kit_magicboomerang": True, "kit_magicshield": True, "kit_rod": True, "kit_book": True, "kit_raft": True,
         "kit_ladder": True, "kit_magickey": True, "kit_bracelet": True, "kit_recorder": True, "kit_bombs": 8, "kit_rupees": 255},
       "Hard mode": {"damage": 2}}}
if os.environ.get("ZELDA_EXTRA"): P.update(json.load(open(os.environ["ZELDA_EXTRA"])))
out = os.environ.get("ZELDA_OUT", "/tmp/zelda_profile.json"); json.dump(P, open(out, "w"), separators=(",", ":"))
print(len(json.dumps(P)) // 1024, "KB")
if os.environ.get("WRITE_HTML"):
    html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../index.html"); h = open(html).read()
    i = h.index("const ZELDA_PROFILE = ") + len("const ZELDA_PROFILE = "); j = h.index(";\n", i)
    open(html, "w").write(h[:i] + json.dumps(P, separators=(",", ":")) + h[j:])
