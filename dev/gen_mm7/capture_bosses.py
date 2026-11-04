"""The robot masters as they pose in each stage's intro. A stage counts as beaten when its weapon is owned
($0B83 + 2n bit 7) and $0B7C is set, so taking both away while the password loads replays the intro."""
import json, sys
import capture as C
WEAPON_OF = {"Freeze Man": 1, "Cloud Man": 2, "Junk Man": 3, "Turbo Man": 4, "Slash Man": 5, "Shade Man": 6, "Burst Man": 7, "Spring Man": 8}
FIRST_FOUR = "6235564618413555"   # a published password (the first robot masters beaten)
def capture():
    prov = C.Prov(); out = {}
    for name, k in WEAPON_OF.items():
        s = C.stage_select(password=FIRST_FOUR, unbeat=[k]); s.run(60)
        for m in C.STAGES[name]: s.run(4, m); s.run(12)
        s.run(4, "START"); seen = {}; cgs = []
        for f in range(0, 600, 3):
            s.run(3); r = s.ram
            ents = [e for e in C.oam(r) if e[1] < 224]
            if not ents: continue
            s.run(1); parts, miss = prov.parts(s.vram, ents, 0, 0)
            # the boss is the big group in the middle band of the intro screen (the cursor and energy bar aren't)
            parts = [p for p in parts if 70 <= p[3] <= 150 and 60 <= p[2] <= 250]
            if len(parts) >= 16 and not miss:
                seen.setdefault(json.dumps(sorted(map(tuple, parts))), parts); cgs.append(s.cgram.hex())
        cg = max(set(cgs), key=cgs.count) if cgs else None   # the colours most of the intro is shown in (not a flash)
        out[name] = {"frames": list(seen.values()), "cgram": cg}
        print(name, len(seen), flush=True)
    return out
if __name__ == "__main__":
    json.dump(capture(), open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mm7_bosses.json", "w"))
