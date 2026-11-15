"""Pipeline mode, the shipped path (Gemini only, one key): speech -> text -> reply (+ action) -> speech in THAT NPC's
own voice.

- Hearing: while the player holds the talk key their audio streams to gemini-3.5-transcribe-live (gemini.py); the
  final text is ready about 0.25 s after they let go.
- Thinking: one composer call writes the NPC's line, says whether a saved reply of this same NPC fits instead, and may
  pick one whitelisted action. Strict safety settings: a blocked request or reply is never spoken.
- Before playback: a separate Gemini moderation check of the line runs while it is synthesized; the audio is held
  until it clears. Blocked or flagged: the game plays one of that NPC's own baked lines instead.
- Speech: Gemini TTS in the NPC's designed voice from audio's roster (identical to its baked lines), else the stock
  Gemini voice of its slot.
The game sees the same events as in realtime mode, plus `reply.thinking` and `npc.action`.
"""
import asyncio
import base64
import dataclasses
import time

from actions import ACTIONS, QUEST_VERBS, describe, offers_for, validate
from composing import Decision
from costs import tts_cost, transcription_cost
from persona import GEMINI_SLOT_VOICES, REACTION_TEXT, SLOT_PERSONAS, TARNISH_GEMINI_VOICE, VOICE_DELIVERY
from relay import PROTOCOL, DialogueSession, _clean_text, log, worth_asking
from tts import TtsError


def _done(value):
    future = asyncio.get_running_loop().create_future()
    future.set_result(value)
    return future


