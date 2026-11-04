"""Python twin of snes/lib/clz.js: the LZ graphics compression of Mega Man 7 (also Rockman & Forte, Mega Man X2/X3).
A control byte gives 8 flags, high bit first: 0 = one literal byte, 1 = two bytes LLLLLLDD DDDDDDDD = copy L (1-63)
bytes from D (1-1023) back in the output. There's no end marker: the game's table gives the unpacked size."""
def decode(r, off, size):
    out = bytearray(); i = off; ctl = r[i]; i += 1; n = 8
    while len(out) < size:
        if ctl & 0x80 == 0: out.append(r[i]); i += 1
        else:
            d = (r[i] & 3) << 8 | r[i + 1]; L = r[i] >> 2; i += 2
            for _ in range(L): out.append(out[-d])
        if len(out) >= size: break
        ctl = (ctl << 1) & 255; n -= 1
        if n == 0: ctl = r[i]; i += 1; n = 8
    return bytes(out[:size]), i - off
def matches(d):
    """for each position: (longest match length, its distance), nearest first on ties (hash chains on 3-byte keys)"""
    n = len(d); chains = {}; out = []
    for i in range(n):
        bl, bd = 0, 0; m = min(63, n - i)
        if i + 2 < n:
            key = d[i:i + 3]; c = chains.get(key)
            if c:
                for s in reversed(c):
                    if i - s > 1023: break
                    k = 0
                    while k < m and d[s + k] == d[i + k]: k += 1
                    if k > bl: bl, bd = k, i - s
                    if k == m: break
            chains.setdefault(key, []).append(i)
        out.append((bl, bd))
    return out
def encode(d):
    """optimal for this format (fewest bits: a literal is 9, a copy 17), and deterministic, so the browser and Ruby
    produce the same bytes: from the end, each position takes the cheapest of a literal or a copy of 3..longest bytes
    (longer wins a tie with a shorter copy; a literal wins a tie with a copy)"""
    n = len(d); mt = matches(d); cost = [0] * (n + 1); pick = [0] * n
    for i in range(n - 1, -1, -1):
        best, choice = 9 + cost[i + 1], 0
        for L in range(mt[i][0], 2, -1):
            c = 17 + cost[i + L]
            if c < best: best, choice = c, L
        cost[i] = best; pick[i] = choice
    out = bytearray(); i = 0; ctl_at = -1; bits = 8
    while i < n:
        if bits == 8: ctl_at = len(out); out.append(0); bits = 0
        L = pick[i]
        if L:
            out[ctl_at] |= 0x80 >> bits; dd = mt[i][1]; out += bytes([L << 2 | dd >> 8, dd & 255]); i += L
        else:
            out.append(d[i]); i += 1
        bits += 1
    return bytes(out)
