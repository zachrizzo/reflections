# Proposal: Gemini voices, client-side calls, and NPC actions (for the user to decide)

Status: research only. Nothing here is built yet, and the OpenAI path keeps working unchanged. Research date: 2026-11-14. `ai.google.dev/gemini-api/docs/*` now redirects to `aistudio.google.com/docs/*`; the links below are the pages that were read.

## Short answer

1. **Live replies in the shipped game: keep OpenAI `gpt-realtime-2.1`.** Google's Gemini API terms say you "must be 18 years of age or older to use the APIs" and bar use in an app "directed towards or is likely to be accessed by individuals under the age of 18" ([Gemini API terms](https://aistudio.google.com/docs/terms)). Our game is rated Teen (13+), so live Gemini calls from the shipped build are out. OpenAI allows serving teens with safeguards ([OpenAI under-18 API guidance](https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance)).
2. **Voice continuity favours OpenAI too.** Gemini's custom voices (voice design, cloning) exist only for its text-to-speech models, and Google staff say they are "not supported on gemini-3.8-live in the Gemini Developer API" ([forum, 2026-10-27](https://discuss.ai.google.dev/t/gemini-3-8-live-replicated-voice-config-is-accepted-but-ignored-on-the-gemini-developer-api-api-key/189199); on Vertex AI only "select customers" get it, per [Vertex live voice docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api/configure-language-voice)). So with 120 designed Gemini voices, a baked line would sound different from the same NPC's live reply. Today the audio session bakes the slot lines with the same `gpt-realtime-2.1` voices the live replies use (coral, sage, shimmer, ash, echo, verse), so they match.
3. **Gemini is still worth it offline, if the terms allow.** For baked ambient lines (many unique voices, cheap): Gemini 3.8 Flash TTS costs about $0.001 per 5 s line ([pricing](https://aistudio.google.com/docs/pricing)). But the same terms may cover baking lines that ship in a Teen game; whether they do is unclear and is the user's call. OpenAI TTS (what audio uses now) has no such issue.
4. **Decisions stay on OpenAI's small model** (`gpt-6-luna`): which saved reply fits, intent, choosing and checking NPC actions. It's fast enough (about 1.5 s), costs $0.10/$0.50 per 1M tokens, and supports structured output.
5. **NPC actions (tool calling): yes, as a whitelist.** Both providers support function calling in live sessions. The design below has the relay and the game each validate every call, so a model can never run a free-form action.

## 1. Gemini Live API (findings)

| Topic | Finding | Source |
|---|---|---|
| Models | `gemini-3.8-live` (current; the model card says Stable, the capabilities page still says the Live API is in preview), `gemini-3.8-live-extended-thinking`, legacy `gemini-3.1-flash-live-preview` | [models](https://aistudio.google.com/docs/models), [3.8 Live card](https://aistudio.google.com/docs/models/gemini-3.8-live), [capabilities](https://aistudio.google.com/docs/live-api/capabilities) |
| Audio | 16-bit PCM; 16 kHz in, 24 kHz out. Our capture would need resampling from 24 kHz to 16 kHz. | [capabilities](https://aistudio.google.com/docs/live-api/capabilities) |
| Sessions | About 10 minutes per connection (GoAway warning before it closes), 15 minutes per audio-only session without compression, resumption handles valid 2 hours | [session management](https://aistudio.google.com/docs/live-api/session-management) |
| Latency | No millisecond figure is published. VAD waits about 800 ms of silence by default; we use push-to-talk, so this doesn't apply. | [Live API](https://aistudio.google.com/docs/live-api) |
| Voices | 30 prebuilt voices, the same names as Gemini TTS (no promise they sound identical across models). Designed and cloned voices are TTS-only (Beta), 200 per project. | [speech generation](https://aistudio.google.com/docs/speech-generation), [voices API](https://aistudio.google.com/api-reference/voices) |
| Tools | Function calling in Live: synchronous by default, `NON_BLOCKING` for async; the client sends `toolResponse` | [Live tools](https://aistudio.google.com/docs/live-api/tools) |
| Price | Audio in $3/1M ($0.005/min), audio out $12/1M ($0.018/min): about **0.25¢ per spoken exchange**, versus about **1¢** for `gpt-realtime-2.1`. The context is billed again every turn. | [pricing](https://aistudio.google.com/docs/pricing), [forum](https://discuss.ai.google.dev/t/does-gemini-live-native-audio-bill-cumulative-prompt-tokens-on-every-turn-cost-seems-to-scale-with-turn-count-not-call-duration/173248) |
| Data | On the free tier, prompts are used to improve Google products and may be read by human reviewers. On paid, they aren't. | [terms](https://aistudio.google.com/docs/terms), [billing](https://aistudio.google.com/docs/billing) |

## 2. Calling the provider from the player's machine ("host it on their own machine")

The user's idea: no server of ours; the game calls the model provider directly. The voice models run at the provider either way. What changes is **where the API key lives**: it would ship inside the game.

- **A key in a Windows build can be extracted in minutes** with a strings or pak tool. Google's own guide says "Keys compiled in client-side code can be extracted by users" ([API keys](https://aistudio.google.com/docs/api-key)). Google key restrictions only cover HTTP referrers, IPs, Android and iOS apps; there's nothing for desktop apps ([Cloud API keys](https://docs.cloud.google.com/docs/authentication/api-keys)).
- **What actually limits the damage** is a hard spend stop on a dedicated project:
  - Gemini: AI Studio project spend caps, Prepay (a $0 balance stops keys with HTTP 402), or the Tier 1 $250/month cap. All have about 10 minutes of billing lag ([billing](https://aistudio.google.com/docs/billing)). Cloud budgets only alert and do not cap ([budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets)). Per-API quota caps exist but don't track spend ([capping](https://docs.cloud.google.com/apis/docs/capping-api-usage)).
  - OpenAI: a dedicated project, its own key and a project budget in the dashboard.
- **Ephemeral tokens** are the providers' answer for client-side use: Gemini `POST /v1beta/auth_tokens` (Live only, [ephemeral tokens](https://aistudio.google.com/docs/live-api/ephemeral-tokens)); OpenAI `POST /v1/realtime/client_secrets`, 10 minutes by default ([OpenAI client secrets](https://developers.openai.com/api/reference/resources/realtime/subresources/client_secrets/methods/create)). Both still need *a* server to mint them, so they don't remove the server.

**If the user accepts a key in the build**, the lowest-effort way that keeps everything already built (cache, decision model, reuse ratio, spend cap, moderation) is to **ship the relay as a small helper exe** (PyInstaller, about 15 MB). The game starts it on 127.0.0.1, as in the editor today. The key goes in, obfuscated, which only slows a determined person by minutes. Required with it:
1. A brand-new OpenAI project and key used only for this build, with a low monthly budget.
2. The relay's own per-install caps: the hosted defaults are $0.50/day per player and cache-only past the cap.
3. Revoking the key right after judging.
4. The cache generated during development ships as a starter cache, so even offline or over budget, NPCs can reuse real replies before falling back to barks.

The hosted relay (already written, see the README) stays the safer option: the key never leaves our server.

## 3. NPC actions (tool calling)

The live voice model (OpenAI or Gemini, both support function calling) may call **only** these functions. The relay checks each call against a strict schema and the NPC's kind, then sends `npc.action` to the game. The game checks it again against live state (distance, cooldowns, once-only flags, archetype permissions) and performs it through the unified NPC system. The result (`ok` or the reason it was refused) goes back to the model as the function output, so the NPC says what actually happened ("I can't leave my post"), never something that didn't.

| Action | Who may | Arguments (whitelisted) | Game effect (owner) | Limits |
|---|---|---|---|---|
| `follow_player` | civilians (Brave), guards | `seconds` ≤ 60 | NPC escorts the player. Needs a `Follow(Actor, Seconds)` order from NPC unify (today only `Engage` / `SetExternallySteered` exist). | one follower at a time; ends on combat or distance > 25 m |
| `stop_following` | anyone following | none | releases the order | none |
| `point_the_way` | civilians, guards | `target`: nearest_mirror_page, gilt_tower, nearest_shard, step_through_spot | the NPC turns and points; a short-lived marker on the HUD (game flow) | 1 per 20 s per NPC; uncollected targets only (world jump pickups) |
| `lead_to` | guards, Brave civilians | same targets | walks ahead to the target (needs navmesh; Lvl_HeroSampleCrowd has none, so this falls back to `point_the_way`) | 1 per NPC |
| `warn_guards` | civilians | none | `ReportStimulus(Alarm)` at the NPC; guards and the Brave come | 1 per 30 s globally |
| `flee` | civilians | none | runs from the player (needs a `Flee(From)` order from NPC unify, or a `Violence` stimulus at the player) | none |
| `heal_player` | NPCs tagged `NPC_Healer` (none exist yet) | `amount` ≤ 25 | `UReflectionsHealthComponent::Heal` on the hero | once per NPC per 2 min; standing ≥ neutral |
| `give_shard` | civilians, standing ≥ liked | `side` = the NPC's own side | `UReflectionsWorldLibrary::AwardCoin(side, 1)` | once per NPC per game; at most 3 per playthrough |
| `share_lore` | anyone | `topic` from a fixed list (sides, tarnish, shards, pages, final_spell, gilt_tower) | none: returns the canon text for the model to say, so it can't invent lore | none |
| `end_conversation` | anyone | none | the NPC turns away and resumes its routine | none |

Never allowed: anything that harms, moves the player, spawns, changes reputation directly, or isn't on the list. Hostile or Tarnished NPCs get only `share_lore` and `end_conversation`. Soldiers get `point_the_way`, `share_lore` and `end_conversation`.

**Without the live model** (no key or no network): typed lines go through the small decision model when it's reachable, else through a local keyword match ("follow", "stop", "where", "page", "tower", "heal", "shard"), to the same whitelist, with baked confirmation lines (about 3 per kind; to be baked by audio).

## 4. End-to-end design (proposal)

1. **Ambient (always, offline):** NPCs bark and chat from baked lines (audio session; per-NPC voice slot).
2. **Player walks up** (prompt appears): the session pre-opens to the relay, or to the local helper exe if client-side is chosen.
3. **Player speaks or types:** the reuse rule plus `gpt-6-luna` decide between a saved reply and a new `gpt-realtime-2.1` reply in that NPC's own voice slot. A function call becomes a validated action.
4. **No key, no network, or over budget:** saved replies first (cache-first), then baked barks. Actions via local keyword intents.

| Job | Model | Why |
|---|---|---|
| Live spoken replies | OpenAI `gpt-realtime-2.1` (or `-mini` for about a third of the cost) | Allowed for Teen with safeguards; same voices as the baked slot lines; already working |
| Player speech to text | OpenAI `gpt-live-transcribe` | Transcript ready about 0.5 s after release |
| Reuse decision, intent, action choice and checks | OpenAI `gpt-6-luna` | About 1.5 s, cheapest, structured output |
| Baked ambient lines | OpenAI TTS (current), or Gemini 3.8 Flash TTS if the user clears the under-18 terms | Gemini is cheaper and offers many designed voices, but live replies won't match those voices |
| Moderation of saved replies | `omni-moderation-latest` | Free |

**Decisions needed from the user:**
- (a) Ship live AI to judges at all, and if so how: the hosted relay (safest), a helper exe with a key in the build (accepting the extraction risk), or none (barks only).
- (b) Gemini for baked lines, given the under-18 terms.
- (c) Which NPC actions to build first. Suggested: `point_the_way`, `share_lore`, `warn_guards`, `end_conversation` (no new NPC-system orders needed); then `follow_player` and `give_shard`.

Effort for (c), first four actions: about 3–4 hours (relay tool schema and validation, game-side executor, tests). `follow_player` and `flee` also need new orders from NPC unify.
