"""Which sprite codes make each object, and the block whose graphics it is drawn with.
Codes come from the bank 0 pointer tables; many codes mean different enemies in different blocks (the block's
CHR set decides), so each object names its block. Picked by rendering every code in every block and by
logging the codes the game draws while walking each stage in the emulator."""
def R(prefix, codes, start=1): return [(f"{prefix} {i}" if len(codes) > 1 else prefix, c) for i, c in enumerate(codes, start)]
SIMON = [("stand", 0x01)] + R("walk", [0x02, 0x03, 0x04]) + [("crouch / jump", 0x05)] + R("whip", [0x06, 0x07, 0x08]) + R("crouch whip", [0x09, 0x0A, 0x0B]) + \
        R("whip on stairs", [0x0D, 0x0E, 0x0F]) + R("stairs", [0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xAB, 0xAC]) + [("hurt", 0x97), ("knocked down", 0x98), ("getting up", 0x99)]
# (name, group, block, frames)
OBJECTS = [
  ("Simon", "Player", "B1", SIMON),
  ("Whip", "Weapons", "B1", R("leather", [0x10, 0x11, 0x12, 0x13]) + R("chain", [0x14, 0x15, 0x16, 0x17]) + [("long chain tip", 0x18)]),
  ("Dagger", "Weapons", "B1", [("dagger", 0x50)]),
  ("Axe", "Weapons", "B1", R("spin", [0x4C, 0x4D, 0x4E, 0x4F])),
  ("Holy water", "Weapons", "B1", [("flask", 0x25)] + R("fire", [0x5A, 0x5B, 0x5C])),
  ("Cross", "Weapons", "B1", R("spin", [0x28, 0x29])),
  ("Hearts", "Items", "B1", [("big heart", 0x26), ("small heart", 0x4A)]),
  ("Subweapon items", "Items", "B1", [("cross", 0x27), ("holy water", 0x2C), ("morning star (whip upgrade)", 0x2D)]),
  ("Power-ups", "Items", "B1", [("double shot", 0x51), ("triple shot", 0x52), ("rosary", 0x72), ("invisibility potion", 0x2B), ("pot roast", 0x4B), ("1UP", 0x2A)]),
  ("Money bag", "Items", "B1", [("money bag", 0x49)]),
  ("Magic crystal", "Items", "B1", R("frame", [0xA2, 0xA3])),
  ("Treasure", "Items", "B2", [("crown", 0xDF), ("chest", 0xE0)]),
  ("Points", "Items", "B1", [("100", 0x5F), ("200", 0x60), ("400", 0x61), ("700", 0x62), ("1000", 0x63), ("2000", 0xAD), ("4000", 0xAE)]),
  ("Candles", "Effects", "B1", R("candle", [0x31, 0x32, 0x33, 0x34, 0x35, 0x36]) + R("brazier", [0x55, 0x56])),
  ("Flames", "Effects", "B1", R("torch", [0x2E, 0x2F, 0x30]) + R("flash", [0x6E, 0x6F]) + R("spark", [0x66, 0xAF, 0xB0])),
  ("Moving platform", "Effects", "B4", R("width", [0xC9, 0xCA, 0xCB, 0xCC])),
  ("Castle gate", "Effects", "B1", [("closed", 0x1D), ("open", 0x1E)]),
  ("Zombie", "Enemies", "B1", R("frame", [0x1F, 0x20, 0x21, 0x22, 0x23])),
  ("Panther", "Enemies", "B1", R("frame", [0xB6, 0xB7, 0xB8, 0xB9])),
  ("Bat", "Enemies", "B1", R("fly", [0x44, 0x45, 0x46, 0x47])),
  ("Fishman", "Enemies", "B1", R("walk", [0x37, 0x38, 0x39]) + R("small", [0x3F, 0x40, 0x41, 0x42, 0x48]) + [("fireball", 0x43)]),
  ("Spear knight", "Enemies", "B2", R("walk", [0x9A, 0x9B, 0x9C, 0x9D])),
  ("Medusa head", "Enemies", "B2", R("frame", [0x64, 0x65])),
  ("Snakes", "Enemies", "B2", R("frame", [0x73, 0x74, 0x75, 0x76])),
  ("Skeleton", "Enemies", "B3", R("walk", [0xB1, 0xB2]) + R("frame", [0x1F, 0x20, 0x21, 0x22, 0x23]) + R("bone", [0xB3, 0xB4, 0xB5])),
  ("Raven", "Enemies", "B3", R("frame", [0x37, 0x38, 0x39, 0x3F, 0x40, 0x41, 0x42, 0x48])),
  ("Fleaman", "Enemies", "B3", R("hop", [0x73, 0x74, 0x87])),
  ("Bone pillar", "Enemies", "B3", [("pillar", 0x9E), ("fireball", 0x43)]),
  ("Eagle", "Enemies", "B4", [("glide", 0x3A)] + R("flap", [0xB7, 0xB8, 0xB9])),
  ("Axe knight", "Enemies", "B5", R("frame", [0x85, 0x86])),
  ("Red skeleton", "Enemies", "B5", R("walk", [0x22, 0x23]) + R("crumble", [0xBA, 0xBB, 0xBF])),
  ("Phantom Bat", "Bosses", "B1", [("asleep", 0x9F)] + R("fly", [0xA0, 0xA1])),
  ("Medusa", "Bosses", "B2", R("frame", [0x78, 0x79, 0xA0, 0xA1])),
  ("Mummies", "Bosses", "B3", R("walk", [0x67, 0x68, 0x69, 0x6A, 0x6B, 0x6C])),
  ("Frankenstein", "Bosses", "B4", R("walk", [0x8F, 0x90, 0x91, 0x92])),
  ("Death", "Bosses", "B5", R("float", [0xC2, 0xC3]) + R("sickle", [0xC4, 0xC5, 0xC6, 0xC7, 0xC8])),
  ("Dracula", "Bosses", "B7", R("cloak", [0xD0, 0xD1])),
  ("Dracula's second form", "Bosses", "B7", R("frame", [0xD3, 0xD4, 0xD5])),
]
