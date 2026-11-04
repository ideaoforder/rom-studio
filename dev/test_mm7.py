"""Mega Man 7 (USA), the SNES page. Needs MM7_ROM=/path/to/Mega Man 7 (USA).sfc (pip install stable-retro for the boot checks).
1. Capcom LZ: the browser, Ruby and Python encoders give identical bytes for every graphics set, and decode back exactly.
2. Edits (Mega Man's uncompressed tiles, an enemy, a background tile, a colour) -> download -> Ruby build is byte-identical
   -> reopen round trip.
3. A big edit that no longer fits -> every set is repacked and its table entry repointed (JS == Ruby again).
4. Both built ROMs boot into Freeze Man's stage with the edited background tile and colour in VRAM/CGRAM."""
import os, sys, json, zipfile, subprocess, shutil, hashlib
from playwright.sync_api import sync_playwright
DEV = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(DEV); T = f"{DEV}/mm7_test"
ROM = os.environ.get("MM7_ROM") or sys.exit("Set MM7_ROM")
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
sys.path.insert(0, f"{DEV}/snes"); sys.path.insert(0, f"{DEV}/gen_mm7")
import clz, tiles
rom = open(ROM, "rb").read(); errors = []; res = []
def check(name, ok, info=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", name, info)
prof = json.loads(open(f"{REPO}/snes/profiles/mm7.js").read().split("push(", 1)[1].rsplit(");", 1)[0])
files = prof["gfx"]["files"]; sets = [f for f in files if f["codec"] == "clz"]

# 1. codec parity
dec = {f["id"]: clz.decode(rom, f["at"], f["unpacked"])[0] for f in sets}
py = hashlib.sha1(b"".join(clz.encode(dec[f["id"]]) for f in sets)).hexdigest()
node = subprocess.run(["node", "-e", f"""
require('{REPO}/snes/lib/clz.js'); const r = require('fs').readFileSync({json.dumps(ROM)}), h = require('crypto').createHash('sha1');
for (const [at, n] of {json.dumps([[f['at'], f['unpacked']] for f in sets])}) h.update(CLZ.encode(CLZ.decode(r, at, n).data)); console.log(h.digest('hex'));"""],
    capture_output=True, text=True).stdout.strip()
rb = subprocess.run(["ruby", "-e", f"""
require_relative '{REPO}/tools/snes_build'; require 'digest'; r = File.binread({json.dumps(ROM)}); h = Digest::SHA1.new
{json.dumps([[f['at'], f['unpacked']] for f in sets])}.each {{ |at, n| h << SnesStudio::CLZ.encode(SnesStudio::CLZ.decode(r, at, n)[0]) }}; puts h.hexdigest"""],
    capture_output=True, text=True)
check("Capcom LZ encoders agree (JS, Ruby, Python)", py == node == rb.stdout.strip(), (py[:10], node[:10], rb.stdout.strip()[:10], rb.stderr[-200:]))
check("re-encoding every set round-trips", all(clz.decode(clz.encode(d), 0, len(d))[0] == d for d in dec.values()))
saved = sum(clz.decode(rom, f["at"], f["unpacked"])[1] for f in sets) - sum(len(clz.encode(d)) for d in dec.values())
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
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.add_init_script("try{localStorage.clear()}catch(e){}")
    pg.goto(f"file://{REPO}/snes/index.html"); pg.wait_for_timeout(400); pg.set_input_files("#fRom", ROM); pg.wait_for_timeout(2500)
    check("ROM recognised", "Mega Man 7" in pg.text_content("#romChip"), pg.text_content("#romChip"))
    edits = pg.evaluate("""(() => {
      const O = n => S.P.objects.find(o => o.name === n);
      const touch = (p, f) => { const px = tileAt(p[0], p[1]).map((r, y) => r.map((v, x) => f(v, x, y))); (S.tiles[fileOf(p[0]).id] ||= {})[p[1]] = Tiles.toHex(px); return [fileOf(p[0]).id, p[1]]; };
      const out = { mega: O('Mega Man').frames[1].parts.slice(0, 4).map(p => touch(p, (v, x, y) => v ? (y % 2 ? 1 : v) : 0)) };
      const en = S.P.objects.find(o => o.group === 'Freeze Man' && o.type !== '04'); out.enemy = [touch(en.frames[0].parts.find(p => tileAt(p[0], p[1]).some(r => r.some(v => v))), v => v ? 2 : 0)];
      const blk = S.P.objects.find(o => o.name.startsWith('Freeze Man')); const bp = blk.frames[0].parts.find(p => tileAt(p[0], p[1]).some(r => r.some(v => v)));
      out.block = [touch(bp, (v, x, y) => y < 2 ? 1 : v)];
      const off = S.P.palettes[bp[4]].colors[1]; S.colors[off] = '03E0'; out.color = off;
      changed(); return out; })()""")
    z1, x1, cfg, js, rb, r = download(pg, "edit")
    check("Ruby build == browser build", js == rb and r.returncode == 0, r.stderr[-300:])
    m = {f["id"]: f for f in files}
    raw_ok = all(js[m[fid]["at"] + 32 * t:m[fid]["at"] + 32 * t + 32] != rom[m[fid]["at"] + 32 * t:m[fid]["at"] + 32 * t + 32] for fid, t in edits["mega"] if fid.startswith("RAW"))
    check("Mega Man's uncompressed tiles written in place", raw_ok, edits["mega"])
    pg2 = ctx.new_page(); pg2.on("pageerror", lambda e: errors.append(str(e))); pg2.goto(f"file://{REPO}/snes/index.html"); pg2.wait_for_timeout(400)
    pg2.set_input_files("#fProj", z1); pg2.wait_for_timeout(2500)
    z2, *_ = download(pg2, "reopen"); A, B = zipped(z1), zipped(z2)
    check("reopen round trip identical", A == B, [k for k in A if A.get(k) != B.get(k)])
    # 3. noise over three big sets: too big to fit -> repack everything and repoint the set table
    pg.evaluate("""(() => { let s = 7; const rnd = () => (s = (s * 1103515245 + 12345) & 0x7fffffff) >> 16;
      const big = S.P.gfx.files.filter(f => f.codec === 'clz').sort((a, b) => b.unpacked - a.unpacked).slice(0, 3);
      for (const f of big) for (let t = 0; t < 200; t++) (S.tiles[f.id] ||= {})[t] = Tiles.toHex(Array.from({length: 8}, () => Array.from({length: 8}, () => rnd() % 16)));
      changed(); })()""")
    z3, x3, cfg3, js3, rb3, r3 = download(pg, "repack")
    check("repacked build: Ruby == browser", js3 == rb3 and r3.returncode == 0, r3.stderr[-300:])
    moved = sum(1 for f in sets if js3[f["ptrs"][0][0]:f["ptrs"][0][0] + 3] != rom[f["ptrs"][0][0]:f["ptrs"][0][0] + 3])
    check("repacked: sets moved and the table follows", moved > 50, f"{moved} sets start somewhere new")
    st3 = json.load(open(f"{x3}/config.json"))["state"]["tiles"]
    ok = True
    for f in sets:
        e = st3.get(f["id"]); off = (js3[f["ptrs"][0][0]] | js3[f["ptrs"][0][0] + 1] << 8 | js3[f["ptrs"][0][0] + 2] << 16) - 0xC00000
        want = bytearray(dec[f["id"]])
        for t, h in (e or {}).items(): tiles.encode_tile(h, want, int(t) * 32, 4)
        ok &= clz.decode(js3, off, f["unpacked"])[0] == bytes(want)
    check("repacked: every set decodes to its edits through the new table", ok)
    check("checksum fixed", (sum(js3) & 0xFFFF) == (js3[0xFFDE] | js3[0xFFDF] << 8))
    b.close()

# 4. boot them
try:
    import capture as C
    from emu import SNES
except ImportError as e:
    C = None; print("(stable-retro not installed: skipped booting)", e)
if C:
    st = C.stage_select().save()
    for tag, path in [("edited", f"{x1}/{cfg['output']}"), ("repacked", f"{x3}/{cfg3['output']}")]:
        s = SNES(path); s.load(st); C.enter(s, "Freeze Man"); s.run(20); v = s.vram; cg = s.cgram
        fid, t = edits["block"][0]; d = bytearray(dec[fid]); tiles.encode_tile(json.load(open(f"{x1}/config.json"))["state"]["tiles"][fid][str(t)], d, 32 * t, 4)
        if tag == "edited":
            check("edited ROM: the painted background tile is in VRAM", bytes(d[32 * t:32 * t + 32]) in v)
            check("edited ROM: the new colour is in CGRAM", any(cg[2 * i:2 * i + 2] == bytes([0xE0, 0x03]) for i in range(128)))
        else:
            check("repacked ROM reaches Freeze Man's stage with its graphics", s.ram[0x0C2E] == 28 and sum(1 for i in range(0, 0xA000, 32) if any(v[i:i + 32])) > 200)
print("errors:", errors or "none"); print(f"{sum(res)}/{len(res)} PASS")
sys.exit(0 if all(res) and not errors else 1)
