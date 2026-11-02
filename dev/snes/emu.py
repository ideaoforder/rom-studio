"""Headless SNES for checks: stable-retro's Snes9x core, with RAM/VRAM/CGRAM/OAM read from (and RAM written into) save states.

    pip install stable-retro
    from emu import SNES
    s = SNES(path); s.run(60, "START"); s.ram[0x19]; s.poke(0x19, 2); s.vram; s.cgram; s.oam
"""
import numpy as np
import stable_retro

BUTTONS = ["B", "Y", "SELECT", "START", "UP", "DOWN", "LEFT", "RIGHT", "A", "X", "L", "R"]
CGRAM_AT, OAM_AT = 63, 2002   # offsets inside the snapshot's PPU block (Snes9x snapshot v9; CGRAM words are big-endian there)

_live = []   # stable-retro allows one emulator per process: opening a new one closes the last
class SNES:
    def __init__(self, path):
        while _live: _live.pop().close()
        self.e = stable_retro.RetroEmulator(path); self.e.step(); self._st = None; _live.append(self)
    def close(self):
        if getattr(self, "e", None) is not None:
            del self.e; self.e = None; import gc; gc.collect()
    def run(self, frames, *buttons):
        m = np.array([b in buttons for b in BUTTONS], dtype=np.uint8)
        for _ in range(frames): self.e.set_button_mask(m, 0); self.e.step()
        self._st = None; return self
    def screen(self): return self.e.get_screen().copy()
    def _blocks(self):
        if self._st is None:
            s = self.e.get_state(); b = {}; i = s.index(b"\n") + 1
            while i + 11 <= len(s):
                ln = int(s[i + 4:i + 10]); b[s[i:i + 3].decode()] = (i + 11, ln); i += 11 + ln
            self._st = (bytearray(s), b)
        return self._st
    def block(self, name):
        s, b = self._blocks(); o, n = b[name]; return bytes(s[o:o + n])
    @property
    def ram(self): return self.block("RAM")
    @property
    def vram(self): return self.block("VRA")
    @property
    def cgram(self):
        p = self.block("PPU")[CGRAM_AT:CGRAM_AT + 512]; return bytes(p[i ^ 1] for i in range(512))  # little-endian words
    @property
    def oam(self):
        return self.block("PPU")[OAM_AT:OAM_AT + 544]
    def poke(self, addr, *vals):  # WRAM $7E:0000-$7F:FFFF (or low-RAM mirrors $0000-$1FFF)
        s, b = self._blocks(); o = b["RAM"][0] + (addr & 0x1FFFF)
        for k, v in enumerate(vals): s[o + k] = v & 255
        self.e.set_state(bytes(s)); self._st = None
    def save(self): return self.e.get_state()
    def load(self, st): self.e.set_state(st); self._st = None
    def sprites(self):
        """OAM as (x, y, tile 0-511, palette 0-7, priority, hflip, vflip, large)"""
        o = self.oam; out = []
        for i in range(128):
            x, y, t, a = o[4 * i:4 * i + 4]; hi = (o[512 + i // 4] >> (2 * (i % 4))) & 3
            out.append((x | (hi & 1) << 8, y, t | (a & 1) << 8, (a >> 1) & 7, (a >> 4) & 3, a >> 6 & 1, a >> 7, hi >> 1))
        return out
