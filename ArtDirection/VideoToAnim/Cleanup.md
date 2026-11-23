# Cleaning GEM-X clips and getting them into the game

Written 2026-11-22. This follows [StressTest.md](StressTest.md).

> **Licence warning.** Every clip named here comes from YouTube and is a **private test**. These clips can show how the pipeline works and can sit in private builds as placeholders. They must never reach a build you sell, upload or show publicly. For shippable motion, run the same pipeline on footage you film yourself (see the last section).

## Bottom line

GEM-X output has three faults that matter in a game:
- feet slide while planted;
- small jitter on every joint;
- open hands.

One cleanup script now fixes all three, and it runs in about 20 s per 20 s clip, with no editor needed:
- **Feet:** planted feet stop sliding. On our skeleton the median slide drops from 10 cm/s to 0. On the Hero it drops from 9.6 to 1.7 cm/s after the retarget.
- **Jitter:** jerk is about 3× lower on our skeleton and 4× lower on the Hero.
- **Strikes:** sword strikes keep about 90% of their peak hand speed.
- **Shape:** the overall pose moves by only about 1 cm on average.
- **Hands:** a sword grip is baked onto both hands.

**What is still manual:**
- cutting long takes into single moves;
- attaching the weapon;
- blending in and out of the game's own stance;
- hit timing.

## What the cleanup does

The script is `C:\Users\zachc\GemXTest\scripts\clean_motion.py`. It reads the GEM-X `.pt` file and writes the same `.npz` layout as `gemx_to_soma30.py`, so the existing import and retarget scripts work unchanged. It runs these passes in order:

| Pass | What it does | Why |
|---|---|---|
| Trim | `--range S E` cuts one move out of a long take | Game moves are 1–3 s long, not 20 s |
| Despike | Wherever a joint moves faster than 12 m/s for 6 frames or fewer, the pose is interpolated across that run | Removes the one-frame pops GEM-X makes when tracking briefly fails |
| Smooth | Savitzky–Golay filter on each joint's rotation, with a different window per body part: arms 5 frames, spine and legs 9, head 13 | Removes jitter but keeps cuts sharp. A plain blur would soften the strikes |
| Floor | The floor is placed under the **planted** foot, using GEM-X's own contact guesses. Swing feet never move it, and any foot that would sink is lifted | The old converter used the lowest joint in every frame, so the body bobbed whenever a foot lifted |
| Foot lock | Each planted foot is pinned to one spot for the whole time it is planted. Two-bone leg IK bends the knee to reach it, the foot's facing is held, and each lock eases in and out over 4 frames | Stops foot sliding, the most visible fault |
| Root | Root motion follows a smoothed path of the hips, or stays at the origin with `--inplace` | Gives the character capsule a clean path to follow |

**Grip.** A fixed sword-handle grip is keyed onto both hands after the retarget, using `scripts\_apply_grip.py`. The curl axis was taken from the Hero's existing idle, so every finger closes toward the palm. The closed fist was checked in the editor.

## Results

**On our skeleton**, before the retarget. Metrics are from `clean_motion.py`.

| Clip | Planted-foot slide, median / p95 | Jitter (median jerk) | Pops | Foot below floor | Peak right-hand speed |
|---|---|---|---|---|---|
| Sword spar, raw | 10.3 / 40.7 cm/s | 447 | 0 | 16 frames | 3.15 m/s |
| Sword spar, cleaned | **0.0 / 1.2 cm/s** | **153** | 0 | **0** | 2.86 m/s |
| Armoured duel, raw | 9.1 / 47.1 cm/s | 611 | 1 | 5 frames | 4.09 m/s |
| Armoured duel, cleaned | **0.0 / 0.0 cm/s** | **209** | **0** | **0** | 4.18 m/s |

**On the Hero**, after the retarget. Metrics are from the MetaHuman bones in the editor.

| Clip | Planted-foot slide, median / p95 | Jitter (median jerk) | Peak right-hand speed |
|---|---|---|---|
| Sword spar, raw | 9.6 / 37.5 cm/s | 295 | 2.68 m/s |
| Sword spar, cleaned | **1.7 / 8.2 cm/s** | **75** | 2.40 m/s |
| Armoured duel, raw | 8.7 / 41.0 cm/s | 355 | 3.40 m/s |
| Armoured duel, cleaned | **2.1 / 7.1 cm/s** | **91** | 3.55 m/s |

**Why some slide comes back on the Hero.** The Hero's legs are a different length from the source skeleton's, and the retargeter copies rotations. To get the Hero to zero, add one of these:
- a leg-IK step in `RTG_SomaToHero_Video` that sends the Hero's feet to the source feet;
- a foot-lock pass on the Hero clip.

At 1–2 cm/s the slide is hard to see.

**Things to look at:**
- `C:\Users\zachc\GemXTest\outputs\sparring_clean_compare.mp4` and `armored_clean_compare.mp4`: stick figures, raw against cleaned, frame-exact. Trails show where the ankles slid, and green rings mark planted feet.
- `C:\Users\zachc\GemXTest\preview\hero_spar_frames.mp4` and `hero_armored_frames.mp4`: the Hero, raw against cleaned, frame-exact, at 15 fps.

