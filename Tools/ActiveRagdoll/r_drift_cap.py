import base64, os
_r = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureEditorViewport', bShowUI=False)
_fn = os.path.join(OUTDIR, 'drift_' + globals().get('SHOT', 'shot') + '.png')
open(_fn, 'wb').write(base64.b64decode(_r['image']['data']))
_fn
