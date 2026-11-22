# Digging spike: results

This page holds the numbers from the digging spike. They decide whether the full digging feature gets built.
Every number in the results tables comes from the same three measurement runs.

## Read this first

- **This was not a packaged game.** The measurements ran in the editor program started as a game (the only way to run
  them in this copy of the project). In that mode some of the renderer's bookkeeping for changed objects runs on the
  game's main thread at the end of each frame; a packaged game does that work elsewhere. A packaged game may
  therefore be faster. These numbers are the cautious reading.
- **Two cases break the 4 ms mark clearly:** digging in a chunk that is already full of holes (about 60 ms of extra
  main-thread work per dig, frames of 65 to 75 ms) and digging where eight chunks meet (about 11 ms per dig, 99 frames
  in 100 under 5.6 to 7.5 ms). Streaming also has a single slow frame of 40 to 46 ms each run when a heavily dug chunk
  comes back. Digging in open ground meets the mark on 99 frames in 100 but not on the worst frame.

## How it was measured

- The game ran with its real renderer, drawn off screen at 1280 x 720, capped at 60 frames a second, on an RTX 5080.
  Another full Unreal editor was running on the same machine the whole time, so the computer was not quiet.
- Hardware ray tracing was on, except where a screenshot turned it off on purpose.
- The test ran three times; each run took about 4.6 minutes (278, 279 and 278 seconds). Before each measurement the
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
- Log files: run 1 `test-084533.log`, run 2 `test-085012.log`, run 3 `test-085450.log` (in `.superpowers/logs/` of the
  digging worktree).

## Results with the renderer on

The 4 ms mark is judged two ways, as the plan document asks: on the worst frame of the window minus idle, and on the
99th percentile (99 frames in 100 at or under this, minus idle). "Not met" rows are listed first.

| What | Run 1 | Run 2 | Run 3 | Pass mark | Result |
|---|---|---|---|---|---|
| Digging in a busy chunk: 99 in 100 / worst frame (above idle) | 63.8 / 71.1 ms | 68.2 / 78.0 ms | 65.8 / 73.1 ms | 4 ms or less | **Not met** on both, all runs |
| Digging at an eight-chunk corner: 99 in 100 / worst frame | 7.5 / 20.7 ms (a) | 5.6 / 26.6 ms (a) | 7.1 / 153.3 ms | 4 ms or less | **Not met** on both, all runs |
| Digging in open ground: 99 in 100 / worst frame | 2.6 / 35.7 ms (a) | 3.2 / 25.8 ms (a) | 2.8 / 231.8 ms (b) | 4 ms or less | Met on 99 in 100; **not met** on the worst frame, all runs |
| Streaming: 99 in 100 / worst frame | 3.0 / 39.7 ms | 2.2 / 41.5 ms | 3.6 / 45.8 ms | 4 ms or less | Met on 99 in 100; **not met** on the worst frame, all runs |
| Collision size per chunk (largest collision mesh) | 10,320 vertices | 10,320 vertices | 10,320 vertices | under 16,384 | Met |
| Seams (missed downward traces out of 500) | 0 | 0 | 0 | no missed traces | Met |
| Navmesh: dig to walkable floor | 0.067 s | 0.067 s | 0.067 s | 1 s or less, no stall | Met; worst frame while it rebuilt 3.1 to 3.5 ms above idle |
| Shadows: render thread / graphics card, average while digging (idle) | 5.5 (5.4) / 2.70 (2.59) ms | 5.7 (5.5) / 2.67 (2.60) ms | 5.2 (5.2) / 2.68 (2.62) ms | frame cost recorded, no flicker | Cost recorded; not judged (flicker) |
| Cave lighting | screenshots | screenshots | screenshots | judged by the owner | For the owner |
| Packaged build | not measured | not measured | not measured | same checks repeated | Not measured |

(a) The worst frame was a garbage collection (the engine cleaning up memory). It is kept in the row.
(b) The worst frame (234 ms) was the frame after a dig call, so it counts as dig-related; nothing else of the dig
happened in it (no chunk update, no collision, no navigation), and the dig call itself took at most 0.04 ms. It was
most likely the machine stalling, but by the rule above it counts.

### The machine's noise level

Frames with no dig-related event and no garbage collection, and the idle windows, reached at most these values above
idle: 11.6, 7.8 and 7.2 ms in the open-ground digging windows, 9.1, 9.8 and 10.9 ms in the streaming windows, and up
to 17.4 ms in the idle windows, with one idle frame of 54.8 ms (run 2, before the busy-chunk test). So on this machine a single frame of about 10 to 17 ms above idle, and once 55 ms, happened
with no digging at all. That is why the 99-in-100 figure is the steadier one; the worst-frame figure is kept as the plan asks.

### Digging in open ground

