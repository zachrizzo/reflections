"""NPC dialogue relay: in-character spoken NPC replies, with a reply cache.

The game never holds a key. It talks to this relay over a WebSocket; the relay holds the key, builds the NPC's
persona from whitelisted game state, and for every player line either replays a saved reply of that same NPC that the
model judges a genuine fit, or generates a new one (and saves it). ReusePolicy keeps new generations well ahead of
reused ones.

Modes: "pipeline" (default, shipped; Gemini only, one Gemini key; see pipeline.py) and "realtime" (development only:
OpenAI gpt-realtime speech-to-speech, needs an OpenAI key).

Local development: `python relay.py` listens on 127.0.0.1:8765 and writes a random per-launch token to
Saved/NpcDialogue/relay.token, which editor builds read. Packaged builds start the same relay as a helper exe
(NpcDialogueRelay.exe) with keys.json next to it. The hosted variant is hosted_relay.py.

Client -> relay events: session.start {token, npc, client_id?}, input_audio_buffer.append {audio},
turn.end, turn.clear, text.turn {text}, response.cancel {played_ms?}, context.update {npc}, ping.
Relay -> client events: session.ready {voice, speaker, offline}, transcript.player {text},
reply.start {source, reply_id?}, response.output_audio.delta {delta}, reply.text.delta {delta},
reply.text {text}, response.done {status, source}, reply.unavailable {reason}, relay.error {message}, pong.
"""
import argparse
import asyncio
import base64
import binascii
import hmac
import http
import json
import logging
import os
import secrets
import sys
import time
from collections import deque
from dataclasses import dataclass

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from composing import Decision
from costs import SpendMeter, realtime_cost, text_cost, transcription_cost
from decider import Decider
from persona import normalize
from reply_cache import ReplyCache, ReusePolicy, similarity, tokens

log = logging.getLogger("npc-dialogue")

PORT = 8765
PROTOCOL = 2
MAX_CHUNK_BYTES = 32_000
MAX_TEXT_CHARS = 300
REPLAY_CHUNK_BYTES = 9_600  # 200 ms of 24 kHz PCM16
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_DATA_DIR = os.path.join(REPO_ROOT, "Saved", "NpcDialogue")


@dataclass
class RelayConfig:
    mode: str = "pipeline"              # pipeline (Gemini, shipped): hear -> reply -> TTS in the NPC's own voice
    composer_model: str = "gemini-3.5-flash-lite"
    hearing_model: str = "gemini-3.5-transcribe-live"
    moderation_model: str = "gemini-3.5-flash-lite"
    gemini_tts_model: str = "gemini-3.8-flash-tts"
    safety_threshold: str = "BLOCK_LOW_AND_ABOVE"  # Gemini safety settings for every text call
    hearing_language: str = "en-US"
    # realtime mode (development only, OpenAI):
    model: str = "gpt-realtime-2.1"
    transcribe_model: str = "gpt-live-transcribe"
    decision_model: str = "gpt-6-luna"
    max_output_tokens: int = 600
    reasoning_effort: str = ""          # empty: the model's default
    turn_seconds: int = 20              # longest single utterance
    session_seconds: int = 3600         # Realtime sessions end at 60 minutes
    idle_seconds: int = 600
    transcript_wait: float = 4.0
    min_similarity_to_ask: float = 0.15  # below this (and for lines over 3 words) the decider is not asked
    max_sessions: int = 4              # local: one player, but switching NPCs briefly overlaps sessions
    log_text: bool = True               # print player and NPC lines in the relay log (off in the packaged helper)
    turn_deadline: float = 12.0         # pipeline: a turn not finished by then gives up (the game barks at 15 s)
    soft_budget_reuse_cap: float = 0.6  # reuse cap while spend is past the soft budget line
    soft_budget_min_confidence: float = 0.6

    @classmethod
    def from_env(cls, **overrides):
        env = os.environ.get
        cfg = cls(
            mode=env("REFLECTIONS_NPC_MODE", cls.mode),
            composer_model=env("REFLECTIONS_COMPOSER_MODEL", cls.composer_model),
            hearing_model=env("REFLECTIONS_HEARING_MODEL", cls.hearing_model),
            moderation_model=env("REFLECTIONS_MODERATION_MODEL", cls.moderation_model),
            gemini_tts_model=env("REFLECTIONS_GEMINI_TTS_MODEL", cls.gemini_tts_model),
            safety_threshold=env("REFLECTIONS_SAFETY_THRESHOLD", cls.safety_threshold),
            hearing_language=env("REFLECTIONS_HEARING_LANGUAGE", cls.hearing_language),
            model=env("REFLECTIONS_VOICE_MODEL", cls.model),
            transcribe_model=env("REFLECTIONS_TRANSCRIBE_MODEL", cls.transcribe_model),
            decision_model=env("REFLECTIONS_DECISION_MODEL", cls.decision_model),
            max_output_tokens=int(env("REFLECTIONS_MAX_OUTPUT_TOKENS", cls.max_output_tokens)),
            reasoning_effort=env("REFLECTIONS_REASONING_EFFORT", cls.reasoning_effort),
            turn_seconds=int(env("REFLECTIONS_VOICE_TURN_SECONDS", cls.turn_seconds)),
            session_seconds=int(env("REFLECTIONS_VOICE_SESSION_SECONDS", cls.session_seconds)),
            log_text=env("REFLECTIONS_NPC_LOG_TEXT", "0" if getattr(sys, "frozen", False) else "1") == "1",
        )
        for name, value in overrides.items():
            setattr(cfg, name, value)
        if cfg.mode not in ("pipeline", "realtime"):
            raise ValueError("REFLECTIONS_NPC_MODE must be pipeline or realtime.")
        if cfg.safety_threshold not in ("BLOCK_LOW_AND_ABOVE", "BLOCK_MEDIUM_AND_ABOVE", "BLOCK_ONLY_HIGH"):
            raise ValueError("REFLECTIONS_SAFETY_THRESHOLD must be BLOCK_LOW_AND_ABOVE, BLOCK_MEDIUM_AND_ABOVE "
                             "or BLOCK_ONLY_HIGH.")
        if not 1 <= cfg.turn_seconds <= 120 or not 1 <= cfg.session_seconds <= 3600:
            raise ValueError("Turn length must be 1-120 s and session length 1-3600 s.")
        return cfg


