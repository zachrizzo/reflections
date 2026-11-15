# RedLondon untangle: re-point plan (plan only, no asset changes)

Packaging, Sun 15 Nov ~02:00. Asked by the orchestrator: which assets to move off `/Game/Characters/RedLondon` and onto what, after train #15, in coordinated rows.

**Bottom line: the player-invisible saving is about 66 MB, not 206 MB.** The other ~140 MB is the six donor MetaHuman builds (`RedLondon/<Body>/Assembled`), which every Lanthorne look is built on. crowd-looks already said these can't leave without rebuilding every body, and the cook data agrees.

## How this was measured

- **Source:** tonight's measurement build (Sun 01:10). I listed its IoStore container (`UnrealPak -ListContainer`) and took every cooked `/Game` package's compressed size. Then I read the name tables of their source `.uasset` files, giving 12,380 packages and their references.
- **Roots:** what the config always cooks (the map, the always-cook folders, `[AlwaysCookMaps]`, everything outside `/Game/Characters`). From those, every cooked RedLondon package (744, 206.2 MB) is explained. Nothing was left unexplained.
- **Editor-only references** were left out: anim assets pointing at a preview skeletal mesh.
- **Limit:** name tables over-count references, so these savings are lower bounds.
- Scripts: `redlondon_graph.py`, `rl_query*.py` and `common_dupes.py` in the packaging session's scratchpad. They can be re-run on the next build's pak listing.

## Where the 206 MB is

