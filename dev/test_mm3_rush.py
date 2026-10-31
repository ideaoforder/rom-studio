"""Mega Man 3 Rush (Coil, Marine, Jet): frames vs the game's tables, paint + recolor, Ruby parity, and the built ROM in cynes.
Needs MM3_ROM=/path/to/Mega Man 3 (USA).nes. `pip install cynes` for the in-game half."""
import os, sys, json, zipfile, subprocess, shutil
from playwright.sync_api import sync_playwright
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV)
ROM = os.environ.get("MM3_ROM") or sys.exit("Set MM3_ROM")
rom = open(ROM, "rb").read(); T = f"{DEV}/mm3_rush_test"; shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
C = 0x10 + 256 * 1024
PRG = lambda b: 0x10 + b * 0x2000
def s8(v): return v - 256 if v > 127 else v
def frame_model(b, fid, facing=1):  # independent re-implementation of the renderer at $1FF13B
    base = PRG(b); p = rom[base + 0x100 + fid] | rom[base + 0x200 + fid] << 8; o = base + p - 0x8000
    ob = PRG(0x14 if rom[o] & 0x80 else 0x19); idx = rom[o + 1] + facing
    q = rom[ob + 0x1E00 + idx] | rom[ob + 0x1F00 + idx] << 8; qo = ob + q - 0xA000 - 2
    return [(rom[o + 2 + 2 * k], rom[o + 3 + 2 * k] ^ (0x40 if facing else 0), s8(rom[qo + 3 + 2 * k]), s8(rom[qo + 2 + 2 * k])) for k in range((rom[o] & 0x7F) + 1)]
tok = lambda t, a: f"{t:02X}" + ("h" if a & 0x40 else "") + ("v" if a & 0x80 else "")
fails = []
def check(label, ok, extra=""):
    print(f"{label}: {ok}" + (f" {extra}" if extra else ""))
    if not ok: fails.append(label)

# what the game draws, from its tables (bank $1B for Rush's anims $D7-$D9, $1A for the teleport $13)
WANT = {"Rush Coil": (7, 4, {"sit": (0x1B, 0x0F), "spring": (0x1B, 0x10)}),
        "Rush Marine": (9, 2, {"swim": (0x1B, 0x94)}),
        "Rush Jet": (11, 3, {"fly 1": (0x1B, 0x0D), "fly 2": (0x1B, 0x0E)})}
