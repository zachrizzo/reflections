# Build an already-made person. Globals: PID, QUALITY ('CINEMATIC' or 'OPTIMIZED:<LOW|MEDIUM|HIGH>'), OUTDIR (optional)
import json, time
ROOT = '/Game/Characters/Lanthorne/People'
sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
mhc = unreal.load_asset('%s/%s/MHC_%s' % (ROOT, PID, PID))
sub.try_add_object_to_edit(mhc)
out = {'can_build': sub.can_build_meta_human(mhc, True)}
T0 = time.time()
if out['can_build']:
    p = unreal.MetaHumanCharacterEditorBuildParameters()
    kind, _, q = QUALITY.partition(':')
    p.set_editor_property('pipeline_type', getattr(unreal.MetaHumanDefaultPipelineType, kind))
    if q:
        p.set_editor_property('pipeline_quality', getattr(unreal.MetaHumanQualityLevel, q))
    p.set_editor_property('common_folder_path', ROOT + '/Common')
    p.set_editor_property('absolute_build_path', globals().get('OUTDIR') or ('%s/%s/Assembled' % (ROOT, PID)))
    sub.build_meta_human(mhc, p)
out['secs'] = round(time.time() - T0, 1)
RESULT = json.dumps(out)
