"""Screens from the emulator: overworld rooms (a copy of the ROM with LevelInfoOW's start room changed) and each level's
entrance (game mode 2 with CurLevel set). Playfield = nametable rows 8-29; nametable 0 and CHR-RAM are read from cynes states."""
import os, json, tempfile
import cynes as C, numpy as np
from gfx import ROM, LEVELINFO
S, A, SEL = C.NES_INPUT_START, C.NES_INPUT_A, C.NES_INPUT_SELECT
VRAM, NT = 994, 17378
def run(n, k, c=0):
    for _ in range(k): n.controller = c; n.step(1)
def boot(path):  # title -> register a name -> start file 1
    n = C.NES(path)
    for k, c in [(120, 0), (5, S), (80, 0), (5, S), (40, 0)] + [(5, A), (15, 0)] * 3 + [(5, SEL), (15, 0)] * 3 + [(5, S), (60, 0), (5, S), (300, 0)]:
        run(n, k, c)
    return n
def grab(n):
    st = bytes(n.save()); nt = st[NT:NT + 0x400]; toks, pals = [], []
    for ty in range(8, 30):
        for tx in range(32):
            a = nt[0x3C0 + (ty // 4) * 8 + tx // 4]; p = (a >> (((ty % 4) // 2) * 4 + ((tx % 4) // 2) * 2)) & 3
            toks.append(0x100 + nt[ty * 32 + tx]); pals.append(p)
    return toks, pals, st[VRAM:VRAM + 0x2000]
OW_ROOMS = [0x77, 0x76, 0x78, 0x67, 0x37, 0x45, 0x22, 0x0A]
def all_screens():
    out = {}; tmp = tempfile.mkdtemp()
    for room in OW_ROOMS:
        b = bytearray(ROM); b[LEVELINFO["ow"] + 0x2F] = room; p = f"{tmp}/ow{room:02X}.nes"; open(p, "wb").write(b)
        n = boot(p); out[f"ow:{room:02X}"] = grab(n)[:2]
    n0 = boot(os.environ["ZELDA_ROM"]); base = n0.save()
    for L in range(1, 10):
        n0.load(base); n0[0x10] = L; n0[0x12] = 2; n0[0x11] = 0; n0[0x13] = 0; run(n0, 300)
        t, p, chr_ = grab(n0); out[f"L{L}"] = (t, p); out[f"L{L}:chr"] = chr_.hex()
    return out
