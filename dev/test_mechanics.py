"""Mechanics tab: builds variants through the page, checks Ruby parity + round trip, then measures them in an
emulator (pip install cynes). SMB_ROM required; MM3_ROM optional."""
import os, sys, json, zipfile, io, subprocess, shutil
from playwright.sync_api import sync_playwright
import cynes
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV); T = f"{DEV}/mech_test"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
SMB = os.environ.get("SMB_ROM") or sys.exit("Set SMB_ROM"); MM3 = os.environ.get("MM3_ROM")
C = cynes; R, A, B, S, U = C.NES_INPUT_RIGHT, C.NES_INPUT_A, C.NES_INPUT_B, C.NES_INPUT_START, C.NES_INPUT_UP
D, L = C.NES_INPUT_DOWN, C.NES_INPUT_LEFT
errors = []
def build(pw, rom, settings, tag):
    ctx = pw.new_context(accept_downloads=True); ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/index.html"); pg.wait_for_timeout(500); pg.set_input_files("#fRom", rom); pg.wait_for_timeout(600)
    pg.evaluate("(m) => { S.mech = m; persist(); }", settings)
    with pg.expect_download() as d: pg.click("#btnSave"); pg.click("#dlGo")
    z1 = f"{T}/{tag}.zip"; d.value.save_as(z1); x = f"{T}/{tag}"; zipfile.ZipFile(z1).extractall(x)
    name = json.load(open(f"{x}/config.json"))["output"]; js = open(f"{x}/{name}", "rb").read()
    subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{x}/config.json"], capture_output=True, check=True)
    parity = open(f"{x}/{name}", "rb").read() == js
    pg2 = ctx.new_page(); pg2.goto(f"file://{REPO}/index.html"); pg2.wait_for_timeout(500); pg2.set_input_files("#fProj", z1); pg2.wait_for_timeout(900)
    with pg2.expect_download() as d: pg2.click("#btnSave"); pg2.click("#dlGo")
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
    def peak(seq):
        nes = smb_boot(path); y0 = nes[0xCE]; ys = []
        for n, b in seq:
            for _ in range(n): nes.controller = b; nes.step(1); ys.append(nes[0xCE])
        return y0 - min(ys)
    o["air"] = [peak([(30, A), (10, 0)] + [(20, A), (6, 0)] * k + [(90, 0)]) for k in (0, 1, 4)]  # 0, 1 and 4 presses in mid-air
    nes = smb_boot(path); l0 = nes[0x75A]
    for t in range(1200): nes.controller = R if t < 900 else 0; nes.step(1)
    o["lives_lost"] = l0 - nes[0x75A]; o["got_past_goomba"] = nes[0x6D] > 0
    nes = smb_boot(path); o["start_power"] = (nes[0x754], nes[0x756])  # (size 0 = big, status 0/1/2 = small/super/fire)
    for _ in range(40): nes.controller = R; nes.step(1)
    nes[0xCE] = 0xF0; nes[0xB5] = 1  # drop into a pit
    for _ in range(700): nes.controller = 0; nes.step(1)
    o["after_death"] = (nes[0x754], nes[0x756])
    for t in range(30): nes.controller = B if t < 3 else 0; nes.step(1)  # B throws a fireball only when fiery
    o["fireball"] = any(nes[0x24 + i] for i in range(2))
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
    def peak(seq):
        nes = mm3_boot(path); y0 = nes[0x3C0]; ys = []
        for n, b in seq:
            for _ in range(n): nes.controller = b; nes.step(1); ys.append(nes[0x3C0])
        return y0 - min(ys)
    o["air"] = [peak([(25, A), (3, 0)] + [(25, A), (3, 0)] * k + [(100, 0)]) for k in (0, 1, 3)]
    o["owned"] = sum(nes[a] >= 0x80 for a in range(0xA3, 0xAE))  # weapons + Rush with the "have it" bit
    nes = mm3_boot(path); nes[0xA3] = 0x9C; nes[0xA0] = 1
    for t in range(200): nes.controller = B if t % 12 < 2 else 0; nes.step(1)
    o["gemini_left"] = nes[0xA3] & 0x1F
    # Mega Buster: shot speed (px/frame) and most shots alive at once while holding rapid fire
    nes = mm3_boot(path); last = {}; speeds = []; most = 0
    for t in range(240):
        nes.controller = B if t % 6 < 2 else 0; nes.step(1)
        alive = [sl for sl in (1, 2, 3) if nes[0x300 + sl] & 0x80]; most = max(most, len(alive))
        for sl in alive:
            x = nes[0x380 + sl] * 256 + nes[0x360 + sl]
            if sl in last and 0 < x - last[sl] < 32: speeds.append(x - last[sl])
            last[sl] = x
        for sl in set(last) - set(alive): last.pop(sl)
    o["shot_px_per_frame"] = max(set(speeds), key=speeds.count) if speeds else 0; o["most_shots"] = most
    return o