def policy_from_env(path):
    env = os.environ.get
    return ReusePolicy(path, cap=float(env("REFLECTIONS_NPC_MAX_REUSE", "0.35")),
                       target=float(env("REFLECTIONS_NPC_TARGET_REUSE", "0.25")),
                       window=int(env("REFLECTIONS_NPC_REUSE_WINDOW", "20")))


class LocalAuth:
    """Loopback relay: the client must present the per-launch token. Also caps turns, in case a key is misused."""

    def __init__(self, token, turns_per_minute=12, turns_per_day=600):
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("The local token must be at least 32 characters.")
        self.token = token
        self.turns_per_minute, self.turns_per_day = turns_per_minute, turns_per_day
        self.recent_turns = deque()
        self.day, self.day_turns = None, 0

    def check(self, first, connection):
        supplied = first.get("token", "")
        if isinstance(supplied, str) and hmac.compare_digest(supplied, self.token):
            return "local"
        return None

    def session_started(self, client_id, connection):
        return None

    def session_ended(self, client_id, connection):
        pass

    def before_turn(self, client_id, connection):
        now = time.time()
        today = time.strftime("%Y-%m-%d", time.gmtime(now))
        if today != self.day:
            self.day, self.day_turns = today, 0
        while self.recent_turns and now - self.recent_turns[0] > 60:
            self.recent_turns.popleft()
        if len(self.recent_turns) >= self.turns_per_minute or self.day_turns >= self.turns_per_day:
            return "rate"
        self.recent_turns.append(now)
        self.day_turns += 1
        return None

    def spent(self, client_id, usd):
        pass


def _clean_text(value):
    if not isinstance(value, str):
        return ""
    text = "".join(ch for ch in value if ch.isprintable()).strip()
    return text[:MAX_TEXT_CHARS]


