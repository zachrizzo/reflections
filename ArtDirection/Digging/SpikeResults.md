# Digging spike: results

This page holds the numbers from the digging spike. They decide whether the full digging feature gets built.

## How it was measured

- The game ran with its real renderer, drawn off screen at 1280 x 720, capped at 60 frames a second.
- Machine: RTX 5080. Another full Unreal editor was running on the same machine the whole time, so the
  computer was not quiet. This matters for single slow frames (see "Why the raw worst frame is not trusted").
- Hardware ray tracing was on (DirectX 12, ray tracing 1, Lumen hardware ray tracing 1), except where a
  screenshot turned it off on purpose.
- The measurement test ran three times. Each run took about 3.3 minutes (199, 199 and 200 seconds). No shaders
  had to be compiled during the runs.
- "Game-thread time" is the time the game's main thread spends working in one frame, in milliseconds (ms). It
  leaves out the time the game waits for the 60-frames cap. One frame at 60 frames a second lasts 16.7 ms.
- "Idle" means the same spot, just before, with nothing being dug, for as long as the measured window (30 s for
  digging, 20 s for streaming). "Above idle" means above the idle median (the middle idle frame, about 2.1 ms).
- Every frame was tagged with what happened in it: a chunk update put on screen, a chunk dropped or rebuilt, or the
  engine cleaning up memory (garbage collection). That lets the slow frames be blamed on the right thing.
- Log files: run 1 `test-073024.log`, run 2 `test-073343.log`, run 3 `test-073702.log`
  (in `.superpowers/logs/` of the digging worktree).

## Results with the renderer on

| What | Run 1 | Run 2 | Run 3 | Pass mark | Result |
|---|---|---|---|---|---|
| Digging: frames with a chunk update, 99 in 100 at or under (above idle) | 2.8 ms | 1.8 ms | 1.7 ms | 4 ms or less | Met |
| Digging: slowest frame with a chunk update (above idle) | 12.0 ms | 27.1 ms | 2.3 ms | (for reference) | Over in runs 1 and 2, see below |
| Digging: raw worst frame (above idle) | 12.0 ms | 27.1 ms | 6.9 ms | (not trusted) | |
| Streaming: slowest frame with a chunk dropped or rebuilt (above idle) | 1.2 ms | 1.9 ms | 1.2 ms | 4 ms or less | Met |
| Streaming: raw worst frame (above idle) | 24.8 ms | 63.6 ms | 25.3 ms | (not trusted) | |
| Collision size per chunk (largest collision mesh) | 7,466 vertices | 7,466 vertices | 7,466 vertices | under 16,384 | Met (not a worst case) |
| Seams (missed downward traces out of 500) | 0 | 0 | 0 | no missed traces | Met |
| Navmesh: dig to walkable floor | 0.033 s | | | 1 s or less, no stall | Met (one renderer run) |
| Cave lighting | screenshots | screenshots | screenshots | judged by the owner | For the owner; judge the "plain material" tunnel shots (the default material makes the tunnel view black, see below) |
| Shadows: worst frame while digging (minus worst idle frame) | 9.3 ms | 13.5 ms | 1.5 ms | frame cost recorded, no flicker | Cost recorded; flicker not judged |
| Packaged build | not measured | not measured | not measured | same checks repeated | Not measured |

### Which number the 4 ms mark should be judged on

The 4 ms mark asks what digging costs. That cost lives in the frames where the terrain does its digging work:
the frames where a chunk update is put on screen (digging) and where a chunk is dropped or rebuilt (streaming).
So the mark should be judged on those frames, compared with a quiet idle frame. The best single figure is
"99 frames in 100 with a chunk update", because it is not decided by one unlucky frame.

### Why the raw worst frame is not trusted on this machine

- While nothing was being dug at all, the worst idle frames took 23, 28 and 29 ms (digging), and 11, 128 and
  47 ms (streaming). Digging cannot cause those.
- Frames with a garbage collection took up to 25 ms above idle. In the digging window there were none; in the
  idle window of the same length there was one in each run. So the collection is not caused by digging either.
- Frames with nothing at all happening in them still reached 10.6 ms above idle while digging and 63.6 ms
  while walking. That is the background noise from the rest of the machine.
- The slowest frame with a chunk update in run 2 (27.1 ms above idle) contained one chunk update that took
  0.27 ms by the terrain's own clock. The remaining 27 ms came from somewhere else in the same frame.

### Digging in more detail

A character stood on the ground at (1800, -1600). The test dug under its feet every 0.1 seconds for 30 seconds:
300 digs, and every one changed the ground. For the first 7.6 seconds it dug straight down; the character fell
27.6 m to the bottom (bedrock). After that it dug out and filled back a small pocket beside the character in
turn, so every dig still changed the ground.

