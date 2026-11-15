"""Read-only: rotations of the rotated pieces in the side levels (ramps, door, arena, cracks) and the PlayerStart."""
import json
import unreal

res = {}
for side, labels in (('Frostside', ('Tower_Ramp_', 'VillainArena', 'Tower_Crack_')), ('Giltside', ('Tower_SealedDoor',))):
    w = unreal.load_asset('/Game/MockCity/Lvl_MockCity_' + side)
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        lab = a.get_actor_label()
        if lab.startswith(labels):
            r = a.get_actor_rotation()
            res[side + ':' + lab] = [round(r.roll, 1), round(r.pitch, 1), round(r.yaw, 1)]
    t = unreal.Transform(location=[0, 0, 0], rotation=[1.0, 2.0, 3.0], scale=[1, 1, 1]).rotation.rotator()
    res['list_[1,2,3]_->roll,pitch,yaw'] = [round(t.roll, 1), round(t.pitch, 1), round(t.yaw, 1)]
p = unreal.load_asset('/Game/MockCity/Lvl_MockCity')
for a in unreal.GameplayStatics.get_all_actors_of_class(p, unreal.PlayerStart):
    r = a.get_actor_rotation()
    res['PlayerStart'] = [round(r.roll, 1), round(r.pitch, 1), round(r.yaw, 1)]
json.dumps(res)
