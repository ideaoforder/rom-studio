"""Castlevania mechanics: build variants through the page (Ruby parity + round trip), then measure them in cynes. Needs CV_ROM."""
import os, sys, json, zipfile, subprocess, shutil
from playwright.sync_api import sync_playwright
import cynes
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV); T = f"{DEV}/cv_mech_test"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
ROM = os.environ.get("CV_ROM") or sys.exit("Set CV_ROM")
C = cynes; R, A, B, U = C.NES_INPUT_RIGHT, C.NES_INPUT_A, C.NES_INPUT_B, C.NES_INPUT_UP
LIVES, HEARTS, HEALTH, SUB, SHOTS, WHIP, Y, STAGE = 0x2A, 0x71, 0x45, 0x15B, 0x64, 0x70, 0x354, 0x28
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
def start(path):  # title -> START -> wait out the walk to the gate
    nes = C.NES(path); run(nes, 200); run(nes, 5, C.NES_INPUT_START); run(nes, 650); return nes
def hall(path):  # walk through the gate into stage 2, the hall with zombies
    nes = start(path)
    for _ in range(1200):
        nes.controller = R; nes.step(1); nes[HEALTH] = 0x40
        if nes[STAGE] == 1: break
    run(nes, 60); return nes
def rise(nes, seq):
    y0 = nes[Y]; last = y0; yy = y0; ys = []
    for n, b in seq:
        for _ in range(n):
            nes.controller = b; nes.step(1); d = (nes[Y] - last + 128) % 256 - 128; yy += d; last = nes[Y]; ys.append(yy)
    return y0 - min(ys)
def measure(path):
    o = {}
    nes = start(path); o["lives"] = nes[LIVES]; o["hearts"] = nes[HEARTS]; o["kit"] = [nes[SUB], nes[SHOTS], nes[WHIP]]
    run(nes, 30); o["jump"] = rise(nes, [(3, A), (60, 0)])
    def air(k):
        nes = start(path); run(nes, 30); return rise(nes, [(10, A), (4, 0)] + [(3, A), (6, 0)] * k + [(80, 0)])
    o["air"] = [air(0), air(1), air(3)]
    nes = start(path); nes[SUB] = 8; nes[HEARTS] = 10; run(nes, 3, U | B); run(nes, 20); o["hearts_after_throw"] = nes[HEARTS]
    nes = hall(path); nes[HEALTH] = 0x0C; l0 = nes[LIVES]; low = 0x40; died = False; o["first_hit"] = None
    for _ in range(1500):
        h = nes[HEALTH]; nes.controller = R; nes.step(1); low = min(low, nes[HEALTH])
        if o["first_hit"] is None and nes[HEALTH] < h: o["first_hit"] = h - nes[HEALTH]
        if nes[HEALTH] == 0 or nes[LIVES] != l0: died = True
    o["low_health"] = low; o["died"] = died; o["lives_lost"] = l0 - nes[LIVES]
    run(nes, 400); o["kit_after_death"] = [nes[SUB], nes[SHOTS], nes[WHIP]]; o["crashed"] = nes.has_crashed
    return o

with sync_playwright() as p:
    pw = p.chromium.launch(); res = {}
    for tag, st in [("base", {}), ("inv", {"invincible": True}), ("lives", {"lives": True, "startlives": 9}), ("hearts", {"hearts": True, "starthearts": 30}),
                    ("kit", {"subweapon": 13, "shots": 2, "whip": 2}), ("dagger", {"subweapon": 8}), ("high", {"jump": 150}), ("low", {"jump": 50}),
                    ("double", {"airjump": 1}), ("fly", {"airjump": 2}), ("soft", {"damage": 25})]:
        path, parity, same = build(pw, st, tag); res[tag] = measure(path); res[tag]["ruby"] = parity; res[tag]["roundtrip"] = same
        print(tag, res[tag])
    pw.close()
b = res["base"]
checks = {
    "invincible: zombies can't take health": b["died"] and not res["inv"]["died"] and res["inv"]["low_health"] == 0x0C,
    "infinite lives keeps the count": res["lives"]["died"] and res["lives"]["lives_lost"] == 0 and b["lives_lost"] == 1,
    "start with P-09 (byte 10)": res["lives"]["lives"] == 10 and b["lives"] == 4,
    "infinite hearts + 30 at the start": res["hearts"]["hearts"] == 30 and res["hearts"]["hearts_after_throw"] == 10 and b["hearts_after_throw"] == 9,
    "start kit (axe, triple shot, long chain), again after a death": res["kit"]["kit"] == [13, 2, 2] and res["kit"]["kit_after_death"] == [13, 2, 2] and b["kit_after_death"] == [0, 0, 0],
    "dagger alone leaves shots and whip normal": res["dagger"]["kit"] == [8, 0, 0] and res["dagger"]["kit_after_death"] == [8, 0, 0],
    "jump height 150% / 50%": res["high"]["jump"] > b["jump"] * 1.3 and res["low"]["jump"] < b["jump"] * 0.75,
    "air jumps: off = 1 jump, double = 1 extra, unlimited keeps climbing": b["air"][0] == b["air"][1] == b["air"][2] and res["double"]["air"][1] > b["air"][0] * 1.5 and res["double"]["air"][2] == res["double"]["air"][1] and res["fly"]["air"][2] > res["double"]["air"][2] * 1.3,
    "25% damage: a zombie hit takes 2 instead of 8": b["first_hit"] == 8 and res["soft"]["first_hit"] == 2,
    "no crashes": not any(v["crashed"] for v in res.values()),
    "Ruby parity + round trip": all(v["ruby"] and v["roundtrip"] for v in res.values()),
}
for k, v in checks.items(): print(("PASS " if v else "FAIL ") + k)
print("errors:", errors or "none")
