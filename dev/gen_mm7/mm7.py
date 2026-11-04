"""Mega Man 7 (USA): ROM facts shared by the generator. No public disassembly: everything here was found by reading the
ROM and watching the game in stable-retro (see README.md). File offsets unless noted; the ROM is HiROM ($C0:0000 = 0)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "snes"))
from clz import decode  # noqa: E402
ROM_PATH = os.environ.get("MM7_ROM") or sys.exit("Set MM7_ROM to your Mega Man 7 (USA) .sfc")
ROM = open(ROM_PATH, "rb").read()
if len(ROM) % 1024 == 512: ROM = ROM[512:]
SETS_TABLE, N_SETS = 0x00E993, 0xB8          # 5 bytes per graphics set: 24-bit address ($C0:xxxx), 16-bit unpacked size
def set_entry(i):
    o = SETS_TABLE + 5 * i
    return int.from_bytes(ROM[o:o + 3], "little") - 0xC00000, int.from_bytes(ROM[o + 3:o + 5], "little")
SETS = {}
for i in range(N_SETS):
    at, n = set_entry(i); data, size = decode(ROM, at, n); SETS[i] = (at, n, data, size)
RAW_BANKS = range(0x10, 0x20)                 # where the uncompressed art (Mega Man, Rush, ...) was found; tiles are 32-aligned
# RAM (found by experiment)
OAM_BUF = 0x0700                              # OAM buffer: 512 bytes + 32 bytes of size/x-high bits at $0900
CAM_X, CAM_Y = 0x00D8, 0x00DA
PLAYER = 0x0C00                               # Mega Man's object: +5 x, +8 y (words)
HEALTH = (0x0BD1, 0x0C2E)                     # 28 = full
PASSWORD = 0x1DF2                             # 16 digits on the password screen
def provenance_index():
    """4bpp tile bytes -> ("set", i, tile) for every tile of every decoded set, then ("raw", bank, tile) for the
    uncompressed banks (only 32-byte-aligned tiles; first match wins)"""
    idx = {}
    for i, (_, _, d, _) in SETS.items():
        for t in range(len(d) // 32): idx.setdefault(d[32 * t:32 * t + 32], ("set", i, t))
    return idx
def raw_lookup(b):
    i = ROM.find(b)
    while i >= 0 and i % 32: i = ROM.find(b, i + 1)
    return None if i < 0 else ("raw", i >> 16, (i & 0xFFFF) // 32)
