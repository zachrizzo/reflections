"""Write ArtDirection/Audio/data/voice_roster_dialogue.json for the NPC dialogue relay:
{"voices": {"V103": {"gemini_voice": "voice_...", "sex": "Male", "side": "Frostside", "persona": "...", "style": "...",
                      "named": "person_id" | null, "cue_talk": "/Game/Audio/Jam/Voice/Cues/Guard_Talk/SCue_VO_Guard_Talk_V103"}}}
style = the baseline delivery the baked lines use (named people: people.json delivery; others: the roster attitude).
No keys or secrets in this file. The designed voices only work with the project's own Gemini key.
"""
import os, json, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_lines as SL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\Audio\data\voice_roster_dialogue.json"
TALK = {"civilian": "Civilian_Talk", "guard": "Guard_Talk", "soldier": "Soldier_Talk"}

roster = json.load(open(os.path.join(ROOT, "voice", "roster.json"), encoding="utf-8"))
people = {x["voice_id"]: x for x in SL.people()["people"]}
out = {}
for v in roster:
    if not v.get("GeminiVoice"):
        continue
    p = people.get(v["VoiceId"])
    if p:
        persona = f"{p['name']}, {p['job']}, {p['side']}. {p['personality']['speech_style']}"
        style = p["voice_design"].get("delivery", "")
    else:
        persona = f"a {v['Role']} in {v['Side']}, {v['Attitude']}"
        style = re.sub(r"\s+and\s+", ", ", v["Attitude"])
    group = TALK[v["Archetype"]]
    out[v["VoiceId"]] = {"gemini_voice": v["GeminiVoice"], "sex": "Female" if v["Sex"] == "F" else "Male", "side": v["Side"],
                         "persona": persona, "style": style, "named": p["id"] if p else None,
                         "cue_talk": f"/Game/Audio/Jam/Voice/Cues/{group}/SCue_VO_{group}_{v['VoiceId']}"}
json.dump({"_readme": __doc__.strip(), "voices": out}, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(OUT, len(out), "voices,", sum(1 for x in out.values() if x["named"]), "named")
