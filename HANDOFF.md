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

`BUILTIN_PROFILES = [SMB_PROFILE, MM3_PROFILE, SMB2_PROFILE, CONTRA_PROFILE, CV_PROFILE]`. Opening a ROM picks the profile whose `rom.size` + `rom.check` match (asks for a second open if unsaved edits would be cleared). The autosave remembers which game it belongs to (`snap().game`).

### Mega Man 3 (USA), MMC3, 256 KB PRG + 128 KB CHR-ROM

- Sprite renderer at $1FF13B: OAM/anim ID ($05C0,x) → bank $1A (<$80) or $1B, anim ptr lo/hi at $8000/$8080 → `[last, duration, frame ids…]`; frame ptr at $8100/$8200 → `[count|$80 = offsets in bank $14 else $19, offset-table index (+1 when facing flips), (tile, attr)…]`; offsets ptr at $BE00/$BF00 (minus 2) → `(dy, dx)` pairs. Facing = $0580,x bit 6 (EOR attr $40, index +1).
- Sprite CHR: MMC3 R2–R5 from RAM $EA–$ED (1 KB banks at $1000/$1400/$1800/$1C00). $EA = 0, $EB = per-weapon Mega Man bank (`$A634[$A0]`: 1,2,7,3,1,7,1,4,6,2,6,3), $EC = stage bank whose first 32 tiles are shared Mega Man extras (17 banks carry identical copies).
- Profile: one "Mega Man" object, 25 frames from anims $01–$14 as free-placed `sprites: [tile, dx, dy, palette]`, `chr_banks: [0, 1, 0x0A, 0]`, palette 0 = body (`body.N` = `$A641 + 4N` per weapon, `body.0` also mirrored at `$C898+1`), palette 1 = `face` (`$C898+5`). `chr_links` make the per-weapon / per-stage copies follow edits (JS `chrEditsWithLinks()`, Ruby `links` in objects.json).
- **Copy colors:** an object can list `color_match: [{label, palette}]`. The palette panel then shows a "Copy colors from …" button that copies that palette into the object's own (`renderColorMatch`). MM3 pairs each weapon's `body.N` with its boss's `set.XX.2` both ways; Top Man copies `body.5` (Top Spin has no shot object). Weapon and boss colors are separate in the ROM, so copying is the only link between them.
- Verified: profile frames == the ROM tables; the model matched the running game's OAM (cynes emulator) on 232/260 recorded frames (misses = frame-timing); recolored + repainted build boots to gameplay with the new palette in RAM. `dev/test_mm3.py` (needs `MM3_ROM`, optional `pip install cynes`).
- Weapon index → name (confirmed by Mark in play): 0 Mega Buster, 1 Gemini, 2 Needle, 3 Hard, 4 Magnet, 5 Top, 6 Snake, 7 Rush Coil, 8 Spark, 9 Rush Marine, 10 Shadow, 11 Rush Jet (9 and 11 per the disassembly's Rush checks).
- **Bosses** (8 robot masters): during fights ($5A set, slot ≥ $10) sprite tables come from PRG bank **$15**, not $1A/$1B. Animations = initial OAM ID (`enemy_OAM_ID_g`, bank 0 $A300) + every `LDA #id / JSR reset_sprite_anim` in that boss's code region (banks 06/07). CHR + palettes from the boss room's sprite set.
- **Enemies/items**: stage enemy lists at stage bank $AB00 screen / $AC00 x / $AD00 y / $AE00 global ID. Area k covers `(AA40[k] & $1F) + 1` screens; its sprite set is `AA60[2k]` → bank 1 `$A200[2s]` = ($EC, $ED), sprite palettes 2/3 at `$A030 + 8s`. Names from the disassembly's `sprite_main_ptr_lo` labels; extra animations from each main routine's code (bank $1C/$1D). Same enemy elsewhere with other banks → `chr_alt` links. Checked in cynes: frames ~94% OAM match (rest timing), sprite sets 100%.
- **Blocks**: stage bank layout — screen list `$AA00[i]` → 64-byte screen at `$AF00 + id*64` (row-major 8×8 of 32×32 blocks) → `$B700 + 4*block` (TL, TR, BL, BR metatiles) → metatile tiles `$BB00/$BC00/$BD00/$BE00 + m`, palette+collision `$BF00 + m` (low 2 bits = palette). BG CHR = 2 KB banks `$AA80/$AA81`; BG palettes (area 0) at `$AA82 + 20*AA61`. Each stage object has the stage's first screen and a sheet of every metatile its screens use.
- Not yet: Doc Robot / Wily bosses, weapon-specific Mega Man poses, later-area BG palettes/CHR swaps, sounds/music.

- **Start powered up:** SMB `start` is a `choice` knob with no `offset`; each option carries `patches` (applied with the toggles). Big/Fire rewrite PrimaryGameSetup ($9061: `LDA #st; STA PlayerStatus; STA FetchNewGameTimerFlag`, size is already 0 = big from the memory clear) and ContinueGame ($9267: `LDX #st; STX PlayerStatus … STA PlayerSize` with A=0), so every life starts that way. MM3 `allweapons` replaces the new-game `LDA #$9C; STA $A9` (Rush Coil) at $1EC8F7 with `JSR $CCED`, the game's own unused routine that fills $A2–$AD with $9C. The lives byte at $C8FC stays put.

- **Air jumps** (`airjump` choice, both games; replaces SMB's old `flap` toggle, which `legacy` maps to 2). Free space was the hard part:
  - SMB Double: ProcJumping ($B48B–$B49F) is rewritten in place. The on-ground check is dropped, the swim rules are kept, and non-swimming jumps `JSR $92AA`. That is the residual DoNothing1, now `LDA $EE; INC $EE; LSR A; RTS`, which allows a jump while $EE < 2. Landing calls `JSR $F2CA` (6 unused bytes before SoundEngine) in place of `STA StompChainCounter`, which does that store plus `STA $EE`. It runs on every grounded frame. RAM $EE is otherwise unused. The ground jump counts as 1, so walking off a ledge gives 2 air jumps. Unlimited = the old flap NOPs.
  - MM3: the air state's `JSR $D355` at $D0CC becomes `JSR $F0D9` (the space of a controller-2 debug pit bounce, disabled at $F0BE). On a new A press with $7F == 0 it sets `$7F` and jumps to $CEC0 (the space of the controller-2 debug super jump), which loads the speed from the normal jump's own operands ($CEB4/$CEB9), so it follows Jump height. The state-0 pointer ($CD9A/$CDB0) goes to a wrapper at $F0E9, `STY $7F; JMP $CE36` (Y = state = 0), to reset on the ground. The jump entry $CEAD clears bit 7 of $14 (`ASL $14; LSR $14`), so the ground-jump frame can't also air-jump. Unlimited skips the `INC $7F`.

## Super Mario Bros. 2 (USA, Rev 1 / PRG1)

`SMB2_PROFILE`: MMC3, 128 KB PRG + 128 KB CHR (262,160 bytes). It's built by `dev/gen_smb2/` from the Xkeeper0/smb2 disassembly, which rebuilds PRG1 byte for byte. PRG0 differs in 8,000+ bytes, so detection checks a PRG1-only byte run, and PRG0 is unsupported for now.

- **8×16 sprites.** A tile index N draws N on top and N+1 below. Odd N reads from the background pattern table. The profile spells a sprite as two 8×8 tokens, with odd-table tiles written as `100`–`1FF` (TOK now takes 3 hex digits). `chr_banks` has 8 entries covering $0000–$1FFF:
  - SpriteCHR1: the character bank, chosen by `CHRBank_CharacterSize`.
  - CHR2/3: common enemies, $08/$09.
  - CHR4: world enemies, from `CHRBank_WorldEnemies`.
  - BG1: world background, a 2 KB bank.
  - BG2: Animated1 ($18), a 2 KB bank.
- **Players.** 4 characters × big/small × 11 frames from `CharacterTiles_Walk1`, each a 2×2 grid of 8×16 sprites plus an "eyes" sprite in palette 1 (`CharacterEyeTiles`).
  - CurrentCharacter order is Mario 0, Princess 1, Toad 2, Luigi 3. The disassembly's eye comments swap Luigi and the Princess.
  - The eyes live in the animated BG banks, and `chr_links` keep all 8 copies in step.
  - Checked against live OAM over about 6,300 frames; the only mismatches were screen-edge wrap.
- **Enemies and items.** `EnemyTilemap1/2` groups. Size comes from `ObjectAttributeTable` (16x32, Horizontal, Mirrored). Palettes come from the types whose `EnemyAnimationTable` offset falls in the group. Birdo's are pink 3, red 1 and gray 2 (`Enemy_Birdo_Attributes`). The rocket is drawn by hand as 32×32, as `RenderSprite_Rocket` does.
- **Areas.** World 1–7, using each world's overworld sprite palettes (`World{n}SpritePalettes` + 1). The sky is the day background color. The underground and boss sets aren't exposed yet.
- **Next:** bosses (Mouser, Tryclyde, Fryguy, Clawgrip, Wart, Hawkmouth boss; these use tilemap 2 and `BossTileset` BG banks), blocks, mechanics, character-select sprites.

## Contra (USA)

`CONTRA_PROFILE`: UNROM, 128 KB PRG, **CHR-RAM**. It's built by `dev/gen_contra/` from the vermiceli/nes-contra-us disassembly, which rebuilds the ROM byte for byte with cc65.

- **Compressed graphics (`profile.chr_ram`).** All art is RLE in `graphic_data_xx` blocks, unpacked into the PPU per level.
  - **Virtual offsets.** The app decodes each block (`gfxDecode`, mirroring `write_graphic_data_to_ppu`) and gives its tiles virtual offsets: `vbase (0x1000000) + block * 0x2000 + PPU address`. `srcTile()` reads them; `chrEdits` key on them like any tile.
  - **Mapping objects to tiles.** An object's `chr_area` names a per-level PPU map (runs of `[tile, count, offset]`), so tokens resolve to virtual or raw offsets. The boss areas (`L1b` etc.) include the uncompressed `alt_graphic_data` tiles in bank 2, which are plain offsets.
  - **Build.** Only edited blocks are re-encoded (`gfxEncode`: greedy, runs of 3+). A block that fits goes back in place. Otherwise it moves to its bank's free tail (`free`: bank 2 707, bank 4 575, bank 5 2508, bank 6 730 bytes), and `graphic_data_ptr_tbl` is repointed. Block 0a carries `aliases: [0x10]` + `prefix`, because 10 reads 0a's data flipped from 2 bytes earlier.
  - **Ruby.** `SMB.gfx_decode/gfx_encode`, `Rom#tile_bytes/set_tile_bytes/pack_chr_ram!`, byte-identical to JS. The encoder reproduces every original block at its original size.
- **Palettes.** `gp.XX` are `game_palettes` entries. `L1.0`–`L1.3` (sprite) and `L1.bg0`–`L1.bg3` (background) are `same_as` aliases from each level header, so editing a shared palette edits it everywhere. `palIdFor`/`palRef` follow aliases, and the load/build/export loops skip them. Per-tile numeric and area-relative palettes now appear as editable rows.
- **Sprites.** 35 objects from `sprite_ptr_tbl_0/1` (players outdoor and base, bullets, falcons, explosions, soldiers, level enemies, bosses, ending). Bill uses sprite palettes 0 + 1; Lance is the same tiles all in palette 1 (`sprite_attr_start_tbl` $05).
- **Blocks.** Per level: first screen, a tile sheet, and a boss-area screen drawn with the alt graphics. Indoor levels use a flipped copy of block 0a (block 10); the generator adds `h` to those tokens.

- **Contra mechanics.** Checked by `dev/test_contra_mech.py` in cynes.
  - **Invincible:** `@collide_with_enemy`'s `LDA NEW_LIFE_INVINCIBILITY_TIMER,x` becomes `LDA #1`. Weapon pickups and platforms run before it; pits still kill.
  - **Lives:** infinite lives turns `DEC P1_NUM_LIVES,x` into `LDA`. Extra lives at the start is the immediate in `init_player_lives`.
  - **Starting weapon:** `player_state_routine_00` calls a routine at `$F612` (unused bank-7 space), which gives the chosen weapon when a life starts with the normal gun. Keep-weapon turns the `STA` in `init_player_and_weapon` into an `LDA`.
  - **Jump height:** the signed 16-bit Y velocities (the engine's `words` now take `signed`).
  - **Gravity:** the `apply_gravity` `ADC #$23`.
  - **Run speed:** the ±1 X velocities.
  - **Air jumps:** `@player_jump_check`'s `JMP handle_jump` goes through `$F620`. A new A press re-runs `set_jump_status_and_y_velocity`, and bit 3 of `PLAYER_JUMP_STATUS` marks a used double jump (the game doesn't use bits 1–3, and landing clears the byte).

## Castlevania (USA) (Rev 1)

`CV_PROFILE`: UNROM, 128 KB PRG, **CHR-RAM**, but unlike Contra the art is stored **raw** in PRG. There's no public disassembly, so `dev/gen_castlevania/` works from the ROM plus the cynes emulator.

- **Graphics sets.** The loader at `$FD23` (fixed bank) copies "sets" from `$FDBB`. A set is a list of `bank, CPU source, PPU address, length` records, ending with `$FF`. `$C8B0` gives the set for each stage (0–18). Each block's PPU contents are set 3 (Simon, common sprites, the status bar font) overlaid with its own set. These were checked against the game's CHR-RAM in cynes save states (CHR-RAM sits at offset 11234, nametable 0 just before it).
  - The profile uses `chr_ram` with no compressed `blocks`. `areas` map each block's tiles straight to file offsets, so edits are plain tile writes, and Ruby needs nothing new.
  - `chr_link_sets` carry an edit to identical tiles at the same PPU address in the title, intro, map and ending sets.
- **Sprites.** The drawer at `$80D6` (bank 0) reads pointer tables `$8FBE` (codes 00–7F) and `$90BE` (80–FF).
  - Each entry is a count, then parts. A part is a Y byte (signed Y = byte >> 1; bit 0 = reuse the previous attribute), a tile, an optional attribute, and X.
  - `$80 lo hi` jumps into a shared list and `$81` returns. Sprites are 8×16 (PPUCTRL `$B0`).
  - Many codes are different enemies in different blocks, because the block's set decides the tiles. Each object names its block (`B1`–`B7`). They were picked by rendering every code in every block and by logging codes the game draws (`$031C,x`) while walking each stage (`explore.py`).
- **Palettes.**
  - Sprite palettes (`spr.0`–`spr.3`) are VRAM string 6 (`$CCF9` table), shared by every stage. The `B1.0`… entries are aliases of them.
  - Background palettes come per block from string `$FB9B[stage]`.
- **Blocks.** Each stage's first screen comes from nametable 0 after warping there, plus a tile sheet per block.
  - The warp: set `$28`/`$29` to the stage, game state `$18 = $0C`, step `$19 = 5`. That's the restart path that runs the set load.
- **Mechanics** (`mech.py`, checked by `dev/test_castlevania_mech.py`):
  - **Invincible:** `SBC $4B` in the damage routine becomes `SBC #0`, so knockback still happens.
  - **Infinite lives:** `DEC $2A` becomes `LDA`.
  - **Lives at the start:** the two `LDA #4 / STA $2A`. Number knobs now take `also` (more offsets) and `bias` (the byte = the shown number + bias).
  - **Hearts:** infinite hearts NOPs the two `DEY`s on `$71`, and the stopwatch's `SBC #5` becomes `SBC #0`. The start amount is the `LDX #5` that refills hearts each life.
  - **Starting kit:** subweapon (`$015B`: 08 dagger, 09 cross, 0A stopwatch, 0B holy water, 0D axe), shots (`$64`) and whip (`$70`).
    - All three share a hook at `$BA40` (bank 6 free space), called from the three `LDA #0 / STA $015B / STA $64` resets and the whip reset on death. The new-game `STX $70` is NOPed.
    - Choice/number knobs with `install` write the hook first, then their value byte.
  - **Damage:** the immediates 8/12/16 in the damage routine.
  - **Jump height:** the jump table at `$9B90`, signed. The walker plays it forward, then mirrored for the fall. `$F8` means "hold" and `$80`/`$81` are markers, so the most per frame is 7.
  - **Air jumps:** the jump state's `LDA #0 / JSR $9B1E` goes through `$BA60`. It clears a counter at `$07E0` (unreferenced RAM) on a jump's first frame. A new A press restarts the table going up.

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

Other games: `MM3_ROM`, `SMB2_ROM`, `CONTRA_ROM` and `CV_ROM` add `test_mm3`…, `test_smb2`, `test_contra(_mech)` and `test_castlevania(_mech)`.

Each test writes scratch output to `dev/<name>_test/` (ignored by git).

## Recent history

- 2026-10-18: Blocks tab (textures + palettes only, no level layout editing, by request).
- 2026-10-20: downloads broke in the Claude desktop artifact panel ("Cannot read properties of null"). Fixed with the PNG fallback + per-piece export + rescue dialog. Mark's unsaved character (**PIP / PAP**: P1 `02 06 04`, P2 `06 02 04`, fire `15 37 20`, custom big walk 1 pose `back_arm -26, back_leg -23, torso 2, front_leg 27, head 0, front_arm 25`) was rebuilt from screenshots; every frame and badge matched. Saved as `pip_pap_project.zip`.

## Next

- [ ] MM3: Doc Robot and Wily bosses; per-weapon poses; per-area block palettes.
- [ ] Mega Man 6 (CHR-RAM; uncompressed graphics in PRG): run `tools/sprite_capture.lua` in MesenCE 2.2.1 → `capture.jsonl`, then write `capture_to_profile.rb`, allow PRG tile offsets (relax the CHR-range check in `import_objects` and the SMB-only ROM validation), and support freely placed sprite frames.
- [ ] Optional: original blank enemy templates; a CLI `skin` subcommand.

Copyright line held throughout: no Nintendo art in the repo, no drawn look-alikes of known characters; all game data is read from the user's ROM.
