import sys, os, json, collections; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfx import ROM, fixed, chr_sets, ppu_map, stage_set
from sprites import sprite
from render import BLOCK_STAGE, string_data, SPRITE_PAL, block_bg
from objects_def import OBJECTS
from mech import mechanics
VBASE = 0x1000000
LABELS = {"B1": "Block 1 · Stages 1–3", "B2": "Block 2 · Stages 4–6", "B3": "Block 3 · Stages 7–9", "B4": "Block 4 · Stages 10–12",
          "B5": "Block 5 · Stages 13–15", "B6": "Block 6 · Stages 16–17", "B7": "Stage 18 · Dracula"}
STAGES = {"B1": [0, 1, 2, 3], "B2": [4, 5, 6], "B3": [7, 8, 9], "B4": [10, 11, 12], "B5": [13, 14, 15], "B6": [16, 17], "B7": [18]}
def area_map(a): return ppu_map([3] if a == "B1" else [3, stage_set(BLOCK_STAGE[a])])
maps = {a: area_map(a) for a in LABELS}
def runs(m):
    out = []
    for t in sorted(m):
        o = m[t]
        if out and out[-1][0] + out[-1][1] == t and out[-1][2] + out[-1][1] * 16 == o: out[-1][1] += 1
        else: out.append([t, 1, o])
    return out
def tok(i, h, v): return f"{i:02X}" + ("h" if h else "") + ("v" if v else "")
objects = []; used = set()
for name, group, area, frames in OBJECTS:
    m = maps[area]; fr = {}
    for fn, code in frames:
        sp = []
        for dy, t, a, dx in sprite(code):
            top = (t & 0xFE) + (0x100 if t & 1 else 0); h = bool(a & 0x40); v = bool(a & 0x80)
            first, second = (top + 1, top) if v else (top, top + 1)
            sp.append([tok(first, h, v), dx, dy, a & 3]); sp.append([tok(second, h, v), dx, dy + 8, a & 3])
            for q in (top, top + 1):
                assert q in m, (name, fn, hex(q)); used.add(m[q])
        fr[fn] = {"sprites": sp}
    pal = collections.Counter(s[3] for f in fr.values() for s in f["sprites"]).most_common(1)[0][0]
    objects.append({"name": name, "group": group, "chr_area": area, "home": area, "palette": [pal], "frames": fr})
# background: the first screen of each stage (from the emulator) and a sheet of the block's background tiles
CACHE = os.environ.get("CV_SCREENS", "/tmp/cv_screens.json")
if os.path.exists(CACHE): SCR = {int(k): v for k, v in json.load(open(CACHE)).items()}
else:
    from screens import screen
    SCR = {}
    for st in range(19): t, p, _ = screen(st); SCR[st] = [t, p]
    json.dump(SCR, open(CACHE, "w"))
for a, sts in STAGES.items():
    m = maps[a]; fr = {}; use = collections.defaultdict(collections.Counter)
    for st in sts:
        t, p = SCR[st]
        fr[f"stage {max(st, 1)}" + (" (courtyard)" if st == 0 else "")] = {"cols": 32, "tiles": " ".join(f"{x:03X}" for x in t), "palettes": " ".join(f"bg{x}" for x in p)}
        for x, q in zip(t, p): use[x][q] += 1; used.add(m[x])
    toks = [f"{0x100 + i:03X}" if 0x100 + i in m else "." for i in range(256)]
    pals = [f"bg{use[0x100 + i].most_common(1)[0][0]}" if use[0x100 + i] else "bg0" for i in range(256)]
    fr["tiles"] = {"cols": 16, "tiles": " ".join(toks), "palettes": " ".join(pals)}
    objects.append({"name": LABELS[a], "category": "blocks", "group": "Stages", "chr_area": a, "home": a, "palette": ["bg0"], "frames": fr})
# identical copies of a used tile at the same PPU address in other CHR sets (title, intro, map, ending) follow it
sets = []; allmaps = [ppu_map([s]) for s in range(12)]
for o in sorted(used):
    data = ROM[o:o + 16]
    if not any(data): continue
    addrs = {t for m in maps.values() for t, x in m.items() if x == o}
    grp = sorted({m[t] for m in allmaps for t in addrs if t in m and ROM[m[t]:m[t] + 16] == data} | {o})
    if len(grp) > 1 and grp not in sets: sets.append(grp)
palettes = {}
NAMES = ["Simon & gold", "Purple (whip, axe, ghouls)", "Blue & tan (dagger, cross)", "Red (fire, hearts, bats)"]
for k in range(4): palettes[f"spr.{k}"] = {"offset": SPRITE_PAL + 4 * k + 1, "label": f"Sprite palette {k} · {NAMES[k]}"}
areas = {}
for a in LABELS:
    areas[a] = {"label": LABELS[a], "sky": "0F"}
    for k in range(4): palettes[f"{a}.{k}"] = {"same_as": f"spr.{k}"}
    bg = block_bg(STAGES[a][-1])
    for k in range(4): palettes[f"{a}.bg{k}"] = {"offset": bg + 4 * k + 1, "label": f"{LABELS[a]} · background {k}" + (" (status bar)" if k == 3 else "")}
P = {"format": "nes-sprite-profile/1", "game": "Castlevania (USA)", "objects_label": "Sprites",
     "rom": {"size": len(ROM), "chr_offset": 0, "check": [[0, "4E45531A0800"], [fixed(0xFDBB), ROM[fixed(0xFDBB):fixed(0xFDBB) + 8].hex().upper()],
                                                          [fixed(0xC8B0), ROM[fixed(0xC8B0):fixed(0xC8B0) + 19].hex().upper()]]},
     "chr_ram": {"vbase": VBASE, "blocks": {}, "free": {}, "areas": {a: runs(m) for a, m in maps.items()}},
     "chr_link_sets": sets, "areas": areas, "palettes": palettes, "objects": objects, "mechanics": mechanics(),
     "mechanics_presets": {"Normal": {}, "Vampire hunter": {"invincible": True, "lives": True, "hearts": True, "subweapon": 13, "shots": 2, "whip": 2},
                           "Moon": {"jump": 150, "airjump": 1}, "Glass cannon": {"damage": 400, "whip": 2, "subweapon": 11, "shots": 2}}}
out = os.environ.get("CV_OUT", "/tmp/cv_profile.json"); json.dump(P, open(out, "w"), separators=(",", ":"))
print(len(objects), "objects", len(sets), "link sets", len(json.dumps(P)) // 1024, "KB")
if os.environ.get("WRITE_HTML"):
    html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../index.html"); h = open(html).read()
    i = h.index("const CV_PROFILE = ") + len("const CV_PROFILE = "); j = h.index(";\nconst BUILTIN_PROFILES", i)
    open(html, "w").write(h[:i] + json.dumps(P, separators=(",", ":")) + h[j:])
