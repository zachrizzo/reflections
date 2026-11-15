# Runs inside the Unreal editor (exec'd by execute_python). Globals: STEP = "waves" | "cues" | "tables", N (batch size).
# Imports the processed Gemini lines (voice/gemini/final/<id>.wav) and builds cues and conversation tables:
#   waves   next N not-yet-imported lines -> SoundWaves (subtitle, SCL_Jam_Voice; ambient waves also get ATT_Jam_NPCVoice)
#   cues    per-voice group cues /Cues/<Group>/SCue_VO_<Group>_<VoiceId>, story cues /Cues/SCue_VO_<LineId>
#   tables  /Game/Audio/Jam/Voice/Ambient/DT_AmbientConversations (generic cliques: the crowd director casts these)
#           /Game/Audio/Jam/Voice/Ambient/DT_StoryConversations (story cliques: only for the named people themselves)
import json, os, re, sys

ROOT = r"C:\Users\zachc\AppData\Local\Temp\claude\79559c54b34378d8\0ad1d4e2-870d-41ef-9980-50c658a16681\scratchpad\audio"
sys.path.insert(0, os.path.join(ROOT, "tools"))
import importlib
import story_import as ST
import synth_roster as SR
importlib.reload(ST); importlib.reload(SR)

VO = "/Game/Audio/Jam/Voice"
CUES, MIX = VO + "/Cues", "/Game/Audio/Jam/Mix"
FINAL = os.path.join(ROOT, "voice", "gemini", "final")
DONE_P = os.path.join(ROOT, "voice", "gemini", "ue_imported.json")
at = unreal.AssetToolsHelpers.get_asset_tools()
cue_sub = unreal.get_editor_subsystem(unreal.SoundCueEditorSubsystem)
L = unreal.load_asset
voice_cls, npc_att = L(f"{MIX}/SCL_Jam_Voice"), L(f"{MIX}/ATT_Jam_NPCVoice")
barks_con = L(f"{MIX}/SCON_Jam_Barks")
STEP = globals().get("STEP", "waves")
N = globals().get("N", 60)
ONLY = set(globals().get("ONLY_VOICES") or ())  # cues step: rebuild only these voices' cues (empty = all)
story = ST.load()
pmap = story.get("Map", {})


def subtitle(text):
    t = re.sub(r"<[^>]+>", "", text)
    t = re.sub(r"\b([A-Z]{2,})\b", lambda m: m.group(1).lower() if m.group(1) not in ("OK",) else m.group(1), t)
    t = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t.strip())
    return re.sub(r"\s{2,}", " ", t)


def dest(lid):
    """line id -> (folder, asset name, ambient?)"""
    k, rest = lid.split("_", 1)
    if k == "S":
        return f"{VO}/Story", f"SW_VO_{rest}", False
    if k in ("A", "SC", "C"):
        cid, conv, n = rest.rsplit("_", 2)
        return f"{VO}/Ambient/{cid}", f"SW_AMB_{cid}_{conv}_{n}", True
    if k == "B":
        g, vid = rest.rsplit("_", 2)[0].rsplit("_", 1)[0], rest.rsplit("_", 2)[1]
        return f"{VO}/Roster/{vid}", f"SW_{rest}", False
    if k == "R":
        vid = rest.split("_", 1)[0]
        return f"{VO}/Roster/{vid}", f"SW_{rest}", False
    if k == "SB":
        g, pid_n = rest.split("_", 1)
        pid, n = pid_n.rsplit("_", 1)
        return f"{VO}/Roster/{pmap[pid]}", f"SW_{g}_{pmap[pid]}_{n}", False
    if k == "P":
        pid, n = rest.rsplit("_", 1)
        return f"{VO}/Roster/{pmap[pid]}", f"SW_Persona_{pmap[pid]}_{n}", False
    raise ValueError(lid)


def asset_path(lid):
    folder, name, _ = dest(lid)
    return f"{folder}/{name}.{name}"


done = json.load(open(DONE_P)) if os.path.exists(DONE_P) else {}
AT_P = os.path.join(ROOT, "voice", "gemini", "ue_imported_at.json")
_base = os.path.getmtime(DONE_P) if os.path.exists(DONE_P) else 0.0  # lines imported before per-line times were kept
imported_at = json.load(open(AT_P)) if os.path.exists(AT_P) else {}
lines = {l[0]: l for l in SR.lines()}


def needs_import(lid):
    f = os.path.join(FINAL, lid + ".wav")
    return os.path.exists(f) and (lid not in done or os.path.getmtime(f) > imported_at.get(lid, _base) + 1)

