import re, os
DBG=os.path.join(os.environ["CONTRA_DIS"],"contra.dbg")
SEG={}; LAB={}
for l in open(DBG):
    kv=dict(re.findall(r'(\w+)=("[^"]*"|[^,]+)', l))
    if l.startswith("seg"):
        SEG[kv["id"]]={"name":kv["name"].strip('"'),"start":int(kv["start"],16),"ooffs":int(kv.get("ooffs","-1"),0) if "ooffs" in kv else None}
    elif l.startswith("sym") and "val" in kv and "seg" in kv:
        LAB.setdefault(kv["name"].strip('"'),(kv["seg"],int(kv["val"],16)))
def off(name, plus=0):
    seg,val=LAB[name]; s=SEG[seg]
    return s["ooffs"]+(val-s["start"])+plus
def cpu(name): return LAB[name][1]
