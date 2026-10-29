"""Contra (USA): compressed CHR-RAM graphics. Edits -> download -> Ruby parity -> reopen, then:
- re-decode every edited block from the built ROM through the game's own pointer table (relocated blocks included),
- boot the built ROM and check Bill on screen shows the painted pattern.
Needs CONTRA_ROM=/path/to/Contra (USA).nes"""
import os, sys, json, zipfile, subprocess, shutil, random
from playwright.sync_api import sync_playwright
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV)
ROM = os.environ.get("CONTRA_ROM") or sys.exit("Set CONTRA_ROM")
rom = open(ROM, "rb").read(); T = f"{DEV}/contra_test"; shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
errors = []

def gfx_decode(b, off):
    buf = bytearray(0x2000); p = off; ppu = b[p] | b[p + 1] << 8; p += 2
    while True:
        c = b[p]
        if c == 0xFF: return buf, p + 1 - off
        if c == 0x7F: ppu = b[p + 1] | b[p + 2] << 8; p += 3; continue
        if c < 0x80:
            for _ in range(c):
                if ppu < 0x2000: buf[ppu] = b[p + 1]
                ppu += 1
            p += 2
        else:
            n = c & 0x7F
            for k in range(n):
                if ppu < 0x2000: buf[ppu] = b[p + 1 + k]
                ppu += 1
            p += 1 + n

with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(accept_downloads=True, viewport={"width": 1400, "height": 1000})
    ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/index.html"); pg.wait_for_timeout(600)
    pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(1000)
    print("game:", pg.text_content("#gameName"))
    prof = json.loads(pg.evaluate("JSON.stringify(CONTRA_PROFILE)")); C = prof["chr_ram"]
    groups = {}
    for o in prof["objects"]: groups[o["group"]] = groups.get(o["group"], 0) + 1
    print("objects by group:", groups, "| areas:", len(C["areas"]), "| link sets:", len(prof["chr_link_sets"]))
    # 1) Bill's standing frame: every tile painted with a stripe pattern (block 03 grows -> moves into bank 4's free space)
    # 2) prone tiles: copies in every outdoor level follow   3) a palette edit   4) speckle noise on soldier tiles (block 1a, bank 5)
    edits = pg.evaluate("""(() => { checkpoint('');
      const bill = S.objs.find(o => o.name === 'Bill'), sol = S.objs.find(o => o.name === 'Soldier');
      const stand = [...new Set(bill.frames['walk & aim 3'].slots.filter(Boolean).map(q => q.off))];
      for (const off of stand) S.chrEdits[off] = Array.from({length: 8}, (_, y) => Array.from({length: 8}, (_, x) => tileAt(off)[y][x] ? (y % 2 ? 1 : 2) : 0));
      const prone = bill.frames.prone.slots.find(q => q && chrLinks().has(q.off)).off;
      S.chrEdits[prone] = tileAt(prone).map(r => r.map(v => v ? 3 : 0));
      let seed = 7; const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
      const sold = [...new Set(Object.values(sol.frames).flatMap(f => f.slots.filter(Boolean).map(q => q.off)))].slice(0, 24);
      for (const off of sold) S.chrEdits[off] = tileAt(off).map(r => r.map(v => v ? 1 + Math.floor(rnd() * 3) : 0));
      S.spritePals['gp.00'] = ['37', '1A', '0F']; S.palEdited['gp.00'] = true; objChanged();
      return { stand, prone, sold }; })()""")
    links = dict((int(k), v) for k, v in pg.evaluate("[...chrLinks()]"))
    print("Bill stand tiles:", len(edits["stand"]), "| prone copies that follow:", len(links.get(edits["prone"], [])), "| soldier tiles speckled:", len(edits["sold"]))
    pg.click("#btnSave"); pg.wait_for_timeout(200)
    with pg.expect_download() as d: pg.click("#dlGo")
    z1 = f"{T}/p1.zip"; d.value.save_as(z1); zipfile.ZipFile(z1).extractall(f"{T}/x")
    names = zipfile.ZipFile(z1).namelist(); cfg = json.load(open(f"{T}/x/config.json")); print("zip:", sorted(names))
    js = open(f"{T}/x/{cfg['output']}", "rb").read()
    r = subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{T}/x/config.json"], capture_output=True, text=True)
    print("ruby:", r.returncode, [l for l in r.stdout.splitlines() if "graphics block" in l], r.stderr[-300:])
    rb = open(f"{T}/x/{cfg['output']}", "rb").read()
    print("JS == Ruby:", js == rb, "| bytes changed:", sum(1 for i in range(len(rom)) if rom[i] != rb[i]))
    # every edited tile, read back through the game's pointer table
    ok = True; moved = []
    want = {int(k): v for k, v in pg.evaluate("Object.fromEntries(Object.entries(chrEditsWithLinks()))").items()}
    for off, px in want.items():
        if off < C["vbase"]: continue
        blk = (off - C["vbase"]) // 0x2000; ppu = (off - C["vbase"]) % 0x2000; info = C["blocks"][str(blk)]
        t = C["ptr_table"] + 3 * blk; cpu = rb[t] | rb[t + 1] << 8; fo = 0x10 + info["bank"] * 0x4000 + (cpu - 0x8000)
        if fo != info["offset"] and blk not in moved: moved.append(blk)
        buf, _ = gfx_decode(rb, fo)
        lo = bytes(sum(((px[y][x] & 1) << (7 - x)) for x in range(8)) for y in range(8)); hi = bytes(sum(((px[y][x] >> 1) << (7 - x)) for x in range(8)) for y in range(8))
        ok &= bytes(buf[ppu:ppu + 16]) == lo + hi
    print("edited tiles decode back through the pointer table:", ok, "| blocks moved to free space:", [f"{m:02x}" for m in moved])
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
    def boot(path):
        nes = cynes.NES(path); f = None
        for n, k in [(300, 0), (5, cynes.NES_INPUT_START), (60, 0), (5, cynes.NES_INPUT_START), (600, 0)]:
            for _ in range(n): nes.controller = k; f = nes.step(1)
        return nes, np.asarray(f).copy()
    n0, f0 = boot(ROM); n1, f1 = boot(f"{T}/x/{cfg['output']}")
    Image.fromarray(np.hstack([f0, f1])).resize((1024, 480), Image.NEAREST).save(f"{T}/ingame.png")
    box = (slice(70, 125), slice(30, 80))  # where Bill stands at the start of level 1
    diff = (f0[box] != f1[box]).any(axis=2).sum()
    print("built ROM boots into level 1:", not n1.has_crashed and n1[0x30] == 0, "| Bill's pixels changed on screen:", int(diff))
except ImportError:
    print("(cynes not installed: skipped booting the built ROM)")
print("errors:", errors or "none")
