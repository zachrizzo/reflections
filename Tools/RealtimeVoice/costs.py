"""Estimated spend from the usage numbers the APIs return, and a persisted budget.

Gemini (the shipped pipeline): USD per 1M tokens from the Gemini Developer API pricing page (paid tier, standard),
read 2026-11-14. gemini-3.8-flash and the 3.8 TTS models have introductory prices through 2026-12-31 and double on
2027-01-01; the estimate switches by date. An unknown Gemini model is priced like gemini-3.8-flash after 2026.
OpenAI (development only): from the OpenAI model pages on 2026-11-14; an unknown model is priced like
gpt-realtime-2.1. Estimates err high.
"""
import json
import logging
import os
import threading
import time

PRICES = {
    "gpt-realtime-2.1": {"text_in": 4.0, "text_cached": 0.4, "text_out": 24.0,
                         "audio_in": 32.0, "audio_cached": 0.4, "audio_out": 64.0},
    "gpt-realtime-2.1-mini": {"text_in": 0.6, "text_cached": 0.06, "text_out": 2.4,
                              "audio_in": 10.0, "audio_cached": 0.3, "audio_out": 20.0},
    "gpt-6-luna": {"text_in": 0.1, "text_cached": 0.01, "text_out": 0.5},
    "gpt-4.1-mini": {"text_in": 0.4, "text_cached": 0.1, "text_out": 1.6},
    "gpt-5.6-luna": {"text_in": 0.2, "text_cached": 0.02, "text_out": 1.2},
}
TRANSCRIBE_PER_MINUTE = {"gpt-transcribe": 0.0045, "gpt-4o-mini-transcribe": 0.003,
                         "gpt-live-transcribe": 0.017, "gpt-realtime-whisper": 0.017,
                         # blended audio in + text out (25 audio tokens/s, 175 text tokens/min)
                         "gemini-3.5-transcribe-live": 0.009, "gemini-3.5-transcribe": 0.005}

# (input, output incl. thinking) per 1M tokens: (until 2026-12-31, from 2027-01-01)
GEMINI_PRICES = {
    "gemini-3.8-flash": ((0.75, 3.75), (1.50, 7.50)),
    "gemini-3.5-flash-lite": ((0.30, 2.50), (0.30, 2.50)),
    "gemini-3.1-flash-lite": ((0.25, 1.50), (0.25, 1.50)),
}
# Audio out per 1M tokens at 25 tokens per second of speech: (until 2026-12-31, from 2027-01-01)
GEMINI_TTS = {"gemini-3.8-flash-tts": (9.0, 18.0), "gemini-3.8-flash-lite-tts": (6.0, 12.0)}


def _after_intro(now=None):
    return time.gmtime(now if now is not None else time.time()).tm_year >= 2027


def gemini_cost(model, usage, now=None):
    """Cost of one generateContent usageMetadata block (cached tokens are priced in full: errs high)."""
    if not isinstance(usage, dict):
        return 0.0
    prices = GEMINI_PRICES.get(model, GEMINI_PRICES["gemini-3.8-flash"])
    price_in, price_out = prices[1] if _after_intro(now) or model not in GEMINI_PRICES else prices[0]
    prompt = int(usage.get("promptTokenCount", 0) or 0)
    out = int(usage.get("candidatesTokenCount", 0) or 0) + int(usage.get("thoughtsTokenCount", 0) or 0)
    return (prompt * price_in + out * price_out) / 1_000_000


def _prices(model):
    for name in sorted(PRICES, key=len, reverse=True):
        if model == name or model.startswith(name + "-20"):
            return PRICES[name]
    return PRICES["gpt-realtime-2.1"]


def realtime_cost(model, usage):
    """Cost of one Realtime response.done usage block."""
    if not isinstance(usage, dict):
        return 0.0
    p = _prices(model)
    inp = usage.get("input_token_details") or {}
    out = usage.get("output_token_details") or {}
    cached = inp.get("cached_tokens_details") or {}
    audio_in, text_in = int(inp.get("audio_tokens", 0) or 0), int(inp.get("text_tokens", 0) or 0)
    audio_cached, text_cached = int(cached.get("audio_tokens", 0) or 0), int(cached.get("text_tokens", 0) or 0)
    if not cached and inp.get("cached_tokens"):
        text_cached = min(text_in, int(inp.get("cached_tokens") or 0))
    audio_out, text_out = int(out.get("audio_tokens", 0) or 0), int(out.get("text_tokens", 0) or 0)
    if not inp and not out:  # no breakdown: treat everything as audio (worst case)
        audio_in, audio_out = int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0)
    return (max(0, audio_in - audio_cached) * p.get("audio_in", 0) + audio_cached * p.get("audio_cached", 0)
            + max(0, text_in - text_cached) * p.get("text_in", 0) + text_cached * p.get("text_cached", 0)
            + audio_out * p.get("audio_out", 0) + text_out * p.get("text_out", 0)) / 1_000_000


