// SNES ROM model for a profile ("snes-profile/1"): addressing, compressed graphics files, palettes, building.
// No DOM. tools/snes_build.rb mirrors build() byte for byte (checked by dev/test_smw.py).
(function (root) {
  const { LZ2, Tiles, SnesColor, Mechanics } = root;
  // LoROM: 32 KB banks at $8000-$FFFF. (HiROM profiles would add their own pair here.)
  const MAPS = {
    lorom: { toFile: a => ((a >> 16) & 0x7F) * 0x8000 + (a & 0x7FFF), toSnes: o => ((o >> 15) << 16) | 0x8000 | (o & 0x7FFF) },
  };
  // Strip a 512-byte copier header if there is one.
  function normalize(bytes) { return bytes.length % 1024 === 512 ? { rom: bytes.slice(512), header: true } : { rom: bytes, header: false }; }
  function matches(P, rom) {
    if (rom.length !== P.rom.size) return false;
    return (P.rom.check || []).every(([off, hex]) => hex.match(/../g).every((h, i) => rom[off + i] === parseInt(h, 16)));
  }
  // Each graphics file decoded once per ROM: {id: {data, size, bpp, tiles}}
  function decodeFiles(P, rom) {
    const out = {};
    for (const f of P.gfx.files) {
      const { data, size } = LZ2.decode(rom, f.at, P.gfx.codec === "lz1");
      out[f.id] = { data, size, bpp: f.bpp, tiles: Math.floor(data.length / Tiles.BYTES[f.bpp]) };
    }
    return out;
  }
  function tile(files, id, t) { const f = files[id]; return Tiles.decodeTile(f.data, t * Tiles.BYTES[f.bpp], f.bpp); }
  // A palette lists, per colour index, the ROM offset its colour is loaded from (null = set by code / not editable).
  // Colour edits are keyed by that offset, so a colour shared by several palettes changes everywhere at once.
  function color(P, rom, state, id, i) {
    const off = P.palettes[id].colors[i];
    if (off == null) { const seen = (P.palettes[id].seen || [])[i]; return seen == null ? null : parseInt(seen, 16); }
    const e = (state.colors || {})[off]; return e != null ? parseInt(e, 16) : SnesColor.read(rom, off);
  }
  function writePtr(out, off, kind, a) {
    if (kind === "lo") out[off] = a & 255;
    else if (kind === "hi") out[off] = (a >> 8) & 255;
    else if (kind === "bank") out[off] = (a >> 16) & 0x7F;
    else if (kind === "word") { out[off] = a & 255; out[off + 1] = (a >> 8) & 255; }
    else if (kind === "long") { out[off] = a & 255; out[off + 1] = (a >> 8) & 255; out[off + 2] = (a >> 16) & 255; }
    else throw new Error("unknown pointer kind " + kind);
  }
  // state: {tiles: {fileId: {tileIndex: hex64}}, colors: {romOffset: hex4}, mech: {knobId: value}}
  function build(P, rom, state, files) {
    files = files || decodeFiles(P, rom);
    const out = rom.slice(), map = MAPS[P.rom.map || "lorom"], enc = {};
    for (const f of P.gfx.files) {
      const edits = (state.tiles || {})[f.id]; if (!edits || !Object.keys(edits).length) continue;
      const src = files[f.id], data = src.data.slice(), n = Tiles.BYTES[f.bpp];
      for (const t of Object.keys(edits).map(Number).sort((a, b) => a - b)) Tiles.encodeTile(Tiles.fromHex(edits[t]), data, t * n, f.bpp);
      if (data.every((v, i) => v === src.data[i])) continue;
      enc[f.id] = LZ2.encode(data, P.gfx.codec === "lz1");
    }
    const ids = Object.keys(enc);
    if (ids.every(id => enc[id].length <= files[id].size)) {
      for (const f of P.gfx.files) if (enc[f.id]) out.set(enc[f.id], f.at);   // everything fits where it was
    } else {
      // repack every file (re-encoding the untouched ones too, which frees space) one after another in the region
      let at = P.gfx.region[0];
      for (const f of P.gfx.files) {
        const b = enc[f.id] || LZ2.encode(files[f.id].data, P.gfx.codec === "lz1");
        if (at + b.length > P.gfx.region[1] || (f.max_end != null && at + b.length > f.max_end))
          throw new Error("The edited graphics don't fit back in the ROM. Try simpler art (fewer colours and patterns) in the newest edits.");
        out.set(b, at); for (const [off, kind] of f.ptrs || []) writePtr(out, off, kind, map.toSnes(at));
        at += b.length;
      }
    }
    for (const [off, h] of Object.entries(state.colors || {})) SnesColor.write(out, Number(off), parseInt(h, 16));
    for (const [off, v] of Object.entries(Mechanics.patches(P.mechanics, rom, state.mech || {}))) out[Number(off)] = v;
    if (P.rom.checksum) fixChecksum(out, P.rom.checksum);
    return out;
  }
  // Internal header checksum (at = file offset of the complement word; checksum follows it)
  function fixChecksum(out, at) {
    out[at] = 0xFF; out[at + 1] = 0xFF; out[at + 2] = 0; out[at + 3] = 0;
    let sum = 0; for (let i = 0; i < out.length; i++) sum = (sum + out[i]) & 0xFFFF;
    out[at] = ~sum & 255; out[at + 1] = (~sum >> 8) & 255; out[at + 2] = sum & 255; out[at + 3] = sum >> 8;
  }
  root.SnesRom = { MAPS, normalize, matches, decodeFiles, tile, color, build, fixChecksum };
})(typeof window !== "undefined" ? window : globalThis);
