# Runs inside the Unreal editor (exec'd by execute_python). Expects IDS (list of line ids, or empty for all) in globals.
# Imports <work>/voice/final/<id>.wav as /Game/Audio/Jam/Voice/<Group>/SW_VO_<id> and builds the voice cues.
import json, os, sys

ROOT = r"C:\Users\zachc\AppData\Local\Temp\claude\79559c54b34378d8\0ad1d4e2-870d-41ef-9980-50c658a16681\scratchpad\audio"
sys.path.insert(0, os.path.join(ROOT, "tools"))
import importlib
import voice_script as V
importlib.reload(V)

JAM = "/Game/Audio/Jam"
MIX = JAM + "/Mix"
VO = JAM + "/Voice"
CUES = VO + "/Cues"
FINAL = os.path.join(ROOT, "voice", "final")
at = unreal.AssetToolsHelpers.get_asset_tools()
cue_sub = unreal.get_editor_subsystem(unreal.SoundCueEditorSubsystem)
L = unreal.load_asset
dirty = []


def get_or_create(path, name, cls, factory):
    try:
        a = unreal.find_asset(f"{path}/{name}.{name}") or L(f"{path}/{name}")
    except Exception:
        a = None
    return a or at.create_asset(name, path, cls, factory)


# --- Voice sound class (child of Master, through the jam limiter) and concurrency groups
master = L(f"{MIX}/SCL_Jam_Master")
voice_cls = get_or_create(MIX, "SCL_Jam_Voice", unreal.SoundClass, unreal.SoundClassFactory())
p = voice_cls.get_editor_property("properties")
p.set_editor_property("volume", 1.0)
p.set_editor_property("default_submix", L(f"{MIX}/SUB_Jam_Main"))
voice_cls.set_editor_property("properties", p)
voice_cls.set_editor_property("parent_class", master)
kids = list(master.get_editor_property("child_classes"))
if voice_cls not in kids:
    kids.append(voice_cls)
    master.set_editor_property("child_classes", kids)
dirty += [voice_cls, master]


def concurrency(name, max_count, rule, retrigger=0.0):
    c = get_or_create(MIX, name, unreal.SoundConcurrency, unreal.SoundConcurrencyFactory())
    s = c.get_editor_property("concurrency")
    s.set_editor_property("max_count", max_count)
    s.set_editor_property("resolution_rule", rule)
    s.set_editor_property("retrigger_time", retrigger)
    c.set_editor_property("concurrency", s)
    dirty.append(c)
    return c


R = unreal.MaxConcurrentResolutionRule
CON = {
    "bark": concurrency("SCON_Jam_Barks", 3, R.STOP_FARTHEST_THEN_OLDEST, 0.5),
    "tarnish": concurrency("SCON_Jam_Tarnish", 1, R.STOP_OLDEST),
    "narrator": concurrency("SCON_Jam_Narrator", 1, R.STOP_OLDEST),
}
CON["tarnished"] = CON["bark"]
def npc_voice_attenuation():
    """Speech from a position: full volume within 3 m, natural falloff to silence by ~28 m, slight air absorption, light occlusion."""
    a = get_or_create(MIX, "ATT_Jam_NPCVoice", unreal.SoundAttenuation, unreal.SoundAttenuationFactory())
    s = a.get_editor_property("attenuation")
    s.set_editor_property("attenuate", True)
    s.set_editor_property("spatialize", True)
    s.set_editor_property("distance_algorithm", unreal.AttenuationDistanceModel.NATURAL_SOUND)
    s.set_editor_property("attenuation_shape", unreal.AttenuationShape.SPHERE)
    s.set_editor_property("attenuation_shape_extents", unreal.Vector(300.0, 0, 0))  # inner radius: full volume
    s.set_editor_property("falloff_distance", 2500.0)  # silent at 300 + 2500 cm
    s.set_editor_property("d_b_attenuation_at_max", -60.0)
    s.set_editor_property("non_spatialized_radius_start", 60.0)
    s.set_editor_property("non_spatialized_radius_end", 20.0)
    s.set_editor_property("attenuate_with_lpf", True)  # air absorption: highs roll off with distance
    s.set_editor_property("lpf_radius_min", 800.0)
    s.set_editor_property("lpf_radius_max", 2800.0)
    s.set_editor_property("lpf_frequency_at_min", 20000.0)
    s.set_editor_property("lpf_frequency_at_max", 4500.0)
    s.set_editor_property("enable_occlusion", True)  # one line trace per playing voice; voices are short and capped by concurrency
    s.set_editor_property("occlusion_trace_channel", unreal.CollisionChannel.ECC_VISIBILITY)
    s.set_editor_property("occlusion_low_pass_filter_frequency", 2500.0)
    s.set_editor_property("occlusion_volume_attenuation", 0.6)
    s.set_editor_property("occlusion_interpolation_time", 0.2)
    a.set_editor_property("attenuation", s)
    dirty.append(a)
    return a


