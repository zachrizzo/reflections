"""Compare Gemini and OpenAI transcription as the word check for baked lines.

    python stt_compare.py
1) 30 takes OpenAI heard word for word: does Gemini pass them too? (false fails)
2) the takes OpenAI did NOT pass (names, accent words): does Gemini pass them?
3) 10 deliberately wrong takes (one word changed, synthesized in the same voice): does each check catch them? (false passes)
Writes voice/stt_compare.json. Keys from ~/.gemini/api_key and ~/.openai/api_key, read inside the helpers only.
"""
import sys, os, json, random, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
import gemini_tts as G, tts as T, realtime_tts as R, synth_roster as SR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "voice", "gemini", "raw")
OUT = os.path.join(ROOT, "voice", "stt_compare.json")
SWAP = ["little", "never", "always", "quickly", "garden", "yellow", "morning", "careful"]


def main():
    gk, ok = G.load_key(), T.load_key()
    man = json.load(open(os.path.join(ROOT, "voice", "gemini", "manifest.json"), encoding="utf-8"))
    rng = random.Random(11)
    have = [k for k, m in man.items() if "stt" in m and not m.get("wordless") and os.path.exists(os.path.join(RAW, k + ".wav"))]
    exact = rng.sample([k for k in have if float(m_ := man[k]["match"]) >= 0.999], 30)
    failing = [k for k in have if not R.passes(SR.plain(man[k]["text"]), man[k]["stt"])][:20]
    vocab = R.VOCAB

    def gem(path):
        try:
            return G.transcribe(gk, path, vocab)
        except Exception as e:
            return "ERROR " + G.scrub(e, gk)[:80]

    res = {"exact": [], "openai_failing": [], "altered": []}
    with ThreadPoolExecutor(4) as ex:
        for k, h in zip(exact, ex.map(lambda k: gem(os.path.join(RAW, k + ".wav")), exact)):
            res["exact"].append({"id": k, "text": man[k]["text"], "gemini": h, "gemini_pass": R.passes(SR.plain(man[k]["text"]), h)})
        for k, h in zip(failing, ex.map(lambda k: gem(os.path.join(RAW, k + ".wav")), failing)):
            res["openai_failing"].append({"id": k, "text": man[k]["text"], "openai": man[k]["stt"], "gemini": h,
                                          "gemini_pass": R.passes(SR.plain(man[k]["text"]), h)})
    # altered takes
    tmpdir = os.path.join(ROOT, "voice", "stt_test"); os.makedirs(tmpdir, exist_ok=True)
    picks = rng.sample(exact, 10)

    def altered(k):
        text = SR.plain(man[k]["text"]).strip()
        words = text.split()
        idx = [i for i, w in enumerate(words) if len(re.sub(r"[^A-Za-z]", "", w)) >= 4]
        i = idx[len(idx) // 2] if idx else 0
        core = re.sub(r"[^A-Za-z']", "", words[i])
        new = SWAP[hash(k) % len(SWAP)]
        words[i] = words[i].replace(core, new if core[:1].islower() else new.capitalize())
        wrong = " ".join(words)
        p = os.path.join(tmpdir, k + ".wav")
        open(p, "wb").write(G.speak(gk, wrong, man[k]["gemini_voice"], style=man[k].get("style", "")))
        return {"id": k, "script": text, "spoken": wrong, "openai": R.stt(ok, p), "gemini": gem(p)}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(altered, picks):
            r["openai_caught"] = not R.passes(r["script"], r["openai"])
            r["gemini_caught"] = not R.passes(r["script"], r["gemini"])
            res["altered"].append(r)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    e = res["exact"]; f = res["openai_failing"]; a = res["altered"]
    print(f"exact-by-OpenAI takes that Gemini also passes: {sum(x['gemini_pass'] for x in e)}/{len(e)}")
    for x in e:
        if not x["gemini_pass"]:
            print("   gemini fails:", x["text"][:70], "| heard:", x["gemini"][:70])
    print(f"takes OpenAI did not pass that Gemini passes: {sum(x['gemini_pass'] for x in f)}/{len(f)}")
    print(f"wrong takes caught: OpenAI {sum(x['openai_caught'] for x in a)}/{len(a)}, Gemini {sum(x['gemini_caught'] for x in a)}/{len(a)}")
    for x in a:
        print("   ", "O" if x["openai_caught"] else "-", "G" if x["gemini_caught"] else "-", "| spoken:", x["spoken"][:60],
              "| gemini heard:", x["gemini"][:60])


if __name__ == "__main__":
    main()
