"""Bosses: Mouser, Tryclyde, Fryguy, Clawgrip and Wart, put together the way their RenderSprite_* routines draw them.
Their art is in tilemap 2 at odd tile numbers, so it comes from the background pattern table: each world's background
bank holds its boss (grass $10 Mouser, desert $12 Tryclyde, ice $14 Fryguy, $0A Clawgrip, sky $16 Wart)."""
import os, json
OUT = os.environ.get("SMB2_OUT", "/tmp/smb2_gen")
WORLDBANK = {"w1": 0x0C, "w2": 0x0D, "w4": 0x0E, "w5": 0x0C, "w7": 0x0F}
BGBANK = {"w1": 0x10, "w2": 0x12, "w4": 0x14, "w5": 0x0A, "w7": 0x16}
def tok(n, h=False):
    base = (n & 0xFE) + (0x100 if n & 1 else 0); f = "h" if h else ""
    return f"{base:02X}{f}", f"{base + 1:02X}{f}"
def grid(rows, mirror=()):
    """rows: lists of 8x16 tile numbers (None = blank). mirror: rows (by index) whose tiles are drawn flipped."""
    cols = max(len(r) for r in rows); out = []
    for i, r in enumerate(rows):
        top, bot = [], []
        for n in r + [None] * (cols - len(r)):
            if n is None or n in (0xFB, 0xFF): top.append("."); bot.append("."); continue
            a, b = tok(n, i in mirror); top.append(a); bot.append(b)
        out += [top, bot]
    return {"cols": cols, "tiles": " ".join(" ".join(x) for x in out)}
def halves(left, right):
    """Clawgrip-style: a 16-wide left half and a right half drawn mirrored (columns swapped, tiles flipped)."""
    cols = 4; out = []
    for lr, rr in zip(left, right):
        for half in (0, 1):
            row = [tok(n)[half] if n not in (0xFB, None) else "." for n in lr]
            row += [tok(n, True)[half] if n not in (0xFB, None) else "." for n in reversed(rr)]
            out.append(row)
    return {"cols": cols, "tiles": " ".join(" ".join(x) for x in out)}
def sprites(parts, pal):
    """free placement: (8x16 tile number, dx, dy)"""
    sp = []
    for n, dx, dy in parts:
        a, b = tok(n); sp += [[a, dx, dy, pal], [b, dx, dy + 8, pal]]
    return {"sprites": sp}
def boss(name, home, pal, frames):
    return {"name": name, "group": "Bosses", "home": home, "palette": [pal], "frames": frames,
            "chr_banks": [0x00, 0x08, 0x09, WORLDBANK[home], BGBANK[home], BGBANK[home] + 1, 0x18, 0x19]}
B = []
# Mouser: 3 wide, 16x32 (EnemyTilemap2 $14..$37); bomb $9C/$9E is a common-enemies sprite
B.append(boss("Mouser", "w1", 3, {"walk 1": grid([[0x01, 0x03, 0x09], [0x05, 0x07, 0x0B]]), "walk 2": grid([[0x0D, 0x0F, 0x15], [0x11, 0x13, 0x17]]),
                                  "throw": grid([[0x01, 0x03, 0x09], [0x05, 0x19, 0x1B]]), "hurt": grid([[0x1D, 0x1F, 0x25], [0x21, 0x23, 0x27]])}))
B.append(boss("Mouser bomb", "w1", 1, {"bomb": grid([[0x9C, 0x9E]])}))
# Tryclyde: body ($48) with the tail ($50/$53) 8 px left and below, two heads ($56/$58/$5A) to the left (necks not shown)
def tryclyde(body, tail, head):
    p = [(body[0], 0, 0), (body[1], 8, 0), (body[2], 0, 16), (body[3], 8, 16)]
    p += [(t, -8 + 8 * i, 32) for i, t in enumerate(tail)]
    p += [(head[0], -24, 0), (head[1], -16, 0), (head[0], -24, 16), (head[1], -16, 16)]
    return sprites(p, 2)
B.append(boss("Tryclyde", "w2", 2, {"tail up": tryclyde([0x0F, 0x11, 0x13, 0x15], [0x17, 0x19, 0x1B], [0x01, 0x03]),
                                    "tail down": tryclyde([0x0F, 0x11, 0x13, 0x15], [0x17, 0x19, 0x1D], [0x01, 0x03]),
                                    "spit": tryclyde([0x0F, 0x11, 0x13, 0x15], [0x17, 0x19, 0x1B], [0x05, 0x07]),
                                    "hurt": tryclyde([0x1F, 0x11, 0x13, 0x15], [0x17, 0x19, 0x1B], [0x09, 0x0B])}))
# Fryguy: 32x32 from two 16x32 halves ($80/$84, hurt $88/$8C); the small flames after he splits ($90)
B.append(boss("Fryguy", "w4", 1, {"fryguy": grid([[0x01, 0x03, 0x09, 0x0B], [0x05, 0x07, 0x0D, 0x0F]]),
                                  "hurt": grid([[0x01, 0x11, 0x13, 0x0B], [0x05, 0x15, 0x17, 0x0F]]),
                                  "split": grid([[0x19, 0x1B]])}))
# Clawgrip: the left half, then a mirrored right half 16 px over (RenderSprite_Clawgrip_RightSide); the rock is its own object
B.append(boss("Clawgrip", "w5", 1, {"claws 1": halves([[0x01, 0x03], [0x05, 0x07]], [[0x09, 0x0B], [0x0D, 0x0F]]),
                                    "claws 2": halves([[0x09, 0x0B], [0x0D, 0x0F]], [[0x01, 0x03], [0x05, 0x07]]),
                                    "reach": halves([[0xFB, 0x11], [0x15, 0x17]], [[0x13, 0xFB], [0x19, 0x1B]]),
                                    "hurt": halves([[0x1D, 0x1F], [0x21, 0x23]], [[0x1D, 0x1F], [0x21, 0x23]])}))
B.append(boss("Clawgrip rock", "w5", 2, {"rock": grid([[0x25, 0x27]])}))
# Wart: top + middle + bottom rows, 4 wide (32x48); bubbles are 16x16, mirrored
W = {"top": [0x01, 0x03, 0x05, 0x07], "top spit": [0x4F, 0x5D, 0x05, 0x07], "top hurt": [0x4F, 0x2F, 0x45, 0x55], "mid": [0x09, 0x0B, 0x0D, 0x0F],
     "mid spit": [0x27, 0x79, 0x7B, 0x2D], "stand": [0x11, 0x13, 0x23, 0x25], "left up": [0x11, 0x13, 0x15, 0x17], "right up": [0x1F, 0x21, 0x23, 0x25]}
def bubble(n):  # 16x16: tile and its mirror
    a, b = tok(n); c, d = tok(n, True); return {"cols": 2, "tiles": f"{a} {c} {b} {d}"}
B.append(boss("Wart", "w7", 3, {"stand": grid([W["top"], W["mid"], W["stand"]]), "walk 1": grid([W["top"], W["mid"], W["left up"]]),
                                "walk 2": grid([W["top"], W["mid"], W["right up"]]), "spit": grid([W["top spit"], W["mid spit"], W["stand"]]),
                                "hurt": grid([W["top hurt"], W["mid"], W["stand"]])}))
B.append(boss("Wart bubble", "w7", 1, {"bubble 1": bubble(0x59), "bubble 2": bubble(0x5B)}))
json.dump(B, open(OUT + "/bosses.json", "w"), indent=0)
print(len(B), "bosses")
