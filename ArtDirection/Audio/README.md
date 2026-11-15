# Reflections — Jam Audio

All game audio for the jam build lives under `/Game/Audio/Jam/`. Sounds come from two sources, marked per asset below: AI generation with ElevenLabs (through the ElevenLabs Creative connector), and procedural numpy synthesis used as stand-ins while the ElevenLabs free tier throttles generation. Everything was trimmed, made mono (SFX), level-matched and loop-crossfaded locally, then imported as SoundWaves. Prompts were written for this project and name no artist, franchise or game.

**Gameplay code should reference the cues (`/Game/Audio/Jam/Cues/SCue_*`), not the waves.** Cues carry the sound class, attenuation, volume and the randomized variation / pitch spread.

## AI declaration (for the jam submission)

- Character voices: OpenAI's realtime audio model, baked offline into WAVs (no runtime API use). Engine per line: `gpt-realtime-2.1` x115, `gpt-4o-mini-tts` x8; `gpt-4o-mini-tts` is the fallback when a take's transcript doesn't match the script. Prompts (actor rules, per-character brief, pronunciation) and every line are in `ArtDirection/Audio/VoiceScript.md`. The voices are AI-generated, not performed by actors, and the credits must say so.
- Crowd voices (137 NPC voices): Google Gemini Voice design (`gemini-3.8-flash-tts`) made one voice per character from a written brief (`ArtDirection/Audio/data/voice_roster.json`); the lines are synthesized offline with Gemini 3.8 Flash TTS and accepted only when an OpenAI `gpt-4o-transcribe` transcript matches the script word for word. These baked lines make no API calls at runtime. The optional live-reply helper (NPC dialogue session) uses the same designed voices with a Gemini key the user supplies, and is declared in its own README. Status: 3312 lines generated.
- Crowd scripts: the conversations, remarks, replies, barks, possessed mutters and fillers were drafted by Google Gemini 3.8 Flash (text) from the project's canon brief, then machine-checked (never-say words, Teen-safe wording, length) and passed through an AI editor pass. Every line is unique to its speaker: `tools/uniq_check.py` fails the build on any line two characters share. The full script is `ArtDirection/Audio/AmbientScript.md`.
- ElevenLabs (ElevenLabs Sound Effects v2 (eleven_text_to_sound_v2); ElevenLabs Music v2.5 (eleven_music_v2_5), instrumental): only the 6 final cues listed below. The team decided on 2026-11-14 not to generate more.
- Post-processing (not AI): trim, mono downmix for SFX, peak/RMS normalization, equal-power loop crossfade, slicing of multi-take clips.
- Currently AI-generated (6): `Water_Impact`, `MUS_Gray_Loop`, `MUS_Red_Loop`, `MUS_White_Loop`, `Fire_Cast`, `Fire_Impact`.
- Currently procedural stand-ins, not AI (39): `Water_Cast`, `Ice_Cast`, `Ice_Impact`, `Lightning_Cast`, `Lightning_Impact`, `Earth_Cast`, `Earth_Impact`, `Arcane_Cast`, `Arcane_Impact`, `Heal_Shimmer`, `Shield_Up`, `Shield_Block`, `Shield_Loop`, `Projectile_Loop`, `Levitation_Start`, `Levitation_Loop`, `Sword_Swing`, `Sword_Hit`, `Sword_Clash`, `WorldJump_Whoosh`, `WorldJump_Stinger`, `WorldJump_Refused`, `Coin_Pickup`, `Page_Pickup`, `Door_Unseal`, `UI_Click`, `UI_Hover`, `UI_Confirm`, `Infected_Growl`, `MUS_Combat_Layer`, `MUS_Victory_Sting`, `Villain_Manifest`, `Villain_Voice`, `Villain_Hop`, `Villain_Telegraph`, `Villain_Slam`, `Villain_Hurt`, `Villain_Death`, `FinalSpell_Cast`. These are synthesized from scratch (numpy); no recorded or sampled audio is used.
- No third-party or licensed audio is included in `/Game/Audio/Jam/`.

## Mix setup (`/Game/Audio/Jam/Mix/`)

| Asset | What it does |
|---|---|
| `SCL_Jam_Master` | Root sound class. |
| `SCL_Jam_Music` (vol 0.7) | All music. Children: `SCL_Jam_Music_World` (world loops), `SCL_Jam_Music_Combat` (combat layer, victory sting). |
| `SCL_Jam_SFX` (vol 1.0) | All gameplay sound effects. |
| `SCL_Jam_UI` (vol 0.6) | Menu / HUD sounds (UI sound flag, no reverb). |
| `SMX_Jam_Base` | Neutral mix with Music / SFX / UI adjusters at 1.0. Push it as the base mix and drive options sliders with `SetSoundMixClassOverride` on it. |
| `SMX_Jam_Combat` | Ducks `SCL_Jam_Music_World` (the world loops) to 0.45 (1.5 s in, 2 s out) so the combat layer sits on top. Push when combat starts, pop when it ends. |
| `SMX_Jam_StingerDuck` | Ducks all music to 0.3 for 3.5 s, then releases by itself. Push with the world-jump stinger and the victory sting. |
| `ATT_Jam_Small` / `ATT_Jam_Medium` / `ATT_Jam_Large` | Natural-falloff spherical attenuation, distance low-pass, 2 m / 4 m / 8 m inner radius, 25 m / 50 m / 100 m falloff. |
| `ATT_Jam_NPCVoice` | Speech from a position: spatialized, full volume within 3 m, natural falloff to silence by ~28 m, distance low-pass (air absorption), light occlusion. On every NPC and Tarnish voice cue; play those attached to the speaker's head bone (`SpawnSoundAttached(..., "head")`). The narrator and the `_Head` Tarnish variants are 2D. |
| `SUB_Jam_Main` + `SFXP_Jam_Limiter` | Every jam sound class defaults to this submix; its limiter (-1.5 dB threshold, 3 ms look-ahead) keeps stacked spells over music from clipping. It feeds the master submix. |

Levels are baked into the waves by a loudness pass (BS.1770 K-weighted): music loops at -20 LUFS integrated (combat layer -21, victory -17); SFX normalized on their loudest 400 ms window to per-sound targets (impacts -12 to -13 LUFS, casts -16, sword -14 to -17, pickups -18/-19, loops -22 to -25, UI -24/-30), peaks limited to -1 dBFS with at most 3 dB of gain reduction. Every cue plays at volume 1.0 and every SFX cue randomizes pitch (about +/-3 to 8%) and volume (0.92 to 1.0). Sound class volumes (music 0.7, UI 0.6) put music about 7 dB under spell casts, so nothing needs to be pushed for sound to work; the mixes are optional extras.

## Final vs stand-in