| What | MB | Packages | Needed by |
|---|---|---|---|
| Donor bodies (`<Body>/Assembled/<Body>/Body`), all six | 54.6 | 48 | Every Lanthorne look on that body |
| Donor faces (`<Body>/Assembled/<Body>/Face`) | 60.2 | 156 | The looks that reuse a donor face (see "Visible" below) |
| `BridgeGuard/Assembled/Common` (the shared `metahuman_base_skel` and the MetaHuman Common set) | 40.3 | ~140 | Five of the six donors, all Lanthorne looks on them, the crowd ABPs and the melee and march clips |
| `CoinClerk/Assembled/Common` (a second copy of the MetaHuman Common set, with its own skeleton) | 34.6 | 152 | The CoinClerk body and the looks on it, and the CoinClerk melee clips |
| Donor grooms (`<Body>/Assembled/<Body>/Grooms`) | ~6 | ~60 | The groom bindings in `Lanthorne/Grooms` |
| `Wardrobe` / `Outfit` / `Clothing` / `Crowd/Materials` | 10.2 | ~110 | Some Lanthorne looks (crowd-looks' list) |

## Re-point list

1. **`CrowdMotion/ABP_Crowd_*` (19 that touch RedLondon), the 20 `Combat/Melee/AS_Melee_*_BridgeGuard`/`_CoinClerk` clips and `Squads/Animation/AS_Soldier_March_BridgeGuard`: leave them. Saving: 0 MB.**
   - Their only RedLondon references are the skeleton they animate (`.../Assembled/Common/Female/Medium/NormalWeight/Body/metahuman_base_skel`, needed by every MetaHuman) and an editor-only preview body mesh.
   - Changing the preview mesh saves nothing.
   - Don't move or re-save `metahuman_base_skel`. Saving it dirty at 19:28 dropped `root` and T-posed half the cast.
2. **Lanthorne looks onto Lanthorne clothing and materials: −10.2 MB, low risk, crowd-looks.** Re-point the looks that still use donor wardrobes onto `Lanthorne/Clothing`, or copy the few garments and CrowdTint MIs they use into `Lanthorne/`:
   - `BridgeGuard/Wardrobe`: FrostAmara, FrostHyeon, FrostNia, FrostSaran, GiltBridgeGuard, GiltRowena, PewLook_BridgeGuard, PewLook_Rowena, and the BridgeGuard-body soldiers if any still use it.
   - `FestivalDrummer/Wardrobe`: PewLook_Drummer, PewLook_Priya.
   - `ArchiveApprentice/Outfit`: GiltArchivist, GiltBarnaby, PewLook_Archivist, PewLook_Barnaby.
   - `CoinClerk/Outfit`: GiltCoinClerk, GiltMaren, PewLook_CoinClerk, PewLook_Maren.
   - `GlassArtisan/Outfit`: GiltGlassman, GiltHaruto, PewLook_Glassman, PewLook_Haruto.
   - `FerryPilot/Clothing`: PewLook_Ferryman, PewLook_Ramon.
   - `RedLondon/Crowd/Materials` (CrowdTint MIs): about 20 looks.

   The list is crowd-looks' (`crowd-looks.md`, 01:20). With all of these re-pointed, the cook drops 10.2 MB: `FerryPilot/Clothing` 4.4, `CoinClerk/Outfit` 2.3, `FestivalDrummer/Wardrobe` 1.4, `BridgeGuard/Wardrobe` 1.1, plus the rest.
3. **Deduplicate the MetaHuman Common copies: about −56 MB, invisible if done right, medium risk.** Do it as one coordinated row: crowd-looks for the looks, and IvenRook's owner (hero-cloak / squads).
   - **What:** the duplicates are **byte-identical** cooked chunks, matched by hash in the pak:

     | Copy | Identical to `BridgeGuard/Assembled/Common` |
     |---|---|
     | `CoinClerk/Assembled/Common` | 18.2 MB |
     | `WhiteLondon/IvenRook/MetaHuman/Assembled/Common` | 18.1 MB |
     | `Lanthorne/People/Common` | 19.4 MB |

     In each copy, 17.1 MB of it is `Lookdev_UHM`: the MetaHuman unified eye, teeth and skin master materials, material functions and textures. The face and body MIs use these at runtime, so they can't simply be dropped, but one copy is enough.
   - **How:**
     - In the editor, run **Replace References** (consolidate) from each duplicate's identical `Lookdev_UHM`, `Textures` and `Optional` assets onto the BridgeGuard Common asset at the same path.
     - Only take assets whose cooked chunk hash matches. The list can be generated from the pak listing.
     - Then delete the emptied duplicates, or leave them unreferenced, and they drop out of the cook.
   - **Don't touch:**
     - either `metahuman_base_skel` (CoinClerk has its own);
     - the physics assets;
     - `ABP_*PostProcess`;
     - the face rigs, DNA and control rigs;
     - anything whose hash differs (Lanthorne's Common is a newer MetaHuman build: only 19.6 of its 57.2 MB of bulk data matches).
   - **Risks:** it re-saves every face and body MI that points at a duplicate (hundreds of packages), and recompiles their materials, though the shader bytecode is already shared. Do it:
     - with more than 8 GB of free virtual memory;
     - under a save freeze;
     - with backups of `Common` and the looks;
     - then a PIE check of each look, one at a time, as crowd-looks did at 01:50.
   - **Payoff:** about 56 MB.
4. **Optional, needs a code change: `CrowdMotion/SimpleRed` stops being always-cooked: −10.2 MB.** That includes 8.1 MB of `Hair_M_TwistedBraids` that only SimpleRed reaches. The code still loads SimpleRed by path as a fallback: `ReflectionsNpcSubsystem.cpp:307–310`, `ReflectionsNpcArchetype.cpp:216` and `ReflectionsSpellCraftingCommands.cpp:100–102`. It can only go if those fallbacks go. `CrowdMotion/WardrobeRefit` is another 3.2 MB, if nothing uses it.

**Invisible total: about −66 MB (items 2 and 3), or −76 to −80 MB with item 4.**

## Visible (the user's call, not part of the untangle)

- **The two full donor faces.** `CoinClerk` (20.6 MB) and `BridgeGuard` (19.9 MB) carry LOD3 baked face textures (`T_Head_LOD3_N_VT` 5.3 MB, `T_Head_LOD3_SRMF_VT` 4.6 MB, each) and full-size eye and teeth normals. The other four donor faces only have the LOD5to7 set, at ~5 MB each.
  - Used by: BP_Look_GiltCoinClerk, PewLook_CoinClerk, BP_Look_GiltBridgeGuard, PewLook_BridgeGuard, BP_WhiteLook_05_GuardRags, BP_WhiteLook_06_GuardBoldRunes and the SimpleRed fallbacks.
  - Making them like the others saves about −30 MB, with softer faces on those looks.
  - The Character texture cap at 1024, also pending with the user, shrinks them anyway.
