# Quests, journal and story markers

Code: `Source/reflections/Quests/` (the quest session owns it). Content: `/Game/Quests/` (`DA_QuestPack_Story`).
Tools: `Tools/Quests/` (`import_story.py` builds the content pack, `test_quests_pie.py` is the PIE proof).
Story content in JSON: `ArtDirection/Quests/data/`. Screenshots: `ArtDirection/Quests/Screenshots/`.

## What the player gets

- **Tracked objective**, top right under the Tarnish meter: the quest name in gold, its open objectives with
  progress (`2/3`, protect timers), the distance, or "On Frostside: step through" when the target is on another side.
- **Pointer**: a gold diamond over the target with the distance. Off screen, it sits on the screen edge and an arrow
  points the way. It hides once you are there.
- **Marks over people**: `!` has a quest for you, `?` waits for something you finished, `...` wants to talk (a talk
  objective, a delivery or a choice). Near a person: **E** (keyboard) or **D-pad Down** (gamepad) *Speak with...*.
- **Talk card** (the non-voice path, which always works): the person's lines, then buttons such as *I'll do it* /
  *Not now* / *Hand it over* / the choices / *Any advice?* / *Goodbye*. A or Enter picks, B or Esc backs out, and the
  mouse works too. Talking never pauses: the world keeps running. The person stops and turns to face the hero,
  and the card closes by itself if the hero is hurt, walks more than 5 m away, or a menu opens. Only the journal
  pauses. Quest subtitles sit above npc-dialogue's conversation panel while it shows.
- **Journal**: **L**, or **Start > Journal** on a gamepad. The left side lists quests under way and finished ones;
  the right side shows the selected quest's notes, its objectives, a "so far" log including your choices, and the
  reward. A or Enter tracks the selected quest; B, Esc or L closes it.
- **Banners**, top centre: quest started, quest updated, objective complete, return to someone, quest complete with
  the reward line.

Controls for the itch page: `L` Journal (gamepad: Start > Journal) and `E` Speak (gamepad: D-pad Down).

## For the map designer: dropping markers

Quests, NPC daily lives and cutscenes all find places through **one actor: Reflections Story Marker**
(`AReflectionsStoryMarker`). Nobody edits your map. You place markers, and every system looks them up by name.

1. *Place Actors* > search **Reflections Story Marker**. Drop it where the thing happens, on walkable ground.
2. Set **Marker Name**, or add the name as an actor **Tag**. One marker can answer to several names, such as
   `Home_GiltMaren` plus `QuestGiver_GiltMaren`.
3. **Rotation** is the facing: a quest giver stands looking along the arrow, and a cutscene uses it as forward.
4. **Radius** is the area the name means: the go-to and protect zone, or a home's wander radius. The default is 3 m.
5. **Side** can stay *Auto*: it reads the world-jump anchor box the marker stands in.

| Name | What it marks | Example |
|---|---|---|
| `Home_<PersonId>` | where a person lives | `Home_GiltMaren` |
| `Work_<Job>` | a workplace (stall, exchange, guard post) | `Work_CoinExchange` |
| `Haunt_<Place>` | somewhere people gather | `Haunt_LampSquare` |
| `QuestGiver_<PersonId>` | where a quest giver waits for the hero | `QuestGiver_GiltMaren` |
| `CutsceneAnchor_<Name>` | a cutscene's origin and facing | `CutsceneAnchor_Intro` |
| `Tower_<Side>` | foot of a side's tower (`Pewterside`, `Giltside`, `Frostside`) | `Tower_Giltside` |
| `Spot_<Name>` | any quest place: go to, hold, a spell target | `Spot_OldWell` |
| `Item_<ItemId>` | where a quest item lies | `Item_LostLedger` |

`PersonId` is the id from the story bible's `people.json`. Each quest's needs are listed in the generated table
`ArtDirection/Quests/markers-needed.md`, written by `import_story.py`.

**Missing markers are placed for you.** When a name is missing (test maps, or a map still being built), the game
puts an auto-placed marker on a nav-reachable point near the right side, deterministic per name, and logs
`Story marker X auto-placed at ...`. Then play and run these in the console:

