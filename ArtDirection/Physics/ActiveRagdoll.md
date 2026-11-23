# Active ragdoll prototype ("GTA-style physics") on a MetaHuman

Prototype date: 2026-11-22. Engine: UE 5.9, Physics Control plugin. Character: `BP_Hero` (unchanged). Map: `/Game/Maps/TestTown/L_TestTown`, market square (700, 0).

## Verdict

**Recommendation: yes, design it into the NPC rebuild as a "reaction layer" that is dormant by default.**

UE 5.9's stock Physics Control plugin gets about two thirds of the GTA IV/V look on a MetaHuman:
- partial hits where the struck limb and the spine give way and the body stays standing;
- staggers;
- being knocked off the feet with arms out;
- a limp body;
- a get-up.

It does this with no plugins outside the engine. In the editor it costs about 0.15 ms of game thread and 0.3 to 0.4 ms of physics worker time per character, and only while a character is actually reacting.

> **Update, 2026-11-22 afternoon: the standing slump is found and fixed, and physics is now off until a hit.**
>
> **The slump.** In the first version, normal animations did not play cleanly while the upper body simulated.
> - The upper body sat hunched with the chin on the chest.
> - The head was 15 to 20 cm low and turned 40 to 55°, the chest about 9 cm low, the hands 7 to 12 cm low.
> - Image: `ArtDirection/Physics/ActiveRagdoll_StandingSlump.png`.
>
> It was not the head's weight. Three separate faults stacked up ("Problems found", items 9 to 11):
> 1. **The physics asset was built for a smaller body.**
>    - `PHYS_MHC_Hero`'s joints sit at the shared base skeleton's bone lengths: pelvis to spine_02 is 6.2 cm in the asset but 12.6 cm on the Hero's mesh; spine_04 to neck is 25.7 cm against 31.7 cm.
>    - Locked joints squash the simulated spine and arms to the short lengths on the first physics frame.
>    - **All 15 cast body meshes checked have the same fault**, 4 to 10 cm per joint, so ordinary death ragdolls compress too.
>    - Fixed in our copy with `Tools/ActiveRagdoll/snap_frames.py`. It moves each joint to the mesh's own proportions and keeps MetaHuman's authored angles.
> 2. **The neck and head controls had zero strength.**
>    - Zeroing the world-space control named `head` also zeroed the limb set named `Head`, because Unreal names ignore case and per-control setters also apply to sets with the same name by default.
>    - Fixed by passing `apply_to_sets_with_name=False`.
> 3. **Gravity sag on the neck and shoulders.**
>    - Fixed with "muscle tone": while standing, a limb feels gravity only in proportion to how weakened it is.
>    - The shoulder, neck and wrist limits were also widened to fit our animations (`widen_limits.py`).
>
> **Result: the standing pose now matches the animation.** Before/after image: `ArtDirection/Physics/ActiveRagdoll_SlumpFixed.png`.
>
> | Pose | Before | After |
> |---|---|---|
> | Idle: head | 18 cm, 50° | 1.6 cm, 0.6° |
> | Idle: spine | 9 cm | 1.6 cm |
> | Idle: hands | 9 to 11 cm | 2 cm |
>
> Fast arm motion (walking, casting) still lags 20 to 30 cm while physics is on. Stronger controls, freed joint limits and switching body collision off do not change this.
>
> **New design: physics only when hit.** The Hero now plays pure animation by default (DORMANT, exact to 0.00 cm, control component tick off).
> - **What wakes it:** a hit, a stagger, a knockdown, or a prop contact harder than normal motion. A dormant body still registers collisions.
> - **During the reaction:** physics runs at full strength.
> - **Afterwards:** it blends back to the animation as the struck limbs regain strength (about 1 s), then goes dormant again.
> - **Effect on the arm lag:** it only shows during that second and fades out with it.
>
> Video, real time: `Saved/ActiveRagdollTest/ActiveRagdoll_PhysicsOnlyWhenHit.mp4`, 27 s, with a "PHYSICS ON" / "animation only" label. Key frames: `ArtDirection/Physics/ActiveRagdoll_PhysicsOnlyWhenHit_KeyFrames.png`. Raw numbers: `ArtDirection/Physics/DriftTest/`.
>
> **Get-ups are animation too** (after review). Physics now runs only while a force acts: from the impact until he lies still on the ground.
> - **The get-up:** a 0.45 s visual blend from the lying pose into the get-up clip (the bodies stay limp, nothing is pulled), then the whole get-up plays as pure animation (`GETUP_ANIM`: all kinematic, control tick off).
> - **New force mid get-up wakes physics from that pose:**
>   - a light hit: the upper body reacts while the legs keep getting up;
>   - a stagger-strength hit or prop: he collapses back down, since there is no balance yet. The legs hold the frozen get-up pose, soft, with a smaller kick. The standing knockdown's straight stiff legs flipped a kneeling body over.
> - Video: `Saved/ActiveRagdollTest/ActiveRagdoll_GetUpIsAnimation.mp4`, 17 s, real time, labelled "PHYSICS ON" / "blending into the get-up" / "animation only". Key frames: `ArtDirection/Physics/ActiveRagdoll_GetUpIsAnimation_KeyFrames.png`.

