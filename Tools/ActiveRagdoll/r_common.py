import builtins, importlib, json, sys, time, math
SP = r'C:\Users\zachc\Documents\Unreal Projects\reflections\Tools\ActiveRagdoll'
if SP not in sys.path: sys.path.append(SP)
LOCKF = r'C:\Users\zachc\Documents\Unreal Projects\reflections\Saved\PIE_LOCK.json'
ME = 'active-ragdoll local_6fe2a304'
def lock_mine():
    try:
        l = json.load(open(LOCKF, encoding='utf-8'))
        return l.get('owner') == ME and float(l.get('expires_epoch', 0)) > time.time()
    except Exception:
        return False
import ar_proto
importlib.reload(ar_proto)
AR = ar_proto
def cam(eye, aim):
    e = unreal.Vector(*eye); a = unreal.Vector(*aim)
    rot = unreal.MathLibrary.find_look_at_rotation(e, a)
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(e, rot)