def text_cost(model, usage):
    """Cost of a Responses API usage block."""
    if not isinstance(usage, dict):
        return 0.0
    p = _prices(model)
    cached = int((usage.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0)
    inp = int(usage.get("input_tokens", 0) or 0)
    out = int(usage.get("output_tokens", 0) or 0)
    return (max(0, inp - cached) * p["text_in"] + cached * p["text_cached"] + out * p["text_out"]) / 1_000_000


# Speech out, per second of audio. Text input is negligible next to it. OpenAI's gpt-4o-mini-tts (development only)
# is about $0.015/min.
TTS_PER_SECOND = {"openai": 0.015 / 60}


def tts_cost(provider, pcm_bytes, model="gemini-3.8-flash-tts", now=None):
    if provider == "gemini":
        early, late = GEMINI_TTS.get(model, GEMINI_TTS["gemini-3.8-flash-tts"])
        per_second = 25 * (late if _after_intro(now) else early) / 1_000_000
    else:
        per_second = TTS_PER_SECOND.get(provider, 0.015 / 60)
    return pcm_bytes / 48000 * per_second


def transcription_cost(model, pcm_bytes):
    minutes = pcm_bytes / 2 / 24000 / 60
    return minutes * TRANSCRIBE_PER_MINUTE.get(model, 0.017)


class SpendMeter:
    """Running spend per UTC day and month, saved to a JSON file so a restart keeps the count."""

    def __init__(self, path=None, daily_cap=None, monthly_cap=None, soft_fraction=0.8):
        self.path, self.daily_cap, self.monthly_cap, self.soft_fraction = path, daily_cap, monthly_cap, soft_fraction
        self.lock = threading.Lock()
        self.days, self.months = {}, {}
        if path:
            try:
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
                self.days = {k: float(v) for k, v in data.get("days", {}).items()}
                self.months = {k: float(v) for k, v in data.get("months", {}).items()}
            except (OSError, ValueError, TypeError, AttributeError):
                pass

    @staticmethod
    def _keys(now=None):
        stamp = time.gmtime(now if now is not None else time.time())
        return time.strftime("%Y-%m-%d", stamp), time.strftime("%Y-%m", stamp)

    def add(self, usd, now=None):
        if usd <= 0:
            return
        day, month = self._keys(now)
        with self.lock:
            self.days[day] = self.days.get(day, 0.0) + usd
            self.months[month] = self.months.get(month, 0.0) + usd
            self.days = dict(sorted(self.days.items())[-45:])
            if self.path:
                try:
                    temp = self.path + ".tmp"
                    with open(temp, "w", encoding="utf-8") as handle:
                        json.dump({"days": self.days, "months": self.months}, handle)
                    os.replace(temp, self.path)
                except OSError as exc:  # the in-memory count still caps this run
                    logging.getLogger("npc-dialogue").warning("could not save spend.json (%s)", type(exc).__name__)

    def today(self, now=None):
        return self.days.get(self._keys(now)[0], 0.0)

    def this_month(self, now=None):
        return self.months.get(self._keys(now)[1], 0.0)

    def _fraction(self, now=None):
        fractions = [0.0]
        if self.daily_cap:
            fractions.append(self.today(now) / self.daily_cap)
        if self.monthly_cap:
            fractions.append(self.this_month(now) / self.monthly_cap)
        return max(fractions)

    def state(self, now=None):
        """'ok', 'soft' (prefer the cache) or 'hard' (no model calls at all)."""
        fraction = self._fraction(now)
        if fraction >= 1.0:
            return "hard"
        if fraction >= self.soft_fraction:
            return "soft"
        return "ok"

    def summary(self, now=None):
        caps = []
        if self.daily_cap:
            caps.append(f"today ${self.today(now):.3f} of ${self.daily_cap:.2f}")
        if self.monthly_cap:
            caps.append(f"month ${self.this_month(now):.3f} of ${self.monthly_cap:.2f}")
        return ", ".join(caps) or f"today ${self.today(now):.3f} (no cap)"
