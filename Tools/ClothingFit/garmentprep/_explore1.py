import sys, time
ST=r"C:/Users/zachc/Documents/Unreal Projects/reflections/Saved/ClothingFit/DirectImage3D/MarketJerkin/MeshRetargetPilot/ContactStudy/tools"
sys.path.insert(0,ST); import os; os.chdir(ST)
from check import *
sys.path.insert(0,r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
from field import SignedField
src=PILOT/"AfterPreserved"; fr=load(src,"standing"); c,cf=fr["cloth"],fr["cf"]; skin,sf=fr["skin"],fr["sf"]
t=time.time(); S=SignedField(skin,sf,c.min(0)-8,c.max(0)+[8,8,14]); print("field",S.shape,round(time.time()-t,1),"s")
cl=clearance(c,skin,sf); g=S(c)
d=g-cl; print("grid - exact clearance: pct 1/50/99",np.percentile(d,[1,50,99]).round(2),"sign mismatch",int(((g<0)!=(cl<0)).sum()),"of",len(c))
bad=np.flatnonzero((g<0)!=(cl<0)); print("mismatch exact vals",np.round(cl[bad][:20],2),"grid",np.round(g[bad][:20],2))
B=np.flatnonzero(g<0.6); p=c[B]
tu=S.exit_distance(p,[0,0,1.],.6); tb=S.exit_distance(p,[0,-1.,0],.6); tf=S.exit_distance(p,[0,1.,0],.6); tl=S.exit_distance(p,np.column_stack((np.sign(p[:,0]),0*p[:,0],0*p[:,0])),.6); td=S.exit_distance(p,[0,0,-1.],.6)
print("buried(<0.6) verts",len(B))
import numpy as np
np.set_printoptions(linewidth=220,suppress=True)
zone=np.where(p[:,2]>137,"upper",np.where(p[:,2]>116,"mid","low"))
for zn in ("upper","mid","low"):
    m=zone==zn; print(zn,m.sum(),"depth pct",np.percentile(-g[B][m],[50,90,100]).round(2) if m.any() else None)
m=zone=="upper"
print("upper: x  y  z  depth  up  back  fwd  lat")
o=np.argsort(np.abs(p[m][:,0])); rows=np.column_stack((p[m],-g[B][m],tu[m],tb[m],tf[m],tl[m]))[o]
for r in rows[::max(1,len(rows)//60)]: print(np.round(r,1))
np.savez("_explore1.npz",B=B,tu=tu,tb=tb,tf=tf,tl=tl,g=g)
