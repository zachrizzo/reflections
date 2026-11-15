# Gray London watch-yard stronghold kit

Use the timber gateway as the visible entrance, the pennants to show ownership, and a lantern inside the yard to mark the reclaim point. In the occupied state, the gate carries dark red flags with the existing pale diamond. Reclaimed flags use plain green cloth with a pale border. Reusing the same timber frame keeps streets and sightlines consistent. The capture marker sits on traversable ground in the yard, with the lantern and supplies to one side of the path.

The split reuses the reviewed WatchGate mesh from the medieval watch-yard art. The two banner variants share identical positions, normals, UVs, and pivot. The existing wing, supply cask and archive lantern add a second layer of detail. `placement_recipe.json` gives a relative layout and an existing Trinity watch gate as a survey hint. The hint does not authorize placement, replacement or a new objective at either Trinity landmark identity. Confirm actor identity and current street and story routes first. Leave all existing story markers and adjacent structures in place.

## Offline build

`Source/` contains the pinned original `SM_GL1450_WatchGate.glb` and the verified gate frame and two pennant GLBs. Fetch the repository's Git LFS assets when checking out the kit. The builder reads that original by default, so a separate `Saved` export is unnecessary. To regenerate from the repository root, choose a fresh output folder:

```powershell
python Tools/CityPCG/build_stronghold_kit.py --output Saved/CityPCG/StrongholdKit/TrinityWatchYard
```

The builder checks the source hash and writes three GLBs and their audit to a fresh directory. Raw asset triangles and pivot stay intact. For a live preview, the neutral frame and one pennant mesh replace the combined gate visually at the same transform. Do not stack them over the old gate. The gate and props are cosmetic, with no collision or navigation contribution, so the approach stays open. The existing terrace or yard remains responsible for support and collision.

Run the offline tests with `python -m unittest discover -s Tools/CityPCG -p test_stronghold_kit.py`.

## Reclaim behavior

There is a usable quest path for a single reclaimable site. Start with a localized `NpcCured` objective like the Lantern Gate story beat, then run `Protect` at the watch lantern. The example uses a 2.5 m hold radius and 12 seconds of total time inside it. Protect pauses outside its radius. It does not check for enemy occupancy. `reclaim_step_example.json` is an authoring example. A quest owner must attach it to a reviewed quest, and the encounter owner must supply the local encounter. The cure event tests horizontal distance, so set its `arg` to the reviewed encounter person once they are identified, or confirm the trigger has no conflicting occupants above or below it. The example creates no people or waves.

On successful hold, award the site's explicit `GrayLondon_Stronghold_TrinityWatchYard_Reclaimed` quest unlock. The eventually placed visual controller should read `HasUnlock` on load or stream-in, then refresh on `OnUnlock` and `OnQuestsChanged`. The last event also covers checkpoint application, which restores saved flags without replaying each unlock. Toggle the two cosmetic pennant components so exactly one state appears. The controller only reads quest state. Further sites can use different marker IDs and unlocks with the same environment kit. A citywide quest can require the set of site unlocks once its story design is approved. Shared LAN state needs explicit authority and replication review. The quest snapshot currently provides player checkpoint persistence.

Before integrating, verify the open approach, original sightlines, marker identity, enemy encounter prerequisites, early movement outside the radius, capture feedback, and saved state after reload and World Partition stream-out/in. Test from both street approaches in day and night lighting. Keep the occupied and reclaimed pennants distinguishable by the diamond and border in addition to color. The offline kit does not install the quest, set up the visual controller, or change any map packages.
