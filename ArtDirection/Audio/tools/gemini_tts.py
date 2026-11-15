"""Gemini TTS helper (Interactions API + Voices API).

KEY HANDLING: read from GEMINI_API_KEY or the one-line file ~/.gemini/api_key (outside the project); sent only in the
x-goog-api-key HTTPS header; never printed, logged, written to disk or passed on a command line; errors are scrubbed.
"""
import os, re, json, base64, urllib.request, urllib.error, urllib.parse

BASE = "https://generativelanguage.googleapis.com/v1beta"
KEY_FILE = os.path.join(os.path.expanduser("~"), ".gemini", "api_key")


def load_key():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k and os.path.isfile(KEY_FILE):
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            k = f.readline().strip()
    return k or None


def scrub(text, key):
    text = str(text)
    if key:
        text = text.replace(key, "[REDACTED]")
    return re.sub(r"AIza[0-9A-Za-z_\-]{10,}", "AIza[REDACTED]", text)


def _req(key, method, path, body=None, timeout=180):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: " + scrub(e.read().decode("utf-8", "replace")[:600], key)) from None


def list_voices(key, **params):
    out, token = [], None
    while True:
        q = dict(params)
        q["pageSize"] = 200
        if token:
            q["pageToken"] = token
        r = _req(key, "GET", "/voices?" + urllib.parse.urlencode(q, doseq=True))
        out += r.get("voices", [])
        token = r.get("nextPageToken")
        if not token:
            return out


def design_voice(key, display_name, description, gender=None, language_code="en-GB", model="gemini-3.8-flash-tts"):
    v = {"model": model, "type": "prompted", "display_name": display_name, "language_code": language_code,
         "prompted": {"input": description}}
    if gender:
        v["gender"] = gender
    r = _req(key, "POST", "/voices", {"store": True, "voice": v})
    wav = base64.b64decode(r["sample_audio"]["data"]) if r.get("sample_audio") else None
    return r, wav


def _audio_from_interaction(r):
    datas = []
    for step in r.get("steps", []):
        if step.get("type") == "model_output":
            for c in step.get("content", []):
                if c.get("type") == "audio" and c.get("data"):
                    datas.append(c["data"])
    if not datas:
        raise RuntimeError("no audio in response: " + json.dumps(r)[:300])
    return base64.b64decode(datas[-1])


def speak(key, text, voice, style="", model="gemini-3.8-flash-tts"):
    item = {"type": "text", "text": text}
    if style:
        item["annotations"] = [{"type": "speech_metadata", "style": style}]
    body = {"model": model, "input": [{"type": "user_input", "content": [item]}], "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": voice}]}}
    return _audio_from_interaction(_req(key, "POST", "/interactions", body))


def dialogue(key, turns, speakers, model="gemini-3.8-flash-tts"):
    """turns: [(speaker, text, style)], speakers: {speaker: prebuilt voice} (max 2)."""
    content = []
    for spk, text, style in turns:
        meta = {"type": "speech_metadata", "speaker": spk}
        if style:
            meta["style"] = style
        content.append({"type": "text", "text": text, "annotations": [meta]})
    body = {"model": model, "input": [{"type": "user_input", "content": content}], "response_format": {"type": "audio"},
            "generation_config": {"speech_config": {"speakers": [{"speaker": s, "voice": v} for s, v in speakers.items()]}}}
    return _audio_from_interaction(_req(key, "POST", "/interactions", body))


def delete_voice(key, voice_id):
    """Delete one of OUR stored voices (voice_...). Never call this on voices this project's scripts didn't create."""
    if not voice_id.startswith("voice_"):
        raise ValueError("refusing to delete a non-custom voice")
    return _req(key, "DELETE", "/voices/" + voice_id)


STT_MODEL = "gemini-3.8-flash"


def transcribe(key, wav_path, vocab="", model=STT_MODEL):
    """Verbatim transcript of a WAV with Gemini audio understanding (used to check baked takes). The script is never
    sent, so the model can't 'hear' what it expects; only a vocabulary of names is given."""
    import base64
    b64 = base64.b64encode(open(wav_path, "rb").read()).decode()
    prompt = ("Transcribe the speech in this audio verbatim, in English. Write exactly the words that are spoken, "
              "including repeated words, cut-off words and interjections. Do not correct grammar, do not complete or "
              "tidy sentences, do not add or drop words, and do not describe non-speech sounds."
              + (f" Names and words that may occur: {vocab}" if vocab else "")
              + ' Return JSON: {"text": "..."}')
    body = {"contents": [{"role": "user", "parts": [{"text": prompt},
                                                     {"inline_data": {"mime_type": "audio/wav", "data": b64}}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.0}}
    r = _req(key, "POST", f"/models/{model}:generateContent", body, timeout=120)
    txt = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
    try:
        return str(json.loads(txt).get("text", ""))
    except Exception:
        return txt.strip()
