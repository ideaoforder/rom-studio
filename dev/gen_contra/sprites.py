import sys, os, re; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from labels import off, cpu, LAB
from gfx import ROM, table, decode, bank_off
B1=lambda a: bank_off(1,a)
def s8(v): return v-256 if v>127 else v
def sprite(code):
    """-> list of (dy, tile, attr, dx) 8x16 parts, or ('small', tile, attr). Mirrors load_sprite_to_cpu_mem."""
    if code<0x80: t=off("sprite_ptr_tbl_0")+(code-1)*2
    else: t=off("sprite_ptr_tbl_1")+(code-0x80)*2
    p=B1(ROM[t]|ROM[t+1]<<8); n=ROM[p]; p+=1
    if n==0: return []
    if n==0xFE: return [("small",ROM[p],ROM[p+1])]
    parts=[]
    while n:
        if ROM[p]==0x80: p=B1(ROM[p+1]|ROM[p+2]<<8); continue
        parts.append((s8(ROM[p]),ROM[p+1],ROM[p+2],s8(ROM[p+3]))); p+=4; n-=1
    return parts
def names():
    src=open(os.path.join(os.environ["CONTRA_DIS"],"src/bank1.asm")).read()
    out={}
    for tbl,base in (("sprite_ptr_tbl_0:",1),("sprite_ptr_tbl_1:",0x80)):
        i=src.index(tbl); k=0
        for l in src[i:].split("\n")[1:]:
            l=l.strip()
            if not l.startswith(".addr"):
                if l and not l.startswith(";"): break
                continue
            m=re.search(r"- (.*)$",l); out[base+k]=m.group(1) if m else ""; k+=1
    return out
# PPU state per area: list of blocks; map ppu tile -> ("v", block, ppuaddr) or ("raw", fileoffset)
LEVELS={"L1":[3,0x13,0x19,0x1a,0x14,0x16,5],"L2":[3,4,6,0x0a,0x0f,0x10,0x11],"L3":[3,0x13,0x19,0x1a,0x14,0x16,7],"L4":[3,4,6,0x0a,0x0f,0x10,0x11,0x12],
        "L5":[3,0x13,0x19,0x1a,0x15,0x16,0x0b],"L6":[3,0x13,0x19,0x1a,0x15,0x16,0x0c],"L7":[3,0x13,0x19,0x1a,0x15,0x16,0x0d],"L8":[3,0x13,0x19,0x0e],
        "L2boss":[3,4,0x13,8],"L4boss":[3,4,0x13,8,9]}
ALIAS={0x10:0x0a}
def ppu_map(blocks, alt=None):
    tbl={e["id"]:e for e in table()}; m={}
    for b in blocks:
        e=tbl[b]
        if b in ALIAS:  # flipped copy of another block's data, written at its own address
            src=tbl[ALIAS[b]]; w,_=decode(src["off"]); base_src=w[0][0]; base_dst=ROM[e["off"]]|ROM[e["off"]+1]<<8
            for a,_v in w:
                if (a-base_src)%16==0: m[(a-base_src+base_dst)//16]=("v",ALIAS[b],a,True)
            continue
        w,_=decode(e["off"])
        for a,_v in w:
            if a<0x2000 and a%16==0: m[a//16]=("v",b,a,False)
    if alt:
        ppu,src,n=alt
        for k in range(n*2): m[ppu//16+k]=("raw",src+k*16,None,False)
    return m
def alt_entry(level):  # level 0-based
    t=off("alt_graphic_data_ptr_tbl")+5*level
    ppu=ROM[t]|ROM[t+1]<<8; addr=ROM[t+2]|ROM[t+3]<<8; n=ROM[t+4]
    return (ppu, bank_off(2,addr), n) if n else None
