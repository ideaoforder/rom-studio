# Super Mario World profile generator

Rebuilds `snes/profiles/smw.js` from your own ROM: Super Mario World (USA), 524,288 bytes, CRC32 `B19ED489`. Addresses are SNES (LoROM) labels from [SMWDisX](https://github.com/IsoFrieze/SMWDisX)'s `SMW_U.sym`. Frames come from the running game in stable-retro's Snes9x core. Nothing from the game is committed.

```sh
pip install stable-retro
export SMW_ROM="/path/to/Super Mario World (USA).sfc"
python3 capture_mario.py /tmp/smw_mario.json     # every pose x power-up (about 30 s)
python3 capture_levels.py /tmp/smw_levels.json   # levels $01-$24 and $101-$13B, plus spawned items (about 10 min)
python3 build_profile.py                          # -> ../../snes/profiles/smw.js
```

- `smw.py`: ROM facts. The 52 LZ2 graphics files (GFX00–31 through `GFXFilesLow/High/Bank`, GFX32/33 loaded by `CODE_00B888`), the 3bpp→4bpp upload rule, and a model of `LoadPalette` (which ROM offset ends up in each CGRAM colour).
- `capture.py`: boots to the map, force-loads levels with `$0109`, groups OAM per sprite slot (`$15EA,x`), and maps VRAM tiles back to (file, tile) by matching bytes. It also reads the layer 1/2 tilemaps, which are 64×64.
- `capture_mario.py`: a scratch ROM whose player drawing routine reads the pose from `$1B97` (unused RAM), so every pose can be drawn for each power-up.
- `capture_levels.py`: plays each level (Mario hovers and flashes, so he can't fall into pits or get hurt) and spawns the always-loaded items next to Mario. The `$101`+ levels use a scratch ROM whose forced level number always gets the submap high byte.
- `names.py`: sprite names from SMWDisX's sprite table comments.
- `mech.py`: the mechanics (patterns, plus two small hooks in the unused bytes at `$00:FF93`).
- `build_profile.py`: puts it together.

Checks: `dev/test_smw.py` (codec parity, edits → download → Ruby parity → reopen, a too-big edit that forces a repack, then both ROMs booted with the edits found in WRAM/VRAM/CGRAM) and `dev/test_smw_mech.py`.
