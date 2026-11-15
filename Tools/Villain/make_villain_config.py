"""Creates or refreshes /Game/Villain/DA_VillainConfig (needs the villain C++ loaded). Run in the editor's MCP Python tool.

The data asset hard-references every asset the villain uses, so always-cooking /Game/Villain cooks them all
(C++ string-path loads are invisible to the cooker). Missing assets are skipped; the C++ falls back by path.
"""
import unreal

PATH = '/Game/Villain/DA_VillainConfig'
CUES = '/Game/Audio/Jam/Cues/'
MANNY = '/Game/Characters/Mannequins/'
SPELL = '/Game/Characters/Hero/SpellVFX/Systems/'

FIELDS = {
    'body_mesh': [MANNY + 'Meshes/SKM_Manny_Simple'],
    'body_material': ['/Game/Villain/Materials/M_Villain_Body'],
    'shroud_mesh': ['/Game/Villain/Meshes/SM_Villain_Shroud'],
    'shroud_material': ['/Game/Villain/Materials/M_Villain_Shroud'],
    'hood_mesh': ['/Game/Villain/Meshes/SM_Villain_Hood'],
    'eye_mesh': ['/Engine/BasicShapes/Sphere'],
    'eye_material': ['/Game/Villain/Materials/M_Villain_Eye'],
    'infected_overlay': ['/Game/Villain/Materials/M_Villain_InfectedOverlay'],
    'burned_overlay': ['/Game/Villain/Materials/M_Villain_BurnedOverlay'],
    'telegraph_material': ['/Game/Villain/Materials/M_Villain_Telegraph'],
    'disc_mesh': ['/Engine/BasicShapes/Plane'],
    'hover_anim': [MANNY + 'Anims/Unarmed/Jump/MM_Fall_Loop', MANNY + 'Anims/Unarmed/MM_Idle'],
    'volley_anim': [MANNY + 'Anims/Unarmed/Attack/MM_Attack_02'],
    'slam_anim': [MANNY + 'Anims/Unarmed/Attack/MM_ChargedAttack'],
    'wave_anim': [MANNY + 'Anims/Unarmed/Attack/MM_Attack_03'],
    'blink_anim': [MANNY + 'Anims/Unarmed/Jump/MM_Dash'],
    'test_host_mesh': [MANNY + 'Meshes/SKM_Quinn_Simple'],
    'shroud_fx': ['/Game/Villain/FX/NS_Villain_Shroud'],
    'projectile_fx': [SPELL + 'NS_Spell_Projectile'],
    'impact_fx': [SPELL + 'NS_Spell_Impact'],
    'possess_sound': [CUES + 'SCue_Villain_Possess', CUES + 'SCue_Infected_Growl'],
    'voice_sound': [CUES + 'SCue_Villain_Voice', CUES + 'SCue_Infected_Growl'],
    'hop_sound': [CUES + 'SCue_Villain_Hop', CUES + 'SCue_WorldJump_Whoosh'],
    'manifest_sound': [CUES + 'SCue_Villain_Manifest', CUES + 'SCue_WorldJump_Stinger'],
    'telegraph_sound': [CUES + 'SCue_Villain_Telegraph', CUES + 'SCue_Arcane_Cast'],
    'orb_sound': [CUES + 'SCue_Villain_Orb', CUES + 'SCue_Arcane_Impact'],
    'slam_sound': [CUES + 'SCue_Villain_Slam', CUES + 'SCue_Earth_Impact'],
    'hurt_sound': [CUES + 'SCue_Villain_Hurt', CUES + 'SCue_Lightning_Impact'],
    'resist_sound': [CUES + 'SCue_Villain_Resist', CUES + 'SCue_Shield_Block'],
    'death_sound': [CUES + 'SCue_Villain_Death', CUES + 'SCue_WorldJump_Stinger'],
    'final_spell_sound': [CUES + 'SCue_FinalSpell_Cast', CUES + 'SCue_Heal_Shimmer'],
    'fight_music': [CUES + 'SCue_MUS_Villain_Fight', CUES + 'SCue_MUS_Combat_Layer'],
}
# The mannequin's idle under the robe reads as hovering; the fall loop flails. Prefer the idle for the hover.
FIELDS['hover_anim'] = [MANNY + 'Anims/Unarmed/MM_Idle']

cls = unreal.load_class(None, '/Script/reflections.ReflectionsVillainConfig')
if not cls:
    raise RuntimeError('ReflectionsVillainConfig is not loaded yet (wait for the build train).')
asset = unreal.load_asset(PATH)
if not asset:
    factory = unreal.DataAssetFactory()
    factory.set_editor_property('data_asset_class', cls)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset('DA_VillainConfig', '/Game/Villain', cls, factory)
report = {}
for field, paths in FIELDS.items():
    value = None
    for p in paths:
        value = unreal.load_asset(p)
        if value:
            report[field] = p
            break
    if value:
        asset.set_editor_property(field, value)
    else:
        report[field] = None
abp = unreal.load_object(None, MANNY + 'Anims/Unarmed/ABP_Unarmed.ABP_Unarmed_C')
if abp:
    asset.set_editor_property('test_host_anim_class', abp)
report['test_host_anim_class'] = str(abp)
RESULT = {'saved': unreal.EditorLoadingAndSavingUtils.save_packages([asset.get_outermost()], True), 'fields': report}
