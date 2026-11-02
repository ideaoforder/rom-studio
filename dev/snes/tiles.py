"""Python twin of snes/lib/tiles.js: SNES planar tiles (bpp 2, 3 = SMW's 24-byte form, 4, 8) <-> 8x8 colour indexes."""
BYTES = {2: 16, 3: 24, 4: 32, 8: 64}
def _at(bpp, y, p): return (2 * y + p if p < 2 else 16 + y) if bpp == 3 else 16 * (p >> 1) + 2 * y + (p & 1)
def _planes(bpp): return 3 if bpp == 3 else bpp
def decode_tile(buf, off, bpp):
    return [[sum(((buf[off + _at(bpp, y, p)] >> (7 - x)) & 1) << p for p in range(_planes(bpp))) for x in range(8)] for y in range(8)]
def encode_tile(px, buf, off, bpp):
    """px: 8x8 list, or the 64-hex-digit form project files use"""
    if isinstance(px, str): px = [[int(px[y * 8 + x], 16) for x in range(8)] for y in range(8)]
    for i in range(BYTES[bpp]): buf[off + i] = 0
    for y in range(8):
        for x in range(8):
            for p in range(_planes(bpp)):
                if (px[y][x] >> p) & 1: buf[off + _at(bpp, y, p)] |= 0x80 >> x
