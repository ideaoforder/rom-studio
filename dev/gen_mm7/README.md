# Mega Man 7 profile generator

Rebuilds `snes/profiles/mm7.js` from your own ROM: Mega Man 7 (USA), 2,097,152 bytes, HiROM, CRC32 `2D947536`. There's no public disassembly or RAM map, so everything here was found by reading the ROM and watching the game in stable-retro. Nothing from the game is committed.

```sh
pip install stable-retro
export MM7_ROM="/path/to/Mega Man 7 (USA).sfc"
python3 capture_player.py /tmp/mm7_player.json   # Mega Man's poses on flat ground
python3 capture_stages.py /tmp/mm7_stages.json   # the 8 stages (a few minutes)
python3 build_profile.py                          # -> ../../snes/profiles/mm7.js
```

What's known:

- **Graphics sets.** A table at file `$E993` has 184 × 5 bytes: a 24-bit address (`$C0:xxxx`) and the unpacked size. The sets sit back to back from `$0E2700` to `$1888F6`, packed with Capcom's LZ (`snes/lib/clz.js`; the format is shared with Rockman & Forte and Mega Man X2/X3). Mega Man's own tiles are uncompressed in bank `$19` and are streamed into VRAM per pose; the profile edits them in place (`codec: raw`).
- **RAM:**
  - The OAM buffer is at `$0700`, with the size and X-high bits at `$0900`.
  - The camera is at `$00D8`/`$00DA`.
  - Mega Man's object is at `$0C00` (+5 X, +8 Y, +`$1A` Y speed, +`$2E` energy, mirrored at `$0BD1`).
  - Objects are 32-byte slots from `$0E00`, with +0 = 1 when live, +5/+8 the position, and +`$0A` the type. Type `$04` is Mega Man's shots.
  - Lives are at `$0B81`.
  - Weapon energy is at `$0B83 + 2·n` (bit 7 = owned): 1 Freeze, 2 Thunder Bolt, 3 Junk Shield, 4 Scorch Wheel, 5 Slash Claw, 6 Noise Crush, 7 Danger Wrap, 8 Wild Coil, 10 Rush Search, 11 Rush Jet, 12 Rush Coil, 14 Super Adaptor. The current weapon is at `$0B73`.
  - Tanks are at `$0BA0` (E), `$0BA1` (W) and `$0BA2` (S). Items are bits of `$0BA4`: R/U/S/H plates `$01`–`$08`, Exit `$20`, Beat `$40`, Energy Balancer `$80`. Bolts are a word at `$0BA6`.
  - Mega Man's state is at `$0C02` (0 stand, 6 jump, 8 fall, 10 land) and his substate at `$0C03`. Buttons held are at `$0C41` and new presses at `$0C45`.
  - The password digits are at `$1DF2` (16 bytes).
  - In VRAM, sprite tiles start at `$C000` and the BG tilemaps are at `$A800` (front) and `$B800` (back).
- **Reaching the stages:** `capture.stage_select()` boots through the title to the password screen, writes a published all-masters password straight into `$1DF2`, and confirms it. Stages are picked with the d-pad.
- **Frames:** while Mega Man flies right (no clipping, can't be hurt), OAM is split into runs and each entry goes to the nearest live object. Tiles are mapped back to (set, tile) or (bank, tile) by matching VRAM bytes.
- **Palettes:** each CGRAM row the frames use is searched for in the ROM: the whole row, else halves, else quarters. What isn't found is shown but can't be edited.
- `mech.py`:
  - **Invincible:** the four `SBC` in Mega Man's damage code become `SBC #0`.
  - **Infinite lives:** `DEC $0B81` becomes `LDA`.
  - **Lives at the start:** the three `LDA #2 / STA $0B81`.

Not done yet:

- **Boss fights.** The robot masters come from their stage-intro poses (`capture_bosses.py`). A stage counts as beaten when its weapon is owned *and* `$0B7C` is set, so clearing both while a published password loads replays the intro. The fights themselves aren't captured, because rooms lock the camera and flying right doesn't reach them. Bass, Wily and the fortress bosses aren't captured either.
- **Enemy names.** Enemies are labelled by stage and object type.
- **Per-weapon colours for Mega Man.** The menu cursor isn't found yet.
- **Weapon energy.** The code that spends it hasn't been found yet.

Checks: `dev/test_mm7.py` (codec parity, edits → download → Ruby parity → reopen, a forced repack, and booting both builds) and `dev/test_mm7_mech.py`.
