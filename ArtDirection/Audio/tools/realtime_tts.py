"""Bake voice lines with OpenAI's gpt-realtime audio model (offline; nothing runs in the game).

    python realtime_tts.py --models            list realtime models available to the key and the one that would be used
    python realtime_tts.py [--force] [ids...]  generate missing lines (or the given ids) into <work>/voice/raw/<id>.wav

For each line: open a realtime session with the character brief + delivery as session instructions, send the line as text,
collect the audio deltas (PCM16 24 kHz) and the model's own transcript, and accept the take only if the transcript matches
the script word for word (up to 2 tries). Lines that never match fall back to gpt-4o-mini-tts (recorded in the manifest).

KEY HANDLING: read from OPENAI_API_KEY or the one-line file ~/.openai/api_key (outside the project). Used only in HTTPS/WSS
Authorization headers; never printed, logged, written to disk or passed on a command line; error text is scrubbed of it.
"""
import sys, os, json, re, time, base64, wave, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice_script as V
import tts as T
from websockets.sync.client import connect

WORK = T.WORK
RAW = T.RAW
ACCEPT = 0.85  # minimum STT word match for a take


def list_models(key):
    req = urllib.request.Request("https://api.openai.com/v1/models", headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))["data"]
    return sorted(((m["id"], m.get("created", 0)) for m in data if m["id"].startswith("gpt-realtime")), key=lambda x: -x[1])


def pick_model(models):
    models = [m for m in models if not any(x in m[0] for x in ("whisper", "translate", "transcribe"))]
    full = [m for m in models if "mini" not in m[0]]
    return (full or models)[0][0] if models else None


ALIASES = [(r"\blant[- ]?horne?\b", "lanthorne"), (r"\bfrost[- ]side\b", "frostside"), (r"\bgilt[- ]side\b", "giltside"),
           (r"\bpewter[- ]side\b", "pewterside"), (r"\bit's\b", "its"), (r"\bmirrors\b", "mirror"),
           (r"\bs[iy]lv[a-z']*\b", "silverer"), (r"\bren\b", "wren")]
# User decision (2026-11-14): any transcription of "Silverer" (Silvera, Sylvari, Silverweir, silver...) is a PASS; the
# name sounds right. Re-take only when another word is wrong. Jory calls Wren "Ren".


ALIASES += [(r"\bway[- ]house\b", "weigh house"), (r"\bselvage\b", "selvedge")]  # homophones / spelling variants
VOCALISATIONS = {"mm", "mmm", "hm", "hmm", "hmph", "hrm", "shh", "sh", "er", "erm", "um", "uh", "eh", "ah", "oh", "oy", "oi",
                 "oof", "oho", "hah", "ha", "tch", "whoa", "ooh", "aha"}  # interjections the transcriber often drops


def norm_words(s):
    s = s.lower().replace("’", "'").replace("‘", "'")
    for pat, rep in ALIASES:
        s = re.sub(pat, rep, s)
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return [w for w in (t.strip("'") for t in s.split()) if w and w not in VOCALISATIONS]


def passes(text, heard, word_accept=0.999, letters_accept=0.93):
    """Acceptance for baked lines: every word right, OR the same letters once spacing, apostrophes and interjections are
    ignored (contractions, compounds, dropped g's: 'What're'/'What are', 'Frost gate'/'Frostgate')."""
    import difflib
    if word_match(text, heard) >= word_accept:
        return True
    a, b = "".join(norm_words(text)).replace("'", ""), "".join(norm_words(heard)).replace("'", "")
    return bool(a) and difflib.SequenceMatcher(None, a, b).ratio() >= letters_accept


def word_match(a, b):
    import difflib
    return difflib.SequenceMatcher(None, norm_words(a), norm_words(b)).ratio()


VOCAB = "Lanthorne, Pewterside, Giltside, Frostside, the Tarnish, tarnished, Silverer, mirror shard, step through."


