# Opening spawn roof audit

From the project root, write a diagnostic for the exact reviewed `Tile_p03_p00.glb` export:

```powershell
python Tools/CityPCG/audit_opening_subshell.py --report Saved/CityPCG/MedievalSurvey/opening_subshell_geometry_report.json
```

Use a fresh JSON name under `Saved` for each run. The script checks the exported tile's pinned SHA-256 before reading geometry. It resolves ordinary wall triangles 5014–5029 and roof triangles 2279–2284, verifies that the cap matches the eight-wall outline, and records adjoining roof triangles, opposing walls, frontage fixtures and nearby story markers.

The six roof faces form a distinct cap within the larger nonmanifold roof component. The report preserves the three shared edges and identifies the retained neighbors. Keep this block on hold until the opening cutscene, home marker, stairs, and existing façades have been reviewed in the live map. The diagnostic only writes the report and provides no removal input.
