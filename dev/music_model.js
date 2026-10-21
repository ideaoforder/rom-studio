// ======================================================================= music (SMB engine, real code on a tiny 6502)
// The preview runs the game's own sound routine on an emulated 6502 against the compiled song bytes,
// so what you hear is what the console does. Songs are edited as patterns: a tempo row plus four lanes
// (melody = square 2, harmony = square 1, bass = triangle, drums = noise).

// ------------------------------------------------------------ 6502 core (official opcodes)
function Cpu6502(read, write) {
  const c = { a: 0, x: 0, y: 0, s: 0xFD, pc: 0, p: 0x24, read, write };
  const C = 1, Z = 2, I = 4, D = 8, B = 16, V = 64, N = 128;
  const nz = v => { c.p = (c.p & ~(N | Z)) | (v & N) | (v ? 0 : Z); return v; };
  const rd16 = a => read(a) | (read((a + 1) & 0xFFFF) << 8);
  const rd16zp = a => read(a & 0xFF) | (read((a + 1) & 0xFF) << 8);
  const push = v => { write(0x100 | c.s, v); c.s = (c.s - 1) & 0xFF; };
  const pull = () => { c.s = (c.s + 1) & 0xFF; return read(0x100 | c.s); };
  const fetch = () => { const v = read(c.pc); c.pc = (c.pc + 1) & 0xFFFF; return v; };
  const fetch16 = () => { const v = rd16(c.pc); c.pc = (c.pc + 2) & 0xFFFF; return v; };
  const AM = {
    imm: () => { const a = c.pc; c.pc = (c.pc + 1) & 0xFFFF; return a; },
    zp: () => fetch(), zpx: () => (fetch() + c.x) & 0xFF, zpy: () => (fetch() + c.y) & 0xFF,
    abs: () => fetch16(), abx: () => (fetch16() + c.x) & 0xFFFF, aby: () => (fetch16() + c.y) & 0xFFFF,
    izx: () => rd16zp((fetch() + c.x) & 0xFF), izy: () => (rd16zp(fetch()) + c.y) & 0xFFFF
  };
  const adc = v => { const t = c.a + v + (c.p & C); c.p = (c.p & ~(C | V)) | (t > 0xFF ? C : 0) | ((~(c.a ^ v) & (c.a ^ t) & 0x80) ? V : 0); c.a = nz(t & 0xFF); };
  const cmp = (r, v) => { const t = r - v; c.p = (c.p & ~C) | (t >= 0 ? C : 0); nz(t & 0xFF); };
  const br = cond => { const o = fetch(); if (cond) c.pc = (c.pc + (o < 128 ? o : o - 256)) & 0xFFFF; };
  const rmw = (am, f) => { const a = AM[am](); write(a, f(read(a))); };
  const asl = v => { c.p = (c.p & ~C) | (v >> 7); return nz((v << 1) & 0xFF); };
  const lsr = v => { c.p = (c.p & ~C) | (v & 1); return nz(v >> 1); };
  const rol = v => { const r = ((v << 1) | (c.p & C)) & 0xFF; c.p = (c.p & ~C) | (v >> 7); return nz(r); };
  const ror = v => { const r = (v >> 1) | ((c.p & C) << 7); c.p = (c.p & ~C) | (v & 1); return nz(r); };
  const ops = new Array(256);
  const def = (codes, fn) => { for (const [op, am] of codes) ops[op] = () => fn(am); };
  def([[0xA9, "imm"], [0xA5, "zp"], [0xB5, "zpx"], [0xAD, "abs"], [0xBD, "abx"], [0xB9, "aby"], [0xA1, "izx"], [0xB1, "izy"]], am => { c.a = nz(read(AM[am]())); });
  def([[0xA2, "imm"], [0xA6, "zp"], [0xB6, "zpy"], [0xAE, "abs"], [0xBE, "aby"]], am => { c.x = nz(read(AM[am]())); });
  def([[0xA0, "imm"], [0xA4, "zp"], [0xB4, "zpx"], [0xAC, "abs"], [0xBC, "abx"]], am => { c.y = nz(read(AM[am]())); });
  def([[0x85, "zp"], [0x95, "zpx"], [0x8D, "abs"], [0x9D, "abx"], [0x99, "aby"], [0x81, "izx"], [0x91, "izy"]], am => write(AM[am](), c.a));
  def([[0x86, "zp"], [0x96, "zpy"], [0x8E, "abs"]], am => write(AM[am](), c.x));
  def([[0x84, "zp"], [0x94, "zpx"], [0x8C, "abs"]], am => write(AM[am](), c.y));
  def([[0x69, "imm"], [0x65, "zp"], [0x75, "zpx"], [0x6D, "abs"], [0x7D, "abx"], [0x79, "aby"], [0x61, "izx"], [0x71, "izy"]], am => adc(read(AM[am]())));
  def([[0xE9, "imm"], [0xE5, "zp"], [0xF5, "zpx"], [0xED, "abs"], [0xFD, "abx"], [0xF9, "aby"], [0xE1, "izx"], [0xF1, "izy"]], am => adc(read(AM[am]()) ^ 0xFF));
  def([[0x29, "imm"], [0x25, "zp"], [0x35, "zpx"], [0x2D, "abs"], [0x3D, "abx"], [0x39, "aby"], [0x21, "izx"], [0x31, "izy"]], am => { c.a = nz(c.a & read(AM[am]())); });
  def([[0x09, "imm"], [0x05, "zp"], [0x15, "zpx"], [0x0D, "abs"], [0x1D, "abx"], [0x19, "aby"], [0x01, "izx"], [0x11, "izy"]], am => { c.a = nz(c.a | read(AM[am]())); });
  def([[0x49, "imm"], [0x45, "zp"], [0x55, "zpx"], [0x4D, "abs"], [0x5D, "abx"], [0x59, "aby"], [0x41, "izx"], [0x51, "izy"]], am => { c.a = nz(c.a ^ read(AM[am]())); });
  def([[0xC9, "imm"], [0xC5, "zp"], [0xD5, "zpx"], [0xCD, "abs"], [0xDD, "abx"], [0xD9, "aby"], [0xC1, "izx"], [0xD1, "izy"]], am => cmp(c.a, read(AM[am]())));
  def([[0xE0, "imm"], [0xE4, "zp"], [0xEC, "abs"]], am => cmp(c.x, read(AM[am]())));
  def([[0xC0, "imm"], [0xC4, "zp"], [0xCC, "abs"]], am => cmp(c.y, read(AM[am]())));
  def([[0x24, "zp"], [0x2C, "abs"]], am => { const v = read(AM[am]()); c.p = (c.p & ~(N | V | Z)) | (v & (N | V)) | ((v & c.a) ? 0 : Z); });
  def([[0xE6, "zp"], [0xF6, "zpx"], [0xEE, "abs"], [0xFE, "abx"]], am => rmw(am, v => nz((v + 1) & 0xFF)));
  def([[0xC6, "zp"], [0xD6, "zpx"], [0xCE, "abs"], [0xDE, "abx"]], am => rmw(am, v => nz((v - 1) & 0xFF)));
  def([[0x06, "zp"], [0x16, "zpx"], [0x0E, "abs"], [0x1E, "abx"]], am => rmw(am, asl));
  def([[0x46, "zp"], [0x56, "zpx"], [0x4E, "abs"], [0x5E, "abx"]], am => rmw(am, lsr));
  def([[0x26, "zp"], [0x36, "zpx"], [0x2E, "abs"], [0x3E, "abx"]], am => rmw(am, rol));
  def([[0x66, "zp"], [0x76, "zpx"], [0x6E, "abs"], [0x7E, "abx"]], am => rmw(am, ror));
  ops[0x0A] = () => { c.a = asl(c.a); }; ops[0x4A] = () => { c.a = lsr(c.a); }; ops[0x2A] = () => { c.a = rol(c.a); }; ops[0x6A] = () => { c.a = ror(c.a); };
  ops[0xAA] = () => { c.x = nz(c.a); }; ops[0x8A] = () => { c.a = nz(c.x); }; ops[0xA8] = () => { c.y = nz(c.a); }; ops[0x98] = () => { c.a = nz(c.y); };
  ops[0xBA] = () => { c.x = nz(c.s); }; ops[0x9A] = () => { c.s = c.x; };
  ops[0xE8] = () => { c.x = nz((c.x + 1) & 0xFF); }; ops[0xCA] = () => { c.x = nz((c.x - 1) & 0xFF); };
  ops[0xC8] = () => { c.y = nz((c.y + 1) & 0xFF); }; ops[0x88] = () => { c.y = nz((c.y - 1) & 0xFF); };
  ops[0x18] = () => { c.p &= ~C; }; ops[0x38] = () => { c.p |= C; }; ops[0x58] = () => { c.p &= ~I; }; ops[0x78] = () => { c.p |= I; };
  ops[0xB8] = () => { c.p &= ~V; }; ops[0xD8] = () => { c.p &= ~D; }; ops[0xF8] = () => { c.p |= D; };
  ops[0x48] = () => push(c.a); ops[0x68] = () => { c.a = nz(pull()); };
  ops[0x08] = () => push(c.p | B | 0x20); ops[0x28] = () => { c.p = (pull() & ~B) | 0x20; };
  ops[0x4C] = () => { c.pc = fetch16(); };
  ops[0x6C] = () => { const a = fetch16(); c.pc = read(a) | (read((a & 0xFF00) | ((a + 1) & 0xFF)) << 8); };
  ops[0x20] = () => { const t = fetch16(); const r = (c.pc - 1) & 0xFFFF; push(r >> 8); push(r & 0xFF); c.pc = t; };
  ops[0x60] = () => { const lo = pull(), hi = pull(); c.pc = (((hi << 8) | lo) + 1) & 0xFFFF; };
  ops[0x40] = () => { c.p = (pull() & ~B) | 0x20; const lo = pull(), hi = pull(); c.pc = (hi << 8) | lo; };
  ops[0x10] = () => br(!(c.p & N)); ops[0x30] = () => br(c.p & N); ops[0x50] = () => br(!(c.p & V)); ops[0x70] = () => br(c.p & V);
  ops[0x90] = () => br(!(c.p & C)); ops[0xB0] = () => br(c.p & C); ops[0xD0] = () => br(!(c.p & Z)); ops[0xF0] = () => br(c.p & Z);
  ops[0xEA] = () => {};
  c.step = () => { const op = fetch(); const f = ops[op]; if (!f) throw new Error(`6502: unsupported opcode $${op.toString(16)} at $${((c.pc - 1) & 0xFFFF).toString(16)}`); f(); };
  // Call a subroutine and return when it does (RTS to a sentinel)
  c.call = (addr, maxSteps = 200000) => {
    c.s = 0xFF; push(0xFF); push(0xEF); c.pc = addr;
    for (let n = 0; c.pc !== 0xFFF0; n++) { if (n > maxSteps) throw new Error("6502: routine didn't return"); c.step(); }
  };
  return c;
}