class DialogueSession:
    def __init__(self, relay, client, persona, client_id, offline):
        self.relay, self.client, self.persona, self.client_id = relay, client, persona, client_id
        self.offline = offline
        self.cfg = relay.config
        self.upstream = None
        self.turn_task = None
        self.audio_bytes = 0
        self.max_turn_bytes = 24_000 * 2 * self.cfg.turn_seconds
        self.recent = deque(maxlen=8)
        self.commit_future = None
        self.transcripts = {}
        self.response = None
        self.response_idle = asyncio.Event()
        self.response_idle.set()
        self.last_assistant = None
        self.replay_cancel = False
        self.background = set()
        self.last_activity = time.monotonic()
        self.instructions = persona.instructions()
        self.reply_started = False  # this turn already sent reply.start (or its end)
        self.turn_deadline = None   # pipeline sessions set one

    # ---- plumbing ------------------------------------------------------------------------------------

    async def send(self, event):
        if event.get("type") in ("reply.start", "reply.unavailable"):
            self.reply_started = True
        try:
            await self.client.send(json.dumps(event))
        except ConnectionClosed:
            pass

    async def up(self, event):
        if self.upstream is not None:
            await self.upstream.send(json.dumps(event))

    def spawn(self, coro):
        task = asyncio.create_task(coro)
        self.background.add(task)
        task.add_done_callback(self.background.discard)
        return task

    def transcript_future(self, item_id):
        if item_id not in self.transcripts:
            self.transcripts[item_id] = asyncio.get_running_loop().create_future()
        return self.transcripts[item_id]

    def session_config(self):
        return {"type": "realtime", "model": self.cfg.model, "output_modalities": ["audio"],
                "instructions": self.instructions,
                "audio": {"input": {"format": {"type": "audio/pcm", "rate": 24000}, "turn_detection": None,
                                    "noise_reduction": {"type": "near_field"},
                                    "transcription": {"model": self.cfg.transcribe_model, "language": "en"}},
                          "output": {"format": {"type": "audio/pcm", "rate": 24000},
                                     "voice": self.persona.voice}}}

    # ---- lifecycle -----------------------------------------------------------------------------------

    async def run(self):
        if self.offline:
            await self.send({"type": "session.ready", "protocol": PROTOCOL, "voice": self.persona.voice,
                             "speaker": self.persona.speaker, "offline": True})
            await self.client_loop()
            return
        uri = "wss://api.openai.com/v1/realtime?model=" + self.cfg.model
        async with self.relay.connector(uri, additional_headers={"Authorization": "Bearer " + self.relay.api_key},
                                        max_size=4_000_000, proxy=None, open_timeout=15) as upstream:
            self.upstream = upstream
            async with asyncio.timeout(15):
                event = json.loads(await upstream.recv())
                if event.get("type") != "session.created":
                    raise ValueError("Upstream session not established")
                await self.up({"type": "session.update", "session": self.session_config()})
                while True:
                    event = json.loads(await upstream.recv())
                    if event.get("type") == "session.updated":
                        break
                    if event.get("type") == "error":
                        log.warning("session rejected by OpenAI: %s", _error_code(event))
                        raise ValueError("Upstream session rejected")
            await self.send({"type": "session.ready", "protocol": PROTOCOL, "voice": self.persona.voice,
                             "speaker": self.persona.speaker, "offline": False})
            log.info("session %s: %s (%s, %s), voice %s", self.client_id, self.persona.speaker,
                     self.persona.group, self.persona.context_key(), self.persona.voice)
            tasks = [asyncio.create_task(self.client_loop()), asyncio.create_task(self.upstream_loop()),
                     asyncio.create_task(self.idle_watch())]
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                if self.turn_task:
                    self.turn_task.cancel()
                    await asyncio.gather(self.turn_task, return_exceptions=True)
                if self.background:
                    await asyncio.wait(self.background, timeout=10)

    async def idle_watch(self):
        while True:
            await asyncio.sleep(5)
            if time.monotonic() - self.last_activity > self.cfg.idle_seconds:
                return

    # ---- client events -------------------------------------------------------------------------------

    async def client_loop(self):
        async for raw in self.client:
            self.last_activity = time.monotonic()
            try:
                event = json.loads(raw)
                kind = event.get("type")
                if kind == "input_audio_buffer.append":
                    data = base64.b64decode(event.get("audio", ""), validate=True)
                    if not data or len(data) > MAX_CHUNK_BYTES or len(data) % 2:
                        raise ValueError("Invalid audio")
                    if self.turn_busy():
                        await self.interrupt(None)
                    if self.audio_bytes + len(data) > self.max_turn_bytes:
                        continue  # past the utterance limit: drop the rest
                    self.audio_bytes += len(data)
                    await self.on_audio(data)
                elif kind == "turn.end":
                    if self.audio_bytes:
                        await self.start_turn(self.voice_turn())
                elif kind == "turn.clear":
                    self.audio_bytes = 0
                    await self.clear_audio()
                elif kind == "text.turn":
                    text = _clean_text(event.get("text"))
                    if text:
                        await self.start_turn(self.text_turn(text))
                elif kind == "response.cancel":
                    played = event.get("played_ms")
                    await self.interrupt(played if isinstance(played, int) and played >= 0 else None)
                elif kind == "context.update":
                    if not await self.update_persona(event.get("npc")):
                        return
                elif kind == "ping":
                    await self.send({"type": "pong"})
                elif kind == "action.result":
                    self.on_action_result(event)
                else:
                    raise ValueError("Invalid event")
            except (ValueError, TypeError, AttributeError, binascii.Error):
                await self.client.close(code=1008, reason="Invalid dialogue event")
                return

    def on_action_result(self, event):
        pass  # realtime mode has no actions

    async def on_audio(self, data):
        if not self.offline:
            await self.up({"type": "input_audio_buffer.append", "audio": base64.b64encode(data).decode("ascii")})

    async def clear_audio(self):
        if not self.offline:
            await self.up({"type": "input_audio_buffer.clear"})

    def turn_busy(self):
        return self.turn_task is not None and not self.turn_task.done()

    async def start_turn(self, coro):
        if self.turn_busy():
            await self.interrupt(None)
            self.turn_task.cancel()
            await asyncio.gather(self.turn_task, return_exceptions=True)
        refusal = self.relay.auth.before_turn(self.client_id, self.client)
        if refusal:
            coro.close()
            self.audio_bytes = 0
            await self.clear_audio()
            await self.send({"type": "reply.unavailable", "reason": refusal})
            return
        self.turn_task = asyncio.create_task(self.guarded(coro))

    async def guarded(self, coro):
        self.reply_started = False
        try:
            async with asyncio.timeout(self.turn_deadline):
                await coro
        except TimeoutError:
            # Too slow to be worth hearing now: stop, and let the game bark at once instead of at its own timeout.
            log.warning("turn gave up after %.0f s", self.turn_deadline or 0)
            self.replay_cancel = True
            if self.reply_started:
                await self.send({"type": "response.done", "status": "incomplete", "source": "generated"})
            else:
                await self.send({"type": "reply.unavailable", "reason": "error"})
        except asyncio.CancelledError:
            raise
        except ConnectionClosed:
            pass
        except Exception as exc:  # never log exception text: it can carry user data
            log.warning("turn failed: %s", type(exc).__name__)
            await self.send({"type": "reply.unavailable", "reason": "error"})

    async def update_persona(self, npc):
        updated = normalize(npc, previous=self.persona)
        if updated.voice != self.persona.voice:
            # A different voice (the Tarnish itself taking the body) needs a new Realtime session.
            await self.send({"type": "session.restart", "reason": "persona"})
            await self.client.close(code=4000, reason="Persona changed")
            return False
        self.persona = updated
        instructions = updated.instructions()
        if instructions != self.instructions:
            self.instructions = instructions
            if not self.offline:
                await self.up({"type": "session.update",
                               "session": {"type": "realtime", "instructions": instructions}})
        return True

    async def interrupt(self, played_ms):
        """The player cut the NPC off: stop what is streaming and trim the model's memory to what was heard."""
        self.replay_cancel = True
        if self.response is not None and not self.response["cancelled"]:
            self.response["cancelled"] = True
            await self.up({"type": "response.cancel"})
        last = self.last_assistant
        if last and played_ms is not None and not self.offline and last.get("item_id"):
            await self.up({"type": "conversation.item.truncate", "item_id": last["item_id"], "content_index": 0,
                           "audio_end_ms": max(0, min(int(played_ms), last.get("audio_ms", 0)))})
            self.last_assistant = None

    # ---- turns ---------------------------------------------------------------------------------------

    async def voice_turn(self):
        pcm_bytes, self.audio_bytes = self.audio_bytes, 0
        if self.offline:
            await self.offline_reply(None)
            return
        self.relay.spend(self.client_id, transcription_cost(self.cfg.transcribe_model, pcm_bytes))
        self.commit_future = asyncio.get_running_loop().create_future()
        await self.up({"type": "input_audio_buffer.commit"})
        async with asyncio.timeout(5):
            item_id = await self.commit_future
        if item_id is None:
            await self.send({"type": "reply.unavailable", "reason": "unheard"})
            return
        await self.respond(self.transcript_future(item_id), typed=False)

    async def text_turn(self, text):
        await self.send({"type": "transcript.player", "text": text})
        if self.offline:
            await self.offline_reply(text)
            return
        await self.up({"type": "conversation.item.create", "item": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}})
        line = asyncio.get_running_loop().create_future()
        line.set_result(text)
        await self.respond(line, typed=True)

    async def respond(self, line_future, typed):
        relay = self.relay
        budget = relay.budget_state()
        cap = relay.policy.cap if budget == "ok" else max(relay.policy.cap, self.cfg.soft_budget_reuse_cap)
        if not relay.policy.allowed(cap):
            await self.generate(line_future, "reuse cap reached")
            return
        if not relay.cache.has_persona(self.persona):
            await self.generate(line_future, "nothing saved for this persona yet")
            return
        try:
            async with asyncio.timeout(self.cfg.transcript_wait):
                line = await asyncio.shield(line_future)
        except TimeoutError:
            await self.generate(line_future, "transcript was late")
            return
        if not line.strip():
            await self.generate(line_future, "empty transcript")
            return
        candidates = relay.cache.candidates(self.persona, line, exclude=self.recent)
        if not candidates:
            await self.generate(line_future, "no candidates")
            return
        if not worth_asking(line, candidates, self.cfg.min_similarity_to_ask):
            await self.generate(line_future, "nothing saved is close to this line")
            return
        decision = await relay.decider.choose(self.persona, line, candidates)
        relay.spend(self.client_id, text_cost(self.cfg.decision_model, decision.usage))
        threshold = relay.policy.min_confidence() if budget == "ok" else self.cfg.soft_budget_min_confidence
        if decision.choice and decision.confidence >= threshold:
            entry = relay.cache.get(decision.choice)
            if entry is not None:
                await self.replay(entry, line, decision)
                return
        why = decision.error or (f"decider chose {decision.choice} at {decision.confidence:.2f} < {threshold:.2f}"
                                 if decision.choice else "decider: nothing fits")
        await self.generate(line_future, why, intent=decision.intent)

    async def generate(self, line_future, reason, intent=None):
        async with asyncio.timeout(5):
            await self.response_idle.wait()
        loop = asyncio.get_running_loop()
        self.replay_cancel = False
        self.response = {"audio": bytearray(), "text": [], "final_text": None, "item_id": None,
                         "line_future": line_future, "intent": intent, "cancelled": False, "reason": reason,
                         "done": loop.create_future(), "started": time.monotonic(), "first_audio": None,
                         "persona": self.persona}
        self.response_idle.clear()
        done = self.response["done"]
        await self.send({"type": "reply.start", "source": "generated"})
        body = {"max_output_tokens": self.cfg.max_output_tokens}
        if self.cfg.reasoning_effort:
            body["reasoning"] = {"effort": self.cfg.reasoning_effort}
        await self.up({"type": "response.create", "response": body})
        await done

    async def replay(self, entry, line, decision):
        relay = self.relay
        pcm = relay.cache.load_pcm(entry)
        self.replay_cancel = False
        relay.policy.record("reuse")
        relay.cache.record_use(entry.id)
        self.recent.append(entry.id)
        await self.send({"type": "reply.start", "source": "cached", "reply_id": entry.id})
        await self.send({"type": "reply.text", "text": entry.reply_text})
        if not self.offline:
            # Keep the model's memory of the conversation in step with what the NPC said.
            await self.up({"type": "conversation.item.create", "item": {
                "type": "message", "role": "assistant",
                "content": [{"type": "output_text", "text": entry.reply_text}]}})
        for start in range(0, len(pcm), REPLAY_CHUNK_BYTES):
            if self.replay_cancel:
                break
            await self.send({"type": "response.output_audio.delta",
                             "delta": base64.b64encode(pcm[start:start + REPLAY_CHUNK_BYTES]).decode("ascii")})
            await asyncio.sleep(0)
        await self.send({"type": "response.done", "status": "cancelled" if self.replay_cancel else "completed",
                         "source": "cached"})
        relay.log_turn(self, "CACHE HIT", entry.id, line, entry.reply_text,
                       f"decider {decision.confidence:.2f}, intent {decision.intent}, used {entry.uses}x")

    async def offline_reply(self, line):
        entry = self.relay.cache.best_offline(self.persona, line, exclude=self.recent)
        if entry is None:
            await self.send({"type": "reply.unavailable", "reason": "budget"})
            self.relay.log_turn(self, "NO REPLY", "-", line or "(voice)", "", "over budget, nothing cached fits")
            return
        await self.replay(entry, line or "(voice, not transcribed)", Decision(entry.id, 1.0, entry.intent, "offline"))

    # ---- upstream events -----------------------------------------------------------------------------

    async def upstream_loop(self):
        async for raw in self.upstream:
            event = json.loads(raw)
            kind = event.get("type", "")
            r = self.response
            if kind == "input_audio_buffer.committed":
                if self.commit_future is not None and not self.commit_future.done():
                    self.commit_future.set_result(event.get("item_id"))
            elif kind == "conversation.item.input_audio_transcription.completed":
                text = _clean_text(event.get("transcript")) if isinstance(event.get("transcript"), str) else ""
                future = self.transcript_future(event.get("item_id"))
                if not future.done():
                    future.set_result(text)
                await self.send({"type": "transcript.player", "text": text})
            elif kind == "conversation.item.input_audio_transcription.failed":
                future = self.transcript_future(event.get("item_id"))
                if not future.done():
                    future.set_result("")
            elif kind == "response.output_audio.delta":
                if r is not None and not r["cancelled"]:
                    delta = event.get("delta", "")
                    try:
                        pcm = base64.b64decode(delta, validate=True)
                    except (binascii.Error, ValueError):
                        continue
                    if r["first_audio"] is None:
                        r["first_audio"] = time.monotonic()
                    r["item_id"] = event.get("item_id") or r["item_id"]
                    r["audio"].extend(pcm)
                    await self.send({"type": "response.output_audio.delta", "delta": delta})
            elif kind == "response.output_audio_transcript.delta":
                if r is not None and not r["cancelled"] and isinstance(event.get("delta"), str):
                    r["text"].append(event["delta"])
                    await self.send({"type": "reply.text.delta", "delta": event["delta"]})
            elif kind == "response.output_audio_transcript.done":
                if r is not None and isinstance(event.get("transcript"), str):
                    r["final_text"] = event["transcript"]
                    if not r["cancelled"]:
                        await self.send({"type": "reply.text", "text": event["transcript"]})
            elif kind == "response.done":
                await self.finish_response(event.get("response") or {})
            elif kind == "error":
                await self.upstream_error(event)

    async def finish_response(self, response):
        r, self.response = self.response, None
        self.response_idle.set()
        status = response.get("status", "unknown")
        cost = realtime_cost(self.cfg.model, response.get("usage"))
        self.relay.spend(self.client_id, cost)
        if r is None:
            return
        text = r["final_text"] if r["final_text"] is not None else "".join(r["text"])
        if r["item_id"]:
            self.last_assistant = {"item_id": r["item_id"], "audio_ms": int(len(r["audio"]) / 48)}
        await self.send({"type": "response.done", "status": "cancelled" if r["cancelled"] else status,
                         "source": "generated"})
        if r["audio"]:
            self.relay.policy.record("new")
        latency = f"first audio {r['first_audio'] - r['started']:.2f}s" if r["first_audio"] else "no audio"
        line = r["line_future"].result() if r["line_future"].done() else "(transcribing)"
        self.relay.log_turn(self, "GENERATED", "-", line, text, f"{r['reason']}; {latency}; {len(r['audio']) / 48000:.1f}s audio; ${cost:.4f}; status {status}")
        if status == "completed" and not r["cancelled"] and r["audio"] and text.strip():
            task = self.spawn(self.relay.save_reply(r["persona"], r["line_future"], text, bytes(r["audio"]),
                                                    r["intent"], self.client_id))
            # Never offer an NPC's own fresh line back to it in the same conversation.
            task.add_done_callback(lambda t: self.recent.append(t.result().id)
                                   if not t.cancelled() and t.exception() is None else None)
        if not r["done"].done():
            r["done"].set_result(status)

    async def upstream_error(self, event):
        code = _error_code(event)
        if code in ("response_cancel_not_active", "conversation_already_has_active_response"):
            return
        if code == "input_audio_buffer_commit_empty":
            # Too little speech (a tap on the talk key): nothing to answer, and no need to wait for a timeout.
            if self.commit_future is not None and not self.commit_future.done():
                self.commit_future.set_result(None)
            return
        log.warning("OpenAI error event: %s", code)
        r = self.response
        if r is not None and not r["audio"]:
            self.response = None
            self.response_idle.set()
            await self.send({"type": "reply.unavailable", "reason": "error"})
            if not r["done"].done():
                r["done"].set_result("failed")