class PipelineSession(DialogueSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.history = []
        self.hearing = None  # the utterance being recorded (gemini.HearingTurn)
        self.turn_deadline = self.cfg.turn_deadline

    # ---- lifecycle: no upstream session; each utterance gets its own short hearing stream ---------------

    async def run(self):
        await self.send({"type": "session.ready", "protocol": PROTOCOL, "voice": self.persona.voice,
                         "speaker": self.persona.speaker, "offline": self.offline})
        log.info("session %s: %s (%s, %s), voice %s", self.client_id, self.persona.speaker, self.persona.group,
                 self.persona.context_key(), self.route()[0])
        tasks = [asyncio.create_task(self.client_loop()), asyncio.create_task(self.idle_watch())]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.clear_audio()
            if self.turn_task:
                self.turn_task.cancel()
                await asyncio.gather(self.turn_task, return_exceptions=True)
            if self.background:
                await asyncio.wait(self.background, timeout=10)

    async def on_audio(self, data):
        if self.offline or self.relay.hearing is None:
            return
        if self.hearing is None:
            self.hearing = self.relay.hearing.start([self.persona.name] if self.persona.name else [])
        await self.hearing.feed(data)

    async def clear_audio(self):
        hearing, self.hearing = self.hearing, None
        if hearing is not None:
            hearing.cancel()

    async def interrupt(self, played_ms):
        """The player cut in, or the game gave up waiting: stop speaking, and drop a reply not yet started."""
        self.replay_cancel = True
        if self.turn_busy() and not self.reply_started:
            self.turn_task.cancel()

    async def send_audio(self, pcm):
        # The game drops any single message over 200,000 bytes; Gemini may send bigger chunks.
        for start in range(0, len(pcm), 48_000):
            await self.send({"type": "response.output_audio.delta",
                             "delta": base64.b64encode(pcm[start:start + 48_000]).decode("ascii")})

    async def update_persona(self, npc):
        # Voices are chosen per turn here, so a mood or kind change never needs a new session.
        from persona import normalize
        self.persona = normalize(npc, previous=self.persona)
        return True

    # ---- turns -----------------------------------------------------------------------------------------

    async def voice_turn(self):
        pcm_bytes, self.audio_bytes = self.audio_bytes, 0
        hearing, self.hearing = self.hearing, None
        if self.offline:
            if hearing is not None:
                hearing.cancel()
            await self.offline_reply(None)
            return
        if hearing is None:
            await self.send({"type": "reply.unavailable", "reason": "unheard"})
            return
        relay = self.relay
        relay.spend(self.client_id, transcription_cost(relay.config.hearing_model, pcm_bytes))
        started = time.monotonic()
        text = await hearing.finish(self.cfg.transcript_wait)
        heard_s = time.monotonic() - started
        if text is None:
            await self.send({"type": "reply.unavailable", "reason": "error"})
            relay.log_turn(self, "NO REPLY", "-", "(voice)", "", f"hearing failed ({hearing.error or 'timeout'})")
            return
        text = _clean_text(text)
        if not text:
            await self.send({"type": "reply.unavailable", "reason": "unheard"})
            relay.log_turn(self, "NO REPLY", "-", "(nothing heard)", "", f"empty transcript after {heard_s:.2f}s")
            return
        await self.send({"type": "transcript.player", "text": text})
        await self.respond(_done(text), typed=False, heard_s=heard_s)

    async def text_turn(self, text):
        await self.send({"type": "transcript.player", "text": text})
        if self.offline:
            await self.offline_reply(text)
            return
        await self.respond(_done(text), typed=True)

    def on_action_result(self, event):
        name = event.get("name") if event.get("name") in ACTIONS or event.get("name") in QUEST_VERBS else None
        if name:
            outcome = "done" if event.get("ok") is True else "it could not be done"
            note = f"({name.replace('_', ' ')}: {outcome})"
            say = " ".join(str(event.get("say", "")).split())[:200] if isinstance(event.get("say"), str) else ""
            if say:
                note = note[:-1] + f"; the game showed: {say})"
            self.history.append({"speaker": "game", "text": note})

    def stock_voice(self):
        persona = self.persona
        if persona.group == "tarnish":
            return TARNISH_GEMINI_VOICE
        return GEMINI_SLOT_VOICES.get(persona.slot, "Kore")

    def route(self):
        """Which voice speaks: (voice, style, persona keyed by that exact voice for the cache, stock fallback)."""
        persona, relay = self.persona, self.relay
        mood = REACTION_TEXT.get(persona.reaction, "")
        entry = relay.roster.get(persona.voice_id)
        if entry is None and persona.gemini_voice:
            # The NPC system sends the designed voice straight from audio's roster table (DT_NpcVoiceRoster).
            entry = {"gemini_voice": persona.gemini_voice, "style": ""}
        stock = self.stock_voice()
        voice = entry["gemini_voice"] if entry is not None else stock
        default_style = VOICE_DELIVERY.get(persona.group, "")
        if entry is None:
            default_style = "; ".join(s for s in (SLOT_PERSONAS.get(persona.slot, ""), default_style) if s)
        style = " ".join(s for s in ((entry or {}).get("style") or default_style, mood) if s)
        return voice, style, dataclasses.replace(persona, voice="gemini:" + voice), stock

    async def respond(self, line_future, typed, heard_s=None):
        relay = self.relay
        line = line_future.result() if line_future.done() else ""
        if not line.strip():
            await self.send({"type": "reply.unavailable", "reason": "unheard"})
            relay.log_turn(self, "NO REPLY", "-", "(nothing heard)", "", "empty transcript")
            return
        voice, style, keyed, stock = self.route()
        budget = relay.budget_state()
        cap = relay.policy.cap if budget == "ok" else max(relay.policy.cap, self.cfg.soft_budget_reuse_cap)
        candidates = []
        if relay.policy.allowed(cap) and relay.cache.has_persona(keyed):
            found = relay.cache.candidates(keyed, line, exclude=self.recent)
            if found and worth_asking(line, found, self.cfg.min_similarity_to_ask):
                candidates = found
        offers = offers_for(keyed.group, keyed.actions)
        await self.send({"type": "reply.thinking"})
        started = time.monotonic()
        turn = await relay.composer.compose(keyed, self.history, line, candidates, offers, describe(offers))
        relay.spend(self.client_id, relay.composer.cost({"usageMetadata": turn.usage}))
        milder = False
        if turn.blocked and turn.blocked.startswith("reply"):
            # The filter stopped the NPC's draft (not the player's line): ask once for a milder line. The retry
            # passes the same strict filter, so nothing gets through that would not have before.
            milder = True
            turn = await relay.composer.compose(keyed, self.history, line, candidates, offers, describe(offers),
                                                milder=True)
            relay.spend(self.client_id, relay.composer.cost({"usageMetadata": turn.usage}))
        compose_s = time.monotonic() - started
        if turn.blocked:
            await self.send({"type": "reply.unavailable", "reason": "moderated"})
            relay.log_turn(self, "BLOCKED", "-", line, "(withheld)", f"Gemini safety filter ({turn.blocked}"
                           f"{', also the milder retry' if milder else ''}) after {compose_s:.2f}s; the NPC says one "
                           "of its own baked lines instead")
            return
        if turn.error or not (turn.reply or turn.reuse):
            await self.send({"type": "reply.unavailable", "reason": "error"})
            relay.log_turn(self, "NO REPLY", "-", line, "", f"composer failed: {turn.error}")
            return
        if not turn.reuse and relay.cache.said_by_other(turn.reply, keyed.npc_id):
            # No two characters say the exact same phrase: ask once more, telling the model what to avoid.
            retry = await relay.composer.compose(keyed, self.history, line, [], offers, describe(offers),
                                                 avoid=[turn.reply])
            relay.spend(self.client_id, relay.composer.cost({"usageMetadata": retry.usage}))
            if not retry.error and not retry.blocked and retry.reply and not relay.cache.said_by_other(
                    retry.reply, keyed.npc_id):
                turn = retry
            else:
                await self.send({"type": "reply.unavailable", "reason": "duplicate"})
                relay.log_turn(self, "NO REPLY", "-", line, turn.reply, "another NPC already said this line")
                return
        self.history.append({"speaker": "player", "text": line[:300]})
        chosen = validate(turn.action, turn.target, offers) if turn.action else None
        if turn.action and not chosen:
            log.info("composer chose an action that was not offered (%s %s): ignored", turn.action, turn.target)
        if chosen:
            await self.send({"type": "npc.action", "name": chosen[0], "target": chosen[1]})
        threshold = relay.policy.min_confidence() if budget == "ok" else self.cfg.soft_budget_min_confidence
        if turn.reuse and turn.reuse_confidence >= threshold:
            entry = relay.cache.get(turn.reuse)
            if entry is not None:
                self.history.append({"speaker": "you", "text": entry.reply_text})
                await self.replay(entry, line, Decision(entry.id, turn.reuse_confidence, turn.intent, "composer"))
                return
        self.history.append({"speaker": "you", "text": turn.reply})
        timing = ((f"heard {heard_s:.2f}s; " if heard_s is not None else "") + f"compose {compose_s:.2f}s"
                  + (" (milder retry after a filtered draft)" if milder else ""))
        await self.speak(turn.reply, line, turn.intent, voice, style, keyed, stock, timing, chosen,
                         "reuse rejected" if turn.reuse else ("no saved replies offered" if not candidates else "fresh"))

    async def speak(self, text, line, intent, voice, style, keyed, stock, timing, chosen, why):
        """Synthesizes while moderation runs, holding the audio back until the text is cleared. A flagged line is
        never heard or shown: the game plays one of that NPC's own baked lines instead."""
        relay = self.relay
        self.replay_cancel = False
        verdict = asyncio.create_task(relay.moderator.moderate(
            text, on_cost=lambda usd: relay.spend(self.client_id, usd)))
        held, released = [], False

        async def release():
            nonlocal released
            result = await verdict
            if result is True:
                return False
            if result is None:
                log.warning("moderation unreachable; the safety settings and persona rules still applied")
            released = True
            await self.send({"type": "reply.start", "source": "generated"})
            await self.send({"type": "reply.text", "text": text})
            for part in held:
                await self.send_audio(part)
            held.clear()
            return True

        # The designed voice first; if it is gone (deleted, wrong project), the slot's stock voice.
        attempts = [voice] + ([stock] if stock != voice else [])
        pcm, first, used, started, blocked = bytearray(), None, voice, time.monotonic(), False
        for use_voice in attempts:
            try:
                async for chunk in relay.gemini_tts.stream(text, use_voice, style):
                    if self.replay_cancel:
                        break
                    pcm.extend(chunk)
                    if not released:
                        held.append(chunk)
                        if verdict.done() and not await release():
                            blocked = True
                            break
                        continue
                    if first is None:
                        first = time.monotonic() - started
                    await self.send_audio(chunk)
                used = use_voice
                break
            except TtsError as error:
                log.warning("speech failed (%s)%s", error.code, "; trying the slot's stock voice"
                            if not pcm and use_voice != attempts[-1] else "")
                if pcm:
                    break
        relay.spend(self.client_id, tts_cost("gemini", len(pcm), relay.config.gemini_tts_model))
        if not blocked and not released and pcm:
            blocked = not await release()
        if first is None and released:
            first = time.monotonic() - started
        if blocked:
            self.history.pop() if self.history and self.history[-1].get("speaker") == "you" else None
            await self.send({"type": "reply.unavailable", "reason": "moderated"})
            relay.log_turn(self, "MODERATED", "-", line, "(withheld)", "reply flagged by moderation before playback; "
                           "the NPC says one of its own baked lines instead")
            return
        if not pcm:
            if not verdict.done():
                verdict.cancel()
            await self.send({"type": "reply.unavailable", "reason": "error"})
            relay.log_turn(self, "NO REPLY", "-", line, text, "speech synthesis failed")
            return
        status = "cancelled" if self.replay_cancel else "completed"
        await self.send({"type": "response.done", "status": status, "source": "generated"})
        relay.policy.record("new")
        action = f"; action {chosen[0]} {chosen[1]}" if chosen else ""
        relay.log_turn(self, "GENERATED", "-", line, text,
                       f"{why}; {timing}; speech first audio {first if first is not None else 0:.2f}s "
                       f"({used}); {len(pcm) / 48000:.1f}s audio{action}")
        if status == "completed":
            if used != voice:
                keyed = dataclasses.replace(self.persona, voice="gemini:" + used)
            # Only a line moderation cleared may be offered again later.
            cleared = (verdict.done() and not verdict.cancelled() and verdict.exception() is None
                       and verdict.result() is False)
            task = self.spawn(relay.save_reply(keyed, _done(line), text, bytes(pcm), intent, self.client_id,
                                               model=f"{relay.config.gemini_tts_model}:{used}",
                                               flagged=not cleared))
            task.add_done_callback(lambda t: self.recent.append(t.result().id)
                                   if not t.cancelled() and t.exception() is None else None)
