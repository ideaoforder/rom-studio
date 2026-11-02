# rom-studio

Read `HANDOFF.md` first: it covers what this is, the architecture of `index.html`, ROM facts, how changes are verified, and what's next.

- `index.html` is the NES app (served by GitHub Pages); `snes/` is the SNES app (`snes/index.html` + `app.js`, format code in `snes/lib/`, one profile per game in `snes/profiles/`). `lib/` has helpers both can share.
- `tools/` is the Ruby CLI; `build` (NES `smb_patcher.rb`, SNES `snes_build.rb`) must stay byte-identical with the browser's output.
- Never commit ROMs (`*.nes`), IPS patches, or disassembly; `.gitignore` covers the first three. Same for SNES ROMs (`*.sfc`, `*.smc`) and decoded graphics.