if STEP == "waves":
    todo = [lid for lid in lines if needs_import(lid)][:N]
    tasks = []
    for lid in todo:
        folder, name, amb = dest(lid)
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", os.path.join(FINAL, lid + ".wav"))
        t.set_editor_property("destination_path", folder)
        t.set_editor_property("destination_name", name)
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("save", False)
        tasks.append((lid, amb, t))
    if tasks:
        at.import_asset_tasks([t for _, _, t in tasks])
    saved = []
    for lid, amb, t in tasks:
        paths = list(t.get_editor_property("imported_object_paths"))
        if not paths:
            continue
        w = L(paths[0])
        w.set_editor_property("sound_class_object", voice_cls)
        w.set_editor_property("compression_quality", 25 if amb else 40)  # distant street talk can afford a lower bitrate
        sc = unreal.SubtitleCue()
        sc.set_editor_property("text", unreal.Text(subtitle(lines[lid][2])))
        sc.set_editor_property("time", 0.0)
        w.set_editor_property("subtitles", [sc])
        if amb:
            w.set_editor_property("attenuation_settings", npc_att)  # the crowd director plays these waves from the head
        saved.append(w)
        done[lid] = paths[0]
        imported_at[lid] = __import__("time").time()
    if saved:
        unreal.EditorLoadingAndSavingUtils.save_packages([w.get_package() for w in saved], False)
    saved = len(saved)
    unreal.SystemLibrary.collect_garbage()  # release the imported audio data once saved (editor memory)
    json.dump(imported_at, open(AT_P, "w"), indent=1)
    json.dump(done, open(DONE_P, "w"), indent=1)
    left = sum(1 for lid in lines if needs_import(lid))
    RESULT = {"imported": saved, "total_imported": len(done), "ready_left": left,
              "not_processed_yet": sum(1 for lid in lines if not os.path.exists(os.path.join(FINAL, lid + ".wav")))}

