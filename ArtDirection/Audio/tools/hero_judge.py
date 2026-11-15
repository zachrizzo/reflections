"""Ask Gemini (audio understanding) to compare the hero candidates by ear: each candidate's 4 audition lines are joined
into one clip and sent inline. Prints the scores and the pick; writes voice/hero_judgement.json."""
import sys, os, json, base64, io, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import gemini_tts as G, conv_gen as CG, audiolib as A, hero_audition as H

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cands = json.load(open(H.CAND_P))
parts = []
for k in sorted(cands):
    xs = []
    for lid, _t, _s in H.LINES:
        x, sr = A.decode(os.path.join(H.OUT, f"Wren{k}_{lid}.wav"))
        xs += [A.to_mono(x), np.zeros(int(sr * 0.6), np.float32)]
    y = np.concatenate(xs)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    parts += [{"text": f"Candidate {k}:"}, {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(buf.getvalue()).decode()}}]
lines = "; ".join(f'"{t}" ({s})' for _l, t, s in H.LINES)
prompt = ("You are casting the hero's voice for a story game. The hero is a young man in his mid-twenties: warm, steady and a "
          "little wry; he jokes when scared and goes quiet when angry. The player hears him more than anyone. Each candidate "
          f"reads the same four lines: {lines}. Listen to every candidate and score each from 1 to 10 on: distinctive "
          "(memorable, not a generic narrator), warm, wry, range (the shout, the quiet anger and the soft goodbye all convincing), "
          "natural (no robotic artefacts). Then pick the single most captivating hero voice. Return JSON: "
          '{"scores": {"A": {"distinctive": 0, "warm": 0, "wry": 0, "range": 0, "natural": 0, "note": "..."}}, "pick": "A", "why": "..."}')
key = G.load_key()
body = {"contents": [{"role": "user", "parts": [{"text": prompt}] + parts}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
r = G._req(key, "POST", f"/models/{CG.TEXT_MODEL}:generateContent", body, timeout=240)
out = json.loads("".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"]))
json.dump(out, open(os.path.join(ROOT, "voice", "hero_judgement.json"), "w"), indent=1)
for k, sc in out["scores"].items():
    tot = sum(v for kk, v in sc.items() if kk != "note")
    print(k, tot, {kk: v for kk, v in sc.items() if kk != "note"}, "|", sc.get("note", "")[:140])
print("PICK", out["pick"], "|", out["why"][:300])
