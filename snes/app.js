// ROM Studio (SNES): the editor page. Game knowledge lives in profiles/*.js; formats in lib/*.js.
// State that matters (what a project saves): S.tiles, S.colors, S.mech. Everything else is view state.
"use strict";
const $ = s => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k.nodeType ? k : String(k));
  return e;
};
const STORE = "rom-studio-snes-v1";
const S = { P: null, rom: null, files: null, tiles: {}, colors: {}, mech: {}, tab: "sprites", obj: 0, frame: 0, tool: "pen",
  sel: { pal: null, idx: 1 }, zoom: 0, undo: [], redo: [], cache: new Map(), name: "" };

// ------------------------------------------------------------------ model
const fileOf = fi => S.P.gfx.files[fi];
function tileAt(fi, t) {
  const f = fileOf(fi), e = (S.tiles[f.id] || {})[t];
  if (e) return Tiles.fromHex(e);
  const k = fi + ":" + t; let px = S.cache.get(k);
  if (!px) { px = SnesRom.tile(S.files, f.id, t); S.cache.set(k, px); }
  return px;
}
function setTilePx(fi, t, x, y, v) {
  const px = tileAt(fi, t).map(r => r.slice()); if (px[y][x] === v) return false;
  px[y][x] = v; const id = fileOf(fi).id; (S.tiles[id] ||= {})[t] = Tiles.toHex(px); return true;
}
const pal = pi => S.P.palettes[pi];
const colorWord = (pi, i) => SnesRom.color({ palettes: S.P.palettes }, S.rom, S, pi, i);
const css = w => (w == null ? null : SnesColor.toCss(w));
// colour index the screen shows for a stored tile value (3bpp "hi" tiles use colours 8-15)
const shown = (part, v) => (v && part[5] & 4 ? v + 8 : v);
const objs = () => S.P.objects.filter(o => (o.category || "sprites") === (S.tab === "blocks" ? "blocks" : "sprites"));
const curObj = () => objs()[S.obj] || objs()[0];
const curFrame = () => { const o = curObj(); return o && (o.frames[S.frame] || o.frames[0]); };
function bounds(fr) {
  if (fr.w) return { x0: fr.x0 || 0, y0: fr.y0 || 0, w: fr.w, h: fr.h };
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (const p of fr.parts) { x0 = Math.min(x0, p[2]); y0 = Math.min(y0, p[3]); x1 = Math.max(x1, p[2] + 8); y1 = Math.max(y1, p[3] + 8); }
  if (x0 > x1) return { x0: 0, y0: 0, w: 8, h: 8 };
  return { x0, y0, w: x1 - x0, h: y1 - y0 };
}
// pixels of a frame, front part first (the PPU draws lower OAM entries on top; profiles list parts front to back)
function framePixels(fr) {
  const b = bounds(fr), idx = new Int16Array(b.w * b.h).fill(-1), who = new Int32Array(b.w * b.h).fill(-1);
  fr.parts.forEach((p, n) => {
    const px = tileAt(p[0], p[1]);
    for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) {
      const X = p[2] - b.x0 + x, Y = p[3] - b.y0 + y; if (X < 0 || Y < 0 || X >= b.w || Y >= b.h) continue;
      const k = Y * b.w + X; if (who[k] >= 0) continue;
      const v = px[p[5] & 2 ? 7 - y : y][p[5] & 1 ? 7 - x : x]; if (!v) continue;
      who[k] = n; idx[k] = shown(p, v);
    }
  });
  return { b, idx, who };
}
function drawFrame(canvas, fr, scale) {
  const { b, idx, who } = framePixels(fr), ctx = canvas.getContext("2d");
  canvas.width = b.w * scale; canvas.height = b.h * scale;
  const im = ctx.createImageData(b.w, b.h), bg = fr.bg != null ? SnesColor.toRgb(parseInt(fr.bg, 16)) : [32, 30, 28];
  const memo = new Map();
  for (let k = 0; k < b.w * b.h; k++) {
    let c = bg;
    if (who[k] >= 0) {
      const p = fr.parts[who[k]], key = p[4] * 16 + idx[k];
      if (!memo.has(key)) { const w = colorWord(p[4], idx[k]); memo.set(key, w == null ? [255, 0, 255] : SnesColor.toRgb(w)); }
      c = memo.get(key);
    }
    im.data.set([c[0], c[1], c[2], 255], k * 4);
  }
  if (scale === 1) { ctx.putImageData(im, 0, 0); return b; }
  const tmp = document.createElement("canvas"); tmp.width = b.w; tmp.height = b.h; tmp.getContext("2d").putImageData(im, 0, 0);
  ctx.imageSmoothingEnabled = false; ctx.drawImage(tmp, 0, 0, b.w * scale, b.h * scale);
  return b;
}