elif STEP == "cues":
    def build_cue(folder, name, waves, att, bark):
        path = f"{folder}/{name}"
        cue = L(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else cue_sub.create_sound_cue(folder, name)
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
        cue_sub.set_root_node(cue, top)
        cue.set_editor_property("sound_class_object", voice_cls)
        cue.set_editor_property("attenuation_settings", att)
        cue.set_editor_property("concurrency_set", {barks_con} if bark else set())
        cue_sub.layout_sound_cue(cue)
        return cue

    def W(lid):
        return L(done[lid]) if lid in done else None

    groups = {}  # (group, VoiceId) -> [line ids]
    roster = {v["VoiceId"]: v for v in json.load(open(os.path.join(ROOT, "voice", "roster.json"), encoding="utf-8"))}
    talk = {"civilian": "Civilian_Talk", "guard": "Guard_Talk", "soldier": "Soldier_Talk"}
    for lid, (_, vid, _t, kind, _s) in lines.items():
        k, rest = lid.split("_", 1)
        if k == "B":
            groups.setdefault((rest.rsplit("_", 2)[0], vid), []).append(lid)
        elif k == "R":
            g = rest.split("_")[1]
            groups.setdefault((g, vid), []).append(lid)
            if g == "Reply":
                groups.setdefault((talk[roster[vid]["Archetype"]], vid), []).append(lid)
        elif k == "SB":
            g = rest.split("_", 1)[0]
            groups.setdefault((g, vid), []).append(lid)
            into = {"Flee": "Civilian_Fear", "SeeTarnished": "Civilian_Fear", "Idle": "Remark", "Dread": "Remark",
                    "Greet": "Reply", "TarnishedLine": "Tarnished_Mutter"}.get(g)
            if into:
                groups.setdefault((into, vid), []).append(lid)
                if into == "Reply":
                    groups.setdefault((talk[roster[vid]["Archetype"]], vid), []).append(lid)
        elif k == "P":
            groups.setdefault(("Reply", vid), []).append(lid)
            groups.setdefault((talk[roster[vid]["Archetype"]], vid), []).append(lid)
    # story barks that reuse a scripted take (same person, same words) point at that wave
    for pid, gs in story.get("Barks", {}).items():
        for g, items in gs.items():
            for x in items:
                if x.get("Take") and f"S_{x['Take']}" in done:
                    groups.setdefault((g, pmap[pid]), []).append(f"S_{x['Take']}")
    made, missing = 0, []
    BARK_GROUPS = {"Civilian_Fear", "Guard_Alert", "Guard_Attack", "Soldier_Command", "Tarnished_Mutter", "Flee", "SeeTarnished",
                   "TarnishedLine", "React_Hurt", "React_Knocked", "React_Burning", "React_Shocked", "React_Death",
                   "React_Effort", "Heat_CallGuards", "Heat_Halt", "Heat_Alarm", "Soldier_Battle"}
    for (g, vid), ids in sorted(groups.items()):
        if ONLY and vid not in ONLY:
            continue
        ws = [W(i) for i in ids if W(i)]
        if not ws:
            missing.append(f"{g}/{vid}"); continue
        build_cue(f"{CUES}/{g}", f"SCue_VO_{g}_{vid}", ws, npc_att, g in BARK_GROUPS)
        made += 1
    story_made = 0
    for lid, v in ({} if ONLY else story.get("Scripted", {})).items():
        src = f"S_{v['AliasOf'] or lid}"
        if v["Voice"] == "TARNISH" or src not in done:
            continue
        build_cue(CUES, f"SCue_VO_{lid}", [W(src)], npc_att if v["Att"] == "3D" else None, False)
        story_made += 1
    unreal.EditorAssetLibrary.save_directory(CUES, only_if_is_dirty=True, recursive=True)
    RESULT = {"group_cues": made, "story_cues": story_made, "groups_without_waves": len(missing), "examples_missing": missing[:8]}

elif STEP == "tables":
    SPOT = {"market stall": "market", "tram stop": "street", "laundry": "street", "bridge": "bridge", "tavern": "tavern",
            "street corner": "street", "festival square": "market", "bakery": "market", "city gate": "gate", "tower steps": "tower",
            "drill yard": "gate", "shelter": "street", "broth line": "market", "ruins": "street", "gate": "gate", "ice cut": "street",
            "alley": "street"}
    STORY_SPOT = {"lantern_row": "market", "lantern_gate": "gate", "lamplight": "tavern", "archive_steps": "street",
                  "muster_yard": "gate", "bell_lane": "tower", "coal_lane_stop": "street", "fish_steps": "market",
                  "weigh_house_corner": "market", "ice_stairs": "street", "bone_market": "market", "drifters_camp": "gate",
                  "long_shelter": "street"}

    def gap(text):
        return 0.5 if text.rstrip().endswith("?") else 0.35

    def table(name, rows):
        path = f"{VO}/Ambient/{name}"
        struct = unreal.load_object(None, "/Script/reflections.ReflectionsAmbientConversationRow")
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            dt = L(path)
        else:
            f = unreal.DataTableFactory(); f.set_editor_property("struct", struct)
            dt = at.create_asset(name, f"{VO}/Ambient", unreal.DataTable, f)
        ok = unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(dt, json.dumps(rows))
        unreal.EditorLoadingAndSavingUtils.save_packages([dt.get_package()], False)
        return ok, len(unreal.DataTableFunctionLibrary.get_data_table_row_names(dt))

    _probe = unreal.ReflectionsAmbientConversationRow()
    HAS_COND = hasattr(_probe, "band") and hasattr(_probe, "required_flag")
    generic, story_rows, skipped = [], [], 0
    cv = json.load(open(os.path.join(ROOT, "voice", "script", "conversations.json"), encoding="utf-8"))
    for cid, c in cv.items():
        for k, conv in enumerate(c["Conversations"], 1):
            ids = [f"A_{cid}_{k}_{n}" for n in range(1, len(conv["Lines"]) + 1)]
            if not all(i in done for i in ids):
                skipped += 1; continue
            generic.append({"Name": f"{cid}_{k}", "ConvId": f"{cid}_{k}", "Side": c["Side"], "CliqueId": cid,
                            "Spot": SPOT.get(conv.get("Spot", "").lower(), "street"), "Speakers": c["Voices"],
                            "Lines": [{"SpeakerIndex": l["S"] - 1, "Wave": done[i], "Subtitle": subtitle(l["Text"]),
                                       "Duration": 0.0, "GapAfter": gap(l["Text"])} for i, l in zip(ids, conv["Lines"])]})
    for cid, convs in story.get("Conversations", {}).items():
        side = next((c["side"] for c in ST.SL.people()["cliques"] if c["id"] == cid), "")
        for k, conv in enumerate(convs, 1):
            ids = [f"{'SC' if l.get('Locked') else 'C'}_{cid}_{k}_{n}" for n, l in enumerate(conv["Lines"], 1)]
            if not all(i in done for i in ids):
                skipped += 1; continue
            spk = []
            for l in conv["Lines"]:
                if pmap[l["P"]] not in spk:
                    spk.append(pmap[l["P"]])
            cond = conv["Seed"] + (f"_{conv['Band']}" if conv["Band"] else "") + (f"_{conv['Flag']}" if conv["Flag"] else "")
            row = {"Name": f"{cid}_{cond}", "ConvId": f"{cid}_{cond}", "Side": side, "CliqueId": cid,
                               "Spot": STORY_SPOT.get(cid, "street"), "Speakers": spk,
                               "Lines": [{"SpeakerIndex": spk.index(pmap[l["P"]]), "Wave": done[i], "Subtitle": subtitle(l["Text"]),
                                          "Duration": 0.0, "GapAfter": gap(l["Text"])} for i, l in zip(ids, conv["Lines"])]}
            if HAS_COND:  # train #7 row fields; the caller (lives) judges them, the director doesn't
                row["Band"] = conv["Band"] or "None"
                row["RequiredFlag"] = conv["Flag"] or "None"
            story_rows.append(row)
    r1 = table("DT_AmbientConversations", generic) if generic else (None, 0)
    r2 = table("DT_StoryConversations", story_rows) if story_rows else (None, 0)
    RESULT = {"ambient_rows": r1, "story_rows": r2, "skipped_incomplete": skipped, "band_flag_fields": HAS_COND}
