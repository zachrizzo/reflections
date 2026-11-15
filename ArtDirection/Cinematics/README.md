# Cutscenes: how they work, how to add one, how to place its anchor

Owner: the cutscenes side session.
- **Code:** `Source/reflections/Cinematics/`
- **Content:** `/Game/Cinematics/` (`Sequences/LS_Cutscene_<Name>`, `Data/DA_Cutscene_<Name>`)
- **Tools:** `Tools/Cinematics/`
- **Contact sheets:** this folder

## What a cutscene is

A cutscene has two assets:

- **The Level Sequence** (`/Game/Cinematics/Sequences/LS_Cutscene_<Name>`) holds the cameras and the cuts.
  - Cameras are *spawnables* (cine cameras that exist only while the sequence plays) with keyed moves.
  - Props and effects can go in it too.
  - It never contains a copy of Wren or an NPC.
- **The data asset** (`/Game/Cinematics/Data/DA_Cutscene_<Name>`, class `ReflectionsCutsceneAsset`) holds everything else:
  - **Cast:** who plays which part. The live hero, or a named NPC found on the map. A stand-in spawns only when the map has nobody for the part.
  - **Takes:** body animations, such as Kimodo takes, started at a time on a cast member.
  - **Lines:** subtitle, speaker name and voice cue.
  - **Cards:** title, caption and location stamp.
  - **Fades** to and from black.
  - **Cues:** named moments other systems hear (for example, the villain's manifest).
  - **Presentation:** letterbox, skip and the camera hand-off.

### Map-agnostic by design

Every camera position is authored in **anchor space**:
- X is the anchor's forward.
- Y is right.
- Z is up from the anchor's feet, in cm.

At play time the cutscene subsystem finds the anchor and plays the sequence with it as the **transform origin**. The same cutscene therefore plays correctly on the real map, on our test maps, or anywhere else.

How the anchor is found, in this order:
1. An actor tagged `CutsceneAnchor_<Name>` (the quest system's **Reflections Story Marker** with that `MarkerName` or tag).
2. An actor whose name or label starts with `CutsceneAnchor_<Name>`.
3. Neither: **Wren's feet and facing** at the moment the cutscene starts.

The anchor is snapped to the ground under it and only its yaw is used, so marker placement is forgiving.

## What the player sees and gets back

- **Letterbox** bars ease in (2.39:1 by default).
- **Subtitles** are centred in the lower bar, in the game-flow text style: parchment text with a gold speaker name.
- **Title cards** come in three styles:
  - `title`: the REFLECTIONS wordmark.
  - `caption`: a large italic line.
  - `location`: small spaced capitals, lower left.
- **Skip:** hold **Space / Enter** or gamepad **A** for 1 s.
  - The "HOLD SPACE TO SKIP" prompt and its fill bar appear for a few seconds at the start and after any input. The key name follows the last device used.
  - A skip fades to black, cuts back to gameplay, and lifts the black.
- **While a cutscene plays:**
  - Game input is off (the viewport ignores it, re-asserted every frame), along with movement and look input.
  - Wren can't be damaged.
  - The other HUD layers (spell bar, Tarnish meter, world-jump panel, dialogue) fade to transparent.
  - NPCs in the cast are externally steered, so their AI doesn't walk them away.
- **On the way out:**
  - Every one of those is restored exactly as it was.
  - Stand-ins are removed, and cast members marked `restore` go back where they stood.
  - The camera blends from the last shot to the gameplay camera, which is turned to point along Wren's facing. With the last shot authored behind him, the hand-off is seamless.
- **Menus:**
  - If a game-flow menu opens (pause), the other layers come back while it is up.
  - Lose, victory and title end the cutscene at once.

## Events (quests, game flow, villain)

World subsystem `/Script/reflections.ReflectionsCutsceneSubsystem`. Every member below is a UFUNCTION or delegate, so it can be called **by name** without the header.

| Member | Meaning |
|---|---|
| `bool PlayCutscene(FName Name)` | Plays `DA_Cutscene_<Name>`. Returns false if the asset is missing or a cutscene is already playing; the caller then carries on. |
| `bool PlayNewGameIntro()` | Game flow calls this on a fresh run. It plays `Intro`; in PIE only with `Cutscene.IntroInPIE 1`. |
| `void SkipCutscene()` | Ends the current cutscene with the skip fade. |
| `bool IsCutscenePlaying()`, `FName GetCurrentCutscene()`, `float GetCutsceneTime()`, `bool HasPlayed(FName)` | State. |
| `AActor* GetCastActor(FName Role)`, `FTransform GetAnchorTransform()` | Who is playing a part, and where the stage is. |
| `OnCutsceneStarted(FName Cutscene)` | Fires after control is taken. |
| `OnCutsceneCue(FName Cutscene, FName Cue)` | Fires at each cue time in the asset. |
| `OnCutsceneFinished(FName Cutscene, bool bSkipped)` | Fires after control is back. |

From C++: `UReflectionsCutsceneSubsystem::Get(this)->PlayCutscene(TEXT("Intro"))`, or `UReflectionsCutsceneSubsystem::IsAnyCutscenePlaying(this)`.

Console commands (any build):
- `Cutscene.Play <Name>`
- `Cutscene.Skip`
- `Cutscene.Status [AnchorName ...]`: shows where each anchor resolves.
- `Cutscene.Enable 0|1`
- `Cutscene.IntroInPIE 0|1`
- `Cutscene.HideHud 0|1`

## Adding a cutscene

1. **Write it** in `Tools/Cinematics/cutscene_defs.py`. Add an entry to `CUTSCENES` with the shots (camera keys in anchor space), cast, takes, lines, cards, fades and cues. The format is documented at the top of that file, and `Intro` is a full example.
2. **Build it** in the editor (MCP Python): run `Tools/Cinematics/build_cutscene.py` with `ARGS = ['build', '<Name>']`. This creates or refreshes both assets and never touches a level.
3. **Trigger it** from your system with `PlayCutscene("<Name>")`, by name or from C++. Listen to `OnCutsceneFinished` to continue your quest step.
4. **Check it** in PIE with `Cutscene.Play <Name>` on any map. Without a marker it plays around Wren.
5. **Tune cameras** by editing the keys and rebuilding. Or open `LS_Cutscene_<Name>` in Sequencer: set *Transform Origin* in the sequence's playback settings to a spot in the level to preview it in place. Don't save that preview origin.

### Body motion: what ships tonight

Kimodo generation did not run in this editor session (see below), so every cutscene uses **fallback takes**: existing project clips, listed in `FALLBACK` in `cutscene_defs.py`.

| Kind | Clips | How it plays |
|---|---|---|
| Wren | crafting gestures (Conjure, Lance, SkyCall); spell casts (HealRaise, AimHold, ArcaneShield, GreaterHeal, HealingPulse) | Upper-body montages on his MetaHuman body's DefaultSlot; the legs keep the idle |
| Jory | the project's Kimodo hand wave, retargeted to the UEFN driver (`Tools/Cinematics/fallback_takes.py`) | On the driver; the MetaHuman follows through its own retarget |

That's 15 of the 26 scripted beats. The rest stay on the idle. Once real Kimodo takes exist, rebuilding a cutscene (`build_cutscene.py build <Name>`) swaps them in automatically: a Kimodo take always wins over the fallback.

### Body motion (Kimodo)

- Takes are generated with the engine's Kimodo text-to-motion plugin and land on the UE5 mannequin skeleton. The pipeline is the spell-crafting session's `Tools/SpellCrafting/author_conversion_kimodo.py`.
- **Hero takes** stay on the mannequin skeleton. They play on Wren's hidden driver mesh, and the MetaHuman follows through its retarget.
- **NPC takes** are retargeted to the UEFN mannequin (the NPC drivers' skeleton) with `RTG_Mannequin_to_UEFN`.
- A take plays as a dynamic montage on `DefaultSlot` of the first mesh in the cast member's hierarchy that uses the clip's skeleton.

### Voice

- Lines are recorded by the audio session in each character's designed voice.
- Point a line's `voice` at the cue. `role` plays it from that cast member's head (3D); no role plays it 2D.
- `dur: 0` holds the subtitle for the length of the voice.

## Placing anchors on the real map (map owner)

For each scripted cutscene, place one **Reflections Story Marker** (quest system), or any actor with the tag `CutsceneAnchor_<Name>`.

- **Position:** where the scene happens, on the ground. It is snapped down, so a little above the floor is fine.
- **Facing:** the arrow points at "stage forward", the way Wren faces during the scene. Cameras are placed around it.
- **Space:** leave about 6 m clear around the marker, at eye height, so close shots aren't inside a wall. Wide shots need open sky in the anchor's forward direction.
- **Check:** in PIE, `Cutscene.Status <Name>` prints which marker was found. `Cutscene.Play <Name>` plays it there.

| Cutscene | Trigger (who calls it) | Anchor | Where on the real map | Facing |
|---|---|---|---|---|
| `Intro` (CS01, 48 s) | game flow, on a fresh run (`PlayNewGameIntro`) | `CutsceneAnchor_Intro` (optional) | Wren's start, outside the Lamplight inn in Giltside | toward the skyline |
| `BurningEyes` (CS02, 30 s plus the conversion hold) | quests, MQ02, within 12 m of the marker | `CutsceneAnchor_BurningEyes` (**wanted**) | Bell Square, about 6 m from where Jory can stand; 9 m of open ground ahead | toward where Jory stands |
| `FirstPage` (CS03, 22 s) | quests, on the first page | `CutsceneAnchor_FirstPage` (optional) | none needed: plays where the page was picked up | out over the city |
| `GiltTower` (CS04, 26 s) | quests, on the Gilt Tower door `OnOpened` | `CutsceneAnchor_GiltTower` (optional) | the Gilt Tower door's threshold | into the tower |
| `MirrorWhole` (CS05, 24 s) | villain or quests, on `OnBookComplete` | `CutsceneAnchor_MirrorWhole` (optional) | the Frostside page's spot inside the Frost Tower | up toward the arena |
| `Ending` (CS06, 46 s) | villain, after the dissolve; it calls `ShowVictory()` on `OnCutsceneFinished(Ending)` | `CutsceneAnchor_Ending` (optional) | the villain arena's centre | out over the city |

How each scene adapts when a person isn't on the map:
- **Intro:** Jory gets a stand-in. Goldie's lines play 2D.
- **BurningEyes:**
  - Jory is played by the nearest citizen within 40 m, else a stand-in, and the variant-B lines play.
  - The attacker is the nearest tarnished NPC, else the nearest citizen, whom the scene tarnishes.
  - At the `Convert` cue the villain's own `BeginConversion` runs, and the wide shot holds until it is over.
- **GiltTower:** Pim's lines play 2D.

## Packaging

- **Cooking:** cutscenes are loaded by path, so `/Game/Cinematics` must be in `DirectoriesToAlwaysCook`.
- **Size:** a sequence and its data asset are a few hundred KB. Kimodo takes are about 1–3 MB each before compression. Stand-ins reuse existing characters.

## Status: PIE proof, Sat 14 Nov, 20:26–20:41 (Lvl_HeroSampleCrowd, train #12)

`Tools/Cinematics/test_cutscenes_pie.py runall` plays each cutscene to the end, capturing 8 frames, then plays it again and skips it 3 s in. After each, it checks that the cutscene stopped, that move and look input aren't ignored, that the view target is the one from before the cutscene, and that the hero can be damaged. Results: `Saved/CinematicsTest/runall.json`.

| Cutscene | Played | Skipped | Control restored | Contact sheet |
|---|---|---|---|---|
| Intro | yes | yes | yes, both times | `ContactSheet_Intro.png` |
| BurningEyes | yes | yes | yes, both times | `ContactSheet_BurningEyes.png` |
| FirstPage | yes | yes | yes, both times | `ContactSheet_FirstPage.png` |
| GiltTower | yes (8 frames) | not reached: stopped at the slot's deadline | — | `ContactSheet_GiltTower.png` |
| MirrorWhole | not run yet | | | |
| Ending | not run yet | | | |

What the frames show:
- **Working:** the letterbox, title card, theme caption, subtitles with gold speaker names, the location card, the skip prompt and the Wren close-ups.
- **Known problems** (fixes in progress):
  - On the small test map, the high wide shots show the slab's edge in empty space. They need a city around them (`Lvl_MockCity`, or the real map).
  - Crowd NPCs stand inside close shots. Fix: "clear the set" (train #13, `ClearRadius` on the asset) hides non-cast NPCs within 15 m of the anchor during the scene.
  - Two BurningEyes shots frame empty ground: the cast stood off their marks. To be rechecked on the mock city with the set cleared.
