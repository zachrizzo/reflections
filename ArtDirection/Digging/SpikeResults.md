# Digging spike: results

This page holds the numbers from the digging spike. They decide whether the full digging feature gets built.
Every number in the results tables comes from the same four measurement runs, except the table "Before the
navigation fix", which keeps the figures of the three runs before them.

## Read this first

- **This was not a packaged game.** The measurements ran in the editor program started as a game (the only way to run
  them in this copy of the project). Nothing measured here says whether a packaged game would be faster or slower.
- **The spike's gate is not passed as measured.** On these numbers the heavily dug chunk and the eight-chunk corner do
  not meet the 4 ms mark on either figure in any run, no row meets it on the worst frame, and the navmesh row does not
  meet "no stall" in run 1.
- **Two cases miss the 4 ms mark on 99 frames in 100:** digging in a chunk that is already full of holes (5.3 to
  10.3 ms of extra main-thread work per dig, 99 frames in 100 under 4.4 to 9.1 ms, worst frames of 7.1 to 15.4 ms) and
  digging where eight chunks meet (7.8 to 9.5 ms per dig, 99 frames in 100 under 4.2 to 5.5 ms, worst frames of 19.4 to
  28.1 ms). Digging in open ground and streaming meet the mark on 99 frames in 100 (1.6 to 2.6 ms and 1.1 to 1.8 ms) but
  not on the worst frame (14.5 to 862.1 ms and 16.9 to 42.4 ms).
- **Two things changed since the three runs before these:** navigation no longer builds collision on the game thread,
  and the engine's embedded web browser is switched off for the measurement. The earlier figures are in "Before the
  navigation fix".
- **The parts the test times** (the terrain's chunk updates and clean-up of old pieces, the engine's swap-in of the new
  collision, the navigation update) add up to 24 to 36 percent of the busy chunk's cost and 29 to 31 percent of the
  corner's. See "Where the cost of a heavy dig goes".

## How it was measured

- The game ran with its real renderer, drawn off screen at 1280 x 720, capped at 60 frames a second, on an RTX 5080.
  Another full Unreal editor was running on the same machine the whole time, so the computer was not quiet.
- Hardware ray tracing was on, except where a screenshot turned it off on purpose.
- **The engine's embedded web browser was switched off for these runs** (the command line option `-nocef`). A traced
  run before them (`test-110014.log`) showed that every remaining stall was the tick of the engine's embedded web
  browser (56, 65, 63 and 215 ms, in frames with no dig work in them; 0.93 s over the run). The browser is loaded by the
  editor tooling plugin `UnrealCanvasBridge`, not by the game. The engine still loads the browser's library at start
  (the log line `LogWebBrowser: Loaded CEF3` is in every run), but the browser itself did not start (no `LogCEFBrowser`
  line, which the earlier runs have).
