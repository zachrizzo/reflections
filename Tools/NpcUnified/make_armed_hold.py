"""Makes the additive "sword and shield held at the ready" overlay for the NPCs' hidden walker.

Source: spell crafting's whole-body hold for the walker skeleton, /Game/Combat/Melee/AS_Melee_Shield_March_Hold_Walker
(or the guard idle if the march hold is not there yet). The copy in /Game/NPC/Anim is switched to a local-space
additive whose base pose is frame 0 of the walker's neutral stand, so only the difference from standing (the arms,
the closed fists) is left. Played in the walker's default slot it is added on top of whatever the legs are doing.

Run in the editor's Python, not during PIE:  exec(open(r'<project>/Tools/NpcUnified/make_armed_hold.py').read())
Only /Game/NPC/Anim/AS_Npc_ArmedHold_Add_Walker is created or saved. The source clip is not changed.
"""
import unreal

SOURCES = ('/Game/Combat/Melee/AS_Melee_Shield_March_Hold_Walker', '/Game/Combat/Melee/AS_Melee_Shield_Guard_Idle_Walker')
BASE = '/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop'
TARGET_DIR = '/Game/NPC/Anim'
TARGET_NAME = 'AS_Npc_ArmedHold_Add_Walker'


def make_armed_hold():
    report = {'target': TARGET_DIR + '/' + TARGET_NAME}
    source = next((path for path in SOURCES if unreal.EditorAssetLibrary.does_asset_exist(path)), None)
    report['source'] = source
    if not source:
        report['made'] = False
        report['why'] = 'no hold clip from spell crafting on disk yet'
        return report
    base = unreal.load_asset(BASE)
    if not base:
        report['made'] = False
        report['why'] = 'the base pose clip did not load'
        return report
    target = TARGET_DIR + '/' + TARGET_NAME
    if unreal.EditorAssetLibrary.does_asset_exist(target):
        clip = unreal.load_asset(target)
        report['existed'] = True
    else:
        clip = unreal.EditorAssetLibrary.duplicate_asset(source, target)
        report['existed'] = False
    if not clip:
        report['made'] = False
        report['why'] = 'could not create the copy'
        return report
    clip.set_editor_property('additive_anim_type', unreal.AdditiveAnimationType.AAT_LOCAL_SPACE_BASE)
    clip.set_editor_property('ref_pose_type', unreal.AdditiveBasePoseType.ABPT_ANIM_FRAME)
    clip.set_editor_property('ref_pose_seq', base)
    clip.set_editor_property('ref_frame_index', 0)
    report['saved'] = unreal.EditorAssetLibrary.save_loaded_asset(clip, False)
    report['made'] = bool(report['saved'])
    report['length_s'] = round(clip.get_play_length(), 2)
    report['additive'] = str(clip.get_editor_property('additive_anim_type'))
    report['skeleton'] = clip.get_editor_property('skeleton').get_name() if clip.get_editor_property('skeleton') else None
    return report


RESULT = make_armed_hold()
