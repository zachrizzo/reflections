"""Finds any spoken line used twice across the story folder (people.json + every .md). Run from anywhere."""
import json, re, os, collections, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
norm = lambda s: re.sub(r"[^a-z ]", "", s.lower()).strip()
hits = collections.defaultdict(list)
people = json.load(open(os.path.join(HERE, "people.json"), encoding="utf-8"))
for p in people["people"]:
    lines = list(p["barks"].values()) + p["story"].get("cured_lines", []) + p["story"].get("tarnished_lines", []) + [p["opinion_of_silverer"]["line"]]
    for l in lines:
        hits[norm(l)].append(f"people.json:{p['id']}")
for f in sorted(os.listdir(HERE)):
    if not f.endswith(".md") or f == "conversations_seeds.md": continue
    for i, row in enumerate(open(os.path.join(HERE, f), encoding="utf-8"), 1):
        if row.startswith("<!-- BARKS"): break
        if "|" in row and "(existing)" in row: continue
        for m in re.finditer(r'"([^"]{12,})"', row):
            t = m.group(1)
            if t.count(" ") < 2: continue
            hits[norm(t)].append(f"{f}:{i}")
dupes = {k: v for k, v in hits.items() if len(set(x.split(':')[0] + x.split(':')[1] if x.startswith('people') else x for x in v)) > 1}
for k, v in sorted(dupes.items()):
    print(f"{k[:70]!r}: {v}")
print(f"{len(hits)} distinct lines, {len(dupes)} used more than once")
