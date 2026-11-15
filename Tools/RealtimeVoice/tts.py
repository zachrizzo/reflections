"""Text-to-speech for the pipeline relay: the NPC's reply text becomes audio in that NPC's own voice.

GeminiTts speaks with the NPC's designed Gemini voice from the audio session's roster (the same voice as its
baked lines), or a stock Gemini voice (by voice slot) for an NPC without one. It yields 24 kHz mono 16-bit PCM
chunks. Keys stay in this process; error text is never logged.
"""
import base64
import io
import json
import os
import wave

import httpx

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class TtsError(Exception):
    """Synthesis failed; .code is a short, key-free reason (http status or exception name)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def pcm_from_wav(data):
    with wave.open(io.BytesIO(data), "rb") as source:
        if source.getsampwidth() != 2 or source.getnchannels() != 1:
            raise TtsError("unexpected wav format")
        pcm = source.readframes(source.getnframes())
        rate = source.getframerate()
    if rate != 24000:
        raise TtsError(f"unexpected rate {rate}")
    return pcm


class GeminiTts:
    """Gemini 3.8 Flash TTS through the Interactions API (the request the audio session uses for baked lines)."""
    name = "gemini"

    def __init__(self, api_key, model="gemini-3.8-flash-tts", client=None, timeout=30.0):
        self.api_key, self.model = api_key, model
        self.client = client or httpx.AsyncClient(timeout=timeout, trust_env=False)

    async def stream(self, text, voice, style=""):
        """Streams the reply (server-sent events): first audio about 1.4 s after the request, not after the whole line."""
        item = {"type": "text", "text": text}
        if style:
            item["annotations"] = [{"type": "speech_metadata", "style": style[:300]}]
        body = {"model": self.model, "input": [{"type": "user_input", "content": [item]}],
                "response_format": {"type": "audio"}, "generation_config": {"speech_config": [{"voice": voice}]},
                "stream": True}
        carry, got_audio = b"", False
        try:
            async with self.client.stream("POST", GEMINI_BASE + "/interactions", params={"alt": "sse"}, json=body,
                                          headers={"x-goog-api-key": self.api_key}) as response:
                if response.status_code != 200:
                    raise TtsError(f"http {response.status_code}")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:])
                    except ValueError:
                        continue
                    delta = event.get("delta") if event.get("event_type") == "step.delta" else None
                    if not isinstance(delta, dict) or delta.get("type") != "audio" or not delta.get("data"):
                        continue
                    if delta.get("sample_rate", 24000) != 24000 or delta.get("channels", 1) != 1:
                        raise TtsError("unexpected audio format")
                    chunk = carry + base64.b64decode(delta["data"])
                    cut = len(chunk) - (len(chunk) % 2)
                    carry = chunk[cut:]
                    if cut:
                        got_audio = True
                        yield chunk[:cut]
        except httpx.HTTPError as exc:
            raise TtsError(type(exc).__name__) from None
        if not got_audio:
            raise TtsError("no audio")


class Roster:
    """The audio session's voice roster: VoiceId -> designed Gemini voice, persona and delivery style.

    Expected JSON: {"voices": {"V017": {"gemini_voice": "voice_...", "sex": "Male", "persona": "...", "style": "..."}}}
    (a list of objects with a "VoiceId" field is accepted too). Missing file: an empty roster.
    """

    def __init__(self, path=None):
        self.voices = {}
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            items = data.get("voices", data) if isinstance(data, dict) else data
            if isinstance(items, dict):
                items = [dict(v, VoiceId=k) for k, v in items.items()]
            for entry in items if isinstance(items, list) else []:
                voice_id = str(entry.get("VoiceId") or entry.get("voice_id") or "")
                gemini = entry.get("gemini_voice") or entry.get("GeminiVoice") or entry.get("voice")
                if voice_id and isinstance(gemini, str) and gemini:
                    self.voices[voice_id] = {"gemini_voice": gemini, "sex": entry.get("sex") or entry.get("Sex"),
                                             "persona": entry.get("persona") or entry.get("Persona") or "",
                                             "style": entry.get("style") or entry.get("Style") or ""}

    def get(self, voice_id):
        return self.voices.get(voice_id) if voice_id else None

    def __len__(self):
        return len(self.voices)
