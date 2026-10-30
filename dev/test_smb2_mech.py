"""SMB2 mechanics: build variants through the page (Ruby parity + round trip), then measure them in cynes. Needs SMB2_ROM."""
import os, sys, json, zipfile, subprocess, shutil
from playwright.sync_api import sync_playwright
import cynes
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV); T = f"{DEV}/smb2_mech_test"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
ROM = os.environ.get("SMB2_ROM") or sys.exit("Set SMB2_ROM")
C = cynes; R, A, B, S, L = C.NES_INPUT_RIGHT, C.NES_INPUT_A, C.NES_INPUT_B, C.NES_INPUT_START, C.NES_INPUT_LEFT
LIVES, HEALTH, INAIR, CHAR = 0x4ED, 0x4C2, 0x99, 0x8F
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

def run(nes, n, k=0):
    for _ in range(n): nes.controller = k; nes.step(1)
def boot(path):  # title -> character select (Mario) -> 1-1, standing after the drop-in
    nes = C.NES(path); run(nes, 120); run(nes, 5, S); run(nes, 200); run(nes, 5, A); run(nes, 600); return nes
Y = lambda nes: nes[0x1E] * 256 + nes[0x32]
X = lambda nes: nes[0x14] * 256 + nes[0x28]
def rise(nes, seq):
    y0 = Y(nes); ys = []; air = 0
    for n, b in seq:
        for _ in range(n): nes.controller = b; nes.step(1); ys.append(Y(nes)); air += bool(nes[INAIR])
    return y0 - min(ys), air
def measure(path):
    o = {}
    nes = boot(path); o["lives"] = nes[LIVES]; o["char"] = nes[CHAR]
    o["jump"], o["airtime"] = rise(nes, [(4, A), (90, 0)])
    nes = boot(path); o["float_airtime"] = rise(nes, [(150, A)])[1]
    o["air"] = [rise(boot(path), [(10, A), (4, 0)] + [(3, A), (8, 0)] * k + [(120, 0)])[0] for k in (0, 1, 3)]
    nes = boot(path); vs = []
    for _ in range(90): nes.controller = R | B; nes.step(1); vs.append(nes[0x3C])
    o["run_speed"] = max(vs)  # PlayerXVelocity
    # walk until a Shyguy is out, then keep it on top of Mario with one heart left: base loses a life, invincible doesn't
    nes = boot(path)
    for _ in range(600):
        nes.controller = R; nes.step(1)
        if any(nes[0x51 + x] == 1 for x in range(9)): break
    l0 = nes[LIVES]; nes[HEALTH] = 0x0F; hits = 0
    for t in range(700):
        alive = [x for x in range(9) if nes[0x51 + x] == 1]
        if alive and t < 300:
            x = alive[0]; nes[0x29 + x] = nes[0x28]; nes[0x15 + x] = nes[0x14]; nes[0x33 + x] = nes[0x32]; nes[0x1F + x] = nes[0x1E]  # bring the Shyguy to Mario
        h = nes[HEALTH]; nes.controller = 0; nes.step(1)
        if nes[HEALTH] < h: hits += 1
    o["hits"] = hits; o["lives_left"] = nes[LIVES]; o["lives_lost"] = l0 - nes[LIVES]; o["crashed"] = nes.has_crashed
    return o

with sync_playwright() as p:
    pw = p.chromium.launch(); res = {}
    for tag, st in [("base", {}), ("inv", {"invincible": True}), ("lives", {"lives": True, "startlives": 9}), ("high", {"jump": 150}), ("low", {"jump": 50}),
                    ("double", {"airjump": 1}), ("fly", {"airjump": 2}), ("float", {"float": True}), ("moon", {"gravity": 50}), ("fast", {"speed": 150})]:
        path, parity, same = build(pw, st, tag); res[tag] = measure(path); res[tag]["ruby"] = parity; res[tag]["roundtrip"] = same
        print(tag, res[tag])
    pw.close()
b = res["base"]
checks = {
    "playing Mario in 1-1": b["char"] == 0,
    "invincible: Shyguys can't take a heart": b["hits"] > 0 and res["inv"]["hits"] == 0,
    "infinite lives keeps the count": res["lives"]["lives_lost"] == 0 and b["lives_lost"] > 0,
    "start with 9 lives": res["lives"]["lives"] == 9 and b["lives"] == 3,
    "jump height 150% / 50%": res["high"]["jump"] > b["jump"] * 1.3 and res["low"]["jump"] < b["jump"] * 0.7,
    "air jumps: off = 1 jump, double = 1 extra, unlimited keeps climbing": b["air"][0] == b["air"][1] == b["air"][2] and res["double"]["air"][1] > b["air"][0] * 1.4 and abs(res["double"]["air"][2] - res["double"]["air"][1]) <= 2 and res["fly"]["air"][2] > res["double"]["air"][2] * 1.3,
    "Mario floats like the Princess": res["float"]["float_airtime"] > b["float_airtime"] + 30,
    "half gravity stays up longer": res["moon"]["airtime"] > b["airtime"] * 1.2,
    "150% run speed": res["fast"]["run_speed"] == round(b["run_speed"] * 1.5),
    "no crashes": not any(v["crashed"] for v in res.values()),
    "Ruby parity + round trip": all(v["ruby"] and v["roundtrip"] for v in res.values()),
}
for k, v in checks.items(): print(("PASS " if v else "FAIL ") + k)
print("errors:", errors or "none")
