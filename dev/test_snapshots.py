"""Start over + snapshots: save, clear, go back, survive a reload, switch games, undo."""
import os, sys
from playwright.sync_api import sync_playwright
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV)
SMB = os.environ.get("SMB_ROM") or sys.exit("Set SMB_ROM"); MM3 = os.environ.get("MM3_ROM")
errors = []
state = "() => JSON.stringify([Object.keys(S.chrEdits).length, S.mech, S.palettes && S.palettes.player1, S.names && S.names.player1, S.profile.game])"
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(accept_downloads=True); ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"file://{REPO}/index.html"); pg.evaluate("try{localStorage.clear()}catch(e){}"); pg.reload(); pg.wait_for_timeout(500)
    pg.set_input_files("#fRom", SMB); pg.wait_for_timeout(400)
    pg.evaluate("() => { checkpoint(''); S.names.player1 = 'STEVE'; S.palettes.player1 = ['2A','30','11']; S.mech = {gravity: 25, flap: true}; const o = S.objs[0], f = Object.values(o.frames)[0], q = f.slots.find(Boolean); S.chrEdits[q.off] = tileAt(q.off).map(r => r.map(v => (v + 1) % 4)); fullRefresh(); }")
    edited = pg.evaluate(state)
    pg.click("#btnSnaps"); pg.fill("#snapName", "Steve, moon"); pg.click("#snapSave"); pg.wait_for_timeout(200)
    print("snapshot listed:", pg.eval_on_selector_all("#snapList .sname", "e => e.map(x => x.firstChild.textContent)"))
    pg.click("#snapClose")
    pg.click("#btnStartOver"); pg.wait_for_timeout(100); print("confirm text:", pg.text_content("#overText")[:70]); pg.click("#overGo"); pg.wait_for_timeout(300)
    cleared = pg.evaluate(state); print("after start over:", cleared)
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(200); print("undo brings it back:", pg.evaluate(state) == edited)
    pg.click("#btnStartOver"); pg.click("#overSnap"); pg.wait_for_timeout(300)
    print("snapshot-then-start-over saved:", pg.eval_on_selector_all("#snapList .sname", "e => e.length") >= 0 and pg.evaluate("loadSnaps().map(s => s.name)"))
    pg.reload(); pg.wait_for_timeout(500); pg.set_input_files("#fRom", SMB); pg.wait_for_timeout(300)
    pg.click("#btnSnaps"); pg.wait_for_timeout(100)
    rows = pg.eval_on_selector_all("#snapList .sname", "e => e.map(x => x.firstChild.textContent)"); print("after reload:", rows)
    pg.click(f"#snapList .snaprow >> nth={rows.index('Steve, moon')} >> text=Go back to this"); pg.wait_for_timeout(300)
    print("went back:", pg.evaluate(state) == edited)
    if MM3:
        pg.set_input_files("#fRom", MM3); pg.wait_for_timeout(300); pg.set_input_files("#fRom", MM3); pg.wait_for_timeout(600)
        pg.evaluate("() => { S.mech = {invincible: true}; persist(); }"); pg.evaluate("saveSnapshot('MM3 super')")
        pg.click("#btnSnaps"); pg.wait_for_timeout(100)
        rows = pg.eval_on_selector_all("#snapList .sname", "e => e.map(x => x.firstChild.textContent)")
        pg.click(f"#snapList .snaprow >> nth={rows.index('Steve, moon')} >> text=Go back to this"); pg.wait_for_timeout(400)
        print("SMB snapshot from MM3 switches game:", pg.evaluate("S.profile.game"), pg.evaluate("S.names.player1"))
    b.close()
print("errors:", errors or "none")
