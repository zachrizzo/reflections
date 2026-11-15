# Import the grouped medieval buildings

`import_grouped_buildings_unreal.py` prepares the checked-in grouped building
cells for a future Gray London replacement. It imports new StaticMesh packages
only. It does not place actors, change a level, suppress source buildings, or
enable the runtime replacement. A successful import is not a gameplay or
performance approval.

## Offline preflight

From the project root, run a preflight with system Python and the installed
Blender FBX decoder. The decoder is read as a Python library; the command does
not launch Blender or Unreal. Choose a new report path under `Saved` for every
run:

```powershell
$decoder = 'C:/Program Files (x86)/Steam/steamapps/common/Blender/5.3/scripts/addons_core/io_scene_fbx'
$report = 'Saved/CityPCG/GroupedImport/grouped_preflight.json'
python -B Tools/CityPCG/import_grouped_buildings_unreal.py --preflight --fbx-decoder-dir $decoder --report $report
python -B -m unittest discover -s Tools/CityPCG -p test_import_grouped_buildings_unreal.py -v
```

The independent source comparison checks every ordered triangle corner,
normal and UV against the prepared FBXs. It also validates the complete tile
barriers, named section materials, GLB byte hashes and local signed bounds.
The report fingerprints the grouped meshes, source FBXs, kit manifests and
mask evidence. Any change to those inputs requires a new preflight.

## Import in the shared editor

Wait for an allocated editor slot, hold the `codex-gray-london` lease in
`Saved/PIE_LOCK.json`, and open `/Game/GrayLondon/Maps/GrayLondon_Geodata`
outside PIE and outside a Multi-User session. The script checks the same
unexpired lease before each import and again before saving. It requires at
least 4 GiB of free physical memory and 10 GiB of available system commit
headroom at those checks. No source tile or map package is saved. With
`Tools/CityPCG` on Unreal Python's module path:

```python
from pathlib import Path
import sys
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(project / "Tools/CityPCG"))
import import_grouped_buildings_unreal as grouped

result = grouped.run(
    ["Tile_p03_p00"],
    project / "Saved/CityPCG/GroupedImport/grouped_preflight.json",
)
```

The selected tile is a complete unit: `Tile_p03_p00` has five grouped meshes,
`Tile_p03_p01` has two, and `Tile_p04_p00` has two. Pass additional tile names
to import their complete units together. Existing disk, registry or in-memory
packages are never overwritten. The new packages have exact names under
`/Game/GrayLondon/MedievalOpening/WholeBuildings/GroupedCells`.

For each mesh the importer binds the existing medieval material assets by
slot name, enables collision in every section, selects ComplexAsSimple, and
sets the mesh's navigation-data flag. It checks material bindings, local
bounds, one UV channel and one LOD, then exports the imported mesh and compares
signed triangle corners, UVs and normals against the verified GLB. Only after
every selected mesh passes does it save the exact new mesh packages and inspect
their hard material dependencies. Failure before the save can leave new,
unsaved objects in the editor; inspect those specific objects before trying
again. The script never removes existing content or uses save-all. A partial
disk failure during the explicit save is reported with the paths present.

## Required live work after import

The GLBs contain material-slot names but no source tangents, collision hulls or
additional LODs. Inspect shading, orientation, dimensions, pivot and materials
in Unreal. The pivot for each mesh is the `origin_ue_m` cell anchor, not a
building's base center; its placement must apply that anchor in centimetres.
Complex collision and a navigation-data flag are only asset settings: test
actual player sweeps, roof traversal and navigation paths in the level.

The current West Mark Lane filtered tile removes **three** source shells. The
grouped `Tile_p03_p00` unit represents **six**; they cannot be combined with
that three-shell filter. Build and validate the exact cumulative filtered tile
for each selected unit, review all nearby actors and story routes, and keep the
original tile rendering and collision until its filtered tile **and every
required grouped mesh** are ready. A group unload or any verification failure
must restore the original. The current runtime actor's gate has not been tested
with these grouped assets. Verify world-partition streaming, geometry/collision
rollback, in-game visuals and a fresh standalone cook before rollout.
