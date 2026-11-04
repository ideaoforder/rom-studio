"""Mega Man 7 mechanics: byte edits found by pattern (checked in the emulator by dev/test_mm7_mech.py)."""
from mm7 import ROM
def at(hexs, n=None):
    p = bytes.fromhex(hexs.replace(" ", "")); r = []; i = ROM.find(p)
    while i != -1: r.append(i); i = ROM.find(p, i + 1)
    assert r and (len(r) == n if n else len(r) == 1), (hexs, r)
    return r if n else r[0]
FREE = 0x7BA0          # unused bytes in bank $C0 ($C0:7B96-$7FFF are all $FF)
assert set(ROM[0x7B96:0x8000]) == {0xFF}
KIT_AT, DJ_AT = FREE, FREE + 0xA0
FLAG = (0xF0, 0xFF, 0x7F)   # $7F:FFF0, unused WRAM: double-jump state
def asm(parts):
    """tiny assembler: parts are bytes or ("label",) / ("br", opcode, label); returns bytes"""
    pos, labels, out = 0, {}, []
    for p in parts:
        if isinstance(p, tuple) and p[0] == "label": labels[p[1]] = pos
        elif isinstance(p, tuple): pos += 2
        else: pos += len(p)
    pos = 0
    for p in parts:
        if isinstance(p, tuple) and p[0] == "label": continue
        if isinstance(p, tuple): out += [p[1], (labels[p[2]] - (pos + 2)) & 255]; pos += 2
        else: out += list(p); pos += len(p)
    return bytes(out)
def double_jump():
    """the jump state ($C1:12A1) starts with LDX $03 / BNE (substate 0 = take off). JSL here instead: in mid-air, a new
    B press with the jump unused sets substate 0 again, so the game's own take-off code runs once more; otherwise the
    return address is moved to the BNE's target. A fresh take-off from the ground clears the flag."""
    site = at("A6 03 D0 25 C2 20 A5 5B 85 1A")
    flag = bytes(FLAG); a = 0xC00000 | DJ_AT
    code = asm([b"\xA5\x03", ("br", 0xF0, "fresh"),                     # LDA $03 / BEQ fresh
                b"\xA5\x45\x29\x80", ("br", 0xF0, "air"),               # LDA $45 (new presses) / AND #$80 (B) / BEQ air
                b"\xAF" + flag, ("br", 0xD0, "air"),                      # LDA flag / BNE air   (EA EA = unlimited)
                b"\xA9\x81\x8F" + flag + b"\x64\x03\xA6\x03\x6B",       # flag = $81 / STZ $03 / LDX $03 / RTL
                ("label", "air"),
                b"\xA3\x01\x18\x69\x25\x83\x01\xA3\x02\x69\x00\x83\x02",  # return address += $25 (the BNE's target)
                b"\xA6\x03\x6B",                                         # LDX $03 / RTL
                ("label", "fresh"),
                b"\xAF" + flag, ("br", 0x10, "clear"), b"\x29\x7F", ("br", 0x80, "store"),   # our restart: keep "used"
                ("label", "clear"), b"\xA9\x00", ("label", "store"), b"\x8F" + flag,        # from the ground: clear
                b"\xA6\x03\x6B"])
    bne = code.index(b"\xAF" + flag) + 4
    assert code[bne] == 0xD0
    # falling (state 8) has its own handler: its substate-2 entry ($C1:1362, table at $C1:1321) goes through a trampoline
    # in bank C1's free bytes that asks a second hook whether to take off again (carry set: state 6, substate 0)
    fall = DJ_AT + len(code); fa = 0xC00000 | fall
    fcode = asm([b"\xA5\x45\x29\x80", ("br", 0xF0, "no"),                  # LDA $45 / AND #$80 / BEQ no
                 b"\xAF" + flag, ("br", 0xD0, "no"),                       # LDA flag / BNE no   (EA EA = unlimited)
                 b"\xA9\x81\x8F" + flag + b"\xA9\x06\x85\x02\x64\x03\x38\x6B",   # flag / state 6 / substate 0 / SEC / RTL
                 ("label", "no"), b"\x18\x6B"])                            # CLC / RTL
    fbne = fall + fcode.index(b"\xAF" + flag) + 4
    table = at("A6 03 7C 21 13") + 5; assert ROM[table + 2:table + 4] == b"\x62\x13"
    tramp = 0x17F60; assert set(ROM[tramp:tramp + 0xA0]) == {0xFF}
    tcode = bytes([0x22, fa & 255, (fa >> 8) & 255, fa >> 16, 0xB0, 0x03, 0x4C, 0x62, 0x13, 0x60])
    install = [{"offset": site, "hex": "22%02X%02X%02X" % (a & 255, (a >> 8) & 255, a >> 16)}, {"offset": DJ_AT, "hex": (code + fcode).hex().upper()},
               {"offset": tramp, "hex": tcode.hex().upper()}, {"offset": table + 2, "hex": "%02X%02X" % (tramp & 255, (tramp >> 8) & 255)}]
    return install, [DJ_AT + bne, fbne]
