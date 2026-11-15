"""Narrator replacement (user, 2026-11-14 evening: "I also hate the narrator voice. It is too clean.").

    python narrator_audition.py design      design the 3 candidates (voice/narrator_candidates.json)
    python narrator_audition.py audition    each candidate reads 4 lines -> voice/gemini/narrator/<K>_<line>.wav (+ post)
    python narrator_audition.py judge       Gemini audio judgement of A/B/C plus the old narrator -> voice/narrator_judgement.json
    python narrator_audition.py voice K     voice all 10 narrator lines with candidate K -> voice/final/Narrator_*.wav
    python narrator_audition.py compare     old vs new clip -> ArtDirection/Audio/reel/Reflections_narrator_old_vs_new.mp3
Post-processing (post()): gentle trim (no gate), a touch of warmth and saturation, a short warm room reverb and a quiet
room tone bed under the line, levelled to the narrator target (-18 LUFS momentary max).
"""
import sys, os, json, base64, io, wave, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import gemini_tts as G, tts as T, gemini_batch as B, audiolib as A, conv_gen as CG, synth as S, level as Lv
import voice_script as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "voice", "gemini", "narrator")
CAND_P = os.path.join(ROOT, "voice", "narrator_candidates.json")
JUDGE_P = os.path.join(ROOT, "voice", "narrator_judgement.json")
CHOICE_P = os.path.join(ROOT, "voice", "narrator_choice.json")
FINAL = os.path.join(ROOT, "voice", "final")
OLD = os.path.join(ROOT, "voice", "final_openai_narrator")  # backup of the replaced OpenAI takes
REEL = r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\Audio\reel"

COMMON = ("He or she never sounds like an announcer or an advert: the voice is close to the listener, lived-in and textured, "
          "with natural breaths, uneven pacing and pauses where a person would stop to think.")
CANDIDATES = {
    "A": ("male", "A man in his seventies, a retired lamplighter of the old city, with a weathered, gravelly baritone, a soft "
                  "rasp and an audible breath between phrases, and a broad Yorkshire accent with flat, warm vowels. He speaks "
                  "low and close, as if by a hearth, at an unhurried and uneven pace: he lingers on some words, hurries "
                  "others, and lets pauses fall where he is remembering. Lived-in and textured, never smooth."),
    "B": ("female", "A woman in her late sixties, keeper of the city's old records, with a husky, smoky alto worn rough at the "
                    "edges, a faint catch of breath, and a soft Scottish accent with gently rolled r's. She speaks intimately "
                    "close, quietly confiding, with an uneven, thoughtful rhythm, small hesitations and a dry warmth. "
                    "Textured and human, never polished or broadcast-smooth."),
    "C": ("male", "A man in his sixties with a deep, smoky voice that cracks a little and a dry rattle low in the chest, and a "
                  "rural West Country accent with rolling r's and broad vowels. He tells stories by a fire: close and "
                  "conspiratorial, a wry smile in the voice, natural breaths, irregular pacing and a long pause before the "
                  "word that matters. Earthy and worn, never smooth."),
}
STYLE = {  # per-line delivery (emotion, volume, pace only)
    "Narrator_Intro": "close and confiding, brisk conversational pace",  # fits the title card (the slower take ran 13.4 s)
    "Narrator_Tip_Aim": "plain and friendly, unhurried",
    "Narrator_Tip_Cast": "plain and friendly, a little wonder",
    "Narrator_Tip_Shard": "plain, friendly, matter-of-fact",
    "Narrator_Tip_StepThrough": "friendly, quietly fascinated",
    "Narrator_Tip_Crafting": "warm, encouraging, unhurried",
    "Narrator_FirstHost": "hushed warning, grave",
    "Narrator_MirrorWhole": "quiet, rising resolve",
    "Narrator_FinalSpellHint": "low, confiding, grave",
    "Narrator_Victory": "quiet relief, warm and slow",
}
AUDITION = ["Narrator_Intro", "Narrator_Tip_Cast", "Narrator_FirstHost", "Narrator_Victory"]


def lines():
    return {lid: text for lid, grp, spk, text in V.LINES if spk == "Narrator"}


