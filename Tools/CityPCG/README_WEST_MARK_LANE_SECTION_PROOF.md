# West Mark Lane source-section comparison

The source mesh section assigned to each `Tile_p03_p00.glb` primitive is not
yet verified. Five primitives share `WorldGridMaterial`, so matching material
names, section counts, and triangle totals cannot distinguish them. The
existing filtered pilot remains disabled until this mapping and retained road
geometry are independently checked.

`verify_west_mark_lane_section_mapping.py` prepares a **read-only** comparison
for the existing source mesh and source GLB. It requests source-model LOD0
through GeometryScript with section indices as dynamic-mesh material IDs, and
copies only into a transient `DynamicMesh`. It queries the corresponding
section slot names, vertex positions and triangle indices, and compares each
source section with every GLB primitive using complete signed triangle
multisets. Cyclic vertex rotations match; reversed winding does not. It
converts Unreal centimetres to GLB metres using UE 5.9's `(X,Z,Y)` axis
convention and float32 scaling. Duplicate triangle signatures shared across
source sections, empty sections, ID gaps, unsupported GLB data or an
incomplete match all require manual review. Exact float matching may reject
otherwise valid geometry if conversion changes it; it does not relax the
comparison to force a result.

The Unreal log shows that GeometryScripting was mounted in train #17, and its
installed source describes these reflected operations. **Their availability,
Python signatures, and section-ID fidelity have not been tested live.** The
script names a missing operation if the expected capability or signature is
unavailable, and never guesses a mapping. Its geometry comparison and fake
Unreal API tests pass offline; parsing the existing source GLB found six
primitives with 18,084, 7,622, 18,340, 348, 283, and 624 triangles. This is
not a source-section proof.

Only after an allocated shared-editor turn and explicit handoff in
`Saved/PIE_QUEUE.md`, with the matching current lease in
`Saved/PIE_LOCK.json`, Gray London Geodata open outside PIE, and the memory
requirements met, run in Unreal Python:

```python
from pathlib import Path
import sys
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(project / 'Tools/CityPCG'))
import verify_west_mark_lane_section_mapping as section_proof

result = section_proof.run('codex-gray-london')
print(result)
```

The function requires a lease with at least 120 seconds remaining, checks
memory, world, PIE, lease, actor descriptor, hard mesh dependency, source and
actor package hashes, source transform, dirty package state, and GLB hash. It
checks them again around the copy and before returning. It does not save any
package, change actor or asset properties, write a metadata file, start PIE,
restart the editor, or enable the replacement.

An `ambiguous_or_mismatch` result is a stop for manual inspection. Even a
`geometry_match_review_required` result only identifies candidate source
section/primitive correspondence for that exact source and GLB. It does not
verify the filtered replacement still contains every original road triangle,
does not validate actor placement or collision, and does not authorize pilot
activation. Compare the returned road primitive with the original pilot
assumption, independently verify retained road geometry in the actual filtered
replacement, and complete the visual and gameplay checks in
`README_WEST_MARK_LANE_PILOT.md` before enabling it.

Offline tests from the project root:

```text
python Tools/CityPCG/test_verify_west_mark_lane_section_mapping.py -v
```