| Cue | Status |
|---|---|
| `SCue_Water_Impact` | **final** (ElevenLabs) |
| `SCue_MUS_Gray_Loop` | **final** (ElevenLabs) |
| `SCue_MUS_Red_Loop` | **final** (ElevenLabs) |
| `SCue_MUS_White_Loop` | **final** (ElevenLabs) |
| `SCue_Fire_Cast` | **final** (ElevenLabs) |
| `SCue_Fire_Impact` | **final** (ElevenLabs) |
| `SCue_Water_Cast` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Ice_Cast` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Ice_Impact` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Lightning_Cast` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Lightning_Impact` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Earth_Cast` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Earth_Impact` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Arcane_Cast` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Arcane_Impact` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Heal_Shimmer` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Shield_Up` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Shield_Block` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Shield_Loop` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Projectile_Loop` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Levitation_Start` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Levitation_Loop` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Sword_Swing` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Sword_Hit` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Sword_Clash` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_WorldJump_Whoosh` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_WorldJump_Stinger` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_WorldJump_Refused` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Coin_Pickup` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Page_Pickup` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Door_Unseal` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_UI_Click` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_UI_Hover` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_UI_Confirm` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Infected_Growl` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_MUS_Combat_Layer` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_MUS_Victory_Sting` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Villain_Manifest` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Villain_Voice` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Villain_Hop` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Villain_Telegraph` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Villain_Slam` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Villain_Hurt` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_Villain_Death` | stand-in (procedural; ElevenLabs take queued) |
| `SCue_FinalSpell_Cast` | stand-in (procedural; ElevenLabs take queued) |

## Event → sound map

| Event | Play this | How | Owner |
|---|---|---|---|
| Cast of a Fire-element spell (Fire Bolt, Flame Burst, Fireball) | `/Game/Audio/Jam/Cues/SCue_Fire_Cast` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Fire projectile hit / Flame Burst and Fireball area detonation | `/Game/Audio/Jam/Cues/SCue_Fire_Impact` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Cast of a Water-element spell (Water Bolt, Tidal Surge, Water Orb) | `/Game/Audio/Jam/Cues/SCue_Water_Cast` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Water projectile hit / Tidal Surge area | `/Game/Audio/Jam/Cues/SCue_Water_Impact` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Cast of an Ice-element spell (Ice Shard, Frost Nova) | `/Game/Audio/Jam/Cues/SCue_Ice_Cast` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Ice Shard hit / Frost Nova burst | `/Game/Audio/Jam/Cues/SCue_Ice_Impact` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Cast of a Lightning spell (Lightning Burst, Lightning Bolt, Thunder Wave) | `/Game/Audio/Jam/Cues/SCue_Lightning_Cast` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Lightning hit / Thunder Wave area | `/Game/Audio/Jam/Cues/SCue_Lightning_Impact` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Cast of an Earth spell (Stone Shard, Earth Shock) | `/Game/Audio/Jam/Cues/SCue_Earth_Cast` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Stone Shard hit / Earth Shock area | `/Game/Audio/Jam/Cues/SCue_Earth_Impact` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Cast of an Arcane spell (Arcane Bolt, Force Push) | `/Game/Audio/Jam/Cues/SCue_Arcane_Cast` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Arcane Bolt hit / Force Push wave | `/Game/Audio/Jam/Cues/SCue_Arcane_Impact` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Healing / Greater Heal / Healing Pulse cast (Life element) | `/Game/Audio/Jam/Cues/SCue_Heal_Shimmer` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Arcane Shield (Ward) raised | `/Game/Audio/Jam/Cues/SCue_Shield_Up` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Damage absorbed by the Arcane Shield | `/Game/Audio/Jam/Cues/SCue_Shield_Block` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Looping hum while the Arcane Shield is active (attach to caster, stop on expiry) | `/Game/Audio/Jam/Cues/SCue_Shield_Loop` | spawn attached, looping — stop/fade it out when the effect ends | spell-combat-rebuild |
| Looping in-flight sound attached to any spell projectile | `/Game/Audio/Jam/Cues/SCue_Projectile_Loop` | spawn attached, looping — stop/fade it out when the effect ends | spell-combat-rebuild |
| Levitation (Air / Hover) cast | `/Game/Audio/Jam/Cues/SCue_Levitation_Start` | PlaySoundAtLocation / SpawnSoundAttached | spell-combat-rebuild |
| Looping wind while levitating | `/Game/Audio/Jam/Cues/SCue_Levitation_Loop` | spawn attached, looping — stop/fade it out when the effect ends | spell-combat-rebuild |
| Sword swing (every attack, on the swing anim notify) | `/Game/Audio/Jam/Cues/SCue_Sword_Swing` | PlaySoundAtLocation / SpawnSoundAttached | NPC / enemy combat code (Codex, the user) |
| Sword connects with a character | `/Game/Audio/Jam/Cues/SCue_Sword_Hit` | PlaySoundAtLocation / SpawnSoundAttached | NPC / enemy combat code (Codex, the user) |
| Sword blocked / parried by another blade | `/Game/Audio/Jam/Cues/SCue_Sword_Clash` | PlaySoundAtLocation / SpawnSoundAttached | NPC / enemy combat code (Codex, the user) |
| World jump departure (JumpSound): play 2D when the jump starts | `/Game/Audio/Jam/Cues/SCue_WorldJump_Whoosh` | PlaySound2D | world-jump |
| World jump arrival in the new world: play 2D on arrival | `/Game/Audio/Jam/Cues/SCue_WorldJump_Stinger` | PlaySound2D | world-jump |
| World jump refused (RefusedSound): no mirror shard / blocked | `/Game/Audio/Jam/Cues/SCue_WorldJump_Refused` | PlaySound2D | world-jump |
| Mirror shard (coin) collected (PickupSound) | `/Game/Audio/Jam/Cues/SCue_Coin_Pickup` | PlaySoundAtLocation / SpawnSoundAttached | world-jump |
| Book page collected from a tower | `/Game/Audio/Jam/Cues/SCue_Page_Pickup` | PlaySoundAtLocation / SpawnSoundAttached | world-jump |
| Tower door unsealed / opened | `/Game/Audio/Jam/Cues/SCue_Door_Unseal` | PlaySoundAtLocation / SpawnSoundAttached | world-jump |
| Button pressed | `/Game/Audio/Jam/Cues/SCue_UI_Click` | PlaySound2D | whoever owns menus/HUD |
| Button hovered / focus moved | `/Game/Audio/Jam/Cues/SCue_UI_Hover` | PlaySound2D | whoever owns menus/HUD |
| Confirm / start game / spell crafted | `/Game/Audio/Jam/Cues/SCue_UI_Confirm` | PlaySound2D | whoever owns menus/HUD |
| Infected / Tarnish-touched NPC idle growl, aggro or attack bark | `/Game/Audio/Jam/Cues/SCue_Infected_Growl` | PlaySoundAtLocation / SpawnSoundAttached | NPC / enemy combat code (Codex, the user) |
| The Tarnish's true form appears (dark stinger) | `/Game/Audio/Jam/Cues/SCue_Villain_Manifest` | PlaySoundAtLocation / SpawnSoundAttached | villain session (possession + finale) |
| The Tarnish's whispered taunt / laugh; also when he hops hosts | `/Game/Audio/Jam/Cues/SCue_Villain_Voice` | PlaySoundAtLocation / SpawnSoundAttached | villain session (possession + finale) |
| The Tarnish leaves one host for another | `/Game/Audio/Jam/Cues/SCue_Villain_Hop` | PlaySoundAtLocation / SpawnSoundAttached | villain session (possession + finale) |
| 1 s charge-up before each of the Tarnish's attacks | `/Game/Audio/Jam/Cues/SCue_Villain_Telegraph` | PlaySoundAtLocation / SpawnSoundAttached | villain session (possession + finale) |
| The Tarnish's heavy attack impact (ground shockwave / tendril strike) | `/Game/Audio/Jam/Cues/SCue_Villain_Slam` | PlaySoundAtLocation / SpawnSoundAttached | villain session (possession + finale) |
| The Tarnish hit by the Final Spell | `/Game/Audio/Jam/Cues/SCue_Villain_Hurt` | PlaySoundAtLocation / SpawnSoundAttached | villain session (possession + finale) |
| The Tarnish's death: dissolve and scream | `/Game/Audio/Jam/Cues/SCue_Villain_Death` | PlaySoundAtLocation / SpawnSoundAttached | villain session (possession + finale) |
| Hero casts the Final Spell (bright, holy, big) | `/Game/Audio/Jam/Cues/SCue_FinalSpell_Cast` | PlaySoundAtLocation / SpawnSoundAttached | villain session (possession + finale) |
| Pewterside (gray, present-day) ambient music loop | `/Game/Audio/Jam/Cues/SCue_MUS_Gray_Loop` | 2D, looping | world-jump |
| Giltside (red, medieval war) music loop | `/Game/Audio/Jam/Cues/SCue_MUS_Red_Loop` | 2D, looping | world-jump |
| Frostside (white, wasteland) music loop | `/Game/Audio/Jam/Cues/SCue_MUS_White_Loop` | 2D, looping | world-jump |
| Combat layer: fade in over the world loop when enemies engage (push SMX_Jam_Combat) | `/Game/Audio/Jam/Cues/SCue_MUS_Combat_Layer` | 2D, looping | NPC / enemy combat code (Codex, the user) |
| Victory sting: last enemy of an encounter defeated (push SMX_Jam_StingerDuck) | `/Game/Audio/Jam/Cues/SCue_MUS_Victory_Sting` | 2D one-shot | NPC / enemy combat code (Codex, the user) |

## Sound effects

Generator: ElevenLabs Sound Effects v2 (eleven_text_to_sound_v2). Waves are mono 44.1 kHz, peak-normalized to -1 dBFS; levels are set on the cue.

### Fire_Cast

- Cue: `/Game/Audio/Jam/Cues/SCue_Fire_Cast` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.95–1.05
- Waves (1): `SW_Fire_Cast_01` (1.07 s)
- Loudness: target -16 LUFS momentary max; result -16.1 (peaks <= -1 dBFS)
- Source: **ElevenLabs** (ElevenLabs Sound Effects v2 (eleven_text_to_sound_v2))
- Prompt: "Burst of fire igniting from an open hand, sharp whoosh of flame with crackling embers, close-mic"
- Generation: 1.2 s requested, prompt influence 0.5

### Fire_Impact

- Cue: `/Game/Audio/Jam/Cues/SCue_Fire_Impact` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Large (8 m inner, 100 m falloff), volume 1.0, pitch 0.94–1.06
- Waves (1): `SW_Fire_Impact_01` (1.76 s)
- Loudness: target -12 LUFS momentary max; result -12.9 (peaks <= -1 dBFS)
- Source: **ElevenLabs** (ElevenLabs Sound Effects v2 (eleven_text_to_sound_v2))
- Prompt: "Fireball exploding on impact, deep punchy boom with roaring flames and crackling embers scattering"
- Generation: 1.8 s requested, prompt influence 0.5

### Water_Cast

- Cue: `/Game/Audio/Jam/Cues/SCue_Water_Cast` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.95–1.05
- Waves (3): `SW_Water_Cast_01` (1.02 s), `SW_Water_Cast_02` (1.03 s), `SW_Water_Cast_03` (1.01 s)
- Loudness: target -16 LUFS momentary max; result -16.0, -16.0, -16.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Water_Cast`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Swirling rush of water gathering and launching forward, splashy whoosh, close-mic"

