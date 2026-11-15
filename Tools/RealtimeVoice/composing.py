"""Provider-neutral pieces of a composed NPC turn: the intent labels, the composer's rules and JSON schema, and the
parsed result. The shipped composer is gemini.GeminiComposer; decider.Composer (OpenAI) is development only.
"""
import json

INTENTS = ("greeting", "smalltalk", "farewell", "ask_about_tarnish", "ask_about_sides", "ask_directions",
           "ask_about_shards_or_pages", "ask_about_self", "ask_for_help", "offer_help", "threat_or_insult",
           "apology", "nonsense", "other")

COMPOSER_RULES = (
    "You are now writing this NPC's next spoken line in a game conversation. You get the recent conversation, what "
    "the player just said, some saved replies this same NPC voice gave before, and the actions you may take. "
    "Write 'reply': your next line, following all the rules above (one or two short sentences, at most 20 words). "
    "'reuse': if one saved reply would be a natural, direct answer to the player right now, in this exact situation "
    "(same question, matching mood, no wrong place or job), give its id, and your confidence from 0 to 1 in "
    "'reuse_confidence'; otherwise 'none' and 0. A fresh reply is always acceptable; a wrong saved one is not. "
    "'action': if the player asks for something one of the listed actions does, or the moment clearly calls for it, "
    "choose it and make your reply fit it (for pointing: say the way, briefly); otherwise name 'none'. Never claim to "
    "do anything that is not an action you chose. Quests: offer a quest only when the player asks for work or help; "
    "accept or decline only on a clear yes or no; give a hint when they ask for help with it; turn it in when they "
    "say it is done; never invent quests. 'intent': label what the player's line is."
)


class Decision:
    def __init__(self, choice=None, confidence=0.0, intent="other", reason="", usage=None, error=None):
        self.choice, self.confidence, self.intent, self.reason = choice, confidence, intent, reason
        self.usage, self.error = usage or {}, error

    def __repr__(self):
        return f"Decision(choice={self.choice}, confidence={self.confidence:.2f}, intent={self.intent})"


class ComposedTurn:
    """blocked: the provider's safety filter stopped the request or the reply (never spoken; the game plays one of
    that NPC's own baked lines). error: the call failed (also never spoken)."""

    def __init__(self, reply="", reuse=None, reuse_confidence=0.0, action=None, target="none", intent="other",
                 usage=None, error=None, blocked=None):
        self.reply, self.reuse, self.reuse_confidence = reply, reuse, reuse_confidence
        self.action, self.target, self.intent = action, target, intent
        self.usage, self.error, self.blocked = usage or {}, error, blocked


def compose_schema(candidate_ids, offers):
    names = sorted({name for name, _ in offers}) + ["none"]
    targets = sorted({target for _, target in offers} | {"none"})
    return {
        "type": "object", "additionalProperties": False,
        "required": ["reply", "reuse", "reuse_confidence", "action", "intent"],
        "properties": {
            "reply": {"type": "string"},
            "reuse": {"type": "string", "enum": list(candidate_ids) + ["none"]},
            "reuse_confidence": {"type": "number"},
            "action": {"type": "object", "additionalProperties": False, "required": ["name", "target"],
                       "properties": {"name": {"type": "string", "enum": names},
                                      "target": {"type": "string", "enum": targets}}},
            "intent": {"type": "string", "enum": list(INTENTS)},
        },
    }


def compose_payload(history, line, candidates, action_text, avoid=(), milder=False):
    payload = {"recent_conversation": history[-10:], "player_said": (line or "")[:400],
               "saved_replies": [c.summary_for_decider() for c in candidates],
               "actions_you_may_take": action_text}
    if avoid:
        payload["other_people_already_said_these_exact_lines_so_word_yours_differently"] = list(avoid)[:5]
    if milder:
        payload["your_last_draft_was_stopped_by_the_content_filter"] = (
            "Answer again, in character, more mildly: no threats, injuries, weapons or insults.")
    return json.dumps(payload, ensure_ascii=False)


def parse_turn(text, candidates, usage):
    """The composer's JSON reply as a ComposedTurn; anything off-schema is dropped, never trusted."""
    data = json.loads(text or "{}")
    if not isinstance(data, dict):
        raise ValueError("not an object")
    ids = {c.id for c in candidates}
    action = data.get("action") if isinstance(data.get("action"), dict) else {}
    confidence = data.get("reuse_confidence")
    return ComposedTurn(
        reply=str(data.get("reply", "")).strip()[:400],
        reuse=data.get("reuse") if data.get("reuse") in ids else None,
        reuse_confidence=float(confidence) if isinstance(confidence, (int, float)) else 0.0,
        action=action.get("name") if action.get("name") not in (None, "none") else None,
        target=action.get("target") or "none",
        intent=data.get("intent") if data.get("intent") in INTENTS else "other",
        usage=usage)
