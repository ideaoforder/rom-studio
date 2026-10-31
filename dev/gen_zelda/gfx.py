"""The Legend of Zelda (USA) (Rev 1): CHR-RAM loaded from raw pattern blocks in PRG (banks 2 and 3).
Block offsets are the aldonunez/zelda1-disassembly's bins.xml (PRG0); Rev 1 keeps them at the same places (checked against
the game's CHR-RAM in cynes). PPU destinations come from TransferCommonPatterns / TransferLevelPatternBlocks."""
import os
ROM = open(os.environ["ZELDA_ROM"], "rb").read()
F = lambda prg0_off: 0x10 + prg0_off
# DemoSpritePatterns go to $0700-$0FFF on the title screen; levels overwrite from $08E0, so $0700-$08DF (sword swing,
# arrows, ...) stays from that load for the whole game.
COMMON = [(F(19892), 0x0700, 0x1E0), (F(32895), 0x0000, 0x700), (F(34687), 0x1000, 0x700), (F(36479), 0x1F20, 0xE0)]
OW = [(F(51515), 0x1700, 0x820), (F(53595), 0x08E0, 0x720)]
UWBG, UWSP = F(49435), F(56507)
SPECIAL = {"127": F(56763), "358": F(55419), "469": F(55963)}
BOSS = {"1257": F(57307), "3468": F(58331), "9": F(59355)}
LEVEL_SPECIAL = {1: "127", 2: "127", 3: "358", 4: "469", 5: "358", 6: "469", 7: "127", 8: "358", 9: "469"}  # LevelPatternBlockSrcAddrs
LEVEL_BOSS = {1: "1257", 2: "1257", 3: "3468", 4: "3468", 5: "1257", 6: "3468", 7: "1257", 8: "3468", 9: "9"}  # BossPatternBlockSrcAddrs
def blocks(area):
    if area == "ow": return COMMON + OW
    L = int(area[1:])
    return COMMON + [(UWBG, 0x1700, 0x820), (UWSP, 0x08E0, 0x100), (SPECIAL[LEVEL_SPECIAL[L]], 0x09E0, 0x220), (BOSS[LEVEL_BOSS[L]], 0x0C00, 0x400)]
def ppu_map(area):
    m = {}
    for src, ppu, n in blocks(area):
        for a in range(ppu, ppu + n, 16): m[a // 16] = src + (a - ppu)
    return m
LEVELINFO = {"ow": F(103168), **{f"L{i}": F(103420 + 252 * (i - 1)) for i in range(1, 10)}}
def palettes(area):  # LevelInfo starts with a PPU transfer: 3F 00 20, then 16 background + 16 sprite colors
    o = LEVELINFO[area] + 3; assert ROM[o - 3:o] == bytes([0x3F, 0x00, 0x20]); return o
def tile_px(off):
    lo, hi = ROM[off:off + 8], ROM[off + 8:off + 16]
    return [[((lo[y] >> (7 - x)) & 1) | (((hi[y] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]
