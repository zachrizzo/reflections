"""DEVELOPMENT ONLY: the cheap OpenAI calls of the optional realtime mode (REFLECTIONS_NPC_MODE=realtime): reuse
decision, intent label and moderation. The shipped pipeline uses gemini.py and needs no OpenAI key.

All calls use the REST API through httpx with short timeouts. Failures never raise into the relay: a failed
decision means "generate a new reply", a failed moderation means "do not reuse this reply later".
"""
import json

import httpx

from composing import INTENTS, Decision  # noqa: F401  (Decision is re-exported for older callers)

API = "https://api.openai.com/v1"

SYSTEM = (
    "You pick voice lines for non-player characters in a fantasy game. The player just said a line to an NPC. "
    "You get the NPC's current situation and up to eight replies this kind of NPC gave before, each with the "
    "line it answered. Choose a candidate only if playing its reply right now would sound like a natural, "
    "direct answer to what the player just said, in this exact situation. Reject a candidate if it answers a "
    "different question, names a different place or job than the current NPC's, contradicts the NPC's "
    "current mood (calm versus fleeing, friendly versus hostile) or the Silverer's standing, or refers to "
    "something that is not in the player's line. When in doubt choose \"none\": a fresh reply is always "
    "acceptable, a wrong one is not. Also label the intent of the player's line."
)


def _decision_schema(ids):
    return {
        "type": "object", "additionalProperties": False,
        "required": ["choice", "confidence", "intent", "reason"],
        "properties": {
            "choice": {"type": "string", "enum": list(ids) + ["none"]},
            "confidence": {"type": "number"},
            "intent": {"type": "string", "enum": list(INTENTS)},
            "reason": {"type": "string"},
        },
    }


def _output_text(body):
    for item in body.get("output", []) or []:
        if item.get("type") == "message":
            for part in item.get("content", []) or []:
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    return part["text"]
    return body.get("output_text") if isinstance(body.get("output_text"), str) else ""


class Decider:
    def __init__(self, api_key, model="gpt-6-luna", timeout=4.0, client=None, reasoning_effort="none"):
        self.api_key, self.model, self.timeout = api_key, model, timeout
        self.reasoning_effort = reasoning_effort
        self.client = client or httpx.AsyncClient(timeout=timeout, trust_env=False)

    def _headers(self):
        return {"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"}

    async def choose(self, persona, player_line, candidates):
        """Returns a Decision. choice is a candidate id or None."""
        ids = [c.id for c in candidates]
        payload = {
            "npc": {"kind": persona.group, "role": persona.role, "situation": persona.context()},
            "player_said": (player_line or "")[:400],
            "candidates": [c.summary_for_decider() for c in candidates],
        }
        request = {
            "model": self.model,
            "input": [{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            "text": {"format": {"type": "json_schema", "name": "reuse_decision", "strict": True,
                                "schema": _decision_schema(ids)}},
            "max_output_tokens": 300,
        }
        if self.reasoning_effort:
            request["reasoning"] = {"effort": self.reasoning_effort}
        try:
            response = await self.client.post(API + "/responses", headers=self._headers(), json=request,
                                              timeout=self.timeout)
            if response.status_code != 200:
                return Decision(error=f"http {response.status_code}")
            body = response.json()
            data = json.loads(_output_text(body) or "{}")
        except (httpx.HTTPError, ValueError) as exc:
            return Decision(error=type(exc).__name__)
        choice = data.get("choice")
        intent = data.get("intent") if data.get("intent") in INTENTS else "other"
        confidence = data.get("confidence") if isinstance(data.get("confidence"), (int, float)) else 0.0
        return Decision(choice=choice if choice in ids else None, confidence=float(confidence), intent=intent,
                        reason=str(data.get("reason", ""))[:200], usage=body.get("usage") or {})

    async def classify(self, persona, player_line):
        """Intent label only (no candidates). Used in the background after a fresh generation."""
        if not player_line:
            return Decision(intent="other")
        return await self.choose(persona, player_line, [])

    async def moderate(self, text):
        """True if flagged, False if clean, None if moderation could not be reached (the caller decides)."""
        if not text:
            return False
        try:
            response = await self.client.post(API + "/moderations", headers=self._headers(), timeout=self.timeout,
                                              json={"model": "omni-moderation-latest", "input": text[:2000]})
            if response.status_code != 200:
                return None
            return any(r.get("flagged") for r in response.json().get("results", []))
        except (httpx.HTTPError, ValueError):
            return None

    async def flagged(self, text):
        """True if the moderation model flags the text, or if moderation cannot be reached."""
        if not text:
            return False
        try:
            response = await self.client.post(API + "/moderations", headers=self._headers(), timeout=self.timeout,
                                              json={"model": "omni-moderation-latest", "input": text[:2000]})
            if response.status_code != 200:
                return True
            return any(r.get("flagged") for r in response.json().get("results", []))
        except (httpx.HTTPError, ValueError):
            return True

    async def aclose(self):
        await self.client.aclose()
