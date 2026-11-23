"""who_test.py - list every actor with a skeletal mesh in the play world (to find what stands next to the Hero)."""
import builtins
import unreal
import ar_proto as AR
W = builtins.__dict__.setdefault('_AR_WHO', {})


def snapshot():
    w = AR.world()
    rows = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        sk = a.get_components_by_class(unreal.SkeletalMeshComponent)
        if not sk:
            continue
        p = a.get_actor_location()
        try:
            label = a.get_actor_label()
        except Exception:
            label = '?'
        rows.append({'name': a.get_name(), 'label': label, 'class': a.get_class().get_path_name(), 'loc': [round(p.x), round(p.y), round(p.z)],
                     'tags': [str(t) for t in a.tags], 'owner': a.get_owner().get_name() if a.get_owner() else None,
                     'meshes': [(c.get_name(), c.get_skinned_asset().get_name() if c.get_skinned_asset() else None) for c in sk][:4]})
    return rows
