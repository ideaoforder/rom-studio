# rom-studio

Read `HANDOFF.md` first: it covers what this is, the architecture of `index.html`, ROM facts, how changes are verified, and what's next.

- `index.html` is the single source for the app (served by GitHub Pages).
- `tools/` is the Ruby CLI; `build` must stay byte-identical with the browser's output.
- Never commit ROMs (`*.nes`), IPS patches, or disassembly; `.gitignore` covers the first three.