// ------------------------------------------------------------ SMB sound system on the emulated CPU
const SND = {
  engine: 0xF2D0, mhd: 0xF90D, regionStart: 0xF90D, regionEnd: 0xFF00,   // [start, end)
  lenTable: 0xFF66, areaQueue: 0xFB, eventQueue: 0xFC, operMode: 0x0770
};
const fileOf = addr => addr - 0x8000 + 0x10;
// request: { area: bits } or { event: bits }. Returns per-frame APU writes (like sfxFrames).
function runSoundEngine(rom, request, frames) {
  const ram = new Uint8Array(0x800);
  let log = null;
  const read = a => a < 0x2000 ? ram[a & 0x7FF] : a >= 0x8000 ? rom[a - 0x8000 + 0x10] : 0;
  const write = (a, v) => { if (a < 0x2000) ram[a & 0x7FF] = v; else if (a >= 0x4000 && a <= 0x4017 && log) log.push([a, v]); };
  const cpu = Cpu6502(read, write);
  ram[SND.operMode] = 1;
  const out = [];
  for (let f = 0; f < frames; f++) {
    if (f === 0) { if (request.area) ram[SND.areaQueue] = request.area; if (request.event) ram[SND.eventQueue] = request.event; if (request.sfx) ram[request.sfx[0]] = request.sfx[1]; }
    log = [];
    cpu.call(SND.engine);
    const w = log.filter(([a]) => a !== 0x4017 && a !== 0x4011 && a !== 0x4010 && a !== 0x4012 && a !== 0x4013);
    if (w.length && w[0][0] === 0x4015 && w[0][1] === 0x0F) w.shift();
    out.push(w);
  }
  return out;
}

