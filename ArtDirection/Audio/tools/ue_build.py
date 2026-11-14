# Runs inside the Unreal editor (exec'd by execute_python). Expects NAMES (list of catalog names) in globals.
import json, os, glob

ROOT = r"C:\Users\zachc\AppData\Local\Temp\claude\79559c54b34378d8\0ad1d4e2-870d-41ef-9980-50c658a16681\scratchpad\audio"
JAM = "/Game/Audio/Jam"
MIX = JAM + "/Mix"
CUES = JAM + "/Cues"
cat = json.load(open(os.path.join(ROOT, "catalog.json")))
SFX = {s["name"]: s for s in cat["sfx"]}
MUS = {m["name"]: m for m in cat["music"]}
SOURCES = json.load(open(os.path.join(ROOT, "proc", "final", "sources.json")))

at = unreal.AssetToolsHelpers.get_asset_tools()
cue_sub = unreal.get_editor_subsystem(unreal.SoundCueEditorSubsystem)
EAL = unreal.EditorAssetLibrary
L = unreal.load_asset
CLS = {k: L(f"{MIX}/SCL_Jam_{k}") for k in ["SFX", "UI", "Music_World", "Music_Combat"]}
ATT = {k: L(f"{MIX}/ATT_Jam_{k}") for k in ["Small", "Medium", "Large"]}
report = {}
dirty = []


def import_wavs(files, dest):
    tasks = []
    for f in files:
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", f)
        t.set_editor_property("destination_path", dest)
        t.set_editor_property("destination_name", "SW_" + os.path.splitext(os.path.basename(f))[0])
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("save", False)
        tasks.append(t)
    at.import_asset_tasks(tasks)
    out = []
    for t in tasks:
        paths = list(t.get_editor_property("imported_object_paths"))
        out.append(L(paths[0]) if paths else None)
    return out


def remove_stale_waves(dest, name, keep):
    """Delete SW_<name>_NN waves left from an earlier run that had more takes (own assets only)."""
    content = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    for k in range(1, 16):
        base = f"SW_{name}_{k:02d}"
        if base in keep:
            continue
        rel = dest.replace("/Game/", "") + f"/{base}.uasset"
        if os.path.exists(os.path.join(content, rel)):
            obj = L(f"{dest}/{base}")
            if obj is not None:
                sub.delete_loaded_asset(obj)


def get_cue(name):
    path = f"{CUES}/SCue_{name}"
    try:
        cue = unreal.find_asset(path + "." + f"SCue_{name}") or L(path)
    except Exception:
        cue = None
    if cue is None:
        cue = cue_sub.create_sound_cue(CUES, f"SCue_{name}")
    else:
        for n in list(cue_sub.get_nodes(cue)):
            cue_sub.remove_node(cue, n)
    return cue


def build_cue(name, waves, loop, pitch, cls, att, vol):
    cue = get_cue(name)
    players = []
    for w in waves:
        wp = cue_sub.add_node(cue, unreal.SoundNodeWavePlayer)
        wp.set_editor_property("sound_wave_asset_ptr", w)
        wp.set_editor_property("looping", bool(loop))
        players.append(wp)
    top = players[0]
    if len(players) > 1:
        rnd = cue_sub.add_node(cue, unreal.SoundNodeRandom)
        rnd.set_editor_property("randomize_without_replacement", True)
        for i, wp in enumerate(players):
            cue_sub.connect_nodes(cue, rnd, wp, i)
        top = rnd
    if pitch:
        mod = cue_sub.add_node(cue, unreal.SoundNodeModulator)
        mod.set_editor_property("pitch_min", pitch[0])
        mod.set_editor_property("pitch_max", pitch[1])
        mod.set_editor_property("volume_min", 0.92 if not loop else 0.96)
        mod.set_editor_property("volume_max", 1.0)
        cue_sub.connect_nodes(cue, mod, top, 0)
        top = mod
    cue_sub.set_root_node(cue, top)
    cue.set_editor_property("sound_class_object", cls)
    cue.set_editor_property("volume_multiplier", vol)
    cue.set_editor_property("attenuation_settings", att)
    cue_sub.layout_sound_cue(cue)
    dirty.append(cue)
    return cue


for name in NAMES:
    if name in SFX:
        s = SFX[name]
        files = sorted(glob.glob(os.path.join(ROOT, "proc", "final", "sfx", f"{name}_[0-9][0-9].wav")))
        source = SOURCES[name]["source"]
        dest = f"{JAM}/SFX/{s['folder']}"
        waves = [w for w in import_wavs(files, dest) if w]
        remove_stale_waves(dest, name, {w.get_name() for w in waves})
        cls = CLS[s["cls"]]
        for w in waves:
            w.set_editor_property("looping", bool(s["loop"]))
            w.set_editor_property("sound_class_object", cls)
            w.set_editor_property("compression_quality", 40)
            dirty.append(w)
        cue = build_cue(name, waves, s["loop"], s["pitch"], cls, ATT.get(s["att"]) if s["att"] else None, s["vol"])
    else:
        m = MUS[name]
        files = [os.path.join(ROOT, "proc", "final", "music", f"{name}.wav")]
        source = SOURCES[name]["source"]
        dest = f"{JAM}/Music"
        waves = [w for w in import_wavs(files, dest) if w]
        cls = CLS[m["cls"]]
        for w in waves:
            w.set_editor_property("looping", bool(m["loop"]))
            w.set_editor_property("sound_class_object", cls)
            w.set_editor_property("compression_quality", 50)
            dirty.append(w)
        cue = build_cue(name, waves, m["loop"], None, cls, None, m["vol"])
    report[name] = {
        "source": source,
        "cue": cue.get_path_name().split(".")[0],
        "waves": [w.get_path_name().split(".")[0] for w in waves],
        "dur": [round(w.get_editor_property("duration"), 2) for w in waves],
        "ch": [w.get_editor_property("num_channels") for w in waves],
    }

unreal.EditorLoadingAndSavingUtils.save_packages(list({o.get_package() for o in dirty}), False)
_rp = os.path.join(ROOT, "ue_report.json")
_old = json.load(open(_rp)) if os.path.exists(_rp) else {}
_old.update(report)
json.dump(_old, open(_rp, "w"), indent=1)
RESULT = report
