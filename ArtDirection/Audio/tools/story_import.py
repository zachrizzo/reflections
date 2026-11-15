"""Import the story session's lines (ArtDirection/Story, read only) into voice/script/story.json for the audio pipeline.

    python story_import.py            (re)build story.json; keeps styles already drafted for unchanged lines
story.json = {
  "Map":      {person_id: VoiceId}                      resolved from people.json at import time
  "Scripted": {LineId: {Person, Voice, Text, Style, Att, FX, AliasOf}}   Voice: VoiceId | "HERO" | "TARNISH"
  "Barks":    {person_id: {Group: [{Text, Style}]}}     story-written, protected from rewrites
  "Replies":  {person_id: [{Text, Style}]}              persona replies (drafted here; rewritable)
}
Cues: scripted -> /Game/Audio/Jam/Voice/Cues/SCue_VO_<LineId>; barks -> /Cues/<Group>/SCue_VO_<Group>_<VoiceId>.
"""
import sys, os, json, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_lines as SL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "voice", "script")
OUT = os.path.join(SCRIPT, "story.json")
INTENT_GROUP = {"greet": "Greet", "idle": "Idle", "see_tarnished": "SeeTarnished", "flee": "Flee", "spell_near": "SpellNear",
                "thanks": "Thanks", "dread": "Dread", "farewell": "Farewell",
                # story batch 2 (2026-11-14 evening): reactions, heat and soldiers' battle lines
                "witness_crime": "WitnessCrime", "flee_silverer": "FleeSilverer", "call_guards": "CallGuards",
                "knocked_down": "KnockedDown", "on_fire": "OnFire", "shocked": "Shocked", "mourning": "Grief",  # Lives plays Grief
                "battle_1": "Battle", "battle_2": "Battle", "patrol_1": "Patrol", "patrol_2": "Patrol",
                "enemy_down": "EnemyDown"}
TARNISH_3D = {"MQ09_01", "MQ09_03", "MQ09_05"}
HERO_3D = {"MQ09_02", "MQ09_04"}


def load():
    return json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}


def speaker_name(voice):
    return {"HERO": "Wren", "TARNISH": "Tarnish"}.get(voice, voice)


def suppressed(story=None):
    """Generic per-voice lines replaced by a named person's story lines: {(kind, VoiceId)}.
    kind: 'Civilian_Fear' / 'Tarnished_Mutter' (barks.json groups), 'Remark' / 'Reply' (voice_lines.json)."""
    story = story if story is not None else load()
    out = set()
    for pid, vid in story.get("Map", {}).items():
        b = story.get("Barks", {}).get(pid, {})
        if "Flee" in b or "SeeTarnished" in b:
            out.add(("Civilian_Fear", vid))
        if "Idle" in b or "Dread" in b:
            out.add(("Remark", vid))
        if story.get("Replies", {}).get(pid):
            out.add(("Reply", vid))
        if "TarnishedLine" in b:
            out.add(("Tarnished_Mutter", vid))
    return out


def story_lines(story=None):
    """[(line_id, speaker, text)] for the checker: scripted (S_), story barks (SB_, protected), persona replies (P_)."""
    story = story if story is not None else load()
    out = []
    for lid, v in story.get("Scripted", {}).items():
        if not v.get("AliasOf"):
            out.append((f"S_{lid}", speaker_name(v["Voice"]), v["Text"]))
    for pid, groups in story.get("Barks", {}).items():
        for g, items in groups.items():
            out += [(f"SB_{g}_{pid}_{i}", story["Map"][pid], x["Text"]) for i, x in enumerate(items, 1) if not x.get("Take")]
    for pid, items in story.get("Replies", {}).items():
        out += [(f"P_{pid}_{i}", story["Map"][pid], x["Text"]) for i, x in enumerate(items, 1)]
    for cid, convs in story.get("Conversations", {}).items():
        for k, conv in enumerate(convs, 1):
            for n, l in enumerate(conv["Lines"], 1):
                out.append((f"{'SC' if l.get('Locked') else 'C'}_{cid}_{k}_{n}", story["Map"][l["P"]], l["Text"]))
    return out


def victim_voice(roster, named):
    """An unnamed Giltside civilian voice for 'any tarnished citizen' (CS02_05B)."""
    c = [v for v in roster if v["Side"] == "Giltside" and v["Archetype"] == "civilian" and v["VoiceId"] not in named
         and v.get("GeminiVoice")]
    return sorted(c, key=lambda v: (v["Sex"] != "M", v["VoiceId"]))[0]["VoiceId"]


