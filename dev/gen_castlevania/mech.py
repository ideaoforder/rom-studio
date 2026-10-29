"""Castlevania mechanics: byte edits found by unique patterns (checked in the emulator by dev/test_castlevania_mech.py)."""
from gfx import ROM
def at(hexs, lo=0x10, hi=len(ROM), n=None):
    p = bytes.fromhex(hexs.replace(" ", "")); r = []; i = ROM.find(p, lo, hi)
    while i != -1: r.append(i); i = ROM.find(p, i + 1, hi)
    assert r and (n is None or len(r) == n) and (n is not None or len(r) == 1), (hexs, r)
    return r if n else r[0]
B6 = lambda a: 0x10 + 6 * 0x4000 + (a - 0x8000)
KIT, AIR = 0xBA40, 0xBA60  # free space at the end of bank 6 (all $FF)
assert set(ROM[B6(KIT):B6(KIT) + 0x60]) == {0xFF}
def mechanics():
    dmg = at("A9 10 A4 2B D0 0E A4 28 C0 0C B0 08 A9 0C C0 07 B0 02 A9 08 85 4B")
    hit = at("A5 45 30 05 38 E5 4B 85 45") + 5
    die = at("C6 2A D0")
    lives = [i + 1 for i in at("A9 04 85 2A", n=2)]
    hearts_use = at("A4 71 F0 FA 88 84 71") + 4
    watch = at("A5 71 38 E9 05") + 4
    hearts_use2 = at("A4 71 F0", n=2)[1] + 4; assert ROM[hearts_use2] == 0x88
    hearts0 = at("A2 05 86 71") + 1
    kit_sites = at("A9 00 8D 5B 01 85 64", n=3)   # new game, continue, after losing a life
    whip_site = at("A9 00 85 70 85 E2")           # losing a life takes the whip back to leather
    newgame_whip = at("86 28 8E 34 04 86 70") + 5   # a new game resets the whip after the kit runs
    jump = at("FB FB FD FD FD FD FD FE FE FE FF FF FF FF 00 FF 00 00 00 00 81")
    jump_site = at("A9 00 20 1E 9B", n=2)[0]             # the jump state's call to the jump-table walker
    # starting kit: JSR $BA40 at each reset site: LDA #sub STA $015B / LDA #shots STA $64 / LDA #whip STA $70 / LDA #0 RTS
    kit = B6(KIT)
    install = [{"offset": s, "hex": "2040BAEAEAEAEA"} for s in kit_sites] + [{"offset": whip_site, "hex": "2040BAEA"}, {"offset": newgame_whip, "hex": "EAEA"},
              {"offset": kit, "hex": "A9008D5B01A9008564A9008570A90060"}]
    def airpatch(limit):
        code = ("ADDC04C990D00FADF804C99BD008AD1405D0038DE007"   # first frame of a jump (pointer at the table start): clear the count
                "A5F52980F017" + ("ADE007D012" if limit else "EAEAEAEAEA") +   # new A press (and, for a double jump, none used yet)
                "A9908DDC04A99B8DF804A9008D1405EEE007"            # restart the jump table, going up
                "A9004C1E9B")
        return [{"offset": jump_site, "hex": "2060BAEAEA"}, {"offset": B6(AIR), "hex": code}]
    return [
      {"id": "invincible", "label": "Invincible", "kind": "toggle", "help": "Enemies can't take health away. They still knock you back, so watch the pits.",
       "patches": [{"offset": hit, "hex": "E900"}]},
      {"id": "lives", "label": "Infinite lives", "kind": "toggle", "help": "Losing a life doesn't count down.", "patches": [{"offset": die, "hex": "A5"}]},
      {"id": "startlives", "label": "Lives at the start", "kind": "number", "offset": lives[0], "also": lives[1:], "bias": 1, "min": 1, "max": 98,
       "help": "The P number at the top of the screen when a game starts (normally 3)."},
      {"id": "hearts", "label": "Infinite hearts", "kind": "toggle", "help": "Throwing a subweapon (or stopping time) doesn't use hearts.",
       "patches": [{"offset": hearts_use, "hex": "EA"}, {"offset": hearts_use2, "hex": "EA"}, {"offset": watch, "hex": "00"}]},
      {"id": "starthearts", "label": "Hearts at the start of each life", "kind": "number", "offset": hearts0, "min": 0, "max": 99, "help": "Normally 5."},
      {"id": "subweapon", "label": "Subweapon at the start of each life", "kind": "choice", "offset": kit + 1, "default": 0, "install": install,
       "help": "Each new game and each life starts with this. Picking up another one still replaces it.",
       "options": [{"value": 0, "label": "None (normal)"}, {"value": 8, "label": "Dagger"}, {"value": 0x0D, "label": "Axe"}, {"value": 0x0B, "label": "Holy water"},
                   {"value": 9, "label": "Cross"}, {"value": 0x0A, "label": "Stopwatch"}]},
      {"id": "shots", "label": "Shots at the start of each life", "kind": "choice", "offset": kit + 6, "default": 0, "install": install,
       "help": "Double and triple shot let you throw 2 or 3 of the subweapon at once.",
       "options": [{"value": 0, "label": "Single (normal)"}, {"value": 1, "label": "Double shot"}, {"value": 2, "label": "Triple shot"}]},
      {"id": "whip", "label": "Whip at the start of each life", "kind": "choice", "offset": kit + 10, "default": 0, "install": install,
       "help": "Normally a lost life takes you back to the leather whip.",
       "options": [{"value": 0, "label": "Leather (normal)"}, {"value": 1, "label": "Chain"}, {"value": 2, "label": "Long chain"}]},
      {"id": "damage", "label": "Damage you take", "kind": "percent", "values": [25, 50, 100, 200, 400], "default": 100,
       "help": "How much health a hit takes (normally 2 bars, 3 from stage 7, 4 from stage 12). 400% = 4 hits and you're done.",
       "bytes": [{"offset": dmg + 1, "n": 1, "mode": "mul", "min": 1, "max": 64}, {"offset": dmg + 13, "n": 1, "mode": "mul", "min": 1, "max": 64},
                 {"offset": dmg + 19, "n": 1, "mode": "mul", "min": 1, "max": 64}]},
      {"id": "jump", "label": "Jump height", "kind": "percent", "values": [50, 75, 100, 125, 150, 200], "default": 100, "help": "How high Simon jumps (the fall mirrors the rise).",
       "bytes": [{"offset": jump, "n": 20, "mode": "mul", "signed": True, "max": 7}]},  # -8 ($F8) means "hold" to the walker, so 7 a frame is the most
      {"id": "airjump", "label": "Air jumps", "kind": "choice", "default": 0, "help": "Press A again in mid-jump to jump again. Double jump gives one extra jump and resets when you land. Unlimited lets you climb the sky.",
       "options": [{"value": 0, "label": "Off (normal)"}, {"value": 1, "label": "Double jump", "patches": airpatch(True)}, {"value": 2, "label": "Unlimited", "patches": airpatch(False)}]},
    ]
