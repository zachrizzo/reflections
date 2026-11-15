# Gray London — source and build notes

These notes describe the original development project and its exploratory work. This repository includes the assets referenced by the Gray London level, not every asset mentioned as imported or evaluated below. In this repository the shop awnings use an original substitute mesh; the City Street Props awning referenced in the historical notes is not distributed here. The complete Noto Serif license is included as `OFL-NotoSerif.txt` in this directory. Some notes refer to development-workspace files that are not included in this repository.

The geographic geometry is derived from OpenStreetMap data © OpenStreetMap
contributors, available under the Open Database License (ODbL):
https://www.openstreetmap.org/copyright and https://opendatacommons.org/licenses/odbl/.
The source extracts were downloaded from Geofabrik:
https://download.geofabrik.de/europe/united-kingdom/england/greater-london.html.

The current Greater London extract was compared with the 1 January 2014
extract. The current extract has more mapped geometry; it is **not** a
verified 1980–2009 reconstruction. Features explicitly tagged as starting
after 2009 were excluded from generated building geometry. Undated buildings,
shops, and infrastructure require historical verification. Heights are taken
from height or building-level tags when available and otherwise estimated.
Road widths are taken from width tags when available and otherwise estimated
by road classification. The tile manifest retains OSM IDs and whether each
feature ID was present in the 2014 source.

Coordinates are in British National Grid (EPSG:27700), with the local origin
at 51.5080° N, 0.1281° W. The generated area is clipped to a 5,650 m radius.
The imported meshes are a work in progress and do not establish that all
landmarks, building details, shops, bridges, or period features are complete.

## External visual assets

The Buckingham Palace, Tower of London, Tower Bridge, St Paul's Cathedral,
Palace of Westminster, London Eye, Westminster Abbey, 30 St Mary Axe
(the Gherkin), Albert Bridge, Royal Albert Hall, and National Theatre models
are adapted from Codriver 3D, © 2026 Codriver, licensed under CC BY 4.0:
https://3d-assets.codriver.io/ and https://creativecommons.org/licenses/by/4.0/.
Their geographic placement also uses © OpenStreetMap contributors, ODbL 1.0.
The models were decompressed, their axes converted and their meshes combined
for Unreal; generic OpenStreetMap building massing within the landmark
footprints was removed. The models are visual approximations, not surveys;
the source's catalogue and model-specific notes are retained in the workspace.

