"""Super Mario Bros. 2 (USA, Rev 1 / PRG1): profile vs the ROM's tables, edits -> download -> Ruby parity -> reopen,
then boot the built ROM into 1-1 and check the sprites on screen. Needs SMB2_ROM=/path/to/Super Mario Bros. 2 (USA) (Rev 1).nes"""
import os, sys, json, zipfile, subprocess, shutil
from playwright.sync_api import sync_playwright
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV)
ROM = os.environ.get("SMB2_ROM") or sys.exit("Set SMB2_ROM")
rom = open(ROM, "rb").read(); T = f"{DEV}/smb2_test"; shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
CHR = 0x20010
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(accept_downloads=True, viewport={"width": 1400, "height": 1000})
    ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/index.html"); pg.wait_for_timeout(600)
    pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(800)
    print("game:", pg.text_content("#gameName"))
    prof = json.loads(pg.evaluate("JSON.stringify(SMB2_PROFILE)"))
    groups = {}
    for o in prof["objects"]: groups[o["group"]] = groups.get(o["group"], 0) + 1
    print("objects by group:", groups)
    # player frames vs CharacterTiles ($F2E4 in bank F): Mario's "walk 2" faces right, so columns swap and flip
    ct = 0x10 + 7 * 0x4000 + (0xF2E4 & 0x3FFF)
    w2 = [rom[ct + 8 + i] for i in range(4)]
    mario = next(o for o in prof["objects"] if o["name"] == "Mario")
    body = {(s[1], s[2]): s[0] for s in mario["frames"]["walk 2"]["sprites"] if s[3] is None}
    want = {(0, 0): f"{w2[1]:02X}h", (8, 0): f"{w2[0]:02X}h", (0, 16): f"{w2[3]:02X}h", (8, 16): f"{w2[2]:02X}h"}
    print("Mario walk 2 matches CharacterTiles:", all(body.get(k) == v for k, v in want.items()))
    # edits: Mario's tile, his eyes (a background tile with copies in every animated bank), Shyguy, and two palettes
    edits = pg.evaluate("""(() => { checkpoint('');
      const m = S.objs.find(o => o.name === 'Mario'), sg = S.objs.find(o => o.name === 'Shyguy');
      const body = m.frames['walk 2'].slots.find(q => q.idx < 0x40), eye = m.frames['walk 2'].slots.find(q => q.idx >= 0x100 && tileAt(q.off).some(r => r.some(v => v)));
      const shy = sg.frames['frame 1'].slots.find(q => q.idx >= 0xC0 && q.idx < 0x100);
      for (const q of [body, eye, shy]) S.chrEdits[q.off] = tileAt(q.off).map((r, y) => r.map((v, x) => y === 4 ? 3 : v));
      S.spritePals['player.mario'] = ['01', '2A', '27']; S.palEdited['player.mario'] = true;
      S.spritePals['w1.1'] = ['30', '12', '0F']; S.palEdited['w1.1'] = true;
      const wart = S.objs.find(o => o.name === 'Wart').frames.stand.slots.find(q => q && tileAt(q.off).some(r => r.some(v => v)));
      const blk = S.objs.find(o => o.name.startsWith('World 7')).frames['palette 1'].slots.find(q => q && tileAt(q.off).some(r => r.some(v => v)));
      for (const q of [wart, blk]) S.chrEdits[q.off] = tileAt(q.off).map(r => r.map(v => v ? 3 - v : 0));
      S.spritePals['w7.bg1'] = ['2A', '1A', '0F']; S.palEdited['w7.bg1'] = true; objChanged();
      return { body: body.off, eye: eye.off, shy: shy.off, wart: wart.off, blk: blk.off }; })()""")
    links = dict((int(k), v) for k, v in pg.evaluate("[...chrLinks()]"))
    print("copies that follow: eyes", len(links.get(edits["eye"], [])), "| shyguy", len(links.get(edits["shy"], [])), "| Mario body", len(links.get(edits["body"], [])))
    selected = pg.evaluate("selectObj(S.objs.findIndex(o => o.name === 'Birdo')); [curObj().name, palRows(curObj())[0].label]")
    print("Birdo opens on:", selected)
    pg.screenshot(path=f"{T}/smb2.png")
    pg.click("#btnSave"); pg.wait_for_timeout(200)
    print("download name:", pg.input_value("#dlName"))
    with pg.expect_download() as d: pg.click("#dlGo")
    z1 = f"{T}/p1.zip"; d.value.save_as(z1); zipfile.ZipFile(z1).extractall(f"{T}/x")
    names = zipfile.ZipFile(z1).namelist(); cfg = json.load(open(f"{T}/x/config.json")); print("zip:", sorted(names))
    js = open(f"{T}/x/{cfg['output']}", "rb").read()
    r = subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{T}/x/config.json"], capture_output=True, text=True)
    print("ruby:", r.returncode, r.stderr[-300:])
    rb = open(f"{T}/x/{cfg['output']}", "rb").read()
    follow = all(rb[m:m + 16] == rb[t:t + 16] for t in edits.values() for m in links.get(t, []))
    cp = 0x10 + 5 * 0x4000 + (0x8429 & 0x3FFF)
    enc = lambda px: bytes(sum(((px[y][x] & 1) << (7 - x)) for x in range(8)) for y in range(8)) + bytes(sum(((px[y][x] >> 1) << (7 - x)) for x in range(8)) for y in range(8))
    want = {int(k): v for k, v in pg.evaluate("Object.fromEntries(Object.entries(chrEditsWithLinks()))").items()}
    print("Wart + World 7 block tiles written:", all(rb[o:o + 16] == enc(want[o]) for o in (edits["wart"], edits["blk"])), "| bosses:", groups.get("Bosses"), "| worlds:", groups.get("Worlds"))
    print("JS == Ruby:", js == rb, "| bytes changed:", sum(1 for i in range(len(rom)) if rom[i] != rb[i]), "| copies follow:", follow, "| Mario palette:", rb[cp:cp + 4].hex())
    pg2 = ctx.new_page(); pg2.on("pageerror", lambda e: errors.append(str(e)))
    pg2.goto(f"file://{REPO}/index.html"); pg2.wait_for_timeout(500)
    pg2.set_input_files("#fProj", z1); pg2.wait_for_timeout(1200)
    with pg2.expect_download() as d: pg2.click("#btnSave"); pg2.click("#dlGo")
    z2 = f"{T}/p2.zip"; d.value.save_as(z2)
    A = {n: zipfile.ZipFile(z1).read(n) for n in names}; B = {n: zipfile.ZipFile(z2).read(n) for n in zipfile.ZipFile(z2).namelist()}
    print("reopen round trip identical:", A == B, [k for k in A if A.get(k) != B.get(k)])
    b.close()
try:
    import cynes, numpy as np
    from PIL import Image
    C = cynes
    nes = C.NES(f"{T}/x/{cfg['output']}")
    for n, k in [(120, 0), (5, C.NES_INPUT_START), (200, 0), (5, C.NES_INPUT_A), (600, 0)]:
        for _ in range(n): nes.controller = k; f = nes.step(1)
    Image.fromarray(f).resize((512, 480), Image.NEAREST).save(f"{T}/ingame.png")
    oam = [(nes[0x200 + 4 * k], nes[0x201 + 4 * k], nes[0x202 + 4 * k], nes[0x203 + 4 * k]) for k in range(64)]
    px = np.asarray(f).reshape(-1, 3); green = {(0x4C, 0xD0, 0x20), (76, 208, 32)}
    print("built ROM boots into 1-1:", not nes.has_crashed and nes[0x8F] == 0, "| player on screen:", sum(1 for o in oam[8:12] if o[0] < 0xEF) == 4)
except ImportError:
    print("(cynes not installed: skipped booting the built ROM)")
print("errors:", errors or "none")