def voice_for(person, pmap, victim):
    if person == "wren_hale":
        return "HERO"
    if person.startswith("the_tarnish"):
        return "TARNISH"
    if person.startswith("victim"):
        return victim
    return pmap[person]


def build():
    people = SL.people()
    pmap = {x["id"]: x["voice_id"] for x in people["people"]}
    persons = {x["id"]: x for x in people["people"]}
    roster = json.load(open(os.path.join(ROOT, "voice", "roster.json"), encoding="utf-8"))
    victim = victim_voice(roster, set(pmap.values()))
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    old_s = old.get("Scripted", {})

    lines = {k: (v[0], v[1], v[2]) for k, v in SL.scripted().items() if not k.startswith("CS")}
    cs = json.load(open(os.path.join(SCRIPT, "cutscene_lines.json"), encoding="utf-8"))
    lines.update({k: tuple(v) for k, v in cs.items() if not k.startswith("_")})

    scripted, seen = {}, {}
    for lid in sorted(lines):
        person, text, note = lines[lid]
        person = person.split(" ")[0]
        voice = voice_for(person, pmap, victim)
        fx = "tarnished" if ("tarnished" in note.lower() and voice not in ("TARNISH", "HERO")) or person.startswith("victim") else ""
        if lid.startswith("CS"):
            att = "2D"
        elif voice == "TARNISH":
            att = "3D" if lid in TARNISH_3D else "2D"
        elif voice == "HERO":
            att = "3D" if lid in HERO_3D else "2D"
        else:
            att = "3D"
        key = (voice, re.sub(r"[^a-z ]", "", text.lower()).strip())
        alias = seen.get(key)
        prev = old_s.get(lid, {})
        style = prev.get("Style", "") if prev.get("Text") == text else ""
        if lid.startswith("CS") and note and not style:
            style = note.split(":", 1)[-1].strip() if note.startswith("tarnished") else note
        scripted[lid] = {"Person": person, "Voice": voice, "Text": text, "Style": style, "Att": att, "FX": fx,
                         "AliasOf": alias}
        if not alias:
            seen[key] = lid

    barks = {}
    for pid, vid, intent, text in SL.barks():
        group = INTENT_GROUP.get(intent) or ("Cured" if intent.startswith("cured") else "TarnishedLine")
        delivery = persons[pid]["voice_design"].get("delivery", "")
        take = seen.get((pmap[pid], re.sub(r"[^a-z ]", "", text.lower()).strip()))  # same person, same words: reuse the take
        barks.setdefault(pid, {}).setdefault(group, []).append({"Text": text, "Style": "" if group != "TarnishedLine" else "slow, flat, hollow",
                                                                "Delivery": delivery, "Take": take})
    out = {"Map": pmap, "Victim": victim, "Scripted": scripted, "Barks": barks, "Replies": old.get("Replies", {}),
           "Conversations": old.get("Conversations", {})}  # drafted by story_convs.py; voiced, so always carried over
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    from collections import Counter
    print(len(scripted), "scripted", Counter(v["Voice"] if v["Voice"] in ("HERO", "TARNISH") else "roster" for v in scripted.values()),
          "aliases:", {k: v["AliasOf"] for k, v in scripted.items() if v["AliasOf"]},
          "| barks:", sum(len(i) for g in barks.values() for i in g.values()), "for", len(barks), "people | victim voice", victim)
    return out


