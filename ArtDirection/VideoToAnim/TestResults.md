# GEM-X video-to-MetaHuman test (2026-11-21/22)

**Result: it works end to end.** NVIDIA GEM-X turned a 19 s jiu-jitsu hip-escape (shrimp) video into motion on the Hero MetaHuman. GEM-X ran on the RTX 5080. The output was converted to Kimodo's SOMA skeleton and retargeted to `metahuman_base_skel`. The poses visibly match the drill: on the back with knees bent, then curled on the side.

- **Recording:** `Saved/Recordings/Viewport_20261122-001303_4U6643WAGCLPVI8BG4F30PI8B.mp4`. It is 20 s, rendered in the animation editor on the Hero body mesh. It is not frame-synced to the source.
- **Comparison image:** `C:\Users\zachc\GemXTest\preview\hip_compare.jpg`. The top row is the source clip and the bottom row is the MetaHuman, sampled every 2.5 s.

> **Do not ship the hip-escape assets.** They come from a third-party YouTube video, "Stationary Shrimp/Hip Escape (BJJ)" by Nomad Fitness & Jiu Jitsu. It was downloaded with yt-dlp for a private test, at the owner's request. See [Research.md](Research.md) section 5. Re-do any move you want to keep from footage you film yourself.

## Run 3: medieval longsword (2026-11-22, 00:22–00:34)

- **Source:** YouTube, Matt Galas, "HEMA Longsword – 64 Cut Solo Drill" (46 s, 1080p30). One fencer, locked-off camera, whole body, plain wall. I processed the first 24 s.
- **GEM-X:** 6 m 22 s on the GPU (whole-GPU VRAM peak 14.9 GB with the editor open), started after active-ragdoll's PIE lock cleared. All 720 frames were tracked.
- **Numbers:**
  - Hips at 0.96–1.06 m.
  - Median joint jerk 288 m/s³, the same as the clean Kimodo render.
  - The root moves through 10.5 m of real weight-shift and footwork within a 1.3 × 0.4 m area. It ends 0.5 m from where it started.
- **Result:** `AS_Hero_GemX_Longsword64` (24.0 s). The pelvis is at about 87 cm and the right hand moves through cuts at chest-to-head height.
  - Recording: `Saved/Recordings/Viewport_20261122-003310_5L7GK8PUY0LVH2N59IRH5MDUS.mp4` (19.7 s captured).
  - Comparison: `C:\Users\zachc\GemXTest\preview\sword_compare.jpg`.
- **Look:** a convincing two-handed fencing motion, with high and low cuts, a wide stance, passing steps and turns. It looks more like a real fencer than the Kimodo sword takes.
- **Limits:**
  - There is no sword: GEM-X doesn't track props.
  - There are no fingers, so the grip is open hands.
  - Blade direction would need a sword attached to `hand_r` and wrist checks, as in the Kimodo test.
- **Do not ship:** this clip is derived from YouTube.

## What was set up (outside the repo)

