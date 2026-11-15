# Medieval London market dressing — review source

This small kit is being prepared to add street-level activity around the new
medieval buildings. It contains a movable plank trestle, a turned wooden bowl,
and an alehouse stake with foliage. The forms are artist reconstructions for
game use; they are not scans or exact reconstructions of particular objects.
The kit does not include people or the Merchant Gate being built separately.

## Historical references

- The Corporation of London's records include a 1375 ordinance limiting the
  projection of tavern ale-stakes bearing signs or foliage. See Henry Thomas
  Riley's edition of the original records, [*Memorials of London*, p. 386](https://upload.wikimedia.org/wikipedia/commons/1/16/Memorials_of_London_and_London_life%2C_in_the_XIIIth%2C_XIVth%2C_and_XVth_centuries_-_Being_a_series_of_extracts%2C_local%2C_social%2C_and_political%2C_from_the_early_archives_of_the_City_of_London%2C_A.D._1276-1419_%28IA_b2485881x%29.pdf).
  The model's hoop, leaf shapes and construction are design choices; use this
  particular prop to identify an alehouse, not every shop.
- A London Museum [archaeological collection record](https://www.londonmuseum.org.uk/collections/v/object-371680/bowl/)
  documents a late-13th-century turned ash bowl from Milk Street, approximately
  195 mm in diameter and 45 mm high. Our bowl uses those dimensions and a
  plausible turned profile, but is not a scan of the object. Its use in a
  later market scene is an inference.
- London and Middlesex Archaeological Society research on
  [medieval and Tudor shops](https://www.lamas.org.uk/wp-content/uploads/2024/09/Vol-40.pdf)
  cites a movable stall leased at Ludgate in 1375 and describes movable boards
  used at markets. Our planked trestle is an interpretation of that evidence,
  not a surviving measured example.
- Hugh Alley's [1598 New Fish Street drawing](https://mapoflondon.uvic.ca/NEWF1.htm)
  offers later visual context for street-side trading. It is post-medieval;
  the Folger's [curatorial commentary](https://folgerpedia.folger.edu/Scholars%27_insights_on_Open_City%3A_London%2C_1500%E2%80%931700)
  cautions that Alley's marketplace views can present an idealized plan.

No museum image or external artwork is copied into these assets.

## Bounded generation

The generator is prepared but has **not yet been run on the real kit**. It
requires Windows, Python and Pillow. Once the other offline generator has
finished, run only if the editor is back, the leading train is loaded, no
compiler/build/cook or restart is active, and at least 4 GiB physical / 10 GiB
commit headroom is available. An ordinary NPC PIE lease may coexist because
this job never accesses Unreal; restart/build leases fail closed. The job caps
its source geometry at 2,400 triangles and its output at 12 MiB. It checks
private process memory against 160 MiB and elapsed time against 30 seconds at
intervals; those checks are not hard operating-system limits.

Compiler checks use a Windows process snapshot, including PIDs and parent
PIDs. The only `gcc.exe` exception is a process whose full path is the local
Gigabyte Control Center executable and which has a matching `GBT_DL_LIB.exe`
child with a compatible process creation time. Any other `gcc.exe`, any
listed compiler/build process, an unreadable snapshot, or inaccessible
identity information stops the job. Memory thresholds remain unchanged.

A bounded in-memory audit evaluated the drafted trestle, bowl and ale-stake
at 372, 704 and 396 triangles respectively. The emitted OBJ coordinates, UVs
and normals are finite, and each rounded triangle's winding agrees with its
normal. The bowl measures 195 mm across by 45 mm high, rests at z=0 and has
outward-facing exterior and inward-facing interior surfaces. The ale-stake's
wall bracket surrounds its origin and its farthest geometry projects about
1.307 m along +X. These checks do not establish watertightness, visual
quality, texture appearance, Unreal import or collision behavior.

```powershell
python ArtDirection/CityPCG/MedievalOpening/MarketDressingKit/test_market_dressing.py -v
# Run only in a coordinated safe window:
python ArtDirection/CityPCG/MedievalOpening/MarketDressingKit/build_market_dressing.py
```

A successful run creates a fresh, non-overwriting
`Saved/CityPCG/MedievalMarketProps_*` directory containing three OBJ files, a
shared MTL, a PNG preview rendered from the source meshes, and a hash manifest.
Each prop is in metres, with +Z up and +X outward from the frontage; the bowl
and trestle have ground-level origins, while the ale-stake's origin is its wall
mount. A directory without `manifest.json` is incomplete and should not be
used. Nothing is imported into Unreal, placed in the map, or enabled in game.
OBJ axes, UVs, normals, flat-color materials, collision, visual appearance and
gameplay placement all require review in the real toolchain.
