# North Market tenancy source-art trial

This trial breaks the long east `0a73564b` frontage into seven narrow,
closed visual shop/house bays: alternating muted red, green and weathered
timber, plank-door and shuttered-hatch motifs, shallow trade boards, timber
divisions and shop sills. The original OBJ and verified FBX remain untouched.
It does not change roofs, create functional doors or alter the people system.
This is a source-art experiment, not an in-game result.

The choice of small trading bays draws on the [Museum of London's archaeological
assessment](https://www.mola.org.uk/sites/default/files/downloads/The%20archaeology%20of%20Greater%20London%20an%20assessment%20of%20archaeological%20evidence%20for%20human%20presence%20in%20the%20area%20now%20covered%20by%20Greater%20London_Part1.pdf),
pages 230–231, which discusses numerous small London shops and later rows.
The design is period-inspired, not a reconstruction of a specific surviving
frontage.

`north_market_tenancies.py` starts with the hash-pinned original OBJ, MTL,
texture manifest and surveyed plan. It constructs additional geometry on the
three suitably oriented exposed front spans, suppresses listed party walls,
reserves the existing doorway, and checks every added box edge against the
surveyed plot, including concave boundary crossings. It writes a *new* complete
OBJ plus a separate overlay OBJ, with the original source bytes retained as
the complete OBJ's prefix. Materials and textures accompany both; no reviewed
asset is overwritten. The door and hatch shapes are decorative panels backed
by the original closed shell.

The small geometry tests run without Blender or the editor:

```text
python -B Tools/CityPCG/test_north_market_tenancies.py -v
python -O -B Tools/CityPCG/test_north_market_tenancies.py -v
```

## Hosted before/after review

For a future reviewed run, extend the existing `north-market-hosted-roundtrip`
GitHub-hosted workflow's sparse checkout with these files and the pinned east
plan:

```text
Tools/CityPCG/north_market_tenancies.py
Tools/CityPCG/north_market_tenancy_preview.py
Tools/CityPCG/test_north_market_tenancies.py
ArtDirection/CityPCG/MedievalOpening/FollowOn20261115/north_market_east_plan_20261115.json
```

After the original east-0a FBX export and clean-process verification succeed,
run the small tests, then on that matrix row only run:

```bash
python3 -B Tools/CityPCG/north_market_tenancies.py
"$blender" --background --threads 2 --factory-startup --python-exit-code 1 \
  --python "$GITHUB_WORKSPACE/Tools/CityPCG/north_market_tenancy_preview.py"
```

Upload the fresh `ci-north-market-tenancy/` folder as a **separate review-only
artifact** with short retention. The preview script imports and checks the
original FBX and the overlay's geometry, winding, UVs, normals and material
assignments, then renders eye-level and three-quarter before/after pairs with
identical cameras and lighting. The originals stay available for comparison.
The renderer and generated variant have not yet run in Blender; strict checks
may expose an import difference and stop before rendering. No workflow has
been triggered by these instructions.

`make_details` accepts a surveyed local footprint, a door exclusion and party
edge indices, so its box generation, variation and containment checks can be
reused. The current entrypoint and +X-facing front selection are deliberately
pinned to **one** east building and its two-building plan, which currently lists
no party walls. Other parcels need their own verified frontage directions,
complete cross-plan party-wall data, route constraints and review; this is not
a citywide placement system yet. Within-footprint geometry cannot prove live
road clearance or the behavior of the loaded actor. Blender output still needs
visual review and a separate FBX round-trip; Unreal needs material, scale,
placement, collision, navigation, road and gameplay checks before activation.
