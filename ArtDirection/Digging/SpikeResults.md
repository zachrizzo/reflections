# Digging spike: results

This page holds the numbers from the digging spike. They decide whether the full digging feature gets built.

## How it was measured

- The game ran with its real renderer, drawn off screen at 1280 x 720, capped at 60 frames a second.
- Machine: RTX 5080. Another full Unreal editor was running on the same machine the whole time, so the
  computer was not quiet. Treat single slow frames with care (see "Slow frames that are not digging" below).
- Hardware ray tracing was on (DirectX 12, ray tracing 1, Lumen hardware ray tracing 1), except where a
  screenshot turned it off on purpose.
- The test ran three times. Each run took about 2.5 minutes (149, 149 and 150 seconds). No shaders had to be
  compiled during the runs.
- "Game-thread time" is the time the game's main thread spends working in one frame, in milliseconds (ms).
  It leaves out the time the game waits for the 60-frames cap. One frame at 60 frames a second lasts 16.7 ms.
- "Idle baseline" is the same thing measured over 300 frames at the same spot, just before, with nothing
  being dug. Each cost below is "worst frame while digging" minus "worst idle frame".
- Log files: run 1 `test-064923.log`, run 2 `test-065152.log`, run 3 `test-065421.log`
  (in `.superpowers/logs/` of the digging worktree).

## Results with the renderer on