def worth_asking(line, candidates, min_similarity):
    """Skip the decision model (about 1.5 s) when no saved line is remotely close. Very short lines
    ("hello", "who are you?") are asked about anyway: they are the most reusable and share few words."""
    if len(tokens(line)) <= 3:
        return True
    return max(similarity(line, c.player_line) for c in candidates) >= min_similarity


def _error_code(event):
    error = event.get("error") if isinstance(event.get("error"), dict) else {}
    return str(error.get("code") or error.get("type") or "unknown")[:80]


class VoiceRelay:
    """api_key: OpenAI, development-only realtime mode. gemini_key: everything in pipeline mode (the shipped path).
    The model clients can be injected (tests)."""

    def __init__(self, api_key, auth, config=None, cache=None, policy=None, decider=None, meter=None,
                 connector=connect, data_dir=DEFAULT_DATA_DIR, composer=None, gemini_tts=None,
                 roster=None, gemini_key="", hearing=None, moderator=None):
        if isinstance(auth, str):
            auth = LocalAuth(auth)
        self.api_key, self.auth = api_key, auth
        self.config = config or RelayConfig()
        cfg = self.config
        if cfg.mode == "pipeline" and not gemini_key and None in (composer, gemini_tts, hearing, moderator):
            raise ValueError("Set a Gemini API key (keys.json next to the helper, GEMINI_API_KEY or ~/.gemini/api_key).")
        if cfg.mode == "realtime" and not api_key:
            raise ValueError("Realtime mode (development only) needs an OpenAI API key.")
        os.makedirs(data_dir, exist_ok=True)
        self.cache = cache or ReplyCache(os.path.join(data_dir, "cache"))
        self.policy = policy or ReusePolicy(os.path.join(data_dir, "reuse_stats.json"))
        self.decider = decider or (Decider(api_key, model=cfg.decision_model) if api_key else None)
        self.meter = meter or SpendMeter(os.path.join(data_dir, "spend.json"))
        from tts import GeminiTts, Roster
        if cfg.mode == "pipeline":
            from gemini import GeminiComposer, GeminiHearing, GeminiModerator
            composer = composer or GeminiComposer(gemini_key, model=cfg.composer_model, threshold=cfg.safety_threshold)
            hearing = hearing or GeminiHearing(gemini_key, model=cfg.hearing_model, language=cfg.hearing_language)
            moderator = moderator or GeminiModerator(gemini_key, model=cfg.moderation_model,
                                                     threshold=cfg.safety_threshold)
            gemini_tts = gemini_tts or GeminiTts(gemini_key, model=cfg.gemini_tts_model)
        self.composer, self.hearing, self.moderator, self.gemini_tts = composer, hearing, moderator, gemini_tts
        self.roster = roster if roster is not None else Roster(None)
        self.connector = connector
        self.slots = asyncio.Semaphore(self.config.max_sessions)
        self.turns = 0

    def budget_state(self):
        return self.meter.state()

    def spend(self, client_id, usd):
        if usd > 0:
            self.meter.add(usd)
            self.auth.spent(client_id, usd)

    def log_turn(self, session, outcome, reply_id, line, reply, detail):
        self.turns += 1
        if self.config.log_text:
            log.info("[turn %d] %s %s | %s | player: %r | npc: %r | %s", self.turns, outcome, reply_id,
                     session.persona.key, (line or "")[:120], (reply or "")[:160], detail)
        else:
            log.info("[turn %d] %s %s | %s | %s", self.turns, outcome, reply_id, session.persona.key, detail)
        log.info("[ratio] %s | cache %d replies | spend %s", self.policy.summary(), len(self.cache),
                 self.meter.summary())

    async def save_reply(self, persona, line_future, text, pcm, intent, client_id, model=None, flagged=None):
        """Saves a fresh reply. Flagged (or never cleared by moderation): kept for the record but never reused."""
        try:
            async with asyncio.timeout(10):
                line = await asyncio.shield(line_future)
        except (TimeoutError, asyncio.CancelledError):
            line = ""
        if flagged is None:
            flagged = await self.decider.flagged(text + "\n" + line) if self.decider else True
        if intent is None and line and self.decider:
            decision = await self.decider.classify(persona, line)
            self.spend(client_id, text_cost(self.config.decision_model, decision.usage))
            intent = decision.intent
        entry = self.cache.add(persona, line, text, pcm, model or self.config.model, intent=intent or "other",
                               flagged=flagged)
        log.info("saved reply %s (%s, %d ms, intent %s%s)", entry.id, persona.key, entry.audio_ms, entry.intent,
                 ", flagged: not reusable" if flagged else "")
        return entry

    async def handle(self, client):
        client_id = None
        try:
            async with asyncio.timeout(5):
                first = json.loads(await client.recv())
            if not isinstance(first, dict) or first.get("type") != "session.start":
                await client.close(code=1008, reason="Authentication failed")
                return
            client_id = self.auth.check(first, client)
            if not client_id:
                await client.close(code=1008, reason="Authentication failed")
                return
            npc = first.get("npc", {})
            if not isinstance(npc, dict):
                await client.close(code=1008, reason="Invalid context")
                return
            refusal = self.auth.session_started(client_id, client)
            if refusal:
                await client.send(json.dumps({"type": "reply.unavailable", "reason": refusal}))
                await client.close(code=1013, reason="Try again later")
                client_id = None
                return
            try:
                # Switching NPCs overlaps an ending session with a new one: wait a moment for a slot.
                async with asyncio.timeout(3):
                    await self.slots.acquire()
            except TimeoutError:
                await client.close(code=1013, reason="Dialogue relay is busy")
                return
            try:
                offline = self.budget_state() == "hard"
                if self.config.mode == "pipeline":
                    from pipeline import PipelineSession
                    session = PipelineSession(self, client, normalize(npc), client_id, offline)
                else:
                    session = DialogueSession(self, client, normalize(npc), client_id, offline)
                async with asyncio.timeout(self.config.session_seconds):
                    await session.run()
            finally:
                self.slots.release()
        except (TimeoutError, ValueError, json.JSONDecodeError, ConnectionClosed):
            pass
        except Exception as exc:
            # Never log exception text: HTTP errors can contain credentials or user data.
            log.warning("session failed: %s", type(exc).__name__)
            try:
                await client.send(json.dumps({"type": "relay.error", "message": "Dialogue connection failed."}))
            except ConnectionClosed:
                pass
        finally:
            if client_id:
                self.auth.session_ended(client_id, client)
            await client.close()


