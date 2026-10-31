# ROM Studio

A browser workbench for reskinning NES games. **Super Mario Bros.**: the player, enemies and items, blocks, sound effects and music. **Mega Man 3**: Mega Man (25 frames, palettes per weapon), Rush (Coil, Marine and Jet), the 8 robot masters, 64 enemies, item pickups, and each stage's blocks.

**Mechanics** (both games): invincibility, jump height, gravity, speed, and more. SMB adds grip (ice physics), flap-to-fly, infinite lives and Bowser's health. Mega Man 3 adds infinite weapon energy and weapon power.

**Open it:** https://ideaoforder.github.io/rom-studio/ (works on iPad, too).

Bring your own ROM: open a legally dumped *Super Mario Bros. (World)* or *Mega Man 3 (USA)* `.nes` file; the page picks the game from the ROM. Nothing from the game is included here; all art, sounds and music are read from the ROM you open, and it never leaves your browser.

The command-line tools in `tools/` (Ruby, stdlib only) rebuild the same ROM from a downloaded project zip. Run them from inside `tools/`.

---


## Supported games

Open one of these with **Open ROM…** and ROM Studio switches to that game (the **Games** button lists them too). You bring the ROM; nothing from the games is in this repo. Fingerprints are of the ROM without its 16-byte iNES header, as No-Intro lists them.

| Game | ROM | Size | CRC32 | What you can edit |
|---|---|---|---|---|
| Super Mario Bros. | Super Mario Bros. (World) | 40,976 | `D445F698` | player rig, enemies & items, blocks, sounds, music, mechanics |
| Mega Man 3 | Mega Man 3 (USA) | 393,232 | `603AAA57` | Mega Man & weapons, Rush, bosses, enemies, items, blocks, mechanics |
| Super Mario Bros. 2 | Super Mario Bros. 2 (USA) (Rev 1) | 262,160 | `CA594ACE` | the four players (big & small), enemies, items, bosses, every world's blocks, mechanics |
| Contra | Contra (USA) | 131,088 | `F6035030` | Bill & Lance, weapons, enemies, bosses, all 8 levels' blocks, mechanics |
| Castlevania | Castlevania (USA) (Rev 1) | 131,088 | `B668C7FC` | Simon, whip & subweapons, items, enemies, bosses, every stage's background, mechanics |

Another revision or region of the same game has its code in different places, so it won't open until it has its own profile (for example the first release of SMB2, Rev 0).

## Workflow

```sh
ruby smb_patcher.rb dump  smb.nes work      # once
# paint work/parts.png, tweak work/rig.yml and work/config.json
ruby smb_patcher.rb pose  work/config.json  # fast: just re-render frames.png
ruby smb_patcher.rb build work/config.json  # pose + ROM + IPS + preview
```

```
parts.png + rig.yml  --pose-->  frames.png  --build-->  .nes / .ips / .chr / preview.png
```

## What you paint: parts.png

Eight boxes, starting as a plain mannequin:

| part | size | used for |
|---|---|---|
| `head` | 8×8, facing right | every side-view frame, big and small |
| `head_front` | 8×8, facing you | small "killed" frame |
| `torso`, `arm`, `leg` | 4×12 each | big frames |
| `s_torso`, `s_arm`, `s_leg` | 4×4, 2×4, 4×4 | small frames |

Index 0 (sky) is transparent; draw with colors 1–3. Arms and legs hang **straight down** with the joint at the top; the rig rotates them.

Change a size in `rig.yml`, then run `parts` — the sheet is re-laid-out and existing art is kept (cropped if it shrank). Run `parts` after changing palettes too, to recolor the sheet.

## How it's posed: rig.yml

- **parts** — size and pivot (the joint) of each part.
- **skeletons** — which part each bone uses and where its joint sits in the 16×32 frame. Small characters live in the bottom half. Bones draw in list order (later = in front).
- **poses** — one per game frame. `front_arm: 30` rotates that bone 30°; **positive swings forward**. Override any bone field: `at`, `part`, `rot`, `flip`, `hide`, `remap: {3: 1}`. `offset: [dx, dy]` shifts the whole body. `like: big walk 2` copies another pose so you only list what differs.

