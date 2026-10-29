"""Emulator helpers: boot, warp to a stage (set the stage + checkpoint, then lose a life), read CHR-RAM from save states."""
import cynes, numpy as np, os
C = cynes; ROMPATH = os.environ["CV_ROM"]
VRAM = 11234  # CHR-RAM offset inside a cynes save state (found by matching the title-screen tiles)
def run(nes, n, k=0):
    f = None
    for _ in range(n): nes.controller = k; f = nes.step(1)
    return np.asarray(f).copy()
def boot(path=ROMPATH):
    nes = C.NES(path); run(nes, 200); run(nes, 5, C.NES_INPUT_START); run(nes, 400); return nes
def warp(stage, path=ROMPATH, settle=400, nes=None):
    """Jump to a stage the way the game restarts one (state $0C, step 5 runs the stage graphics load from $C8B0)."""
    nes = nes or boot(path); run(nes, 100)
    nes[0x28] = stage; nes[0x29] = stage; nes[0x18] = 0x0C; nes[0x19] = 5
    f = run(nes, settle); return nes, f
def chr_ram(nes):
    st = bytes(nes.save()); return st[VRAM:VRAM + 0x2000]
