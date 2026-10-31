"""Zelda mechanics: byte edits found by unique patterns (checked in the emulator by dev/test_zelda_mech.py).

The starting kit hooks the code that sets up a newly registered file (hearts, max bombs): it calls a little loop in free
space at the end of bank 2 that writes (slot, value) pairs into the new file's item block. Every pair starts as a harmless
vanilla write, and each knob owns one pair's value byte, so the knobs combine freely. Kit changes only reach files
registered after patching: an existing save keeps its items."""
from gfx import ROM
def at(hexs, lo=0x10, hi=len(ROM), n=None):
    p = bytes.fromhex(hexs.replace(" ", "")); r = []; i = ROM.find(p, lo, hi)
    while i != -1: r.append(i); i = ROM.find(p, i + 1, hi)
    assert r and (n is None or len(r) == n) and (n is not None or len(r) == 1), (hexs, r)
    return r if n else r[0]
B2 = lambda a: 0x10 + 2 * 0x4000 + (a - 0x8000)
HOOK = 0xAF90  # free space near the end of bank 2 (all $FF), the bank that registers names
assert set(ROM[B2(HOOK):B2(HOOK) + 0x80]) == {0xFF}

# item slots in a save file (offset from Items = $0657) and the vanilla new-file value
KIT = [("maxbombs", 0x25, 0x08), ("hearts", 0x18, 0x22), ("sword", 0x00, 0), ("bombs", 0x01, 0), ("rupees", 0x16, 0), ("keys", 0x17, 0),
       ("arrow", 0x02, 0), ("bow", 0x03, 0), ("candle", 0x04, 0), ("recorder", 0x05, 0), ("rod", 0x08, 0), ("raft", 0x09, 0),
       ("book", 0x0A, 0), ("ring", 0x0B, 0), ("ladder", 0x0C, 0), ("magickey", 0x0D, 0), ("bracelet", 0x0E, 0), ("boomerang", 0x1D, 0),
       ("magicboomerang", 0x1E, 0), ("magicshield", 0x1F, 0)]

def kit_code():
    tbl = HOOK + 0x20
    code = bytes([0x8A, 0x48, 0xA2, 0x00,                       # TXA PHA (X is the save slot) LDX #0
                  0xBD, tbl & 255, tbl >> 8, 0xC9, 0xFF, 0xF0, 0x0A,   # loop: LDA tbl,X  CMP #$FF  BEQ done
                  0xA8, 0xBD, (tbl + 1) & 255, (tbl + 1) >> 8,  # TAY  LDA tbl+1,X
                  0x91, 0xC0, 0xE8, 0xE8, 0xD0, 0xEF,           # STA ($C0),Y  INX INX  BNE loop
                  0x68, 0xAA, 0x60])                            # done: PLA TAX RTS
    assert len(code) == 24 and code[11 + 0x0A] == 0x68 and (21 - 0x11) == 4
    code = code.ljust(0x20, b"\xFF")
    table = b"".join(bytes([s, v]) for _, s, v in KIT) + b"\xFF"
    return code + table, {name: B2(tbl) + 2 * i + 1 for i, (name, _, _) in enumerate(KIT)}