def mm3_aim(path):  # first Mega Buster (or Shadow Blade) shot's movement over 3 frames for each held direction
    out = {}
    for lab, hold, weapon in [("none", 0, 0), ("up", U, 0), ("up+right", U | R, 0), ("down", D, 0), ("down+left", D | L, 0), ("blade up", U, 10), ("blade", 0, 10)]:
        nes = mm3_boot(path)
        if weapon: nes[0xA0] = weapon; nes[0xA2 + weapon] = 0x9C
        tr = []
        for t in range(90):
            nes.controller = hold | (B if t < 2 else 0); nes.step(1)
            if nes[0x301] & 0x80: tr.append((nes[0x381] * 256 + nes[0x361], nes[0x3E1] * 240 + nes[0x3C1]))
        out[lab] = (tr[3][0] - tr[0][0], tr[3][1] - tr[0][1], len(tr)) if len(tr) > 3 else None
    return out
with sync_playwright() as p:
    pw = p.chromium.launch()
    smb = {}
    for tag, st in [("smb_base", {}), ("smb_moon", {"gravity": 25, "jump": 150}), ("smb_fast", {"speed": 150}), ("smb_ice", {"grip": 25}),
                    ("smb_inv", {"invincible": True}), ("smb_lives", {"lives": True}), ("smb_flap", {"flap": True}),
                    ("smb_big", {"start": 1}), ("smb_double", {"airjump": 1}), ("smb_fire", {"start": 2})]:
        path, parity, same = build(pw, SMB, st, tag); smb[tag] = smb_measure(path); smb[tag]["ruby"] = parity; smb[tag]["roundtrip"] = same
    for k, v in smb.items(): print(k, v)
    b = smb["smb_base"]
    checks = {"moon jumps higher": smb["smb_moon"]["jump_px"] > b["jump_px"] * 1.3, "fast is faster": smb["smb_fast"]["top_speed"] > b["top_speed"],
              "ice takes longer to speed up": smb["smb_ice"]["frames_to_top"] > b["frames_to_top"] * 2, "flap rises mid-air (old saved flap toggle still works)": smb["smb_flap"]["flap_rise_px"] > 20 and b["flap_rise_px"] == 0,
              "air jumps: off = 1 jump, double = 1 extra, flap = keeps climbing": b["air"][0] == b["air"][1] == b["air"][2] and smb["smb_double"]["air"][1] > b["air"][0] * 1.4 and smb["smb_double"]["air"][2] <= smb["smb_double"]["air"][1] and smb["smb_flap"]["air"][2] > smb["smb_double"]["air"][2] * 1.3,
              "invincible survives the goomba": smb["smb_inv"]["got_past_goomba"] and smb["smb_inv"]["lives_lost"] == 0 and b["lives_lost"] > 0,
              "infinite lives keeps the count": smb["smb_lives"]["lives_lost"] == 0,
              "start Big, and Big again after a death": smb["smb_big"]["start_power"] == (0, 1) and smb["smb_big"]["after_death"] == (0, 1) and b["after_death"] == (1, 0),
              "start Fire, again after a death, throws fireballs": smb["smb_fire"]["start_power"] == (0, 2) and smb["smb_fire"]["after_death"] == (0, 2) and smb["smb_fire"]["fireball"] and not smb["smb_big"]["fireball"], "Ruby parity + round trip": all(v["ruby"] and v["roundtrip"] for v in smb.values())}
    if MM3:
        mm = {}
        for tag, st in [("mm3_base", {}), ("mm3_floaty", {"gravity": 50, "jump": 150}), ("mm3_fast", {"speed": 150}), ("mm3_double", {"airjump": 1}), ("mm3_fly", {"airjump": 2, "jump": 150}), ("mm3_inv", {"invincible": True, "allweapons": True}), ("mm3_ammo", {"ammo": True, "power": 1000}),
                        ("mm3_weap", {"shotspeed": 150, "w0.shots": 1, "w1.cost": 0, "w1.dmg": 300, "power": 200, "w8.sound": 0x2E, "hitbox": 200})]:
            path, parity, same = build(pw, MM3, st, tag); mm[tag] = mm3_measure(path); mm[tag]["ruby"] = parity; mm[tag]["roundtrip"] = same
        for tag, st in [("mm3_aim", {"aim": True}), ("mm3_aim_fast", {"aim": True, "shotspeed": 150})]:
            path, parity, same = build(pw, MM3, st, tag); mm[tag] = {"aim": mm3_aim(path), "ruby": parity, "roundtrip": same}
        mm["mm3_base"]["aim"] = mm3_aim(f"{T}/mm3_base.nes")
        for k, v in mm.items(): print(k, v)
        b = mm["mm3_base"]; rom = open(f"{T}/mm3_ammo.nes", "rb").read(); orig = open(MM3, "rb").read(); wr = open(f"{T}/mm3_weap.nes", "rb").read()
        F3 = lambda bank, a: 0x10 + bank * 0x2000 + (a & 0x1FFF)
        def weap_dmg_ok():  # Gemini table x2 (global) x3 (Gemini), others x2, capped at 28, 0/$58 untouched
            ok = True
            for base, mul in [(0xA400, 6), (0xA100, 2), (0xA800, 2)]:
                for i in range(256):
                    o0 = orig[F3(0x0A, base) + i]; want = o0 if o0 in (0, 0x58) else min(28, o0 * mul) if base != 0xA800 or o0 * 2 != 0x58 else o0
                    if base == 0xA400 and o0 not in (0, 0x58): want = min(28, min(28, o0 * 2) * 3)
                    ok &= wr[F3(0x0A, base) + i] == want
            return ok
        def weap_bytes_ok():
            hb = all(wr[F3(0x1F, 0xFC03) + i] == min(0x60, max(1, orig[F3(0x1F, 0xFC03) + i] * 2)) for i in range(64))
            return wr[F3(0x1E, 0xD349 + 8)] == 0x2E and hb
        dmg = 0x10 + 0x0A * 0x2000 + 0x100
        checks.update({"MM3 floaty jumps higher": mm["mm3_floaty"]["jump_px"] > b["jump_px"] * 2, "MM3 fast walks farther": mm["mm3_fast"]["walk_px"] > b["walk_px"] * 1.25,
                       "MM3 invincible keeps full health": mm["mm3_inv"]["lowest_health"] == 28 and b["lowest_health"] < 28,
                       "MM3 air jumps: double = 1 extra, unlimited keeps climbing (and follows Jump height)": b["air"][0] == b["air"][1] == b["air"][2] and mm["mm3_double"]["air"][0] == b["air"][0] and mm["mm3_double"]["air"][1] > b["air"][0] * 1.5 and mm["mm3_double"]["air"][2] == mm["mm3_double"]["air"][1] and mm["mm3_fly"]["air"][2] > mm["mm3_double"]["air"][2] * 1.5,
                       "MM3 start with every weapon": mm["mm3_inv"]["owned"] == 11 and b["owned"] == 1,
                       "MM3 weapons don't drain": mm["mm3_ammo"]["gemini_left"] == 28 and b["gemini_left"] < 28,
                       "MM3 one-hit damage tables": all((rom[dmg + i] == 28) == (orig[dmg + i] not in (0, 0x58)) for i in range(9 * 256)),
                       "MM3 shot speed 4 -> 6 px/frame": b["shot_px_per_frame"] == 4 and mm["mm3_weap"]["shot_px_per_frame"] == 6,
                       "MM3 Mega Buster limited to 1 shot": b["most_shots"] == 3 and mm["mm3_weap"]["most_shots"] == 1,
                       "MM3 Gemini costs nothing (only Gemini)": mm["mm3_weap"]["gemini_left"] == 28,
                       "MM3 per-weapon damage compounds with power": weap_dmg_ok(),
                       "MM3 Spark sound + bigger target boxes": weap_bytes_ok(),
                       "MM3 aim: up/down/diagonal shots (off: always straight); blade keeps returning": all(v[1] == 0 for k, v in b["aim"].items() if k.startswith(("none", "up", "down")))
                           and (lambda a: a["none"][:2] == (12, 0) and a["up"][:2] == (0, -12) and a["up+right"][:2] == (12, -12) and a["down"][:2] == (0, 12) and a["down+left"][:2] == (-12, 12)
                                and a["blade up"] == b["aim"]["blade up"] and a["blade"] == b["aim"]["blade"])(mm["mm3_aim"]["aim"])
                           and mm["mm3_aim_fast"]["aim"]["up+right"][:2] == (18, -18),
                       "MM3 Ruby parity + round trip": all(v["ruby"] and v["roundtrip"] for v in mm.values())})
    pw.close()
for k, v in checks.items(): print(("PASS " if v else "FAIL ") + k)
print("errors:", errors or "none")
