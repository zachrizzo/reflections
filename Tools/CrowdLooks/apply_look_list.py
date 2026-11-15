"""Point the NPC archetype data assets (/Game/NPC/Archetypes/DA_Npc_*) at the finished look list.

The look list is Tools/CrowdLooks/cast.json; each look Blueprint carries its own tags
(NPC_Voice_F|M, Look_Age_*, Look_Side_*, Look_Role_*, Look_Id_*). Run only with npc-unify's OK (they own the assets).
Global DRY_RUN (default True) prints what would change.
Pools:
  Civilian, Timid, Brave : every Civilian-role look, interleaved Giltside/Frostside and F/M so neighbours differ
  Guard                  : Guard-role looks
  Soldier                : Soldier-role looks (Frostside)
  SoldierCaster          : Caster-role looks (Frostside, share the hero skeleton for the cast clip)
  Enemy, Hostile         : Soldier + Caster looks
"""
import json

cast = json.load(open(PROJECT + 'Tools/CrowdLooks/cast.json'))['looks']
path = lambda L: '/Game/Characters/Lanthorne/Looks/BP_Look_%s.BP_Look_%s_C' % (L['id'], L['id'])
by_role = {}
for L in cast:
    by_role.setdefault(L['role'], []).append(L)


def interleave(looks):
    # Alternate side and sex so the round-robin spawner never puts two similar people side by side.
    buckets = {}
    for L in looks:
        buckets.setdefault((L['side'], L['sex']), []).append(L)
    keys = sorted(buckets)
    out = []
    while any(buckets.values()):
        for k in keys:
            if buckets[k]:
                out.append(buckets[k].pop(0))
    return out


civ = interleave(by_role.get('Civilian', []))
POOLS = {
    'Civilian': civ, 'Timid': civ, 'Brave': civ,
    'Guard': by_role.get('Guard', []),
    'Soldier': by_role.get('Soldier', []),
    'SoldierCaster': by_role.get('Caster', []),
    'Enemy': by_role.get('Soldier', []) + by_role.get('Caster', []),
    'Hostile': by_role.get('Soldier', []) + by_role.get('Caster', []),
}
report = {}
for arch, looks in POOLS.items():
    asset_path = '/Game/NPC/Archetypes/DA_Npc_' + arch
    da = unreal.load_asset(asset_path)
    if da is None:
        report[arch] = 'no asset'
        continue
    before = [str(x) for x in da.get_editor_property('looks')]
    after = [path(L) for L in looks]
    report[arch] = {'before': len(before), 'after': [a.split('.')[-1][:-2] for a in after]}
    if not globals().get('DRY_RUN', True):
        da.set_editor_property('looks', [unreal.SoftClassPath(a) for a in after])
        unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
RESULT = json.dumps(report, indent=0)
