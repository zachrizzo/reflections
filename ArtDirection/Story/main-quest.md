# Main quest: "The Mirror Made Whole"

Owner: the story session. Built from by the quest-system and cutscene sessions. Story background is in [bible.md](bible.md); the people (ids, voices, markers) are in [people.json](people.json).

The quest has 10 beats, MQ00 to MQ09, over four acts. Every trigger is an event the game already fires, unless it is marked **(quest system)**, which means the quest system computes it itself from existing state.

## Conventions

- **Events** (all exist today):
  - `UReflectionsWorldJumpSubsystem`: `OnWorldChanged(From, To)`, `OnCoinsChanged(World, Count)` (shards), `OnPagesChanged(Pages, PagesForBook)`, `OnBookComplete`, `OnKeyAdded(KeyId)`.
  - The sealed door: `AReflectionsSealedDoor::OnOpened`.
  - `UReflectionsNpcSubsystem`: `OnNpcInfection(Npc, State, Source)`, `OnNpcSpellHit`, `OnNpcDied`.
  - `UReflectionsGameFlowSubsystem`: `OnInfectionChanged(Count, Cap)`, `OnGameLost`, `OnVictory`, `OnCheckpointSaved`.
- **Code names:** in code the sides are Gray = Pewterside, Red = Giltside, White = Frostside. Players never see those names.
- **Named people in the level** carry the actor tag `Person_<id>`, for example `Person_ilse_varrow`. If a beat's person isn't placed, the quest system spawns them at their `markers.work` (see people.json) or skips their lines. No beat is blocked by a missing NPC.
- **Places** are `Mk_…` marker tags; people.json → `markers` gives the fallback rules. Objective markers point at the marker, or at the named actor or pickup when one exists.
- **"Talk to X"** completes when the player opens a conversation with that NPC (hold T, or Enter), or stands within 3 m of them for 2 seconds. Then the beat's scripted lines play as baked voice. Live replies stay available afterwards.
- **Lines:**
  - Barks are under about 3 seconds; cutscene lines are under about 5.
  - Speaker ids are people.json ids, plus `wren_hale`, `the_tarnish` and `narrator`.
  - Each line has an id, `MQxx_nn`, for the audio session, and every line is unique.
  - Wren's existing canon lines (canon.md) still fire from their own triggers; the beats below don't repeat them.
- **Journal:** each beat has a one-line journal entry in Wren's voice for the quest journal.

## Flow at a glance

```
MQ00 Intro (CS01) → MQ01 Lantern Row → MQ02 The First Face (CS02) → MQ03 Through the Glass
  → MQ04 Dull as Ever → page 1 (CS03) → MQ05 Hold the Line → MQ06 The Key
  → MQ07 The Gilt Tower (CS04) → page 2 → MQ08 The Cracked Crown → page 3 (CS05)
  → MQ09 Let the Light Through → victory (CS06)
```

The order is soft wherever the game allows it. If the player grabs a shard or a page early, the quest **skips forward**: each beat's completion check runs as soon as the beat starts, so a beat already satisfied completes at once. Pages can be taken in any order. The beats below are the intended path.

---

## Act I: Lantern Law (Giltside)

