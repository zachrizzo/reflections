# AI use and pre-jam declaration

**What the rules ask** ([rules.md](rules.md)):
- **Sourced (non-original) assets must be listed** with the submission (rules 1(d) and 15(c)). AI-generated content doesn't count as sourced.
- **Anything made before Nov 12 must be declared** (jam page; rule 7(h)).
- An AI-use statement is **optional**: "Tools you used" is needed only for partner prizes. Judges treat AI use as context and don't score it.

Declaring generously costs nothing and protects the entry.

This was compiled on 2026-11-14 (≈10:50 MST) from every README in `ArtDirection/`, the scripts in `Tools/` and `ArtDirection/**`, the side-session hand-over notes, `reflections.uproject`, file timestamps, and C2PA metadata in the images. Each row says whether it's verified, and [Can't verify](#cant-verify) lists what isn't. ElevenLabs is fixed at 6 cues. **Updated 11-14 ~18:40 for the user's Gemini-only decision:** live NPC replies use Google Gemini only, the baked crowd and story voices are Gemini designed voices, and OpenAI is no longer called at runtime. **Re-check this on Sunday** against the final build.

## Short form for the itch page

> **Made with AI agents, directed by [team].** Code was written by Claude Code (Anthropic) and OpenAI Codex agents working in parallel. Concept art and wardrobe references came from OpenAI image generation (gpt-image), and some garment meshes were turned into 3D with Hunyuan3D-2 (Tencent). Spell-casting and gesture animations were generated with NVIDIA Kimodo text-to-motion. Characters were built in Epic's MetaHuman Creator from Epic presets. **Character voices are AI-generated and not performed by human actors.** More than 3,200 lines are spoken by over 130 voices designed with Google Gemini (Gemini 3.8 Flash TTS). The Tarnish, the narrator and the original crowd barks use OpenAI voice models (gpt-realtime-2.1, with gpt-4o-mini-tts as a fallback). All of these lines are baked into audio files. **Talking to people can use live AI:** with a Google Gemini API key, gemini-3.5-transcribe-live hears what you say, gemini-3.5-flash-lite writes the reply, and gemini-3.8-flash-tts speaks it in that person's designed voice. Without a key, people answer with recorded lines. Six sounds (the three world music loops, fire cast and impact, water impact) were generated with ElevenLabs; the other sound effects are procedural synthesis written by the agents. Built on Epic's Game Animation Sample and Third Person template; full sourced-asset list below.

**"Tools you used" field (submission form):** Unreal Engine 5.9, Claude Code (Anthropic), OpenAI Codex, OpenAI gpt-image, Google Gemini (voice design and gemini-3.8-flash-tts voices; gemini-3.5-flash-lite and gemini-3.5-transcribe-live for live NPC replies), OpenAI gpt-realtime-2.1 and gpt-4o-mini-tts (the Tarnish and narrator voices), OpenAI gpt-4o-transcribe (word-for-word check of every baked line), Hunyuan3D-2, NVIDIA Kimodo, ElevenLabs, MetaHuman Creator, Blender (scripted), Python/numpy. No Rodin, Meshy, Tripo, fal or PBRgen, so those partner prizes don't apply.

**OpenAI question (optional; makes the entry eligible for the OpenAI Award):** OpenAI Codex wrote the NPC and enemy combat code and, judging by its logs, most of the day-one wardrobe, MetaHuman and animation set-up. gpt-image produced all 51 concept and wardrobe images, some of which became in-game garment textures and meshes. **The Tarnish, the narrator and the original crowd barks were voiced with OpenAI**: 123 lines baked offline from a written script, 115 with `gpt-realtime-2.1` and 8 with `gpt-4o-mini-tts` as the fallback. **OpenAI also checked every baked voice line in the game**, the 3,200+ Gemini lines included: each take was transcribed with `gpt-4o-transcribe` and kept only if it matched the script word for word. OpenAI isn't called while the game runs. Live NPC replies use Google Gemini, so don't claim them here. The spell-recipe relay (`gpt-5-mini`) never made a live call, so don't claim it either.

**Required disclosure:** OpenAI's usage policies require telling players that a TTS voice is AI-generated and not a human. That's covered by the short form above (itch page) and the credits block below (in game). Keep both lines. The Gemini voices get the same treatment. For live replies, the game also shows this notice the first time you talk (checked in `Voice/ReflectionsVoiceInteractionSubsystem.cpp:223`): "NPC voices are AI-generated (Google Gemini). What you say to them is sent to Google to make their reply." Each live reply carries an "AI VOICE" tag. The itch page has a matching [privacy note](itch-page.md#privacy-talking-to-people).

## Which AI tools made what

| Tool | What it made | What ships in the game | Evidence | Verified? |
| --- | --- | --- | --- | --- |
| **Claude Code** (Anthropic), several parallel side sessions | Spell aiming and combat rebuild, spell VFX (Niagara and materials, built by script), spell crafting, world jump with shards and pages, jam audio pipeline and procedural sounds, cloak fix, packaging config, villain/finale and game flow/menus (in progress), all the `ArtDirection/*` docs including this kit | All of that code and content | Hand-over notes in the shared notes folder (`spell-rebuild-findings.md`, `jam-audio.md`, `world-jump-notes.md`, `spell-crafting-notes.md`, `hero-cloak-findings.md`, `packaging-findings.md`) | **Partly**. Areas are verified from the notes. The model per session isn't recorded, and the 11-13 C++ in `Crowd/`, `Hero/` (character and cloth tools), `NPC/` reactions and `Voice/` isn't attributed in any file. |
| **OpenAI Codex** (coding agent) | NPC and enemy combat (`Source/reflections/NPC/ReflectionsNpcCombatComponent.*`, `Tools/NpcCombat/*`). Going by its logs, also the 11-13 image generation, MetaHuman, Hunyuan and first Kimodo work. | Combat code; those assets | 20 Codex sessions in `~/.codex/sessions/2026/11/13-14` with this repo as cwd, the first at 11-13 14:06. Ownership notes in `Audio/README.md` and `Packaging/README.md`. | **Partly**. Use is confirmed; the per-file split isn't. |
| **OpenAI image generation** (gpt-image, via Codex/ChatGPT) | **51 images**: 10 concept pieces (`Three-Londons/`), 10 photoreal versions (`Three-Londons-Realistic/`), 31 wardrobe lineups and garment references (`Three-Londons-Wardrobe/**`) | **Yes**: garment colour atlases for the Red-world NPCs (`Red London/SimpleOutfits/`), and the inputs to the Hunyuan meshes | Prompts in each folder's `prompts.md`. All 51 PNGs carry C2PA metadata naming OpenAI / ChatGPT / gpt-image. | **Yes** (model version unnamed) |
| **Hunyuan3D-2** (Tencent, image-to-3D, run locally) | Meshes from those images: the hero's boots, shirt and trouser folds and the old mantle; the tunic, trousers and boots of 4 Red-world NPCs; an Iven test mesh | **Yes**: fitted derivatives on the hero (`Hero/TravelCloak/*_Generated*`) and in `/Game/Characters/CrowdMotion/SimpleRed` | `Hero/TravelCloak/README.md:5,13,17`, `Red London/SimpleOutfits/README.md:3`, `Intermediate/IvenRook/IvenGenerated.json` (`"provider": "local Hunyuan3D-2"`) | **Partly**. Recorded in JSON and READMEs; no install found and the GLB headers say only "trimesh". |
| **NVIDIA Kimodo** text-to-motion (Epic's experimental plugin; model `nvidia/Kimodo-SOMA-RP-v1.1` with a Llama-3-8B-based text encoder) | 16 spell casts, 7 combat casts, 5 spell-crafting gestures, V2/V3 cast variants, an explosion cast, Iven showcase clips, test clips | **Yes**: the baked `AS_Hero_*` animations, retargeted with `RTG_SomaToHero`. The model itself is editor-only. | Prompts and seeds in `Tools/SpellVFX/author_distinct_casts.py`, `author_combat_casts.py`, `Tools/SpellCrafting/author_cast_gestures.py`; `Spell-Animation-Audit/README.md`. Weights in the Hugging Face cache, downloaded 11-13. | **Yes** |
| **ElevenLabs** (Sound Effects v2, Music v2.5; free tier) | **6 cues, final**: `MUS_Gray_Loop`, `MUS_Red_Loop`, `MUS_White_Loop`, `Fire_Cast`, `Fire_Impact`, `Water_Impact`. The team decided on 11-14 that ElevenLabs stays at these six. | **Yes** | `ArtDirection/Audio/README.md` (prompt per sound); 6 generation IDs in the audio session's `raw/manifest.json` | **Yes** |
| **Google Gemini voice design and TTS** (`gemini-3.8-flash-tts`; paid tier, going by the prepaid credit in audio's notes) | **The crowd, the named people, Wren and the story lines.** Gemini Voice design made one voice per character from a written brief (`ArtDirection/Audio/data/voice_roster.json`; audio's README counts 137 voices). Audio reports **3,242 lines** synthesized offline in those voices, each kept only if an OpenAI `gpt-4o-transcribe` transcript matched the script word for word. | **Yes**, as WAVs under `/Game/Audio/Jam/Voice/{Ambient,Roster,Story}`. The baked lines make no API calls. | `ArtDirection/Audio/README.md:10`, `AmbientScript.md`, `jam-audio.md` in the shared notes | **Partly.** I counted **3,312** waves in those three folders on disk; audio's note says 3,242 lines. The gap may be shared takes or retakes not yet cleaned up. Audio should confirm the number. |
| **OpenAI voice models** (`gpt-realtime-2.1`, with `gpt-4o-mini-tts` as fallback) | **123 lines**: the Tarnish (19 combat lines plus its 16 story lines, on its `cedar` voice), 10 narrator lines and the original crowd barks (`Civilian_*`, `Guard_*`, `Soldier_*`, `Tarnished_Mutter`). **115 are `gpt-realtime-2.1` and 8 are `gpt-4o-mini-tts`**, each a fallback after realtime failed the word check. Baked offline and checked with `gpt-4o-transcribe` against `ArtDirection/Audio/VoiceScript.md`. | **Yes**, as WAVs. Nothing calls OpenAI at runtime, and no key ships. | `VoiceScript.md` (model, voice, prompt and STT result per line); `ArtDirection/Audio/README.md:9` | **Yes.** I counted 107 waves in the slot and narrator folders and 16 in `Story_Tarnish`. Whether the old crowd barks still play now that most people have Gemini voices is audio's call; if they're deleted, the OpenAI voice credit narrows to the Tarnish and the narrator. |
| **OpenAI `gpt-4o-transcribe`** (dev only) | Nothing that ships. It transcribed every baked take, Gemini and OpenAI alike, for the word-for-word check. | No | `ArtDirection/Audio/README.md:9-10` | **Yes** |
| **Epic MetaHuman Creator** | 8 characters from Epic presets: Hero ← Mateo, IvenRook ← Mikel, CoinClerk ← Lorenzo, ArchiveApprentice ← Aoi, FestivalDrummer ← Zuri, FerryPilot ← Dominic, BridgeGuard ← Ada, GlassArtisan ← (preset not found); 36 crowd recolours | **Yes** | `Intermediate/*/assemble*.py`, `build_hero.py`; `MHC_*` written 11-13 18:03–19:42 | **Yes**. Whether to call it "AI" is the team's call. Listing it is harmless. |
| **Epic editor AI toolsets / MCP** | The channel agents used to drive the editor and build Niagara and material assets by script | No content of its own | `reflections.uproject` (editor-only), `Tools/SpellVFX/ue_mcp.py` | **Partly**. Whether Epic's in-editor assistant was asked anything can't be told from files. |
| **OpenAI API at runtime, spell recipes** (dev only): `gpt-5-mini` | Nothing. A dev prototype that **never made a live call**. | Code ships but stays inert: without the local relay's token, crafting uses its offline parser. | `Tools/SpellCrafting/recipe_relay.py`, `SpellCrafting/README.md:228` | Code **yes**; live use **no** |
| **Google Gemini API at runtime, NPC talk-back** (NPC dialogue session; **Gemini only** since 11-14 18:15, the user's decision): `gemini-3.5-transcribe-live` hears the player (Live API, push-to-talk), one `gemini-3.5-flash-lite` call writes the reply and picks a safe action, a second `gemini-3.5-flash-lite` call moderates it, and `gemini-3.8-flash-tts` speaks it in the NPC's designed voice | Live NPC replies. They run **only when a Gemini key is in `keys.json`** next to the bundled helper (`Content/NpcDialogue/Relay/NpcDialogueRelay.exe`). The build ships only `keys.json.example`. **Sent to Google:** the player's speech (while T is held) or typed line, the NPC's facts and recent conversation, and the reply text for speech and moderation. Replies are saved on the player's PC with the text of the line that prompted them, and some are reused. Player audio isn't kept. | The helper and its code ship. Without a key, people answer with baked lines and the talk feature makes no network calls. In game: on first use, the notice "NPC voices are AI-generated (Google Gemini). What you say to them is sent to Google to make their reply."; an "AI VOICE" tag on each reply. OpenAI code (`decider.py`, `openai_key.py`, realtime mode) is dev-only and never on the shipped path. | `ArtDirection/NpcDialogue/README.md` (§ Shipping, § Privacy and AI disclosure), `npc-dialogue.md` in the shared notes, `Tools/RealtimeVoice/*` | **Partly.** I checked the notice text in code and that `Content/NpcDialogue/Relay/` holds no `keys.json`. The model names and the send/store list come from the NPC dialogue session's README and notes. |

**Not AI** (agent-written code that generates content): 39 procedural audio stand-ins (`ArtDirection/Audio/tools/synth*.py`), headless Blender garment fitting (`fit_*.py`), and spell names and looks from seeded word lists.

## Sourced and pre-jam material

Paste this list into the submission's **sourced assets** field. Sourced assets aren't judged (rule 15(c)).

| Item | Where | Source | Before the jam? | Ships? |
| --- | --- | --- | --- | --- |
| **Unreal Engine Third Person template**, plus its Combat, Platforming and SideScrolling variants | `Content/ThirdPerson`, `Content/Variant_*`, `Source/reflections/Variant_*`, `reflections{Character,GameMode,PlayerController}.*` | Epic template | Created 11-13 14:05 and unchanged since | Partly (template code) |
| **Epic Game Animation Sample (GASP)**: sandbox character, motion-matching animations, traversal, smart objects, mannequins (UE4, UE5, UEFN), Echo, Paragon TwinBlast, MetaHuman Kellan, prototype level blocks, foley | `Content/Blueprints/*`, `Content/Characters/{UEFN_Mannequin,UE5_Mannequins,UE4_Mannequin,Echo,Paragon}`, `Content/MetaHumans/Kellan`, `Content/Levels/LevelPrototyping`, `Content/Audio/Foley` | Epic sample content, copied in from the team's earlier project `action_fighting_UE59` | **Yes**: files dated from 2026-09-05 | Yes: hero locomotion and the UEFN mannequin animations |
| **Start map built from GASP's sandbox level** | `/Game/Characters/Hero/Sample/Lvl_HeroSampleCrowd` (a copy of `Lvl_HeroSampleSandbox`), `GM_HeroSample`, `BP_HeroSample*` | Epic sample level, with jam additions | The level is Epic's; the additions are jam work | **Yes, as the start map today**. See the note below. |
| **Advanced Locomotion System V4** | `Content/AdvancedLocomotionV4` | Third-party (usually a free Fab pack). **Confirm the source and licence.** | Yes (files from 2025-02-15) | Unknown. Check the pak listing, and remove it if unused. |
| **The team's own earlier gameplay Blueprints and input** (AI, health, melee and weapons, squad commands) | `Content/Blueprints/{AI,Humans,Combat}`, `IA_Shoot`, `IA_Reload`, `IA_CycleWeapon`, `IA_Squad*`, `IA_WarMap`, `IMC_Sandbox` | The team's project `action_fighting_UE59` | **Yes**: 2026-09-24 → 11-08 | Mostly **no** (not cooked). But `IMC_Sandbox` and `IA_Reload` are live in-game input. |
| **The team's own earlier VFX**: blood impact, explosion, missile trail and ground fire (Niagara, materials, textures) | `Content/Blueprints/Combat/{Blood,Explosives}` | Copied from `action_fighting_UE59` by `ArtDirection/SpellVFX/migrate.py` | **Yes**: made 2026-09-30 → 10-08 | **Blood: yes** (always-cooked, used on flesh hits) |
| **Epic MetaHuman presets and grooms** | MetaHuman Creator optional content (Mateo, Mikel, Lorenzo, Aoi, Zuri, Dominic, Ada; BobCurly hair) | Epic | Engine content | Yes, as the base of every character |
| Engine plugin content used only by tools | Kimodo's Soma skeleton, MetaHuman Crowd template | Epic plugins | — | No (never cooked) |
| **Gray London map**: street, building and river geometry | `Content/GrayLondon`, `__ExternalActors__/GrayLondon` | **OpenStreetMap** (Geofabrik extracts), ODbL 1.0. Generated by Jah's pipeline. | Data: yes (it's OSM). The map itself: dated 11-13 and 11-14. **Jah to confirm the source project started on or after Nov 12.** | Yes, once it's the main map |
| **Landmark models** in that map: Buckingham Palace, Tower of London, Tower Bridge, St Paul's, Westminster, London Eye, Westminster Abbey, 30 St Mary Axe, Albert Bridge, Royal Albert Hall, National Theatre | `Content/GrayLondon/Geodata/Landmarks` | **Codriver 3D**, CC BY 4.0, adapted | Third-party | Yes |
| **Albert Memorial scan** | `Content/GrayLondon/External/AlbertMemorialReducedReview_20261114` | **artfletch** (Zenodo), CC BY 4.0, reduced | Third-party | Yes |
| **Street props** (postboxes, bins, bollards, railings) | `Content/Fab/London_Street_Props__Free_`, `Geodata/Props` | **Minimaliano**, Fab, *London Street Props (Free)*. The docs say CC BY 4.0; the Fab page shows no licence. | Third-party | Yes |
| **Poly Haven** textures and props; a lion scan; the Cosmo Tree Gen tree; Noto Serif lettering in sign textures | Various, in `Content/GrayLondon` | Poly Haven (CC0); danielpett (CC0); FrogCosmonaut (MIT tool, CC0 textures); Google Fonts (OFL) | Third-party | Yes |
| Tools and agent set-up (allowed before the jam, rule 7(h)) | `BuildConfiguration.xml` (2026-02-11), Codex and Claude configs and skills | Team | Yes | No |

No C++ came from the earlier project: every `.cpp` and `.h` was hash-checked against `action_fighting_UE59` and none matched.

### Fix or decide before submitting

1. **The start map is Epic's GASP sandbox.** If it's still the default map on Sunday, judges see a sample level, and Level Design is a scored criterion. The world-jump map with Pewterside, Giltside and Frostside anchors should become `GameDefaultMap` (packaging and world-jump). Either way, the sandbox origin is declared above.
2. **The blood VFX is pre-jam content that ships.** Declare it (it's in the table), or swap it for a jam-made hit effect. Spells could own that swap.
3. ~~`Sword_Hit` contained GASP foley~~. **Fixed 11-14 at 10:57.** Audio re-imported `SW_Sword_Hit_01..03` as fully synthesized sound; I checked, and no `/Game/Audio/Jam` asset references `foley_punch` any more. `/Game/Audio/Jam` is now 6 ElevenLabs cues plus 39 procedural ones. The GASP foley still sits in `Content/Audio/Foley` as sample content, but no jam sound uses it.
4. **Keep the concept art off the itch page and out of the dev log.** It carries the old names, its C2PA metadata marks it as AI-made, and the hero coat prompt names the book.

## Credits block (the source for the itch page and game-flow-ui's Credits/Victory panel)

**This block is the source of truth.** The in-game panel (`/Game/UI/ST_GameFlowText`, keys `Credits.*`) should match it word for word. Revised 2026-11-14 ~13:00:
- the ElevenLabs free-tier attribution ("elevenlabs.io", "Eleven Music") is added;
- the Kimodo model and licence notice are given exactly;
- the voice line is written for what ships.

Revised again ~18:40 for Gemini only: the voice line now names Google Gemini first, and a live NPC replies line is added. Both were sent to game-flow-ui as the new `Credits.Tools`.

```
REFLECTIONS
A 2026 Epic AI MegaJam entry by [Team name]
[Member — role] · [Member — role] · …

Directed by [team]; built with AI agents
Code: Claude Code (Anthropic), OpenAI Codex
Wardrobe textures and references: OpenAI image generation
3D garments: Tencent Hunyuan3D-2 (Powered by Tencent Hunyuan)
Spell animations: NVIDIA Kimodo text-to-motion (Kimodo-SOMA-RP-v1.1, licensed by NVIDIA Corporation under the NVIDIA Open Model License)
Characters: Epic MetaHuman Creator
Character voices: AI-generated with Google Gemini (designed voices, Gemini 3.8 Flash TTS) and OpenAI (gpt-realtime-2.1, gpt-4o-mini-tts), not human actors
Live NPC replies: Google Gemini (gemini-3.5-transcribe-live, gemini-3.5-flash-lite, gemini-3.8-flash-tts). What you say to NPCs is sent to Google.
Music: Eleven Music by ElevenLabs (elevenlabs.io)
Fire and water spell sounds: ElevenLabs (elevenlabs.io); all other sounds procedurally synthesized
Built on Epic's Game Animation Sample and Third Person template
Map data © OpenStreetMap contributors, ODbL (openstreetmap.org/copyright)
Landmark models adapted from Codriver 3D (3d-assets.codriver.io), CC BY 4.0
Albert Memorial scan by artfletch (Zenodo), CC BY 4.0 · Street props by Minimaliano (Fab), CC BY 4.0
Textures and props: Poly Haven (CC0) · Trees: Cosmo Tree Gen by FrogCosmonaut (MIT) · Signs set in Noto Serif (SIL OFL 1.1)
Full licence notices: THIRD_PARTY_NOTICES.txt
Made with Unreal Engine 5.9
```

**Map lines, added 2026-11-14 ~21:10** for Jah's Gray London map. They go in a new key, `Credits.Map`, so that `Credits.Tools` stays unchanged. **Live 21:24.** game-flow-ui saved them in the string table and the C++ fallback (`ReflectionsGameFlowSlate.cpp:1170-1174`). I checked that the CSV matches this block line for line (5 lines). Screenshots `ArtDirection/GameFlow/Screenshots/15_credits_map.png` and `16_victory_credits_map.png` show every line with no clipping. They show in a packaged build, and in the editor from train #14. The full CC BY notices (licence link, changes, disclaimer) are in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt), which ships at the root of the zip. Why each line is needed: [gray-london-review.md](gray-london-review.md#1-required-attributions). If Jah finds the Fab props are under the Fab Standard License, not CC BY, drop "· Street props by Minimaliano (Fab), CC BY 4.0".

**If audio deletes the old OpenAI crowd barks**, the voice line stays as it is: the Tarnish and the narrator still use OpenAI. Drop "and OpenAI (…)" only if every OpenAI line is re-voiced.

Why these wordings:
- **ElevenLabs:** the free plan requires attribution to elevenlabs.io, and music to "Eleven Music" ([commercial-readiness.md](commercial-readiness.md)).
- **Kimodo:** "Kimodo" is NVIDIA's name for the model (Kinematic Motion Diffusion), and SOMA-RP-v1.1 is the checkpoint the scripts used. The NVIDIA Open Model License's notice clause, "Licensed by NVIDIA Corporation under the NVIDIA Open Model License", applies when the model is redistributed. Crediting it for outputs is a conservative extra, not a confirmed requirement.
- **Hunyuan:** "Powered by Tencent Hunyuan" is also conservative. Tencent's Hunyuan licences ask for it on products using their works, and whether that covers outputs is unclear.

## Can't verify

1. **Who wrote which C++ folder.** There are no authorship markers. "Codex owns enemy/NPC combat" rests on ownership notes, and a deeper review of the Codex and Claude transcripts was blocked by permissions.
2. **The image model version.** C2PA says only "gpt-image". The "attached game plan" the prompts cite isn't in the repo, so who wrote it (a person or an agent) is unknown.
3. **The Hunyuan3D-2 runs.** They're recorded in JSON and READMEs, but no install was found. **Licence**: the Tencent Hunyuan 3D community licence reportedly excludes the EU, UK and South Korea. Confirm the team is outside those, and read the current terms.
4. **Licence terms for ElevenLabs on the free tier** (reportedly attribution required and non-commercial use only), **the Kimodo weights**, and **the Llama-3-based encoder**. The game is non-commercial and the credits block attributes ElevenLabs, but confirm.
5. **GASP's version and ALS V4's origin and licence.** GASP is identified by asset names and two README mentions; there's no licence file.
6. **Whether ALS V4, Paragon TwinBlast, Echo or UE4_Mannequin end up in the cooked pak**, and whether players can reach GASP's visual-override cycling (`IA_NextVisualOverride`), which would show Epic's Paragon and Echo characters.
7. **Which assets are jam-made by date.** Re-saving resets LastWriteTime, so GASP-derived files (`Hero/Sample/*`) look new. The 11-13 20:30 creation time marks the copy, not authorship.
8. **Whether Epic's in-editor AI assistant was used.**
9. ~~OpenAI voices pending~~. **Done 11-14:** first 59 lines, now 123 OpenAI lines alongside the Gemini lines. The Gemini-only credits went to game-flow-ui at ~18:40.
10. **The exact Gemini line count** (3,242 per audio, 3,312 waves on disk) and **whether the old OpenAI crowd barks still play**. Audio owns both.
11. **Whether the jam zip will include a Gemini key.** The NPC dialogue README suggests a dedicated, capped key for judging; the orchestrator's brief says players use their own. The itch page assumes the player's own key. If the team ships a key, swap in the alternative sentence marked in [itch-page.md](itch-page.md#privacy-talking-to-people).
12. **How the Gray London map was made** (Jah to confirm). Its docs describe AI-agent work ("agent_audit", "agent_assets"), but not which agent. There are also **three AI-generated photo textures** for shop windows, `T_BookshopPhoto`, `T_GroceryPhoto` and `T_BishopsgateClothesPhoto`, and the image model isn't named. Add both to the tools table once known. Also confirm the map's source project was started on or after Nov 12, and keep its history (rule 7(h)). See [gray-london-review.md](gray-london-review.md#25-not-licence-problems-but-the-team-should-decide).
