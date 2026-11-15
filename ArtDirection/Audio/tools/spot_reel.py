"""Spot-check reel: 10 contrasting NEW voices (not the pilot), calm line in character + frightened line; STT-checked."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import gemini_tts as G, tts as T, gemini_batch as B, audiolib as A, reel as RL, pilot2 as P

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "voice", "gemini", "spot")
REEL = P.REEL


def pick(r):
    new = [v for v in r if v.get("GeminiVoice") and v["VoiceId"] not in P.PILOT]
    want = [("F", "Giltside", "soldier"), ("M", "Giltside", "soldier"), ("F", "Frostside", "guard"), ("M", "Giltside", "guard"),
            ("F", "Giltside", "civilian"), ("M", "Frostside", "civilian"), ("F", "Frostside", "civilian"), ("M", "Giltside", "civilian"),
            ("F", "Pewterside", "civilian"), ("M", "Frostside", "civilian")]
    chosen, bands = [], set()
    for sex, side, arch in want:
        c = [v for v in new if v["Sex"] == sex and v["Side"] == side and v["Archetype"] == arch and v not in chosen]
        c.sort(key=lambda v: (v["AgeBand"] in bands, v["VoiceId"]))
        if c:
            chosen.append(c[0]); bands.add(c[0]["AgeBand"])
    return chosen


def calm_line(v, vl):
    d = vl.get(v["VoiceId"])
    if d and d.get("Replies"):
        return d["Replies"][0]["Text"], d["Replies"][0]["Style"]
    return "Evening. Keep to the lit side of the street tonight.", ""


BARK_GROUP = {"civilian": "Civilian_Fear", "guard": "Guard_Alert", "soldier": "Soldier_Command"}


def bark_line(v, barks):
    items = barks.get(v["VoiceId"], {}).get(BARK_GROUP[v["Archetype"]])
    return (items[0]["Text"], items[0]["Style"]) if items else P.AFRAID


def main():
    gk, ok = G.load_key(), T.load_key()
    r = B.load_roster()
    vl_p = os.path.join(ROOT, "voice", "script", "voice_lines.json")
    vl = json.load(open(vl_p, encoding="utf-8")) if os.path.exists(vl_p) else {}
    bp = os.path.join(ROOT, "voice", "script", "barks.json")
    barks = json.load(open(bp, encoding="utf-8")) if os.path.exists(bp) else {}
    os.makedirs(OUT, exist_ok=True)
    chosen = pick(r)
    res, parts, rows, t = [], [RL.silence(0.3)], [], 0.3
    for i, v in enumerate(chosen, 1):
        parts += [RL.beep(), RL.silence(0.4)]; start = t; t += 0.49
        for kind, (text, style) in (("calm", calm_line(v, vl)), ("bark", bark_line(v, barks))):
            out = os.path.join(OUT, f"{v['VoiceId']}_{kind}.wav")
            sc, heard, tries = B.synth_line(gk, ok, v["GeminiVoice"], text.replace("Lanthorne", "Lant-horn"), style, out,
                                            want_text=text)
            res.append({"voice": v["VoiceId"], "kind": kind, "text": text, "style": style, "stt": heard, "match": round(sc, 2)})
            x = P.prep(out)
            parts += [x, RL.silence(0.6)]; t += len(x) / RL.SR + 0.6
        parts.append(RL.silence(0.5)); t += 0.5
        c, a = res[-2], res[-1]
        rows += [f"**{i}. {v['VoiceId']}** ({'female' if v['Sex'] == 'F' else 'male'}, {v['Side']}, {v['AgeBand']}, {v['Role']}) at {start:.0f} s",
                 f"> {v['Brief']}", "",
                 f"- calm (style \"{c['style']}\"): \"{c['text']}\" → heard \"{c['stt']}\" ({c['match']})",
                 f"- bark (style \"{a['style']}\"): \"{a['text']}\" → heard \"{a['stt']}\" ({a['match']})", ""]
        print(v["VoiceId"], c["match"], a["match"])
    y = np.concatenate(parts)
    mp3 = os.path.join(REEL, "Reflections_voice_spotcheck.mp3")
    if not RL.write_mp3(mp3, y):
        mp3 = mp3[:-4] + ".wav"; A.write_wav(mp3, y, RL.SR)
    ex = sum(1 for x in res if x["match"] >= 0.999)
    open(os.path.join(REEL, "voice_spotcheck.md"), "w", encoding="utf-8").write(
        f"# Spot check: 10 of the 110 new voices ({len(y) / RL.SR:.0f} s)\n\nEach: a calm line from the voice's own baked replies "
        "(with its per-line style), then its own bark (fear, guard alert or soldier command). Model gemini-3.8-flash-tts, designed from rich briefs.\n\n"
        f"STT exact: {ex}/{len(res)} lines.\n\n" + "\n".join(rows) + "\n")
    json.dump(res, open(os.path.join(OUT, "spot.json"), "w"), indent=1)
    print(mp3, round(len(y) / RL.SR, 1), "s", f"exact {ex}/{len(res)}")


if __name__ == "__main__":
    main()
