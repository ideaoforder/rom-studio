// Small file helpers shared by the editors: CRC32, stored ZIP read/write, IPS patches, PNG encoding.
// Plain browser globals (no modules) so the pages also work when opened from disk (file://).
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc32 = b => { let c = 0xFFFFFFFF; for (const x of b) c = CRC[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
function encodePng(rgba, w, h) { // RGBA, filter 0, zlib stored blocks; no spreads (sheets are large)
  const stride = w * 4 + 1, raw = new Uint8Array(h * stride);
  for (let y = 0; y < h; y++) raw.set(rgba.subarray(y * w * 4, (y + 1) * w * 4), y * stride + 1);
  const nBlocks = Math.max(1, Math.ceil(raw.length / 65535)), z = new Uint8Array(2 + raw.length + nBlocks * 5 + 4);
  let a = 1, b2 = 0, o = 0;
  for (let i = 0; i < raw.length; i++) { a = (a + raw[i]) % 65521; b2 = (b2 + a) % 65521; }
  z[o++] = 0x78; z[o++] = 0x01;
  for (let k = 0; k < nBlocks; k++) {
    const i = k * 65535, n = Math.min(65535, raw.length - i);
    z[o++] = k === nBlocks - 1 ? 1 : 0; z[o++] = n & 255; z[o++] = n >> 8; z[o++] = ~n & 255; z[o++] = (~n >> 8) & 255;
    z.set(raw.subarray(i, i + n), o); o += n;
  }
  z[o++] = (b2 >>> 8) & 255; z[o++] = b2 & 255; z[o++] = (a >>> 8) & 255; z[o++] = a & 255;
  const chunks = [["IHDR", new Uint8Array([w >>> 24, (w >>> 16) & 255, (w >>> 8) & 255, w & 255, h >>> 24, (h >>> 16) & 255, (h >>> 8) & 255, h & 255, 8, 6, 0, 0, 0])], ["IDAT", z], ["IEND", new Uint8Array(0)]];
  const out = new Uint8Array(8 + chunks.reduce((n, [, d]) => n + d.length + 12, 0)); out.set([137, 80, 78, 71, 13, 10, 26, 10]);
  let p = 8; const be = n => { out[p++] = n >>> 24; out[p++] = (n >>> 16) & 255; out[p++] = (n >>> 8) & 255; out[p++] = n & 255; };
  for (const [type, d] of chunks) {
    be(d.length); const start = p; for (let i = 0; i < 4; i++) out[p++] = type.charCodeAt(i);
    out.set(d, p); p += d.length; be(crc32(out.subarray(start, p)));
  }
  return out;
}
function zip(entries) { // [{name, data: Uint8Array}] stored, no compression
  const enc = new TextEncoder(), parts = [], central = []; let off = 0;
  const u16 = n => [n & 255, (n >> 8) & 255], u32 = n => [n & 255, (n >> 8) & 255, (n >> 16) & 255, (n >>> 24) & 255];
  for (const { name, data } of entries) {
    const nb = enc.encode(name), crc = crc32(data);
    const common = [...u16(20), ...u16(0x0800), ...u16(0), ...u16(0), ...u16(0x5821), ...u32(crc), ...u32(data.length), ...u32(data.length), ...u16(nb.length), ...u16(0)];
    const local = Uint8Array.from([0x50, 0x4B, 0x03, 0x04, ...common]);
    parts.push(local, nb, data);
    central.push(Uint8Array.from([0x50, 0x4B, 0x01, 0x02, ...u16(20), ...common, ...u16(0), ...u16(0), ...u16(0), ...u32(0), ...u32(off)]), nb);
    off += local.length + nb.length + data.length;
  }
  const csize = central.reduce((n, a) => n + a.length, 0);
  const end = Uint8Array.from([0x50, 0x4B, 0x05, 0x06, ...u16(0), ...u16(0), ...u16(entries.length), ...u16(entries.length), ...u32(csize), ...u32(off), ...u16(0)]);
  return new Blob([...parts, ...central, end]);
}
async function unzip(buf) {
  const b = new Uint8Array(buf), dv = new DataView(buf);
  let e = -1;
  for (let i = b.length - 22; i >= Math.max(0, b.length - 65557); i--) if (dv.getUint32(i, true) === 0x06054b50) { e = i; break; }
  if (e < 0) throw new Error("That .zip looks damaged (no directory found).");
  const count = dv.getUint16(e + 10, true); let p = dv.getUint32(e + 16, true);
  const out = {}, dec = new TextDecoder();
  for (let n = 0; n < count; n++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break;
    const method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true);
    const nlen = dv.getUint16(p + 28, true), xlen = dv.getUint16(p + 30, true), clen = dv.getUint16(p + 32, true), lo = dv.getUint32(p + 42, true);
    const name = dec.decode(b.slice(p + 46, p + 46 + nlen));
    p += 46 + nlen + xlen + clen;
    if (name.endsWith("/") || /(^|\/)(__MACOSX|\.)/.test(name)) continue;
    const start = lo + 30 + dv.getUint16(lo + 26, true) + dv.getUint16(lo + 28, true);
    let data = b.slice(start, start + csize);
    if (method === 8) data = new Uint8Array(await new Response(new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"))).arrayBuffer());
    else if (method !== 0) continue;
    out[name.split("/").pop()] = data;
  }
  return out;
}

// IPS: offsets are 24-bit, so this covers ROMs up to 16 MB
function ips(orig, mod) {
  const out = [..."PATCH"].map(c => c.charCodeAt(0));
  let i = 0;
  while (i < mod.length) {
    if (orig[i] === mod[i]) { i++; continue; }
    let j = i;
    while (j < mod.length && orig[j] !== mod[j] && j - i < 0xFFFF) j++;
    out.push((i >> 16) & 255, (i >> 8) & 255, i & 255, ((j - i) >> 8) & 255, (j - i) & 255, ...mod.slice(i, j));
    i = j;
  }
  out.push(..."EOF".split("").map(c => c.charCodeAt(0)));
  return Uint8Array.from(out);
}
