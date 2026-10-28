import os; OUT=os.environ.get("SMB2_OUT","/tmp/smb2_gen"); os.makedirs(OUT,exist_ok=True)
import re, glob
DIS=os.environ["SMB2_DIS"]+"/bin/"
LAB={}
for f in glob.glob(DIS+"smb2.nes.[0-7].nl"):
    bank=int(f.split(".")[-2])
    for l in open(f):
        m=re.match(r"\$([0-9A-F]{4})#([^#]+)#",l)
        if m: LAB.setdefault(m.group(2),(bank,int(m.group(1),16)))
def off(name, plus=0):
    bank,addr=LAB[name]; a=addr+plus
    return 0x10+bank*0x4000+(a&0x3FFF)