// ------------------------------------------------------------------ undo / persistence
const snap = () => JSON.stringify({ tiles: S.tiles, colors: S.colors, mech: S.mech });
function checkpoint() { S.undo.push(snap()); if (S.undo.length > 100) S.undo.shift(); S.redo = []; updButtons(); }
function restoreSnap(s) { const o = JSON.parse(s); S.tiles = o.tiles; S.colors = o.colors; S.mech = o.mech; }
function undo() { if (!S.undo.length) return; S.redo.push(snap()); restoreSnap(S.undo.pop()); changed(); }
function redo() { if (!S.redo.length) return; S.undo.push(snap()); restoreSnap(S.redo.pop()); changed(); }
function persist() {
  if (!S.P) return;
  try { localStorage.setItem(STORE, JSON.stringify({ game: S.P.id, name: S.name, tiles: S.tiles, colors: S.colors, mech: S.mech })); } catch (e) { /* private mode: no autosave */ }
  try { localStorage.setItem(STORE + "-rom", b64(S.rom)); } catch (e) { /* too big for this browser's storage; the ROM is asked for again */ }
}
const b64 = u8 => { let s = ""; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode(...u8.subarray(i, i + 0x8000)); return btoa(s); };
const unb64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
function updButtons() { $("#btnUndo").disabled = !S.undo.length; $("#btnRedo").disabled = !S.redo.length; $("#btnSave").disabled = !S.rom; $("#btnStart").disabled = !S.rom; }
function changed() { persist(); updButtons(); render(); }
let toastT;
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.hidden = false; clearTimeout(toastT); toastT = setTimeout(() => { t.hidden = true; }, 3200); }

