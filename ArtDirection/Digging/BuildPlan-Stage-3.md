# Digging Stage 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the spike's dig patch into the ground engine for the whole town: digs that rebuild only what they change, a grid that holds 500 m of ground, minerals, and dug ground that saves and reloads.

**Architecture:** The grid stays the single source of truth and every dig still goes through `UReflectionsDigSubsystem::Dig`. Part A makes a chunk's mesh eight fixed blocks, so a dig replaces only the blocks it changes. Part B (planned to task level after part A's gate) makes the grid sparse and town-sized, streams a 150 m ring with collision kept farther out than visuals, adds materials and minerals, and saves dug chunks.

**Tech Stack:** UE 5.9 C++, `UDynamicMeshComponent`, the project's own surface-nets mesher, Chaos collision built in the background, a dynamic navmesh, `USaveGame`. No third-party plugin.

**Spec:** `ArtDirection/Digging/Feasibility.md` (section 7.1), the Claude Doc "Reflections full digging plan" (stages 3 to 5 in outline), `ArtDirection/Digging/SpikeResults.md` (the verdict's named changes) and `ArtDirection/Digging/BuildRulings.md` (decisions already taken and what was left for later).

## Global Constraints

- **Where you work:** only inside the worktree `C:\Users\zachc\Documents\Unreal Projects\reflections\.worktrees\digging`, branch `claude/digging-stages-1-2`. The controller, not you, moves finished work to `main`. Never use the running Unreal editor, `unreal-mcp` tools, or PIE: the editor on this machine belongs to other sessions.
- **The worktree is sparse.** It holds `Source/`, `Config/`, `ArtDirection/Digging/`, `Tools/Digging/` and `Content/Maps/DigSpike/` only. Use engine content (`/Engine/BasicShapes/...`) in tests and in the map.
- **Build:** only with `powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\zachc\Documents\Unreal Projects\reflections\.worktrees\digging\.superpowers\bin\build.ps1"`. A pass prints `BUILD OK`.
- **Editor-context tests:** only with `...\.superpowers\bin\test.ps1 -Filter <prefix>`. A pass prints `TESTS: N ran, N passed, 0 failed` with N > 0 and `automation warnings/errors logged: 0`.
- **Game-context tests:** the same script with `-Game -Map /Game/Maps/DigSpike/L_DigSpike`. From Git Bash the map path needs `MSYS_NO_PATHCONV=1`.
- **Rendered measurement tests:** `test.ps1 -Game -Render -Map /Game/Maps/DigSpike/L_DigSpike -Filter Reflections.SpikePerf -TimeoutSec 2400`. A run takes about five minutes: run it in the background, never two at once, and afterwards run `git checkout -- ArtDirection/Digging/SpikeShots/`. The wrapper passes `-nocef`.
- **Editor Python** (the map script): only with `...\.superpowers\bin\editor-python.ps1 -Script <path>`.
- **If any wrapper prints `REFUSED` or `ABORTED` (exit 75), stop and report BLOCKED.** Never call `Build.bat`, UnrealBuildTool, `UnrealEditor.exe` or `UnrealEditor-Cmd.exe` directly.
- **Engine:** UE 5.9 at `C:\Program Files\Epic Games\UE_5.9`. Engine source is readable there. Check real headers before using an engine API.
- **Module rules:** `reflections` has `bUseUnity = false` and explicit PCHs. Every `.cpp` includes its own header first and then everything it uses. Types used across files carry `REFLECTIONS_API`.
- **Names:** classes are `AReflections...`, `UReflections...`, `FReflections...`; namespaces are `ReflectionsSave`, `ReflectionsDig`, `ReflectionsDigMesher`, `ReflectionsDigPieces`.
- **Tests:** Unreal automation tests named `Reflections.*`, inside `#if WITH_DEV_AUTOMATION_TESTS`. Output must be clean: a deliberate warning or error is declared with `AddExpectedError`. Tests never touch the real save slot `Reflections`; they use `ReflectionsTest`.
- **Fixed numbers:** cell 50 cm; chunk 32 cells (16 m); block 16 cells (8 m), eight blocks per chunk; density is `int8`, positive is solid; `DensityPerCell = 64`; `SampleBorder = 2`; topsoil material 0; bedrock material 255; dig radius 100 cm; reach 250 cm; commit budget default 2 per frame; a piece holds at most 12,000 vertices.
- **Rules that must keep holding** (each is pinned by existing tests; a task may change how, never whether): a dig never opens the floor while collision rebuilds (old collision stays until the new one is in); navigation never builds a piece's collision (`GetGameThreadCookCount()` stays 0); a retiring piece leaves navigation at once and a new piece joins it only with its first collision; pieces never draw with the engine default material; nothing leaves the world (the safety floor).
- **Scope limits:** single-player only, no replication. No third-party code, no new plugins, no `.uproject` change.
- **Git:** one commit per task (a fix round adds a commit). Stage only the task's files by path. Never stash, reset, rebase, switch branches or push. Commit messages are one plain imperative sentence and end with a `Co-Authored-By:` line naming the model that wrote the commit (for an Opus subagent: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). If `git commit` fails with "unable to write file .git/objects/... Permission denied", run the same commit again.

## Review Focus

1. A dig at a block border inside one chunk: the hole's floor lies in a block that had no piece before. The floor must collide before the old collision above it goes.
2. A dig that changes nothing in a chunk except its border samples: no component work at all, and the terrain still becomes idle.
3. A result that arrives for a chunk whose earlier pieces are still building collision: the newest mesh wins, nothing is left hidden but colliding for good.
4. A block dug or filled until it holds no surface: its piece goes, its collision stays until the terrain is quiet, and a later dig brings a piece back.
5. Streaming a chunk out and back: all eight blocks return as they were.

---

## Part A: cheaper digs

### Task 3.1: A dig rebuilds only the blocks it changes

**Why:** `SpikeResults.md` shows what a heavy dig still costs: every dig in a chunk replaces all of that chunk's pieces (about 30,000 vertices in the worst case) for a hole 2 m across, and all the main-thread cost grows with the mesh replaced. Pieces are cut by vertex count into horizontal slabs, so they have no fixed identity and a chunk with more than one piece always swaps every piece.

**Files:**
- Modify: `Source/reflections/Digging/ReflectionsDigTypes.h`, `ReflectionsDigPieces.h/.cpp`, `ReflectionsDigTerrain.h/.cpp`, `ReflectionsDigSubsystem.cpp`
- Modify tests: `Tests/ReflectionsDigPiecesTests.cpp`, `Tests/ReflectionsDigTerrainTests.cpp`, `Tests/ReflectionsDigGameTests.cpp`, `Tests/ReflectionsDigPerfTests.cpp`; other test files only where a test pins the old slab behaviour

**Interfaces:**
- Consumes: `FReflectionsDigMeshData` (one chunk's mesh from the mesher, positions relative to the grid origin), `FReflectionsDigChunkSamples::LocalOriginCm`, `AReflectionsDigTerrain::CommitChunkPieces`, the retire and swap logic of `ReflectionsDigTerrain.cpp`.
- Produces:
  - `ReflectionsDig::BlockCells = 16` and `ReflectionsDig::BlocksPerChunk = 8` in `ReflectionsDigTypes.h`. A chunk's blocks are its eight octants; block index = `X + 2 * Y + 4 * Z` with `X`, `Y`, `Z` 0 for the low half of the chunk on that axis and 1 for the high half.
  - `FReflectionsDigChunkResult` holds exactly eight slots: `TStaticArray<UE::Geometry::FDynamicMesh3, 8> Pieces`, `TStaticArray<FReflectionsDigNavGeometry, 8> NavGeometry`, `TStaticArray<uint64, 8> PieceHash` (0 for a block with no triangles) and the existing counters. `int32 NumPieces() const` counts the non-empty slots.
  - `void ReflectionsDigPieces::Build(const FReflectionsDigMeshData& Mesh, const FVector3f& ChunkLocalOriginCm, FReflectionsDigChunkResult& Out)`: a triangle goes to the block that holds its centroid (the border between two blocks is `ChunkLocalOriginCm + 16 cells`; a centroid exactly on it goes to the high block). Each piece has its own copy of the vertices it uses. `PieceHash` covers the piece's positions, normals and triangles in the mesher's order, so the same input gives the same hash on any thread. `BuildWithSlabs` and the slab search are removed.
  - `AReflectionsDigTerrain`: the chunk's current pieces are eight slots indexed by block. `int32 GetChunkPieceCount(FIntVector Chunk) const` counts the filled slots; `UDynamicMeshComponent* GetChunkBlockPiece(FIntVector Chunk, int32 Block) const` returns a slot's piece or null; `GetChunkPiece(Chunk, Index)` keeps working as "the Index-th filled slot, lowest block index first".
  - `int32 AReflectionsDigTerrain::GetPiecesChangedCount() const` and `int32 GetPiecesKeptCount() const`: read-only totals of slots given a new mesh and of slots a commit left alone because their hash had not changed. For measurements and tests.

**Rules:**
1. **Only changed blocks are touched.** A commit compares each slot's new hash with the hash of the mesh that slot shows. A slot whose hash is equal keeps its component exactly as it is: no `SetMesh`, no collision build, no navigation update, the same component object.
2. **The swap rule applies to the changed blocks as one set.** The pieces a commit replaces stay hidden but colliding until every piece that commit created or changed has collision; then they go together. This is the existing retire-and-swap logic, applied to the changed slots instead of the whole chunk. A commit that changes exactly one slot which has a piece before and after keeps using the single-piece reuse path (the same component gets the new mesh and the engine keeps its old body until the new one is in).
3. **A block that loses its surface** (its new slot is empty) retires its piece under the existing "emptied" rule: the collision stays until the terrain is quiet. A block that gains a surface gets a new piece, which joins navigation with its first collision as any new piece does.
4. **A result that changes no slot does no component work**, and the chunk does not count as waiting on collision because of it.
5. **No slab split.** A block's piece cannot pass `ReflectionsDig::MaxPieceVertices`: prove it with a test on the worst mesh a chunk can produce, and log a warning (not a split) if a piece ever does.
6. **Worker jobs run at background priority** (`UE::Tasks::ETaskPriority::BackgroundNormal` in the subsystem's `Launch`), so the frame's own tasks do not queue behind meshing.
7. Everything listed under "Rules that must keep holding" in Global Constraints still holds, and every existing test still passes. A test that pins slab behaviour (piece counts of a riddled chunk, `BusyMeshSplitsUnderTheLimit`, `SlabsAreTheFewestThatFit`, `BusyChunkIsSplitUnderTheCollisionLimit`, `SplitChunkCollisionFollowsEachCook` and helpers that expect "three pieces") is rewritten to pin the same property for blocks; name each one you change in the report and say what it pins now.

- [ ] **Step 1: Write the failing tests.**
  - `Reflections.Digging.Pieces.TrianglesGoToTheBlockOfTheirCentroid`: for a riddled chunk mesh, every triangle of piece `B` has its centroid inside block `B`'s box (low border included, high border excluded), the pieces' triangle counts add up to the source's, and an untouched flat chunk fills exactly the four blocks its surface runs through.
  - `Reflections.Digging.Pieces.HashFollowsTheMeshOnly`: building the same mesh twice gives equal hashes; after one more dig inside block `B`, the hashes of the blocks whose triangles did not change are equal to before and block `B`'s differs.
  - `Reflections.Digging.Pieces.WorstBlockStaysUnderTheLimit`: for a chunk whose cells alternate solid and air in every direction (the mesh with the most vertices the mesher can make), every piece has at most `MaxPieceVertices` vertices.
  - `Reflections.Digging.Terrain.UnchangedBlocksAreNotTouched`: riddle one chunk, wait for idle and note each slot's component and the terrain's collision-finish count; dig once well inside one block, wait for idle: that block's slot changed, every other slot holds the same component object, `GetPiecesKeptCount()` grew by the number of other filled slots, and the collision-finish count grew by exactly one.
  - `Reflections.Digging.Terrain.BorderOnlyChangeDoesNoWork`: dig once so close to a chunk's face that the neighbouring chunk is dirtied but its mesh does not change (for example a dig deep underground whose hole stays inside the first chunk); after idle, the neighbour's slots hold the same components, its collision-finish count did not grow, and the terrain is idle.
  - `Reflections.Digging.Terrain.NewBlockCollidesBeforeItsNeighbourOpens`: commit, to one chunk, a mesh whose pit floor lies in a block that had no piece; until the new block's piece has collision, a downward trace into the pit still hits the old surface of the block above (its old piece is hidden but colliding); after idle the trace hits the pit floor and no retiring piece is left.
  - `Reflections.DigSpike.DigDownCrossesBlocks` (game context): hold dig under a character from the surface down through two block borders inside one chunk; the character's feet never go below the grid floor, never end below the last dug floor by more than 100 cm, and after idle the character stands on the pit floor.
- [ ] **Step 2: Run them**; each fails or does not compile for the stated reason.
- [ ] **Step 3: Implement** rules 1 to 7.
- [ ] **Step 4: Measurement lines.** `BUSY_BEFORE` and `BUSY_AFTER` log `pieces=<filled slots>`; every `_WHOLE` line gains `pieces_changed=<n>` and `pieces_kept=<n>` (the window's deltas). `Tools/Digging/summarize_spike_log.py` prints both, and prints `n/a` for logs that lack them.
- [ ] **Step 5: Run** the build, the editor-context suite, the game-context suite and one rendered run; report the busy-chunk, corner, open-ground and streaming whole-window lines beside those of `ArtDirection/Digging/SpikeLogs/test-112757.digspike.log`. Restore the screenshots. Do not edit `SpikeResults.md`.
- [ ] **Step 6: Commit.**

### Task 3.2: Measure the tuning round

**Files:**
- Modify: `ArtDirection/Digging/SpikeResults.md`
- Create: `ArtDirection/Digging/SpikeLogs/` files for the new runs
- Modify: `Tools/Digging/summarize_spike_log.py` only if a figure the page needs is not printed

- [ ] **Step 1: Run** the rendered measurement command four times with the default commit budget (2 per frame), then twice with `-ExtraArgs "-dpcvars=reflections.Dig.MaxCommitsPerFrame=1"` on the wrapper. Each run 10 of 10, clean. Restore the screenshots after each. If the second command does not set the variable (check the log for the value), stop and report.
- [ ] **Step 2: Keep the logs' measurement lines** in `ArtDirection/Digging/SpikeLogs/` the way the folder's `README.md` describes, and add the six runs to its table.
- [ ] **Step 3: Add one section to `SpikeResults.md`,** "After the tuning round", placed before "Verdict": the pass-mark rows (busy chunk, corner, open ground, streaming, navmesh, collision size, seams) for the four default runs and, in a second table, for the two runs with a commit budget of 1; for each row the same figures as the main table, `pieces_changed` and `pieces_kept` per window, and the "Met / Not met" result by the page's rule. One sentence says what changed since the four runs above it (a dig now replaces only the blocks it changes; worker jobs run at background priority). State no cause and no recommendation; leave every other section and the Verdict as they are.
- [ ] **Step 4: Commit.**

**Gate 2b (the plan's one tuning round):** the heavily dug chunk and the eight-chunk corner meet 4 ms on 99 frames in 100. The controller then rewrites the Verdict. If they do not, the plan doc's stop condition is put to the owner before part B starts.

---

## Part B: the whole town's ground (outline)

Planned to task level after gate 2b, from its numbers. In this order:

1. **A sparse, town-sized grid.** 500 m by 500 m by 32 m; a chunk that is all rock or all air is one value; ground height comes from a height function so stage 4 can match the town.
2. **A 150 m ring with collision farther out than visuals,** and bookkeeping that visits only chunks with work to do (today every chunk is visited every frame).
3. **Materials in the mesh.** The mesher's per-vertex material reaches the pieces; one triplanar ground material with placeholder textures made by script.
4. **Minerals.** Depth layers and seeded veins of soil, clay, stone, coal, iron ore and gold-bearing rock; hand-placed vein volumes; a hardness per material; a dig reports how much of each material came out, and the totals are kept in the save.
5. **No-dig volumes** (the protected slab under each building, to be placed in stage 4).
6. **Saving dug ground.** Only chunks that differ from the generated ground, compressed, in `DigTerrainBlob`; save version 2, with a test that a version 1 save still loads.
7. **Gate 3 measurements:** the 150 m ring holds frame time while digging, and a dug area reloads exactly as it was saved.
