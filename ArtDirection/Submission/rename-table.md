# Rename table: "Three Londons" → *Reflections* (set B)

The team chose set B on 2026-11-14 ([originality.md](originality.md)). This file lists every string a player can see or hear that has to change, with its file and owner. The survey ran at 10:20–10:45 MST on 2026-11-14. Line numbers drift as sessions edit, so search for the old text rather than trusting the line. **Owners make their own edits.** This session edits none of their files.

## The vocabulary

| Old | New | Notes |
| --- | --- | --- |
| Three Londons (title) | **Reflections** | |
| London (the city) | **Lanthorne** | Rarely needed. Most lines name a side instead. |
| Gray London | **Pewterside** | One word, so the HUD coin row, which shows only the first word, works unchanged |
| Red London | **Giltside** | |
| White London | **Frostside** | |
| "a London" (one of the worlds) | **a side** / **a reflection** | e.g. "There is no reflection above Frostside." |
| coin | **mirror shard**, shortened to **shard** where space is tight | Say "mirror shard" in any sentence, because the spells already have *Ice Shard*, *Stone Shard* and crafting's *Split* shards |
| cross / crossing / world jump | **step through** / **stepping through** | Keep the direction words: "step up into", "step down into" |
| the hero's coat | **the silvered coat** | No coat text reaches the player today |
| hero | **Wren Hale, the Silverer** | Not named anywhere in game yet |
| villain ("him") | **the Tarnish**, called **it** | "Now stop him." → "Now burn out the Tarnish." |
| infection / infected | **Tarnish** / **tarnished** | Name of the infection meter |
| the book / book pages | **the mirror** / **mirror pages** | "The book is whole" → "The mirror is whole" |
| Red Tower | **Gilt Tower** | |

## world-jump (`local_830b60d0`)

**Change all three name sources.** `GetWorldName()` reads the data asset first, then the C++ defaults, then the enum `DisplayName`, so any one left unchanged brings the old name back.

