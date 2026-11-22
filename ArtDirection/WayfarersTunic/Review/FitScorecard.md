# Wayfarer’s Tunic fit scorecard

0 of 24 wearers passed every check. 24 failed at least one measured limit. 0 had unresolved coverage as their only remaining issue.

Working limits for this tunic are expressed in millimeters unless stated otherwise. They are design choices for this garment.

| Check | Limit | Wearers passing |
| --- | --- | ---: |
| Front chest clearance at rest | All 27 rays between 3 and 40 mm | 24/24 |
| Front waist clearance at rest | All 27 rays between 3 and 30 mm | 24/24 |
| Extra circumference at the waist | Closed 128-ray garment and body rings, difference 30–80 mm | 24/24 |
| Top of each shoulder at rest | At least 5 of 9 rays hit matching surfaces, each between 0 and 30 mm | 24/24 |
| Following the body | Per-pose 95th percentile change in gap to tracked skin ≤ 3 mm, garment travel at the 95th percentile > 1 cm in all nine moving samples | 24/24 |
| Fabric edge stretch | 95th percentile edge elongation ≤ 20% in each moving sample | 11/24 |
| Contact with wholly unmasked body triangles | Zero garment triangles crossing them in all ten samples | 0/24 |
| Contacts at mask boundaries or on unverified skin | All crossings classified | 0/24 |

## Individual results

| Wearer | Chest max (mm) | Waist max (mm) | Extra waist circumference (mm) | Shoulder max (mm) | Skin tracking, worst p95 (mm) | Edge stretch, worst p95 | Most triangles crossing wholly unmasked skin in one pose | Pose | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| ArchiveApprentice | 20.4 | 9.3 | 51.6 | 20.7 | 0.68 | 19% | 151 | cast_22 | fail |
| BridgeGuard | 32.4 | 12.3 | 55.4 | 14.6 | 0.50 | 19% | 123 | cast_22 | fail |
| CoinClerk | 28.5 | 12.7 | 45.1 | 20.4 | 0.55 | 27% | 316 | cast_22 | fail |
| Dwarf | 28.4 | 8.1 | 56.3 | 16.1 | 0.69 | 28% | 288 | cast_22 | fail |
| Elf | 21.7 | 16.1 | 55.2 | 16.4 | 0.56 | 19% | 122 | cast_22 | fail |
| FerryPilot | 20.8 | 10.2 | 43.6 | 20.3 | 0.54 | 22% | 276 | cast_22 | fail |
| FestivalDrummer | 33.6 | 13.7 | 59.2 | 15.9 | 0.51 | 19% | 128 | cast_22 | fail |
| FrostAmara | 22.5 | 14.6 | 48.6 | 15.6 | 0.53 | 22% | 220 | cast_22 | fail |
| FrostHyeon | 14.5 | 18.7 | 48.3 | 13.9 | 0.48 | 19% | 132 | cast_22 | fail |
| FrostNia | 34.3 | 13.3 | 58.0 | 15.3 | 0.49 | 18% | 120 | cast_22 | fail |
| FrostSaran | 17.9 | 16.7 | 51.7 | 15.0 | 0.48 | 20% | 217 | cast_50 | fail |
| FrostSilas | 24.9 | 20.9 | 51.3 | 18.4 | 0.69 | 23% | 148 | cast_22 | fail |
| FrostTobias | 19.4 | 9.2 | 49.8 | 24.8 | 0.72 | 20% | 105 | cast_22 | fail |
| FrostWen | 23.9 | 18.9 | 54.1 | 17.4 | 0.63 | 21% | 151 | cast_22 | fail |
| GiltBarnaby | 21.5 | 9.8 | 44.8 | 22.8 | 0.59 | 27% | 319 | cast_22 | fail |
| GiltHaruto | 26.6 | 13.8 | 47.1 | 20.3 | 0.65 | 27% | 293 | cast_22 | fail |
| GiltMaren | 31.3 | 9.3 | 39.4 | 20.6 | 0.59 | 24% | 337 | cast_22 | fail |
| GiltPriya | 31.9 | 12.9 | 55.4 | 15.2 | 0.53 | 18% | 129 | cast_22 | fail |
| GiltRamon | 27.7 | 11.1 | 51.3 | 17.9 | 0.67 | 25% | 365 | cast_22 | fail |
| GiltRowena | 31.7 | 12.4 | 56.5 | 15.2 | 0.48 | 19% | 140 | cast_22 | fail |
| GlassArtisan | 27.4 | 11.2 | 53.5 | 23.3 | 0.68 | 22% | 283 | cast_22 | fail |
| IvenRook | 20.7 | 9.8 | 44.2 | 23.1 | 0.51 | 21% | 159 | cast_22 | fail |
| Orc | 32.9 | 14.8 | 55.5 | 15.7 | 0.75 | 18% | 148 | cast_22 | fail |
| TunicFieldTest | 27.2 | 11.8 | 49.4 | 20.5 | 0.60 | 23% | 230 | cast_22 | fail |

## How to interpret the contact counts

The audit intersects the actual fitted garment and skin triangles in each pose. A body triangle counts as unmasked when its entire UV bounding box, including a filtering margin, samples white in the assigned mask. The report separates fully masked areas from mixed areas and face geometry. A raw triangle count measures contact and depends on mesh density.

The bare body also had self-intersections in 216 of 216 moving samples. Of 15977 garment triangle contacts with wholly unmasked body triangles across those samples, 13903 were within 20 mm of a bare-body contact, measured between triangle centers. This test counts intersections between disjoint body triangles whose centers were at least 40 mm apart in the neutral pose. The same garment triangle can be counted in different frames.

The measurements cover the editor’s skinned LOD 0 mesh in the neutral pose, walk, crouch walk and healing cast. The full sample file includes percentiles, sample counts and additional regions around the back and hem. [Full measurements](FitSamples.json)