def post(x, sr, seed=5):
    """Narrator chain: gentle trim, warmth + saturation, short warm room, quiet room tone; no gate between words."""
    rng = np.random.default_rng(seed)
    x = A.to_mono(x)
    x = A.trim_oneshot(x, sr, head_db=-50, tail_db=-62, pre_ms=30, post_ms=300, fade_out_ms=200)
    S.SR = sr
    x = S.fft_filter(x, 70, None)
    warm = S.fft_filter(x, None, 350)
    y = x + 0.08 * warm  # a touch of low-mid body
    y = y / (np.abs(y).max() + 1e-9) * 0.7
    y = (np.tanh(1.35 * y) / np.tanh(1.35)).astype(np.float32)  # gentle saturation
    y = S.reverb(y, wet=0.11, size=0.32, tail_s=0.45, damp_hz=4200)[: len(y) + int(0.35 * sr)]
    pre = int(0.18 * sr)
    y = np.concatenate([np.zeros(pre, np.float32), y.astype(np.float32)])
    # room tone loud enough that pauses keep the same air as the speech (TTS breath noise vanishes in pauses, which
    # otherwise reads as a noise gate), but well under the voice
    tone = S.fft_filter(S.colored(rng, len(y), -5.0), 60, 3500) * (0.85 + 0.15 * np.abs(S.fft_filter(rng.standard_normal(len(y)), None, 0.7)).clip(0, 1))
    tone = tone / (A.rms(tone) + 1e-9) * (10 ** (-50 / 20)) * float(np.abs(y).max())  # ~-50 dB under the line's peak
    f, f2 = int(0.12 * sr), int(0.35 * sr)
    tone[:f] *= np.linspace(0, 1, f); tone[-f2:] *= np.linspace(1, 0, f2) ** 2
    y = y + tone
    y = y - 0.12 * S.fft_filter(y, 140, 260)  # a small dip in the 150-250 Hz chest build-up
    g = 10 ** ((-18 - Lv.momentary_max(y, sr)) / 20)
    y, _ = Lv.limit((y * g).astype(np.float32), sr)
    return y


def design():
    gk = G.load_key()
    cands = json.load(open(CAND_P)) if os.path.exists(CAND_P) else {}
    for k, (sex, brief) in CANDIDATES.items():
        if k in cands:
            continue
        for attempt in range(4):
            try:
                res, _wav = G.design_voice(gk, f"Lanthorne Narrator {k} (narrator candidate)", brief + " " + COMMON.replace(
                    "He or she", "He" if sex == "male" else "She"), gender=sex, language_code="en-GB", model=B.MODEL)
                cands[k] = {"voice": res["id"], "brief": brief, "sex": sex}
                json.dump(cands, open(CAND_P, "w"), indent=1)
                print(k, "designed", res["id"], flush=True)
                break
            except Exception as e:
                print(k, "design error:", G.scrub(e, gk)[:120], flush=True)


def audition():
    gk, ok = G.load_key(), T.load_key()
    cands = json.load(open(CAND_P))
    os.makedirs(OUT, exist_ok=True)
    L = lines()
    rep = {}
    for k, c in cands.items():
        for lid in AUDITION:
            raw = os.path.join(OUT, f"{k}_{lid}.raw.wav")
            sc, heard, tries = B.synth_line(gk, ok, c["voice"], L[lid].replace("Lanthorne", "Lant-horn"), STYLE[lid], raw,
                                            want_text=L[lid])
            x, sr = A.decode(raw)
            A.write_wav(os.path.join(OUT, f"{k}_{lid}.wav"), post(x, sr), sr)
            rep[f"{k}_{lid}"] = {"match": round(sc, 3), "heard": heard}
            print(k, lid, round(sc, 2), heard[:70], flush=True)
    json.dump(rep, open(os.path.join(OUT, "audition.json"), "w"), indent=1)


