# Digging spike: results

This page holds the numbers from the digging spike. They decide whether the full digging feature gets built.
Every number in the results tables comes from the same three measurement runs.

## Read this first

- **This was not a packaged game.** The measurements ran in the editor program started as a game (the only way to run
  them in this copy of the project). In that mode some of the renderer's bookkeeping for changed objects runs on the
  game's main thread at the end of each frame; a packaged game does that work elsewhere. A packaged game may
  therefore be faster. These numbers are the cautious reading.
- **Two cases break the 4 ms mark clearly:** digging in a chunk that is already full of holes (about 60 ms of extra
  main-thread work per dig, worst frames of 64 to 89 ms) and digging where eight chunks meet (about 11 to 15 ms per
  dig, 99 frames in 100 under 6.5 to 8.8 ms). Streaming also has a single slow frame of 42 to 65 ms each run when a
  heavily dug chunk comes back. Digging in open ground meets the mark on 99 frames in 100 but not on the worst frame.
- **Where the heavy cost goes:** almost all of it is in the frame right after a chunk is updated, outside the terrain's
  own code. The terrain's own work is about 2.5 ms per dig in a busy chunk and about 3 ms per corner dig. See "Where
  the cost of a heavy dig goes".

## How it was measured

- The game ran with its real renderer, drawn off screen at 1280 x 720, capped at 60 frames a second, on an RTX 5080.
  Another full Unreal editor was running on the same machine the whole time, so the computer was not quiet.
- Hardware ray tracing was on, except where a screenshot turned it off on purpose.
- The test ran three times; each run took about 4.7 minutes (279, 293 and 282 seconds). Before each measurement the
  test waited until no shaders were being compiled, the terrain was settled and navigation was not rebuilding.
- **Game-thread time** is the time the game's main thread spends working in one frame, in milliseconds (ms). It leaves
  out time the main thread spends waiting: for the 60-frames cap, and for other threads (the renderer, the graphics
  card, background tasks). One frame at 60 frames a second lasts 16.7 ms.
- **Above idle** means above the middle idle frame of the same run (about 2.1 ms), measured at the same spot just
  before, with nothing being dug, for as long as the measured window.
