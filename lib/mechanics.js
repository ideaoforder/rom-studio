// Mechanics knobs -> byte patches. Pure functions of (profile.mechanics, rom bytes, settings), shared by the editors.
// Knob kinds (see CONTRIBUTING.md): toggle {patches}, number {offset, also, bias, min, max},
// choice {offset, options:[{value,label}]} or patch-set choice {options:[{value,label,patches}]},
// percent {values, bytes:[{offset,n,mode,signed,min,max,skip}], words:[{lo,hi,mode,signed,min,max}]}.
// `install` patches (e.g. a hook in free space) are written first whenever the knob is away from its default.
(function (root) {
  function value(k, rom, settings) {
    const v = settings[k.id];
    if (k.kind === "toggle") return !!v;
    if (k.kind === "percent") return v ?? k.default;
    if (k.offset == null) return v ?? k.default;
    if (v != null || k.install) return v ?? k.default;
    return rom ? rom[k.offset] - (k.bias || 0) : null;
  }
  function patches(knobs, rom, settings) {
    const out = {}; if (!rom || !knobs) return out;
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v)), cur = o => (o in out ? out[o] : rom[o]);
    const put = pts => { for (const pt of pts || []) pt.hex.match(/../g).forEach((h, i) => { out[pt.offset + i] = parseInt(h, 16); }); };
    const away = k => k.kind === "toggle" ? !!settings[k.id] : settings[k.id] != null && settings[k.id] !== k.default;
    for (const k of knobs) if (k.install && away(k)) put(k.install);
    for (const k of knobs) {
      const v = settings[k.id];
      if (k.kind === "choice" && k.offset == null) continue;
      if (k.kind === "number" || k.kind === "choice") {
        if (v == null || (k.install && v === k.default)) continue;
        const b = ((k.kind === "number" ? clamp(v, k.min, k.max) : v) + (k.bias || 0)) & 255;
        for (const o of [k.offset, ...(k.also || [])]) if (k.install || b !== rom[o]) out[o] = b;
      } else if (k.kind === "percent") {
        if (v == null || v === k.default) continue;
        const f = v / 100, scale = (x, mode) => mode === "div" ? x / f : mode === "sqrt" ? x * Math.sqrt(f) : x * f;
        for (const b of k.bytes || []) for (let i = 0; i < b.n; i++) {
          const o = b.offset + i, base = cur(o);
          if ((b.skip || []).includes(base)) continue;
          const neg = b.signed && base >= 128, mag = neg ? 256 - base : base;
          const nv = k.max_value != null && v === k.max_value ? (b.max ?? 255) : clamp(Math.round(scale(mag, b.mode)), b.min ?? 0, b.max ?? 255);
          out[o] = neg ? (256 - nv) & 255 : nv;
        }
        for (const w of k.words || []) {
          let base = cur(w.hi) * 256 + cur(w.lo); if (!base) continue;
          const neg = w.signed && base >= 0x8000; if (neg) base = 0x10000 - base;
          let nv = clamp(Math.round(scale(base, w.mode)), w.min ?? 1, w.max ?? 0x7FFF);
          if (neg) nv = (0x10000 - nv) & 0xFFFF;
          out[w.lo] = nv & 255; out[w.hi] = nv >> 8;
        }
      }
    }
    for (const k of knobs) {
      if (k.kind === "toggle" && settings[k.id]) put(k.patches);
      if (k.kind === "choice" && k.offset == null) { const o = k.options.find(x => x.value === value(k, rom, settings)); if (o) put(o.patches); }
    }
    return out;
  }
  root.Mechanics = { value, patches };
})(typeof window !== "undefined" ? window : globalThis);