def clip(paths, gap=0.6):
    xs, sr = [], 24000
    for p in paths:
        x, sr = A.decode(p)
        xs += [A.to_mono(x), np.zeros(int(sr * gap), np.float32)]
    y = np.concatenate(xs)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def judge():
    gk = G.load_key()
    cands = json.load(open(CAND_P))
    parts = []
    names = list(cands) + ["OLD"]
    for k in names:
        ps = [os.path.join(FINAL if k == "OLD" else OUT, (f"{lid}.wav" if k == "OLD" else f"{k}_{lid}.wav")) for lid in AUDITION]
        if k == "OLD" and os.path.exists(OLD):
            ps = [os.path.join(OLD, f"{lid}.wav") for lid in AUDITION]
        parts += [{"text": f"Candidate {k}:"}, {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(clip(ps)).decode()}}]
    L = lines()
    said = "; ".join(f'"{L[l]}"' for l in AUDITION)
    prompt = ("You are casting the narrator of a dark-fantasy story game. The director's brief: the current narrator is "
              "'too clean'. The new narrator must have CHARACTER: weathered, textured, lived-in, like an old lamplighter or "
              "archivist telling a story by a fire; slight rasp and breath, natural pauses and uneven pacing, a regional "
              "accent, intimate and close, not announcer-smooth. It must still be clear enough for short gameplay tips. "
              f"Each candidate reads the same four lines: {said}. Score every candidate 1-10 on: character (weathered, "
              "lived-in, textured), intimacy (close, fireside), naturalness (pacing, breath, no robotic artefacts), "
              "clarity (every word understood once), fit (right for a dark-fantasy city's storyteller). Then pick the "
              'single best NEW candidate (not OLD). Return JSON: {"scores": {"A": {"character": 0, "intimacy": 0, '
              '"naturalness": 0, "clarity": 0, "fit": 0, "note": "..."}}, "pick": "A", "why": "..."}')
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}] + parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    r = G._req(gk, "POST", f"/models/{CG.TEXT_MODEL}:generateContent", body, timeout=300)
    out = json.loads("".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"]))
    json.dump(out, open(JUDGE_P, "w"), indent=1)
    for k, sc in out["scores"].items():
        tot = sum(v for kk, v in sc.items() if kk != "note" and isinstance(v, (int, float)))
        print(k, tot, {kk: v for kk, v in sc.items() if kk != "note"}, "|", str(sc.get("note", ""))[:160])
    print("PICK", out["pick"], "|", out["why"][:300])


def voice(k):
    gk, ok = G.load_key(), T.load_key()
    cands = json.load(open(CAND_P))
    c = cands[k]
    os.makedirs(OUT, exist_ok=True); os.makedirs(OLD, exist_ok=True)
    rep = {}
    for lid, text in lines().items():
        old = os.path.join(FINAL, f"{lid}.wav")
        if os.path.exists(old) and not os.path.exists(os.path.join(OLD, f"{lid}.wav")):
            shutil.copy2(old, os.path.join(OLD, f"{lid}.wav"))
        raw = os.path.join(OUT, f"{k}_{lid}.raw.wav")
        if not os.path.exists(raw):
            sc, heard, tries = B.synth_line(gk, ok, c["voice"], text.replace("Lanthorne", "Lant-horn"), STYLE[lid], raw,
                                            want_text=text)
        else:
            heard = B.check_transcript(gk, ok, raw); sc = B.R.word_match(text, heard)
        import realtime_tts as R
        if not R.passes(text, heard):
            sc, heard, tries = B.synth_line(gk, ok, c["voice"], text.replace("Lanthorne", "Lant-horn"),
                                            STYLE[lid] + ", clear diction", raw, want_text=text)
        x, sr = A.decode(raw)
        A.write_wav(old, post(x, sr), sr)
        rep[lid] = {"engine": B.MODEL, "voice": c["voice"], "candidate": k, "text": text, "style": STYLE[lid], "stt": heard,
                    "stt_engine": B.TRANSCRIBER, "match": round(sc, 3), "pass": R.passes(text, heard)}
        print(lid, round(sc, 2), rep[lid]["pass"], heard[:80], flush=True)
    json.dump({"Candidate": k, "GeminiVoice": c["voice"], "lines": rep}, open(CHOICE_P, "w"), indent=1)


def compare():
    import reel as RL
    ch = json.load(open(CHOICE_P))
    parts = [RL.silence(0.3)]
    for lid in ["Narrator_Intro", "Narrator_FirstHost", "Narrator_Victory"]:
        for src in (OLD, FINAL):
            x, sr = A.decode(os.path.join(src, f"{lid}.wav"))
            x = A.to_mono(x)
            if sr != RL.SR:
                x = np.interp(np.linspace(0, len(x) - 1, int(len(x) * RL.SR / sr)), np.arange(len(x)), x).astype(np.float32)
            parts += [RL.beep() if src == OLD else RL.silence(0.15), RL.silence(0.35), x, RL.silence(0.9)]
    y = np.concatenate(parts)
    mp3 = os.path.join(REEL, "Reflections_narrator_old_vs_new.mp3")
    if not RL.write_mp3(mp3, y):
        mp3 = mp3[:-4] + ".wav"; A.write_wav(mp3, y, RL.SR)
    print(mp3, round(len(y) / RL.SR, 1), "s")


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"design": design, "audition": audition, "judge": judge, "compare": compare}.get(cmd, lambda: voice(sys.argv[2]))()
