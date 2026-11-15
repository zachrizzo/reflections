"""Sets MaxHealth on the NPC archetype data assets (nothing else changes, nothing is reset).

Health is counted in Fire Bolts (14 each; a Fireball does 20): after the user's playtest ("they don't even die") a
civilian falls to a Fireball or two bolts, a guard to three, a soldier to four.
Run in the editor's Python, not during PIE:  exec(open(r'<project>/Tools/NpcUnified/set_archetype_health.py').read())
"""
import unreal

HEALTH = {'Civilian': 20.0, 'Timid': 20.0, 'Brave': 28.0, 'Guard': 42.0, 'Enemy': 70.0, 'Hostile': 42.0,
          'Soldier': 56.0, 'SoldierCaster': 42.0, 'Infected': 28.0, 'VillainHost': 70.0, 'AlliedSoldier': 56.0, 'AlliedSoldierCaster': 42.0}


def set_archetype_health(dry_run=False):
    report = {}
    for archetype_id, value in HEALTH.items():
        path = '/Game/NPC/Archetypes/DA_Npc_' + archetype_id
        asset = unreal.load_asset(path)
        if not asset:
            report[archetype_id] = 'no asset'
            continue
        before = asset.get_editor_property('max_health')
        if not dry_run and before != value:
            asset.set_editor_property('max_health', value)
            if not unreal.EditorAssetLibrary.save_loaded_asset(asset, False):
                raise RuntimeError('Could not save ' + path)
        report[archetype_id] = [before, value]
    return report


RESULT = set_archetype_health(dry_run=globals().get('DRY_RUN', False))
