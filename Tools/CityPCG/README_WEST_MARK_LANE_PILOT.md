# West Mark Lane whole-building pilot

The pilot defaults to off. In an ordinary Gray London play session, the subsystem leaves the source tile alone and the staged replacement stays hidden and noncolliding.

The implementation has passed Editor-target single-file compilation. It has
not yet been linked into the shared editor, placed in the map, or validated in
PIE or a packaged build. The steps below describe the future pilot test.

1. Use an editor build that includes the replacement subsystem. Load Gray London Geodata with the reviewed West Mark Lane replacement actor saved and the original tile loaded. Hold the `codex-gray-london` lease in `Saved/PIE_LOCK.json`.
2. Add `Tools/CityPCG` to Unreal Python's import path. Run `import audit_west_mark_lane_pie as qa` and `baseline = qa.audit("baseline")` outside PIE.
3. In the editor Output Log command box, run the following **before** starting in-process PIE.

   ```text
   GrayLondon.TileReplacement.Enable 1
   ```

4. Start PIE normally and walk to West Mark Lane. Once streaming settles, run `active = qa.audit("active", baseline=baseline)`. To test streaming, walk away and collect `away = qa.audit("away")`. Return and collect `reloaded = qa.audit("active", baseline=baseline)`, then run `qa.assess_cycle(active, away, reloaded)`.
5. Stop PIE. Run `GrayLondon.TileReplacement.Enable 0` in the editor Output Log command box and repeat the baseline. The setting is read when each world begins play. Changing it during PIE takes effect in the next world.

The audit checks the three new roofs, retained roads, player-capsule clearance and two local navigation paths. If both actors unload together, the audit can verify reactivation on return. Observing the original restored in live PIE requires a sample where the original stays streamed after the replacement unloads.
