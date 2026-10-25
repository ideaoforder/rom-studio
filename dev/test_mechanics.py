"""Mechanics tab: builds variants through the page, checks Ruby parity + round trip, then measures them in an
emulator (pip install cynes). SMB_ROM required; MM3_ROM optional."""
import os, sys, json, zipfile, io, subprocess, shutil
from playwright.sync_api import sync_playwright
import cynes
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV); T = f"{DEV}/mech_test"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
SMB = os.environ.get("SMB_ROM") or sys.exit("Set SMB_ROM"); MM3 = os.environ.get("MM3_ROM")
C = cynes; R, A, B, S, U = C.NES_INPUT_RIGHT, C.NES_INPUT_A, C.NES_INPUT_B, C.NES_INPUT_START, C.NES_INPUT_UP
errors = []
def build(pw, rom, settings, tag):
    ctx = pw.new_context(accept_downloads=True); ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/index.html"); pg.wait_for_timeout(500); pg.set_input_files("#fRom", rom); pg.wait_for_timeout(600)
    pg.evaluate("(m) => { S.mech = m; persist(); }", settings)
    with pg.expect_download() as d: pg.click("#btnSave")
    z1 = f"{T}/{tag}.zip"; d.value.save_as(z1); x = f"{T}/{tag}"; zipfile.ZipFile(z1).extractall(x)
    name = [n for n in os.listdir(x) if n.endswith("_hacked.nes")][0]; js = open(f"{x}/{name}", "rb").read()
    subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{x}/config.json"], capture_output=True, check=True)
    parity = open(f"{x}/{name}", "rb").read() == js
    pg2 = ctx.new_page(); pg2.goto(f"file://{REPO}/index.html"); pg2.wait_for_timeout(500); pg2.set_input_files("#fProj", z1); pg2.wait_for_timeout(900)
    with pg2.expect_download() as d: pg2.click("#btnSave")
    z2 = f"{T}/{tag}_re.zip"; d.value.save_as(z2)
    same = {n: zipfile.ZipFile(z1).read(n) for n in zipfile.ZipFile(z1).namelist()} == {n: zipfile.ZipFile(z2).read(n) for n in zipfile.ZipFile(z2).namelist()}
    ctx.close(); path = f"{T}/{tag}.nes"; open(path, "wb").write(js)
    return path, parity, same
s8 = lambda v: v - 256 if v > 127 else v
def smb_boot(path):
    nes = C.NES(path)
    for n, b in [(60, 0), (5, S), (220, 0)]:
        for _ in range(n): nes.controller = b; nes.step(1)
    return nes
def smb_measure(path):
    o = {}; nes = smb_boot(path); y0 = nes[0xCE]; ys = []
    for _ in range(90): nes.controller = A; nes.step(1); ys.append(nes[0xCE])
    o["jump_px"] = y0 - min(ys)
    nes = smb_boot(path); sp = []
    for _ in range(120): nes.controller = R | B; nes.step(1); sp.append(s8(nes[0x57]))
    o["top_speed"] = max(sp); o["frames_to_top"] = sp.index(max(sp))
    nes = smb_boot(path)
    for n, b in [(25, A), (10, 0), (4, A)]:
        for _ in range(n): nes.controller = b; nes.step(1)
    yb = nes[0xCE]; ys = []
    for _ in range(20): nes.controller = A; nes.step(1); ys.append(nes[0xCE])
    o["flap_rise_px"] = max(0, yb - min(ys))
    nes = smb_boot(path); l0 = nes[0x75A]
    for t in range(1200): nes.controller = R if t < 900 else 0; nes.step(1)
    o["lives_lost"] = l0 - nes[0x75A]; o["got_past_goomba"] = nes[0x6D] > 0
    return o
def mm3_boot(path):
    nes = C.NES(path)
    for n, b in [(240, 0), (5, S), (180, 0), (5, S), (180, 0), (8, U), (30, 0), (5, S), (900, 0)]:
        for _ in range(n): nes.controller = b; nes.step(1)
    return nes