### MQ00 Intro
- **Trigger:** play begins in a new game (game flow's start checkpoint with no earlier save).
- **What happens:** [CS01 "Lantern Law"](cutscenes.md#cs01-lantern-law) plays at `CutsceneAnchor_Intro` (else Wren's spawn). It's skippable.
- **Completes:** when the cutscene ends or is skipped.
- **Journal:** "Dusk bell. The Lamp Companies are marching again, and Ilse wants me on Lantern Row."

### MQ01 Lantern Row
- **Trigger:** MQ00 completes.
- **Objective:** "Find Ilse Varrow on Lantern Row" → `Person_ilse_varrow`, else `Mk_Gilt_Market_LanternRow`.
- **Meanwhile:** game flow's Aim and Cast tips run as they do now. The beat doesn't wait for them.
- **NPCs:** Ilse Varrow. Barnaby, Dov and Amos stand at the spot (clique `lantern_row`).
- **Lines** (on talk):

| Id | Speaker | Line |
|---|---|---|
| MQ01_01 | ilse_varrow | "You're late, and you're limping. Which first?" |
| MQ01_02 | wren_hale | "Neither. I came the long way." |
| MQ01_03 | ilse_varrow | "Mm. Show me your hands. Aim at the lamp post." |
| MQ01_04 | ilse_varrow | "Light's the only thing it hates. Cast like you mean it." |

- **Second objective:** "Cast a spell" (the spell driver's first cast; already counted for the Cast tip).
- **Completes:** after the first cast.

| Id | Speaker | Line |
|---|---|---|
| MQ01_05 | ilse_varrow | "Better. Now keep that hand ready. It's close tonight." |

- **Journal:** "Ilse made me cast at a lamp post like I was twelve again. She's frightened. She doesn't get frightened."

### MQ02 The First Face
- **Trigger:** the villain takes its first host: the first `OnNpcInfection` with State `VillainHost`. This is about 20 s into play (`Villain.StartDelay`). The narrator's existing "The Tarnish has taken a face" line plays here.
- **Objective 1:** "Find the burning eyes": a marker on the host actor while it lives, then on the nearest tarnished.
- **Cutscene:** [CS02 "Burning Eyes"](cutscenes.md#cs02-burning-eyes), where Jory is converted, plays when either of these happens first:
  - **(a) Scripted:** the player comes within 12 m of `CutsceneAnchor_BurningEyes` (Bell Square) while MQ02 is active. The cutscene uses `Person_jory_pell` and the nearest tarnished, and calls the villain's `BeginConversion(Attacker, Victim)` for real.
  - **(b) Fallback:** the first real conversion (`OnNpcInfection` State `Infected` with a non-null Source) within 40 m of the player. In that case the cutscene's generic variant runs, with no names.
- **Objective 2:** "Burn the Tarnish out of Jory" (variant a), or "Burn the Tarnish out of them" (variant b). It completes when that NPC's `OnNpcInfection` returns to `None` after a spell hit.
- **If Jory dies instead:** the beat still completes, the lines change, and side quest SQ2 is lost. Dark, and allowed.
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| MQ02_01 | wren_hale | Objective 1 shows | "Somebody's wearing the Tarnish. Find them." |
| MQ02_02 | the_tarnish | Jory turns (end of CS02) | "Your friend hums when he's frightened. We like the tune." |
| MQ02_03 | wren_hale | Objective 2 shows | "Hold on, Jory. This is going to sting." |
| MQ02_04 | jory_pell | Jory cured | "Ren? It was in my mouth. It was singing." |
| MQ02_05 | wren_hale | after MQ02_04 | "You're out. Breathe. It's gone from you." |
| MQ02_06 | ilse_varrow | Ilse within 20 m, else plays as a 2D line | "So light does burn it out. Good. Now you know." |
| MQ02_07 | wren_hale | Jory died instead | "No. No, I was quick. I was quick." |

- **Journal:** "It took Jory in the middle of Bell Square. Light brought him back. I didn't know it could."

### MQ03 Through the Glass
- **Trigger:** MQ02 completes.
- **Lines:**

| Id | Speaker | Line |
|---|---|---|
| MQ03_01 | ilse_varrow | "It wants the pages. So we want them first." |
| MQ03_02 | ilse_varrow | "One's on the Weigh-House roof, down in Pewterside." |
| MQ03_03 | wren_hale | "Then I need a Pewterside shard." |
| MQ03_04 | ilse_varrow | "Drifters bring them through. Ask under the Lantern Gate." |

- **Objective 1:** "Find a Pewterside shard". It completes on `OnCoinsChanged(Gray, n>0)`. The shard tip fires as it does now. The objective marker is the nearest Gray shard pickup; NPCs asked for directions can `point_the_way:nearest_shard`.
- **Optional:** if the player visits `Mk_Gilt_Camp_UnderGate`, Kit Marrow offers SQ6, and his first line points at a shard (MQ03_05).

| Id | Speaker | Line |
|---|---|---|
| MQ03_05 | kit_marrow | "Grey ones wash up here sometimes. Found one by the pillar. Yours." |
| MQ03_06 | wren_hale | (shard picked up) "Grey glass. Pewterside, then." |

- **Objective 2:** "Step down into Pewterside". It completes on `OnWorldChanged(To = Gray)`. The step tip fires as it does now.
- **Journal:** "One page in each side. The first is in Pewterside. I'm going down through the glass."

---

## Act II: Through the Glass (Pewterside)

### MQ04 Dull as Ever
- **Trigger:** the first `OnWorldChanged(To = Gray)` while MQ03 or later is active. Wren's canon arrival line plays.
- **Objective 1:** "Find the Old Weigh-House": `Mk_Pew_Square_WeighHouse`, else the Gray page pickup.
- **NPCs (optional and helpful):**
  - Constable Ivy Harker at the corner.
  - Winnie Cobb, who points the way: `point_the_way:nearest_mirror_page`.
  - Hester Quaile on her doorstep, who offers SQ4.
  - Horace Pratt, who grumbles about the stair. The stair key is flavour only, because the page's high spot is reachable by stairs in the world-jump design.
- **Lines** (on talk, each optional):

| Id | Speaker | Line |
|---|---|---|
| MQ04_01 | ivy_harker | "For the record, the roof's been glowing. Is that yours? Lawfully?" |
| MQ04_02 | wren_hale | "It will be. Which way up?" |
| MQ04_03 | winnie_cobb | "Round the back, love, the stair by the drainpipe. Mind the third step." |
| MQ04_04 | horace_pratt | "Nobody's been up there in eleven years. Mark my words, it'll be the death of you." |

- **Objective 2:** "Climb to the Weigh-House roof": the Gray page pickup (page id `GrayTowerPage`).
- **Completes:** on `OnPagesChanged` when the Gray page is collected. [CS03 "The First Page"](cutscenes.md#cs03-the-first-page) plays at the page's position.
- **Journal:** "Pewterside's grey as a spoon and twice as stubborn. The first page was on the Weigh-House roof, under eleven years of pigeons."

---

## Act III: Hold the Line (Pewterside → Giltside)

### MQ05 Hold the Line
- **Trigger:** the first page is collected (any page; this is the first `OnPagesChanged` with Pages = 1).
- **Story:** the Tarnish feels a page move and pushes harder. This is spine beat 4. Ask the villain session for an optional escalation: after the first page, lower `Villain.InfectInterval` from 16 to 12. Leave it at 16 if that's too hard.
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| MQ05_01 | the_tarnish | inside CS03 (as CS03_03); play here only if CS03 was skipped | "You moved a page, Silverer. We felt it in every face." |
| MQ05_02 | wren_hale | inside CS03 (as CS03_04); same rule | "Good. Feel the next one too." |

- **Objective 1:** "Step back up into Giltside". It completes on `OnWorldChanged(To = Red)`. The Gilt shard comes with the page spot in the world-jump design.
- **Objective 2:** "Hold the Lantern Gate: burn the Tarnish out of 3 people": `Mk_Gilt_Gate_LanternGate`. The counter **(quest system)** counts `OnNpcInfection` changes Infected → None within 40 m of the gate while the objective is active.
  - If fewer than 3 tarnished are around, the quest system asks the villain for more: `Villain.Convert` near the gate, by name. If that isn't available, any 3 cures anywhere in Giltside count.
  - If the Tarnish meter passes 75%, Maud's line MQ05_06 plays once.
- **NPCs:** Sergeant Maud Kettering, Nell Bramley and Hollis Greave at the gate. Captain Brask and Ros pass with the Third Company squad if squads are live.

| Id | Speaker | When | Line |
|---|---|---|---|
| MQ05_03 | maud_kettering | arrival at the gate | "Silverer. You picked a busy night to come home. Hold here with us." |
| MQ05_04 | nell_bramley | first cure at the gate | "It came out of them! Sergeant, it came right out!" |
| MQ05_05 | hollis_greave | second cure | "Course you can do that. Course you can. Keep going." |
| MQ05_06 | maud_kettering | meter past 75% | "We're losing faces faster than we save them. Faster, Silverer!" |
| MQ05_07 | sela_brask | squad passes, if present | "Third Company, by the gate. Silverer, keep your light off my line." |

- **Completes:** on the third cure.
- **Journal:** "We held the Lantern Gate. Three people walked away with their own eyes. Maud didn't say thank you, which means she meant it."

### MQ06 The Key Where Light Won't Go Out
- **Trigger:** MQ05 completes.
- **Lines:**

| Id | Speaker | Line |
|---|---|---|
| MQ06_01 | maud_kettering | "You want the Gilt Tower. I sealed it. I hid the key." |
| MQ06_02 | maud_kettering | "A tarnished came for it wearing my captain's face. I trust nobody's face now." |
| MQ06_03 | wren_hale | "Then trust what I just did." |
| MQ06_04 | maud_kettering | "Noted. It's where the light never goes out. Go and look." |

- **Objective:** "Find the Gilt Tower key": the key pickup actor (`GiltTowerKey`). The map owner places it; the line "where the light never goes out" works anywhere a lamp is near. It completes on `OnKeyAdded(GiltTowerKey)`.

| Id | Speaker | Line |
|---|---|---|
| MQ06_05 | wren_hale | (key picked up) "Brass and warm. Maud, you sentimental thing." |

- **Journal:** "Maud hid the tower key under a lamp that never goes out. She's been guarding it from her own captain's face."

### MQ07 The Gilt Tower
- **Trigger:** `OnKeyAdded(GiltTowerKey)`.
- **Objective 1:** "Open the Gilt Tower": the sealed door actor, else `Mk_Gilt_Tower_GiltTower`. It completes on the door's `OnOpened`, and [CS04 "The Gilt Tower"](cutscenes.md#cs04-the-gilt-tower) plays at the door.
- **Objective 2:** "Take the page inside the tower": the Red page pickup (`RedTowerPage`). It completes on `OnPagesChanged` with that page.

| Id | Speaker | When | Line |
|---|---|---|---|
| MQ07_01 | wren_hale | inside, page in sight | "Second leaf. It's warm, like it's been waiting." |
| MQ07_02 | the_tarnish | page 2 collected | "Two leaves. You're building us a door, Silverer." |

- **Journal:** "The second page was in the Gilt Tower, where it's always been. The Tarnish says I'm building it a door."

---

## Act IV: The Cracked Crown (Giltside → Frostside)

### MQ08 The Cracked Crown
- **Trigger:** two pages are collected.
- **Story:** the Frost Tower is the Gilt Tower's own reflection, sealed on every side by cracks. The only way in is to stand inside the Gilt Tower and step up. The Frost shard is inside the Gilt Tower in the world-jump design.
- **Lines** (Ilse plays as a 2D line here, since she isn't present: she "speaks" through the shard, a Silverer's trick):

| Id | Speaker | Line |
|---|---|---|
| MQ08_01 | ilse_varrow | "The last leaf is above you, boy. Same tower, colder light." |
| MQ08_02 | ilse_varrow | "Your mother went that way. Come back from it." |
| MQ08_03 | wren_hale | "That's the plan. It's always been the plan." |

- **Objective 1:** "Step up into Frostside from inside the tower". It completes on `OnWorldChanged(To = White)`.

| Id | Speaker | When | Line |
|---|---|---|---|
| MQ08_04 | wren_hale | arrival inside the Frost Tower | "Cracks everywhere. It's been clawing at these walls." |
| MQ08_05 | the_tarnish | ambient, 6 s after arrival | "She stood just there, your mother. Right where you are." |

- **Objective 2:** "Take the last page". It completes on `OnBookComplete`, and [CS05 "The Mirror Is Whole"](cutscenes.md#cs05-the-mirror-is-whole) plays at the page's position.
- **Journal:** "Third leaf, in the cracked tower. The mirror is whole. Now it burns."

### MQ09 Let the Light Through
- **Trigger:** `OnBookComplete`. The villain session's finale runs here: the banner "The Mirror Is Whole", the Final Spell prompt, and the true form rising at the top of the Frost Tower once the player is within 32 m of the arena.
- **Objective 1:** "Climb to the top of the Frost Tower": the villain arena actor, else the Frostside page position.
- **Objective 2:** "Burn out the Tarnish with the Final Spell (F / X)": shown when the true form manifests (the arena's 32 m radius **(quest system)**).
- **Lines** play alongside the villain's own manifest, taunt, hurt and death lines in canon.md and don't replace them. The villain session triggers them:

| Id | Speaker | When | Line |
|---|---|---|---|
| MQ09_01 | the_tarnish | fight start, after its canon manifest line | "Look, Silverer. Three of you in the glass, and none of them sure." |
| MQ09_02 | wren_hale | first Final Spell hit | "That's for Jory." |
| MQ09_03 | the_tarnish | below half health (its phase two) | "She called your name at the end. Shall we tell you how it sounded?" |
| MQ09_04 | wren_hale | after MQ09_03 | "You don't get her voice. You don't get anyone's." |
| MQ09_05 | the_tarnish | final blow, before its canon death line | "Every face you save... still has a dark side..." |

- **Completes:** on villain defeat. [CS06 "Lanthorne Is Itself Again"](cutscenes.md#cs06-lanthorne-is-itself-again) plays, then `ShowVictory`. The handoff is in cutscenes.md.
- **Journal:** "It's gone. I looked into the whole mirror, and the only face in it was mine."

---

## Losing

- **Trigger:** `OnGameLost` (the Tarnish meter at its cap). Game flow's lose screen shows "THE TARNISH HAS TAKEN LANTHORNE", and Wren's canon defeat line is "Not… yet."
- **Extra line** (optional; plays under the lose screen as a 2D whisper):

| Id | Speaker | Line |
|---|---|---|
| MQ_LOSE_01 | the_tarnish | "Every face in Lanthorne, and every one of them fits." |

## Ambient story lines tied to the meter

These play once each, as 2D lines, when `OnInfectionChanged` first crosses each band from people.json `infection_bands`. They give the meter a voice. The speaker is the most relevant named person present, else the narrator's version.

| Id | Band crossed | Speaker | Line |
|---|---|---|---|
| MQ_BAND_01 | quiet → spreading | the_tarnish | "Five faces now. They're all a little like you." |
| MQ_BAND_02 | spreading → rising | the_tarnish | "Half a street of us. Can you hear us humming?" |
| MQ_BAND_03 | rising → brink | the_tarnish | "Nearly enough of us to wear the whole city." |
| MQ_BAND_N1 | spreading (narrator alt) | narrator | "The Tarnish is spreading. Burn it out of them before it holds the city." |
| MQ_BAND_N2 | brink (narrator alt) | narrator | "Lanthorne is close to lost. Every face you save buys time." |

The villain session decides between its own taunts and these; MQ_BAND_01 to 03 are written to sit with its random taunts without repeating them.

## Who plays which line

Every scripted line loads as `/Game/Audio/Jam/Voice/Cues/SCue_VO_<LineId>`; it is silent until the audio session makes it.

| Owner | Lines |
|---|---|
| **villain-finale** (confirmed) | MQ07_02, MQ09_01–05, MQ_BAND_01–03, MQ_LOSE_01 |
| **cutscenes** | every CSxx_nn line (inside each cutscene's data asset) |
| **quest-system** | all other MQ lines, among them MQ02_02 (when CS02 ends), MQ05_01/02 (only if CS03 was skipped) and MQ08_05 (6 s after arriving in the Frost Tower), plus every SQ line |
| **npc-unify / npc-lives** | barks (people.json `barks`), ambient conversations (crowd director) |

## For the quest system: objective text (all strings in one place)

| Beat | Objective strings (player-facing) |
|---|---|
| MQ01 | "Find Ilse Varrow on Lantern Row" · "Cast a spell" |
| MQ02 | "Find the burning eyes" · "Burn the Tarnish out of Jory" / "Burn the Tarnish out of them" |
| MQ03 | "Find a Pewterside shard" · "Step down into Pewterside" |
| MQ04 | "Find the Old Weigh-House" · "Climb to the Weigh-House roof" |
| MQ05 | "Step back up into Giltside" · "Hold the Lantern Gate: burn the Tarnish out of 3 people ({n}/3)" |
| MQ06 | "Find the Gilt Tower key" |
| MQ07 | "Open the Gilt Tower" · "Take the page inside the tower" |
| MQ08 | "Step up into Frostside from inside the tower" · "Take the last page" |
| MQ09 | "Climb to the top of the Frost Tower" · "Burn out the Tarnish with the Final Spell" |

Quest titles for the journal: MQ01 "Lantern Row", MQ02 "The First Face", MQ03 "Through the Glass", MQ04 "Dull as Ever", MQ05 "Hold the Line", MQ06 "The Key Where Light Won't Go Out", MQ07 "The Gilt Tower", MQ08 "The Cracked Crown", MQ09 "Let the Light Through".

## Pages: what the player reads

When a page is picked up, world jump already shows "A page from …". If the quest journal or a toast can show one more line, show the Glazier's line for that page:

| Page id | Side | Glazier's line |
|---|---|---|
| `GrayTowerPage` | Pewterside | "I cut it in three, so no one dark could hold it all." |
| `RedTowerPage` | Giltside | "Let each side believe it is the true one. Pride makes a good lock." |
| `WhiteTowerPage` | Frostside | "The city I meant is the one they make together. Finish it." |

These are written to work in any pickup order.

**Suggested rename for world jump's config:** change the Page Source "Pewterside's high spot" to "the Old Weigh-House roof". That's one string in `DA_WorldJumpConfig`, owned by the world-jump session.
