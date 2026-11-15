"""(The sample map has no world anchors, so it counts as Pewterside: Giltside looks only, no rags.)
Swap the placed NPC walkers in the open level to finished Lanthorne looks (for the map's owner to run and save).

Every placed actor whose class is a SimpleRed or WhiteLook preview look is replaced by a look from SWAP (same
transform, same actor tags except old NPC_Voice_* ones, same label + ' (look)'). Nothing is saved: the map owner
saves. Global DRY_RUN (default True).
"""
import json

SWAP = {
    'BP_BridgeGuard_SimpleRed_C': 'GiltRowena',
    'BP_ArchiveApprentice_SimpleRed_C': 'GiltArchivist',
    'BP_CoinClerk_SimpleRed_C': 'GiltMaren',
    'BP_FestivalDrummer_SimpleRed_C': 'GiltPriya',
    'BP_WhiteLook_01_Plain_C': 'GiltHaruto',
    'BP_WhiteLook_06_GuardBoldRunes_C': 'GiltBridgeGuard',
    'BP_WhiteLook_02_Cap_C': 'FrostWen',
    'BP_WhiteLook_03_Mantle_C': 'FrostTobias',
    'BP_WhiteLook_04_CapMantle_C': 'FrostWen',
    'BP_WhiteLook_05_GuardRags_C': 'FrostSaran',
}
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
out = []
for a in eas.get_all_level_actors():
    cn = a.get_class().get_name()
    if cn not in SWAP:
        continue
    look = SWAP[cn]
    path = '/Game/Characters/Lanthorne/Looks/BP_Look_%s.BP_Look_%s_C' % (look, look)
    row = {'actor': a.get_actor_label(), 'from': cn, 'to': look}
    if not globals().get('DRY_RUN', True):
        cls = unreal.load_class(None, path)
        if cls is None:
            row['err'] = 'look not built yet'
        else:
            t = a.get_actor_transform()
            tags = [x for x in a.tags if not str(x).startswith('NPC_Voice_')]
            new = eas.spawn_actor_from_class(cls, t.translation, t.rotation.rotator())
            new.set_actor_scale3d(t.scale3d)
            new.tags = list(new.tags) + [x for x in tags if x not in new.tags]
            new.set_actor_label(a.get_actor_label() + ' (look)')
            eas.destroy_actor(a)
            row['new'] = new.get_actor_label()
    out.append(row)
RESULT = json.dumps(out)
