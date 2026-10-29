"""Metasprites, as the drawer at $80D6 in bank 0 reads them. Pointer tables: $8FBE (codes 00-7F) and $90BE (80-FF), bank 0.
Entry: count, then parts. Part: y byte (signed y = byte>>1 arithmetic; bit 0 = reuse the previous part's attribute),
tile, [attr], x. $80 lo hi = continue in a shared list, $81 = return from it. Sprites are 8x16 (PPUCTRL $B0)."""
from gfx import ROM, bank_off
def s8(v): return v - 256 if v > 127 else v
def ptr(code):
    t = bank_off(0, 0x8FBE if code < 0x80 else 0x90BE) + (code * 2 & 0xFF)
    return ROM[t] | ROM[t + 1] << 8
def sprite(code):
    a = ptr(code)
    if not 0x8000 <= a < 0xC000: return None
    p = bank_off(0, a); n = ROM[p]; p += 1; parts = []; attr = 0; ret = None; guard = 0
    while n and guard < 64:
        guard += 1; b = ROM[p]; p += 1
        if b == 0x80: ret = p + 2; p = bank_off(0, ROM[p] | ROM[p + 1] << 8); continue
        if b == 0x81: p = ret; continue
        dy = s8(b) >> 1; t = ROM[p]; p += 1
        if not b & 1: attr = ROM[p]; p += 1
        dx = s8(ROM[p]); p += 1
        parts.append((dy, t, attr, dx)); n -= 1
    return parts
