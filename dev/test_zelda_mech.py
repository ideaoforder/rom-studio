"""Zelda mechanics: build variants through the page (Ruby parity + round trip), then measure them in cynes. Needs ZELDA_ROM."""
import os, sys, json, zipfile, subprocess, shutil
from playwright.sync_api import sync_playwright
import cynes as C
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV); T = f"{DEV}/zelda_mech_test"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
ROM = os.environ.get("ZELDA_ROM") or sys.exit("Set ZELDA_ROM")
sys.path.insert(0, f"{DEV}/gen_zelda"); import screens as Z; from gfx import LEVELINFO
L, R, U, D, A, B = C.NES_INPUT_LEFT, C.NES_INPUT_RIGHT, C.NES_INPUT_UP, C.NES_INPUT_DOWN, C.NES_INPUT_A, C.NES_INPUT_B
ITEMS, BOMBS, RUPEES, HEARTS, PARTIAL, SEL, X, SHOT = 0x657, 0x658, 0x66D, 0x66F, 0x670, 0x656, 0x70, 0xAC + 0x0E
errors = []
def build(pw, settings, tag):
    ctx = pw.new_context(accept_downloads=True); ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/index.html"); pg.wait_for_timeout(500); pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(800)
    pg.evaluate("(m) => { S.mech = m; persist(); }", settings)
    with pg.expect_download() as d: pg.click("#btnSave"); pg.click("#dlGo")
    z1 = f"{T}/{tag}.zip"; d.value.save_as(z1); x = f"{T}/{tag}"; zipfile.ZipFile(z1).extractall(x)
    name = json.load(open(f"{x}/config.json"))["output"]; js = open(f"{x}/{name}", "rb").read()
    subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{x}/config.json"], capture_output=True, check=True)
    parity = open(f"{x}/{name}", "rb").read() == js
    pg2 = ctx.new_page(); pg2.goto(f"file://{REPO}/index.html"); pg2.wait_for_timeout(500); pg2.set_input_files("#fProj", z1); pg2.wait_for_timeout(1200)
    with pg2.expect_download() as d: pg2.click("#btnSave"); pg2.click("#dlGo")
    z2 = f"{T}/{tag}_re.zip"; d.value.save_as(z2)
    same = {n: zipfile.ZipFile(z1).read(n) for n in zipfile.ZipFile(z1).namelist()} == {n: zipfile.ZipFile(z2).read(n) for n in zipfile.ZipFile(z2).namelist()}
    ctx.close(); path = f"{T}/{tag}.nes"; open(path, "wb").write(js)
    return path, parity, same
def room(path, r):  # same ROM, starting in another overworld room
    b = bytearray(open(path, "rb").read()); b[LEVELINFO["ow"] + 0x2F] = r; p = path.replace(".nes", f"_{r:02X}.nes"); open(p, "wb").write(b); return p
def run(n, k, c=0):
    for _ in range(k): n.controller = c; n.step(1)
def health(n): return (n[HEARTS] & 15) * 256 + n[PARTIAL]
def first_hit(path):  # wander in room $66 (moblins); how much the first hit takes, None if nothing in 1500 frames
    n = Z.boot(room(path, 0x66)); h0 = health(n)
    for f in range(1500):
        n.controller = [L, U, R, D][(f // 60) % 4]; n.step(1)
        if health(n) < h0: return h0 - health(n)
    return None
def walk(path):  # pixels walked right in 40 frames in the start room
    n = Z.boot(path); x0 = n[X]; run(n, 40, R); return n[X] - x0
def beam(path):  # at half health, does the sword shoot?
    n = Z.boot(path); n[ITEMS] = 1; n[HEARTS] = (n[HEARTS] & 0xF0) | 0; n[PARTIAL] = 0x7F; run(n, 2)
    for _ in range(30):
        n.controller = A; n.step(1)
        if n[SHOT]: return True
    return False
def bomb(path):  # set one bomb with one in the bag: is it still there?
    n = Z.boot(path); n[BOMBS] = 1; n[SEL] = 1; run(n, 2); run(n, 5, B); run(n, 60); return n[BOMBS]
def kit(path):
    n = Z.boot(path); return {"sword": n[ITEMS], "bombs": n[BOMBS], "rupees": n[RUPEES], "hearts": n[HEARTS], "ring": n[0x662], "candle": n[0x65B],
                              "boomerang": n[0x674], "magickey": n[0x664], "arrow": n[0x659], "bow": n[0x65A]}
with sync_playwright() as pw:
    b = pw.chromium.launch(); prof = None
    V = {"normal": {}, "inv": {"invincible": True}, "half": {"damage": 0}, "double": {"damage": 2}, "fast": {"speed": 0x80}, "beam": {"beam": True},
         "bombs": {"bombs": True}, "kit": {"kit_sword": 3, "kit_hearts": 0xFF, "kit_ring": 2, "kit_candle": 1, "kit_bombs": 8, "kit_rupees": 255,
                                           "kit_boomerang": True, "kit_magickey": True, "kit_arrow": 2, "kit_bow": True}}
    paths = {}
    for tag, s in V.items():
        p, parity, same = build(b, s, tag); paths[tag] = p
        print(f"{tag:7} JS == Ruby: {parity} | reopen identical: {same}")
    b.close()
res = []
def check(name, ok, info): res.append(ok); print(("PASS" if ok else "FAIL"), name, info)
h = {t: first_hit(paths[t]) for t in ["normal", "inv", "half", "double"]}
check("normal hit takes half a heart", h["normal"] in (0x80, 0x81), h["normal"])
check("invincible: no hit takes hearts", h["inv"] is None, h["inv"])
check("half damage", h["half"] in (0x40, 0x41), h["half"])
check("double damage", h["double"] in (0x100, 0x101), h["double"])
w0, w1 = walk(paths["normal"]), walk(paths["fast"]); check("walking speed 1.5 -> 2 px a frame", 50 <= w0 <= 60 and 75 <= w1 <= 85, (w0, w1))
b0, b1 = beam(paths["normal"]), beam(paths["beam"]); check("sword beam at half health", not b0 and b1, (b0, b1))
m0, m1 = bomb(paths["normal"]), bomb(paths["bombs"]); check("bombs never run out", m0 == 0 and m1 == 1, (m0, m1))
k0, k1 = kit(paths["normal"]), kit(paths["kit"])
want = {"sword": 3, "bombs": 8, "rupees": 255, "hearts": 0xFF, "ring": 2, "candle": 1, "boomerang": 1, "magickey": 1, "arrow": 2, "bow": 1}
check("normal new file", k0 == {**{k: 0 for k in want}, "hearts": 0x22}, k0)
check("starting kit on a new file", k1 == want, k1)
print("errors:", errors or "none"); print(f"{sum(res)}/{len(res)} PASS")
