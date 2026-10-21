const fs = require("fs"), { execFileSync } = require("child_process");
const M = require("./sfx_model.js");
const rom0 = fs.readFileSync(process.env.SMB_ROM);
const IDS = { jump: ["jump", 0], jumpbig: ["jump", 1], bump: ["bump"], stomp: ["stomp"], kick: ["kick"], pipe: ["pipe"], fire: ["fire"], flag: ["flag"],
  bf: ["bf"], coin: ["coin"], sprout: ["sprout"], vine: ["vine"], blast: ["blast"], tick: ["tick"], grab: ["grab"], oneup: ["oneup"], brick: ["brick"], flame: ["flame"] };
function compare(patches, label) {
  const rom = Buffer.from(rom0); for (const [o, v] of Object.entries(patches)) rom[o] = v;
  const truth = JSON.parse(execFileSync("python3", ["sfx_truth.py", process.env.SMB_ROM, JSON.stringify(patches)], { maxBuffer: 1 << 26 }).toString());
  const bad = [];
  for (const [k, [id, variant]] of Object.entries(IDS)) {
    const js = M.sfxFrames(id, o => rom[o], variant || 0);
    while (js.length && !js[js.length - 1].length) js.pop();
    const a = JSON.stringify(js), b = JSON.stringify(truth[k]);
    if (a !== b) {
      let f = 0; while (f < Math.max(js.length, truth[k].length) && JSON.stringify(js[f]) === JSON.stringify(truth[k][f])) f++;
      bad.push(`${k}: differs at frame ${f} js=${JSON.stringify(js[f])} real=${JSON.stringify(truth[k][f])} (js ${js.length} frames, real ${truth[k].length})`);
    }
  }
  console.log(`${label}: ${bad.length ? "MISMATCH\n  " + bad.join("\n  ") : "all 18 effects identical"}`);
  return bad.length === 0;
}
let ok = compare({}, "stock ROM");
// randomized edits within the editor's limits
let seed = 7; const rnd = n => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed % n; };
for (let round = 0; round < 40; round++) {
  const p = {}, val = {};
  for (const [k, d] of Object.entries(M.SFX_KNOBS)) {
    let v;
    if (d.kind === "pitch") { do { v = (1 + rnd(50)) * 2; } while (rom0[M.SFX_FREQ_TABLE + v + 1] === 0); }
    else if (d.kind === "len") v = (d.min || 1) + rnd((d.max || 80) - (d.min || 1) + 1);
    else if (d.kind === "npitch") v = rnd(16) | (rnd(2) << 7);
    else if (d.kind === "raw") continue;
    else v = rnd(256);
    if (d.nz && v === 0) v = d.kind === "sweep" ? 0x08 : 1;
    val[k] = v; p[d.off] = v;
  }
  for (const [k, d] of Object.entries(M.SFX_KNOBS)) if (d.kind === "when") { const L = val[d.len]; const v = 1 + rnd(Math.max(1, L - 1)); p[d.off] = v; }
  for (const [k, t] of Object.entries(M.SFX_TABLES)) for (let i = 0; i < t.n; i++) {
    const v = t.kind === "pitch" ? rnd(51) * 2 : t.kind === "npitch" ? rnd(16) : (((rnd(16) << 4) | 0x10) & 0xF0) | rnd(16);
    p[t.off + i] = v;
  }
  ok = compare(p, `random edit set ${String(round + 1).padStart(2)}`) && ok;
}
process.exit(ok ? 0 : 1);