// ------------------------------------------------------------------ opening
function useRom(bytes, state) {
  const { rom, header } = SnesRom.normalize(bytes);
  const P = window.SNES_PROFILES.find(p => SnesRom.matches(p, rom));
  if (!P) { toast("That ROM isn't one ROM Studio knows yet. The list of supported games is on the first screen."); return false; }
  S.P = P; S.rom = rom; S.files = SnesRom.decodeFiles(P, rom); S.cache.clear();
  S.tiles = state?.tiles || {}; S.colors = state?.colors || {}; S.mech = state?.mech || {}; S.name = state?.name || "";
  S.undo = []; S.redo = []; S.obj = 0; S.frame = 0; S.sel = { pal: null, idx: 1 };
  $("#romChip").textContent = P.game + (header ? " (header removed)" : ""); $("#romChip").className = "chip ok";
  $("#welcome").hidden = true; persist(); updButtons(); render(); return true;
}
// Opening is deliberately loud: on an iPad there's no console, so anything that goes wrong is said on the page.
function romMsg(text) { const m = $("#romMsg"); m.textContent = text || ""; m.hidden = !text; if (text) { $("#welcome").hidden = false; m.scrollIntoView({ block: "nearest" }); } }
async function romBytes(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (bytes[0] === 0x50 && bytes[1] === 0x4B) { // a .zip: use the ROM inside it
    const z = await unzip(bytes.buffer), name = Object.keys(z).find(n => /\.(sfc|smc|swc|fig|bin)$/i.test(n)) || Object.keys(z).sort((a, b) => z[b].length - z[a].length)[0];
    if (!name) throw new Error("That .zip is empty.");
    if (z["config.json"]) return { project: true };
    return { bytes: z[name], name };
  }
  return { bytes, name: file.name };
}
async function openRom(file) {
  romMsg("");
  let got;
  try { got = await romBytes(file); } catch (e) { romMsg(`Couldn't read "${file.name}": ${e.message || e}`); return; }
  if (got.project) return openProject(file);
  const bytes = got.bytes, { rom, header } = SnesRom.normalize(bytes);
  if (!window.SNES_PROFILES.some(p => SnesRom.matches(p, rom))) {
    const want = window.SNES_PROFILES.map(p => `${p.game}: ${p.rom.size.toLocaleString()} bytes`).join("; ");
    romMsg(`"${got.name}" isn't a ROM ROM Studio knows yet. It's ${bytes.length.toLocaleString()} bytes${header ? " (with a copier header)" : ""}, CRC32 ${crc32(rom).toString(16).toUpperCase().padStart(8, "0")}. Supported: ${want}, CRC32 B19ED489.`);
    return;
  }
  let keep = null;
  try { const saved = JSON.parse(localStorage.getItem(STORE) || "null"); const P = window.SNES_PROFILES.find(p => SnesRom.matches(p, SnesRom.normalize(bytes).rom)); if (saved && P && saved.game === P.id) keep = saved; } catch (e) { /* ignore */ }
  try {
    if (useRom(bytes, keep) && keep && (Object.keys(keep.tiles || {}).length || Object.keys(keep.colors || {}).length)) toast("Picked up your saved edits for this game.");
  } catch (e) { console.error(e); romMsg(`Opened the ROM, but something broke while setting up: ${e.message || e}`); }
}
function startOver() {
  if (!S.P) return;
  checkpoint(); S.tiles = {}; S.colors = {}; S.mech = {}; S.name = ""; changed();
  toast("Started over. Undo brings your work back.");
}
async function openProject(file) {
  const buf = await file.arrayBuffer();
  try {
    if (/\.json$/i.test(file.name)) {
      const o = JSON.parse(new TextDecoder().decode(buf));
      if (!S.rom) { toast("Open the ROM first, then the backup."); return; }
      checkpoint(); S.tiles = o.state?.tiles || o.tiles || {}; S.colors = o.state?.colors || o.colors || {}; S.mech = o.state?.mech || o.mech || {}; changed(); return;
    }
    const z = await unzip(buf), cfg = JSON.parse(new TextDecoder().decode(z["config.json"]));
    const orig = z[cfg.original] || S.rom;
    if (!orig) { toast("This project has no ROM inside. Open the ROM first, then the project."); return; }
    if (useRom(orig, { ...cfg.state, name: cfg.name })) toast(`Opened ${cfg.name || "project"}`);
  } catch (e) { console.error(e); toast("Couldn't read that project: " + e.message); }
}

// ------------------------------------------------------------------ download
const fileSafe = s => s.trim().replace(/[^\w\- ]+/g, "").replace(/\s+/g, "-").toLowerCase().slice(0, 60);
function download() {
  $("#dlName").value = S.name || `${S.P.id}-hack`;
  const prev = () => { const b = fileSafe($("#dlName").value) || "rom-hack"; $("#dlFiles").textContent = `${b}.zip · inside: ${b}.sfc (play this), ${b}.ips, your project files and the original ROM`; };
  $("#dlName").oninput = prev; prev(); $("#dlDlg").showModal();
}
async function doDownload() {
  const base = fileSafe($("#dlName").value) || "rom-hack"; S.name = $("#dlName").value.trim(); persist();
  let out;
  try { out = SnesRom.build(S.P, S.rom, S, S.files); } catch (e) { toast(e.message); return; }
  const enc = new TextEncoder(), state = { tiles: S.tiles, colors: S.colors, mech: S.mech };
  const cfg = { format: "rom-studio-snes/1", game: S.P.id, name: S.name, original: "original.sfc", profile: "profile.json", output: `${base}.sfc`, state };
  const blob = zip([
    { name: "config.json", data: enc.encode(JSON.stringify(cfg, null, 1)) },
    { name: "profile.json", data: enc.encode(JSON.stringify(S.P)) },
    { name: "original.sfc", data: S.rom },
    { name: `${base}.sfc`, data: out },
    { name: `${base}.ips`, data: ips(S.rom, out) },
  ]);
  const a = el("a", { href: URL.createObjectURL(blob), download: `${base}.zip` }); document.body.append(a); a.click(); a.remove();
  toast(`Saved ${base}.zip`);
}

