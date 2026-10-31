# Zelda profile generator

Rebuilds `ZELDA_PROFILE` in `index.html` from your own ROM: Legend of Zelda, The (USA) (Rev 1), headerless CRC32 `EAF7ED72`. Labels and data offsets come from the [zelda1-disassembly](https://github.com/aldonunez/zelda1-disassembly) (`bins.xml`). Everything is checked against the Rev 1 ROM in the [cynes](https://github.com/Youlixx/cynes) emulator. Nothing from the game is committed.

```sh
export ZELDA_ROM="/path/to/Legend of Zelda, The (USA) (Rev 1).nes"
WRITE_HTML=1 python3 build_profile.py   # first run captures the room screens in cynes (cached in $ZELDA_SCREENS, default /tmp/zelda_screens.json)
```

- `gfx.py`: which PRG blocks each area copies to CHR-RAM. `ppu_map(area)` maps PPU tile → file offset. `palettes(area)` reads the LevelInfo palettes.
- `anims.py`: the animation frame and attribute tables, and the left/right mirroring guess.
- `render.py`, `render2.py`: contact sheets for picking objects. Nothing they draw is committed.
- `objects_def.py`: the objects, with their animations and the areas they live in.
- `screens.py`: boots the game, registers a file, and grabs overworld rooms and level entrances from nametable 0.
- `mech.py`: mechanics (byte patterns, plus the starting-kit hook at `$AF90` in bank 2's free space).
- `build_profile.py`: puts it together (areas, palettes, objects, room blocks, mechanics, presets).

Checks: `dev/test_zelda.py` (edits → download → Ruby parity → reopen → the built ROM's CHR-RAM holds the painted tiles) and `dev/test_zelda_mech.py`.
