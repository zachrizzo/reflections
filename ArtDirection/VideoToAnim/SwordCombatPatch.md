# Sword combat test patch

A small, temporary way to try the sword animation library in PIE. The player draws a stand-in sword, swings it with the attack button, and sees what the blade hits. It is a test harness, not the melee system.

**Status (2026-11-23 00:35):** applied in main (uncommitted), built in two build trains, and tested in PIE on L_TestTown. After the fix below, every tested move plays to its end, root motion moves the capsule, and cuts hit a test post. `sword_combat_test.patch` (next to this file) was regenerated from the working tree after the fix, so `git apply -R` on it still undoes everything.

## In-game test results (PIE, L_TestTown)

**First test (23:40, original patch):**
- **Worked:** X / `Sword.Toggle` puts the sword on the Body's `hand_r`, the scan finds 192 moves (113 cuts, 26 combos, 40 footwork, 13 guards), moves start full body on `BP_HeroAnimation`, and putting the sword away restores walking.
- **Broke:** every move was cut off about 0.2 s before its end, with a pop and 0 hits. The tick checked `Montage_IsActive`, which turns false once a montage starts blending out, so the component treated the move as gone.

**The fix** is in `ReflectionsSwordTest.cpp` / `.h`:
- The tick now tracks the move with `GetInstanceForMontage`, which keeps the montage through its blend-out, and reads the hit position from that instance.
- Each move logs one line when it ends: its hits, length, capsule travel and the root motion applied.

**Second test (00:28, with the fix):** all 11 moves ended normally, and after each one walking and the cast-blend anim class came back.

| Move | Hits on the post | Capsule travel / root motion applied |
|---|---|---|
| 2H_Cut_Down_Shift_01 | 0 | 13 / 16 cm |
| 2H_Cut_AcrossRight_Advance_01 | 1 | 38 / 38 cm |
| 1H_Cut_DownLeft_01 | 1 | 0 / 0 |
| 2H_Cut_Up_01 | 1 | 0 / 0 |
| 2H_Combo3_Shift_01 (3 Hit notifies) | 0. The post stopped the capsule and the blade passed beside the post. | 22 / 92 cm |
| 1H_Cut_Down_Advance_01 | no post | 69 / 72 cm |
| 1H_Combo2_Advance_02 | no post | 59 / 62 cm |
| 2H_Step_Forward_01 | no post | 28 / 33 cm |
| 1H_Step_Back_01 | no post | 53 / 54 cm |
| 1H_Guard_Idle_01 | no post | 12 / 12 cm |
| 2H_Cut_DownLeft_Shift_01, at time dilation 0.4 | no post | 21 / 30 cm, ended normally |

**Not tested yet:**
- the keys by hand (X, LMB / Q / RT, F): the tests used console commands;
- `Sword.Damage`;
- hits on an NPC.

**Unexplained:** during one earlier run that took a `HighResShot` every 0.12 s, moves stopped advancing. It didn't happen again without the screenshots.

**Capturing PIE:** the one clip that works is `Review/SwordInGame_PlayerView.mp4`. It is 9.6 s from the player camera, recorded with the editor's `SceneCaptureToolset` `StartViewportRecording` on the PIE game viewport. Every attempt that used a camera of my own failed:
- the `HighResShot` frames showed an empty street;
- a `SceneCaptureComponent2D` gave black frames;
- `SetViewTarget` onto my camera gave black frames.

In each case the camera actor came from `ClothingFitLibrary.SpawnBenchActor` with a camera added by `AddComponentByClass`. That camera stayed at the world origin even when its component was moved, so to film from another angle, use a camera built some other way.

## What the patch changes

| File | Change |
|---|---|
| `Source/reflections/Hero/ReflectionsSwordTest.h` / `.cpp` | **New.** `UReflectionsSwordTestComponent`: the sword, the keys, playback, the hit trace, root motion, cvars and console commands. |
| `Source/reflections/Hero/ReflectionsSampleGameMode.cpp` | **+3 lines.** `SetPlayerDefaults` adds the component to the player pawn, next to the dig component's `EnsureOnPawn`. |

There are no Build.cs, Config or asset changes, and no new socket on `metahuman_base_skel`.

## How the Hero is wired (what the design is built on)

