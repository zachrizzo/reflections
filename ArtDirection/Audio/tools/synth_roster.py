"""Synthesize roster lines (remarks, replies, conversation lines) with Gemini designed voices; STT-check; process.

    python synth_roster.py plan                 count lines and which voices still need designing
    python synth_roster.py synth [VoiceId ...]  synthesize missing lines whose voices exist (all if none given)
    python synth_roster.py process              trim / tighten / level all raw lines into final WAVs
Line ids: R_<VoiceId>_Remark_<n>, R_<VoiceId>_Reply_<n>, A_<CliqueId>_<k>_<n>.
"""
import sys, os, json, re, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _heavy():
    """Synthesis and processing modules, imported only when needed (the editor imports this file for lines() alone)."""
    global np, G, T, B, A, Lv, PV, S
    import numpy as np
    import gemini_tts as G, tts as T, gemini_batch as B, audiolib as A, level as Lv, process_voice as PV, synth as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "voice", "script")
RAW = os.path.join(ROOT, "voice", "gemini", "raw")
FINAL = os.path.join(ROOT, "voice", "gemini", "final")
MAN = os.environ.get("SYNTH_MANIFEST") or os.path.join(ROOT, "voice", "gemini", "manifest.json")  # override to run a side batch
TARGET = {"Remark": -19, "Reply": -17, "Amb": -19, "Bark": -16, "Tarnished": -19}
MAX_GAP = 0.45


BARK_KIND = {"Civilian_Fear": "Bark", "Guard_Alert": "Bark", "Guard_Attack": "Bark", "Soldier_Command": "Bark",
             "Tarnished_Mutter": "Tarnished", "Filler": "Reply",
             "React_Hurt": "Bark", "React_Knocked": "Bark", "React_Burning": "Bark", "React_Shocked": "Bark",
             "React_Death": "Bark", "React_Effort": "Bark", "Heat_CallGuards": "Bark", "Heat_Halt": "Bark",
             "Heat_Alarm": "Bark", "Soldier_Battle": "Bark"}


STORY_BARK_KIND = {"Flee": "Bark", "SeeTarnished": "Bark", "Greet": "Reply", "Farewell": "Reply", "Thanks": "Reply",
                   "SpellNear": "Reply", "Cured": "Reply", "Idle": "Remark", "Dread": "Remark", "TarnishedLine": "Tarnished"}
HERO_FILE = os.path.join(ROOT, "voice", "hero_choice.json")  # {"Candidate": "A", "GeminiVoice": "voice_..."} once the user picks


def hero_voice():
    return json.load(open(HERO_FILE)).get("GeminiVoice") if os.path.exists(HERO_FILE) else None


def lines():
    """All Gemini lines: (line_id, voice_id, text, kind, style). voice_id "HERO" = Wren (hero_choice.json).
    Generic: B_<Group>_<VoiceId>_<n>, R_<VoiceId>_<Remark|Reply>_<n>, A_<CliqueId>_<k>_<n>.
    Story: S_<LineId> (scripted), SB_<Group>_<person>_<n> (barks), P_<person>_<n> (persona replies),
    SC_/C_<clique>_<k>_<n> (story conversations). Generic lines a named person's story lines replace are left out;
    the Tarnish's story lines go through the OpenAI Tarnish voice instead (voice_script.py)."""
    import story_import as ST
    story = ST.load()
    sup = ST.suppressed(story)
    out = []
    bp = os.path.join(SCRIPT, "barks.json")
    for vid, groups in (json.load(open(bp, encoding="utf-8")) if os.path.exists(bp) else {}).items():
        for group, items in groups.items():
            if (group, vid) not in sup:
                out += [(f"B_{group}_{vid}_{i + 1}", vid, t["Text"], BARK_KIND[group], t.get("Style", "")) for i, t in enumerate(items)]
    vp = os.path.join(SCRIPT, "voice_lines.json")
    for vid, d in (json.load(open(vp, encoding="utf-8")) if os.path.exists(vp) else {}).items():
        if ("Remark", vid) not in sup:
            out += [(f"R_{vid}_Remark_{i + 1}", vid, t["Text"], "Remark", t["Style"]) for i, t in enumerate(d["Remarks"])]
        if ("Reply", vid) not in sup:
            out += [(f"R_{vid}_Reply_{i + 1}", vid, t["Text"], "Reply", t["Style"]) for i, t in enumerate(d["Replies"])]
    cp = os.path.join(SCRIPT, "conversations.json")
    for cid, c in (json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}).items():
        for k, conv in enumerate(c["Conversations"], 1):
            for n, l in enumerate(conv["Lines"], 1):
                out.append((f"A_{cid}_{k}_{n}", c["Voices"][l["S"] - 1], l["Text"], "Amb", l.get("Style", "")))
    pmap = story.get("Map", {})
    for lid, v in story.get("Scripted", {}).items():
        if v.get("AliasOf") or v["Voice"] == "TARNISH":
            continue
        out.append((f"S_{lid}", v["Voice"], v["Text"], "Tarnished" if v.get("FX") == "tarnished" else "Reply", v.get("Style", "")))
    for pid, groups in story.get("Barks", {}).items():
        for g, items in groups.items():
            out += [(f"SB_{g}_{pid}_{i}", pmap[pid], x["Text"], STORY_BARK_KIND[g], x.get("Style") or x.get("Delivery", ""))
                    for i, x in enumerate(items, 1) if not x.get("Take")]
    for pid, items in story.get("Replies", {}).items():
        out += [(f"P_{pid}_{i}", pmap[pid], x["Text"], "Reply", x.get("Style", "")) for i, x in enumerate(items, 1)]
    for cid, convs in story.get("Conversations", {}).items():
        for k, conv in enumerate(convs, 1):
            for n, l in enumerate(conv["Lines"], 1):
                out.append((f"{'SC' if l.get('Locked') else 'C'}_{cid}_{k}_{n}", pmap[l["P"]], l["Text"], "Amb", l.get("Style", "")))
    return out


