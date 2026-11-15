# NPC dialogue relay

The relay behind NPC talk-back. Design, costs, hosting options and status: [ArtDirection/NpcDialogue/README.md](../../ArtDirection/NpcDialogue/README.md).

- Install: `python -m pip install -r requirements.txt` (websockets, httpx).
- Gemini only: one Gemini API key (`GEMINI_API_KEY`, `keys.json` next to the helper exe, or `~/.gemini/api_key`). Hearing `gemini.py` (gemini-3.5-transcribe-live), replies and moderation `gemini.py` (gemini-3.5-flash-lite), speech `tts.py` (gemini-3.8-flash-tts, the NPC's designed voice), session flow `pipeline.py`. OpenAI (`decider.py`, `openai_key.py`, `REFLECTIONS_NPC_MODE=realtime`) is development only and never used by the shipped path.
- Local relay for Play in Editor: `.\Start-NpcDialogueRelay.ps1` (`-Foreground` to watch it, `-Stop` to stop). It reads the key itself, listens on 127.0.0.1:8765, and writes a per-launch token to `Saved/NpcDialogue/relay.token` for the editor. Cache, stats and log: `Saved/NpcDialogue/`.
- Models this key can use: `python relay.py --list-models`.
- Packaged helper: `.\Build-NpcDialogueHelper.ps1`, then copy `dist\NpcDialogueRelay` to `Content\NpcDialogue\Relay` (never with a keys.json).
- Tests: `python -m unittest -v test_relay` (mocked, no network); `python live_check.py` (real Gemini API, about 2 cents: normal talk, a spoken line, a cache repeat and the four guardrail lines, with latency and cost per turn); `python run_pie_locked.py test_npc_dialogue_pie.py` (PIE, through the editor MCP, under the PIE lock).
- Hosted relay (not deployed; needs approval): `hosted_relay.py`, `Dockerfile`, `fly.toml`.

Never package this folder, a token or a key with the game.
