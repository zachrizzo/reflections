"""Hosted NPC dialogue relay: the same relay as relay.py, set up as a small public service.

NOT DEPLOYED. Hosting needs the user's approval first (see ArtDirection/NpcDialogue/README.md).

What it adds over the loopback relay:
- The Gemini key comes from the host's secret store (GEMINI_API_KEY); the game only knows the relay URL and a
  non-secret client key, which is a speed bump, not a lock. Anything shipped in a game can be extracted.
- Per-player limits (client id sent by the game, plus the caller's IP): turns per minute, turns per day,
  spend per day, concurrent sessions per IP, and a global session cap.
- A hard spend cap per UTC day and month. Past the soft line (80%) the reuse cap rises so the cache answers
  more; past the cap the relay makes no model calls at all and answers only from saved replies
  ("cache-first"); if nothing saved fits, the game plays its baked barks.
- Player lines are not written to the log (they are still stored with each saved reply, which the cache needs).

Environment (defaults in brackets): PORT [8080], REFLECTIONS_NPC_DATA_DIR [/data], REFLECTIONS_CLIENT_KEYS
(comma-separated; empty accepts any), REFLECTIONS_DAILY_CAP_USD [5], REFLECTIONS_MONTHLY_CAP_USD [25],
REFLECTIONS_MAX_SESSIONS [20], REFLECTIONS_PLAYER_TURNS_PER_MINUTE [8], REFLECTIONS_PLAYER_TURNS_PER_DAY [80],
REFLECTIONS_IP_TURNS_PER_DAY [300], REFLECTIONS_PLAYER_USD_PER_DAY [0.50], REFLECTIONS_IP_SESSIONS [3],
REFLECTIONS_CLIENT_IP_HEADER [Fly-Client-IP], plus the model and reuse settings relay.py reads.
"""
import asyncio
import hashlib
import hmac
import os
import re
import sys
import time
from collections import defaultdict, deque

from websockets.asyncio.server import serve

from costs import SpendMeter
from api_keys import load_keys
from relay import RelayConfig, VoiceRelay, health, log, policy_from_env, setup_logging


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return int(default)