Comments at the top of the generated `rig.yml` cover the same ground.

### Shared tiles (the one thing to understand)

The game assembles frames from a pool of 8×8 tiles, and many frames share tiles. The default rig groups poses into the families Nintendo designed:

- **fire throw / swim 1 / swim kick / climb 1** share everything above the knees
- **walk 2 / swim 2 / swim 3 / climb 2** share the head and shoulders (climb 2 shares down to the waist)

The **first pose in the file wins** a shared tile. `pose` prints how many pixels each frame lost and to whom; `posed_raw.png` shows what the rig drew before that, `frames.png` shows what the game will actually show.

Known quirk: **big standing**'s waist row is a single tile drawn twice side by side (not mirrored), so anything off-center there gets copied 8px to the right.

Some rows are mirrored by the game (bottom of standing, crouch, growing; both halves of "killed") — only the left half counts there.

## config.json

```json
{
  "input": "../smb.nes",
  "output": "smb_hacked.nes",
  "ips": "smb_hacked.ips",
  "chr": "smb_hacked.chr",
  "rig": "rig.yml",
  "frames": "frames.png",
  "palettes": { "player1": ["16", "27", "18"], "player2": ["30", "27", "19"], "fire": ["37", "27", "16"] },
  "names": { "player1": "MARIO", "player2": "LUIGI" }
}
```

- `ips` — a shareable patch (only what you changed). `chr` — optional raw 8 KB CHR for other tools.
- Palette slots match drawing colors 1, 2, 3. Pick from `nes_colors.png`; avoid `0D`. **fire** is shared by both players.
- Names: up to 5 letters/digits/spaces; patched into the HUD, 2-player screens, and "THANK YOU ___!".

### Hand-finishing frames

Want to touch up individual frames by hand? Run `pose` one last time, delete `"rig"` from `config.json`, then edit `frames.png` directly — `build` imports it as-is (and refuses if two copies of a shared tile disagree). Without `"rig"`, dump → build with no edits is byte-identical to the input.

## Enemies & items (objects.png + profile.json)

Projects downloaded from the Skin Bench can also contain:

| file | what it is |
|---|---|
| `objects.png` / `objects.json` | Repainted enemies, fireballs, and other items. For each 8×8 slot, the json records the CHR file offset and the flips the game draws it with. `build` imports it generically: it un-flips each slot, writes the tile, and stops if two copies of a shared tile disagree. Slots set to `null` are left alone. |
| `profile.json` | The game profile the bench used. The CLI ignores it. |

`config.json` also gets `"objects"` and `"sprite_palettes"`. Each sprite palette entry is written by byte offset (`{"ground.3": {"offset": 3320, "colors": ["0F","36","17"]}}`), so the CLI needs no game-specific code for it.

### Game profiles

Everything game-specific about objects lives in a profile, so the same tooling can target other games:

```json
{
  "format": "nes-sprite-profile/1",
  "game": "Super Mario Bros. (World)",
  "rom": { "size": 40976, "chr_offset": 32784, "check": [[28183, "2028C81800405058"]] },
  "areas": { "ground": { "label": "Overworld", "sky": "22" } },
  "palettes": { "ground.3": { "offset": 3320 } },
  "objects": [
    { "name": "Goomba", "palette": [3], "home": "ground",
      "frames": { "walk": { "cols": 2, "tiles": "70 71 72 73" }, "flat": { "cols": 2, "tiles": "EFv EFhv" } },
      "clips": { "walk": [["walk", 8], ["walk", 8, "m"]] } }
  ]
}
```

- **Tiles** are hex indices relative to `chr_offset` (an object can set its own `chr_offset` for another bank). Add `h` and/or `v` for flips, or use `.` for an empty slot.
- **Clips** are `[frame, frames-to-show, flags]`: `m` mirrors the whole frame left/right, `v` flips it upside down, and a frame of `null` shows nothing.
- **Palettes:** a number means a palette slot for the current area (so `3` resolves to `ground.3`), and a string names a palette directly.
- **`"player": "smb"`** turns on the Steve/Alex rig. It's SMB-only today. Leave it out and the bench shows only Enemies & items for that game.

