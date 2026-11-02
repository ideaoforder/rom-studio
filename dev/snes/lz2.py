"""Python twin of snes/lib/lz2.js (decode + the same greedy encoder), for generators and checks."""
def lorom(a): return ((a >> 16) & 0x7F) * 0x8000 + (a & 0x7FFF)
def decode(r, off):
    out = bytearray(); i = off
    while True:
        b = r[i]; i += 1
        if b == 0xFF: return bytes(out), i - off
        if b & 0xE0 == 0xE0: cmd = (b << 3) & 0xE0; n = ((b & 3) << 8 | r[i]) + 1; i += 1
        else: cmd = b & 0xE0; n = (b & 0x1F) + 1
        if cmd == 0: out += r[i:i + n]; i += n
        elif cmd == 0x20: out += bytes([r[i]]) * n; i += 1
        elif cmd == 0x40: out += bytes(r[i + (k & 1)] for k in range(n)); i += 2
        elif cmd == 0x60: out += bytes((r[i] + k) & 255 for k in range(n)); i += 1
        else:
            src = r[i] << 8 | r[i + 1]; i += 2
            for k in range(n): out.append(out[src + k])

def encode(d):
    n = len(d); out = bytearray(); lit = bytearray(); chains = {}
    def hdr(cmd, ln):
        ln -= 1
        return bytes([cmd | ln]) if ln < 32 else bytes([0xE0 | (cmd >> 3) | (ln >> 8), ln & 255])
    def flush():
        while lit:
            k = min(len(lit), 1024); out.extend(hdr(0, k)); out.extend(lit[:k]); del lit[:k]
    i = 0
    def index(p):
        if p + 2 < n: chains.setdefault(d[p:p + 3], []).append(p)
    while i < n:
        m = min(1024, n - i); best = (0, None)
        k = 1
        while k < m and d[i + k] == d[i]: k += 1
        cands = [(k, 0x20, bytes([d[i]]))]
        if m >= 2:
            k = 2
            while k < m and d[i + k] == d[i + (k & 1)]: k += 1
            cands.append((k, 0x40, bytes(d[i:i + 2])))
        k = 1
        while k < m and d[i + k] == (d[i] + k) & 255: k += 1
        cands.append((k, 0x60, bytes([d[i]])))
        bl, bs = 0, 0
        for s in chains.get(d[i:i + 3], ()):
            if s > 0xFFFF: break
            k = 0
            while k < m and d[s + k] == d[i + k]: k += 1
            if k > bl: bl, bs = k, s
            if k == m: break
        if bl: cands.insert(0, (bl, 0x80, bytes([bs >> 8, bs & 255])))
        for ln, cmd, arg in cands:
            sav = ln - (1 if ln <= 32 else 2) - len(arg)
            if sav > best[0]: best = (sav, (ln, cmd, arg))
        if best[1] is None:
            lit.append(d[i]); index(i); i += 1; continue
        ln, cmd, arg = best[1]; flush(); out.extend(hdr(cmd, ln)); out.extend(arg)
        for p in range(i, i + ln): index(p)
        i += ln
    flush(); out.append(0xFF); return bytes(out)
