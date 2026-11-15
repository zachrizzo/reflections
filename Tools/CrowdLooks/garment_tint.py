"""Garment material instances under /Game/Characters/Lanthorne/Clothing (parent M_LanthorneGarment: BaseColor texture x
Tint; no normal/roughness inputs). Default: READ ONLY, report every MI's Tint and BaseColor texture, and export one
texture per look family to PNG (EXPORT_DIR) so the base colour can be judged. With APPLY = {mi_name_substring: (r,g,b)},
sets Tint on matching MIs and saves only those MIs (orchestrator OK needed first; owner of the MIs: hero-cloak).
Globals: OUT_JSON, EXPORT_DIR (optional), APPLY (optional)."""
import json
import os

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
ROOT = '/Game/Characters/Lanthorne/Clothing'
report = {'mis': {}, 'exported': [], 'applied': []}
apply = globals().get('APPLY') or {}
for p in eal.list_assets(ROOT, recursive=True):
    path = p.split('.')[0]
    name = path.split('/')[-1]
    if not name.startswith('MI_'):
        continue
    mi = unreal.load_asset(path)
    if not isinstance(mi, unreal.MaterialInstanceConstant):
        continue
    row = {}
    try:
        t = mel.get_material_instance_vector_parameter_value(mi, 'Tint')
        row['tint'] = [round(t.r, 3), round(t.g, 3), round(t.b, 3)]
    except Exception as e:
        row['tint_err'] = str(e)
    try:
        tex = mel.get_material_instance_texture_parameter_value(mi, 'BaseColor')
        row['basecolor'] = tex.get_path_name().split('.')[0] if tex else None
    except Exception as e:
        row['tex_err'] = str(e)
    for key, vals in (globals().get('SCALARS') or {}).items():
        # {mi_name_substring: {param: value}}, e.g. feet to leather: {'_Feet_': {'WeaveStrength': 0.0, 'Roughness': 0.7}}
        if key in name:
            got = {}
            for prm, val in vals.items():
                try:
                    got[prm] = round(mel.get_material_instance_scalar_parameter_value(mi, prm), 3)
                except Exception as e:
                    got[prm] = 'ERR %s' % e
                mel.set_material_instance_scalar_parameter_value(mi, prm, val)
            mel.update_material_instance(mi)
            eal.save_asset(path, only_if_is_dirty=False)
            row['scalars_was'] = got
            row['scalars_now'] = vals
            report['applied'].append(name)
    for key, rgb in apply.items():
        if key in name:
            mel.set_material_instance_vector_parameter_value(mi, 'Tint', unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
            mel.update_material_instance(mi)
            eal.save_asset(path, only_if_is_dirty=False)
            row['tint_now'] = list(rgb)
            report['applied'].append(name)
            break
    report['mis'][name] = row
exp = globals().get('EXPORT_DIR')
if exp:
    os.makedirs(exp, exist_ok=True)
    done = set()
    for name, row in report['mis'].items():
        tex = row.get('basecolor')
        if not tex or tex in done or 'Upper' not in tex:
            continue
        done.add(tex)
        task = unreal.AssetExportTask()
        task.object = unreal.load_asset(tex)
        task.filename = os.path.join(exp, tex.split('/')[-1] + '.png')
        task.automated = True
        task.prompt = False
        task.replace_identical = True
        ok = unreal.Exporter.run_asset_export_task(task)
        report['exported'].append([task.filename, bool(ok)])
open(OUT_JSON, 'w', encoding='utf-8').write(json.dumps(report, indent=1))
