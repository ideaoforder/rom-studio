from devpaths import REPO, ROM_PATH, JSYAML, bench_body
import os, zipfile, subprocess, shutil, json
from playwright.sync_api import sync_playwright
S = os.path.dirname(os.path.abspath(__file__)); OUT = REPO
ROM = ROM_PATH; rom = open(ROM, "rb").read(); T = f"{S}/pu_test"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
open(f"{T}/page.html", "w").write('<!doctype html><html><head><meta charset="utf-8"></head><body>' + bench_body() + "</body></html>")
TBL = 0xE6BE - 0x8000 + 0x10
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    ctx.route("https://cdnjs.cloudflare.com/**/js-yaml.min.js", lambda r: r.fulfill(path=JSYAML, content_type="text/javascript"))
    ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{T}/page.html"); pg.wait_for_timeout(500)
    prof = {o["name"]: o for o in json.loads(pg.evaluate("JSON.stringify(S.profile.objects)"))}
    for name, frame, idx in [("Mushroom", "mushroom", 0), ("Fire Flower", "flower", 1), ("Starman", "star", 2)]:
        got = sorted(int(t[:2], 16) for t in prof[name]["frames"][frame]["tiles"].split())
        want = sorted(rom[TBL + idx * 4: TBL + idx * 4 + 4])
        print(f"{name}: tiles {'match' if got == want else 'MISMATCH'} ROM table", [hex(x) for x in want])
    print("1-Up table row == Super row:", rom[TBL:TBL + 4] == rom[TBL + 12:TBL + 16], "| attrs", list(rom[TBL + 16:TBL + 20]))
    pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(300); pg.click("#tabObjects"); pg.wait_for_timeout(200)
    names = pg.eval_on_selector_all(".oitem span:not(.dot)", "els => els.map(e => e.textContent)")
    print("objects:", names)
    pg.click(f".oitem >> nth={names.index('Fire Flower')}"); pg.wait_for_timeout(200)
    # flashing: top-half colors must differ across palette cycle; stem constant
    r = pg.evaluate("""() => { const o = curObj(), f = o.frames.flower;
      const out = []; for (const cyc of [0,1,2,3]) { const res = colorResolver(o, 0, cyc), g = composeFrame(f);
        out.push([JSON.stringify(res(g.pr[2][4])), JSON.stringify(res(g.pr[12][4]))]); } return out; }""")
    print("flower top palettes distinct:", len({a for a, _ in r}), "| stem palettes distinct:", len({b for _, b in r}))
    pg.screenshot(path=f"{T}/flower.png", full_page=True)
    pg.click(f".oitem >> nth={names.index('Mushroom')}"); pg.wait_for_timeout(200)
    print("variant buttons:", pg.eval_on_selector_all("#segVariant button", "els => els.map(e => e.textContent)"))
    cv = pg.locator("#oframes canvas").first; bb = cv.bounding_box()
    v = pg.evaluate("() => composeFrame(curObj().frames.mushroom)[4][4]"); pg.keyboard.press(str(3 if v != 3 else 1))
    pg.mouse.click(bb["x"] + bb["width"] * 0.3, bb["y"] + bb["height"] * 0.3)
    with pg.expect_download() as d: pg.click("#btnSave"); pg.click("#dlGo")
    z = f"{T}/p.zip"; d.value.save_as(z); zipfile.ZipFile(z).extractall(f"{T}/x")
    js = open(f"{T}/x/super-mario-bros-hack.nes", "rb").read()
    r = subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{T}/x/config.json"], capture_output=True, text=True)
    print("ruby:", [l for l in r.stdout.splitlines() if l.startswith("objects")], r.stderr[-200:])
    rb = open(f"{T}/x/super-mario-bros-hack.nes", "rb").read()
    t76 = 0x8010 + 0x76 * 16
    print("JS == Ruby:", js == rb, "| mushroom tile $76 changed:", rom[t76:t76 + 16] != rb[t76:t76 + 16])
    b.close()
print("errors:", errors or "none")
