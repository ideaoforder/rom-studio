"""Contra mechanics: build variants through the page (Ruby parity + round trip), then measure them in cynes. Needs CONTRA_ROM."""
import os, sys, json, zipfile, subprocess, shutil
from playwright.sync_api import sync_playwright
import cynes
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV); T = f"{DEV}/contra_mech_test"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
ROM = os.environ.get("CONTRA_ROM") or sys.exit("Set CONTRA_ROM")
C = cynes; R, A, B, S, L = C.NES_INPUT_RIGHT, C.NES_INPUT_A, C.NES_INPUT_B, C.NES_INPUT_START, C.NES_INPUT_LEFT
LIVES, WEAPON, STATE, Y, X = 0x32, 0xAA, 0x90, 0x31A, 0x334
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

def boot(path):
    nes = C.NES(path)
    for n, k in [(300, 0), (5, S), (60, 0), (5, S), (520, 0)]:
        for _ in range(n): nes.controller = k; nes.step(1)
    return nes

def measure(path):
    o = {}
    nes = boot(path); o["lives_start"] = nes[LIVES]; o["weapon_start"] = nes[WEAPON]
    y0 = nes[Y]; ys = []; last = y0; yy = y0
    for _ in range(40):  # unwrap: a high jump can leave the top of the screen
        nes.controller = A; nes.step(1); d = (nes[Y] - last + 128) % 256 - 128; yy += d; last = nes[Y]; ys.append(yy)
    o["jump_px"] = y0 - min(ys); o["apex_frame"] = ys.index(min(ys))
    def peak(k):  # jump, then k more presses mid-air
        nes = boot(path); y0 = nes[Y]; last = y0; yy = y0; ys = []
        for n, b in [(14, A), (3, 0)] + [(12, A), (3, 0)] * k + [(70, 0)]:
            for _ in range(n):
                nes.controller = b; nes.step(1); d = (nes[Y] - last + 128) % 256 - 128; yy += d; last = nes[Y]; ys.append(yy)
        return y0 - min(ys)
    o["air"] = [peak(0), peak(1), peak(3)]
    nes = boot(path); x0 = nes[X]
    for _ in range(40): nes.controller = R; nes.step(1)
    o["walk_px_40f"] = nes[X] - x0
    # run into the level shooting: base game loses lives here
    nes = boot(path); l0 = nes[LIVES]; nes[WEAPON] = 0x01; deaths = 0; pits = 0; weapon_after = None; prev = nes[STATE]
    for t in range(2400):
        nes.controller = R | (B if t % 8 < 4 else 0) | (A if t % 90 < 6 else 0); nes.step(1)
        if nes[STATE] == 2 and prev != 2:
            if nes[Y] >= 0xD8: pits += 1  # fell off the bottom of the screen
            else: deaths += 1
        if prev == 2 and nes[STATE] != 2 and weapon_after is None: weapon_after = None
        if (deaths or pits) and weapon_after is None and nes[STATE] == 1: weapon_after = nes[WEAPON]
        prev = nes[STATE]
    o["deaths"] = deaths; o["pits"] = pits; o["lives_lost"] = l0 - nes[LIVES]; o["weapon_after_death"] = weapon_after; o["crashed"] = nes.has_crashed
    return o

with sync_playwright() as p:
    pw = p.chromium.launch(); res = {}
    for tag, st in [("base", {}), ("inv", {"invincible": True}), ("lives", {"lives": True, "startlives": 9}), ("spread", {"weapon": 3}),
                    ("keep", {"keepweapon": True}), ("moon", {"jump": 150, "gravity": 50}), ("fast", {"speed": 200}), ("double", {"airjump": 1}), ("fly", {"airjump": 2})]:
        path, parity, same = build(pw, st, tag); res[tag] = measure(path); res[tag]["ruby"] = parity; res[tag]["roundtrip"] = same
        print(tag, res[tag])
    pw.close()
b = res["base"]
checks = {
    "invincible: enemies never kill (pits still do)": b["deaths"] > 0 and res["inv"]["deaths"] == 0,
    "infinite lives keeps the count": res["lives"]["deaths"] + res["lives"]["pits"] > 0 and res["lives"]["lives_lost"] == 0 and b["lives_lost"] > 0,
    "9 extra lives at the start": res["lives"]["lives_start"] == 9 and b["lives_start"] == 2,
    "start with Spread (and get it back after a death)": res["spread"]["weapon_start"] == 3 and b["weapon_start"] == 0 and res["spread"]["weapon_after_death"] == 3,
    "keep weapon after a death": (res["keep"]["weapon_after_death"] or 0) & 0x0F == 1 and b["weapon_after_death"] == 0,
    "higher, floatier jump": res["moon"]["jump_px"] > b["jump_px"] * 1.3 and res["moon"]["apex_frame"] > b["apex_frame"],
    "air jumps: off = 1 jump, double = 1 extra, unlimited keeps climbing": b["air"][0] == b["air"][1] == b["air"][2] and res["double"]["air"][1] > b["air"][0] * 1.4 and res["double"]["air"][2] == res["double"]["air"][1] and res["fly"]["air"][2] > res["double"]["air"][2] * 1.3,
    "2x run speed": res["fast"]["walk_px_40f"] >= b["walk_px_40f"] * 1.8,
    "no crashes": not any(v["crashed"] for v in res.values()),
    "Ruby parity + round trip": all(v["ruby"] and v["roundtrip"] for v in res.values()),
}
for k, v in checks.items(): print(("PASS " if v else "FAIL ") + k)
print("errors:", errors or "none")
