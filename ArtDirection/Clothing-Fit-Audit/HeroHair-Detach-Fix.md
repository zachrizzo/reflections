# Hero hair detaching while running: 14 November 2026

The bug: while the hero runs, the hair sometimes sits a few centimetres behind the head, and at low frame rates it leaves a bald head with the hair floating behind. It's intermittent: it shows up in some sessions and not others.

Image: `HeroHair_Sprint_BeforeAfter.png`. Both rows are real gameplay frames recorded while sprinting at 700 cm/s.

## Cause

- With the engine default `r.HairStrands.SwapType=2`, a skinned groom gets its world position from its own tick. During `UGroomComponent::TickComponent` it copies its Face mesh's component transform and uses that for the frame.
- The engine orders the groom after the Face, and the Face after the Body (its anim copies the Body pose). In a normal MetaHuman, the Body is the Character's own Mesh, which `ACharacter` orders after `CharacterMovement` (`Character.cpp`, `Mesh->PrimaryComponentTick.AddPrerequisite(CharacterMovement)`). So the hair always sees the moved head.
- Our hero's MetaHuman lives in a child actor: `BP_HeroSampleCleanTest` → `HeroVisual` (ChildActorComponent) → `BP_HeroTravelVisual`. Its Body, Face and Hair all tick in Pre Physics with no link to the pawn's `CharacterMovement`.
- Whether the hair ticks before or after the movement is therefore down to whatever order the tick manager picks. When the hair goes first, it uses last frame's head position, so it trails by speed × frame time: about 8 cm at 500 cm/s and 60 fps, and about 25 cm at 700 cm/s and 28 fps.
- That explains why it was intermittent and why it was worse when frames were slow (the old 13 ms cloth stall).

Proof (same PIE session, same 700 cm/s sprint, side camera parented to the pawn):

| Condition | Hair |
|---|---|
| As shipped (this session's order happened to be good) | On the head |
| Hair forced to tick before movement | Bald head, hair about 25 cm behind, in every frame |
| Hair in Post Update Work | On the head |

## Fix

- In `BP_HeroTravelVisual`, the `Hair` groom component's tick group is now **Post Update Work** (was Pre Physics).
- I also changed `Eyebrows`, `Fuzz`, `Eyelashes`, `Mustache` and `Beard` for consistency. They have no groom asset assigned, so nothing changes for them today.
- Nothing else changed: no C++, config, groom asset, binding, LOD or materials. The world-jump coat tint on `TravelDrape`/`TravelSleeves` is untouched.
- Post Update Work runs after movement, physics, timers and tickables, so the hair always gets the head transform the frame is rendered with, whatever order the Body and Face tick in.
- To revert, set those components' Tick Group back to Pre Physics.

## Verified

Checked in PIE on `Lvl_HeroSampleCrowd` with the saved Blueprint. At runtime the hair's tick group reads `TG_POST_UPDATE_WORK`. The hair stays on the head in every recorded frame of:

- idle
- walk at 200 cm/s
- sprint at 700 cm/s
- hard stop from a sprint
- turning while running
- a 4 m teleport mid-sprint, standing in for a world jump
- a sprint with `CharacterMovement` made to wait for the Body (the realistic bad order)
- the normal gameplay camera

I repeated the check with the same paused offscreen capture that first showed the bald frames (`HeroHair_PausedCaptures_Proof.png`):

- **Bad order forced:** both shots the NPCs didn't block show a bald head with the hair behind it.
- **Saved fix:** 24 captures, 12 at jog and 12 at sprint. The hair is on the head in every one where the hero isn't hidden by an NPC.

I re-checked on train #7 (15:15) with the same paused capture: 12 jog at 500 cm/s and 12 sprint at 700 cm/s. NPCs were hidden only for the instant of each paused capture. The hair is on the head in all 24 (`HeroHair_Train7_Captures.png`). At runtime the hair's tick group reads `TG_POST_UPDATE_WORK`, and only Hair ticks.

## Ruled out along the way

- Groom simulation: it's off.
- Hair LOD switching: LODSync keeps the hair on LOD 2, and forcing LOD 2↔3↔4 switches mid-jog didn't detach it.
- TSR or velocity output.
- Culling.
- The Face and Body LODs.
- Aim mode and spell casts.
- Scene captures. Nothing in the game's content uses one.

## Still open

- 14:29: I applied the same change to `BP_HeroSampleVisual`, the visual used by `BP_HeroSample`. Same six groom components, Pre Physics to Post Update Work, nothing else.
- 15:09, perf follow-up: the five empty groom slots (Beard, Mustache, Eyelashes, Eyebrows, Fuzz) in `BP_HeroTravelVisual` and `BP_HeroSampleVisual` still registered a tick. Their Start With Tick Enabled and Auto Activate are both now off. Turning off Start With Tick Enabled alone isn't enough: `UActorComponent::Activate()` calls `SetComponentTickEnabled(true)`, so an auto-activated component ticks anyway. In PIE on train #7 only Hair reports tick enabled. Hair is unchanged and still ticks. Nothing in the hero's code or content assigns them a groom at runtime. If someone gives one a groom later, they must turn its tick back on, or that groom will trail the head as before.
- `BP_HeroSampleVisual_PreCastBlend`, `BP_Hero` and the preview Blueprints still have Pre Physics grooms. None of them puts a groom in a child actor on a moving pawn.
- NPC MetaHumans that sit in child actors on moving pawns would have the same bug. The crowd-looks session has the exact change and is applying it to every NPC look that has grooms.
- The packaged build hasn't been checked yet; the change will be in the next cook.
