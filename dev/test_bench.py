from devpaths import REPO, ROM_PATH, JSYAML, bench_body
import os, sys, zipfile, subprocess, shutil, io, json
from playwright.sync_api import sync_playwright
from PIL import Image

S = os.path.dirname(os.path.abspath(__file__))
OUT = REPO
ROM = ROM_PATH
T = f"{S}/bench_test"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)

page_src = bench_body()
wrapped = f"{T}/page.html"
open(wrapped, "w").write('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>' + page_src + "</body></html>")

# a test skin: original colors, non-trivial layout, with a hat overlay pixel
skin = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
px = skin.load()
def rect(x, y, w, h, c):
    for yy in range(y, y + h):
        for xx in range(x, x + w): px[xx, yy] = c + (255,)
rect(0, 8, 8, 8, (240, 200, 160)); rect(0, 8, 8, 3, (200, 120, 40)); rect(16, 20, 4, 12, (40, 160, 70))
rect(40, 20, 4, 12, (240, 200, 160)); rect(40, 20, 4, 4, (40, 160, 70)); rect(0, 20, 4, 12, (90, 60, 30))
rect(8, 8, 8, 8, (240, 200, 160)); px[33, 9] = (255, 0, 0, 255)
skin.save(f"{T}/skin.png")
skin2 = skin.copy(); p2 = skin2.load()
for y in range(64):
    for x in range(64):
        if p2[x, y][:3] == (40, 160, 70): p2[x, y] = (200, 60, 200, 255)
skin2.save(f"{T}/skin2.png")

errors = []
def ruby_build(zpath, tag):
    d = f"{T}/{tag}"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    zipfile.ZipFile(zpath).extractall(d)
    r = subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{d}/config.json"], capture_output=True, text=True)
    if r.returncode: print(r.stdout, r.stderr); raise SystemExit("ruby build failed")
    # ruby writes super-mario-bros-hack.nes over the JS one; keep the JS copy first
    return d, r.stdout

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    ctx.route("https://cdnjs.cloudflare.com/**/js-yaml.min.js", lambda r: r.fulfill(path=JSYAML, content_type="text/javascript"))
    ctx.route("https://fonts.googleapis.com/**", lambda r: r.abort())
    ctx.route("https://fonts.gstatic.com/**", lambda r: r.abort())
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
    page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
    page.goto("file://" + wrapped)
    page.wait_for_timeout(800)
    page.screenshot(path=f"{T}/shot_start.png", full_page=True)
    print("frame summary:", page.inner_text("#frameSummary"), "| err box hidden:", page.is_hidden("#errBox"))

    def download(tag):
        with page.expect_download() as d:
            page.click("#btnSave"); page.click("#dlGo")
        path = f"{T}/{tag}.zip"; d.value.save_as(path); return path

    # 1. no ROM: project only
    z0 = download("noroom")
    print("no-ROM zip:", sorted(zipfile.ZipFile(z0).namelist()))

    # 2. with ROM
    page.set_input_files("#fRom", ROM); page.wait_for_timeout(300)
    print("rom chip:", page.inner_text("#romChip"))
    z1 = download("sample")

    def compare(zpath, tag):
        names = zipfile.ZipFile(zpath).namelist()
        js_nes = zipfile.ZipFile(zpath).read("super-mario-bros-hack.nes"); js_ips = zipfile.ZipFile(zpath).read("super-mario-bros-hack.ips")
        d, out = ruby_build(zpath, tag)
        rb_nes = open(f"{d}/super-mario-bros-hack.nes", "rb").read(); rb_ips = open(f"{d}/super-mario-bros-hack.ips", "rb").read()
        print(f"[{tag}] files={sorted(names)}")
        print(f"[{tag}] ruby: " + " | ".join(l for l in out.splitlines() if "frames:" in l))
        print(f"[{tag}] JS ROM == Ruby ROM: {js_nes == rb_nes}   JS IPS == Ruby IPS: {js_ips == rb_ips}   changed bytes: {sum(a != c for a, c in zip(open(ROM,'rb').read(), js_nes))}")
        return d
    compare(z1, "sample")

    # 3. skin import P1 + P2
    page.set_input_files("#fSkin1", f"{T}/skin.png"); page.wait_for_timeout(500)
    page.set_input_files("#fSkin2", f"{T}/skin2.png"); page.wait_for_timeout(300)
    pal = json.loads(page.evaluate("JSON.stringify(S.palettes)"))
    print("palettes after skins:", pal)
    page.screenshot(path=f"{T}/shot_skin.png", full_page=True)
    z2 = download("skin")
    compare(z2, "skin")

    # 4. pose edit via slider + yaml sync
    page.click(".fr >> nth=0")
    s = page.locator("#bones input[type=range]").first
    s.fill("90"); page.wait_for_timeout(200)
    page.click("#yamlBox summary")
    y = page.input_value("#yaml")
    print("yaml line:", [l for l in y.splitlines() if l.strip().startswith("big walk 1:")][0])
    z3 = download("posed")
    compare(z3, "posed")

    # 5. reopen exported project in a fresh page: re-export must be identical
    page2 = ctx.new_page()
    page2.on("pageerror", lambda e: errors.append("pageerror2: " + str(e)))
    page2.add_init_script("try{localStorage.clear()}catch(e){}")
    page2.goto("file://" + wrapped); page2.wait_for_timeout(500)
    page2.set_input_files("#fProj", z3); page2.wait_for_timeout(800)
    with page2.expect_download() as d:
        page2.click("#btnSave"); page2.click("#dlGo")
    z4 = f"{T}/reopen.zip"; d.value.save_as(z4)
    A, B = zipfile.ZipFile(z3), zipfile.ZipFile(z4)
    same = {n: A.read(n) == B.read(n) for n in A.namelist()}
    print("reopen roundtrip identical:", same)

    # 6. yaml error surfaces
    page.fill("#yaml", "parts: {}\nposes:\n  nope: {}\n"); page.wait_for_timeout(600)
    print("yaml error shown:", page.is_visible("#yamlErr"), "|", page.inner_text("#yamlErr")[:60])

    # 7. phone width
    m = b.new_page(viewport={"width": 400, "height": 900})
    m.route("https://cdnjs.cloudflare.com/**/js-yaml.min.js", lambda r: r.fulfill(path=JSYAML, content_type="text/javascript"))
    m.goto("file://" + wrapped); m.wait_for_timeout(500)
    print("phone scrollWidth:", m.evaluate("document.documentElement.scrollWidth"))
    b.close()

print("console/page errors:", errors or "none")
