"""Mega Man 3 profile: frames vs the game's sprite tables, painting + palettes, Ruby parity, links, round trip.
Needs MM3_ROM=/path/to/Mega Man 3 (USA).nes (393,232 bytes). Optionally `pip install cynes` to boot the built ROM."""
import os, sys, json, zipfile, subprocess, shutil
from playwright.sync_api import sync_playwright
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV)
ROM = os.environ.get("MM3_ROM") or sys.exit("Set MM3_ROM")
rom = open(ROM, "rb").read(); T = f"{DEV}/mm3_test"; shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
C = 0x10 + 256 * 1024
def s8(v): return v - 256 if v > 127 else v
PRG = lambda b: 0x10 + b * 0x2000
def frame_model(b, fid):  # independent re-implementation of the renderer at $1FF13B (facing right = no flip)
    base = PRG(b); p = rom[base + 0x100 + fid] | rom[base + 0x200 + fid] << 8; o = base + p - 0x8000
    ob = PRG(0x14 if rom[o] & 0x80 else 0x19); idx = rom[o + 1]
    q = rom[ob + 0x1E00 + idx] | rom[ob + 0x1F00 + idx] << 8; qo = ob + q - 0xA000 - 2
    return [(rom[o + 2 + 2 * k], rom[o + 3 + 2 * k], s8(rom[qo + 3 + 2 * k]), s8(rom[qo + 2 + 2 * k])) for k in range((rom[o] & 0x7F) + 1)]
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(accept_downloads=True, viewport={"width": 1400, "height": 1000})
    ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/index.html"); pg.wait_for_timeout(600)
    pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(500)
    print("game:", pg.text_content("#gameName"), "| tab:", pg.text_content("#tabObjects"), "| player tab hidden:", pg.is_hidden("#tabPlayer"))
    # every frame's sprites vs the ROM tables (stand = anim 01 frame id 10, etc.)
    prof = json.loads(pg.evaluate("JSON.stringify(MM3_PROFILE)"))
    fids = {"stand": 10, "walk 1": 7, "jump": 15, "climb top": 6, "slide": 27, "hurt flash": 14}
    ok = True
    for name, fid in fids.items():
        want = [((f"{t:02X}" + ("h" if a & 0x40 else "") + ("v" if a & 0x80 else "")), dx, dy, a & 3) for (t, a, dx, dy) in frame_model(0x1A, fid)]
        got = [(s[0], s[1], s[2], 0 if s[3] is None else 1) for s in prof["objects"][0]["frames"][name]["sprites"]]
        ok &= want == got
    print("profile frames match the ROM's sprite tables:", ok)
    groups = {}
    for o in prof["objects"]: groups[o.get("group")] = groups.get(o.get("group"), 0) + 1
    print("objects by group:", groups)
    # bosses draw from bank $15 during the fight: Hard Man's first frame vs that table
    hm = next(o for o in prof["objects"] if o["name"] == "Hard Man")
    base = PRG(0x15); aid = 0x2B; p0 = rom[base + aid] | rom[base + 0x80 + aid] << 8; ao = base + p0 - 0x8000
    want = [((f"{t:02X}" + ("h" if a & 0x40 else "") + ("v" if a & 0x80 else "")), dx, dy) for (t, a, dx, dy) in frame_model(0x15, rom[ao + 2])]
    print("Hard Man frame 1 matches the boss table:", [tuple(x[:3]) for x in hm["frames"]["1"]["sprites"]] == want)
    pg.screenshot(path=f"{T}/mm3.png")
    # paint the stand frame, recolor body (Mega Buster) and face
    # paint a tile that lives in the per-weapon bank ($40-$7F), so its copies must follow
    tile_off = pg.evaluate("(() => { const f = curObj().frames.shoot; return f.slots.find(q => q.idx >= 0x40 && q.idx < 0x80 && chrLinks().has(q.off)).off; })()")
    pg.evaluate("""(off) => { checkpoint(''); const f = curObj().frames.shoot; const q = f.slots.find(q => q.off === off);
       let done = false; for (let y = 0; y < 8 && !done; y++) for (let x = 0; x < 8 && !done; x++) { const hit = slotAt(f, q.x + x, q.y + y);
         if (hit && hit.s === q) { setObjPixel(f, q.x + x, q.y + y, (tileAt(q.off)[hit.ly][hit.lx] + 1) % 4); done = true; } }
       S.spritePals['body.0'] = ['0F','16','06']; S.palEdited['body.0'] = true; S.spritePals['face'] = ['0F','30','27']; S.palEdited['face'] = true; objChanged(); }""", tile_off)
    # and an enemy that appears with different CHR banks in other stages
    enemy_off = pg.evaluate("""(() => { const o = S.objs.find(o => o.chr_alt.length && Object.values(o.frames).some(f => f.slots.some(q => chrLinks().has(q.off))));
       const f = Object.values(o.frames).find(f => f.slots.some(q => chrLinks().has(q.off))); const q = f.slots.find(q => chrLinks().has(q.off));
       S.chrEdits[q.off] = tileAt(q.off).map(r => r.map(v => (v + 1) % 4)); return q.off; })()""")
    links = dict((int(k), v) for k, v in pg.evaluate("[...chrLinks()]"))
    print("linked copies for the painted tile:", len(links.get(tile_off, [])), "| tiles with copies:", len(links))
    with pg.expect_download() as d: pg.click("#btnSave")
    z1 = f"{T}/p1.zip"; d.value.save_as(z1); zipfile.ZipFile(z1).extractall(f"{T}/x")
    names = zipfile.ZipFile(z1).namelist(); print("zip:", sorted(names))
    js = open(f"{T}/x/game_hacked.nes", "rb").read()
    r = subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{T}/x/config.json"], capture_output=True, text=True)
    print("ruby:", r.returncode, r.stdout.strip().splitlines()[:2], r.stderr[-300:])
    rb = open(f"{T}/x/game_hacked.nes", "rb").read()
    diff = [i for i in range(len(rom)) if rom[i] != rb[i]]
    mir_ok = all(rb[m:m + 16] == rb[t:t + 16] for t in (tile_off, enemy_off) for m in links.get(t, []))
    print("JS == Ruby:", js == rb, "| bytes changed:", len(diff), "| painted tile changed:", rom[tile_off:tile_off+16] != rb[tile_off:tile_off+16], "| copies follow:", mir_ok)
    A641 = PRG(2) + 0x641; C898 = PRG(0x1E) + 0x898
    print("palettes: body", rb[A641:A641+3].hex(), "start copy", rb[C898+1:C898+4].hex(), "face", rb[C898+5:C898+8].hex())
    # reopen round trip
    pg2 = ctx.new_page(); pg2.on("pageerror", lambda e: errors.append(str(e)))
    pg2.goto(f"file://{REPO}/index.html"); pg2.wait_for_timeout(500)
    pg2.set_input_files("#fProj", z1); pg2.wait_for_timeout(1000)
    with pg2.expect_download() as d: pg2.click("#btnSave")
    z2 = f"{T}/p2.zip"; d.value.save_as(z2)
    A = {n: zipfile.ZipFile(z1).read(n) for n in names}; B = {n: zipfile.ZipFile(z2).read(n) for n in zipfile.ZipFile(z2).namelist()}
    print("reopen round trip identical:", A == B, [k for k in A if A.get(k) != B.get(k)])
    b.close()
try:
    import cynes, numpy as np
    from PIL import Image
    nes = cynes.NES(f"{T}/x/game_hacked.nes")
    for n, btn in [(240, 0), (5, cynes.NES_INPUT_START), (180, 0), (5, cynes.NES_INPUT_START), (180, 0), (8, cynes.NES_INPUT_UP), (30, 0), (5, cynes.NES_INPUT_START), (1000, 0)]:
        for _ in range(n): nes.controller = btn; f = nes.step(1)
    Image.fromarray(f).resize((512, 480), Image.NEAREST).save(f"{T}/ingame.png")
    print("built ROM boots to gameplay:", not nes.has_crashed, "| sprite palette in RAM:", " ".join(f"{nes[0x610 + i]:02X}" for i in range(8)))
except ImportError:
    print("(cynes not installed: skipped booting the built ROM)")
print("errors:", errors or "none")