def kit():
    """new game: the item reset at $C0:0C1E (game-start step 1; a password skips it) ends STZ $0BA6 / STZ $0BA7 / RTS.
    Those two STZ become JSL to: the same two STZ, then LDA #v / STA addr lines (LDA/ORA/STA for item bits), RTL.
    Each knob owns the v byte(s) of its own lines; untouched, every line writes what a new game has anyway."""
    site = at("9C A6 0B 9C A7 0B 60"); a = 0xC00000 | KIT_AT
    lines, own = [bytes.fromhex("9CA60B9CA70B")], {}
    def put(key, addr, v): own.setdefault(key, []).append(len(b"".join(lines)) + 1); lines.append(bytes([0xA9, v, 0x8D, addr & 255, addr >> 8]))
    def bit(key, addr): own.setdefault(key, []).append(len(b"".join(lines)) + 4); lines.append(bytes([0xAD, addr & 255, addr >> 8, 0x09, 0, 0x8D, addr & 255, addr >> 8]))
    put("rcoil", 0x0B9B, 0x80)
    for k in range(1, 9): put("weapons", 0x0B83 + 2 * k, 0)
    put("rsearch", 0x0B97, 0); put("rjet", 0x0B99, 0); put("adaptor", 0x0B9F, 0)
    put("etanks", 0x0BA0, 0); put("wtanks", 0x0BA1, 0); put("stank", 0x0BA2, 0)
    put("bolts", 0x0BA6, 0); put("bolts", 0x0BA7, 0)
    for key in ("balancer", "exit", "beat"): bit(key, 0x0BA4)
    code = b"".join(lines) + b"\x6B"
    off = {k: [KIT_AT + o for o in v] for k, v in own.items()}
    install = [{"offset": site, "hex": "22%02X%02X%02XEAEA" % (a & 255, (a >> 8) & 255, a >> 16)}, {"offset": KIT_AT, "hex": code.hex().upper()}]
    assert len(code) <= DJ_AT - KIT_AT
    return install, off