def stt(key, path, model="gpt-4o-transcribe", prompt=None):
    """Speech-to-text of a WAV, used to verify what was actually spoken (the realtime self-transcript can't be trusted).
    prompt: vocabulary hint; defaults to the module-level VOCAB at call time (scripts may extend it with names)."""
    prompt = VOCAB if prompt is None else prompt
    import uuid
    b = uuid.uuid4().hex
    parts = [f"--{b}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{model}\r\n".encode(),
             f"--{b}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\nen\r\n".encode(),
             *([f"--{b}\r\nContent-Disposition: form-data; name=\"prompt\"\r\n\r\n{prompt}\r\n".encode()] if prompt else []),
             f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"take.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode(),
             open(path, "rb").read(), f"\r\n--{b}--\r\n".encode()]
    req = urllib.request.Request("https://api.openai.com/v1/audio/transcriptions", data=b"".join(parts), method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8")).get("text", "")


def session_payloads(voice, instructions):
    ga = {"type": "session.update", "session": {"type": "realtime", "instructions": instructions, "output_modalities": ["audio"],
                                                  "audio": {"output": {"voice": voice, "format": {"type": "audio/pcm", "rate": 24000}}}}}
    beta = {"type": "session.update", "session": {"instructions": instructions, "modalities": ["audio", "text"], "voice": voice,
                                                    "output_audio_format": "pcm16"}}
    return [ga, beta]


def take(key, model, voice, instructions, text):
    """One realtime take. Returns (pcm_bytes, transcript)."""
    url = f"wss://api.openai.com/v1/realtime?model={model}"
    last_err = None
    for payload in session_payloads(voice, instructions):
        headers = {"Authorization": "Bearer " + key}
        if "type" not in payload["session"]:
            headers["OpenAI-Beta"] = "realtime=v1"
        with connect(url, additional_headers=headers, max_size=None, open_timeout=30) as ws:
            ws.send(json.dumps(payload))
            ws.send(json.dumps({"type": "conversation.item.create", "item": {"type": "message", "role": "user",
                                "content": [{"type": "input_text", "text": "Line: " + text}]}}))
            ws.send(json.dumps({"type": "response.create"}))
            pcm, transcript, err = bytearray(), [], None
            deadline = time.time() + 60
            while time.time() < deadline:
                ev = json.loads(ws.recv(timeout=60))
                t = ev.get("type", "")
                if t in ("response.output_audio.delta", "response.audio.delta"):
                    pcm += base64.b64decode(ev["delta"])
                elif t in ("response.output_audio_transcript.delta", "response.audio_transcript.delta"):
                    transcript.append(ev.get("delta", ""))
                elif t == "error":
                    err = ev.get("error", {}).get("message", "error")
                    if not pcm:
                        break
                elif t == "response.done":
                    break
            if err and not pcm:
                last_err = err
                continue  # try the other session schema
            return bytes(pcm), "".join(transcript)
    raise RuntimeError(last_err or "no audio")


def write_wav(path, pcm, rate=24000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def main(argv):
    key = T.load_key()
    if not key:
        print("No OpenAI key found (OPENAI_API_KEY or ~/.openai/api_key). Nothing generated.")
        return 2
    try:
        models = list_models(key)
    except Exception as e:
        print("model list failed:", T.scrub(e, key))
        return 1
    model = pick_model(models)
    if "--models" in argv:
        print("realtime models:", [m[0] for m in models])
        print("would use:", model)
        return 0
    if not model:
        print("no gpt-realtime model available to this key")
        return 1
    force = "--force" in argv
    ids = [a for a in argv if not a.startswith("--")]
    V.check()
    todo = [l for l in V.LINES if (not ids or l[0] in ids) and (force or not os.path.exists(os.path.join(RAW, l[0] + ".wav")))]
    os.makedirs(RAW, exist_ok=True)
    mp = os.path.join(WORK, "manifest.json")
    manifest = json.load(open(mp)) if os.path.exists(mp) else {}
    print("model:", model, "lines:", len(todo))
    for lid, grp, spk, text in todo:
        voice = V.RT_VOICE[spk]
        brief = V.SPEAKERS[spk][1]
        instructions = f"{V.ACTOR_RULES}\n\nCharacter and delivery: {brief}\n\n{V.PRONOUNCE}"
        spoken = V.spoken(lid, text)
        tmp = os.path.join(RAW, lid + ".take.wav")
        best = None  # (score, wav_bytes_path_content, engine, voice, heard, tries)
        tries = 0
        for attempt in range(2):
            tries += 1
            try:
                pcm, tr = take(key, model, voice, instructions, spoken)
                write_wav(tmp, pcm)
                heard = stt(key, tmp)
            except Exception as e:
                print("fail", lid, T.scrub(type(e).__name__ + ": " + str(e), key)[:300])
                time.sleep(2)
                continue
            score = word_match(text, heard)
            if best is None or score > best[0]:
                best = (score, open(tmp, "rb").read(), model, voice, heard, tries)
            if score >= ACCEPT:
                break
            print(f"retry {lid} stt={score:.2f} | {heard[:100]}")
        if best is None or best[0] < ACCEPT:  # fall back to plain TTS; keep whichever take STT hears best
            tts_voice = V.SPEAKERS[spk][0]
            try:
                data = T.speak(key, tts_voice, spoken, brief + " " + V.PRONOUNCE)
                open(tmp, "wb").write(data)
                heard = stt(key, tmp)
                score = word_match(text, heard)
                tries += 1
                if best is None or score > best[0]:
                    best = (score, data, V.MODEL, tts_voice, heard, tries)
            except Exception as e:
                print("tts fallback failed", lid, T.scrub(e, key)[:300])
        if os.path.exists(tmp):
            os.remove(tmp)
        if best is None:
            print("FAILED", lid)
            continue
        score, data, engine, used_voice, heard, _ = best
        open(os.path.join(RAW, lid + ".wav"), "wb").write(data)
        manifest[lid] = {"engine": engine, "voice": used_voice, "speaker": spk, "text": text, "spoken_input": spoken,
                         "instructions": instructions, "stt_heard": heard, "stt_match": round(score, 3), "tries": tries,
                         "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        json.dump(manifest, open(mp, "w"), indent=1)
        print(f"ok   {lid} {engine} {used_voice} stt={score:.2f} tries={tries} | {heard[:80]}".encode("ascii", "replace").decode())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
