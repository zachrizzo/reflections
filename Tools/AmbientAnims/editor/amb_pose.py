# Pose the category sequence's spawned body on a baked clip at time T (globals CLIP, T). Sequencer scrubbing from
# Python does not update skeletal poses in this editor, so drive the body directly; capture in the NEXT call.
assert not pie(), 'PIE running'
seq = obj(AC.seq_path(CI))
assert L.get_current_level_sequence() == seq, 'category sequence not open'
clip = [c for c in AC.CATEGORIES[CI][2] if c['id'] == CLIP][0]
actor = L.get_bound_objects(seq.get_binding_id(body_binding(seq)))[0]
skm = actor.get_component_by_class(unreal.SkeletalMeshComponent)
skm.set_animation_mode(unreal.AnimationMode.ANIMATION_BLUEPRINT)
skm.override_animation_data(obj(AC.folder(CI) + '/' + AC.asset_name(CI, clip)), False, False, float(T), 0.0)
for c in actor.get_components_by_class(unreal.SkeletalMeshComponent):
    if c.get_name() == 'Face':
        cls = c.get_editor_property('anim_class')
        c.set_anim_instance_class(None)
        c.set_anim_instance_class(cls)
'posed %s %.2f' % (CLIP, float(T))
