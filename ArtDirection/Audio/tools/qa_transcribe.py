"""QA: transcribe the processed voice files with OpenAI speech-to-text and compare them with the script.
Same key rules as tts.py (never printed/logged; scrubbed from errors)."""
import sys, os, json, uuid, urllib.request, urllib.error, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice_script as V
import tts as T
import realtime_tts as R

FINAL = os.path.join(T.WORK, "final")


def pick_stt(key):
    req = urllib.request.Request("https://api.openai.com/v1/models", headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=60) as r:
        ids = {m["id"] for m in json.loads(r.read().decode("utf-8"))["data"]}
    for m in ("gpt-4o-transcribe", "gpt-4o-mini-transcribe", "whisper-1"):
        if m in ids:
            return m
    return None


def transcribe(key, model, path):
    b = uuid.uuid4().hex
    data = open(path, "rb").read()
    parts = [f"--{b}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{model}\r\n".encode(),
             f"--{b}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\nen\r\n".encode(),
             f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(path)}\"\r\nContent-Type: audio/wav\r\n\r\n".encode(),
             data, f"\r\n--{b}--\r\n".encode()]
    req = urllib.request.Request("https://api.openai.com/v1/audio/transcriptions", data=b"".join(parts), method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8")).get("text", "")


def main(ids):
    key = T.load_key()
    if not key:
        print("no key")
        return 2
    model = pick_stt(key)
    print("stt model:", model)
    out = {}
    for lid, grp, spk, text in V.LINES:
        if ids and lid not in ids:
            continue
        p = os.path.join(FINAL, lid + ".wav")
        if not os.path.exists(p):
            continue
        try:
            heard = transcribe(key, model, p)
        except Exception as e:
            print("fail", lid, T.scrub(e, key)[:200])
            continue
        a, b = R.norm_words(text), R.norm_words(heard)
        sim = difflib.SequenceMatcher(None, a, b).ratio()
        out[lid] = {"heard": heard, "word_match": round(sim, 3), "stt": model}
        flag = "" if sim >= 0.9 else "   <-- CHECK"
        print(f"{lid:26s} {sim:.2f}  {heard}{flag}")
    p = os.path.join(T.WORK, "qa_transcripts.json")
    old = json.load(open(p)) if os.path.exists(p) else {}
    old.update(out)
    json.dump(old, open(p, "w"), indent=1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
