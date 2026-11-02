"""Super Mario World mechanics: build variants through the SNES page (Ruby parity + reopen round trip), then measure
them in the emulator (stable-retro). Needs SMW_ROM."""
import os, sys, json, zipfile, subprocess, shutil
from playwright.sync_api import sync_playwright
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV); T = f"{DEV}/smw_mech_test"
ROM = os.environ.get("SMW_ROM") or sys.exit("Set SMW_ROM")
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
sys.path.insert(0, f"{DEV}/snes"); sys.path.insert(0, f"{DEV}/gen_smw")
from emu import SNES
from capture import warp
errors, res = [], []
def check(name, ok, info=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", name, info)
def build(b, settings, tag):
    ctx = b.new_context(accept_downloads=True); ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/snes/index.html"); pg.wait_for_timeout(300); pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(1200)
    pg.evaluate("(m) => { S.mech = m; changed(); }", settings)
    with pg.expect_download() as d: pg.click("#btnSave"); pg.click("#dlGo")
    z = f"{T}/{tag}.zip"; d.value.save_as(z); x = f"{T}/{tag}"; zipfile.ZipFile(z).extractall(x)
    cfg = json.load(open(f"{x}/config.json")); js = open(f"{x}/{cfg['output']}", "rb").read()
    subprocess.run(["ruby", f"{REPO}/tools/snes_build.rb", "build", f"{x}/config.json"], capture_output=True, check=True)
    parity = open(f"{x}/{cfg['output']}", "rb").read() == js
    pg2 = ctx.new_page(); pg2.goto(f"file://{REPO}/snes/index.html"); pg2.wait_for_timeout(300); pg2.set_input_files("#fProj", z); pg2.wait_for_timeout(1200)
    with pg2.expect_download() as d: pg2.click("#btnSave"); pg2.click("#dlGo")
    z2 = f"{T}/{tag}_re.zip"; d.value.save_as(z2)
    same = {n: zipfile.ZipFile(z).read(n) for n in zipfile.ZipFile(z).namelist()} == {n: zipfile.ZipFile(z2).read(n) for n in zipfile.ZipFile(z2).namelist()}
    ctx.close(); p = f"{T}/{tag}.sfc"; open(p, "wb").write(js); return p, parity, same
def new_game(path):   # title -> file A -> 1 player -> intro message -> overworld
    s = SNES(path); s.run(300); s.run(5, "START"); s.run(90)
    for _ in range(3): s.run(5, "START"); s.run(60)
    for _ in range(60):
        s.run(5, "A"); s.run(25)
        if s.ram[0x100] == 0x0E: break
    s.run(60); return s
def in_level(path, v=0x15):
    s = new_game(path); lives = s.ram[0xDBE]; warp(s, v); s.run(40); return s, lives
def y(s): return s.ram[0x96] | s.ram[0x97] << 8
def jump(path):
    s, _ = in_level(path); s.run(20); y0 = y(s); top = y0
    for f in range(60): s.run(1, "B" if f < 30 else ""); top = min(top, y(s))
    return y0 - top
def hit(path):  # put a Koopa right on top of small Mario: does he die?
    s, _ = in_level(path); r = s.ram; x, yy = r[0x94] | r[0x95] << 8, y(s) + 16
    for a, v in [(0x9E, 0x04), (0x14C8, 1), (0xE4, x & 255), (0x14E0, x >> 8), (0xD8, yy & 255), (0x14D4, yy >> 8)]: s.poke(a, v)
    for _ in range(40):
        s.run(2); s.poke(0xE4, (x) & 255); s.poke(0xD8, yy & 255)
        if s.ram[0x71] == 9: return True
    return False
def die(path):  # drop Mario below the screen; lives and power-up once back on the map
    s, lives = in_level(path); s.poke(0x19, 1); s.poke(0x96, 0xF0, 0x01); s.run(400)
    for _ in range(40):
        if s.ram[0x100] == 0x0E: break
        s.run(10)
    return lives, s.ram[0xDBE], s.ram[0x19]
def clock(path):
    s, _ = in_level(path); t0 = s.ram[0xF31:0xF34]; s.run(300); return bytes(t0), bytes(s.ram[0xF31:0xF34])
V = {"normal": {}, "inv": {"invincible": True}, "lives": {"lives": True, "startlives": 20}, "time": {"time": True},
     "jump": {"jump": 150}, "cape": {"power": 2}}
with sync_playwright() as p:
    b = p.chromium.launch(); paths = {}
    for tag, st in V.items():
        paths[tag], parity, same = build(b, st, tag); print(f"{tag:7} JS == Ruby: {parity} | reopen identical: {same}"); res += [parity, same]
    b.close()
check("normal: a Koopa on small Mario kills him", hit(paths["normal"]))
check("invincible: it doesn't", not hit(paths["inv"]))
l0, l1, _ = die(paths["normal"]); m0, m1, _ = die(paths["lives"])
check("normal: falling costs a life", l1 == l0 - 1, (l0, l1))
check("infinite lives: it doesn't, and the game starts with 20", m0 == m1 == 19, (m0, m1))
t0, t1 = clock(paths["normal"]); u0, u1 = clock(paths["time"])
check("timer counts down normally, stands still when frozen", t0 != t1 and u0 == u1, (t0.hex(), t1.hex(), u0.hex(), u1.hex()))
j0, j1 = jump(paths["normal"]), jump(paths["jump"]); check("jump height 150%", 1.3 <= j1 / max(j0, 1) <= 1.7, (j0, j1))
s, _ = in_level(paths["cape"]); p0 = s.ram[0x19]
_, _, p1 = die(paths["cape"])
check("start as Cape Mario: new game and after losing a life", p0 == 2 and p1 == 2, (p0, p1))
print("errors:", errors or "none"); print(f"{sum(res)}/{len(res)} PASS")
sys.exit(0 if all(res) and not errors else 1)
