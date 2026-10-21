from devpaths import REPO, ROM_PATH, JSYAML, bench_body
import os, zipfile, subprocess, shutil, json
from playwright.sync_api import sync_playwright
S = os.path.dirname(os.path.abspath(__file__)); OUT = REPO
ROM = ROM_PATH; rom = open(ROM, "rb").read(); T = f"{S}/blk_test"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
open(f"{T}/page.html", "w").write('<!doctype html><html><head><meta charset="utf-8"></head><body>' + bench_body() + "</body></html>")
f = lambda a: a - 0x8000 + 0x10
mt = rom[f(0x8B10):f(0x8CBC)]  # all four metatile groups
mtset = {mt[i:i+4] for i in range(0, len(mt) - 3, 4)}
errors = []
def zipmap(z): return {n: zipfile.ZipFile(z).read(n) for n in zipfile.ZipFile(z).namelist()}
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    ctx.route("https://cdnjs.cloudflare.com/**/js-yaml.min.js", lambda r: r.fulfill(path=JSYAML, content_type="text/javascript"))
    ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{T}/page.html"); pg.wait_for_timeout(500)
    print("Blocks tab visible before ROM:", pg.is_visible("#tabBlocks"))
    pg.click("#tabBlocks"); pg.wait_for_timeout(200)  # no ROM: must not crash
    pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(300)
    names = pg.eval_on_selector_all(".oitem span:not(.dot)", "els => els.map(e => e.textContent)")
    print("blocks listed:", len(names), names[:6], "| heading:", pg.text_content("#hObjList"))
    # every 2x2 block in the profile is a real metatile (cols 2, row-major -> TL TR BL BR; table is TL BL TR BR)
    objs = json.loads(pg.evaluate("JSON.stringify(S.profile.objects.filter(o => o.category === 'blocks'))"))
    bad = 0; n = 0
    for o in objs:
        for fn, fr in o["frames"].items():
            toks = [0x24 if t == "." else int(t, 16) for t in fr["tiles"].split()]
            c = fr["cols"]; rows = len(toks) // c
            for r in range(0, rows, 2):
                for k in range(0, c, 2):
                    q = bytes([toks[r*c+k], toks[(r+1)*c+k] if r+1 < rows else 0x24, toks[r*c+k+1], toks[(r+1)*c+k+1] if r+1 < rows else 0x24]); n += 1
                    if q not in mtset and rows > 1: bad += 1; print("  not a metatile:", o["name"], fn, q.hex())
    print(f"metatiles checked: {n}, not found: {bad}")
    pals = json.loads(pg.evaluate("JSON.stringify(S.spritePals)")); meta = json.loads(pg.evaluate("JSON.stringify(S.profile.palettes)"))
    mism = [k for k, m in meta.items() if [int(h, 16) for h in pals[k]] != list(rom[m['offset']:m['offset'] + m.get('count', 3)])]
    print("palettes read from ROM:", len(meta), "mismatches:", mism or "none")
    # tabs don't leak: Enemies tab shows no blocks
    pg.click("#tabObjects"); pg.wait_for_timeout(150)
    en = pg.eval_on_selector_all(".oitem span:not(.dot)", "els => els.map(e => e.textContent)")
    print("enemies tab has blocks?", any(x in en for x in ("Brick", "Pipe")), "| count", len(en))
    pg.click("#tabBlocks"); pg.wait_for_timeout(150)
    # select ? Block: shimmer should animate color 1
    pg.click(f".oitem >> nth={names.index('? Block')}"); pg.wait_for_timeout(150)
    sh = pg.evaluate("() => [0, 8, 16, 24, 32, 40].map(t => JSON.stringify(objColors(curObj(), 0, t)[1]))")
    print("? block color 1 over time distinct:", len(set(sh)), "| locked slot rendered:", pg.locator("#opalSlots .slot.locked").count(), "| rows:", pg.eval_on_selector_all("#opalSlots .opal-row", "e => e.length"))
    pg.screenshot(path=f"{T}/qblock.png", full_page=True)
    # edit: shimmer color 0 -> $11, sky -> $0F
    pg.locator("#opalSlots .opal-row >> nth=1").locator(".slot >> nth=0").click(); pg.click('#opicker button[title="$11"]')
    pg.locator("#opalSlots .opal-row >> nth=2").locator(".slot >> nth=0").click(); pg.click('#opicker button[title="$0F"]')
    # Brick: paint a pixel, recolor ground bg1 slot 2 -> $2A
    pg.click(f".oitem >> nth={names.index('Brick')}"); pg.wait_for_timeout(150)
    pg.locator("#opalSlots .opal-row >> nth=0").locator(".slot >> nth=1").click(); pg.click('#opicker button[title="$2A"]')
    cv = pg.locator("#oframes canvas").first; bb = cv.bounding_box()
    v = pg.evaluate("() => composeFrame(curObj().frames.plain)[3][3]"); pg.keyboard.press(str(3 if v != 3 else 1))
    pg.mouse.click(bb["x"] + bb["width"] * 3.5 / 16, bb["y"] + bb["height"] * 3.5 / 16)
    print("tile info:", pg.text_content("#tileInfo")[:90])
    pg.click("#segArea button >> nth=2"); pg.wait_for_timeout(150)  # underground bricks
    pg.screenshot(path=f"{T}/brick_ug.png", full_page=True)
    with pg.expect_download() as d: pg.click("#btnSave")
    z1 = f"{T}/p1.zip"; d.value.save_as(z1); zipfile.ZipFile(z1).extractall(f"{T}/x")
    js = open(f"{T}/x/smb_hacked.nes", "rb").read()
    r = subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{T}/x/config.json"], capture_output=True, text=True)
    print("ruby:", r.returncode, [l for l in r.stdout.splitlines() if l.startswith(("objects", "sprite"))], r.stderr[-300:])
    rb = open(f"{T}/x/smb_hacked.nes", "rb").read()
    t47 = 0x9010 + 0x47 * 16
    diff = [i for i in range(len(rom)) if rom[i] != rb[i]]
    print("JS == Ruby:", js == rb, "| brick tile $47 changed:", rom[t47:t47+16] != rb[t47:t47+16],
          "| shimmer[0]", hex(rb[0x9D3]), "| ground sky", hex(rb[0x5E0]), "| ground.bg1", rb[0xCDC+4:0xCDC+7].hex(), "| bytes changed:", len(diff))
    # reopen round trip
    pg.evaluate("try{localStorage.clear()}catch(e){}"); pg.reload(); pg.wait_for_timeout(500)
    pg.set_input_files("#fProj", z1); pg.wait_for_timeout(800)
    with pg.expect_download() as d: pg.click("#btnSave")
    z2 = f"{T}/p2.zip"; d.value.save_as(z2)
    a, c = zipmap(z1), zipmap(z2)
    print("reopen round trip identical:", a == c, [k for k in a if a.get(k) != c.get(k)])
    b.close()
print("errors:", errors or "none")
