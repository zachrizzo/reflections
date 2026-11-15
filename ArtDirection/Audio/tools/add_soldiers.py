"""Add 8 Giltside soldier voices (V138-V145) for the allied Giltside squads (orchestrator batch, 2026-11-14 evening):
4 men and 4 women, Archetype soldier, unnamed (bEnabled true). Same fields and style as roster.py.
    python add_soldiers.py      (idempotent: skips ids that exist)
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roster as RO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "voice", "roster.json")
AGE = {a[0]: a for a in RO.AGES}
NEW = [  # (sex, age band, role, attitude, accent, timbre, texture); all Giltside soldiers
    ("M", "young", "squire", "earnest and eager", "Yorkshire", "light, boyish tenor", "with a lively bounce"),
    ("M", "adult", "spearman", "teasing and playful", "Merseyside-style", "raspy", "with a gruff edge"),
    ("M", "middle", "sergeant-at-arms", "proud and confident", "broad northern English", "booming and broad",
     "with an even steadiness"),
    ("M", "older", "veteran swordsman", "gracious", "soft Scottish", "gravelly", "with a tired drawl"),
    ("F", "young", "standard bearer", "cheerful and warm", "lilting Welsh", "bright, clear soprano", "with a sing-song lilt"),
    ("F", "adult", "shield-bearer", "proud and confident", "South Asian-British", "warm, low alto", "with an even steadiness"),
    ("F", "middle", "squad sergeant", "loud and jolly", "rural West Country", "throaty and rough", "with a gruff edge"),
    ("F", "adult", "swordswoman", "teasing and playful", "gentle Irish", "husky, smoky", "with a smooth finish"),
]

r = json.load(open(P, encoding="utf-8"))
have = {v["VoiceId"] for v in r}
n = 138
for sex, band, role, att, acc, timbre, tex in NEW:
    vid = f"V{n:03d}"; n += 1
    if vid in have:
        continue
    age = AGE[band][1] if sex == "F" else AGE[band][2]
    r.append({"VoiceId": vid, "Sex": sex, "Side": "Giltside", "AgeBand": band, "Archetype": "soldier", "Role": role,
              "Attitude": att, "Accent": acc,
              "Description": f"A {role} {age}: a {timbre} voice {tex}; {att}, with a {acc} accent.", "Added": "giltside-squads"})
json.dump(r, open(P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(len(r), "voices;", sum(1 for v in r if v["Archetype"] == "soldier" and v["Side"] == "Giltside"), "Giltside soldier voices")