- **Whole window**: every frame of the measured time counts, not only selected frames. Most of what a dig costs lands
  in the frames after the dig (the new collision finishing, navigation, the renderer's data), so only the whole window
  shows the full cost.
- **Cost per dig**: the extra main-thread time of the whole window divided by the number of digs.
- Each frame was also tagged with what happened in it or in the frame before (a dig, a chunk put on screen, a collision
  finishing, a navigation update, a chunk dropped or rebuilt) and whether the engine cleaned up memory (garbage
  collection). Frames with none of these are "background": that is the only place the machine's noise is read from.
- Log files: run 1 `test-090807.log`, run 2 `test-091247.log`, run 3 `test-091739.log` (in `.superpowers/logs/` of the
  digging worktree).

## Results with the renderer on

The 4 ms mark is judged two ways, as the plan document asks: on the worst frame of the window minus idle, and on the
99th percentile (99 frames in 100 at or under this, minus idle). "Not met" rows are listed first.

| What | Run 1 | Run 2 | Run 3 | Pass mark | Result |
|---|---|---|---|---|---|
| Digging in a busy chunk: 99 in 100 / worst frame (above idle) | 60.2 / 63.5 ms | 67.5 / 88.6 ms | 61.1 / 75.8 ms | 4 ms or less | **Not met** on both, all runs |
| Digging at an eight-chunk corner: 99 in 100 / worst frame | 8.8 / 392.8 ms (b) | 6.5 / 22.5 ms | 7.9 / 44.3 ms (a) | 4 ms or less | **Not met** on both, all runs |
| Digging in open ground: 99 in 100 / worst frame | 2.2 / 22.0 ms (a) | 2.7 / 24.4 ms (a) | 2.4 / 45.4 ms | 4 ms or less | Met on 99 in 100; **not met** on the worst frame, all runs |
| Streaming: 99 in 100 / worst frame | 2.7 / 51.3 ms | 2.9 / 64.8 ms | 2.8 / 42.4 ms | 4 ms or less | Met on 99 in 100; **not met** on the worst frame, all runs |
| Collision size per chunk (largest collision mesh) | 10,320 vertices | 10,320 vertices | 10,320 vertices | under 16,384 | Met |
| Seams (missed downward traces out of 500) | 0 | 0 | 0 | no missed traces | Met |
| Navmesh: dig to walkable floor | 0.067 s | 0.083 s | 0.067 s | 1 s or less, no stall | Met; worst frame while it rebuilt 1.8 to 3.7 ms above idle |
| Shadows: render thread / graphics card, average while digging (idle) | 5.3 (5.2) / 2.63 (2.59) ms | 5.3 (5.5) / 2.67 (2.60) ms | 5.5 (5.2) / 2.63 (2.57) ms | frame cost recorded, no flicker | Cost recorded; not judged (flicker) |
| Cave lighting | screenshots | screenshots | screenshots | judged by the owner | For the owner |
| Packaged build | not measured | not measured | not measured | same checks repeated | Not measured |

(a) The worst frame was a garbage collection (the engine cleaning up memory). It is kept in the row.
(b) The worst frame (395 ms) was the frame after a dig call, so it counts as dig-related; nothing else of the dig
happened in it (no chunk update, no collision, no navigation), and the dig call itself takes well under 0.1 ms. It was
most likely the machine stalling, but by the rule above it counts.

### The machine's noise level

Frames with no dig-related event and no garbage collection reached at most 4.8, 4.3 and 6.5 ms above idle in the
open-ground digging windows and 4.3, 4.8 and 3.5 ms in the streaming windows. The idle windows (same spot, nothing
being dug) reached up to 29 ms in the open-ground test and once 103 ms (run 1, before the streaming test). So on this
machine a single frame of tens of milliseconds, and once over 100 ms, happened with no digging at all. That is why the
99-in-100 figure is the steadier one; the worst-frame figure is kept as the plan asks.

### Digging in open ground

A character stood at (1800, -1600). The test dug under its feet every 0.1 seconds for 30 seconds: 300 digs, all
changing the ground. For the first 7 to 8 seconds it dug straight down until the character reached the bottom,
27.6 m down; after that it dug out and filled back a small pocket beside it, in turn.

| Whole window, above idle | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Average / middle frame | 0.35 / 0.21 ms | 0.36 / 0.19 ms | 0.37 / 0.20 ms |
| 99 in 100 at or under | 2.2 ms | 2.7 ms | 2.4 ms |
| Worst frame (raw) | 22.0 ms (24.1) | 24.4 ms (26.5) | 45.4 ms (47.5) |
| Worst dig-related frame | 8.4 ms | 20.9 ms | 45.4 ms |
| Cost per dig | 1.6 ms | 1.5 ms | 1.5 ms |

### Digging at an eight-chunk corner

At (2625, 825, -1200), where eight chunks meet, the test dug out and filled back in turn every 0.1 seconds for 10
seconds. Each dig rebuilds all eight chunks.

| Whole window, above idle | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Average / middle frame | 2.7 / 1.7 ms | 2.0 / 1.7 ms | 2.0 / 1.7 ms |
| 99 in 100 at or under | 8.8 ms | 6.5 ms | 7.9 ms |
| Worst frame (raw) | 392.8 ms (395.0) | 22.5 ms (24.6) | 44.3 ms (46.4) |
| Worst dig-related frame | 392.8 ms | 22.5 ms | 9.8 ms |
| Cost per dig | 15.1 ms | 11.0 ms | 11.1 ms |

### Digging in a busy chunk

The buried chunk at X 4225 to 5825, Y -2375 to -775 was first riddled with 512 round holes until its mesh had about
30,000 vertices, split into pieces of at most 10,320. Then the test dug out and filled back one spot inside it every
0.1 seconds for 10 seconds.

| Whole window, above idle | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Average / middle frame | 14.4 / 3.7 ms | 15.7 / 3.8 ms | 14.2 / 3.5 ms |
| 99 in 100 at or under | 60.2 ms | 67.5 ms | 61.1 ms |
| Worst frame (raw) | 63.5 ms (65.6) | 88.6 ms (90.6) | 75.8 ms (77.9) |
| Cost per dig | 58.8 ms | 61.2 ms | 57.8 ms |
| Frames in the 10 seconds | 412 | 393 | 410 |

The game dropped to about 40 frames a second while digging. Where that time goes is the next section; it is the most
important result on the page.

## Where the cost of a heavy dig goes

For the busy chunk and the corner, the test also timed the terrain's own work, piece by piece, and compared it with
the whole window's extra main-thread time:

- **chunk updates**: the terrain putting new meshes on its pieces and starting their new collision;
- **swap check**: the terrain retiring and destroying old pieces;
- **collision finishing**: the engine's own work when a piece's new collision is ready (swapping it in);
- **navigation**: the terrain telling navigation about the new collision;
- **rest**: everything else in those frames. The test cannot see inside it. In this mode (the editor program run as a
  game) it includes the renderer rebuilding the drawing data of changed pieces on the main thread, which happens in the
  frame after a chunk update.

| Total over the 10-second window, 100 digs | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| **Busy chunk**: whole window, extra main-thread time | 5,878 ms | 6,122 ms | 5,785 ms |
| ... chunk updates / swap check | 196 / 16 ms | 208 / 15 ms | 207 / 15 ms |
| ... collision finishing / navigation | 21 / 5 ms | 23 / 5 ms | 23 / 5 ms |
| ... rest, in the frame right after a chunk update | 4,826 ms | 4,722 ms | 4,681 ms |
| ... rest, all other frames | 814 ms | 1,149 ms | 854 ms |
| **Corner**: whole window, extra main-thread time | 1,508 ms | 1,101 ms | 1,115 ms |
| ... chunk updates / swap check | 195 / 9 ms | 204 / 8 ms | 195 / 8 ms |
| ... collision finishing / navigation | 62 / 18 ms | 63 / 17 ms | 61 / 16 ms |
| ... rest, in the frames with a chunk update | 470 ms | 435 ms | 418 ms |
| ... rest, in the frame right after | 238 ms | 261 ms | 246 ms |
| ... rest, all other frames | 516 ms | 112 ms | 170 ms |

What this shows, in plain words:

- **Busy chunk.** Every dig rebuilt all three pieces of the chunk, about 29,800 vertices in all, even though one dig
  touches a small part of it. The terrain's own work was about 2.2 ms per dig. The engine's work when the new collision
  came in was about 0.2 ms per dig. About 47 ms per dig sat in the frame right after the chunk update, outside
  everything the test times. Only about 4% of the cost is in parts the test can name.
- **Corner.** Each dig updates eight small chunks (about 620 vertices each). The terrain's own work was about 2 ms per
  dig, collision finishing and navigation about 0.8 ms. The rest is spread over the update frame and the frame after.
  About a fifth to a quarter of the cost is in named parts. Run 1's total includes one 395 ms frame (see note (b) above).

What it does not show:

- It does not say what the "rest" is. The likely cause is the renderer rebuilding the drawing data of the changed
  pieces on the main thread, because that is the work this mode does in the frame after an update. It may also include
  the engine's physics and navigation work outside the timed calls. Splitting it needs a profiler capture.
- It does not say whether a packaged game is faster. If the "rest" is the renderer's rebuild, a packaged game does it
  elsewhere and may be much faster; that is not measured.
- It does not include waiting: game-thread time leaves out time the main thread spends waiting for other threads.

### Streaming

The character was moved (not walked) from one corner of the patch (1100, -2300) to the opposite corner (5700, 2300)
over 20 seconds. Ten chunks were dropped behind it and eleven rebuilt in front of it, in every run.

| Whole window, above idle | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Average / middle frame | 0.25 / 0.06 ms | 0.29 / 0.10 ms | 0.24 / 0.05 ms |
| 99 in 100 at or under | 2.7 ms | 2.9 ms | 2.8 ms |
| Worst frame (raw) | 51.3 ms (53.4) | 64.8 ms (66.9) | 42.4 ms (44.4) |
| Time spent dropping chunks, all ten | 0.9 ms | 0.9 ms | 0.9 ms |

The worst frame in each run was the frame after the riddled busy chunk came back into range, when its three large
pieces were rebuilt.

### Navmesh

A walkable ramp (12 digs at once, from (3600, -1700) down to (3000, -1700, -300)) was dug in each run. From the dig to
the first successful navigation query on the new floor: 0.067, 0.083 and 0.067 s (collision ready after 0.050 s,
walkable 0.017 to 0.033 s later). The worst frame while navigation rebuilt was 3.7, 2.3 and 1.8 ms above idle. No
stall.

### Collision size

The largest collision mesh anywhere was 10,320 vertices, from the riddled busy chunk; the 200 random digs of the
collision test alone made smaller meshes. The engine's problem starts above 16,384 vertices per collision mesh, and
the code splits a chunk into pieces of at most 12,000.

### Seams

500 downward traces on the join with the plain ground at X = 1000 and the four chunk borders inside the patch
(X = 2625 and 4225, Y = -775 and 825). None missed, in any run.

### Shadows

A pit at (3000, 0) in sunlight, seen by a fixed camera, with a dig every 0.1 seconds along its sunlit rim for 10
seconds (100 digs). The render thread and the graphics card each changed by less than 0.25 ms on average while
digging. On the game thread, the worst frame minus the worst idle frame was 1.9, -1.0 and 0.6 ms. Flicker was not
judged: nobody watched the game running.

### Graphics card (for information)

Average graphics-card time per frame was about 1.8 to 2.7 ms in every window, and digging added at most about 0.2 ms
to it. The graphics card is far from being the limit here.

## Cave lighting

A 500 cm tunnel was dug from the bottom of a 4 m pit at (1800, 1400). For the shots only, cave light 1 was moved just
inside the tunnel's mouth, under its roof, at (1900, 1400, -220), and dimmed from 5000 to 300 (unitless); each shot
waited 8 seconds for the lighting and the exposure to settle, and the light was put back afterwards. The screenshots
are in `ArtDirection/Digging/SpikeShots/` (from run 3; all runs gave the same brightness).

**About brightness:** the game's automatic exposure brightens dark views and darkens bright ones, as an eye adapts. So
in the first six shots a dim tunnel and a sunny pit look about equally bright; they do not show how dark the tunnel
really is. The last two shots use one fixed exposure, so they compare real brightness.

- `tunnel_hwrt_on.png`: from the pit, looking down the tunnel. Pale grey walls, a darker band where the floor meets
  the walls, the far end a softer darker square, and on the right a bright sharp-edged strip (a wall of the pit in
  sunlight). Smooth, soft shading with no surface detail.
- `tunnel_hwrt_off.png`: the same shapes, with the whole tunnel tinted blue-grey.
- `tunnel_wall_hwrt_on.png`: inside the tunnel, looking at its side wall from about 1 m. A bright, sharp-edged diagonal
  band, most likely sunlight coming down through the pit opening, across dark grey wall.
- `tunnel_wall_hwrt_off.png`: the same, with the dark wall blue-grey.
- `pit_hwrt_on.png`: the pit from above its rim. Grey ground; angular, faceted walls inside the pit; its shadowed lower
  part near black.
- `pit_hwrt_off.png`: the same, but the shadowed inside of the pit is dark blue.
- `tunnel_fixed_exposure_hwrt_on.png` and `tunnel_fixed_exposure_hwrt_off.png`: the tunnel view at one fixed exposure.
  With hardware ray tracing on, the tunnel is a dim, neutral grey with a darker far end and the sunlit strip on the
  right. With it off, the same view is noticeably brighter (average brightness 134 against 108 out of 255) and
  blue-grey throughout.

**Hardware ray tracing on and off look different.** With it off, the parts of the tunnel and pit that the sun does
not reach are lit blue-grey, and the fixed-exposure pair shows that this is extra light, not only a colour change:
sky light reaching underground. The likely reason is that without hardware ray tracing the lighting system works from
a simplified version of the scene that does not include the dug ground, so nothing blocks the sky's light. Whether
either look is right for a cave is for the owner to judge.

For each "on" shot the ray-tracing settings, and the conditions the renderer itself checks, said hardware ray tracing
was in use; for each "off" shot they said it was not; the images agree. It was switched back on afterwards.

## What we found along the way

- **The dug ground sat 25 cm off.** The first rendered measurement showed a 25 cm strip without ground along two edges
  of the patch. Fixed: the terrain's grid now starts half a cell inside the patch corner, so the ground covers exactly
  the patch.
- **The engine's default material turned tunnels black.** When the dug ground had no material of its own, the engine
  drew it with its default grid material, and a view down a tunnel came out completely black. Fixed: the terrain always
  uses a plain engine material when none is set, and the test map sets one.
- **Hardware ray tracing matters underground.** Without it, sky light leaks into tunnels and pits (see "Cave lighting").
- **Heavily dug chunks are expensive to change.** Each change to a chunk of about 30,000 vertices costs about 60 ms on
  the main thread, almost all of it after the terrain's own code has finished.

## Numbers from earlier tests, without the renderer (headless)

These come from tasks 2.3 to 2.5, run without any graphics. They are not comparable with the tables above.

| What | Measured |
|---|---|
| Putting a flat or lightly dug chunk on screen | 0.15 to 0.45 ms |
| Putting a heavily dug chunk on screen (about 29,000 vertices in three pieces) | 1.9 to 2.5 ms |
| Copying one chunk's data for the background workers | about 0.02 ms |
| The frame that copies and starts eight chunks | 0.2 to 0.4 ms |
| Longest wait from a dig until the terrain was settled again | 95 to 247 ms |
| Navmesh walkable after the collision was ready | 0.033 s |
| A computer-controlled character reached the bottom of a new ramp | 1.5 s |
| Holding dig under the character reached bedrock, 27.7 m down | 5.4 to 6.0 s |

## What was not measured

- **A packaged build.** This copy of the project has no game content, so nothing can be packaged; and see "Read this
  first" on why a packaged game may be faster.
- **The real hero and the real town.** They are not in this copy. All tests used a plain stand-in character on a small
  test map.
- **A machine without a ray-tracing graphics card.** Only this machine (RTX 5080) was used. Given the sky-light leak
  above, caves on such a machine would likely look blue-grey.
- **Flicker.** Nobody watched the game running.
- **A quiet machine.** Another Unreal editor ran throughout; the worst single frames reflect that.

## Plugin check

Voxel Plugin 2 listed support for Unreal Engine 5.6 and 5.7 only when checked on 2026-11-21. Nothing was bought or
installed.

## Verdict

Verdict: to be written by the controller after review.
