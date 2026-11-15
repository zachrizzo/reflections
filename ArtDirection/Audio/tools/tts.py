"""Generate the voice script with OpenAI text-to-speech.

    python tts.py --dry-run            list what would be generated (no network, no key needed)
    python tts.py [--force] [ids...]   generate missing lines (or the given ids) into <work>/voice/raw/<id>.wav

KEY HANDLING: the key is read from the OPENAI_API_KEY environment variable, else from the one-line file
C:\\Users\\zachc\\.openai\\api_key (outside the project). It is only ever placed in the HTTPS Authorization header.
It is never printed, logged, written to disk or passed on a command line, and any error text is scrubbed of it.
"""
import sys, os, json, re, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice_script as V

WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voice")
RAW = os.path.join(WORK, "raw")
KEY_FILE = os.path.join(os.path.expanduser("~"), ".openai", "api_key")
URL = "https://api.openai.com/v1/audio/speech"


def load_key():
    k = os.environ.get("OPENAI_API_KEY", "").strip()
    if not k and os.path.isfile(KEY_FILE):
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            k = f.readline().strip()
    return k or None


def scrub(text, key):
    text = str(text)
    if key:
        text = text.replace(key, "[REDACTED]")
    return re.sub(r"sk-[A-Za-z0-9_\-]{4,}", "sk-[REDACTED]", text)


def speak(key, voice, text, instructions):
    body = json.dumps({"model": V.MODEL, "voice": voice, "input": text, "instructions": instructions,
                       "response_format": "wav"}).encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main(argv):
    dry = "--dry-run" in argv
    force = "--force" in argv
    ids = [a for a in argv if not a.startswith("--")]
    V.check()
    todo = [l for l in V.LINES if (not ids or l[0] in ids) and (force or not os.path.exists(os.path.join(RAW, l[0] + ".wav")))]
    if dry:
        for lid, grp, spk, text in todo:
            print(f"{lid:28s} {V.SPEAKERS[spk][0]:7s} {text}")
        print(len(todo), "to generate;", "key present" if load_key() else "no key yet")
        return 0
    key = load_key()
    if not key:
        print("No OpenAI key found (OPENAI_API_KEY or ~/.openai/api_key). Nothing generated.")
        return 2
    os.makedirs(RAW, exist_ok=True)
    manifest_p = os.path.join(WORK, "manifest.json")
    manifest = json.load(open(manifest_p)) if os.path.exists(manifest_p) else {}
    ok = fail = 0
    for lid, grp, spk, text in todo:
        voice, inst, fx = V.SPEAKERS[spk]
        done = False
        for attempt in range(3):
            try:
                data = speak(key, voice, text, inst)
                with open(os.path.join(RAW, lid + ".wav"), "wb") as f:
                    f.write(data)
                manifest[lid] = {"model": V.MODEL, "voice": voice, "speaker": spk, "text": text, "instructions": inst,
                                 "bytes": len(data), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                print("ok  ", lid, len(data))
                done = True
                break
            except urllib.error.HTTPError as e:
                msg = scrub(e.read().decode("utf-8", "replace")[:400], key)
                print("fail", lid, e.code, msg)
                if e.code in (400, 401, 403, 404):
                    break
                time.sleep(2 + 3 * attempt)
            except Exception as e:  # network etc.
                print("fail", lid, scrub(type(e).__name__ + ": " + str(e), key))
                time.sleep(2 + 3 * attempt)
        ok += done
        fail += not done
    json.dump(manifest, open(manifest_p, "w"), indent=1)
    print(f"generated {ok}, failed {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
