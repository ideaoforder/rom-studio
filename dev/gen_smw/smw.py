"""Super Mario World (USA): ROM facts shared by the generator. Addresses are SNES (LoROM) labels from SMWDisX's SMW_U.sym."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "snes"))
from lz2 import decode, encode  # noqa: E402
ROM_PATH = os.environ.get("SMW_ROM") or sys.exit("Set SMW_ROM to your Super Mario World (USA) .sfc")
ROM = open(ROM_PATH, "rb").read()
if len(ROM) % 1024 == 512: ROM = ROM[512:]
def F(a): return ((a >> 16) & 0x7F) * 0x8000 + (a & 0x7FFF)       # LoROM SNES address -> file offset
def A(o): return ((o >> 15) << 16) | 0x8000 | (o & 0x7FFF)
GFX_LO, GFX_HI, GFX_BANK = 0x00B992, 0x00B9C4, 0x00B9F6             # GFXFilesLow/High/Bank (files $00-$31)
LOAD_32_33 = 0x00B888                                                # CODE_00B888: LDY #GFX33 / LDA #bank ... LDA #GFX32
def gfx_addr(f): return ROM[F(GFX_BANK) + f] << 16 | ROM[F(GFX_HI) + f] << 8 | ROM[F(GFX_LO) + f]
ADDR = {f"GFX{f:02X}": gfx_addr(f) for f in range(0x32)}
ADDR["GFX32"], ADDR["GFX33"] = 0x088000, 0x08BFC0
FILES = {k: decode(ROM, F(a)) for k, a in ADDR.items()}               # id -> (data, compressed size)
BPP = {k: 4 if k == "GFX32" else 3 for k in ADDR}
# Palettes (LoadPalette, $00:AFxx): CGRAM byte destinations and sources
STANDARD, SPRITE_SETS, PLAYER, BERRY, PAL_INDEX = 0x00B250, 0x00B318, 0x00B2C8, 0x00B674, 0x00ABD3
FG_SETS, BG_SETS, BACK_AREA, STATUS = 0x00B190, 0x00B0B0, 0x00B0A0, 0x00B170

def to4(t24, hi):  # the game's 3bpp -> 4bpp upload; "hi" sets plane 3 on every non-zero pixel (colours 8-15)
    out = bytearray(t24[:16])
    for y in range(8): out += bytes([t24[16 + y], (t24[2 * y] | t24[2 * y + 1] | t24[16 + y]) if hi else 0])
    return bytes(out)
def provenance_index():
    """4bpp VRAM tile bytes -> (file, tile, hi) for every tile in every file (first match wins, GFX32 first)"""
    idx = {}
    d = FILES["GFX32"][0]
    for t in range(len(d) // 32): idx.setdefault(d[32 * t:32 * t + 32], ("GFX32", t, 0))
    for k, (d, _) in FILES.items():
        if k == "GFX32": continue
        for t in range(len(d) // 24):
            for h in (0, 1): idx.setdefault(to4(d[24 * t:24 * t + 24], h), (k, t, h))
    return idx

def cgram_sources(sprite_pal=0, fg_pal=0, bg_pal=0, player=0):
    """CGRAM word index (0-255) -> ROM file offset of the colour LoadPalette (and the player palette) puts there"""
    src = {}
    def load(base, dest, cols, rows):
        p = F(base)
        for r in range(rows):
            for c in range(cols): src[dest // 2 + 16 * r + c] = p; p += 2
    load(STATUS, 0x10, 8, 2)
    load(STANDARD, 0x84, 6, 10)
    src[0] = F(BACK_AREA)  # colour 0 comes from BackAreaColors[header]; set per level by the caller
    load(FG_SETS + ROM[F(PAL_INDEX) + fg_pal], 0x44, 6, 2)
    load(SPRITE_SETS + ROM[F(PAL_INDEX) + sprite_pal], 0x1C4, 6, 2)
    load(BG_SETS + ROM[F(PAL_INDEX) + bg_pal], 0x04, 6, 2)
    load(BERRY, 0x52, 7, 3)
    load(BERRY, 0x132, 7, 3)
    load(PLAYER + 20 * player, 0x10C, 10, 1)
    return src