// ------------------------------------------------------------ song catalog
// slot: which MusicHeaderOffsetData entries (y index) point at the song's header(s)
const SONGS = [
  { id: "ground", name: "Overworld", req: { area: 0x01 }, layout: true },
  { id: "underground", name: "Underground", req: { area: 0x04 }, slot: 0x0B },
  { id: "water", name: "Underwater", req: { area: 0x02 }, slot: 0x0A },
  { id: "castle", name: "Castle", req: { area: 0x08 }, slot: 0x0C },
  { id: "star", name: "Starman", req: { area: 0x40 }, slot: 0x0F, also: [0x0D], alsoName: "also the cloud bonus" },
  { id: "pipe", name: "Pipe intro", req: { area: 0x20 }, slot: 0x0E, note: "also opens the overworld" },
  { id: "death", name: "Lose a life", req: { event: 0x01 }, slot: 0x01 },
  { id: "gameover", name: "Game over", req: { event: 0x02 }, slot: 0x02, also: [0x05] },
  { id: "victory", name: "Princess saved", req: { event: 0x04 }, slot: 0x03 },
  { id: "castleclear", name: "Castle clear", req: { event: 0x08 }, slot: 0x04 },
  { id: "levelclear", name: "Level clear", req: { event: 0x20 }, slot: 0x06 },
  { id: "hurry", name: "Hurry up!", req: { event: 0x40 }, slot: 0x07 }
];
const LAYOUT_SLOTS = [...Array(33).keys()].map(i => 0x11 + i); // ground playlist: y = $11..$31
const SILENCE_SLOTS = [0x08, 0x10];