class HostedAuth:
    def __init__(self, client_keys=(), turns_per_minute=8, turns_per_day=80, ip_turns_per_day=300,
                 usd_per_day=0.50, ip_sessions=3, ip_header="Fly-Client-IP", clock=time.time):
        self.client_keys = tuple(k for k in client_keys if k)
        self.turns_per_minute, self.turns_per_day = turns_per_minute, turns_per_day
        self.ip_turns_per_day, self.usd_per_day, self.ip_sessions = ip_turns_per_day, usd_per_day, ip_sessions
        self.ip_header, self.clock = ip_header, clock
        self.minute = defaultdict(deque)
        self.day_turns = defaultdict(int)
        self.day_ip_turns = defaultdict(int)
        self.day_spend = defaultdict(float)
        self.live_sessions = defaultdict(int)
        self.ip_of = {}
        self.day = None

    def _roll_day(self):
        today = time.strftime("%Y-%m-%d", time.gmtime(self.clock()))
        if today != self.day:
            self.day = today
            self.day_turns.clear()
            self.day_ip_turns.clear()
            self.day_spend.clear()

    def _ip(self, connection):
        headers = getattr(getattr(connection, "request", None), "headers", None)
        value = headers.get(self.ip_header) if headers is not None and self.ip_header else None
        if not value and headers is not None:
            value = (headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if not value:
            address = getattr(connection, "remote_address", None)
            value = address[0] if address else "unknown"
        # Only a hash is kept in memory, never written anywhere.
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    def check(self, first, connection):
        supplied = first.get("client_key", "")
        if self.client_keys and not (isinstance(supplied, str) and
                                     any(hmac.compare_digest(supplied, key) for key in self.client_keys)):
            return None
        raw = first.get("client_id") if isinstance(first.get("client_id"), str) else ""
        player = re.sub(r"[^A-Za-z0-9-]", "", raw)[:40] or "anon"
        ip = self._ip(connection)
        client_id = f"{ip}:{player}"
        self.ip_of[client_id] = ip
        return client_id

    def session_started(self, client_id, connection):
        ip = self.ip_of.get(client_id, "unknown")
        if self.live_sessions[ip] >= self.ip_sessions:
            return "rate"
        self.live_sessions[ip] += 1
        return None

    def session_ended(self, client_id, connection):
        ip = self.ip_of.get(client_id, "unknown")
        self.live_sessions[ip] = max(0, self.live_sessions[ip] - 1)

    def before_turn(self, client_id, connection):
        self._roll_day()
        now, ip = self.clock(), self.ip_of.get(client_id, "unknown")
        window = self.minute[client_id]
        while window and now - window[0] > 60:
            window.popleft()
        if (len(window) >= self.turns_per_minute or self.day_turns[client_id] >= self.turns_per_day
                or self.day_ip_turns[ip] >= self.ip_turns_per_day or self.day_spend[client_id] >= self.usd_per_day):
            return "rate"
        window.append(now)
        self.day_turns[client_id] += 1
        self.day_ip_turns[ip] += 1
        return None

    def spent(self, client_id, usd):
        self._roll_day()
        self.day_spend[client_id] += usd


def build(gemini_key=None, data_dir=None):
    data_dir = data_dir or os.environ.get("REFLECTIONS_NPC_DATA_DIR", "/data")
    os.makedirs(data_dir, exist_ok=True)
    auth = HostedAuth(
        client_keys=[k.strip() for k in os.environ.get("REFLECTIONS_CLIENT_KEYS", "").split(",")],
        turns_per_minute=_env_int("REFLECTIONS_PLAYER_TURNS_PER_MINUTE", 8),
        turns_per_day=_env_int("REFLECTIONS_PLAYER_TURNS_PER_DAY", 80),
        ip_turns_per_day=_env_int("REFLECTIONS_IP_TURNS_PER_DAY", 300),
        usd_per_day=_env_float("REFLECTIONS_PLAYER_USD_PER_DAY", 0.50),
        ip_sessions=_env_int("REFLECTIONS_IP_SESSIONS", 3),
        ip_header=os.environ.get("REFLECTIONS_CLIENT_IP_HEADER", "Fly-Client-IP"))
    config = RelayConfig.from_env(max_sessions=_env_int("REFLECTIONS_MAX_SESSIONS", 20), log_text=False,
                                  session_seconds=_env_int("REFLECTIONS_VOICE_SESSION_SECONDS", 900),
                                  idle_seconds=_env_int("REFLECTIONS_IDLE_SECONDS", 180))
    meter = SpendMeter(os.path.join(data_dir, "spend.json"),
                       daily_cap=_env_float("REFLECTIONS_DAILY_CAP_USD", 5.0),
                       monthly_cap=_env_float("REFLECTIONS_MONTHLY_CAP_USD", 25.0))
    relay = VoiceRelay("", auth, config, policy=policy_from_env(os.path.join(data_dir, "reuse_stats.json")),
                       meter=meter, data_dir=data_dir,
                       gemini_key=gemini_key if gemini_key is not None else load_keys()["gemini"])
    return relay


async def main():
    data_dir = os.environ.get("REFLECTIONS_NPC_DATA_DIR", "/data")
    os.makedirs(data_dir, exist_ok=True)
    setup_logging()
    relay = build(data_dir=data_dir)
    port = _env_int("PORT", 8080)
    # The game's WebSocket client sends "http://<relay host>" as its Origin; list it in REFLECTIONS_ALLOWED_ORIGINS.
    origins = [None] + [o.strip() for o in os.environ.get("REFLECTIONS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    async with serve(relay.handle, "0.0.0.0", port, max_size=100_000, origins=origins, process_request=health,
                     ping_interval=20, ping_timeout=20):
        log.info("hosted NPC dialogue relay on port %d; %d saved replies; %s; %s", port, len(relay.cache),
                 relay.policy.summary(), relay.meter.summary())
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ValueError as exc:
        print(str(exc))
        sys.exit(2)
