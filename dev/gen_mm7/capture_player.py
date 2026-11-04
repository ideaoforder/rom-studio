"""Mega Man's poses on flat ground: standing, walking, jumping, shooting, sliding, charging (one frame in three)."""
import json, sys
import capture as C
SCRIPT = [(60, ()), (60, ("RIGHT",)), (40, ("B",)), (30, ()), (40, ("Y",)), (40, ("RIGHT", "Y")), (30, ("B", "Y")), (30, ()),
          (30, ("DOWN", "B")), (30, ()), (100, ("Y",)), (30, ()), (60, ("LEFT",)), (40, ("LEFT", "B")), (30, ("LEFT", "Y")),
          (40, ("UP",)), (40, ("DOWN",)), (60, ("RIGHT", "B", "Y"))]
def capture(stage="Freeze Man"):
    s = C.stage_select(); C.enter(s, stage); s.run(20); prov = C.Prov(); seen = {}
    for n, keys in SCRIPT:
        for f in range(n):
            pressed = keys if not ("Y" in keys and n == 100) or f < n - 1 else ()   # let go after charging
            s.run(1, *pressed)
            if f % 3: continue
            g = C.groups(s.ram).get(("player", 0, 0))
            if not g: continue
            s.run(1, *pressed); parts, miss = prov.parts(s.vram, g[2], g[0], g[1])
            if parts and not miss: seen.setdefault(json.dumps(sorted(map(tuple, parts))), parts)
    return seen
if __name__ == "__main__":
    out = capture(); json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mm7_player.json", "w")); print(len(out), "poses")
