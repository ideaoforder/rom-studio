# ROM Studio: handoff

Where this project stands and how to pick it up in an IDE. Written 2026-10-20 at the end of a long Claude session (Mark + son, SMB reskin).

## What it is

- `index.html`: the whole app ("SMB Skin Bench"), one self-contained page. Tabs: **Player** (rig-posed body parts → 28 game frames), **Enemies & items**, **Blocks**, **Sounds** (18 SFX), **Music** (12 songs). Bring your own *Super Mario Bros. (World)* ROM (40,976 bytes); nothing from the game is in the repo.
- `tools/smb_patcher.rb` + `tools/smb_rig.rb`: Ruby (stdlib only) CLI: `dump` / `pose` / `build` / `parts` / `colors`. `build config.json` rebuilds the exact same ROM as the browser from a downloaded project zip (verified byte-identical in every feature).
- `tools/sprite_capture.lua`: Mesen 2 script that logs OAM/CHR to `capture.jsonl` (for Mega Man 6, see Next).
- Hosted on GitHub Pages (`ideaoforder.github.io/rom-studio`) for the kids' iPads. Also published as a private Claude artifact, but **the Claude desktop artifact panel does not persist localStorage**, so autosave doesn't work there. Pages does.

## Architecture (index.html)

Global state `S`: `rig, parts, palettes, names, rom, profile, objs, chrEdits, spritePals, palEdited, sfxEdits, music, musicEdited, ov{sel, area, variant, clip, slot, slotId, cat}, tab`. `snap()` / `restore()` / `persist()` (localStorage key `smb-skin-bench-v1`), undo/redo stacks of snaps.

- **Player:** `S.rig` (YAML, js-yaml from cdnjs) + `S.parts` → `renderPose` → `compute()` → `S.derived.{raw, game, report, tiles}`. Shared 8×8 tiles: the first pose in the rig wins; `report[frame].forced` = the badges.
- **Profile-driven objects:** `SMB_PROFILE` (`nes-sprite-profile/1`): objects with frames as tile tokens (`"7C"`, `"7Ch"`, `"7Cv"`, `"."`), `cols`, optional per-tile palettes (`*` = cycling), clips, `category` (`objects` | `blocks`), per-object `chr_offset`. Palettes are by file offset with optional `count` and `rotate`. `loadProfile` → `S.objs`; painting writes `S.chrEdits[fileOffset]` (8×8 index grids), so shared tiles propagate.
- **Blocks:** 30 metatile-derived objects at BG CHR (`chr_offset` 0x9010). Tile $24 (sky) is locked. Palettes are `{area}.bg0–bg3` and `{area}.sky`, plus `shimmer` (6 colors at 0x9D3; it overwrites bg3 color 1 every 8 frames).
- **Sounds:** SFX are 6502 code with immediates; `SFX_KNOBS` / `SFX_TABLES` with `nz` flags (bytes the code branches on must stay nonzero). Exported as `byte_patches`.
- **Music:** a JS 6502 emulator runs the real SoundEngine ($F2D0), plus a 2A03 synth (`renderApu`). `decodeMusic` → patterns → `compileMusic` (stream sharing, 46 pack orders) into the 1,523-byte region $F90D–$FEFF. Exported as `byte_ranges` + `music.json`.
- **Export:** `downloadProject()` → zip of `parts.png/json`, `rig.yml`, `objects.png/json`, `profile.json`, `config.json`, `music.json`, `smb.nes`, `smb_hacked.nes/.ips`. Each piece is built in `tryPart()`. On failure it still saves, with `backup.json` inside; total failure opens the rescue dialog (`#rescueDlg`: save or copy `smb-skin-backup/1` JSON). **Open project…** accepts zips, backup JSON, or the raw `snap()` JSON.
- **PNG output:** `canvasPng()` uses `toBlob`, falling back to `encodePng()` (stored zlib), because some views return null from `toBlob`. That was the 2026-10-20 download bug.

## ROM facts (SMB World, NROM)

16-byte header, PRG at 0x10, CHR at 0x8010 (sprites) / 0x9010 (BG). File offset = addr − 0x8000 + 0x10. Labels from the Xkeeper0 smb1 disassembly. Key ones: `Palette0_MTiles` $8B10, `Palette3Data` $89D1, `ColorRotatePalette` $89C3, `BackgroundColors` $85CF, `PowerUpGfxTable` $E6BE, SoundEngine $F2D0.

## How it's been verified (keep doing this)

1. Browser zip → `ruby tools/smb_patcher.rb build x/config.json` → `smb_hacked.nes` byte-identical to the browser's.
2. Reopen the downloaded zip → download again → identical zip.
3. Sound/music: page model vs py65 running the real ROM engine, register-for-register.
4. Profile frames vs ROM tables (enemies, power-ups, metatiles).

### Running the checks (`dev/`)

```sh
cd dev && npm install                    # js-yaml for the page's YAML loader
pip install playwright py65 pillow lupa  # lupa only for test_capture.py
export SMB_ROM="/path/to/Super Mario Bros. (World).nes"   # never commit it
./run_all.sh
```

| script | checks |
|---|---|
| `test_bench.py` | player rig, skins, zip round trip, Ruby parity, phone layout |
| `test_objects.py`, `test_powerups.py` | enemy/item frames vs ROM tables, painting, palettes, Ruby parity |
| `test_blocks.py` | metatiles vs ROM, BG palettes/shimmer/sky, Ruby parity, round trip |
| `test_sounds.py`, `test_scope.py` | SFX model vs the real engine (py65, `sfx_truth.py`), scope trace |
| `test_music.py` | page 6502 vs py65 (`music_truth.py`), repack lossless, space meter |
| `test_ipad.py` | the standalone `index.html` at iPad size with touch |
| `test_capture.py` | `tools/sprite_capture.lua` logic (lupa) |
| `sfx_compare.js`, `music_test.js` | node versions of the model-vs-engine checks (`sfx_model.js`, `music_model.js`) |

Each test writes scratch output to `dev/<name>_test/` (ignored by git).

## Recent history

- 2026-10-18: Blocks tab (textures + palettes only, no level layout editing, by request).
- 2026-10-20: downloads broke in the Claude desktop artifact panel ("Cannot read properties of null"). Fixed with the PNG fallback + per-piece export + rescue dialog. Mark's unsaved character (**PIP / PAP**: P1 `02 06 04`, P2 `06 02 04`, fire `15 37 20`, custom big walk 1 pose `back_arm -26, back_leg -23, torso 2, front_leg 27, head 0, front_arm 25`) was rebuilt from screenshots; every frame and badge matched. Saved as `pip_pap_project.zip`.

## Next

- [ ] Mega Man 6 (CHR-RAM; uncompressed graphics in PRG): run `tools/sprite_capture.lua` in MesenCE 2.2.1 → `capture.jsonl`, then write `capture_to_profile.rb`, allow PRG tile offsets (relax the CHR-range check in `import_objects` and the SMB-only ROM validation), and support freely placed sprite frames.
- [ ] Optional: original blank enemy templates; a CLI `skin` subcommand.

Copyright line held throughout: no Nintendo art in the repo, no drawn look-alikes of known characters; all game data is read from the user's ROM.
