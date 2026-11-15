# Gemini voices for Lanthorne's streets: research and plan

Status: **plan only, nothing bulk-generated.** The Gemini project's prepaid credit ran out during the tests (see Blocker).

## 1. What the Gemini API offers (read 2026-11-14)

Sources: [Speech generation guide](https://aistudio.google.com/docs/speech-generation), [Voice design](https://aistudio.google.com/docs/voice-design), [Gemini 3.8 Flash TTS model page](https://aistudio.google.com/docs/models/gemini-3.8-flash-tts), [Pricing](https://aistudio.google.com/docs/pricing), [Rate limits](https://aistudio.google.com/docs/rate-limits), [Gemini API Additional Terms](https://aistudio.google.com/docs/terms).

**Models.** `gemini-3.8-flash-tts` is the best acting and dialogue model; `gemini-3.8-flash-lite-tts` is the cheaper bulk model. Both use the same schema (Interactions API, `POST /v1beta/interactions`). The text is read verbatim. Delivery goes in `speech_metadata.style` (e.g. "hushed, gossiping"), and inline tags such as `<short pause>`, `<laugh>`, `<sigh>` or `|hmm|` backchannels can go in the text.

**Voice variety: how close to "a unique voice per NPC" we can get.**
- **30 prebuilt studio voices**, multilingual.
- **Extended Voice Library:** prebuilt voices by locale (`GET /v1beta/voices?languageCode=…`). Measured: 117 en-GB and about 200 en-US. They are "professional" personas (Tutor, Concierge, Podcaster, Storyteller, Call Center Agent…), so the timbres vary but none sounds like a street character.
- **Voice design:** `POST /v1beta/voices` with `type: "prompted"`, `gender` and `language_code`, plus a 1–2 sentence description of age, timbre, texture and accent. It returns a persistent `voice_…` id and a preview clip. **This is the "infinite voices" feature, with a cap: 200 stored voices per project**, each kept for 1 year from last use. Google says to put permanent traits (age, gender, timbre, accent) in the design, not in the per-line style, or the voice drifts.
- So "unique per NPC" is realistic up to roughly 190 designed voices, plus library voices if more are needed.

**Multi-speaker in one call:** up to **2 speakers, and only with prebuilt or library voices**. Designed voices must be synthesized one turn at a time, then joined. For the game that's what we want anyway: each line has to come out of a different NPC's head, so every turn is its own wave.

**Output:** unary calls return WAV, 24 kHz mono 16-bit PCM; streaming returns raw PCM.

**Pricing (paid tier, through 2026-12-31):** Flash TTS costs $9 per 1M audio tokens (25 tokens per second of audio), about **$0.00225 per 10 s**. Flash-Lite is about $0.0015 per 10 s. Text input is $0.50 per 1M tokens. On the free tier Google may use prompts and audio to improve its products, including human review.

**Rate limits:** per project. Current values appear only in AI Studio; the docs tables don't list the 3.8 TTS models yet. We'll learn them from 429 responses and throttle.

**Terms that matter:**
- Google claims no ownership of generated content, and may generate similar content for others.
- **"You must be 18 years of age or older to use the APIs. You also will not use the Services as part of a … application … likely to be accessed by individuals under the age of 18."** The jam requires a Teen (13+) rating. Baked audio files are just generated content we own, but **calling Gemini live from the shipped game would make the game an API client, which these terms forbid for a Teen audience.** Live calls would also mean shipping a key or running a relay server.
- The Prohibited Use Policy applies, and voice replication needs consent (not planned).

## 1b. Google's prompting rules for voices (what we follow)

From [Voice design: prompting best practices](https://aistudio.google.com/docs/voice-design#prompting-best-practices-for-voice-design), [TTS prompting guide](https://aistudio.google.com/docs/speech-generation#prompting-guide) and [Voice remixing](https://aistudio.google.com/docs/voice-remixing):

1. **Fixed traits go in the voice design**, not the per-line style: age, gender, timbre, vocal texture, regional accent. Putting age, gender, names or a permanent accent in `style` causes drift.
2. **Descriptions should be specific and not contradictory.** Google: "A clear 1–2 sentence description … produces cleaner, more consistent results than contradictory or overly long paragraphs." Their example: "A crisp, energetic sports announcer in her 30s with a slight Midwestern accent."
3. **The text is a verbatim transcript.** Delivery goes in `speech_metadata.style` as a short turn-level string ("hushed, gossiping", "speaking slowly", "out of breath"). Momentary sounds go inline in angle brackets: `<sigh>`, `<laugh>`, `<breath>`, `<cough>`, `<short pause>`, `<long pause>`.
4. **Pacing** comes from punctuation, dashes and ellipses, `<short pause>` / `<long pause>`, or a style such as "speaking rapidly". **Emphasis** comes from CAPITALISING the stressed word. **Pitch and prosody** come from style ("high pitch, excited", "monotone and flat").
5. **Anti-patterns:** long "Audio Profile" or "Director's Notes" paragraphs (the most common cause of drift), meta-instructions such as "keep the same timbre", and changing permanent traits in style.
6. **Workflow:** design the character once, test with an empty style first, then add short style strings only where needed, reusing the same short string for a consistent baseline. Write natural transcripts with small disfluencies. In two-speaker calls, `|reaction|` inside a turn adds a backchannel.

**How we apply this:** each voice gets a rich, specific brief (the user asked for detailed prompts). It is dense and free of contradictions, covering age and sex, region and class, timbre and pitch, texture, pace and rhythm, baseline emotion, one quirk, and occupation and personality. The pilot A/B tests the rich brief against Google's 1–2 sentence style on the same characters, and the winner is used for all 120. Fear-versus-calm behaviour lives in the per-line `style` field, not the brief. Every line gets its own short style string, CAPS for emphasis, and pause tags where they help.

## 2. Tests run (3 calls)

| # | Test | Result |
|---|---|---|
| 1 | Voice design: "A wiry old lamplighter in his seventies from a misty harbour city: gravelly, slightly wheezy, wry and unhurried, with a soft working-class British accent." (male, en-GB) | ✅ Created `voice_lws20oio2mq7` in 23 s. The preview is a 52 s **improvised in-character monologue** (lamps, gas, "cup of tea"), so design produces a whole character, not just a timbre. |
| 2 | That voice speaking a street line with `<short pause>` | ❌ HTTP 402 "prepayment credits are depleted" |
| 3 | 2-speaker exchange with two en-GB library voices, `|hmm|` and `<laugh>` | ❌ HTTP 402 (same) |

Also found: the project already holds **8 stored "Night Narrator" voices**, made at about 19:27–19:29 UTC today by someone else. With my lamplighter, 9 of the 200 slots are in use.

## 3. Proposed plan (needs your go-ahead and a credit top-up)

**Voices: 120 designed voices, 60 female and 60 male** (about 130 of 200 slots, leaving room for the Night Narrator owner and the villain or narrator).
- Ages 18 to 80; varied timbre (breathy, nasal, gravelly, bright, booming); a range of British-flavoured accents.
- About 40 per side, matched to its mood. Pewterside: tired, everyday, rain and work. Giltside: warm and bright, guards, soldiers, festival trade. Frostside: hoarse, cold, wary, starving.
- Each roster entry records: `VoiceId` (V001…V120), Gemini `voice_…` id, sex, age band, side, archetype fit (civilian, guard, soldier, tarnished, vendor…), a one-line persona, and the description prompt (for the AI declaration).

**Fixed voice per NPC.** NPC unify's voice profile extends from 3 slots per sex to the roster. An NPC's `VoiceId` is fixed when it spawns (e.g. least-used voice of its sex and side, then a hash of the actor name), and it's saved, so its ambient lines, barks and any later reply all use the same voice. The live dialogue relay can call TTS with the same `voice_…` id in development builds.

**Content (written by me in canon, from `canon.md`; never "London", no book names, Teen-safe):**
- **About 240 ambient conversations,** 2–4 speakers and 2–6 lines each, tagged by side and location type (market, gate, tavern, bridge, tower), with the archetypes they need. Topics are city life plus rumours of the Tarnish, the burning eyes, mirror shards, people stepping through, and the Gilt Tower. Conversations can't be baked for every pair of voices, so the voices are grouped into **cliques of 2–4** who are placed together. About 60 cliques with about 4 conversations each gives 240.
- **Passing remarks:** 2 one-liners per voice (240) for NPCs walking alone.
- **Interaction replies:** 3 per voice (360) for when the player talks to someone, baked so the shipped game never calls an API.
- **Barks** (fear, alert, attack, commands) stay as they are from OpenAI, or can be re-voiced per roster voice later if wanted.

**Engine side.** One wave per line, `/Game/Audio/Jam/Voice/Ambient/<Clique>/SW_AMB_<ConvId>_<n>`, played from each speaker's head with `ATT_Jam_NPCVoice`. The manifest is a DataTable plus JSON at `/Game/Audio/Jam/Voice/Ambient/DT_AmbientConversations`. Each row holds the side, the cliques' `VoiceId`s, and the lines (speaker, wave, subtitle, length, gap). Who drives it: NPC unify, or the crowd session, runs the "nearby clique → pick unplayed conversation → play line by line from the right heads" director.

**Size and time:**

| | Estimate |
|---|---|
| Lines | about 1,000 conversation lines + 240 remarks + 360 replies = **about 1,600 lines, about 75 min of audio** |
| Packaged size | mono 24 kHz, compressed: **about 15–30 MB** (well inside the ~270 MB headroom) |
| Editor source | about 210 MB of PCM WAV in `Content/` (not shipped) |
| Cost | lines about $1 (Flash) + 120 voice designs about $1.5 (preview audio) + retries → **under $5** |
| Generation time | about 45 min to design voices, about 1.5–2 h to synthesize and check (3–4 requests in parallel, depending on rate limits). All of it is checked with speech-to-text, and names are spoken phonetically. |

## 4. Decisions needed

1. **Top up the Gemini prepaid credit** (AI Studio → project → billing). About $5–10 covers everything. This is the user's purchase, and nothing more runs until then.
2. **No live Gemini calls in the shipped game** (Google's under-18 terms and key exposure). Use the baked interaction replies, with live only in development builds through a local relay. Agree?
3. **Who owns the 8 "Night Narrator" voices,** so we don't collide on the 200-voice cap?
4. **Scope:** 120 voices and about 240 conversations as above, or smaller? For example, 60 voices and 120 conversations halves time and size.
