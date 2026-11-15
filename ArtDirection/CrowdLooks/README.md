# Crowd looks: who the player sees in Lanthorne

Owner: the crowd-looks session (appearance only; behaviour is the NPC, crowd and squad sessions'). Tools: `Tools/CrowdLooks/`.

## Before (audit, PIE on `Lvl_HeroSampleCrowd`, 14 Nov 13:10–13:20)

| Image | What it shows |
|---|---|
| `before/before_play_view.png` | The opening view on Play. The pale, bald figures are the Mass city crowd. |
| `before/before_mass_closeup.png` | Mass pedestrians up close (first panel): white untextured head, no hair, brows or lashes, grey rag garments floating off the body. |
| `before/before_spawn_pools.png` | The ten looks the spawn pools use, with the verdict for each. |
| `before/before_wardrobe_variants.png` | The six Red MetaHumans, Iven Rook and the 36 `BP_Crowd_*` palette variants (six faces × six palettes). |

Verdicts:

| Source | Spawned by | Problem |
|---|---|---|
| `COL_CrowdPrototype_CoinClerk` × 40 | Crowd session's Mass city level (`/Game/Crowd/City`) | White or untextured head, missing hair/brows/lashes, baggy and misaligned garments, one face 40 times |
| SimpleRed CoinClerk / ArchiveApprentice / FestivalDrummer / BridgeGuard | Placed in the map; NPC archetypes Civilian/Guard; `TeamLooks()`; crowd promotion | All four wear one shared maroon tunic ("all copied"). Archive: no brows. Drummer: broken flat-strip hair, no brows. No lashes on any. |
| WhiteLook_01–04 | Placed in the map; Civilian pool; squads' casters | One face (Iven Rook) four times; the rag mantle on 03/04 doesn't render |
| WhiteLook_05–06 | Squads' melee soldiers; placed in the map | The Bridge Guard's face, the same face as the Red guard |
| Base `BP_<Name>` and `BP_Crowd_01..36` | Not in any pool | Finished outfits. FerryPilot and GlassArtisan couldn't walk (no `ABP_Crowd_*`). 4 of 7 had no brows, and none had lashes. |

Distinct faces across every spawn pool: **5**.

## After (14 Nov, 18:25–18:40)

| Image | What it shows |
|---|---|
| `after/after_cast_lineup.png` | All 20 looks in PIE: face close-up and full body, each labelled with sex, age, side and role. Same camera setup as `before_spawn_pools.png`. |
| `after/after_giltside_walking.png` | The 12 Giltside looks enrolled as real NPCs, walking on the hidden GASP pawns (backlit, in motion). |
| `after/after_play_view.png` | The opening view on Play (see "What Play shows" below). |

**20 people, 20 distinct faces:** 12 Giltside and 8 Frostside; 10 women and 10 men; 5 Young, 10 Adult and 5 Old. Every face has brows, lashes and hair (or a deliberate shaved head: FrostTobias, FrostNia, and the Ferry Pilot under his hat). Everyone wears a fitted outfit from the existing wardrobe. An outfit used twice gets a different palette (`/Game/Characters/RedLondon/Crowd/Materials/MI_Crowd_*`) or White London variant, so no outfit repeats with the same colours.

| Look | Side | Sex | Age | Role | Face | Outfit copied from |
|---|---|---|---|---|---|---|
| `BP_Look_GiltArchivist` | Giltside | M | Young | Civilian | Existing ArchiveApprentice face, re-groomed | `BP_Crowd_03` |
| `BP_Look_GiltBarnaby` | Giltside | M | Old | Civilian | New: MetaHuman preset "Walter" | `BP_Crowd_06` |
| `BP_Look_GiltBridgeGuard` | Giltside | F | Adult | Guard | Existing BridgeGuard face, re-groomed | `BP_Crowd_07` |
| `BP_Look_GiltRowena` | Giltside | F | Adult | Guard | New: MetaHuman preset "Vivian" | `BP_Crowd_11` |
| `BP_Look_GiltCoinClerk` | Giltside | F | Adult | Civilian | Existing CoinClerk face, re-groomed | `BP_Crowd_16` |
| `BP_Look_GiltMaren` | Giltside | F | Old | Civilian | New: MetaHuman preset "Grace" | `BP_Crowd_18` |
| `BP_Look_GiltFerryman` | Giltside | M | Adult | Civilian | Existing FerryPilot face, re-groomed | `BP_Crowd_22` |
| `BP_Look_GiltRamon` | Giltside | M | Adult | Civilian | New: MetaHuman preset "Jorge" | `BP_Crowd_21` |
| `BP_Look_GiltDrummer` | Giltside | F | Young | Civilian | Existing FestivalDrummer face, new cornrows | `BP_Crowd_28` |
| `BP_Look_GiltPriya` | Giltside | F | Young | Civilian | New: MetaHuman preset "Sunita" | `BP_Crowd_30` |
| `BP_Look_GiltGlassman` | Giltside | M | Adult | Civilian | Existing GlassArtisan face, re-groomed | `BP_Crowd_34` |
| `BP_Look_GiltHaruto` | Giltside | M | Young | Civilian | New: MetaHuman preset "Kelvin" | `BP_Crowd_33` |
| `BP_Look_FrostIven` | Frostside | M | Young | Soldier | Existing IvenRook face | `BP_WhiteLook_01_Plain` |
| `BP_Look_FrostSilas` | Frostside | M | Old | Civilian | New: MetaHuman preset "Lorenzo" (cap removed) | `BP_WhiteLook_02_Cap` |
| `BP_Look_FrostTobias` | Frostside | M | Adult | Caster | New: MetaHuman preset "Isaiah" | `BP_WhiteLook_03_Mantle` |
| `BP_Look_FrostWen` | Frostside | M | Adult | Caster | New: MetaHuman preset "Bo" | `BP_WhiteLook_04_CapMantle` |
| `BP_Look_FrostHyeon` | Frostside | F | Old | Civilian | New: MetaHuman preset "Sook-ja", silver ponytail | `BP_WhiteLook_05_GuardRags` |
| `BP_Look_FrostSaran` | Frostside | F | Adult | Soldier | New: MetaHuman preset "Tuya" | `BP_WhiteLook_06_GuardBoldRunes` |
| `BP_Look_FrostNia` | Frostside | F | Young | Soldier | New: MetaHuman preset "Zuri" | `BP_WhiteLook_05_GuardRags` |
| `BP_Look_FrostAmara` | Frostside | F | Adult | Soldier | New: MetaHuman preset "Asha" | `BP_WhiteLook_06_GuardBoldRunes` |

The machine-readable version is `Tools/CrowdLooks/cast.json`. The faces are Epic's MetaHuman Creator presets from the engine's MetaHuman plugin, covered by the MetaHuman licence for Unreal Engine projects. The in-world names are ours, not Epic's preset names.

## Pewterside (14 Nov, 19:50)

The user's rule: rags only in Frostside, red only in Giltside, grey in Pewterside, never mixed. `Tools/CrowdLooks/make_pewter.py` made 12 Pewterside looks, `/Game/Characters/Lanthorne/Looks/Pewterside/PewLook_<X>`, one per Giltside look. Each is a material-only change: the outfit's tinted fabric gets `MI_Crowd_<Char>_Pewter` (slate grey, `CrowdTint` 0.30/0.32/0.35, a child of the outfit's own `M_CrowdTint_<Char>`). They keep the same faces as their Giltside twins (the city is mirrored, and SpawnNpc never mixes sides). Tags are `Look_Side_Pewterside` and `Look_Id_Pew<X>`, plus the twin's sex, age and role: 10 civilians and 2 guards. No Pewterside soldiers or casters yet. Not yet checked in PIE for leftover red trims (sash, shield).

## Armour-free soldiers (14 Nov, 20:04)

The user: "Remove the armor from the soldiers." `Tools/CrowdLooks/make_soldiers.py` made `/Game/Characters/Lanthorne/Looks/Soldiers/`:
- GiltSoldier_BridgeGuard and GiltSoldier_Rowena: the Giltside guard outfit without `BridgeGuard_Armor` (plates/bracers). They keep the red gambeson, trousers, boots, sash and the carried shield.
- FrostSoldier_Iven, _Saran, _Nia, _Amara: the Frostside soldier looks (cloth only), with the leftover hidden armour part stripped.

All are tagged `Look_Role_Soldier`; the source looks are unchanged. They replace the soldier pool entries. That swap is npc-unify's and squads', handed over in the shared notes.

## Licence check (commercial-readiness.md)

- **No Hunyuan3D-2 garments in any look.** The Hunyuan pieces are the SimpleRed tunic, trousers and boots (`CrowdMotion/SimpleRed`) and the hero's generated boots and shirt folds. No `BP_Look_*` uses them, and the six SimpleRed actors placed in `Lvl_HeroSampleCrowd` were replaced.
- Garments used: the team's Red London wardrobe (`RedLondon/<Name>/Outfit|Wardrobe|Clothing`, with `RedLondon/Crowd/Materials` tints) and the White London garments (`WhiteLondon/IvenRook/MetaHuman/Clothing`, `WhiteLondon/CrowdPreview/Clothing`), as listed in `ArtDirection/Clothing-Fit-Audit`.
- Faces, skin, eyes and grooms come from Epic's MetaHuman Creator (presets, wardrobe grooms and cloud texture sources), under the MetaHuman licence for Unreal Engine projects.
- Codex-generated, Blender-fitted garments will replace the baggy rags and mantles as they land (the hero-cloak session fits them).

## How a look is built (one source of truth)

- **Tags on the Blueprint** carry everything other systems need: `NPC_Voice_F|M`, `Look_Age_Young|Adult|Old`, `Look_Side_Giltside|Frostside`, `Look_Role_Civilian|Guard|Soldier|Caster`, `Look_Id_<Id>`. The NPC system's `GetLookSex` and side-aware `GetLooksAt` read them, and so do the voice roster and lives.
- **Pools:** the NPC archetype data assets (`/Game/NPC/Archetypes/DA_Npc_*`, owned by npc-unify) hold the look lists. `SpawnNpc`, the crowd's ring walkers and promoted pedestrians, and (from the next squads train) the soldier squads all read them. `Tools/CrowdLooks/apply_look_list.py` writes the lists from `cast.json`.
- **New person** (`Tools/CrowdLooks/person_sync.py`): duplicate an Epic preset → copy the donor body's parametric constraints → cloud auto-rig (joints only: no blendshapes, a lighter face) → cloud texture sources → Optimized/Medium build into `/Game/Characters/Lanthorne/People/<Id>/Built`, sharing `People/Common` → `make_look.py` copies the donor's fitted wardrobe Blueprint. It swaps in the new face and grooms, keeps the donor body mesh (so the garments fit and the walk ABP resolves) and puts the new skin material on it.
- **Existing faces** (`fix_existing.py`): the same wardrobe Blueprint, plus brows/hair taken from a built person's groom (card LODs) with a new binding to that face.
- **Finishing:** `fix_extras.py` (Silas's cap, Hyeon's hair), `perf_pass.py` (empty groom components removed, garments `OnlyTickPoseWhenRendered`), groom tick group `PostUpdateWork` (the hero hair-lag fix, `ArtDirection/Clothing-Fit-Audit/HeroHair-Detach-Fix.md`), `cap_textures.py` (body maps 1024, eyes and teeth 512).
- **Walking:** `ABP_Crowd_FerryPilot` and `ABP_Crowd_GlassArtisan` (copies of the Archive one) were added, so those bodies walk too.

## Root causes fixed on the way

- **Missing Common files = bald "helmet" hair.** A MetaHuman build copies each groom's textures and card meshes into its Common folder; unsaved, they vanish on the next editor restart. That is what broke the original FestivalDrummer hair: 5 files missing in `RedLondon/BridgeGuard/Assembled/Common`, also the Ferry Pilot's moustache. `repair_common.py` restores them from the plugin. Builds now save Common.
- **Raw plugin grooms render as a painted helmet in this project** (their LOD0 is strands). Only grooms that come out of a MetaHuman build (card LODs) are used.
- **The Mass prototype collection** (`COL_CrowdPrototype_CoinClerk`, white heads, no grooms, floating rags) is off by default since train #6, and Mass is a no-go for the jam (decided with crowd). A smaller crowd of finished actor walkers with the crowd LOD subsystem replaces it.

## Cost

- Uncooked: about 1.4 GB for the 13 new people plus 435 MB of shared Common. The cooked size is being measured by packaging (NPC budget 320 MB). The old pools (`CrowdMotion/SimpleRed`, `WhiteLondon/CrowdPreview`, `RedLondon/Crowd/Variants`) drop out of the cook once the last references are switched.
- Frame time: same component count per look as before, minus 2–5 empty grooms each; garments no longer tick their pose off screen.

## Known gaps

- New faces have joints-only rigs: no facial blendshapes, so no lip-sync (barks play from the head bone as before).
- The White London rag mantle (WhiteLook_03/04) still doesn't render. The casters read as tunic and rags.
- Groom strand data may still be cooked; if packaging measures it as the main cost, switch those grooms to cards-only.

## What Play shows (train #11 editor, 19:05)

- The six placed walkers in `Lvl_HeroSampleCrowd` were swapped from SimpleRed/WhiteLook to GiltHaruto, GiltBridgeGuard, GiltRowena, GiltArchivist, GiltMaren and GiltPriya, and the map saved (with the orchestrator's OK). The map has no world anchors, so it counts as Pewterside and gets Giltside looks only.
- `after/after_play_view.png`: the opening view on Play. No white-headed Mass clones, no shared maroon tunic.
- `after/after_play_crowd_closeups.png`: each walker in that same Play session, at close range, walking.
- Spawned NPCs (SpawnNpc, the crowd's ring walkers and promoted pedestrians, squads from their next train, lives' named people) draw from the archetype look lists. Train #11 makes SpawnNpc pick looks by the side of the spawn point.

## Open items (owners)

- **lives:** stop giving several named people the same look (seen: 3× GiltFerryman, 2 standing 50 cm apart). Asked to hand out unused looks first and match on the tags.
- **squads:** read Soldier/SoldierCaster looks from the archetypes (`ReflectionsSquad.cpp:97-102` still hard-codes WhiteLook_03..06).
- **npc-unify:** add the Frostside looks to the pools (Silas and Hyeon as civilians; Nia and Saran as soldiers; Tobias and Wen as casters); put the look lists in code, so "Reset To Built In" can't bring back SimpleRed.
- **packaging:** measure the cooked size of `/Game/Characters/Lanthorne` against the 320 MB NPC budget. `/Game/Crowd/City` is always-cooked and still pulls in the Mass prototype collection.
- **crowd-looks (next queue row):** swap in the Codex/Blender-fitted garments from hero-cloak as they land; add 2 male Giltside soldier faces on the ArchiveApprentice body; Pewterside grey-palette looks (12 named Pewterside people have none); perf's LODSync minimum LOD 1, once close-ups at LOD1 are checked.
- Not mine, seen in passing: in the train #11 editor the hero shows white mannequin limbs through the coat (`after_play_view.png`).
