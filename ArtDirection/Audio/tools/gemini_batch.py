"""Design roster voices with Gemini and synthesize lines; every line STT-checked (OpenAI gpt-4o-transcribe).

    python gemini_batch.py design V001 V002 ...      create missing designed voices (stores GeminiVoice id in roster.json)
    python gemini_batch.py sample                     batch-1 sample lines for the reel
Keys: Gemini from ~/.gemini/api_key, OpenAI (STT only) from ~/.openai/api_key; never printed or stored.
"""
import sys, os, json, time, threading
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_tts as G
import tts as T
import realtime_tts as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROSTER = os.path.join(ROOT, "voice", "roster.json")
GOUT = os.path.join(ROOT, "voice", "gemini")
MODEL = "gemini-3.8-flash-tts"
LOCK = threading.Lock()


def load_roster():
    return json.load(open(ROSTER))


def save_roster(r):
    with LOCK:
        json.dump(r, open(ROSTER, "w"), indent=1)


def design(ids, workers=4):
    gk = G.load_key()
    r = load_roster()
    todo = [v for v in r if v["VoiceId"] in ids and not v.get("GeminiVoice")]

    def one(v):
        for attempt in range(4):
            try:
                if not v.get("Brief"):
                    return v["VoiceId"], "SKIP no brief"
                res, wav = G.design_voice(gk, f"Lanthorne {v['VoiceId']} {v['Role']}", v["Brief"],
                                          gender="female" if v["Sex"] == "F" else "male", language_code="en-GB", model=MODEL)
                os.makedirs(os.path.join(GOUT, "previews"), exist_ok=True)
                if wav:
                    open(os.path.join(GOUT, "previews", v["VoiceId"] + ".wav"), "wb").write(wav)
                with LOCK:
                    v["GeminiVoice"] = res["id"]
                save_roster(r)
                return v["VoiceId"], res["id"]
            except Exception as e:
                msg = G.scrub(e, gk)
                if "429" in msg or "RESOURCE" in msg or "503" in msg:
                    time.sleep(10 * (attempt + 1))
                    continue
                if "safety" in msg.lower():
                    return v["VoiceId"], "SAFETY " + msg[:120]
                return v["VoiceId"], "FAIL " + msg[:200]
        return v["VoiceId"], "FAIL retries"

    with ThreadPoolExecutor(workers) as ex:
        for vid, res in ex.map(one, todo):
            print(vid, res)


TRANSCRIBER = os.environ.get("TRANSCRIBER", "gemini")  # gemini (default since 2026-11-14 evening) or openai


def check_transcript(gk, ok, path):
    """Verbatim transcript for the word check. Gemini by default: in stt_compare.py it passed 29/30 takes OpenAI heard
    word for word and caught 10/10 deliberately wrong takes, the same as OpenAI."""
    if TRANSCRIBER == "openai" and ok:
        return R.stt(ok, path)
    for attempt in range(3):
        try:
            return G.transcribe(gk, path, R.VOCAB)
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(4 * (attempt + 1))


def synth_line(gk, ok, voice_id, text, style, out_path, want_text=None, tries=3, accept=0.999):
    """Synthesize one line; accept when STT word match >= 0.85. Returns (score, heard, tries)."""
    best = None
    for t in range(1, tries + 1):
        try:
            wav = G.speak(gk, text, voice_id, style=style, model=MODEL)
        except Exception as e:
            msg = G.scrub(e, gk)
            if "429" in msg or "503" in msg:
                time.sleep(8 * t)
                continue
            raise RuntimeError(msg)
        tmp = out_path + ".take.wav"
        open(tmp, "wb").write(wav)
        heard = check_transcript(gk, ok, tmp)
        sc = R.word_match(want_text or text, heard)
        if best is None or sc > best[0]:
            best = (sc, heard, t)
            os.replace(tmp, out_path)
        else:
            os.remove(tmp)
        if sc >= accept:
            break
    return best


SAMPLE_LINES = {
    ("Pewterside", "civilian"): "Rain again. You'd think the glass would at least keep the damp out.",
    ("Giltside", "civilian"): "Lanterns are up early this year. Come and look before the crowds get here!",
    ("Frostside", "civilian"): "Keep your hands where I can see them. Out here, everyone's hungry.",
    ("any", "guard"): "Move along now. The watch doesn't like crowds near the bridge.",
    ("any", "soldier"): "Form up! Second line, shields high!",
    ("any", "vendor"): "Fresh broth, still warm! Best you'll find on this side of the glass.",
    ("lanthorne", "civilian"): "They say every street in Lanthorne has three faces. I've only ever trusted one.",
}


def pick_batch1(r):
    want = [("F", "Pewterside", "young", None), ("F", "Giltside", "older", None), ("F", "Frostside", "middle", None),
            ("F", None, None, "guard"), ("F", "Giltside", None, "soldier"), ("M", "Pewterside", "older", None),
            ("M", "Giltside", None, "soldier"), ("M", "Frostside", "young", None), ("M", None, None, "guard"),
            ("M", "Frostside", "older", None)]
    chosen = []
    for sex, side, band, arch in want:
        for v in r:
            if v in chosen or v["Sex"] != sex:
                continue
            if side and v["Side"] != side:
                continue
            if band and v["AgeBand"] != band:
                continue
            if arch and v["Archetype"] != arch:
                continue
            if not arch and v["Archetype"] != "civilian":
                continue
            chosen.append(v)
            break
    return chosen


def sample():
    gk, ok = G.load_key(), T.load_key()
    r = load_roster()
    batch = pick_batch1(r)
    os.makedirs(os.path.join(GOUT, "sample"), exist_ok=True)
    res = []
    for i, v in enumerate(batch):
        if v["Archetype"] in ("guard", "soldier"):
            text = SAMPLE_LINES[("any", v["Archetype"])]
        elif "seller" in v["Role"] or "vendor" in v["Role"] or "trader" in v["Role"]:
            text = SAMPLE_LINES[("any", "vendor")]
        elif i == 1:
            text = SAMPLE_LINES[("lanthorne", "civilian")]
        else:
            text = SAMPLE_LINES[(v["Side"], "civilian")]
        out = os.path.join(GOUT, "sample", v["VoiceId"] + ".wav")
        sc, heard, t = synth_line(gk, ok, v["GeminiVoice"], text, "", out)
        res.append({"VoiceId": v["VoiceId"], "Description": v["Description"], "text": text, "stt": heard, "match": round(sc, 2), "tries": t})
        print(f"{v['VoiceId']} {sc:.2f} | {heard}".encode("ascii", "replace").decode())
    json.dump(res, open(os.path.join(GOUT, "sample", "sample.json"), "w"), indent=1)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "design":
        design(set(sys.argv[2:]))
    elif cmd == "batch1":
        print([v["VoiceId"] for v in pick_batch1(load_roster())])
    elif cmd == "sample":
        sample()
