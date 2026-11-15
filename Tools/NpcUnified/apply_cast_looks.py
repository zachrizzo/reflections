"""Writes the finished cast (crowd-looks' list) into the Looks of the NPC archetype data assets.

Only the Looks arrays change: nothing is reset to a built-in (on the 16:20 build a reset would also switch on the
strike clips that crashed the editor). Only look Blueprints that exist on disk are written, and a pool with fewer
than two finished looks is left as it is, so no archetype ends up as copies of one person and no asset points at
a missing package.

Run in the editor's Python, not during PIE and not during a SAVE FREEZE:
    exec(open(r'<project>/Tools/NpcUnified/apply_cast_looks.py').read())
    apply_cast_looks()            # returns {archetype: [look ids written]} ; dry_run=True only reports
"""

import os

import unreal

LOOKS_DIR = '/Game/Characters/Lanthorne/Looks'
CIVILIANS = ('FrostHyeon', 'FrostSilas', 'GiltCoinClerk', 'GiltArchivist', 'GiltMaren', 'GiltBarnaby', 'GiltDrummer', 'GiltFerryman',
             'GiltPriya', 'GiltRamon', 'GiltGlassman', 'GiltHaruto')
GUARDS = ('GiltBridgeGuard', 'GiltRowena')
SOLDIERS = ('FrostIven', 'FrostSaran', 'FrostNia', 'FrostAmara')
CASTERS = ('FrostTobias', 'FrostWen')
POOLS = {'Civilian': CIVILIANS, 'Timid': CIVILIANS, 'Brave': CIVILIANS, 'Guard': GUARDS, 'Soldier': SOLDIERS,
         'SoldierCaster': CASTERS, 'Enemy': SOLDIERS + CASTERS, 'Hostile': SOLDIERS + CASTERS}


def apply_cast_looks(dry_run=False):
    content = unreal.Paths.project_content_dir()
    report = {}
    for archetype_id, cast in POOLS.items():
        finished = [look for look in cast
                    if os.path.exists(os.path.join(content, 'Characters', 'Lanthorne', 'Looks', 'BP_Look_%s.uasset' % look))]
        if len(finished) < 2:
            report[archetype_id] = 'kept as it is (%d finished look(s))' % len(finished)
            continue
        path = '/Game/NPC/Archetypes/DA_Npc_' + archetype_id
        asset = unreal.load_asset(path)
        if not asset:
            report[archetype_id] = 'no asset'
            continue
        classes = [unreal.load_class(None, '%s/BP_Look_%s.BP_Look_%s_C' % (LOOKS_DIR, look, look)) for look in finished]
        if any(c is None for c in classes):
            report[archetype_id] = 'a look class did not load; kept as it is'
            continue
        if not dry_run:
            asset.set_editor_property('looks', classes)
            if not unreal.EditorAssetLibrary.save_loaded_asset(asset, False):
                raise RuntimeError('Could not save ' + path)
        report[archetype_id] = finished
    return report


if __name__ == '__main__':
    print(apply_cast_looks(dry_run=True))
