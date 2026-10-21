# Runs SMB's real sound engine on a 6502 emulator and logs APU writes per frame.
import json, sys
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

QUEUES = {  # effect id -> (queue address, value)
 "jump": (0xFF, 0x80), "jumpbig": (0xFF, 0x01), "bump": (0xFF, 0x02), "stomp": (0xFF, 0x04), "kick": (0xFF, 0x08),
 "pipe": (0xFF, 0x10), "fire": (0xFF, 0x20), "flag": (0xFF, 0x40),
 "bf": (0xFE, 0x80), "coin": (0xFE, 0x01), "sprout": (0xFE, 0x02), "vine": (0xFE, 0x04), "blast": (0xFE, 0x08),
 "tick": (0xFE, 0x10), "grab": (0xFE, 0x20), "oneup": (0xFE, 0x40),
 "brick": (0xFD, 0x01), "flame": (0xFD, 0x02)}

def run(rom, sfx, frames=700):
    prg = rom[0x10:0x8010]
    mem = ObservableMemory()
    for i, b in enumerate(prg): mem[0x8000 + i] = b
    log = []
    mem.subscribe_to_write(range(0x4000, 0x4018), lambda a, v: log.append([a, v]))
    mpu = MPU(memory=mem); mem[0x0770] = 1  # OperMode: in game
    q, v = QUEUES[sfx]
    out = []
    for f in range(frames):
        if f == 0: mem[q] = v
        log.clear()
        mpu.sp = 0xFF; mem[0x1FF] = 0xFF; mem[0x1FE] = 0xEF; mpu.sp = 0xFD  # return to $FFF0
        mpu.pc = 0xF2D0
        n = 0
        while mpu.pc != 0xFFF0:
            mpu.step(); n += 1
            if n > 200000: raise RuntimeError("runaway")
        w = [x for x in log if x[0] not in (0x4017, 0x4011, 0x4010, 0x4012, 0x4013)]
        if w and w[0] == [0x4015, 0x0F]: w = w[1:]  # SndOn's per-frame enable
        out.append(w)
    while out and not out[-1]: out.pop()
    return out

if __name__ == "__main__":
    rom = bytearray(open(sys.argv[1], "rb").read())
    patches = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    for off, val in patches.items(): rom[int(off)] = val
    res = {k: run(rom, k) for k in QUEUES}
    print(json.dumps(res))
