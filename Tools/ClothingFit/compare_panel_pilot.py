"""Compare three wardrobe items on the same recorded Unreal body. Run in Blender."""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_posed_surfaces import (classify_body_triangles, mask_image, measure_girth, measure_rest,
                                 surface, tree)


def shirt_faces(name, points, triangles):
    if name != 'stock':
        return triangles
    # Epic's shirt and shorts are separate connected surfaces in the same component.
    # Weld material/UV splits for the connectivity query only.
    vertices, remap = np.unique(np.round(points, 3), axis=0, return_inverse=True)
    remap = remap.ravel()
    parent = list(range(len(vertices)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b, c in remap[triangles]:
        a = root(a)
        parent[root(b)] = a
        parent[root(c)] = a
    labels = np.array([root(i) for i in remap])
    assert len(set(labels)) == 2
    shirt = labels[np.argmax(points[:, 2])]
    assert np.max(points[labels != shirt, 2]) < np.max(points[:, 2]) - 30
    return triangles[labels[triangles[:, 0]] == shirt]


def compare(directory, output):
    variants = ('current', 'stock', 'panel')
    frames = json.loads((directory/'current/frames.json').read_text())
    neutral, topology = surface(directory/'current/rest_body.bin')
    masks, garment_topology, edges, lengths, results = {}, {}, {}, {}, {}
    for name in variants:
        path = directory/name
        manifest = json.loads((path/'frames.json').read_text())
        assert list(manifest) == list(frames)
        for label, pose in manifest.items():
            assert abs(pose['time'] - frames[label]['time']) < .00001
        skin, faces = surface(path/'rest_body.bin')
        assert np.array_equal(faces, topology) and np.max(np.abs(skin-neutral)) < .001
        state = json.loads((path/'body_mask.json').read_text())
        if name == 'panel':
            assert state['texture'].endswith('.T_Flat_White_C')
            masks[name] = np.ones(len(faces), dtype=np.uint8)
        else:
            tex = (directory/'stock/body_mask.tga' if name == 'stock'
                   else directory.parent/'source/T_WayfarersTunic_BodyMask.png')
            masks[name] = classify_body_triangles(path, skin, faces, mask_image(tex),
                                                  state['texture'].split('.')[-1])
        cloth, tris = surface(path/'rest_cloth0.bin')
        shirt = shirt_faces(name, cloth, tris)
        garment_topology[name] = (tris, shirt)
        e = np.unique(np.sort(np.vstack([shirt[:, [0,1]], shirt[:, [1,2]], shirt[:, [2,0]]]),axis=1), axis=0)
        length = np.linalg.norm(cloth[e[:,0]]-cloth[e[:,1]], axis=1)
        edges[name], lengths[name] = e[length > .25], length[length > .25]
        fabric = tree(cloth, shirt)
        naked = tree(skin, faces)
        results[name] = {'shirt_triangles':len(shirt), 'mask_texture':state['texture'],
                         'girth_mm':measure_girth(naked, fabric, frames['rest']['bones_cm']),
                         'directional_mm':measure_rest(naked, fabric, frames['rest']['bones_cm']), 'samples':{}}
    common = np.logical_and.reduce([masks[n] == 1 for n in variants])
    run = json.loads((directory/'game/frames.json').read_text())
    game_frames = run.pop('frames')
    overlap = {}
    names = json.loads((directory/'bones.json').read_text())
    index = np.fromfile(directory/'dominant_bone.bin', dtype='<u2')
    assert len(index) == len(neutral)
    bone_names = np.asarray([names[str(Counter(v).most_common(1)[0][0])] for v in index[topology]])
    hotspots = {name:Counter() for name in (*variants,'all_three')}
    for stage, label in ([('editor', k) for k in frames] + [('game', k) for k in game_frames]):
        game = stage == 'game'
        source = directory/('game' if game else 'current')
        pose = game_frames[label] if game else frames[label]
        skin, faces = surface(source/f'{label}_body.bin')
        head, head_faces = surface(source/f'{label}_face.bin')
        assert np.array_equal(faces, topology)
        skin_tree, head_tree = tree(skin, faces), tree(head, head_faces)
        per_variant = []
        for name in variants:
            if not game and name != 'current':
                other, ot = surface(directory/name/f'{label}_body.bin')
                assert np.array_equal(faces, ot) and abs(other-skin).max() < .01, (name,label,'body')
                other, ot = surface(directory/name/f'{label}_face.bin')
                assert np.array_equal(head_faces, ot) and abs(other-head).max() < .01, (name,label,'head')
            cloth, tris = surface(source/f'{label}_{name}.bin' if game else directory/name/f'{label}_cloth0.bin')
            full, shirt = garment_topology[name]
            assert np.array_equal(tris, full)
            fabric = tree(cloth, shirt)
            pairs = np.array(skin_tree.overlap(fabric), dtype=int).reshape(-1,2)
            body_ids = np.unique(pairs[:,0])
            exposed = body_ids[masks[name][body_ids] == 1]
            shared = body_ids[common[body_ids]]
            per_variant.append(set(shared.tolist()))
            if game and pose['casting']:
                hotspots[name].update(bone_names[shared])
            # A local inward distance is only counted for vertices of crossing
            # faces whose nearest body triangle also participates in a crossing.
            # This excludes distant sheets of the open, sometimes self-intersecting skin.
            depth = 0.
            if len(shared):
                targets = set(shared.tolist())
                cloth_ids = pairs[common[pairs[:,0]],1]
                for v in np.unique(shirt[cloth_ids]):
                    point = Vector(cloth[v])
                    p, inward, tri, dist = skin_tree.find_nearest(point)
                    if tri in targets:
                        depth = max(depth, (point-p).dot(inward)*10)
            e = edges[name]
            ratios = np.linalg.norm(cloth[e[:,0]]-cloth[e[:,1]],axis=1)/lengths[name]
            head_ids = {i for i, _ in head_tree.overlap(fabric)}
            samples = results[name].setdefault('gameplay_samples',{}) if game else results[name]['samples']
            samples[label] = {'time_s':round(pose['time'],4),
                'intersected_body_faces':len(body_ids), 'fully_unmasked_body_faces':len(exposed),
                'common_unmasked_body_faces':len(shared), 'unknown_mask_body_faces':int((masks[name][body_ids]==2).sum()),
                'head_faces_crossed_mask_unverified':len(head_ids),
                'sampled_local_inward_mm_on_common_skin':round(depth,2),
                'p95_edge_extension_pct':round(float(np.percentile(ratios,95)-1)*100,2)}
        intersection = set.intersection(*per_variant)
        overlap.setdefault(stage,{})[label] = len(intersection)
        if game and pose['casting'] and intersection:
            hotspots['all_three'].update(bone_names[sorted(intersection)])
    run['sample_times_s'] = [p['time'] for p in game_frames.values()]
    run['casting_at_sample'] = [p['casting'] for p in game_frames.values()]
    idle = np.asarray(game_frames['idle']['bones_cm']['hand_l'])
    run['left_hand_max_travel_from_idle_cm'] = round(max(
        np.linalg.norm(np.asarray(p['bones_cm']['hand_l'])-idle) for p in game_frames.values()),2)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'body':'GiltBarnaby','clip':'AS_Hero_CombatHealRaise',
                                 'method':'Unreal LOD 0 bone-skinned surfaces. Editor clip sampled at 30 Hz including both endpoints. Game sampled at recorded elapsed game times.',
                                 'gameplay_run':run, 'common_skin_faces_hit_by_all_three':overlap,
                                 'active_cast_body_face_contacts_by_dominant_bone':hotspots,
                                 'common_unmasked_skin_triangles':int(common.sum()),'variants':results}, indent=2))


if __name__ == '__main__':
    compare(*map(Path, sys.argv[sys.argv.index('--')+1:]))
