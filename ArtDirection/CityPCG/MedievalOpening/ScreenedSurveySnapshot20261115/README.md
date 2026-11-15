# Historical screened-building survey snapshot

These four JSON files preserve an offline baseline of 18 candidate buildings
and the three available tile screening reports. `snapshot_manifest.json`
records the original local file hashes and the canonical LF hashes of these
copies. The contents are historical review evidence, not approval to place
or remove buildings in Gray London. They include Unreal `/Game` package
references but no machine-specific absolute paths.

To rebuild a fresh review-only worklist from this snapshot:

```powershell
python -B Tools/CityPCG/build_screened_worklist.py
```

The generated worklist goes to a fresh file under `Saved/CityPCG/MedievalSurvey`.
Its builder validates every snapshot hash and refuses to overwrite an existing
output. It records screened source face fingerprints, cumulative-baseline
membership, original links and the connected components left after baseline
members are removed. Mixed groups and singletons need their own renewed route
checks, and groups larger than four are flagged for safe partitioning.

The original GLBs, overlay exports and neighboring exports are **not** included;
their recorded SHA-256 pins are historical references, not evidence that those
files exist or still match. The older screening did not pin every settings,
protection and actor input. Before deriving models or masks, recheck the exact
source/overlay and available neighbor hashes, reproduce screening with current
settings and live actor descriptors, and independently verify source GLB
primitive-to-Unreal section identity. The snapshot does not verify collision,
navigation, story routes, streaming, or a playable build. A current complete
cumulative mask and every matching grouped cell are required before any tile
replacement, with original geometry retained for rollback.
