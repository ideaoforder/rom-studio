from devpaths import REPO, ROM_PATH, JSYAML, bench_body
import os, json, zipfile, shutil, subprocess
from playwright.sync_api import sync_playwright
import music_truth as MT
S = os.path.dirname(os.path.abspath(__file__)); OUT = REPO
ROM = ROM_PATH; TD = f"{S}/mus_test"
shutil.rmtree(TD, ignore_errors=True); os.makedirs(TD)
open(f"{TD}/page.html", "w").write('<!doctype html><html><head><meta charset="utf-8"></head><body>' + bench_body() + "</body></html>")
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
    ctx.route("https://cdnjs.cloudflare.com/**/js-yaml.min.js", lambda r: r.fulfill(path=JSYAML, content_type="text/javascript"))
    ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e) + " @ " + (e.stack or "")[:400])); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{TD}/page.html"); pg.wait_for_timeout(500)
    pg.click("#tabMusic"); pg.wait_for_timeout(100)
    print("no-ROM notice:", pg.is_visible("#musNoRom"))
    pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(400)
    print("song sizes:", pg.eval_on_selector_all("#songList .name", "els => els.map(e => e.textContent.trim())")); print("meter (stock):", pg.inner_text("#musMeterText"), "| songs:", pg.eval_on_selector_all("#songList .name", "els => els.length"), "| overworld parts:", pg.eval_on_selector_all("#musParts button", "els => els.length"))
    pg.click("#musPlay"); pg.wait_for_timeout(400); pg.click("#musStop")
    pg.screenshot(path=f"{TD}/music_overworld.png", full_page=True)
    # --- edit Underground melody through the UI
    pg.click("#songList .name:has-text('Underground')"); pg.wait_for_timeout(150)
    roll = pg.locator("#roll"); bb = roll.bounding_box()
    lane = pg.evaluate("ROLL.lanes[0]"); it = lane["items"][2]
    sx = bb["width"] / pg.evaluate("document.querySelector('#roll').width"); sy = bb["height"] / pg.evaluate("document.querySelector('#roll').height")
    pg.mouse.click(bb["x"] + (it["x"] + 2) * sx, bb["y"] + (lane["y"] + lane["h"] / 2) * sy)
    print("selected:", pg.evaluate("JSON.stringify(MU.sel)"), "|", pg.inner_text("#noteBar .what"))
    for k in ["ArrowUp", "ArrowUp", "ArrowUp", "4", "ArrowRight", "r", "ArrowRight", "Enter"]: pg.keyboard.press(k)
    # add a note with the + zone on the melody lane
    lane = pg.evaluate("ROLL.lanes[0]"); endx = lane["end"] * pg.evaluate("ROLL.ppf")
    pg.mouse.click(bb["x"] + (endx + 12) * sx, bb["y"] + (lane["y"] + lane["h"] / 2) * sy)
    # harmony on (Underground has none), bass -> own notes
    pg.locator("#musLanes .lane:has-text('Harmony') input").check()
    pg.click("#musLanes .lane:has-text('Bass') button:has-text('Own notes')")
    print("underground after edits:", pg.evaluate("(() => { const p = curPart(); return {mel: p.melody.length, harmony: p.harmony && p.harmony.length, bassCopy: p.bassCopy, bass: p.bass && p.bass.length}; })()"))
    print("meter after edits:", pg.inner_text("#musMeterText"))
    # Overworld: change arrangement slot 5, tempo of a part
    pg.click("#songList .name:has-text('Overworld')"); pg.click("#arrBox summary")
    pg.select_option("#musArr select >> nth=4", index=0)
    pg.select_option("#musTempo", index=2)
    # silence game over to free space
    pg.click("#songList .name:has-text('Game over')"); pg.click("#musFacts button:has-text('Silence this song')")
    pg.click("#songList .name:has-text('Princess')"); pg.click("#musFacts button:has-text('Silence this song')")
    pg.click("#songList .name:has-text('Hurry')"); pg.click("#musFacts button:has-text('Silence this song')")
    print("meter after silencing 3 songs:", pg.inner_text("#musMeterText"))
    model = json.loads(pg.evaluate("JSON.stringify(S.music)")); json.dump(model, open(f"{TD}/model.json", "w"))
    pg.click("#songList .name:has-text('Underground')"); pg.click("#musPlay"); pg.wait_for_timeout(300)
    pg.screenshot(path=f"{TD}/music_underground.png", full_page=True)
    with pg.expect_download() as d: pg.click("#btnSave")
    z = f"{TD}/p.zip"; d.value.save_as(z); zipfile.ZipFile(z).extractall(f"{TD}/x")
    cfg = json.load(open(f"{TD}/x/config.json"))
    print("zip has music.json:", os.path.exists(f"{TD}/x/music.json"), "| byte_ranges:", [(r["label"], len(r["hex"]) // 2) for r in cfg.get("byte_ranges", [])])
    js_nes = open(f"{TD}/x/smb_hacked.nes", "rb").read()
    r = subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{TD}/x/config.json"], capture_output=True, text=True)
    print("ruby:", [l for l in r.stdout.splitlines() if l.startswith("music")], r.stderr[-300:])
    rb_nes = open(f"{TD}/x/smb_hacked.nes", "rb").read()
    print("JS ROM == Ruby ROM:", js_nes == rb_nes)
    open(f"{TD}/built.nes", "wb").write(rb_nes)
    # decode the built ROM and compare with the edited model, song by song (notes + lengths)
    chk = subprocess.run(["node", "-e", f'''
const fs=require("fs"),M=require("{S}/music_model.js");const rom=fs.readFileSync("{TD}/built.nes");const model=JSON.parse(fs.readFileSync("{TD}/model.json"));
const dec=M.decodeMusic(o=>rom[o]);const strip=ev=>ev?ev.filter(e=>!e.stop).map(e=>[e.n,e.li]):null;
let bad=[];for(const [y,id] of Object.entries(model.slots)){{if(id==="silence"){{if(dec.slots[y]!==undefined&&dec.slots[y]!=="silence"){{const p=dec.patterns.find(q=>q.id===dec.slots[y]);if(p.melody.length>0)bad.push("slot "+y+" should be silent")}}continue}}
const a=model.patterns.find(p=>p.id===id),b=dec.patterns.find(p=>p.id===dec.slots[y]);
const am=strip(a.melody),bm=strip(b.melody);if(JSON.stringify(am)!==JSON.stringify(bm))bad.push("slot "+y+" melody");
if(a.tempo!==b.tempo)bad.push("slot "+y+" tempo");
if(!!a.harmony!==!!b.harmony)bad.push("slot "+y+" harmony on/off");
else if(a.harmony){{const A=strip(a.harmony),B=strip(b.harmony);for(let i=0;i<B.length;i++){{if(i<A.length?(A[i][0]!==B[i][0]||A[i][1]!==B[i][1]):B[i][0]!==4){{bad.push("slot "+y+" harmony@"+i);break}}}}}}}}
console.log(bad.length?"MISMATCH "+bad.join(", "):"built ROM decodes back to exactly what was edited");'''], capture_output=True, text=True, input="")
    print(chk.stdout.strip() or chk.stderr[-400:])
    # real engine vs page's emulator on the built ROM
    reqs = {"underground": [0xFB, 0x04], "ground": [0xFB, 0x01], "gameover": [0xFC, 0x02], "water": [0xFB, 0x02]}
    real = MT.run(bytearray(rb_nes), 0xFB, 0x04, 1500)
    jsr = pg.evaluate("(() => { const img = new Uint8Array(arguments[0]); return runSoundEngine(img, {area: 4}, 1500); })", list(rb_nes)) if False else None
    jsw = pg.evaluate("bytes => runSoundEngine(Uint8Array.from(bytes), {area: 4}, 1500)", list(rb_nes))
    print("edited Underground: page's 6502 vs py65 real engine:", "identical" if jsw == real else "DIFFERENT")
    real_g = MT.run(bytearray(rb_nes), 0xFB, 0x01, 1500); jsw_g = pg.evaluate("bytes => runSoundEngine(Uint8Array.from(bytes), {area: 1}, 1500)", list(rb_nes))
    print("edited Overworld:   page's 6502 vs py65 real engine:", "identical" if jsw_g == real_g else "DIFFERENT")
    # reopen
    p2 = ctx.new_page(); p2.add_init_script("try{localStorage.clear()}catch(e){}"); p2.on("pageerror", lambda e: errors.append("p2 " + str(e)))
    p2.goto(f"file://{TD}/page.html"); p2.wait_for_timeout(400); p2.set_input_files("#fProj", z); p2.wait_for_timeout(800)
    with p2.expect_download() as d: p2.click("#btnSave")
    z2 = f"{TD}/p2.zip"; d.value.save_as(z2); A, B = zipfile.ZipFile(z), zipfile.ZipFile(z2)
    print("reopen roundtrip identical:", sorted(A.namelist()) == sorted(B.namelist()) and all(A.read(n) == B.read(n) for n in A.namelist()))
    # overflow: stuff the overworld with notes
    pg.click("#songList .name:has-text('Castle clear')"); pg.wait_for_timeout(100)
    pg.evaluate("musEdit(() => { const p = curPart(); for (let i = 0; i < 120; i++) p.melody.push({n: 0x30, li: 1}); })")
    print("overflow meter:", pg.inner_text("#musMeterText"), "| error shown:", pg.is_visible("#musErr"))
    pg.click("#btnSave"); pg.wait_for_timeout(300); print("download blocked with message:", pg.inner_text("#toast")[:70])
    pg.keyboard.press("Control+z"); print("undo restores fit:", pg.inner_text("#musMeterText"))
    b.close()
print("errors:", errors or "none")
