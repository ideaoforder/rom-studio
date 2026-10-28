import os; OUT=os.environ.get("SMB2_OUT","/tmp/smb2_gen"); os.makedirs(OUT,exist_ok=True)
import json, sys, re; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); from labels import off
r=open(os.environ["SMB2_ROM"],"rb").read()
players=json.load(open(OUT+"/players.json")); enemies=json.load(open(OUT+"/enemies.json"))
ITEMS={"Small vegetable","Large vegetable","Shell","Coin","Bomb","Mushroom block","POW block","Key","Potion","Door","Door with lock","Crystal ball","Mushroom","1-Up","Stopwatch","Starman","Egg","Falling log","Flying carpet","Rocket","Bullet","Fireball"}
EFFECTS={"Puff of smoke","Block fizzle","Sand","Whale spout","Spark"}
for o in enemies:
    o.pop("_users",None)
    o["group"]="Items" if o["name"] in ITEMS else "Effects" if o["name"] in EFFECTS else "Enemies"
for o in players:
    o["note"]="The eyes are their own sprite in palette 1, the same palette many enemies use, so their colors follow the world you pick."
for o in enemies:
    if o.get("variant_labels") and o["name"]!="Birdo":
        base=re.sub(r"[^A-Za-z]","",o["name"]).lower(); out=[]
        for l in o["variant_labels"]:
            w=re.sub(r"([a-z])([A-Z])",r"\1 \2",l)
            if w.replace(" ","").lower().startswith(base): w=w[len(w.split(" ")[0]):].strip() if " " in w else w
            out.append(w[:1].upper()+w[1:].lower())
        o["variant_labels"]=out
    if not o.get("variant_labels"): o.pop("variant_labels",None)
palettes={}
for name,i in (("mario",0),("princess",1),("toad",2),("luigi",3)):
    palettes[f"player.{name}"]={"offset":off("CharacterPalette")+i*4+1,"label":f"{name.capitalize()} body"}
areas={}
for w in range(1,8):
    sp=off(f"World{w}SpritePalettes"); bg=off(f"World{w}BackgroundPalettes")
    areas[f"w{w}"]={"label":f"World {w}","sky":f"{r[bg]:02X}"}
    for k in (1,2,3): palettes[f"w{w}.{k}"]={"offset":sp+(k-1)*4+1,"label":f"World {w} sprite palette {k}"}
P={"format":"nes-sprite-profile/1","game":"Super Mario Bros. 2 (USA) (Rev 1)","objects_label":"Sprites",
   "rom":{"size":262160,"chr_offset":0x20010,"check":[[0,"4E45531A0810"],[0x1A70,r[0x1A70:0x1A78].hex().upper()],[off("CharacterPalette"),r[off("CharacterPalette"):off("CharacterPalette")+4].hex().upper()]]},
   "areas":areas,
   "chr_links":[{"banks":list(range(8)),"tiles":[0x34,0x3C]},{"banks":[0x0C,0x0D,0x0E,0x0F],"tiles":[0,64]},
                {"banks":list(range(0x18,0x28,2)),"tiles":[0,64]},{"banks":list(range(0x19,0x28,2)),"tiles":[0,64]},
                {"banks":[0x0A,0x10,0x12,0x14,0x16],"tiles":[0,64]},{"banks":[0x0B,0x11,0x13,0x15,0x17],"tiles":[0,64]}],
   "palettes":palettes,"objects":players+enemies}
json.dump(P,open(OUT+"/smb2_profile.json","w"),separators=(",",":"),ensure_ascii=False)
print(len(P["objects"]), len(json.dumps(P))//1024,"KB", P["rom"]["check"])

html=""+os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../index.html")+""; h=open(html).read()
i=h.index("const SMB2_PROFILE = ")+len("const SMB2_PROFILE = "); j=h.index(";\nconst BUILTIN_PROFILES",i)
open(html,"w").write(h[:i]+json.dumps(P,separators=(",",":"),ensure_ascii=False)+h[j:])
