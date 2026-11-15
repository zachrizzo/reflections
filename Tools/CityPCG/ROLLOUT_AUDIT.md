# Whole-building rollout preflight

The rollout audit inventories saved tile exports and combines reviewed building
shell masks for each original tile. It checks that the geometry, material-slot
order, tile origin and protected road/landmark sections match the exact source
export. Passing this preflight does not approve a block for gameplay: actor,
quest, road, collision, navigation and visual checks still need the live map.

Export the original tiles and their metadata before running the audit. From the
project root, an example using the four current review-only candidates is:

```powershell
$art = 'ArtDirection/CityPCG/MedievalOpening'
$survey = 'Saved/CityPCG/MedievalSurvey'
python Tools/CityPCG/audit_whole_building_rollout.py "$survey/rollout_preflight.json" `
  --candidate "$art/west_mark_lane_whole_buildings_candidate.json" `
  --candidate "$art/west_connector_whole_buildings_candidate.json" `
  --candidate "$art/leadenhall_northwest_whole_buildings_candidate.json" `
  --candidate "$art/east_tower_whole_buildings_candidate.json"
```

The output path must be new. Each candidate pins its export SHA-256; this is
important where exports of the same tile name differ. For inventory without a
candidate, `--source-pin Tile_p04_p00 <sha256>` selects an exact revision. To
ensure a later rollout has not removed or changed an earlier candidate, add
`--previous-report <report.json>` and include all earlier candidates again.
Any requested mask or pin that fails validation causes a nonzero exit status.

Run the small offline tests with:

```powershell
python -m unittest discover -s Tools/CityPCG -p test_audit_whole_building_rollout.py
```
