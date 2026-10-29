# Castlevania profile generator

Rebuilds `CV_PROFILE` in `index.html` from your own ROM: Castlevania (USA) (Rev 1), headerless CRC32 `B668C7FC`. There's no public disassembly. Everything here reads the ROM directly and checks it in the [cynes](https://github.com/Youlixx/cynes) emulator. Nothing from the game is committed.

```sh
export CV_ROM="/path/to/Castlevania (USA) (Rev 1).nes"
WRITE_HTML=1 python3 build_profile.py   # first run captures the stage screens in cynes (cached in $CV_SCREENS, default /tmp/cv_screens.json)
```

- `gfx.py`: the CHR set table at `$FDBB` and the per-stage set at `$C8B0`. `ppu_map(sets)` maps PPU tile → file offset.
- `sprites.py`: metasprites as the bank 0 drawer reads them.
- `render.py`: draws codes with the game's palettes, for picking objects. Nothing it draws is committed.
- `emu.py`: boots the game, warps to a stage, and reads CHR-RAM from save states.
- `explore.py`: walks a stage and logs the sprite codes the game draws.
- `screens.py`: each stage's first screen from nametable 0.
- `objects_def.py`: which codes make each object, and in which block.
- `mech.py`: mechanics (byte patterns, hooks at `$BA40`/`$BA60` in bank 6's free space).
- `build_profile.py`: puts it together (areas, link sets, palettes, objects, stage blocks, mechanics).

Checks: `dev/test_castlevania.py` (edits → download → Ruby parity → reopen → the built ROM's CHR-RAM holds the painted tiles) and `dev/test_castlevania_mech.py`.
