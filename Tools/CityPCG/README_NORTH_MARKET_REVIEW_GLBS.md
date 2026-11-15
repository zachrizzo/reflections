# North Market review GLB preparation

`build_north_market_review_glbs.py` prepares four review-only GLBs from the
existing pinned North Market OBJ source bundle. It has passed small synthetic
tests but has **not yet run on the four real models**. No review GLBs have
been produced by this script yet.

Run it only when the shared editor is loaded, the leading queue entry no
longer reserves another team's work, no `Saved/PIE_LOCK.json` exists, and the
other offline city worker has finished. It checks for a running editor, a
loaded and unreserved train, no lease, and at least 4 GiB physical / 10 GiB
commit headroom. It rechecks the lease, train and memory during processing.

```powershell
# Tiny synthetic tests; they do not process the four source models.
python Tools/CityPCG/test_build_north_market_review_glbs.py -v
python -O Tools/CityPCG/test_build_north_market_review_glbs.py -v

# Only in a safe, unreserved and coordinated window:
python Tools/CityPCG/build_north_market_review_glbs.py
```

The converter authenticates the source manifest, each OBJ, material library,
and referenced PNG before use. It preflights every model before writing any
of them, triangulates simple concave polygons without changing winding,
rejects degenerate or self-intersecting input, and allows at most 0.00001 m
(10 micrometres) of polygon nonplanarity. This tolerance includes the source
bundle's documented approximately 3.1–5.5 micrometre deviations; appreciable
warping is rejected. The actual conversion may still fail on other ambiguous
geometry and must not be forced through.

Vertices retain the source local origin while converting OBJ `(x,y,z)` to
glTF `(x,z,-y)`; UVs convert from the OBJ lower-left to glTF upper-left image
convention. It carries source normals and embeds the referenced PNGs. The
source pivot and yaw remain metadata and are not applied to the mesh. In the
source material, an existing PNG connects directly to Base Color, so textured
GLB materials use a white color factor; untextured materials use their MTL
diffuse color. Neutral roughness and metallic values are preview assumptions.
The retained folder is
a fresh `Saved/CityPCG/NorthMarketReviewGLB_*` directory, and each output is
read back against its generated attributes and texture hashes. A complete
`review_manifest.json` appears only after all four and all input rechecks
succeed. Any folder without that manifest is incomplete and should not be
used; the script never overwrites or removes it.

These are review copies only. Source normals, texture appearance, UV
orientation, pivots, collision and Unreal import have not been validated. In
particular, the roof gaps seen in flat previews need a real 3D review before
deciding whether they are geometry defects. Source-tile section binding,
replacement coverage, actor placement, live visuals and gameplay are also
unverified; the converter does not enable anything in the game.
