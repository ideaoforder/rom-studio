"""Rush (Coil, Marine, Jet) objects for MM3_PROFILE, read from your own Mega Man 3 (USA) ROM.

    MM3_ROM="/path/to/Mega Man 3 (USA).nes" python3 rush.py              # print the objects
    MM3_ROM=... WRITE_HTML=1 python3 rush.py                             # replace them in index.html

How the game draws Rush (see HANDOFF.md, Mega Man 3):
- Rush Coil/Marine/Jet are weapons 7/9/11. `init_rush` ($1ED1A6) puts him in object slot 1 with
  animation $13 (the teleport, the same beam as Mega Man's) and main routine $80.
- When he lands, bank $1C $86CA switches to main $81 and the animation `[$D8, $D9, $D7][($A0 - 7) / 2]`
  (table at $1C:8718). Marine only lands where `$41 == $80` (water); elsewhere he teleports away.
- His art is tiles $70-$7F of the weapon's own sprite bank ($EB = `$A634[w]`: Coil 4, Marine 2, Jet 3).
  No other object uses those tiles in those banks. Attribute palette 0 = Mega Man's body colors for that
  weapon (`body.N`), 1 = the face colors, the same palettes Mega Man is drawn with while Rush is selected.
Checked in cynes by dev/test_mm3.py: Coil sits on $0F and shows $10 once Mega Man lands on him, Jet
alternates $0D/$0E every 5 frames, Marine draws $94 (with the water check skipped in a scratch copy).
"""
import json, os, sys

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(DEV)
ROM = os.environ.get("MM3_ROM") or sys.exit("Set MM3_ROM=/path/to/Mega Man 3 (USA).nes")
rom = open(ROM, "rb").read()
assert len(rom) == 393232, "expected Mega Man 3 (USA), 393,232 bytes"

PRG = lambda b: 0x10 + b * 0x2000
s8 = lambda v: v - 256 if v > 127 else v


def anim(aid):
    """[frame ids], duration - 1, from the anim tables in bank $1A (< $80) or $1B."""
    b = PRG(0x1A if aid < 0x80 else 0x1B); i = aid & 0x7F
    o = b + (rom[b + i] | rom[b + 0x80 + i] << 8) - 0x8000
    return list(rom[o + 2:o + 3 + rom[o]]), rom[o + 1]


def frame(aid, fid, facing=1):
    """The renderer at $1FF13B: (tile, attr, dx, dy) per hardware sprite. facing 1 = right (H-flip, offsets index + 1)."""
    base = PRG(0x1A if aid < 0x80 else 0x1B)
    o = base + (rom[base + 0x100 + fid] | rom[base + 0x200 + fid] << 8) - 0x8000
    ob = PRG(0x14 if rom[o] & 0x80 else 0x19); idx = rom[o + 1] + facing
    q = ob + (rom[ob + 0x1E00 + idx] | rom[ob + 0x1F00 + idx] << 8) - 0xA000 - 2
    return [(rom[o + 2 + 2 * k], rom[o + 3 + 2 * k] ^ (0x40 if facing else 0), s8(rom[q + 3 + 2 * k]), s8(rom[q + 2 + 2 * k]))
            for k in range((rom[o] & 0x7F) + 1)]


def sprites(aid, fid):
    out = []
    for t, a, dx, dy in frame(aid, fid):
        tok = f"{t:02X}" + ("h" if a & 0x40 else "") + ("v" if a & 0x80 else "")
        out.append([tok, dx, dy, "face" if a & 3 == 1 else None])
    return out


