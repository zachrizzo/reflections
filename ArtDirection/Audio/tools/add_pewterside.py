"""Add 12 unnamed Pewterside civilian voices (V121-V132): the story's named cast took 12 of Pewterside's 16 voices,
leaving unnamed Pewterside crowds 1 female and 0 male civilian voices. Same fields and style as roster.py.
    python add_pewterside.py      (idempotent: skips ids that exist)
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roster as RO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "voice", "roster.json")
AGE = {a[0]: a for a in RO.AGES}
NEW = [  # (sex, age band, role, attitude, accent, timbre, texture)
    ("F", "young", "tram conductor", "brisk and practical", "Yorkshire", "sharp and quick", "with a lively bounce"),
    ("F", "adult", "seamstress", "quietly worried", "lilting Welsh", "soft and velvety", "with a faint quaver"),
    ("F", "adult", "fishmonger", "dry and matter-of-fact", "broad northern English", "throaty and rough", "with a gruff edge"),
    ("F", "middle", "bookbinder", "weary but polite", "crisp, refined southern English", "crisp and precise", "with an even steadiness"),
    ("F", "middle", "tea-stall keeper", "kind but rushed", "West African-British", "rich and rounded", "with a sing-song lilt"),
    ("F", "older", "pensioner", "gloomy and wry", "rural West Country", "thin and reedy", "with a tired drawl"),
    ("F", "older", "newspaper seller", "kind but rushed", "Midlands", "deep for a woman, steady", "with a slight rasp"),
    ("M", "young", "newspaper seller", "kind but rushed", "working-class southern English", "light, boyish tenor", "with a lively bounce"),
    ("M", "adult", "tram conductor", "dry and matter-of-fact", "lilting Welsh", "mellow and smooth", "with an even steadiness"),
    ("M", "middle", "fishmonger", "gloomy and wry", "Eastern European", "booming and broad", "with a gruff edge"),
    ("M", "middle", "bookbinder", "quietly worried", "soft Scottish", "soft-spoken and gentle", "with an airy edge"),
    ("M", "older", "seamstress", "weary but polite", "Caribbean-British", "hoarse and cracked", "with a faint quaver"),
]

r = json.load(open(P, encoding="utf-8"))
have = {v["VoiceId"] for v in r}
n = 121
for sex, band, role, att, acc, timbre, tex in NEW:
    vid = f"V{n:03d}"; n += 1
    if vid in have:
        continue
    age = AGE[band][1] if sex == "F" else AGE[band][2]
    r.append({"VoiceId": vid, "Sex": sex, "Side": "Pewterside", "AgeBand": band, "Archetype": "civilian", "Role": role,
              "Attitude": att, "Accent": acc,
              "Description": f"A {role} {age}: a {timbre} voice {tex}; {att}, with a {acc} accent.", "Added": "pewterside-fill"})
json.dump(r, open(P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(len(r), "voices;", sum(1 for v in r if v["Side"] == "Pewterside"), "Pewterside")
