import os; OUT=os.environ.get("SMB2_OUT","/tmp/smb2_gen"); os.makedirs(OUT,exist_ok=True)
import sys, json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); from labels import off
r=open(os.environ["SMB2_ROM"],"rb").read()
CHARS=[("Mario",0,0x00,0x04),("Luigi",3,0x01,0x05),("Toad",2,0x03,0x07),("Princess",1,0x02,0x06)]  # name, CurrentCharacter, big bank, small bank
FRAMES=["walk 1","carry 1","walk 2","carry 2","duck","duck carry","jump","dead","lift","throw","climb"]
EYE=[r[off('CharacterEyeTiles')+c] for c in range(4)]
FEYE=[r[off('CharacterFrameEyeTiles')+f] for f in range(11)]
T=lambda i: r[off('CharacterTiles_Walk1')+i]
BG1,BG2=0x10,0x18  # world 1 gameplay: BackgroundGrass, Animated1
def tok8x16(n):
    """8x16 sprite tile n -> (top, bottom) 8x8 tokens in the 512-tile space (odd = background table)"""
    base=(n&0xFE)+(0x100 if n&1 else 0)
    return f"{base:02X}", f"{base+1:02X}"
def sprite(n, x, y, flip, pal=None):
    t,b=tok8x16(n); h="h" if flip else ""
    return [[t+h,x,y,pal],[b+h,x,y+8,pal]]
def frame(c, f, small, princess):
    i=f*4; tl,tr,bl,br=T(i),T(i+1),T(i+2),T(i+3)
    if small and princess and f==6: bl,br=T(0x2C),T(0x2D)
    eye=FEYE[f] or EYE[c]
    sp=[]
    if eye!=0xFB: sp+=sprite(eye,8,0,True,1)              # facing right: eye sits on the right, flipped, palette 1
    if f in (4,5,7):  # duck / dead: one tile drawn twice, right half mirrored
        cols=[(tl,bl,False),(tl,bl,True)]
    else:           # facing right: columns swap and flip
        cols=[(tr,br,True),(tl,bl,True)]
    for x,(top,bot,fl) in zip((0,8),cols):
        if top!=0xFB: sp+=sprite(top,x,0,fl)
        if bot!=0xFB: sp+=sprite(bot,x,16,fl)
    return {"sprites":sp}
objs=[]
for name,c,big,small in CHARS:
    for sm in (False,True):
        bank=small if sm else big
        objs.append({"name":name+(" (small)" if sm else ""),"group":"Players","home":"w1",
            "palette":[f"player.{name.lower()}"],
            "chr_banks":[bank,0x08,0x09,0x0C,BG1,BG1+1,BG2,BG2+1],
            "frames":{FRAMES[f]:frame(c,f,sm,name=="Princess") for f in range(11)}})
json.dump(objs,open(OUT+"/players.json","w"),indent=0)
print(len(objs), objs[0]["frames"]["walk 1"])