### Water_Impact

- Cue: `/Game/Audio/Jam/Cues/SCue_Water_Impact` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.94–1.06
- Waves (1): `SW_Water_Impact_01` (1.32 s)
- Loudness: target -13 LUFS momentary max; result -13.0 (peaks <= -1 dBFS)
- Source: **ElevenLabs** (ElevenLabs Sound Effects v2 (eleven_text_to_sound_v2))
- Prompt: "Heavy blast of water slamming into stone, big splash with spray and dripping"
- Generation: 1.5 s requested, prompt influence 0.5

### Ice_Cast

- Cue: `/Game/Audio/Jam/Cues/SCue_Ice_Cast` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.95–1.05
- Waves (3): `SW_Ice_Cast_01` (1.41 s), `SW_Ice_Cast_02` (1.29 s), `SW_Ice_Cast_03` (1.42 s)
- Loudness: target -16 LUFS momentary max; result -16.0, -16.0, -16.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Ice_Cast`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Ice crystals forming rapidly, crisp crackling freeze with a cold glassy shimmer"

### Ice_Impact

- Cue: `/Game/Audio/Jam/Cues/SCue_Ice_Impact` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.94–1.06
- Waves (3): `SW_Ice_Impact_01` (1.60 s), `SW_Ice_Impact_02` (1.60 s), `SW_Ice_Impact_03` (1.60 s)
- Loudness: target -13 LUFS momentary max; result -13.7, -13.1, -13.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Ice_Impact`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Ice shard shattering on impact, sharp glassy crack with tinkling frozen fragments"

### Lightning_Cast