// ------------------------------------------------------------------ rendering
function render() {
  $("#viewArt").hidden = !S.P || S.tab === "mech"; $("#viewMech").hidden = !S.P || S.tab !== "mech";
  document.querySelectorAll("#tabs button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.tab === S.tab)));
  if (!S.P) return;
  if (S.tab === "mech") return renderMech();
  renderList(); renderFrames(); renderPainter(); renderPalettes();
}
const edited = o => o.frames.some(f => f.parts.some(p => (S.tiles[fileOf(p[0]).id] || {})[p[1]]));
function renderList() {
  const box = $("#objList"); box.replaceChildren(); let group = null;
  $("#listTitle").textContent = S.tab === "blocks" ? "Blocks" : "Sprites";
  objs().forEach((o, i) => {
    if (o.group !== group) { group = o.group; box.append(el("h3", {}, group)); }
    const c = el("canvas"); drawFrame(c, o.frames[o.thumb || 0], 1);
    const s = Math.min(1, 28 / Math.max(c.width, c.height)); c.style.width = c.width * s + "px"; c.style.height = c.height * s + "px";
    box.append(el("button", { type: "button", "aria-current": String(i === S.obj), onclick: () => { S.obj = i; S.frame = 0; render(); } },
      c, el("span", {}, o.name), edited(o) ? el("span", { class: "dot", title: "edited" }) : null));
  });
  $("#listHint").textContent = `${objs().length}`;
}
function renderFrames() {
  const o = curObj(), box = $("#frames"); box.replaceChildren(); if (!o) return;
  $("#objTitle").textContent = o.name;
  $("#frameHint").textContent = o.note || `${o.frames.length} frame${o.frames.length === 1 ? "" : "s"}`;
  o.frames.forEach((f, i) => {
    const c = el("canvas"), b = bounds(f), sc = Math.max(1, Math.min(2, Math.floor(64 / Math.max(b.w, b.h)))); drawFrame(c, f, sc);
    if (c.width > 96) { c.style.width = "96px"; c.style.height = (c.height * 96 / c.width) + "px"; }
    box.append(el("button", { type: "button", "aria-current": String(i === S.frame), onclick: () => { S.frame = i; render(); } }, c, el("span", {}, f.name)));
  });
}
function autoZoom(b) { return Math.max(1, Math.min(12, Math.floor(Math.min(680 / b.w, 520 / b.h)))); }
function renderPainter() {
  const fr = curFrame(); if (!fr) return;
  const b = bounds(fr), z = S.zoom || autoZoom(b), seg = $("#zoomSeg"); seg.replaceChildren();
  for (const n of [...new Set([autoZoom(b), 1, 2, 4, 8])].sort((a, c) => a - c)) seg.append(el("button", { type: "button", "aria-pressed": String(n === z), onclick: () => { S.zoom = n; renderPainter(); } }, `${n}×`));
  drawFrame($("#painter"), fr, z);
}
function framePals(fr) { return [...new Set(fr.parts.map(p => p[4]))]; }
function renderPalettes() {
  const fr = curFrame(), box = $("#palRows"); box.replaceChildren(); if (!fr) return;
  const pis = framePals(fr); if (S.sel.pal == null || !pis.includes(S.sel.pal)) S.sel.pal = pis[0];
  for (const pi of pis) {
    const p = pal(pi), row = el("div", { class: "prow" }, el("span", { class: "name", title: p.label }, p.label));
    for (let i = 0; i < 16; i++) {
      const w = colorWord(pi, i), usable = i > 0 && w != null;
      row.append(el("button", { type: "button", class: "sw" + (i === 0 ? " clear" : "") + (w == null ? " off" : "") + (p.colors[i] == null && i ? " locked" : ""),
        style: i && w != null ? `background:${css(w)}` : null, "data-pi": i && w != null ? pi : null, "data-i": i, "aria-pressed": String(S.sel.pal === pi && S.sel.idx === i),
        title: i === 0 ? "See-through (eraser)" : w == null ? "Not used here" : p.colors[i] == null ? "Set by the game's code (can paint with it, can't change it)" : `Colour ${i}`,
        onclick: () => { if (!usable && i) return; S.sel = { pal: pi, idx: i }; renderPalettes(); } }));
    }
    box.append(row);
  }
  const w = S.sel.idx ? colorWord(S.sel.pal, S.sel.idx) : null, off = S.sel.idx ? pal(S.sel.pal).colors[S.sel.idx] : null;
  $("#colorIn").disabled = off == null; $("#colorIn").value = w != null ? css(w) : "#000000";
  $("#colorOut").textContent = S.sel.idx === 0 ? "See-through" : w == null ? "" : `$${SnesColor.hex(w)}` + (off == null ? " · fixed" : "");
  $("#palHint").textContent = `${pis.length} palette${pis.length === 1 ? "" : "s"}`;
}

// ------------------------------------------------------------------ painting
function hit(ev) {
  const c = $("#painter"), r = c.getBoundingClientRect(), fr = curFrame(), b = bounds(fr);
  const X = Math.floor((ev.clientX - r.left) * b.w / r.width), Y = Math.floor((ev.clientY - r.top) * b.h / r.height);
  if (X < 0 || Y < 0 || X >= b.w || Y >= b.h) return null;
  // the part you can see at this pixel; on a see-through pixel, the front-most part that covers it
  const vis = framePixels(fr).who[Y * b.w + X], order = vis >= 0 ? [fr.parts[vis], ...fr.parts] : fr.parts;
  for (const p of order) {
    const x = X + b.x0 - p[2], y = Y + b.y0 - p[3];
    if (x < 0 || y < 0 || x > 7 || y > 7) continue;
    const tx = p[5] & 1 ? 7 - x : x, ty = p[5] & 2 ? 7 - y : y, v = tileAt(p[0], p[1])[ty][tx];
    return { p, tx, ty, v };
  }
  return null;
}
function paintAt(ev) {
  const h = hit(ev); if (!h) return false;
  const { p } = h, bpp = fileOf(p[0]).bpp;
  if (S.tool === "pick") { if (h.v) { S.sel = { pal: p[4], idx: shown(p, h.v) }; S.tool = "pen"; renderTools(); renderPalettes(); } return false; }
  let v = S.sel.idx;
  if (v && bpp === 3) { const hi = !!(p[5] & 4); if ((v >= 8) !== hi) { toast(hi ? "This tile uses colours 9–15. Pick one of those." : "This tile uses colours 1–7. Pick one of those."); return false; } v &= 7; }
  if (S.tool === "fill") return fillTile(p, h.tx, h.ty, v);
  return setTilePx(p[0], p[1], h.tx, h.ty, v);
}
function fillTile(p, x, y, v) {
  const px = tileAt(p[0], p[1]).map(r => r.slice()), from = px[y][x]; if (from === v) return false;
  const st = [[x, y]];
  while (st.length) { const [a, c] = st.pop(); if (a < 0 || c < 0 || a > 7 || c > 7 || px[c][a] !== from) continue; px[c][a] = v; st.push([a + 1, c], [a - 1, c], [a, c + 1], [a, c - 1]); }
  (S.tiles[fileOf(p[0]).id] ||= {})[p[1]] = Tiles.toHex(px); return true;
}
let stroke = null;
function painterEvents() {
  const c = $("#painter");
  c.addEventListener("pointerdown", ev => { if (!S.P) return; ev.preventDefault(); c.setPointerCapture(ev.pointerId); stroke = { before: snap(), any: false }; if (paintAt(ev)) { stroke.any = true; renderPainter(); } });
  c.addEventListener("pointermove", ev => {
    const h = S.P && hit(ev); $("#tileHint").textContent = h ? `${fileOf(h.p[0]).id} tile $${h.p[1].toString(16).toUpperCase().padStart(2, "0")} · ${pal(h.p[4]).label}` : "";
    if (stroke && S.tool === "pen" && paintAt(ev)) { stroke.any = true; renderPainter(); }
  });
  const end = () => { if (!stroke) return; if (stroke.any) { S.undo.push(stroke.before); if (S.undo.length > 100) S.undo.shift(); S.redo = []; changed(); } stroke = null; };
  c.addEventListener("pointerup", end); c.addEventListener("pointercancel", end);
}
function renderTools() { document.querySelectorAll("#toolSeg button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.tool === S.tool))); }
// While the colour picker is open, show the colour everywhere it's used without saving or adding undo steps;
// the picker's "change" (closing it, or letting go) commits it as one undo step.
let preview = null; // {off, had, was}: the colour edit as it was before the preview
function previewColor(hex) {
  const off = pal(S.sel.pal).colors[S.sel.idx]; if (off == null) return;
  if (!preview || preview.off !== off) { endPreview(); preview = { off, had: off in S.colors, was: S.colors[off] }; }
  S.colors[off] = SnesColor.hex(SnesColor.fromCss(hex));
  if (!previewColor.raf) previewColor.raf = requestAnimationFrame(() => { previewColor.raf = 0; renderPainter(); renderFrames(); renderSwatches(); renderList(); });
}
function endPreview() {
  if (!preview) return;
  if (preview.had) S.colors[preview.off] = preview.was; else delete S.colors[preview.off];
  preview = null;
}
function renderSwatches() { // recolour the palette swatches in place (re-rendering would reset the open picker)
  document.querySelectorAll("#palRows .sw[data-pi]").forEach(b => { const w = colorWord(+b.dataset.pi, +b.dataset.i); if (w != null) b.style.background = css(w); });
  const w = colorWord(S.sel.pal, S.sel.idx); if (w != null) $("#colorOut").textContent = `$${SnesColor.hex(w)}`;
}
function setColor(hex) {
  endPreview();
  const off = pal(S.sel.pal).colors[S.sel.idx]; if (off == null) return;
  const w = SnesColor.fromCss(hex); if (w === colorWord(S.sel.pal, S.sel.idx)) return;
  checkpoint(); if (w === SnesColor.read(S.rom, off)) delete S.colors[off]; else S.colors[off] = SnesColor.hex(w); changed();
}

// ------------------------------------------------------------------ mechanics
const mval = k => Mechanics.value(k, S.rom, S.mech);
function setMech(id, v) { checkpoint(); S.mech[id] = v; changed(); }
function renderMech() {
  const list = $("#mechList"), pre = $("#mechPresets"); list.replaceChildren(); pre.replaceChildren();
  const knobs = S.P.mechanics || [];
  $("#mechHint").textContent = knobs.length ? S.P.game : "No mechanics for this game yet";
  pre.append(el("span", { class: "label" }, "Presets"));
  for (const [name, vals] of Object.entries(S.P.mechanics_presets || {}))
    pre.append(el("button", { type: "button", class: "btn", onclick: () => { checkpoint(); S.mech = { ...vals }; changed(); toast(`${name} mechanics`); } }, name));
  let section = null;
  for (const k of knobs) {
    if (k.section && k.section !== section) { section = k.section; list.append(el("h3", {}, section)); }
    const v = mval(k); let ctl;
    if (k.kind === "toggle") ctl = el("div", { class: "seg", role: "group", "aria-label": k.label },
      el("button", { type: "button", "aria-pressed": String(!v), onclick: () => setMech(k.id, false) }, "Off"),
      el("button", { type: "button", "aria-pressed": String(v), onclick: () => setMech(k.id, true) }, "On"));
    else if (k.kind === "percent") ctl = el("div", { class: "seg", role: "group", "aria-label": k.label },
      ...k.values.map(x => el("button", { type: "button", "aria-pressed": String(v === x), onclick: () => setMech(k.id, x) }, (k.labels || {})[x] || (x === k.default ? "normal" : `${x}%`))));
    else if (k.kind === "choice") ctl = el("select", { "aria-label": k.label, onchange: e => setMech(k.id, Number(e.target.value)) },
      ...k.options.map(o => el("option", { value: o.value, selected: v === o.value || null }, o.label)));
    else ctl = el("div", { class: "mnum" },
      el("button", { type: "button", class: "btn", "aria-label": `${k.label}: less`, disabled: v <= k.min, onclick: () => setMech(k.id, Math.max(k.min, v - 1)) }, "−"),
      el("output", {}, String(v)),
      el("button", { type: "button", class: "btn", "aria-label": `${k.label}: more`, disabled: v >= k.max, onclick: () => setMech(k.id, Math.min(k.max, v + 1)) }, "+"));
    list.append(el("div", { class: "mrow" }, el("span", {}, k.label), ctl, el("p", { class: "mhelp" }, k.help || "")));
  }
}

// ------------------------------------------------------------------ wiring
function init() {
  $("#gamesList").replaceChildren("Supported: ", ...window.SNES_PROFILES.flatMap((p, i) => [i ? ", " : "", el("strong", {}, p.game), ` (${p.rom.size.toLocaleString()} bytes, no header)`]));
  $("#btnRom").onclick = () => $("#fRom").click(); $("#btnProj").onclick = () => $("#fProj").click();
  // read the file before clearing the input (iOS can drop the File once the input is reset)
  $("#fRom").onchange = async e => { const f = e.target.files[0]; if (f) await openRom(f); e.target.value = ""; };
  $("#fProj").onchange = async e => { const f = e.target.files[0]; if (f) await openProject(f); e.target.value = ""; };
  $("#btnUndo").onclick = undo; $("#btnRedo").onclick = redo; $("#btnSave").onclick = download; $("#btnStart").onclick = startOver;
  $("#dlDlg").addEventListener("close", () => { if ($("#dlDlg").returnValue === "ok") doDownload(); });
  document.querySelectorAll("#tabs button").forEach(b => { b.onclick = () => { S.tab = b.dataset.tab; S.obj = 0; S.frame = 0; S.zoom = 0; render(); }; });
  document.querySelectorAll("#toolSeg button").forEach(b => { b.onclick = () => { S.tool = b.dataset.tool; renderTools(); }; });
  $("#colorIn").addEventListener("input", e => previewColor(e.target.value));
  $("#colorIn").addEventListener("change", e => setColor(e.target.value));
  document.addEventListener("keydown", e => {
    if (e.target.matches("input, textarea, select")) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? redo() : undo(); }
  });
  painterEvents();
  try { // reopen the last ROM and edits
    const saved = JSON.parse(localStorage.getItem(STORE) || "null"), r = localStorage.getItem(STORE + "-rom");
    if (saved && r) useRom(unb64(r), saved);
  } catch (e) { /* nothing saved */ }
  render();
  // a ROM inserted on the landing page (../index.html) opens as if it had been picked here
  if (window.RomHandoff) RomHandoff.take().then(f => { if (f) openRom(f); });
}
init();