| # | File:line | Current | New |
| --- | --- | --- | --- |
| W1 | `/Game/Worlds/DA_WorldJumpConfig` → `Worlds[0..2].DisplayName` | `Gray London` · `Red London` · `White London` | `Pewterside` · `Giltside` · `Frostside` |
| W2 | `Source/reflections/Worlds/ReflectionsWorldJumpConfig.cpp:30,32,34` | same, as C++ defaults | same as W1 |
| W3 | `Source/reflections/Worlds/ReflectionsWorldTypes.h:13-15` | `UMETA(DisplayName = "Gray London")` etc. | `"Pewterside"` · `"Giltside"` · `"Frostside"` |
| W4 | `ReflectionsWorldHud.cpp:131` (panel) and `:218` (arrival banner) | upper-cased name: `RED LONDON` | follows W1: `GILTSIDE` |
| W5 | `ReflectionsWorldHud.cpp:83` | `Coins` | `Mirror shards` |
| W6 | `ReflectionsWorldHud.cpp:148-151` | `Gray 0  Red 1  White 0` (first word of each name) | follows W1: `Pewterside 0  Giltside 1  Frostside 0` |
| W7 | `ReflectionsWorldHud.cpp:198` | `  (needs a {0} coin)` | `  (needs a {0} shard)` |
| W8 | `ReflectionsWorldHud.cpp:204` with `:207` / `:208` | `Hold [{0}]  rise to {1}` / `sink to {1}` | `Hold [{0}]  step up into {1}` / `step down into {1}` |
| W9 | `ReflectionsWorldHud.cpp:177` | `Magic {0} / {1}  -  a crossing takes {2}` | `Magic {0} / {1}  -  stepping through takes {2}` |
| W10 | `ReflectionsWorldHud.cpp:178` | `… a crossing takes {2} (not drained yet)` | `… stepping through takes {2} (not drained yet)` |
| W11 | `ReflectionsWorldHud.cpp:184` | `Magic: no magic bar on this hero (crossings are free)` | `… (stepping through is free)` |
| W12 | KeyId `RedTowerKey` (`ReflectionsWorldPickups.h:122`, `ReflectionsSealedDoor.h:24`, plus every placed key and door) → `Keys: Red Tower Key` | `RedTowerKey` | `GiltTowerKey` → `Keys: Gilt Tower Key` |
| W13 | `ReflectionsWorldPickups.cpp:200` | `the Red Tower key` | `the Gilt Tower key` |
| W14 | `ReflectionsSealedDoor.cpp:51` | `Sealed. Its key is hidden somewhere in Red London.` | `Sealed. Its key is hidden somewhere in Giltside.` |
| W15 | `ReflectionsWorldJumpComponent.cpp:523` | `There is no London above {0}.` | `There is no reflection above {0}.` |
| W16 | `ReflectionsWorldJumpComponent.cpp:524` | `There is no London below {0}.` | `There is no reflection below {0}.` |
| W17 | `ReflectionsWorldJumpComponent.cpp:532` | `You need a coin from {0} to cross.` | `You need a {0} shard to step through.` |
| W18 | `ReflectionsWorldJumpComponent.cpp:618` | `You need a coin to cross.` | `You need a mirror shard to step through.` |
| W19 | `ReflectionsWorldJumpComponent.cpp:543` | `Not enough magic: the crossing takes {0}, you have {1}.` | `Not enough magic: stepping through takes {0}, you have {1}.` |
| W20 | `ReflectionsWorldJumpComponent.cpp:549` | `Your magic cannot be spent on a crossing yet.` | `Your magic cannot be spent on stepping through yet.` |
| W21 | `ReflectionsWorldJumpComponent.cpp:555` | `You have no magic to cross with.` | `You have no magic to step through with.` |
| W22 | `ReflectionsWorldJumpComponent.cpp:757` | `Crossing into {0}...` | `Stepping through into {0}...` |
| W23 | `ReflectionsWorldPickups.cpp:146` | `A {0} coin: it pays for one crossing into {0}.` | `A {0} shard: it lets you step through into {0} once.` |
| W24 | `ReflectionsWorldHud.cpp:156-157` | `Book pages {0} / {1}` (`  -  the spell is ready`) | `Mirror pages {0} / {1}` (`  -  the spell is ready`) |
| W25 | `ReflectionsWorldJumpComponent.cpp:1161` | `The book is whole` | `The mirror is whole` |
| W26 | `ReflectionsWorldJumpComponent.cpp:1162` | `Three pages, one spell. Now stop him.` | `Three pages, one spell. Now burn out the Tarnish.` |
| W27 | `ReflectionsWorldPickups.cpp:181` | `A page of the book` | `A mirror page` |
| W28 | `PageTitle` on every BookPagePickup placed in the **final map** (test maps have `A page from the Red tower` etc.) | `… Gray / Red / White …` | e.g. `A page from the Gilt Tower`, `A page from Pewterside's high spot` |
| W29 | `/Game/Worlds/Input/IA_WorldJumpUp` / `IA_WorldJumpDown` → `ActionDescription` | `Rise one London toward White` / `Sink one London toward Gray` | `Step up one side, toward Frostside` / `Step down one side, toward Pewterside` (shown if game-flow-ui's Controls screen lists descriptions) |
| W30 | `/Game/Worlds/Input/IMC_WorldJump` → `ContextDescription` | `World jump (Reflections): rise / sink one London` | `Step through (Reflections): up / down one side` |
| W31 | Optional, hidden in game: `ReflectionsWorldAnchor.cpp:114` | `{0} anchor` gives `Red London anchor` | follows W1 automatically |
| W32 | Optional, de-risks IP: `DA_WorldJumpConfig` → **Coin Rule** | `destination` | `any` or `current`: the books' traveller carries a token of the destination. The user still has to decide this (README decision 4). Don't change it before then. |

## game-flow-ui (`local_0b912c4f`)

| # | File:line | Current | New |
| --- | --- | --- | --- |
| G1 | `Source/reflections/GameFlow/ReflectionsGameFlowSubsystem.h:178` | Save slot `ThreeLondons_Checkpoint` (seen as `Saved/SaveGames/ThreeLondons_Checkpoint.sav`) | `Reflections_Checkpoint` |
| G2 | Title screen, Credits, Victory and Lose (Slate text, not written yet) | — | Title **REFLECTIONS**. No "London" or "Three Londons" anywhere. Credits: see [ai-declaration.md](ai-declaration.md). |
| G3 | Infection meter label and toasts | "Infection" / "infected" | **Tarnish** / **tarnished** (e.g. "Tarnish 7 / 20", "The Tarnish has taken Lanthorne.") |
| G4 | Tips `Coin` and `CrossWorlds` (`ReflectionsGameFlowTypes.h`) | — | Wording from the vocabulary, kept neutral to the Coin Rule (revised 11-14): "Mirror shards let you step through. Stepping through also takes most of your magic." / "Hold X / Y to step up into the next side, Z / R3 to step down." |
| G5 | Controls screen | — | Use the action names in [itch-page.md](itch-page.md#controls). If it lists `ActionDescription`, W29–W30 apply. |
| G6 | Theme line (chosen 2026-11-14) | — | The title or intro screen shows: **"Lanthorne was cut into three reflections, and only one is the version its maker meant. The Tarnish wants the final cut."** |

## villain-finale (`local_dd0eeffa`)

| # | File:line | Current | New |
| --- | --- | --- | --- |
| V1 | `Source/reflections/Villain/ReflectionsVillainFx.cpp:31-32` (`Villain.RiftDelay` / `RiftChance` help, Development console only) | `…sent to another London…` | `…sent to another side…` |
| V2 | All on-screen villain text you add (`ShowMessage`, the finale, a boss name bar) | — | The villain is **the Tarnish**, called **it**. Hosts are **tarnished**. Never "London", "the Shadow King", or any name from the books. |
| V3 | `/Game/Villain/*` asset names | — | Internal only, so any name is fine |

## packaging (`local_51169275`)

| # | File | Current | New |
| --- | --- | --- | --- |
| P1 | `Config/DefaultGame.ini` `[/Script/EngineSettings.GeneralProjectSettings]` | `ProjectName=Third Person Game Template`; no `ProjectDisplayedTitle` (the window shows "reflections (64-bit Development PCD3D_SM6)") | `ProjectName=Reflections`; Displayed Title `Reflections` (the `ProjectDisplayedTitle` FText, also editable in Project Settings → Description); `CompanyName=[team name]`; `Description=Three reflections of one city.` |
| P2 | Zip name | `matched_Windows.zip` | `[TeamName]_Reflections.zip` (team name pending, README decision 3) |
| P3 | `reflections.exe`, pak and folder names | — | Leave as they are. They already match the title. |

## spells (`local_07d1c5bc`) and spell-crafting (`local_f926586a`)

**No renames.** Neither area has world, coin or coat wording. The shard overlap (*Ice Shard*, *Stone Shard*, crafting's Split "shards") is handled by world-jump saying "mirror shard". Low risk, no action needed: crafting's `Escort: the field travels with you` (`ReflectionsSpellCraftingLibrary.cpp:602`).

## audio (`local_8ac9a603`)

**No renames.** Nothing audio-related is visible or spoken. The music is instrumental and the villain whispers have no words. Asset names such as `SW_MUS_Red_Loop` are internal. If any voiced line or title is ever generated, use the vocabulary above.

## Unassigned (orchestrator to place)

| # | File:line | Current | New |
| --- | --- | --- | --- |
| U1 | `Tools/RealtimeVoice/relay.py:33` (spoken context for the dev AI voice) | `A London citizen` | **Done.** The NPC dialogue session owns it now; the only "London" left is in a test that checks it's filtered out. |
| U2 | `Source/reflections/Voice/ReflectionsVoiceInteractionSubsystem.cpp` | **T** printed `AI voice: Voice relay token is not configured.` | **Done.** It's now NPC talk-back, failures show nothing, and it's off-network in the packaged build. |
| U3 | `/Game/Levels/LevelPrototyping` blocks in the start map | `1 M`, `2 M` height labels show in the world (visible in every current screenshot) | Hide the TextRender, or swap the blocks in the final map |

## Not player-visible: leave alone

Content folders `Characters/RedLondon`, `Characters/WhiteLondon`, `ArtDirection/Three-Londons*`, audio asset names, `TravelDrape` / `HeroCoat` / `CoatTint` and NPC role assets such as `CoinClerk`. They only appear in cooked paths and logs. Renaming packages this late risks broken references for no player-facing gain.
