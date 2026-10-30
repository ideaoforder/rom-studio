"""Background blocks: every map tile ("tile quad", 16x16) per world, from TileQuads1-4 (bank F).
A map tile id's top two bits pick the palette and the quad table; the low six index it. Quads are TL TR BL BR,
8x8 background tiles: $00-$7F from the world's background bank, $80-$FF from the animated bank."""
import os, json, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from labels import off
OUT = os.environ.get("SMB2_OUT", "/tmp/smb2_gen"); DIS = os.environ["SMB2_DIS"]
r = open(os.environ["SMB2_ROM"], "rb").read()
src = open(DIS + "/src/prg-e-f.asm").read().split("\n")
counts = []; cur = None
for l in src:
    m = re.match(r"^TileQuads([1-4]):", l)
    if m: cur = int(m.group(1)); counts.append(0); continue
    if cur and re.match(r"^\s*\.db ", l): counts[-1] += 1; continue
    if cur and re.match(r"^\S", l): cur = None
assert len(counts) == 4, counts
Q = []; o = off("TileQuads1")
for n in counts: Q.append((o, n)); o += 4 * n
WORLDS = {"w1": "Grass", "w2": "Desert", "w3": "Grass", "w4": "Ice", "w5": "Grass", "w6": "Desert", "w7": "Sky"}
BGBANK = {"w1": 0x10, "w2": 0x12, "w3": 0x10, "w4": 0x14, "w5": 0x0A, "w6": 0x12, "w7": 0x16}
def sheet(k):
    o, n = Q[k]; per = 8; rows = (n + per - 1) // per; toks = [["."] * (per * 2) for _ in range(rows * 2)]
    for i in range(n):
        q = r[o + 4 * i:o + 4 * i + 4]; X = (i % per) * 2; Y = (i // per) * 2
        for (dx, dy), t in zip(((0, 0), (1, 0), (0, 1), (1, 1)), q): toks[Y + dy][X + dx] = f"{0x100 + t:03X}"
    flat = sum(toks, []); return {"cols": per * 2, "tiles": " ".join(flat), "palettes": " ".join(f"bg{k}" if t != "." else "bg0" for t in flat)}
objs = []
for w, kind in WORLDS.items():
    b = BGBANK[w]
    objs.append({"name": f"World {w[1]} · {kind}", "category": "blocks", "group": "Worlds", "home": w, "palette": ["bg0"],
                 "chr_banks": [0x00, 0x08, 0x09, 0x0C, b, b + 1, 0x18, 0x19],
                 "frames": {f"palette {k}": sheet(k) for k in range(4)}})
json.dump(objs, open(OUT + "/blocks.json", "w"), indent=0)
print(counts, [hex(q[0]) for q in Q])
