"""Guard for the shared MetaHuman skeletons (orchestrator, 20:25).

Opening a donor MetaHuman for editing, or building one whose body shares a Common folder, can rewrite that folder's
metahuman_base_skel IN MEMORY (14 Nov: the BridgeGuard Common skeleton lost its 'root' bone and gained Rig_FerryPilot;
a later save wrote it to disk and T-posed half the cast). Rule: my scripts never save a shared skeleton.
skel_guard() finds every dirty skeleton package outside my own folder and reloads it from disk, returning their names.
"""


def skel_guard(log=None):
    mine = '/Game/Characters/Lanthorne/'
    dirty = []
    for pkg in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
        name = pkg.get_name()
        if name.startswith(mine):
            continue
        if 'skel' in name.lower() or name.lower().endswith('_skeleton'):
            dirty.append(pkg)
    names = [p.get_name() for p in dirty]
    if dirty:
        unreal.EditorLoadingAndSavingUtils.reload_packages(dirty, unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
        unreal.log_warning('crowd-looks skel_guard: reloaded from disk (never saved): %s' % names)
    if log is not None:
        log.setdefault('skel_guard', []).extend(names)
    return names
