# Story markers in the mock Lanthorne

Generated from the mock build (`tools/mockcity_build.py`). Every row is one **Reflections Story Marker** actor in
that side's level. *Also answers to* lists the extra names on the same marker (actor Tags). Quests, NPC
lives and cutscenes look markers up by any of these names, so the real map needs the same names on the same
side. Positions are local to the side level, in metres (+X east, +Y north; see `plan.png`). Add the side's
level offset for world space: Pewterside 0, Giltside +1500 m X, Frostside +3000 m X.

Fastest swap: select a mock side level's markers, copy, paste into your side level, and move each one to
the real spot. In PIE, `Story.Markers` must then report no auto-placed names.

## Giltside (50 markers)

| Marker | Also answers to | Where (local m) | Yaw | What it is |
|---|---|---|---|---|
| `Mk_Gilt_Camp_UnderGate` | `Home_kit_marrow`, `Home_fen_lowry`, `Spot_DrifterCamp` | 131.0, 12.0, 0.0 | 0 | The drifters' camp under the Lantern Gate (clique drifters_camp). |
| `Mk_Gilt_Cellar_Lamplight` | `Home_hal_fairweather`, `Spot_LamplightCellar` | -28.0, -0.5, 0.0 | 90 | The inn's cellar, where Hal is hidden (SQ1). |
| `Mk_Gilt_Gate_LanternGate` | `Mk_Gilt_Gate`, `Spot_LanternGate` | 140.0, 35.0, 0.0 | 180 | The Lantern Gate and its bridge (clique lantern_gate). |
| `Mk_Gilt_Home_Barracks` | `Home_sela_brask`, `Spot_GiltBarracks` | -123.5, -67.0, 0.0 | 90 | Named place used by people markers |
| `Mk_Gilt_Home_IlseAttic` | `Home_ilse_varrow` | 70.1, 31.3, 0.0 | 90 | Named place used by people markers |
| `Mk_Gilt_Home_ThraleShop` | `Home_barnaby_thrale`, `Home_ros_thrale` | 80.1, 38.7, 0.0 | 270 | Named place used by people markers |
| `Mk_Gilt_Home_WatchBarracks` | `Home_nell_bramley`, `Spot_WatchBarracks` | 123.5, -67.0, 0.0 | 90 | Named place used by people markers |
| `Mk_Gilt_Inn_Lamplight` | `Home_goldie_fairweather`, `Mk_Gilt_Inn`, `Haunt_Tavern`, `Spot_Lamplight` | -37.0, 15.2, 0.0 | 180 | The Lamplight inn; Wren lodges upstairs (clique lamplight). |
| `Mk_Gilt_Lane_BellLane` | `Spot_BellLane` | -40.0, 10.0, 0.0 | 90 | Bell Lane, where the lamps are failing (clique bell_lane, SQ7). |
| `Mk_Gilt_Market_LanternRow` | `Mk_Gilt_Market`, `Haunt_Market`, `Spot_LanternRow` | 70.0, 35.0, 0.0 | 180 | Lantern Row, the candle-and-glass market (clique lantern_row). |
| `Mk_Gilt_Rift_Canal` | `Spot_CanalRift` | 125.0, -11.0, 0.0 | 270 | The canal rift post (SQ6). |
| `Mk_Gilt_Square_BellSquare` | `Mk_Gilt_Square`, `Haunt_Square`, `Spot_BellSquare` | -65.0, 7.0, 0.0 | 90 | Giltside's central square with the dry fountain. Intro and first-conversion spot. |
| `Mk_Gilt_Steps_Archive` | `Spot_ArchiveSteps` | -43.0, 72.5, 0.0 | 180 | The Archive steps (clique archive_steps). |
| `Mk_Gilt_Tower_GiltTower` | `Tower_Giltside` | 0.0, 60.5, 0.0 | 90 | The Gilt Tower's sealed door. |
| `Mk_Gilt_Workshop_Furnace` | `Mk_Gilt_Workshop`, `Spot_Furnace` | 60.0, 29.0, 0.0 | 90 | Dov's glass furnace. |
| `Mk_Gilt_Workshop_ThraleShop` | `Spot_ThraleShop` | 75.0, 29.0, 0.0 | 90 | Barnaby's tailoring shop. |
| `Mk_Gilt_Workshop_Vane` | `Spot_VaneAtelier` | 62.0, 41.5, 0.0 | 270 | Named place used by people markers |
| `Mk_Gilt_Yard_Muster` | `Spot_MusterYard` | 123.5, 70.0, 0.0 | 270 | The Lamp Companies' muster yard (clique muster_yard). |
| `Spot_BellLaneLamp1` | `Mk_Gilt_Lane_BellLane_Lamp1` | -37.6, 4.0, 0.0 | 0 | Failing lamp 1 on Bell Lane; fire spell within 3 m; space about 8 m apart along the lane |
| `Spot_BellLaneLamp2` | `Mk_Gilt_Lane_BellLane_Lamp2` | -37.6, 12.0, 0.0 | 0 | Failing lamp 2 on Bell Lane; fire spell within 3 m; space about 8 m apart along the lane |
| `Spot_BellLaneLamp3` | `Mk_Gilt_Lane_BellLane_Lamp3` | -37.6, 20.0, 0.0 | 0 | Failing lamp 3 on Bell Lane; fire spell within 3 m; space about 8 m apart along the lane |
| `Item_Fiddle` |  | -60.0, 16.0, 0.0 | 0 | Jory's fiddle lies in Bell Square (SQ2); two tarnished stand near it |
| `CutsceneAnchor_BurningEyes` |  | -71.0, 8.0, 0.0 | 45 | Bell Square, about 6 m from where Jory stands, facing the dry fountain; CS02 Jory is tackled and turned |
| `CutsceneAnchor_GiltTower` |  | 0.0, 61.5, 0.0 | 90 | Threshold of the sealed Gilt Tower door, facing in; CS04 with Pim |
| `CutsceneAnchor_Intro` |  | -38.0, 11.0, 0.0 | 57 | Wren start, outside the Lamplight inn, facing the skyline; CS01 intro, Jory and Goldie nearby |
| `QuestGiver_barnaby_thrale` |  | 75.8, 31.4, 0.0 | 90 | Where Barnaby Thrale waits for the hero |
| `QuestGiver_corin_ashby` |  | -41.0, 12.3, 0.0 | 90 | Where Corin Ashby waits for the hero |
| `QuestGiver_dov_merriman` |  | 62.1, 30.3, 0.0 | 90 | Where Dov Merriman waits for the hero |
| `QuestGiver_goldie_fairweather` |  | -38.8, 16.9, 0.0 | 180 | Where Marigold "Goldie" Fairweather waits for the hero |
| `QuestGiver_ilse_varrow` |  | 72.5, 35.0, 0.0 | 180 | Where Ilse Varrow waits for the hero |
| `QuestGiver_jory_pell` |  | -39.9, 14.4, 0.0 | 180 | Where Jory Pell waits for the hero |
| `QuestGiver_kit_marrow` |  | 133.1, 10.7, 0.0 | 0 | Where Kit Marrow waits for the hero |
| `QuestGiver_lucan_marlowe` |  | -63.9, 4.7, 0.0 | 90 | Where Lucan Marlowe waits for the hero |
| `QuestGiver_nell_bramley` |  | 141.5, 37.0, 0.0 | 180 | Where Nell Bramley waits for the hero |
| `QuestGiver_odette_vane` |  | 62.2, 38.5, 0.0 | 270 | Where Odette Vane waits for the hero |
| `QuestGiver_ros_thrale` |  | 124.4, -8.6, 0.0 | 270 | Where Ros Thrale waits for the hero |
| `QuestGiver_sela_brask` |  | 122.3, 67.8, 0.0 | 270 | Where Captain Sela Brask waits for the hero |
| `QuestGiver_tobias_quell` |  | -42.4, 70.1, 0.0 | 180 | Where Professor Tobias Quell waits for the hero |
| `Home_amos_saffery` |  | 64.8, 38.7, 0.0 | 270 | Home of Amos Saffery (spice trader) |
| `Home_corin_ashby` |  | 10.0, 31.3, 0.0 | 90 | Home of Corin Ashby (lantern maker) |
| `Home_dov_merriman` | `Mk_Gilt_Home` | 52.7, 31.3, 0.0 | 90 | Home of Dov Merriman (glassblower) |
| `Home_hollis_greave` |  | 111.9, -10.3, 0.0 | 270 | Home of Hollis Greave (bridge guard of the Lantern Watch) |
| `Home_jory_pell` |  | 2.2, -10.3, 0.0 | 270 | Home of Jory Pell (fiddler) |
| `Home_lucan_marlowe` |  | -108.9, -10.3, 0.0 | 270 | Home of Lucan Marlowe (dancer) |
| `Home_maud_kettering` |  | 87.4, 31.3, 0.0 | 90 | Home of Sergeant Maud Kettering (sergeant of the Lantern Watch at the Lantern Gate) |
| `Home_odette_vane` |  | 50.6, 38.7, 0.0 | 270 | Home of Odette Vane (couturier) |
| `Home_pim_ashgrove` |  | 28.1, 31.3, 0.0 | 90 | Home of Pim Ashgrove (bell-ringer's apprentice) |
| `Home_tobias_quell` |  | -51.3, 108.7, 0.0 | 270 | Home of Professor Tobias Quell (scholar of the Glazier) |
| `Home_tobin_lark` |  | 18.9, -10.3, 0.0 | 270 | Home of Tobin Lark (candle seller on Bell Lane) |
| `Haunt_Bridge` |  | 165.0, 35.0, 0.0 | 180 | Fallback haunt for the old stub book; not used by the real people.json |

## Pewterside (22 markers)

| Marker | Also answers to | Where (local m) | Yaw | What it is |
|---|---|---|---|---|
| `Mk_Pew_Doorstep_Hester` | `Home_hester_quaile`, `Home_sid_kettle`, `Spot_HesterDoorstep` | 18.0, -57.0, 0.0 | 90 | Hester's doorstep on Coal Lane (SQ4). |
| `Mk_Pew_Home_Ada` | `Home_ada_pollard` | 67.3, -10.3, 0.0 | 270 | Named place used by people markers |
| `Mk_Pew_Home_PrattShop` | `Home_horace_pratt` | -108.9, -10.3, 0.0 | 270 | Named place used by people markers |
| `Mk_Pew_Infirmary_WickStreet` | `Mk_Pew_Infirmary`, `Spot_WickStreetInfirmary` | -70.0, -62.5, 0.0 | 270 | The Wick Street infirmary. |
| `Mk_Pew_Laundry_CoalLane` | `Mk_Pew_Laundry`, `Spot_CoalLaneLaundry` | 75.0, -57.0, 0.0 | 90 | The Coal Lane steam laundry. |
| `Mk_Pew_Square_WeighHouse` | `Mk_Pew_Square`, `Spot_WeighHouseCorner` | -77.0, 10.0, 0.0 | 45 | Weigh-House Corner (clique weigh_house_corner). |
| `Mk_Pew_Stair_WeighHouse` | `Tower_Pewterside` | -97.5, -9.5, 0.0 | 90 | Foot of the Old Weigh-House stair up to the first page. |
| `Mk_Pew_Steps_FishSteps` | `Mk_Pew_Market`, `Spot_FishSteps` | 67.5, -27.5, 0.0 | 90 | The Fish Steps market by the river (clique fish_steps). |
| `Mk_Pew_Stop_CoalLane` | `Mk_Pew_Stop`, `Spot_CoalLaneStop` | 60.0, -57.5, 0.0 | 270 | The Coal Lane tram stop (clique coal_lane_stop). |
| `CutsceneAnchor_FirstPage` |  | -89.0, -1.5, 10.0 | 0 | Optional; plays where the first page was picked up (usually Weigh-House roof, Pewterside); CS03 |
| `QuestGiver_ada_pollard` |  | 65.1, -28.1, 0.0 | 90 | Where Ada Pollard waits for the hero |
| `QuestGiver_edie_bramley` |  | 62.5, -57.5, 0.0 | 270 | Where Edie Bramley waits for the hero |
| `QuestGiver_hester_quaile` |  | 15.5, -57.2, 0.0 | 90 | Where Hester Quaile, "the Queen of Coal Lane" waits for the hero |
| `QuestGiver_walter_dunmore` |  | 60.2, -60.0, 0.0 | 270 | Where Walter Dunmore waits for the hero |
| `Home_agnes_moth` |  | -73.2, -63.7, 0.0 | 90 | Home of Agnes Moth (night nurse at the Wick Street infirmary) |
| `Home_bet_crawley` |  | 51.2, -10.3, 0.0 | 270 | Home of Bet Crawley (fishmonger on the Fish Steps) |
| `Home_edie_bramley` | `Mk_Pew_Home` | 66.9, -56.3, 0.0 | 270 | Home of Edie Bramley (tram conductor on the Coal Lane line) |
| `Home_frank_dunning` |  | -119.7, 38.7, 0.0 | 270 | Home of Frank Dunning (newspaper seller) |
| `Home_ivy_harker` |  | -114.0, 31.3, 0.0 | 90 | Home of Constable Ivy Harker (watch constable posted at the Old Weigh-House) |
| `Home_ned_lusk` |  | 52.7, -63.7, 0.0 | 90 | Home of Ned Lusk (seamstress) |
| `Home_walter_dunmore` |  | 51.0, -56.3, 0.0 | 270 | Home of Walter Dunmore (pensioner) |
| `Home_winnie_cobb` |  | -121.8, -10.3, 0.0 | 270 | Home of Winnie Cobb (keeps the tea stall at Weigh-House Corner) |

## Frostside (17 markers)

| Marker | Also answers to | Where (local m) | Yaw | What it is |
|---|---|---|---|---|
| `Mk_Frost_Cistern` | `Mk_Frost_Square`, `Spot_Cistern` | -65.0, 9.5, 0.0 | 90 | Named place used by people markers |
| `Mk_Frost_Gate_FrozenGate` | `Mk_Frost_Gate`, `Spot_FrozenGate` | 140.0, 35.0, 0.0 | 180 | The gate that won't close. |
| `Mk_Frost_Home_Barracks` | `Home_brenna_cold`, `Home_eskil_varn` | 9.3, 143.3, 0.0 | 90 | Named place used by people markers |
| `Mk_Frost_Home_Rook` | `Home_mother_rook`, `Home_tilly_frane` | -51.3, 108.7, 0.0 | 270 | Named place used by people markers |
| `Mk_Frost_Market_BoneMarket` | `Mk_Frost_Market`, `Spot_BoneMarket` | 70.0, 35.0, 0.0 | 180 | The Bone Market (clique bone_market). |
| `Mk_Frost_Shed_Sorrel` | `Home_sorrel_vey`, `Home_petra_lisle`, `Mk_Frost_Workshop`, `Spot_SorrelShed` | 86.5, 3.0, 0.0 | 270 | Sorrel's shed (SQ8). |
| `Mk_Frost_Shelter_LongShelter` | `Home_marta_quarry`, `Mk_Frost_Inn`, `Spot_LongShelter` | -37.0, 15.2, 0.0 | 180 | The Long Shelter (clique long_shelter). |
| `Mk_Frost_Stair_IceStairs` | `Spot_IceStairs` | -43.0, 72.5, 0.0 | 180 | The Ice Stairs (clique ice_stairs). |
| `Mk_Frost_Tower_FrostTower` | `Tower_Frostside` | 0.0, 70.0, 0.0 | 90 | Inside the sealed Frost Tower (the Gilt Tower's reflection). |
| `Mk_Frost_Wall_IceWall` | `Spot_IceWall` | 0.0, 140.0, 0.0 | 90 | The ice wall. |
| `CutsceneAnchor_Ending` |  | 13.0, 70.0, 24.0 | 270 | Optional; villain arena centre atop the Frost Tower, facing out over the city; CS06 |
| `CutsceneAnchor_MirrorWhole` |  | 1.0, 71.0, 0.0 | 90 | Optional; inside the Frost Tower at the third page spot, facing up toward the arena; CS05 |
| `QuestGiver_petra_lisle` |  | 84.7, 4.7, 0.0 | 270 | Where Petra Lisle waits for the hero |
| `QuestGiver_sorrel_vey` |  | 72.5, 35.0, 0.0 | 180 | Where Sorrel Vey waits for the hero |
| `Home_dagny_thorn` |  | 87.4, 31.3, 0.0 | 90 | Home of Dagny Thorn (guard at the gate that won't close) |
| `Home_greta_holm` |  | 70.1, 31.3, 0.0 | 90 | Home of Greta Holm (bone carver at the Bone Market) |
| `Home_gunnar_skarre` | `Mk_Frost_Home` | -29.0, 108.7, 0.0 | 270 | Home of Gunnar Skarre (ice-cutter on the Ice Stairs) |

## Not story markers

- `VillainArena` is a **Reflections Villain Arena** actor (Frostside, on the Frost Tower crown, arena radius 11.5 m).
  Without one, the villain falls back to `Tower_Frostside`.
- Optional generic fallbacks (`Mk_<Side>_<Kind>`, `Haunt_Square/Market/Tavern/Bridge`) ride as tags on the
  named places above where one fits. The rest fall back to a navmesh point near the side anchor.
- Test-quest names (`Item_TestLedger`, `Spot_TestBrazier`) are not placed.
