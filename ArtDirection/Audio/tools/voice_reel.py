"""10-voice sample reel: per voice a beep, its scripted line, then ~6 s of its own design preview. MP3 + contents."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import audiolib as A, level as Lv, reel as RL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "voice", "gemini")
OUT = r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\Audio\reel"
SR = RL.SR

def prep(path, max_s=None, target=-18.0):
    x = RL.load.__wrapped__(path) if hasattr(RL.load, "__wrapped__") else None
    d, sr = A.decode(path)
    m = A.to_mono(d)
    if sr != SR:
        t = np.arange(0, len(m) * SR / sr) * sr / SR
        m = np.interp(t, np.arange(len(m)), m).astype(np.float32)
    m = A.trim_oneshot(m, SR, head_db=-40, tail_db=-50, pre_ms=5, post_ms=60, fade_out_ms=40)
    if max_s and len(m) > max_s * SR:  # cut at the quietest 50 ms point in the last second before max_s
        e = A.env_db(m[: int(max_s * SR)], SR, 50)
        lo = int((max_s - 1.5) / 0.05)
        k = lo + int(np.argmin(e[lo:])) if len(e) > lo else len(e)
        m = m[: k * int(0.05 * SR)]
        m = A.trim_oneshot(m, SR, head_db=-60, tail_db=-60, fade_out_ms=150)
    g = 10 ** ((target - Lv.momentary_max(m, SR)) / 20)
    return np.clip(m * g, -0.89, 0.89).astype(np.float32)

def main():
    samples = json.load(open(os.path.join(G, "sample", "sample.json")))
    roster = {v["VoiceId"]: v for v in json.load(open(os.path.join(ROOT, "voice", "roster.json")))}
    parts, rows, t = [RL.silence(0.3)], [], 0.3
    for i, s in enumerate(samples, 1):
        v = roster[s["VoiceId"]]
        parts += [RL.beep(), RL.silence(0.4)]; t += 0.49
        line = prep(os.path.join(G, "sample", s["VoiceId"] + ".wav"))
        prev = prep(os.path.join(G, "previews", s["VoiceId"] + ".wav"), max_s=6.5)
        rows.append(f"{i}. **{v['VoiceId']}** ({'female' if v['Sex']=='F' else 'male'}, {v['Side']}, {v['AgeBand']}, {v['Archetype']}) at {t:.0f} s  \n"
                    f"   Design: {v['Description']}  \n   Line: \"{s['text']}\" (heard: \"{s['stt']}\"), then ~6 s of the voice's own improvised preview.")
        parts += [line, RL.silence(0.6), prev, RL.silence(0.8)]
        t += len(line) / SR + 0.6 + len(prev) / SR + 0.8
    y = np.concatenate(parts)
    os.makedirs(OUT, exist_ok=True)
    mp3 = os.path.join(OUT, "Reflections_voice_sample_10.mp3")
    if not RL.write_mp3(mp3, y):
        mp3 = mp3[:-4] + ".wav"; A.write_wav(mp3, y, SR)
    open(os.path.join(OUT, "voice_sample_10.md"), "w", encoding="utf-8").write(
        f"# 10 sample Gemini voices ({len(y)/SR:.0f} s)\n\nEach starts with a beep: the scripted line, then a few seconds of the voice's own improvised design preview. "
        "Model gemini-3.8-flash-tts, Voice design (en-GB).\n\n" + "\n".join(rows) + "\n")
    print(mp3, round(len(y) / SR, 1), "s")

if __name__ == "__main__":
    main()