| Digging | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Idle median frame | 2.08 ms | 2.06 ms | 2.08 ms |
| Frames with a chunk update | 300 | 300 | 300 |
| ... average above idle | 0.50 ms | 0.56 ms | 0.42 ms |
| ... 99 in 100 at or under, above idle | 2.8 ms | 1.8 ms | 1.7 ms |
| ... slowest, above idle | 12.0 ms | 27.1 ms | 2.3 ms |
| Frames with nothing happening: slowest, above idle | 9.8 ms | 10.6 ms | 6.9 ms |
| Garbage collections: while digging / idle of the same length | 0 / 1 | 0 / 1 | 0 / 1 |
| Slowest single chunk update, by the terrain's own clock | 1.10 ms | 1.05 ms | 0.75 ms |
| Navigation requests (count / total time) | 306 / 11.5 ms | 306 / 11.8 ms | 306 / 11.3 ms |
| Graphics card, average frame: idle / digging | 1.71 / 1.80 ms | 1.71 / 1.81 ms | 1.70 / 1.82 ms |

Runs 1 and 2 each had one frame with a chunk update that was well over 4 ms above idle. The terrain's own work in
any frame was never more than about 2 ms (at most two chunk updates per frame, the slowest 1.10 ms), and frames
with nothing happening in them were nearly as slow. So these single frames look like the machine's background
noise landing on a digging frame, but this test cannot prove that for each frame.

### Streaming in more detail

The character was moved from one corner of the patch (1100, -2300) to the opposite corner (5700, 2300) over
20 seconds. Six chunks were dropped behind it and eight were built in front of it, in every run.

| Streaming | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Idle median frame | 2.06 ms | 2.06 ms | 2.08 ms |
| Frames with a chunk dropped or rebuilt | 9 | 9 | 9 |
| ... slowest, above idle | 1.2 ms | 1.9 ms | 1.2 ms |
| Time spent dropping chunks, all six together | 0.54 ms | 0.50 ms | 0.52 ms |
| Frames with a garbage collection: slowest, above idle | 24.8 ms | 17.6 ms | 25.3 ms |
| Frames with nothing happening: slowest, above idle | 16.7 ms | 63.6 ms | 13.2 ms |
| Garbage collections: while moving / idle of the same length | 1 / 0 | 1 / 0 | 1 / 0 |

Each run had one garbage collection while moving and none in the idle time of the same length. That one
collection may come from the chunks that were dropped (they leave memory to clean up), but one in each run is
too few to be sure.

### Collision size

200 digs at fixed random points inside one corner column of the patch (X 4225 to 5800, Y 825 to 2400, from near
the bottom up to the ground). The largest collision mesh had 7,466 vertices, and no chunk needed more than one
piece. The engine's problem starts above 16,384 vertices per collision mesh, and the code splits a chunk into
pieces of at most 12,000. These random digs were scattered, so they did not reach the worst case: an earlier test
without the renderer made a chunk of about 29,000 vertices, split into three pieces.

### Seams

500 downward traces, 100 on each of five lines: the join with the plain ground at X = 1000, and the four chunk
borders inside the patch (X = 2625 and 4225, Y = -775 and 825). None missed, in any run. An extra check walked
in from each outer edge of the patch: the ground starts right at every edge.

(The first measurement found the dug ground shifted 25 cm from where it should be, leaving a 25 cm strip without
ground along two edges. That is fixed: the terrain's grid now starts half a cell inside the patch corner, so the
ground covers exactly the patch. The chunk borders moved 25 cm with it.)

### Navmesh

The ordinary game tests were run once with the renderer on (`test-074021.log`): the navmesh reached the bottom
of a newly dug ramp 0.033 s after the ramp's collision was ready, and a computer-controlled character walked to
the bottom of another ramp in 1.5 s. During the 30 seconds of digging the terrain asked navigation for 306
updates, about 0.04 ms each. The navigation system's own work after a request is not in these numbers.

### Shadows

A pit at (4000, -1600) in sunlight, seen by a fixed camera. For 10 seconds the test dug every 0.1 seconds along the
sunlit rim (100 digs, all changed the ground).

| Shadows | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Game thread, idle: average / worst | 2.1 / 6.3 ms | 2.1 / 3.7 ms | 2.2 / 6.1 ms |
| Game thread, digging: average / worst | 2.7 / 15.6 ms | 2.6 / 17.3 ms | 2.6 / 7.6 ms |
| Render thread average: idle / digging | 5.1 / 5.3 ms | 5.1 / 5.3 ms | 5.1 / 5.4 ms |
| Graphics card average: idle / digging | 1.85 / 1.90 ms | 1.88 / 1.92 ms | 1.92 / 1.96 ms |
| Graphics card worst frame while digging | 4.3 ms | 4.8 ms | 4.7 ms |