What it does not do is Euphoria's real trick: a balance controller that decides on its own to take a corrective step or grab something. Here, steps and get-ups come from animation clips that physics blends into and out of. That is how most non-Rockstar games do it, and it reads well in the video. Expect occasional pops and foot slides at the hand-offs.

## What to look at

| What | Where |
|---|---|
| **Current video, 27 s, real time:** physics only when hit, fixed asset | `Saved/ActiveRagdollTest/ActiveRagdoll_PhysicsOnlyWhenHit.mp4` (recorded at time dilation 0.25, re-timed) |
| Current key frames | `ArtDirection/Physics/ActiveRagdoll_PhysicsOnlyWhenHit_KeyFrames.png` |
| **Get-up video, 17 s, real time:** get-up as animation, hit and shove mid get-up | `Saved/ActiveRagdollTest/ActiveRagdoll_GetUpIsAnimation.mp4`; key frames `ArtDirection/Physics/ActiveRagdoll_GetUpIsAnimation_KeyFrames.png` |
| First demo video, 29 s (before the slump fix; physics always on while standing) | `Saved/ActiveRagdollTest/ActiveRagdoll_Demo.mp4` (re-timed from a 0.354x recording, see "Recording" below) |
| First demo key frames | `ArtDirection/Physics/ActiveRagdoll_KeyFrames.png` |
| Code (prototype, editor Python) | `Tools/ActiveRagdoll/ar_proto.py`, plus small driver scripts in the same folder |
| Assets (all new, only under this folder) | `/Game/Physics/ActiveRagdollTest/` |
| Raw recordings | `Saved/Recordings/Viewport_20261122-00*.mp4` (the editor prunes old ones to a disk budget) |

The demo, in order:
1. Partial hits:
   - chest hit from the front;
   - right upper arm hit from the side;
   - an 8 kg crate dropped on the head (a real collision; the contact picks the reaction).
2. Two staggers:
   - a strong hit from the front: real steps back;
   - a shove from behind: real steps forward.
3. A 30 kg crate thrown at 9.5 m/s hits the hips:
   - knocked off his feet, arms fly up;
   - lands, goes limp;
   - waits until still, then gets up from his back.
4. A shove from behind:
   - pitches forward, legs straight, arms reach for the ground;
   - lies limp face down;
   - gets up from the front.

## Setup

### Plugin
- `PhysicsControl` (engine plugin, not beta or experimental) is already loaded in this project. It comes in as a dependency of `ControlRigPhysics`, which is pulled in by AnimatorKit and ControlRigModules (both enabled by default) and by the enabled `AnimGenOffline` (Kimodo).
- **`reflections.uproject` was not changed.**
- For production, add an explicit `{"Name": "PhysicsControl", "Enabled": true}` entry. Then a packaged build doesn't depend on another plugin keeping it alive.

