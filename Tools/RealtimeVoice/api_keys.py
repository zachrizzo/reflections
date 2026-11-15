"""Loads API keys for a relay process. Keys never leave this process: nothing here prints, logs or returns them
anywhere except to the caller.

The shipped pipeline needs only the Gemini key. The packaged helper (and any run with --keys) reads ONLY its
keys.json ({"gemini_api_key": "..."}, next to the exe): never the environment or home-folder files, so a player
who happens to have their own GEMINI_API_KEY set is never billed, and a broken keys.json means baked lines, not a
silent switch to someone else's key. Development runs without --keys: GEMINI_API_KEY, else
REFLECTIONS_GEMINI_KEY_FILE, else ~/.gemini/api_key.
OpenAI (development only: the optional realtime mode and old live checks): OPENAI_API_KEY, else "openai_api_key"
in keys.json, else REFLECTIONS_OPENAI_KEY_FILE, else ~/.openai/api_key.
"""
import json
import os


def default_key_file():
    return os.path.join(os.path.expanduser("~"), ".openai", "api_key")


def _read_first_line(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.readline().strip()
    except OSError:
        return ""


def _keys_json(path):
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8-sig") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_keys(keys_file=None, only_file=False):
    """{'gemini': str, 'openai': str}; empty strings for keys that are not configured. only_file: keys_file alone."""
    data = _keys_json(keys_file)
    if only_file:
        return {"gemini": str(data.get("gemini_api_key", "")).strip(),
                "openai": str(data.get("openai_api_key", "")).strip()}
    gemini = (os.environ.get("GEMINI_API_KEY", "").strip() or str(data.get("gemini_api_key", "")).strip()
              or _read_first_line(os.environ.get("REFLECTIONS_GEMINI_KEY_FILE")
                                  or os.path.join(os.path.expanduser("~"), ".gemini", "api_key")))
    openai = (os.environ.get("OPENAI_API_KEY", "").strip() or str(data.get("openai_api_key", "")).strip()
              or _read_first_line(os.environ.get("REFLECTIONS_OPENAI_KEY_FILE") or default_key_file()))
    return {"gemini": gemini, "openai": openai}
