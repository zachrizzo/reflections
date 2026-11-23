"""Evaluate a matched Chaos and bone-skinned capture of the loose tunic."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_posed_surfaces import classify_body_triangles, mask_image, surface, tree


def audit(directory, mask_dir, output):
    capture = directory/'surface'
    frames = json.loads((capture/'frames.json').read_text())
    neutral, triangles = surface(capture/'off_skinned_probe.bin')
    disabled, disabled_triangles = surface(capture/'off_probe.bin')
    error = np.linalg.norm(disabled-neutral, axis=1)*10
    assert np.array_equal(triangles, disabled_triangles) and error.max() < .5, error.max()
    hem = neutral[:,2] < neutral[:,2].min()+12
    upper = neutral[:,2] > neutral[:,2].min()+33
    hem_triangles = hem[triangles].any(axis=1)
    mask = mask_image(mask_dir/'SmoothSource/InstalledTorso.tga')
    results = []
    for index, data in enumerate(frames):
        prefix = capture/f'{index:03d}'
        def read(part):
            return surface(prefix.with_name(prefix.name+'_'+part+'.bin'))
        off, t0 = read('skinned')
        on, t1 = read('cloth')
        assert np.array_equal(triangles,t0) and np.array_equal(t0,t1)
        body, body_tri = read('body')
        if index == 0:
            classes = classify_body_triangles(mask_dir/'smoothed_masked',body,body_tri,mask,
                                              'T_PanelCoveredTorso')
            assert len(set(classes))==3
        head, head_tri = read('face')
        skin = tree(body,body_tri)
        face = tree(head,head_tri)
        travel = np.linalg.norm(on-off,axis=1)*10
        row = {**data,'hem_p95_mm':round(float(np.percentile(travel[hem],95)),3),
               'hem_max_mm':round(float(travel[hem].max()),3),
               'upper_p95_mm':round(float(np.percentile(travel[upper],95)),3)}
        # Sudden root/clip changes can leave the CPU render readback one frame
        # behind the current pose. The pinned upper garment detects this.
        row['matched_pose'] = row['upper_p95_mm'] <= 10
        for key, vertices in [('off',off),('on',on)]:
            cloth = tree(vertices,triangles)
            pairs = np.asarray(skin.overlap(cloth),dtype=int).reshape(-1,2)
            ids = np.unique(pairs[:,0])
            hem_ids = np.unique(pairs[hem_triangles[pairs[:,1]],0])
            row[key]={'all_body_triangles_crossed':len(ids),
                      'exposed_body_triangles_crossed':int(sum(classes[ids]==1)),
                      'exposed_body_triangles_crossed_by_hem':int(sum(classes[hem_ids]==1)),
                      'head_triangles_crossed':len({i for i,_ in face.overlap(cloth)})}
        results.append(row)
    assert max(f['hem_p95_mm'] for f in results) > 1, 'No simulated hem motion reached the render mesh'
    output.write_text(json.dumps({'disabled_reference_max_difference_mm':float(error.max()),
                                  'frames':results},indent=2))


if __name__ == '__main__':
    audit(*map(Path,sys.argv[sys.argv.index('--')+1:]))
