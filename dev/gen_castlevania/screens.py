"""Background screens, captured from the emulator: warp to each stage, read nametable 0 and the attributes."""
from emu import *
NT = VRAM - 0x800   # nametable 0 sits just before CHR-RAM in a cynes save state
HUD_ROWS = 6        # score / health / hearts rows at the top
def screen(stage):
    nes, f = warp(stage); st = bytes(nes.save()); nt = st[NT:NT + 0x400]
    toks, pals = [], []
    for ty in range(HUD_ROWS, 30):
        for tx in range(32):
            a = nt[0x3C0 + (ty // 4) * 8 + tx // 4]; p = (a >> (((ty % 4) // 2) * 4 + ((tx % 4) // 2) * 2)) & 3
            toks.append(0x100 + nt[ty * 32 + tx]); pals.append(p)
    return toks, pals, f