A character stood at (1800, -1600). The test dug under its feet every 0.1 seconds for 30 seconds: 300 digs, all
changing the ground. For the first 7 to 8 seconds it dug straight down until the character reached the bottom,
27.6 m down; after that it dug out and filled back a small pocket beside it, in turn.

| Whole window, above idle | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Average / middle frame | 0.40 / 0.21 ms | 0.38 / 0.20 ms | 0.52 / 0.21 ms |
| 99 in 100 at or under | 2.6 ms | 3.2 ms | 2.8 ms |
| Worst frame (raw) | 35.7 ms (37.8) | 25.8 ms (27.9) | 231.8 ms (233.9) |
| Worst dig-related frame | 10.1 ms | 9.8 ms | 231.8 ms |
| Cost per dig | 1.9 ms | 1.6 ms | 2.7 ms |

### Digging at an eight-chunk corner

At (2625, 825, -1200), where eight chunks meet, the test dug out and filled back in turn every 0.1 seconds for 10
seconds. Each dig rebuilds all eight chunks.

| Whole window, above idle | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Average / middle frame | 2.0 / 1.7 ms | 1.9 / 1.7 ms | 2.3 / 1.8 ms |
| 99 in 100 at or under | 7.5 ms | 5.6 ms | 7.1 ms |
| Worst frame (raw) | 20.7 ms (22.9) | 26.6 ms (28.6) | 153.3 ms (155.4) |
| Worst dig-related frame | 10.1 ms | 12.3 ms | 153.3 ms |
| Cost per dig | 11.4 ms | 11.1 ms | 13.1 ms |

### Digging in a busy chunk

The buried chunk at X 4225 to 5825, Y -2375 to -775 was first riddled with 512 round holes until its mesh had about
30,000 vertices, split into pieces of at most 10,320. Then the test dug out and filled back one spot inside it every
0.1 seconds for 10 seconds.

| Whole window, above idle | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Average / middle frame | 14.4 / 3.5 ms | 15.7 / 3.6 ms | 15.2 / 3.7 ms |
| 99 in 100 at or under | 63.8 ms | 68.2 ms | 65.8 ms |
| Worst frame (raw) | 71.1 ms (73.2) | 78.0 ms (80.1) | 73.1 ms (75.2) |
| Cost per dig | 58.5 ms | 60.7 ms | 60.2 ms |
| Frames in the 10 seconds | 410 | 392 | 398 |

Each of the 100 digs gave one frame over 16 ms (the logged ones were 40 to 75 ms), and every logged one was the frame
in which the new collision of the chunk's three large pieces finished. The game dropped to about 40 frames a second
while digging. The terrain's own code took little of it (about 2 ms per chunk update, at most 6.9 ms); the time goes
to the engine taking in the new collision, navigation and drawing data for pieces of about 10,000 vertices each. This
is the most important result on the page.

### Streaming

The character was moved (not walked) from one corner of the patch (1100, -2300) to the opposite corner (5700, 2300)
over 20 seconds. Ten chunks were dropped behind it and eleven rebuilt in front of it, in every run.

| Whole window, above idle | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Average / middle frame | 0.23 / 0.04 ms | 0.24 / 0.06 ms | 0.25 / 0.05 ms |
| 99 in 100 at or under | 3.0 ms | 2.2 ms | 3.6 ms |
| Worst frame (raw) | 39.7 ms (41.8) | 41.5 ms (43.6) | 45.8 ms (47.9) |
| Time spent dropping chunks, all ten | 1.1 ms | 1.0 ms | 0.8 ms |

The worst frame in each run was the frame in which the collision of three large pieces finished: the riddled busy
chunk coming back into range.

### Navmesh

A walkable ramp (12 digs at once, from (3600, -1700) down to (3000, -1700, -300)) was dug in each run. From the dig to
the first successful navigation query on the new floor: 0.067 s in all three runs (collision ready after 0.050 s,
walkable 0.017 s later). The worst frame while navigation rebuilt was 3.3, 3.1 and 3.5 ms above idle. No stall.

### Collision size

The largest collision mesh anywhere was 10,320 vertices, from the riddled busy chunk; the 200 random digs of the
collision test alone made smaller meshes. The engine's problem starts above 16,384 vertices per collision mesh, and
the code splits a chunk into pieces of at most 12,000.

### Seams

500 downward traces on the join with the plain ground at X = 1000 and the four chunk borders inside the patch
(X = 2625 and 4225, Y = -775 and 825). None missed, in any run.

### Shadows

A pit at (3000, 0) in sunlight, seen by a fixed camera, with a dig every 0.1 seconds along its sunlit rim for 10
seconds (100 digs). The render thread and the graphics card each rose by about 0.1 ms on average while digging. On the
game thread, the worst frame minus the worst idle frame was 3.7, -2.7 and 123.7 ms (run 3 had one 131 ms frame with one
chunk update in it). Flicker was not judged: nobody watched the game running.

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
