"""Castlevania (USA): raw CHR in PRG, copied to CHR-RAM by the loader at $FD23 (fixed bank).
chr_sets(): the loader's table at $FDBB. Each entry: (bank, cpu source, PPU address, length)."""
import os
ROM = open(os.environ["CV_ROM"], "rb").read()
def fixed(a): return 0x10 + 7 * 0x4000 + (a - 0xC000)
def bank_off(bank, a): return 0x10 + bank * 0x4000 + (a - 0x8000)
SET_TABLE = 0xFDBB; STAGE_SETS = 0xC8B0
def chr_sets():
    out = []
    for i in range(12):
        p = fixed(ROM[fixed(SET_TABLE + 2 * i)] | ROM[fixed(SET_TABLE + 2 * i + 1)] << 8); es = []
        while ROM[p] != 0xFF:
            r = ROM[p:p + 7]; es.append((r[0], r[1] | r[2] << 8, r[3] | r[4] << 8, r[5] | r[6] << 8)); p += 7
        out.append(es)
    return out
def stage_set(stage): return ROM[fixed(STAGE_SETS + stage)]
def ppu_map(set_ids):
    """tile 0..0x1FF -> file offset, after loading the sets in order."""
    sets = chr_sets(); m = {}
    for s in set_ids:
        for bank, src, ppu, n in sets[s]:
            for a in range(ppu, ppu + n, 16):
                if a % 16 == 0 and a + 16 <= ppu + n and a < 0x2000: m[a // 16] = bank_off(bank, src) + (a - ppu)
    return m
def tile_px(off):
    lo, hi = ROM[off:off + 8], ROM[off + 8:off + 16]
    return [[((lo[y] >> (7 - x)) & 1) | (((hi[y] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]
