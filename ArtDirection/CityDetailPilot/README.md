# Gray London street-detail pilot

Four shopfronts on the introduction street near Great Tower Street / Mark Lane
now have weathered materials, modeled doors and display windows, pilasters,
cornices and striped awnings. Three removable panels carry fictional shop and
pub signs for Lamplight Books, Mark Lane Provisions and The Lantern Room. Two
pavement sections, two street lamps, one warm point light, a bench and two cycle
hoops dress the same block.

The Unreal assets are in `/Game/GrayLondon/CityDetailPilot/`, with the finish
assets under `StreetFinish`. Four World Partition actors labeled
`CityDetailPilot_1` through `CityDetailPilot_4` carry the base shopfronts. Their
positions came from wall and ground traces, and the imported meshes have UVs,
assigned materials, base-center pivots and approximately 4.07 m × 3.20 m face
dimensions. This folder contains the source FBX files, textures and build scripts.

The [lit Unreal viewport capture](../../Saved/Screenshots/WindowsEditor/street_finish_qa.png)
confirms the signs read in the correct orientation. The temporary camera was
removed after capture. All four shopfront actors now have the `NoCollision`
profile and actor collision disabled. Ground rays reached the original city
surfaces beneath the awnings, and capsule sweeps using the hero's dimensions
passed in front of the three signed shops. A gameplay walk and a World Partition
unload/reload check are still pending. `shopfront_preview.png` and
`unreal_base_color.png` show the earlier prototype.

## Next production passes

1. Model No. 27 Great Tower Street on its mapped south-side footprint with
   red brick, Portland stone dressings, a pedimented entrance and a tiled
   mansard with dormers. Build the distinct stone office arches and glazed
   corner of Mark Lane from the junction photos. Place the separate 60–61 Mark
   Lane façade on its east-side parcel. [London photo references](PHOTO_REFERENCES.md)
2. Walk the intro block with the gameplay camera and check navigation, ground
   contact and World Partition streaming before propagating the kit to other
   streets.
3. Continue toward Byward Street, Tower Hill and Leadenhall. Use the mapped
   narrow approach to Lime Street Passage and build the market's own arched
   entrance, painted ironwork and glazed roof.

Independent source modeling, reference gathering and material work can run
concurrently. Editor imports, placement and saves should be coordinated in the
shared editor. The previous local Hunyuan3D-2 workflow has geographic licence
restrictions that require review before its outputs are selected for release.
