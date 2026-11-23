"""Compare the original and smoothed panels on one wearer in neutral stance and motion."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_posed_surfaces import classify_body_triangles, mask_image, measure_girth, surface, tree
from panel_edge_quality import crease_metrics, edge_pairs


def rim_edges(points, tri):
    _, indices = np.unique(np.round(points, 4), axis=0, return_inverse=True)
    edges = np.sort(np.vstack([tri[:, [0,1]], tri[:, [1,2]], tri[:, [2,0]]]), axis=1)
    welded = np.sort(indices.ravel()[edges], axis=1)
    _, first, count = np.unique(welded, axis=0, return_index=True, return_counts=True)
    return edges[first[count == 1]]


def opening_clearance(cloth, rim, hidden_skin):
    # Distance to the entire hidden body triangle surface. Samples span every
    # boundary segment with <= 2 mm spacing. Subtract 1 mm for a lower bound.
    start, end = cloth[rim].transpose(1, 0, 2)
    count = max(1,int(np.ceil(np.linalg.norm(end-start, axis=1).max()/.2)))
    distance = min(hidden_skin.find_nearest(p)[3] for t in np.linspace(0,1,count+1)
                   for p in start+(end-start)*t)
    return round(max(0.,distance*10-1),2)


def validate(path, output):
    old, new, bare = path/'panel', path/'smoothed_masked', path/'smoothed'
    frames = json.loads((new/'frames.json').read_text())
    run = json.loads((path/'edge_game/frames.json').read_text())
    game = run.pop('frames')
    mask_name = 'T_PanelCoveredTorso'
    assert run['body_mask'].endswith('.'+mask_name)
    body, body_tri = surface(new/'rest_body.bin')
    face, face_tri = surface(new/'rest_face.bin')
    mask = mask_image(path/'SmoothSource'/f'{mask_name}.png')
    classes = classify_body_triangles(new,body,body_tri,mask,mask_name)
    assert set(classes)=={0,1,2}
    names = json.loads((path/'bones.json').read_text())
    dominant = np.fromfile(path/'dominant_bone.bin',dtype='<u2')
    labels = np.array([names[str(i)] for i in dominant])
    allowed = np.array([s.startswith(('spine','pelvis','clavicle','upperarm')) for s in labels])
    protected = ~allowed[body_tri].all(axis=1)
    rest, triangles, adj, borders = {}, {}, {}, {}
    result = {'gameplay':run, 'fully_hidden_body_triangles':int(sum(classes==0)),
              'fully_hidden_faces_with_any_vertex_outside_torso_or_upper_arm':int(sum((classes==0)&protected)),
              'samples':{}}
    for key, folder in [('before',old),('after',new)]:
        rest[key], triangles[key] = surface(folder/'rest_cloth0.bin')
        adj[key] = edge_pairs(rest[key],triangles[key])
        borders[key] = rim_edges(rest[key],triangles[key])
        girth = measure_girth(tree(body,body_tri),tree(rest[key],triangles[key]),frames['rest']['bones_cm'])
        result[key+'_waist_ease_mm'] = girth['waist']['ease_mm']
    marks = [('editor',k) for k in frames] + [('game',k) for k in game]
    for stage,k in marks:
        gameplay = stage=='game'
        folder = path/'edge_game' if gameplay else new
        skin, st = surface(folder/f'{k}_body.bin')
        head, ht = surface(folder/f'{k}_face.bin')
        assert np.array_equal(st,body_tri) and np.array_equal(ht,face_tri)
        skin_tree, head_tree = tree(skin,st), tree(head,ht)
        # Include mixed UV triangles and uncertain filter borders in the opening
        # clearance bound, including the entire triangle when only a corner is dark.
        touched_by_mask = tree(skin,st[classes!=1])
        data = {}
        for key,d in [('before',old),('after',new)]:
            cloth, tri = surface(folder/f'{k}_{key}.bin' if gameplay else d/f'{k}_cloth0.bin')
            assert np.array_equal(tri,triangles[key])
            if not gameplay:
                comparison = bare if key=='after' else old
                other, t = surface(comparison/f'{k}_body.bin')
                assert np.array_equal(t,st) and np.max(abs(other-skin)) < .01
                if key=='after':
                    other,t = surface(bare/f'{k}_cloth0.bin')
                    assert np.array_equal(tri,t) and np.max(abs(other-cloth)) < .01
            textile = tree(cloth,tri)
            hits = np.array(sorted({i for i,_ in skin_tree.overlap(textile)}),dtype=int)
            entry = {'creases':crease_metrics(cloth,tri,adj[key]),'crossed_body_faces':len(hits),
                     'head_faces_crossed':len({i for i,_ in head_tree.overlap(textile)})}
            if key == 'after':
                entry.update(fully_hidden_crossings=int(sum(classes[hits]==0)),
                             fully_exposed_crossings=int(sum(classes[hits]==1)),
                             mixed_or_unverified_crossings=int(sum(classes[hits]==2)),
                             mask_to_opening_lower_bound_mm=opening_clearance(cloth,borders[key],touched_by_mask))
            data[key] = entry
        if gameplay:
            data['cast_active']=game[k]['casting']
        result['samples'].setdefault(stage,{})[k] = data
    output.write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    validate(*map(Path,sys.argv[sys.argv.index('--')+1:]))
