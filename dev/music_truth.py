import json, sys
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory
def run(rom, q, v, frames):
    mem = ObservableMemory()
    for i, b in enumerate(rom[0x10:0x8010]): mem[0x8000 + i] = b
    log = []
    mem.subscribe_to_write(range(0x4000, 0x4018), lambda a, x: log.append([a, x]))
    mpu = MPU(memory=mem); mem[0x0770] = 1
    out = []
    for f in range(frames):
        if f == 0: mem[q] = v
        log.clear(); mpu.sp = 0xFF; mem[0x1FF] = 0xFF; mem[0x1FE] = 0xEF; mpu.sp = 0xFD; mpu.pc = 0xF2D0
        n = 0
        while mpu.pc != 0xFFF0:
            mpu.step(); n += 1
            if n > 200000: raise RuntimeError("runaway")
        w = [x for x in log if x[0] not in (0x4017, 0x4011, 0x4010, 0x4012, 0x4013)]
        if w and w[0] == [0x4015, 0x0F]: w = w[1:]
        out.append(w)
    return out
if __name__ == "__main__":
    rom = bytearray(open(sys.argv[1], "rb").read()); reqs = json.loads(sys.argv[2]); frames = int(sys.argv[3])
    print(json.dumps({k: run(rom, q, v, frames) for k, (q, v) in reqs.items()}))
