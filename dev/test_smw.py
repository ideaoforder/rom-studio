"""Super Mario World (USA), the SNES page. Needs SMW_ROM=/path/to/Super Mario World (USA).sfc (pip install stable-retro for the boot checks).
1. LZ2: the browser, Ruby and Python encoders give identical bytes for every graphics file, and decode back exactly.
2. Edits (Mario, an item, a block tile, a colour) -> download -> Ruby build is byte-identical -> reopen round trip.
3. A big edit that no longer fits -> every file is repacked and repointed (JS == Ruby again).
4. Both built ROMs boot to a level; the game's own decompressed graphics (WRAM/VRAM) and colours carry the edits."""
import os, sys, json, zipfile, subprocess, shutil, hashlib
from playwright.sync_api import sync_playwright
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV); T = f"{DEV}/smw_test"
ROM = os.environ.get("SMW_ROM") or sys.exit("Set SMW_ROM")
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
sys.path.insert(0, f"{DEV}/snes"); sys.path.insert(0, f"{DEV}/gen_smw")
import lz2
rom = open(ROM, "rb").read(); errors = []; res = []
def check(name, ok, info=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", name, info)
prof = json.loads(open(f"{REPO}/snes/profiles/smw.js").read().split("push(", 1)[1].rsplit(");", 1)[0])
files = prof["gfx"]["files"]

# 1. codec parity
dec = {f["id"]: lz2.decode(rom, f["at"])[0] for f in files}
py = hashlib.sha1(b"".join(lz2.encode(dec[f["id"]]) for f in files)).hexdigest()
node = subprocess.run(["node", "-e", f"""
require('{REPO}/snes/lib/lz2.js'); const fs = require('fs'), c = require('crypto'); const r = fs.readFileSync({json.dumps(ROM)});
const h = c.createHash('sha1'); for (const at of {json.dumps([f['at'] for f in files])}) h.update(LZ2.encode(LZ2.decode(r, at).data)); console.log(h.digest('hex'));"""], capture_output=True, text=True).stdout.strip()
rb = subprocess.run(["ruby", "-e", f"""
require_relative '{REPO}/tools/snes_build'; require 'digest'; r = File.binread({json.dumps(ROM)}); h = Digest::SHA1.new
{json.dumps([f['at'] for f in files])}.each {{ |at| h << SnesStudio::LZ2.encode(SnesStudio::LZ2.decode(r, at)[0]) }}; puts h.hexdigest"""], capture_output=True, text=True)
check("LZ2 encoders agree (JS, Ruby, Python)", py == node == rb.stdout.strip(), (py[:10], node[:10], rb.stdout.strip()[:10], rb.stderr[-200:]))
check("re-encoding every file round-trips", all(lz2.decode(lz2.encode(d), 0)[0] == d for d in dec.values()))
saved = sum(lz2.decode(rom, f["at"])[1] for f in files) - sum(len(lz2.encode(d)) for d in dec.values())
check("our encoder packs tighter than the original (room to grow)", saved > 0, f"{saved} bytes")

def zipped(z): return {n: zipfile.ZipFile(z).read(n) for n in zipfile.ZipFile(z).namelist()}
def download(pg, tag):
    with pg.expect_download() as d: pg.click("#btnSave"); pg.click("#dlGo")
    z = f"{T}/{tag}.zip"; d.value.save_as(z); x = f"{T}/{tag}"; zipfile.ZipFile(z).extractall(x)
    cfg = json.load(open(f"{x}/config.json")); js = open(f"{x}/{cfg['output']}", "rb").read()
    r = subprocess.run(["ruby", f"{REPO}/tools/snes_build.rb", "build", f"{x}/config.json"], capture_output=True, text=True)
    return z, x, cfg, js, open(f"{x}/{cfg['output']}", "rb").read(), r
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(accept_downloads=True, viewport={"width": 1400, "height": 950}); ctx.route("https://fonts.**/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/snes/index.html"); pg.wait_for_timeout(400)
    pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(1500)
    check("ROM recognised", "Super Mario World" in pg.text_content("#romChip"), pg.text_content("#romChip"))
    # painting with the pointer (as on an iPad): a stroke on the canvas edits a tile, Undo takes it back
    box = pg.locator("#painter").bounding_box(); pg.evaluate("S.sel = { pal: curFrame().parts[0][4], idx: 1 }")
    pg.mouse.move(box["x"] + box["width"] * .3, box["y"] + box["height"] * .4); pg.mouse.down()
    pg.mouse.move(box["x"] + box["width"] * .7, box["y"] + box["height"] * .45, steps=8); pg.mouse.up()
    n_painted = pg.evaluate("Object.values(S.tiles).reduce((n, f) => n + Object.keys(f).length, 0)")
    pg.click("#btnUndo"); n_after = pg.evaluate("Object.values(S.tiles).reduce((n, f) => n + Object.keys(f).length, 0)")
    check("a pencil stroke paints tiles; Undo removes it", n_painted > 0 and n_after == 0, (n_painted, n_after))
    # 2. paint: Mario (small) pose 00 striped, the mushroom filled, a tile of the first screen, Mario's red changed
    edits = pg.evaluate("""(() => {
      const O = n => S.P.objects.find(o => o.name === n), fr = (o, i) => o.frames[i || 0];
      const touch = (p, f) => { const px = tileAt(p[0], p[1]).map((r, y) => r.map((v, x) => f(v, x, y))); (S.tiles[fileOf(p[0]).id] ||= {})[p[1]] = Tiles.toHex(px); return [fileOf(p[0]).id, p[1]]; };
      const out = { mario: fr(O('Mario (small)')).parts.map(p => touch(p, (v, x, y) => v ? (y % 2 ? 1 : v) : 0)) };
      out.mush = fr(O('Mushroom')).parts.slice(0, 1).map(p => touch(p, v => v ? 2 : 0));
      const blk = S.P.objects.find(o => o.category === 'blocks'); out.block = [touch(fr(blk).parts.find(p => tileAt(p[0], p[1]).some(r => r.some(v => v))), (v, x, y) => y < 2 ? 1 : v)];
      const mp = fr(O('Mario (small)')).parts[0][4], off = S.P.palettes[mp].colors[8]; S.colors[off] = '03E0'; out.color = off;
      changed(); return out; })()""")
    z1, x1, cfg, js, rb, r = download(pg, "edit")
    check("Ruby build == browser build", js == rb and r.returncode == 0, r.stderr[-300:])
    ptrs = lambda b: bytes(b[o] for f in files for o, k in f.get("ptrs", []) for o in range(o, o + {"word": 2, "long": 3}.get(k, 1)))
    check("edited files fit back where they were (no pointer changes)", ptrs(js) == ptrs(rom) and js != rom)
    pg2 = ctx.new_page(); pg2.on("pageerror", lambda e: errors.append(str(e))); pg2.goto(f"file://{REPO}/snes/index.html"); pg2.wait_for_timeout(400)
    pg2.set_input_files("#fProj", z1); pg2.wait_for_timeout(1500)
    z2, *_ = download(pg2, "reopen")
    A, B = zipped(z1), zipped(z2)
    check("reopen round trip identical", A == B, [k for k in A if A.get(k) != B.get(k)])
    # 3. noise over Mario's graphics and a sprite file: too big to fit -> repack all files and repoint
    pg.evaluate("""(() => { let s = 7; const rnd = () => (s = (s * 1103515245 + 12345) & 0x7fffffff) >> 16;
      for (const [id, n] of [['GFX32', 200], ['GFX00', 120], ['GFX14', 120]]) { const fi = S.P.gfx.files.findIndex(f => f.id === id), bpp = S.P.gfx.files[fi].bpp;
        for (let t = 0; t < n; t++) (S.tiles[id] ||= {})[t] = Tiles.toHex(Array.from({length: 8}, () => Array.from({length: 8}, () => rnd() % (bpp === 4 ? 16 : 8)))); }
      changed(); })()""")
    z3, x3, cfg3, js3, rb3, r3 = download(pg, "repack")
    moved = [f["id"] for f in files if f.get("ptrs") and bytes(js3[o] for o, k in f["ptrs"][:1]) != bytes(rom[o] for o, k in f["ptrs"][:1])]
    check("repacked build: Ruby == browser", js3 == rb3 and r3.returncode == 0, r3.stderr[-300:])
    check("repacked: files moved and pointers follow", len(moved) > 10, f"{len(moved)} files start somewhere new")
    want = json.loads(pg.evaluate("JSON.stringify(Object.fromEntries(['GFX32','GFX00','GFX14'].map(id => [id, (() => { const f = S.P.gfx.files.find(x => x.id === id), d = S.files[id].data.slice(); for (const [t, h] of Object.entries(S.tiles[id])) Tiles.encodeTile(Tiles.fromHex(h), d, t * Tiles.BYTES[f.bpp], f.bpp); return Array.from(d); })()])))"))
    check("checksum fixed", (sum(js3) & 0xFFFF) == (js3[0x7FDE] | js3[0x7FDF] << 8))
    b.close()

# 4. boot them
try:
    from emu import SNES
    from capture import warp, OBJ_VRAM
    from smw import to4
    def level(path):
        s = SNES(path); s.run(300); s.run(5, "START"); s.run(90)
        for _ in range(3): s.run(5, "START"); s.run(60)
        for _ in range(60):
            s.run(5, "A"); s.run(25)
            if s.ram[0x100] == 0x0E: break
        s.run(60); ok = warp(s, 0x15); s.run(30); return s, ok
    s1, ok1 = level(f"{x1}/{cfg['output']}")
    m = dict((f["id"], f) for f in files)
    d32 = bytearray(dec["GFX32"])
    from tiles import encode_tile  # noqa
except ImportError as e:
    s1 = None; print("(stable-retro not installed: skipped booting)", e)
if s1:
    gf = json.load(open(f"{x1}/config.json"))["state"]["tiles"]
    import importlib; tl = importlib.import_module("tiles")
    def applied(id_, base):
        d = bytearray(base); bpp = m[id_]["bpp"]; n = {3: 24, 4: 32}[bpp]
        for t, h in gf.get(id_, {}).items(): tl.encode_tile(h, d, int(t) * n, bpp)
        return bytes(d)
    ram = s1.ram
    check("edited ROM reaches a level", ok1 and s1.ram[0x100] == 0x14)
    check("the game decompresses the painted Mario into WRAM ($7E:2000)", ram[0x2000:0x2000 + len(d32)] == applied("GFX32", d32))
    g00 = applied("GFX00", dec["GFX00"]); v = s1.vram
    check("sprite graphics in VRAM carry the painted item", all(v[OBJ_VRAM + 32 * t:OBJ_VRAM + 32 * t + 32] == to4(g00[24 * t:24 * t + 24], 0) for t in range(0x80) if str(t) in gf.get("GFX00", {})))
    cg = s1.cgram; cidx = [i for i in range(256) if cg[2 * i:2 * i + 2] == bytes([0xE0, 0x03])]
    check("the new colour is in CGRAM", len(cidx) > 0, [hex(i) for i in cidx][:4])
    s3, ok3 = level(f"{x3}/{cfg3['output']}")
    check("repacked ROM reaches a level", ok3 and s3.ram[0x100] == 0x14)
    check("repacked: Mario's graphics decompress to the edits", s3.ram[0x2000:0x2000 + len(d32)] == bytes(want["GFX32"]))
    v3 = s3.vram; g = bytes(want["GFX00"])
    check("repacked: sprite file decompresses to the edits", all(v3[OBJ_VRAM + 32 * t:OBJ_VRAM + 32 * t + 32] == to4(g[24 * t:24 * t + 24], 0) for t in range(0x40, 0x78)))   # (tiles 00-3F also hold Mario & friends, uploaded each frame)
print("errors:", errors or "none"); print(f"{sum(res)}/{len(res)} PASS")
sys.exit(0 if all(res) and not errors else 1)
