"""SMB2 mechanics (checked in cynes by dev/test_smb2_mech.py). Offsets from the disassembly's labels + byte checks."""
import os
from labels import off
R = open(os.environ["SMB2_ROM"], "rb").read()
def at(name, plus, want):
    o = off(name, plus); assert R[o:o + len(bytes.fromhex(want))] == bytes.fromhex(want), (name, R[o:o + 8].hex()); return o
def find(hexs, n=1):
    p = bytes.fromhex(hexs); r = []; i = R.find(p)
    while i != -1: r.append(i); i = R.find(p, i + 1)
    assert len(r) == n, (hexs, r); return r
FIX = lambda a: 0x10 + 7 * 0x4000 + (a - 0xC000)
HOOK = 0xFB40  # unused space in the original ($FB36-$FDFF, all $FF)
assert set(R[FIX(0xFB36):FIX(0xFE00)]) == {0xFF}
STATS = [off(n) for n in ("MarioStats", "ToadStats", "LuigiStats", "PrincessStats")]  # 23 bytes each, copied to RAM per character
JUMP, FLOAT, GRAV, RUN = range(6, 12), 13, (14, 15), (17, 18, 20, 21)
def mechanics():
    hurt = [i + 4 for i in find("ADC20438E910", 2)]          # DamagePlayer and PlayerTileCollision_HurtPlayer: SBC #$10 (one heart)
    lose = at("LoseALife", 6, "CEED04")                    # DEC ExtraLives
    lives = at("ContinueGame", 0, "A9038DED04") + 1        # LDA #$03 ; STA ExtraLives
    site = at("sub_BANK0_8C1A", 3, "A599D042")             # LDA PlayerInAir ; BNE ResetPartialCrouchJumpTimer ($8C63)
    princess_float = R[STATS[3] + FLOAT]
    def air(limit):
        code = ("A599D0048D5D0560"                            # on the ground: clear the count (FOR RENT $055D), carry on
                "24F51010" + ("AD5D05D00B" if limit else "EAEAEAEAEA") +  # in the air: new A press (and, for a double jump, none used)
                "EE5D05" "20998C" "A9018D0406"                 # count it, PlayerStartJump, jump sound
                "68684C638C")                                  # back to the in-air path
        return [{"offset": site, "hex": "2040FBEA"}, {"offset": FIX(HOOK), "hex": code}]
    b = lambda idx: [{"offset": s + i, "n": 1, "mode": "mul", "signed": True, "max": 0x7F} for s in STATS for i in idx]
    return [
      {"id": "invincible", "label": "Invincible", "kind": "toggle", "help": "Enemies and spikes can't take a heart away. Falling off the screen still loses a life.",
       "patches": [{"offset": o + 1, "hex": "00"} for o in hurt]},
      {"id": "lives", "label": "Infinite lives", "kind": "toggle", "help": "Losing a life doesn't count down.", "patches": [{"offset": lose, "hex": "AD"}]},
      {"id": "startlives", "label": "Lives at the start", "kind": "number", "offset": lives, "min": 1, "max": 99, "help": "Normally 3 (also what Continue gives you)."},
      {"id": "jump", "label": "Jump height", "kind": "percent", "values": [50, 75, 100, 125, 150, 200], "default": 100, "help": "How high everyone jumps (standing, running, super jump, carrying).",
       "bytes": [{"offset": s + i, "n": 1, "mode": "sqrt", "signed": True, "max": 0x7F} for s in STATS for i in JUMP]},
      {"id": "airjump", "label": "Air jumps", "kind": "choice", "default": 0, "help": "Press A again in mid-air to jump again, as high as a normal jump. Double jump gives one extra jump and resets when you land. Unlimited lets you climb the sky.",
       "options": [{"value": 0, "label": "Off (normal)"}, {"value": 1, "label": "Double jump", "patches": air(True)}, {"value": 2, "label": "Unlimited", "patches": air(False)}]},
      {"id": "float", "label": "Everyone can float", "kind": "toggle", "help": "Mario, Luigi and Toad hover like the Princess when you hold A at the top of a jump.",
       "patches": [{"offset": s + FLOAT, "hex": f"{princess_float:02X}"} for s in STATS[:3]]},
      {"id": "gravity", "label": "Gravity", "kind": "percent", "values": [25, 50, 75, 100, 150, 200], "default": 100, "help": "How hard everyone falls. Low = floaty.",
       "bytes": [{"offset": s + i, "n": 1, "mode": "mul", "min": 1} for s in STATS for i in GRAV]},
      {"id": "speed", "label": "Run speed", "kind": "percent", "values": [75, 100, 125, 150, 200], "default": 100, "help": "Top running speed, with or without something in your hands.", "bytes": b(RUN)},
    ]
