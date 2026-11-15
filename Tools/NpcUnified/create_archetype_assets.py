"""Creates or re-syncs one UReflectionsNpcArchetype data asset per built-in NPC type under /Game/NPC/Archetypes.

The assets override the built-ins in code and keep their own copy of every value. So after a build that adds an
archetype field or changes a built-in number, run this with resync=True: each existing asset is reset to the
built-in of its ArchetypeId and saved (hand tuning in those assets is lost; a custom type with its own id is never
touched).

Run in the editor's Python (not during PIE, not during a SAVE FREEZE):
    exec(open(r'<project>/Tools/NpcUnified/create_archetype_assets.py').read())
    create_archetype_assets(resync=True)

A new NPC type needs none of this: create a ReflectionsNpcArchetype data asset in the same folder by hand, give it
an ArchetypeId, and tag an actor NPC_Reactive + NPC_Type_<ArchetypeId>.
"""

import unreal

FOLDER = '/Game/NPC/Archetypes'
BUILT_IN = ('Civilian', 'Timid', 'Brave', 'Guard', 'Enemy', 'Hostile', 'Soldier', 'SoldierCaster', 'Infected', 'VillainHost',
            'AlliedSoldier')


def create_archetype_assets(ids=BUILT_IN, resync=False):
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    done = []
    for archetype_id in ids:
        name = 'DA_Npc_' + archetype_id
        path = FOLDER + '/' + name
        exists = unreal.EditorAssetLibrary.does_asset_exist(path)
        if exists and not resync:
            continue
        if exists:
            asset = unreal.EditorAssetLibrary.load_asset(path)
        else:
            asset = tools.create_asset(name, FOLDER, unreal.ReflectionsNpcArchetype, unreal.DataAssetFactory())
        if not asset:
            raise RuntimeError('Could not create or load ' + path)
        asset.set_editor_property('archetype_id', unreal.Name(archetype_id))
        asset.reset_to_built_in()
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset, False):
            raise RuntimeError('Could not save ' + path)
        done.append(path)
    return done


if __name__ == '__main__':
    print(create_archetype_assets())
