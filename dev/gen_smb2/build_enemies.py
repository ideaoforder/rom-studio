import os; OUT=os.environ.get("SMB2_OUT","/tmp/smb2_gen"); os.makedirs(OUT,exist_ok=True)
import json, re, sys
D=json.load(open(OUT+"/enemy_data.json")); N={int(k):v for k,v in D["names"].items()}
WORLDBANK={"w1":0x0C,"w2":0x0D,"w3":0x0C,"w4":0x0E,"w5":0x0C,"w6":0x0D,"w7":0x0F}
BGBANK={"w1":0x10,"w2":0x12,"w3":0x10,"w4":0x14,"w5":0x0A,"w6":0x12,"w7":0x16}
BOSS=re.compile(r"Mouser|Tryclyde|Fryguy|Clawgrip|Wart|Unused|opening|empty space|spit\?")
HOME={"Cobrat":"w2","Cobrat (spit)":"w2","Pokey":"w2","Panser":"w2","Panser (spit)":"w2","Panser (spit?)":"w2","Flurry":"w4","Autobomb":"w4","Autobomb Fire":"w4","Autobomb Shyguy":"w4","Whale spout":"w4","Whale spout (falling)":"w4","Rocket":"w2","Flying carpet":"w1","Ostro":"w1","Ostro Shyguy":"w1"}
SPECIAL={"Heart","HawkmouthBoss","Rocket","Tryclyde","Clawgrip","Wart","Mouser","Fryguy"}
TALL_DEFAULT={"Door":2,"Door with lock":2,"Hawkmouth (closed top)":2,"Hawkmouth (open top)":2}
def tok(n):
    base=(n&0xFE)+(0x100 if n&1 else 0); return f"{base:02X}",f"{base+1:02X}"
objs=[]
PARENT={}
for tm,key in ((1,"T1"),(2,"T2")):
    for g in D[key]:
        if BOSS.search(g["name"]) or not g["rows"]: continue
        lo=g["rows"][0][0]; hi=g["rows"][-1][0]+2*(len(g["rows"][-1][1])//2)
        users=[t for t in range(0x47) if N[t] not in SPECIAL if D["anim"][t]!=0xFF and ((D["flags"][t]>>4)&1)==(tm-1) and lo<=D["anim"][t]<hi]
        pm=re.match(r"(.+?) \((.+)\)$",g["name"]); par=PARENT.get(pm.group(1)) if pm else None
        if par and not users: users=par
        a=D["attr"][users[0]] if users else 0x01
        tall=bool(a&0x40); horiz=tall and bool(a&0x04); mirrored=bool(a&0x10)
        rpf=2 if tall else TALL_DEFAULT.get(g["name"],1)
        if rpf==2 and not tall: tall=True
        frames={}; rows=g["rows"]
        for k in range(0,len(rows),rpf):
            chunk=rows[k:k+rpf]
            if len(chunk)<rpf: break
            cols=4 if horiz else 2; grid=[]
            rowsTiles=[sum((c[1] for c in chunk),[])] if horiz else [c[1] for c in chunk]
            for rt in rowsTiles:
                top=[];bot=[]
                for j,n in enumerate(rt):
                    fl="h" if mirrored and j%2==1 else ""
                    if n in (0xFB,0xFF): top.append(".");bot.append("."); continue
                    t,b=tok(n); top.append(t+fl); bot.append(b+fl)
                grid+= [top,bot]
            frames[f"frame {k//rpf+1}"]={"cols":cols,"tiles":" ".join(" ".join(x) for x in grid)}
        # dedupe identical frames
        seen=[];fr2={}
        for kname,f in frames.items():
            if f["tiles"] in seen: continue
            seen.append(f["tiles"]); fr2[f"frame {len(fr2)+1}"]=f
        pals=[]; labels=[]
        for t in users:
            p=D["attr"][t]&3 or 1
            if p not in pals: pals.append(p); labels.append(N[t])
        if users: PARENT[g["name"]]=users
        home=HOME.get(g["name"],"w1")
        if g["name"]=="Birdo": pals=[3,1,2]; labels=["Pink","Red","Gray"]  # Enemy_Birdo_Attributes, picked by x position at spawn
        if g["name"]=="Rocket":  # drawn twice by RenderSprite_Rocket: left half as stored, right half mirrored -> 32x32
            fr2={"frame 1":{"cols":4,"tiles":"E0 E2 E2h E0h E1 E3 E3h E1h E4 E6 E6h E4h E5 E7 E7h E5h"}}; pals=[1]
        objs.append({"name":g["name"],"group":"Enemies & items","home":home,"palette":pals or [1],"variant_labels":labels if len(pals)>1 else [],
            "chr_banks":[0x00,0x08,0x09,WORLDBANK[home],BGBANK[home],BGBANK[home]+1,0x18,0x19],"frames":fr2,"_users":[N[t] for t in users]})
RENAME={"BobOmb":"Bob-omb","Puff of smoke, which can be two sprites tall for doors!":"Puff of smoke","Crystal Ball":"Crystal ball","Hawkmouth (closed top)":"Hawkmouth"}
merged=[]
for o in objs:
    o["name"]=RENAME.get(o["name"],o["name"])
    m=re.match(r"(.+?) \((.+)\)$",o["name"])
    parent=next((x for x in merged if m and x["name"]==m.group(1)),None) if m else None
    if parent:
        for i,(k,f) in enumerate(o["frames"].items()):
            parent["frames"][m.group(2)+("" if len(o["frames"])==1 else f" {i+1}")]=f
        continue
    merged.append(o)
for o in merged:
    if o["name"]=="Hawkmouth": o["frames"]={("closed" if k=="frame 1" else k):v for k,v in o["frames"].items()}
objs=merged
json.dump(objs,open(OUT+"/enemies.json","w"),indent=0)
for o in objs: print(o["name"],"|",o["home"],o["palette"],len(o["frames"]),"|",",".join(o["_users"]))
