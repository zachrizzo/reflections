"""The Gemini calls of the shipped dialogue pipeline. One key: a Gemini API key from the Google Cloud project that
holds the audio session's designed voices.

- GeminiHearing: the player's speech streams to gemini-3.5-transcribe-live (Live API) while they hold the talk key;
  push-to-talk marks the start and end. Final text measured 0.24 s after release.
- GeminiComposer: one generateContent call per player line: the NPC's reply, whether a saved reply of the same NPC
  fits instead, an optional whitelisted action and an intent label (strict JSON schema).
- GeminiModerator: an independent check of the reply text, run while it is synthesized; the audio is held until it
  clears.
Both text calls use strict safety settings (BLOCK_LOW_AND_ABOVE by default); a blocked request or reply is never
spoken. Keys travel only in the x-goog-api-key header, never in a URL; error text is never logged.
"""
import asyncio
import base64
import json

import httpx
from websockets.asyncio.client import connect

from composing import COMPOSER_RULES, ComposedTurn, compose_payload, compose_schema, parse_turn
from costs import gemini_cost

API = "https://generativelanguage.googleapis.com/v1beta"
LIVE_URL = ("wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent")
HARM_CATEGORIES = ("HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                   "HARM_CATEGORY_DANGEROUS_CONTENT")
THRESHOLDS = ("BLOCK_LOW_AND_ABOVE", "BLOCK_MEDIUM_AND_ABOVE", "BLOCK_ONLY_HIGH")
BLOCK_FINISH = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION", "IMAGE_SAFETY"}
# Words of the world the recogniser would otherwise mishear ("Guild Tower" for Gilt Tower, measured).
VOCABULARY = ("Lanthorne", "Lanthorne Glass", "Pewterside", "Giltside", "Frostside", "Gilt Tower", "Frost Tower",
              "Old Weigh-House", "Tarnish", "tarnished", "Silverer", "Silverers", "Wren", "Wren Hale",
              "mirror page", "mirror shard", "shards", "Lantern Law", "drifter", "drifters", "Final Spell")


def safety_settings(threshold):
    threshold = threshold if threshold in THRESHOLDS else "BLOCK_LOW_AND_ABOVE"
    return [{"category": c, "threshold": threshold} for c in HARM_CATEGORIES]


def blocked_reason(data):
    """Why the safety filter stopped this response, or None."""
    feedback = data.get("promptFeedback") if isinstance(data.get("promptFeedback"), dict) else {}
    if feedback.get("blockReason"):
        return "request " + str(feedback["blockReason"])[:40]
    candidates = data.get("candidates") or []
    reason = candidates[0].get("finishReason") if candidates and isinstance(candidates[0], dict) else None
    return "reply " + reason if reason in BLOCK_FINISH else None


def response_text(data):
    candidates = data.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought"))


class GeminiText:
    """Shared generateContent plumbing. Returns (data, error); error is a short key-free code."""

    def __init__(self, api_key, model, timeout, client=None, threshold="BLOCK_LOW_AND_ABOVE", thinking=None):
        self.api_key, self.model, self.timeout = api_key, model, timeout
        self.threshold, self.thinking = threshold, thinking
        self.client = client or httpx.AsyncClient(timeout=timeout, trust_env=False)

    def body(self, system, user, schema, max_tokens):
        config = {"responseMimeType": "application/json", "responseJsonSchema": schema, "maxOutputTokens": max_tokens}
        if self.thinking:
            config["thinkingConfig"] = {"thinkingLevel": self.thinking}
        return {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": config, "safetySettings": safety_settings(self.threshold)}

    async def call(self, body):
        try:
            response = await self.client.post(f"{API}/models/{self.model}:generateContent", json=body,
                                              headers={"x-goog-api-key": self.api_key}, timeout=self.timeout)
            if response.status_code != 200:
                return None, f"http {response.status_code}"
            data = response.json()
            return (data, None) if isinstance(data, dict) else (None, "bad body")
        except (httpx.HTTPError, ValueError) as exc:
            return None, type(exc).__name__

    def cost(self, data):
        return gemini_cost(self.model, (data or {}).get("usageMetadata"))

    async def aclose(self):
        await self.client.aclose()


class GeminiComposer(GeminiText):
    """The NPC's reply, the per-NPC reuse decision and the action pick in one call.

    Default gemini-3.5-flash-lite: measured 1.05-1.4 s per call on this request, against 1.8-3.3 s for gemini-3.8-flash
    (REFLECTIONS_COMPOSER_MODEL switches it; both deflected the guardrail lines in character).
    """

    def __init__(self, api_key, model="gemini-3.5-flash-lite", timeout=8.0, client=None,
                 threshold="BLOCK_LOW_AND_ABOVE", thinking=None):
        super().__init__(api_key, model, timeout, client, threshold, thinking)

    async def compose(self, persona, history, line, candidates, offers, action_text, avoid=(), milder=False):
        body = self.body(persona.instructions() + "\n\n" + COMPOSER_RULES,
                         compose_payload(history, line, candidates, action_text, avoid, milder),
                         compose_schema([c.id for c in candidates], offers), 300)
        data, error = await self.call(body)
        if error:
            return ComposedTurn(error=error)
        usage = data.get("usageMetadata") or {}
        blocked = blocked_reason(data)
        if blocked:
            return ComposedTurn(blocked=blocked, usage=usage)
        try:
            return parse_turn(response_text(data), candidates, usage)
        except (ValueError, TypeError):
            finish = ((data.get("candidates") or [{}])[0] or {}).get("finishReason")
            return ComposedTurn(error=f"unreadable reply ({str(finish)[:20]})", usage=usage)


MODERATION_RULES = (
    "You check one line that a character in a fantasy video game is about to say aloud to the player. The game is "
    "rated M: in-world threats, fantasy danger and violence mentioned without gore, and mild language are fine. "
    "Block the line if it contains any of: a slur, or hate or harassment aimed at a real-world group; sexual content; "
    "graphic or gory description; real-world politics, elections, religion or current events; real people; "
    "instructions for real-world harm or weapons; encouragement of self-harm. Otherwise allow it."
)
MODERATION_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["allow", "reason"],
                     "properties": {"allow": {"type": "boolean"},
                                    "reason": {"type": "string", "enum": ["ok", "hate", "sexual", "gore",
                                                                          "real_world", "harm", "self_harm",
                                                                          "other"]}}}


class GeminiModerator(GeminiText):
    """moderate(text) -> True (flagged: never play), False (clean), None (unreachable: the caller decides)."""

    def __init__(self, api_key, model="gemini-3.5-flash-lite", timeout=4.0, client=None,
                 threshold="BLOCK_LOW_AND_ABOVE"):
        super().__init__(api_key, model, timeout, client, threshold)

    async def moderate(self, text, on_cost=None):
        if not text:
            return False
        data, error = await self.call(self.body(MODERATION_RULES, json.dumps({"line": text[:600]}),
                                                MODERATION_SCHEMA, 40))
        if on_cost and data:
            on_cost(self.cost(data))
        if error:
            return None
        if blocked_reason(data):
            return True
        try:
            verdict = json.loads(response_text(data) or "{}")
        except ValueError:
            return None
        if not isinstance(verdict, dict) or not isinstance(verdict.get("allow"), bool):
            return None
        return not verdict["allow"]


class HearingTurn:
    """One push-to-talk utterance streamed to the Live transcription model.

    feed() may be called before the socket is up (audio is held and sent once it is). finish() marks the end of
    speech and returns the transcript: "" if nothing was heard, None if hearing failed.
    """

    def __init__(self, hearing, vocabulary):
        loop = asyncio.get_running_loop()
        self.hearing, self.vocabulary = hearing, vocabulary
        self.pending, self.ws = [], None
        self.connected, self.result = loop.create_future(), loop.create_future()
        self.finals, self.interim = [], ""
        self.ended, self.error, self.audio_bytes = False, None, 0
        self.task = asyncio.create_task(self._run())

    def _text(self):
        return " ".join(self.finals).strip() if self.finals else self.interim.strip()

    def _resolve(self, value):
        if not self.result.done():
            self.result.set_result(value)

    async def _send_audio(self, ws, pcm):
        await ws.send(json.dumps({"realtimeInput": {"audio": {
            "data": base64.b64encode(pcm).decode("ascii"), "mimeType": f"audio/pcm;rate={self.hearing.rate}"}}}))

    def _on_event(self, event):
        content = event.get("serverContent") if isinstance(event.get("serverContent"), dict) else {}
        interim = content.get("interimInputTranscription")
        if isinstance(interim, dict) and isinstance(interim.get("text"), str):
            self.interim = interim["text"]
        final = content.get("inputTranscription")
        if isinstance(final, dict) and isinstance(final.get("text"), str) and final["text"].strip():
            self.finals.append(final["text"].strip())
        activity = (content.get("voiceActivity") or event.get("voiceActivity") or {})
        complete = (content.get("generationComplete") or content.get("turnComplete")
                    or (isinstance(activity, dict) and activity.get("type") == "ACTIVITY_END"))
        if self.ended and complete:
            self._resolve(self._text())

    async def _run(self):
        hearing = self.hearing
        try:
            async with hearing.connector(LIVE_URL, additional_headers={"x-goog-api-key": hearing.api_key},
                                         max_size=1_000_000, proxy=None, open_timeout=8) as ws:
                await ws.send(json.dumps(hearing.setup_message(self.vocabulary)))
                async with asyncio.timeout(8):
                    first = json.loads(await ws.recv())
                if not isinstance(first, dict) or "setupComplete" not in first:
                    raise ValueError("setup")
                await ws.send(json.dumps({"realtimeInput": {"activityStart": {}}}))
                while self.pending:
                    await self._send_audio(ws, self.pending.pop(0))
                self.ws = ws  # set only once nothing is pending, so audio never goes out of order
                if not self.connected.done():
                    self.connected.set_result(True)
                async for raw in ws:
                    event = json.loads(raw)
                    if isinstance(event, dict):
                        self._on_event(event)
                    if self.result.done():
                        break
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never keep exception text: it can carry request details
            self.error = type(exc).__name__
        finally:
            self.ws = None
            if not self.connected.done():
                self.connected.set_result(False)
            # The socket ended: what was heard counts if speech had ended; otherwise hearing failed.
            self._resolve(self._text() if self.ended and self.error is None else None)

    async def feed(self, pcm):
        if self.ended or self.result.done():
            return
        self.audio_bytes += len(pcm)
        ws = self.ws
        if ws is None:
            self.pending.append(pcm)
            return
        try:
            await self._send_audio(ws, pcm)
        except Exception:
            self.error = self.error or "send"

    async def finish(self, timeout=4.0):
        self.ended = True
        try:
            async with asyncio.timeout(timeout):
                if await asyncio.shield(self.connected) and self.ws is not None:
                    await self.ws.send(json.dumps({"realtimeInput": {"activityEnd": {}}}))
                return await asyncio.shield(self.result)
        except TimeoutError:
            return self._text() or None
        except Exception:
            return self._text() or None
        finally:
            self.cancel()

    def cancel(self):
        if not self.task.done():
            self.task.cancel()


class GeminiHearing:
    """Starts one HearingTurn per utterance (sessions are capped at 10 minutes, so none is kept open)."""

    def __init__(self, api_key, model="gemini-3.5-transcribe-live", language="en-US", vocabulary=VOCABULARY,
                 connector=connect, rate=24000):
        self.api_key, self.model, self.language = api_key, model, language
        self.vocabulary, self.connector, self.rate = tuple(vocabulary), connector, rate

    def setup_message(self, vocabulary):
        transcription = {"languageCodes": [self.language] if self.language else []}
        if vocabulary:
            transcription["customVocabulary"] = list(vocabulary)[:100]
        return {"setup": {"model": "models/" + self.model, "generationConfig": {"responseModalities": ["TEXT"]},
                          "inputAudioTranscription": transcription,
                          "realtimeInputConfig": {"automaticActivityDetection": {"disabled": True}}}}

    def start(self, extra_vocabulary=()):
        words = list(self.vocabulary) + [w for w in extra_vocabulary if w and w not in self.vocabulary]
        return HearingTurn(self, words)