- `Story.Markers`: every marker and which ones were auto-placed (`[auto]`). Those are the ones still to drop.
- `Story.ShowMarkers 1`: draws every marker's name, radius and facing in game. Gold is hand-placed, blue is auto.
- `Story.MarkerFallback 0`: turns auto-placing off, to check a finished map.

Quest people the map doesn't have are spawned at their `QuestGiver_<Id>` marker (else `Home_<Id>`) through the NPC
system and tagged `Person_<Id>`. If you place or spawn people yourself, tag them `Person_<PersonId>` and nothing is
spawned for them. The Tarnish leaves quest givers the quest system spawned alone (`NoVillain`).

**Check a map without the editor:** `python Tools/Quests/check_markers.py` resolves every name the story quests ask
for, the way the game does. It reads world-jump's `ArtDirection/WorldJump/graylondon_markers.json` by default, or
any MARKERS.md table. On 2026-11-14 at 21:20 it reported 54 names, 0 auto-placed and 0 stand-ins for Gray London
(main and SQ1 to SQ12).

## For other systems

`#include "Quests/ReflectionsQuestSubsystem.h"`, then `UReflectionsQuestSubsystem::Get(this)`. It's a game-instance
subsystem, so state survives map loads. Everything below is a UFUNCTION, so by-name calls work too.

- **Listen:** `OnQuestEvent(QuestId, StepId, ObjectiveId, Type)` with Type one of Offered, Accepted, Declined,
  StepStarted, ObjectiveProgress, ObjectiveComplete, StepComplete, ReadyToTurnIn, Completed, Failed, ChoiceMade or
  Tracked. Also `OnUnlock(Unlock, Quest)`, `OnGameEvent(Key, Arg, Count)`, `OnStandingChanged(Person, Value)` and
  `OnQuestsChanged`.
- **Report:** `NotifyEvent(Key, Arg, Count)` for anything a quest may wait on. Cutscenes send
  `NotifyEvent("CutsceneDone", "<Name>")`.
- **Ask:** `GetStatus(Quest)`, `HasUnlock(Flag)` (every finished quest sets `Quest_<Id>`, every choice
  `Choice_<Quest>_<Choice>`), `GetStanding(Person)`, `GetItemCount(Item)`.
- **Markers:** `#include "Quests/ReflectionsStoryMarker.h"`, then `UReflectionsStoryMarkerSubsystem::FindMarker(this, Name)`
  or `GetMarkerTransform(this, Name, OutXf)`. Also `FindByKind("Home")`, `GetAllMarkers()` and
  `OnMarkerPlaced(Name, Marker, bAuto)`.
- **Voice (npc-dialogue):** `GetQuestActions(Npc)` returns `offer_quest:<q>`, `accept:<q>`, `decline:<q>`,
  `turn_in:<q>`, `give_hint:<q>`, `choose:<q>.<choice>`, `talk:<q>` and `deliver:<q>`.
  `ExecuteQuestAction(Npc, Action, OutReason, OutSay)` re-checks against the live state, and OutSay is the line to
  speak. `GetQuestContext(Npc)` returns JSON for the persona. `HandleTalkPressed(Npc)` opens the talk card when the
  person has quest business. `NotifyTalkedTo(Npc)` counts a voice conversation for talk objectives.
- **Game flow:** `OpenJournal()` is what the pause menu's Journal button calls.
- **Consequences (npc-unify):**
  - Deaths come through `OnNpcDied`. Anyone can also call `NotifyPersonDied(Person, bByHero)` by name.
  - `OnPlayerCrime(Victim, Crime, Witness, Location, Heat)` is bound by name, and only when it exists. One crime is
    counted once per victim + crime + 3 m cell + 10 s, whatever the number of witnesses. The victim loses standing:
    Murder 20, Assault 10, Theft 7, anything else 4. A witness who is a person loses a quarter of that.
  - `NotifyCrimeAgainst(Person, Severity 0..1)` does the same by hand.
  - Heat comes by name from `UReflectionsNpcSubsystem::GetPlayerHeat()` (0..1). Without it, heat is 0.

## When people die, and when the hero is wanted

