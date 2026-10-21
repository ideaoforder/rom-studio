from devpaths import REPO, ROM_PATH, JSYAML, bench_body
import json, os, shutil, tempfile
from lupa import lua54

S = os.path.dirname(os.path.abspath(__file__))
rom = open(ROM_PATH, "rb").read()
chr_ = rom[0x8010:0x8010 + 0x2000]
folder = tempfile.mkdtemp()

# Fake OAM: big-Mario walk 1 (tiles 00..07 as 2x4) at (100, 80) + a goomba (70..73) + offscreen rest
oam = [0xF8, 0, 0, 0] * 64
spr = [(100 + (i % 2) * 8, 80 + (i // 2) * 8, i, 0) for i in range(8)]
spr += [(150, 100, 0x70, 3), (158, 100, 0x71, 3), (150, 108, 0x72, 3), (158, 108, 0x73, 3)]
for i, (x, y, t, a) in enumerate(spr):
    oam[i * 4:i * 4 + 4] = [y, t, a, x]
pal = list(range(32))
logs, draws = [], []

L = lua54.LuaRuntime(unpack_returned_tuples=True)
L.execute("bit32 = nil")
callbacks = {}
def read(addr, mt, signed):
    if mt == 1: return oam[addr]
    if mt == 2: return pal[addr]
    if mt == 3: return chr_[addr]
    raise Exception("bad memtype %r" % mt)
state = {"ppu.control.largeSprites": False, "ppu.control.spritePatternAddr": 0}
emu = L.table_from({
    "memType": L.table_from({"nesSpriteRam": 1, "nesPaletteRam": 2, "nesPpuDebug": 3, "nesPpuMemory": 4}),
    "eventType": L.table_from({"endFrame": 3, "scriptEnded": 5}),
    "getScriptDataFolder": lambda: folder,
    "displayMessage": lambda c, m: logs.append(m),
    "log": lambda m: logs.append(m),
    "getRomInfo": lambda: L.table_from({"name": "smb.nes", "fileSha1Hash": "abc"}),
    "getState": lambda: L.table_from(state),
    "read": read,
    "drawString": lambda *a: draws.append(a),
    "addEventCallback": lambda fn, ev: callbacks.__setitem__(ev, fn),
})
L.globals().emu = emu
L.execute(open(f"{REPO}/tools/sprite_capture.lua").read())
for n in range(40):
    if n == 20:  # change arrangement: mario walk 2 tiles 08..0F
        for i in range(8): oam[i * 4 + 1] = 8 + i
    callbacks[3]()
callbacks[5]()

lines = [json.loads(l) for l in open(f"{folder}/capture.jsonl")]
print("lines:", [l["type"] for l in lines])
fr = [l for l in lines if l["type"] == "frame"]
ok = all(bytes.fromhex(hx) == chr_[int(ad):int(ad) + 16] for f in fr for ad, hx in f["tiles"].items())
print("frames recorded:", len(fr), "(expect 2 distinct)", "| sprites in first:", len(fr[0]["sprites"]), "| tile bytes match ROM:", ok)
print("end:", lines[-1], "| logs:", logs[-1][:70])
shutil.rmtree(folder)
