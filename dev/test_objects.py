from devpaths import REPO, ROM_PATH, JSYAML, bench_body
import os, zipfile, subprocess, shutil, json
from playwright.sync_api import sync_playwright

S = os.path.dirname(os.path.abspath(__file__))
OUT = REPO
ROM = ROM_PATH
T = f"{S}/obj_test"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
rom = open(ROM, "rb").read()
src = bench_body()
page_path = f"{T}/page.html"
open(page_path, "w").write('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + src + "</body></html>")


def paint(page, fx, fy):
    cv = page.locator("#oframes canvas").first; bb = cv.bounding_box()
    x, y = bb["x"] + bb["width"] * fx, bb["y"] + bb["height"] * fy
    v = page.evaluate(f"""() => {{ const c = document.querySelector('#oframes canvas'), r = c.getBoundingClientRect();
      const f = Object.values(curObj().frames)[0], g = composeFrame(f);
      return g[Math.floor(({y}-r.top)/r.height*f.rows*8)][Math.floor(({x}-r.left)/r.width*f.cols*8)]; }}""")
    page.keyboard.press(str(3 if v != 3 else 1))
    page.mouse.click(x, y)

errors = []
def route(ctx):
    ctx.route("https://cdnjs.cloudflare.com/**/js-yaml.min.js", lambda r: r.fulfill(path=JSYAML, content_type="text/javascript"))
    ctx.route("https://fonts.googleapis.com/**", lambda r: r.abort()); ctx.route("https://fonts.gstatic.com/**", lambda r: r.abort())

def ruby_compare(zpath, tag):
    d = f"{T}/{tag}"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    z = zipfile.ZipFile(zpath); z.extractall(d)
    js_nes, js_ips = z.read("smb_hacked.nes"), z.read("smb_hacked.ips")
    r = subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{d}/config.json"], capture_output=True, text=True)
    if r.returncode: print(r.stdout, r.stderr); raise SystemExit("ruby failed")
    print(f"[{tag}] ruby:", " | ".join(l for l in r.stdout.splitlines() if l.startswith(("frames:", "objects:"))))
    print(f"[{tag}] JS ROM == Ruby ROM: {open(f'{d}/smb_hacked.nes','rb').read() == js_nes}   IPS equal: {open(f'{d}/smb_hacked.ips','rb').read() == js_ips}")
    return js_nes

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True); route(ctx)
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
    page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
    page.goto("file://" + page_path); page.wait_for_timeout(600)

    # profile vs the ROM's EnemyGraphicsTable (file 0x674E): tile multisets must match
    table = rom[0x674E:0x674E + 0x102]
    expect = {("Goomba","walk"):0x54, ("Koopa Troopa","walk 1"):0x0C, ("Koopa Troopa","walk 2"):0x12, ("Koopa Troopa","shell 1"):0x66,
              ("Koopa Troopa","shell 2"):0x6C, ("Koopa Troopa","shell flipped 1"):0x5A, ("Koopa Troopa","shell flipped 2"):0x60,
              ("Koopa Paratroopa","fly 1"):0x18, ("Koopa Paratroopa","fly 2"):0x1E, ("Buzzy Beetle","walk 1"):0x00, ("Buzzy Beetle","walk 2"):0x06,
              ("Buzzy Beetle","shell"):0x72, ("Buzzy Beetle","shell flipped"):0x7E, ("Spiny","walk 1"):0x24, ("Spiny","walk 2"):0x2A,
              ("Spiny","egg 1"):0x30, ("Spiny","egg 2"):0x36, ("Piranha Plant","bite 1"):0xC0, ("Piranha Plant","bite 2"):0xC6,
              ("Hammer Bro","walk 1"):0xA8, ("Hammer Bro","walk 2"):0xAE, ("Hammer Bro","throw 1"):0xB4, ("Hammer Bro","throw 2"):0xBA,
              ("Lakitu","cloud 1"):0x90, ("Lakitu","cloud 2"):0x96, ("Bullet Bill","fly"):0xEA, ("Cheep Cheep","swim 1"):0x48,
              ("Cheep Cheep","swim 2"):0x4E, ("Blooper","swim 1"):0x3C, ("Blooper","swim 2"):0x42, ("Podoboo","rise"):0xCC, ("Goomba","flat"):0x8A}
    prof = json.loads(page.evaluate("JSON.stringify(S.profile.objects)"))
    bad = []
    for o in prof:
        for fn, f in o["frames"].items():
            key = (o["name"], fn)
            if key not in expect: continue
            got = sorted(int(t[:2], 16) for t in f["tiles"].split() if t != ".")
            want = sorted(x for x in table[expect[key]:expect[key] + 6] if x != 0xFC)
            if got != want: bad.append((key, [hex(x) for x in got], [hex(x) for x in want]))
    print(f"profile vs ROM table: {len(expect)} frames checked, mismatches: {bad or 'none'}")

    page.set_input_files("#fRom", ROM); page.wait_for_timeout(300)
    page.click("#tabObjects"); page.wait_for_timeout(300)
    page.screenshot(path=f"{T}/objects_goomba.png", full_page=True)

    # paint on Goomba walk (top-left pixel area) with color 1
    paint(page, 0.3, 0.3)
    # Koopa: paint walk 1 lower-right (tile A9) and check Paratroopa shares it
    page.click(".oitem >> nth=1"); page.wait_for_timeout(150)
    paint(page, 0.8, 0.9)
    r = page.evaluate("""() => {
      const A9 = 0x8010 + 0xA9*16;
      const para = S.objs.find(o => o.name === 'Koopa Paratroopa');
      const g = composeFrame(para.frames['fly 1']), k = composeFrame(S.objs[1].frames['walk 1']);
      const same = JSON.stringify(g.slice(16).map(r=>r.slice(8))) === JSON.stringify(k.slice(16).map(r=>r.slice(8)));
      return { edits: Object.keys(S.chrEdits).map(o => (Number(o)-0x8010)/16).map(t => t.toString(16)), sharedUpdated: same, facts: document.querySelector('#ofacts').innerText.split('\\n').slice(0,4).join(' | ') };
    }""")
    print("after painting:", r)
    # fireball: paint + palette change on ground.2 (shared by red koopa, spiny...)
    page.click(".oitem >> nth=2"); page.wait_for_timeout(150)
    paint(page, 0.5, 0.5)
    page.click("#opalSlots .slot >> nth=1"); page.click("#opicker button >> nth=33")
    print("ground.2 now:", page.evaluate("S.spritePals['ground.2']"), "| shared note:", page.inner_text("#opalShared"))
    page.wait_for_timeout(300)
    page.screenshot(path=f"{T}/objects_fireball.png", full_page=True)

    with page.expect_download() as d: page.click("#btnSave")
    z1 = f"{T}/proj.zip"; d.value.save_as(z1)
    print("zip:", sorted(zipfile.ZipFile(z1).namelist()))
    built = ruby_compare(z1, "objects")
    changed = [i for i, (a, c) in enumerate(zip(rom, built)) if a != c]
    print("palette byte 0x0CF5 now:", hex(built[0x0CF5]), "| fireball tile changed:", any(0x8010 + 0x64*16 <= i < 0x8010 + 0x65*16 for i in changed))

    # reopen in a clean page, export again: identical?
    p2 = ctx.new_page(); p2.add_init_script("try{localStorage.clear()}catch(e){}")
    p2.on("pageerror", lambda e: errors.append("pageerror2: " + str(e)))
    p2.goto("file://" + page_path); p2.wait_for_timeout(500)
    p2.set_input_files("#fProj", z1); p2.wait_for_timeout(800)
    with p2.expect_download() as d: p2.click("#btnSave")
    z2 = f"{T}/reopen.zip"; d.value.save_as(z2)
    A, B = zipfile.ZipFile(z1), zipfile.ZipFile(z2)
    print("reopen roundtrip identical:", all(A.read(n) == B.read(n) for n in A.namelist()) and sorted(A.namelist()) == sorted(B.namelist()))

    # undo restores edits
    page.keyboard.press("Control+z"); page.keyboard.press("Control+z")
    print("after 2 undos, ground.2:", page.evaluate("S.spritePals['ground.2']"))

    m = b.new_page(viewport={"width": 400, "height": 900}); route(m)
    m.goto("file://" + page_path); m.wait_for_timeout(400); m.click("#tabObjects"); m.wait_for_timeout(200)
    print("phone scrollWidth (objects):", m.evaluate("document.documentElement.scrollWidth"))
    b.close()
print("errors:", errors or "none")
