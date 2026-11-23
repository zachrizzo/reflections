# Bake every generated clip of the category to its own AnimSequence (in place, no root motion) and tag it with
# the catalog data as asset metadata. Saves only the new clips; never a skeleton.
out = {}
assert not pie(), 'PIE running'
seq = obj(AC.seq_path(CI))
assert L.get_current_level_sequence() == seq, 'category sequence not open'
name = AC.CATEGORIES[CI][0]
mixer = mixer_of(seq)
anims = section_anims(sorted_sections(mixer))
body = L.get_bound_objects(seq.get_binding_id(body_binding(seq)))[0].get_component_by_class(unreal.SkeletalMeshComponent)
mesh = body.get_editor_property('skeletal_mesh_asset')
skel = mesh.get_editor_property('skeleton')
tools = unreal.AssetToolsHelpers.get_asset_tools()
E = unreal.EditorAssetLibrary
ONLY = globals().get('ONLY')
ROOTMOTION = globals().get('ROOTMOTION', False)  # SEQUENCER-movement takes already keep their small sway on the root
for i, (clip, start, seed) in enumerate(AC.layout(CI)):
    if ONLY and clip['id'] not in ONLY:
        continue
    if not generated(anims, i):
        out[clip['id']] = 'not generated'
        continue
    an = AC.asset_name(CI, clip)
    path = AC.folder(CI) + '/' + an
    if exists(path):
        anim = obj(path)
    else:
        f = unreal.AnimSequenceFactory()
        f.set_editor_property('target_skeleton', skel)
        f.set_editor_property('preview_skeletal_mesh', mesh)
        anim = tools.create_asset(an, AC.folder(CI), unreal.AnimSequence, f)
    o = unreal.AnimSeqExportOption()
    o.set_editor_property('use_custom_time_range', True)
    o.set_editor_property('custom_start_frame', unreal.FrameNumber(start))
    o.set_editor_property('custom_end_frame', unreal.FrameNumber(start + clip['frames'] - 1))  # end frame is inclusive
    o.set_editor_property('record_in_world_space', False)
    # Without this the bake pins the pelvis in place and every lean or step turns into foot sliding. With it the
    # body's travel lands on the root bone (in world space), which is re-based below so frame 0 is the origin.
    o.set_editor_property('map_skeletal_motion_to_root', ROOTMOTION)
    await call_tool('MovieSceneAnimMixerScripting.MovieSceneAnimMixerBakeExtensions.BakeToAnimSequenceAsync',
                    track=mixer, animSequence=anim, exportOptions=o, firstLayer=0, lastLayer=0)
    anim.set_preview_skeletal_mesh(mesh)
    anim.set_editor_property('enable_root_motion', False)
    if ROOTMOTION:
        X = unreal.AnimPoseExtensions
        eo = unreal.AnimPoseEvaluationOptions()
        n = anim.data_model_interface.get_number_of_keys()
        roots = [X.get_bone_pose(X.get_anim_pose_at_frame(anim, f, eo), 'root', unreal.AnimPoseSpaces.LOCAL) for f in range(n)]
        rel = [t.make_relative(roots[0]) for t in roots]
        anim.controller.set_bone_track_keys('root', [t.translation for t in rel], [t.rotation for t in rel],
                                            [t.scale3d for t in rel])
        out[clip['id'] + '_root_end'] = [round(v, 1) for v in (rel[-1].translation.x, rel[-1].translation.y,
                                                               rel[-1].translation.z, rel[-1].rotation.rotator().yaw)]
    for k, v in (('Ambient.Category', name), ('Ambient.Clip', clip['id']), ('Ambient.Kind', clip['kind']),
                 ('Ambient.Props', ', '.join(clip['props'])), ('Ambient.Jobs', ', '.join(clip['jobs'])),
                 ('Kimodo.Prompts', ' | '.join('%d: %s' % (o2, s2) for o2, s2 in clip['prompts'])),
                 ('Kimodo.Seed', str(seed)), ('Kimodo.Model', 'nvidia/Kimodo-SOMA-RP-v1.1')):
        E.set_metadata_tag(anim, k, v)
    out[clip['id']] = [round(anim.get_play_length(), 2), anim.data_model_interface.get_number_of_keys(), bool(save_mine(anim))]
    await asyncio.sleep(0)
save_mine(seq)  # keep the generated takes inside the source sequence too
out['skel'] = skel.get_path_name()
out['dirty_skel_unsaved'] = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
                             if 'skel' in p.get_name().lower()]
out
