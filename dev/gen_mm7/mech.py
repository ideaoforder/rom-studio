"""Mega Man 7 mechanics: byte edits found by pattern (checked in the emulator by dev/test_mm7_mech.py)."""
from mm7 import ROM
def at(hexs, n=None):
    p = bytes.fromhex(hexs.replace(" ", "")); r = []; i = ROM.find(p)
    while i != -1: r.append(i); i = ROM.find(p, i + 1)
    assert r and (len(r) == n if n else len(r) == 1), (hexs, r)
    return r if n else r[0]
def mechanics():
    touch = at("AD 2E 0C 38 E5 31 B0 02 A9 00 8D 2E 0C") + 3          # LDA health / SEC / SBC $31 (contact damage)
    hits = [i + 3 for i in at("AD 2E 0C 38 ED 00 00 10 02 A9 00 8D 2E 0C", n=3)]   # three more: SBC $0000 (shots, hazards)
    lives_dec = at("AD 81 0B F0 04 CE 81 0B") + 5                       # LDA lives / BEQ / DEC lives
    lives0 = [i + 1 for i in at("A9 02 8D 81 0B", n=3)]                   # LDA #2 / STA lives: new game, continue, password
    return [
      {"id": "invincible", "label": "Invincible", "kind": "toggle", "section": "Playing",
       "help": "Enemies and their shots can't take energy. Spikes and pits still can.",
       "patches": [{"offset": touch, "hex": "38E900"}] + [{"offset": h, "hex": "38E900EA"} for h in hits]},
      {"id": "lives", "label": "Infinite lives", "kind": "toggle", "help": "Losing a life doesn't count down.",
       "patches": [{"offset": lives_dec, "hex": "AD"}]},
      {"id": "startlives", "label": "Lives at the start", "kind": "number", "offset": lives0[0], "also": lives0[1:], "min": 0, "max": 9,
       "help": "The number on Mega Man's 1-up icon when a game starts or continues (normally 2)."},
    ]
def presets():
    return {"Normal": {}, "Easy": {"startlives": 9}, "Unstoppable": {"invincible": True, "lives": True, "startlives": 9}}
