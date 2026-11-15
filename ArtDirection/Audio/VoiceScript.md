# Reflections: voice script (OpenAI text-to-speech)

Generated offline with OpenAI's realtime audio model (`gpt-4o-mini-tts`, `gpt-realtime-2.1`); `gpt-4o-mini-tts` is the fallback for any take whose transcript doesn't match the script word for word. Voices are AI-generated, not performed by actors; the credits and the itch page must say so (see `ArtDirection/Submission/ai-declaration.md`). Names follow `ArtDirection/Submission/canon.md`. The script is `ArtDirection/Audio/tools/voice_script.py`; edit lines there and run `realtime_tts.py`.

**Prompt per line** (session instructions): the actor rules, then the speaker's character and delivery brief from the table below, then the pronunciation guide. The line itself is sent as the user message `Line: <text>`.

> You are a professional voice actor recording a single line for a video game. You will be given exactly one line. Perform it once, word for word, exactly as written: do not add, drop, change, translate or repeat any words, and do not greet, answer, explain or ask anything. Speak only the line, in English, in character.
>
> Pronunciation: Lanthorne is LANT-horn; Pewterside is PYOO-ter-side; Giltside is GILT-side; Frostside is FROST-side; Silverer is SIL-ver-er; Tarnish is TAR-nish.

## Speakers

| Speaker | Realtime voice | Character and delivery brief | Post-FX |
|---|---|---|---|
| Tarnish | `cedar` | You are the Tarnish, an ancient, cold presence speaking through a stolen body. Speak low, slow and close to the microphone, half-whispered and intimate, with quiet amusement and contempt. Never rush. Let words trail off. | tarnish |
| TarnishDeath | `cedar` | You are the Tarnish, being burned away by light. Strained, cracking, fading in and out, bitter to the last breath, the final words almost a whisper. | tarnish |
| Narrator | `marin` | A warm, friendly guide giving the player brief tips. Natural conversational pace, clear and concise, with a touch of wonder. Keep pauses short. Never sound like an advert. | narrator |

NPC bark speakers are `<Group>@<Slot>`: instructions = the slot persona + the group delivery (see below).

## Per-NPC voice slots

Every NPC keeps one voice slot (chosen by the NPC system from its sex): F1-F3 female, M1-M3 male. Each bark group exists in every slot as `SCue_VO_<Group>_<Slot>`; `SCue_VO_<Group>` (no slot) is a fallback that picks across all slots.

| Slot | Realtime voice | Persona |
|---|---|---|
| F1 | `coral` | a young woman in her twenties with a quick, bright voice |
| F2 | `sage` | a woman in her forties with a firm, slightly husky, practical voice |
| F3 | `shimmer` | an older woman in her sixties with a thinner, warm but shaky voice |
| M1 | `ash` | a young man in his twenties with a quick, tense voice |
| M2 | `echo` | a man in his forties with a steady, gruff voice |
| M3 | `verse` | an older man in his sixties with a deep, weathered, slower voice |

## Cues and lines

### `SCue_VO_Tarnish_Taunt` (6 lines, picked at random)

Owner: villain session. When: Taunt while possessing a host or during the boss fight.

