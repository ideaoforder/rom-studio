import sys, os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); from labels import off, cpu, LAB
ROM=open(os.environ["CONTRA_ROM"],"rb").read()
def bank_off(bank, addr): return 0x10+bank*0x4000+(addr-(0xC000 if bank==7 else 0x8000))
def table():
    t=off("graphic_data_ptr_tbl"); out=[]
    for i in range(0x1b):
        lo,hi,b=ROM[t+3*i:t+3*i+3]; addr=lo|hi<<8; bank=b&7 or 7
        out.append({"id":i,"addr":addr,"bank":bank,"flip":bool(b&0x80),"off":bank_off(bank,addr)})
    return out
def decode(o, flip=False):
    """returns (writes: list of (ppu_addr, byte, src_kind)), end offset). Mirrors write_graphic_data_to_ppu."""
    p=o; ppu=ROM[p]|ROM[p+1]<<8; p+=2
    if flip: p+=2
    writes=[]; runs=[]
    while True:
        b=ROM[p]
        if b==0xFF: p+=1; break
        if b==0x7F: ppu=ROM[p+1]|ROM[p+2]<<8; p+=3; continue
        if b<0x80:
            v=ROM[p+1]; 
            for _ in range(b): writes.append((ppu,v)); ppu+=1
            p+=2
        else:
            n=b&0x7F
            for k in range(n): writes.append((ppu,ROM[p+1+k])); ppu+=1
            p+=1+n
    return writes, p
if __name__=="__main__":
    for e in table():
        w,end=decode(e["off"],e["flip"])
        ppus=[a for a,_ in w]
        print(f'{e["id"]:02x} bank{e["bank"]} {e["addr"]:04x} flip={int(e["flip"])} comp={end-e["off"]} out={len(w)} ppu {min(ppus) if ppus else 0:04x}-{max(ppus)+1 if ppus else 0:04x}')
