from devpaths import REPO, ROM_PATH, JSYAML, bench_body
import os
from playwright.sync_api import sync_playwright
S = os.path.dirname(os.path.abspath(__file__)); errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 820, "height": 1180}, has_touch=True, is_mobile=True, device_scale_factor=2, accept_downloads=True)
    ctx.route("https://cdnjs.cloudflare.com/**/js-yaml.min.js", lambda r: r.fulfill(path=JSYAML, content_type="text/javascript"))
    ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"file://{REPO}/index.html"); pg.wait_for_timeout(600)
    print("scrollWidth:", pg.evaluate("document.documentElement.scrollWidth"), "| doctype:", pg.evaluate("document.compatMode"))
    before = pg.evaluate("JSON.stringify(S.parts.head)")
    bb = pg.locator("#painter").bounding_box(); pg.touchscreen.tap(bb["x"] + 30, bb["y"] + bb["height"] - 30)
    print("tap painted:", before != pg.evaluate("JSON.stringify(S.parts.head)"))
    pg.set_input_files("#fRom", ROM_PATH); pg.wait_for_timeout(300)
    with pg.expect_download() as d: pg.click("#btnSave"); pg.click("#dlGo")
    print("download:", d.value.suggested_filename)
    pg.screenshot(path=f"{S}/ipad.png")
    b.close()
print("errors:", errors or "none")