def mechanics():
    touch = at("AD 2E 0C 38 E5 31 B0 02 A9 00 8D 2E 0C") + 3          # LDA health / SEC / SBC $31 (contact damage)
    hits = [i + 3 for i in at("AD 2E 0C 38 ED 00 00 10 02 A9 00 8D 2E 0C", n=3)]   # three more: SBC $0000 (shots, hazards)
    lives_dec = at("AD 81 0B F0 04 CE 81 0B") + 5                       # LDA lives / BEQ / DEC lives
    lives0 = [i + 1 for i in at("A9 02 8D 81 0B", n=3)]                   # LDA #2 / STA lives: new game, continue, password
    jump = at("A9 40 85 1C C2 20 A9 F4 05 85 5B")         # Mega Man's setup: gravity $40, jump speed $05F4
    dj_install, dj_bne = double_jump()
    kit_install, K = kit()
    def toggle(id_, label, help_, offs, v):
        return {"id": id_, "label": label, "kind": "toggle", "section": "Start a new game with", "install": kit_install, "help": help_,
                "patches": [{"offset": o, "hex": "%02X" % v} for o in offs]}
    def count(id_, label, help_, offs, mx):
        return {"id": id_, "label": label, "kind": "number", "section": "Start a new game with", "offset": offs[0], "also": offs[1:],
                "default": 0, "min": 0, "max": mx, "install": kit_install, "help": help_}
    new = " Only reaches games started with GAME START, not passwords."
    knobs = [
      {"id": "jump", "label": "Jump height", "kind": "percent", "section": "Playing", "values": [50, 75, 100, 125, 150, 200], "default": 100,
       "help": "How high Mega Man jumps.", "words": [{"lo": jump + 7, "hi": jump + 8, "mode": "sqrt", "max": 0x7FFF}]},
      {"id": "gravity", "label": "Gravity", "kind": "percent", "values": [50, 75, 100, 150], "default": 100,
       "help": "How fast Mega Man falls back down (lower = floatier).", "bytes": [{"offset": jump + 1, "n": 1, "mode": "mul", "min": 8, "max": 0x7F}]},
      {"id": "airjump", "label": "Air jumps", "kind": "choice", "default": 0,
       "help": "Press jump again in mid-air. Double jump gives one more and resets when you next jump from the ground.",
       "options": [{"value": 0, "label": "Off (normal)"}, {"value": 1, "label": "Double jump", "patches": dj_install},
                   {"value": 2, "label": "Unlimited", "patches": dj_install + [{"offset": o, "hex": "EAEA"} for o in dj_bne]}]},
      toggle("kit_weapons", "All robot master weapons", "Freeze Cracker, Thunder Bolt, Junk Shield, Scorch Wheel, Slash Claw, Noise Crush, Danger Wrap and Wild Coil, full." + new, K["weapons"], 0x9C),
      toggle("kit_adaptor", "Super Adaptor (Rush Adapt)", "Mega Man can fly a little and fire his rocket fist." + new, K["adaptor"], 0x9C),
      toggle("kit_rjet", "Rush Jet", "Rush turns into a jet Mega Man can ride." + new, K["rjet"], 0x9C),
      toggle("kit_rsearch", "Rush Search", "Rush digs up items." + new, K["rsearch"], 0x9C),
      toggle("kit_balancer", "Energy Balancer", "Weapon energy you pick up fills the emptiest weapon." + new, K["balancer"], 0x80),
      toggle("kit_exit", "Exit", "Leave a stage you've already beaten from the menu." + new, K["exit"], 0x20),
      toggle("kit_beat", "Beat", "The bird who rescues Mega Man from pits." + new, K["beat"], 0x40),
      count("kit_etanks", "Energy tanks", "Refill Mega Man's energy from the menu (4 is the most)." + new, K["etanks"], 4),
      count("kit_wtanks", "Weapon tanks", "Refill a weapon from the menu (4 is the most)." + new, K["wtanks"], 4),
      count("kit_stank", "Super tank", "Refills everything (1 is the most)." + new, K["stank"], 1),
      {"id": "kit_bolts", "label": "Bolts", "kind": "choice", "section": "Start a new game with", "default": 0, "install": kit_install,
       "help": "Money for Auto's shop." + new,
       "options": [{"value": 0, "label": "None (normal)"}] + [{"value": n, "label": str(n), "patches": [
           {"offset": K["bolts"][0], "hex": "%02X" % (n & 255)}, {"offset": K["bolts"][1], "hex": "%02X" % (n >> 8)}]} for n in (100, 300, 500, 999)]},
      {"id": "invincible", "label": "Invincible", "kind": "toggle",
       "help": "Enemies and their shots can't take energy. Spikes and pits still can.",
       "patches": [{"offset": touch, "hex": "38E900"}] + [{"offset": h, "hex": "38E900EA"} for h in hits]},
      {"id": "lives", "label": "Infinite lives", "kind": "toggle", "help": "Losing a life doesn't count down.",
       "patches": [{"offset": lives_dec, "hex": "AD"}]},
      {"id": "startlives", "label": "Lives at the start", "kind": "number", "offset": lives0[0], "also": lives0[1:], "min": 0, "max": 9,
       "help": "The number on Mega Man's 1-up icon when a game starts or continues (normally 2)."},
    ]
    return [k for k in knobs if not k["id"].startswith("kit_")] + [k for k in knobs if k["id"].startswith("kit_")]
def presets():
    kit = {"kit_weapons": True, "kit_adaptor": True, "kit_rjet": True, "kit_rsearch": True, "kit_balancer": True, "kit_exit": True,
           "kit_beat": True, "kit_etanks": 4, "kit_wtanks": 4, "kit_stank": 1, "kit_bolts": 999}
    return {"Normal": {}, "Easy": {"startlives": 9, "kit_etanks": 4, "kit_balancer": True}, "Ready to go": kit,
            "Super Mega Man": {**kit, "invincible": True, "lives": True, "startlives": 9, "airjump": 1, "jump": 125}}
