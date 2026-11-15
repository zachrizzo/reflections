"""Rewrite every line that collides with another speaker's (exact or near duplicate) until uniq_check passes.

    python uniq_fix.py [--rounds 4] [--dry]
Keeps the first occurrence; never rewrites the shipped single-character OpenAI lines (Tarnish, narrator); rewrites the
others in place in conversations.json / voice_lines.json / barks.json with Gemini text, keeping meaning, speaker and
length, and refusing any rewrite that collides again. Run only when no drafting job is writing those files.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_tts as G
import conv_gen as CG
import uniq_check as U
import bark_gen as BG

FILES = {"A": "conversations.json", "R": "voice_lines.json", "B": "barks.json", "P": "story.json"}


def load():
    return {k: (json.load(open(os.path.join(CG.SCRIPT, f), encoding="utf-8"))
                if os.path.exists(os.path.join(CG.SCRIPT, f)) else {}) for k, f in FILES.items()}


def save(d, kinds=None):
    for k, f in FILES.items():
        if d[k] and (kinds is None or k in kinds):
            json.dump(d[k], open(os.path.join(CG.SCRIPT, f), "w", encoding="utf-8"), indent=1, ensure_ascii=False)


REWRITABLE = ("A_", "R_", "B_", "P_", "C_")  # S_ / SB_ / SC_ (story-written) and OpenAI lines are never rewritten


def locate(d, lid):
    """-> (line dict, context text, max words)"""
    kind, rest = lid.split("_", 1)
    if kind == "C":
        rest2, k, n = rest.rsplit("_", 2)
        conv = d["P"]["Conversations"][rest2][int(k) - 1]
        ctx = "Overheard conversation between named townspeople:\n" + "\n".join(
            f"{'>>' if i == int(n) - 1 else '  '} {l['P']}: {l['Text']}" for i, l in enumerate(conv["Lines"]))
        return conv["Lines"][int(n) - 1], ctx + "\n(rewrite the >> line only; keep the speaker's voice and the flow)", 14
    if kind == "P":
        pid, i = rest.rsplit("_", 1)
        return d["P"]["Replies"][pid][int(i) - 1], "a short in-character answer when the Silverer speaks to them", 14
    if kind == "A":
        cid, k, n = rest.rsplit("_", 2)
        c = d["A"][cid]
        conv = c["Conversations"][int(k) - 1]
        ctx = "Overheard conversation in {} at the {}:\n{}".format(c["Side"], conv.get("Spot", ""), "\n".join(
            f"{'>>' if i == int(n) - 1 else '  '} S{l['S']}: {l['Text']}" for i, l in enumerate(conv["Lines"])))
        return conv["Lines"][int(n) - 1], ctx + "\n(rewrite the >> line only; keep it a reply that fits the flow)", 16
    if kind == "R":
        vid, typ, i = rest.rsplit("_", 2)
        what = ("something they mutter to themselves walking alone" if typ == "Remark"
                else "a short answer when the Silverer walks up and speaks to them")
        return d["R"][vid]["Remarks" if typ == "Remark" else "Replies"][int(i) - 1], f"{what}", 12 if typ == "Remark" else 14
    group_vid, i = rest.rsplit("_", 1)
    group, vid = group_vid.rsplit("_", 1)
    return d["B"][vid][group][int(i) - 1], f'"{group}" line: {BG.GROUPS[group][3]}', BG.GROUPS[group][2]


def voiced():
    """Line ids that already have a take: never reword them (the audio would stop matching the script)."""
    mp = os.path.join(os.path.dirname(CG.SCRIPT), "gemini", "manifest.json")
    return {k for k, v in (json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}).items() if "match" in v}


def in_scope(lid, _s=[]):
    """voice/script/edit_scope.json {"voices": [...]} limits edits to lines spoken by those voices (when present)."""
    if not _s:
        p = os.path.join(CG.SCRIPT, "edit_scope.json")
        _s.append(set(json.load(open(p))["voices"]) if os.path.exists(p) else None)
    scope = _s[0]
    if scope is None:
        return True
    if lid.startswith(("B_", "R_")):
        return any(f"_{v}_" in lid + "_" for v in scope)
    if lid.startswith("A_"):
        cid = lid.split("_")[1]
        cl = {c["CliqueId"]: c["Voices"] for c in json.load(open(os.path.join(CG.SCRIPT, "cliques.json")))}
        return bool(set(cl.get(cid, [])) & scope)
    return False


def rewritable(lid, _v=[]):
    if not _v:
        _v.append(voiced())
    return lid[:2] in REWRITABLE and lid not in _v[0] and in_scope(lid)


def offenders(lines):
    ex_cross, ex_self, near = U.check(lines)
    bad = []
    for g in ex_cross + ex_self:
        keep = next((x for x in g if not rewritable(x[0])), g[0])
        bad += [x for x in g if x is not keep and rewritable(x[0])]
    for _r, a, b in near:
        victim = b if rewritable(b[0]) else a
        if rewritable(victim[0]) and victim not in bad:
            bad.append(victim)
    return bad, (len(ex_cross), len(ex_self), len(near))


def rewrite(key, d, rmap, items, used):
    blocks = []
    for lid, vid, text in items:
        line, ctx, maxw = locate(d, lid)
        v = rmap.get(vid)
        who = BG.person(v) if v else vid
        blocks.append(f'- id "{lid}" | speaker {who} | {ctx} | current: "{text}" | at most {maxw} words')
    prompt = f"""{CG.CANON}

