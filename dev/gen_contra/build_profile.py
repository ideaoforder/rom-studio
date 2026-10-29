import sys, os, json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from render import *; from labels import off, cpu
from objects_def import OBJECTS
from build_blocks import blocks
VBASE=0x1000000
tbl={e["id"]:e for e in table()}
PATTERN=[i for i in tbl if i not in (0,2,0x18,0x10)]  # 10 = flipped copy of 0a's data
AREAMAP=dict(LEVELS); AREAMAP["END"]=[1,3,0x17]
def amap(a):
    return ppu_map(LEVELS[a[:-1]], alt_entry(int(a[1])-1)) if a.endswith("b") else ppu_map(AREAMAP[a])
def voff(k):
    kind,ref,a,flip=k
    return VBASE+ref*0x2000+a if kind=="v" else ref
def runs(m):
    out=[]
    for t in sorted(m):
        o=voff(m[t])
        if out and out[-1][0]+out[-1][1]==t and out[-1][2]+out[-1][1]*16==o: out[-1][1]+=1
        else: out.append([t,1,o])
    return out
LABELS={"L1":"Level 1 · Jungle","L2":"Level 2 · Base 1","L3":"Level 3 · Waterfall","L4":"Level 4 · Base 2","L5":"Level 5 · Snow Field","L6":"Level 6 · Energy Zone","L7":"Level 7 · Hangar","L8":"Level 8 · Alien's Lair"}
HOME={"L2boss":"L2","L4boss":"L4","END":"L1"}
BLOCKS=blocks()
used_areas=sorted({o[2] for o in OBJECTS}|{b["chr_area"] for b in BLOCKS})
areas_ppu={a:amap(a) for a in used_areas}
def tok(i, h, v): return f"{i:02X}"+("h" if h else "")+("v" if v else "")
objects=[]; used=set()
for o in OBJECTS:
    name,group,area,frames=o[:4]; lance=len(o)>4 and o[4]
    m=areas_ppu[area]; fr={}
    for fn,code in frames:
        parts=sprite(code)
        if parts and parts[0][0]=="small": parts=[(-8,parts[0][1],parts[0][2],-4)]
        sp=[]
        for dy,t,a,dx in parts:
            top=(t&0xFE)+(0x100 if t&1 else 0); h=bool(a&0x40); v=bool(a&0x80); pal=1 if lance else a&3
            first,second=(top+1,top) if v else (top,top+1)
            sp.append([tok(first,h,v),dx,dy,pal]); sp.append([tok(second,h,v),dx,dy+8,pal])
            for q in (top,top+1): used.add(voff(m[q]))
        fr[fn]={"sprites":sp}
    objects.append({"name":name,"group":group,"chr_area":area,"home":HOME.get(area,area[:2]),"palette":[1 if lance else 0],"frames":fr})
for bo in BLOCKS:
    for f in bo["frames"].values():
        for t in f["tiles"].split():
            if t!=".": i=int(t.rstrip("h"),16); k=areas_ppu[bo["chr_area"]].get(i); used.add(voff(k)) if k else None
objects+=BLOCKS
# identical copies of a used tile at the same PPU address in other blocks follow it (e.g. prone/capsule tiles in every outdoor level block)
bufs={b:blockbuf(b) for b in PATTERN}
writes={b:{a for a,_ in decode(tbl[b]["off"])[0] if a<0x2000} for b in PATTERN}
sets=[]
for o in sorted(used):
    if o<VBASE: continue
    b,a=(o-VBASE)//0x2000,(o-VBASE)%0x2000; data=bytes(bufs[b][a:a+16])
    if not any(data): continue
    grp=sorted(VBASE+b2*0x2000+a for b2 in PATTERN if a in writes[b2] and bytes(bufs[b2][a:a+16])==data)
    if len(grp)>1 and grp not in sets: sets.append(grp)
# palettes: game_palettes entries + per-level sprite palette aliases
gp=off("game_palettes"); hdr=off("level_headers")
palettes={f"gp.{i:02X}":{"offset":gp+3*i,"label":f"Game palette {i:02X}"} for i in range(110)}
areas={}
for L in range(8):
    a=f"L{L+1}"; areas[a]={"label":LABELS[a],"sky":"0F"}
    for k in range(4): palettes[f"{a}.{k}"]={"same_as":f"gp.{ROM[hdr+L*32+20+k]:02X}"}
    for k in range(4): palettes[f"{a}.bg{k}"]={"same_as":f"gp.{ROM[hdr+L*32+16+k]:02X}"}
for a in palettes:
    if a.startswith("gp."):
        users=[f"L{L+1}.{k}" for L in range(8) for k in ("0","1","2","3","bg0","bg1","bg2","bg3") if palettes[f"L{L+1}.{k}"]["same_as"]==a]
        if users:
            kind=users[0].split('.')[1]; kind=f"Background palette {kind[2:]}" if kind.startswith("bg") else f"Sprite palette {kind}"
            palettes[a]["label"]=f"{kind} · " + ", ".join(sorted({u.split('.')[0] for u in users}))
blocks={}
for b in PATTERN:
    e=tbl[b]; d={"offset":e["off"],"bank":e["bank"]}
    if b==0x0a: d["aliases"]=[0x10]; d["prefix"]=ROM[e["off"]-2:e["off"]].hex().upper()
    blocks[str(b)]=d
free={}
for l in open(os.path.join(os.environ["CONTRA_DIS"],"contra.dbg")):
    if l.startswith("seg") and "BANK_" in l:
        kv=dict(re.findall(r'(\w+)=("[^"]*"|[^,]+)',l)); bank=int(kv["name"].strip('"')[5:]); size=int(kv["size"],16); oo=int(kv["ooffs"])
        if bank in (2,4,5,6): free[str(bank)]=[oo+size, 0x10+bank*0x4000+0x4000-(oo+size)]
P={"format":"nes-sprite-profile/1","game":"Contra (USA)","objects_label":"Sprites",
   "rom":{"size":131088,"chr_offset":0,"check":[[0,"4E45531A0800"],[off("level_1_graphic_data"),"0313191A141605FF"],[off("graphic_data_ptr_tbl"),ROM[off("graphic_data_ptr_tbl"):off("graphic_data_ptr_tbl")+6].hex().upper()]]},
   "chr_ram":{"vbase":VBASE,"ptr_table":off("graphic_data_ptr_tbl"),"blocks":blocks,"free":free,"areas":{a:runs(areas_ppu[a]) for a in used_areas}},
   "chr_link_sets":sets,"areas":areas,"palettes":palettes,"objects":objects}
out=os.environ.get("CONTRA_OUT","/tmp/contra_profile.json"); json.dump(P,open(out,"w"),separators=(",",":"))
print(len(objects),"objects",len(sets),"link sets",len(json.dumps(P))//1024,"KB", free)
if os.environ.get("WRITE_HTML"):
    html=os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../index.html"); h=open(html).read()
    i=h.index("const CONTRA_PROFILE = ")+len("const CONTRA_PROFILE = "); j=h.index(";\nconst BUILTIN_PROFILES",i)
    open(html,"w").write(h[:i]+json.dumps(P,separators=(",",":"))+h[j:])
