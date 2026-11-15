"""Read the story session's scripted lines and named-person barks from ArtDirection/Story (read only).

    python story_lines.py           print counts per speaker and file
Scripted lines: table rows "| <LineId> | ... | <speaker id> | ... | "text" |" and variant bullets
"<LineId> becomes <LineId>B: "text"" in main-quest.md, cutscenes.md, side-quests.md.
Named-person barks: people.json -> people[].barks{intent: text}, story.cured_lines / tarnished_lines.
"""
import os, re, json, sys
from collections import Counter

STORY = r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\Story"
FILES = ["main-quest.md", "cutscenes.md", "side-quests.md"]
ID = r"(?:MQ\d\d_\d\d[A-Z]?|MQ_[A-Z]+_\d\d[A-Z]?|CS\d\d_\d\d[A-Z]?|SQ\d+_\d\d[A-Z]?)"


def people():
    return json.load(open(os.path.join(STORY, "people.json"), encoding="utf-8"))


def speakers():
    p = people()
    ids = {x["id"]: x.get("voice_id") for x in p["people"]}
    ids.update({x["id"]: None for x in p.get("principals", [])})
    ids.setdefault("the_tarnish", None)
    ids.setdefault("wren_hale", None)
    return ids


def scripted():
    """-> {line_id: (speaker, text, note, file)}"""
    spk = speakers()
    out = {}
    for f in FILES:
        for row in open(os.path.join(STORY, f), encoding="utf-8"):
            m = re.match(r"\|\s*(" + ID + r")\s*\|(.*)", row)
            if m:
                cells = [c.strip() for c in m.group(2).split("|")]
                who = next((c for c in cells if c in spk or c.startswith("victim")), None)
                quoted = re.findall(r'"([^"]+)"', m.group(2))
                if who and quoted:
                    note = " / ".join(c for c in cells if c and c != who and not c.startswith('"') and not re.match(r"^[\d.]+$", c))
                    out[m.group(1)] = (who, quoted[-1], note, f)
                continue
            for v in re.finditer(r"(" + ID + r") becomes (" + ID + r"):\s*\"([^\"]+)\"", row):
                base, var, text = v.groups()
                if base in out and var not in out:
                    out[var] = (out[base][0], text, "variant of " + base, f)
    return out


def barks():
    """-> [(person_id, voice_id, intent, text)]"""
    rows = []
    for x in people()["people"]:
        for intent, text in x.get("barks", {}).items():
            rows.append((x["id"], x["voice_id"], intent, text))
        for k in ("cured_lines", "tarnished_lines"):
            for i, text in enumerate(x.get("story", {}).get(k, []), 1):
                rows.append((x["id"], x["voice_id"], f"{k[:-6]}_{i}", text))
    return rows


if __name__ == "__main__":
    s = scripted()
    print(len(s), "scripted lines;", Counter(v[3] for v in s.values()))
    print("by speaker:", Counter(v[0] for v in s.values()).most_common())
    b = barks()
    print(len(b), "named barks;", Counter(r[2].split("_")[0] for r in b))
    if "-v" in sys.argv:
        for k, v in s.items():
            print(k, v[0], repr(v[1]), "|", v[2][:50])