- `GlobalDefaultGameMode` is `ReflectionsSampleGameMode`, so the live pawn is `BP_HeroSampleCleanTest`. That is a Blueprint child of `BP_SampleCMCClean2` (a GASP CharacterMovement character), not `AReflectionsHeroCharacter`. Its own mesh, `CharacterMesh0`, runs the GASP locomotion.
- The visible Hero is the `HeroVisual` child actor (`BP_HeroTravelVisual`). Its `Body` skeletal mesh runs `ABP_HeroSampleCastBlend`, which retargets the pose from the parent mesh (`RTG_UEFN_to_Hero`) and blends `DefaultSlot` in **above spine_01 only**.
- The pawn's `HeroSpellDriver` has `bUseLayeredCasting = true`. I read this from the saved asset: the property tag carries the BoolTrue flag. So spells play on the upper body and the player can keep walking. `PlayCast`'s full-body branch only runs when layered casting is off. That branch swaps the Body to `BP_HeroAnimation` (a `UReflectionsHeroAnimInstance` whose `DefaultSlot` covers the whole body), stops movement, and puts `RetargetClass` back from the tick.

## Design

**One self-contained component**, added at runtime the way the dig component is. It finds the same Body the spell driver uses (`HeroVisual` → `Body`).

**Sword.** It creates a `UStaticMeshComponent` with `SM_Frostside_MirrorSword`. The mesh has no collision and is owned by the visual actor. It is attached to the **bone** `hand_r` with *snap to target, not scale*, at location (-2.97, 3.48, -5.07) and rotation Pitch 59.13 / Yaw -158.21 / Roll 128.29. The transform is two editable UPROPERTYs, `GripLocation` and `GripRotation`, and both apply live: edit them in the Details panel or with `Sword.Grip`.

**Playback.** Moves play as montages on `DefaultSlot` and keep the assets' own 0.12 s blend in and 0.2 s blend out. By default they play full body, using the same pattern as `PlayCast`'s non-layered path:
1. Swap the Body to `BP_HeroAnimation`.
2. `StopMovementImmediately` and `DisableMovement`.
3. When the montage ends, set the anim class and `MOVE_Walking` back from the component tick, never from inside the anim update.

Other details:
- Moves started back to back reuse the swapped instance, so the class doesn't thrash.
- The hero turns to the camera's heading as a move starts.
- `Sword.FullBody 0` plays the move on the current layered anim BP instead: upper body only, and the legs keep walking.

**Why not `CastExternal`.** It fits a spell, not a sword move:
- `PlayCast` retimes every clip. It starts late and plays up to 1.9× so the release lands 0.28 s after the press.
- `FollowThrough` stops the montage 0.3 s after the first release. That cuts recovery short and drops a combo's later hits.
- It has one release per cast, not a trace window.
- On the live pawn it is upper-body only.

The patch keeps the driver's **input path** instead. While the sword is out, the driver's `PrimaryCastOverride` routes LMB / Q / RT to the sword, and holding the button repeats. That reuses the driver's HUD mouse-mode guard and gamepad trigger, and spells stay untouched while the sword is put away. The override is chained: any previous override still runs while the sword is away, and the old one is put back at EndPlay.

**Library discovery.** Asset names are not final, so the component hard-codes none:
- Each time the sword is drawn, and on `Sword.List`, it scans `/Game/Animation/SwordLibrary/Montages` and its subfolders through the asset registry.
- Folders starting with `_` (the `_Review` rejects) are skipped.
- If no montages exist yet, it falls back to the clips in `/Game/Animation/SwordLibrary/Hero` and plays them as `DefaultSlot` dynamic montages with the same blends.
- The kind of each move (Cut, Thrust, Combo, Footwork, Guard) comes from its folder, or failing that from its name.
- Assets nothing references won't cook. That's fine for PIE. A packaged test would need the folder added to *Additional Asset Directories to Cook*.

**Hit test.** Hit times are read from the `UReflectionsSpellReleaseNotify` events on the Hit track: the montage's own, or else its clips' notifies mapped onto montage time. Every Hit notify in a combo counts. For each notify, the component works on a window from 0.08 s before to 0.06 s after (`HitWindowBefore` / `HitWindowAfter`). Each frame in that window it:
- sweeps the blade from guard to tip (+X 22 → 86 cm, radius 4 cm);
- sweeps the path each of 5 points along the blade travelled since the last frame;
- looks for Pawn, WorldDynamic and PhysicsBody objects (the same set the spell area queries use), ignoring the hero and its child actor;
- logs each actor once per notify to `LogSwordTest`, draws the blade (yellow, or red on contact), and puts a red sphere and label at the hit.

`Sword.Damage <n>` (default 0) also applies `UGameplayStatics::ApplyPointDamage`. That is the existing combat hook: spells damage through the same call, and `UReflectionsHealthComponent` turns it into health loss and death. A real melee system would also broadcast `UReflectionsSpellEventSubsystem::OnSpellHit` with `Reaction = Hit` so NPCs flinch, but that struct is keyed by `EHeroSpell`, so it needs a small extension first.

## Keys

