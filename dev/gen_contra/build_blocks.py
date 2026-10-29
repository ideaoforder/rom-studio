import sys, os, json, collections; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from screens import *
NAMES=["Jungle","Base 1","Waterfall","Base 2","Snow Field","Energy Zone","Hangar","Alien's Lair"]
def tile_tok(m, t):
    k=m.get(0x100+t); fl=k and k[3]
    return f"{0x100+t:03X}"+("h" if fl else "")
def screen_frame(info, sc, m):
    rows=8 if info["vertical"] else 7; toks=[[None]*32 for _ in range(rows*4)]; pals=[[None]*32 for _ in range(rows*4)]
    for k,st in enumerate(sc):
        d=supertile(info,st); pb=ROM[info["pal"]+st]
        for ty in range(4):
            for tx in range(4):
                q=(ty//2)*2+(tx//2); Y=(k//8)*4+ty; X=(k%8)*4+tx
                toks[Y][X]=tile_tok(m,d[ty*4+tx]); pals[Y][X]=f"bg{(pb>>(2*q))&3}"
    return {"cols":32,"tiles":" ".join(sum(toks,[])),"palettes":" ".join(sum(pals,[]))}
def tiles_frame(info, screens, m):
    use=collections.defaultdict(collections.Counter)
    for sc in screens:
        for st in sc:
            d=supertile(info,st); pb=ROM[info["pal"]+st]
            for i,t in enumerate(d): use[t][(pb>>(2*((i//8)*2+((i%4)//2))))&3]+=1
    toks=[];pals=[]
    for t in range(256):
        toks.append(tile_tok(m,t) if (0x100+t) in m else "."); pals.append(f"bg{use[t].most_common(1)[0][0]}" if use[t] else "bg0")
    return {"cols":16,"tiles":" ".join(toks),"palettes":" ".join(pals)}
def blocks():
    objs=[]; areas={}
    for L in range(8):
        info=level_info(L); name=f"L{L+1}"; seen=[]; screens=[]
        for p in info["screens"]:
            if p in seen: continue
            seen.append(p); screens.append(decode_screen(p,info["vertical"]))
        base=ppu_map(LEVELS[name]); alt=alt_entry(L)
        label=f"Level {L+1} · {NAMES[L]}"
        objs.append({"name":label,"category":"blocks","group":"Levels","chr_area":name,"home":name,"palette":["bg0"],
                     "frames":{"first screen":screen_frame(info,screens[0],base),"tiles":tiles_frame(info,screens,base)}})
        if alt and not info["indoor"]:
            objs.append({"name":label+" boss","category":"blocks","group":"Levels","chr_area":name+"b","home":name,"palette":["bg0"],
                         "frames":{"boss screen":screen_frame(info,[sc for sc in screens if len(set(sc))>=8][-1],ppu_map(LEVELS[name],alt))}})
    return objs
if __name__=="__main__":
    o=blocks(); print(len(o), [x["name"] for x in o], len(json.dumps(o))//1024,"KB")
