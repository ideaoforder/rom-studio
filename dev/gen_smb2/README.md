# SMB2 profile generator

Rebuilds `SMB2_PROFILE` in `index.html` from your own ROM and the [Xkeeper0/smb2](https://github.com/Xkeeper0/smb2) disassembly (built with `./build.sh -dREV_A`, which must match the ROM byte for byte). Nothing from either is committed.

```sh
export SMB2_ROM=/path/to/smb2-rev1.nes SMB2_DIS=/path/to/smb2 SMB2_OUT=/tmp/smb2_gen
python3 gen_players.py && python3 gen_enemies.py && python3 build_enemies.py && python3 build_profile.py
```

- `gen_players.py`: `CharacterTiles_*`, `CharacterEyeTiles` and `CharacterFrameEyeTiles`, drawn the way the player renderer at $F350 does it. Every frame faces right, and duck, duck carry and dead are mirrored.
- `gen_enemies.py` / `build_enemies.py`: groups `EnemyTilemap1/2` by their comments, then uses `EnemyAnimationTable`, `ObjectAttributeTable` and `EnemyArray_46E_Data` for each group's size, mirroring and palettes. Bosses with their own renderers are skipped for now.
- `build_profile.py`: palettes, areas (World 1–7 overworld sprite palettes), `chr_links`, and the write into `index.html`.
