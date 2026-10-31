"""ObjAnimations / ObjAnimFrameHeap / ObjAnimAttrHeap (bank 1, from the disassembly's labels; Rev 1 found by pattern).
Animation index = object type + 1 (Link uses 0 and 1). A frame is an 8x16 sprite pair: tile T on the left and T+2 on the
right, or for mirrored objects T and T flipped."""
from gfx import ROM
HEAD = bytes([0x00, 0x08, 0x0B, 0x0F, 0x13, 0x17, 0x5C, 0x60])
ANIMS = ROM.find(HEAD); assert ANIMS > 0 and ROM.find(HEAD, ANIMS + 1) == -1
N_ANIMS = 0x7F
HEAP = ANIMS + N_ANIMS; HEAP_LEN = 0xCC; ATTR = HEAP + HEAP_LEN
assert ROM[HEAP:HEAP + 4] == bytes([0, 4, 8, 0x0C])
def frames(anim):
    s = ROM[ANIMS + anim]
    if s >= HEAP_LEN: return []
    nxt = sorted({ROM[ANIMS + a] for a in range(N_ANIMS)} | {HEAP_LEN})
    e = next(x for x in nxt if x > s)
    return [(ROM[HEAP + i], ROM[ATTR + i], i) for i in range(s, e)]
LEFT_TILES = {ROM[HEAP + i] for i in range(HEAP_LEN)}
def mirrored_guess(t):
    """A frame stores only its left half when T+2 is some other frame's tile."""
    return (t + 2) & 0xFF in LEFT_TILES
