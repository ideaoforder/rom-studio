// ======================================================================= sound effects (SMB engine model)
// Each effect is described by the ROM bytes it reads (knobs + tables) and a frame-by-frame model of
// the game's own routine. sfxFrames() returns the sound-register writes the game would make on each
// frame (tested against the real 6502 code), and renderApu() turns them into audio like the 2A03 does.
const SFX_FREQ_TABLE = 0x7F10;
const SFX_KNOBS = {
  "jump.small": { off: 0x73DE, kind: "pitch", label: "Start pitch (small)" },
  "jump.big": { off: 0x73E2, kind: "pitch", label: "Start pitch (big)" },
  "jump.c1": { off: 0x73E4, kind: "ctrl", label: "Tone" },
  "jump.s1": { off: 0x73E6, kind: "sweep", label: "Slide" },
  "jump.len": { off: 0x73EB, kind: "len", label: "Length", min: 2 },
  "jump.t2": { off: 0x73F3, kind: "when", label: "Part 2 starts", len: "jump.len" },
  "jump.c2": { off: 0x73F7, kind: "ctrl", nz: true, label: "Part 2 tone" },
  "jump.s2": { off: 0x73F9, kind: "sweep", nz: true, label: "Part 2 slide" },
  "jump.t3": { off: 0x73FD, kind: "when", label: "Part 3 starts", len: "jump.len" },
  "jump.c3": { off: 0x7401, kind: "ctrl", label: "Part 3 tone" },
  "jump.s3": { off: 0x7403, kind: "sweep", nz: true, label: "Part 3 slide" },
  "fire.len": { off: 0x740A, kind: "len", label: "Length", min: 1 },
  "fire.s": { off: 0x740C, kind: "sweep", nz: true, label: "Slide" },
  "bump.len": { off: 0x7410, kind: "len", label: "Length", min: 1 },
  "bump.s": { off: 0x7412, kind: "sweep", label: "Slide" },
  "fb.c": { off: 0x7414, kind: "ctrl", label: "Tone" },
  "fb.p": { off: 0x7419, kind: "pitch", label: "Start pitch" },
  "fb.t2": { off: 0x7421, kind: "when", label: "Part 2 starts", len: "bump.len" },
  "fb.s2": { off: 0x7425, kind: "sweep", nz: true, label: "Part 2 slide" },
  "stomp.len": { off: 0x746C, kind: "len", label: "Length", min: 1, max: 14 },
  "stomp.s": { off: 0x7471, kind: "sweep", label: "Slide" },
  "stomp.p": { off: 0x7475, kind: "pitch", label: "Start pitch" },
  "stomp.t2": { off: 0x7483, kind: "when", label: "Second tone at", len: "stomp.len" },
  "stomp.lo2": { off: 0x7487, kind: "lo", nz: true, label: "Second tone", base: "stomp.p" },
  "kick.len": { off: 0x748E, kind: "len", label: "Length", min: 1 },
  "kick.s": { off: 0x7490, kind: "sweep", label: "Slide" },
  "kick.c1": { off: 0x7492, kind: "ctrl", label: "First tick tone" },
  "kick.p": { off: 0x7497, kind: "pitch", label: "Start pitch" },
  "kick.t2": { off: 0x74A1, kind: "when", label: "Second tick at", len: "kick.len" },
  "kick.lo2": { off: 0x74A5, kind: "lo", label: "Second tick pitch", base: "kick.p" },
  "kick.c2": { off: 0x74AA, kind: "ctrl", nz: true, label: "Second tick tone" },
  "kick.gap": { off: 0x74AE, kind: "ctrl", label: "Between ticks" },
  "pipe.len": { off: 0x74C7, kind: "len", label: "Length", min: 1 },
  "pipe.s": { off: 0x74D9, kind: "sweep", label: "Slide" },
  "pipe.c": { off: 0x74DB, kind: "ctrl", label: "Tone" },
  "pipe.p": { off: 0x74DD, kind: "pitch", label: "Pitch" },
  "flag.len": { off: 0x73D0, kind: "len", label: "Length", min: 1 },
  "flag.p": { off: 0x73D5, kind: "pitch", label: "Pitch" },
  "flag.c": { off: 0x73DA, kind: "ctrl", nz: true, label: "Tone" },
  "coin.len": { off: 0x7529, kind: "len", label: "Length", min: 1 },
  "coin.c": { off: 0x752B, kind: "ctrl", nz: true, label: "Tone" },
  "tick.len": { off: 0x752F, kind: "len", label: "Length", min: 1 },
  "tick.c": { off: 0x7531, kind: "ctrl", label: "Tone" },
  "ct.s": { off: 0x7536, kind: "sweep", label: "Slide" },
  "ct.p": { off: 0x7538, kind: "pitch", label: "First note" },
  "ct.t2": { off: 0x7540, kind: "when", label: "Second note at", len: "coin.len" },
  "ct.lo2": { off: 0x7544, kind: "lo", nz: true, label: "Second note", base: "ct.p" },
  "blast.len": { off: 0x754B, kind: "len", label: "Length", min: 1 },
  "blast.s1": { off: 0x7550, kind: "sweep", label: "Slide" },
  "blast.p1": { off: 0x7552, kind: "pitch", label: "Start pitch" },
  "blast.t2": { off: 0x7559, kind: "when", label: "Part 2 starts", len: "blast.len" },
  "blast.s2": { off: 0x755D, kind: "sweep", label: "Part 2 slide" },
  "blast.p2": { off: 0x755F, kind: "pitch", label: "Part 2 pitch" },
  "bf.len": { off: 0x75D9, kind: "len", label: "Length", min: 1 },
  "bf.s1": { off: 0x75DE, kind: "sweep", label: "Slide" },
  "bf.p1": { off: 0x75E0, kind: "pitch", label: "Start pitch" },
  "bf.t2": { off: 0x75E7, kind: "when", label: "Part 2 starts", len: "bf.len" },
  "bf.s2": { off: 0x75EB, kind: "sweep", label: "Part 2 slide" },
  "bf.p2": { off: 0x75ED, kind: "pitch", label: "Part 2 pitch" },
  "boom.c": { off: 0x75EF, kind: "ctrl", nz: true, label: "Tone" },
  "grab.len": { off: 0x7563, kind: "len", label: "Length", min: 1, max: 54 },
  "grab.c": { off: 0x7572, kind: "ctrl", label: "Tone" },
  "grab.s": { off: 0x7574, kind: "sweep", label: "Slide" },
  "oneup.len": { off: 0x75F3, kind: "len", label: "Length", min: 1, max: 48 },
  "oneup.c": { off: 0x7607, kind: "ctrl", label: "Tone" },
  "oneup.s": { off: 0x7609, kind: "sweep", nz: true, label: "Slide" },
  "sprout.len": { off: 0x760D, kind: "len", label: "Notes", min: 1, max: 32 },
  "vine.len": { off: 0x7611, kind: "len", label: "Notes", min: 1, max: 32 },
  "grow.s": { off: 0x7616, kind: "sweep", label: "Slide" },
  "grow.c": { off: 0x762D, kind: "ctrl", label: "Tone" },
  "brick.len": { off: 0x764C, kind: "len", label: "Length", min: 1, max: 32 },
  "flame.len": { off: 0x7691, kind: "len", label: "Length", min: 1, max: 64 },
  "flame.p": { off: 0x769B, kind: "npitch", label: "Rumble" },
  "noise.lenload": { off: 0x7664, kind: "raw", label: "Noise length code" }
};
const SFX_TABLES = {
  "stomp.env": { off: 0x73C1, n: 14, kind: "vol", label: "Volume over time" },
  "oneup.notes": { off: 0x74E4, n: 6, kind: "pitch", label: "Notes (played last to first)" },
  "grab.notes": { off: 0x74EA, n: 27, kind: "pitch", label: "Notes (played last to first)" },
  "grow.notes": { off: 0x7508, n: 32, kind: "pitch", label: "Notes (sprout uses the first 16)" },
  "brick.pitch": { off: 0x763B, n: 16, kind: "npitch", label: "Crunch pitch (played last to first)" },
  "brick.vol": { off: 0x7FFA, n: 16, kind: "vol", label: "Crunch volume (played last to first)" },
  "flame.vol": { off: 0x7FDA, n: 32, kind: "vol", label: "Volume (played last to first)" }
};
// queue: [channel queue, bit] as the game requests it; groups list what the editor shows.
const SFX_LIST = [
  { id: "jump", name: "Jump", ch: "sq1", variants: [["Small", "jump.small"], ["Big", "jump.big"]],
    groups: [["Start", ["jump.small", "jump.big", "jump.c1", "jump.s1", "jump.len"]], ["Part 2", ["jump.t2", "jump.c2", "jump.s2"]], ["Part 3", ["jump.t3", "jump.c3", "jump.s3"]]] },
  { id: "fire", name: "Fireball", ch: "sq1", groups: [["Sound", ["fb.p", "fb.c", "fire.s", "fire.len"]], ["Part 2 (only if longer than its start frame)", ["fb.t2", "fb.s2"]]] },
  { id: "stomp", name: "Stomp / swim", ch: "sq1", groups: [["Sound", ["stomp.p", "stomp.s", "stomp.len"]], ["Second tone", ["stomp.t2", "stomp.lo2"]]], tables: ["stomp.env"] },
  { id: "kick", name: "Kick", ch: "sq1", groups: [["First tick", ["kick.p", "kick.c1", "kick.s", "kick.len"]], ["Second tick", ["kick.t2", "kick.lo2", "kick.c2", "kick.gap"]]] },
  { id: "bump", name: "Bump", ch: "sq1", groups: [["Sound", ["fb.p", "fb.c", "bump.s", "bump.len"]], ["Part 2", ["fb.t2", "fb.s2"]]] },
  { id: "coin", name: "Coin", ch: "sq2", groups: [["Sound", ["ct.p", "coin.c", "ct.s", "coin.len"]], ["Second note", ["ct.t2", "ct.lo2"]]] },
  { id: "sprout", name: "Power-up appears", ch: "sq2", groups: [["Sound", ["grow.c", "grow.s", "sprout.len"]]], tables: ["grow.notes"] },
  { id: "grab", name: "Power-up grab", ch: "sq2", groups: [["Sound", ["grab.c", "grab.s", "grab.len"]]], tables: ["grab.notes"] },
  { id: "oneup", name: "1-Up", ch: "sq2", groups: [["Sound", ["oneup.c", "oneup.s", "oneup.len"]]], tables: ["oneup.notes"] },
  { id: "pipe", name: "Pipe / ouch", ch: "sq1", groups: [["Sound", ["pipe.p", "pipe.c", "pipe.s", "pipe.len"]]] },
  { id: "brick", name: "Brick break", ch: "noise", groups: [["Sound", ["brick.len"]]], tables: ["brick.pitch", "brick.vol"] },
  { id: "flag", name: "Flagpole", ch: "sq1", groups: [["Sound", ["flag.p", "flag.c", "jump.s3", "flag.len"]]] },
  { id: "blast", name: "Fireworks", ch: "sq2", groups: [["Bang", ["blast.p1", "boom.c", "blast.s1", "blast.len"]], ["Echo", ["blast.t2", "blast.p2", "blast.s2"]]] },
  { id: "vine", name: "Vine grows", ch: "sq2", groups: [["Sound", ["grow.c", "grow.s", "vine.len"]]], tables: ["grow.notes"] },
  { id: "tick", name: "Timer tick", ch: "sq2", groups: [["Sound", ["ct.p", "tick.c", "ct.s", "tick.len"]]] },
  { id: "bf", name: "Bowser falls", ch: "sq2", groups: [["Fall", ["bf.p1", "boom.c", "bf.s1", "bf.len"]], ["Splash", ["bf.t2", "bf.p2", "bf.s2"]]] },
  { id: "flame", name: "Bowser flame", ch: "noise", groups: [["Sound", ["flame.p", "flame.len"]]], tables: ["flame.vol"] }
];
// Which effects read each byte, so the editor can say "this also changes Bump".
const SFX_USERS = (() => {
  const m = {};
  const add = (key, id) => { (m[key] = m[key] || new Set()).add(id); };
  for (const s of SFX_LIST) {
    for (const [, ks] of s.groups) for (const k of ks) add(k, s.id);
    for (const t of s.tables || []) add(t, s.id);
  }
  // reads that aren't edited in that effect's own panel but still happen in its routine
  add("fb.t2", "fire"); add("fb.s2", "fire"); add("ct.t2", "tick"); add("ct.lo2", "tick");
  add("noise.lenload", "brick"); add("noise.lenload", "flame");
  return m;
})();