def draft_styles(out):
    """Short delivery styles for quest lines (MQ/SQ) that lack one, from the speaker's persona and the line's context."""
    import gemini_tts as G, conv_gen as CG
    people = {x["id"]: x for x in SL.people()["people"]}
    todo = [(k, v) for k, v in out["Scripted"].items() if not v["Style"] and not v["AliasOf"]]
    if not todo:
        return
    key = G.load_key()
    notes = {k: v[2] for k, v in SL.scripted().items()}
    for i in range(0, len(todo), 40):
        chunk = todo[i:i + 40]
        rows = []
        for k, v in chunk:
            who = ("Wren Hale, the hero: warm, steady, a little wry; jokes when scared, quiet when angry" if v["Voice"] == "HERO" else
                   "the Tarnish: a close whisper, amused" if v["Voice"] == "TARNISH" else
                   f"{people[v['Person']]['name']}: {people[v['Person']]['voice_design'].get('delivery', '')}")
            rows.append(f'- "{k}" | {who} | context: {notes.get(k, "")[:120]} | "{v["Text"]}"')
        prompt = ("For each game voice line below, give a delivery direction of at most 6 words for a voice actor: emotion, "
                  "volume and pace for THIS moment (no age, accent or gender).\n" + "\n".join(rows) +
                  '\nReturn JSON: {"styles": {"<LineId>": "..."}}')
        for attempt in range(3):
            try:
                st = CG.gen_json(key, prompt, temperature=0.4).get("styles", {})
                break
            except Exception as e:
                print("err", G.scrub(e, key)[:120]); time.sleep(6); st = {}
        for k, v in chunk:
            s = str(st.get(k, "")).strip()
            if s and CG.C_ok(s):
                v["Style"] = s
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("styles:", sum(1 for v in out["Scripted"].values() if v["Style"]), "/", len(out["Scripted"]))


def draft_replies(out, n=2):
    """Persona replies for named people: what they say when the Silverer walks up and speaks to them (the Reply group
    = their story greet + these). Drafted from people.json persona; never the secret, never their never-says."""
    import gemini_tts as G, conv_gen as CG
    import uniq_check as U
    people = {x["id"]: x for x in SL.people()["people"]}
    todo = [pid for pid in out["Map"] if len(out["Replies"].get(pid, [])) < n]
    if not todo:
        return
    key = G.load_key()
    used = {U.norm(t) for _, _, t in U.collect()}
    for i in range(0, len(todo), 8):
        rows = []
        for pid in todo[i:i + 8]:
            x = people[pid]
            per = x["personality"]
            rows.append(f'- id "{pid}": {x["name"]}, {x["age"]}, {x["job"]}, {x["side"]}. Speech: {per["speech_style"]} '
                        f'Tics: {"; ".join(per.get("tics", []))}. Favourite words: {", ".join(per.get("favourite_words", []))}. '
                        f'Never says: {", ".join(per.get("never_says", []))}. Feels about the Silverer: '
                        f'{x["opinion_of_silverer"]["stance"]}. Knows: {" ".join(x.get("knows", [])[:2])} '
                        f'How they sound (their own written lines, do not repeat): "{x["barks"].get("greet", "")}" / '
                        f'"{x["barks"].get("idle", "")}" / "{x["barks"].get("farewell", "")}"')
        prompt = f"""{CG.CANON}

The Silverer here is Wren Hale. For each person below write {n} different short replies (at most 14 words each) they give
when Wren walks up and speaks to them in the street. Match the quality and rhythm of their own written lines: natural
speech a person would really say, clear when heard once, with their colour applied lightly. Do not cram in tics, facts
and names; one touch per line is plenty. At most one of the two may pass on something they know, said plainly.
Never reveal a secret, never use their never-say words, no swearing. Give each a delivery "style" of at most 6 words (emotion and pace only).
{chr(10).join(rows)}
Return JSON: {{"people": [{{"id": "...", "replies": [{{"text": "...", "style": "..."}}]}}]}}"""
        for attempt in range(3):
            try:
                res = CG.gen_json(key, prompt, temperature=0.7).get("people", [])
                break
            except Exception as e:
                print("err", G.scrub(e, key)[:120]); time.sleep(6); res = []
        for item in res:
            pid = item.get("id")
            if pid not in out["Map"]:
                continue
            nev = [w.lower() for w in people[pid]["personality"].get("never_says", [])]
            good = [{"Text": r["text"].strip(), "Style": r.get("style", "").strip()} for r in item.get("replies", [])
                    if isinstance(r, dict) and CG.clean_ok(r.get("text", ""), 14) and CG.C_ok(r.get("style", "x"))
                    and not any(w in r["text"].lower() for w in nev) and U.norm(r["text"]) not in used]
            if len(good) >= n:
                out["Replies"][pid] = good[:n]
                used.update(U.norm(g["Text"]) for g in good[:n])
        json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("persona replies:", sum(1 for p in out["Map"] if len(out["Replies"].get(p, [])) >= n), "/", len(out["Map"]))


if __name__ == "__main__":
    o = build()
    if "--styles" in sys.argv:
        draft_styles(o)
    if "--replies" in sys.argv:
        draft_replies(o)
