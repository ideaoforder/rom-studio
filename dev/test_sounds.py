from devpaths import REPO, ROM_PATH, JSYAML, bench_body
import os, json, zipfile, shutil, subprocess
from playwright.sync_api import sync_playwright
import sfx_truth as T
S = os.path.dirname(os.path.abspath(__file__)); OUT = REPO
ROM = ROM_PATH; TD = f"{S}/snd_test"
shutil.rmtree(TD, ignore_errors=True); os.makedirs(TD)
open(f"{TD}/page.html", "w").write('<!doctype html><html><head><meta charset="utf-8"></head><body>' + bench_body() + "</body></html>")
IDS = {"jump": ["jump", 0], "jumpbig": ["jump", 1], "bump": ["bump", 0], "stomp": ["stomp", 0], "kick": ["kick", 0], "pipe": ["pipe", 0], "fire": ["fire", 0], "flag": ["flag", 0],
       "bf": ["bf", 0], "coin": ["coin", 0], "sprout": ["sprout", 0], "vine": ["vine", 0], "blast": ["blast", 0], "tick": ["tick", 0], "grab": ["grab", 0], "oneup": ["oneup", 0], "brick": ["brick", 0], "flame": ["flame", 0]}
def page_frames(pg):
    return pg.evaluate("ids => Object.fromEntries(Object.entries(ids).map(([k,[id,v]]) => { const f = sfxFrames(id, rbs, v); while (f.length && !f[f.length-1].length) f.pop(); return [k, f]; }))", IDS)
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
    ctx.route("https://cdnjs.cloudflare.com/**/js-yaml.min.js", lambda r: r.fulfill(path=JSYAML, content_type="text/javascript"))
    ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{TD}/page.html"); pg.wait_for_timeout(500)
    pg.click("#tabSounds"); pg.wait_for_timeout(150)
    print("no-ROM message shown:", pg.is_visible("#sfxNoRom"), "| play disabled:", pg.is_disabled("#sfxPlay"))
    pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(300)
    truth = json.load(open(f"{S}/truth_default.json"))
    pf = page_frames(pg)
    print("in-page model vs real engine (stock):", "identical" if all(pf[k] == truth[k] for k in IDS) else [k for k in IDS if pf[k] != truth[k]])
    # --- edit through the UI
    pg.select_option("#sfxKnobs select >> nth=0", index=5)                 # jump small pitch
    pg.locator("#sfxKnobs .kgroup >> nth=0").locator("label.chk:has-text('Slide') input").first.uncheck()
    r = pg.locator("#sfxKnobs .kgroup >> nth=0").locator("input[type=range]").last; r.fill("30")   # length
    pg.click(".srow .name:has-text('Stomp')"); pg.wait_for_timeout(100)
    bars = pg.locator("#sfxTables .bars").first; bb = bars.bounding_box()
    pg.mouse.move(bb["x"] + 8, bb["y"] + bb["height"] * 0.2); pg.mouse.down(); pg.mouse.move(bb["x"] + bb["width"] - 8, bb["y"] + bb["height"] * 0.8, steps=12); pg.mouse.up()
    pg.click(".srow .name:has-text('Fireball')"); pg.click("#sfxRandom"); pg.wait_for_timeout(150)
    pg.click(".srow .name:has-text('Power-up grab')"); pg.select_option("#sfxTables select >> nth=0", index=10)
    pg.click(".srow .name:has-text('Brick')"); pg.click("#sfxRandom")
    edits = pg.evaluate("Object.keys(S.sfxEdits).length")
    print("edits made through the UI:", edits)
    nz_ok = pg.evaluate("Object.entries(S.sfxEdits).every(([o,v]) => !sfxNonzero(Number(o)) || v !== 0)")
    print("nonzero rule held:", nz_ok)
    pg.click("#sfxPlay"); pg.wait_for_timeout(300)
    pg.screenshot(path=f"{TD}/sounds.png", full_page=True)
    pf_edit = page_frames(pg)
    with pg.expect_download() as d: pg.click("#btnSave")
    z = f"{TD}/p.zip"; d.value.save_as(z); zipfile.ZipFile(z).extractall(f"{TD}/x")
    cfg = json.load(open(f"{TD}/x/config.json")); print("config byte_patches:", len(cfg.get("byte_patches", [])))
    js_nes = open(f"{TD}/x/smb_hacked.nes", "rb").read()
    r = subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{TD}/x/config.json"], capture_output=True, text=True)
    print("ruby:", [l for l in r.stdout.splitlines() if "byte patches" in l], r.stderr[-300:])
    rb_nes = open(f"{TD}/x/smb_hacked.nes", "rb").read()
    print("JS ROM == Ruby ROM:", js_nes == rb_nes)
    real = {k: T.run(bytearray(rb_nes), k) for k in IDS}
    bad = [k for k in IDS if real[k] != pf_edit[k]]
    print("edited sounds: page model vs REAL engine on the built ROM:", "identical" if not bad else bad)
    # reopen
    p2 = ctx.new_page(); p2.add_init_script("try{localStorage.clear()}catch(e){}"); p2.on("pageerror", lambda e: errors.append("p2 " + str(e)))
    p2.goto(f"file://{TD}/page.html"); p2.wait_for_timeout(400); p2.set_input_files("#fProj", z); p2.wait_for_timeout(700)
    with p2.expect_download() as d: p2.click("#btnSave")
    z2 = f"{TD}/p2.zip"; d.value.save_as(z2)
    A, B = zipfile.ZipFile(z), zipfile.ZipFile(z2)
    print("reopen roundtrip identical:", sorted(A.namelist()) == sorted(B.namelist()) and all(A.read(n) == B.read(n) for n in A.namelist()))
    # undo
    n0 = pg.evaluate("Object.keys(S.sfxEdits).length"); pg.keyboard.press("Control+z"); print("undo reverts last change:", pg.evaluate("Object.keys(S.sfxEdits).length") != n0)
    # touch: d-pad + pick
    t = b.new_context(viewport={"width": 820, "height": 1180}, has_touch=True, is_mobile=True)
    t.route("https://cdnjs.cloudflare.com/**/js-yaml.min.js", lambda r: r.fulfill(path=JSYAML, content_type="text/javascript"))
    tp = t.new_page(); tp.on("pageerror", lambda e: errors.append("touch " + str(e))); tp.goto(f"file://{TD}/page.html"); tp.wait_for_timeout(400)
    print("d-pad visible on touch:", tp.is_visible("#dpad"))
    x0 = tp.evaluate("A.hero.x"); right = tp.locator("#dpad button[data-key=ArrowRight]")
    bb = right.bounding_box(); tp.dispatch_event("#dpad button[data-key=ArrowRight]", "pointerdown", {"pointerId": 1}); tp.wait_for_timeout(500); tp.dispatch_event("#dpad button[data-key=ArrowRight]", "pointerup", {"pointerId": 1})
    print("d-pad moves the character:", tp.evaluate("A.hero.x") > x0, "| mode:", tp.evaluate("S.view.mode"))
    tp.click("#toolPick"); bb = tp.locator("#painter").bounding_box(); tp.touchscreen.tap(bb["x"] + 5, bb["y"] + 5)
    print("pick tool grabbed a color and returned to pen:", tp.evaluate("S.tool") == "pen")
    b.close()
print("errors:", errors or "none")
