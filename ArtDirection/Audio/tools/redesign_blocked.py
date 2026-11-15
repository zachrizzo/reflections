"""Re-design voices whose prompt Google's safety filter blocked: re-roll once, then a neutral rewrite, then the short brief.

    python redesign_blocked.py V009 V026 ...
The brief actually used is saved in roster["Brief"]; the blocked original is kept in roster["BriefBlocked"].
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_tts as G
import gemini_batch as B
import conv_gen as CG

REWRITE = """Rewrite this voice description for a voice-design tool. It must describe the SAME voice: age, sex, accent,
pitch, timbre, texture, pace, baseline mood, one speech quirk and occupation. Use neutral, positive, technical vocal
terms. Avoid wording an automated safety filter could misread: nothing about choking, scraping throats, injury,
trauma, being an orphan, distrust of people or aggression; describe the accent as a regional or heritage accent of
British English, never as a trait of a people. 60 to 90 words, one paragraph, third person.
Description: {brief}
Return JSON: {{"brief": "..."}}"""


def try_design(gk, v, brief):
    res, wav = G.design_voice(gk, f"Lanthorne {v['VoiceId']} {v['Role']}", brief,
                              gender="female" if v["Sex"] == "F" else "male", language_code="en-GB", model=B.MODEL)
    if wav:
        os.makedirs(os.path.join(B.GOUT, "previews"), exist_ok=True)
        open(os.path.join(B.GOUT, "previews", v["VoiceId"] + ".wav"), "wb").write(wav)
    return res["id"]


def main(ids):
    gk = G.load_key()
    r = B.load_roster()
    for v in [v for v in r if v["VoiceId"] in ids and not v.get("GeminiVoice")]:
        original = v.get("BriefBlocked") or v["Brief"]
        tries = [("re-roll", original)]
        try:
            tries.append(("neutral rewrite", CG.gen_json(gk, REWRITE.format(brief=original), temperature=0.5)["brief"]))
        except Exception as e:
            print(v["VoiceId"], "rewrite failed:", G.scrub(e, gk)[:100])
        if v.get("BriefShort"):
            tries.append(("short brief", v["BriefShort"]))
        for how, brief in tries:
            try:
                vid = try_design(gk, v, brief)
            except Exception as e:
                msg = G.scrub(e, gk)
                print(v["VoiceId"], how, "->", "SAFETY" if "safety" in msg.lower() else msg[:120], flush=True)
                time.sleep(2)
                continue
            if brief != original:
                v["BriefBlocked"], v["Brief"] = original, brief
            v["GeminiVoice"], v["BriefHow"] = vid, how
            B.save_roster(r)
            print(v["VoiceId"], how, "-> designed", vid, flush=True)
            break
    print("designed", sum(1 for v in r if v.get("GeminiVoice")), "/", len(r),
          "still blocked:", [v["VoiceId"] for v in r if not v.get("GeminiVoice")])


if __name__ == "__main__":
    main(set(sys.argv[1:]))