// ------------------------------------------------------------ stream decoding helpers
const lenIndexAlt = b => (((b & 1) << 2) | ((b >> 6) & 2) | ((b >> 6) & 1)) & 7;   // bits d0,d7,d6
const altByte = (val6, li) => (val6 & 0x3E) | ((li & 4) ? 1 : 0) | ((li & 2) ? 0x80 : 0) | ((li & 1) ? 0x40 : 0);
function lengthOf(rb, lenOfs, li, adder = 0) { return rb(fileOf(SND.lenTable) + ((li + lenOfs + adder) & 0xFF)) || 256; }

// Decode one header into a pattern: { tempo, melody, harmony, bass, drums, flags }
// Each lane is a list of { n: noteByte (or beat), li: length index }. Durations come from the tempo row.
function decodePattern(rb, hdrAddr, opts = {}) {
  const h = i => rb(fileOf(hdrAddr) + i);
  const tempo = h(0), ptr = h(1) | (h(2) << 8), triOfs = h(3), sq1Ofs = h(4), noiseOfs = h(5);
  const at = o => rb(fileOf(ptr + (o & 0xFF)));
  const len = li => lengthOf(rb, tempo, li, opts.adder || 0);
  // melody
  const melody = []; let o = 0, li = null, total = 0, guard = 0;
  for (;;) {
    let b = at(o++); if (++guard > 400) throw new Error("melody runaway");
    if (b === 0) break;
    let L = false;
    if (b & 0x80) { li = b & 7; b = at(o++); L = true; }
    melody.push({ n: b, li: li == null ? 0 : li, inherited: li == null, L });
    total += len(li == null ? 0 : li);
  }
  const melodyBytes = o;
  // harmony
  let harmony = null, alt = false;
  if (sq1Ofs) {
    harmony = []; let o2 = sq1Ofs, t = 0, g = 0;
    while (t < total && g++ < 400) {
      let b = at(o2++);
      if (b === 0) { alt = true; continue; }
      const l = lenIndexAlt(b); harmony.push({ n: b & 0x3E, li: l }); t += len(l);
    }
  }
  // bass: triOfs 0 means the triangle reads the melody stream itself
  let bass = null, bassCopy = triOfs === 0;
  if (!bassCopy) {
    bass = []; let o3 = triOfs, t = 0, l = null, g = 0;
    while (t < total && g++ < 400) {
      let b = at(o3++);
      if (b === 0) { bass.push({ stop: true }); break; }
      let L = false;
      if (b & 0x80) { l = b & 7; b = at(o3++); L = true; if (b === 0) { bass.push({ stop: true, li: l, L: true }); break; } }
      bass.push({ n: b, li: l == null ? 0 : l, inherited: l == null, L }); t += len(l == null ? 0 : l);
    }
  }
  // drums: a loop that repeats until the pattern ends
  let drums = null;
  if (opts.noise && noiseOfs != null) {
    drums = []; let o4 = noiseOfs, g = 0;
    for (;;) { const b = at(o4++); if (b === 0 || ++g > 200) break; drums.push({ n: b & 0x3E, li: lenIndexAlt(b) }); }
  }
  return { tempo, melody, harmony, alt, bass, bassCopy, drums, ptr, triOfs, sq1Ofs, noiseOfs, melodyBytes };
}

