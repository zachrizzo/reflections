# Melee animation set: swords and wands for NPCs and soldiers

Kimodo-generated, trimmed for snap, and retargeted to the MetaHuman bodies the crowd NPCs and soldiers use. Made
2026-11-14 for npc-unify (NPC combat) and soldier-squads (melee soldiers). The weapon props come from Codex.
Tool: `Tools/SpellCrafting/author_melee_kimodo.py`. Assets: `/Game/Combat/Melee/`.

## Which clip for which body

`UReflectionsNpcCombatComponent` and `AReflectionsSquad::ClipFor` play a clip on the MetaHuman body only when the
clip's skeleton is the body's skeleton. So every clip exists three times, one per body skeleton in use:

| Suffix | Skeleton | Bodies |
|---|---|---|
| `_IvenRook` | IvenRook `metahuman_base_skel` (also the hero's) | Iven Rook, White London `BP_WhiteLook_01`–`04` |
| `_BridgeGuard` | BridgeGuard `metahuman_base_skel` | Bridge Guard, Archive Apprentice, Festival Drummer, `BP_WhiteLook_05`–`06` |
| `_CoinClerk` | CoinClerk `metahuman_base_skel` | Coin Clerk |

List all three variants of a move and pick by skeleton, the way `ClipFor` already does. Each asset is named
`AS_Melee_<Move>_<Suffix>`, for example `AS_Melee_Sword_Stab_BridgeGuard`.

## The moves

All clips are 30 fps with root motion off: steps (the stab lunge, the hit-react stagger) play in place. "Strike" is
when the hit or contact lands, measured from the right hand's peak speed. For NPC combat, set `ImpactFraction` to the
fraction shown.

| Move | Length | Strike at | Fraction | Notes |
|---|---|---|---|---|
| `Sword_Idle` | 3.00 s loop | n/a | n/a | Low ready stance, sword forward, left hand up for balance. Seamless loop (seam 0 cm after train #7; was 3.9). |
| `Sword_Slash_LR` | 0.57 s | 0.27 s | 0.47 | Backhand: wind up across the left side, slash left → right at chest height. |
| `Sword_Slash_RL` | 0.57 s | 0.27 s | 0.47 | Forehand: draw back right, slash right → left across the body. |
| `Sword_Overhead` | 0.60 s | 0.30 s | 0.50 | Raise high, chop straight down. |
| `Sword_Stab` | 0.57 s | 0.27 s | 0.47 | Lunge step and straight thrust, arm fully extended. |
| `Sword_Block` | 0.63 s | 0.30 s | 0.47 | Sword up horizontally in front of the face; brace on contact. |
| `Sword_HitReact` | 0.47 s | 0.13 s | 0.29 | Upper body jolts back, half-step stagger, back to stance. |
| `Sword_Death` | 1.40 s | n/a | n/a | Fatal hit, stumble, knees buckle. It ends as the pelvis drops below 55 cm: switch to ragdoll there. |
| `Wand_Flick` | 0.57 s | 0.27 s | 0.47 | Sharp wrist-and-forearm flick forward: the cast release. |
| `Wand_Channel` | 3.00 s loop | n/a | n/a | Both arms forward, leaning into a channel. Seamless loop (seam 0 cm after train #7; was 20.9). Squads use it while casting. |

How they were made fast and weighty: each strike is cut from the Kimodo take as 0.35 s before the peak hand speed to
0.40 s after. It is then resampled 1.1–1.2× faster overall, with up to 0.9× extra speed in a 0.12 s window around the
strike. The wind-up stays readable and the hit snaps: right-hand peak speed is about 470 cm/s on the slowest slash and
900+ cm/s on the overhead, forehand and flick.

## Walker set: what NPC combat actually plays (from 14 Nov, 18:27)

Playing clips straight on the visible MetaHuman body crashed the shared editor at 16:16, and that route is now off in
code. npc-unify instead plays clips as DefaultSlot montages on the NPC's hidden walker pawn (`BP_SampleCMCClean2`,
mesh `SKM_UEFN_Mannequin`). The visible body follows the walker through its retarget blueprint. So npc-unify needs
one set of clips on the walker's skeleton, exactly `/Game/Characters/UEFN_Mannequin/Meshes/SK_UEFN_Mannequin`:

| Clip | Length | Strike | Notes |
|---|---|---|---|
| `AS_Melee_Sword_Slash_LR_Walker` | 0.57 s | 0.27 s (0.47) | |
| `AS_Melee_Sword_Slash_RL_Walker` | 0.57 s | 0.27 s (0.47) | left hand pushed clear on 17 frames |
| `AS_Melee_Sword_Stab_Walker` | 0.57 s | 0.27 s (0.47) | |
| `AS_Melee_Sword_Overhead_Walker` | 0.60 s | 0.30 s (0.50) | left hand pushed clear |
| `AS_Melee_Wand_Flick_Walker` | 0.57 s | 0.27 s (0.47) | both hands pushed clear |
| `AS_Melee_Sword_HitReact_Walker` | 0.47 s | jolt 0.13 s (0.29) | |
| `AS_Melee_Wand_Channel_Walker` | 3.00 s loop | n/a | seam 0 cm; both forearms were up to 7.7 cm inside the chest before the fix |
| `AS_Shock_Convulse_Walker` | 1.00 s loop | n/a | Electrify reaction: authored overlay, see below |
| `AS_React_Stagger_Walker` | 0.47 s | jolt 0.13 s | Explosion/Push survivor reaction. For now it holds the HitReact motion: the Kimodo stumble take (19:47) came out as a weak sway with the pelvis pinned, so it wasn't used. A real stumble needs a take that follows a backward transform track. |

- **How they're made:** `author_melee_kimodo.py walker [moves]` retargets the same trimmed Kimodo takes as the body
  clips with `/Game/Villain/Conversion/Rigs/RTG_Mannequin_to_UEFN`. It runs the two-bone IK hand fix against
  `PA_UEFN_Mannequin` (2 cm margin), and loop-blends the channel.
- **Settings:** root motion is off for every clip, and the strike timing is the same as in the body table.
- **Hand clearance:** every clip keeps both hands at least 2 cm clear of the walker's torso collision. The visible
  MetaHuman follows through a retarget, so it can differ by a few cm.

**Sword and shield soldiers** (the user's request: soldiers must hold sword and shield in their hands). Stages
`add_shield`, then `arm_shield` (twice: open, then arm), then `build_shield`:
- `AS_Melee_Shield_Guard_Idle_Walker`: a 3 s seamless loop. Guard stance with the shield forearm raised across the
  chest and the sword low by the right hip.
- `AS_Melee_Shield_March_Hold_Walker`: a 2 s seamless loop for an upper-body layer while walking or marching. The sword
  hangs at the right side and the shield forearm is carried across the stomach.

Kimodo keeps the pelvis in place, so neither clip walks by itself. Both get the closed grip.

**Shock loop** (`author_melee_kimodo.py shock`):
- **Pose:** frame 0 of `M_Neutral_Stand_Idle_Loop`, held, with an authored overlay in component space. The back arches
  and the head goes back; the shoulders shrug. The arms go rigid a little out from the sides, elbows locked half bent
  with the forearms forward, wrists cocked back and fingers splayed.
- **Motion:** a 14–16 Hz tremor plus three hard jolts a second. Every frequency is a whole number of cycles over the
  clip, so the loop seam is 0 cm.
- **Legs:** the legs and pelvis are untouched, so the feet stay planted (0 cm drift).
- **Use:** npc-unify loops it for the Electrify duration, then ragdolls.

## Hands vs. body (checked per frame on each body)

Each clip was measured against the body's own physics-asset torso (pelvis, spine, neck, head and the far clavicle),
with a 3 cm half-thickness for the hand and forearm. Where Kimodo put a hand or forearm closer than 2 cm, a two-bone
IK pass pushed it out (smoothed over time), and the clip was measured again.
- After the fix, every clip on every body keeps both hands and forearms at least 2.0 cm clear on every frame.
- The one exception is `Sword_Death`: the sword hand touches the torso on one frame at the very end (0.4–2.1 cm),
  where the ragdoll takes over.
- Before the fix, the free left hand grazed the chest in the forehand slash, overhead, block and flick. The channel
  had both hands up to 9 cm inside the chest, and the death had the sword hand up to 15 cm inside.

Not checked: the blade or wand itself against the body. There was no prop to test with yet.

## Weapon socket for Codex's props

Add a socket `weapon_r` on bone `hand_r` (the numbers are the same on all three body skeletons):
- Location (cm): X −3.8, Y −0.1, Z 0.1. That is the centre of the palm, halfway from the wrist to the middle knuckle.
- Rotation (degrees): Pitch 73.2, Yaw −142.3, Roll 0. The socket's +X then runs along the blade, out of the top of
  the fist on the thumb side, the direction a hammer-gripped sword points.

Model the sword and wand with the grip at the pivot and the blade or tip along +X. The wand uses the same socket. In
`Wand_Channel` the left hand comes alongside the right but doesn't hold the wand.

**Fingers.** Kimodo animates the body, not the fingers, so raw takes keep the fingers at the reference pose: open
hands. The walker clips get a closed grip baked in. `author_melee_kimodo.py` stage `fist <clip names>` applies it, and
`build_shield` applies it automatically.
- **What it closes around:** a round handle 3 cm across, a sword grip or the shield's strap handle.
- **Fingers:** each finger's segments lie tangent to the handle, using that finger's own bone lengths. Every segment
  touches it with no penetration, and each finger wraps 146–174°.
- **Thumb:** it comes over the top on the wrist side, with its tip beside the index fingertip.
- **Handle position:** the axis runs index-to-pinky, about 3 cm palm-side of the knuckles. All four fingers' axes
  agree within 0.4 cm.
- **Check:** `grip_check` measures it on the reference hands; `draw_grip_sheet.py` draws it from two angles
  (`grip_check.png`).
- **On the visible bodies:** the runtime retargeters (`RTG_Crowd_<Body>`) map every finger chain, thumb included,
  from the walker.
- **Not checked yet:** the grip on the visible MetaHuman bodies in PIE, and against the actual sword and shield
  meshes.

## Packaging

The clips are loaded by path from C++.
- npc-unify's archetype assets (in the always-cooked `/Game/NPC/Archetypes`) soft-reference the four sword strikes,
  so those cook by reference. As of train #7, Guard/Enemy/Hostile/Soldier get both slashes, the stab and the
  overhead; Infected/VillainHost get the forehand slash and the overhead. One clip is picked at random among those
  matching the body's skeleton, with the blow at 47%.
- The idle, block, hit-react, death and wand clips aren't referenced by anything yet. I've asked packaging to add
  `/Game/Combat/Melee` to `DirectoriesToAlwaysCook`.
- Keep the asset names and the three body suffixes stable; npc-unify builds the paths from them.

## Re-running

In `author_melee_kimodo.py`, the stages are:
1. `source`, then `arm` (sequence open, PIE idle, PIE lock held).
2. `status`.
3. `build [moves]`.
4. `anticlip [moves]`.
5. `loopblend`.
6. `check`, then `grip`.

The Kimodo takes live in `/Game/Combat/Melee/Source/LS_Melee_Kimodo`. The trimmed Kimodo-skeleton copies are in
`/Game/Combat/Melee/Source`.