TELE = {"teleport beam": 0x12, "teleport 2": 0x13, "teleport 3": 0x14}
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(accept_downloads=True, viewport={"width": 1400, "height": 1000})
    ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/index.html"); pg.wait_for_timeout(600)
    pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(500)
    prof = json.loads(pg.evaluate("JSON.stringify(MM3_PROFILE)"))
    names = [o["name"] for o in prof["objects"]]
    rush = {o["name"]: o for o in prof["objects"] if o.get("group") == "Rush"}
    check("Rush objects, after the weapons", list(rush) == list(WANT) and names.index("Rush Coil") == names.index("Shadow Blade") + 1)
    for name, (w, bank, frames) in WANT.items():
        o = rush[name]
        ok = o["chr_banks"] == [0, bank, 10, 0] and o["palette"] == [f"body.{w}"] and rom[PRG(2) + 0x634 + w] == bank
        for fn, (tb, fid) in {**frames, **{k: (0x1A, v) for k, v in TELE.items()}}.items():
            want = [[tok(t, a), dx, dy, "face" if a & 3 == 1 else None] for t, a, dx, dy in frame_model(tb, fid)]
            ok &= o["frames"][fn]["sprites"] == want
        check(f"{name}: frames, bank and palette match the ROM", ok)
    # Rush's own tiles: no other object draws them, and none follow edits elsewhere
    links = dict((int(k), v) for k, v in pg.evaluate("[...chrLinks()]"))
    body_offs = pg.evaluate("""S.objs.filter(o => o.group === 'Rush').flatMap(o => Object.entries(o.frames).filter(([n]) => !n.startsWith('teleport')).flatMap(([, f]) => f.slots.map(q => q.off)))""")
    others = pg.evaluate("""S.objs.filter(o => o.group !== 'Rush').flatMap(o => Object.values(o.frames).flatMap(f => f.slots.filter(Boolean).map(q => q.off)))""")
    marine70, jet70 = C + 2 * 1024 + 0x30 * 16, C + 3 * 1024 + 0x30 * 16  # tile $70 is byte-identical in Marine's and Jet's banks
    linked = {o: links[o] for o in set(body_offs) if o in links}
    check("Rush's tiles are his own (only Marine/Jet $70 follow each other)", not (set(body_offs) & set(others)) and linked == {marine70: [jet70], jet70: [marine70]}, {hex(k): [hex(x) for x in v] for k, v in linked.items()})
    # paint his face tile on the Coil sit frame + recolor Coil's body, the way a kid would in the editor
    pg.evaluate("selectObj(S.objs.findIndex(o => o.name === 'Rush Coil'))"); pg.wait_for_timeout(200)
    paint = pg.evaluate("""(() => { checkpoint(''); const f = curObj().frames.sit; const q = f.slots.find(q => q.idx === 0x71);
       for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) { const hit = slotAt(f, q.x + x, q.y + y); if (hit && hit.s === q) setObjPixel(f, q.x + x, q.y + y, ((x + y) & 1) ? 3 : 1); }
       S.spritePals['body.7'] = ['0F','24','14']; S.palEdited['body.7'] = true; objChanged(); return q.off; })()""")
    pg.screenshot(path=f"{T}/rush.png")
    with pg.expect_download() as d: pg.click("#btnSave"); pg.click("#dlGo")
    z1 = f"{T}/p1.zip"; d.value.save_as(z1); zipfile.ZipFile(z1).extractall(f"{T}/x")
    js = open(f"{T}/x/mega-man-3-hack.nes", "rb").read()
    r = subprocess.run(["ruby", f"{REPO}/tools/smb_patcher.rb", "build", f"{T}/x/config.json"], capture_output=True, text=True)
    rb = open(f"{T}/x/mega-man-3-hack.nes", "rb").read()
    check("JS == Ruby", r.returncode == 0 and js == rb, r.stderr[-200:])
    same_tile_other_banks = [C + bk * 1024 + 0x31 * 16 for bk in (1, 2, 3, 6, 7)]
    check("only Coil's bank changed", paint == C + 4 * 1024 + 0x31 * 16 and rb[paint:paint + 16] != rom[paint:paint + 16]
          and all(rb[o:o + 16] == rom[o:o + 16] for o in same_tile_other_banks))
    A641 = PRG(2) + 0x641
    check("body.7 in the ROM", rb[A641 + 28:A641 + 31].hex() == "0f2414", rb[A641 + 28:A641 + 31].hex())
    pg2 = ctx.new_page(); pg2.on("pageerror", lambda e: errors.append(str(e)))
    pg2.goto(f"file://{REPO}/index.html"); pg2.wait_for_timeout(500)
    pg2.set_input_files("#fProj", z1); pg2.wait_for_timeout(1000)
    with pg2.expect_download() as d: pg2.click("#btnSave"); pg2.click("#dlGo")
    z2 = f"{T}/p2.zip"; d.value.save_as(z2)
    A = {n: zipfile.ZipFile(z1).read(n) for n in zipfile.ZipFile(z1).namelist()}; B = {n: zipfile.ZipFile(z2).read(n) for n in zipfile.ZipFile(z2).namelist()}
    check("reopen round trip identical", A == B)
    b.close()
check("no page errors", not errors, errors)

try:
    import cynes
    from PIL import Image
except ImportError:
    print("(cynes not installed: skipped the in-game check)"); cynes = None
