"""Frostside grade in DA_WorldJumpConfig (Worlds[White].Grade): cold and bleached but with contrast.
Was saturation 0.15, exposure +0.6, bloom 1.2 (near monochrome white). ARGS: ['apply'] saves; anything else only prints."""
import json
import unreal

APPLY = bool(ARGS) and ARGS[0] == 'apply'
cfg = unreal.load_asset('/Game/Worlds/DA_WorldJumpConfig')
worlds = list(cfg.get_editor_property('worlds'))
res = {}
SETTINGS = [  # (property, value)
    ('color_saturation', unreal.Vector4(1.0, 1.0, 1.0, 0.5)),          # bleached, but blue survives
    ('color_contrast', unreal.Vector4(1.0, 1.0, 1.0, 1.18)),
    ('color_gain_shadows', unreal.Vector4(0.86, 0.94, 1.12, 1.0)),     # blue-grey shadows
    ('color_saturation_shadows', unreal.Vector4(1.0, 1.0, 1.0, 1.15)),
    ('scene_color_tint', unreal.LinearColor(0.88, 0.94, 1.0, 1.0)),
    ('white_temp', 5600.0),                                             # below 6500 = cooler
    ('auto_exposure_bias', -0.3),
    ('bloom_intensity', 0.5),
    ('vignette_intensity', 0.45),
]
for info in worlds:
    if 'WHITE' not in str(info.get_editor_property('world')).upper():
        continue
    g = info.get_editor_property('grade')
    before = {p: str(g.get_editor_property(p))[-60:] for p, _ in SETTINGS}
    for p, v in SETTINGS:
        g.set_editor_property(p, v)
        g.set_editor_property('override_' + p, True)
    info.set_editor_property('grade', g)
    res['before'] = before
    res['after'] = {p: str(info.get_editor_property('grade').get_editor_property(p))[-60:] for p, _ in SETTINGS}
if APPLY:
    cfg.set_editor_property('worlds', worlds)
    res['saved'] = unreal.EditorAssetLibrary.save_loaded_asset(cfg, only_if_is_dirty=False)
json.dumps(res, indent=0)
