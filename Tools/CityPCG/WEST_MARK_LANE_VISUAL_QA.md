# West Mark Lane visual comparison

Use the running editor outside PIE with an active `Saved/PIE_LOCK.json` reservation for this preview. At least 120 seconds must remain on the lease at launch so the 85-second capture budget leaves time for cleanup. Open `GrayLondon_Geodata` with the original `Tile_p03_p00` actor already loaded and visible. The four audited mesh packages must exist in `/Game/GrayLondon/MedievalOpening/WholeBuildings/WestMarkLane`. The preflight uses the original export metadata and filtered tile audit in `Saved/CityPCG`.

From Unreal Python, inspect the current editor state before starting the comparison:

```python
from pathlib import Path
import runpy
import unreal

project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
qa = runpy.run_path(str(project / 'Tools/CityPCG/preview_west_mark_lane_unreal.py'))
owner = 'exact owner string from the active preview lease'
qa['inspect'](lease_owner=owner)
qa['run'](lease_owner=owner)
```

`qa['run']` schedules four 1280 × 720 captures and returns the output folder. Keep the original reservation active and unchanged while the editor captures the merchant and workshop streets from identical positions before and after the replacement. Each run produces four PNGs and a `report.json` under `Saved/CityPCG/MedievalSurvey/WestMarkLaneVisualQA`.

Call `qa['cleanup'](lease_owner=owner)` to cancel or retry cleanup. Normal completion, capture failure, timeout and manual cancellation restore the original actor selection, viewport and source visibility, and remove the temporary actors. If the reservation is removed or replaced early, the callback stops and the report shows `cleanup_pending` if any preview state remains. Wait for the other editor work to finish, reacquire an active lease with the same owner string, return to the original editor world if needed, and call `cleanup` before starting another preview. Reacquiring a lease allows cleanup only. The interrupted capture does not resume.

Check that `report.json` reports `passed` and `selection_restored`, the source is visible with identical collision settings, and the original actor, mesh, and map hashes match. The filtered tile and three preview buildings have collision and navigation disabled for the comparison. Use a separate runtime pass to test movement and physics.

The preview makes no package saves. It uses transient editor actors and the original actor's temporary visibility flag. Unreal's editor spawn and destroy utilities can still mark the open level dirty in memory. The report lists any newly dirty packages. The preview does not clear shared dirty state. An editor crash stops the callback and drops the unsaved preview actors and visibility changes.