### How the prototype is wired
Nothing is placed in the map, and `BP_Hero` itself is unchanged. During Simulate, `ar_proto.setup()` does the following:
1. **Spawn the Hero.** It spawns a `BP_Hero` into the play world. Python hides `BeginDeferredActorSpawnFromClass`, so it is called through `call_method` on the `GameplayStatics` class default object.
2. **Set up the Body mesh component:**
   - physics asset override to `PHYS_Hero_ActiveRagdoll`;
   - single-node animation (`AS_Hero_Idle`);
   - collision `PhysicsBody`, blocking everything except Pawn and Camera;
   - `PhysicsTransformUpdateMode = ComponentTransformIsKinematic`, so a simulated pelvis does not drag the component off the actor.
3. **Spawn a control actor.** It spawns an `APhysicsControlActor` (it ships with the plugin) next to the Hero. Its `PhysicsControlComponent` drives the Hero's Body from outside, so no Blueprint edits are needed.
4. **Create the controls.** `CreateControlsAndBodyModifiersFromLimbBones` runs with six limbs: ArmLeft (`clavicle_l`), ArmRight (`clavicle_r`), Head (`neck_01`), LegLeft (`thigh_l`), LegRight (`thigh_r`) and Spine (`spine_01` plus its parent, `pelvis`). The result:
   - 22 parent-space controls (the "muscles": each drives a child body's rotation toward the animation, relative to its parent);
   - 21 world-space controls, created but left at strength 0;
   - 21 body modifiers, one per body (kinematic or simulated, blend weight, gravity).
   The control and modifier sets are named after the limbs.
5. **Tick.** A slate post-tick callback runs the state machine below. Crate hits arrive through `OnComponentHit` on the Body.

### State machine

| State | Bodies | Controls | Animation |
|---|---|---|---|
| DORMANT (default) | All kinematic, on the animated pose | All disabled; control component tick off | Whatever is playing |
| STAND (only while reacting) | Pelvis and legs kinematic; spine, head and arms simulated; upper-body gravity scaled by weakness | Parent-space at stand strength | Whatever was playing (hits keep the walk going) |
| Partial hit (in STAND) | Same | Struck limb loses 90 %, spine 80 %, then recovers at 1.1 per second; velocity kick of 900 cm/s on the bone, 45 % of that on its parent | Same |
| STAGGER | Same | Upper body loses 92 %, spine 85 %, then recovers at 1.0 per second; kick of 380 cm/s | GASP `Run_Stop_B` or `Run_Stop_F`, started part-way (see below) |
| FALL | All simulated | Legs 1.8x stand strength, targeting their straight bind pose and softening to 0.35x over 0.6 s; arms 1.3x and spine 1.0x on the brace clip; upper-body kick of 380 cm/s | GASP `reach_back` or `reach_forward` |
| DOWN (limp) | All simulated | Everything ramps to 4 % with extra damping 2.0 over 0.35 s, starting when the pelvis is under 45 cm or 1.3 s after the hit | Held |
| GETUP (0.45 s) | Still simulated and limp, so nothing is pulled; only the visible blend moves from the lying pose to the clip | Limp | GASP `getup_stand_B` or `getup_stand_F` at 1.25x |
| GETUP_ANIM | All kinematic: pure animation | All disabled; control tick off | The get-up clip, then idle at 2.6 s. A hit wakes physics (STAND, the legs keep getting up); a knockdown or stagger-strength hit collapses him from the frozen get-up pose with soft legs |

How the stagger and the get-up work:
- **Stagger.** The run-stop clips carry root motion that ends at the origin. The stagger starts the clip part-way:
  - the backward clip at 0.45 s, about 0.9 m from the end;
  - the forward clip at 0.62 s, played at 0.75x.

  It moves the actor back by the clip's root offset first. The body stays put, then the clip's own root motion walks it back onto the actor. The feet take real steps and nothing slides.
- **Get-up:**
  - back or front comes from the chest normal: (right hip minus left hip) crossed with (head minus pelvis); z > 0 means on the back;
  - the actor is placed so the clip's first-frame pelvis and pelvis-to-head direction land on the ragdoll's. That first-frame pose is measured with `AnimationLibrary.get_bone_pose_for_time`;
  - the physics blend weight fades from 1 to 0 over 0.45 s while the controls pull the ragdoll toward the clip at 3x;
  - legs and pelvis go kinematic;
  - upper-body physics fades back in over 0.3 s.

### Physics asset

`PHYS_Hero_ActiveRagdoll` is a copy of `PHYS_MHC_Hero`; the shared asset was not edited.

What the MetaHuman asset has, and what the copy changes:
- **21 bodies:**
  - pelvis, spine_02, spine_04, neck_01, head;
  - clavicle, upperarm, lowerarm, hand on each side;
  - thigh, calf, foot, ball on each side.
  - There are no spine_01, spine_03 or spine_05 bodies, so the torso bends in only two places. Feet have a mass scale of 0.2.
- **Every joint has an angular motor on, pulling toward the reference A-pose.** These are SLERP position drives, stiffness 1000 to 10000, in the default instance and in both constraint profiles (`Ragdoll`, `RollDownSlope`). They fight Physics Control's own controls, and they make a plain ragdoll "action-figure" stiff.
  - **The copy turns them off on all 22 constraints** (position and velocity drives off, stiffness and damping 0).
  - This was done through `ObjectToolset.SetProperties` on the `PhysicsConstraintTemplate` sub-objects; Python can't reach constraint templates directly.
- **Two extra constraints, calf to pelvis on each side.** Linear is free, swing is limited to 90 degrees and collision is off between the pair. They close a loop around the thigh and could fight deep kneels. Left as is in the prototype.
- **Body angular damping is 1.0** on every body. Left as is: it reads as muscle tone in the limp state.
- **No physical-animation profiles.** None are needed: Physics Control replaces the old Physical Animation component.

### Animations

All in `/Game/Physics/ActiveRagdollTest/Anims`, retargeted onto the Hero skeleton (the IvenRook `metahuman_base_skel`):

| Clip | Source | Use |
|---|---|---|
| `AS_Hero_getup_stand_B`, `AS_Hero_getup_stand_F` | GASP `M_ragdoll_getup_stand_B/F` | Get-up from back and front (5 s, played at 1.25x) |
| `AS_Hero_reach_back`, `AS_Hero_reach_forward`, `AS_Hero_reach_down` | GASP `M_ragdoll_reach_*` | Brace targets for the arms while falling |
| `AS_Hero_Run_Stop_B_Lfoot`, `AS_Hero_Run_Stop_F_Lfoot`, `AS_Hero_Run_Start_B_Lfoot` | GASP run starts and stops (already in this project) | Stagger steps |
| `AS_Hero_HitReact_*` (3) | UE5 Mannequin rifle hit reactions (`/Game/Characters/Mannequins/Anims/Rifle/HitReact`) | Tried for the stagger. Unused: rifle arms, no steps |

Where they came from:
- **GASP ragdoll clips.** The `M_ragdoll_*` source clips were in this repo until the Test Town reset deleted them. I copied 5 of them from the user's `action_fighting_UE59` project into `/Game/Physics/ActiveRagdollTest/GASP/`. That is a local copy, not a download. They are Epic's Game Animation Sample content, usable in UE projects.
- **Retargeting.** UEFN to Hero clips use `RTG_UEFN_to_Hero`; the Mannequin hit reactions use `RTG_MannequinToHero`.
- **Kimodo.** I asked the kimodo-sword session for two text-to-motion stagger clips. Its auto mode blocked a request that came from another session, and it is waiting for the user's yes. The GASP run-stop clips did the job instead.

### Test triggers

All of these are in `ar_proto.py`:
- `hit(bone, direction, strength)`, `stagger(...)` and `knockdown(...)`: scripted impulses at a bone.
- `drop(target, height, mass, speed, from_dir)`: spawns a physics crate (`/Engine/BasicShapes/Cube`). It falls onto a bone, or flies at one when `speed` is given.
  - The Body's `OnComponentHit` turns the collision into a reaction. It classifies by the crate's momentum: under 11,000 kg·cm/s is a hit, under 20,000 is a stagger, above that a knockdown.
  - Normal impulse was unreliable for this. The 30 kg crate's contact reported only 3,500 to 13,000 because the impulse is split across light bodies.
- `schedule([(delay, fn, kwargs), ...])`: a timed sequence, used for the demo (`ev_final.py`).
- `dormant(True/False)`: the default state. Every body is kinematic and every control is disabled; the control component's tick switches off 0.1 s later. Reactions call `wake()` themselves, and `on_body_hit` wakes the body for a prop contact above `imp_hit`. After a reaction, the envelope (`envelope_full_weak`, `fadeout`) blends physics back out and returns here.

## Tuning values

Parent-space controls run in acceleration mode, so strength works like a frequency in Hz and doesn't depend on mass. Damping ratio is 1.0 (critical).

| Parameter | Value |
|---|---|
| Stand strength | Spine 9, Head 8, Arms 7, Legs 10 |
| Partial hit | Limb −90 %, spine −80 %; recovers at 1.1/s; kick 900 cm/s on the bone, 45 % on its parent |
| Stagger | Upper body −92 %, spine −85 %; recovers at 1.0/s; kick 380 cm/s on spine_04 plus 50 % on spine_02; clip start 0.45 s (back) or 0.62 s at 0.75x (forward); hand-over to idle at 1.7 s (back) or 1.9 s (forward) clip time |
| Fall | Legs 1.8x on the bind pose, softening to 0.35x over 0.6 s; arms 1.3x on the brace clip; head 0.6x; kick 380 cm/s on head/neck/chest (1.0), clavicles (0.9), upper arms (0.8), spine_02 (0.6), pelvis (0.25) |
| Limp | 4 % strength, extra damping 2.0, 0.35 s ramp; starts when the pelvis is below 45 cm, or at 1.3 s at the latest |
| Down | Gets up after 0.7 s with pelvis speed under 22 cm/s (minimum 1.2 s down, maximum 4 s) |
| Get-up | Physics fades out over 0.45 s with a 3x pull, clip at 1.25x, upper body fades back in over 0.3 s, idle after 2.6 s |
| Control component | Teleport distance threshold 0; debug drawing off; `bAttemptToRecreateDisabledControls` off (see "Problems found") |

## What looks good

- **Knockdowns are the strongest part.** A body hit at the hips by a thrown crate is lifted, rotates around the impact, throws its arms up and lands in a different heap every time. Toppling forward with straight legs and hands reaching down also reads well.
- **Get-ups land in the right place and face the right way** for both back and front. The physics-to-clip fade hides the start pose not matching exactly.
- **Partial hits look physical.** Head and shoulder sway, the arm swings and the spine bends, then the body recovers. Crates landing on the head produce a reaction that matches where they hit, with no scripting.
- **Staggers with real steps.** Because the steps come from GASP's run-stop clips, the feet plant without sliding.

## What doesn't

- **No balance or stepping intelligence.** The stagger is a clip with physics on top, not a body catching itself. Strong hits always pick the same two clips: back or forward. Sideways hits fall back to those two.
- **Hand-offs pop:**
  - stagger end to idle;
  - get-up end to idle;
  - the stagger start: the legs jump from the idle stance into the clip mid-stride, hidden by the impact.

  Single-node animation has no blending. Production needs an AnimBP with inertialization, or Pose Snapshot plus montages.
- **Partial hits are subtle from a distance.** They read clearly at 2 to 3 m and weakly from across a street. Combat would want the hit sound, a short additive flinch, or a stronger kick.
- **Cloth on the Hero's coat tails** (`SK_HeroTails`) whips on big moves and flares for a frame when the actor is re-placed at get-up start, even after `ForceClothNextUpdateTeleportAndReset` for 3 frames. Fitted clothing (house style) will look calmer.
- **The coarse spine** (two bodies) makes the torso fold like two blocks when it hits the ground.
- **The get-up always faces the way the clip ends,** so after a backward fall he ends up facing roughly opposite his old heading.
- **No ground awareness.** Get-ups don't check for walls, slopes or stairs, and a knockdown next to a wall would get up inside it.

## Cost

Measured with `PerfToolset.StatsToolset.GetFrameTree`: median of 30 frames, one Hero, Simulate in the Development editor. Machine: Ryzen 7 9700X, RTX 5080. "Solver" is `FPhysicsSolverAdvanceTask` for the whole scene, which runs on a worker thread. The game thread waits on it only when it runs long.

| State | Control component tick (game thread) | Body anim tick (game thread) | Physics solver (worker) | Solver above "no Hero" |
|---|---|---|---|---|
| No Hero (scene baseline) | n/a | n/a | 0.17 ms | 0 |
| Dormant: all kinematic, controls disabled | 0.11 ms | 0.15 ms | 0.26 ms | +0.09 ms |
| All kinematic, controls enabled | 0.14 ms | 0.13 ms | 0.25 ms | +0.08 ms |
| **Standing, upper body simulated** | **0.14 ms** | 0.14 ms | **0.48 to 0.51 ms** | **+0.31 to 0.34 ms** |
| Full ragdoll, limp | 0.14 ms | 0.14 ms | 0.55 ms | +0.38 ms |

What the numbers mean:
- **Per reacting character:** about 0.15 ms of game thread for the control tick, plus about 0.35 ms of physics worker time.
  - The Body's own animation tick (0.14 ms) is MetaHuman cost that exists anyway.
  - So does the rest of the Hero's 0.9 to 1.3 ms of world-tick time: face anim BP, LOD sync, cloth, grooms.
  - The prototype's Python tick is not counted. Production code would be C++.
- **The control component still ticks at 0.11 ms when dormant** unless switched off. The prototype now switches its tick off while dormant and back on in `wake()`/`enter_stand()`. The plugin also offers `UpdateTargetCaches` and `UpdateControls` to drive it manually.
- **Rough budget**, if a packaged build is about 1.5 to 2x cheaper than the editor: about 6 to 8 NPCs reacting at the same moment costs roughly 1 ms of game thread and 2 ms of physics. Everyone else stays dormant, close to free.
- **Cap it.** Cap simultaneous active ragdolls; GTA does this as well. Hand the oldest corpses to a cheap "frozen pose" state.
- **Not measured:** a packaged build, many characters at once, the cost of the physics worker stalling the game thread at low frame rates.

## Problems found (lessons for the rebuild)

1. **A notified property write replaces the component.** `set_editor_property` with the default notify, on a spawned MetaHuman's Body during play, re-runs `BP_Hero`'s construction script and replaces the Body component. The controls were then left on a dead component ("both static" joint warnings, no reaction). Runtime writes must use `PropertyAccessChangeNotifyMode.NEVER`; C++ setters avoid this.
2. **Setting the transform mode first stopped the controls being created.** Setting `PhysicsTransformUpdateMode` before `CreateControlsAndBodyModifiersFromLimbBones` resulted in no controls ("No Skeletal mesh in limb"). This is very likely the same construction-script re-run as item 1. Set the mode after creating controls.
3. **Controls between two kinematic bodies lose their joints.**
   - After the first get-up version set every body kinematic, the upper body came back with no muscle: the head drooped onto the shoulder.
   - The plugin's `bAttemptToRecreateDisabledControls` fixes that, but it retries the kinematic leg joints every frame: 0.40 instead of 0.14 ms.
   - The fix used: never make the upper body kinematic during the get-up, and disable all controls in the fully kinematic dormant state.
4. **The physics asset fights Physics Control.** MetaHuman physics assets ship with joint motors toward the A-pose (see "Physics asset" above). Every body type's ragdoll asset needs them off.
5. **The GASP reach (brace) clips crouch.** Following them with the legs folds the character into a sit instead of a fall. During a fall the legs target their straight bind pose (`SetControlUseSkeletalAnimation(false)`), and only the arms and spine follow the brace clip.
6. **The old WalkerPhysics crash class doesn't apply here.** The deleted WalkerPhysics system used two meshes: a hidden physics "walker" plus a visible body copying its pose. It switched tick groups mid-reaction; its crashes (the lightning kill, empty pose buffers) came from that. This prototype has one mesh, one owner and no tick-group changes. A death during any state must still go through the same state machine (FALL to DOWN, no GETUP), never a second path.
7. **Background throttling breaks physics in editor tests.** With the editor in the background, "Use less CPU when in background" throttles the frame rate. Physics steps cap at 1/30 s (no substepping in this project), so below 30 fps physics runs in slow motion while game time and timers don't.
   - The PIE runs switched that preference off and restored it afterwards.
   - The demos were recorded at time dilation 0.35, so every frame stayed under the 1/30 s cap, then sped up 2.83x.
8. **Classify hits by momentum, not contact impulse** (see "Test triggers").
9. **MetaHuman Creator physics assets don't fit their own body meshes (fixed in our copy; systemic).**
   - **Symptom.** As soon as the upper body simulates, the spine squashes: spine_02 sits 6.3 cm low, the chest 9 cm, the head 15 to 20 cm. It happens on the first physics frame, with or without gravity, controls or collision, and also with plain `SetAllBodiesBelowSimulatePhysics` (no Physics Control).
   - **Cause.** The joints' parent-side anchors (`Pos2`) equal the shared `metahuman_base_skel` reference pose to 0.00 cm. The body meshes are differently proportioned: on the Hero, pelvis to spine_02 is 12.6 cm on the mesh against 6.2 cm in the asset. Locked joints pull the bodies to the short lengths. Bone angles match, so only lengths are off.
   - **How widespread.** `Tools/ActiveRagdoll/audit_pa_fit.py` (read-only) checked 15 cast body meshes. All are off, worst joint 4 to 10 cm, usually pelvis to spine_02:
     - GiltRamon 9.6 cm and ArchiveApprentice 8.5 cm are the worst;
     - the Hero is 6.6 cm.

     So the game's ordinary death ragdolls compress too.
   - **Fix.** `Tools/ActiveRagdoll/snap_frames.py` carries each joint's parent-side frame from the base-skeleton reference pose to the mesh's reference pose. Position is fixed; MetaHuman's deliberate 15 to 64° limit-cone offsets are kept. Applied to `PHYS_Hero_ActiveRagdoll` only; the shared `PHYS_MHC_*` assets are untouched.
   - **Production.** Run it on every body type's physics asset.
   - **Test tools.** `drift_test.py` / `drift_run.py` compare the prototype with a plain `BP_Hero` on the same clip, every frame; `rel_test.py` gives per-joint offsets and rotations; `joint_angles.py` shows where clips sit inside each joint's limits.
10. **Per-control setters also hit sets with the same name, and names ignore case.**
    - `SetControlAngularData('head', …)` on the world-space control `head` also zeroed the limb set `Head`, so the neck and head controls had zero strength from the start. The head hung chin-down, and making the controls "stronger" made it worse.
    - Always pass `apply_to_controls_with_name=True, apply_to_sets_with_name=False`, or never name a limb after a bone.
11. **Gravity sag and tight limits while standing.**
    - Neck about 13° and shoulders about 11° sagged at stand strength. Fixed by "muscle tone": upper-body gravity = weakness, so an unhit limb holds its pose and a struck limb drops.
    - The animations sit past MetaHuman's shoulder limits even at idle (76° against a cone of 60°). `widen_limits.py` widened shoulder, neck, head, clavicle and wrist limits in our copy to cover idle, walk, jog, cast, heal, stagger and get-up clips plus 10°. Elbows were kept as hinges (25/20° sideways).
    - Still open: fast arm motion (walking arm swing, spell cast) lags 20 to 30 cm while physics is on. Neither stronger controls, freed limits nor switching collision off change this. The reaction envelope hides it: physics is only on for about 1 s per hit.
12. **Shared-editor hazards found while testing.**
    - Another session's open Level Sequence spawns a MetaHuman (`BP_Kellan`, tag `SequencerActor`) at (700, 0, 8) into every play world. Test spots should avoid it; the reaction recording uses (700, 450).
    - Test Town also has a "Conversation Test NPC" that walks up to characters.
    - Heavy editor work by other sessions (Kimodo batches) drops play to 5 to 10 fps. Below 30 fps, physics (capped at 1/30 s per step) falls behind animation, so measurements and recordings taken then are invalid.

## Production effort estimate

For one programmer who can also do animation setup, to reach a solid "GTA V-lite" reaction system for NPCs:

| Work | Days |
|---|---|
| C++ `UNpcReactionPhysicsComponent`: state machine; profiles in a `UPhysicsControlAsset` instead of hand-set values; hit API fed by damage and spell events; dormant mode with the component tick off; cap on active ragdolls; death and KO path | 5 to 8 |
| Anim Blueprint integration: slots and montages, inertialization or Pose Snapshot for get-up and stagger hand-offs, directional stagger set (8-way GASP run stops), get-up left/right variants, brace chosen by fall direction | 4 to 6 |
| Physics assets per body type (the cast uses several MetaHuman bodies): motors off, spine bodies, limits, collision filtering with Chaos cloth outfits | 2 to 4 |
| Movement integration: capsule off and following the pelvis while down, back on at get-up; navmesh re-snap; get-up clearance tests near walls and on slopes or stairs (alternative clips or shuffling) | 4 to 6 |
| Gameplay hooks: spell elements to reactions (fire knockback, ice shatter, lightning twitch on a limp body), corpse sleep and despawn, hit sounds | 3 to 5 |
| Performance: significance or LOD, packaged-build profiling with crowds | 2 to 3 |
| Tuning and QA: kills mid-get-up, hits while down, crowd collisions, falls off ledges, stairs | 5 to 10 |
| Per-body physics-asset fit pass, scripted: joint re-snap (`snap_frames.py`), limit widening, motors off, run for each cast body type and re-checked with `audit_pa_fit.py` | 1 to 2 |
| **Total** | **about 26 to 42 working days** |

Not in that estimate: real balance and stepping, meaning Euphoria-style corrective steps and grabbing. That is research-grade: weeks of work on a procedural foot-placement controller, or Learning Agents (experimental 0.2 in this install). I would not plan on it. Clip-driven staggers plus physics are what most shipped games outside Rockstar use.

## How to re-run the prototype

1. Take `Saved/PIE_LOCK.json` with `python Tools/ActiveRagdoll/lock.py take`. It waits until the lock is free and PIE is idle.
2. Switch the background throttle off: `python Tools/ActiveRagdoll/ue.py Tools/ActiveRagdoll/r_common.py Tools/ActiveRagdoll/r_thr_off.py`.
3. Start Simulate and spawn: same `ue.py r_common.py` pattern with `r_start.py`.
4. Optional slow-motion for recording: `r_td.py`.
5. Run the demo and record it: `ev_final.py r_rec_start.py`, then later `r_rec_stop.py`.
6. Stop and clean up: `r_stop.py`, then `r_thr_restore.py`, then `lock.py release`.
7. Cost sampling: `r_measure.py` with `MODE='all'` or `MODE='dorm'`.

The driver scripts are throwaway glue for the shared editor's MCP port (8019). `ar_proto.py` holds all the logic.
