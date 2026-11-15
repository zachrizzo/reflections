"""Widens the townspeople's look pools in the NPC archetype data assets (Civilian, Timid, Brave). Data only.

Why: Frostside had two townsperson looks (FrostSilas, FrostHyeon), so a Frostside street was six copies of each.
The orchestrator asked for the other Frost looks to walk the streets too.

  Always:            FrostIven, FrostTobias, FrostWen (no armour parts on these looks).
  On a build that can hide parts of a look (the archetype has HiddenLookParts, train #13 on):
                     FrostAmara, FrostNia, FrostSaran as well, the ten Pewterside townspeople (PewLook_*), and
                     HiddenLookParts = Armor, Shield on the three townsperson archetypes, so nobody walks the
                     street in a soldier's plate or with a shield on the arm.

The whole pool is rebuilt from look ids (never read back from the asset, where an unloaded look reads as nothing).
Only looks that exist on disk are written. Only these three assets are saved, by path.
Run in the editor's Python, not during PIE:  exec(open(r'<project>/Tools/NpcUnified/apply_extra_looks.py').read())
A re-sync (create_archetype_assets(resync=True)) puts the built-in pools back: run this again after it.
"""
import os

import unreal

LOOKS = '/Game/Characters/Lanthorne/Looks'
BASE = ('FrostHyeon', 'FrostSilas', 'GiltCoinClerk', 'GiltArchivist', 'GiltMaren', 'GiltBarnaby', 'GiltDrummer', 'GiltFerryman',
        'GiltPriya', 'GiltRamon', 'GiltGlassman', 'GiltHaruto')
FROST_PLAIN = ('FrostIven', 'FrostTobias', 'FrostWen')
FROST_ARMOURED = ('FrostAmara', 'FrostNia', 'FrostSaran')
PEWTER = ('CoinClerk', 'Archivist', 'Maren', 'Barnaby', 'Drummer', 'Ferryman', 'Priya', 'Ramon', 'Glassman', 'Haruto')
HIDE = ('Armor', 'Shield')


def _look(folder, name):
    disk = os.path.join(unreal.Paths.project_content_dir(), *folder.split('/')[2:], name + '.uasset')
    if not os.path.exists(disk):
        return None
    return unreal.load_class(None, '%s/%s.%s_C' % (folder, name, name))


def apply_extra_looks(dry_run=False):
    report = {}
    for archetype_id in ('Civilian', 'Timid', 'Brave'):
        path = '/Game/NPC/Archetypes/DA_Npc_' + archetype_id
        asset = unreal.load_asset(path)
        if not asset:
            report[archetype_id] = 'no asset'
            continue
        try:
            asset.get_editor_property('hidden_look_parts')
            can_hide = True
        except Exception:
            can_hide = False
        wanted = [(LOOKS, 'BP_Look_' + n) for n in BASE + FROST_PLAIN]
        if can_hide:
            wanted += [(LOOKS, 'BP_Look_' + n) for n in FROST_ARMOURED]
            wanted += [(LOOKS + '/Pewterside', 'PewLook_' + n) for n in PEWTER]
        classes, names, missing = [], [], []
        for folder, name in wanted:
            cls = _look(folder, name)
            if cls:
                classes.append(cls)
                names.append(name)
            else:
                missing.append(name)
        if len(classes) < 2:
            report[archetype_id] = 'kept as it is (fewer than two looks found)'
            continue
        if not dry_run:
            asset.set_editor_property('looks', classes)
            if can_hide:
                asset.set_editor_property('hidden_look_parts', [unreal.Name(piece) for piece in HIDE])
            if not unreal.EditorAssetLibrary.save_loaded_asset(asset, False):
                raise RuntimeError('Could not save ' + path)
        report[archetype_id] = {'looks': len(names), 'frost': [n for n in names if 'Frost' in n], 'pewter': sum(1 for n in names if 'PewLook' in n),
                                'hides': list(HIDE) if can_hide else 'this build cannot hide parts', 'not_on_disk': missing}
    return report


RESULT = apply_extra_looks(dry_run=globals().get('DRY_RUN', False))
