# World jump and tower hunt: how to plug in the real Londons

This covers the jump between Gray, Red and White London, the coins, the book pages, the Red tower key and its
sealed door. All the code is in `Source/reflections/Worlds/`. All the assets are in `/Game/Worlds/`.

## The one assumption your maps must match

**The three Londons are the same city at the same scale and orientation. Each copy is moved by a pure
translation (no rotation, no scale).**

A jump keeps the hero's exact spot and height. In code, that is
`new position = old position - anchor(current London) + anchor(destination London)`. So a stair-top in Gray
lands on whatever sits at that same spot in Red. That spot is how the win path works:

- **Gray to Red:** Gray's stairs climb to a high spot. Red needs something to stand on at that height and spot,
  such as a rooftop. If nothing is there, the jump is refused. The hero is never dropped into the void.
- **Red's tower:** the door is sealed. Its key (`RedTowerKey`) is somewhere else in Red.
- **White's tower:** it is locked from the ground, so the only way in is to stand inside Red's tower and jump up.
  White's tower interior must sit where Red's tower interior is, at the same floor height. If something solid is
  there, the landing spot moves up to 1.5 m clear of it.

Each London can still look and play differently: buildings missing, rubble, other props. Only the spots the win
path relies on need to line up.

## Swap the real Londons in (the short version)

The test maps use a fixed convention: **Gray at X = 0, Red at X = +150000, White at X = +300000** (1.5 km apart,
no rotation, no scale). The code does not hard-code these numbers. It only uses the distance between the anchors.
So you can keep the convention, or use a bigger step if your city is wider. The step must be larger than the city's
width plus the fog or draw distance, so one copy can never see another. For a city about 1 km wide, 150000 is
enough. For 3 km, use about 500000.

1. Make the three real maps: `Gray`, `Red` and `White`. They are the same city, so duplicate one and dress each
   copy. Keep them out of `/Game/Worlds/Test`, which is never cooked.
2. In each real map, place a **Reflections World Anchor** on the same landmark and at the same local coordinates in
   all three. The simplest choice is the map's origin (0, 0, 0). Set its **World** and size its **Bounds** box to
   cover the whole map. The default box is 1.2 km x 1.2 km x 600 m, centred on the anchor. Keep a copy's box from
   overlapping the next copy.
3. Make the persistent map. Either duplicate `/Game/Worlds/Test/Lvl_WorldJumpTest` (sun, sky, fog, PlayerStart,
   `ReflectionsSampleGameMode`) and point its three sublevels at your maps, or build a new one: in *Window >
   Levels*, add the three maps as **Always Loaded** sublevels. Then right-click each > *Change Streaming Level
   Transform* and set the translation to (0,0,0), (150000,0,0) and (300000,0,0), or your own step.
4. Move the PlayerStart to the London the game opens in. It belongs in the persistent level, at its offset
   position (for Red, add 150000 to X).
5. Play. The HUD (top left) shows the London you're in, the coins, the pages and the jump prompts. A rise or sink
   lands at the same local spot in the next copy.

If the real map is **World Partition**, it can't be a sublevel. Then the options are: put all three copies into one
World Partition map at the offsets, with one anchor in each copy, or switch the config's *Layout* to
*Separate Maps* (route B below).

## Two ways to lay out the maps

Pick one in `/Game/Worlds/DA_WorldJumpConfig` > **Layout**.

### A. Offset copies (recommended: the jump is instant, with no loading)

All three Londons are loaded at once, far apart, and the jump is a teleport.

1. Get the three copies into one level, far enough apart that no copy can see another. 1.5 km between copies
   works for the test maps. For the real city, use more distance than the fog and draw distance can show. Two
   ways to do it:
   - **One map, duplicated in place.** Select all the actors of the city, duplicate them, and move the copy
     along X (for example +150000). Do it twice.
   - **Three separate maps as sublevels.** Make a persistent level. In *Window > Levels*, add `Gray`, `Red` and
     `White` as *Always Loaded* sublevels. Then use *Change Streaming Level Transform* (Levels window, right-click)
     to give each one a translation. This is how `/Game/Worlds/Test/Lvl_WorldJumpTest` is built: open it to see
     it. A World Partition map cannot be a sublevel. If yours is World Partition, use the duplicate-in-place
     route, or Level Instances of non-partitioned maps.
2. Put one **Reflections World Anchor** (Place Actors, search "World Anchor") in each copy, on **the same
   landmark**. For example, put each one on the same corner of the same building's doorstep. Set its **World**
   to Gray, Red or White. Only the anchors' positions relative to each other matter, so place them carefully.
   One wrong anchor shifts every landing in that London.
