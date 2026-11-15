import json, math
sub = unreal.MetaHumanCharacterEditorSubsystem
a = unreal.load_asset(A)
b = unreal.load_asset(B)
va, ta = sub.get_mesh_data_for_conforming(a)
vb, tb = sub.get_mesh_data_for_conforming(b)
out = {'na': len(va), 'nb': len(vb)}
if len(va) == len(vb):
    ds = sorted(math.sqrt((p.x-q.x)**2 + (p.y-q.y)**2 + (p.z-q.z)**2) for p, q in zip(va, vb))
    out.update({'median_cm': round(ds[len(ds)//2], 3), 'p95_cm': round(ds[int(len(ds)*0.95)], 3), 'max_cm': round(ds[-1], 3)})
RESULT = json.dumps(out)