Everything lives in `C:\Users\zachc\GemXTest\`, about 13 GB on disk in total.

- **Python environment:** uv venv on CPython 3.11, torch 2.11.0+cu128 and torchvision 0.26. CUDA works on the RTX 5080 (sm_120).
- **GEM-X:** git clone of NVlabs/GEM-X, installed `-e .[video]` (transformers 5.3.0, py-soma-x 0.3.3, onnxruntime).
- **Weights:** from `nvidia/GEM-X` on Hugging Face (not gated, NVIDIA Open Model License):
  - `body_s240000.ckpt` (3.54 GB)
  - `vitpose.pth` (3.39 GB)
  - `motion_native77_e774_s292175.ckpt` (187 MB)
  - stats and config files
- **SOMA v0.3.3 assets:** 3 files, 55 MB.
- **Person detector:** OpenMMLab YOLOX-X HumanArt ONNX (368 MB zip).
- **ffmpeg:** the imageio-ffmpeg binary, copied to `bin\ffmpeg.exe`.
- **Scripts** (`scripts\`):
  - `gemx_to_soma30.py`: GEM-X output to a 31-bone SOMA clip, with a stick-figure check.
  - `npz_to_json.py`
  - `ue_mcp.py`: a minimal client for the editor's built-in MCP on port 8019.
  - `ue_import_soma.py`: writes the AnimSequence through AnimationDataController.
  - `ue_make_rtg.py`
  - `ue_retarget.py` and `ue_after_lock.py`
  - `preview_frames.py`

## Runs

| Clip | Source | GEM-X device | Time | Notes |
|---|---|---|---|---|
| Smoke test | Our own render, `Saved/KimodoSwordTest/Kimodo_Sword_Take3_TestTown.mp4` (5.5 s, 15 fps) | CPU | 13 m 44 s | The first GPU attempt segfaulted at "frozen body Pose features". The editor plus another session's GPU job had VRAM at 15.4/16.3 GB. On CPU it passed. Its stick figures show guard, cuts and lunge, matching Take3. |
| Hip escape | YouTube, 25 s, 1080p30, from 5 s to the end | GPU, batch 2 | 11 m 52 s | Whole-GPU VRAM peaked at 15.5/16.3 GB with the editor open. The first 34 frames (the logo fade) had no person and were trimmed, leaving 18.8 s / 563 frames. Model-predicted contact fraction was 0.10. |

## How the motion reaches the MetaHuman

1. **GEM-X output:** `pred_soma_params_global` holds 77-joint SMPL-style axis-angle rotations, relative to the T-pose, in Y-up metres.
2. **Rebase:** FK, then Kimodo's `from_standard_tpose` rebase using `standard_t_pose_global_offsets_rots.p`. This is the same step the Kimodo UE worker uses. I checked that the rebased rest frames match the UE asset `soma_neutral`'s reference pose to within 1° on all 30 bones.
3. **Skeleton:** take the 30-joint subset, add a synthetic floor `root` bone (the pelvis split, as Kimodo does it), then swap Y/Z and convert metres to cm. Rotations only. Bone translations come from the UE asset's own reference pose; only `root` and `Hips` move.
4. **Grounding:** each frame is grounded on its lowest joint, 4 cm above the floor, with a 15-frame median. This handles floor work, but it would flatten real jumps.
5. **AnimSequence:** written on `/Kimodo/Characters/Soma/soma_neutral_Skeleton` through `AnimationDataController.set_bone_track_keys`.
6. **Retarget to the Hero body:** batch retarget with the **new** `RTG_SomaToHero_Video`.
   - The existing `RTG_SomaToHero` (built for combat casts) does not work for full-body clips. Its Pelvis Motion op reads source bone `pelvis`, which SOMA lacks (SOMA uses `Hips`). Its `IK_Soma_Combat` `head` chain points at a missing bone `head` (SOMA uses `Head`). The pelvis froze at 87 cm.
   - The new retargeter uses default ops, exact chain mapping onto `IK_Hero_Body`, Hips → pelvis, and target retarget pose `VideoAlign` (auto-aligned to SOMA's T-pose).

## Assets created (all new; nothing else saved)

`/Game/Animation/VideoTests/`:
- `AS_Soma_GemX_KimodoTake3` (5.5 s)
- `AS_Soma_GemX_HipEscape` (18.7 s)
- `AS_Hero_GemX_KimodoTake3` (5.5 s)
- `AS_Hero_GemX_HipEscape` (18.7 s); preview mesh set to `SKM_MHC_Hero_BodyMesh`
- `Rigs/IK_Soma_Video`
- `Rigs/RTG_SomaToHero_Video`

`Content/Animation/` is untracked in git, so none of this is committed.

Sampled from the Hero clips:
- **KimodoTake3:** pelvis at 90–91 cm while standing, 83 cm in the lunge.
- **HipEscape:** pelvis at 7–36 cm and head at 2–15 cm off the floor, travelling across the mat.

## Quality, honestly

- **Good:** the gross body motion is right. Supine with knees bent, rolling to the side and tucking into the shrimp, then returning. No limb swaps showed in the sampled frames. Floor contact is believable after grounding.
- **Rough:**
  - Jitter is about 2× the Kimodo render's (median joint jerk 662 vs 286 m/s³, before any smoothing).
  - One sampled frame (around 8 s) has the hips raised high, which is either a bridge or a glitch.
  - There are no fingers; GEM-X hand weights are separate and gated.
  - The editor preview shows the body mesh only, so there is no head in the recording. The full `BP_Hero` would add head and clothes.
- **Not checked yet:**
  - Foot-skate and jitter metrics on the Hero clip.
  - A frame-synced side-by-side.
  - How it plays in game through `BP_Hero`'s AnimInstance.
  - Speed: 12 min for 19 s of video on a shared GPU, so plan batches for when the editor is closed.

## Shared-editor footprint (for other sessions)

- Editor calls went through the editor's built-in MCP at 127.0.0.1:8019. This session's `unreal-mcp` entry points at port 8000. At the time of the test, port 8000 was held by a headless `UnrealEditor-Cmd` running automation tests in `.worktrees\digging`, so I did not use it.
- A temporary `BP_Hero` (`ZZ_VideoAnimPreview_TEMP`) stood at (700, 0, 8) in `L_TestTown` from 00:03 to 00:12 and was then removed. `L_TestTown` is flagged dirty only because of that spawn and removal, and I did not save it. The temporary Hero was in the level during active-ragdoll's PIE run 2 (00:03–00:11).
- Several of my short `execute_python` calls also overlapped active-ragdoll's PIE run 2, between about 00:04 and 00:07. If that run misbehaved, this is a possible cause.
- I never started or stopped PIE.
