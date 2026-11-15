# First-view corner story clearance

The saved FirstPage and Frank marker packages contain a single typed
`RelativeLocation` FVector apiece. Their XY values fall outside the original
shell when interpreted as world coordinates. The published planning points
for both markers fall inside. Retain both sets of guards until the loaded
actor transforms and runtime behavior are confirmed.

| Marker | Published XY clearance to shell | Serialized-relative XY hypothesis | Hypothesis clearance after 0.52 m capsule and reserve |
| --- | ---: | ---: | ---: |
| FirstPage | −5.072095 m | 1.781927 m | 1.261927 m |
| Frank Dunning home | −3.114843 m | 1.582611 m | 1.062611 m |
| Weigh-House stair | 0.743549 m | 0.743549 m | 0.223549 m |

The straight saved-coordinate probe from Frank to the stair has 0.223549 m
of remaining lateral clearance against this shell. The nominal probe runs
into the footprint. Both are planning probes and cover only this shell.
The loaded hero capsule and the actual walk may differ. The 25 m nominal
stair guard covers all eight footprint vertices, with the farthest at
21.699930 m. The 255.791521 m² Weigh-House reservation overlap still applies.

The UE package evidence matches the actor label and the serialized tag
`RelativeLocation / StructProperty / /Script/CoreUObject.Vector`, with a
native 24-byte payload. FirstPage comes from
`9/BQ/WOAAHAQTHPOHYIU0WI5GSH.uasset` at byte 4642. Frank comes from
`9/7S/P2MSGDZBGCXVFNH5MGY2AR.uasset` at byte 4661. The report records the
complete package and payload SHA-256 values, offsets, and exact coordinates
for all five checked markers. FirstPage's saved XY is 10 m east of its
planning point and Frank's is 6 m southwest. Both offsets match candidates
in the original placement spiral. That placement script uses a ground
trace and adds 5 cm to the hit height. Attachment and world transforms
require live confirmation.

The two nominal XY points fall under the source export's 15 m roof.
At the saved relative XY coordinates, neither point nor the stair has a
road, roof, park, or water triangle directly underneath in the tile
export. Their saved Z values are about 0.15 m and their current floor
support is unresolved. The Lamplight package distinguishes a known road
case. Its saved Z is 0.33 m and the export has road at 0.28 m.

At the saved FirstPage coordinates and authored yaw zero, three camera
keys lie inside the original shell or intersect it on the way to the
look target. The runtime can snap the anchor to ground and turn it to
find stage depth. Test the resolved FirstPage origin and heading against
the current scene before changing its sightline.

## Geometry proposal and handoff

Prepare a full inboard render shell using the eight source edges, a
0.20 m base, and the complete original roof at Z 15 m. Wrap the timber,
lime-render and stone treatment around the whole shell. Recess detail
inside the wall planes. Retain the original collision footprint, roof
support, three sealed party edges, road and paving surfaces, and all
story actors. Reconcile the three front bays and Wheatsheaf support from
the existing spawn review only after the geometry and story checks pass.

Keep a pitched roof, exterior projection, altered collision, and interior
changes out of the first proposal. The existing guard covers the entire
plot and the exact playable stair, landing and cutscene volumes still
need measurement. The render shell can be prepared offline while the
source and map disposition stay blocked.

Under the active lease, the next review needs the saved and loaded root
transforms, live world transforms and attachments, actual floor hits at
FirstPage and Frank, the stair and roof landing, an actual hero capsule
sweep along the route, and the resolved FirstPage camera and look rays.
Confirm that the first page pickup and Frank's Home arrival still work
in a baseline run. Compare that baseline to any later full-shell proposal.

The five marker packages, original tile asset, and its external actor
package were tracked and clean during the offline check. The Gray London
map file had an on-disk tracked modification. The offline check cannot
establish editor-memory dirtiness or unsaved Multi-User changes.

## Reproduce

```powershell
python -B Tools/CityPCG/survey_spawn_story_clearance.py
python -B -m unittest discover -s Tools/CityPCG -p 'test_survey_spawn_story_clearance.py' -v
```
