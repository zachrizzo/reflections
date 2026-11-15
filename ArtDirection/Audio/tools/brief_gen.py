"""Write voice-design briefs per roster voice with a Gemini text model: A = rich brief, B = concise (Google style).

    python brief_gen.py V001 V032 ...   (or no ids = every voice without a brief)
Rules follow Google's Voice design guidance (permanent traits only, specific, non-contradictory; fear/calm is per-line style).
"""
import sys, os, json, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_tts as G, conv_gen as C, gemini_batch as B

SIDE_FLAVOUR = {
    "Pewterside": "Pewterside, the dull grey everyday side: working people, docks, trams, rain. Accents lean weathered, practical, "
                  "period working-class British (dockside, market, mill, clerk), sometimes faded gentility.",
    "Giltside": "Giltside, the warm glowing side: festival trade, guards and soldiers, music. Accents lean crisp courtly diction, "
                "proud parade-ground command, or warm, lively market banter.",
    "Frostside": "Frostside, the cold cracked starving side: survivors, ruins, broth lines. Voices lean hollow, hushed, frost-roughened, "
                 "wary; regional accents worn thin by hardship.",
}
AGE_TXT = {"young": "early twenties", "adult": "thirties", "middle": "fifties", "older": "seventies"}


def make_prompt(v, neighbours):
    sex = "woman" if v["Sex"] == "F" else "man"
    near = "\n".join(f"- {n}" for n in neighbours) or "- (none yet)"
    return f"""You write voice-design prompts for Google's Gemini text-to-speech Voice design (a description turns into a persistent voice).
Google's rules: describe only PERMANENT traits (age, gender, timbre, vocal texture, regional accent, baseline delivery); be specific;
never contradict yourself; no stage directions; no situational emotions (fear/calm is controlled per line later).

Character: a {sex} in their {AGE_TXT[v['AgeBand']]}, works as a {v['Role']}, attitude: {v['Attitude']}, accent family: {v['Accent']}.
World: {SIDE_FLAVOUR[v['Side']]} Never mention London or any real city; you may say "British" and regional accent names.

Write two descriptions of THIS voice:
A) "brief": 3 to 4 sentences, 60 to 90 words. Cover, in flowing prose: age and sex; regional accent and class with a period British
   flavour fitting the side; timbre and pitch (e.g. low contralto, reedy tenor); texture (breathy, gravelly, clear, nasal...); pace and rhythm;
   emotional baseline; ONE distinctive speech quirk (e.g. clipped consonants, a slight catch on hard sounds, a sing-song lift at
   sentence ends, dropped h's); occupation and personality as it shows in the voice.
B) "short": 1 to 2 sentences, at most 30 words, same voice, in the style "A crisp, energetic sports announcer in her 30s with a slight
   Midwestern accent".
It must sound clearly different from these neighbouring voices:
{near}
Return JSON: {{"brief": "...", "short": "..."}}"""


def run(ids=None):
    key = G.load_key()
    r = B.load_roster()
    todo = [v for v in r if (not ids or v["VoiceId"] in ids) and (ids or not v.get("Brief"))]
    for v in todo:
        neigh = [x["Brief"][:160] for x in r if x.get("Brief") and x["Sex"] == v["Sex"] and x["VoiceId"] != v["VoiceId"]][-14:]
        for attempt in range(3):
            try:
                o = C.gen_json(key, make_prompt(v, neigh), temperature=0.9)
                a, s = o["brief"].strip(), o["short"].strip()
                wa = len(a.split())
                if 50 <= wa <= 110 and len(s.split()) <= 34 and C.clean_ok(a, 120) and C.clean_ok(s, 40):
                    v["Brief"], v["BriefShort"] = a, s
                    break
            except Exception as e:
                print(v["VoiceId"], "err", G.scrub(e, key)[:120]); time.sleep(4)
        B.save_roster(r)
        print(v["VoiceId"], len(v.get("Brief", "").split()), "words |", v.get("Brief", "")[:110].encode("ascii", "replace").decode())


if __name__ == "__main__":
    run(set(sys.argv[1:]) or None)
