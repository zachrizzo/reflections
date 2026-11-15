# The NPC walker picks /Game/Characters/CrowdMotion/ABP_Crowd_<Body> from the Body mesh name
# (UReflectionsNpcReactionComponent::InitializeLocomotion). FerryPilot and GlassArtisan bodies have none, so their
# looks could not walk. Both are male MetaHuman bodies on the shared skeleton: copy the Archive Apprentice one.
import json
eal = unreal.EditorAssetLibrary
out = {}
for body in ('FerryPilot', 'GlassArtisan'):
    dst = '/Game/Characters/CrowdMotion/ABP_Crowd_' + body
    if not eal.does_asset_exist(dst):
        eal.duplicate_asset('/Game/Characters/CrowdMotion/ABP_Crowd_ArchiveApprentice', dst)
        eal.save_asset(dst, only_if_is_dirty=False)
        out[body] = 'created'
    else:
        out[body] = 'exists'
RESULT = json.dumps(out)