# Browsers always send the page's own Origin, so a web page elsewhere can't reach the relay. Unreal's libwebsockets
# client sends "http://<host it connects to>", which for the loopback relay is one of these.
LOOPBACK_ORIGINS = [None, "http://127.0.0.1", "http://localhost", "http://[::1]"] + [
    f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in range(8765, 8776)]


def health(connection, request):
    if request.path == "/healthz":
        return connection.respond(http.HTTPStatus.OK, "ok\n")
    return None


def setup_logging(path=None):
    from logging.handlers import RotatingFileHandler
    handlers = [logging.StreamHandler(sys.stdout)]
    if path:
        handlers.append(RotatingFileHandler(path, maxBytes=2_000_000, backupCount=2, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=handlers, force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def serve_first_free(handler, host, port, fallbacks=0, **kwargs):
    """Listens on the first free port of port..port+fallbacks: (server, port). OSError if all are taken."""
    error = None
    for candidate in range(port, port + max(0, fallbacks) + 1):
        try:
            return await serve(handler, host, candidate, **kwargs), candidate
        except OSError as exc:
            error = exc
    raise error


async def list_models(gemini_key):
    """The Gemini models this key can use for hearing, replies and speech (names only)."""
    import httpx
    async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
        response = await client.get("https://generativelanguage.googleapis.com/v1beta/models",
                                    params={"pageSize": 200}, headers={"x-goog-api-key": gemini_key})
    if response.status_code != 200:
        print("Listing models failed: HTTP", response.status_code)
        return
    for model in sorted(m["name"] for m in response.json().get("models", [])):
        if any(word in model for word in ("flash", "transcribe", "tts", "live")):
            print(model.removeprefix("models/"))


def parent_alive(pid):
    """True while process `pid` runs (Windows: never use os.kill here, it would terminate the process)."""
    if sys.platform == "win32":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, int(pid))  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) != 0  # WAIT_OBJECT_0: exited
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


