# Runs inside the Unreal editor (exec'd). Creates/refreshes /Game/Audio/Jam/Voice/DT_NpcVoiceRoster from voice/roster.json,
# using NPC unify's row struct FReflectionsNpcVoiceRow. Only voices that have a designed Gemini voice are written.
import json, os

ROOT = r"C:\Users\zachc\AppData\Local\Temp\claude\79559c54b34378d8\0ad1d4e2-870d-41ef-9980-50c658a16681\scratchpad\audio"
PATH, NAME = "/Game/Audio/Jam/Voice", "DT_NpcVoiceRoster"
AGE = {"young": 23, "adult": 35, "middle": 55, "older": 72}
CHAR = {"civilian": ["Civilian", "Tarnished"], "guard": ["Guard", "Tarnished"], "soldier": ["Soldier"]}

roster = json.load(open(os.path.join(ROOT, "voice", "roster.json"), encoding="utf-8"))
# Named story people (ArtDirection/Story/people.json via voice/script/story.json) keep their voice to themselves:
# bEnabled = false keeps the row out of random assignment; SetVoiceOverride / FindVoiceRow still find it.
_sp = os.path.join(ROOT, "voice", "script", "story.json")
_story = json.load(open(_sp, encoding="utf-8")) if os.path.exists(_sp) else {}
NAMED = {vid: pid for pid, vid in _story.get("Map", {}).items()}
rows = []
for v in roster:
    if not v.get("GeminiVoice") or (v["VoiceId"] in PILOT_ONLY_EXCLUDE if "PILOT_ONLY_EXCLUDE" in globals() else False):
        continue
    rows.append({"Name": v["VoiceId"], "Sex": "Female" if v["Sex"] == "F" else "Male", "Side": v["Side"],
                 "Characters": CHAR[v["Archetype"]], "Age": AGE[v["AgeBand"]],
                 "Description": (f"[named: {NAMED[v['VoiceId']]}] " if v["VoiceId"] in NAMED else "") + f"{v['Role']}: "
                                + (v.get("Brief") or v["Description"]),
                 "GeminiVoice": v["GeminiVoice"], "bEnabled": v["VoiceId"] not in NAMED})

struct = unreal.load_object(None, "/Script/reflections.ReflectionsNpcVoiceRow")
if struct is None:
    RESULT = "row struct not loaded yet"
else:
    try:
        dt = unreal.find_asset(f"{PATH}/{NAME}.{NAME}") or unreal.load_asset(f"{PATH}/{NAME}")
    except Exception:
        dt = None
    if dt is None:
        f = unreal.DataTableFactory()
        f.set_editor_property("struct", struct)
        dt = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, PATH, unreal.DataTable, f)
    ok = unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(dt, json.dumps(rows))
    unreal.EditorLoadingAndSavingUtils.save_packages([dt.get_package()], False)
    names = [str(n) for n in unreal.DataTableFunctionLibrary.get_data_table_row_names(dt)]
    RESULT = {"filled": ok, "rows": len(names), "first": names[:5], "reserved_for_named": len(NAMED)}
