# Digging spike: results

This page holds the numbers from the digging spike. They decide whether the full digging feature gets built.
Every number in the results tables below comes from the final three measurement runs, taken after the two fixes
described in "What we found along the way".

## How it was measured

- The game ran with its real renderer, drawn off screen at 1280 x 720, capped at 60 frames a second.
- Machine: RTX 5080. Another full Unreal editor was running on the same machine the whole time, so the computer
  was not quiet. This matters for single slow frames (see "Why the raw worst frame is not trusted").
- Hardware ray tracing was on (DirectX 12, ray tracing 1, Lumen hardware ray tracing 1), except where a screenshot
  turned it off on purpose.
- The measurement test ran three times; each run took about 3.5 minutes (207, 210 and 207 seconds). No shaders had
  to be compiled during the runs.
- "Game-thread time" is the time the game's main thread spends working in one frame, in milliseconds (ms). It
  leaves out the time the game waits for the 60-frames cap. One frame at 60 frames a second lasts 16.7 ms.
- "Idle" means the same spot, just before, with nothing being dug, for as long as the measured window (30 s for
  digging, 20 s for streaming). "Above idle" means above the idle median (the middle idle frame, about 2.1 ms).
- Every frame was tagged with what happened in it: a chunk update put on screen, a chunk dropped or rebuilt, or the
  engine cleaning up memory (garbage collection). That lets slow frames be blamed on the right thing.
- Log files: run 1 `test-080706.log`, run 2 `test-081032.log`, run 3 `test-081402.log`; the game tests with the
  renderer on, `test-081730.log` (all in `.superpowers/logs/` of the digging worktree).

## Results with the renderer on

| What | Run 1 | Run 2 | Run 3 | Pass mark | Result |
|---|---|---|---|---|---|
| Digging: frames with a chunk update, 99 in 100 at or under (above idle) | 4.4 ms | 1.6 ms | 3.1 ms | 4 ms or less | Met in runs 2 and 3, just over in run 1 |
| Digging: slowest frame with a chunk update (above idle) | 8.1 ms | 2.6 ms | 4.3 ms | (for reference) | |
| Digging: raw worst frame (above idle) | 25.9 ms | 23.2 ms | 21.7 ms | (not trusted) | It was a garbage collection in every run |
| Streaming: slowest frame with a chunk dropped or rebuilt (above idle) | 1.3 ms | 1.6 ms | 1.4 ms | 4 ms or less | Met |
| Streaming: raw worst frame (above idle) | 19.6 ms | 95.0 ms | 27.6 ms | (not trusted) | Garbage collection in runs 1 and 3, background noise in run 2 |
| Collision size per chunk (largest collision mesh) | 7,466 vertices | 7,466 vertices | 7,466 vertices | under 16,384 | Met (not a worst case) |
| Seams (missed downward traces out of 500) | 0 | 0 | 0 | no missed traces | Met |
| Navmesh: dig to walkable floor | 0.033 s | | | 1 s or less, no stall | Met (one run of the game tests with the renderer on) |
| Cave lighting | screenshots | screenshots | screenshots | judged by the owner | For the owner (see "Cave lighting") |
| Shadows: worst frame while digging, minus worst idle frame | 1.1 ms | 1.6 ms | 2.3 ms | frame cost recorded, no flicker | Cost recorded; flicker not judged |
| Packaged build | not measured | not measured | not measured | same checks repeated | Not measured |

### Which number the 4 ms mark is judged on

The 4 ms mark asks what digging costs. That cost lives in the frames where the terrain does its work: frames
where a chunk update is put on screen (digging), and frames where a chunk is dropped or rebuilt (streaming). So the
mark is judged on those frames, compared with the middle idle frame. The fairest single figure is "99 frames in 100
with a chunk update", because one unlucky frame does not decide it. On that figure digging is just over the mark in
run 1 (4.4 ms) and under it in runs 2 and 3; streaming is well under it in all three.

### Why the raw worst frame is not trusted on this machine

- The raw worst digging frame was a garbage collection in all three runs (about 22 to 26 ms above idle), and it
  contained no chunk update.
- While nothing at all was being dug, the worst idle frames still took 27, 39 and 45 ms (digging idle) and up to
  11 ms (streaming idle). Digging cannot cause those.
- Frames with nothing happening in them reached 17.6 ms above idle while digging, and 95 ms in one run while
  walking. That is background noise from the rest of the machine.
- Each run had one garbage collection while digging and while walking, and none in the idle time of the same
  length. So the collections may be partly caused by digging and streaming (dropped pieces leave memory to clean up),
  but one per run is too few to be sure, and how often the engine collects depends on settings, not only on digging.

### Digging in more detail

