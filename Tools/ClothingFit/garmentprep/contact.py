"""Exact triangle-level contact tests between a garment and the surfaces it must clear.

Ported from the contact study tools (same numbers as Tools/ClothingFit/audit_wardrobe_layers.py).
"""
import numpy as np
from scipy.spatial import cKDTree


def tri_aabb(P,F):
    T=P[F]; return T.min(1), T.max(1)

def candidate_pairs(PA,FA,PB,FB,chunk=4000):
    """AABB-overlapping triangle pairs (ia, ib). Tree on B centroids."""
    TA=PA[FA]; TB=PB[FB]
    if not len(TA) or not len(TB): return np.zeros(0,np.int64),np.zeros(0,np.int64)
    ca=TA.mean(1); cb=TB.mean(1)
    ra=np.linalg.norm(TA-ca[:,None],axis=2).max(1); rb=np.linalg.norm(TB-cb[:,None],axis=2).max(1)
    order=np.argsort(rb); cut=np.searchsorted(rb[order],np.percentile(rb,99.5),side="right")
    la,ha=TA.min(1),TA.max(1); lb,hb=TB.min(1),TB.max(1)
    res_a=[];res_b=[]
    for sel in (order[:cut],order[cut:]):
        if not len(sel): continue
        tb=cKDTree(cb[sel]); rmax=rb[sel].max()
        for s in range(0,len(ca),chunk):
            lists=tb.query_ball_point(ca[s:s+chunk], ra[s:s+chunk]+rmax)
            n=np.fromiter((len(l) for l in lists),dtype=np.int64,count=len(lists))
            if not n.sum(): continue
            ia=np.repeat(np.arange(s,s+len(lists)),n); ib=sel[np.concatenate([np.asarray(l,dtype=np.int64) for l in lists if len(l)])]
            keep=np.all((la[ia]<=hb[ib])&(lb[ib]<=ha[ia]),axis=1)
            res_a.append(ia[keep]);res_b.append(ib[keep])
    if not res_a: return np.zeros(0,np.int64),np.zeros(0,np.int64)
    return np.concatenate(res_a),np.concatenate(res_b)

def _seg_tri(p,q,a,b,c):
    """segments p->q vs triangles abc (vectorized). True where they cross."""
    e1=b-a;e2=c-a;d=q-p
    h=np.cross(d,e2);det=np.einsum("ij,ij->i",e1,h)
    ok=np.abs(det)>1e-12
    inv=np.where(ok,1/np.where(ok,det,1),0)
    s=p-a;u=np.einsum("ij,ij->i",s,h)*inv
    qv=np.cross(s,e1);v=np.einsum("ij,ij->i",d,qv)*inv
    t=np.einsum("ij,ij->i",e2,qv)*inv
    return ok&(u>=0)&(v>=0)&(u+v<=1)&(t>=0)&(t<=1)

def tri_tri(TA,TB):
    hit=np.zeros(len(TA),bool)
    for i in range(3):
        hit|=_seg_tri(TA[:,i],TA[:,(i+1)%3],TB[:,0],TB[:,1],TB[:,2])
        hit|=_seg_tri(TB[:,i],TB[:,(i+1)%3],TA[:,0],TA[:,1],TA[:,2])
    return hit

def intersections(PA,FA,PB,FB):
    ia,ib=candidate_pairs(PA,FA,PB,FB)
    if not len(ia): return ia,ib
    h=tri_tri(PA[FA[ia]],PB[FB[ib]])
    return ia[h],ib[h]

def tri_area(P,F):
    a,b,c=P[F].transpose(1,0,2); return .5*np.linalg.norm(np.cross(b-a,c-a),axis=1)

def closest_on_tris(pts, P, F, k=12):
    """closest point on mesh for each pt (approx: test k nearest triangles by centroid + vertex adjacency)."""
    T=P[F]; cen=T.mean(1); tree=cKDTree(cen)
    k=min(k,len(F)); _,idx=tree.query(pts,k=k)
    best=np.full(len(pts),np.inf); bp=np.zeros((len(pts),3)); bf=np.zeros(len(pts),np.int64)
    for j in range(k):
        f=idx[:,j]; cp=_closest_pt_tri(pts,T[f,0],T[f,1],T[f,2]); d=np.linalg.norm(pts-cp,axis=1)
        m=d<best; best[m]=d[m]; bp[m]=cp[m]; bf[m]=f[m]
    return bp,best,bf

def _closest_pt_tri(p,a,b,c):
    ab=b-a;ac=c-a;ap=p-a
    d1=np.einsum("ij,ij->i",ab,ap);d2=np.einsum("ij,ij->i",ac,ap)
    bp_=p-b;d3=np.einsum("ij,ij->i",ab,bp_);d4=np.einsum("ij,ij->i",ac,bp_)
    cp_=p-c;d5=np.einsum("ij,ij->i",ab,cp_);d6=np.einsum("ij,ij->i",ac,cp_)
    va=d3*d6-d5*d4;vb=d5*d2-d1*d6;vc=d1*d4-d3*d2
    out=np.empty_like(p)
    den=va+vb+vc; den=np.where(np.abs(den)<1e-20,1e-20,den)
    v=vb/den;w=vc/den
    out[:]=a+ab*v[:,None]+ac*w[:,None]
    m=(d1<=0)&(d2<=0); out[m]=a[m]; done=m.copy()
    m=(d3>=0)&(d4<=d3)&~done; out[m]=b[m]; done|=m
    m=(d6>=0)&(d5<=d6)&~done; out[m]=c[m]; done|=m
    m=(vc<=0)&(d1>=0)&(d3<=0)&~done; t=d1/np.where(d1-d3==0,1,d1-d3); out[m]=(a+ab*t[:,None])[m]; done|=m
    m=(vb<=0)&(d2>=0)&(d6<=0)&~done; t=d2/np.where(d2-d6==0,1,d2-d6); out[m]=(a+ac*t[:,None])[m]; done|=m
    m=(va<=0)&((d4-d3)>=0)&((d5-d6)>=0)&~done; t=(d4-d3)/np.where((d4-d3)+(d5-d6)==0,1,(d4-d3)+(d5-d6)); out[m]=(b+(c-b)*t[:,None])[m]
    return out

def vnormals(P,F):
    a,b,c=P[F].transpose(1,0,2); fn=np.cross(b-a,c-a); n=np.zeros_like(P)
    for i in range(3): np.add.at(n,F[:,i],fn)
    return n/np.maximum(np.linalg.norm(n,axis=1),1e-12)[:,None], fn/np.maximum(np.linalg.norm(fn,axis=1),1e-12)[:,None]


def crossing_triangles(skin, skin_faces, cloth, cloth_faces, pad=2.):
    """Indices of garment triangles that cross the skin, and of the skin triangles they cross."""
    lo, hi = cloth.min(0) - pad, cloth.max(0) + pad
    near = np.all((skin >= lo) & (skin <= hi), axis=1)
    sub = skin_faces[near[skin_faces].any(1)]
    i_skin, i_cloth = intersections(skin, sub, cloth, cloth_faces)
    return np.unique(i_cloth), sub[np.unique(i_skin)]


def self_crossing_pairs(P, F):
    """Number of non-adjacent triangle pairs of one mesh that cross each other."""
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    ia, ib = candidate_pairs(P, F, P, F)
    keep = ia < ib
    ia, ib = ia[keep], ib[keep]
    share = (F[ia][:, :, None] == F[ib][:, None, :]).any((1, 2))
    ia, ib = ia[~share], ib[~share]
    return int(tri_tri(P[F[ia]], P[F[ib]]).sum())
