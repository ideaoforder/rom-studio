// Capcom's LZ graphics compression (Mega Man 7; also Rockman & Forte, Mega Man X2/X3). Pure functions, no DOM.
// A control byte holds 8 flags, high bit first: 0 = one literal byte, 1 = two bytes LLLLLLDD DDDDDDDD meaning
// "copy L (1-63) bytes from D (1-1023) back in the output". No end marker: the game's table gives the unpacked size.
// encode() is an optimal parse (fewest bits: literal 9, copy 17) with fixed tie rules, mirrored by
// tools/snes_build.rb and dev/snes/clz.py so every build is byte-identical.
(function (root) {
  function decode(r, off, size) {
    const out = new Uint8Array(size); let o = 0, i = off, ctl = r[i++], n = 8;
    while (o < size) {
      if (!(ctl & 0x80)) out[o++] = r[i++];
      else {
        const d = ((r[i] & 3) << 8) | r[i + 1], L = r[i] >> 2; i += 2;
        if (d === 0 || d > o) throw new Error("bad Capcom LZ data (copy before the start)");
        for (let k = 0; k < L && o < size; k++, o++) out[o] = out[o - d];
      }
      if (o >= size) break;
      ctl = (ctl << 1) & 255;
      if (--n === 0) { ctl = r[i++]; n = 8; }
    }
    return { data: out, size: i - off };
  }
  // longest match (<= 63) within 1023 bytes back for every position; nearest wins a tie
  function matches(d) {
    const n = d.length, len = new Uint8Array(n), dist = new Uint16Array(n), chains = new Map();
    for (let i = 0; i < n; i++) {
      let bl = 0, bd = 0; const m = Math.min(63, n - i);
      if (i + 2 < n) {
        const key = (d[i] << 16) | (d[i + 1] << 8) | d[i + 2]; let c = chains.get(key);
        if (c) for (let j = c.length - 1; j >= 0; j--) {
          const s = c[j]; if (i - s > 1023) break;
          let k = 0; while (k < m && d[s + k] === d[i + k]) k++;
          if (k > bl) { bl = k; bd = i - s; }
          if (k === m) break;
        } else chains.set(key, c = []);
        c.push(i);
      }
      len[i] = bl; dist[i] = bd;
    }
    return { len, dist };
  }
  function encode(d) {
    const n = d.length, { len, dist } = matches(d), cost = new Float64Array(n + 1), pick = new Uint8Array(n);
    for (let i = n - 1; i >= 0; i--) {
      let best = 9 + cost[i + 1], choice = 0;
      for (let L = len[i]; L >= 3; L--) { const c = 17 + cost[i + L]; if (c < best) { best = c; choice = L; } }
      cost[i] = best; pick[i] = choice;
    }
    const out = []; let i = 0, ctlAt = -1, bits = 8;
    while (i < n) {
      if (bits === 8) { ctlAt = out.length; out.push(0); bits = 0; }
      const L = pick[i];
      if (L) { out[ctlAt] |= 0x80 >> bits; const dd = dist[i]; out.push((L << 2) | (dd >> 8), dd & 255); i += L; }
      else out.push(d[i++]);
      bits++;
    }
    return Uint8Array.from(out);
  }
  root.CLZ = { decode, encode };
})(typeof window !== "undefined" ? window : globalThis);