if cynes:
    from collections import Counter
    ST, B_ = cynes.NES_INPUT_START, cynes.NES_INPUT_B
    def run(nes, n, btn=0):
        f = None
        for _ in range(n): nes.controller = btn; f = nes.step(1)
        return f
    def boot(path):
        nes = cynes.NES(path)
        for n, btn in [(240, 0), (5, ST), (180, 0), (5, ST), (180, 0), (8, cynes.NES_INPUT_UP), (30, 0), (5, ST), (1000, 0)]: run(nes, n, btn)
        for i in range(12): nes[0xA2 + i] = 0x9C          # own every weapon so the pause menu lists Rush
        run(nes, 5, ST); run(nes, 120, 0)
        return nes
    def pick(nes, w):  # the pause-menu cursor ($A1); unpausing runs the game's own weapon switch
        nes[0xA1] = w; run(nes, 5, ST); run(nes, 120, 0)
    def rush_oam(nes, lo, hi): return Counter((nes[0x200 + 4 * i + 1], nes[0x200 + 4 * i + 2] & 0xC3) for i in range(64) if nes[0x200 + 4 * i] < 0xEF and lo <= nes[0x200 + 4 * i + 1] <= hi)
    model = lambda b, fid: [Counter((t, a) for t, a, dx, dy in frame_model(b, fid, f)) for f in (1, 0)]
    built = f"{T}/x/mega-man-3-hack.nes"
    # Coil in the built ROM: the game picks bank 4 and the new colors, sits on $0F, springs to $10 when Mega Man lands on him
    nes = boot(built); pick(nes, 7)
    check("game selects Coil: bank + palette", nes[0xA0] == 7 and nes[0xEB] == 4 and [nes[0x611 + i] for i in range(3)] == [0x0F, 0x24, 0x14])
    run(nes, 4, B_); seq = []
    for n, btn in [(46, 0), (10, cynes.NES_INPUT_A | cynes.NES_INPUT_RIGHT), (14, cynes.NES_INPUT_A), (40, 0)]:
        for _ in range(n):
            f = run(nes, 1, btn); c = rush_oam(nes, 0x70, 0x7E)
            seq.append("sit" if c in model(0x1B, 0x0F) else "spring" if c in model(0x1B, 0x10) else "-" if not c else "?")
            if seq[-1] == "sit" and not os.path.exists(f"{T}/coil_ingame.png"): Image.fromarray(f).resize((512, 480), Image.NEAREST).save(f"{T}/coil_ingame.png")
    runs = [x for i, x in enumerate(seq) if not i or seq[i - 1] != x]
    check("Coil in game: teleport, sit, spring", runs == ["-", "sit", "spring"], runs)
    # Jet: alternates $0D/$0E every 5 frames
    nes = boot(ROM); pick(nes, 11); run(nes, 4, B_); seq = []
    for _ in range(80):
        run(nes, 1, 0); c = rush_oam(nes, 0x70, 0x79); seq.append("1" if c in model(0x1B, 0x0D) else "2" if c in model(0x1B, 0x0E) else "-" if not c else "?")
    s = "".join(seq).strip("-"); check("Jet in game: flicker 5/5", "?" not in s and len(s) > 30 and all(len(r) == 5 for r in s.replace("12", "1 2").replace("21", "2 1").split()[1:-1]), s[:40])
    # Marine: only lands in water ($41 == $80, bank $1C $86F6); skip that check in a scratch copy so he lands here
    dry = bytearray(rom); o = PRG(0x1C) + 0x6FA; assert dry[o:o + 2] == b"\xd0\xe8"; dry[o:o + 2] = b"\xea\xea"
    open(f"{T}/marine_dry.nes", "wb").write(dry)
    nes = boot(f"{T}/marine_dry.nes"); pick(nes, 9)
    check("game selects Marine: bank", nes[0xA0] == 9 and nes[0xEB] == 2)
    run(nes, 4, B_); run(nes, 50, 0)
    check("Marine in game: draws $94", nes[0x5C1] == 0xD9 and rush_oam(nes, 0x70, 0x7C) in model(0x1B, 0x94))

print("FAILED:", fails) if fails else print("all Rush checks passed")
sys.exit(1 if fails else 0)