| Line id | Speaker | Text | Engine / voice / tries |
|---|---|---|---|
| `Tarnish_Taunt_01` | Tarnish | Every face in Lanthorne will wear me, sooner or later. | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Taunt_02` | Tarnish | You polish. I spread. | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Taunt_03` | Tarnish | Look closer, Silverer. I'm already on you. | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Taunt_04` | Tarnish | Three reflections... and I am in all of them. | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Taunt_05` | Tarnish | Break the glass if you like. I'll still be here. | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Taunt_06` | Tarnish | This one is warm. I think I'll keep it. | `gpt-realtime-2.1` / `cedar` / 1 |

### `SCue_VO_Tarnish_Hop` (3 lines, picked at random)

Owner: villain session. When: The Tarnish takes a new host (play with SCue_Villain_Hop).

| Line id | Speaker | Text | Engine / voice / tries |
|---|---|---|---|
| `Tarnish_Hop_01` | Tarnish | A new face. How fitting. | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Hop_02` | Tarnish | Not that one... this one. | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Hop_03` | Tarnish | Did you miss me? | `gpt-realtime-2.1` / `cedar` / 1 |

### `SCue_VO_Tarnish_Manifest` (2 lines, picked at random)

Owner: villain session. When: True form appears (play after SCue_Villain_Manifest).

| Line id | Speaker | Text | Engine / voice / tries |
|---|---|---|---|
| `Tarnish_Manifest_01` | Tarnish | Enough masks. See what Lanthorne was always hiding. | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Manifest_02` | Tarnish | Its maker wanted one true Lanthorne. I'll make the final cut. | `gpt-realtime-2.1` / `cedar` / 1 |

### `SCue_VO_Tarnish_PhaseTwo` (1 lines, picked at random)

Owner: villain session. When: Boss phase two: it tears loose from its shroud.

| Line id | Speaker | Text | Engine / voice / tries |
|---|---|---|---|
| `Tarnish_PhaseTwo_01` | Tarnish | You only scratched the surface. | `gpt-realtime-2.1` / `cedar` / 1 |

### `SCue_VO_Tarnish_Cured` (2 lines, picked at random)

Owner: villain session. When: The player burns the Tarnish out of someone (at most once per 10 s).

| Line id | Speaker | Text | Engine / voice / tries |
|---|---|---|---|
| `Tarnish_Cured_01` | Tarnish | You can't polish them all. | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Cured_02` | Tarnish | There are always more faces. | `gpt-realtime-2.1` / `cedar` / 1 |

### `SCue_VO_Tarnish_Hurt` (3 lines, picked at random)

Owner: villain session. When: Hit by the Final Spell (with SCue_Villain_Hurt).

| Line id | Speaker | Text | Engine / voice / tries |
|---|---|---|---|
| `Tarnish_Hurt_01` | TarnishDeath | No... that light! | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Hurt_02` | TarnishDeath | Stop... shining! | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Hurt_03` | TarnishDeath | It burns... it burns clean... | `gpt-realtime-2.1` / `cedar` / 1 |

### `SCue_VO_Tarnish_Death` (2 lines, picked at random)

Owner: villain session. When: Death (with SCue_Villain_Death).

| Line id | Speaker | Text | Engine / voice / tries |
|---|---|---|---|
| `Tarnish_Death_01` | TarnishDeath | Polish all you like... everything dulls again... | `gpt-realtime-2.1` / `cedar` / 1 |
| `Tarnish_Death_02` | TarnishDeath | I was... the truest reflection... | `gpt-realtime-2.1` / `cedar` / 1 |

### Narrator (10 cues, one per line: `SCue_VO_<LineId>`)

Owner: game-flow-ui. When: Narration and one-time tips (one cue per line).

