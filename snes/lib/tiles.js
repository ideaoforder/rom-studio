// SNES planar tiles <-> 8x8 colour-index grids. bpp 2, 4, 8 are the hardware formats; "3" is the 24-byte form
// Super Mario World (and others) store in ROM: a 2bpp tile (planes 0-1) followed by 8 bytes of plane 2.
(function (root) {
  const BYTES = { 2: 16, 3: 24, 4: 32, 8: 64 };
  // byte offset of (row y, plane p) inside one tile
  function at(bpp, y, p) {
    if (bpp === 3) return p < 2 ? 2 * y + p : 16 + y;
    return 16 * (p >> 1) + 2 * y + (p & 1);
  }
  const planes = bpp => (bpp === 3 ? 3 : bpp);
  function decodeTile(buf, off, bpp) {
    const px = [];
    for (let y = 0; y < 8; y++) {
      const row = [];
      for (let x = 0; x < 8; x++) { let v = 0; for (let p = 0; p < planes(bpp); p++) v |= ((buf[off + at(bpp, y, p)] >> (7 - x)) & 1) << p; row.push(v); }
      px.push(row);
    }
    return px;
  }
  function encodeTile(px, buf, off, bpp) {
    for (let i = 0; i < BYTES[bpp]; i++) buf[off + i] = 0;
    for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) for (let p = 0; p < planes(bpp); p++)
      if ((px[y][x] >> p) & 1) buf[off + at(bpp, y, p)] |= 0x80 >> x;
  }
  // compact text form used in project files: 64 hex digits, row by row
  const toHex = px => px.map(r => r.map(v => v.toString(16)).join("")).join("");
  const fromHex = s => Array.from({ length: 8 }, (_, y) => Array.from({ length: 8 }, (_, x) => parseInt(s[y * 8 + x], 16)));
  root.Tiles = { BYTES, decodeTile, encodeTile, toHex, fromHex };
})(typeof window !== "undefined" ? window : globalThis);
