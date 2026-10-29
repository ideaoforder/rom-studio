import sys, os, numpy as np; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from sprites import *
NES=[(84,84,84),(0,30,116),(8,16,144),(48,0,136),(68,0,100),(92,0,48),(84,4,0),(60,24,0),(32,42,0),(8,58,0),(0,64,0),(0,60,0),(0,50,60),(0,0,0),(0,0,0),(0,0,0),(152,150,152),(8,76,196),(48,50,236),(92,30,228),(136,20,176),(160,20,100),(152,34,32),(120,60,0),(84,90,0),(40,114,0),(8,124,0),(0,118,40),(0,102,120),(0,0,0),(0,0,0),(0,0,0),(236,238,236),(76,154,236),(120,124,236),(176,98,236),(228,84,236),(236,88,180),(236,106,100),(212,136,32),(160,170,0),(116,196,0),(76,208,32),(56,204,108),(56,180,204),(60,60,60),(0,0,0),(0,0,0),(236,238,236),(168,204,236),(188,188,236),(212,178,236),(236,174,236),(236,174,212),(236,180,176),(228,196,144),(204,210,120),(180,222,120),(168,226,144),(152,226,180),(160,214,228),(160,162,160),(0,0,0),(0,0,0)]
_dec={}
def blockbuf(b):
    if b not in _dec:
        e={x["id"]:x for x in table()}[b]; w,_=decode(e["off"]); buf=bytearray(0x2000)
        for a,v in w:
            if a<0x2000: buf[a]=v
        _dec[b]=buf
    return _dec[b]
def tile_px(m, t):
    k=m.get(t)
    if not k: return np.zeros((8,8),int)
    kind,ref,a,flip=k
    data=bytes(blockbuf(ref)[a:a+16]) if kind=="v" else ROM[ref:ref+16]
    px=np.array([[((data[y]>>(7-x))&1)|(((data[y+8]>>(7-x))&1)<<1) for x in range(8)] for y in range(8)])
    return px[:,::-1] if flip else px
def render(parts, m, pals, scale=1):
    if parts and parts[0][0]=="small": parts=[(-8,parts[0][1],parts[0][2],-4)]
    if not parts: return np.zeros((8,8,3),np.uint8)
    xs=[p[3] for p in parts]; ys=[p[0] for p in parts]; x0,y0=min(xs),min(ys)
    W=max(xs)-x0+8; H=max(ys)-y0+16; img=np.zeros((H,W,3),np.uint8); img[:]=(40,40,40); drawn=np.zeros((H,W),bool)
    for dy,t,a,dx in parts:
        top=t&0xFE; tb=[tile_px(m,top),tile_px(m,top+1)] if not t&1 else [tile_px(m,0x100+top),tile_px(m,0x100+top+1)]
        px=np.vstack(tb)
        if a&0x40: px=px[:,::-1]
        if a&0x80: px=px[::-1]
        col=pals[a&3]
        for y in range(16):
            for x in range(8):
                v=px[y,x]; Y,X=dy-y0+y,dx-x0+x
                if v and not drawn[Y,X]: img[Y,X]=NES[col[v-1]]; drawn[Y,X]=True
    return img