## Running it

```powershell
cd C:\Users\zachc\GemXTest
# whole take, with the compare video
.venv\Scripts\python.exe -I scripts\clean_motion.py outputs\stress_sparring_1v1.pt outputs\sparring_clean --video
# one move from a take, in place (seconds 3.2 to 5.0)
.venv\Scripts\python.exe -I scripts\clean_motion.py outputs\stress_sparring_1v1.pt outputs\spar_cut1 --range 3.2 5.0 --inplace
# then: npz_to_json.py -> ue_import_soma.py -> ue_retarget_one.py -> _apply_grip.py (same as before)
```

Use `--no-despike`, `--no-smooth` or `--no-footlock` to switch off a pass. Use `--arm-win 7` for smoother but softer arms.

## Getting moves into the game

The Hero already plays one-shot clips through a slot montage. `AReflectionsHeroCharacter::CastHeroSpell` calls `PlaySlotAnimationAsDynamicMontage` on `SpellSlot`, then fires its effect once the clip reaches `ReleaseTime`. A sword attack can reuse that same path. Here is the order to do it in:

1. **Cut moves, not takes.** From each cleaned take, cut moves of 0.8–2.5 s: guard, high cut, low cut, thrust, block, parry, a step-in, a step-back, a stagger, and so on. Start and end each move in the same guard pose, so moves chain together and blend into the game's stance. Use `--range` and look at the compare video to find the frames.
2. **Root motion.** Moves that step should keep root motion. The cleaner gives a smooth root, and the asset needs `enable_root_motion` set to true, so the capsule moves with the feet. Moves that stand still should use `--inplace`.
3. **Montages and timing.** Make one `AM_` montage per move with notifies for:
   - hit start and hit end, to turn the blade trace on and off;
   - swing sound (`SCue_Sword_Swing` already exists);
   - combo window.

   Alternatively, for a first test, add the moves as a "melee spell" with `ReleaseTime` set to the hit frame.
4. **Weapon.** Attach the sword mesh to the `hand_r` **bone** with an offset in the Blueprint or in code. Don't add a socket: that means saving `metahuman_base_skel`, which other work keeps dirty and must not be saved casually. A first offset to try, in hand_r space:
   - location (-7, 3.5, 6) cm;
   - blade along +Z, toward the thumb side;
   - guard along X.

   This offset is untested. The Python API can't place a sword in the animation preview, so it couldn't be checked there.
5. **Hands.**
   - **For now:** the grip is baked into each cleaned clip.
   - **Long term:** keep one grip pose and layer it over the fingers in the AnimInstance, with a per-bone blend on the finger chains. Then every clip holds the sword, and idle or spell clips can open the hand.
6. **What not to take from video.**
   - **Locomotion cycles:** keep the existing ones.
   - **Airborne moves:** they lose their height (see StressTest.md).
   - **Anything that relies on the sword's exact angle:** the wrist from video isn't sword-aware. Expect to touch up the wrist on the key frames of each cut.
7. **NPC fighters.** Retarget the same cleaned SOMA clips to each NPC's skeleton. The cleanup happens before the retarget, so it carries over to every body.

## The shippable path (the same pipeline on your own footage)

1. **Film it.** Use a phone on a tripod, static camera mode, the whole body in frame, and plain clothes against a busy background. Do one move per take, starting and ending in guard. Hold a wooden sword or broomstick of the right length. Get a signed release from anyone who performs.
2. **Run GEM-X** with `--camera-mode static --postprocess`, then `clean_motion.py` with `--range` for each move.
3. **Import, retarget, grip.** The scripts already exist.
4. **In the editor:**
   - touch up the wrist on the strike frames;
   - make the montage;
   - add the notifies;
   - attach the weapon;
   - play-test.

**Budget per move:** about 10 minutes of GPU time per 20 s take, which yields several moves. The cleanup takes seconds, and hand polish takes 15–30 minutes per move.

## Files

**Project files** (only my own new assets, all saved):
- `/Game/Animation/VideoTests/AS_Soma_GemX_Sparring1v1_Clean`
- `/Game/Animation/VideoTests/AS_Soma_GemX_ArmoredDuel_Clean`
- `/Game/Animation/VideoTests/AS_Hero_GemX_Sparring1v1_Clean` (has the grip)
- `/Game/Animation/VideoTests/AS_Hero_GemX_ArmoredDuel_Clean` (has the grip)

**Outside the project:**
- `C:\Users\zachc\GemXTest\scripts\clean_motion.py`
- `C:\Users\zachc\GemXTest\scripts\_apply_grip.py`
- `C:\Users\zachc\GemXTest\stress\hero_grip_pose.json`
- `C:\Users\zachc\GemXTest\stress\hero_clean_metrics.json`
- the compare videos listed above

**Not touched:** the level, the skeleton, `Source/`, and other sessions' assets. Nothing is committed.