3. Resize each anchor's yellow **Bounds** box so it covers its whole copy. Anything inside the box belongs to that
   London. This tells the game which London the hero, or a native, is standing in.
4. Lighting: one directional light, sky and fog serve all three copies. Give each copy its own *bounded*
   Post Process Volume for its colour grade. The test maps do this: Gray is desaturated, Red is warm and red,
   White is bleached and pale.

Maps with no anchors are left completely alone. Nobody else's test map gets a world-jump HUD.

### B. Separate maps (fallback: it works with anything, but loads)

Set **Layout** to *Separate Maps* and set each London's **Map** in the config's **Worlds** list. A jump opens the
other map and puts the hero at the same coordinates, with the same safe-landing rules. Coins, pages and keys
carry over, because they live in a game-instance subsystem. This has a loading hitch. The spell driver also
refills magic on load, so the 80% cost is undone. Use it only if offset copies are impossible.

## What the player does

| | Keyboard | Controller |
|---|---|---|
| Rise one London (toward White) | hold **X** | hold **Y** (top face button) |
| Sink one London (toward Gray) | hold **Z** | hold **R3** (right stick click) |

The hold is 0.25 s, so a stray press doesn't burn a coin. Spells own LT, RT, the bumpers and D-pad Left/Right.
L3 is gamepad sprint. D-pad Down is smart-object Interact. Y was only mapped to an unused sandbox action
(IA_CycleWeapon). Rebind in `/Game/Worlds/Input/IMC_WorldJump`. The world-jump context is added at priority 2,
above the pawn's and the spells' contexts, so it takes Y and R3 first.

A jump costs **one coin of the destination London** and **80% of maximum magic**. The coin is a token of the place
you're going, and enemies drop the coin of their home London. Both are set in the config: **Coin Rule** (destination /
current / any) and **Magic Cost Fraction**. If the hero can't pay, or the landing spot is blocked, the jump is
refused with a reason on screen and nothing is spent.

The transition is a quick flash in the destination's colour: 0.12 s out, then 0.45 s back in. The hero's velocity
is kept, cloth is reset in place, the coat takes the new London's tint, and the London's name comes up as a
banner. Each London has a colour grade, applied by its anchor's bounds and set per London in the config's
**Worlds > Grade**. Turn it off on an anchor (*Apply World Grade*) if the map brings its own volumes.

Audio (cues by the audio session in `/Game/Audio/Jam/Cues`, referenced from the config): *Jump Sound* (whoosh at
departure), *Arrival Sound* (stinger) plus *Arrival Sound Mix* (a 3.5 s music duck), *Refused Sound*, *Pickup Sound*
(coins), *Page Sound*, *Key Sound* and *Door Unseal Sound*. Each London's **Music** loop is in **Worlds**: it fades
out over 0.5 s at departure and in over 1.5 s on arrival. Untick *Play World Music* if music moves elsewhere.
Optional extras: *Arrival Camera Shake* and *Departure/Arrival Effect* (Niagara).

### Coat tint

The visible coat on the hero (`BP_HeroTravelVisual`) is the `TravelDrape` cloak plus `TravelSleeves`. Their
materials have no colour parameter, so the tint draws on top of them. `/Game/Worlds/Materials/M_WorldCoatTintOverlay`
is set as the mesh's *overlay material* at runtime: translucent, lit, with a soft rim glow in the London's **Coat
Tint**. It works like a dye: the tint's **alpha** sets how strongly it covers the cloth (Red 0.5, Gray 0.45,
White 0.6), so the folds and shading show through. It sits 0.4 cm outside the cloth (*ShellOffset*) and draws front faces only, so it never speckles
against the coat underneath. Nothing of the cloak's is edited, and its lining and cloth sim stay as they are. The components are listed
by name in the config's **Coat Component Names**. Any replacement overlay material needs **Used with Skeletal
Mesh** and **Used with Clothing** ticked, or the game draws the default material instead. If the drape material
ever gets a `WorldTint` vector parameter, the code sets that instead and skips the overlay.

## Placing the hunt

All of these are in Place Actors under "Reflections":

- **Reflections World Coin**: set *Coin World*. Walk over it to pick it up.
- **Reflections Book Page**: set a unique *Page Id* (for example `GrayTowerPage`, `RedTowerPage`,
  `WhiteTowerPage`). When the book has *Pages For Book* distinct pages (3), it fires **OnBookComplete**, a
  "The book is whole" banner comes up, and `IsBookComplete()` returns true.
- **Reflections Key**: *Key Id* defaults to `RedTowerKey`.
- **Reflections Sealed Door**: *Required Key* defaults to `RedTowerKey`. Without the key it blocks the way and
  shows the locked message. With the key it slides up and stays open.

## For enemy and NPC code