// Whole-ROM decode: unique patterns (by header address) + song/slot references.
function decodeMusic(rb) {
  const mhd = SND.mhd, off = y => rb(fileOf(mhd - 1 + y));
  const hdrOf = y => mhd + off(y);
  const pats = new Map();   // header address -> pattern record
  const noiseHeaders = new Set();
  // headers whose noise is actually played: ground parts, water, star/cloud, pipe intro
  for (const y of [...LAYOUT_SLOTS, 0x0A, 0x0D, 0x0E, 0x0F]) noiseHeaders.add(hdrOf(y));
  const slots = {};
  for (let y = 1; y <= 0x31; y++) {
    const ha = hdrOf(y);
    if (SILENCE_SLOTS.includes(y)) { slots[y] = "silence"; continue; }
    if (!pats.has(ha)) {
      const adder = y === 0x07 ? 8 : 0;
      pats.set(ha, { id: "p" + pats.size, hdr: ha, ...decodePattern(rb, ha, { noise: noiseHeaders.has(ha), adder }) });
    }
    slots[y] = pats.get(ha).id;
  }
  return { patterns: [...pats.values()], slots };
}

// ------------------------------------------------------------ compiler
// model: { patterns: [{id, tempo, melody, harmony|null, alt, bass|null, bassCopy, drums|null}], slots: {y: patternId|"silence"} }
// Returns { bytes (region image), size, used, errors }
function encodePattern(p) {
  const err = [];
  // melody: emit a length byte whenever the length changes (always before the first note)
  const mel = []; let cur = null;
  for (const e of p.melody) {
    if (!(e.n > 0 && e.n < 0x80 && !(e.n & 1))) err.push(`melody note $${e.n.toString(16)} is invalid`);
    if (e.L || e.li !== cur) { mel.push(0x80 | e.li); cur = e.li; }
    mel.push(e.n);
  }
  mel.push(0);
  let sq1 = [];
  if (p.harmony) {
    if (p.alt) sq1.push(0);
    for (const e of p.harmony) {
      const b = altByte(e.n, e.li);
      if (b === 0) err.push("harmony note can't be the lowest note at the shortest length");
      if (e.n & ~0x3E) err.push(`harmony note $${e.n.toString(16)} is out of the harmony range`);
      sq1.push(b);
    }
  }
  let tri = [];
  if (p.bass && !p.bassCopy) {
    let c2 = null;
    for (const e of p.bass) {
      if (e.stop) { if (e.L || (e.li != null && e.li !== c2)) tri.push(0x80 | e.li); tri.push(0); break; }
      if (e.L || e.li !== c2) { tri.push(0x80 | e.li); c2 = e.li; }
      tri.push(e.n);
    }
  }
  let noi = [];
  if (p.drums) { for (const e of p.drums) noi.push(altByte(e.n, e.li) || 0x04); noi.push(0); }
  return { mel, sq1, tri, noi, err };
}
// Packs patterns into the music region the way the engine requires:
//   offset table (49 bytes) -> headers within 256 bytes of it -> pattern data.
// Each pattern's other streams must start within 255 bytes after its melody pointer.
// Streams are shared when the same bytes already exist in range (Nintendo did the same).
function compileMusicOrdered(model, regionSize, orderFn) {
  const errors = [];
  const base = SND.mhd;
  const slotIds = Object.values(model.slots);
  const used = model.patterns.filter(p => slotIds.includes(p.id));
  const noiseSlots = new Set([...LAYOUT_SLOTS, 0x0A, 0x0D, 0x0E, 0x0F]);
  const noisy = new Set(Object.entries(model.slots).filter(([y, id]) => noiseSlots.has(+y)).map(([, id]) => id));
  const enc = new Map();
  for (const p of used) {
    const q = noisy.has(p.id) && !(p.drums && p.drums.length) ? { ...p, drums: [{ n: 0x04, li: 4 }] } : p;   // noise songs need a drum loop
    const e = encodePattern(noisy.has(p.id) ? q : { ...q, drums: null });
    for (const m of e.err) errors.push(`${p.name || p.id}: ${m}`);
    enc.set(p.id, e);
  }
  // headers: 6 bytes, or 5 when the 6th (drum) byte is never read and the next header supplies one
  const order = [...used].sort((a, b) => (noisy.has(a.id) ? 0 : 1) - (noisy.has(b.id) ? 0 : 1));
  let hp = 0x31;
  const hdrAt = {};
  const silenceHdr = hp; hp += 5;
  for (const p of order) { hdrAt[p.id] = hp; hp += noisy.has(p.id) ? 6 : 5; }
  hp += 1;  // the last 5-byte header still reads one byte past itself
  if (hp > 256) errors.push(`too many song parts (${used.length}) for the header table`);
  const data = [];                 // bytes after the headers
  const dataStart = hp;
  const findIn = (needle, lo, hi) => {   // search data[lo..hi) for needle; returns index or -1
    outer: for (let i = Math.max(0, lo); i + needle.length <= Math.min(hi, data.length); i++) {
      for (let k = 0; k < needle.length; k++) if (data[i + k] !== needle[k]) continue outer;
      return i;
    }
    return -1;
  };
  const appendShared = (needle) => {     // append, overlapping the current tail when it matches
    for (let ov = Math.min(needle.length, data.length); ov > 0; ov--) {
      let ok = true; for (let k = 0; k < ov; k++) if (data[data.length - ov + k] !== needle[k]) { ok = false; break; }
      if (ok) { const at = data.length - ov; data.push(...needle.slice(ov)); return at; }
    }
    const at = data.length; data.push(...needle); return at;
  };
  const silentAt = appendShared([0]);
  const headers = { [silenceHdr]: [0x18, silentAt, 0, 0, 0] };
  // bigger patterns first gives the packer the most room to reuse their streams
  const byLen = orderFn(used, enc);
  // Streams used by several parts are written after the last of those parts, so every user's
  // melody pointer sits before it (offsets only reach forward, up to 255 bytes).
  const keyOf = b => b.join(",");
  const futureUses = new Map();
  byLen.forEach(p => { const e = enc.get(p.id); for (const k of ["sq1", "tri", "noi"]) if (e[k].length && !(k === "tri" && p.bassCopy)) { const kk = k + ":" + keyOf(e[k]); futureUses.set(kk, (futureUses.get(kk) || 0) + 1); } });
  const pending = new Map();   // key -> { bytes, users: [{p, kind, mp}] }
  const plans = {};
  const placePrivate = (pl, kind, bytes) => {
    const at = findIn(bytes, pl.mp + 1, pl.mp + 256);
    if (at >= 0 && at + bytes.length <= pl.mp + 256) { pl.offs[kind] = at - pl.mp; return true; }
    if (data.length - pl.mp + 0 <= 255) { pl.offs[kind] = appendShared(bytes) - pl.mp; return pl.offs[kind] <= 255; }
    return false;
  };
  for (const p of byLen) {
    const e = enc.get(p.id);
    let mp = findIn(e.mel, 0, data.length);
    if (mp < 0) mp = appendShared(e.mel);
    const pl = { mp, offs: {} }; plans[p.id] = pl;
    for (const kind of ["sq1", "tri", "noi"]) {
      const bytes = e[kind];
      if (!bytes.length || (kind === "tri" && p.bassCopy)) continue;
      const kk = kind + ":" + keyOf(bytes);
      futureUses.set(kk, futureUses.get(kk) - 1);
      const at = findIn(bytes, mp + 1, mp + 256);
      if (at >= 0 && at + bytes.length <= mp + 256) { pl.offs[kind] = at - mp; continue; }
      if (!pending.has(kk)) pending.set(kk, { bytes, users: [] });
      pending.get(kk).users.push({ p, kind, pl });
    }
    // flush shared streams whose last user is now placed (non-shared ones flush immediately)
    for (const [kk, pd] of [...pending]) {
      if (futureUses.get(kk) > 0) continue;
      pending.delete(kk);
      const lo = Math.max(...pd.users.map(u => u.pl.mp)) + 1, hi = Math.min(...pd.users.map(u => u.pl.mp)) + 256;
      let at = findIn(pd.bytes, lo, hi);
      if (!(at >= 0 && at + pd.bytes.length <= hi)) at = appendShared(pd.bytes);
      for (const u of pd.users) {
        const o = at - u.pl.mp;
        if (o >= 1 && o + pd.bytes.length <= 256) u.pl.offs[u.kind] = o;
        else if (!placePrivate(u.pl, u.kind, pd.bytes)) {
          // out of reach: give this part its own fresh copy of the melody and streams
          const e2 = enc.get(u.p.id), m2 = appendShared(e2.mel);
          u.pl.mp = m2; u.pl.offs = {};
          for (const k2 of ["sq1", "tri", "noi"]) if (e2[k2].length && !(k2 === "tri" && u.p.bassCopy)) u.pl.offs[k2] = appendShared(e2[k2]) - m2;
        }
      }
    }
  }
  for (const p of byLen) {
    const pl = plans[p.id];
    const tri = p.bassCopy ? 0 : (pl.offs.tri || 0), sq1 = pl.offs.sq1 || 0, noi = pl.offs.noi || 0;
    if (tri > 255 || sq1 > 255 || noi > 255) errors.push(`${p.name || p.id} is too long for one part; split it in two`);
    headers[hdrAt[p.id]] = [p.tempo, pl.mp, tri & 0xFF, sq1 & 0xFF, noi & 0xFF, noisy.has(p.id)];
  }
  const size = dataStart + data.length;
  const region = new Uint8Array(regionSize);
  if (size > regionSize) errors.push(`out of space: needs ${size} bytes, the game has ${regionSize}`);
  for (let y = 1; y <= 0x31; y++) { const sl = model.slots[y]; region[y - 1] = sl === "silence" || sl == null ? silenceHdr : hdrAt[sl]; }
  for (const [at, h] of Object.entries(headers)) {
    const ptr = base + dataStart + h[1];
    const bytes = [h[0], ptr & 0xFF, ptr >> 8, h[2], h[3]];
    if (h[5]) bytes.push(h[4]);
    region.set(bytes, +at);
  }
  region.set(data.slice(0, Math.max(0, regionSize - dataStart)), dataStart);
  return { bytes: region, used: size, size: regionSize, errors };
}