function sfxFrames(id, rb, variant) {
  const K = k => rb(SFX_KNOBS[k].off), T = (k, i) => rb(SFX_TABLES[k].off + i);
  const ft = i => rb(SFX_FREQ_TABLE + i);
  const frames = [];
  let w = [];
  const freq = (base, a) => { const lo = ft((a + 1) & 0xFF); if (lo === 0) return; w.push([base + 2, lo], [base + 3, ft(a & 0xFF) | 8]); };
  const sq1 = (y, x, a) => { w.push([0x4001, y], [0x4000, x]); freq(0x4000, a); };
  const sq2 = (x, y, a) => { w.push([0x4004, x], [0x4005, y]); freq(0x4004, a); };
  const endFrame = () => { frames.push(w); w = []; };
  const stop1 = () => w.push([0x4015, 0x0E], [0x4015, 0x0F]);
  const stop2 = () => w.push([0x4015, 0x0D], [0x4015, 0x0F]);
  const MAXF = 600;
  let cnt;
  const dec = stop => { cnt = (cnt - 1) & 0xFF; if (cnt === 0) { stop(); endFrame(); return true; } endFrame(); return false; };
  switch (id) {
    case "jump": {
      cnt = K("jump.len");
      sq1(K("jump.s1"), K("jump.c1"), K(variant === 1 ? "jump.big" : "jump.small"));
      for (let f = 0; f < MAXF; f++) {
        if (cnt === K("jump.t2")) w.push([0x4001, K("jump.s2")], [0x4000, K("jump.c2")]);
        else if (cnt === K("jump.t3")) w.push([0x4001, K("jump.s3")], [0x4000, K("jump.c3")]);
        if (dec(stop1)) break;
      }
      break;
    }
    case "fire": case "bump": {
      cnt = K(id + ".len");
      sq1(K(id === "fire" ? "fire.s" : "bump.s"), K("fb.c"), K("fb.p"));
      for (let f = 0; f < MAXF; f++) {
        if (cnt === K("fb.t2")) w.push([0x4001, K("fb.s2")]);
        if (dec(stop1)) break;
      }
      break;
    }
    case "stomp": {
      cnt = K("stomp.len");
      sq1(K("stomp.s"), rb(0x7473), K("stomp.p"));
      for (let f = 0; f < MAXF; f++) {
        w.push([0x4000, rb(SFX_TABLES["stomp.env"].off + cnt - 1)]);
        if (cnt === K("stomp.t2")) w.push([0x4002, K("stomp.lo2")]);
        if (dec(stop1)) break;
      }
      break;
    }
    case "kick": {
      cnt = K("kick.len");
      sq1(K("kick.s"), K("kick.c1"), K("kick.p"));
      if (!dec(stop1)) for (let f = 0; f < MAXF; f++) {
        if (cnt === K("kick.t2")) w.push([0x4002, K("kick.lo2")], [0x4000, K("kick.c2")]);
        else w.push([0x4000, K("kick.gap")]);
        if (dec(stop1)) break;
      }
      break;
    }
    case "pipe": {
      cnt = K("pipe.len");
      for (let f = 0; f < MAXF; f++) {
        if (!(cnt & 1) && !(cnt & 2) && (cnt & 8)) sq1(K("pipe.s"), K("pipe.c"), K("pipe.p"));
        if (dec(stop1)) break;
      }
      break;
    }
    case "flag": {
      cnt = K("flag.len");
      freq(0x4000, K("flag.p")); w.push([0x4001, K("jump.s3")], [0x4000, K("flag.c")]);
      for (let f = 0; f < MAXF; f++) if (dec(stop1)) break;
      break;
    }
    case "coin": case "tick": {
      cnt = K(id + ".len");
      sq2(K(id + ".c"), K("ct.s"), K("ct.p"));
      for (let f = 0; f < MAXF; f++) {
        if (cnt === K("ct.t2")) w.push([0x4006, K("ct.lo2")]);
        if (dec(stop2)) break;
      }
      break;
    }
    case "blast": case "bf": {
      cnt = K(id + ".len");
      sq2(K("boom.c"), K(id + ".s1"), K(id + ".p1"));
      if (!dec(stop2)) for (let f = 0; f < MAXF; f++) {
        if (cnt === K(id + ".t2")) sq2(K("boom.c"), K(id + ".s2"), K(id + ".p2"));
        if (dec(stop2)) break;
      }
      break;
    }
    case "grab": {
      cnt = K("grab.len");
      for (let f = 0; f < MAXF; f++) {
        if (!(cnt & 1)) sq2(K("grab.c"), K("grab.s"), T("grab.notes", (cnt >> 1) - 1));
        if (dec(stop2)) break;
      }
      break;
    }
    case "oneup": {
      cnt = K("oneup.len");
      for (let f = 0; f < MAXF; f++) {
        if (!(cnt & 7)) sq2(K("oneup.c"), K("oneup.s"), T("oneup.notes", (cnt >> 3) - 1));
        if (dec(stop2)) break;
      }
      break;
    }
    case "sprout": case "vine": {
      cnt = K(id + ".len");
      w.push([0x4005, K("grow.s")]);
      let sec = 0;
      for (let f = 0; f < MAXF; f++) {
        sec = (sec + 1) & 0xFF;
        const y = sec >> 1;
        if (y === cnt) { stop2(); endFrame(); break; }
        w.push([0x4004, K("grow.c")]); freq(0x4004, T("grow.notes", y));
        endFrame();
      }
      break;
    }
    case "brick": case "flame": {
      cnt = K(id + ".len");
      const ll = K("noise.lenload");
      for (let f = 0; f < MAXF; f++) {
        if (id === "brick") {
          if (cnt & 1) { const y = cnt >> 1; w.push([0x400C, T("brick.vol", y)], [0x400E, T("brick.pitch", y)], [0x400F, ll]); }
        } else {
          const y = cnt >> 1; w.push([0x400C, rb(SFX_TABLES["flame.vol"].off + y - 1)], [0x400E, K("flame.p")], [0x400F, ll]);
        }
        cnt = (cnt - 1) & 0xFF;
        if (cnt === 0) { w.push([0x400C, 0xF0]); endFrame(); break; }
        endFrame();
      }
      break;
    }
  }
  return frames;
}