NPC_ATT = npc_voice_attenuation()
ATT = {"bark": NPC_ATT, "tarnished": NPC_ATT, "tarnish": NPC_ATT, "narrator": None}
HEAD_VARIANTS = {"Tarnish_Taunt", "Tarnish_Hop"}  # also built as 2D "_Head" cues for lines heard inside the player's head


def import_wave(lid, group, text):
    f = os.path.join(FINAL, lid + ".wav")
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", f)
    t.set_editor_property("destination_path", f"{VO}/{V.base_group(group)}")
    t.set_editor_property("destination_name", "SW_VO_" + lid)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", False)
    at.import_asset_tasks([t])
    w = L(list(t.get_editor_property("imported_object_paths"))[0])
    w.set_editor_property("sound_class_object", voice_cls)
    w.set_editor_property("compression_quality", 40)
    sc = unreal.SubtitleCue()
    sc.set_editor_property("text", unreal.Text(text))
    sc.set_editor_property("time", 0.0)
    w.set_editor_property("subtitles", [sc])
    dirty.append(w)
    return w


def build_cue(name, waves, kind):
    path = f"{CUES}/{name}"
    try:
        cue = unreal.find_asset(f"{path}.{name}") or L(path)
    except Exception:
        cue = None
    if cue is None:
        cue = cue_sub.create_sound_cue(CUES, name)
    else:
        for n in list(cue_sub.get_nodes(cue)):
            cue_sub.remove_node(cue, n)
    players = []
    for w in waves:
        wp = cue_sub.add_node(cue, unreal.SoundNodeWavePlayer)
        wp.set_editor_property("sound_wave_asset_ptr", w)
        players.append(wp)
    top = players[0]
    if len(players) > 1:
        rnd = cue_sub.add_node(cue, unreal.SoundNodeRandom)
        rnd.set_editor_property("randomize_without_replacement", True)
        for i, wp in enumerate(players):
            cue_sub.connect_nodes(cue, rnd, wp, i)
        top = rnd
    if kind == "bark":  # tiny pitch spread so repeated barks feel like different people; none on story voices
        mod = cue_sub.add_node(cue, unreal.SoundNodeModulator)
        mod.set_editor_property("pitch_min", 0.97)
        mod.set_editor_property("pitch_max", 1.04)
        mod.set_editor_property("volume_min", 0.92)
        mod.set_editor_property("volume_max", 1.0)
        cue_sub.connect_nodes(cue, mod, top, 0)
        top = mod
    cue_sub.set_root_node(cue, top)
    cue.set_editor_property("sound_class_object", voice_cls)
    cue.set_editor_property("attenuation_settings", ATT[kind])
    cue.set_editor_property("concurrency_set", {CON[kind]})
    cue.set_editor_property("volume_multiplier", 1.0)
    cue_sub.layout_sound_cue(cue)
    dirty.append(cue)
    return cue


rp = os.path.join(ROOT, "voice", "ue_report.json")
report = json.load(open(rp)) if os.path.exists(rp) else {}
want = set(IDS) if IDS else None
by_base = {}  # base group -> waves from all voice slots (for the fallback cue)
for group, (owner, event, mode) in V.GROUPS.items():
    lines = [l for l in V.LINES if l[1] == group and os.path.exists(os.path.join(FINAL, l[0] + ".wav"))]
    if want is not None and not any(l[0] in want for l in lines):
        continue
    waves = {l[0]: import_wave(l[0], group, l[3]) for l in lines}
    if not waves:
        continue
    kind = V.SPEAKERS[lines[0][2]][2]
    if V.base_group(group) != group:
        by_base.setdefault(V.base_group(group), (kind, []))[1].extend(waves.values())
    if mode == "random":
        c = build_cue(f"SCue_VO_{group}", list(waves.values()), kind)
        report[c.get_path_name().split(".")[0]] = [w.get_name() for w in waves.values()]
        if group in HEAD_VARIANTS:
            h = build_cue(f"SCue_VO_{group}_Head", list(waves.values()), kind)
            h.set_editor_property("attenuation_settings", None)  # 2D: inside the player's head
            report[h.get_path_name().split(".")[0]] = [w.get_name() for w in waves.values()]
    else:
        for lid, w in waves.items():
            c = build_cue(f"SCue_VO_{lid}", [w], V.SPEAKERS[[l for l in lines if l[0] == lid][0][2]][2])
            if getattr(V, "STORY_ATT", {}).get(lid) == "2D":
                c.set_editor_property("attenuation_settings", None)  # story line played 2D (cutscene / announcer)
            report[c.get_path_name().split(".")[0]] = [w.get_name()]
# Fallback cue per base group (same path as before): random over every voice slot's lines.
for base, (kind, waves) in by_base.items():
    c = build_cue(f"SCue_VO_{base}", waves, kind)
    report[c.get_path_name().split(".")[0]] = [w.get_name() for w in waves]

unreal.EditorLoadingAndSavingUtils.save_packages(list({o.get_package() for o in dirty}), False)
json.dump(report, open(rp, "w"), indent=1)
RESULT = report
