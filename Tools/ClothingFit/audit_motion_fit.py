"""Read paired LOD 0 surfaces and summarize fully exposed body intersections."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_posed_surfaces import classify_body_triangles, mask_image, surface, tree


def nearby_faces(vertices, faces, lower, upper):
    points = vertices[faces]
    return np.flatnonzero(((points.max(axis=1) >= lower) &
                           (points.min(axis=1) <= upper)).all(axis=1))


def compact_tree(vertices, faces):
    ids, remap = np.unique(faces,return_inverse=True)
    return tree(vertices[ids],remap.reshape(-1,3))


def audit(directory, output, mask_path, part=0, parts=1):
    mask = mask_image(mask_path)
    results = {}
    for folder in sorted((directory/'surfaces').iterdir())[part::parts]:
        if not (folder/'frames.json').is_file():
            continue
        poses = json.loads((folder/'frames.json').read_text())
        rest, tri = surface(folder/'rest_off.bin')
        body, bt = surface(folder/'rest_body.bin')
        classes = classify_body_triangles(folder,body,bt,mask,'T_PanelCoveredTorso')
        mask_verified = bool(np.any(classes==0) and np.any(classes==1))
        hem = rest[:,2] <= rest[:,2].min()+12.
        pin = rest[:,2] >= rest[:,2].min()+33.
        lower = hem[tri].any(axis=1)
        entries = {}
        for label, pose in poses.items():
            b, body_t = surface(folder/f'{label}_body.bin')
            face, head_t = surface(folder/f'{label}_face.bin')
            off, off_t = surface(folder/f'{label}_off.bin')
            on, on_t = surface(folder/f'{label}_on.bin')
            assert np.array_equal(bt,body_t) and np.array_equal(tri,off_t) and np.array_equal(tri,on_t)
            minimum = np.minimum(off.min(axis=0),on.min(axis=0))-.01
            maximum = np.maximum(off.max(axis=0),on.max(axis=0))+.01
            skin_ids = nearby_faces(b,body_t,minimum,maximum)
            head_ids = nearby_faces(face,head_t,minimum,maximum)
            skin = compact_tree(b,body_t[skin_ids])
            head = compact_tree(face,head_t[head_ids]) if len(head_ids) else None
            displacement = np.linalg.norm(on-off,axis=1)*10
            entries[label] = entry = {**pose,'mask_verified':mask_verified,
                'hem_motion_p95_mm':round(float(np.percentile(displacement[hem],95)),2),
                'upper_motion_p95_mm':round(float(np.percentile(displacement[pin],95)),2)}
            for key,vertices in [('off',off),('on',on)]:
                textile = tree(vertices,tri)
                pairs = np.asarray(skin.overlap(textile),dtype=int).reshape(-1,2)
                hem_hits = skin_ids[np.unique(pairs[lower[pairs[:,1]],0])]
                garment_hits = skin_ids[np.unique(pairs[:,0])]
                entry[key] = {
                    'exposed_hem_contacts':int(sum(classes[hem_hits]==1)),
                    'unresolved_hem_contacts':int(sum(classes[hem_hits]==2)),
                    'all_hem_contacts':len(hem_hits),
                    'exposed_total_contacts':int(sum(classes[garment_hits]==1)),
                    'head_contacts':len({i for i,_ in head.overlap(textile)}) if head else 0,
                }
        results[folder.name] = entries
        print(f'Checked {folder.name}',flush=True)

    rows = []
    for name, entries in results.items():
        row = {'wearer':name,'collider_body_lod':entries['rest']['collider_lod'],
               'dynamic_particles':entries['rest']['particles'],'mask_verified':entries['rest']['mask_verified']}
        for action in ('walk','cast'):
            poses = [e for label,e in entries.items() if label.startswith(action+'_')]
            assert poses
            row[f'{action}_samples'] = len(poses)
            row[f'{action}_max_hem_motion_mm'] = max(e['hem_motion_p95_mm'] for e in poses)
            for mode in ('off','on'):
                contacts = [e[mode]['exposed_hem_contacts'] for e in poses]
                row[f'{action}_hem_{mode}_mean'] = round(float(np.mean(contacts)),1)
                row[f'{action}_hem_{mode}_peak'] = max(contacts)
                row[f'{action}_hem_{mode}_affected'] = sum(x>0 for x in contacts)
                row[f'{action}_hem_{mode}_unresolved_peak'] = max(e[mode]['unresolved_hem_contacts'] for e in poses)
                row[f'{action}_hem_{mode}_geometric_peak'] = max(e[mode]['all_hem_contacts'] for e in poses)
                row[f'{action}_garment_{mode}_peak'] = max(e[mode]['exposed_total_contacts'] for e in poses)
        rows.append(row)
    assert rows
    output.parent.mkdir(parents=True,exist_ok=True)
    holdout = directory/'holdout.json'
    output.with_suffix('.json').write_text(json.dumps(
        {'holdout':json.loads(holdout.read_text()) if holdout.is_file() else None,
         'summary':rows,'samples':results},indent=2))


if __name__=='__main__':
    args = sys.argv[sys.argv.index('--')+1:]
    audit(*map(Path,args[:3]), *map(int,args[3:]))