| Line id | Speaker | Text | Engine / voice / tries |
|---|---|---|---|
| `Narrator_Intro` | Narrator | Lanthorne was cut into three reflections, and only one is the version its maker meant. The Tarnish wants the final cut. | `gpt-realtime-2.1` / `marin` / 1 |
| `Narrator_Tip_Aim` | Narrator | Hold to aim. The glow shows where your spell will land. | `gpt-realtime-2.1` / `marin` / 1 |
| `Narrator_Tip_Cast` | Narrator | Then cast. Each element answers differently: fire burns, ice slows, lightning leaps. | `gpt-realtime-2.1` / `marin` / 1 |
| `Narrator_Tip_Shard` | Narrator | Mirror shards let you step through. Stepping through also takes most of your magic. | `gpt-realtime-2.1` / `marin` / 1 |
| `Narrator_Tip_StepThrough` | Narrator | Step up into the next side, or down into the one below. Pewterside, Giltside, Frostside: the same streets, in three different lights. | `gpt-realtime-2.1` / `marin` / 1 |
| `Narrator_Tip_Crafting` | Narrator | Build your own spells. Choose a form, an element, and how it behaves, then cast what you made. | `gpt-realtime-2.1` / `marin` / 1 |
| `Narrator_FirstHost` | Narrator | The Tarnish has taken a face. Watch for the burning eyes. | `gpt-realtime-2.1` / `marin` / 1 |
| `Narrator_MirrorWhole` | Narrator | The mirror is whole. The Final Spell is yours. Now burn out the Tarnish. | `gpt-realtime-2.1` / `marin` / 1 |
| `Narrator_FinalSpellHint` | Narrator | Ordinary spells barely touch it. Only the Final Spell can burn it out. | `gpt-realtime-2.1` / `marin` / 1 |
| `Narrator_Victory` | Narrator | The Tarnish is burned out. Lanthorne is itself again. | `gpt-realtime-2.1` / `marin` / 1 |

### `SCue_VO_Civilian_Fear_<Slot>` (2 line(s) per slot; fallback `SCue_VO_Civilian_Fear`)

Owner: npc-unify (NPC reactions). When: Civilian/Timid starts Fleeing or is hit. Delivery: A frightened city dweller caught in sudden magic: panicked, breathless, urgent.

| Line id | Slot | Text | Engine / voice / tries |
|---|---|---|---|
| `Civilian_Fear_F1_1` | F1 | Run! Get away from it! | `gpt-realtime-2.1` / `coral` / 1 |
| `Civilian_Fear_F1_2` | F1 | Help! Somebody help! | `gpt-realtime-2.1` / `coral` / 1 |
| `Civilian_Fear_F2_1` | F2 | Please, don't hurt me! | `gpt-realtime-2.1` / `sage` / 1 |
| `Civilian_Fear_F2_2` | F2 | Magic! Get inside, get inside! | `gpt-realtime-2.1` / `sage` / 2 |
| `Civilian_Fear_F3_1` | F3 | Its eyes... they're burning! Run! | `gpt-realtime-2.1` / `shimmer` / 1 |
| `Civilian_Fear_F3_2` | F3 | No, no, no, no... | `gpt-realtime-2.1` / `shimmer` / 2 |
| `Civilian_Fear_M1_1` | M1 | Help! Somebody help! | `gpt-realtime-2.1` / `ash` / 1 |
| `Civilian_Fear_M1_2` | M1 | Please, don't hurt me! | `gpt-realtime-2.1` / `ash` / 1 |
| `Civilian_Fear_M2_1` | M2 | Magic! Get inside, get inside! | `gpt-realtime-2.1` / `echo` / 2 |
| `Civilian_Fear_M2_2` | M2 | Its eyes... they're burning! Run! | `gpt-realtime-2.1` / `echo` / 1 |
| `Civilian_Fear_M3_1` | M3 | No, no, no, no... | `gpt-realtime-2.1` / `verse` / 1 |
| `Civilian_Fear_M3_2` | M3 | Run! Get away from it! | `gpt-realtime-2.1` / `verse` / 1 |

### `SCue_VO_Guard_Alert_<Slot>` (2 line(s) per slot; fallback `SCue_VO_Guard_Alert`)

Owner: npc-unify (NPC reactions). When: Guard enters Alert / Investigating. Delivery: A city watch guard spotting trouble: loud, commanding and suspicious, projecting across a street.

