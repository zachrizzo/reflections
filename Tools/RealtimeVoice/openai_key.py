"""Development only: the OpenAI key for the optional realtime mode (REFLECTIONS_NPC_MODE=realtime). The shipped
relay needs only the Gemini key; see api_keys.py, which holds the loading rules for both."""
from api_keys import default_key_file, load_keys  # noqa: F401


def load_api_key():
    return load_keys()["openai"]
