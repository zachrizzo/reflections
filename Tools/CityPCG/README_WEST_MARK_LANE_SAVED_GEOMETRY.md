# West Mark Lane saved replacement geometry check

`verify_west_mark_lane_saved_geometry.py` is prepared to compare the actual
saved replacement mesh's MeshDescription with the pinned named pilot GLB.
**It has not yet been run on the real compressed payload.** Its output must
not be treated as evidence of a match until the guarded comparison succeeds.

Run only after the editor is loaded, the leading queue entry no longer
reserves the NPC proof rounds, no `Saved/PIE_LOCK.json` exists, and the other
offline city worker has finished. The program checks the queue, actual
`UnrealEditor.exe` process, absence of any lease, and at least 4 GiB available
physical / 10 GiB available commit. It repeatedly rechecks these conditions
and stops on a new lease, train change, reserved window, process closure or
significant memory drop. It kills its parser child if a guard fails.

The comparison depends on Windows, Python, Node.js, the Epic-installed
`oo2core.dll`, the external Python `blake3` package under
`Saved/CityPCG/OfflineGeometryDeps`, and the hash-pinned MIT-licensed
`@threenative/raw-unreal` parser at
`Saved/CityPCG/UAssetResearch/raw-unreal-0.1.13/package/dist/index.js`.
Dependency provenance and setup are described in
`README_UNREAL_SOURCE_GROUPS_OFFLINE.md`. Epic's DLL and the parser are not
vendored by this tool.

```powershell
# Small synthetic tests; do not decode the real asset or launch Node.
python Tools/CityPCG/test_verify_west_mark_lane_saved_geometry.py -v
python -O Tools/CityPCG/test_verify_west_mark_lane_saved_geometry.py -v

# Only in the safe, unreserved window described above, with a fresh filename:
python Tools/CityPCG/verify_west_mark_lane_saved_geometry.py --payload-output Saved/CityPCG/MedievalSurvey/WestBlockTile_mesh_payload_review_01.bin
```

The checker first authenticates the original saved replacement asset and named
GLB, the raw-unreal parser and the existing source-group extractor. It checks
the compressed buffer's exact layout, block table and CRC, the output length
and full BLAKE3 against the pinned buffer header. It creates a fresh file
directly in `Saved/CityPCG/MedievalSurvey`, writes guarded 256 KiB chunks,
then checks its full length, SHA-256 and BLAKE3 from disk. An existing or
redirected target is refused. Node reads that verified file with stdin
disabled, so timed polling can interrupt the parser when the lease or memory
conditions change. The file is retained for inspection. If writing is
interrupted, the incomplete file is also retained but must not be used as a
verified payload; select a new filename for a later run. The in-memory
extractor adaptation changes only the pinned asset/payload identities and
Node argument positions; it rejects altered source anchors.
It requires one-to-one complete signed-triangle matches across six unique
material names and rehashes the source inputs before reporting a result.

A passing result would describe positions, winding, multiplicity, and
polygon-group slot names in these specific saved bytes. It would not establish
UVs, normals, textures, collision behavior, the loaded asset or component,
post-load render-section binding, actor placement, streaming, visual quality,
navigation or gameplay. The pilot remains disabled until its separate live
checks are complete.