Each line below is spoken by one character but is identical or nearly identical to another character's line. Rewrite each
one so it keeps its meaning, mood and job in the scene but is worded clearly differently, in that speaker's own manner.
Do not just reorder words or add a filler word. Keep spoken contractions. Also give a delivery "style" (at most 6 words,
emotion and pace only).
{chr(10).join(blocks)}
Already used lines (do not reuse or closely copy): {json.dumps(sorted(used)[:60])}
Return JSON: {{"rewrites": [{{"id": "...", "text": "...", "style": "..."}}]}}"""
    for attempt in range(3):
        try:
            return {x["id"]: x for x in CG.gen_json(key, prompt, temperature=1.0).get("rewrites", []) if isinstance(x, dict)}
        except Exception as e:
            print("err", G.scrub(e, key)[:150], flush=True); time.sleep(8)
    return {}


def main(argv):
    rounds = int(argv[argv.index("--rounds") + 1]) if "--rounds" in argv else 4
    key = G.load_key()
    rmap = {v["VoiceId"]: v for v in CG.roster()}
    d = load()
    for rnd in range(1, rounds + 1):
        lines = U.collect()
        bad, counts = offenders(lines)
        print(f"round {rnd}: exact cross {counts[0]}, exact self {counts[1]}, near {counts[2]} -> rewriting {len(bad)}",
              flush=True)
        if not bad or "--dry" in argv:
            for x in bad[:30]:
                print("  ", x[0], x[1], x[2])
            break
        used = {U.norm(t) for _, _, t in lines}
        fixed = 0
        for i in range(0, len(bad), 12):
            chunk = bad[i:i + 12]
            res = rewrite(key, d, rmap, chunk, used)
            for lid, vid, text in chunk:
                r = res.get(lid)
                if not r:
                    continue
                line, _ctx, maxw = locate(d, lid)
                new = r.get("text", "").strip()
                nn = U.norm(new)
                if not CG.clean_ok(new, maxw) or nn in used or not nn:
                    continue
                line["Text"] = new
                if CG.C_ok(r.get("style", "x")):
                    line["Style"] = r["style"].strip()
                used.discard(U.norm(text))
                used.add(nn)
                fixed += 1
        save(d)
        print(f"  rewrote {fixed}", flush=True)
    return U.main(["--quiet"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
