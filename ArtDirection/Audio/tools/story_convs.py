"""Expand the story session's clique seeds (ArtDirection/Story/conversations.md, read only) into full conversations.

    python story_convs.py parse      print the parsed conversation specs
    python story_convs.py draft      draft every spec into story.json "Conversations" (resumes per clique)
Each spec: A/B/C everyday; D per infection band (quiet, spreading, rising, brink); E per story flag. Opening lines and the
brink pair are kept word for word (protected); the continuation is drafted in persona (rewritable by uniq_fix).
"""
import sys, os, re, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_lines as SL
import story_import as ST

DOC = os.path.join(SL.STORY, "conversations.md")
BANDS = ["quiet", "spreading", "rising", "brink"]


def name_index(people):
    idx = {}
    for x in people:
        name = x["name"]
        for nick in re.findall(r'"([^"]+)"', name):  # 'Marigold "Goldie" Fairweather', 'Agathe Rook, "Mother Rook"'
            idx[nick.lower()] = x["id"]
        clean = re.sub(r'"[^"]+"|,', " ", name).replace("Sergeant ", "").replace("Captain ", "")
        idx[clean.lower().strip()] = x["id"]
        for p in clean.split():
            idx.setdefault(p.lower(), x["id"])
    return idx


def parse():
    P = SL.people()
    people = P["people"]
    idx = name_index(people)
    cliques = {c["id"]: c for c in P["cliques"]}
    text = open(DOC, encoding="utf-8").read().split("## The rest of the crowd")[0]
    specs = {}
    for sec in re.split(r"\n### ", text)[1:]:
        m = re.match(r".*?\(`([a-z_]+)`\)", sec)
        if not m or m.group(1) not in cliques:
            continue
        cid = m.group(1)
        out = []
        for seed in re.split(r"\n- \*\*", sec)[1:]:
            sm = re.match(r"([A-E])\. (.+?)\*\*", seed)
            if not sm:
                continue
            letter, title = sm.groups()
            stances = " ".join(re.findall(r"Stances: (.+)", seed))
            body = seed
            # openings: "Opening:" / "Opening (rising):" / "Opening (after MQ02):" / "Brink pair:" followed by "- Name: "text""
            blocks = re.split(r"\n\s+- (Opening(?: \(([^)]+)\))?|Brink pair):\s*\n", body)
            openings, k = {}, 1
            while k < len(blocks):
                label, cond, lines_txt = blocks[k], blocks[k + 1], blocks[k + 3] if k + 3 < len(blocks) else ""
                lines_txt = blocks[k + 2]
                ls = []
                for lm in re.finditer(r'^\s+- ([A-Z][\w .\'-]+?): "(.+)"\s*$', lines_txt, re.M):
                    pid = idx.get(lm.group(1).lower()) or idx.get(lm.group(1).split()[-1].lower())
                    ls.append((pid, lm.group(2)))
                key = "brink" if label == "Brink pair" else (cond or "")
                openings[key] = ls
                k += 3
            if letter in "ABC":
                cond_m = re.search(r"\n\s+- (Before|After) ([^:]+):", seed)
                out.append({"Seed": letter, "Title": title, "Band": "", "Flag": "", "Cond": cond_m.group(0).strip("- \n") if cond_m else "",
                            "Stances": stances, "Opening": openings.get("", []), "Exact": False})
            elif letter == "D":
                for b in BANDS:
                    desc = " ".join(re.findall(r"\n\s+- " + b + r": (.+)", seed))
                    op = openings.get("brink", []) if b == "brink" else openings.get(b, [])
                    out.append({"Seed": "D", "Title": title, "Band": b, "Flag": "", "Cond": desc, "Stances": stances,
                                "Opening": op, "Exact": b == "brink" and bool(op)})
            else:
                flags = re.findall(r"\n\s+- (?:After|Once) (`?[\w]+`?)[,:]? (.+)", seed)
                if not flags:
                    flags = re.findall(r"Flags: (?:after|After) (`?[\w]+`?)[,:]? ([^.]+\.)", seed)
                for fl, desc in flags:
                    fl = fl.strip("`")
                    op = next((v for kk, v in openings.items() if fl in kk), [])
                    out.append({"Seed": "E", "Title": title, "Band": "", "Flag": fl, "Cond": desc.strip(), "Stances": stances,
                                "Opening": op, "Exact": False})
        specs[cid] = out
    return specs