- **A side quest that still needs the dead person fails.** That's a later talk-to, delivery, cure or protect target,
  a choice, or `failIfDies`. The quest shows QUEST FAILED with a journal note ("Hal is dead. There's no finishing
  this now.", or "…died by my hand…" when the hero did it). The dead speak no fail lines.
- **The alternative: only the giver is gone.** The quest goes on ("NO ONE TO RETURN TO") and finishes itself when
  its work is done, with no turn-in and no reputation with the dead.
- **An offered but not accepted quest just closes.** It's listed in the journal only if the hero had heard the
  offer.
- **The main quest never fails.** A beat that needed the dead person is passed over, now or when its step starts.
- **Dead people are never respawned as givers or offer quests again.** The dead list saves with the checkpoint.
- **Heat:** at heat ≥ `Quest.HeatRefuse` (default 0.5, the point where guards turn on the hero), givers refuse new
  side quests with a baked line, and the voice relay gets `wary_of_hero` in `GetQuestContext` plus a reason from
  `ExecuteQuestAction`. Each giver's limit shifts: Timid -0.15, Brave +0.15, standing 25+ with them +0.25, 60+
  +0.5. Quests already accepted, hints, turn-ins and the main quest
  are never refused.

## Writing quests (JSON)

A quest is steps. A step is objectives (all required by default, or `"any": true`) and optionally a choice. Every
field is optional except `id`. The format accepts camelCase or snake_case, and several aliases (`type: "kill"` =
`defeat`).

```json
{"quests": [{
  "id": "lost_ledger", "title": "The Clerk's Lost Ledger", "summary": "...",
  "giver": "GiltMaren", "side": "Giltside", "requires": ["other_quest"], "requiresUnlocks": ["Quest_main"],
  "offer": ["line", "line"], "accept": ["line"], "decline": ["line"], "reminder": ["line"], "turnInLines": ["line"],
  "reward": {"coins": 2, "coinSide": "Giltside", "mana": 25, "reputation": {"GiltMaren": 15}, "unlocks": ["X"], "items": ["Y"]},
  "steps": [
    {"id": "find", "title": "In the Fog", "description": "journal text",
     "lines": ["said when the step starts"], "speaker": "GiltMaren",
     "objectives": [{"type": "collect", "target": "Ledger", "count": 1, "text": "Find the ledger", "hints": ["..."]}]},
    {"id": "decide", "choicePerson": "GiltMaren",
     "objectives": [{"type": "deliver", "item": "Ledger", "target": "GiltMaren"}],
     "choices": [{"id": "keep", "text": "Your secret is safe.", "response": "...", "next": "End",
                  "reward": {"reputation": {"GiltMaren": 10}}, "journal": "I promised..."}]}
  ]}]}
```

| Objective `type` | Uses | Done when |
|---|---|---|
| `talkTo` | `target` person | the hero talks to them (card or voice) |
| `goTo` | `target` marker, `radius` | the hero is inside the radius, on the same side |
| `collect` | `target` item, `count`, `marker` (default `Item_<item>`) | holding `count` (items spawn at the marker) |
| `deliver` | `item`, `target` person, `count` | handed over while talking to them |
| `defeat` | `target` = archetype prefix (`Soldier`), tag, person, `Infected`, `Hostile`, `Any`; `spawn` + `spawnCount` + `marker` | `count` killed by the hero |
| `spellHit` | `spell` = spell (`IceShard`) or element (`Fire`, `Ice`, `Water`, `Lightning`, `Earth`, `Air`, `Arcane`, `Life`); `target` = marker (hit within `radius`), person, tag or `Infected` | `count` hits |
| `worldJump` | `side` (or none for any jump) | the hero steps through to it |
| `protect` | `target` marker, `radius`, `seconds`, optional `spawn` waves | the hero stays inside for `seconds` in total |
| `event` | `target` = key, `arg` filter, `count` | the game reports it |

Event keys the game reports itself:
- **Progress:** `ShardCollected` (arg side), `WorldJump` (side), `PageFound` (`Pewterside`/`Giltside`/`Frostside`),
  `KeyFound` (key id, such as `GiltTowerKey`), `DoorOpened` (the door's key id), `BookComplete`, `FinaleStarted`,
  `BossDefeated`, `Victory`.
- **People and spells:** `NpcCured` (person id or none; a tarnished NPC back to None), `NpcTarnished`, `Conversion`
  (the Tarnish converts someone within 40 m of the hero), `VillainHost`, `PersonDied` (anyone kills a person),
  `Defeated` (archetype, hero kills), `SpellCast` (spell name, hero casts).
- **Quest system:** `Talked` (person), `QuestComplete` (quest), `ItemFound` (item), `Unlocked` (flag).
- **Other systems:** `CutsceneDone` (name, from cutscenes).

Give an `event` objective a `marker` and a `radius`, and it only counts events inside that zone. MQ05 counts cures
within 40 m of the gate this way. The keys that describe a state (pages, keys, doors, book, finale, victory, quests,
items, shards, unlocks, cutscenes seen) also count what already happened before the step began. A `worldJump` with
a `side` counts as done if the hero is already there. So the story skips forward when the player is ahead, and a
reloaded checkpoint still sees the pages you already have.

**Lines** are strings, or `{"id": "MQ01_03", "speaker": "ilse_varrow", "text": "...", "delay": 6}`. The id's cue
`/Game/Audio/Jam/Voice/Cues/SCue_VO_<id>` plays from the speaker. Speakers are people-book ids, plus `wren_hale`,
`the_tarnish` and `narrator`. Lines show in the talk card when it's open, and otherwise as subtitles above the
spell bar. Where lines go:

| Field | Where | When |
|---|---|---|
| `offer`, `accept`, `decline`, `reminder`, `turnInLines` | quest | talk card or voice |
| `after` | quest | once after it's done: on talking to the speaker, or within 3 m |
| `fail` | quest | once if it fails (`failIfDies: <person>`) |
| `lines`, `completeLines` | step | step starts, step ends |
| `talk: [{person, lines}]` | step | talking to that person during the step (optional colour) |
| `completeLines` (alias `lines`) | objective | objective done; a `talkTo` objective's lines are what the person says when spoken to |
| `progressLines` | objective | entry i at progress i + 1 (MQ05's first and second cure) |

Other step and objective fields:
- `cutscene` (step): plays at step start. A step with only a cutscene waits until it ends; it moves on if the scene
  can't play or was already seen.
- `timeout` (step): seconds; finishes the step if nothing else did.
- `hidden` (objective): kept out of the tracker. Use it for branches and trigger zones.
- `spawn` + `spawnCount` (objective, any type): spawns that archetype at the objective's `marker`, or in front of the
  hero. `Infected` / `Tarnished` first turns townsfolk near the spot (the story's rule) and counts tarnished already
  there.
- `"target": "VillainHost"` / `"VillainArena"`: the Tarnish's current host (else the nearest tarnished) and the
  finale arena.

FirstPage, GiltTower and MirrorWhole play on their game events (first page, tower door opened, book whole), whatever
the main quest's step. A quest step naming them then sees them as played and goes on. Pages come in any order.

Step flow: `next` names the following step. `"End"` finishes the quest, and `"Fail"` fails it. Quests with a giver
end at **Return to <giver>** (`turnIn`, on by default). The main quest (`"main": true`) starts by itself, can't be
declined and replaces the built-in one.

Step voice: if `/Game/Audio/Jam/Voice/Cues/Quest/SCue_VO_Quest_<QuestId>_<StepId>` exists, it plays when the step
starts. Quest sounds `SCue_Quest_Start`, `SCue_Quest_Objective`, `SCue_Quest_Complete` and `SCue_Quest_Update` fall
back to `SCue_UI_Confirm`.

**Load content:** put the quests in `ArtDirection/Quests/data/story_quests.json`, then run `Tools/Quests/import_story.py`
in the editor. That writes `/Game/Quests/DA_QuestPack_Story` and needs a rebuild of nothing. To try content without
saving an asset, run `Quest.LoadJson ArtDirection/Quests/data/story_quests.json ArtDirection/Story/people.json` in PIE.

## Story content (v1, from the story bible)

**The source is `ArtDirection/Story/quests.json`.** The story session generates it with
`ArtDirection/Story/tools/build_quests.py` from `main-quest.md` and `side-quests.md`; change the generator, not the
JSON. It holds:
- **The main quest:** "The Mirror Made Whole". It replaces the built-in one below.
- **Side quests:** `sq1_cellar` … `sq12_empty_chair`. SQ10 to SQ12 cover the Watch book, the Third at the canal
  rift and the Fennicks.
- **An item list:** item names for the HUD.

`Tools/Quests/import_story.py` builds the asset from it. `ArtDirection/Quests/data/story_quests.json` is an older
hand conversion, kept only for reference.

Story fields the parser understands on top of the format above:
- **Lines:** `linesOn` / `linesAt: "complete" | "arrive"` (the step's lines play when it ends). With no `linesOn`, a
  step with a `talkTo` objective gives its lines to that person, said when spoken to. Also `linesOnComplete`,
  `linesOnObjective {"i": lines}`, `progressLines {"n": lines}`, `optionalTalk {person: lines}`, and `afterLine`.
- **Items:** `giveItems` (at step start), `giveItemsOnObjective {"i": items}`, and `rewardOnComplete`.
- **Order and failure:** `ordered` (objectives one at a time), `failIfDies` (on a step), and `startsTarnished` (those
  people turn tarnished, with `NoVillain`, when the quest is accepted).
- **Cutscenes and spawns:** `cutscene`, `cutsceneOnComplete`, and `spawnMarker`.
- **Cures:** a `spellHit` with `cure` / `requireInfected` counts only the cure itself, the `NpcCured` event. Its
  target is a person, or anyone when it's `Infected` or has a `fallbackTarget`.
- **Branches and the law:**
  - `ifKilledNext` on a step: when the hero kills a tarnished target there instead of curing it, the quest goes to
    that step, and the kill counts there. SQ11: `cure_wat` → `cut_wat`.
  - `offerIfWanted` on a quest: the giver says those lines and holds the offer while heat is 0.5 or more. SQ11:
    Mayne.
  - The `Silverer_RecordClean` unlock (SQ10's reward) calls npc-unify's `ClearPlayerHeat`.

Story intent the code doesn't act on yet: `ifInfected`, `linesIfTargetWasCured`, `linesOnFail`, `meterLines`,
`squadLines`, `ifCutsceneSkipped`, `pauseLinesWhenOutside`, `spawnAfterObjective`, `scriptedHold`,
`endHoldOnStart`, `startOn`, `requiresAlive`, `autoOffer`, and `availability`. The quests still play without them.

Every finished step sets the unlock `Quest_<quest>.<step>`, which is what side quests' `requiresUnlocks` name, for
example `Quest_main.lantern_row`. People come from `people.json`:
- Their `markers.work` is where a person nobody placed gets spawned.
- Their barks are the talk card's idle lines.
- `markers.story_names` maps the people book's `Mk_` tags onto the `Spot_`/`Tower_` names, so either tag works in
  the map.

Places use the story's `Mk_<Pew|Gilt|Frost>_<Kind>_<Name>` tags on any actor, a Target Point included. The story
marker subsystem adopts a tagged actor, else uses another `Mk_<Side>_<Kind>_*` place as a stand-in, else
auto-places one.

## The built-in main quest

The built-in main quest (`main`) follows the progression that already exists. It only listens; it doesn't change
how anything plays. The story pack replaces it with the same beats, richer.

1. **A Shard of Glass**: pick up a mirror shard (`ShardCollected`).
2. **Through the Glass**: step through to another side (`worldJump`).
3. **Three Towers, Three Pages**: Pewterside's, Giltside's and Frostside's pages (`PageFound` per side, pointers to
   `Tower_<Side>`), plus the optional Gilt Tower key (`KeyFound GiltTowerKey`).
4. **The Mirror Made Whole**: reach the Tarnish atop Frostside's tower (`goTo VillainArena`: the villain's arena,
   else `Tower_Frostside`).
5. **Break the Tarnish**: defeat it with the Final Spell (`BossDefeated`, from game flow's victory).

The story bible's main quest replaces this with its own beats on the same events.

## One London (Gray London, no world jump)

When the map has no world anchors (world-jump's `IsWorldJumpActive()` is false), the three-Londons story still
plays:
- `worldJump` objectives finish by themselves.
- Side filters on objectives always match.
- `PageFound <Side>` means the Nth page found: Pewterside the 1st, Giltside the 2nd, Frostside the 3rd.
- Shards from any side count.
- `goTo` radii are at least 25 m, since the walks between beats are 300–600 m.

## The story catches up

The main quest's steps come in order, but the world doesn't wait for that order. Each tick, if a later main-quest
step's progress has already happened (`PageFound`, `KeyFound`, `BookComplete`, `FinaleStarted`, `BossDefeated`,
`Victory`), the steps before it are passed over. Their subtitles are dropped, and only the newest banner shows.

## PIE proof (`Tools/Quests/test_quests_pie.py`, screenshots in `Screenshots/`)

- **Side quest:** the test quest, start to finish on `Lvl_WorldJumpTest` (2026-11-14 16:41). Offer, accept,
  pickup, Fire cast at the brazier, delivery, choice, turn-in, reward and journal (`01_…` to `16_…`).
- **Main quest:** start to victory on `Lvl_MockCity`, train #11+12 (2026-11-14 20:05). The intro fallback leads to
  the tracker (`20_main_start`).
  - **Catch-up:** with the story still at `lantern_row`, picking up the real Pewterside page jumped it straight to
    `hold_line` ("Step back up into Giltside", `21_catchup_after_page`).
  - **The rest of the walk:** `22_main_NN_<step>`, ending Completed with `Quest_main` (`29_victory`). The steps the
    test can't act out (world jumps from script, the key, the boss outside the finale) were forced with
    `Quest.CompleteStep`.
  - **Markers:** nothing was auto-placed (`GetAutoPlacedNames` was empty).
- **Story pack on Gray London** (train #13, 2026-11-15 01:59): 13 quests imported.
  - **SQ9 *Unsigned*:** played end to end through talk cards. Barnaby's offer (`31_sq9_offer`), accept, Odette, the
    wool to Barnaby, the shears to Odette, then Completed with `Seam_Held` (`33_…`, `34_sq9_complete`).
  - **No pause:** the game was not paused while a talk card was open.
  - **Deaths:** with SQ7 accepted, Dov Merriman died, and SQ7 FAILED with the note "Dov Merriman died by my hand.
    There's no finishing this now." (`36_quest_failed_banner`, `35_journal_story`).
  - **Markers:** nothing was auto-placed.
- **Still to run:** heat refusals (npc-unify's `Npc.Heat` is off), SQ11's kill branch, and one-London mode plus the
  spawn-through-Lives change (next train).

## Saving

The quest state goes with game flow's checkpoints. On every checkpoint save, the quests write slot
`Reflections_Quests`, stamped with the checkpoint's time. When game flow restores that checkpoint (try again, continue,
respawn after a reload), the quests roll back to the same moment. Game flow's save slots copy this file into each
slot and write it back on load. If the in-memory copy belongs to another checkpoint, the quests re-read the file
before restoring. New Game clears them. Saved per quest: status,
step, objective progress, protect timers, hints given, log and choices. Also saved: items, standing per person,
unlock flags, the tracked quest and who has died.

## Console (non-shipping)

`Quest.Status`, `Quest.Ui`, `Quest.Journal`, `Quest.Talk <Person>`, `Quest.TalkOption <i>` (-1 = next line),
`Quest.Accept <q>`, `Quest.CompleteObjective <q> <o>`, `Quest.CompleteStep <q>`, `Quest.Choose <q> <c>`,
`Quest.TurnIn <q>`, `Quest.Event <Key> [Arg] [Count]`, `Quest.Track <q>`, `Quest.GiveItem <item> [n]`,
`Quest.Reset`, `Quest.Reload`, `Quest.LoadJson <quests> [people]`, `Quest.HeatRefuse <0..1, 2 = never>`. Also `Quest.ShowTestQuests -1|0|1` (the test
quest shows only while no real side quests are loaded), `Quest.SpawnMissingPeople 0|1`, `Quest.TalkRadius <cm>` and
`Quest.Enable 0|1`. Markers: `Story.Markers`, `Story.FindMarker <Name>`, `Story.ShowMarkers 0|1`,
`Story.MarkerFallback 0|1`.

## Packaging

`/Game/Quests` is loaded by path (`DA_QuestPack_Story`), so it has to be in `DirectoriesToAlwaysCook`.
