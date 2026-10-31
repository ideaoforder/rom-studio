# Mega Man 3 profile generators

`MM3_PROFILE` in `index.html` predates this folder; `rush.py` is the first piece rebuilt by a script. It reads your own Mega Man 3 (USA) ROM (393,232 bytes) and writes the three Rush objects (Coil, Marine, Jet) after the weapons. Nothing from the game is committed.

```sh
export MM3_ROM="/path/to/Mega Man 3 (USA).nes"
python3 rush.py                 # print the objects
WRITE_HTML=1 python3 rush.py    # replace them in index.html (idempotent)
```

Check: `dev/test_mm3_rush.py`. How Rush is drawn is in `HANDOFF.md` (Mega Man 3 → Rush).
