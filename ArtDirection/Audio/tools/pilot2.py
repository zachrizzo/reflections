"""Pilot 2: design the 10 pilot voices from rich briefs (A) and 3 from concise briefs (B); calm + afraid lines; STT; timings; reel."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import gemini_tts as G, tts as T, gemini_batch as B, audiolib as A, level as Lv, reel as RL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "voice", "gemini", "pilot2")
REEL = r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\Audio\reel"
PILOT = ["V001", "V032", "V059", "V011", "V024", "V064", "V087", "V105", "V065", "V101"]
AB = ["V001", "V064", "V087"]
CALM = {
    "V001": "Two loaves and the good tea, love? That's the last of it till Thursday.",
    "V032": "Beeswax candles, hand-dipped this morning. They'll burn till the lanterns go out.",
    "V059": "Line moves when it moves. Stand still and keep your bowl out.",
    "V011": "Quiet night so far. I'd like to keep it that way, if it's all the same to you.",
    "V024": "Second line, hold your spacing. I want those shields touching, not kissing.",
    "V064": "Forty years of chimneys, and not one of them ever said thank you.",
    "V087": "Breathe first, then the spell. Rushing it only singes your eyebrows.",
    "V105": "Don't look at me like that. I found it fair, out in the ruins.",
    "V065": "Evening. Mind the bridge steps, they're slick as anything tonight.",
    "V101": "My family once owned this whole street. Now I own this blanket.",
}
AFRAID = ("Did you see its eyes? Get back... get BACK!", "terrified, breathless, voice shaking")


def design_all():
    gk = G.load_key()
    r = B.load_roster()
    for v in r:
        if v["VoiceId"] not in PILOT:
            continue
        if v.get("GeminiVoice") and not v.get("PilotV2"):
            v.setdefault("Superseded", []).append(v.pop("GeminiVoice"))
        for which, field, desc in (("A", "GeminiVoice", v["Brief"]), ("B", "GeminiVoiceB", v.get("BriefShort"))):
            if which == "B" and v["VoiceId"] not in AB:
                continue
            if v.get(field) and v.get("PilotV2"):
                continue
            t0 = time.time()
            res, wav = G.design_voice(gk, f"Lanthorne {v['VoiceId']}{which} {v['Role']}", desc,
                                      gender="female" if v["Sex"] == "F" else "male", language_code="en-GB", model=B.MODEL)
            v[field] = res["id"]
            v.setdefault("Timing", {})["design_" + which] = round(time.time() - t0, 1)
            os.makedirs(OUT, exist_ok=True)
            if wav:
                open(os.path.join(OUT, f"{v['VoiceId']}{which}_preview.wav"), "wb").write(wav)
            print(v["VoiceId"], which, res["id"], v["Timing"]["design_" + which], "s")
        v["PilotV2"] = True
        B.save_roster(r)


def lines_all():
    gk, ok = G.load_key(), T.load_key()
    r = {v["VoiceId"]: v for v in B.load_roster()}
    res = []
    for vid in PILOT:
        v = r[vid]
        for which, field in (("A", "GeminiVoice"), ("B", "GeminiVoiceB")):
            if not v.get(field):
                continue
            for kind, (text, style) in (("calm", (CALM[vid], "")), ("afraid", AFRAID)):
                out = os.path.join(OUT, f"{vid}{which}_{kind}.wav")
                t0 = time.time()
                sc, heard, t = B.synth_line(gk, ok, v[field], text, style, out, want_text=text)
                dt = round((time.time() - t0) / max(1, t), 1)
                res.append({"voice": vid + which, "kind": kind, "text": text, "style": style, "stt": heard, "match": round(sc, 2),
                            "tries": t, "secs_per_call_incl_stt": dt})
                print(f"{vid}{which} {kind:6s} {sc:.2f} {dt}s | {heard}".encode("ascii", "replace").decode())
    json.dump(res, open(os.path.join(OUT, "pilot2.json"), "w"), indent=1)


def prep(path, target=-18.0):
    d, sr = A.decode(path)
    m = A.to_mono(d)
    if sr != RL.SR:
        t = np.arange(0, len(m) * RL.SR / sr) * sr / RL.SR
        m = np.interp(t, np.arange(len(m)), m).astype(np.float32)
    m = A.trim_oneshot(m, RL.SR, head_db=-40, tail_db=-50, pre_ms=5, post_ms=60, fade_out_ms=40)
    g = 10 ** ((target - Lv.momentary_max(m, RL.SR)) / 20)
    return np.clip(m * g, -0.89, 0.89).astype(np.float32)


def reel():
    r = {v["VoiceId"]: v for v in B.load_roster()}
    res = json.load(open(os.path.join(OUT, "pilot2.json")))
    parts, rows, t = [RL.silence(0.3)], [], 0.3
    for i, vid in enumerate(PILOT, 1):
        v = r[vid]
        variants = ["A", "B"] if vid in AB else ["A"]
        for which in variants:
            parts += [RL.beep(), RL.silence(0.4)] if which == "A" else [RL.beep(), RL.silence(0.12), RL.beep(), RL.silence(0.4)]
            start = t
            t += 0.49 if which == "A" else 0.7
            for kind in ("calm", "afraid"):
                x = prep(os.path.join(OUT, f"{vid}{which}_{kind}.wav"))
                parts += [x, RL.silence(0.6)]
                t += len(x) / RL.SR + 0.6
            parts.append(RL.silence(0.5)); t += 0.5
            calm = next(x for x in res if x["voice"] == vid + which and x["kind"] == "calm")
            afr = next(x for x in res if x["voice"] == vid + which and x["kind"] == "afraid")
            label = f"{i}{'' if which == 'A' else 'b'}"
            head = (f"**{label}. {vid} ({'female' if v['Sex'] == 'F' else 'male'}, {v['Side']}, {v['Role']})**"
                    + (" — A: rich brief" if vid in AB and which == "A" else " — B: concise brief (double beep)" if which == "B" else "")
                    + f" at {start:.0f} s")
            brief = v["Brief"] if which == "A" else v["BriefShort"]
            rows += [head, f"> {brief}", "",
                     f"- calm (no style): \"{calm['text']}\" → heard \"{calm['stt']}\" ({calm['match']})",
                     f"- afraid (style \"{afr['style']}\"): \"{afr['text']}\" → heard \"{afr['stt']}\" ({afr['match']})", ""]
    y = np.concatenate(parts)
    mp3 = os.path.join(REEL, "Reflections_voice_pilot2.mp3")
    if not RL.write_mp3(mp3, y):
        mp3 = mp3[:-4] + ".wav"; A.write_wav(mp3, y, RL.SR)
    calls = [x["secs_per_call_incl_stt"] for x in res]
    open(os.path.join(REEL, "voice_pilot2.md"), "w", encoding="utf-8").write(
        f"# Voice pilot 2: rich briefs, calm vs afraid ({len(y) / RL.SR:.0f} s)\n\n"
        "Model gemini-3.8-flash-tts, Voice design (en-GB). One beep = voice from the rich brief (A); a double beep = the same "
        "character designed from Google's concise 1–2 sentence style (B), for voices 1, 6 and 7. Each voice says a calm line "
        "with no style, then a frightened line with style \"terrified, breathless, voice shaking\".\n\n"
        f"Average time per line (synthesis + speech-to-text check): {sum(calls) / len(calls):.1f} s.\n\n" + "\n".join(rows) + "\n")
    print(mp3, round(len(y) / RL.SR, 1), "s")


if __name__ == "__main__":
    {"design": design_all, "lines": lines_all, "reel": reel}[sys.argv[1]]()
