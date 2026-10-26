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
- **Mechanics** (`profile.mechanics`, tab `#viewMech`): knobs are `toggle` (hex patches), `percent` (scale ROM bytes `bytes:[{offset,n,mode:mul|div|sqrt,signed,min,max,skip}]` or 16-bit `words:[{lo,hi,mode}]`; `max_value` = set to max) and `number`. `mechPatches()` derives byte edits from the ROM's own values; saved as `config.mechanics` and as `byte_patches` labeled `mechanics` (Ruby applies them; reopen rebuilds from `config.mechanics`). Presets in `mechanics_presets`.
  - SMB: invincible `0x593C` A9 01 EA (InjurePlayer's timer check always "still invincible"); infinite lives `0x11E9` AD 5A 07 (DEC→LDA keeps the BPL); flap `0x34A2` EA EA (mid-air jumps allowed via the swim path); jump = JumpMForceData `0x3434`×5 ÷ factor; gravity = FallMForceData `0x343B`×5; speed = MaxRight/Left `0x3453`/`0x3450`; grip = FrictionData `0x3457`; Bowser HP operand `0x457C`.
  - MM3: invincible = RTS at check_player_hit (`0x380A7`); ammo = weapon_cost `0x3DF2B`×12 → 0; power = 9 damage tables `0x14110` (bank 0A $A100, 256 each, skip 0/$58, max 28); speed = 5 walk sites ($014C) + slide ($0280) in bank 1E; jump = $04E5 at `0x3CEC4/0x3CEC9` (×√h); gravity = `$40` at `0x3C8FA`, `0x3CD5C`, `0x606A` (player only; enemies use $55).
  - MM3 weapons (bank 1E unless noted): per-weapon damage tables (bank 0A: buster $A100, needle $A200, magnet $A300, gemini $A400, hard $A500, top $A600, snake $A700, spark $A800, shadow $A900; Rush uses buster's), `weapon_max_shots` $D33D (slots 1–3, shots spawn top slot down), `weapon_cost` $DF1B, `weapon_fire_sound` $D349, shared launch speed $0400 at init_weapon ($D151/$D156 = $0400), Search Snake $D2BA/$D2BF, $D2C4/$D2C9 + crawl bank 1C $89DC/$89E4, Shadow Blade aimed $D2E2/$D2E7, Gemini bounce bank 1C $88D9/$88E1, Magnet/Hard Knuckle steering ADC #$20 at bank 1C $8857/$8979, enemy target boxes for shots `hitbox_weapon_heights/widths` bank 1F $FC03 (64 bytes). Shot sprites = `weapon_OAM_ID` $D323 + anims in each weapon's main routine, drawn from the weapon's $EB bank (`$A634[w]` in bank 2).
  - Percent knobs compound (`cur()` = earlier knob's result), toggles apply last.
  - Verified in cynes by `dev/test_mechanics.py`: jump px, top speed, accel frames, flap rise, surviving the first goomba / keeping lives, MM3 jump/walk/health/ammo, one-hit tables, Ruby parity + round trip.
- **Start over / Snapshots** (header): `startOver()` clears the current game's edits (SMB also resets to the sample character; Undo restores). Snapshots are `{name, game, when, state: snap()}` in localStorage `rom-studio-snapshots` (max 30); restoring goes through `restoreBackup()`, which switches games if needed; each can be downloaded as a backup JSON that Open project reads.
- **Tile inspector** (right panel, `TZ`): hovering a frame shows a 3×3-tile zoom around that tile; the **Tile** tool (T, default on the Blocks tab) pins it, and painting there calls the same `setObjPixel` as the frames. ◀ ▶ step through a frame's tiles.
- **Export:** `downloadProject()` → zip of `parts.png/json`, `rig.yml`, `objects.png/json`, `profile.json`, `config.json`, `music.json`, `original.nes` (untouched input), `{name}.nes/.ips`. **Download** first asks for a name (`#dlDlg`): it defaults to `S.projectName` (the current snapshot's name, an opened project's `config.name`, or the last download name), else `{game}-hack` (`super-mario-bros-hack`, `mega-man-3-hack`). `fileSafe()` makes it the zip, ROM and IPS base name. Each piece is built in `tryPart()`. On failure it still saves, with `backup.json` inside; total failure opens the rescue dialog (`#rescueDlg`: save or copy `smb-skin-backup/1` JSON). **Open project…** accepts zips, backup JSON, or the raw `snap()` JSON.
- **PNG output:** `canvasPng()` uses `toBlob`, falling back to `encodePng()` (stored zlib), because some views return null from `toBlob`. That was the 2026-10-20 download bug.

## Supported games

`BUILTIN_PROFILES = [SMB_PROFILE, MM3_PROFILE]`. Opening a ROM picks the profile whose `rom.size` + `rom.check` match (asks for a second open if unsaved edits would be cleared). The autosave remembers which game it belongs to (`snap().game`).

### Mega Man 3 (USA), MMC3, 256 KB PRG + 128 KB CHR-ROM

- Sprite renderer at $1FF13B: OAM/anim ID ($05C0,x) → bank $1A (<$80) or $1B, anim ptr lo/hi at $8000/$8080 → `[last, duration, frame ids…]`; frame ptr at $8100/$8200 → `[count|$80 = offsets in bank $14 else $19, offset-table index (+1 when facing flips), (tile, attr)…]`; offsets ptr at $BE00/$BF00 (minus 2) → `(dy, dx)` pairs. Facing = $0580,x bit 6 (EOR attr $40, index +1).
- Sprite CHR: MMC3 R2–R5 from RAM $EA–$ED (1 KB banks at $1000/$1400/$1800/$1C00). $EA = 0, $EB = per-weapon Mega Man bank (`$A634[$A0]`: 1,2,7,3,1,7,1,4,6,2,6,3), $EC = stage bank whose first 32 tiles are shared Mega Man extras (17 banks carry identical copies).
- Profile: one "Mega Man" object, 25 frames from anims $01–$14 as free-placed `sprites: [tile, dx, dy, palette]`, `chr_banks: [0, 1, 0x0A, 0]`, palette 0 = body (`body.N` = `$A641 + 4N` per weapon, `body.0` also mirrored at `$C898+1`), palette 1 = `face` (`$C898+5`). `chr_links` make the per-weapon / per-stage copies follow edits (JS `chrEditsWithLinks()`, Ruby `links` in objects.json).
- Verified: profile frames == the ROM tables; the model matched the running game's OAM (cynes emulator) on 232/260 recorded frames (misses = frame-timing); recolored + repainted build boots to gameplay with the new palette in RAM. `dev/test_mm3.py` (needs `MM3_ROM`, optional `pip install cynes`).
- Weapon index → name (confirmed by Mark in play): 0 Mega Buster, 1 Gemini, 2 Needle, 3 Hard, 4 Magnet, 5 Top, 6 Snake, 7 Rush Coil, 8 Spark, 9 Rush Marine, 10 Shadow, 11 Rush Jet (9 and 11 per the disassembly's Rush checks).
- **Bosses** (8 robot masters): during fights ($5A set, slot ≥ $10) sprite tables come from PRG bank **$15**, not $1A/$1B. Animations = initial OAM ID (`enemy_OAM_ID_g`, bank 0 $A300) + every `LDA #id / JSR reset_sprite_anim` in that boss's code region (banks 06/07). CHR + palettes from the boss room's sprite set.
- **Enemies/items**: stage enemy lists at stage bank $AB00 screen / $AC00 x / $AD00 y / $AE00 global ID. Area k covers `(AA40[k] & $1F) + 1` screens; its sprite set is `AA60[2k]` → bank 1 `$A200[2s]` = ($EC, $ED), sprite palettes 2/3 at `$A030 + 8s`. Names from the disassembly's `sprite_main_ptr_lo` labels; extra animations from each main routine's code (bank $1C/$1D). Same enemy elsewhere with other banks → `chr_alt` links. Checked in cynes: frames ~94% OAM match (rest timing), sprite sets 100%.
- **Blocks**: stage bank layout — screen list `$AA00[i]` → 64-byte screen at `$AF00 + id*64` (row-major 8×8 of 32×32 blocks) → `$B700 + 4*block` (TL, TR, BL, BR metatiles) → metatile tiles `$BB00/$BC00/$BD00/$BE00 + m`, palette+collision `$BF00 + m` (low 2 bits = palette). BG CHR = 2 KB banks `$AA80/$AA81`; BG palettes (area 0) at `$AA82 + 20*AA61`. Each stage object has the stage's first screen and a sheet of every metatile its screens use.
- Not yet: Doc Robot / Wily bosses, weapon-specific Mega Man poses, later-area BG palettes/CHR swaps, sounds/music.

## ROM facts (SMB World, NROM)

16-byte header, PRG at 0x10, CHR at 0x8010 (sprites) / 0x9010 (BG). File offset = addr − 0x8000 + 0x10. Labels from the Xkeeper0 smb1 disassembly. Key ones: `Palette0_MTiles` $8B10, `Palette3Data` $89D1, `ColorRotatePalette` $89C3, `BackgroundColors` $85CF, `PowerUpGfxTable` $E6BE, SoundEngine $F2D0.

## How it's been verified (keep doing this)

1. Browser zip → `ruby tools/smb_patcher.rb build x/config.json` → the `output` ROM byte-identical to the browser's.
2. Reopen the downloaded zip → download again → identical zip.
3. Sound/music: page model vs py65 running the real ROM engine, register-for-register.
4. Profile frames vs ROM tables (enemies, power-ups, metatiles).

### Running the checks (`dev/`)

```sh
cd dev && npm install                    # js-yaml for the page's YAML loader
pip install playwright py65 pillow lupa cynes  # lupa only for test_capture.py; cynes = NES emulator for mechanics/MM3 checks
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

- [ ] MM3: Doc Robot and Wily bosses; per-weapon poses; per-area block palettes.
- [ ] Mega Man 6 (CHR-RAM; uncompressed graphics in PRG): run `tools/sprite_capture.lua` in MesenCE 2.2.1 → `capture.jsonl`, then write `capture_to_profile.rb`, allow PRG tile offsets (relax the CHR-range check in `import_objects` and the SMB-only ROM validation), and support freely placed sprite frames.
- [ ] Optional: original blank enemy templates; a CLI `skin` subcommand.

Copyright line held throughout: no Nintendo art in the repo, no drawn look-alikes of known characters; all game data is read from the user's ROM.
