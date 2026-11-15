"""Draft ambient conversations, passing remarks and interaction replies with a Gemini text model, then validate.

    python conv_gen.py cliques          build cliques from the roster
    python conv_gen.py convs [Cid ...]  draft 6 conversations per clique
    python conv_gen.py lines            draft 2 remarks + 3 replies per voice
    python conv_gen.py doc              write ArtDirection/Audio/AmbientScript.md for review
Key: ~/.gemini/api_key (never printed/stored).
"""
import sys, os, json, re, random, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_tts as G
import conv_topics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(ROOT, "voice")
SCRIPT = os.path.join(V, "script")
TEXT_MODEL = "gemini-3.8-flash"
DOC = r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\Audio\AmbientScript.md"

CANON = """Setting: the city of Lanthorne exists as three reflections that share every street and stone:
- Pewterside: the dull, grey, everyday side. Rain, work, queues, trams, tired people.
- Giltside: the warm, glowing side. Lanterns, festival trade, music, bridge guards; soldiers drill in the streets.
- Frostside: the cold, cracked, bleached side. Hunger, broth lines, ruins, wary survivors.
Describe the sides only by look and mood, never by how much magic they have or who rules them.
Something called the Tarnish (always "it") is spreading through all three reflections and taking over people's faces;
the taken are "tarnished" and have burning eyes. A few people can "step through" between sides using "mirror shards"
(always say "mirror shard" or "shard"). Rumours mention the Gilt Tower and pages of a broken mirror. The player is a
"Silverer", one of the few who can walk through the glass (say "Silverer", never a personal name).
Rules: short natural spoken English, everyday street talk with personality, some humour and some dread. Teen-safe: no
swearing, no gore, no real brands or real places. Never use these words: London, Kell, Lila, Holland, Rhy, Osaron,
Antari, Travars, blood magic, traveller. Write dialogue only, no stage directions, no narration, no speaker names inside the lines.
You may use at most one inline vocal tag per conversation, only from: <laugh>, <sigh>, <short pause>."""

SPOTS = {"Pewterside": ["market stall", "tram stop", "laundry", "bridge", "tavern", "street corner"],
         "Giltside": ["festival square", "bakery", "city gate", "tower steps", "tavern", "drill yard"],
         "Frostside": ["shelter", "broth line", "ruins", "gate", "ice cut", "alley"]}
BANNED = ["london", "kell", "lila", "holland", "rhy", "osaron", "antari", "travars", "blood magic", "traveller", "traveler"]


def roster():
    snap = os.path.join(V, "roster_snapshot.json")
    return json.load(open(snap if os.path.exists(snap) else os.path.join(V, "roster.json")))


def gen_json(key, prompt, temperature=1.0):
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": temperature}}
    r = G._req(key, "POST", f"/models/{TEXT_MODEL}:generateContent", body, timeout=240)
    txt = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
    return json.loads(txt)


SOFT_BANNED = ["cripple", "crippled", "retard", "retarded", "spastic", "spaz", "gypsy", "gypsies", "midget", "lunatic",
               "savages", "freak", "imbecile", "moron", "hell", "damn", "god", "christ", "jesus", "bloody",
               "blood", "bleed", "bleeding", "bleeder", "veins", "guts", "gore"]  # Teen-safe: no slurs, oaths or gore


def clean_ok(text, max_words):
    t = text.lower()
    if any(re.search(r"\b" + re.escape(b) + r"\b", t) for b in BANNED + SOFT_BANNED):
        return False
    words = re.sub(r"<[^>]+>", "", text).split()
    return 1 <= len(words) <= max_words


def C_ok(style):
    return clean_ok(style, 6) and not re.search(r"(years? old|accent|male|female|man|woman)", style.lower())


def build_cliques(seed=7):
    rng = random.Random(seed)
    r = roster()
    cliques = []
    for side in SPOTS:
        vs = [v for v in r if v["Side"] == side]
        duty = [v for v in vs if v["Archetype"] in ("guard", "soldier")]
        civ = [v for v in vs if v["Archetype"] == "civilian"]
        rng.shuffle(civ)
        groups = []
        # duty voices: guards together, soldiers together (pairs or trios)
        for arch in ("guard", "soldier"):
            d = [v for v in duty if v["Archetype"] == arch]
            while d:
                n = 3 if len(d) in (3, 5) else 2 if len(d) >= 2 else 1
                groups.append(d[:n]); d = d[n:]
        sizes = []
        left = len(civ)
        while left > 0:
            s = rng.choice([2, 2, 3, 3, 4]) if left > 4 else left
            if left - s == 1:
                s += 1 if s < 4 else -1
            sizes.append(s); left -= s
        i = 0
        for s in sizes:
            groups.append(civ[i:i + s]); i += s
        for g in groups:
            if len(g) == 1 and groups:  # never a solo clique
                groups[0].extend(g)
        for g in [g for g in groups if len(g) >= 2]:
            cliques.append({"CliqueId": f"C{len(cliques) + 1:02d}", "Side": side, "Voices": [v["VoiceId"] for v in g]})
    os.makedirs(SCRIPT, exist_ok=True)
    json.dump(cliques, open(os.path.join(SCRIPT, "cliques.json"), "w", encoding="utf-8"), indent=1)
    from collections import Counter
    print(len(cliques), "cliques", Counter(len(c["Voices"]) for c in cliques), Counter(c["Side"] for c in cliques))
    return cliques