# weapon index -> sprite bank, from the game's own table ($A634 in bank 2)
EB = {w: rom[PRG(2) + 0x634 + w] for w in range(12)}
LAND = [rom[PRG(0x1C) + 0x718 + k] for k in range(3)]  # $D8, $D9, $D7
TELEPORT = 0x13
tele_ids, tele_dur = anim(TELEPORT)
assert rom[PRG(0x1E) + 0x11BD] == TELEPORT, "init_rush should start anim $13"
assert tele_ids == [0x12, 0x13, 0x12, 0x14, 0x14]
tele_frames = {"teleport beam": 0x12, "teleport 2": 0x13, "teleport 3": 0x14}
tele_clip = [["teleport beam", tele_dur + 1], ["teleport 2", tele_dur + 1], ["teleport beam", tele_dur + 1], ["teleport 3", 2 * (tele_dur + 1)]]

NOTE = ("Rush is drawn in Mega Man's colors for this weapon, so recoloring him also recolors Mega Man while {mode} is selected. "
        "No other character uses his tiles.{twins} The teleport beam is the same art as Mega Man's, Proto Man's and a few "
        "enemies' teleports, so painting it changes theirs too.")
CHR = 0x10 + 256 * 1024
chr_tile = lambda bank, t: rom[CHR + bank * 1024 + (t & 63) * 16:CHR + bank * 1024 + (t & 63) * 16 + 16]

MODES = [  # (weapon, name, {frame name: frame id}, clips)
    (7, "Rush Coil", ["sit", "spring"], lambda f: {"sit": [[f[0], 60]], "bounce": [[f[0], 30], [f[1], 30]]}),
    (9, "Rush Marine", ["swim"], lambda f: {"swim": [[f[0], 60]]}),
    (11, "Rush Jet", ["fly 1", "fly 2"], lambda f: {"fly": [[f[0], 5], [f[1], 5]]}),
]


def build():
    objs = []
    for w, name, names, clips in MODES:
        aid = LAND[(w - 7) // 2]
        ids, dur = anim(aid)
        ids = list(dict.fromkeys(ids))
        assert len(ids) == len(names), (name, ids)
        frames = {n: {"sprites": sprites(aid, fid)} for n, fid in zip(names, ids)}
        for n, fid in tele_frames.items(): frames[n] = {"sprites": sprites(TELEPORT, fid)}
        c = clips(names); c["teleport"] = tele_clip
        if name == "Rush Jet": assert dur + 1 == 5
        others = [(m[1], f"body.{m[0]}") for m in MODES if m[0] != w]
        # tiles that are byte-identical in another Rush bank: the profile's chr_links make those copies follow each other
        used = {int(sp[0][:2], 16) for n in names for sp in frames[n]["sprites"]}
        twins = [(m[1], t) for m in MODES if m[0] != w for t in sorted(used) if t >= 0x40 and chr_tile(EB[w], t) == chr_tile(EB[m[0]], t)]
        twin_txt = "".join(f" Tile {t:02X} is the same as {nm}'s, so painting it here repaints it there too." for nm, t in twins)
        objs.append({
            "name": name, "group": "Rush", "palette": [f"body.{w}"], "home": "stage",
            "chr_banks": [0, EB[w], 10, 0],
            "note": NOTE.format(mode=name, twins=twin_txt),
            "frames": frames, "clips": c,
            "color_match": [{"label": lbl, "palette": pal} for lbl, pal in others],
        })
    return objs


if __name__ == "__main__":
    objs = build()
    if not os.environ.get("WRITE_HTML"):
        print(json.dumps(objs, indent=1, ensure_ascii=False)); sys.exit()
    path = os.path.join(REPO, "index.html"); html = open(path).read()
    head = "const MM3_PROFILE = "; i = html.index(head); j = html.index("\n", i)
    prof = json.loads(html[i + len(head):j].rstrip(";"))
    rest = [o for o in prof["objects"] if o.get("group") != "Rush"]
    at = max(k for k, o in enumerate(rest) if o.get("group") == "Weapons") + 1
    prof["objects"] = rest[:at] + objs + rest[at:]
    html = html[:i] + head + json.dumps(prof, separators=(",", ":"), ensure_ascii=False) + ";" + html[j:]
    open(path, "w").write(html)
    print(f"wrote {len(objs)} Rush objects after the weapons ({len(prof['objects'])} objects)")
