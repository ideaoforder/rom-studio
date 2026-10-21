const fs = require("fs"), { execFileSync } = require("child_process");
const M = require("./music_model.js");
const rom = fs.readFileSync(process.env.SMB_ROM);
const FR = +process.argv[2] || 900;
const reqs = {};
for (const s of M.SONGS) reqs[s.id] = s.req.area ? [0xFB, s.req.area] : [0xFC, s.req.event];
reqs.sfx_jump = [0xFF, 0x80]; reqs.sfx_coin = [0xFE, 0x01]; reqs.sfx_brick = [0xFD, 0x01];
// 1) JS 6502 vs py65
const truth = JSON.parse(execFileSync("python3", ["music_truth.py", process.env.SMB_ROM, JSON.stringify(reqs), String(FR)], { maxBuffer: 1 << 28 }).toString());
let bad = [];
for (const [k, [q, v]] of Object.entries(reqs)) {
  const js = M.runSoundEngine(rom, q === 0xFB ? { area: v } : q === 0xFC ? { event: v } : { sfx: [q, v] }, FR);
  if (q !== 0xFB && q !== 0xFC) continue;
  if (JSON.stringify(js) !== JSON.stringify(truth[k])) { let f = 0; while (JSON.stringify(js[f]) === JSON.stringify(truth[k][f])) f++; bad.push(`${k}@${f}`); }
}
console.log(`JS 6502 vs py65 over ${FR} frames, ${Object.keys(reqs).length - 3} songs:`, bad.length ? "MISMATCH " + bad.join(" ") : "identical");
// 2) decode -> compile -> replay
const dec = M.decodeMusic(o => rom[o]);
console.log("patterns:", dec.patterns.length, "| inherited-length starts:", dec.patterns.filter(p => (p.melody[0] || {}).inherited || (p.bass && (p.bass[0] || {}).inherited)).map(p => p.id).join(",") || "none",
  "| odd notes:", dec.patterns.some(p => p.melody.some(e => e.n & 1)));
const comp = M.compileMusic(dec);
console.log("compiled size:", comp.used, "of", comp.size, "| errors:", comp.errors.join("; ") || "none");
const rom2 = Buffer.from(rom); rom2.set(comp.bytes, M.fileOf(M.SND.regionStart));
let bad2 = [];
for (const s of M.SONGS) {
  const a = M.runSoundEngine(rom, s.req, FR), b = M.runSoundEngine(rom2, s.req, FR);
  if (JSON.stringify(a) !== JSON.stringify(b)) { let f = 0; while (JSON.stringify(a[f]) === JSON.stringify(b[f])) f++; bad2.push(`${s.id}@${f} orig=${JSON.stringify(a[f])} new=${JSON.stringify(b[f])}`); }
}
console.log("recompiled music plays identically:", bad2.length ? "NO\n  " + bad2.join("\n  ") : "yes, all " + M.SONGS.length + " songs");