| Input | Action |
|---|---|
| **X** | Draw / put away the sword |
| **LMB / Q / RT** (sword out) | Next Cut or Thrust. Hold to chain. |
| **F** (sword out) | Next Combo |
| LMB / Q / RT (sword away) | Spells, as before |

Console:
- `Sword.Play [filter]` plays the next move whose kind or name contains the filter: `Footwork`, `Guard`, `Advance`, `2H_Cut`, and so on. Repeat it to cycle.
- `Sword.List` rescans and logs every move with its length, root motion and hit times.
- `Sword.Grip [x y z pitch yaw roll]` shows or sets the grip.
- `Sword.Toggle` draws or puts away the sword, and adds the component first if the pawn lacks it, so it works in other game modes.

**What I checked for collisions:**
- **C++:** every `EKeys::`, `MapKey` and `BindKey` in `Source/`.
  - Spell driver: LMB, RT, Q, Tab (with Shift), RB, LB, 1–4, N, F8, left-stick click.
  - Dig: G, and H while the world has a dig terrain.
  - HUD mouse mode: Right Alt.
  - Aim: polls RMB and LT.
  - `AReflectionsHeroCharacter`'s legacy binds: Shift, Left Alt, Left Ctrl, V, 1–4.
- **`IMC_Sandbox` name table:** W A S D, Space, Left Shift, Left Ctrl, C, J, M, R, 1, 2, 3, LMB, RMB, MMB, D-pad and face buttons. `IMC_Default` and `IMC_MouseLook` have only movement, look and jump.
- **Key events in Blueprints:** `BP_SampleCMCClean2`, `BP_SampleControllerClean`, `PC_Sandbox`, `BP_Player`, `SandboxCharacter_*` and `AC_SmartObjectAnimation` have only D-pad up/down and the mouse wheel. The map files and the Developers, Combat, NpcDialogue and Misc folders have no input events.
- **`DefaultInput.ini`:** no legacy action mappings; Tilde opens the console.

X and F appear in none of these.

**What I couldn't verify:**
- Widget `OnKeyDown` handlers in folders I didn't scan, such as Fab and LanthorneAssets.
- Mapping contexts that other sessions add at runtime in work that hasn't landed yet.
- Which `IMC_Sandbox` action owns which key: I only have the set of keys.
- Gamepad: the patch adds no gamepad bindings beyond the driver's RT.

## Root motion: does a montage on the Body move the capsule?

**No.** I checked this against the UE 5.9 engine source:

- CharacterMovement takes animation root motion only from the character's own mesh. `ACharacter::IsPlayingRootMotion()` checks `Mesh`, and `UCharacterMovementComponent` calls `CharacterMesh->ConsumeRootMotion()`. Here that mesh is the GASP `CharacterMesh0`, not the Hero Body in the child actor.
- A montage with root motion locks the root bone in the pose it plays (`AnimInstanceProxy.cpp`: the extract context's root-motion flag is `Montage->HasRootMotion() && RootMotionMode != NoRootMotionExtraction`). The motion builds up in the Body's anim instance until someone calls `ConsumeRootMotion`, and nobody does. So a travelling move plays **in place**: the feet step but the hero stays put.
- With the live layered setup it's moot anyway: `DefaultSlot` only drives the bones above `spine_01`.

**What the patch does about it:**
- Moves play full body with movement off, like `PlayCast`.
- For a montage with root motion, each tick the component calls `Body->ConsumeRootMotion()` and converts the result with `Body->ConvertLocalRootMotionToWorld`. It applies the horizontal move and the yaw to the capsule with `SafeMoveUpdatedComponent(sweep)`.
- `Sword.RootMotion 0` plays travelling moves in place, for comparison. In-place moves (no travel suffix) need nothing.

**Limits.** With `MOVE_None` there is no gravity and no floor following during the move. The sweep stops at walls, vertical root motion is dropped, and the hero settles onto the ground when walking resumes. On slopes and stairs a long advance may hover or dip slightly.

**The proper fix, later:** hand the Body's root motion to CharacterMovement while it is in `MOVE_Walking`, through a root motion source or by filling its root motion params before its tick. The other option is to play sword moves on a mesh the CMC owns.

## Turning it off

| CVar | Default | Effect |
|---|---|---|
| `Sword.Test` | 1 (0 in Shipping) | 0: new pawns get no component, X / F / the console commands do nothing, and a drawn sword is put away |
| `Sword.FullBody` | 1 | 0: upper body on the layered BP, legs walk, no root motion |
| `Sword.RootMotion` | 1 | 0: travelling moves play in place |
| `Sword.DrawHits` | 1 | 0: no debug drawing |
| `Sword.Damage` | 0 | > 0: point damage per hit |

To remove it completely, run `git apply -R ArtDirection/VideoToAnim/sword_combat_test.patch` with the editor closed.

## Applying and building (build train rules)

1. Apply it only in a train window: editor closed, no other session compiling, through the orchestrated build if one is running. Run `git apply ArtDirection/VideoToAnim/sword_combat_test.patch` from the repo root.
2. It adds a new `UCLASS`, so Live Coding won't do. Build `reflectionsEditor` (Development Editor, Win64) with UBT and let the usual READY check pass.
3. No Build.cs change should be needed. `IAssetRegistry::Get()` and `GetAssets` are inline or virtual through a CoreUObject singleton, and Engine lists AssetRegistry as a public dependency. If the include or link fails anyway, add `"AssetRegistry"` to `PrivateDependencyModuleNames`.
4. If `ReflectionsSampleGameMode.cpp` has moved on by then, the 3-line hunk may not apply. Use `git apply --3way`, or add the include and the `EnsureOnPawn` line by hand. The two new files can't conflict.

## Testing in PIE

1. Make sure the library has montages under `/Game/Animation/SwordLibrary/Montages`, or at least clips under `Hero/`. Open the test map (`L_TestTown` or the current main map) and check that World Settings doesn't override the game mode.
2. Claim `PIE_LOCK` from bash on your turn, then start PIE.
3. Press **X**. The sword appears in the right fist and the screen shows how many cuts, thrusts and combos were found. If it shows 0, run `Sword.List`; the asset registry may still have been scanning.
4. Check the grip at idle. Tune it live with `Sword.Grip` or in the Details panel (pawn → `SwordTest` → Grip Location / Rotation). Copy the final numbers into the constructor.
5. Press **LMB**. The hero faces the camera and plays a cut full body, and can't move until the move ends. A yellow fan shows the traced blade around the hit frame, and the swing sound plays about 0.15 s before it. Hold LMB to chain moves. Walk afterwards to confirm movement comes back.
6. Put a target in reach, such as an `AReflectionsSpellTarget` or an NPC. On a hit you should see a red sphere and label, and a `LogSwordTest: <move> hit <actor> ...` line. With `Sword.Damage 10`, the target's health drops.
7. Press **F** for combos. Each Hit notify opens its own window, so a target can be hit once per strike.
8. Run `Sword.Play Footwork` and `Sword.Play Advance`. The capsule should travel about as far as the feet do, with no drift or snap at the end. Compare with `Sword.RootMotion 0`.
9. Run `Sword.FullBody 0` and strike while walking: you should get an upper-body swing with the legs still walking.
10. Press **X** again. The sword hides, and LMB, held repeat, RMB aim and Tab cycling all behave as before. G and H dig still work.
11. Run `Sword.Test 0`. The sword hides and X does nothing.
12. Stop PIE. Only do this while `PIE_LOCK` is yours.

## What to check after compiling

- UHT and the compiler accept the header's plain `enum class` and struct, and there are no warnings in `ReflectionsSwordTest.cpp`.
- The `Sword test: N moves under ...` log line matches the library and leaves out `_Review`.
- The Body anim-class swap works both ways with no T-pose frame:
  - the clothing followers still follow;
  - `BP_HeroTravelVisual`'s `OnAnimInitialized` logic doesn't misbehave;
  - the retarget picks up again after the restore.
- Movement comes back after a move ends, after X mid-swing, and after `Sword.Test 0` mid-swing. A hero killed mid-swing stays down until respawn; the restore checks `IsDefeated`.
- The yellow windows line up with the visible contact. If not, tune `HitWindowBefore` / `After`.
- Travelling moves cover their authored distance, and walls stop them.

## Known risks

- **Shared machine and build train.** Source edits need the editor closed and an orchestrated build. Other sessions' in-flight `Source/` work could collide with the game mode hunk; the digging work already edited that file. `ReflectionsHeroCharacter.*` is not touched.
- **The anim-class swap is the less-used path.** The live pawn casts layered, so `PlayCast`'s swap hasn't been exercised there lately. Expect:
  - a small pop from the retargeted pose into `BP_HeroAnimation`'s idle;
  - a re-initialisation cost when the retarget BP comes back.
  - Holding RMB to aim would interrupt a move, so moves are refused while aiming.
- **`PrimaryCastOverride` is a single slot.** The patch chains whatever was there and restores it. A system that installs its own override after this one would replace it.
- **Root motion runs with movement off.** See the limits above. Don't press Space mid-move: GASP traversal can change the movement mode.
- **X and F may become taken by later work.** Re-grep before applying if much time has passed.
- **Packaged non-Shipping builds** have it on by default. Revert the patch, or set `Sword.Test=0`, before any jam build.
- **The sword is a stand-in.** On two-handed moves the left hand is only as good as the bake.
