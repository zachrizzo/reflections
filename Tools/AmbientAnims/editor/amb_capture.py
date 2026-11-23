# Capture the editor viewport from EYE toward AIM (globals; defaults frame the body at the market spot) to
# Saved/KimodoAmbient/stills/<LABEL>.png. CaptureEditorViewport keeps eye adaptation and restores the camera.
import base64
import os
assert not pie(), 'PIE running'
d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) + 'KimodoAmbient/stills'
os.makedirs(d, exist_ok=True)
eye = unreal.Vector(*globals().get('EYE', (360.0, -170.0, 150.0)))
aim = unreal.Vector(*globals().get('AIM', (700.0, 0.0, 100.0)))
rot = unreal.MathLibrary.find_look_at_rotation(eye, aim)
xf = {'translation': {'x': eye.x, 'y': eye.y, 'z': eye.z}, 'rotation': {'pitch': rot.pitch, 'yaw': rot.yaw, 'roll': 0.0},
      'scale3D': {'x': 1.0, 'y': 1.0, 'z': 1.0}}
for _k in range(globals().get('WARM', 2)):
    r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureEditorViewport', captureTransform=xf, bShowUI=False)
fn = '%s/%s.png' % (d, LABEL)
with open(fn, 'wb') as fh:
    fh.write(base64.b64decode(r['image']['data']))
fn