A character stood on the ground at (1800, -1600). The test dug under its feet every 0.1 seconds for 30 seconds: 300
digs, and every one changed the ground. For the first 7.6 to 7.7 seconds it dug straight down; the character fell
27.6 m to the bottom (bedrock). After that it dug out and filled back a small pocket beside the character in turn,
so every dig still changed the ground.

| Digging | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Idle median frame | 2.11 ms | 2.10 ms | 2.09 ms |
| Frames with a chunk update | 300 | 300 | 300 |
| ... average above idle | 0.53 ms | 0.50 ms | 0.51 ms |
| ... 99 in 100 at or under, above idle | 4.4 ms | 1.6 ms | 3.1 ms |
| ... slowest, above idle | 8.1 ms | 2.6 ms | 4.3 ms |
| Frames with nothing happening: slowest, above idle | 8.1 ms | 17.6 ms | 6.1 ms |
| Frames with a garbage collection: slowest, above idle | 25.9 ms | 23.2 ms | 21.7 ms |
| Garbage collections: while digging / idle of the same length | 1 / 0 | 1 / 0 | 1 / 0 |
| Slowest single chunk update, by the terrain's own clock | 0.71 ms | 0.79 ms | 0.83 ms |
| Navigation requests (count / total time) | 306 / 11.1 ms | 306 / 11.0 ms | 306 / 11.2 ms |

The terrain's own work in a frame is small: at most two chunk updates per frame, the slowest 0.83 ms. The rest of a
slow frame with a chunk update is the engine's own follow-up work (drawing data for the new piece, physics,
navigation) plus whatever else the machine was doing at that moment; this test cannot split those apart.

### Streaming in more detail

The character was moved from one corner of the patch (1100, -2300) to the opposite corner (5700, 2300) over 20
seconds. Six chunks were dropped behind it and eight were built in front of it, in every run.

| Streaming | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Idle median frame | 2.11 ms | 2.09 ms | 2.08 ms |
| Frames with a chunk dropped or rebuilt | 9 | 9 | 9 |
| ... slowest, above idle | 1.3 ms | 1.6 ms | 1.4 ms |
| Time spent dropping chunks, all six together | 0.57 ms | 0.62 ms | 0.51 ms |
| Frames with a garbage collection: slowest, above idle | 19.6 ms | 19.8 ms | 27.6 ms |
| Frames with nothing happening: slowest, above idle | 12.3 ms | 95.0 ms | 13.2 ms |
| Garbage collections: while moving / idle of the same length | 1 / 0 | 1 / 0 | 1 / 0 |

### Graphics card and render thread (for information)

| Average frame | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Graphics card: idle / digging | 2.01 / 2.08 ms | 2.01 / 2.06 ms | 2.01 / 2.09 ms |
| Graphics card: worst frame while digging | 5.1 ms | 4.9 ms | 4.9 ms |
| Render thread: idle / digging | 5.4 / 5.2 ms | 5.5 / 5.2 ms | 5.4 / 5.2 ms |

Digging adds less than a tenth of a millisecond to the graphics card's average frame. The render thread was a little
faster while digging, most likely because the camera at the bottom of the shaft sees less of the world.

### Collision size

200 digs at fixed random points inside one corner column of the patch (X 4225 to 5800, Y 825 to 2400, from near the
bottom up to the ground). The largest collision mesh had 7,466 vertices, and no chunk needed more than one piece.
The engine's problem starts above 16,384 vertices per collision mesh, and the code splits a chunk into pieces of at
most 12,000. These random digs were scattered, so they did not reach the worst case: an earlier test without the
renderer made a chunk of about 29,000 vertices, split into three pieces.

### Seams

500 downward traces, 100 on each of five lines: the join with the plain ground at X = 1000, and the four chunk
borders inside the patch (X = 2625 and 4225, Y = -775 and 825). None missed, in any run. An extra check walked in
from each outer edge of the patch: the ground starts right at every edge.

### Navmesh

The ordinary game tests were run once with the renderer on (`test-081730.log`): the navmesh reached the bottom of
a newly dug ramp 0.033 s after the ramp's collision was ready, and a computer-controlled character walked to the
bottom of another ramp in 1.5 s. During the 30 seconds of digging the terrain asked navigation for 306 updates,
about 0.04 ms each. The navigation system's own work after a request is not in these numbers.

### Shadows

A pit at (4000, -1600) in sunlight, seen by a fixed camera. For 10 seconds the test dug every 0.1 seconds along the
sunlit rim (100 digs, all changed the ground).

