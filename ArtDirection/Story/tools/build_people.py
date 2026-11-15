import json, sys, re, collections, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import people_src as S
import people_meta as M

ROOT = r"C:\Users\zachc\Documents\Unreal Projects\reflections"
roster = {v["VoiceId"]: v for v in json.load(open(os.path.join(ROOT, r"ArtDirection\Audio\data\voice_roster.json"), encoding="utf-8"))}
people = S.PEOPLE
ids = [p["id"] for p in people]
errors = []
dupe_ids = [i for i, n in collections.Counter(ids).items() if n > 1]
if dupe_ids: errors.append(f"duplicate ids {dupe_ids}")
known = set(ids) | {p["id"] for p in M.PRINCIPALS}
vids = collections.Counter(p["voice_id"] for p in people)
for v, n in vids.items():
    if n > 1: errors.append(f"voice {v} used {n} times")
for p in people:
    r = roster.get(p["voice_id"])
    if not r: errors.append(f"{p['id']}: voice {p['voice_id']} not in roster"); continue
    if r["Sex"] != p["sex"]: errors.append(f"{p['id']}: voice sex {r['Sex']} != {p['sex']}")
    if r["Side"] != p["side"]: errors.append(f"{p['id']}: voice side {r['Side']} != {p['side']}")
    for ref in [f["id"] for f in p["family"]] + p["friends"] + p.get("rivals", []):
        if ref not in known: errors.append(f"{p['id']}: unknown ref {ref}")
    if p["schedule"]["template"] not in M.SCHEDULES["templates"]: errors.append(f"{p['id']}: schedule {p['schedule']['template']}")
clique_members = {m: c["id"] for c in M.CLIQUES for m in c["members"]}
for p in people:
    if p["clique"] and clique_members.get(p["id"]) != p["clique"]: errors.append(f"{p['id']}: clique mismatch")
for c in M.CLIQUES:
    for m in c["members"]:
        if m not in ids: errors.append(f"clique {c['id']}: unknown member {m}")

# Line uniqueness across everyone (normalised: lowercase, letters only)
norm = lambda s: re.sub(r"[^a-z ]", "", s.lower()).strip()
seen = {}
for p in people:
    lines = list(p["barks"].values()) + p["story"].get("cured_lines", []) + p["story"].get("tarnished_lines", []) + [p["opinion_of_silverer"]["line"]]
    for l in lines:
        k = norm(l)
        if k in seen and seen[k] != p["id"]:
            errors.append(f"line shared by {seen[k]} and {p['id']}: {l}")
        seen[k] = p["id"]
# never-say check
banned = re.compile(r"\b(london|kell|lila|holland|rhy|osaron|antari|travars|traveller)\b", re.I)
blob = json.dumps(people) + json.dumps(M.CLIQUES)
for m in banned.finditer(blob): errors.append(f"never-say word: {m.group(0)}")

for p in people:
    p["title"] = p["job"]; p["role"] = p["look_role"]
    p["markers_story"] = {"home": f"Home_{p['id']}",
                          "work": M.STORY_NAMES.get(p["markers"]["work"], f"Home_{p['id']}" if "_Home" in p["markers"]["work"] else p["markers"]["work"]),
                          "haunt": M.STORY_NAMES.get(p["markers"]["haunt"], p["markers"]["haunt"])}
    for k in ("work", "haunt"):
        if p["markers_story"][k].startswith("Mk_"): errors.append(f"{p['id']}: no story name for {p['markers_story'][k]}")
for c in M.CLIQUES:
    c["spot_story"] = M.STORY_NAMES.get(c["spot"])
# Pinned crowd looks (Tools/CrowdLooks/cast.json): Lives and the quest pack read "look" as a look-id string and match it
# against the look Blueprint's class name. The descriptive look object moves to "appearance".
cast = {l["id"]: l for l in json.load(open(os.path.join(ROOT, r"Tools\CrowdLooks\cast.json"), encoding="utf-8"))["looks"]}
pinned = 0
for p in people:
    p["appearance"] = p.pop("look")
    lid = M.LOOK_PINS.get(p["id"])
    if lid:
        l = cast.get(lid)
        if not l: errors.append(f"{p['id']}: look {lid} not in cast.json"); continue
        if l["sex"] != p["sex"] or l["side"] != p["side"]: errors.append(f"{p['id']}: look {lid} is {l['sex']}/{l['side']}")
        p["look"] = lid; pinned += 1
if len(set(M.LOOK_PINS.values())) != len(M.LOOK_PINS): errors.append("a look is pinned to two people")
print(f"{pinned} people pinned to a crowd look")
out = {
    "readme": M.README,
    "dialogue_rules": M.DIALOGUE_RULES,
    "infection_bands": M.INFECTION_BANDS,
    "markers": M.MARKERS,
    "schedules": M.SCHEDULES,
    "principals": M.PRINCIPALS,
    "cliques": M.CLIQUES,
    "people": people,
    "generator": M.GENERATOR,
}
print(f"{len(people)} people, {len(M.CLIQUES)} cliques, {len(seen)} unique lines")
if errors:
    print("ERRORS:"); [print(" ", e) for e in errors]
if len(sys.argv) > 1 and not errors:
    json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", sys.argv[1], os.path.getsize(sys.argv[1]))
