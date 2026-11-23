# Sample joint positions from every baked clip of the category (component space, every 2nd frame) and write
# them to Saved/KimodoAmbient/analysis/<NN>_<Category>.json for review_sheets.py.
BONES = ['pelvis', 'spine_03', 'spine_05', 'neck_01', 'head',
         'clavicle_l', 'upperarm_l', 'lowerarm_l', 'hand_l', 'clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r',
         'thigh_l', 'calf_l', 'foot_l', 'ball_l', 'thigh_r', 'calf_r', 'foot_r', 'ball_r']
X = unreal.AnimPoseExtensions
W = unreal.AnimPoseSpaces.WORLD
name = AC.CATEGORIES[CI][0]
data = {'category': name, 'fps': FPS, 'step': 2, 'bones': BONES, 'clips': {}}
missing = []
for clip in AC.CATEGORIES[CI][2]:
    path = AC.folder(CI) + '/' + AC.asset_name(CI, clip)
    if not exists(path):
        missing.append(clip['id'])
        continue
    anim = obj(path)
    o = unreal.AnimPoseEvaluationOptions()
    n = anim.data_model_interface.get_number_of_keys()
    frames = []
    for f in range(0, n, 2):
        p = X.get_anim_pose_at_frame(anim, f, o)
        frames.append([[round(v, 1) for v in (t.x, t.y, t.z)] for t in (X.get_bone_pose(p, b, W).translation for b in BONES)])
        if f % 40 == 0:
            await asyncio.sleep(0)
    data['clips'][clip['id']] = {'keys': n, 'kind': clip['kind'], 'props': clip['props'],
                                 'prompts': clip['prompts'], 'frames': frames}
d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) + 'KimodoAmbient/analysis'
import os
os.makedirs(d, exist_ok=True)
fn = '%s/%02d_%s.json' % (d, CI + 1, name)
with open(fn, 'w') as fh:
    json.dump(data, fh)
{'file': fn, 'clips': len(data['clips']), 'missing': missing, 't': time.strftime('%H:%M:%S')}
