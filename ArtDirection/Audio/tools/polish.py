"""Editor pass over the drafted script: flag and rewrite lines that are awkward to say, unclear, demeaning, off-canon or
too long, then hand over to uniq_fix.py for the uniqueness pass.

    python polish.py [B|R|A ...]     review barks (B), remarks/replies (R), conversations (A); default all
Writes voice/script/polish_log.json (id, reason, before, after). Key: ~/.gemini/api_key via gemini_tts only.
"""
import sys, os, json, re, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_tts as G
import conv_gen as CG
import uniq_check as U
import bark_gen as BG
import uniq_fix as F

LOG = os.path.join(CG.SCRIPT, "polish_log.json")
# words a Teen-rated game shouldn't put in any NPC's mouth (demeaning terms), checked on every line
SOFT_BANNED = CG.SOFT_BANNED


def flagged_words(text):
    t = U.norm(text)
    return [w for w in SOFT_BANNED if re.search(r"\b" + w + r"\b", t)]


EDITOR = """You are the dialogue editor for a Teen-rated fantasy game. Review the lines below. FLAG a line only if it is:
1. awkward or unnatural to say aloud (tongue-twisting, garbled grammar, a phrase no person would shout or say);
2. unclear on its own when heard once in passing;
3. demeaning or rude about a group (disability, ethnicity, class), or uses swearing or religious oaths;
4. against the setting rules (never-say words, a personal name for the player, how much magic a side has);
5. too long for its job (barks are shouted in under 2 seconds);
6. wrong for the moment in a reaction line (hurt, thrown down, on fire, shocked, dying, calling the guards): jokes,
   politeness, compliments to the attacker, whimsy, scoring, or odd specifics. People in pain or panic use short, raw,
   everyday words; character shows only in a small touch (a name they call out, how they address people).
Saying "the Tarnish" by name is fine and wanted; the only rule is that it is called "it", never "he" or "she".
Do not flag a line for being plain, regional or blunt; character is good. For each flagged line, rewrite it in the same
speaker's voice with the same intent and job, at most the given word count, worded naturally. Keep contractions."""


def review(key, items, ctx):
    """items: [(lid, speaker summary, text, max words)] -> {lid: {text, style, reason}}"""
    rows = "\n".join(f'- id "{lid}" | {who} | max {mw} words | "{text}"' for lid, who, text, mw in items)
    prompt = f"""{CG.CANON}

{EDITOR}
{ctx}
Lines:
{rows}
Return JSON: {{"fixes": [{{"id": "...", "reason": "...", "text": "...", "style": "..."}}]}} (empty list if all are fine)."""
    for attempt in range(3):
        try:
            return {x["id"]: x for x in CG.gen_json(key, prompt, temperature=0.4).get("fixes", []) if isinstance(x, dict) and "id" in x}
        except Exception as e:
            print("err", G.scrub(e, key)[:150], flush=True); time.sleep(8)
    return {}