def recliq(seed=11):
    """Keep named story people out of generic cliques: cliques with a named voice (story.json Map) are dissolved, and
    their unnamed voices are regrouped into new cliques (new CliqueIds) whose conversations get drafted fresh."""
    story_p = os.path.join(SCRIPT, "story.json")
    named = set(json.load(open(story_p, encoding="utf-8")).get("Map", {}).values()) if os.path.exists(story_p) else set()
    rng = random.Random(seed)
    rmap = {v["VoiceId"]: v for v in roster()}
    cliques = json.load(open(os.path.join(SCRIPT, "cliques.json"), encoding="utf-8"))
    cp = os.path.join(SCRIPT, "conversations.json")
    convs = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}
    keep = [c for c in cliques if not set(c["Voices"]) & named]
    gone = [c for c in cliques if set(c["Voices"]) & named]
    next_id = max(int(c["CliqueId"][1:]) for c in cliques) + 1
    new = []
    for side in SPOTS:
        pool = [v for c in gone if c["Side"] == side for v in c["Voices"] if v not in named]
        for arch in ("guard", "soldier", "civilian"):
            vs = [v for v in pool if rmap[v]["Archetype"] == arch]
            rng.shuffle(vs)
            while len(vs) >= 2:
                n = 3 if len(vs) in (3, 5) else min(len(vs), rng.choice([2, 3, 4]) if arch == "civilian" else 2)
                if len(vs) - n == 1:
                    n += 1
                new.append({"CliqueId": f"C{next_id:02d}", "Side": side, "Voices": vs[:n]}); next_id += 1
                vs = vs[n:]
            if vs:  # a lone voice joins the last clique of its side
                # only a NEW clique takes the lone voice: joining a kept clique would force its voiced conversations to be
                # redrafted; otherwise the voice simply has no street conversations
                same = [c for c in new if c["Side"] == side]
                if same:
                    same[-1]["Voices"].append(vs[0])
                    convs.pop(same[-1]["CliqueId"], None)  # its cast changed, so redraft it
    for c in gone:
        convs.pop(c["CliqueId"], None)
    json.dump(keep + new, open(os.path.join(SCRIPT, "cliques.json"), "w", encoding="utf-8"), indent=1)
    json.dump(convs, open(cp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"kept {len(keep)} cliques, dissolved {len(gone)} with named voices, made {len(new)} new: "
          f"{[c['CliqueId'] for c in new]}; unnamed voices in cliques: {sum(len(c['Voices']) for c in keep + new)}")


def newcliq(seed=13):
    """Put unnamed voices that are in no clique yet (e.g. voices added later) into new cliques of 2-4, by side and archetype."""
    story_p = os.path.join(SCRIPT, "story.json")
    named = set(json.load(open(story_p, encoding="utf-8")).get("Map", {}).values()) if os.path.exists(story_p) else set()
    rng = random.Random(seed)
    cliques = json.load(open(os.path.join(SCRIPT, "cliques.json"), encoding="utf-8"))
    inside = {v for c in cliques for v in c["Voices"]}
    free = [v for v in roster() if v["VoiceId"] not in inside and v["VoiceId"] not in named]
    nid = max(int(c["CliqueId"][1:]) for c in cliques) + 1
    made = []
    for side in SPOTS:
        for arch in ("guard", "soldier", "civilian"):
            vs = [v["VoiceId"] for v in free if v["Side"] == side and v["Archetype"] == arch]
            rng.shuffle(vs)
            while len(vs) >= 2:
                n = 3 if len(vs) >= 5 or len(vs) == 3 else 2
                made.append({"CliqueId": f"C{nid:02d}", "Side": side, "Voices": vs[:n]}); nid += 1
                vs = vs[n:]
            if vs and made:
                made[-1]["Voices"].append(vs[0])
    json.dump(cliques + made, open(os.path.join(SCRIPT, "cliques.json"), "w", encoding="utf-8"), indent=1)
    print("new cliques:", [(c["CliqueId"], c["Voices"]) for c in made])


def topics_for(c, all_cliques, n=6):
    side = [x["CliqueId"] for x in all_cliques if x["Side"] == c["Side"]]
    k = side.index(c["CliqueId"])
    pool = conv_topics.TOPICS[c["Side"]]
    return [pool[(k * n + j * 7) % len(pool)] for j in range(n)]


def draft_clique(key, c, rmap, n=6, topics=None):
    cast = "\n".join(f"S{i + 1}: {rmap[v]['Role']}, {'woman' if rmap[v]['Sex'] == 'F' else 'man'}, "
                     f"{rmap[v]['AgeBand']}, {rmap[v]['Attitude']}" for i, v in enumerate(c["Voices"]))
    spots = ", ".join(SPOTS[c["Side"]])
    prompt = f"""{CANON}

Write {n} different short conversations overheard on the street in {c['Side']}, between these people who know each other:
{cast}
Each conversation: 2 to 6 lines, at least 2 different speakers, every line at most 16 words. Use natural spoken contractions
(don't, I'm, it's, can't, let's). One conversation per topic, in this order:
{chr(10).join(f"{i + 1}. {t}" for i, t in enumerate(topics or []))}
Only mention the Tarnish, burning eyes, stepping through or mirror shards when the topic is about them; keep the rest about
ordinary life in {c['Side']}. Give each a different spot from: {spots}. Make the speakers sound different from each other.
Delivery: give EVERY line a "style": a short direction of at most 6 words for emotion and pace (e.g. "dry, unimpressed",
"hushed, quick", "warm, teasing", "worried, slowing down"). Inside the text you may CAPITALISE one word for emphasis and use
"..." or a dash for hesitation. Keep permanent traits (age, accent, gender) OUT of style.
Return JSON: {{"conversations": [{{"spot": "...", "lines": [{{"s": 1, "text": "...", "style": "..."}}]}}]}} where s is the speaker number."""
    for attempt in range(3):
        try:
            out = gen_json(key, prompt)
        except Exception as e:
            print(c["CliqueId"], "err", G.scrub(e, key)[:150]); time.sleep(5); continue
        good = []
        for conv in out.get("conversations", []):
            lines = conv.get("lines", [])
            spk = {l.get("s") for l in lines}
            if 2 <= len(lines) <= 6 and len(spk) >= 2 and all(isinstance(l.get("s"), int) and 1 <= l["s"] <= len(c["Voices"])
                                                               and clean_ok(l.get("text", ""), 16) for l in lines):
                if len(re.findall(r"<[^>]+>", " ".join(l["text"] for l in lines))) <= 1:
                    if all(1 <= len(str(l.get("style", "")).split()) <= 6 and C_ok(l.get("style", "")) for l in lines):
                        good.append({"Spot": conv.get("spot", ""),
                                     "Lines": [{"S": l["s"], "Text": l["text"].strip(), "Style": l["style"].strip()} for l in lines]})
        if len(good) >= n - 1:
            return good[:n]
    return good


def draft_convs(ids=None):
    key = G.load_key()
    rmap = {v["VoiceId"]: v for v in roster()}
    cliques = json.load(open(os.path.join(SCRIPT, "cliques.json"), encoding="utf-8"))
    p = os.path.join(SCRIPT, "conversations.json")
    out = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    todo = [c for c in cliques if (not ids or c["CliqueId"] in ids) and c["CliqueId"] not in out]
    with ThreadPoolExecutor(4) as ex:
        for c, convs in zip(todo, ex.map(lambda c: draft_clique(key, c, rmap, topics=topics_for(c, cliques)), todo)):
            out[c["CliqueId"]] = {"Side": c["Side"], "Voices": c["Voices"], "Topics": topics_for(c, cliques), "Conversations": convs}
            print(c["CliqueId"], c["Side"], len(c["Voices"]), "voices ->", len(convs), "conversations")
            json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print("total conversations:", sum(len(v["Conversations"]) for v in out.values()))


def draft_lines():
    key = G.load_key()
    r = roster()
    p = os.path.join(SCRIPT, "voice_lines.json")
    out = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    todo = [v for v in r if v["VoiceId"] not in out]
    batches = [todo[i:i + 10] for i in range(0, len(todo), 10)]

    def one(batch):
        cast = "\n".join(f"{v['VoiceId']}: {v['Role']}, {'woman' if v['Sex'] == 'F' else 'man'}, {v['AgeBand']}, "
                         f"{v['Attitude']}, lives in {v['Side']}" for v in batch)
        prompt = f"""{CANON}

For each person below write:
- "remarks": 2 different things they mutter to themselves while walking alone (at most 12 words each);
- "replies": 3 different short answers they give when the Silverer walks up and speaks to them (at most 14 words each),
  in character and in the mood of their side.
People:
{cast}
Give each line a short delivery "style" (at most 6 words, emotion and pace only; no age, accent or gender).
Inside a line you may CAPITALISE one word for emphasis and use "..." for hesitation.
Return JSON: {{"voices": [{{"id": "V001", "remarks": [{{"text": "...", "style": "..."}}, {{"text": "...", "style": "..."}}],
"replies": [{{"text": "...", "style": "..."}}, {{"text": "...", "style": "..."}}, {{"text": "...", "style": "..."}}]}}]}}"""
        for attempt in range(3):
            try:
                o = gen_json(key, prompt)
            except Exception as e:
                print("err", G.scrub(e, key)[:150]); time.sleep(5); continue
            res = {}
            for item in o.get("voices", []):
                rem = [{"Text": t["text"].strip(), "Style": t.get("style", "").strip()} for t in item.get("remarks", [])
                       if isinstance(t, dict) and clean_ok(t.get("text", ""), 12) and C_ok(t.get("style", "x"))][:2]
                rep = [{"Text": t["text"].strip(), "Style": t.get("style", "").strip()} for t in item.get("replies", [])
                       if isinstance(t, dict) and clean_ok(t.get("text", ""), 14) and C_ok(t.get("style", "x"))][:3]
                if len(rem) == 2 and len(rep) == 3:
                    res[item.get("id")] = {"Remarks": rem, "Replies": rep}
            if all(v["VoiceId"] in res for v in batch):
                return res
        return res

    with ThreadPoolExecutor(4) as ex:
        for res in ex.map(one, batches):
            out.update(res)
            json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print("voices with lines:", len(out), "/", len(r))


def write_doc():
    rmap = {v["VoiceId"]: v for v in roster()}
    convs = json.load(open(os.path.join(SCRIPT, "conversations.json"), encoding="utf-8"))
    vl = json.load(open(os.path.join(SCRIPT, "voice_lines.json"), encoding="utf-8")) if os.path.exists(os.path.join(SCRIPT, "voice_lines.json")) else {}
    L = ["# Reflections: ambient street script (draft)", "",
         f"Drafted with Gemini `{TEXT_MODEL}` from the canon brief in `ArtDirection/Audio/tools/conv_gen.py`, machine-checked "
         "(never-say words, length, speakers). Voices are designed with Gemini Voice design; see the voice roster.", ""]
    n = 0
    for cid, c in convs.items():
        names = ", ".join(f"S{i + 1}={v} ({rmap[v]['Role']})" for i, v in enumerate(c["Voices"]))
        L += [f"## {cid}: {c['Side']} ({names})", ""]
        for k, conv in enumerate(c["Conversations"], 1):
            n += 1
            L.append(f"**{cid}-{k}** ({conv['Spot']})  ")
            L += [f"S{l['S']}: {l['Text']} *({l.get('Style', '')})*  " for l in conv["Lines"]]
            L.append("")
    L += ["## Remarks and replies per voice", ""]
    for vid, d in vl.items():
        L.append(f"- **{vid}** ({rmap[vid]['Role']}, {rmap[vid]['Side']}): remarks: " + " / ".join(f"{x['Text']} ({x['Style']})" for x in d["Remarks"])
                 + "; replies: " + " / ".join(f"{x['Text']} ({x['Style']})" for x in d["Replies"]))
    bp = os.path.join(SCRIPT, "barks.json")
    if os.path.exists(bp):
        barks = json.load(open(bp, encoding="utf-8"))
        L += ["", "## Barks, possessed mutters and fillers per voice", "",
              "Every voice has its own wording of each intent (`bark_gen.py`); the canon citizen barks are intents only.", ""]
        for vid in sorted(barks):
            L.append(f"- **{vid}** ({rmap[vid]['Role']}, {rmap[vid]['Side']}): " + "; ".join(
                f"{g}: " + " / ".join(x["Text"] for x in items) for g, items in barks[vid].items()))
    try:
        import uniq_check as U
        lines = U.collect()
        ex, es, near = U.check(lines)
        L[4:4] = [f"**Uniqueness check** (`uniq_check.py`): {len(lines)} lines from {len({l[1] for l in lines})} speakers; "
                  f"{len(ex)} shared across speakers, {len(es)} repeated by one speaker, {len(near)} near-duplicates flagged.", ""]
    except Exception as e:
        print("uniq summary skipped:", e)
    open(DOC, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(DOC, n, "conversations")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "cliques":
        build_cliques()
    elif cmd == "recliq":
        recliq()
    elif cmd == "newcliq":
        newcliq()
    elif cmd == "convs":
        draft_convs(set(sys.argv[2:]) or None)
    elif cmd == "lines":
        draft_lines()
    elif cmd == "doc":
        write_doc()