Road, grass, roof, pavement and brick texture assets and the street-lamp model
are from Poly Haven (https://polyhaven.com/), licensed CC0. The street-lamp
mesh is used at mapped 2014 OSM positions; the lamp design at each position
has not been individually verified. Its generated LODs modify the source mesh.

Tower Bridge uses an added approximate walkable deck and approach ramps to
connect its detailed model to the generated streets. The road heights and
approaches are gameplay approximations, not a surveyed terrain profile.
Overlapping OSM bridge and tower massing was removed to keep the arches open.

The perimeter ash tree was generated with Cosmo Tree Gen by FrogCosmonaut
(MIT license; see LICENSE_COSMO_TREE_GEN.md),
https://github.com/FrogCosmonaut/cosmo_tree_gen. Its source leaf texture is
credited by that project to CC0 vegetation textures at
https://opengameart.org/content/60-cc0-vegetation-textures; its bark texture
is credited to ambientCG Bark014, https://ambientcg.com/view?id=Bark014
(CC0). The model was exported and adapted with masked foliage materials and
automatic Unreal LODs. Perimeter placements are procedural, not mapped trees;
foliage currently has no collision.

Traffic-signal proxies use 2014 OSM traffic-signal nodes and approximate
roadside offsets and orientations inferred from nearby mapped road centerlines.
An OSM signal node does not necessarily locate an individual signal head,
so these placements and the generic UK signal design require local review.
They are static visual props without collision or working signal cycles.

Forty-five K6 telephone kiosks are visual approximations placed at 2014 OSM
nodes explicitly tagged booth=K6, excluding nodes inside current mapped
buildings. Four tagged black are black; unspecified colors default to red.
The design uses the Science Museum Group K6 example dimensions and Historic
England description: https://collection.sciencemuseumgroup.org.uk/objects/co8406900
and https://historicengland.org.uk/listing/the-list/list-entry/1420380.
Orientation is unverified, glazing is opaque, and interiors, working doors,
phone equipment and crowns are not modelled. Presence at every location during
the requested period has not been established.

Eighteen tiles across west and north-central London have an experimental
residential facade pass on 3,689 selected unnamed residential footprints
present in the 2014 extract. The pass adds 3,283 inferred entrances. Windows, doors,
brick finish and door positions are procedurally inferred, not measured or
historically verified. The underlying brick texture is Poly Haven Yellow Brick
by Rob Tuytel (CC0), https://polyhaven.com/a/yellow_brick, modified to add
painted sash-window imagery. Entrances are inferred from road proximity and
an unobstructed outward path; placement and building styles require review.

A Trafalgar Square Waterstone's sign prototype uses the historical apostrophe.
A 2006 stockist list places Waterstone's in the Grand Building:
https://davewalker.com/the-book-in-waterstones/. The sign's precise placement and design still need historical verification.

The pillar postbox mesh is adapted from London Street Props (Free) by
Minimaliano, CC BY 4.0: https://www.fab.com/listings/3a15c74a-8a6f-4f51-b488-28cb6da0205c
and https://creativecommons.org/licenses/by/4.0/. Its imported material was
replaced with a red material. Twenty-four placements use 2014 OSM nodes tagged
as pillar postboxes, omitting nodes explicitly tagged as having two apertures
and those inside current mapped buildings. Orientation is inferred from the
nearest road; individual design, royal cypher and period presence are not
verified.

Nelson's Column has an original, simplified upper-column model centered on
the OSM shaft footprint, with the OSM stepped pedestal retained. The fluted
shaft, bronze-colored capital and approximate crowning silhouette are based
on https://historicengland.org.uk/listing/the-list/list-entry/1276052.
The figure is a placeholder, not a faithful portrait; the capital ornament,
bronze reliefs and four Landseer lions remain incomplete. The surrounding
square and statue placement require further review.

The National Gallery retains its OSM main building footprint with a custom
schematic eight-column portico and dome aligned to mapped building parts;
the overlapping generic portico and dome extrusions were removed. References:
https://historicengland.org.uk/listing/the-list/list-entry/1066236 and
https://www.nationalgallery.org.uk/exhibitions/past/ng-stories/looking-for-a-new-home.
Steps, column ornament, pediment sculpture, exact dimensions, doors and the
remaining facade are approximations or incomplete.

Trafalgar Square's two ornamental fountain basins use the current mapped OSM
quatrefoil outlines (ways 10515369 and 26095439), with a simple granite-colored
retaining rim and schematic marble vase centrepieces. Their historic form is
described by Historic England: https://historicengland.org.uk/listing/the-list/list-entry/1066235
and London City Hall: https://www.london.gov.uk/who-we-are/city-halls-buildings-and-squares/trafalgar-square.
Dimensions and centrepiece profiles are approximations; bronze sculpture,
water jets, ripples and detailed stonework remain to be built. Water surfaces
are the existing static OSM polygons.

The Thames now has hidden, two-sided player collision following a simplified
current OSM shoreline, with openings generated around named bridge road and
footway geometry. This prevents ordinary walking into most of the river while
keeping crossings open; it is a gameplay boundary, not swimming, a flood model,
or a surveyed embankment. An in-game character was stopped at one Westminster
riverbank and walked across Westminster Bridge from west to east. Other bridge
openings and irregular quay geometry require individual testing, and piers or
places with access to the water may need custom treatment.

Grand Buildings (1 Strand), whose 1986–1991 redevelopment included a public
retail arcade, is now represented by an original schematic mesh following its
current OSM footprint. Its seven-storey stone facade, arched windows, recessed
shop glazing, open arcade and simplified slate roof are approximations based on
Sidell Architects' project photographs and description:
https://sidellarchitects.com/projects/grand-buildings/. The original OSM solid
massing was removed. Individual window positions, dimensions, roof pavilions,
dormers, endangered-species carvings and shop interiors remain incomplete.
The Waterstone's sign is provisional; the 2006 branch location is documented
above, while its exact design and position have not been confirmed. An in-game
character entered the arcade through an arch; full route and collision testing
remain necessary.

St Martin-in-the-Fields is represented by an original schematic exterior at
its mapped OSM footprint, replacing the earlier generic mass. Its two-tier
window bays, hexastyle portico, clock tower and steeple follow the broad
architectural description in Historic England's listing:
https://historicengland.org.uk/listing/the-list/list-entry/1217661. The spire
height is approximately 192 feet above the floor, based on
https://www.londonparishclerks.com/Parishes-Churches/Individual-Parish-Info/St-Martin-in-the-Fields.
The columns, stonework, clock, roof, steeple stages and dimensions are simplified
and not surveyed; sculpture, railings, the crypt and church interior are not
modeled. A character walked up the corrected steps into the portico in PIE.

Cecil Court has four schematic, non-interactive shop fronts representing
Watkins Books (19), Travis & Emery (17), Goldsboro Books (7) and Marchpane
(16). Their names and addresses are documented in June–July 2009 by Londonist:
https://londonist.com/2009/07/biblio-text_travis_and_emery_watkin and
https://londonist.com/2009/06/biblio-text_marchpane_goldsboro_boo. The 2014
OSM shop nodes provide approximate along-street positions; wall anchors were
corrected to face Cecil Court and the even/odd sides, rather than blindly using
the nearest wall. Painted signs, illustrated book displays, closed doors and
projecting frames are original approximations inspired by those references;
exact placement, widths and detailed window displays remain unverified. No
interior is provided. A character traversed the lane in PIE after placement.

Cecil Court now has two original approximations of the historic St Martin's
cast-iron gas lamp columns and Upright Rochester lanterns. Their centerline
locations are inferred from the 2014 shop locations at nos. 7 and 19–21 and
the mapped pedestrian route; they are not individually surveyed. Reference:
https://historicengland.org.uk/listing/the-list/list-entry/1488411. The spiral
shaft, ladder rest, glass globe and hood are simplified; lettering, reliefs,
asymmetric scrollwork and functioning gas light are not modeled. The upper
street-facing facades on the two OSM building footprints are a repeated,
inferred brick-and-sash-window texture, not an architectural survey of the
individual buildings. The underlying brick diffuse is Poly Haven Brown Brick
02 (CC0): https://polyhaven.com/a/brown_brick_02.

Broad visual pass (prototype): 120 streamed OSM city tile actors use the
repeated London-stock brick and sash facade material for generic building
walls; the central landmark tile remains on its earlier treatment. Window
positions and brick finishes are illustrative, not an architectural survey.
The underlying Poly Haven Yellow Brick is CC0: https://polyhaven.com/a/yellow_brick.

4,626 mapped 2014 tree points are represented by 85 streamed hierarchical
instance groups. Points were filtered for tree pits, current building/road and
water conflicts and spaced/capped for performance. All use the existing
procedural ash asset as an approximate species and have no foliage collision.
The 2014 map snapshot and inferred height/species do not establish the exact
appearance of every tree in the requested era.

1,300 anonymous, non-interactive shopfronts are distributed across 81 streamed
tiles using 2014 shop nodes and inferred road-facing walls. Displays, signs,
widths, materials and entrance positions are schematic. No business identity
or historical operation date is asserted. The locations use OSM data:
https://www.openstreetmap.org/copyright. A limited two-tile visual check was
performed; other areas and their performance need broader play-testing.

The Cenotaph in Whitehall is an original schematic mesh located at the mapped
OSM memorial site, based on https://historicengland.org.uk/listing/the-list/list-entry/1357354
and the flag order documented in https://flaginstitute.org/pdfs/TCOF_Dec-2011.pdf.
Flags, inscriptions, wreaths and architectural details are approximations; no
animated cloth or ceremony is represented. The playable level was checked
visually at the monument.

Cecil Court has a simple pedestrian paving surface following the OSM road
centerline. The tile pattern is illustrative and uses Poly Haven concrete
pavement 02, CC0: https://polyhaven.com/a/concrete_pavement_02.

A first pass adds 191 bins and 227 bollards in 66 streamed instance groups at
filtered 2014 OSM node positions. The chosen London Street Props (Free) meshes
by Minimaliano are recolored dark; the individual prop design and exact
period presence are approximations. The props have no collision. Source and
CC BY 4.0 attribution: https://www.fab.com/listings/3a15c74a-8a6f-4f51-b488-28cb6da0205c
and https://creativecommons.org/licenses/by/4.0/. Filtering uses estimated
road widths and existing prop/tree locations; placements need ongoing review.

272 OSM bench-node locations are populated with an original generic slatted
bench in 42 streamed instance groups. The design and road-facing orientation
are inferred, not surveyed; the benches currently have no collision or sit
interaction. The wood texture is Brown Planks 03 by Poly Haven (CC0):
https://polyhaven.com/a/brown_planks_03. Locations derive from 2014 OSM data:
https://www.openstreetmap.org/copyright. Ground height is approximated to the
flat road/park surfaces and requires review at individual sites.

An inferred road-marking layer adds 30,920 broken white centre-line strokes
across 118 streamed tiles. Placement uses current road centerlines whose OSM IDs
also occur in 2014, excluding explicit divided, one-way, bridge and tunnel
ways, and omitting strokes near detected junctions and crossings. The 2 m
mark/4 m gap is based on the 2003 Traffic Signs Manual, chapter 5:
https://upload.wikimedia.org/wikipedia/commons/8/83/UK_Traffic_Signs_Manual_-_Chapter_5_Road_Markings._2003_%28Sixth_Impression_2009%29.pdf.
These are visual approximations, not surveyed paint or proof of 2009 layout;
a small number of play views were checked. More junction, collision,
streaming and performance checks remain necessary.

South Africa House retains the mapped OSM building mass with an original,
schematic frontage overlay based on the general 13-bay arrangement and central
entrance described at https://historicengland.org.uk/listing/the-list/list-entry/1066238.
Architectural detailing and side elevations remain simplified.

A generated, panning normal texture adds subtle surface ripples to the 73
mapped water-tile material overrides. This remains an opaque visual surface:
there is no simulated depth, swimming or physical water, and the outer boundary
water retains its earlier material. The ripple map is original procedural work.

181 inferred zebra crossings with 357 static schematic beacons occupy 65
streamed tiles, based on explicitly tagged 2014 OSM zebra nodes and inferred
road widths/directions. Paint and beacon locations are approximations, not a
survey, and there is no flashing, zigzag paint, crossing logic or collision.
The layer was checked at a sample crossing; remaining sites require wider
review. Sources: https://www.openstreetmap.org/copyright and
https://www.legislation.gov.uk/uksi/1997/2400/schedules/made/data.xht?wrap=true.

Forty generic city tiles use a muted red-brick facade variant to add visual
variety. Assignment is procedural by tile and is not building-specific. The
brick source is Poly Haven Red Brick 03 (CC0): https://polyhaven.com/a/red_brick_03.
Twenty-four shop prototypes that exceeded the mapped building height or were
on elevated building parts were removed after a geometry audit.

### Canada House frontage
An original schematic frontage and north portico overlay approximates Canada House at Trafalgar Square, following the OpenStreetMap footprint. It is not a surveyed reproduction; six overheight nested OSM parts have been omitted, retaining the four-level outer mass. The design references [Historic England listing 1217724](https://historicengland.org.uk/listing/the-list/list-entry/1217724) and [Westminster conservation area audit](https://www.westminster.gov.uk/sites/default/files/media/documents/Trafalgar%20Square%20conservation%20area%20audit%20SPG.pdf). Footprint data © OpenStreetMap contributors, ODbL.

### Underground signs
104 generic, non-interactive Underground roundel markers are placed near 2014 OpenStreetMap subway entrances, distributed in 36 streamed tiles. Locations and orientations are inferred from mapped entrances and current road/building footprints; they are not surveyed historic sign positions, station entrances, or accessible Underground interiors. Footprints and entrance data © OpenStreetMap contributors, ODbL. Fifteen earlier candidates were excluded after full-width sign clearance checks.

### Imported fountain scan (not yet placed)
[Drinking Fountain Trafalgar Square West](https://www.fab.com/listings/d7607613-327e-4d7c-9156-eb204314b567), by artfletch, CC BY 4.0, imported from Fab. The source scan includes surrounding surface geometry and its initial trial was removed pending adaptation. The 1960 fountain is described on the [creator’s model page](https://artfletch.com/models/drinkingfountaintrafalgarsquarewest/).

### Additional street lamps
204 inferred additional streetlight proxies use locations from current OpenStreetMap near streets mapped in 2014, grouped in 48 streamed actors. Their 1980s–2000s presence and exact designs have not been established; the two original simplified lamp designs are approximations. Mapped points © OpenStreetMap contributors, ODbL.

### Skyline period adjustments
Five clearly post-2009 buildings (The Shard, the News Building, One Blackfriars, 100 Bishopsgate and 8 Bishopsgate) were excluded from the generated mesh. Some sites may be empty or occupied by other mapped structures; historical replacements remain to be researched. See the project build documentation and source notes for individual feature IDs and dates.

### Bus shelters and additional landmarks
100 simplified bus shelters are inferred near 2014 OpenStreetMap stops tagged as having shelters, in 49 streamed actors. Thirty-six candidates were removed after path and cycleway checks; 23 retained shelters were raised for mapped pavement. Their exact historic form and location are not established. Map data © OpenStreetMap contributors, ODbL.

The Victoria Memorial and Harrods frontage are original schematic approximations based on their mapped footprints and Historic England descriptions: [Victoria Memorial](https://historicengland.org.uk/listing/the-list/list-entry/1273864) and [Harrods](https://historicengland.org.uk/listing/the-list/list-entry/1294346). Their fine architectural and sculptural details are not surveyed. The former 6–8 Bishopsgate and 150 Leadenhall Street are schematic masses on 2014 OSM footprints, based on [Greater London Authority planning records](https://www.london.gov.uk/sites/default/files/public%3A/public%3A/PAWS/media_id_354895/6-8_bishopsgate_and_150_leadenhall_report.pdf); 150 Leadenhall's height is estimated.

### Admiralty Arch
An original schematic centre frontage follows mapped Admiralty Arch geometry and retains the existing open Mall passage. The source footprint © OpenStreetMap contributors, ODbL; its historic listing is [Historic England 1238982](https://historicengland.org.uk/listing/the-list/list-entry/1238982). Arch geometry and detailing are approximate.

### Bus-stop markers
73 generic bus-stop poles are inferred near 2014 OpenStreetMap nodes associated with the retained shelters, grouped in 37 streamed actors. The precise historical stop location and signage are not verified. Map data © OpenStreetMap contributors, ODbL. The original simplified flag references [TfL bus-stop graphics standards](https://content.tfl.gov.uk/buses-bus-stop-graphics-standard-issue02.pdf); it has no route numbers or vehicles.

### Tower Bridge navigation correction
The OSM north-gate and abutment extrusions and two associated floating parts were omitted where they conflicted with the independent Tower Bridge model. The separate misaligned supplemental approach-ramp actor is hidden and collision-disabled; the bridge model retains complex collision. A north-to-south player traversal was tested along the road centerline, including the formerly blocked seam. Other routes remain subject to local play testing.

### British Museum and Royal Exchange
The British Museum colonnade and Royal Exchange portico are original schematic overlays on mapped building parts. They are not surveyed reproductions. References: [British Museum's building history](https://www.britishmuseum.org/sites/default/files/2022-03/Greek_Revival_simplicity_and_splendour_press_release.pdf), [Camden planning record](https://www.camden.gov.uk/documents/d/guest/3-mb-pack-british-museum), and [Historic England: Royal Exchange](https://historicengland.org.uk/listing/the-list/list-entry/1064713). Geographic footprints © OpenStreetMap contributors, ODbL.

### London Bridge navigation correction
Two mapped buildings beneath the real elevated bridge, including the Old Ale Mug House, were omitted from the flat prototype where their extrusions blocked the carriageway. The south approach was tested in both directions, and the full north-to-south crossing was also tested. This is an acknowledged loss of the real grade-separated buildings; the bridge and its undercroft need a future elevation-aware reconstruction. Other lanes and footways have not been exhaustively tested.

### London Bridge parapets
Original schematic granite parapets and metal handrails follow inferred positions near the mapped bridge edges; dimensions and small breaks at paths are approximate. References: [Illuminated River](https://illuminatedriver.london/bridges/london-bridge) and [Building, 1973 bridge archive](https://www.building.co.uk/our-history-180-years-of-building/from-the-archives-the-new-london-bridge-1973/5130375.article). Geographic data © OpenStreetMap contributors, ODbL.

### Somerset House and St Pancras
Somerset House's Strand block is a schematic stone replacement on its mapped footprint, with two rectangular openings following mapped footway and service routes. Their widths and heights are inferred, and the real facade's detail and third arch are not fully reproduced. Both mapped openings were walked in both directions; one was rechecked after the Waterloo tile update. Reference: [Historic England, Somerset House](https://historicengland.org.uk/listing/the-list/list-entry/1237041).

The former Midland Grand Hotel at St Pancras has original simplified red-brick and Gothic frontage overlays and an approximate clock tower. Its exact tower position, dimensions and details are not surveyed; no post-2011 hotel branding is included. Reference: [Historic England listing 1342037](https://historicengland.org.uk/listing/the-list/list-entry/1342037). Geographic data © OpenStreetMap contributors, ODbL.

### Waterloo Bridge and BFI Southbank
The BFI footprint was locally cut around mapped bridge-road and footway corridors because the flat prototype otherwise blocked Waterloo Bridge. About 23% of the mapped mass remains; this is a visual compromise and does not reproduce the building beneath an elevated bridge. A main road lane was tested in both directions; other paths have not been exhaustively checked.

### Marble Arch, Wellington Arch and Shaftesbury Memorial
Original schematic models replace three generic OSM extrusions. Marble Arch has a tested central opening and solid pier collision; Wellington Arch has an estimated 7.4 m opening tested in both directions along mapped Apsley Way. The Shaftesbury Memorial uses a stylized archer and fountain body without working water; its plinth has collision. These models simplify sculpture and architectural detail. Sources: [Marble Arch](https://historicengland.org.uk/listing/the-list/list-entry/1239534), [Wellington Arch](https://historicengland.org.uk/listing/the-list/list-entry/1278092), [Shaftesbury Memorial](https://historicengland.org.uk/listing/the-list/list-entry/1265625), and © OpenStreetMap contributors, ODbL.

### Central facade post-process
A selective original stone/window material is applied above 5 m on 52 ordinary 2014-present buildings in the central tile, excluding the audited landmark and Piccadilly sign-host footprints. The texture and window layouts are schematic. **Rebuilding Tile_p00_p00 from the raw city generator will remove this post-process.** The development workspace's `work/agent_assets/central_facade_selective/REGENERATION_GUARD.md` describes the validation guard; its one-shot transform must be adapted to a future scratch rebuild before staging. The current Unreal tile and component material overrides are saved.

### Piccadilly period signs
Eighteen original generic, static advertising panels use fictional text and graphic motifs inspired by late-20th-century signboards. Their exact historic layout is not established; they follow the current mapped facade. Map source © OpenStreetMap contributors, ODbL.

### Trafalgar Square and Piccadilly pedestrian paving
Original schematic stone paving is clipped to mapped 2014 pedestrian-area polygons for [Trafalgar Square](https://www.openstreetmap.org/way/150915463) and [Piccadilly Circus](https://www.openstreetmap.org/way/106771450), with approximate exclusions for roads, buildings, steps, fountains, monuments and Underground entrances. Geographic data © OpenStreetMap contributors, ODbL. Coverage is approximately 4,924 m² and 1,296 m² respectively; the slab pattern is illustrative rather than a surveyed historical reproduction. The Piccadilly memorial has a conservative clearance of about 0.65 m around its modeled steps. Both surfaces have triangle collision, and sampled floor and walking tests were performed; paths and entrances have not been exhaustively tested.

### Outer boundary repair and lighting
The 96 invisible collision segments were corrected to stand upright and follow the perimeter tangentially. The underlying faceted park island was enlarged slightly to a nominal 6,260 m radius so its ground extends beyond the roughly 6,185 m collision ring even at sampled joints. In PIE, a player was stopped at the east and south sides, at one east-side segment joint and at a diagonal joint; the joint and diagonal tests were repeated with map reloads. A 135 m southward approach also stopped at the boundary. This remains a sample, not proof of every direction, streaming transition, jumping or vehicle behavior. The water is a visual surface beyond the land; the hidden wall prevents ordinary walking through the edge. Exposure bias was raised from -0.4 to +0.15 to make the overcast setting easier to read.

### Outer park tree band
An additional 288 procedurally placed ash trees extend the peripheral grove from roughly 6,100 to 6,140 m radius, in 48 groups. These are invented placements, not mapped or historically verified trees. All 288 candidate centers were checked against the island floor in the editor; a six-tree pilot was visually inspected. The island uses the existing Poly Haven CC0 leafy grass textures with world-space mapping; repetitive distant tiling and the shoreline are still schematic. The source mesh is shared with the earlier grove. Runtime performance has not been benchmarked.

### Mapped cycle-stand proxies
One generic unbranded inverted-U stand represents each of 100 selected 2014 OpenStreetMap bicycle-parking nodes, in 36 groups. © OpenStreetMap contributors, ODbL. Fifteen uncertain candidate locations were omitted; the number of real stands, their exact orientation and their presence during the requested period are unverified. The first 11 centers were traced in PIE, and the remaining 89 were traced after loading their city tiles and nearby bounded actors. The groups are non-colliding and spatially loaded. One initially missing stand appeared in a retest after a level reload; the cause of the initial absence is not established. This set has not been benchmarked. These are visual street fixtures, with no bicycles or interaction.

### Garage-height pilot
Twenty-one 2014-matched `building=garages` footprints across Tile_m03_m03, Tile_p02_p04 and Tile_m03_m04 were lowered from the generator's 15 m default to an estimated 3.2 m. Their geometry and type match the 2014 extract; neither the exact height nor their 1980s–2000s state is verified. A separate original generic brick-and-shutter material is assigned to those garage walls; the repeated door positions, including side or rear walls, are illustrative rather than verified. Other buildings are unchanged. The source reserves separate indices for GL_CentralFacade and GL_GarageFacade, and the generator now blocks unguarded raw overwrites of the canonical central tile. The selective central facade still requires its guarded post-process when rebuilding. Geographic data © OpenStreetMap contributors, ODbL.

### Westminster Cathedral
An original schematic, non-colliding visual overlay adds brick and stone courses to the mapped campanile and four domes with inferred supporting drums. The model is not surveyed: the lower building, openings, decoration and roof shapes remain simplified. The drums connect to the mapped main roof in source-geometry checks; the tower and joins received a sampled game-view review. Geographic data © OpenStreetMap contributors, ODbL. Architectural reference: [Historic England listing 1066500](https://historicengland.org.uk/listing/the-list/list-entry/1066500), which describes Bentley's cathedral, its red brick and Portland stone bands, campanile and domes.

### Covent Garden Market
An original schematic replacement uses the mapped market footprints and source parts, with enclosed retail ranges, illustrated arched shopfronts and approximate roof/clerestory shapes. The glazing is opaque; there are no modeled shop interiors, names, basement or new stairs. Three estimated openings follow mapped passage routes. The long mapped passage was walked in both directions and three local route segments in one direction after a level reload; this does not establish full access or authentic stair geometry. Source geography © OpenStreetMap contributors, ODbL. References: [Historic England listing 1066949](https://historicengland.org.uk/listing/the-list/list-entry/1066949) and [Covent Garden market history](https://www.coventgarden.london/experience/visit/the-market-building-and-piazza). The successor development guard in `work/agent_audit/leadenhall_roof_correction/` pins the accepted Covent Garden, Old Bailey, 22 Bishopsgate, Old Vic, Horse Guards, 20 Fenchurch, Trafalgar statue and Leadenhall transactions and preserves the central facade and protected landmark triangles. Its current-source check passed; eight targeted negative checks correctly failed. Future edits still need independent geometry, UV, actor and collision review.

### Hatchards, Piccadilly
A schematic non-interactive sign and painted bookshop frontage mark Hatchards at its mapped 187 Piccadilly location. The green-and-gold artwork and display arrangement are interpretive, not a verified 1980–2009 facade; there is no shop interior or functioning door. The sign and frontage were viewed after reload. One unrelated generic food frontage incorrectly associated with the same map node was removed from the neighboring building. Geographic data © OpenStreetMap contributors, ODbL. Period reference: [Londonist, 2009](https://londonist.com/2009/09/biblio-text_hatchards).

### Old Bailey
An original schematic copper-colored dome and stylized gilt Justice figure replace two generic rooftop extrusions on the mapped Central Criminal Court. The overlay is non-colliding; the figure, lantern and facade are simplified, not a faithful sculptural or architectural survey. The roof joins and silhouette were reviewed in game after reload. The source footprint is © OpenStreetMap contributors, ODbL; the two detailed rooftop part IDs are present-day mapping and not verified in the 2014 extract. Architectural reference: [Historic England listing 1359218](https://historicengland.org.uk/listing/the-list/list-entry/1359218).

### Twinings, Strand
An original schematic painted frontage marks Twinings at the mapped 216 Strand host. The sign and opaque double door are visual and non-interactive; the underlying mapped footprint is explicitly estimated, and the proportions and ornament are not surveyed. A sampled approach stopped at the existing building wall after reload. Geographic data © OpenStreetMap contributors, ODbL. References: [Historic England listing 1236754](https://historicengland.org.uk/listing/the-list/list-entry/1236754) and [a 2006 photograph](https://commons.wikimedia.org/wiki/File:Twinings_London_April_2006_088.jpg).

### 22 Bishopsgate period correction
The six mapped parts of 22 Bishopsgate, completed in 2020, were removed from the 1980s–2000s prototype; the suppressed parent footprint is also excluded from regeneration. The earlier Crosby Court, 22–24 Bishopsgate and 4 Crosby Square buildings have not been reconstructed because the available 2014 extract did not establish their footprints. The cleared site remains a known gap. The skyline was sampled after reload, and a downward trace at the site hit City ground. Sources: [Multiplex project history](https://www.multiplex.global/projects/22-bishopsgate/), [City of London planning report](https://democracy.cityoflondon.gov.uk/documents/s72097/22%20Bishopsgate%20EC2N.pdf), and © OpenStreetMap contributors, ODbL.

### St Clement Danes
A non-colliding schematic stone facade, roof and tiered steeple overlay the mapped church on the Strand. Both long sides received sampled game-view checks; the existing mapped tower and church supply collision. The spire height, windows, roof and details are approximations, and the real doorway and interior are not modeled. Geographic data © OpenStreetMap contributors, ODbL; architectural reference: [Historic England listing 1237099](https://historicengland.org.uk/listing/the-list/list-entry/1237099).

### Old Vic asset evaluation
[The Old Vic Theatre, The Cut, London, SE1](https://www.fab.com/listings/6dd4ba36-fd97-4b71-8ad3-2ed81e78d8ef), by Vlad Dumitru, CC BY, was imported from Fab for evaluation. The imported mesh depicts an auditorium interior rather than the required street exterior, so it is not placed. The generic theater footprint remains, with the covered sidewalk and frontage treated separately as described below. A 1984 restoration reference is documented in the development workspace at `work/agent_audit/old_vic/SITE_AUDIT.md`.

### Natural History Museum
An original non-colliding schematic treatment adds a terracotta-colored Cromwell Road frontage, twin towers and a simplified paired-door/loggia entrance to the mapped solid museum shell. Tower placement, roof shape, windows and ornament are approximate; doors are not interactive and no interior is modeled. The entrance and tower joins were reviewed in PIE after reload. A mapped rear service-tunnel overlap is unchanged because historical public access and grade could not be established. Current OSM building ID 48872892 is not present by the same ID in the 2014 extract; geography © OpenStreetMap contributors, ODbL. References: [Historic England listing 1080675](https://historicengland.org.uk/listing/the-list/list-entry/1080675) and [the museum's building history](https://www.nhm.ac.uk/discover/alfred-waterhouse-museum-building-cathedral-to-nature.html).

### Royal Courts of Justice
A schematic non-colliding entrance overlay adds dimensional Gothic arches, columns and rose tracery to two mapped wall planes. It is a visual approximation with opaque surfaces, not a surveyed reconstruction or functioning entrance; the rest of the building remains generic. The Strand view and closer approach were sampled in PIE after reload. Two existing mapped private passages were not changed or tested. Source geography © OpenStreetMap contributors, ODbL. References: [Historic England listing 1264258](https://historicengland.org.uk/listing/the-list/list-entry/1264258) and [a 2005 reference photograph](https://commons.wikimedia.org/wiki/File:THE_ROYAL_COURT_OF_JUSTICE.JPG).

### Old Vic frontage and covered footway
An original non-colliding schematic frontage, pediment, sign, canopy and four closed ground-floor door bays suggest the theater's 1983 restoration; proportions, crest, doors and details are approximations. The doors are visual only, with no theater interior. The historic canopy's ground-level columns are omitted to keep the mapped covered footway clear. A narrow estimated 2.1 m opening was cut through two mapped source wall parts; the route was walked in both directions after reload and again after adding the entrance. This is not a survey of actual clearance or proof of all nearby routes. Source geography © OpenStreetMap contributors, ODbL. Reference: [Arup's 1984 restoration account](https://www.arup.com/globalassets/downloads/arup-journal/the-arup-journal-1984-issue-1.pdf). The separate Fab auditorium model remains unplaced.

### Victoria and Albert Museum
An original non-colliding schematic Cromwell Road treatment adds pale stone wings, an arched central portal, closed decorative doors and a simplified tiered crown to the generic museum mass. Its dimensions and ornament are approximate; there is no museum interior or functional entrance. The frontage was inspected from the road and an oblique street view after reload; an approach reaches the existing solid shell. The visual treatment overlaps the last roughly 0.55 m of the mapped entrance centerline, which ends at that wall; steps and nearby mapped centerlines were not intersected by the low overlay in source checks. These are sampled checks, not a full accessibility audit. OSM geography © OpenStreetMap contributors, ODbL. References: [V&A architectural history](https://www.vam.ac.uk/articles/a-grand-entrance-on-cromwell-road) and [Historic England listing](https://historicengland.org.uk/listing/the-list/list-entry/1190187).

### Horse Guards central passage
A narrow arch and simplified barrel lining were cut through three overlapping source parts along mapped pedestrian-permissive route 195406730. Its 3.556 m width follows [Sir John Soane’s Museum’s 1822 survey](https://collections.soane.org/THES99611); the mapped alignment, height and curved vault are estimates. After reload the player walked from Whitehall to the Parade and back on the sampled centerline. The private side routes were not opened; source-level checks preserve their prior sampled wall crossings. A separate non-colliding schematic Whitehall frontage adds a clock, dome and lantern over the generic source mass; its side wings, rear, sculpture and fine details remain generic. The center passage was walked in both directions again after this overlay was added. This is a gameplay approximation, not a survey or a claim about present-day access or vehicle clearance. Source geography © OpenStreetMap contributors, ODbL; see also [Historic England listing](https://historicengland.org.uk/listing/the-list/list-entry/1066100).

### 20 Fenchurch Street period correction
The post-period tower's 211 mapped parts were removed, with their current parent excluded from future generation. The skyline was inspected after reload and a sample at the site traced to ground. The earlier building, demolished in 2008, is not reconstructed: its reliable pre-demolition footprint has not been established. This intentionally leaves a gap, not a historically complete site. The current tower opened in 2014 ([Landsec](https://www.landsec.com/en/about/about-landsec/80)); the earlier demolition is documented in the [City of London planning report](https://democracy.cityoflondon.gov.uk/Data/Planning%20and%20Transportation%20Committee/20110511/Agenda/%2408%20-%20Redevelopment%20of%2020%20Fenchurch%20Street%20-%20Potential%20Acquisition%20of%20Land%20for%20Planning%20Purposes.doc.pdf). Source geography © OpenStreetMap contributors, ODbL.

### Trafalgar Square southern statues
Generic white source blocks above the two southern stone plinths were replaced by original low-poly, bronze-colored approximations of Havelock and Napier. These are schematic silhouettes, not portraits or scans; their exact details and facing remain to be improved. The plinth source geometry and collision remain, the new figures have no collision, and the result was viewed from the start and near Havelock after reload. Source geography © OpenStreetMap contributors, ODbL. Reference: [Historic England's Trafalgar Square listing](https://historicengland.org.uk/listing/the-list/list-entry/1001362).

### Southwark Cathedral
Two original non-colliding schematic treatments add a stone crossing tower, four tapered pinnacles, pitched roofs and selected flint and stone walls with pointed windows to the mapped shell. They were inspected from an elevated view and the west approach after reload; some lower walls remain generic. The west footway ends at an existing solid wall and the added porch doors are decorative. No interior or operable entrance is modeled. Placement, stonework, roof geometry and ornament are approximations, not a survey. Source geography © OpenStreetMap contributors, ODbL. References: [Historic England listing](https://historicengland.org.uk/listing/the-list/list-entry/1378460) and [the cathedral's history](https://www.cathedral.southwark.anglican.org/about-us/our-history/).

### Strand full-width pavement pilot
Three adjoining sections of stone paving extend approximately 61 m along a current mapped sidewalk and fill a gap between the generated footway and frontage. Its source line is absent by the same ID in the 2014 extract, so the layout is an approximation for the requested period. All three meshes use complex-as-simple BlockAll collision. After reload, the player walked across both seams in each direction, stepped between sampled lower ground and the paving, and crossed between the road and frontage. Floor traces hit the new surfaces at 28.8 cm; a far-and-return streaming sample unloaded and reloaded all three actors. These are local tests, not proof of all doors, crossings, projectiles or route access. This remains a short pilot with abrupt ends, not continuous Strand paving. Source geography © OpenStreetMap contributors, ODbL.

### Selfridges Oxford Street
Original non-colliding schematic frontage and entrance overlays add stone bays, columns, glazing, a stylized clock, canopy and four pairs of decorative closed doors to the existing mapped shell. The doors do not open, the shop has no modeled interior, and the Queen of Time sculpture and fine ornament are omitted. Front and oblique views and an approach to the existing solid wall were checked after reload; individual period details remain approximate. Source geography © OpenStreetMap contributors, ODbL. References: [Historic England listing](https://historicengland.org.uk/listing/the-list/list-entry/1357436) and [UCL Survey of London](https://blogs.ucl.ac.uk/survey-of-london/2020/12/23/selfridges-398-454-oxford-street/).

### Lloyd's Building
An original non-colliding schematic treatment adds steel-like bands, glazing and attached service pods above 6 m to nine mapped building parts. It is an approximation of the 1986 building, not a replica of its lifts, machinery or interior; mapped source heights reach 88 m while the architect lists 84 m. The base remains generic. The overlay was inspected from elevated views after reload; no claim is made that all nearby mapped routes are traversable. Source geography © OpenStreetMap contributors, ODbL. References: [Historic England listing](https://historicengland.org.uk/listing/the-list/list-entry/1405493) and [the architect's description](https://rshp.com/projects/office/lloyds-of-london/).

### Leadenhall Market roof correction
Four mapped roof parts that were extruded to ground level were raised to an estimated 7 m underside while retaining their 10 m tops and the explicitly elevated crossing and gateways. The 7 m clearance follows the mapped central crossing and is not a surveyed eave height. After reload, the west, north and south approaches were walked to the crossing and back; the east approach was walked through its bends in both directions. These are sampled routes, not proof of every entrance or access condition. A separate non-colliding schematic arcade adds ribs, opaque faux glazing and generic closed shopfronts beneath the source roof. West and north approaches were walked again after that overlay was added. The source roof remains opaque, some walls are generic, and the passage currently looks dark; local lighting is under review. Source geography © OpenStreetMap contributors, ODbL. Reference: [Historic England's market listing](https://historicengland.org.uk/listing/the-list/list-entry/1286182).

### Standalone bus-stop pilot
Four generic, non-colliding bus-stop poles were added at positions derived from mapped 2014 nodes. Two are at their mapped positions and two were shifted about 1.4 m for local clearance; 2014 mapping does not establish their exact appearance or existence in 2009. All four were viewed after a level reload, with bases on the traced ground. Their separate World Partition bounds are valid; a far-and-return sample unloaded and reloaded the nearby pair. The signs have no routes or services, and surrounding paving and accessibility remain approximate. Source geography © OpenStreetMap contributors, ODbL.

### Leadenhall lighting trial
An initial point-light pilot was removed after it produced glare and uneven pools of light. Two broad, low-intensity downward spot fills now provide a modest test along the west passage; the view was checked in both directions and after reload, and the player walked a sampled section. A far-and-return test unloaded and reloaded both lights with their saved intensities. The bright exit and uneven illumination remain, other passages are not covered by this pilot, and shadowless light can bleed through walls. The source roof remains opaque.


### Strand next paving section
A fourth, approximately 10 m section extends the tested paving to roughly 71 m total. Live traces at three sections found the existing road at z=28 cm, lower ground at z=10 cm, and the current modeled facade just beyond the proposed frontage edge. After reload, the player walked across its join and back, stepped on and off at the ends, and crossed between road and frontage at one location. A far-and-return sample unloaded and reloaded the BlockAll actor. The curb follows estimated road masks rather than a survey, the current and 2014 mapped footprints differ, and the mapped sidewalk centerline falls just outside the modeled curb edge. Entrances, projectiles, and all nearby routes have not been comprehensively tested. The remainder ends abruptly. Geography © OpenStreetMap contributors, ODbL.


### National Gallery west wing
A new original, schematic west-wing treatment adds dimensional sash frames, blind upper panels, stone bands, a secondary four-column portico and a small terminal cupola. Two mapped low blocks that obscured the portico were removed from the central source tile; the building host and overhead mass remain. The treatment uses approximate proportions and material matching. The central dome, fine sculpture and many details remain simplified, and the secondary doorway is decorative with no interior.

The separate podium has BlockAll complex-as-simple collision. After reload, traces hit its four sampled tread and landing heights, and the player walked up to the closed wall and back down. The previously sampled route across the frontage and the Horse Guards central passage were each walked in both directions after the central tile was reimported. A far-and-return sample unloaded and reloaded the wing and podium. These checks do not cover all approaches, objects, collision channels or routes. The source correction preserved named material slots and the existing BlockAll collision profile; Unreal Python exposed eight standard response channels for direct verification. Source geography © OpenStreetMap contributors, ODbL. Architectural references: [Historic England's listing](https://historicengland.org.uk/listing/the-list/list-entry/1066236) and [a 2006 exterior photograph by Peter Broster](https://commons.wikimedia.org/wiki/File:National_Gallery_(8062180641).jpg), CC BY 2.0.

### National Gallery east wing
A matching original, schematic east-wing treatment adds stone bays, sash frames, blind panels, a secondary four-column portico and a shallow terminal cupola. It reuses the west-wing materials. Two low source blocks were removed while retaining the host and overhead source part. The east doorway is decorative and closed; its level approach is a broad interpretation informed by the 2004 Getty entrance, not a surveyed reconstruction. The columns are NoCollision and their shallow bases expose about 2 cm above the sampled z=10 cm ground. A small stone terrace now covers the ground under the portico while preserving adjacent mapped lawns; dark ground remains beyond it.

After reload, the player walked the mapped east approach and a frontage line in both directions, and the Horse Guards central passage was rechecked both ways after reimport. A far-and-return sample unloaded and reloaded both wings and the west podium with their recorded collision profiles. The checks are local, not exhaustive. Named central-tile material slots, BlockAll profile and eight Python-visible collision responses were verified; other effective channel responses rely on the unchanged profile. Source geography © OpenStreetMap contributors, ODbL. References: [Historic England's listing](https://historicengland.org.uk/listing/the-list/list-entry/1066236) and [the Gallery's 2006–07 review](https://nationalgallery.org.uk/upload/pdf/NG_Review_06-07.pdf).

### National Gallery east portico paving
An approximately 39 m² NoCollision stone surface covers the dark ground immediately beneath the east columns, bounded by the mapped portico footprint. It preserves mapped current and 2014 lawns and higher path surfaces. The plane sits at z=11 cm over 28 sampled z=10 cm ground points, with about 1 cm of visual height above ground; its mapped edge is approximate and a dark strip remains beyond the patch. After reload, the east approach was walked in both directions across the existing height transition, and a far-and-return sample unloaded and reloaded the patch. These are local checks rather than proof of full ground coverage, access or every adjacent route. OSM geography © OpenStreetMap contributors, ODbL.

### Fortnum & Mason, Piccadilly
An original schematic frontage adds a pale green arched shopfront, a readable Fortnum & Mason sign and a static decorative clock over a closed entrance. The clock and frontage dimensions are estimates; the current unnamed mapped clock node was used as an approximate anchor. The two historical clock figures are omitted, the clock does not move or chime, and the store has no modeled interior. A single generic Fortnum shopfront was removed from the shared anonymous-commercial mesh; the other source fronts were retained.

After reload, front and oblique views showed the corrected sign and clock, a nearby signal remained visually separate, Hatchards and one other anonymous shop were inspected, and a sampled Piccadilly footway was walked in both directions. A far-and-return test unloaded and reloaded the new actor and its commercial tile. The modeled signal clearance is only about 2.6 cm, so further adjustment may be needed. The new frontage has NoCollision; the shared commercial actor retained its existing BlockAll profile, default complexity and empty simple-collision arrays. These checks are local, not a complete collision or historical survey. Geography © OpenStreetMap contributors, ODbL. Period references: [2006 exterior by Colin Smith](https://commons.wikimedia.org/wiki/File:Late_night_Christmas_Shopping_at_Fortnum_and_Mason_-_geograph.org.uk_-_287502.jpg) and [2008 clock photograph by tristan forward](https://commons.wikimedia.org/wiki/File:Fortnum_and_Mason%27s_Clock_-_geograph.org.uk_-_1579471.jpg), both CC BY-SA 2.0, used as references rather than textures.

### Liberty, Great Marlborough Street
An original schematic Tudor-style treatment adds pale infill, dark timber framing, dimensional oriel bays, a decorative closed entrance, a Liberty sign and five pitched roof volumes to the mapped 15 m host. Its number of bays and gables, roof heights and proportions are estimates inspired by period photographs, not a survey. The remaining sides and rear roof are generic; the historical bridge and Regent Street building have not been reconstructed by this treatment. No interior is modeled.

One overlapping generic Liberty storefront was removed from the shared commercial tile; other source fronts were retained. After reimport reset the actor profile, BlockAll and the empty overrides were restored; the saved state after reload matched the preflight, and the seven material defaults matched the original integrator. Front, oblique and elevated views were inspected. The sampled Great Marlborough sidewalk and a section of Kingly Street were walked in both directions; a far-and-return test unloaded and reloaded the visual actor and shop tile. These local checks do not establish all routes or physical collision channels. The added façade has NoCollision. Geography © OpenStreetMap contributors, ODbL. References: [Historic England listing](https://historicengland.org.uk/listing/the-list/list-entry/1357064) and [Bill Henderson's 2007 exterior](https://www.geograph.org.uk/photo/604105).

### Great Portland Street shop variety pilot
Six existing anonymous storefront panels around Great Portland Street and Little Portland Street now use varied muted paint and original display illustrations. Their signs remain blank, the doors are decorative, and the artwork is not a reconstruction of named 1980s–2000s businesses. Only twelve panel material assignments were changed in the shared source mesh; all vertices, UVs, frames and other faces were retained. Four texture edges were corrected after live inspection exposed fragments of the old display.

All six fronts were inspected after the mesh reimport, and each corrected clothing texture was inspected after reload. A sampled Great Portland Street footway was walked in both directions, and a far-and-return test unloaded and reloaded the shared tile. Its original named material bindings, BlockAll profile, empty overrides and exposed collision settings matched the saved preflight. These are local tests, not proof of all shop interactions or routes. The shared shop generator does not yet reproduce this pilot automatically, so a future regeneration needs a reviewed reapplication. Geography © OpenStreetMap contributors, ODbL.

The shared commercial builder now blocks an unreviewed raw rebuild while the material pilot is present, preventing the twelve accepted material assignments from being silently lost. The guarded builder, exact original backup and its rollback conditions are documented in `work/agent_audit/systemic_facade_pilot/DEPENDENCIES.md`; a separate source-ID reapplication workflow is being reviewed. Four fixed texture files live in `work/agent_audit/systemic_facade_texture_fix/` and must be retained independently of the original pilot images. The older Liberty correction's tile/FBX guards intentionally reject the current later pilot state. If changes must be unwound, first roll back and reimport the thirty-shop batch, then the seven-shop batch, then the original six-shop material pilot, verify its prior state, and finally use the guarded Liberty rollback and reimport. Later changes require reconciliation rather than stale-backup restoration.


The approximate 100 Bishopsgate predecessor blocks use estimated subdivisions of the modern site outline and reused original office materials. Eight and nine above-ground storeys come from the [City of London 2011 planning report](https://democracy.cityoflondon.gov.uk/Data/Planning%20and%20Transportation%20Committee/20110906/Agenda/%2406%202%20-%20100%20Bishopsgate.doc.pdf); the footprints, façades and 3.2 m per floor are estimates. The accepted addition leaves the current eastern mass and mapped paths in place; sampled local play tests are described in the open-and-status guide. OSM geography © OpenStreetMap contributors, ODbL.

The later seven-shop batch is recorded in `work/agent_audit/systemic_facade_batch7/`; the thirteen-ID scratch reapplication is separately reviewed in `work/agent_audit/systemic_facade_reapply/`. The guarded generator remains fail-closed on the accepted state. Reapplication is source-only and needs separate reviewed FBX and Unreal integration.


### Heron site and 100 Bishopsgate shopfronts
The 2011 Heron Tower source parts were removed by the guarded transaction in `work/agent_audit/heron_tower_correction/`. The active Heron successor retains the earlier Leadenhall checks against their pinned baseline; the original Leadenhall placement and lighting helpers still pin the old tile and require separately reviewed successors before reuse. The Lloyd’s source-placement pin and the four Hatchards/Twinings/RCJ manifest guards were independently rebaselined after the exact Heron diff was checked; previous guard files and a hash-guarded rollback are in `work/agent_audit/heron_tower_correction/asset_guard_backup/`. Separate schematic Kempson House and Bishops House masses estimate the earlier site, using the names and construction dates from [Museum of London Archaeology](https://archaeologydataservice.ac.uk/catalogue/adsdata/arch-4072-1/dissemination/pdf/LAMAS_Vol67_99-132_HeronTower.pdf). Their parcel split, façades and dimensions are approximate, with Kempson’s 14 floors from a secondary record and Bishops’ eight floors assumed. Demolition was underway in 2007. Four anonymous decorative 100 Bishopsgate frontages include one original generated texture, saved in `work/agent_audit/bishopsgate100_fronts/clothing_photo.png`; this is not a documented period business or a functional interior. OSM geography © OpenStreetMap contributors, ODbL.

After reload, all four frontage panels, including the photo panel, were visually inspected. Twelve sampled ground traces below the panels hit City ground at z=10 cm, beneath panel bottoms at z=12 cm; the sampled Bishopsgate footway was walked in both directions. A far-and-return test unloaded and reloaded all five new building/frontage actors with their recorded collision profiles retained. These are local observations, not proof of every surface, route or actor interaction.


Senate House has an original schematic pale upper and lower tower facing and stepped crown, using the 57.6 m live roof and approximate 64 m final height. Window rhythm and setbacks are estimated; the remaining wings are generic. The V2 facing is NoCollision, and gaps near mapped paths do not open existing source walls. References: [University of London](https://www.london.ac.uk/about/history/history-senate-house) and [Historic England](https://historicengland.org.uk/listing/what-is-designation/heritage-highlights/which-building-was-rumoured-to-have-survived-the-blitz-because-hitler-coveted-it-for-the-nazis-hq). OSM geography © OpenStreetMap contributors, ODbL.

The thirty-shop expansion and its immediate-predecessor rollback are in `work/agent_audit/systemic_facade_batch30/`. The 43-ID reapplication candidate is documented in `work/agent_audit/systemic_facade_reapply43/`; it requires separate reviewed export and Unreal integration. All five new photo panels and three other varied panels were viewed after reload, a nearby footway was walked both ways, and the shared tile streamed out and back with BlockAll and fourteen material slots.


An additional 89 anonymous storefronts across `Tile_p02_p04`, `Tile_p00_p01`, and `Tile_m02_p01` use shared display materials. Each source transaction has an independent immediate-predecessor backup under `work/agent_audit/systemic_facade_multitile90/`; these edits require reviewed reapplication before regeneration. A sampled photo display at node 823477114 was obscured by existing geometry, while six other photo displays and generic examples in each tile were visible after reload. Each tile streamed out and back with BlockAll and fourteen material slots. The shop displays remain approximate and non-interactive. OSM geography © OpenStreetMap contributors, ODbL.


The British Library clock tower, roof steps and closed entrance are original schematic approximations of the post-1998 building, informed by [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1426345) and a [2006 photograph by R Sones](https://commons.wikimedia.org/wiki/File:Clock_Tower_at_British_Library,_Euston_Road_NW1_-_geograph.org.uk_-_1305388.jpg), CC BY-SA 2.0, used as reference only. The tower and doorway positions, dimensions, materials and roof masses are estimated. The visual overlay is NoCollision and does not create an interior or guarantee passage through the source wall. OSM geography © OpenStreetMap contributors, ODbL.

The commercial builder now has a four-tile fail-closed regeneration guard. It retains the earlier Tile_m01_p01 protection and independently checks the three later tiles; raw bulk generation is blocked until the guarded JSON and FBX predecessors for all four are restored. The installed guard and immediate predecessor backup, isolated negative tests, and source-ID scratch reapplication for the three later tiles are documented in `work/agent_audit/systemic_facade_multitile90_successor/`. The 43-front Tile_m01_p01 has its own post-guard source-ID scratch reapplication. These source checks do not establish FBX or runtime equivalence. Preserve the corrected shared textures, the separate Bishopsgate photo material, and all predecessor backups; do not force an older rollback over later accepted work.


The 51-front two-tile pass is recorded in `work/agent_audit/systemic_facade_next/`. It includes two panels using `bookshop_photo.png`, an original generated image with its prompt in `bookshop_photo_prompt.txt`. The texture is used as an approximate unbranded display, with baked reflections and no functioning interior. Both book panels, a clothing sample and generic samples were viewed after reload, and both shared tiles streamed out and back with their BlockAll profiles and fourteen/fifteen material slots. OSM geography © OpenStreetMap contributors, ODbL.

A further 51 anonymous storefronts were varied across Tile_p01_p01 and Tile_p02_p03. Two center-door bookshop windows use a new original generated photo-style texture; the exact prompt and source PNG are retained in `work/agent_audit/systemic_facade_next/`. The fronts and names are schematic, not verified historic businesses. After reload, both book-photo fronts and representative clothing and generic panels were inspected; both tiles streamed out and back with BlockAll and 14/15 material slots. Each tile has its own guarded immediate-predecessor source and FBX backup. These local checks do not establish all routes or actors. OSM geography © OpenStreetMap contributors, ODbL.


Four Trafalgar Square substitute lions use the [Lion sculpture scan by danielpett](https://sketchfab.com/3d-models/lion-sculpture-3d1956be9e724235817f03a1d570f408), [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/), downloaded via [Zenodo](https://zenodo.org/records/10319589). The Cairo sculpture is a different lion; the model was cropped, decimated and recolored bronze. Positions, orientations and other proportions are estimates; it is not a scan of a Landseer lion. All four modeled plinth contacts were traced at z=200 cm, group appearance checked after reload, and all four actors streamed out and back with NoCollision. OSM geography © OpenStreetMap contributors, ODbL.

The storefront regeneration guard has since been extended from four to six affected tile pairs. The installed guard retains all earlier checks and independently protects both accepted Tile_p01_p01 and Tile_p02_p03 source JSON and FBX predecessors. Its reviewed immediate backup, isolated mixed-state tests and post-guard source-ID reapplications for all affected tile groups are in `work/agent_audit/systemic_facade_next_successor/`. The accepted generated bookshop-photo PNG and its exact generation prompt are retained in `work/agent_audit/systemic_facade_next/`. All predecessor transaction records and backups remain intact; source checks do not establish live actor or FBX equivalence.

A separate reviewed v2 scratch-reapplication receipt now pins the earlier three-tile and 43-front wrapper engines, including the transitive 43-front wrapper, without changing the installed six-pair raw-builder guard or earlier receipts. Use `work/agent_audit/storefront_reapply_hardening/reapply_checked_v2.py` with `prior3` or `prior43` for those scratch checks; an isolated mutation test confirms the transitive engine pin. These checks do not establish FBX or live-editor equivalence.


Buckingham Palace forecourt has original approximate partial railings and piers based on OSM fence way 153405712 and gate points, with open gaps and NoCollision. Pier and gate samples hit z=28 cm, and the placed actor was raised to that height; the central mapped gate was walked both directions after reload. Ornate leaves and the full perimeter remain unmodeled. Reference: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1239251/). OSM geography © OpenStreetMap contributors, ODbL.

The subdued broad animated water normal was applied through per-component overrides on mapped water tiles. The rollout journal under `work/agent_audit/water_broad_rollout/` records 72 tile changes, with central `central_override.json` and the earlier Tower trial handled separately. The normal texture is the existing project asset; geometry and collision were not intentionally changed. Tile UV phase can still create visible seams; the outer water remains a separate boundary surface.

Water restoration has three distinct scopes: the 72 journalled actors can be restored with the batch rollback in `rollout_unreal.py`; the central tile's separately recorded `M_Water` override has its own guarded `rollback_central_unreal.py`; and the earlier Tower `Tile_p04_p00` trial predates the rollout plan and requires separate verified pre-trial evidence before restoration. Neither batch nor central rollback changes the Tower trial. The shared `M_WaterBroadTrial` material's normal-flattening alpha was separately changed from 0.65 to 0.8, so actor-override rollback does not revert that material setting; changing it again would affect any remaining actor using the material. See `work/agent_audit/water_broad_rollout/README.md` for guards and rollback order. The rollback helpers have been syntax-checked but have not been exercised live.

## Tower of London stone material pilot

The existing Codriver Tower of London actor retains its mesh and BlockAll collision. Two component-only overrides on masonry slots 4 and 5 add subtle world-aligned stone courses; the other six effective material slots remain the original model materials. The 1K diffuse source is Castle Wall Variation by Rob Tuytel, Poly Haven, CC0: https://polyhaven.com/a/castle_wall_varriation. It was desaturated, contrast-softened and blended with the model's existing stone tones; the 2 m texture repeat and masonry pattern are visual approximations, not a survey of the fabric. Historic England describes ragstone and Portland dressings at the White Tower: https://historicengland.org.uk/listing/the-list/list-entry/1002061.

Both pilot material graphs compiled without errors. After reload the owner confirmed both slot overrides, identified slot 4 on the White Tower with a collision-face lookup, and reviewed the subtle stone courses at close range. This is a localized appearance check, not validation of every surface, route or performance condition. Original shared Codriver materials and mesh were not modified. To revert, load the same actor and use `rollback_pilot()` from `work/agent_audit/tower_london_material/pilot_unreal.py`; it checks the captured mesh and effective material state, clears the originally empty component overrides and restores the eight original defaults. The runtime baseline is retained in `work/agent_audit/tower_london_material/runtime_snapshot.json`; see `work/agent_audit/tower_london_material/PILOT.md` for guards and reload checks.


The original black-and-white Strand, Whitehall and Great Portland Street plaques use mapped road names and estimated positions. The Noto Serif font is from the [official Google Fonts repository](https://github.com/google/fonts/tree/main/ofl/notoserif), licensed SIL OFL 1.1; its full license and source hash are retained in `work/agent_audit/street_name_pilot/`. These are original generic designs, not Westminster's branded nameplate artwork. The signs are NoCollision, and each was visually readable after reload. OSM geography © OpenStreetMap contributors, ODbL.


Thirty-five additional street-name plaques use mapped names and estimated wall positions; font and OFL license are in `work/agent_audit/street_name_expansion/`. Six representative signs were viewed and readable after reload. The initial import did not persist NoCollision; all 35 expansion and three pilot actors were explicitly saved with the NoCollision profile, then all 38 were checked after another reload. OSM geography © OpenStreetMap contributors, ODbL.

The selected drinking-fountain scan was cropped and reduced with a projected texture in `work/agent_audit/trafalgar_drinking_fountain/`. Two trial actors were removed after live review found their freestanding supports visually unsuitable and side-view artifacts distracting. The original and reduced assets remain available for a future terrace reconstruction.


Tate Modern’s 2016 extension source parts were removed by the guarded transaction in `work/agent_audit/tate_modern_correction/`, retaining the main hall, chimney and other source triangles. The old switch house is not reconstructed. The sampled northern promenade was walked both ways before and after reimport, and the tile retained BlockAll and the BroadTrial water override after reload. Two early-gallery façade trials were hidden after visual review. The accepted V3 adds a schematic north brick facade and glazed band, and a separate skin treats the upper chimney sides. These use NoCollision and the original source geometry remains underneath; the lower level and other faces remain generic. Sources: [Southwark 2009 report](https://moderngov.southwark.gov.uk/Data/Planning%20Committee/20090331/Agenda/Item%206.2%20Report%20Tate%20Modern%20Bankside%2C%20Sumner%20Street%2C%20London%20SE1%209TG.pdf) and [Stanhope](https://www.stanhopeplc.com/projects/tate-modern). OSM geography © OpenStreetMap contributors, ODbL.


### Grocery storefront expansion and Tate facade
Fifteen food panels on `Tile_p03_m01`, `Tile_p04_m01`, and `Tile_p03_p02` use a generated unbranded grocery image, without changing their geometry or collision. Source, exact generation prompt, predecessor FBX/JSON backups and material-only reimport records are in `work/agent_audit/grocery_storefront_plan/`. Representative panels in each tile were viewed in PIE; the first was checked after reload. `work/agent_audit/grocery_storefront_successor/` installs a nine-pair guard and reproduces the grocery source patches in scratch. Earlier six-pair scratch wrappers now need reviewed successor pins before reuse; do not bypass their checks.

The visible Tate north facade and separate upper chimney-side skins are approximate NoCollision actors, with early rejected V1/V2 actors retained but hidden in game. Their backing brick texture is [Poly Haven Brown Brick 02](https://polyhaven.com/a/brown_brick_02), CC0. Traces confirmed the two upper north wall planes and west chimney source walls; the actors and collision profiles persisted after reload. The building remains schematic and lower chimney sides retain generic source windows. Work packages are `work/agent_audit/tate_modern_pilot_v3/` and `work/agent_audit/tate_chimney_sides/`.

A single additional NoCollision bus-stop flag near Tottenham Court Road was placed from the 2014 mapped proxy in `work/agent_audit/standalone_bus_stops_expansion/`; the other proposed nodes have not been placed. A short paving trial was removed; a longer road-material fill was later accepted for this local gap. OSM geography © OpenStreetMap contributors, ODbL.


City ground retains its cylinder, transform and BlockAll collision, but its component material override now uses `/Game/GrayLondon/Geodata/Materials/M_CityGapTrial`, a duplicate of `M_City` with emissive RGB (0.006, 0.006, 0.0056). The prior component override was `/Game/GrayLondon/Materials/M_City`. This reduces deep black gaps without repairing their underlying road/footway geometry. The rejected 12 m Tottenham paving actor was removed; its unreferenced trial asset remains. The material override and collision were checked after reload; to reverse, restore the original material on the City ground component and save its actor.


The Bank of England Threadneedle entrance is a separate schematic NoCollision actor from `work/agent_audit/bank_entrance_pilot/`, reusing Royal Exchange materials. At its midpoint, live source traces hit the front wall at z2 and z5 m, a wall about 2.4 m behind at z8 m, and missed at z11 m. The shallow upper backing is therefore an approximation above unsupported source wall. The entrance was viewed in play, persisted after reload, and a roughly 10 m adjacent route was walked both directions. Door is closed and decorative. Historic references: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1079134), [Bank museum guide](https://www.bankofengland.co.uk/-/media/boe/files/museum/print-guide.pdf).

Six additional named plates reuse existing meshes in `work/agent_audit/reused_street_plates/`; each was read in PIE and checked as spatially loaded and NoCollision after reload. The Regent Street plaque slightly overlaps the edge of an existing anonymous shop fascia. Names derive from mapped roads, while placement and design are approximations. OSM geography © OpenStreetMap contributors, ODbL.


The separate St Mary-le-Bow tower (`work/agent_audit/st_mary_bow_pilot/`) is a schematic 68.2 m skyline treatment on the generic church. Five live roof traces hit z15 m; it persisted with NoCollision after reload. Its support and silhouette were inspected locally; the base remains generic and the dragon is omitted. Sources: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1064696), [City of London](https://www.cityoflondon.gov.uk/assets/Services-Environment/bow-lane-conservation-area-character-summary-management-strategy.pdf).

Six illustrative NoCollision park benches in `work/agent_audit/park_bench_supplement/` reuse the existing bench asset. Each of five support probes per placement hit the loaded source park surface at z24 cm, each was viewed in play, and all six profiles persisted after reload. Exact historical placement is not claimed.

The approximately 33 m Tottenham gap fill (`work/agent_audit/tottenham_gap_continuous/`) uses `M_OSM_Road` and a separate BlockAll complex-collision mesh. A sampled player walked approximately 29 m along it and returned after reload. The nearby bus-stop base is partly embedded by the 18.8 cm raised fill. This is a local fix, not a repair to all road gaps. A textured global ground-material experiment produced streaks and was rejected; A subsequent planar world-coordinate asphalt trial was accepted and bound as `M_CityPlanarTrial`. Geography © OpenStreetMap contributors, ODbL.


The active City ground component override is now `/Game/GrayLondon/Geodata/Materials/M_CityPlanarTrial`, using the project's existing `asphalt_02_Diffuse` texture projected from world XY at a 4 m repeat, with a small texture-scaled emissive contribution (0.025). This was viewed at Waterloo Road, Tottenham Court Road and Trafalgar Square and retained BlockAll after reload. It replaces the flat `M_CityGapTrial` override documented above; that earlier trial and original `/Game/GrayLondon/Materials/M_City` remain available for rollback. The change improves exposed ground appearance, but does not fix road/footway height gaps. The separate world-aligned-function texture trial produced streaks and was rejected.


The St Bride’s tower (`work/agent_audit/st_brides_pilot/`) is an approximate 68.9 m, four-tier NoCollision addition on the generic church roof. Five live roof traces hit z15 m, the silhouette was viewed in PIE, and its NoCollision profile persisted after reload. Sources: [St Bride’s Church](https://www.stbrides.com/about-us/our-history/), [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1064657).

The Victoria Embankment open-air theatre (OSM feature 298346972) had been wrongly extruded into a 15 m building. `work/agent_audit/embankment_theatre_correction/` removes exactly 64 uniquely attributed wall/roof triangles, guards the remaining central features, and preserves predecessor source/FBX backups. The central tile was reimported with all six named material slots, BroadTrial water, BlockAll and complex collision unchanged. After reload a sampled route approximately 23 m across the cleared area was walked in both directions. A schematic low stage and nine generic bench seats were later added. Four active Hatchards/Twinings/RCJ source guard manifest pins were narrowly rebaselined, with predecessor backups; older historical snapshots remain intentionally stale. Geography © OpenStreetMap contributors, ODbL.


The Mansion House frontage (`work/agent_audit/mansion_house_pilot/`) adds a schematic six-column stone portico over the generic shell. Twelve live wall traces at three points and four heights hit the expected source wall; the actor was viewed in PIE, a roughly 11 m route beside it walked both directions, and NoCollision persisted after reload. Its upper backing and pediment exceed the source roof; doors/interior are not modeled. Sources: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1064604), [ASCHB](https://www.aschb.org.uk/wp-content/uploads/2021/12/Vol-8.pdf).

The Victoria Embankment Gardens maintenance office (OSM 410816638) was reduced from the generator's default 15 m to an estimated 3.5 m in `work/agent_audit/embankment_office_correction/`. Exactly 18 isolated top vertices changed, with predecessor source/FBX backups; the central tile retained all six materials, water override and BlockAll. The office's historical height is not verified. A separate NoCollision dark window/door overlay in `embankment_office_facade/` is illustrative and reuses `M_BL_dark`; it persisted after reload. The Horse Guards tile pin was rebaselined with a predecessor backup. Several placement snapshots are stale and must be independently rechecked before reuse.

The open-air theatre is represented by an illustrative 8 x 5 m NoCollision stage and nine existing bench instances (`embankment_theatre_approximation/` and `embankment_theatre_seating/`). Five stage and 27 bench support probes hit the loaded central park surface at z24 cm. Both were viewed in PIE and persisted after reload; the HISM has nine instances and NoCollision. The stage uses the unique matte `M_TheatreStageMatte` component override, replacing its streaked asphalt trial. Exact historical layout is not claimed; the seats have no sit interaction.

Seven supplementary NoCollision street bins from `retail_street_bins/` reuse [Minimaliano's London Street Props](https://www.fab.com/listings/3a15c74a-8a6f-4f51-b488-28cb6da0205c), CC BY 4.0. One Portman Square candidate was removed because an existing bin was nearby; deletion and seven remaining actors were verified after reload. Placement is approximate. OSM geography © OpenStreetMap contributors, ODbL.


Cleopatra’s Needle (`work/agent_audit/cleopatra_needle_pilot/`) is a schematic 20.8 m pink-granite obelisk on pale skins covering the existing three generic pedestal parts. Five live traces hit the source base at z6 m. The separate NoCollision actor was viewed from the promenade and persisted after reload. Hieroglyphs, sphinxes and detailed stone grain are omitted. Sources: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1066169), [London Museum](https://www.londonmuseum.org.uk/collections/london-stories/how-cleopatras-needle-came-london/).

The Tachbrook pedestrian marketplace (OSM 97730768) was wrongly extruded as a 15 m building. `tachbrook_market_correction/` removes exactly 76 uniquely attributed faces and stores predecessor generator, manifest, tile and FBX backups. The five material slots, BroadTrial water and BlockAll complex collision survived reimport. A schematic NoCollision stall and three produce crates (`tachbrook_stall_pilot/`, `tachbrook_stall_produce/`) were viewed in PIE; they have no interaction. The four active Hatchards/Twinings/RCJ manifest guards were rebaselined after the source transaction with backups. The Great Fire Monument source parts were subsequently corrected and replaced, as documented below.

Four supplementary NoCollision, non-emissive street lamps from `central_lamp_supplement/` were placed at mapped nodes and viewed in PIE; their exact 1980–2009 form is estimated. A Clerkenwell Road candidate failed the five-point ground test and was not placed. OSM geography © OpenStreetMap contributors, ODbL.


The Great Fire Monument correction (`monument_fire_correction/`) removes 477 uniquely attributed triangles across twelve generic mapped parts, preserving all other tile geometry and immediate predecessor generator, manifest, tile and FBX backups. The five source material slots, BroadTrial water and BlockAll complex collision were retained. Five live traces on the cleared site hit City ground at z10 cm. The separate `great_fire_monument_pilot/` actor adds an approximate 61.6 m stone fluted column, gallery and gilded flame, and persisted as NoCollision after reload; players can pass through it. Reliefs, inscriptions and access stairs are omitted. Four retail manifest pins and two Southwark Cathedral tile pins were rebaselined with predecessor backups after independent audit; older Fenchurch/placement snapshots remain stale. Sources: [The Monument](https://www.themonument.org.uk/about), [City of London conservation plan](https://democracy.cityoflondon.gov.uk/documents/s220473/Appendix%201%20-%20The%20Monument%20CMP%20volume%201%20-%20Conservation%20Plan.pdf).

Two further NoCollision Tachbrook stalls (`tachbrook_stall_expansion/`) reuse the first stall and produce assets. Both were viewed in PIE and persisted after reload; a sampled ~20 m route was walked both ways. The third candidate failed a ground-height consistency test and was skipped. These are illustrative stalls with no vendors or interactions. OSM geography © OpenStreetMap contributors, ODbL.


King’s Cross (`kings_cross_upper_pilot/`) has a separately saved NoCollision upper brick screen, two large opaque arched windows and a schematic clock tower to 34.5 m, above the generic z6.4 m station mass. Five live roof traces confirmed the sampled height; the actor was viewed from the south and persisted after reload. The full 1972–2012 southern concourse and interior remain unmodeled; a later partial visual treatment is recorded below. The clock is static. Sources: [Network Rail station history](https://www.networkrail.co.uk/who-we-are/our-history/iconic-infrastructure/the-history-of-london-kings-cross-station/), [Network Rail concourse history](https://www.networkrailmediacentre.co.uk/news/a-smashing-start-to-kings-cross-square-londons-newest-public-space). The exporter was corrected to handle the model without UVs; assigned materials are world-aligned or flat.

The four Westminster air grates (OSM 463759002/008/010/012, tagged layer -1) had been generated as 15 m above-ground blocks. `westminster_grates_correction/` removes exactly 40 uniquely attributed faces, retaining immediate predecessor generator, manifest, tile and FBX backups. The five named material slots, BroadTrial water and BlockAll complex collision were retained. Four post-reimport center traces hit the source road at z28 cm; the separate `westminster_grate_surfaces/` overlay sits at z28.5 cm with NoCollision and was viewed after reload, with one sampled crossing walked. Four active retail manifest guards were rebaselined with backups; King’s Cross and Monument pilot manifest pins were independently reviewed and rebaselined.

Two `tachbrook_canopy_variety/` actors add schematic cream/green and cream/red trim to the supplemental stalls. Both were viewed in PIE and their HISM and root components retained NoCollision after reload. They use existing materials and do not assert historic trader identity. Geography © OpenStreetMap contributors, ODbL.


The Actors’ Church portico (`actors_church_portico/`) is a separate approximate NoCollision addition on the piazza side, using four mapped but previously unrendered pier/column footprints. Four live ground samples hit z10 cm and three wall heights hit the expected rear wall; the actor was viewed and persisted after reload. The central door is intentionally false, as described by [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1066487) and [the church](https://actorschurch.org/visit/self-guided-tour/). Its central-tile pin was rebaselined after independently reviewing the later café correction.

The Embankment café (OSM 410816646) source correction (`embankment_cafe_correction/`) changes exactly 18 isolated vertices on ten faces from the default z15 m to an estimated z4 m; footprint and other geometry remain unchanged. The central tile retained six material slots, BroadTrial water and BlockAll complex collision. The separate `embankment_cafe_facade/` overlay uses the shared `M_BL_dark` for schematic windows and a closed door, has NoCollision and persisted after reload. Horse Guards and office-facade tile guards were rebaselined with backups. Historic reference: [2010 café photo](https://commons.wikimedia.org/wiki/File:Victoria_Embankment_Gardens,_the_cafe_-_geograph.org.uk_-_1837295.jpg).

Six illustrative K6-style telephone boxes (`telephone_kiosk_supplement/`) reuse the existing project mesh at untyped 2014 mapped telephone nodes. Five support probes per site hit the loaded City ground at z10 cm; all six were viewed in PIE and retained NoCollision after reload. Their exact historic booth types are not verified. Several placement-package source pins are stale after the café transaction and require review before reuse; existing placed actors are unaffected. Geography © OpenStreetMap contributors, ODbL.


St Dunstan-in-the-West (`st_dunstan_lantern_pilot/`) adds a schematic 39.6 m Gothic tower and octagonal lantern over the generic church. Five live roof traces hit Tile_p01_p01 at z15 m, and its silhouette was reviewed via an elevated offscreen view. The projecting clock, figures and detailed tracery are omitted. The separate actor is NoCollision. Source: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1064663).

The later Flat Iron Square open-area feature (OSM 2366863436) was incorrectly extruded into a 15 m building. `flat_iron_open_area_correction/` removes its 34 uniquely attributed faces, preserving all other source geometry, including three overlapping independently mapped buildings and the prior Tate correction. Generator, manifest, tile and FBX predecessors are backed up. The reimport retained five material slots, BroadTrial water and BlockAll. A player was spawned at the cleared site after reload; earlier land use is not reconstructed. Four active retail manifest pins and the Tate V2/V3/chimney support guards were rebaselined after independent review with backups. Geography © OpenStreetMap contributors, ODbL.


Six approximate pillar postboxes (`postbox_supplement/`) reuse the existing `SM_PillarPostBox` at mapped 2014 postbox nodes. The mesh was uniformly scaled 0.65 to approximately 145.24 cm and positioned with its measured local bottom on the sampled ground. All six were viewed in PIE and retained the scale and NoCollision after reload; exact designs and dates are not asserted. Asset: [Minimaliano, London Street Props](https://www.fab.com/listings/3a15c74a-8a6f-4f51-b488-28cb6da0205c), CC BY 4.0. Geography © OpenStreetMap contributors, ODbL.

The St Dunstan guard originally pinned the wrong tile; its corrected guard now includes the actual Tile_p01_p01, matching an independently retained earlier source baseline. The original guard and audit are preserved in the pilot directory. The actor's NoCollision profile was verified after reload.


Knightsbridge/Belgravia storefront variation (`knightsbridge_storefront_pilot/`) changes 28 panel material entries across 14 ordinary shops without changing geometry or UVs; it reuses six previously accepted materials. A source-ID scratch reconstruction and ten-pair raw-builder guard matrix passed, the previous guard was backed up, and the installed guard blocks all ten applied/mixed source pairs. Sampled PIE fronts were viewed; the tile retained 11 expected material slots and BlockAll after reload. These are generic illustrative fronts, not verified historic businesses. OSM geography © OpenStreetMap contributors, ODbL.

BT Tower's separate `bt_tower_skin_pilot/`, `bt_tower_aerials_pilot/`, and `bt_tower_glazing_pilot/` actors provide a smooth gray shaft, estimated microwave horns/dishes, and opaque glazed upper bands. The 9.72 m radius shaft wraps an overly wide source section and is wider than the historic core; exact proportions, aerial orientations and floor heights are approximate. The original source and collision remain, with all three additions NoCollision. Elevated and distant views were checked and actors verified after reload. There is no interior. References: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1350342), [BT Archives](https://www.bt.com/bt-plc/assets/documents/about-bt/our-history/bt-archives/information-sheets-and-timelines/bt-tower.pdf), and [Twentieth Century Society](https://c20society.org.uk/news/bt-tower-to-be-sold-in-275-million-hotel-deal).

The `waterloo_district_gap/` trial places two reversible BlockAll complex-as-simple road-material meshes over five mapped road/footway gaps, approximately 266 m² total. Six representative pre-placement ground traces found z10 cm and post-placement traces hit the new z28.8 cm surfaces. Two visual views and a local two-way walk were sampled; after reload, short forward-and-back walks were sampled at all six trace points. Both actors retained BlockAll. Component ends, ramps, street furniture, all routes and other collision channels were not comprehensively tested; the approach is not approved for general automatic rollout. Geography © OpenStreetMap contributors, ODbL.


The `Waterloo Road center marking pilot` uses seven instances of the existing zebra-paint material as 2 m × 12 cm dashes, spaced 6 m apart on a section of 2014 way 107677719. The exact markings are estimated. Seven pre-placement traces hit z28 cm source road, and approximately 47 m was walked in both directions; the seven-instance NoCollision actor persisted after reload. `waterloo_centerline_survey/` found that conservative junction, crossing and source-support exclusions do not justify a continuous extension. Geography © OpenStreetMap contributors, ODbL.

Four `lamp_cluster_pilot/` actors reuse the existing non-emissive RoadLamp_Arterial at modern mapped nodes on Parliament Street and Charing Cross Road; each had five level support traces and was viewed in PIE, then retained NoCollision after reload. Candidate 9196521407 was skipped due to uneven support. Positions and historical lamp designs are estimates; foliage, full sidewalk access and all nearby custom actors have not been exhaustively checked. OSM geography © OpenStreetMap contributors, ODbL.

The `holborn_facade_trim/` pilot adds 43 pale stone bands to 12 ordinary 2014/current-matched upper walls, as separately saved NoCollision actors. Source checks confirmed wall support and an independent geometry audit found two clashes with anonymous-commercial panels; the z3.2 m band was removed from buildings 81467974 and 270238004. Both corrected storefronts were viewed after reload, all 12 actor collision states were verified, and other bands had no positive-area overlap with the current commercial triangles. Custom signs and unviewed elevations remain unverified; bands and historical proportions are illustrative. OSM geography © OpenStreetMap contributors, ODbL.

The `city_nonbuilding_batch/` source transaction removed 32 faces associated with outdoor seating 774598644 and a ground-floor `building=no` shop area 631502588 in Tile_p03_p01. Seven coincident shop/office faces were removed by exact multiset subtraction, retaining all non-target triangle multiplicities, including the independently mapped office. Backups and successor guards were saved. After reimport the five slots, BroadTrial water, BlockAll and captured collision state matched on reload. The outdoor site traced to z10 cm, two office points retained a z15 m roof, and a roughly 35 m Bury Court route was walked both ways. Earlier land use is not reconstructed. Source geography © OpenStreetMap contributors, ODbL.


Following the City non-building transaction, four active retail/RCJ manifest guards and the Lloyd’s and Bishopsgate source pins were rebaselined after independent local triangle review. Prior guard files and receipts are retained in `city_nonbuilding_batch/asset_guard_backup/` and `city_nonbuilding_batch/city_asset_guard_backup/`; revert dependent pins before any source rollback. Several earlier placement-package pins are deliberately stale, including central lamps, lamp cluster, Holborn trim, bus stops, bins, telephone boxes and reused street plates. Existing placed actors are unaffected; future placements require renewed source/clearance review rather than forcing those pins. A narrow Charing Cross upper-window overlay was tested and removed after it looked like an isolated strip on a much larger blank wall; its unique unused asset may remain in the project.


The `garrick_arms_pilot/` actor adds an original schematic green pub frontage, static awnings, dark glazing and two generated Noto Serif Bold name panels to mapped 8–10 Charing Cross Road. Font is SIL OFL 1.1 with license in the package. The separate `GarrickArmsUpper` actor adds existing pale-window material above it; its window rhythm is approximate. Both actors are NoCollision and persisted after reload; lettering was viewed from the street and a roughly 23 m sidewalk route walked both ways. No interior or working door is modeled. References: [contemporary CAMRA guide](https://londondrinker.camra.org.uk/londonbeerguides/WLPG.pdf), [2008 exterior photograph](https://www.flickr.com/photos/55935853@N00/2413170842), used as reference only, and © OpenStreetMap contributors, ODbL. The nearby west upper-window trial was rejected and removed, as recorded above.


The Bank of England and Mansion House frontage package source/manifest pins were separately rebaselined after the City batch and intervening accepted transactions were audited; their local supporting geometry is unchanged. Previous baselines and audit receipts are `bank_entrance_pilot/baseline_before_city_nonbuilding.json`, `bank_entrance_pilot/city_nonbuilding_rebaseline_audit.json`, and their `mansion_house_pilot/` counterparts. Review and restore dependent pins before rolling back the City transaction.


The `parliament_gap_survey/` Whitehall pilot adds a 105 m² road-material surface with two approximately 38 cm holes around the existing non-colliding lamp bases. Five pre-placement points hit City ground at z10 cm; after enabling BlockAll they hit the patch at z28.8 cm, while lamp centers still hit z10 cm. A roughly 53 m length and a cross-street route were walked both ways, with short walks sampled around both lamp holes; the actor retained BlockAll after reload. The remaining height transitions, curb geometry, other objects and untested routes remain approximate. Geography © OpenStreetMap contributors, ODbL.


`charing_cross_broad_fix/` adds separate non-colliding approximate office-grid and 19 Charing Cross Road window actors, covering 23.1 m and 9.6 m of supported upper walls respectively. Twenty-one source-wall slices passed; the office’s attribution to former Alhambra House is an inference and two low end segments were intentionally excluded. The accepted Garrick frontage and all central source overrides remain untouched. Front and oblique samples were viewed, a roughly 53 m route was walked both ways, and the four instanced components retained NoCollision after reload. Ground floors and surrounding blocks remain generic. References: [Westminster report](https://westminster.moderngov.co.uk/documents/s23683/ITEM%203%20-%20ALHAMBRA%20HOUSE%2027-31%20CHARING%20CROSS%20ROAD%20LONDON%20WC2H%200AU.pdf), [pre-hotel facade reference](https://arthurlloyd.co.uk/Alhambra/now.jpg), and © OpenStreetMap contributors, ODbL.

The `kings_cross_1972_canopy/` and `kings_cross_1972_frontage/` actors add a schematic 24.1 m green canopy and opaque glazed frontage to part of the station, evoking the temporary southern concourse present before its 2012–13 removal. Layout, length and materials are estimated; decorative doors are closed and the original solid source wall remains. The complete concourse, interior and facilities are not modeled. Nine wall and four ground traces supported placement; the approximately 29 m adjacent route was walked in both directions, and both actors retained NoCollision after reload. References: [National Railway Museum](https://blog.railwaymuseum.org.uk/kings-cross-redevelopment-wins-heritage-award/), [Network Rail](https://www.networkrailmediacentre.co.uk/news/a-smashing-start-to-kings-cross-square-londons-newest-public-space), and © OpenStreetMap contributors, ODbL.


The `lyceum_theatre_pilot/` actor provides a shallow original six-column portico, pediment, closed entrances and geometric LYCEUM THEATRE lettering on mapped building 54327344. It projects at most 53 cm and is a schematic rather than a surveyed reconstruction; the actual portico is deeper, and no interior or working doors are provided. Nine wall traces and six z10 cm ground traces supported placement. It was viewed in PIE, the approximately 11 m adjacent route was walked both ways, and NoCollision persisted after reload. References: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1066119), [2008 Colin Smith photograph](https://commons.wikimedia.org/wiki/File:Lyceum_Theatre_-_geograph.org.uk_-_650371.jpg), used as reference only, and © OpenStreetMap contributors, ODbL.


The `neals_yard_passage/` transaction cuts an estimated 2.1 m × 2.9 m opening in the source wall of building 350310196 along mapped footway 374835687, preserving unrelated faces/materials and roof triangles. Eleven uniquely attributed wall triangles were replaced by 25 clipped pieces; source/FBX backups and inherited-guard successor are retained. After reload, the five slots, BroadTrial water and captured BlockAll/collision state matched preflight. Horizontal traces at z150/250 cm cleared the passage while z320 cm hit the retained upper wall. Ground samples found z28 cm at the entrance and z10 cm inside; the player walked from (6700,73940) through to (9034,73736) cm and back. Neighboring building 350310104 narrows the route, and this is not exhaustive access testing or a measured architectural reconstruction. Sources: [Seven Dials study](https://sevendialscoventgarden.study/neals-yard/the-yard-frontages/) and © OpenStreetMap contributors, ODbL.


`central_facade_expansion_pilot/` adds four separately removable NoCollision actors with repeated `M_CentralStoneWindows` panels on 22 ordinary, unnamed 2014/current-matched central-building street edges above z5 m. Protected IDs and known overlays were screened, 66 source-wall slices had full support, and four partial-wall transitions were excluded. Several examples across all groups were visually sampled; all four collision states survived reload and the two eastern actors unloaded/reloaded in a far-and-return streaming sample. Ground floors remain blank in places, textures repeat, and unviewed custom overlays or historic features are not ruled out. The selection-hash typo in the placement helper was corrected with a backup and negative tests; its manifest pin was narrowly rebaselined after the Neal’s Yard transaction with independently reviewed predecessor records. Geography © OpenStreetMap contributors, ODbL.

After the Neal’s Yard transaction, four active retail/RCJ guards and the accepted Tottenham continuous-gap pin were rebaselined with backups in `neals_yard_passage/asset_guard_backup/` and `tottenham_guard_backup/`. Holborn’s guard, placement plan, helper and verifier were also rebaselined after local geometry review; its successor preserves the two removed shop-clashing bands. Backups are in `holborn_guard_backup/`. On a future Neal’s Yard rollback, do not blindly restore the older 45-band Holborn plan: preserve the corrected 43-band plan and independently rebaseline its pins. Other stale placement snapshots still require package-specific review.


`crosby_rough_survey/` adds an estimated 949.34 m², 28.8 m eight-floor predecessor mass on part of the cleared 22 Bishopsgate site, not a surveyed Crosby Court footprint, height or facade. The earlier, larger candidate was rejected because it crossed mapped passage 742500336; the revised footprint is approximately 4 m from that mapped route. A 2006 plan and City planning record provide context only; the historical tunnel and other predecessor buildings are not modeled. Four ground samples hit City ground z10 cm, a bounded grouped-prop source screen found no recorded conflict, and two mapped routes were walked both ways before and after placement. The uniquely imported mesh was switched from NoCollision to BlockAll complex-as-simple with double-sided geometry; four sampled perimeter faces blocked traces from both directions and settings survived reload. A third adjacent approach was already obstructed before placement; the mesh is open-bottomed, and all routes, collision channels, custom actors and historical circulation are not exhaustively tested. References: [City planning record](https://democracy.cityoflondon.gov.uk/documents/s72097/22%20Bishopsgate%20EC2N.pdf), [2010 engineering study](https://www.issmge.org/filemanager/article/142/ISSMGE_Bulletin_Volume_4_Issue1.pdf), [2008 tunnel case](https://www.bailii.org/ew/cases/EWHC/TCC/2008/1386.html), and © OpenStreetMap contributors, ODbL.


The Senate House V1/V2 and Garrick Arms package guards were narrowly rebaselined after the Neal’s Yard transaction. Senate’s manifest chain and distant geometry were reviewed; Garrick’s central source tile and shop placement inputs were unchanged. Predecessor baselines are retained as `baseline_before_neals_yard_review.json` in each package, with evidence in `senate_garrick_neals_rebaseline_audit.json`. The audit does not claim a complete history of unrelated non-manifest files.


The `piccadilly_arcade_passage/` source transaction opens estimated 2.7 m × 3.2 m portals along mapped footway 264760095 through Empire House, replacing six uniquely attributed wall triangles with 16 while retaining all other faces and roof. The first stage detected conflicting slash/backslash baseline aliases and restored all four source files; the normalized successor passed isolated stage, four mutation tests and rollback, then the retry staged with backups under `backup_retry_01/`. The original failed-attempt backup is retained. After reimport/reload, the five slots, BroadTrial water and captured BlockAll state matched preflight; the approximately 48 m route was walked both ways. Three interior floor samples hit z28 cm and top-down source roof samples hit z1920 cm.

`piccadilly_arcade_interior/` adds 12 anonymous opaque shop bays, a schematic shallow vault and six decorative lanterns, with NoCollision and no working doors/interiors. Six separate shadowless point lights were adjusted from the initial 800-lumen trial to 8 lumens each after it produced glare. The route was walked both ways with the interior; the actor and all six light intensities survived reload. Light spill, bright exit contrast and simplified ends remain; a later schematic checker floor is recorded below. References: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1265804), [arcade heritage](https://www.piccadilly-arcade.com/heritage/), and © OpenStreetMap contributors, ODbL.

After the accepted arcade retry, active Hatchards, Twinings, RCJ, Holborn, postbox, Garrick and Senate guards were narrowly rebaselined with evidence and predecessors in `piccadilly_arcade_passage/asset_guard_backup/`, `prop_guard_backup/` and `landmark_guard_backup/`. The independently reviewed exact transaction changed six wall faces and 16 replacement pieces. Several older street-name, reused-plate, bin and Fortnum placement baselines remain stale for additional reasons and require separate review before reuse.


`central_ground_floor_pilot/` adds 74 simple framed opaque windows to 15 of the 22 upper-facade hosts, grouped in four NoCollision actors using existing assets. Seven hosts were omitted for recorded shops or paths; both-era mapped entrance nodes and indexed custom overlays were screened. Forty-five source-wall support slices passed. Representative walls in each group were viewed, the initial nearby route was walked both ways, and all eight instanced components retained NoCollision after reload. Designs are repeated estimates without working doors; unmapped entrances, custom signs and unviewed walls remain unverified. The package’s Piccadilly manifest rebaseline was independently reviewed with predecessor pins retained. Geography © OpenStreetMap contributors, ODbL.


`central_corridor_plate_batch/` reuses existing plate meshes at Oxford/Berners, Regent/Heddon and High Holborn/Procter. Source support and source-era host checks passed; the exact historical plaque placements are not established. All three were read in PIE and retained NoCollision after reload. The underlying sign font/license remains documented with `street_name_pilot/`; geography © OpenStreetMap contributors, ODbL.


`piccadilly_arcade_support/` adds two closed BlockAll strips totaling approximately 35.63 m² where source z28 road triangles do not cover the proposed arcade floor. Nine live samples found one z10 cm edge and eight z28 cm points; the lower support height is estimated for the unmeasured remainder. The support’s two center traces hit z28 cm, four strip-end samples and a cross-floor path were walked forward and back, and the full center route was walked both ways. `piccadilly_arcade_floor/` adds a separate NoCollision 40.47 × 3.38 m checker surface at z28.8 cm, with approximately 42 cm cells. It was viewed from both directions and the full route walked again. Both floor and support collision settings survived reload; not every edge or object has been tested. Pattern and materials are schematic. Source: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1265804), © OpenStreetMap contributors, ODbL.


`piccadilly_arcade_displays/` adds 96 shallow shelf and abstract merchandise pieces to four anonymous arcade bays using existing stone/gold materials. No historical brands or interiors are asserted. Source checks excluded mullions and maintained at least 1.69 m from the corridor center. The display was viewed in PIE, the full arcade was walked in both directions and both instanced components retained NoCollision after reload. The manifest pin was narrowly rebaselined after the independently checked Savoy transaction; previous pins are retained.


The `savoy_way_passage/` transaction opens an estimated 4 m × 3.8 m corridor through uniquely attributed Savoy Hotel 190399778 along the mapped covered road. Six wall triangles were replaced by 16; roof, Savoy Theatre and unrelated geometry remain unchanged, with generator/manifest/tile/FBX backups. After reload, the tile’s five slots, BroadTrial water and captured BlockAll state matched preflight. The player walked roughly 29 m in both directions; horizontal traces at z150/250 cm cleared the route and z400 cm hit retained hotel wall. Nine center/side ground samples hit z28 cm. The interior remains generic and exact historic portal geometry is not surveyed. Source geography © OpenStreetMap contributors, ODbL.


The accepted Savoy Way transaction was independently audited via `savoy_way_passage/audit_transaction.py`. Active Hatchards/Twinings/RCJ, Lyceum, Cleopatra’s Needle, Garrick, Senate V1/V2, Piccadilly floor/support, Holborn, Waterloo surface, central corridor plate and central facade guards were narrowly rebaselined with predecessor receipts under that package’s `asset_guard_backup/`, `landmark_guard_backup/`, `prop_guard_backup/`, `surface_plate_guard_backup/` and `facade_guard_backup/`. The active source successor is now `savoy_way_passage/successor_guard.py`; the prior Piccadilly successor is historical. Several older street-name, reused-plate, bin, Fortnum, standalone bus-stop and Strand sidewalk snapshots remain stale for earlier reasons and require independent review before reuse.


The selected Trafalgar west drinking-fountain scan remains unplaced after `trafalgar_drinking_fountain/WEST_TERRACE_REASSESSMENT.md`: available references confirm a western fountain and a continuous granite retaining terrace, but not a precise attachment or grade. Two detached-support trials were visually rejected and the reduced scan has oblique edge artifacts. A credible future placement needs a connected terrace/elevation reconstruction and scan-edge repair. The original and derivative assets and their attribution are retained: *Drinking Fountain Trafalgar Square West* by artfletch, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), with cropping, decimation and reprojection in the derivative. References: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1066235) and [2009 report](https://www.edie.net/free-drinking-water-in-central-london/).


`savoy_way_headroom/` is a separate guarded successor to the earlier Savoy cut. It replaces only the 16 clipped hotel-wall triangles with adjusted pieces, removing the z3.80–3.95 m band and retaining other geometry/roof; predecessor generator, manifest, tile and FBX are backed up. After reload, source slot, water and captured BlockAll state matched preflight. Nine floor traces were z28 cm; z390/394 cm horizontal rays cleared and z396/400 cm hit the retained wall; the roughly 29 m route was walked both ways. The resulting 3.67 m sampled floor-to-portal height exceeds the mapped 12 ft by only about 1.2 cm; this does not establish clearance at every point or for vehicles. OSM geography © OpenStreetMap contributors, ODbL.


`savoy_way_interior/` adds a separate 22.89 m schematic stone shell, ceiling and four decorative fixtures, plus two 8-lumen shadowless point lights. No dated interior image was verified, so its finish and fixtures are illustrative. The visual geometry stays at least 2.01 m from the route center below z3.8 m; the ceiling bottom is z4.05 m. Nine live ground probes hit z28 cm and the route was walked both directions with the shell installed. The actor retained NoCollision and both lights retained intensity/shadow settings after reload; light bleed and untested edges remain possible. References: [Savoy engineering paper](https://onlinelibrary.wiley.com/doi/abs/10.1002/stco.201010028), [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1236709), and © OpenStreetMap contributors, ODbL.

`coliseum_globe_pilot/` adds a stationary schematic openwork globe and stone support to the mapped 39 m Coliseum cap, reaching approximately 44.05 m. It omits lettering, sculpted figures, illumination and rotation. Five roof probes supported placement; an elevated view was inspected, NoCollision survived reload, and a far-and-return sample unloaded and reloaded the actor. References: [London Coliseum history](https://londoncoliseum.org/about/), [2006 globe reference](https://www.arthurlloyd.co.uk/LondonColiseum/LondonColiseumGlobe.htm), and © OpenStreetMap contributors, ODbL.

The Savoy portal-height transaction was independently audited and active retail, landmark, Holborn, Waterloo/plate, facade and Piccadilly-display guards were rebaselined with predecessor receipts under `savoy_way_headroom/asset_guard_backup/`, `landmark_guard_backup/`, `prop_guard_backup/`, `surface_plate_guard_backup/`, `facade_guard_backup/` and `arcade_display_guard_backup/`. Savoy interior and Coliseum input guards were independently rebaselined with backups in their respective packages. The active source successor is `savoy_way_headroom/successor_guard.py`. The older packages already flagged as stale remain subject to separate review.


`lincolns_inn_bench_cluster/` reuses the installed generic bench at four illustrative offsets from mapped paths within both-era Lincoln’s Inn Fields. These are not documented individual 2014 bench positions. Five ground probes per site hit z24 cm, all four were viewed in PIE and retained NoCollision after reload; a nearby park route was walked both ways. Existing asset/license is documented in `work/agent_assets/bench/README.md`; geography © OpenStreetMap contributors, ODbL.

`lincolns_inn_tree_cluster/` adds twelve illustrative positions inside the mapped Lincoln’s Inn Fields using the existing GrayAsh mesh; the 2014 filtered tree extract has no individual mapped trees there. Camden’s 2014 ecology review and Historic England document mature park trees, but these positions and species are estimates. Five z24 cm ground probes per tree, all twelve ground-level views, a roughly 20 m two-way walk and four NoCollision groups of three after reload were checked. Existing mesh source/license is documented with the project assets; park/path geography © OpenStreetMap contributors, ODbL.

`princes_arcade_passage/` corrects the blocked connection mapped in both 2014 and current OSM, clipping twelve uniquely attributed wall triangles from two host buildings into an estimated 2.4 m by 3.2 m corridor; the roofs and unrelated material triangles remain. The guarded source and FBX transaction retained an immediate backup. The complete bent route and the previously treated Piccadilly Arcade were each walked both ways after reload, and the source actor’s slots, material defaults and overrides, BlockAll profile, complex collision and exposed responses matched preflight. Ground at sampled entrances is z28 cm and z10 cm inside; the historical sloping floor, shopfronts and interior are not reconstructed. Source geography © OpenStreetMap contributors, ODbL; see Historic England listing https://historicengland.org.uk/listing/the-list/list-entry/1265805.

`work/agent_assets/eleanor_cross/` supplies an original schematic Queen Eleanor Memorial Cross at OSM node 10969212579 in the station forecourt (© OpenStreetMap contributors, ODbL). Network Rail gives the 70 ft height and restoration timing; Historic England describes the octagonal memorial and statues. Estimated 1.98 m base radius, materials, relief, proportions and simplified figures are not survey reconstructions. Nine ground samples hit z10 cm; street/elevated views and a roughly 29 m forecourt walk in both directions were checked. Actor retained NoCollision after reload; underground accesses and complete surroundings were not surveyed.

`work/agent_assets/princes_arcade_interior/` adds a schematic, original standalone visual layer to the mapped route: 16 anonymous bays, shallow goods, ceiling and six non-emitting lanterns. It is inspired by Historic England and David Iliff’s June 2009 panorama (CC BY-SA 3.0, reference only), not a reconstruction of exact businesses. Source masks and an independent low-triangle audit reserved at least 1.33 m from centerline; the full route was walked both ways and the actor retained NoCollision after reload. Lighting is dim, the turn has a simplified open side, and a later floor treatment covers the central strip. OSM geography © contributors, ODbL.

Princes post-acceptance guard audit: `work/agent_audit/princes_arcade_passage/accepted_transaction_audit.md` records exact source-diff validation, retained Piccadilly Arcade and Hatchards local geometry and 19 backed-up rebaselines. The original Piccadilly interior guard pins historical candidate files, so `piccadilly_interior_supplement_guard.py` separately verifies the canonical tile; it is not automatically wired to the original helper. Older already-stale snapshots were not updated.

`work/agent_assets/princes_arcade_floor/` adds a 2.30 m-wide schematic checker visual and an independent closed support from z10 to z28 cm. Fifteen prior interior samples and six end samples were tested, then centerline support traces, a full two-way route and one transverse side step were checked. After reload the visual retained NoCollision and the support BlockAll complex-as-simple. Lower asphalt-like side slivers, the historical slope and complete accessibility remain unresolved. OSM geography © contributors, ODbL.

`oxo_tower_face_pilot/` adds an original, schematic three-window treatment to current OSM part 2899777524’s river face; the 2014 outline differs by ~14 m. The 2004 ChrisO photograph (CC BY-SA 3.0, reference only), Coin Street and the refurbishment architects support the motif and period. Multiple wall traces, including the outer margins, street and elevated views and a roughly 23 m two-way nearby walk were checked; the actor retained NoCollision after reload. Its proportions, simplified mullions and opaque materials do not reproduce the real apertures or lighting; surrounding tower remains generic. Geography © OpenStreetMap contributors, ODbL.

`charing_cross_canopy_correction/` removes twelve uniquely attributed wall triangles from OSM roof part 2753577258; its four roof triangles and all unrelated source faces/materials remain. The prechange canopy wall intruded into the mapped covered footway, although a walking sample slid around its corner. After reimport and exact full actor preflight after reload, z150/500 rays reached the rear hotel wall, route segment rays were clear, five ground samples hit z28 cm, and one roof sample hit z600 cm. The covered forecourt route and Horse Guards central passage were walked both ways. Roof form and station-inward entrances remain unmodeled. Source geography © OpenStreetMap contributors, ODbL; Historic England lists an altered canopy and arcaded hotel frontage.

`work/agent_assets/charing_cross_hotel/` supplies original schematic facade geometry for the hotel’s mapped forecourt face following the retained host’s setback. Historic England and Ben Brooksbank’s 1983 photograph (CC BY-SA 2.0, reference only) inform the 3+12+3 bay rhythm and period. The relief, windows and materials are estimates; authentic ground arches, balustrade, carvings and functional station/hotel entrances remain absent. Source and independent low-triangle screens reserve mapped routes; the facade was viewed, the covered forecourt route walked both ways, and NoCollision retained after reload. OSM geography © contributors, ODbL.

The canopy correction’s accepted source diff and 23 current JSON guard rebaselines plus the Horse Guards text pin are independently documented in `work/agent_audit/charing_cross_canopy_correction/accepted_transaction_audit.md`; backups are beside it. Older stale historical guards remain unchanged.

The Charing Cross hotel frontage helper and validator now pin the current canonical central tile and manifest as well as the historical candidate. In-memory mutations of either canonical file fail the guard; predecessor files are retained in `work/agent_assets/charing_cross_hotel/pre_canonical_source_guard/`.

The women_wwii_memorial_v2 pilot adds an original schematic bronze skin to the existing source mass for OSM memorial 594367358, inspired by the hanging uniforms documented by IWM and NHMF. The actual 17 sculpted uniforms and lettering are not reproduced; the design represents the post-July-2005 period. An earlier arrow-like pilot actor was removed after visual review; its unique assets remain as a backup. Four source faces and roof were traced, all four treatment faces viewed, and approximately 15 m walks on both sides completed in each direction. The visual actor retained NoCollision after reload; source mass collision is unchanged. The shaded relief is difficult to see. OSM geography © contributors, ODbL.

The royal_opera_bow_pilot adds an original schematic Bow Street portico to active OSM parts 1266440476 and 1266440472. Six roof traces supported the z600 cm source podium; the mid-span backing is additive because wall rays missed between z6 and z18 m. The frontage was viewed from the street and both ends, an approximately 28 m Bow Street stretch was walked both ways, and NoCollision survived reload. The doorway, glazing, details and proportions are visual approximations, with no theatre interior. OSM geography © contributors, ODbL; Royal Ballet and Opera history and Russ London's 2007 CC BY-SA 3.0 photograph provided reference.

The cheapside_storefront_plan changes twelve panel material entries across six existing anonymous fronts in Tile_p02_p01, reusing accepted displays and preserving geometry and UVs. Exact actor bindings and collision matched after reload, three representative appearances and a nearby walk were checked. The eleventh-pair raw-builder guard was independently reviewed and installed with its predecessor retained; its full-prefix and scratch reapplication tests pass. The shops are illustrative, unnamed and closed. Geography © OpenStreetMap contributors, ODbL.

The district_tree_plan and district_tree_successor add 24 illustrative GrayAsh instances in three spatial HISM actors: Bloomsbury Square 6, Berkeley Square 9 and Paddington Street Gardens South 9. Source masks screen mapped paths and known props; ground traces, representative live views and short walks were sampled. Instance counts and NoCollision persisted after reload. These are not individually documented historic positions or species, and performance has not been benchmarked. OSM geography © contributors, ODbL.

The multidistrict_storefront_batch changes only display material assignments on 85 existing anonymous fronts across sixteen tiles. Each tile has an immediate source/FBX backup; its actor bindings and BlockAll collision were checked after reload. Representative clothing, grocery, bookshop and generic views and local walks were checked; one tile in each of the first two groups streamed out and back. One group-2 grocery is only confirmed from a closer position due to neighboring geometry. Independently reviewed additive regeneration guards for all four groups are installed; see the batch audit and group receipts. OSM geography © contributors, ODbL.

The park_edge_trees pass adds 40 illustrative GrayAsh instances across Archbishop's Park, Vauxhall Pleasure Gardens, King Square Gardens, Shoreditch Park and St George's Square in 15 bounded spatial HISM actors. Source screens reserved mapped paths and known props; ground probes, representative park views and a short route were sampled. All 40 instances and NoCollision persisted after reload. Species and locations are approximate; rendering cost is unmeasured. OSM geography © contributors, ODbL.

The multidistrict_bin_clusters pass adds 25 NoCollision bins in 23 small spatial HISM groups, reusing the existing Minimaliano London Street Props mesh (CC BY 4.0). Candidate locations are based on 2014 waste-basket nodes or illustrative offsets from bus stops; two uneven-surface candidates and one near-duplicate were omitted. Ground probes, representative views, a nearby walk and one local far-return streaming test were checked; all 25 instances and NoCollision survived reload. Exact historic placements, sidewalk accessibility and runtime cost are not established. Geography © OpenStreetMap contributors, ODbL.

The park_edge_trees_v2 pass adds 40 illustrative GrayAsh instances in 12 bounded spatial HISM actors across Grosvenor Square, Gordon Square, Whitehall Gardens, Tanner Street Park and Larkhall Park. Source screens reserved mapped paths and known props; ground probes, representative park views and a short route were sampled. All 40 instances and NoCollision persisted after reload. Species and locations are approximate; rendering cost is unmeasured. OSM geography © contributors, ODbL.

The multidistrict_sidewalk_pilot adds about 280 m² of NoCollision paving in three actors on Weymouth Street, Aldwych and Carey Street, supported by existing z28 cm source triangles. Saved-source coverage checks, five live support probes per patch, representative views and two-way walks were performed; all three actors retained NoCollision after reload. These are approximate current-way finishes with abrupt boundaries, not a historical survey or new physical walking slabs. OSM geography © contributors, ODbL.

The whole_host_facade_batch changes attributed wall material assignments on 20 ordinary hosts across Tile_m01_p01, Tile_p01_p00 and Tile_p04_p01, reusing M_CentralStoneWindows. Geometry, roofs, non-target materials and non-target FBX UVs remain unchanged; target UVs use full-height phase. Three independent source/FBX backups and generator protection are recorded. Actor/material/collision states matched after reload; representative fronts, an Oxford street walk and the Savoy Way passage were sampled. Appearance is schematic and repeated, not a historic facade survey. OSM geography © contributors, ODbL.

The multidistrict_sidewalk_batch adds 36 approximate supported NoCollision paving patches across six tiles in 18 spatial actors, approximately 2,882 m². Source masks and live support probes were checked; representative views, two-way walks, one far-return streaming sample and all actor collision states after reload passed. It leaves existing physical walking surfaces unchanged. Current mapped sidewalks, unknown custom props and visible patch boundaries remain limitations. OSM geography © contributors, ODbL.

The whole-host facade source audit and eight active dependent guard rebaselines are recorded in work/agent_audit/whole_host_facade_batch/asset_guard_rebaseline_audit.json and associated package-local backups. Older snapshots with pre-existing drift remain stale.

The multidistrict_park_benches pass adds 32 illustrative GrayLondonBench instances across eight parks in 12 local HISM groups. Source masks reserve paths and known trees/furniture; one four-bench Tanner Street group was skipped after uneven ground probes. Representative views and a short walk were checked; all retained NoCollision after reload. Positions, facing and exact historic appearance remain approximate. OSM geography © contributors, ODbL; bench texture attribution is in work/agent_assets/bench/README.md.

The whole_host_facade_next pass adds approximate material variation to 80 ordinary building hosts across four tiles, on top of the earlier 20-host pass. It changes attributed wall material assignments while retaining existing geometry and collision; the repeated facades are not a survey of historic finishes.

The multidistrict_sidewalk_batch2 adds 80 approximate NoCollision paving patches covering about 6,369 m² in 45 bounded visual actors across ten additional tiles. Existing source surfaces continue to provide physical walking collision. The current mapped sidewalk layouts and visible patch transitions are approximate.

The road_markings_gap_batch adds 25 estimated NoCollision road dashes in seven locally streamed groups across Curzon Street, Bruton Street, Stamford Street, Lambeth Palace Road and Southwark Bridge Road, using existing paint and geometry. Their precise target-period placement and pattern are unverified.

These additions were saved and reloaded. Representative street views and walking routes were sampled, together with pavement streaming; not every location was reviewed. Geography © OpenStreetMap contributors, ODbL.

### Street trees and lamps
Ninety-nine mapped 2014 tree locations across nine tiles now reuse the existing ash model in 17 locally streamed, non-colliding groups. Species, scale and historic appearance are approximate, and the trees can be walked through. Ninety-one trees have schematic textured soil patches beneath them; eight were omitted from the soil pass because of nearby road, fixture or raised-surface conflicts, and some roots extend beyond the patches. Representative views, a two-way walk and a far-return streaming sample were checked, and all 99 instances retained NoCollision after reload. Rendering cost has not been benchmarked.

Seven simplified, non-emissive street lamps were added at current mapped locations in Belgravia, Chelsea and Westminster; one candidate on uneven ground was omitted. These locations and models are estimates for the 1980s–2000s, and the poles have NoCollision. Representative views and ground traces were checked, and all seven actors retained NoCollision after reload. Geography © OpenStreetMap contributors, ODbL.

### Wider facade variation
A further 411 ordinary buildings across 13 city tiles now reuse an existing pale stone-and-window finish. These are schematic, repeated materials applied to whole source walls; they are not surveys of individual historic buildings. Thirty-six candidate hosts overlapping protected 2014 building footprints were excluded. Source geometry and other material assignments were preserved, the tile actors were saved and checked after reload, and representative street-level views were sampled. Some earlier landmark verification snapshots remain historical rather than current. Geography © OpenStreetMap contributors, ODbL.

### More anonymous shop displays
One hundred and fifteen additional existing shopfronts in 28 streamed tiles reuse bookshop, clothing, food and general retail displays. The displays are illustrative, signs are blank, and the shops remain closed. Their source geometry and UVs are unchanged. The actors retained their expected material bindings and collision after reload; representative bookshop, general-retail and existing grocery views were sampled. Geography © OpenStreetMap contributors, ODbL.

### Telephone kiosks across districts
Twenty-seven simplified red K6-style kiosks were added at mapped 2014 public-telephone locations in 22 tiles. Six of those locations have a current K6 tag; the enclosure at other locations and its exact 1980s–2000s appearance are estimates. The kiosks are nonfunctional and have NoCollision. Ground checks and a representative view were sampled, and all 27 actors retained NoCollision after reload. One proposed location currently describes a black, non-BT telephone and was omitted. Geography © OpenStreetMap contributors, ODbL.

### Bus-stop signs across districts
Sixty simplified, nonfunctional London bus-stop flags were added near mapped 2014 stops across 57 tiles. Some are shifted slightly for local clearance; their exact historic signs and timetable details are estimates. The poles have NoCollision. Ground probes, representative views, a two-way walk and a far-return streaming sample were checked, and all 60 actors retained NoCollision after reload. Geography © OpenStreetMap contributors, ODbL.

### Shelters at mapped stops
Twelve simple open-sided shelter proxies now sit near mapped stops with current shelter evidence. Their exact period presence, design and position are estimates. They reuse the project's shelter materials and have NoCollision; the seats and bus service are not functional. Ground probes and a representative view and two-way walk were sampled, and all 12 actors retained NoCollision after reload. Geography © OpenStreetMap contributors, ODbL.

### Residential material correction
A city-tile material scan found a checkerboard fallback on one residential tile, with two door materials shifted by compacted slot ordering. Its actor now binds the intended brick facade, door frame and door panel by name. The other 120 city tiles had no fallback material on source-used slots in the scan. The correction was saved and matched its recorded state after reload; a street view and nearby two-way walk were checked. A future rollback of that tile's wider facade change must first roll back this actor-level material repair.

### Residential roof silhouettes
Twenty-eight small schematic chimney stacks were added to mapped ordinary residential roofs across Marylebone, north London and Southwark, in 11 compact groups. Individual chimneys and historic details are estimates. Saved source roofs and live support traces were checked, and an elevated view was sampled. All 56 body and cap instances retained NoCollision after reload; performance was not benchmarked. Geography © OpenStreetMap contributors, ODbL.

### Imported modular facade trial
A [Poly Haven modular urban facade kit](https://polyhaven.com/a/modular_urban_apartments_facade), CC0, is imported into a separate project content folder. One narrowed existing door module is fitted as a decorative, nonfunctional trial at a mapped entrance; it was viewed and the nearby route walked in both directions, and the NoCollision actor survived reload. The module is generic contemporary architecture rather than a surveyed historic door; its source mesh has a large baked pivot offset. Other parts of the kit are available for review but have not yet been broadly placed.

### PCG park railing trial
An editor-generated Unreal PCG graph places three instances of the existing Minimaliano London Street Props fence mesh along a short mapped Russell Square park edge. The style and the roughly 0.25 m offset are estimates. The generated instances have NoCollision; ground support, a street view, a nearby two-way walk, far-return streaming and reload were sampled. This is a local pilot, not a citywide procedural pass or performance benchmark. Model: Minimaliano, [London Street Props](https://www.fab.com/listings/3a15c74a-8a6f-4f51-b488-28cb6da0205c), CC BY 4.0. Geography © OpenStreetMap contributors, ODbL.

### Wider PCG park railings
An additional 410 instances of the existing London Street Props railing mesh are generated by local Unreal PCG graphs across nine mapped park areas. The inferred railing style and locations are approximate, and the railings are visual and pass-through. Source masks, live ground probes, representative street views and routes were checked; the 51 refined groups retained 371 NoCollision instances after reload. Two groups too close to a building or tree and one isolated panel were removed after visual review. Uninspected segments and performance remain unverified. Model: Minimaliano, [London Street Props](https://www.fab.com/listings/3a15c74a-8a6f-4f51-b488-28cb6da0205c), CC BY 4.0. Geography © OpenStreetMap contributors, ODbL.

### Imported environment kits
[City Street Props](https://www.fab.com/listings/717d655e-923f-4c03-bc0b-3509fd1b0ec8) by Dekogon Studios and [Modular Urban houses](https://www.fab.com/listings/c6a42d9c-f2c5-4155-8ced-b1d6d1592f41) by Replex have been imported. The latter is CC BY; retain the creator attribution. The street-prop listing reported both Fab Standard tiers as free at import. A mismatched window-bay trial and a bank-branded awning over a clothing shop were removed after visual review; the City Street Props awning is used in the procedural placement described below. The separate City Sample Buildings Fab workflow was cancelled and its assets were not imported. Six additional [Poly Haven](https://polyhaven.com/license) CC0 street-asset sets have been imported for inspection.

### PCG shop awning trial
One anonymous clothing storefront now has a muted, solid-color awning generated by a local Unreal PCG graph using the existing [City Street Props](https://www.fab.com/listings/717d655e-923f-4c03-bc0b-3509fd1b0ec8) mesh and a project canvas material. It is an illustrative design and partly covers the blank fascia; the shop remains closed. Front and oblique views and a nearby two-way walk were sampled. The material override and NoCollision instance survived regeneration and reload. The earlier bank-branded version was removed.


### Shop awnings across the city
An additional 66 anonymous storefronts across 30 city tiles now use the imported City Street Props awning mesh, placed by 53 small local Unreal PCG groups. Three project-made muted canvas colors (slate, sage and oxide) use instanced-mesh support; the earlier checker-pattern material was replaced. The awning designs and locations are illustrative and sometimes cover part of a blank fascia. They have no collision, and the shops remain closed. Source masks and live wall, ground and clearance probes were used; after a level reload all 53 groups contained the expected 66 instances with the assigned colors and NoCollision. Front views at five separated examples and all three colors were sampled, but individual placements, all routes, and performance have not been exhaustively checked. Model: Dekogon Studios, [City Street Props](https://www.fab.com/listings/717d655e-923f-4c03-bc0b-3509fd1b0ec8); source geography © OpenStreetMap contributors, ODbL.


### Tate Britain, Millbank
An original schematic stone treatment now marks Tate Britain with six paired-edge columns, a pediment, arched decorative openings, a low dome and two set-back wings. A raised entrance and a 21-riser staircase approximate its 2000s Millbank appearance. The stair count follows current mapping and the flight lies within the 2014 mapped steps area; exact historic proportions are estimates. The columns, ornaments, windows, dome and wings are simplified. The doors are decorative and closed, and the original solid building remains behind them. A small illustrative TATE BRITAIN sign stands beside the steps; its exact historic wording and position are estimated.

Wall, roof and ground support were traced, and the frontage and distant Thames view were inspected. The current and 2014 mapped approaches were walked up and down the centered stairs; a nearby south-side footway was also walked both ways. After a level reload, the staircase retained 21 treads and a landing with BlockAll collision, and the visual actors retained NoCollision. A far/near play sample unloaded and loaded all eight local actors. These checks do not cover every entrance, adjoining route or performance. Geography © OpenStreetMap contributors, ODbL. References: [Historic England listing](https://historicengland.org.uk/listing/the-list/list-entry/1222913) and [a 2009 exterior photograph](https://www.geograph.org.uk/photo/1300172).

The centered staircase is a dependent adjustment to the raised-entrance trial. If reverting that work, first restore the prior stair instance transforms using the `tate_britain_stairs_center` rollback, then follow the recorded `tate_britain_stairs` rollback to restore the portico, detail and dome together.


### St James’s Palace gatehouse
A schematic red-brick gatehouse now marks the Pall Mall frontage with two turret forms, a closed Tudor-style gate, windows, a decorative clock and a small cupola. It uses original simplified geometry fitted to the mapped source wall. The clock is static and the gate is decorative; the solid source building remains behind the visual treatment. A 2008 photograph informed the appearance, but the proportions, materials and placement are estimates.

Wall, ground and roof were traced; a street view and a two-way walk along a sampled frontage were checked. The actor and its material overrides persisted with NoCollision after a level reload, and a far/near play sample unloaded and loaded it. These are local checks and do not establish every nearby route or detail. Geography © OpenStreetMap contributors, ODbL. References: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1264851) and [a 2008 exterior photograph](https://commons.wikimedia.org/wiki/File:St_James%27s_Palace,_Pall_Mall,_gatehouse_2665083660.jpg).


### Albert Memorial, Kensington Gardens
The generic central block and four corner blocks have been replaced by a reduced, registered scan of the Albert Memorial and its sculpture groups. The scan is by artfletch, [Albert Memorial](https://zenodo.org/records/10307114), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). It was reduced from about 1.85 million to 648,936 triangles, repositioned and given a two-sided material. The 2020 capture approximates the post-1998 restored appearance; its 1024-pixel texture, scanned shadows, scale, terrain fit and placement have limitations. The source record says some upper-step views incorporated frames from a linked YouTube video; separate permission for those frames is not established in the record.

The visual scan has NoCollision. Five low invisible BlockAll proxies approximate the central and corner sculpture bases; the decorative fence and scanned steps are not physically modeled. The old blocks' collision was removed, all five proxy tops were traced after reload, and a sample walk along the south path and an approach to the central base were checked. South and east views were inspected, and a far/near play sample unloaded and loaded the scan and proxies. These checks are local, not a full route survey or performance benchmark. Two nearby generic mapped blocks remain pending identification. Geography © OpenStreetMap contributors, ODbL.

The `OSM Tile_m03_m01` actor now uses the separately saved `SM_AlbertTile_central_america_asia_africa_europe` mesh, derived from the original tile with 86 identified placeholder triangles removed. Its remaining face positions, winding, material sections, UVs, normals and extracted complex collision were compared to the original; the actor retained its recorded material overrides and BlockAll profile. The original tile asset is untouched. Future regeneration or reimport of the original will not update this fork: reconcile the change or use the recorded `albert_memorial_duplicate` switch rollback before editing that tile. Remove the five recorded collision proxies and the scan separately if reverting the replacement.

### Waterloo Victory Arch and Royal Festival Hall
An original, schematic Victory Arch treatment now identifies Waterloo station with a clock, arched glazing, canted wings and a station sign. Its proportions and architectural details are estimates, and the existing solid station wall remains behind it. The entrance is decorative and closed; there is no station interior. A sampled route along the frontage was walked both ways, and the approach was checked against the existing wall. The actor retained its mesh, material overrides and NoCollision after a level reload. References: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1063898) and a [2009 photograph](https://commons.wikimedia.org/wiki/File:The_Victory_Arch,_Waterloo_Station,_London_-_geograph.org.uk_-_1374272.jpg).

An approximate modernist stone and glazed treatment now covers four mapped riverside wall sections of the Royal Festival Hall, with a double-height glazed zone and a suggested upper terrace. The glazing is opaque, the terrace and entrances are decorative, and the underlying solid building and its collision remain. The real elevated terrace is flattened in this prototype. Wall support was sampled at three heights on each section, and two stretches beside the frontage were walked in both directions. The facade and three joint strips retained their material overrides and NoCollision after a level reload. These are local checks, not a full access or performance survey. References: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1249756) and the [government's building case study](https://assets.publishing.service.gov.uk/media/67ee91cce9c76fa33048c75f/Volume_Two_Case_Studies_Final.pdf). Geography © OpenStreetMap contributors, ODbL.

### Battersea Power Station period pass
Four original, approximate pale tapered chimneys replace the generic window-textured cylinders on the mapped power station. Their bases sit on the existing modeled wash-tower roofs; their fluting and dimensions are simplified, and the chimney actor has NoCollision. Schematic brick treatments add tall decorative windows to both end faces and smaller industrial windows and closed bay panels to the long sides. The intact roof does not represent the derelict, roofless period shell. Three Circus West apartment blocks completed in 2017 were removed, while the cleared area's earlier buildings and landscape have not been reconstructed. Other surrounding modern development remains.

An aerial and riverside view, both end faces and representative side details were inspected. Four roof supports and sampled wall planes were traced; a roughly 31 m mapped riverside path, the north and south approaches and a section along the west wall were walked in both directions. After reload the tile retained BlockAll and its material overrides; the stacks and visual facade actors retained NoCollision and their materials. The east end join and all routes have not been exhaustively reviewed, nor has performance been benchmarked. References: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1357620), [Battersea Power Station history](https://batterseapowerstation.co.uk/about/heritage-history/), and [Circus West architect's project history](https://www.simpsonhaugh.com/projects/battersea-power-station-phase-1). Geography © OpenStreetMap contributors, ODbL.

The `OSM Tile_m01_m03` actor now uses the separately saved `SM_BatterseaTile_f1767286244_f1767286248_f1767286250_f446509450_f446510222_f446510600_f446510956` mesh. It removes the three attributed apartment blocks and four original chimney meshes. Remaining face positions, winding, material sections, UVs, normals and extracted complex collision were checked against the original; the actor retained its material overrides and BlockAll profile. The original tile asset is unchanged. Future regeneration or reimport of the original will not update this fork: reconcile it or use the recorded `battersea_circus_correction` switch rollback before editing the tile; remove the stack actor separately if reverting.

### Former 20 Fenchurch Street
An original, schematic glazed tower with an overhanging crown and bracing now suggests the former 20 Fenchurch Street building, which stood until 2008. Its 91 m height and 25 floors follow published records; its 23 m square body, orientation and exact site position are estimates, not a surveyed footprint. The glass is opaque and the building has no modeled entrance or interior. A separate invisible 23 m square BlockAll volume provides basic building collision.

The sampled site was level, representative ground and elevated views were inspected, and two nearby street segments were walked in both directions before and after placement. After reload the visual actor retained NoCollision and its materials, and four wall traces hit the hidden BlockAll volume. These checks do not establish all routes, historic dimensions or performance. Sources: [Council on Tall Buildings and Urban Habitat](https://www.skyscrapercenter.com/london/20-fenchurch-street/33268/), [City of London planning report](https://democracy.cityoflondon.gov.uk/Data/Court%20of%20Common%20Council/20110609/Agenda/%2417b%20-%20Redevelopment%20of%2020%20Fenchurch%20Street%20%E2%80%93%20Potential%20Acquisition%20of%20Land%20for%20Planning%20Purposes.doc.pdf), and [2007 photograph](https://commons.wikimedia.org/wiki/File:20_Fenchurch_Street.JPG). Geography © OpenStreetMap contributors, ODbL.

### Lambeth Palace gatehouse
An original schematic treatment now suggests Morton's Tower with red brick, two raised battlemented towers, stone-framed windows and a closed pointed gate. The towers' proportions and the simple details are estimates; the historic dark diaper pattern and fine stonework are omitted. The existing solid building remains behind the NoCollision visual treatment, and the mapped private gateway is not opened.

The existing roof and wall planes were traced and the frontage was viewed in play. A sampled public footway was walked both ways before and after placement; the added actor retained NoCollision and its materials after reload. The tests do not cover every nearby route or roof detail. References: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1116399) and [a 2007 photograph](https://commons.wikimedia.org/wiki/File:Lambeth_Palace_gatehouse_-_geograph.org.uk_-_343864.jpg). Geography © OpenStreetMap contributors, ODbL.

### Kensington Palace garden facade
An original, schematic treatment adds brickwork, pale sash frames and a central pediment to several mapped east-facing wall sections. The material color, window rhythm, dimensions and pediment are estimates inspired by a 2007 view; the remaining sides and roof remain generic, the windows are opaque, and no interior is modeled. The shallow visual layer has NoCollision and the original solid walls remain. Some mapped footway geometry meets the facade in plan, and the junctions and other approaches are not fully reviewed.

The wall planes and roof support were checked, the facade was inspected from the gardens, and a nearby footway was walked both ways before and after placement. The actor retained NoCollision and its materials after a level reload. References: [Historic Royal Palaces](https://www.hrp.org.uk/kensington-palace/history-and-stories/the-story-of-kensington-palace/) and [a 2007 east-front photograph](https://commons.wikimedia.org/wiki/File:Kensington-Palace.jpg). Geography © OpenStreetMap contributors, ODbL.

### County Hall and the London Eye
The main County Hall block has been lowered from a generic 45 m extrusion to an estimated 30 m eave, and an approximate five-storey stone treatment and partial mansard have been added to its south, Westminster Bridge-facing frontage. The members' arch is decorative and closed because the original wall blocks the mapped service route. The other elevations and most of the roof remain generic; a separate 35 m source part remains above the lowered roof. A sampled bridge-side path was walked both ways before and after the change, and roof support and material/collision persistence were checked after reload. These are local checks, not a survey of the whole building. References: [Historic England](https://historicengland.org.uk/listing/the-list/list-entry/1358192) and [a 2009 photograph](https://commons.wikimedia.org/wiki/File:Former_County_Hall,_London_-_geograph.org.uk_-_1325703.jpg).

The erroneous solid extrusion of the London Eye outline and 304 mapped wheel/support parts that had been rendered as windowed blocks were removed, revealing the separate Codriver wheel model. Its frontal appearance was inspected in play; the two affected tile actors retained BlockAll and their materials after reload. Ground access and all nearby routes have not yet been exhaustively tested. The Eye opened in 2000, so it represents the later part of the requested period. [London Eye history](https://www.londoneye.com/about-us/history/). Source geography © OpenStreetMap contributors, ODbL.

The `OSM Tile_p01_m01` actor now uses `SM_EyeClean_Tile_p01_m01_parts_frame_parent`, a successor to the separately saved `SM_CountyHeightTile_county_eye` fork, and `OSM Tile_p01_p00` uses `SM_EyeClean_Tile_p01_p00_parts`. Their retained geometry attributes and extracted complex collision were checked against the expected results; both retained BlockAll and material overrides. The original tile assets remain untouched. Future regeneration or reimport will not update these forks. Reconcile the changes before editing; to revert, first use the corresponding `london_eye_successor` switch rollbacks, then the `county_hall_height_fork` rollback if desired. Remove the County Hall visual actor separately if reverting that treatment.

### Illustrative outdoor seating
Five small table-and-two-chair groups reuse an existing Poly Haven set near mapped eateries, including New Street Square. These are illustrative placements rather than evidence that those businesses had outdoor seating in the period. Ground support was sampled, each group was viewed in play, and all fifteen components retained NoCollision after reload; the furniture is decorative and players can walk through it. Asset: [Outdoor Table Chair Set 01, Poly Haven](https://polyhaven.com/a/outdoor_table_chair_set_01), CC0. Geography © OpenStreetMap contributors, ODbL.