| What | Run 1 | Run 2 | Run 3 | Pass mark | Result |
|---|---|---|---|---|---|
| Game-thread cost of digging (worst frame minus worst idle frame) | 17.7 ms | 39.3 ms | 14.8 ms | 4 ms or less | Not met |
| Streaming (worst frame minus worst idle frame) | 47.9 ms | 39.2 ms | 30.3 ms | 4 ms or less | Not met |
| Collision size per chunk (largest collision mesh) | 7,347 vertices | 7,347 vertices | 7,347 vertices | under 16,384 | Met (but see note) |
| Seams (missed downward traces out of 500) | 4 | 4 | 4 | no missed traces | Not met (all 4 at the patch's outer edge, none at a seam) |
| Navmesh: dig to walkable floor | not measured | not measured | not measured | 1 s or less, no stall | Not measured with the renderer on |
| Cave lighting | screenshots | screenshots | screenshots | judged by the owner | For the owner (tunnel shots are black, see below) |
| Shadows (worst frame minus worst idle frame) | 7.8 ms | see note | 3.7 ms | frame cost recorded, no flicker | Cost recorded; flicker not judged |
| Packaged build | not measured | not measured | not measured | same checks repeated | Not measured |

### What each row means, in more detail

**Digging.** A character stood on the ground at (1800, -1600). The test dug under its feet every 0.1 seconds for
30 seconds: 300 digs, and every one changed the ground. For the first 7.4 seconds it dug straight down; the
character fell 27.5 m to the bottom (bedrock). After that, it dug out and filled back a small pocket next to
the character at the bottom, in turn, so every dig still changed the ground.

| Digging, game-thread time | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Idle: average / worst | 2.2 / 6.4 ms | 2.1 / 3.7 ms | 2.1 / 3.8 ms |
| Digging: average | 2.5 ms | 2.4 ms | 2.4 ms |
| Digging: 99 frames in 100 at or under | 4.7 ms | 4.5 ms | 5.0 ms |
| Digging: worst frame | 24.1 ms | 43.1 ms | 18.6 ms |
| Frames over 16 ms (of 1,800) | 1 | 2 | 1 |
| Chunk updates put on screen | 312 | 312 | 312 |
| Slowest single chunk update | 0.75 ms | 1.10 ms | 1.46 ms |
| All chunk updates together | 80.5 ms | 80.5 ms | 80.8 ms |
| Navigation requests (count / total time) | 305 / 11.6 ms | 305 / 11.1 ms | 305 / 11.2 ms |

The worst frames fail the pass mark. But in every one of those slow frames the terrain put no chunk on screen,
and in three of the four the engine was also cleaning up memory (garbage collection). The digging's
own measured work never came near 4 ms in a frame: at most two chunk updates happen in one frame, the
slowest single update was 1.46 ms, and the dig calls themselves took at most 0.6 ms. So the slow frames are real, but this test cannot show they are caused by
digging. Without them, digging adds about 0.3 ms to an average frame, and 99 frames in 100 took at most
4.5 to 5.0 ms while digging, against 3.3 to 3.8 ms when idle.

**Streaming.** The character was moved from one corner of the patch (1100, -2300) to the opposite corner
(5700, 2300) over 20 seconds. Six chunks were dropped behind it and eight were built in front of it, in every run.

| Streaming, game-thread time | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Idle: average / worst | 2.1 / 5.0 ms | 2.4 / 39.3 ms | 2.1 / 3.7 ms |
| Moving: average | 2.4 ms | 2.3 ms | 2.3 ms |
| Moving: 99 frames in 100 at or under | 5.8 ms | 4.2 ms | 4.4 ms |
| Moving: worst frame | 52.9 ms | 78.4 ms | 34.0 ms |
| Frames over 16 ms (of about 1,200) | 3 | 3 | 2 |

This fails too. As with digging, the slow frames had no chunk update in them, and run 2's idle baseline itself
had a 39 ms frame. The test did not time dropping chunks (that work is not logged), so dropping chunks cannot be
ruled out as the cause of these frames.

**Collision size.** 200 digs at fixed random points inside one corner column of the patch
(X 4200 to 5800, Y 800 to 2400, from near the bottom up to the ground). The largest collision mesh had 7,347
vertices, and no chunk needed more than one piece. The engine's problem starts above 16,384 vertices per
collision mesh, and the code splits a chunk into pieces of at most 12,000. These random digs were scattered,
so they did not reach the worst case: an earlier test without the renderer made a chunk of about 29,000
vertices, split into three pieces.

**Seams.** 500 downward traces, 100 on each of five lines: the join with the plain ground at X = 1000, and the
four chunk borders inside the patch. Every trace on the join hit ground. The four misses were the last trace
on four of the lines, 24 cm from the far edge of the patch (X = 5800 or Y = 2400). An extra check found the
cause: the whole dug ground is drawn, and collides, 25 cm off from where it should be in X and Y. It starts 25 cm before the
near edges (so it overlaps the plain ground at X = 1000, which is why the join looks fine) and stops 25 cm
before the far edges, leaving a 25 cm strip with no ground. Inside the patch, no chunk border leaked. This is
a defect in the terrain's placement, not a gap between chunks; it would show wherever the far edges of a patch
meet other ground.

**Navmesh.** The renderer run only counted the navigation requests during digging (above: 305 requests, about
11 ms in total over 30 seconds, about 0.04 ms each). The time from a dig to a walkable floor was measured only
without the renderer (0.033 s, below). The navigation system's own work after a request is not in these numbers.

**Shadows.** A pit at (4000, -1600) in sunlight, viewed by a fixed camera. For 10 seconds the test dug every
0.1 seconds along the sunlit rim (100 digs, all changed the ground).

| Shadows, game-thread time | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Idle: average / worst | 2.1 / 5.8 ms | 3.1 / 283.2 ms | 2.1 / 3.7 ms |
| Digging: average | 2.7 ms | 2.5 ms | 2.6 ms |
| Digging: worst frame | 13.6 ms | 10.2 ms | 7.4 ms |
| Render-thread time while digging: average / worst | 5.5 / 18.0 ms | 5.2 / 15.8 ms | 5.3 / 15.0 ms |

In run 2 a single idle frame took 283 ms, with nothing happening in the game, so run 2's baseline is not usable;
its worst digging frame was 10.2 ms (7.1 ms above the average idle frame). Shadow work happens mostly on the
render thread and the graphics card, not the game thread; the render thread rose by 0.1 to 0.4 ms on average.
The graphics card's own time was not measured. Flicker needs a person watching moving pictures; nobody did.

### Slow frames that are not digging

Every window had a few frames far slower than the rest, idle windows included (283 ms and 39 ms while nothing
was being dug). For each slow frame the test logged what the terrain did in it: none of them contained a chunk
update, and 6 of the 14 contained a garbage collection. The other Unreal editor running on the same machine may cause
some of them. The "worst frame" rows above are therefore the least trustworthy numbers on this page.

## Cave lighting: what the screenshots show

The screenshots are in `ArtDirection/Digging/SpikeShots/` (from run 3; runs 1 and 2 gave the same brightness).
A 500 cm tunnel was dug from the bottom of a 4 m pit at (1800, 1400), and cave light 1 was put inside it.

- `tunnel_hwrt_on.png`, `tunnel_hwrt_off.png`: **completely black.** The camera is in the pit looking down
  the tunnel. Further checks (not committed) showed this is not about the light: the picture stays black with
  no lighting at all, with the sky removed, with shadows off and with automatic exposure off. The dug ground
  is simply not drawn when it is the only thing in view from underground. **This is a defect to fix before
  anything else is judged.**
- `tunnel_with_cube_hwrt_off.png`, `tunnel_with_cube_hwrt_on.png`: the same view with a small grey cube put in
  the tunnel. Now the tunnel walls are drawn and lit by the cave light. The image is very bright and washed out
  (strong automatic exposure), the walls are smooth and soft-edged, the left wall has a blue-grey tint and a flat
  grey-blue facet shows on the floor near the camera. The two pictures, with and without hardware ray tracing, look the same.
- `pit_hwrt_on.png`, `pit_hwrt_off.png`: the pit from just above its rim, looking down. Grey ground, very bright;
  a dark ring at the top of the pit; inside, a lit patch of floor and flat-shaded, faceted edges with blue
  (sky-coloured) slivers. No glow from the cave light shows through the ground in this view. With and without hardware ray tracing they look the
  same (identical brightness).

Hardware ray tracing was really active for every "on" shot and really off for every "off" shot (the test checks
the same conditions as the renderer), and it was put back on afterwards.

## Numbers from earlier tests, without the renderer (headless)

These come from tasks 2.3 to 2.5, run without any graphics. They are not comparable with the table above.

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
- **Graphics-card time and flicker.** Not measured; see "Shadows".
- **Time from a dig to a walkable navmesh with the renderer on.** Only the headless number exists.

## Plugin check

Voxel Plugin 2 listed support for Unreal Engine 5.6 and 5.7 only when checked on 2026-11-21. Nothing was bought
or installed.

## Verdict

Verdict: to be written by the controller after review.
