import os; OUT=os.environ.get("SMB2_OUT","/tmp/smb2_gen"); os.makedirs(OUT,exist_ok=True)
import sys, json, re; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); from labels import off
r=open(os.environ["SMB2_ROM"],"rb").read()
src=open(os.environ["SMB2_DIS"]+"/src/prg-2-3.asm").read().split('\n')
def groups(label):
    i=src.index(label+':')+1; out=[]; cur=None
    while i<len(src):
        l=src[i].strip(); i+=1
        if l.startswith('IFDEF') or (l.endswith(':') and not l.startswith(';')) or l.startswith(';;') : break
        if l=='' : 
            if out and src[i].strip().startswith(';\n'): break
            continue
        if l.startswith(';'):
            name=l[1:].strip()
            if name.startswith('Enemy Animation') or name.startswith('='): break
            cur={"name":name,"rows":[]}; out.append(cur); continue
        m=re.match(r"\.db\s+(.*?)\s*;\s*\$([0-9A-F]+)",l)
        if m and cur is not None:
            cur["rows"].append((int(m.group(2),16),[int(x.strip().strip('$'),16) for x in m.group(1).split(',')]))
    return out
T1=groups('EnemyTilemap1'); T2=groups('EnemyTilemap2')
# enemy types
ef=open(os.environ["SMB2_DIS"]+"/src/prg-e-f.asm").read()
names=re.findall(r"\.db .*; \$([0-9A-F]{2}) Enemy_(\w+)", ef[ef.index('ObjectAttributeTable:'):ef.index('EnemyArray_46E_Data:')])
attr=[r[off('ObjectAttributeTable')+i] for i in range(0x47)]
flags=[r[off('EnemyArray_46E_Data')+i] for i in range(0x47)]
anim=[r[off('EnemyAnimationTable')+i] for i in range(0x47)]
ENAME={int(k,16):v for k,v in names}
print(len(T1),len(T2),len(ENAME))
for g in T1[:3]+T2[:3]: print(g)
json.dump({"T1":T1,"T2":T2,"attr":attr,"flags":flags,"anim":anim,"names":ENAME},open(OUT+"/enemy_data.json","w"))