| Line id | Slot | Text | Engine / voice / tries |
|---|---|---|---|
| `Guard_Alert_F1_1` | F1 | Halt! Who goes there? | `gpt-realtime-2.1` / `coral` / 1 |
| `Guard_Alert_F1_2` | F1 | Stop right there, caster! | `gpt-realtime-2.1` / `coral` / 1 |
| `Guard_Alert_F2_1` | F2 | Spellwork in the street! Stand down! | `gpt-realtime-2.1` / `sage` / 1 |
| `Guard_Alert_F2_2` | F2 | You there! Show me your hands! | `gpt-realtime-2.1` / `sage` / 1 |
| `Guard_Alert_F3_1` | F3 | Something's wrong here. Stay sharp. | `gpt-realtime-2.1` / `shimmer` / 1 |
| `Guard_Alert_F3_2` | F3 | Halt! Who goes there? | `gpt-realtime-2.1` / `shimmer` / 1 |
| `Guard_Alert_M1_1` | M1 | Spellwork in the street! Stand down! | `gpt-realtime-2.1` / `ash` / 1 |
| `Guard_Alert_M1_2` | M1 | You there! Show me your hands! | `gpt-realtime-2.1` / `ash` / 1 |
| `Guard_Alert_M2_1` | M2 | Something's wrong here. Stay sharp. | `gpt-realtime-2.1` / `echo` / 1 |
| `Guard_Alert_M2_2` | M2 | Halt! Who goes there? | `gpt-realtime-2.1` / `echo` / 1 |
| `Guard_Alert_M3_1` | M3 | Stop right there, caster! | `gpt-realtime-2.1` / `verse` / 1 |
| `Guard_Alert_M3_2` | M3 | Spellwork in the street! Stand down! | `gpt-realtime-2.1` / `verse` / 1 |

### `SCue_VO_Guard_Attack_<Slot>` (1 line(s) per slot; fallback `SCue_VO_Guard_Attack`)

Owner: npc-unify (NPC reactions). When: Guard switches to Attacking. Delivery: A city watch guard charging into a fight: shouted, aggressive and decisive.

| Line id | Slot | Text | Engine / voice / tries |
|---|---|---|---|
| `Guard_Attack_F1_1` | F1 | That's it, you're coming with us! | `gpt-realtime-2.1` / `coral` / 1 |
| `Guard_Attack_F2_1` | F2 | Take them down! | `gpt-realtime-2.1` / `sage` / 1 |
| `Guard_Attack_F3_1` | F3 | For the watch! | `gpt-realtime-2.1` / `shimmer` / 2 |
| `Guard_Attack_M1_1` | M1 | Take them down! | `gpt-realtime-2.1` / `ash` / 1 |
| `Guard_Attack_M2_1` | M2 | For the watch! | `gpt-realtime-2.1` / `echo` / 2 |
| `Guard_Attack_M3_1` | M3 | That's it, you're coming with us! | `gpt-realtime-2.1` / `verse` / 1 |

### `SCue_VO_Soldier_Command_<Slot>` (3 line(s) per slot; fallback `SCue_VO_Soldier_Command`)

Owner: soldier-squads. When: Soldier / SoldierCaster squad command (on engage, every few seconds in combat). Delivery: A soldier in a war-torn street barking orders to their squad over the din of battle: shouted, clipped, urgent.