- Cue: `/Game/Audio/Jam/Cues/SCue_Lightning_Cast` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.95–1.05
- Waves (3): `SW_Lightning_Cast_01` (0.82 s), `SW_Lightning_Cast_02` (0.82 s), `SW_Lightning_Cast_03` (0.90 s)
- Loudness: target -16 LUFS momentary max; result -16.1, -16.1, -16.2 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Lightning_Cast`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Electric charge snapping in the air, crackling high-voltage arc zap"

### Lightning_Impact

- Cue: `/Game/Audio/Jam/Cues/SCue_Lightning_Impact` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Large (8 m inner, 100 m falloff), volume 1.0, pitch 0.95–1.05
- Waves (3): `SW_Lightning_Impact_01` (2.70 s), `SW_Lightning_Impact_02` (2.70 s), `SW_Lightning_Impact_03` (2.70 s)
- Loudness: target -12 LUFS momentary max; result -16.9, -15.3, -18.4 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Lightning_Impact`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Lightning bolt striking the ground, loud sharp electric crack followed by a short rolling rumble"

### Earth_Cast

- Cue: `/Game/Audio/Jam/Cues/SCue_Earth_Cast` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.95–1.05
- Waves (3): `SW_Earth_Cast_01` (1.25 s), `SW_Earth_Cast_02` (1.24 s), `SW_Earth_Cast_03` (1.39 s)
- Loudness: target -16 LUFS momentary max; result -16.0, -16.0, -16.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Earth_Cast`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Stone and rock tearing up out of the ground, deep grinding rumble with falling gravel"

### Earth_Impact

- Cue: `/Game/Audio/Jam/Cues/SCue_Earth_Impact` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Large (8 m inner, 100 m falloff), volume 1.0, pitch 0.94–1.06
- Waves (3): `SW_Earth_Impact_01` (2.03 s), `SW_Earth_Impact_02` (1.99 s), `SW_Earth_Impact_03` (1.84 s)
- Loudness: target -12 LUFS momentary max; result -14.8, -17.6, -15.3 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Earth_Impact`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Heavy boulder smashing into the ground, crunching thud with rock debris scattering"

### Arcane_Cast

- Cue: `/Game/Audio/Jam/Cues/SCue_Arcane_Cast` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.95–1.05
- Waves (3): `SW_Arcane_Cast_01` (1.31 s), `SW_Arcane_Cast_02` (1.39 s), `SW_Arcane_Cast_03` (1.31 s)
- Loudness: target -16 LUFS momentary max; result -16.0, -16.0, -16.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Arcane_Cast`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Mystical spell charging, shimmering resonant hum rising quickly into a soft magical whoosh"

### Arcane_Impact

- Cue: `/Game/Audio/Jam/Cues/SCue_Arcane_Impact` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.94–1.06
- Waves (3): `SW_Arcane_Impact_01` (2.00 s), `SW_Arcane_Impact_02` (2.00 s), `SW_Arcane_Impact_03` (2.00 s)
- Loudness: target -13 LUFS momentary max; result -16.1, -15.0, -16.6 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Arcane_Impact`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Burst of magical energy on impact, resonant crystalline pulse with a deep soft boom"

### Heal_Shimmer

- Cue: `/Game/Audio/Jam/Cues/SCue_Heal_Shimmer` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.97–1.03
- Waves (1): `SW_Heal_Shimmer_01` (3.20 s)
- Loudness: target -18 LUFS momentary max; result -18.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Heal_Shimmer`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Gentle healing magic, soft warm chimes and airy sparkling shimmer slowly rising"

### Shield_Up

- Cue: `/Game/Audio/Jam/Cues/SCue_Shield_Up` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.97–1.03
- Waves (1): `SW_Shield_Up_01` (2.00 s)
- Loudness: target -17 LUFS momentary max; result -17.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Shield_Up`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Magical force barrier activating, deep resonant whoomp swelling into a humming glassy shimmer"

### Shield_Block

- Cue: `/Game/Audio/Jam/Cues/SCue_Shield_Block` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.94–1.06
- Waves (2): `SW_Shield_Block_01` (0.90 s), `SW_Shield_Block_02` (0.90 s)
- Loudness: target -16 LUFS momentary max; result -16.0, -16.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Shield_Block`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Blow deflected by a magical energy barrier, resonant metallic ping with a buzzing ripple"

### Shield_Loop

- Cue: `/Game/Audio/Jam/Cues/SCue_Shield_Loop` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.98–1.02, looping
- Waves (1): `SW_Shield_Loop_01` (4.00 s)
- Loudness: target -25 LUFS momentary max; result -25.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Shield_Loop`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Steady low hum of a magical force field, soft electric shimmer, constant"

### Projectile_Loop

- Cue: `/Game/Audio/Jam/Cues/SCue_Projectile_Loop` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.98–1.02, looping
- Waves (1): `SW_Projectile_Loop_01` (3.00 s)
- Loudness: target -22 LUFS momentary max; result -22.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Projectile_Loop`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Magical projectile flying through the air, steady whooshing hum with faint sparkling crackle, constant"

### Levitation_Start

- Cue: `/Game/Audio/Jam/Cues/SCue_Levitation_Start` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.96–1.04
- Waves (1): `SW_Levitation_Start_01` (1.80 s)
- Loudness: target -18 LUFS momentary max; result -18.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Levitation_Start`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Gust of wind lifting upward with a soft airy magical whoosh"

### Levitation_Loop

- Cue: `/Game/Audio/Jam/Cues/SCue_Levitation_Loop` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.98–1.02, looping
- Waves (1): `SW_Levitation_Loop_01` (4.00 s)
- Loudness: target -24 LUFS momentary max; result -24.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Levitation_Loop`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Steady soft wind swirling around a person with a gentle magical hum, constant"

### Sword_Swing

- Cue: `/Game/Audio/Jam/Cues/SCue_Sword_Swing` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.92–1.08
- Waves (4): `SW_Sword_Swing_01` (0.35 s), `SW_Sword_Swing_02` (0.42 s), `SW_Sword_Swing_03` (0.38 s), `SW_Sword_Swing_04` (0.41 s)
- Loudness: target -17 LUFS momentary max; result -17.0, -17.0, -17.0, -17.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Sword_Swing`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Four different fast sword swings through the air, one at a time with a short silent gap between each, sharp metallic blade swishes, close-mic"

### Sword_Hit

- Cue: `/Game/Audio/Jam/Cues/SCue_Sword_Hit` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.93–1.07
- Waves (3): `SW_Sword_Hit_01` (0.40 s), `SW_Sword_Hit_02` (0.40 s), `SW_Sword_Hit_03` (0.40 s)
- Loudness: target -16 LUFS momentary max; result -17.4, -17.6, -18.4 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Sword_Hit`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Four separate sword blade hits slicing into a body, one at a time with a short silent gap between each, meaty cut with a heavy thud"

### Sword_Clash

- Cue: `/Game/Audio/Jam/Cues/SCue_Sword_Clash` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.93–1.07
- Waves (3): `SW_Sword_Clash_01` (1.60 s), `SW_Sword_Clash_02` (1.60 s), `SW_Sword_Clash_03` (1.60 s)
- Loudness: target -15 LUFS momentary max; result -15.0, -15.0, -15.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Sword_Clash`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Three separate clashes of two steel swords, one at a time with a short silent gap between each, bright ringing metal clang"

