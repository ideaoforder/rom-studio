# Adding a game

ROM Studio supports a game through a **profile**: a JSON description of where the game keeps its art, colours and rules. Everything else is shared. A profile holds only offsets, tile numbers and labels. It never holds the game's bytes. The page reads those from the ROM the player opens.

## Ground rules

- **Never commit anything from a game.** That means no ROMs (`*.nes`, `*.sfc`, `*.smc`), no graphics, music or decoded data, and no disassembly. `.gitignore` covers the usual files. Generators read *your* ROM at build time (an env var such as `SMW_ROM`). If you used a public disassembly, link to it from your generator's README.
- **Fingerprint one exact ROM.** Give the size plus a few `check` byte runs that only that revision has. Another revision or region gets its own profile.
- **Prove it in an emulator.** Every supported game has a test that builds through the browser, checks that the Ruby CLI makes the same bytes, reopens the project, then boots the built ROM and confirms that the edits reach the running game.

## Where things live

```
index.html              NES editor (one page; NES profiles are inline consts, written by dev/gen_<game>/build_profile.py)
snes/index.html         SNES editor: markup
snes/app.js             SNES editor: UI and state (tiles, colours, mechanics)
snes/lib/*.js           SNES formats: lz2.js (Nintendo LZ2), tiles.js (planar 2/3/4/8 bpp), color.js (BGR555), rom.js (LoROM, build)
snes/profiles/<game>.js one file per SNES game: window.SNES_PROFILES.push({...})
lib/files.js            zip/unzip, IPS, CRC32, PNG (shared)
lib/mechanics.js        mechanics knobs -> byte patches (shared)
tools/smb_patcher.rb    NES command-line build (byte-identical to the NES page)
tools/snes_build.rb     SNES command-line build (byte-identical to the SNES page)
dev/gen_<game>/         a generator per game: reads your ROM (+ emulator captures), writes the profile
dev/snes/               SNES dev helpers: emu.py (stable-retro), lz2.py, tiles.py, render.py
dev/test_<game>*.py     checks (dev/run_all.sh runs them for every ROM you've set)
```

## SNES profiles (`snes-profile/1`)

```js
window.SNES_PROFILES.push({
  format: "snes-profile/1", id: "smw", game: "Super Mario World (USA)",
  rom: { size: 524288, map: "lorom", checksum: 0x7FDC,           // file offset of the header checksum complement (optional)
         check: [[0x7FC0, "5355504552..."], ...] },               // [file offset, hex] runs that must match
  gfx: { codec: "lz2",                                            // "lz2" (big-endian copy offsets) or "lz1" (little-endian)
         region: [0x40000, 0x5FD0D],                              // where the files may be repacked
         files: [{ id: "GFX32", bpp: 4, at: 0x40000,              // file offset of the compressed data
                   ptrs: [[0x38D8, "word"], ...],                  // where the game keeps its address: lo | hi | bank | word | long
                   max_end: 0x47FFF }, ...] },                     // optional: must end before this offset
  palettes: [{ label: "Mario", colors: [null, 0x2BFA, ...],       // per colour index: the ROM offset it's loaded from (null = set by code)
               seen: [null, null, ...] }],                         // for null entries: the colour the game showed (display only)
  objects: [{ name: "Mario (small)", group: "Mario & Luigi", category: "sprites" /* or "blocks" */,
              frames: [{ name: "pose 00", bg: "7FDD",              // backdrop colour (BGR555 hex)
                         w: 256, h: 224,                           // optional fixed size (screens); otherwise the parts' bounds
                         parts: [[fileIndex, tile, x, y, paletteIndex, flags]] }] }],   // flags: 1 h-flip, 2 v-flip, 4 colours 8-15
  mechanics: [...], mechanics_presets: { "Easy": { ... } },
});
```

- **Parts are 8×8 tiles.** List them front to back, the way the PPU draws lower OAM entries on top. Split 16×16 sprites into four parts the way the hardware does (flips swap the quarters).
- **Tiles are shared.** An edit is keyed by `(file, tile)`, so every frame and object that uses a tile changes with it.
- **Colours are keyed by ROM offset.** An offset used by several palettes changes everywhere at once.
- **Building.** Each edited file is re-encoded. If every edited file still fits in its old space, it's written in place. Otherwise every file in `gfx.files` is re-encoded, packed one after another in `region` (in list order), and its `ptrs` are rewritten. The encoder in `snes/lib/lz2.js` is greedy and deterministic, and `tools/snes_build.rb` and `dev/snes/lz2.py` mirror it exactly. On Super Mario World it beats Nintendo's packing by about 6.5 KB, which is the room edits have to grow into.
- **Uncompressed graphics or HiROM** need a few lines in `snes/lib/rom.js` and `tools/snes_build.rb`: a codec of `"none"`, and another entry in `MAPS`. Keep the two in step and add a parity check.

### Finding the data: capture, then map back

`dev/gen_smw/` shows a method that should carry over to other SNES games:

1. Drive the game in `dev/snes/emu.py`, which wraps stable-retro's Snes9x core. It reads RAM, VRAM, CGRAM and OAM from save states, and writes RAM into them. To reach content, poke RAM or patch a *scratch copy* of the ROM, for example forcing a level number or a pose.
2. Group OAM entries per object. In SMW, each sprite slot's OAM index is at `$15EA,x`.
3. Map every VRAM tile back to its source by matching bytes against every decoded graphics file (`provenance_index`). Map every colour back with a model of the game's palette loader, and check it against CGRAM.
4. Write the profile from the mapped parts.

Because frames come from what the game actually drew, they're right by construction, and the test proves the round trip.

## NES profiles (`nes-sprite-profile/1`)

These are documented per game in [HANDOFF.md](HANDOFF.md): CHR-ROM banks, CHR-RAM areas (raw or compressed), `chr_link_sets`, palettes and objects. The NES profiles still live inline in `index.html`. Each generator rewrites only its own `const <GAME>_PROFILE = …;` line.

## Mechanics knobs (both editors)

| kind | fields | what it writes |
|---|---|---|
| `toggle` | `patches: [{offset, hex}]` | the patches when on |
| `number` | `offset`, `also`, `min`, `max`, `bias` | the byte = shown value + bias, at `offset` and every `also` |
| `choice` | `offset`, `options: [{value, label}]` | the chosen value |
| `choice` (patch set) | `options: [{value, label, patches}]` | the chosen option's patches |
| `percent` | `values`, `bytes: [{offset, n, mode, signed, min, max, skip}]`, `words: [{lo, hi, mode, signed}]` | the ROM's own values scaled (`mul`, `div`, `sqrt`) |

Any knob can have `install` patches (for example a hook in free space). They're written first, whenever the knob is away from its default (for a toggle, when it's on), so knobs can share one hook and each write its own byte. Put a `help` sentence on every knob, written for a kid: what changes in the game. `section` starts a new heading.

## Checks

Copy the nearest test (`dev/test_smw.py` and `dev/test_smw_mech.py` for SNES), point it at your ROM's env var, and add it to `dev/run_all.sh`. A good test:

- paints a few tiles and a colour through the page, downloads, and runs the Ruby build, which must produce the same bytes;
- reopens the downloaded project and downloads it again, which must give an identical zip;
- boots the built ROM and finds the edits in the game's own memory (WRAM, VRAM or CGRAM);
- measures each mechanic in play (a jump's height, surviving a hit, lives after a fall).
