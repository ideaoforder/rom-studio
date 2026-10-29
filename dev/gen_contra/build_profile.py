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
def mechanics():
    """Byte edits checked in the emulator (dev/test_contra_mech.py). Offsets come from labels + unique byte patterns."""
    def at(hexs, lo=0x1c010, hi=0x20010):
        p=bytes.fromhex(hexs); i=ROM.find(p,lo,hi); assert i!=-1 and ROM.find(p,i+1,hi)==-1, hexs; return i
    lives=off("init_player_lives"); dec=off("init_player_dec_num_lives")+9; assert ROM[dec:dec+2]==bytes.fromhex("D632")
    weap=off("init_player_and_weapon"); spawn=off("player_state_routine_00"); assert ROM[spawn:spawn+3]==bytes.fromhex("20D5DA")
    hook=0xF612; hook_off=0x10+7*0x4000+(hook-0xC000); assert set(ROM[hook_off:hook_off+16])=={0xFF}
    collide=at("B92805F02BB5AED0")+5
    jo=at("A9FBA0F0"); ji=at("A9FCA090"); grav=off("apply_gravity")+4; assert ROM[grav-1:grav+1]==bytes.fromhex("6923")
    xr=off("set_player_positive_x_velocity")+1; xl=off("set_player_negative_x_velocity")+1
    W=[("Normal gun",None),("Machine gun (M)",0x01),("Flame (F)",0x02),("Spread (S)",0x03),("Laser (L)",0x04),("Spread + rapid fire",0x13),("Machine gun + rapid fire",0x11)]
    def wpatch(w): # player_state_routine_00 -> JSR $F612: if the weapon is the normal gun, set W; then init_player_attributes
        return [{"offset":spawn,"hex":"2012F6"},{"offset":hook_off,"hex":f"B5AAD004A9{w:02X}95AA4CD5DA"}]
    jump_hook=at("B5A0F0034CAFD7")+4  # @player_jump_check: JMP handle_jump -> JMP $F620
    air=0xF620; air_off=0x10+7*0x4000+(air-0xC000); assert set(ROM[air_off:air_off+24])=={0xFF}
    def airpatch(limit):  # in a jump: new A press -> set_jump_status_and_y_velocity again; bit 3 of PLAYER_JUMP_STATUS = used (landing clears it)
        return [{"offset":jump_hook,"hex":"4C20F6"},
                {"offset":air_off,"hex":"B5F52980F00FB5A02908"+("D009" if limit else "EAEA")+"20D3D6B5A0090895A04CAFD7"}]
    return [
      {"id":"invincible","label":"Invincible","kind":"toggle","help":"Enemies and their bullets can't hurt you. You can still pick up weapons and ride platforms. Pits still count.","patches":[{"offset":collide,"hex":"A901"}]},
      {"id":"lives","label":"Infinite lives","kind":"toggle","help":"Losing a life doesn't count down.","patches":[{"offset":dec,"hex":"B532"}]},
      {"id":"startlives","label":"Extra lives at the start","kind":"number","offset":lives+1,"min":0,"max":29,"help":"Normally 2, plus the life you are playing. The Konami code gives 29."},
      {"id":"weapon","label":"Weapon at the start of each life","kind":"choice","default":0,"help":"When a life starts with the normal gun (a new game, or after losing a life), you get this instead. Weapons you pick up still replace it.",
       "options":[{"value":i,"label":l,**({"patches":wpatch(w)} if w is not None else {})} for i,(l,w) in enumerate(W)]},
      {"id":"keepweapon","label":"Keep your weapon when you lose a life","kind":"toggle","help":"Normally a lost life takes your weapon away.","patches":[{"offset":weap+2,"hex":"B5"}]},
      {"id":"jump","label":"Jump height","kind":"percent","values":[50,75,100,125,150,200,300],"default":100,"help":"How high a jump goes, outdoors and in the base levels.",
       "words":[{"lo":jo+3,"hi":jo+1,"mode":"sqrt","signed":True,"max":0x7F00},{"lo":ji+3,"hi":ji+1,"mode":"sqrt","signed":True,"max":0x7F00}]},
      {"id":"airjump","label":"Air jumps","kind":"choice","default":0,"help":"Press A again in mid-jump to jump again. Double jump gives one extra jump and resets when you land. Unlimited lets you climb the sky.",
       "options":[{"value":0,"label":"Off (normal)"},{"value":1,"label":"Double jump","patches":airpatch(True)},{"value":2,"label":"Unlimited","patches":airpatch(False)}]},
      {"id":"gravity","label":"Gravity","kind":"percent","values":[25,50,75,100,150,200],"default":100,"help":"How hard you fall. Low = floaty.","bytes":[{"offset":grav,"n":1,"mode":"mul","min":4}]},
      {"id":"speed","label":"Run speed","kind":"percent","values":[100,200,300],"labels":{"200":"2×","300":"3×"},"default":100,"help":"Walking speed (the game moves 1 pixel a frame normally).",
       "bytes":[{"offset":xr,"n":1,"mode":"mul","signed":True,"max":3},{"offset":xl,"n":1,"mode":"mul","signed":True,"max":3}]},
    ]
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
   "chr_link_sets":sets,"areas":areas,"palettes":palettes,"objects":objects,"mechanics":mechanics(),
   "mechanics_presets":{"Normal":{},"Super soldier":{"invincible":True,"lives":True,"weapon":5},"Moon":{"jump":150,"gravity":50,"airjump":1},"Speedy":{"speed":200,"airjump":1}}}
out=os.environ.get("CONTRA_OUT","/tmp/contra_profile.json"); json.dump(P,open(out,"w"),separators=(",",":"))
print(len(objects),"objects",len(sets),"link sets",len(json.dumps(P))//1024,"KB", free)
if os.environ.get("WRITE_HTML"):
    html=os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../index.html"); h=open(html).read()
    i=h.index("const CONTRA_PROFILE = ")+len("const CONTRA_PROFILE = "); j=h.index(";\nconst BUILTIN_PROFILES",i)
    open(html,"w").write(h[:i]+json.dumps(P,separators=(",",":"))+h[j:])