// --------------------------------------------------------------- 2A03 square + noise channels
const APU_LEN = [10, 254, 20, 2, 40, 4, 80, 6, 160, 8, 60, 10, 14, 12, 26, 14, 12, 16, 24, 18, 48, 20, 96, 22, 192, 24, 72, 26, 16, 28, 32, 30];
const APU_DUTY = [[0, 1, 0, 0, 0, 0, 0, 0], [0, 1, 1, 0, 0, 0, 0, 0], [0, 1, 1, 1, 1, 0, 0, 0], [1, 0, 0, 1, 1, 1, 1, 1]];
const APU_NOISE = [4, 8, 16, 32, 64, 96, 128, 160, 202, 254, 380, 508, 762, 1016, 2034, 4068];
const APU_CPU = 1789773;
function apuChannel(kind, isSq1) {
  return { kind, isSq1, duty: 0, halt: 0, cv: 0, v: 0, envStart: false, envDiv: 0, decay: 0,
    swOn: 0, swP: 0, swNeg: 0, swShift: 0, swReload: false, swDiv: 0, timer: 0, len: 0, on: true, phase: 0,
    mode: 0, nper: 4, lfsr: 1, nacc: 0 };
}
function apuSweepTarget(c) {
  const ch = c.timer >> c.swShift;
  return c.swNeg ? c.timer - ch - (c.isSq1 ? 1 : 0) : c.timer + ch;
}
const apuMuted = c => c.kind === "sq" && (c.timer < 8 || (!c.swNeg && apuSweepTarget(c) > 0x7FF));
function apuWrite(c, r, val) {
  if (r === 0) { c.duty = val >> 6; c.halt = (val >> 5) & 1; c.cv = (val >> 4) & 1; c.v = val & 15; }
  else if (r === 1 && c.kind === "sq") { c.swOn = val >> 7; c.swP = (val >> 4) & 7; c.swNeg = (val >> 3) & 1; c.swShift = val & 7; c.swReload = true; }
  else if (r === 2) { if (c.kind === "sq") c.timer = (c.timer & 0x700) | val; else { c.mode = val >> 7; c.nper = APU_NOISE[val & 15]; } }
  else if (r === 3) {
    if (c.kind === "sq") { c.timer = (c.timer & 0xFF) | ((val & 7) << 8); c.phase = 0; }
    if (c.on) c.len = APU_LEN[val >> 3];
    c.envStart = true;
  }
}
function apuQuarter(c) {
  if (c.envStart) { c.envStart = false; c.decay = 15; c.envDiv = c.v; }
  else if (c.envDiv === 0) { c.envDiv = c.v; if (c.decay > 0) c.decay--; else if (c.halt) c.decay = 15; }
  else c.envDiv--;
}
function apuHalf(c) {
  if (!c.halt && c.len > 0) c.len--;
  if (c.kind !== "sq") return;
  if (c.swDiv === 0 && c.swOn && c.swShift > 0 && !apuMuted(c)) c.timer = Math.max(0, apuSweepTarget(c)) & 0x7FF;
  if (c.swDiv === 0 || c.swReload) { c.swDiv = c.swP; c.swReload = false; } else c.swDiv--;
}
const apuVol = c => (c.cv ? c.v : c.decay);
// frames: per-frame [[addr, value], ...]  ->  { samples, trace: per frame [{hz, vol, ch}] }
function renderApu(frames, sampleRate = 44100, tailFrames = 6) {
  const chans = [apuChannel("sq", true), apuChannel("sq", false), apuChannel("noise", false)];
  const route = a => a < 0x4004 ? [chans[0], a - 0x4000] : a < 0x4008 ? [chans[1], a - 0x4004] : (a >= 0x400C && a < 0x4010) ? [chans[2], a - 0x400C] : null;
  const spf = sampleRate / 60.0988, cps = APU_CPU / sampleRate;
  const total = Math.ceil((frames.length + tailFrames) * spf);
  const out = new Float32Array(total), trace = [];
  let pos = 0, acc = 0, hp = 0, prevIn = 0;
  for (let f = 0; f < frames.length + tailFrames; f++) {
    for (const [a, v] of frames[f] || []) {
      if (a === 0x4015) { chans[0].on = !!(v & 1); chans[1].on = !!(v & 2); chans[2].on = !!(v & 8); for (const c of chans) if (!c.on) c.len = 0; continue; }
      const r = route(a); if (r) apuWrite(r[0], r[1], v);
    }
    acc += spf; const n = Math.floor(acc); acc -= n;
    for (let q = 0; q < 4; q++) {
      const end = pos + Math.round(n * (q + 1) / 4) - Math.round(n * q / 4);
      for (; pos < end && pos < total; pos++) {
        let p = 0, nz = 0;
        for (let i = 0; i < 2; i++) {
          const c = chans[i];
          if (c.len > 0 && !apuMuted(c)) {
            c.phase += 8 * (APU_CPU / (16 * (c.timer + 1))) / sampleRate;
            p += APU_DUTY[c.duty][Math.floor(c.phase) & 7] * apuVol(c);
          }
        }
        const z = chans[2];
        z.nacc += cps / z.nper;
        while (z.nacc >= 1) { z.nacc -= 1; const fb = (z.lfsr & 1) ^ ((z.lfsr >> (z.mode ? 6 : 1)) & 1); z.lfsr = (z.lfsr >> 1) | (fb << 14); }
        if (z.len > 0 && !(z.lfsr & 1)) nz = apuVol(z);
        const mix = (p > 0 ? 95.88 / (8128 / p + 100) : 0) + (nz > 0 ? 159.79 / (1 / (nz / 12241) + 100) : 0);
        hp = 0.996 * (hp + mix - prevIn); prevIn = mix;  // remove DC like the console's output filter
        out[pos] = hp * 1.6;
      }
      for (const c of chans) apuQuarter(c);
      if (q === 1 || q === 3) for (const c of chans) apuHalf(c);
    }
    trace.push(chans.map((c, i) => {
      const audible = c.len > 0 && !(i < 2 && apuMuted(c)) && apuVol(c) > 0;
      return { ch: i, vol: audible ? apuVol(c) : 0, hz: i < 2 ? APU_CPU / (16 * (c.timer + 1)) : APU_CPU / c.nper / 93, noise: i === 2 };
    }));
  }
  return { samples: out, trace };
}
// Pitch index (even offset into the game's frequency table) -> note name
function sfxPitchInfo(rb, a) {
  const hi = rb(SFX_FREQ_TABLE + (a & 0xFF)), lo = rb(SFX_FREQ_TABLE + ((a + 1) & 0xFF));
  if (lo === 0) return { rest: true, name: "rest", hz: 0 };
  const t = ((hi & 7) << 8) | lo, hz = APU_CPU / (16 * (t + 1));
  return { rest: false, hz, name: hzName(hz), period: t };
}
function hzName(hz) {
  const m = Math.round(69 + 12 * Math.log2(hz / 440));
  return ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"][((m % 12) + 12) % 12] + (Math.floor(m / 12) - 1);
}
if (typeof module !== "undefined") module.exports = { SFX_KNOBS, SFX_TABLES, SFX_LIST, SFX_USERS, SFX_FREQ_TABLE, sfxFrames, renderApu, sfxPitchInfo };
