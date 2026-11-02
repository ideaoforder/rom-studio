// SNES colours: 15-bit BGR words (0bbbbbgggggrrrrr), little-endian in ROM. Project files write them as 4 hex digits.
(function (root) {
  const read = (rom, off) => rom[off] | (rom[off + 1] << 8);
  const write = (rom, off, w) => { rom[off] = w & 255; rom[off + 1] = (w >> 8) & 0x7F; };
  const c5 = v => (v << 3) | (v >> 2); // 5-bit -> 8-bit, full range
  const toRgb = w => [c5(w & 31), c5((w >> 5) & 31), c5((w >> 10) & 31)];
  const fromRgb = (r, g, b) => (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10);
  const toCss = w => "#" + toRgb(w).map(v => v.toString(16).padStart(2, "0")).join("");
  const fromCss = s => { const n = parseInt(s.slice(1), 16); return fromRgb(n >> 16, (n >> 8) & 255, n & 255); };
  const hex = w => w.toString(16).toUpperCase().padStart(4, "0");
  root.SnesColor = { read, write, toRgb, fromRgb, toCss, fromCss, hex };
})(typeof window !== "undefined" ? window : globalThis);
