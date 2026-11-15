# Follow-on block actor survey

Use the Unreal Editor Python tool with `GrayLondon_Geodata` already open
outside PIE and an active editor lease. The query covers west connector,
northwest Leadenhall, and east of Royal Mint Court.

```python
from pathlib import Path
import json
import sys
import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "Tools/CityPCG"))
from survey_follow_on_actor_descs_unreal import survey

json.dumps(survey("EXACT_ACTIVE_LEASE_OWNER", report_name="follow_on_actor_descriptors.json"))
```

Replace the example owner with the owner in the active lease. The optional
report name writes a new JSON file under `Saved/CityPCG/MedievalSurvey`.
Omit it to return the whole report in memory. The helper checks the same
lease again before returning the result.

For each building, the query uses its footprint's bounds with a 4 m
horizontal margin, 3 m below the source foundation and 8 m above the source
roof. Each planned street link also gets a 2 m horizontal buffer and a
vertical range of −3 to +6 m. Review the region hits and their linked actor
records. Those records include the exact actor label, package, object path,
instance GUID, streaming bounds, and descriptor data-layer asset paths.
The World Partition data-layer catalog adds available instance and parent
paths. An empty set of instance matches leaves the original asset path
visible for follow-up. Empty serialized layer references are counted in
`null_data_layer_asset_count`.

## Offline binding verification

The installed UE 5.9 Python wrapper exposes the native soft-object path
break as a one-element tuple from `SoftObjectPath.to_tuple()`. This returns
the exact path string, including any subobject suffix. The implementation
is in the Python plug-in's `PyWrapperStruct.cpp` and
`PyWrapperTypeRegistry.cpp`, with the underlying break registered in
`SoftObjectPath.h` and implemented in `KismetSystemLibrary.cpp`.
`PyGenUtil.cpp` also explains the descriptor query return shape. A
successful call returns the descriptor array, including an empty array when
the query finds no actors. A failed call returns `None`.

Run the offline mock checks from the project root.

```powershell
python -B -m unittest discover -s Tools/CityPCG -p 'test_survey_follow_on_actor_descs_unreal.py' -v
```

World Partition descriptors are saved snapshots and include unloaded
actors in the registered containers. Streaming bounds can cover both a
building and its neighbors even when the visible geometry does not, and
large tile and proxy bounds can intersect multiple regions. The
`footprint_touches_actor_bounds_xy` flag checks the projected footprint
against the streaming bounds. Actual mesh overlap, collision, unsaved
actor changes, and actor or data-layer state in PIE require their own
checks. The survey does not load, place, change, or save an Unreal actor
or package.
