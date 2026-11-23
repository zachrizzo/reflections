"""audit_pa_fit.py - read-only: do the project's body meshes match their physics assets' joint positions?

The Hero's PHYS_MHC_Hero joints were made for the shared base skeleton's proportions, but its body mesh is bigger, so
a simulated spine collapses 6-15 cm the moment it simulates (see ArtDirection/Physics/ActiveRagdoll.md). This checks
every skeletal mesh with a physics asset under ROOTS: for each joint, the distance between the asset's parent-side
anchor (Pos2) and where the mesh's own reference pose puts it. Nothing is modified or saved.
"""
import json

ROOTS = globals().get('ROOTS', ['/Game/Characters', '/Game/MetaHumans'])
NAME_HAS = globals().get('NAME_HAS', ['Body'])
MAX_MESHES = globals().get('MAX_MESHES', 80)

ar = unreal.AssetRegistryHelpers.get_asset_registry()
flt = unreal.ARFilter(class_paths=[unreal.TopLevelAssetPath('/Script/Engine', 'SkeletalMesh')], package_paths=ROOTS,
                      recursive_paths=True)
datas = [d for d in ar.get_assets(flt) if any(k.lower() in str(d.asset_name).lower() for k in NAME_HAS)]
pa_cache = {}


def vec(d):
    return unreal.Vector(float(d['x']), float(d['y']), float(d['z']))


out = {'meshes': [], 'skipped': []}
for d in datas[:MAX_MESHES]:
    path = str(d.package_name)
    mesh = unreal.load_asset(path)
    pa = mesh.get_editor_property('physics_asset') if mesh else None
    if not pa:
        out['skipped'].append([path, 'no physics asset'])
        continue
    smc = unreal.SkeletalMeshComponent()
    smc.set_skeletal_mesh_asset(mesh)
    if pa.get_path_name() not in pa_cache:
        rows = []
        for i in range(0, 200):
            o = unreal.find_object(pa, 'PhysicsConstraintTemplate_' + str(i))
            if not o:
                continue
            g = await call_tool('EditorToolset.ObjectToolset.GetProperties', instance={'refPath': o.get_path_name()},
                                properties=['DefaultInstance.ConstraintBone1', 'DefaultInstance.ConstraintBone2', 'DefaultInstance.Pos1', 'DefaultInstance.Pos2'])
            rows.append(json.loads(g) if isinstance(g, str) else g)
        pa_cache[pa.get_path_name()] = rows
    worst, worst_joint, n = 0.0, '', 0
    for g in pa_cache[pa.get_path_name()]:
        child, parent = g['DefaultInstance.ConstraintBone1'], g['DefaultInstance.ConstraintBone2']
        if smc.get_bone_index(child) < 0 or smc.get_bone_index(parent) < 0:
            continue
        chain, bn = [], child
        while bn != parent and bn not in ('None', ''):
            chain.append(bn)
            bn = str(smc.get_parent_bone(bn))
        if bn != parent:
            continue
        xf = unreal.Transform()
        for c in reversed(chain):
            xf = smc.get_ref_pose_transform(smc.get_bone_index(c)) * xf
        want = xf.transform_location(vec(g['DefaultInstance.Pos1']))
        miss = (want - vec(g['DefaultInstance.Pos2'])).length()
        n += 1
        if miss > worst:
            worst, worst_joint = miss, '%s<-%s' % (parent, child)
    out['meshes'].append({'mesh': path, 'pa': pa.get_path_name().split('.')[0], 'joints': n,
                          'worst_cm': round(worst, 2), 'worst_joint': worst_joint})
out['meshes'].sort(key=lambda r: -r['worst_cm'])
out['found'] = len(datas)
json.dumps(out)
