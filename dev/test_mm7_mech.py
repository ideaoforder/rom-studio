"""Mega Man 7 mechanics: build variants through the SNES page (Ruby parity + reopen round trip), then measure
them in the emulator (stable-retro). Needs MM7_ROM."""
import os, sys, json, zipfile, subprocess, shutil
from playwright.sync_api import sync_playwright
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV); T = f"{DEV}/mm7_mech_test"
ROM = os.environ.get("MM7_ROM") or sys.exit("Set MM7_ROM")
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
sys.path.insert(0, f"{DEV}/snes"); sys.path.insert(0, f"{DEV}/gen_mm7")
from emu import SNES
import capture as C
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
def run(path, frames=300, weak=False):   # walk right through Freeze Man's stage from the start, jumping now and then
    s = SNES(path); s.load(SEL); C.enter(s, "Freeze Man"); s.run(20); lives0 = s.ram[0xB81]; h = []
    if weak: s.poke(0x0C2E, 1); s.poke(0x0BD1, 1)   # one hit from losing a life
    for k in range(frames): s.run(4, "RIGHT", *(("B",) if k % 10 < 4 else ())); h.append(s.ram[0x0C2E])
    return lives0, [x for i, x in enumerate(h) if i == 0 or h[i - 1] != x], s.ram[0xB81]
SEL = C.stage_select().save()
def jump(path, presses):   # highest point over 2 s, holding B for each (start, end) frame range
    s = SNES(path); s.load(SEL); C.enter(s, "Freeze Man"); s.run(30); y0 = s.ram[0xC08] | s.ram[0xC09] << 8; top = y0
    for f in range(120):
        s.run(1, *(("B",) if any(a <= f < b for a, b in presses) else ())); top = min(top, s.ram[0xC08] | s.ram[0xC09] << 8)
    return y0 - top
def new_game(path):       # title -> GAME START, a few seconds in
    s = SNES(path)
    for f in range(120):
        s.run(30) if f % 2 else s.run(4, "START")
        if C.title_menu(s.screen()): break
    s.run(40); s.run(4, "START"); s.run(300); return s.ram
V = {"normal": {}, "inv": {"invincible": True}, "lives": {"lives": True}, "start": {"startlives": 7}, "jump": {"jump": 150},
     "double": {"airjump": 1}, "unlimited": {"airjump": 2},
     "kit": {"kit_weapons": True, "kit_adaptor": True, "kit_rjet": True, "kit_balancer": True, "kit_beat": 4, "kit_pshield": True, "kit_hyper": True, "kit_etanks": 4, "kit_bolts": 999}}
with sync_playwright() as p:
    b = p.chromium.launch(); paths = {}
    for tag, st in V.items():
        paths[tag], parity, same = build(b, st, tag); print(f"{tag:7} JS == Ruby: {parity} | reopen identical: {same}"); res += [parity, same]
    b.close()
_, h0, _ = run(paths["normal"]); _, hi, _ = run(paths["inv"]); l0, _, l1 = run(paths["normal"], 400, True)
check("normal: enemies take energy", any(0 < x < 28 for x in h0), h0[:8])
check("invincible: energy only ever full (or gone in a pit)", all(x in (0, 28) for x in hi), hi[:8])
check("normal: dying costs a life", l1 < l0, (l0, l1))
m0, _, m1 = run(paths["lives"], 400, True); check("infinite lives: it doesn't", m1 == m0, (m0, m1))
s = C.stage_select(paths["start"]); C.enter(s, "Freeze Man"); s.run(20)   # boots the patched ROM through the password screen
check("lives at the start: 7 after entering a password", s.ram[0xB81] == 7, s.ram[0xB81])
ONE, TWO, THREE = [(0, 20)], [(0, 20), (26, 45)], [(0, 20), (26, 45), (50, 70)]
j0, j1 = jump(paths["normal"], ONE), jump(paths["jump"], ONE); check("jump height 150%", 1.25 <= j1 / j0 <= 1.6, (j0, j1))
n2, d1, d2, d3, u3 = jump(paths["normal"], TWO), jump(paths["double"], ONE), jump(paths["double"], TWO), jump(paths["double"], THREE), jump(paths["unlimited"], THREE)
check("normal: pressing jump in the air does nothing", n2 == j0, (j0, n2))
check("double jump: one more jump, not two", d1 == j0 and d2 > 1.6 * j0 and d3 == d2, (d1, d2, d3))
check("unlimited air jumps: a third one too", u3 > d2 + 0.5 * j0, (d2, u3))
k0, k1 = new_game(paths["normal"]), new_game(paths["kit"])
w = lambda r, k: r[0xB83 + 2 * k]
check("normal new game: only the buster and Rush Coil", all(not w(k0, k) & 0x80 for k in (1, 2, 3, 4, 9, 11, 14)) and k0[0xBA0] == 0 and k0[0xBA3] == 0, k0[0xB83:0xBA8].hex())
check("starting kit: weapons, Super Adaptor, Rush Jet, Proto Shield, Energy Balancer, Hyper Rocket Buster, Beat + 4 whistles, 4 E-tanks, 999 bolts",
      all(w(k1, k) == 0x9C for k in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 14)) and k1[0xBA4] & 0xC0 == 0xC0 and k1[0xBA3] == 0x84 and k1[0xBA0] == 4 and k1[0xBA6] | k1[0xBA7] << 8 == 999, k1[0xB83:0xBA8].hex())
p0 = C.stage_select(paths["kit"]).ram; check("a password game isn't touched by the kit", p0[0xBA0] == 1 and p0[0xBA6] | p0[0xBA7] << 8 == 640, p0[0xB9F:0xBA8].hex())
print("errors:", errors or "none"); print(f"{sum(res)}/{len(res)} PASS")
sys.exit(0 if all(res) and not errors else 1)