### WorldJump_Whoosh

- Cue: `/Game/Audio/Jam/Cues/SCue_WorldJump_Whoosh` — class `SCL_Jam_SFX`, attenuation none (2D), volume 1.0, pitch 0.97–1.03
- Waves (1): `SW_WorldJump_Whoosh_01` (2.55 s)
- Loudness: target -15 LUFS momentary max; result -15.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_WorldJump_Whoosh`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Deep rushing vortex whoosh, swirling wind and reversed shimmer sweeping past and rising in intensity"

### WorldJump_Stinger

- Cue: `/Game/Audio/Jam/Cues/SCue_WorldJump_Stinger` — class `SCL_Jam_SFX`, attenuation none (2D), volume 1.0, pitch 0.97–1.03
- Waves (1): `SW_WorldJump_Stinger_01` (4.20 s)
- Loudness: target -14 LUFS momentary max; result -14.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_WorldJump_Stinger`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Dramatic magical arrival hit, deep sub boom followed by a bright shimmering ringing tail"

### WorldJump_Refused

- Cue: `/Game/Audio/Jam/Cues/SCue_WorldJump_Refused` — class `SCL_Jam_SFX`, attenuation none (2D), volume 1.0, pitch 0.96–1.04
- Waves (1): `SW_WorldJump_Refused_01` (0.67 s)
- Loudness: target -19 LUFS momentary max; result -20.8 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_WorldJump_Refused`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Failed magic attempt, short muted fizzle and sputter ending in a dull low thud"

### Coin_Pickup

- Cue: `/Game/Audio/Jam/Cues/SCue_Coin_Pickup` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.95–1.08
- Waves (3): `SW_Coin_Pickup_01` (0.90 s), `SW_Coin_Pickup_02` (0.90 s), `SW_Coin_Pickup_03` (0.90 s)
- Loudness: target -18 LUFS momentary max; result -18.0, -18.0, -18.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Coin_Pickup`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Three separate old metal coins picked up, one at a time with a short silent gap between each, bright clink with a faint magical chime"

### Page_Pickup

- Cue: `/Game/Audio/Jam/Cues/SCue_Page_Pickup` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.97–1.03
- Waves (1): `SW_Page_Pickup_01` (1.00 s)
- Loudness: target -19 LUFS momentary max; result -19.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Page_Pickup`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Old parchment page picked up and rustled, papery flutter with a soft magical chime"

### Door_Unseal

- Cue: `/Game/Audio/Jam/Cues/SCue_Door_Unseal` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.97–1.03
- Waves (1): `SW_Door_Unseal_01` (5.20 s)
- Loudness: target -16 LUFS momentary max; result -16.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Door_Unseal`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Ancient magical seal breaking with a resonant chime, then a heavy stone door grinding open"

### UI_Click

- Cue: `/Game/Audio/Jam/Cues/SCue_UI_Click` — class `SCL_Jam_UI`, attenuation none (2D), volume 1.0, pitch 0.97–1.03
- Waves (4): `SW_UI_Click_01` (0.06 s), `SW_UI_Click_02` (0.06 s), `SW_UI_Click_03` (0.06 s), `SW_UI_Click_04` (0.06 s)
- Loudness: target -24 LUFS momentary max; result -25.7, -26.4, -27.4, -25.9 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_UI_Click`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Four separate soft clean interface button clicks, one at a time with silence between each, short subtle ticks"

### UI_Hover

- Cue: `/Game/Audio/Jam/Cues/SCue_UI_Hover` — class `SCL_Jam_UI`, attenuation none (2D), volume 1.0, pitch 0.98–1.02
- Waves (2): `SW_UI_Hover_01` (0.08 s), `SW_UI_Hover_02` (0.08 s)
- Loudness: target -30 LUFS momentary max; result -30.0, -30.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_UI_Hover`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Very soft quiet interface hover tick, gentle and airy"

### UI_Confirm

- Cue: `/Game/Audio/Jam/Cues/SCue_UI_Confirm` — class `SCL_Jam_UI`, attenuation none (2D), volume 1.0, pitch 0.97–1.03
- Waves (1): `SW_UI_Confirm_01` (0.85 s)
- Loudness: target -22 LUFS momentary max; result -22.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_UI_Confirm`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Pleasant interface confirm sound, short warm two-note chime"

### Infected_Growl

- Cue: `/Game/Audio/Jam/Cues/SCue_Infected_Growl` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Small (2 m inner, 25 m falloff), volume 1.0, pitch 0.9–1.08
- Waves (3): `SW_Infected_Growl_01` (1.57 s), `SW_Infected_Growl_02` (1.45 s), `SW_Infected_Growl_03` (1.35 s)
- Loudness: target -16 LUFS momentary max; result -16.0, -16.1, -16.4 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Infected_Growl`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Three different raspy feral human growls, one at a time with a short pause between each, a crazed person snarling through clenched teeth, throaty and wet"

### Villain_Manifest

- Cue: `/Game/Audio/Jam/Cues/SCue_Villain_Manifest` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Large (8 m inner, 100 m falloff), volume 1.0, pitch 0.97–1.03
- Waves (1): `SW_Villain_Manifest_01` (4.00 s)
- Loudness: target -13 LUFS momentary max; result -14.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Villain_Manifest`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Dark ominous supernatural stinger: a reversed rising hiss slamming into a deep sub boom with a dissonant low brass-like cluster and a long dark reverberant tail"

### Villain_Voice

- Cue: `/Game/Audio/Jam/Cues/SCue_Villain_Voice` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.94–1.04
- Waves (6): `SW_Villain_Voice_01` (2.15 s), `SW_Villain_Voice_02` (2.33 s), `SW_Villain_Voice_03` (2.08 s), `SW_Villain_Voice_04` (2.09 s), `SW_Villain_Voice_05` (2.20 s), `SW_Villain_Voice_06` (2.20 s)
- Loudness: target -18 LUFS momentary max; result -18.0, -18.0, -18.0, -18.0, -18.0, -18.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Villain_Voice`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Three different menacing whispered evil chuckles and hisses, one at a time with a short pause between each, close and breathy"

### Villain_Hop

- Cue: `/Game/Audio/Jam/Cues/SCue_Villain_Hop` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.95–1.05
- Waves (2): `SW_Villain_Hop_01` (1.60 s), `SW_Villain_Hop_02` (1.60 s)
- Loudness: target -16 LUFS momentary max; result -16.0, -16.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Villain_Hop`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Wet dark smoke whoosh with a gloopy squelch, a shadow leaping out of one body and into another"

### Villain_Telegraph

- Cue: `/Game/Audio/Jam/Cues/SCue_Villain_Telegraph` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.98–1.02
- Waves (1): `SW_Villain_Telegraph_01` (1.00 s)
- Loudness: target -16 LUFS momentary max; result -16.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Villain_Telegraph`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Ominous rising dark energy charge-up building tension for one second and stopping abruptly"

