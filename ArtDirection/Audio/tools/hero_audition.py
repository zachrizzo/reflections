"""Wren Hale hero-voice audition: 3 designed Gemini candidates, each reading the same 4 cutscene lines.

    python hero_audition.py
Writes ArtDirection/Audio/reel/Reflections_hero_audition.mp3 + hero_audition.md and voice/hero_candidates.json.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import gemini_tts as G, tts as T, gemini_batch as B, audiolib as A, reel as RL, pilot2 as P

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "voice", "gemini", "hero")
CAND_P = os.path.join(ROOT, "voice", "hero_candidates.json")

COMMON = ("He speaks at an easy, grounded pace and stays calm under pressure. A dry, wry lift lands at the end of a joke, "
          "and he lets a beat of silence sit before anything that matters. When he is angry he gets quieter, not louder. "
          "Friendly, guarded and quietly brave, with a craftsman's patience in every word.")
CANDIDATES = {
    "A": "A man in his mid-twenties with a warm, steady, mid-range baritone and a soft, educated southern English accent. "
         "His tone is smooth with a slight natural grain, never gravelly, and sits comfortably in the chest. " + COMMON,
    "B": "A man in his mid-twenties with a clear, youthful light baritone that brightens toward tenor when he is excited, "
         "and a soft, educated northern English accent with warm, open vowels. His tone is clean and friendly. " + COMMON,
    "C": "A man in his mid-twenties with a rich, low baritone and a faint, pleasant huskiness, and a soft, educated Scottish "
         "accent with gently rolled consonants. His tone is close and intimate, like someone talking across a small table. " + COMMON,
    "D": "A man in his mid-twenties with a warm, characterful baritone that has a soft, smoky grain and a bright smile hidden "
         "in it, and a soft, educated British accent with a faint musical lilt. His voice is instantly recognisable: an easy, "
         "rolling rhythm, a dry little catch of amusement before a joke lands, and a low, still, intimate register when it "
         "matters, as if he is telling you something only you should hear. " + COMMON,
}
LINES = [("CS01_02", "Then play twice as loud.", "dry, wry, amused"),
         ("CS02_03", "Jory! Get away from it!", "shouted, desperate, running"),
         ("CS02_06", "Not him. You don't get him.", "quiet, cold anger"),
         ("CS06_05", "Goodbye, Mum. I looked. It was only me in there.", "soft, tearful, at peace")]


def main():
    gk, ok = G.load_key(), T.load_key()
    cands = json.load(open(CAND_P)) if os.path.exists(CAND_P) else {}
    os.makedirs(OUT, exist_ok=True)
    for k, brief in CANDIDATES.items():
        if k in cands:
            continue
        for attempt in range(3):
            try:
                res, wav = G.design_voice(gk, f"Lanthorne Wren {k} (hero candidate)", brief, gender="male",
                                          language_code="en-GB", model=B.MODEL)
                cands[k] = {"voice": res["id"], "brief": brief}
                json.dump(cands, open(CAND_P, "w"), indent=1)
                print(k, "designed", res["id"], flush=True)
                break
            except Exception as e:
                print(k, "design error:", G.scrub(e, gk)[:120], flush=True)
    parts, rows, t, res = [RL.silence(0.3)], [], 0.3, []
    for k, c in cands.items():
        parts += [RL.beep(), RL.silence(0.4)]; start = t; t += 0.49
        rows += [f"**Candidate {k}** at {start:.0f} s", f"> {c['brief']}", ""]
        for lid, text, style in LINES:
            out = os.path.join(OUT, f"Wren{k}_{lid}.wav")
            sc, heard, tries = B.synth_line(gk, ok, c["voice"], text, style, out)
            x = P.prep(out)
            parts += [x, RL.silence(0.7)]; t += len(x) / RL.SR + 0.7
            rows.append(f"- {lid} (style \"{style}\"): \"{text}\" → heard \"{heard}\" ({sc:.2f})")
            res.append(sc)
            print(k, lid, round(sc, 2), flush=True)
        rows.append(""); parts.append(RL.silence(0.8)); t += 0.8
    y = np.concatenate(parts)
    mp3 = os.path.join(P.REEL, "Reflections_hero_audition.mp3")
    if not RL.write_mp3(mp3, y):
        mp3 = mp3[:-4] + ".wav"; A.write_wav(mp3, y, RL.SR)
    open(os.path.join(P.REEL, "hero_audition.md"), "w", encoding="utf-8").write(
        f"# Wren Hale: hero voice audition ({len(y) / RL.SR:.0f} s)\n\n"
        "Three Gemini designed voices from the bible brief (warm, steady, wry, mid-twenties). They differ in pitch, timbre "
        "and regional accent. Each reads the same four cutscene lines: wry, shouted, quiet anger, soft. A beep marks each "
        "candidate. Pick one (or ask for a blend) and every Wren line gets voiced with it.\n\n"
        f"Word-for-word check: {sum(1 for s in res if s >= 0.999)}/{len(res)}.\n\n" + "\n".join(rows) + "\n")
    print(mp3, round(len(y) / RL.SR, 1), "s")


if __name__ == "__main__":
    main()