def mechanics():
    reg = at("A0 18 A9 22 91 C0 C8 A9 FF 91 C0 A0 25 A9 08 91 C0") + 11   # new file: hearts, partial, then max bombs = 8
    harm = at("85 51 AD 70 06 C5 0E") + 2        # Link_BeHarmed, after the ring halves the damage: LDA HeartPartial
    dmg = at("60 02 01 80 80 01 80 80 80 80 80 01 02 80 80 01")   # ObjTypeToDamagePoints (low nibble whole hearts, high nibble 16ths)
    bomb = at("CE 58 06 A9 20")                  # DEC InvBombs when a bomb is set
    beam = at("AD 6F 06 48 29 0F 85 00 68 4A 4A 4A 4A C5 00 D0")   # sword shot only at full health
    assert ROM[beam + 17:beam + 22] == bytes.fromhex("AD7006C980") and ROM[beam + 22] == 0x90
    speed = at("A9 60 85 00 A5 10 D0") + 1       # InitLinkSpeed: quarter-pixel speed $60 = 1.5 px a frame
    code, slot = kit_code()
    install = [{"offset": reg, "hex": "20%02X%02XEAEAEA" % (HOOK & 255, HOOK >> 8)}, {"offset": B2(HOOK), "hex": code.hex().upper()}]
    def damage(f):
        out = []
        for i in range(1, 93):   # entry 0 (Link) is the RTS of the routine before the table, so it stays
            v = ROM[dmg + i]; t = (v & 0x0F) * 256 + (v & 0xF0)
            n = min(int(t * f), 0xFF0); n = max(n, 0x10) if t else 0
            out.append((n >> 8) | (n & 0xF0))
        return [{"offset": dmg + 1, "hex": bytes(out).hex().upper()}]
    def item(id_, label, help_, value=1):
        return {"id": "kit_" + id_, "label": label, "kind": "toggle", "section": "Starting kit (new files)", "help": help_, "install": install,
                "patches": [{"offset": slot[id_], "hex": "%02X" % value}]}
    def choice(id_, label, help_, options):
        return {"id": "kit_" + id_, "label": label, "kind": "choice", "section": "Starting kit (new files)", "offset": slot[id_], "default": dict(KIT_V)[id_],
                "install": install, "help": help_, "options": [{"value": v, "label": l} for v, l in options]}
    KIT_V = [(n, v) for n, _, v in KIT]
    new = " Only reaches files registered after patching."
    return [
      {"id": "invincible", "label": "Invincible", "kind": "toggle", "section": "Playing", "help": "Enemies can't take hearts away. They still knock Link back.",
       "patches": [{"offset": harm, "hex": "60EAEA"}]},
      {"id": "damage", "label": "Damage you take", "kind": "choice", "default": 1,
       "help": "How many hearts a hit takes. Normally from half a heart (Octoroks) up to 4 (Ganon). Rings still halve it.",
       "options": [{"value": 0, "label": "Half", "patches": damage(0.5)}, {"value": 1, "label": "Normal"},
                   {"value": 2, "label": "Double", "patches": damage(2)}, {"value": 3, "label": "Quadruple", "patches": damage(4)}]},
      {"id": "beam", "label": "Sword beam at any health", "kind": "toggle", "help": "The sword shoots even when Link isn't at full hearts.",
       "patches": [{"offset": beam + 15, "hex": "EAEA"}, {"offset": beam + 22, "hex": "EAEA"}]},
      {"id": "bombs", "label": "Bombs never run out", "kind": "toggle", "help": "Setting a bomb doesn't use one up (you still need at least one).",
       "patches": [{"offset": bomb, "hex": "AD5806"}]},
      {"id": "speed", "label": "Walking speed", "kind": "choice", "offset": speed, "default": 0x60,
       "help": "How fast Link walks: slow is 1 pixel a frame, normal 1.5, fast 2, zoom 2.7 (mountain stairs stay slow).",
       "options": [{"value": 0x40, "label": "Slow"}, {"value": 0x60, "label": "Normal"}, {"value": 0x80, "label": "Fast"},
                   {"value": 0xC0, "label": "Zoom"}]},
      choice("hearts", "Heart containers", "How many hearts a new file starts with (normally 3)." + new,
             [((n - 1) * 0x11, f"{n}" + (" (normal)" if n == 3 else "")) for n in range(1, 17)]),
      choice("sword", "Sword", "The sword a new file starts with." + new,
             [(0, "None (normal)"), (1, "Wooden sword"), (2, "White sword"), (3, "Magical sword")]),
      {"id": "kit_rupees", "label": "Rupees", "kind": "number", "section": "Starting kit (new files)", "offset": slot["rupees"], "default": 0, "min": 0, "max": 255,
       "install": install, "help": "Rupees in a new file's wallet (255 is the most)." + new},
      {"id": "kit_bombs", "label": "Bombs", "kind": "number", "section": "Starting kit (new files)", "offset": slot["bombs"], "default": 0, "min": 0, "max": 8,
       "install": install, "help": "Bombs a new file starts with (8 is the most the bag holds)." + new},
      {"id": "kit_keys", "label": "Keys", "kind": "number", "section": "Starting kit (new files)", "offset": slot["keys"], "default": 0, "min": 0, "max": 9,
       "install": install, "help": "Keys a new file starts with." + new},
      choice("arrow", "Arrows", "Arrows need the bow too, and each shot costs a rupee." + new, [(0, "None (normal)"), (1, "Wooden arrows"), (2, "Silver arrows")]),
      item("bow", "Bow", "Start with the bow (it needs arrows)." + new),
      choice("candle", "Candle", "The candle lights dark rooms and burns bushes." + new, [(0, "None (normal)"), (1, "Blue candle"), (2, "Red candle")]),
      choice("ring", "Ring", "Rings halve (blue) or quarter (red) the damage Link takes." + new, [(0, "None (normal)"), (1, "Blue ring"), (2, "Red ring")]),
      item("boomerang", "Boomerang", "Start with the wooden boomerang." + new),
      item("magicboomerang", "Magical boomerang", "Start with the magical boomerang." + new),
      item("magicshield", "Magical shield", "Start with the big shield." + new),
      item("recorder", "Recorder", "The whistle: warps between dungeons you've beaten." + new),
      item("rod", "Magical rod", "Start with the magical rod." + new),
      item("book", "Book of Magic", "Makes the rod's shots burn." + new),
      item("raft", "Raft", "Start with the raft." + new),
      item("ladder", "Stepladder", "Start with the stepladder." + new),
      item("magickey", "Magical key", "Opens every locked door." + new),
      item("bracelet", "Power bracelet", "Lets Link push some boulders." + new),
    ]