- The test ran four times, and all four runs are shown; each run took about 4.6 minutes (274, 272, 287 and 278 seconds
  from the log's first line to its last). Before each measurement the test waited until no shaders were being
  compiled, the terrain was settled and navigation was not rebuilding.
- **Game-thread time** is the time the game's main thread spends working in one frame, in milliseconds (ms). It leaves
  out time the main thread spends waiting: for the 60-frames cap, and for other threads (the renderer, the graphics
  card, background tasks). One frame at 60 frames a second lasts 16.7 ms.
- **Above idle** means above the middle idle frame of the same run (about 2 ms, 1.85 to 2.26 ms), measured at the same
  spot just before, with nothing being dug, for as long as the measured window.
- **Whole window**: every frame of the measured time counts, not only selected frames. Most of what a dig costs lands
  in the frames after the dig (the new collision finishing, navigation, the renderer's data), so only the whole window
  shows the full cost.
- **Cost per dig**: the extra main-thread time of the whole window divided by the number of digs.
- Each frame was also tagged with what happened in it or in the frame before (a dig, a chunk put on screen, a collision
  finishing, a navigation update, a chunk dropped or rebuilt) and whether the engine cleaned up memory (garbage
  collection). Frames with none of these are "background": that is the only place the machine's noise is read from.
- In every measured window of every run, no piece's collision was built on the game thread by anyone else
  (`game_thread_cooks=0`).
- Log files: run 1 `test-111229.log`, run 2 `test-111733.log`, run 3 `test-112230.log`, run 4 `test-112757.log` (in
  `.superpowers/logs/` of the digging worktree). The numbers were read with `Tools/Digging/summarize_spike_log.py`.

## Results with the renderer on

The 4 ms mark is judged two ways, as the plan document asks: on the worst frame of the window minus idle, and on the
99th percentile (99 frames in 100 at or under this, minus idle). "Not met" rows are listed first.

| What | Run 1 | Run 2 | Run 3 | Run 4 | Pass mark | Result |
|---|---|---|---|---|---|---|
| Digging in a busy chunk: 99 in 100 / worst frame (above idle) | 5.0 / 7.1 ms | 4.4 / 7.6 ms | 4.9 / 10.1 ms | 9.1 / 15.4 ms | 4 ms or less | **Not met** on both, all runs |
| Digging at an eight-chunk corner: 99 in 100 / worst frame | 4.9 / 28.1 ms | 5.5 / 27.8 ms | 4.2 / 19.4 ms (a) | 5.0 / 24.9 ms (a) | 4 ms or less | **Not met** on both, all runs |
| Digging in open ground: 99 in 100 / worst frame | 2.2 / 64.0 ms (b) | 2.1 / 20.8 ms (a) | 1.6 / 862.1 ms (d) | 2.6 / 14.5 ms (a) | 4 ms or less | Met on 99 in 100; **not met** on the worst frame, all runs |
| Streaming: 99 in 100 / worst frame | 1.8 / 22.1 ms (a) | 1.5 / 42.4 ms (c) | 1.2 / 20.1 ms (a) | 1.1 / 16.9 ms (a) | 4 ms or less | Met on 99 in 100; **not met** on the worst frame, all runs |
| Navmesh: dig to walkable floor | 0.126 s | 0.067 s | 0.067 s | 0.067 s | 1 s or less, no stall | Met on time, all runs; no stall: met in runs 2, 3 and 4, **not met** in run 1 (one frame 73.2 ms above idle (b)) |
| Collision size per chunk (largest collision mesh) | 10,320 vertices | 10,320 vertices | 10,320 vertices | 10,320 vertices | under 16,384 | Met |
| Seams (missed downward traces out of 500) | 0 | 0 | 0 | 0 | no missed traces | Met |
| Shadows: render thread / graphics card, average while digging (idle) | 4.7 (4.8) / 2.64 (2.59) ms | 4.7 (4.9) / 2.53 (2.49) ms | 4.4 (4.5) / 2.64 (2.56) ms | 4.5 (4.4) / 2.59 (2.54) ms | frame cost recorded, no flicker | Cost recorded; not judged (flicker) |
| Cave lighting | screenshots | screenshots | screenshots | screenshots | judged by the owner | For the owner |
| Packaged build | not measured | not measured | not measured | not measured | same checks repeated | Not measured |

(a) The worst frame was a garbage collection (the engine cleaning up memory). It is kept in the row.
(b) No chunk update, collision finishing or navigation update happened in the worst frame; it counts as dig-related
only because a dig call was counted into it or the frame before was dig-related. By the rule above it counts.
(c) The worst frame was a background frame: no dig-related event and no garbage collection in it or the frame before.
It is kept in the row.
(d) In the worst frame a collision finished and a navigation update ran, and the frame before was dig-related. It is
kept in the row.

### Before the navigation fix

The same four rows from the three runs before these (run 1 `test-090807.log`, run 2 `test-091247.log`, run 3
`test-091739.log`), when navigation still built collision on the game thread and the embedded web browser was still on.

| 99 in 100 / worst frame (above idle), cost per dig | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Digging in a busy chunk | 60.2 / 63.5 ms, 58.8 ms | 67.5 / 88.6 ms, 61.2 ms | 61.1 / 75.8 ms, 57.8 ms |
| Digging at an eight-chunk corner | 8.8 / 392.8 ms (b), 15.1 ms | 6.5 / 22.5 ms, 11.0 ms | 7.9 / 44.3 ms (a), 11.1 ms |
| Digging in open ground | 2.2 / 22.0 ms (a), 1.6 ms | 2.7 / 24.4 ms (a), 1.5 ms | 2.4 / 45.4 ms (d), 1.5 ms |
| Streaming (no digs) | 2.7 / 51.3 ms | 2.9 / 64.8 ms | 2.8 / 42.4 ms |

### The machine's noise level

Frames with no dig-related event and no garbage collection reached at most 3.2, 1.9, 367.6 and 6.5 ms above idle in
the open-ground digging windows and 3.3, 42.4, 2.8 and 4.1 ms in the streaming windows. The idle windows (same spot,
nothing being dug) reached 896, 112 and 119 ms (runs 1 to 3) and 13 ms (run 4) in the open-ground test and up to 30 ms
in the other tests. So on this machine a single frame of tens of milliseconds, and four times over 100 ms, happened
with no digging at all. That is why the 99-in-100 figure is the steadier one; the worst-frame figure is kept as the
plan asks.

### Digging in open ground

A character stood at (1800, -1600). The test dug under its feet every 0.1 seconds for 30 seconds: 300 digs, all
changing the ground. For the first 7.7 seconds it dug straight down until the character reached the bottom,
27.7 m down; after that it dug out and filled back a small pocket beside it, in turn.

| Whole window, above idle | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|
| Average / middle frame | 0.34 / 0.19 ms | 0.34 / 0.23 ms | 0.93 / 0.14 ms | 0.27 / 0.15 ms |
| 99 in 100 at or under | 2.2 ms | 2.1 ms | 1.6 ms | 2.6 ms |
| Worst frame (raw) | 64.0 ms (66.0) | 20.8 ms (22.9) | 862.1 ms (864.0) | 14.5 ms (16.4) |
| Worst dig-related frame | 64.0 ms | 12.8 ms | 862.1 ms | 6.0 ms |
| Cost per dig | -1.4 ms | 1.2 ms | 4.7 ms | 1.1 ms |

### Digging at an eight-chunk corner

At (2625, 825, -1200), where eight chunks meet, the test dug out and filled back in turn every 0.1 seconds for 10
seconds. Each dig rebuilds all eight chunks.

| Whole window, above idle | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|
| Average / middle frame | 1.6 / 1.4 ms | 1.6 / 1.4 ms | 1.3 / 1.2 ms | 1.5 / 1.2 ms |
| 99 in 100 at or under | 4.9 ms | 5.5 ms | 4.2 ms | 5.0 ms |
| Worst frame (raw) | 28.1 ms (30.1) | 27.8 ms (29.8) | 19.4 ms (21.3) | 24.9 ms (26.8) |
| Worst dig-related frame | 28.1 ms | 27.8 ms | 19.3 ms | 9.5 ms |
| Cost per dig | 9.5 ms | 9.3 ms | 7.8 ms | 8.2 ms |

### Digging in a busy chunk

The buried chunk at X 4225 to 5825, Y -2375 to -775 was first riddled with 512 round holes until its mesh had about
29,700 vertices, split into three pieces of at most 10,320. Then the test dug out and filled back one spot inside it
every 0.1 seconds for 10 seconds.

| Whole window, above idle | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|
| Average / middle frame | 1.2 / 0.8 ms | 1.0 / 0.6 ms | 1.0 / 0.6 ms | 1.8 / 1.2 ms |
| 99 in 100 at or under | 5.0 ms | 4.4 ms | 4.9 ms | 9.1 ms |
| Worst frame (raw) | 7.1 ms (9.1) | 7.6 ms (9.5) | 10.1 ms (12.2) | 15.4 ms (17.7) |
| Cost per dig | 6.6 ms | 5.5 ms | 5.3 ms | 10.3 ms |
| Frames in the 10 seconds | 601 | 601 | 601 | 601 |

The game held 60 frames a second while digging. Where that time goes is the next section.

## Where the cost of a heavy dig goes

For the busy chunk and the corner, the test also timed the terrain's own work, piece by piece, and compared it with
the whole window's extra main-thread time:

- **chunk updates**: the terrain putting new meshes on its pieces and starting their new collision;
- **swap check**: the terrain retiring and destroying old pieces;
- **collision finishing**: the engine's own work when a piece's new collision is ready (swapping it in);
- **navigation**: the terrain telling navigation about the new collision;
- **rest**: everything else in those frames. The test cannot see inside it.

| Total over the 10-second window, 100 digs | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|
| **Busy chunk**: whole window, extra main-thread time | 660 ms | 554 ms | 534 ms | 1,033 ms |
| ... chunk updates / swap check | 160 / 14 ms | 156 / 13 ms | 156 / 14 ms | 195 / 19 ms |
| ... collision finishing / navigation | 18 / 3 ms | 17 / 3 ms | 17 / 3 ms | 26 / 5 ms |
| ... rest, in the frame right after a chunk update | 260 ms | 234 ms | 237 ms | 394 ms |
| ... rest, all other frames | 205 ms | 131 ms | 106 ms | 394 ms |
| **Corner**: whole window, extra main-thread time | 950 ms | 929 ms | 776 ms | 825 ms |
| ... chunk updates / swap check | 191 / 8 ms | 180 / 7 ms | 166 / 7 ms | 174 / 7 ms |
| ... collision finishing / navigation | 62 / 16 ms | 62 / 17 ms | 54 / 14 ms | 55 / 15 ms |
| ... rest, in the frames with a chunk update | 396 ms | 365 ms | 284 ms | 318 ms |
| ... rest, in the frame right after | 170 ms | 176 ms | 151 ms | 162 ms |
| ... rest, all other frames | 107 ms | 123 ms | 99 ms | 93 ms |

The controller's explanation of the heavy-dig cost follows.

### Streaming

The character was moved (not walked) from one corner of the patch (1100, -2300) to the opposite corner (5700, 2300)
over 20 seconds. Ten chunks were dropped behind it and eleven rebuilt in front of it, in every run.

| Whole window, above idle | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|
| Average / middle frame | 0.06 / -0.03 ms | 0.15 / 0.04 ms | -0.00 / -0.06 ms | 0.04 / -0.02 ms |
| 99 in 100 at or under | 1.8 ms | 1.5 ms | 1.2 ms | 1.1 ms |
| Worst frame (raw) | 22.1 ms (24.1) | 42.4 ms (44.5) | 20.1 ms (22.1) | 16.9 ms (18.8) |
| Time spent dropping chunks, all ten | 0.9 ms | 1.0 ms | 0.9 ms | 0.8 ms |

The worst dig-related frame (a chunk dropped, rebuilt or its collision finishing, or the frame after) was 1.8, 3.0,
5.0 and 2.8 ms above idle.

### Navmesh

A walkable ramp (12 digs at once, from (3600, -1700) down to (3000, -1700, -300)) was dug in each run. From the dig to
the first successful navigation query on the new floor: 0.126, 0.067, 0.067 and 0.067 s (collision ready after
0.050 s, walkable 0.017 to 0.076 s later). The worst frame while navigation rebuilt was 73.2, 1.3, 1.0 and 1.5 ms
above idle; in run 1 that frame was the frame after a dig-related frame, and no chunk update, collision finishing or
navigation update happened in it (note (b)).

### Collision size

The largest collision mesh anywhere was 10,320 vertices, from the riddled busy chunk. The engine's problem starts
above 16,384 vertices per collision mesh, and the code splits a chunk into pieces of at most 12,000.

### Seams

500 downward traces on the join with the plain ground at X = 1000 and the four chunk borders inside the patch
(X = 2625 and 4225, Y = -775 and 825). None missed, in any run.

### Shadows

A pit at (3000, 0) in sunlight, seen by a fixed camera, with a dig every 0.1 seconds along its sunlit rim for 10
seconds (100 digs). The render thread and the graphics card each changed by at most 0.2 ms on average while
digging. On the game thread, the worst frame minus the worst idle frame was 1.4, 3.0, -1.2 and 61.5 ms; run 4's worst
frame (66.6 ms raw) had no dig-related event and no garbage collection in it or the frame before. Flicker was not judged:
nobody watched the game running.

### Graphics card (for information)

Average graphics-card time per frame was about 1.8 to 2.6 ms in every window, and digging added at most about 0.1 ms
to it. The graphics card is far from being the limit here.

## Cave lighting

A 500 cm tunnel was dug from the bottom of a 4 m pit at (1800, 1400). For the shots only, cave light 1 was moved just
inside the tunnel's mouth, under its roof, at (1900, 1400, -220), and dimmed from 5000 to 300 (unitless); each shot
waited 8 seconds for the lighting and the exposure to settle, and the light was put back afterwards. The screenshots
are in `ArtDirection/Digging/SpikeShots/` (from run 3 of the runs before these, `test-091739.log`; every run, before
and after, gave the same brightness to within 0.1 out of 255).

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
most likely sky light reaching underground. The likely reason is that without hardware ray tracing the lighting system works from
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
- **Hardware ray tracing matters underground.** Without it, tunnels and pits are lit brighter and blue-grey, most likely
  by sky light leaking in (see "Cave lighting").
- **Heavily dug chunks.** Each change to a chunk of about 29,700 vertices costs 5.3 to 10.3 ms on the main thread, and
  99 frames in 100 stay under 4.4 to 9.1 ms above idle while digging in it.

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

- **A packaged build.** This copy of the project has no game content, so nothing can be packaged. Nothing measured
  here says whether a packaged game would be faster or slower.
- **The real hero and the real town.** They are not in this copy. All tests used a plain stand-in character on a small
  test map.
- **A machine without a ray-tracing graphics card.** Only this machine (RTX 5080) was used. Given the sky-light leak
  above, caves on such a machine would likely look blue-grey.
- **Flicker.** Nobody watched the game running.
- **A quiet machine.** Another Unreal editor was running throughout, and idle frames alone (nothing being dug) reached
  112 and 119 ms and once 896 ms above idle. A quiet machine is needed to bound single slow frames.

## Plugin check

Voxel Plugin 2 listed support for Unreal Engine 5.6 and 5.7 only when checked on 2026-11-21. Nothing was bought or
installed.

## Verdict

Verdict: to be written by the controller after review.
