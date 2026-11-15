import base64, json, os
names = ['Ada','Aera','Aoi','Asha','Bo','Bruce','Cameron','Celeste','Dominic','Etta','Grace','Isaiah','Jelena','Jorge','Kelvin','Lani','Lorenzo','Mateo','Mikel','Omari','Orlando','Sook-ja','Sunita','Trey','Tuya','Victor','Vivian','Walter','Zuri']
paths = ['/MetaHumanCharacter/Optional/Presets/%s.%s' % (n, n) for n in names]
res = await call_tool('EditorToolset.EditorAppToolset.GetAssetThumbnails', assetPaths=paths)
out = os.path.join(unreal.Paths.project_saved_dir(), 'CrowdLooks', 'presets')
os.makedirs(out, exist_ok=True)
vals = res.get('returnValue', res) if isinstance(res, dict) else res
info = []
if isinstance(vals, dict):
    info.append(list(vals.keys()))
    vals = vals.get('value', vals)
for n, v in zip(names, vals if isinstance(vals, list) else []):
    img = v
    if isinstance(v, dict):
        img = next((v[k] for k in v if isinstance(v[k], str) and len(v[k]) > 500), None)
    if img:
        open(os.path.join(out, n + '.png'), 'wb').write(base64.b64decode(img.split(',')[-1]))
        info.append(n)
RESULT = json.dumps(info)
