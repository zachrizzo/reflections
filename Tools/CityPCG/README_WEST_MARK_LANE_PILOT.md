# West Mark Lane whole-building pilot

The pilot defaults to off. In an ordinary Gray London play session, the subsystem leaves the source tile alone and the staged replacement stays hidden and noncolliding.

The replacement runtime was compiled and linked into shared editor build
train #15. Verify that the current editor exposes the class and CVar after
any later build or restart. The replacement actor has not yet been placed in
the map or validated in PIE or a packaged build. The steps below describe the
remaining pilot test.

## Prepare and place the pilot

1. Wait for an allocated turn in `Saved/PIE_QUEUE.md` and hold the
   `codex-gray-london` lease in `Saved/PIE_LOCK.json`. The editor must already
   have Gray London Geodata open outside PIE, and the exact original
   `Tile_p03_p00` actor must already be loaded. The four reviewed assets and
   their source export and filtered tile audit must still be present.
2. Run the [transient visual comparison](WEST_MARK_LANE_VISUAL_QA.md) under
   the lease and review both before/after street views. Confirm its report
   shows successful cleanup before continuing. Do not proceed if any source
   actor, collision, route, marker, or roof concern remains unresolved.
3. In Unreal Python, place the single owned replacement actor only after that
   review. This script checks the loaded source, the three building meshes,
   their collision settings and exact transforms, and its own actor package.
   It saves that one actor package by explicit path; it does not save the
   original tile, the map, other actors, or any skeleton.

   ```python
   from pathlib import Path
   import sys
   import unreal

   project = Path(unreal.Paths.project_dir()).resolve()
   sys.path.insert(0, str(project / 'Tools/CityPCG'))
   import place_west_mark_lane_replacement as pilot

   placement = pilot.run()
   print(placement)
   ```

Record the returned `saved_packages` and verify it contains only the new
pilot actor package. The actor remains hidden, noncolliding and disabled at
runtime until the opt-in gameplay pass below.

## Gameplay and streaming verification

1. Before PIE, check the active reservation, the editor queue, the shared
   free-virtual-memory requirement and that no `ShaderCompileWorker` is
   running. Load Gray London Geodata with the reviewed replacement actor and
   original tile loaded.
2. Add `Tools/CityPCG` to Unreal Python's import path. Run `import audit_west_mark_lane_pie as qa` and `baseline = qa.audit("baseline")` outside PIE.
3. In the editor Output Log command box, run the following **before** starting in-process PIE.

   ```text
   GrayLondon.TileReplacement.Enable 1
   ```

4. Start PIE normally and walk to West Mark Lane. Once streaming settles, run `active = qa.audit("active", baseline=baseline)`. To test streaming, walk away and collect `away = qa.audit("away")`. Return and collect `reloaded = qa.audit("active", baseline=baseline)`, then run `qa.assess_cycle(active, away, reloaded)`.
5. Stop PIE. Run `GrayLondon.TileReplacement.Enable 0` in the editor Output Log command box and repeat the baseline. The setting is read when each world begins play. Changing it during PIE takes effect in the next world.

The audit checks the three new roofs, retained roads, player-capsule clearance and two local navigation paths. If both actors unload together, the audit can verify reactivation on return. Observing the original restored in live PIE requires a sample where the original stays streamed after the replacement unloads.