const encSize = e => e.mel.length + e.sq1.length + e.tri.length + e.noi.length;
const PACK_ORDERS = [
  (u, enc) => [...u].sort((a, b) => encSize(enc.get(b.id)) - encSize(enc.get(a.id))),
  (u) => [...u].sort((a, b) => (a.ptr || 1e9) - (b.ptr || 1e9)),
  (u) => [...u],
  (u) => [...u].reverse(),
  (u, enc) => [...u].sort((a, b) => enc.get(b.id).mel.length - enc.get(a.id).mel.length),
  (u, enc) => [...u].sort((a, b) => (enc.get(b.id).noi.length - enc.get(a.id).noi.length) || (encSize(enc.get(b.id)) - encSize(enc.get(a.id))))
];
for (let seed = 1; seed <= 40; seed++) PACK_ORDERS.push((u, enc) => {   // seeded shuffles of the size order
  let x = seed * 2654435761 >>> 0; const r = () => ((x = (x * 1664525 + 1013904223) >>> 0) / 4294967296);
  return [...u].map(p => [encSize(enc.get(p.id)) * (0.6 + 0.8 * r()), p]).sort((a, b) => b[0] - a[0]).map(v => v[1]);
});
function compileMusic(model, regionSize = SND.regionEnd - SND.regionStart) {
  let best = null;
  for (const ord of PACK_ORDERS) {
    const r = compileMusicOrdered(model, regionSize, ord);
    const bad = r.errors.filter(e => !/^out of space/.test(e)).length;
    if (!best || (bad < best.bad) || (bad === best.bad && r.used < best.r.used)) best = { r, bad };
  }
  return best.r;
}

if (typeof module !== "undefined") module.exports = { Cpu6502, runSoundEngine, SND, SONGS, LAYOUT_SLOTS, fileOf, decodeMusic, decodePattern, compileMusic, encodePattern, lengthOf, lenIndexAlt, altByte };
