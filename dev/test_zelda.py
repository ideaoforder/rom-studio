"""The Legend of Zelda (USA) (Rev 1): raw CHR in PRG, copied to CHR-RAM per area. Edits -> download -> Ruby parity -> reopen, then
boot the built ROM, register a file and check the game's CHR-RAM in the overworld holds the painted tiles (Link, an Octorok, ground).
Needs ZELDA_ROM=/path/to/Legend of Zelda, The (USA) (Rev 1).nes"""
import os, sys, json, zipfile, subprocess, shutil
from playwright.sync_api import sync_playwright
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV)
ROM = os.environ.get("ZELDA_ROM") or sys.exit("Set ZELDA_ROM")
rom = open(ROM, "rb").read(); T = f"{DEV}/zelda_test"; shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(accept_downloads=True, viewport={"width": 1400, "height": 1000})
    ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/index.html"); pg.wait_for_timeout(600)
    pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(1200)
    print("game:", pg.text_content("#gameName"))
    prof = json.loads(pg.evaluate("JSON.stringify(ZELDA_PROFILE)"))
    groups = {}
    for o in prof["objects"]: groups[o["group"]] = groups.get(o["group"], 0) + 1
    print("objects by group:", groups, "| areas:", len(prof["areas"]), "| link sets:", len(prof.get("chr_link_sets", [])))
    # Link's walk-down frame striped; an Octorok tile filled; an overworld ground tile and a palette
    edits = pg.evaluate("""(() => { checkpoint('');
      const sim = S.objs.find(o => o.name === 'Link'), zom = S.objs.find(o => o.name === 'Octorok (red)'), blk = S.objs.find(o => o.name === 'Overworld');
      const stand = [...new Set(sim.frames['walk down'].slots.filter(Boolean).map(q => q.off))];
      for (const off of stand) S.chrEdits[off] = Array.from({length: 8}, (_, y) => Array.from({length: 8}, (_, x) => tileAt(off)[y][x] ? (y % 2 ? 1 : 2) : 0));
      const z = zom.frames['frame 1'].slots.find(q => q && tileAt(q.off).some(r => r.some(v => v))).off;
      S.chrEdits[z] = tileAt(z).map(r => r.map(v => v ? 3 : 0));
      const bg = blk.frames['room 77'].slots.find(q => q && tileAt(q.off).some(r => r.some(v => v))).off;
      S.chrEdits[bg] = tileAt(bg).map((r, y) => r.map(v => y < 2 ? 1 : v));
      S.spritePals['spr.0'] = ['2A', '1A', '0F']; S.palEdited['spr.0'] = true; objChanged();
      return { stand, z, bg }; })()""")
    links = dict((int(k), v) for k, v in pg.evaluate("[...chrLinks()]"))
    print("Link walk-down tiles:", len(edits["stand"]), "| copies that follow Link's tiles:", sum(len(links.get(o, [])) for o in edits["stand"]))
    pg.click("#btnSave"); pg.wait_for_timeout(200)
    with pg.expect_download() as d: pg.click("#dlGo")
    z1 = f"{T}/p1.zip"; d.value.save_as(z1); zipfile.ZipFile(z1).extractall(f"{T}/x")
    names = zipfile.ZipFile(z1).namelist(); cfg = json.load(open(f"{T}/x/config.json")); print("zip:", sorted(names))
    js = open(f"{T}/x/{cfg['output']}", "rb").read()
    r = subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{T}/x/config.json"], capture_output=True, text=True)
    print("ruby:", r.returncode, r.stderr[-300:])
    rb = open(f"{T}/x/{cfg['output']}", "rb").read()
    print("JS == Ruby:", js == rb, "| bytes changed:", sum(1 for i in range(len(rom)) if rom[i] != rb[i]))
    want = {int(k): v for k, v in pg.evaluate("Object.fromEntries(Object.entries(chrEditsWithLinks()))").items()}
    def enc(px): return bytes(sum(((px[y][x] & 1) << (7 - x)) for x in range(8)) for y in range(8)) + bytes(sum(((px[y][x] >> 1) << (7 - x)) for x in range(8)) for y in range(8))
    print("every edited tile (and its copies) written:", all(rb[o:o + 16] == enc(px) for o, px in want.items()), len(want))
    pg2 = ctx.new_page(); pg2.on("pageerror", lambda e: errors.append(str(e)))
    pg2.goto(f"file://{REPO}/index.html"); pg2.wait_for_timeout(500)
    pg2.set_input_files("#fProj", z1); pg2.wait_for_timeout(1500)
    with pg2.expect_download() as d: pg2.click("#btnSave"); pg2.click("#dlGo")
    z2 = f"{T}/p2.zip"; d.value.save_as(z2)
    A = {n: zipfile.ZipFile(z1).read(n) for n in names}; B = {n: zipfile.ZipFile(z2).read(n) for n in zipfile.ZipFile(z2).namelist()}
    print("reopen round trip identical:", A == B, [k for k in A if A.get(k) != B.get(k)])
    b.close()
try:
    import cynes, numpy as np
    from PIL import Image
    sys.path.insert(0, f"{DEV}/gen_zelda"); import screens as Z
    def play(path):  # register a file and stand in the first overworld room
        nes = Z.boot(path); f = None
        for _ in range(20): nes.controller = 0; f = nes.step(1)
        return nes, np.asarray(f).copy(), bytes(nes.save())[Z.VRAM:Z.VRAM + 0x2000]
    n0, f0, c0 = play(ROM); n1, f1, c1 = play(f"{T}/x/{cfg['output']}")
    Image.fromarray(np.hstack([f0, f1])).resize((1024, 480), Image.NEAREST).save(f"{T}/ingame.png")
    area = prof["chr_ram"]["areas"]["ow"]; ppu = {}
    for t0, n, o in area:
        for i in range(n): ppu[o + 16 * i] = t0 + i
    hit = [o for o in [*edits["stand"], edits["z"], edits["bg"]] if o in ppu]
    ok = all(c1[ppu[o] * 16:ppu[o] * 16 + 16] == rb[o:o + 16] and c1[ppu[o] * 16:ppu[o] * 16 + 16] != c0[ppu[o] * 16:ppu[o] * 16 + 16] for o in hit)
    diff = int((f0 != f1).any(axis=2).sum())
    print("built ROM reaches the overworld:", not n1.has_crashed and n1[0x12] == 5 and n1[0x10] == 0, "| painted tiles in the game's CHR-RAM:", ok, len(hit), "| pixels changed on screen:", diff)
except ImportError:
    print("(cynes not installed: skipped booting the built ROM)")
print("errors:", errors or "none")