def spoken(text):
    return text.replace("Lanthorne", "Lant-horn")


def plain(text):
    return re.sub(r"<[^>]+>", " ", text)


def synth(voice_ids=None, workers=6):
    _heavy()
    import uniq_check as U
    ex_cross, ex_self, near = U.check(U.collect())
    if ex_cross or ex_self:
        sys.exit(f"REFUSING to synthesize: {len(ex_cross)} lines shared across speakers, {len(ex_self)} repeated by one "
                 f"speaker (run uniq_fix.py). Near-duplicates: {len(near)}.")
    gk, ok = G.load_key(), T.load_key()
    roster = {v["VoiceId"]: v for v in B.load_roster()}
    try:
        import realtime_tts as R, story_lines as SL
        names = sorted({w for x in SL.people()["people"] for w in re.findall(r"[A-Z][a-z]+", x["name"])} | {"Wren", "Ren", "Elin", "Hale"})
        R.VOCAB = R.VOCAB + " " + ", ".join(names) + "."
    except Exception as e:
        print("vocab: story names not added:", e)
    os.makedirs(RAW, exist_ok=True)
    man = json.load(open(MAN)) if os.path.exists(MAN) else {}
    hv = hero_voice()
    gv = lambda vid: hv if vid == "HERO" else roster[vid].get("GeminiVoice")
    todo = [l for l in lines() if (not voice_ids or l[1] in voice_ids) and gv(l[1])
            and not os.path.exists(os.path.join(RAW, l[0] + ".wav"))]
    # story lines first (cutscenes and quests are waiting on them), then barks and replies, then ambient conversations
    order = {"S": 0, "SB": 1, "P": 1, "B": 2, "R": 2, "SC": 3, "C": 3, "A": 4}
    todo.sort(key=lambda l: order.get(l[0].split("_")[0], 5))
    print("to synthesize:", len(todo))

    def one(l):
        lid, vid, text, kind, style = l
        try:
            if U.is_wordless(text):  # grunts and gasps: one take, no transcript check (judged by ear in a sample)
                sc, heard, t = B.synth_line(gk, ok, gv(vid), spoken(text), style, os.path.join(RAW, lid + ".wav"),
                                            want_text=plain(text), tries=1, accept=0.0)
                return lid, {"voice": vid, "gemini_voice": gv(vid), "model": B.MODEL, "text": text, "style": style,
                             "stt": heard, "stt_engine": B.TRANSCRIBER, "match": 1.0, "wordless": True, "tries": t}
            sc, heard, t = B.synth_line(gk, ok, gv(vid), spoken(text), style, os.path.join(RAW, lid + ".wav"),
                                        want_text=plain(text))
            return lid, {"voice": vid, "gemini_voice": gv(vid), "model": B.MODEL, "text": text, "style": style,
                         "stt": heard, "stt_engine": B.TRANSCRIBER, "match": round(sc, 3), "tries": t}
        except Exception as e:
            return lid, {"error": G.scrub(e, gk)[:200]}

    done = 0
    with ThreadPoolExecutor(workers) as ex:
        for lid, info in ex.map(one, todo):
            man[lid] = info
            done += 1
            if done % 20 == 0 or "error" in info:
                json.dump(man, open(MAN, "w"), indent=1)
                print(done, lid, info.get("match", info.get("error")), flush=True)
    json.dump(man, open(MAN, "w"), indent=1)
    good = [m for m in man.values() if m.get("match", 0) >= 0.999]
    print("lines:", len(man), "exact:", len(good), "below:", [k for k, m in man.items() if m.get("match", 0) < 0.999][:20])


