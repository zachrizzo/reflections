"""Add 5 unnamed women guard voices (V133-V137). The story's named cast took every Giltside and Pewterside women's
guard voice, leaving unnamed women guards 2 voices in all (V049, V056, both Frostside), so a third spilled into a
civilian voice and the shared slot cue (NPC unify, PIE 2026-11-14). Same fields and style as roster.py.
    python add_guards.py      (idempotent: skips ids that exist)
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roster as RO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "voice", "roster.json")
AGE = {a[0]: a for a in RO.AGES}
NEW = [  # (side, age band, role, attitude, accent, timbre, texture); all women, archetype guard
    ("Giltside", "adult", "bridge guard", "proud and confident", "crisp, refined southern English", "bright, clear soprano",
     "with an even steadiness"),
    ("Giltside", "middle", "city watch sergeant", "loud and jolly", "broad northern English", "rich and rounded", "with a gruff edge"),
    ("Pewterside", "young", "watch constable", "brisk and practical", "Merseyside-style", "crisp and precise", "with an airy edge"),
    ("Pewterside", "older", "night watchman", "gloomy and wry", "northeastern English", "warm, low alto", "with a tired drawl"),
    ("Frostside", "middle", "rune-marked sentry", "fierce and defiant", "Eastern European", "deep for a woman, steady",
     "with a slight rasp"),
]

r = json.load(open(P, encoding="utf-8"))
have = {v["VoiceId"] for v in r}
n = 133
for side, band, role, att, acc, timbre, tex in NEW:
    vid = f"V{n:03d}"; n += 1
    if vid in have:
        continue
    r.append({"VoiceId": vid, "Sex": "F", "Side": side, "AgeBand": band, "Archetype": "guard", "Role": role,
              "Attitude": att, "Accent": acc,
              "Description": f"A {role} {AGE[band][1]}: a {timbre} voice {tex}; {att}, with a {acc} accent.", "Added": "guard-fill"})
json.dump(r, open(P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(len(r), "voices;", sum(1 for v in r if v["Archetype"] == "guard" and v["Sex"] == "F"), "women guard voices")