```cpp
#include "Worlds/ReflectionsWorldLibrary.h"

UReflectionsWorldLibrary::AwardCoin(this, EReflectionsWorld::Red);                  // straight to the purse
UReflectionsWorldLibrary::DropCoin(this, HomeWorld, GetActorLocation());            // a coin to walk over
EReflectionsWorld Where = UReflectionsWorldLibrary::GetWorldAtLocation(this, GetActorLocation());
```

The quickest route needs no code. Add a **Reflections World Native** component to an NPC or enemy Blueprint.
It reads its home London from where it spawns (or set *Home World*). When its `ReflectionsHealthComponent`
reports death, it drops one coin of that London. A native that leaked through a rift into the wrong London still
drops its *home* coin. Gameplay code can also call `NotifyDefeated()` on it.

Blueprint events to hook UI, audio or quests into, on the **ReflectionsWorldJumpSubsystem** (game instance):
`OnWorldChanged(From, To)`, `OnCoinsChanged`, `OnPagesChanged`, `OnBookComplete`, `OnKeyAdded`, `OnMessage`.

## Magic

The jump does not keep its own magic bar. It finds the pawn's magic component by function name at runtime, so it
doesn't compile against the spell code: `GetMagic` / `GetMaxMagic` (or `MaxMagic` / `MaxMana`) / `SpendMagic(float)
-> bool`. The names are listed in the config. The spell driver (`UReflectionsSampleSpellDriver`) provides all
three, so a jump drains the real magic bar shown on the spell HUD. On a pawn with no spend function, the jump is
free and the HUD says the cost is "not drained yet".

## The test maps

`/Game/Worlds/Test/Lvl_WorldJumpTest` is a persistent level with the sun, sky, fog and a PlayerStart in Red. It
streams `Lvl_WorldJump_Gray`, `Lvl_WorldJump_Red` and `Lvl_WorldJump_White` at X = 0, 150000 and 300000. Each
London has its own anchor at its local origin, and all three follow the win path:

- **Red** (start): a White, a Red and a Gray coin by the start, enough for Red > White > Red > Gray. A rooftop sits
  where Gray's high spot lands. The tower has the sealed door, with a page and a White coin inside. The key is on a
  pedestal elsewhere in Red.
- **Gray**: stairs up to a 6 m high spot with a page and a Red coin. Rising from it lands on Red's rooftop.
- **White**: a tower sealed on all sides, with a page and a Red coin inside, so a jump from inside Red's tower is
  the only way in. The bleached grade makes it a wasteland.

Play the test map in PIE from any open level by typing `open /Game/Worlds/Test/Lvl_WorldJumpTest` in the console.
It uses `ReflectionsSampleGameMode`, the real hero with the spell driver. `/Game/Worlds/Test` is never cooked,
so keep real maps out of it.

## What it looks like

`Screenshots/` is a PIE run on the test maps, in this order:

1. Red start, three coins collected.
2. The jump into White: banner, and magic drained 80 on the spell HUD's mana bar.
3. A rise from White, refused because no London is above.
4. Back in Red.
5. Down in Gray, at the same spot each time.
6. The Gray high spot with its page.
7. The rise from it lands on the Red rooftop.
8. The Red tower door, sealed.
9. The door open after picking up the key.
10. Inside the sealed White tower: "The book is whole".

The test driver that produced them is a Python tick script run through the editor. Ask the world-jump session for
it if you want to re-run it.

## Files

| Path | What |
|---|---|
| `Worlds/ReflectionsWorldTypes.h` | `EReflectionsWorld`, layout and coin-rule enums, per-London info |
| `Worlds/ReflectionsWorldJumpConfig.*` | the data asset with every tunable |
| `Worlds/ReflectionsWorldAnchor.*` | the per-copy marker and bounds |
| `Worlds/ReflectionsWorldJumpSubsystem.*` | game-instance progress (coins, pages, keys, current London) and per-map anchors + auto-attach |
| `Worlds/ReflectionsWorldJumpComponent.*` | input, cost, safe landing, flash, coat tint, HUD driver (added to the player's pawn at runtime) |
| `Worlds/ReflectionsWorldHud.*` | the top-left panel, arrival banner and messages |
| `Worlds/ReflectionsWorldPickups.*` | coin, page and key pickups |
| `Worlds/ReflectionsSealedDoor.*` | the keyed door |
| `Worlds/ReflectionsWorldLibrary.*` | one-line calls and the World Native component |
| `/Game/Worlds/DA_WorldJumpConfig` | the config used in game |
| `/Game/Worlds/Input/` | `IA_WorldJumpUp`, `IA_WorldJumpDown`, `IMC_WorldJump` |
| `/Game/Worlds/Test/` | the three tinted test Londons and the persistent test map |