def retake(workers=4, tries=3):
    """Re-voice only lines whose best take still misses a word (re-scored with the current matcher, which treats any
    'Silverer' spelling, dropped 'mm/shh' and homophones as a pass). Retakes ask for clear diction instead of whispers and
    turn '...' into commas from the 2nd try on. A new take replaces the old one only if it scores higher."""
    _heavy()
    import realtime_tts as R, shutil
    gk, ok = G.load_key(), T.load_key()
    roster = {v["VoiceId"]: v for v in B.load_roster()}
    hv = hero_voice()
    gv = lambda vid: hv if vid == "HERO" else roster[vid].get("GeminiVoice")
    man = json.load(open(MAN, encoding="utf-8"))
    by_id = {l[0]: l for l in lines()}
    todo = []
    for lid, m in man.items():
        if lid not in by_id or not gv(by_id[lid][1]) or m.get("wordless"):
            continue
        sc = R.word_match(plain(m.get("text", "")), m.get("stt", "")) if "stt" in m else 0.0
        m["match"] = round(sc, 3)
        m["pass"] = "stt" in m and R.passes(plain(m["text"]), m["stt"])
        if not m["pass"]:
            todo.append(lid)
    print("retakes:", len(todo), flush=True)

    def clear_style(st):
        st = re.sub(r"\b(whisper(ed|ing)?|hushed|breathless|mumbl\w*|choked|murmur\w*)\b", "", st, flags=re.I)
        return ", ".join([s.strip() for s in st.split(",") if s.strip()] + ["clear diction"])

    def one(lid):
        _, vid, text, kind, style = by_id[lid]
        best = man[lid].get("match", 0.0)
        out = None
        for t in range(1, tries + 1):
            say = spoken(text) if t == 1 else spoken(text).replace("...", ", ").replace("…", ", ")
            tmp = os.path.join(RAW, lid + ".retake.wav")
            try:
                sc, heard, _n = B.synth_line(gk, ok, gv(vid), say, clear_style(style), tmp, want_text=plain(text), tries=1)
            except Exception as e:
                return lid, {"error": G.scrub(e, gk)[:120]}
            if sc > best:
                best = sc
                shutil.move(tmp, os.path.join(RAW, lid + ".wav"))
                out = {"stt": heard, "match": round(sc, 3), "retake": t, "style_used": clear_style(style),
                       "pass": R.passes(plain(text), heard)}
                if out["pass"]:
                    break
            elif os.path.exists(tmp):
                os.remove(tmp)
            if best >= 0.999:
                break
        return lid, out

    with ThreadPoolExecutor(workers) as ex:
        for lid, upd in ex.map(one, todo):
            if upd:
                man[lid].update(upd)
            print(lid, man[lid].get("match"), flush=True)
    json.dump(man, open(MAN, "w"), indent=1)
    still = [k for k in todo if not man[k].get("pass")]
    print("retakes done; still not exact:", len(still), still[:30])


def process():
    _heavy()
    os.makedirs(FINAL, exist_ok=True)
    n = 0
    for lid, vid, text, kind, _style in lines():
        src = os.path.join(RAW, lid + ".wav")
        dst = os.path.join(FINAL, lid + ".wav")
        if not os.path.exists(src) or (os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(src)):
            continue
        x, sr = A.decode(src)
        m = A.to_mono(x)
        m = A.trim_oneshot(m, sr, head_db=-45, tail_db=-55, pre_ms=10, post_ms=80, fade_out_ms=40)
        m = PV.tighten(m, sr, 0.3 if kind == "Bark" else MAX_GAP)
        S.SR = sr
        y = S.fft_filter(m, 80, None)
        if kind == "Tarnished":
            y = PV.fx(y, sr, "tarnished")
        y = S.fade_out(y, 80)
        g = 10 ** ((TARGET[kind] - Lv.momentary_max(y, sr)) / 20)
        pk = float(np.abs(y).max()) * g
        cap = 10 ** ((Lv.CEILING_DB + Lv.MAX_LIMIT_DB) / 20)
        if pk > cap:
            g *= cap / pk
        y, _ = Lv.limit((y * g).astype(np.float32), sr)
        A.write_wav(dst, y, sr)
        n += 1
    print("processed", n)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "plan":
        _heavy()
        ls = lines()
        roster = {v["VoiceId"]: v for v in B.load_roster()}
        from collections import Counter
        print(len(ls), "lines", Counter(l[3] for l in ls), "voices designed:", sum(1 for v in roster.values() if v.get("GeminiVoice")))
    elif cmd == "synth":
        synth(set(sys.argv[2:]) or None)
    elif cmd == "process":
        process()
    elif cmd == "retake":
        retake()
