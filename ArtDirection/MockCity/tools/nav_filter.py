"""Lvl_MockCity's RecastNavMesh: ledge slope filter off (stairs join), saved. The nav rebuild (map_switch.py) follows."""
import json
import unreal

p = unreal.load_asset('/Game/MockCity/Lvl_MockCity')
res = {}
for a in unreal.GameplayStatics.get_all_actors_of_class(p, unreal.RecastNavMesh):
    a.set_editor_property('ledge_slope_filter_mode', unreal.NavigationLedgeSlopeFilterMode.NONE)
    res[a.get_name()] = str(a.get_editor_property('ledge_slope_filter_mode'))
res['saved'] = unreal.EditorAssetLibrary.save_asset('/Game/MockCity/Lvl_MockCity', only_if_is_dirty=False)
json.dumps(res)