### Villain_Slam

- Cue: `/Game/Audio/Jam/Cues/SCue_Villain_Slam` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Large (8 m inner, 100 m falloff), volume 1.0, pitch 0.95–1.05
- Waves (2): `SW_Villain_Slam_01` (2.55 s), `SW_Villain_Slam_02` (2.55 s)
- Loudness: target -11 LUFS momentary max; result -14.8, -16.2 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Villain_Slam`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Massive heavy ground slam shockwave, deep sub impact with rumbling stone debris"

### Villain_Hurt

- Cue: `/Game/Audio/Jam/Cues/SCue_Villain_Hurt` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Medium (4 m inner, 50 m falloff), volume 1.0, pitch 0.94–1.06
- Waves (3): `SW_Villain_Hurt_01` (1.50 s), `SW_Villain_Hurt_02` (1.50 s), `SW_Villain_Hurt_03` (1.50 s)
- Loudness: target -14 LUFS momentary max; result -14.0, -14.0, -14.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Villain_Hurt`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Demonic creature roaring in pain while burning in holy light, sizzling"

### Villain_Death

- Cue: `/Game/Audio/Jam/Cues/SCue_Villain_Death` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Large (8 m inner, 100 m falloff), volume 1.0, pitch 0.99–1.01
- Waves (1): `SW_Villain_Death_01` (4.60 s)
- Loudness: target -14 LUFS momentary max; result -14.0 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_Villain_Death`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Dark demonic entity dissolving into ash, an agonized distorted scream fading into whispering wind and crackling embers"

### FinalSpell_Cast

- Cue: `/Game/Audio/Jam/Cues/SCue_FinalSpell_Cast` — class `SCL_Jam_SFX`, attenuation ATT_Jam_Large (8 m inner, 100 m falloff), volume 1.0, pitch 0.99–1.01
- Waves (1): `SW_FinalSpell_Cast_01` (4.40 s)
- Loudness: target -12 LUFS momentary max; result -12.2 (peaks <= -1 dBFS)
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_FinalSpell_Cast`. Will be replaced in place by the ElevenLabs take below when the free tier allows.
- Queued ElevenLabs prompt: "Huge radiant holy spell blast, bright choir-like swell with shimmering bells and a deep warm boom"

## Music

Generator: ElevenLabs Music v2.5 (eleven_music_v2_5), instrumental. Stereo 48 kHz. Loops are cut before the model's outro and closed with an equal-power crossfade at a point matched on the spectral/onset envelope, so they wrap without a gap or click.

### MUS_Gray_Loop

- Cue: `/Game/Audio/Jam/Cues/SCue_MUS_Gray_Loop` — class `SCL_Jam_Music_World`, volume 1.0, looping
- Wave: `SW_MUS_Gray_Loop` (137.1 s, loop)
- Loudness: -20.0 LUFS integrated
- Source: **ElevenLabs** (ElevenLabs Music v2.5 (eleven_music_v2_5), instrumental)
- Prompt: "Quiet, melancholic ambient piano piece: soft felt piano, warm sustained strings and a gentle low cello, slow tempo around 70 BPM, introspective rainy-evening mood, sparse and steady with no drums. Keep the energy level constant from start to finish with no big build, no intro and no ending, so it can loop seamlessly."
- Generation: 155 s requested, instrumental
- Loop: source 0.00–137.13 s, crossfade match score 0.24

### MUS_Red_Loop

- Cue: `/Game/Audio/Jam/Cues/SCue_MUS_Red_Loop` — class `SCL_Jam_Music_World`, volume 1.0, looping
- Wave: `SW_MUS_Red_Loop` (128.0 s, loop)
- Loudness: -20.0 LUFS integrated
- Source: **ElevenLabs** (ElevenLabs Music v2.5 (eleven_music_v2_5), instrumental)
- Prompt: "Tense medieval war music in a minor key: steady pounding frame drums and deep war drums at a marching 90 BPM, droning low strings, a gritty bowed drone, low horns and a fiddle melody. Urgent and ominous, with consistent energy from start to finish, no intro and no ending, so it can loop seamlessly."
- Generation: 155 s requested, instrumental
- Loop: source 3.50–131.50 s, crossfade match score 0.62

### MUS_White_Loop

- Cue: `/Game/Audio/Jam/Cues/SCue_MUS_White_Loop` — class `SCL_Jam_Music_World`, volume 1.0, looping
- Wave: `SW_MUS_White_Loop` (144.0 s, loop)
- Loudness: -20.0 LUFS integrated
- Source: **ElevenLabs** (ElevenLabs Music v2.5 (eleven_music_v2_5), instrumental)
- Prompt: "Desolate, eerie dark ambient soundscape: cold breathy synth drones, distant detuned bells, sparse dissonant violin harmonics and a faint low pulse. Very slow, empty and unsettling, no drums. Keep the mood steady from start to finish with no intro and no ending, so it can loop seamlessly."
- Generation: 155 s requested, instrumental
- Loop: source 0.00–144.01 s, crossfade match score 0.22

### MUS_Combat_Layer