| Line id | Slot | Text | Engine / voice / tries |
|---|---|---|---|
| `Soldier_Command_F1_1` | F1 | Shields up! Hold the line! | `gpt-realtime-2.1` / `coral` / 2 |
| `Soldier_Command_F1_2` | F1 | Casters, on me! | `gpt-realtime-2.1` / `coral` / 3 |
| `Soldier_Command_F1_3` | F1 | Flank left! Go, go! | `gpt-4o-mini-tts` / `coral` / 3 |
| `Soldier_Command_F2_1` | F2 | Fall back! Regroup! | `gpt-realtime-2.1` / `sage` / 1 |
| `Soldier_Command_F2_2` | F2 | Loose your spells! Now! | `gpt-4o-mini-tts` / `sage` / 3 |
| `Soldier_Command_F2_3` | F2 | Push forward! For Giltside! | `gpt-realtime-2.1` / `sage` / 2 |
| `Soldier_Command_F3_1` | F3 | Shields up! Hold the line! | `gpt-realtime-2.1` / `shimmer` / 1 |
| `Soldier_Command_F3_2` | F3 | Casters, on me! | `gpt-4o-mini-tts` / `shimmer` / 3 |
| `Soldier_Command_F3_3` | F3 | Flank left! Go, go! | `gpt-realtime-2.1` / `shimmer` / 1 |
| `Soldier_Command_M1_1` | M1 | Loose your spells! Now! | `gpt-realtime-2.1` / `ash` / 1 |
| `Soldier_Command_M1_2` | M1 | Push forward! For Giltside! | `gpt-4o-mini-tts` / `ash` / 3 |
| `Soldier_Command_M1_3` | M1 | Shields up! Hold the line! | `gpt-realtime-2.1` / `ash` / 1 |
| `Soldier_Command_M2_1` | M2 | Casters, on me! | `gpt-realtime-2.1` / `echo` / 3 |
| `Soldier_Command_M2_2` | M2 | Flank left! Go, go! | `gpt-4o-mini-tts` / `echo` / 3 |
| `Soldier_Command_M2_3` | M2 | Fall back! Regroup! | `gpt-realtime-2.1` / `echo` / 1 |
| `Soldier_Command_M3_1` | M3 | Loose your spells! Now! | `gpt-realtime-2.1` / `verse` / 1 |
| `Soldier_Command_M3_2` | M3 | Push forward! For Giltside! | `gpt-4o-mini-tts` / `verse` / 3 |
| `Soldier_Command_M3_3` | M3 | Shields up! Hold the line! | `gpt-realtime-2.1` / `verse` / 1 |

### `SCue_VO_Tarnished_Mutter_<Slot>` (2 line(s) per slot; fallback `SCue_VO_Tarnished_Mutter`)

Owner: npc-unify (NPC reactions). When: Tarnished (Infected / VillainHost) idle or aggro mutter (layer with SCue_Infected_Growl). Delivery: A person possessed by the Tarnish: hollow, flat, slow and murmured, as if someone else is moving the mouth.

| Line id | Slot | Text | Engine / voice / tries |
|---|---|---|---|
| `Tarnished_Mutter_F1_1` | F1 | So... dull... so quiet... | `gpt-realtime-2.1` / `coral` / 1 |
| `Tarnished_Mutter_F1_2` | F1 | Hold still... let it spread... | `gpt-realtime-2.1` / `coral` / 1 |
| `Tarnished_Mutter_F2_1` | F2 | The glass is cracked... let it in... | `gpt-realtime-2.1` / `sage` / 2 |
| `Tarnished_Mutter_F2_2` | F2 | Join us... don't shine... | `gpt-realtime-2.1` / `sage` / 2 |
| `Tarnished_Mutter_F3_1` | F3 | We are... the Tarnish... | `gpt-realtime-2.1` / `shimmer` / 1 |
| `Tarnished_Mutter_F3_2` | F3 | So... dull... so quiet... | `gpt-realtime-2.1` / `shimmer` / 1 |
| `Tarnished_Mutter_M1_1` | M1 | The glass is cracked... let it in... | `gpt-realtime-2.1` / `ash` / 1 |
| `Tarnished_Mutter_M1_2` | M1 | Join us... don't shine... | `gpt-realtime-2.1` / `ash` / 1 |
| `Tarnished_Mutter_M2_1` | M2 | We are... the Tarnish... | `gpt-realtime-2.1` / `echo` / 2 |
| `Tarnished_Mutter_M2_2` | M2 | So... dull... so quiet... | `gpt-4o-mini-tts` / `echo` / 3 |
| `Tarnished_Mutter_M3_1` | M3 | Hold still... let it spread... | `gpt-4o-mini-tts` / `verse` / 3 |
| `Tarnished_Mutter_M3_2` | M3 | The glass is cracked... let it in... | `gpt-realtime-2.1` / `verse` / 1 |