Shadow work happens mostly on the render thread and the graphics card: both rose by less than half a millisecond
on average while digging. The slow game-thread frames in runs 1 and 2 had no chunk update in them. Flicker needs
a person watching moving pictures; nobody did.

## Cave lighting: what the screenshots show

The screenshots are in `ArtDirection/Digging/SpikeShots/`. They come from one run of the cave test made after the
three measurement runs (`test-075449.log`); every shot had the same brightness in all runs.
A 500 cm tunnel was dug from the bottom of a 4 m pit at (1800, 1400), and cave light 1 was put inside it.

- `tunnel_hwrt_on.png`, `tunnel_hwrt_off.png`: **completely black.** The camera stands in the pit looking down
  the length of the tunnel. The dug ground here has no material of its own, so the engine draws it with its default
  grid material, and that material goes wrong on this ground: see "The black tunnel view" below.
- `tunnel_plain_material_hwrt_on.png`, `tunnel_plain_material_hwrt_off.png`: **the shots to judge.** The same view,
  with a plain engine material put on the dug ground. The tunnel is lit: a bright glow in the middle where the cave
  light hangs about 3 m in, the end of the tunnel visible as a soft, slightly darker square behind it, a smooth pale
  wall on the right with angular (faceted) edges, and darker grey towards the edges of the picture. The whole image
  is bright and washed out, with very soft, blurry shading. With and without hardware ray tracing it looks the same.
- `tunnel_wall_hwrt_on.png`, `tunnel_wall_hwrt_off.png`: from inside the tunnel, looking at its side wall from
  about 2 m. The wall is drawn and lit: a smooth, plain grey surface, brighter on the left (towards the light),
  with no detail. The two look the same.
- `tunnel_with_cube_hwrt_off.png`, `tunnel_with_cube_hwrt_on.png`: the same view as the black shots, with a small
  grey cube put in the tunnel. Now the tunnel draws and is lit: very bright and washed out, smooth soft walls, a
  blue-grey tint on the left wall, and a flat grey-blue patch on the floor near the camera. The two look the same.
- `pit_hwrt_on.png`, `pit_hwrt_off.png`: the pit from just above its rim, looking down. Grey ground, very bright;
  a dark ring at the top of the pit; inside, a lit patch of floor with faceted (flat-shaded) edges and blue
  slivers. The blue slivers and the grey-blue patch are reflections of the sky colour, not holes: with lighting
  switched off, the same views show solid ground there. With and without hardware ray tracing the pictures look the
  same.

Hardware ray tracing was really active for every "on" shot and really off for every "off" shot, and it was put
back on afterwards.

### The black tunnel view

**Cause found: the material.** The dug ground has no material set, so the engine uses its default grid material.
On this ground that material makes the view down the tunnel come out completely black. Put a plain engine material
(`/Engine/BasicShapes/BasicShapeMaterial`) on the same ground and the same view is lit, with ray tracing on and off.
Nothing else changed between the black shots and the plain-material shots.

Why the default material misbehaves here: the dug ground carries only positions and normals. When a mesh like this
is drawn, the engine fills in texture coordinates of zero for every point and makes up a tangent direction from the
normal. The default grid material evidently needs one of those to be real. Which one was not tested. Every other
explanation was tested first and ruled out: brighter or moved lights, Lumen off, automatic exposure off,
anti-aliasing off, all post-processing off, the ground drawn from both sides, and broken normals.

What to do about it is a decision still to make. The likely fix is to always give the dug ground a plain material,
both in the terrain's code and on the test map. Until that is done, any player view looking down a long tunnel may
go black.

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

## What could not be measured here

- **The packaged build.** This copy of the project has no game content, so nothing can be packaged.
- **Anything with the real hero or the real town.** They are not in this copy. All tests used a plain
  stand-in character on a small test map.
- **A machine without a ray-tracing graphics card.** Only this machine (RTX 5080) was used.
- **Flicker.** Nobody watched the game running.
- **A quiet machine.** Another Unreal editor was running throughout; single slow frames reflect that.
- **Which part of the default material fails on the dug ground** (no texture coordinates or no real tangents). The
  cave lighting was judged with a plain material instead, so this only matters for choosing the fix.

## Plugin check

Voxel Plugin 2 listed support for Unreal Engine 5.6 and 5.7 only when checked on 2026-11-21. Nothing was bought
or installed.

## Verdict

Verdict: to be written by the controller after review.