- Cue: `/Game/Audio/Jam/Cues/SCue_MUS_Combat_Layer` — class `SCL_Jam_Music_Combat`, volume 1.0, looping
- Wave: `SW_MUS_Combat_Layer` (38.4 s, loop)
- Loudness: -21.0 LUFS integrated
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth_music.py`. Will be replaced in place by the ElevenLabs take below.
- Queued ElevenLabs prompt: "Relentless combat percussion loop: driving large ensemble drums, tight snare rolls, deep booming hits and a low pulsing sub, 100 BPM, aggressive and urgent. Percussion only, no melody, no chords. Constant intensity from start to finish with no intro and no ending, so it can loop seamlessly."

### MUS_Victory_Sting

- Cue: `/Game/Audio/Jam/Cues/SCue_MUS_Victory_Sting` — class `SCL_Jam_Music_Combat`, volume 1.0
- Wave: `SW_MUS_Victory_Sting` (6.0 s)
- Loudness: -17.0 LUFS integrated
- Source: **procedural stand-in** (not AI): numpy synthesis, `synth_music.py`. Will be replaced in place by the ElevenLabs take below.
- Queued ElevenLabs prompt: "Short triumphant orchestral victory sting: bold brass fanfare over a timpani roll, resolving on a bright major chord and ending cleanly with a short reverb tail. Starts immediately at full energy."

## Voices (OpenAI realtime audio model)

Model: OpenAI realtime audio (see the AI declaration above). Waves: `/Game/Audio/Jam/Voice/<Group>/SW_VO_<LineId>` (mono 24 kHz, trimmed, character FX, leveled, subtitles set). Cues: `/Game/Audio/Jam/Voice/Cues/`. NPC and Tarnish voices are 3D (`ATT_Jam_NPCVoice`, attach to the speaker's head); the narrator and `SCue_VO_Tarnish_Taunt_Head` / `_Hop_Head` are 2D. Sound class `SCL_Jam_Voice` routes through the jam limiter. Concurrency: `SCON_Jam_Barks` (3 at a time, 0.5 s retrigger), `SCON_Jam_Tarnish` and `SCON_Jam_Narrator` (one at a time). Status: generated and imported.

| Cue | Lines | When | Owner |
|---|---|---|---|
| `SCue_VO_Tarnish_Taunt` | 6 (random) | Taunt while possessing a host or during the boss fight | villain session |
| `SCue_VO_Tarnish_Hop` | 3 (random) | The Tarnish takes a new host (play with SCue_Villain_Hop) | villain session |
| `SCue_VO_Tarnish_Manifest` | 2 (random) | True form appears (play after SCue_Villain_Manifest) | villain session |
| `SCue_VO_Tarnish_PhaseTwo` | 1 (random) | Boss phase two: it tears loose from its shroud | villain session |
| `SCue_VO_Tarnish_Cured` | 2 (random) | The player burns the Tarnish out of someone (at most once per 10 s) | villain session |
| `SCue_VO_Tarnish_Hurt` | 3 (random) | Hit by the Final Spell (with SCue_Villain_Hurt) | villain session |
| `SCue_VO_Tarnish_Death` | 2 (random) | Death (with SCue_Villain_Death) | villain session |
| `SCue_VO_Narrator_Intro` | 1 | "Lanthorne was cut into three reflections, and only one is the version its maker meant. The Tarnish wants the final cut." | game-flow-ui |
| `SCue_VO_Narrator_Tip_Aim` | 1 | "Hold to aim. The glow shows where your spell will land." | game-flow-ui |
| `SCue_VO_Narrator_Tip_Cast` | 1 | "Then cast. Each element answers differently: fire burns, ice slows, lightning leaps." | game-flow-ui |
| `SCue_VO_Narrator_Tip_Shard` | 1 | "Mirror shards let you step through. Stepping through also takes most of your magic." | game-flow-ui |
| `SCue_VO_Narrator_Tip_StepThrough` | 1 | "Step up into the next side, or down into the one below. Pewterside, Giltside, Frostside: the same streets, in three different lights." | game-flow-ui |
| `SCue_VO_Narrator_Tip_Crafting` | 1 | "Build your own spells. Choose a form, an element, and how it behaves, then cast what you made." | game-flow-ui |
| `SCue_VO_Narrator_FirstHost` | 1 | "The Tarnish has taken a face. Watch for the burning eyes." | game-flow-ui |
| `SCue_VO_Narrator_MirrorWhole` | 1 | "The mirror is whole. The Final Spell is yours. Now burn out the Tarnish." | game-flow-ui |
| `SCue_VO_Narrator_FinalSpellHint` | 1 | "Ordinary spells barely touch it. Only the Final Spell can burn it out." | game-flow-ui |
| `SCue_VO_Narrator_Victory` | 1 | "The Tarnish is burned out. Lanthorne is itself again." | game-flow-ui |
| `SCue_VO_Civilian_Fear_<F1..F3,M1..M3>` (+ fallback `SCue_VO_Civilian_Fear`) | 2 per voice slot | Civilian/Timid starts Fleeing or is hit | npc-unify (NPC reactions) |
| `SCue_VO_Guard_Alert_<F1..F3,M1..M3>` (+ fallback `SCue_VO_Guard_Alert`) | 2 per voice slot | Guard enters Alert / Investigating | npc-unify (NPC reactions) |
| `SCue_VO_Guard_Attack_<F1..F3,M1..M3>` (+ fallback `SCue_VO_Guard_Attack`) | 1 per voice slot | Guard switches to Attacking | npc-unify (NPC reactions) |
| `SCue_VO_Soldier_Command_<F1..F3,M1..M3>` (+ fallback `SCue_VO_Soldier_Command`) | 3 per voice slot | Soldier / SoldierCaster squad command (on engage, every few seconds in combat) | soldier-squads |
| `SCue_VO_Tarnished_Mutter_<F1..F3,M1..M3>` (+ fallback `SCue_VO_Tarnished_Mutter`) | 2 per voice slot | Tarnished (Infected / VillainHost) idle or aggro mutter (layer with SCue_Infected_Growl) | npc-unify (NPC reactions) |
| `SCue_VO_Civilian_Talk_<F1..F3,M1..M3>` (+ fallback `SCue_VO_Civilian_Talk`) | 1 per voice slot | Calm civilian answer when the player talks to them | NPC dialogue session (talk-back fallback) |
| `SCue_VO_Guard_Talk_<F1..F3,M1..M3>` (+ fallback `SCue_VO_Guard_Talk`) | 1 per voice slot | Calm guard answer when the player talks to them | NPC dialogue session (talk-back fallback) |
| `SCue_VO_Soldier_Talk_<F1..F3,M1..M3>` (+ fallback `SCue_VO_Soldier_Talk`) | 1 per voice slot | Calm soldier answer when the player talks to them | NPC dialogue session (talk-back fallback) |
| `SCue_VO_CS01_06` | 1 | "Silverer. We've been watching you in every window." | villain session |
| `SCue_VO_CS02_04` | 1 | "Shh. Let him hum for us." | villain session |
| `SCue_VO_CS03_03` | 1 | "You moved a page, Silverer. We felt it in every face." | villain session |
| `SCue_VO_CS04_05` | 1 | "Up you go, Silverer. We'll be waiting at the top." | villain session |
| `SCue_VO_CS05_01` | 1 | "Three leaves, one mirror. And one Silverer left to look into it." | villain session |
| `SCue_VO_CS05_03` | 1 | "Climb, then. She climbed too." | villain session |
| `SCue_VO_MQ02_02` | 1 | "Your friend hums when he's frightened. We like the tune." | villain session |
| `SCue_VO_MQ07_02` | 1 | "Two leaves. You're building us a door, Silverer." | villain session |
| `SCue_VO_MQ08_05` | 1 | "She stood just there, your mother. Right where you are." | villain session |
| `SCue_VO_MQ09_01` | 1 | "Look, Silverer. Three of you in the glass, and none of them sure." | villain session |
| `SCue_VO_MQ09_03` | 1 | "She called your name at the end. Shall we tell you how it sounded?" | villain session |
| `SCue_VO_MQ09_05` | 1 | "Every face you save... still has a dark side..." | villain session |
| `SCue_VO_MQ_BAND_01` | 1 | "Five faces now. They're all a little like you." | villain session |
| `SCue_VO_MQ_BAND_02` | 1 | "Half a street of us. Can you hear us humming?" | villain session |
| `SCue_VO_MQ_BAND_03` | 1 | "Nearly enough of us to wear the whole city." | villain session |
| `SCue_VO_MQ_LOSE_01` | 1 | "Every face in Lanthorne, and every one of them fits." | villain session |

Full line list, voices and delivery instructions: `ArtDirection/Audio/VoiceScript.md`.

## Crowd voices (Gemini roster, one voice per NPC)

137 designed voices (`DT_NpcVoiceRoster`, row name = VoiceId `V001`–`V137`; NPC unify picks one per NPC by sex, side and character). Every cue is 3D (`ATT_Jam_NPCVoice`, attach to the head), class `SCL_Jam_Voice`. Cue path: `/Game/Audio/Jam/Voice/Cues/<Group>/SCue_VO_<Group>_<VoiceId>`, found by `FindVoiceCue(Actor, Group)` before the 6-slot cues above. No line is shared between two voices.

| Group | Voices | Lines per voice | When | Owner |
|---|---|---|---|---|
| `Remark` | all | 2 | calm NPC, player within ~4.5 m, 60–90 s cooldown | npc-unify |
| `Reply` | all | 3 | the player talks to the NPC (Talk resolves here) | NPC dialogue session |
| `Filler` | all | 2 | short beat before a reply | NPC dialogue session |
| `Civilian_Fear` | civilians | 3 | flee / hit / sees the tarnished | npc-unify |
| `Guard_Alert` | guards | 3 | guard enters Alert | npc-unify |
| `Guard_Attack` | guards | 2 | guard starts attacking | npc-unify |
| `Soldier_Command` | soldiers | 4 | squad commands in combat | soldier-squads |
| `Tarnished_Mutter` | all | 2 | after the NPC is taken (tarnished FX baked in) | npc-unify |

## Story voices (ArtDirection/Story)

- **Scripted lines:** 169 main-quest, side-quest and cutscene lines as `/Game/Audio/Jam/Voice/Cues/SCue_VO_<LineId>` (waves in `/Game/Audio/Jam/Voice/Story/`). Cutscene cues and 2D lines (MQ07_02, MQ_BAND_01-03, MQ_LOSE_01, Wren's quest lines) have no attenuation; MQ09_01-05 and townspeople's quest lines use `ATT_Jam_NPCVoice`. MQ05_01/CS03_03 and MQ05_02/CS03_04 share one take.
- **Wren Hale (hero):** Gemini designed voice `voice_wnw870hwv7ds` (candidate B). The user asked for a unique, captivating designed voice (never the original); four candidates read the same lines and Gemini's audio understanding picked B (`voice/hero_judgement.json`).
- **The Tarnish:** its story lines use its existing OpenAI voice and FX, matching the lines already in the game.
- **Named people (42):** each has a reserved roster voice (`bEnabled = false` in `DT_NpcVoiceRoster`) and story barks as groups Greet, Idle, SeeTarnished, Flee, SpellNear, Thanks, Dread, Farewell, Cured, TarnishedLine (`/Cues/<Group>/SCue_VO_<Group>_<VoiceId>`), also fed into Civilian_Fear, Remark, Reply and Tarnished_Mutter. Story-clique conversations are in `/Game/Audio/Jam/Voice/Ambient/DT_StoryConversations` (played by lives via PlayConversationById, with Band and RequiredFlag).
- **Fill voices:** reserving the named people's voices left gaps, so extra unnamed voices were added: V121-V132 (Pewterside civilians, `tools/add_pewterside.py`) and V133-V137 (women guards: 2 Giltside, 2 Pewterside, 1 Frostside, `tools/add_guards.py`). Before V133-V137, every Giltside and Pewterside women's guard voice was reserved, so a third unnamed woman guard fell back to a civilian voice.
- **Acceptance:** a take is kept when a transcript matches the script word for word, or letter for letter once spacing, apostrophes and interjections are ignored; any spelling of "Silverer" passes (user decision). A few takes whose only difference is a misheard name or accent word are kept with a note in `voice/gemini/manifest.json`.

Street conversations: `/Game/Audio/Jam/Voice/Ambient/<CliqueId>/SW_AMB_<ConvId>_<n>`, listed in `/Game/Audio/Jam/Voice/Ambient/DT_AmbientConversations` for the crowd director (48 cliques × 6 conversations).

## Not generated / known gaps

- The ElevenLabs connector is on the free tier; it stopped accepting generations after 6 takes (16:17 UTC) and is retried hourly. Sounds marked stand-in are layered procedural designs (numpy synthesis, rendered offline into the same SoundCues so wiring never changes). When an ElevenLabs take arrives it replaces the waves inside the cue. The queued prompt is listed with each stand-in.
- Stand-ins were designed as shippable, not as silent placeholders: per-element layered spells (fire crackle+whoosh+roar, water slosh+bubbles, ice crystals+metallic pings, lightning crack+arc buzz+thunder, earth thud+grit+debris, arcane bell shimmer+FM hum), 2-4 variations each plus cue randomization.
- Most clearly synthetic: `Infected_Growl` and `Villain_Voice` (modelled voices: pulse train with period doubling, rattle and formants, plus articulated whisper syllables; they carry no real words) and `MUS_Victory_Sting` (synth brass). Replace these first if an ElevenLabs slot opens or the plan is upgraded.
- No ambience beds (rain for Pewterside, battle din for Giltside, wind for Frostside) were requested or made. The Pewterside music carries the rainy mood.
- Nobody has listened to these yet. They were checked by playing every cue through the editor preview, by spectrogram review of every stand-in, and by signal checks (loudness, peaks, duration, loop-seam continuity). Do a listening pass before submission.

## Size

Editor source in `Content/Audio/Jam` is about 55 MB (uncompressed 16-bit PCM kept for re-import). The cooked size is much smaller: SFX are mono and compressed at quality 40, music at quality 50 (Bink). Packaging always-cooks `/Game/Audio/Jam` and will report the measured cooked size; the expected total is under 15 MB.

## Regenerating

The ElevenLabs flow is id `NoxuIlopg9X9ZlS5daRm` (one node per sound, labelled with the sound name). The scripts are in `ArtDirection/Audio/tools/` (Python 3 + numpy; MP3 decoding uses the engine's bundled libsndfile). Set `ROOT` to a work folder, then: `fetch.py` downloads a take, `process_sfx.py` / `process_music.py` trim, mono-mix, normalize, slice and loop it, `synth.py` / `synth_music.py` render the procedural stand-ins, `ue_build.py` (exec'd in the editor's Python) imports the waves and rebuilds the cues in place, and `gen_readme.py` rewrites this file from `catalog.py`.
