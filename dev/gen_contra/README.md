# Contra profile generator

Rebuilds `CONTRA_PROFILE` in `index.html` from your own ROM and the [vermiceli/nes-contra-us](https://github.com/vermiceli/nes-contra-us) disassembly. Build it with cc65 (`./build.sh`, with `baserom.nes` = your ROM) so `contra.dbg` exists. Nothing from either is committed.

```sh
export CONTRA_ROM=/path/to/contra.nes CONTRA_DIS=/path/to/nes-contra-us
WRITE_HTML=1 python3 build_profile.py
```

- `gfx.py`: `graphic_data_ptr_tbl` and a decoder that mirrors `write_graphic_data_to_ppu`. Every block decodes to exactly the length `assets.txt` gives.
- `sprites.py`: `sprite_ptr_tbl_0/1` sprites (8×16 parts, `$80` jumps, `$FE` small sprites); the per-level PPU state built from `level_N_graphic_data` (+ `alt_graphic_data` for the boss areas, "L1b" etc.).
- `objects_def.py`: which sprite codes make each object, and the level whose graphics each one uses. Levels were picked by matching against the disassembly's sprite library; 181 of 223 frames match exactly, and the rest differ only by the library's mirroring and cropping.
- `screens.py` / `build_blocks.py`: level screens (super-tile RLE as in `load_supertiles_screen_indexes`), per-tile background palettes from the super-tile palette bytes, and a sheet of each level's background tiles.
- `build_profile.py`: the `chr_ram` table (blocks, free space per bank, area tile maps), `chr_link_sets` (identical copies of a used tile at the same PPU address in other blocks), and palettes (`gp.XX` = `game_palettes`; `L1.0`/`L1.bg2` are `same_as` aliases from each level header).
