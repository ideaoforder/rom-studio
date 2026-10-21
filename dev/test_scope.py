from devpaths import REPO, ROM_PATH, JSYAML, bench_body
import os
from playwright.sync_api import sync_playwright
S = os.path.dirname(os.path.abspath(__file__)); TD = f"{S}/snd_test"
open(f"{TD}/page.html", "w").write('<!doctype html><html><head><meta charset="utf-8"></head><body>' + bench_body() + "</body></html>")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 1000}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://cdnjs.cloudflare.com/**/js-yaml.min.js", lambda r: r.fulfill(path=JSYAML, content_type="text/javascript"))
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{TD}/page.html"); pg.wait_for_timeout(400); pg.set_input_files("#fRom", ROM_PATH); pg.click("#tabSounds")
    out = {}
    for name in ["Jump", "Brick break", "Coin", "Power-up grab", "Bowser flame", "Kick"]:
        pg.click(f".srow .name:has-text('{name}')"); pg.wait_for_timeout(80)
        out[name] = pg.evaluate("SFX.last.trace.filter(f => f.some(c => c.vol > 0)).length + '/' + SFX.last.trace.length")
    print("frames with visible sound:", out)
    pg.click(".srow .name:has-text('Power-up grab')"); pg.wait_for_timeout(100)
    pg.locator(".scope").screenshot(path=f"{TD}/scope_grab.png")
    print("errors:", errs or "none"); b.close()
