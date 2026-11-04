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
V = {"normal": {}, "inv": {"invincible": True}, "lives": {"lives": True}, "start": {"startlives": 7}}
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
print("errors:", errors or "none"); print(f"{sum(res)}/{len(res)} PASS")
sys.exit(0 if all(res) and not errors else 1)