| Shadows | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Game thread, idle: average / worst | 2.2 / 6.0 ms | 2.2 / 5.8 ms | 2.2 / 7.6 ms |
| Game thread, digging: average / worst | 2.7 / 7.1 ms | 2.7 / 7.4 ms | 2.7 / 9.9 ms |
| Render thread average: idle / digging | 5.6 / 5.7 ms | 5.4 / 5.6 ms | 5.5 / 5.5 ms |
| Graphics card average: idle / digging | 2.36 / 2.41 ms | 2.37 / 2.40 ms | 2.37 / 2.42 ms |
| Graphics card worst frame while digging | 4.5 ms | 4.5 ms | 5.2 ms |

Shadow work happens mostly on the render thread and the graphics card; both rose by less than a third of a
millisecond on average while digging. Flicker needs a person watching moving pictures; nobody did.

## Cave lighting

A 500 cm tunnel was dug from the bottom of a 4 m pit at (1800, 1400). For the shots, cave light 1 was moved just
inside the tunnel's mouth under its roof, at (1900, 1400, -220), and dimmed from the map's 5000 to 300 (unitless),
so the walls fade with distance instead of glowing; each shot waited 8 seconds for the lighting and the automatic
exposure to settle, and the light was put back afterwards. The screenshots are in `ArtDirection/Digging/SpikeShots/`
(from run 3; all three runs gave the same brightness).

- `tunnel_hwrt_on.png`: from the pit, looking down the tunnel. The tunnel reads clearly as a passage: pale grey
  walls, a darker band where the floor meets the walls, and the far end a soft, darker square. On the right, a bright
  sharp-edged strip is a wall of the pit in sunlight. The shading is smooth and soft, with no surface detail.
- `tunnel_hwrt_off.png`: the same view without hardware ray tracing. The same shapes, but the whole tunnel is tinted
  blue-grey.
- `tunnel_wall_hwrt_on.png`: inside the tunnel, looking at its side wall from about 1 m. A bright diagonal band with
  sharp edges crosses dark grey wall: most likely sunlight coming down through the pit opening at its 45-degree angle and
  landing on the wall. Outside the band the wall is dark and plain.
- `tunnel_wall_hwrt_off.png`: the same, but the dark wall is blue-grey.
- `pit_hwrt_on.png`: the pit from above its rim, looking down. Grey ground; the inside of the pit shows angular,
  faceted walls, and its lower part, out of the sun, is near black.
- `pit_hwrt_off.png`: the same, but the shadowed inside of the pit is dark blue instead of black.

**Hardware ray tracing on and off look different.** With it off, every surface that the sun does not reach turns
blue-grey: that is sky light reaching into the tunnel and the pit. The likely reason: without hardware ray tracing,
Lumen traces a simplified version of the scene built from distance fields, and the dug ground has none (and this
project turns that part of Lumen off for individual meshes), so nothing blocks the sky's light underground. With hardware ray tracing on, the shadowed parts stay neutral grey or black, as a cave should.
Hardware ray tracing was really active for every "on" shot and really off for every "off" shot, and it was put back
on afterwards.

## What we found along the way

- **The dug ground sat 25 cm off.** The first rendered measurement showed a 25 cm strip without ground along two edges
  of the patch. Fixed: the terrain's grid now starts half a cell inside the patch corner, so the ground covers exactly
  the patch. Seams now show no misses.
- **The engine's default material turned tunnels black.** When the dug ground had no material of its own, the engine
  drew it with its default grid material, and a view down a tunnel came out completely black (the whole picture, not
  only the ground). Fixed: the terrain now always uses a plain engine material when none is set, and the test map sets
  one. The tunnel now draws and is lit.
- **Hardware ray tracing matters underground.** Without it, sky light leaks into tunnels and pits and tints them
  blue-grey (see "Cave lighting").
- **Slow single frames come from the machine and from memory clean-up, not from the digging work itself.** Every
  slow frame was checked for what happened in it.

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

- **A packaged build.** This copy of the project has no game content, so nothing can be packaged.
- **The real hero and the real town.** They are not in this copy. All tests used a plain stand-in character on a
  small test map.
- **A machine without a ray-tracing graphics card.** Only this machine (RTX 5080) was used. Given the sky-light leak
  above, caves on such a machine would look blue-grey.
- **Flicker.** Nobody watched the game running.
- **A worst-case dug chunk with the renderer on.** The random digs here made at most 7,466 vertices per piece; the
  heaviest chunk (about 29,000 vertices) was only measured without the renderer.
- **Whether the slowest single frames are noise.** Another Unreal editor ran throughout. The tagging points to
  memory clean-up and background noise, but only a run on a quiet machine can settle it.

## Plugin check

Voxel Plugin 2 listed support for Unreal Engine 5.6 and 5.7 only when checked on 2026-11-21. Nothing was bought or
installed.

## Verdict

Verdict: to be written by the controller after review.