async def watch_parent(pid):
    while parent_alive(pid):
        await asyncio.sleep(2.0)
    log.info("game process %s ended; relay stopping", pid)


def seed_cache(seed_dir, data_dir):
    """First run of a packaged build: start from the replies generated during development."""
    target = os.path.join(data_dir, "cache")
    if seed_dir and os.path.isfile(os.path.join(seed_dir, "index.json")) and not os.path.isfile(
            os.path.join(target, "index.json")):
        import shutil
        shutil.copytree(seed_dir, target, dirs_exist_ok=True)
        return True
    return False


async def main_async(args):
    from api_keys import load_keys
    frozen = getattr(sys, "frozen", False)
    keys_file = args.keys or (os.path.join(os.path.dirname(sys.executable), "keys.json") if frozen else None)
    keys = load_keys(keys_file, only_file=bool(frozen or args.keys))
    overrides = {"mode": args.mode} if args.mode else {}
    config = RelayConfig.from_env(**overrides)
    if config.mode == "pipeline" and not keys["gemini"]:
        if frozen or args.keys:
            print("No gemini_api_key in " + os.path.basename(keys_file) + "; NPCs use baked lines.")
        else:
            print("No Gemini key: set GEMINI_API_KEY or use ~/.gemini/api_key (or pass --keys keys.json).")
        return 2
    if config.mode == "realtime" and not keys["openai"]:
        print("Realtime mode (development only) needs an OpenAI key: OPENAI_API_KEY or ~/.openai/api_key.")
        return 2
    if args.list_models:
        await list_models(keys["gemini"])
        return 0
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("relay.py is the loopback development relay; use hosted_relay.py for a network service.")
        return 2
    data_dir = os.path.abspath(args.data_dir)
    os.makedirs(data_dir, exist_ok=True)
    setup_logging(os.path.join(data_dir, "relay.log"))
    seeded = seed_cache(args.seed_dir, data_dir)
    token = os.environ.get("REFLECTIONS_VOICE_LOCAL_TOKEN") or secrets.token_urlsafe(32)
    # The game that started this helper waits for its own ready file (the port it got); the editor reads relay.token.
    token_path = os.path.abspath(args.ready_file) if args.ready_file else os.path.join(data_dir, "relay.token")
    from tts import Roster
    roster_path = args.roster or os.path.join(os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, "frozen", False) else __file__)), "roster.json")
    if not args.roster and not getattr(sys, "frozen", False) and not os.path.exists(roster_path):
        # Editor: the audio session's roster (VoiceId -> designed Gemini voice, persona, delivery style).
        roster_path = os.path.join(REPO_ROOT, "ArtDirection", "Audio", "data", "voice_roster_dialogue.json")
    meter = SpendMeter(os.path.join(data_dir, "spend.json"), daily_cap=args.daily_cap or None,
                       monthly_cap=args.monthly_cap or None)
    # Pipeline mode never touches OpenAI, even when an OpenAI key happens to be configured.
    relay = VoiceRelay(keys["openai"] if config.mode == "realtime" else "", LocalAuth(token), config,
                       policy=policy_from_env(os.path.join(data_dir, "reuse_stats.json")), data_dir=data_dir,
                       meter=meter, roster=Roster(roster_path), gemini_key=keys["gemini"])
    try:
        server, port = await serve_first_free(relay.handle, args.host, args.port, args.port_fallbacks,
                                              max_size=100_000, origins=LOOPBACK_ORIGINS, process_request=health)
    except OSError as exc:
        log.error("could not listen on %s ports %d-%d (%s): another program, or another copy of the game, has "
                  "them; NPCs use baked lines", args.host, args.port, args.port + args.port_fallbacks,
                  type(exc).__name__)
        return 3
    try:
        async with server:
            # Written once listening: the game treats the file as "ready" (and editor builds read the token from it).
            with open(token_path, "w", encoding="ascii") as handle:
                handle.write(str(port) if args.ready_file else token)
            if config.mode == "pipeline":
                models = (f"Gemini: hearing {config.hearing_model}, replies {config.composer_model}, moderation "
                          f"{config.moderation_model}, speech {config.gemini_tts_model}, safety {config.safety_threshold}")
            else:
                models = f"OpenAI (development): {config.model}, transcription {config.transcribe_model}"
            log.info("NPC dialogue relay on ws://%s:%d, %s mode (%s; roster %d voices); %d saved replies%s; %s; %s",
                     args.host, port, config.mode, models, len(relay.roster), len(relay.cache),
                     " (seeded)" if seeded else "", relay.policy.summary(), relay.meter.summary())
            if args.parent_pid:
                await watch_parent(args.parent_pid)
            else:
                await asyncio.Future()
    finally:
        try:
            os.remove(token_path)
        except OSError:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--data-dir", default=os.environ.get("REFLECTIONS_NPC_DATA_DIR", DEFAULT_DATA_DIR))
    parser.add_argument("--list-models", action="store_true", help="print the Gemini models this key can use")
    parser.add_argument("--mode", choices=("pipeline", "realtime"), help="default: REFLECTIONS_NPC_MODE or pipeline")
    parser.add_argument("--keys", help="keys.json with gemini_api_key (default: next to the exe)")
    parser.add_argument("--roster", help="voice roster JSON (default: roster.json next to the relay)")
    parser.add_argument("--seed-dir", help="a reply cache to start from on first run (shipped with the game)")
    parser.add_argument("--ready-file", help="write the port here once listening (the game's per-run file)")
    parser.add_argument("--port-fallbacks", type=int, default=0, help="also try this many ports after --port")
    parser.add_argument("--parent-pid", type=int, help="exit when this process (the game) ends")
    parser.add_argument("--daily-cap", type=float, default=float(os.environ.get("REFLECTIONS_DAILY_CAP_USD", "3")))
    parser.add_argument("--monthly-cap", type=float, default=float(os.environ.get("REFLECTIONS_MONTHLY_CAP_USD", "20")))
    args = parser.parse_args(argv)
    try:
        return asyncio.run(main_async(args)) or 0
    except KeyboardInterrupt:
        return 0
    except ValueError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
