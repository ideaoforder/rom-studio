import sys, os, re; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from render import *; from labels import off
HDR=off("level_headers")
def hdr(L): return ROM[HDR+L*32:HDR+L*32+32]
def bank_ptr(bank, lo, hi): return bank_off(bank, lo|hi<<8)
def screen_ptrs(L):
    src=open(os.path.join(os.environ.get("CONTRA_DIS",os.path.join(os.path.dirname(os.path.abspath(__file__)),"../dis")),"src/bank2.asm")).read().split("\n")
    i=src.index(f"level_{L+1}_supertiles_screen_ptr_table:"); out=[]
    for l in src[i+1:]:
        m=re.match(r"\s*\.addr (level_\d+_supertiles_screen_\w+)",l)
        if not m:
            if l.strip()=="" or l.strip().startswith(";"): continue
            break
        out.append(off(m.group(1)))
    return out
def decode_screen(p, vertical):
    n=0x40 if vertical else 0x38; out=[]
    while len(out)<n:
        b=ROM[p]; p+=1
        if b<0x80: out.append(b)
        elif b<0xF0: v=ROM[p]; p+=1; out+= [v]*(b&0x7F)
        else: r=(b&0x0F)*8; out+= out[r:r+8]
    return out[:n]
def level_info(L):
    h=hdr(L); return {"vertical":h[1]==1,"screens":screen_ptrs(L),"st":bank_ptr(3,h[4],h[5]),"pal":bank_ptr(3,h[6],h[7]),"alt":h[8],"bgpal":list(h[16:20]),"sppal":list(h[20:24]),"indoor":h[0]==1}
def supertile(info, i): return ROM[info["st"]+16*i:info["st"]+16*i+16]