### `SCue_VO_Civilian_Talk_<Slot>` (1 line(s) per slot; fallback `SCue_VO_Civilian_Talk`)

Owner: NPC dialogue session (talk-back fallback). When: Calm civilian answer when the player talks to them. Delivery: A city dweller answering a stranger in passing: quick, quiet, a little uneasy, natural pace.

| Line id | Slot | Text | Engine / voice / tries |
|---|---|---|---|
| `Civilian_Talk_F1_1` | F1 | Can't stop now. Mind the glass. | `gpt-realtime-2.1` / `coral` / 1 |
| `Civilian_Talk_F2_1` | F2 | Strange times. Keep out of the cold. | `gpt-realtime-2.1` / `sage` / 1 |
| `Civilian_Talk_F3_1` | F3 | Keep your head down out here. | `gpt-realtime-2.1` / `shimmer` / 1 |
| `Civilian_Talk_M1_1` | M1 | Strange times. Keep out of the cold. | `gpt-realtime-2.1` / `ash` / 1 |
| `Civilian_Talk_M2_1` | M2 | Keep your head down out here. | `gpt-realtime-2.1` / `echo` / 1 |
| `Civilian_Talk_M3_1` | M3 | Can't stop now. Mind the glass. | `gpt-realtime-2.1` / `verse` / 1 |

### `SCue_VO_Guard_Talk_<Slot>` (1 line(s) per slot; fallback `SCue_VO_Guard_Talk`)

Owner: NPC dialogue session (talk-back fallback). When: Calm guard answer when the player talks to them. Delivery: A city watch guard answering a passer-by: calm, firm and dry, not shouting.

| Line id | Slot | Text | Engine / voice / tries |
|---|---|---|---|
| `Guard_Talk_F1_1` | F1 | Move along. The watch has eyes on you. | `gpt-realtime-2.1` / `coral` / 1 |
| `Guard_Talk_F2_1` | F2 | No spellwork in the street. Understood? | `gpt-realtime-2.1` / `sage` / 1 |
| `Guard_Talk_F3_1` | F3 | Keep it quiet and you'll have no trouble. | `gpt-realtime-2.1` / `shimmer` / 1 |
| `Guard_Talk_M1_1` | M1 | No spellwork in the street. Understood? | `gpt-realtime-2.1` / `ash` / 1 |
| `Guard_Talk_M2_1` | M2 | Keep it quiet and you'll have no trouble. | `gpt-realtime-2.1` / `echo` / 1 |
| `Guard_Talk_M3_1` | M3 | Move along. The watch has eyes on you. | `gpt-realtime-2.1` / `verse` / 1 |

### `SCue_VO_Soldier_Talk_<Slot>` (1 line(s) per slot; fallback `SCue_VO_Soldier_Talk`)

Owner: NPC dialogue session (talk-back fallback). When: Calm soldier answer when the player talks to them. Delivery: A soldier on duty answering a civilian: curt, steady, at speaking volume, not shouting.

| Line id | Slot | Text | Engine / voice / tries |
|---|---|---|---|
| `Soldier_Talk_F1_1` | F1 | Keep your distance. We march on orders. | `gpt-realtime-2.1` / `coral` / 1 |
| `Soldier_Talk_F2_1` | F2 | Not now. We're holding this street. | `gpt-realtime-2.1` / `sage` / 1 |
| `Soldier_Talk_F3_1` | F3 | Stay behind the line. | `gpt-realtime-2.1` / `shimmer` / 1 |
| `Soldier_Talk_M1_1` | M1 | Not now. We're holding this street. | `gpt-realtime-2.1` / `ash` / 1 |
| `Soldier_Talk_M2_1` | M2 | Stay behind the line. | `gpt-realtime-2.1` / `echo` / 1 |
| `Soldier_Talk_M3_1` | M3 | Keep your distance. We march on orders. | `gpt-realtime-2.1` / `verse` / 1 |

