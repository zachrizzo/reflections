# Cutscenes: six scripts

Owner: the story session. Built by the cutscene session through `Tools/Cinematics/cutscene_defs.py`; the format and the anchor rules are in [ArtDirection/Cinematics/README.md](../Cinematics/README.md). People and voices are in [people.json](people.json); triggers are in [main-quest.md](main-quest.md).

## How to read these

- **Asset names** are the `CUTSCENES` keys: `Intro`, `BurningEyes`, `FirstPage`, `GiltTower`, `MirrorWhole`, `Ending`. `Intro` replaces the current placeholder with the same name, so `PlayNewGameIntro()` keeps working.
- **Anchors.** Each cutscene is anchored to `CutsceneAnchor_<Name>`. With no marker, the cutscene subsystem uses Wren's feet and facing, and every scene below is written to work that way. Each trigger leaves Wren standing at the place the scene is about, facing it.
- **Positions** are in anchor space, in cm: X is forward (Wren's facing), Y is right, Z is up from the anchor's feet. Wren's eyes are at about 168.
- **Working on any map:**
  - Close shots stay within 6 m of the anchor, and their cameras sit at or behind the cast's line, never past a likely wall.
  - Wide shots go high (Z ≥ 1500) and look down, so buildings frame them instead of blocking them.
  - No shot needs a specific prop, door or wall to be in frame. Where the real thing is nice to have (the tower door, a page), it's a bonus.
- **Takes are Kimodo prompts** written the way the conversion takes were: "A person …", one body, one continuous action, plain physical verbs, no props the body has to grip precisely, 2–6 seconds. Frames are at 30 fps. Hero takes stay on the mannequin skeleton. NPC takes are retargeted with `RTG_Mannequin_to_UEFN`.
- **Cast roles** find people by tag `Person_<id>` (see main-quest.md). `stand_in` means a stand-in spawns only if the map has no one for the part. `restore` sends them back where they stood afterwards.
- **Lines** have ids `CSxx_nn` for the audio session. The voice is the person's roster VoiceId in people.json (the VoiceIds below are a snapshot; people.json wins); Wren and the Tarnish use their own voices. `role` plays the line from that cast member's head, and lines with no role play 2D. No line here repeats another line anywhere in the story.
- **Cues** are `OnCutsceneCue(Name, Cue)` events for other systems.

---

## CS01 Lantern Law

`Intro` · **about 48 s** · **trigger:** new game (`PlayNewGameIntro`) · **anchor:** `CutsceneAnchor_Intro`, else Wren's spawn. Face it toward the skyline. **Ends:** behind Wren; MQ01 starts.

**What it does:** shows the city at dusk and at war, gives Wren a home and two people who love him, and lets the Tarnish whisper to him before it does anything. Under a minute.

**Cast**

| Role | Who | Mark (x, y, z, yaw) | Notes |
|---|---|---|---|
| Hero | Wren | anchor (0, 0, 0, 0) | live hero |
| Jory | `Person_jory_pell` | (220, -160, 0, 150) | stand-in OK; restore |
| Goldie | `Person_goldie_fairweather` | (-200, 230, 0, -60) | optional: her lines play 2D if she's absent |

**Shots**

| # | Time | Camera (pos → look, focal) | What we see |
|---|---|---|---|
| 1 | 0.0–7.0 | (-6000, -4200, 4200) → (1500, 800, 600) drifting to (-4600, -3000, 3500), 24 mm | Fade in from black. Lanthorne at dusk from above; amber lamps coming on street by street. Title card. A distant curfew bell. |
| 2 | 7.0–15.0 | (4200, 3600, 2600) → anchor, descending to (1200, 1300, 700), 28 mm | Over the rooftops. The theme caption and the narrator's intro line. Marching drums under the music (audio SFX). |
| 3 | 15.0–21.0 | (420, -60, 40) → (0, 0, 150), 35 mm, low | Low on the street: Jory plays an invisible fiddle beside Wren, who leans against nothing with his arms folded, smiling. |
| 4 | 21.0–27.0 | (180, 260, 165) → (0, 0, 160), 50 mm, f2.8 | Close on Wren as Goldie scolds him from behind (off frame left). |
| 5 | 27.0–33.0 | (-260, -220, 170) → (220, -160, 150), 40 mm | Over Wren's shoulder onto Jory. Laughter. Then the bell rings twice and the music cuts. |
| 6 | 33.0–40.0 | (90, 40, 170) → (0, 0, 165), 85 mm, f2.0, slow push | Very close on Wren. The whisper. He turns his head to the right, then looks over his shoulder at empty air. |
| 7 | 40.0–44.0 | (260, -180, 160) → (0, 0, 155), 45 mm | Jory has stopped playing, his face uncertain. Wren tells him to go in. |
| 8 | 44.0–48.0 | (-120, 240, 185) → (300, 20, 150) to (-330, 60, 190) → (600, 0, 140), 32 mm | Behind Wren. Location card "GILTSIDE · Lanthorne". Hand off. |

**Takes**

| Role | t | Frames | Kimodo prompt |
|---|---|---|---|
| Jory | 15.0 | 180 | A person stands and plays an invisible fiddle under their chin, bowing with the right arm in long strokes, swaying from the hips and tapping one foot in rhythm. |
| Hero | 15.0 | 150 | A person stands relaxed with arms folded across the chest, weight on one leg, nodding slowly along to music and smiling. |
| Hero | 24.0 | 90 | A person unfolds their arms and raises both open hands to shoulder height in a playful shrug, then lets them drop. |
| Jory | 27.0 | 120 | A person stops playing, throws their head back laughing, then points at someone in front of them with the bowing hand. |
| Hero | 33.0 | 180 | A person stands still, then turns the head sharply to the right as if they heard a whisper close to the ear, holds, and slowly turns the whole upper body to look back over the right shoulder. |
| Jory | 40.0 | 90 | A person lowers both arms slowly and takes a small step back, shoulders hunched, looking around uneasily. |
| Hero | 41.0 | 90 | A person turns to face someone beside them and points firmly with the right hand toward a doorway behind them, then lowers the arm. |

**Lines**

| Id | t | Speaker | Role | Line |
|---|---|---|---|---|
| (existing) | 7.0 | narrator | – | `SCue_VO_Narrator_Intro` (the title line) |
| CS01_01 | 16.0 | jory_pell | Jory | "Ren! They've doubled the curfew bell. Twice a night now." |
| CS01_02 | 19.5 | wren_hale | Hero | "Then play twice as loud." |
| CS01_03 | 21.5 | goldie_fairweather | Goldie | "Wren Hale. Your rent's late and your supper's going cold." |
| CS01_04 | 24.5 | wren_hale | Hero | "Put it on my tab, Goldie." |
| CS01_05 | 26.5 | goldie_fairweather | Goldie | "Sweetling, you ARE my tab." |
| CS01_06 | 34.0 | the_tarnish | – (2D, close) | "Silverer. We've been watching you in every window." |
| CS01_07 | 39.0 | jory_pell | Jory | "Did you hear something just now? Ren?" |
| CS01_08 | 41.0 | wren_hale | Hero | "Go inside, Jory. Stay by the lamps." |

**Cards:**
- 1.0 s, for 5.2 s: `title` "REFLECTIONS".
- 7.0 s, for 8.0 s: `caption` with the theme line.
- 44.0 s, for 4.0 s: `location` "GILTSIDE", subtitle "Lanthorne".

**Fades:** 0.0 s, 2.2 s from black. **Cue:** `48.0 IntroDone`, which starts MQ01.

---

## CS02 Burning Eyes

`BurningEyes` · **about 30 s** · **trigger:** MQ02, when the player comes within 12 m of `CutsceneAnchor_BurningEyes` (place it in Bell Square, facing the fountain). Variant B uses the first real conversion within 40 m (see below). **Anchor fallback:** Wren's position and facing. **Ends:** Wren facing the tarnished Jory; MQ02's "burn it out of Jory" objective starts.

**What it does:** this is the first conversion the player sees, and it happens to his best friend. It uses the villain's real tackle, wisp and turn, `BeginConversion(Attacker, Victim)`. The camera watches from far enough away that wherever the tackle clip places the two bodies, they stay in frame.

**Cast**

| Role | Who | Mark | Notes |
|---|---|---|---|
| Hero | Wren | anchor (0, 0, 0, 0) | |
| Jory | `Person_jory_pell` | (600, 0, 0, 180) | Facing Wren. Not restored: he stays tarnished. |
| Tarnished | the nearest NPC whose infection is `Infected` or `VillainHost`, within 40 m | (900, 450, 0, -150) | Stand-in: a crowd NPC from the map. The cutscene session calls the NPC system's `SetInfection(Infected)` on it at t=0 so it gets the look. |

**Shots**

| # | Time | Camera (pos → look, focal) | What we see |
|---|---|---|---|
| 1 | 0.0–5.0 | (-250, 180, 170) → (600, 0, 150), 50 mm | Over Wren's shoulder: Jory is playing for nobody in the empty square, grinning when he sees Wren. |
| 2 | 5.0–9.0 | (700, -260, 150) → (900, 450, 165), 70 mm | Past Jory: a figure walks in slowly from the right, head tilted, with black smoke curling off it. Its eyes burn. |
| 3 | 9.0–11.0 | (450, -500, 160) → (650, 150, 120), 35 mm | Wide and low: it breaks into a run at Jory. Cue `Convert` at 9.5 s. |
| 4 | 11.0–19.0 | (300, -650, 260) → (650, 100, 60), 28 mm, slow arc to (250, 600, 300) | Held wide on the real conversion: the tackle, Jory pinned and convulsing, the black wisp from its hand into his chest. The arc keeps both bodies in frame wherever the clip lands them. |
| 5 | 19.0–24.0 | (120, 60, 165) → (0, 0, 160), 85 mm, f2.0 | Close on Wren: frozen, then his jaw sets. |
| 6 | 24.0–28.0 | (300, 40, 150) → (650, 0, 165), 50 mm | Jory gets up wrong: stiff, head tilted, eyes burning. He speaks. |
| 7 | 28.0–30.0 | (-200, 160, 180) → (600, 0, 150), 35 mm | Behind Wren, facing Jory. Hand off into the fight. |

**Takes**

| Role | t | Frames | Kimodo prompt |
|---|---|---|---|
| Jory | 0.0 | 150 | A person plays an invisible fiddle with big showy bow strokes, then sees someone ahead, grins and lifts the bow arm in a wave. |
| Tarnished | 5.0 | 120 | A person walks forward slowly and stiffly, head tilted far to one side, arms hanging limp, feet dragging slightly. |
| Hero | 19.0 | 120 | A person stands frozen with both hands half raised, then slowly lowers them, clenches the fists and squares the shoulders. |
| Hero | 26.0 | 90 | A person drops into a ready stance, right arm extended forward with the palm open, left arm drawn back. |

- **The conversion** (shot 4) is not a take. It's the villain's own sequence, started by the `Convert` cue. The cutscene session's cue handler calls `UReflectionsVillainSubsystem::BeginConversion(Tarnished, Jory)` by name. That returns the sequence length: if it's longer than 8 s, stretch shot 4 to match; if it's shorter, hold the wide shot.
- **Jory's rise** at shot 6 is the villain's existing turned getup. If that sequence has already ended, use `AS_Conversion_Victim_Possessed_A` as a take at t=22.

**Lines**

| Id | t | Speaker | Role | Line |
|---|---|---|---|---|
| CS02_01 | 1.0 | jory_pell | Jory | "Ren! Here's one for you. I'm calling it 'Curfew Waltz'." |
| CS02_02 | 6.5 | jory_pell | Jory | "Evening, friend. Requests? You look like a slow-song sort." |
| CS02_03 | 9.6 | wren_hale | Hero | "Jory! Get away from it!" |
| CS02_04 | 14.0 | the_tarnish | – (2D) | "Shh. Let him hum for us." |
| CS02_05 | 25.0 | jory_pell | Jory | "Ren. We know all your songs." (his tarnished voice: slow and flat) |
| CS02_06 | 28.5 | wren_hale | Hero | "Not him. You don't get him." |

**Variant B (generic):** if Jory isn't on the map, or the scene is triggered by the first real conversion:
- The Jory role goes to the conversion's victim, and the scene starts at shot 3 (length about 21 s).
- CS02_01 and 02 are skipped.
- CS02_03 becomes CS02_03B: "Hey! Get away from them!"
- CS02_05 becomes CS02_05B, the victim's tarnished line: "We see you, Silverer. We all do."
- CS02_06 becomes CS02_06B: "Hold on. I'm going to burn it out of you."
- The anchor is the victim's position, facing the player.

**Cues:** `9.5 Convert` (see above) and `30.0 BurningEyesDone`, which shows MQ02's objective 2.

---

## CS03 The First Page

`FirstPage` · **about 22 s** · **trigger:** the first `OnPagesChanged` (any page; usually the Weigh-House roof in Pewterside). **Anchor:** `CutsceneAnchor_FirstPage`, else Wren where he picked it up. **Ends:** behind Wren; MQ05 starts.

**What it does:** the first leaf of the mirror, the Glazier's line, and the first time the Tarnish talks about the pages. It's quiet, and the mood is set by the side Wren is standing in.

**Cast:** Hero only.

**Shots**

| # | Time | Camera | What we see |
|---|---|---|---|
| 1 | 0.0–5.0 | (160, -120, 150) → (0, 0, 120), 60 mm, f2.8 | Wren looks down into his cupped hands. Silver light comes up from them onto his face (VFX: a soft light at the hands; optional). |
| 2 | 5.0–11.0 | (60, 30, 175) → (0, 0, 140), 100 mm, f2.0 | Very close: he reads aloud. |
| 3 | 11.0–17.0 | (-800, -900, 1800) → (0, 0, 100), climbing to (-1400, -1600, 3200), 30 mm | Rising away: the first rooftop, the grey (or gold, or white) city around it, rain. |
| 4 | 17.0–22.0 | (-130, 220, 180) → (400, 0, 150) to (-320, 70, 190) → (600, 0, 140), 32 mm | Behind Wren, who looks up from the page out at the city. Hand off. |

**Takes**

| Role | t | Frames | Kimodo prompt |
|---|---|---|---|
| Hero | 0.0 | 150 | A person stands holding both hands together in front of the chest, palms up as if cradling something flat and fragile, head bowed to look at it. |
| Hero | 5.0 | 180 | A person stands still, head bowed over the cupped hands, then slowly tilts the hands toward the face as if reading words on them, and takes a deep breath. |
| Hero | 17.0 | 120 | A person lowers the cupped hands to the waist, lifts the head and looks out into the distance, shoulders rising with one slow breath. |

**Lines**

| Id | t | Speaker | Line |
|---|---|---|---|
| CS03_01 | 5.5 | wren_hale | The Glazier's line for the page collected, read aloud. `GrayTowerPage`: "'I cut it in three, so no one dark could hold it all.'" (CS03_01G is the Giltside line and CS03_01F the Frostside line, from main-quest.md "Pages".) |
| CS03_02 | 10.0 | wren_hale | "One leaf. Still warm from somebody's hand." |
| CS03_03 | 15.0 | the_tarnish (2D) | "You moved a page, Silverer. We felt it in every face." (this is MQ05_01: play it here, and don't repeat it in MQ05) |
| CS03_04 | 19.0 | wren_hale | "Good. Feel the next one too." (this is MQ05_02) |

**Cards:** at 12.0 s, for 4.0 s, a `location` card with the side's name and the page source: "PEWTERSIDE · the Old Weigh-House roof", "GILTSIDE · the Gilt Tower" or "FROSTSIDE · the Frost Tower". **Cue:** `22.0 FirstPageDone`.

---

## CS04 The Gilt Tower

`GiltTower` · **about 26 s** · **trigger:** the Gilt Tower's sealed door `OnOpened`. Wren is standing at the door with the key, facing it. **Anchor:** `CutsceneAnchor_GiltTower` (place it at the door's threshold, facing in), else Wren. **Ends:** behind Wren, looking into the tower; MQ07's objective 2 starts.

**What it does:** opening the place everyone has been told never to open. A bell-ringer's boy who wishes he were Wren. The Tarnish pointing upward.

**Cast**

| Role | Who | Mark | Notes |
|---|---|---|---|
| Hero | Wren | (0, 0, 0, 0) | |
| Pim | `Person_pim_ashgrove` | (-150, -220, 0, 40) | Optional: his lines play 2D if he's absent. Restore. |

**Shots**

| # | Time | Camera | What we see |
|---|---|---|---|
| 1 | 0.0–6.0 | (-420, -60, 60) → (300, 0, 260), 24 mm, low and wide | Low behind Wren as the real door slides up (the door's own motion) and warm gold light spills over him. If there's no door, it's just the light: add a soft gold light at (250, 0, 150). |
| 2 | 6.0–12.0 | (200, -150, 165) → (0, 0, 160), 50 mm | Wren's face in the light from the doorway. |
| 3 | 12.0–18.0 | (-40, -360, 160) → (-150, -220, 150), 45 mm | Pim hurries up behind him, out of breath. |
| 4 | 18.0–22.0 | (60, 260, 160) → (-60, -120, 160), 40 mm | Two-shot: Wren answers Pim with a hand on his shoulder (or a nod, if Pim is a 2D voice). |
| 5 | 22.0–26.0 | (-200, 120, 175) → (500, 0, 220) to (-340, 60, 190) → (700, 0, 200), 30 mm | Behind Wren, looking in and up. The whisper. Hand off. |

**Takes**

| Role | t | Frames | Kimodo prompt |
|---|---|---|---|
| Hero | 0.0 | 150 | A person stands facing forward and lifts one arm to shield the eyes from a bright light ahead, then slowly lowers the arm. |
| Pim | 12.0 | 120 | A person jogs a few steps forward and stops, bending over with hands on knees to catch their breath, then straightens up quickly. |
| Pim | 15.0 | 90 | A person bows quickly from the waist, then clasps both hands together in front of the chest, nervously. |
| Hero | 18.0 | 120 | A person turns to the left, reaches out and rests a hand on the shoulder of someone shorter, and nods once. |
| Hero | 22.0 | 90 | A person turns back to face forward, tilts the head back to look up at something very high, and rolls the shoulders. |

**Lines**

| Id | t | Speaker | Role | Line |
|---|---|---|---|---|
| CS04_01 | 6.5 | wren_hale | Hero | "Sealed since the first night of the war. Not any more." |
| CS04_02 | 13.0 | pim_ashgrove | Pim | "If you please, Silverer, may I come up? No. Quite right." |
| CS04_03 | 17.0 | pim_ashgrove | Pim | "I'll mind the door. Properly. Nobody gets past me." |
| CS04_04 | 19.0 | wren_hale | Hero | "When I'm done, Pim, you ring every bell in this tower." |
| CS04_05 | 23.0 | the_tarnish | – (2D) | "Up you go, Silverer. We'll be waiting at the top." |

**Cue:** `26.0 GiltTowerDone`.

---

## CS05 The Mirror Is Whole

`MirrorWhole` · **about 24 s** · **trigger:** `OnBookComplete`, normally inside the Frost Tower. **Anchor:** `CutsceneAnchor_MirrorWhole`, else Wren where he took the last page. **Ends:** behind Wren facing the way up (the anchor's forward), and hands the finale to the villain session.

**What it does:** the three leaves join, the light pours out, the Tarnish's whole tower answers, and Wren chooses to climb.

**Cast:** Hero only.

**Shots**

| # | Time | Camera | What we see |
|---|---|---|---|
| 1 | 0.0–6.0 | (140, 80, 140) → (0, 0, 130), 70 mm, slow orbit to (80, -150, 150) | Wren holds his cupped hands together. Silver-white light floods up, brighter than in CS03 (VFX: a bright light at the hands, `NS_Spell_Projectile` white sparks; optional). |
| 2 | 6.0–11.0 | (0, 0, 2400) → (0, 0, 0), 20 mm, straight down, slowly turning | From directly overhead: Wren at the centre of a widening ring of light. Fine cracks spread outward on the ground around the light (decal VFX; optional). |
| 3 | 11.0–16.0 | (90, 0, 168) → (0, 0, 165), 100 mm, f1.8 | Very close on Wren's face, lit from below. He speaks. |
| 4 | 16.0–21.0 | (-250, 0, 60) → (600, 0, 900), 24 mm, low, looking up | From Wren's feet, looking up the line he'll climb, into darkness. Violet flickers at the top (the villain's palette). |
| 5 | 21.0–24.0 | (-130, 220, 185) → (500, 0, 300) to (-330, 60, 190) → (700, 0, 400), 32 mm | Behind Wren, looking up. Hand off. |

**Takes**

| Role | t | Frames | Kimodo prompt |
|---|---|---|---|
| Hero | 0.0 | 180 | A person stands with both cupped hands held in front of the chest, then slowly raises them to face height as if lifting something heavy and bright, arms trembling slightly. |
| Hero | 6.0 | 150 | A person stands with arms spread slightly away from the body, palms open and facing forward, head tipped back, chest rising in a deep breath. |
| Hero | 16.0 | 120 | A person lowers the arms, turns the head to look up at something far above, then takes one deliberate step forward. |

**Lines**

| Id | t | Speaker | Line |
|---|---|---|---|
| (existing) | 3.0 | wren_hale | "The mirror's whole. Now it burns." (canon "Mirror whole" line; skip its normal trigger while this cutscene plays) |
| CS05_01 | 7.5 | the_tarnish (2D) | "Three leaves, one mirror. And one Silverer left to look into it." |
| CS05_02 | 12.0 | wren_hale | "I've spent nine years not looking. I'm done with that." |
| CS05_03 | 17.5 | the_tarnish (2D) | "Climb, then. She climbed too." |
| CS05_04 | 21.5 | wren_hale | "Mum, if you're up there, I'm coming." |

**Cards:** at 9.0 s, for 4.0 s, a `caption` card: "The Mirror Is Whole". The villain session's banner text is the same; see the handoff.

**Cues:**
- `11.0 FinaleReady`
- `24.0 MirrorWholeDone`

**Handoff to the villain session's finale** (it owns the manifest; see `ArtDirection/Villain/README.md`):
1. The villain listens to `OnBookComplete` as it does today. **While `IsAnyCutscenePlaying()` is true**, it holds its banner ("The Mirror Is Whole" / "The Final Spell is yours. The Tarnish waits at the top of {side}'s tower."), the music sting and the Final Spell prompt until `OnCutsceneFinished(MirrorWhole)`, then shows them. If the cutscene is skipped, `OnCutsceneFinished` still fires.
2. The cutscene's own caption at 9.0 s carries "The Mirror Is Whole" inside the scene. The villain's banner after the handoff then shows only the second line. If that's simpler for the villain session, it can show both lines; the repeat is acceptable.
3. Nothing manifests during CS05. The true form rises, as today, when the player comes within 32 m of the arena (`Villain.ManifestRadius`) after the handoff. Its canon manifest line "You made the mirror whole. Now look into it." follows naturally from CS05_03.
4. A checkpoint restore with a whole mirror doesn't replay CS05. The quest system checks `HasPlayed(MirrorWhole)`, or the villain's existing "never starts twice" rule.

---

## CS06 Lanthorne Is Itself Again

`Ending` · **about 46 s** · **trigger:** the Tarnish's death dissolve ends. **Anchor:** `CutsceneAnchor_Ending` (place it at the arena centre, facing out over the city), else Wren. **Ends:** fade to black, then `ShowVictory()`.

**What it does:** the quiet after. Ash, then light. Ilse's voice through the shard, which answers the title line. Jory playing again somewhere below. The tower bells. Wren says goodbye to his mother.

**Handoff from the villain session:**
- Today the villain calls `ShowVictory()` 2.5 s after the dissolve.
- **Change:** call `PlayCutscene("Ending")` at that moment instead, and call `ShowVictory()` on `OnCutsceneFinished(Ending)`, skipped or not.
- If `PlayCutscene` returns false (asset missing, or another cutscene playing), call `ShowVictory()` straight away as now.

**Cast:** Hero only. Ilse and Jory are heard, not seen: they're in Giltside, and this is Frostside.

**Shots**

| # | Time | Camera | What we see |
|---|---|---|---|
| 1 | 0.0–7.0 | (300, -200, 120) → (0, 0, 80), 35 mm | Ash drifting down (`NS_Villain_Shroud` embers at low rate; optional). Wren is down on one knee, breathing hard. |
| 2 | 7.0–13.0 | (120, 90, 110) → (0, 0, 110), 85 mm, f2.0 | Close: he gets up slowly. His hands still glow faintly. |
| 3 | 13.0–22.0 | (-2000, -1800, 2600) → (2000, 0, 0), 24 mm, slow push | High and wide over the city: the cold light warms by a few degrees (a post-process tint change; optional). Bells start, far off (audio: the tower bells). Ilse speaks. |
| 4 | 22.0–32.0 | (200, 0, 160) → (0, 0, 160), 50 mm, slow orbit to (0, 220, 160) | Wren's face as he answers. He laughs once, tiredly. |
| 5 | 32.0–39.0 | (-150, 60, 175) → (800, 0, 150), 40 mm | Behind Wren looking out. Fiddle music rises under the bells: Jory's tune from CS01 (audio). Wren speaks to the light. |
| 6 | 39.0–46.0 | (-600, -400, 400) → (0, 0, 150), drifting back to (-1500, -900, 1200), 28 mm | Pulling away from Wren, alone at the top of the tower and looking out. Caption. Fade to black. |

**Takes**

| Role | t | Frames | Kimodo prompt |
|---|---|---|---|
| Hero | 0.0 | 210 | A person kneels on one knee with one hand braced on the ground, head down, shoulders heaving with heavy breaths. |
| Hero | 7.0 | 180 | A person kneeling on one knee pushes slowly up to standing, wobbles once, steadies, and looks down at both open hands. |
| Hero | 22.0 | 150 | A person stands with hands at their sides, lifts the chin, then lets out one tired laugh, the shoulders shaking once. |
| Hero | 32.0 | 180 | A person stands looking into the distance, raises one open hand slowly to chest height as if saying goodbye to someone far away, holds it, and lowers it. |

**Lines**

| Id | t | Speaker | Line |
|---|---|---|---|
| (existing) | 3.0 | wren_hale | "It's gone. Lanthorne is itself again." (canon victory line) |
| CS06_01 | 14.0 | ilse_varrow (2D, through the shard) | "Boy. Can you hear the bells? Pim's ringing all of them." |
| CS06_02 | 18.0 | wren_hale | "I hear them. Ilse, which side was the one it meant?" |
| CS06_03 | 23.0 | ilse_varrow (2D) | "None of them alone. All three, standing together. That's the city it meant." |
| CS06_04 | 28.0 | ilse_varrow (2D) | "And Elin's boy came home. Mm. Plainly enough." |
| CS06_05 | 34.0 | wren_hale | "Goodbye, Mum. I looked. It was only me in there." |
| CS06_06 | 40.0 | jory_pell (2D, distant) | "Ren! This one's called 'Home Before Dawn'!" |

**Cards:** at 41.0 s, for 5.0 s, a `caption` card: "Lanthorne is itself again." (canon victory text). **Fades:** at 43.5 s, over 2.5 s, to black. **Cue:** `46.0 EndingDone`, after which the villain session calls `ShowVictory()`.

---

## Anchor table (for the map owner and the Cinematics README)

| Cutscene | Anchor tag | Where | Facing |
|---|---|---|---|
| `Intro` | `CutsceneAnchor_Intro` | Wren's start, outside the Lamplight inn in Giltside | toward the skyline |
| `BurningEyes` | `CutsceneAnchor_BurningEyes` | Bell Square, about 6 m from somewhere Jory can stand | toward where Jory stands |
| `FirstPage` | `CutsceneAnchor_FirstPage` (optional) | none needed; it plays where the page was picked up | out over the city |
| `GiltTower` | `CutsceneAnchor_GiltTower` (optional) | the Gilt Tower door's threshold | into the tower |
| `MirrorWhole` | `CutsceneAnchor_MirrorWhole` (optional) | the Frostside page's spot inside the Frost Tower | up toward the arena |
| `Ending` | `CutsceneAnchor_Ending` (optional) | the villain arena's centre | out over the city |

Only `BurningEyes` really wants a marker; the others play well around Wren.

## Line index (all cutscene lines, for the audio session)

| Id | Speaker | VoiceId |
|---|---|---|
| CS01_01, CS01_07, CS02_01, CS02_02, CS02_05, CS06_06 | jory_pell | V093 (CS02_05 delivered flat and hollow) |
| CS01_03, CS01_05 | goldie_fairweather | V027 |
| CS04_02, CS04_03 | pim_ashgrove | V063 |
| CS06_01, CS06_03, CS06_04 | ilse_varrow | V014 |
| CS01_02, 04, 08; CS02_03, 06 (+B); CS03_01 (G/F), 02, 04; CS04_01, 04; CS05_02, 04; CS06_02, 05 | wren_hale | the hero's voice |
| CS01_06, CS02_04, CS03_03, CS04_05, CS05_01, CS05_03 | the_tarnish | the Tarnish's voice (cedar) |
