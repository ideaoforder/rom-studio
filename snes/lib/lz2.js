// Nintendo "LZ2" graphics compression (Super Mario World, ALttP and others). Pure functions, no DOM.
// decode(rom, offset) -> {data, size}; encode(data) -> Uint8Array. The encoder is greedy and deterministic:
// tools/snes_build.rb has the same algorithm, so the browser and Ruby produce identical bytes.
// Commands (header byte cccnnnnn, length n+1; ccc=111 is a long header: 111cccnn nnnnnnnn):
//   0 copy n literal bytes, 1 byte fill, 2 word fill (alternating 2 bytes), 3 increasing fill,
//   4-6 repeat earlier output from a 16-bit offset (big-endian here; "LZ1" games use little-endian). $FF ends.
(function (root) {
  function decode(r, off, littleEndian) {
    const out = []; let i = off;
    for (;;) {
      const b = r[i++]; if (b === undefined) throw new Error("LZ2 data runs past the end of the ROM");
      if (b === 0xFF) return { data: Uint8Array.from(out), size: i - off };
      let cmd, n;
      if ((b & 0xE0) === 0xE0) { cmd = (b << 3) & 0xE0; n = (((b & 3) << 8) | r[i++]) + 1; } else { cmd = b & 0xE0; n = (b & 0x1F) + 1; }
      if (cmd === 0) { for (let k = 0; k < n; k++) out.push(r[i + k]); i += n; }
      else if (cmd === 0x20) { const v = r[i++]; for (let k = 0; k < n; k++) out.push(v); }
      else if (cmd === 0x40) { const a = r[i], c = r[i + 1]; i += 2; for (let k = 0; k < n; k++) out.push(k & 1 ? c : a); }
      else if (cmd === 0x60) { const v = r[i++]; for (let k = 0; k < n; k++) out.push((v + k) & 255); }
      else { const src = littleEndian ? r[i] | (r[i + 1] << 8) : (r[i] << 8) | r[i + 1]; i += 2; for (let k = 0; k < n; k++) out.push(out[src + k]); }
      if (out.length > 0x10000) throw new Error("LZ2 data is longer than 64 KB (bad pointer?)");
    }
  }
  function encode(d, littleEndian) {
    const n = d.length, out = [], lit = [], chains = new Map();
    const hdr = (cmd, len) => { len -= 1; if (len < 32) out.push(cmd | len); else out.push(0xE0 | (cmd >> 3) | (len >> 8), len & 255); };
    const flush = () => { while (lit.length) { const k = Math.min(lit.length, 1024); hdr(0, k); out.push(...lit.splice(0, k)); } };
    const key = p => (d[p] << 16) | (d[p + 1] << 8) | d[p + 2];
    const index = p => { if (p + 2 < n) { const k = key(p); let c = chains.get(k); if (!c) chains.set(k, c = []); c.push(p); } };
    let i = 0;
    while (i < n) {
      const m = Math.min(1024, n - i), cands = [];
      let k = 1; while (k < m && d[i + k] === d[i]) k++;
      cands.push([k, 0x20, [d[i]]]);
      if (m >= 2) { k = 2; while (k < m && d[i + k] === d[i + (k & 1)]) k++; cands.push([k, 0x40, [d[i], d[i + 1]]]); }
      k = 1; while (k < m && d[i + k] === ((d[i] + k) & 255)) k++;
      cands.push([k, 0x60, [d[i]]]);
      let bl = 0, bs = 0;
      if (i + 2 < n) for (const s of chains.get(key(i)) || []) {
        if (s > 0xFFFF) break;
        k = 0; while (k < m && d[s + k] === d[i + k]) k++;
        if (k > bl) { bl = k; bs = s; }
        if (k === m) break;
      }
      if (bl) cands.unshift([bl, 0x80, littleEndian ? [bs & 255, bs >> 8] : [bs >> 8, bs & 255]]);
      let best = null, bsav = 0;
      for (const c of cands) { const sav = c[0] - (c[0] <= 32 ? 1 : 2) - c[2].length; if (sav > bsav) { bsav = sav; best = c; } }
      if (!best) { lit.push(d[i]); index(i); i++; continue; }
      flush(); hdr(best[1], best[0]); out.push(...best[2]);
      for (let p = i; p < i + best[0]; p++) index(p);
      i += best[0];
    }
    flush(); out.push(0xFF); return Uint8Array.from(out);
  }
  root.LZ2 = { decode, encode };
})(typeof window !== "undefined" ? window : globalThis);
