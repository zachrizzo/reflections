"""Blind listening check of procedural SFX with Gemini audio understanding.

    python sfx_judge.py Name [Name ...]     judges proc/synth/<Name>_01.wav (and _02 if present)
For each clip Gemini first says what it hears (blind), then rates how convincing it is as the intended sound (1-10) and
names the biggest problems. Writes voice/../sfx_judgement.json. Key: ~/.gemini/api_key via gemini_tts only.
"""
import sys, os, json, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_tts as G, conv_gen as CG

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYN = os.path.join(ROOT, "proc", "synth")
OUT = os.path.join(ROOT, "sfx_judgement.json")
INTENT = {
    "Fireball_Explode": "a fireball exploding in a stone street: a big boom with flying debris and a rumbling tail",
    "Shock_Loop": "an electric shock crackling continuously over a person (looping)",
    "Shock_Collapse": "a final electric zap and then a person collapsing to the ground",
    "Water_Shove": "a heavy wave of magic water slamming into a person, with a big splash and spray",
    "Body_Knockback": "a person thrown through the air landing hard on stone cobbles",
    "Burning_Loop": "flames burning on a person's clothes (looping)",
    "March_Loop": "a squad of eight armoured soldiers marching in step on stone, boots and chain mail jingling (looping)",
    "March_Step": "one armoured soldier's boot step on stone with chain mail jingling",
    "Sword_ShieldHit": "a steel sword striking a wooden shield with a steel rim",
    "Shield_BlockHeavy": "a heavy blow absorbed by a soldier's wooden shield",
}


def judge(key, name, path):
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    prompt = ("You are a game sound designer reviewing a sound effect for a medieval-fantasy game. Step 1, BLIND: describe in "
              "a few words what this sound most likely is, before reading step 2. Step 2: the sound is meant to be "
              f"{INTENT[name]}. Rate how convincing and good it is for that purpose from 1 to 10 (7 = shippable in an indie "
              "game, 9 = as good as a commercial library), and list the two biggest problems as concrete, fixable notes "
              "(frequency, timing, layers missing or too loud). Return JSON: "
              '{"blind_guess": "...", "score": 0, "problems": ["...", "..."]}')
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}, {"inline_data": {"mime_type": "audio/wav", "data": b64}}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    r = G._req(key, "POST", f"/models/{CG.TEXT_MODEL}:generateContent", body, timeout=240)
    return json.loads("".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"]))


def main(names):
    key = G.load_key()
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for name in names:
        for k in ("01", "02"):
            p = os.path.join(SYN, f"{name}_{k}.wav")
            if not os.path.exists(p):
                continue
            try:
                o = judge(key, name, p)
            except Exception as e:
                print(name, k, "error", G.scrub(e, key)[:120]); continue
            res[f"{name}_{k}"] = o
            print(f"{name}_{k} score {o.get('score')} | blind: {o.get('blind_guess', '')[:70]} | "
                  + " / ".join(o.get("problems", []))[:260], flush=True)
    json.dump(res, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:] or list(INTENT))