def draft():
    import gemini_tts as G, conv_gen as CG, uniq_check as U
    P = SL.people()
    people = {x["id"]: x for x in P["people"]}
    cliques = {c["id"]: c for c in P["cliques"]}
    story = ST.load()
    convs = story.setdefault("Conversations", {})
    key = G.load_key()
    used = {U.norm(t) for _, _, t in U.collect()}
    for cid, specs in parse().items():
        if cid in convs and len(convs[cid]) == len(specs):
            continue
        members = cliques[cid]["members"]
        guests = sorted({pid for s in specs for pid, _ in s["Opening"] if pid and pid not in members})
        cast = "\n".join(f"- {pid}: {people[pid]['name']}, {people[pid]['job']}. Speech: {people[pid]['personality']['speech_style']} "
                         f"Tics: {'; '.join(people[pid]['personality'].get('tics', []))}. Never says: "
                         f"{', '.join(people[pid]['personality'].get('never_says', []))}." for pid in members + guests)
        rows = []
        for i, s in enumerate(specs, 1):
            cond = (f"infection band {s['Band']}: {s['Cond']}" if s["Band"] else f"after story flag {s['Flag']}: {s['Cond']}"
                    if s["Flag"] else s["Cond"])
            op = " / ".join(f'{pid}: "{t}"' for pid, t in s["Opening"]) or "(none: write it from scratch)"
            how = "EXACTLY these two lines, nothing more" if s["Exact"] else "keep the opening word for word, then continue to 4-6 lines in all"
            rows.append(f"{i}. Seed {s['Seed']} \"{s['Title']}\" {('[' + cond + ']') if cond else ''}. Stances: {s['Stances']} "
                        f"Opening: {op}. Length: {how}.")
        prompt = f"""{CG.CANON}

You are expanding written conversation seeds for a clique of named townspeople in {cliques[cid]['side']} ({cliques[cid]['name']}).
Cast (speaker ids):
{cast}
Write one conversation per seed below. Rules: every speaker stays in their speech style (tics used lightly), never uses
their never-say words; each line under about 3 seconds (at most 14 words); natural spoken English, clear when overheard;
no narration; secrets are only ever circled, never said. Keep any opening lines EXACTLY as written, same speakers, first.
Give every line a delivery "style" (at most 6 words, emotion and pace only).
Seeds:
{chr(10).join(rows)}
Return JSON: {{"conversations": [{{"n": 1, "lines": [{{"s": "speaker_id", "text": "...", "style": "..."}}]}}]}}"""
        got = None
        for attempt in range(3):
            try:
                got = {c["n"]: c["lines"] for c in CG.gen_json(key, prompt, temperature=0.8).get("conversations", [])}
                break
            except Exception as e:
                print(cid, "err", G.scrub(e, key)[:120]); time.sleep(6)
        if not got:
            continue
        out = []
        for i, s in enumerate(specs, 1):
            ls = [l for l in got.get(i, []) if isinstance(l, dict) and l.get("s") in people and CG.clean_ok(l.get("text", ""), 14)]
            k = len(s["Opening"])
            fixed = [{"P": pid, "Text": t, "Style": (ls[j].get("style", "") if j < len(ls) else ""), "Locked": True}
                     for j, (pid, t) in enumerate(s["Opening"]) if pid]
            rest = [] if s["Exact"] else [{"P": l["s"], "Text": l["text"].strip(), "Style": l.get("style", "").strip(), "Locked": False}
                                          for l in ls[k:] if U.norm(l["text"]) not in used][:6 - len(fixed)]
            lines = fixed + rest
            if len(lines) >= 2 and len({l["P"] for l in lines}) >= 2:
                used.update(U.norm(l["Text"]) for l in rest)
                out.append({**{k2: s[k2] for k2 in ("Seed", "Title", "Band", "Flag")}, "Lines": lines})
        convs[cid] = out
        json.dump(story, open(ST.OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(cid, len(out), "/", len(specs), "conversations", flush=True)
    print("story conversations:", sum(len(v) for v in convs.values()))


if __name__ == "__main__":
    if sys.argv[1] == "parse":
        for cid, specs in parse().items():
            print(cid, len(specs), [(s["Seed"] + (":" + s["Band"] if s["Band"] else "") + (":" + s["Flag"] if s["Flag"] else ""),
                                     len(s["Opening"]), None in [p for p, _ in s["Opening"]]) for s in specs])
    elif sys.argv[1] == "draft":
        draft()