def jobs(d, rmap, kinds):
    out = []
    if "B" in kinds:
        for group, spec in BG.GROUPS.items():
            if group in BG.WORDLESS:
                continue  # grunts and gasps: nothing to edit
            items = [(f"B_{group}_{vid}_{i + 1}", BG.person(rmap[vid]), x["Text"], spec[2])
                     for vid, gs in d["B"].items() for i, x in enumerate(gs.get(group, []))]
            for i in range(0, len(items), 45):
                out.append((items[i:i + 45], f'These are "{group}" lines: {spec[3]}.'))
    if "R" in kinds:
        items = []
        for vid, x in d["R"].items():
            items += [(f"R_{vid}_Remark_{i + 1}", BG.person(rmap[vid]) + " (muttered alone)", t["Text"], 12) for i, t in enumerate(x["Remarks"])]
            items += [(f"R_{vid}_Reply_{i + 1}", BG.person(rmap[vid]) + " (answering the Silverer)", t["Text"], 14) for i, t in enumerate(x["Replies"])]
        for i in range(0, len(items), 50):
            out.append((items[i:i + 50], "Remarks are muttered to oneself while walking; replies answer the Silverer in passing."))
    if "P" in kinds and d.get("P"):
        import story_lines as SL
        people = {x["id"]: x for x in SL.people()["people"]}
        items = []
        for pid, reps in d["P"].get("Replies", {}).items():
            x = people[pid]
            who = (f"{x['name']} ({x['job']}, {x['side']}); speech: {x['personality']['speech_style']} "
                   f"never says: {', '.join(x['personality'].get('never_says', []))}")
            items += [(f"P_{pid}_{i + 1}", who, r["Text"], 14) for i, r in enumerate(reps)]
        for i in range(0, len(items), 30):
            out.append((items[i:i + 30], "These are a named character's replies when the Silverer (Wren) speaks to them "
                                         "in the street. They must stay in that character's speech style."))
    if "A" in kinds:
        for cid, c in d["A"].items():
            cast = "; ".join(f"S{i + 1} = {BG.person(rmap[v])}" for i, v in enumerate(c["Voices"]))
            items, convs = [], []
            for k, conv in enumerate(c["Conversations"], 1):
                convs.append(f"Conversation {k} ({conv.get('Spot', '')}): " + " / ".join(f"S{l['S']}: {l['Text']}" for l in conv["Lines"]))
                items += [(f"A_{cid}_{k}_{n}", f"S{l['S']}", l["Text"], 16) for n, l in enumerate(conv["Lines"], 1)]
            out.append((items, f"Overheard street conversations in {c['Side']}. Cast: {cast}.\n" + "\n".join(convs)
                        + "\nA rewrite must still fit its conversation."))
    return out


def main(argv):
    kinds = set(argv) or {"B", "R", "A"}
    key = G.load_key()
    rmap = {v["VoiceId"]: v for v in CG.roster()}
    d = F.load()
    log = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else []
    js = jobs(d, rmap, kinds)
    done = F.voiced()  # lines with a take already are never edited
    js = [([it for it in items if it[0] not in done and F.in_scope(it[0])], ctx) for items, ctx in js]
    js = [(items, ctx) for items, ctx in js if items]
    print("review calls:", len(js), flush=True)
    # hard filter first: any demeaning or oath word is always sent for rewrite
    forced = {lid for items, _ in js for lid, _w, text, _m in items if flagged_words(text)}
    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(lambda j: review(key, *j), js))
    fixes = {}
    for res in results:
        fixes.update(res)
    missing = [(lid, who, text, mw, ctx) for items, ctx in js for lid, who, text, mw in items if lid in forced and lid not in fixes]
    for lid, who, text, mw, ctx in missing:
        r = review(key, [(lid, who, text, mw)], ctx + " This line MUST be rewritten: it uses a demeaning word or an oath.")
        fixes.update(r)
    used = {U.norm(t) for _, _, t in U.collect()}
    applied = 0
    for lid, fx in fixes.items():
        try:
            line, _ctx, maxw = F.locate(d, lid)
        except Exception:
            continue
        new = str(fx.get("text", "")).strip()
        nn = U.norm(new)
        if not new or nn == U.norm(line["Text"]) or not CG.clean_ok(new, maxw) or flagged_words(new) or nn in used:
            continue
        if lid.startswith("B_React_") and U.is_wordless(new):
            continue  # worded reaction groups must keep at least one real word
        log.append({"id": lid, "reason": fx.get("reason", ""), "before": line["Text"], "after": new})
        used.discard(U.norm(line["Text"])); used.add(nn)
        line["Text"] = new
        if CG.C_ok(str(fx.get("style", "x"))):
            line["Style"] = fx["style"].strip()
        applied += 1
    F.save(d, kinds)
    json.dump(log, open(LOG, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    left = [lid for items, _ in js for lid, _w, _t, _m in items if flagged_words(F.locate(d, lid)[0]["Text"])]
    print(f"flagged {len(fixes)}, applied {applied}; demeaning/oath words still present: {left}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
