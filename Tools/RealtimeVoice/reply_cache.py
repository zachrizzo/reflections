"""Saved NPC replies, and the rule that keeps new generations ahead of reused ones.

Every generated reply is saved: its text, its audio (24 kHz mono PCM16 WAV), the persona key, the context,
the player's line and the intent the decision model gave it. Before a new reply is generated, the relay
asks ReplyCache for a short list of candidates and asks the decision model whether one of them genuinely fits.

ReusePolicy caps reuse: over the last `window` replies, at most `cap` (default 35%) may be reused ones, and
while the measured ratio is above `target` (default 25%) a reuse needs a higher confidence.
"""
import json
import os
import re
import threading
import time
import uuid
import wave
from collections import deque
from dataclasses import dataclass, field, asdict

SAMPLE_RATE = 24000
STOPWORDS = frozenset(
    "a an and are am be but by can could did do does for from had has have he her his how i i'm if in is it "
    "its it's just me my no not of on or our please she so that the their them then there they this to us "
    "was we were what when where which who why will with would you your you're hey oh um uh".split())


def tokens(text):
    words = re.findall(r"[a-z']+", (text or "").lower())
    return {w.strip("'") for w in words if w.strip("'") and w not in STOPWORDS}


def similarity(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class CachedReply:
    id: str
    created: float
    persona_key: str
    group: str
    voice: str
    archetype: str
    role: str
    side: str
    context: dict
    context_key: str
    player_line: str
    reply_text: str
    audio_file: str
    audio_ms: int
    model: str
    intent: str = "other"
    npc_id: str = ""          # the NPC that said it: only that NPC may ever say it again
    uses: int = 0
    last_used: float = 0.0
    flagged: bool = False
    extra: dict = field(default_factory=dict)

    def summary_for_decider(self):
        return {"id": self.id, "player_said": self.player_line[:200], "npc_replied": self.reply_text[:300],
                "intent": self.intent, "situation": self.context}


class ReplyCache:
    """A folder with index.json and audio/<id>.wav. Thread-safe; writes are atomic replaces."""

    def __init__(self, root, max_entries=5000):
        self.root = os.path.abspath(root)
        self.audio_dir = os.path.join(self.root, "audio")
        self.index_path = os.path.join(self.root, "index.json")
        self.max_entries = max_entries
        self.lock = threading.Lock()
        self.entries = {}
        os.makedirs(self.audio_dir, exist_ok=True)
        self._load()

    def _load(self):
        try:
            with open(self.index_path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            data = []
        for raw in data if isinstance(data, list) else []:
            try:
                entry = CachedReply(**raw)
            except TypeError:
                continue
            if os.path.exists(os.path.join(self.audio_dir, entry.audio_file)):
                self.entries[entry.id] = entry

    def _save_locked(self):
        try:
            temp = self.index_path + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump([asdict(e) for e in sorted(self.entries.values(), key=lambda e: e.created)], handle,
                          ensure_ascii=False, indent=1)
            os.replace(temp, self.index_path)
        except OSError as exc:  # kept in memory; the next save writes it
            import logging
            logging.getLogger("npc-dialogue").warning("could not save the reply index (%s)", type(exc).__name__)

    def __len__(self):
        return len(self.entries)

    def add(self, persona, player_line, reply_text, pcm, model, intent="other", flagged=False):
        reply_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        audio_file = reply_id + ".wav"
        path = os.path.join(self.audio_dir, audio_file)
        with wave.open(path, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(SAMPLE_RATE)
            out.writeframes(bytes(pcm))
        entry = CachedReply(
            id=reply_id, created=time.time(), persona_key=persona.key, group=persona.group, voice=persona.voice,
            archetype=persona.archetype, role=persona.role, side=persona.side, context=persona.context(),
            context_key=persona.context_key(), player_line=(player_line or "")[:500],
            reply_text=(reply_text or "")[:1000], audio_file=audio_file,
            audio_ms=int(len(pcm) / 2 / SAMPLE_RATE * 1000), model=model, intent=intent, flagged=flagged,
            npc_id=persona.npc_id)
        with self.lock:
            self.entries[reply_id] = entry
            self._evict_locked()
            self._save_locked()
        return entry

    def _evict_locked(self):
        if len(self.entries) <= self.max_entries:
            return
        # Drop the least useful: never reused, oldest first.
        victims = sorted(self.entries.values(), key=lambda e: (e.uses, e.last_used or e.created))
        for entry in victims[:len(self.entries) - self.max_entries]:
            self.entries.pop(entry.id, None)
            try:
                os.remove(os.path.join(self.audio_dir, entry.audio_file))
            except OSError:
                pass

    def update(self, reply_id, **fields):
        with self.lock:
            entry = self.entries.get(reply_id)
            if not entry:
                return
            for name, value in fields.items():
                setattr(entry, name, value)
            self._save_locked()

    def record_use(self, reply_id):
        with self.lock:
            entry = self.entries.get(reply_id)
            if entry:
                entry.uses += 1
                entry.last_used = time.time()
                self._save_locked()

    def get(self, reply_id):
        return self.entries.get(reply_id)

    def load_pcm(self, entry):
        with wave.open(os.path.join(self.audio_dir, entry.audio_file), "rb") as source:
            return source.readframes(source.getnframes())

    def _usable(self, entry, persona):
        """Only the NPC that first said a line may say it again (same NPC id, same voice and kind)."""
        return (entry.npc_id and entry.npc_id == persona.npc_id and entry.persona_key == persona.key
                and not entry.flagged and entry.player_line)

    def has_persona(self, persona):
        return any(self._usable(e, persona) for e in self.entries.values())

    def candidates(self, persona, player_line, exclude=(), limit=8):
        """That NPC's own saved replies (same voice); ranked by line similarity and matching situation."""
        ctx, scored = persona.context(), []
        for entry in self.entries.values():
            if not self._usable(entry, persona) or entry.id in exclude:
                continue
            score = similarity(player_line, entry.player_line) * 2.0 + similarity(player_line, entry.reply_text) * 0.5
            score += 0.3 if entry.context.get("reaction") == ctx["reaction"] else 0.0
            score += 0.1 if entry.side == persona.side else 0.0
            score += 0.1 if entry.context.get("reputation") == ctx["reputation"] else 0.0
            score += 0.05 if entry.role == persona.role else 0.0
            score -= min(entry.uses, 10) * 0.02
            scored.append((score, entry))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    @staticmethod
    def _norm(text):
        return " ".join(re.findall(r"[a-z0-9']+", (text or "").lower()))

    def said_by_other(self, text, npc_id):
        """True if another NPC already said exactly this line (no two characters share a phrase)."""
        norm = self._norm(text)
        return bool(norm) and any(e.npc_id != npc_id and self._norm(e.reply_text) == norm
                                  for e in self.entries.values())

    def best_offline(self, persona, player_line, exclude=(), min_similarity=0.34):
        """No API available: a local pick. With a line, it must overlap; without one, a greeting-like reply."""
        best, best_score = None, 0.0
        for entry in self.candidates(persona, player_line or "", exclude, limit=50):
            if entry.context.get("reaction") != persona.reaction:
                continue
            if player_line:
                score = similarity(player_line, entry.player_line)
                if score >= min_similarity and score > best_score:
                    best, best_score = entry, score
            elif entry.intent in ("greeting", "smalltalk") and (best is None or entry.uses < best.uses):
                best = entry
        return best


class ReusePolicy:
    """Rolling window of 'new'/'reuse' outcomes, persisted next to the cache."""

    def __init__(self, path=None, cap=0.35, target=0.25, window=20):
        if not 0.0 <= target <= cap <= 1.0:
            raise ValueError("Reuse target must be between 0 and the cap, and the cap at most 1.")
        self.path, self.cap, self.target, self.window = path, cap, target, max(2, int(window))
        self.history = deque(maxlen=self.window)
        self.total_new = 0
        self.total_reuse = 0
        self.lock = threading.Lock()
        if path:
            try:
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
                self.history.extend(k for k in data.get("history", []) if k in ("new", "reuse"))
                self.total_new = int(data.get("total_new", 0))
                self.total_reuse = int(data.get("total_reuse", 0))
            except (OSError, ValueError, TypeError, AttributeError):
                pass

    def ratio(self):
        if not self.history:
            return 0.0
        return sum(1 for k in self.history if k == "reuse") / len(self.history)

    def all_time_ratio(self):
        total = self.total_new + self.total_reuse
        return self.total_reuse / total if total else 0.0

    def allowed(self, cap=None):
        """Whether one more reuse keeps the rolling window at or under the cap."""
        cap = self.cap if cap is None else cap
        recent = list(self.history)[-(self.window - 1):]
        return (sum(1 for k in recent if k == "reuse") + 1) / (len(recent) + 1) <= cap + 1e-9

    def min_confidence(self):
        return 0.7 if self.ratio() < self.target else 0.85

    def record(self, kind):
        assert kind in ("new", "reuse")
        with self.lock:
            self.history.append(kind)
            if kind == "new":
                self.total_new += 1
            else:
                self.total_reuse += 1
            if self.path:
                try:
                    temp = self.path + ".tmp"
                    with open(temp, "w", encoding="utf-8") as handle:
                        json.dump({"history": list(self.history), "total_new": self.total_new,
                                   "total_reuse": self.total_reuse, "cap": self.cap, "target": self.target,
                                   "window": self.window}, handle)
                    os.replace(temp, self.path)
                except OSError as exc:
                    import logging
                    logging.getLogger("npc-dialogue").warning("could not save reuse stats (%s)", type(exc).__name__)

    def summary(self):
        reused = sum(1 for k in self.history if k == "reuse")
        return (f"reuse {reused}/{len(self.history)} = {self.ratio():.0%} over the last {self.window} "
                f"(target {self.target:.0%}, cap {self.cap:.0%}); all time {self.total_reuse}/"
                f"{self.total_new + self.total_reuse} = {self.all_time_ratio():.0%}")