Open a `profile.json` with **Open project…** to switch games.

## Blocks (background art + palettes)

The **Blocks** tab repaints the level art: ground, bricks, ? blocks, coins, pipes, clouds, hills, bushes, castles, the flagpole, bridges, water/lava, coral and more (30 in all). It changes only how things look; level layouts are untouched.

- Blocks are built from SMB's metatile table (each 16×16 block is four 8×8 background tiles), so painting a tile updates every block that shares it. Bricks and castles share tiles, for example, and the editor says so.
- Tile `$24` is the empty-sky tile used all over every level, so it's locked.
- **Palettes:** each area (overworld, underground, castle, underwater) has its own background palettes, so the same brick art can be brown outdoors and blue underground. Use the area buttons to see and edit each one.
- **Shimmer:** the ? block and coin palette's first color is overwritten by the game every 8 frames from a 6-color cycle. That slot is locked and shown as ✶. Edit the **Shimmer** row instead; it applies in every level.
- **Sky:** each area's background color. It shows wherever your art uses color 0.

It all exports through the same files: block tiles go in `objects.png`/`objects.json` (as background CHR offsets), and palettes in `sprite_palettes` (sky entries are 1 color, shimmer is 6).

## Sound effects (byte_patches)

The Skin Bench's **Sounds** tab retunes SMB's 18 sound effects: jump, fireball, stomp, kick, bump, coin, power-up appears, power-up grab, 1-up, pipe/ouch, brick break, flagpole, fireworks, vine, timer tick, Bowser falls, Bowser flame.

Sound effects are small routines that feed the NES sound chip. What you can change is the values inside them:

- starting pitch
- tone (pulse width) and volume or fade
- pitch slides
- length and the timing of each part
- the note and volume tables some effects step through

Each effect keeps its basic shape. Some values are shared between effects (Fireball and Bump use the same pitch and tone, for example), and the editor shows which.

Edits are saved in `config.json` as:

```json
"byte_patches": [{ "label": "jump.small", "offset": 29662, "value": "1E", "nonzero": false }]
```

`build` writes each byte at its file offset. `nonzero: true` marks bytes the game's code branches on; writing `00` there would make the CPU fall into the next routine, so `build` refuses it.

The browser preview models each routine frame by frame. It was checked against SMB's real sound code running on a 6502 emulator, on the stock ROM and with 40 sets of random edits: the register writes were identical.

## Music (byte_ranges + music.json)

The **Music** tab edits all 12 songs: overworld, underground, underwater, castle, Starman, pipe intro, lose a life, game over, princess saved, castle clear, level clear, hurry up.

Each song is made of parts. A part has a tempo row and four rows of notes:

| row | channel |
|---|---|
| Melody | square 2 |
| Harmony | square 1; can be turned off |
| Bass | triangle; its own notes, a copy of the melody, or off |
| Drums | noise; a loop, only in songs the game gives drums |

The overworld is a 33-slot playlist of parts, editable under "Overworld arrangement".

**Space is the real limit.** All songs share one 1,523-byte region. The editor repacks everything on every change (Nintendo-style stream sharing; the stock songs pack into 1,506 bytes) and shows a meter. Over budget, downloads are blocked until you shorten a song, turn off a harmony row, or silence a song.

**Exports:**
- `music.json`: the editable patterns. Re-opening a project uses it.
- `config.json` `"byte_ranges"`: the repacked region as hex. `build` writes it by offset with bounds checks.

**Preview:** the browser runs SMB's real sound routine on a small 6502 emulator against the compiled bytes, so playback is exact. That emulator matches py65 register-for-register. Decoding the stock songs and repacking them plays identically through the real engine (all 12 songs; Overworld, Underwater, Starman and Princess saved checked for 3m20s).

## Limits

- Player 1 and 2 share every tile; they differ only by palette.
- 3 colors + transparent per character.
- Frame sizes are fixed: small 16×16, big 16×32.