def mm3_measure(path):
    o = {}; nes = mm3_boot(path); y0 = nes[0x3C0]; ys = []
    for _ in range(120): nes.controller = A; nes.step(1); ys.append(nes[0x3C0])
    o["jump_px"] = y0 - min(ys)
    nes = mm3_boot(path); x0 = nes[0x380] * 256 + nes[0x360]
    for _ in range(60): nes.controller = R; nes.step(1)
    o["walk_px"] = nes[0x380] * 256 + nes[0x360] - x0
    nes = mm3_boot(path); low = 28
    for t in range(2500):
        nes.controller = R | (A if (t // 40) % 3 == 0 else 0); nes.step(1); low = min(low, nes[0xA2] & 0x1F)
    o["lowest_health"] = low
    nes = mm3_boot(path); nes[0xA3] = 0x9C; nes[0xA0] = 1
    for t in range(200): nes.controller = B if t % 12 < 2 else 0; nes.step(1)
    o["gemini_left"] = nes[0xA3] & 0x1F
    return o
with sync_playwright() as p:
    pw = p.chromium.launch()
    smb = {}
    for tag, st in [("smb_base", {}), ("smb_moon", {"gravity": 25, "jump": 150}), ("smb_fast", {"speed": 150}), ("smb_ice", {"grip": 25}),
                    ("smb_inv", {"invincible": True}), ("smb_lives", {"lives": True}), ("smb_flap", {"flap": True})]:
        path, parity, same = build(pw, SMB, st, tag); smb[tag] = smb_measure(path); smb[tag]["ruby"] = parity; smb[tag]["roundtrip"] = same
    for k, v in smb.items(): print(k, v)
    b = smb["smb_base"]
    checks = {"moon jumps higher": smb["smb_moon"]["jump_px"] > b["jump_px"] * 1.3, "fast is faster": smb["smb_fast"]["top_speed"] > b["top_speed"],
              "ice takes longer to speed up": smb["smb_ice"]["frames_to_top"] > b["frames_to_top"] * 2, "flap rises mid-air": smb["smb_flap"]["flap_rise_px"] > 20 and b["flap_rise_px"] == 0,
              "invincible survives the goomba": smb["smb_inv"]["got_past_goomba"] and smb["smb_inv"]["lives_lost"] == 0 and b["lives_lost"] > 0,
              "infinite lives keeps the count": smb["smb_lives"]["lives_lost"] == 0, "Ruby parity + round trip": all(v["ruby"] and v["roundtrip"] for v in smb.values())}
    if MM3:
        mm = {}
        for tag, st in [("mm3_base", {}), ("mm3_floaty", {"gravity": 50, "jump": 150}), ("mm3_fast", {"speed": 150}), ("mm3_inv", {"invincible": True}), ("mm3_ammo", {"ammo": True, "power": 1000})]:
            path, parity, same = build(pw, MM3, st, tag); mm[tag] = mm3_measure(path); mm[tag]["ruby"] = parity; mm[tag]["roundtrip"] = same
        for k, v in mm.items(): print(k, v)
        b = mm["mm3_base"]; rom = open(f"{T}/mm3_ammo.nes", "rb").read(); orig = open(MM3, "rb").read()
        dmg = 0x10 + 0x0A * 0x2000 + 0x100
        checks.update({"MM3 floaty jumps higher": mm["mm3_floaty"]["jump_px"] > b["jump_px"] * 2, "MM3 fast walks farther": mm["mm3_fast"]["walk_px"] > b["walk_px"] * 1.25,
                       "MM3 invincible keeps full health": mm["mm3_inv"]["lowest_health"] == 28 and b["lowest_health"] < 28,
                       "MM3 weapons don't drain": mm["mm3_ammo"]["gemini_left"] == 28 and b["gemini_left"] < 28,
                       "MM3 one-hit damage tables": all((rom[dmg + i] == 28) == (orig[dmg + i] not in (0, 0x58)) for i in range(9 * 256)),
                       "MM3 Ruby parity + round trip": all(v["ruby"] and v["roundtrip"] for v in mm.values())})
    pw.close()
for k, v in checks.items(): print(("PASS " if v else "FAIL ") + k)
print("errors:", errors or "none")
