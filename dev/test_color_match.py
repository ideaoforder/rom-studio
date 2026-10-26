"""Copy colors between MM3 weapons and their bosses (MM3_ROM)."""
import json, os, zipfile, tempfile
from playwright.sync_api import sync_playwright
import sys
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV)
ROM = os.environ.get("MM3_ROM") or sys.exit("Set MM3_ROM")
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(accept_downloads=True, viewport={"width": 1400, "height": 1000})
    ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/index.html"); pg.wait_for_timeout(600)
    pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(500)
    sel = lambda n: pg.evaluate(f"(()=>{{selectObj(S.objs.findIndex(o=>o.name==={json.dumps(n)}));}})()")
    pals = lambda: pg.evaluate("S.spritePals")
    # weapon -> copy from boss
    sel("Gemini Laser"); pg.wait_for_timeout(150)
    btn = pg.locator("#opalCopy button"); print("weapon button:", btn.inner_text().strip())
    before = pals(); btn.click(); after = pals()
    print("body.1 now == set.27.2:", after["body.1"] == before["set.27.2"], "| boss untouched:", after["set.27.2"] == before["set.27.2"], "| button now:", btn.inner_text().strip(), btn.is_disabled())
    if os.environ.get("SHOT"): pg.screenshot(path=os.environ["SHOT"])
    # boss -> copy from weapon (Top Man has no projectile object, copies body.5)
    pg.evaluate("S.spritePals['body.5']=['0F','27','16'];S.palEdited['body.5']=true")
    sel("Top Man"); pg.wait_for_timeout(150)
    print("boss button:", pg.locator("#opalCopy button").inner_text().strip())
    pg.locator("#opalCopy button").click()
    print("set.2A.2 == body.5:", pals()["set.2A.2"] == ["0F", "27", "16"])
    pg.keyboard.press("Control+z"); print("undo restores:", pals()["set.2A.2"] == before["set.2A.2"])
    # no button on objects without a match
    sel("Mega Buster"); pg.wait_for_timeout(100); print("Mega Buster buttons:", pg.locator("#opalCopy button").count())
    # export writes it
    pg.click("#btnSave")
    with pg.expect_download() as d: pg.click("#dlGo")
    x = tempfile.mkdtemp(); zipfile.ZipFile(d.value.path()).extractall(x)
    cfg = json.load(open(f"{x}/config.json")); sp = cfg.get("sprite_palettes", {})
    print("exported body.1:", sp.get("body.1", {}).get("colors"), "== boss", [c for c in before["set.27.2"]])
print("errors:", errors or "none")
