"""Super Mario World mechanics: byte edits found by pattern (checked in the emulator by dev/test_smw_mech.py)."""
from smw import ROM, F
def at(hexs, lo=0, hi=0x80000, n=None):
    p = bytes.fromhex(hexs.replace(" ", "")); r = []; i = ROM.find(p, lo, hi)
    while i != -1: r.append(i); i = ROM.find(p, i + 1, hi)
    assert r and (len(r) == n if n else len(r) == 1), (hexs, r)
    return r if n else r[0]
FREE = F(0x00FF93)   # unused bytes at the end of bank 00 ($FF93-$FFBF, all $FF in the US ROM)
assert set(ROM[FREE:FREE + 0x2D]) == {0xFF}
def mechanics():
    hurt = F(0x00F5B7); assert ROM[hurt:hurt + 4] == bytes.fromhex("A571D0")[:3] + ROM[hurt + 3:hurt + 4]   # HurtMario: LDA $71 / BNE
    lives_dec = at("CE BE 0D 10")                  # MarioDeathAni: DEC PlayerLives / BPL
    lives0 = at("A9 04 9D B4 0D CA 10 FA") + 1     # new game: LDA #4 / STA SavedPlayerLives,X loop
    timer = at("CE 30 0F 10")                      # DEC InGameTimerFrames / BPL
    jump = F(0x00D2BD); assert ROM[jump:jump + 4] == bytes.fromhex("B0B6AEB4")
    death = at("64 19 A9 3E 8D E0 13")             # MarioDeathAni: STZ Powerup / LDA #$3E / STA PlayerPose
    newgame = at("64 19 9C C2 0D")                 # new game: STZ Powerup / STZ PlayerItembox
    h1, h2 = FREE, FREE + 8
    a1, a2 = 0x8000 | (h1 & 0x7FFF), 0x8000 | (h2 & 0x7FFF)
    install = [{"offset": death, "hex": "20%02X%02XEA" % (a1 & 255, a1 >> 8)}, {"offset": h1, "hex": "A90085 19A93E60".replace(" ", "")},
               {"offset": newgame, "hex": "20%02X%02XEAEA" % (a2 & 255, a2 >> 8)}, {"offset": h2, "hex": "A900 8519 9CC20D 60".replace(" ", "")}]
    return [
      {"id": "invincible", "label": "Invincible", "kind": "toggle", "section": "Playing",
       "help": "Enemies can't hurt Mario. Pits, lava and the timer still can.", "patches": [{"offset": hurt, "hex": "6B"}]},
      {"id": "lives", "label": "Infinite lives", "kind": "toggle", "help": "Losing a life doesn't count down.", "patches": [{"offset": lives_dec, "hex": "AD"}]},
      {"id": "startlives", "label": "Lives at the start", "kind": "number", "offset": lives0, "bias": -1, "min": 1, "max": 99,
       "help": "The number next to MARIO when a new game starts (normally 5)."},
      {"id": "time", "label": "Timer stands still", "kind": "toggle", "help": "The level timer never counts down.", "patches": [{"offset": timer, "hex": "AD"}]},
      {"id": "jump", "label": "Jump height", "kind": "percent", "values": [50, 75, 100, 125, 150], "default": 100,
       "help": "How fast Mario takes off (normal and spin jumps). 150% clears most of a screen.",
       "bytes": [{"offset": jump, "n": 16, "mode": "sqrt", "signed": True, "max": 127}]},
      {"id": "power", "label": "Start every life as", "kind": "choice", "offset": h1 + 1, "also": [h2 + 1], "default": 0, "install": install,
       "help": "A new game and every life after losing one start with this. Getting hit still shrinks Mario.",
       "options": [{"value": 0, "label": "Small Mario (normal)"}, {"value": 1, "label": "Super Mario"}, {"value": 2, "label": "Cape Mario"}, {"value": 3, "label": "Fire Mario"}]},
    ]
def presets():
    return {"Normal": {}, "Easy": {"startlives": 20, "power": 1}, "Super": {"invincible": True, "lives": True, "time": True, "power": 2, "jump": 125},
            "Moon jump": {"jump": 150, "power": 2}}
