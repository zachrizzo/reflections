# Gray London map review: jam and later sale

Reviewed 2026-11-14 at ~21:05 MST. The map is Jah's PR #1 ("Add Gray London prototype level", `4aac7d0d` on `origin/main`), which the orchestrator says becomes the main map.

**How I checked**, with no editor and no checkout:
- I read the five files in `Docs/GrayLondon/` on `origin/main`.
- I listed the 3,626 changed files.
- I fetched the map's LFS objects into `.git/lfs` only, and searched every one of the 3,620 assets for text.
- I checked the three key licence pages online: Codriver, Zenodo and Fab.

The working tree, the branch and the editor were not touched. `main` is **not** merged into `jam/checkpoint-2026-11-14` yet.

## Verdict

| Question | Answer |
| --- | --- |
| **Naming: does "Gray/Red/White London" reach players?** | **No**. "Gray London" appears 684 times, but only as editor actor labels such as "Gray London PCG B01 Awning A01", which are stripped from cooked builds. "GrayLondon" is in package paths only. Red and White London don't appear at all. No config, C++ or string-table change came with the map, and our UI never shows a map name. **But see trademarks.** |
| **Can it ship in the jam?** | **Yes, if the branded signs come out first.** Rule 15(d) allows "no trademarks or logos" except the Unreal logo. The map shows about 15 real brands plus 104 London Underground roundels. |
| **Can it be sold later?** | **Yes, with four fixes:** remove the brands and logos, replace or clear the Albert Memorial scan, meet ODbL's share-alike duty, and confirm the Fab props licence. The licences themselves (ODbL, CC BY 4.0, CC0, MIT, OFL) all allow commercial use with attribution. |
| **Size** | The map adds **376 MB** of assets (142 MB of city tiles). `train5_Windows.zip` was 734 MB, so a build with this map may pass **1 GB** and need butler. Packaging should measure it. |

## 1. Required attributions

Every source the docs name, and whether it ships in this repo (checked against the file list):

| Source | Licence | Ships? | What the licence requires |
| --- | --- | --- | --- |
| **OpenStreetMap** data, from Geofabrik's Greater London extracts (current and 2014) | **ODbL 1.0** | Yes: all street, building, park and river geometry, plus placements | A visible credit, "© OpenStreetMap contributors", with the ODbL named and the link openstreetmap.org/copyright. A credits screen is acceptable for a game. **Plus share-alike (ODbL 4.6):** the map is a Produced Work made from a filtered, height-estimated *Derivative Database*. Whoever publicly uses it must offer that database, or the method that made it (the generator scripts and exclusion lists), under the ODbL. See §2.3. |
| **Codriver 3D**: Buckingham Palace, Tower of London, Tower Bridge, St Paul's, Palace of Westminster, London Eye, Westminster Abbey, 30 St Mary Axe, Albert Bridge, Royal Albert Hall, National Theatre | **CC BY 4.0** (verified on 3d-assets.codriver.io/licenses.html; the model licence is the standard legal code with no added terms) | Yes (`Geodata/Landmarks/*`) | Name the creator (Codriver; the site's template names Codriver / 9570-6198 Québec inc.), link the licence, say it's CC BY 4.0, link the source, **say what was changed** (decompressed, axes converted, meshes combined), and repeat the OSM credit. The site also says that "trademarks remain with their respective rights holders". |
| **Albert Memorial scan** by artfletch (Zenodo, DOI 10.5281/zenodo.10307114) | **CC BY 4.0** | **Yes**: `External/AlbertMemorialReducedReview_20261114`, 21.6 MB. *This one wasn't in the orchestrator's list.* | Credit, licence link, and changes (reduced to 648,936 triangles, repositioned, two-sided material). It has a provenance problem; see §2.2. |
| **London Street Props (Free)** by Minimaliano (Fab): postboxes, bins, bollards, park railings and fence | The docs say **CC BY 4.0**, but **the Fab page shows no licence** ("License terms: -") | Yes (`Content/Fab/London_Street_Props__Free_`, plus adapted meshes in `Geodata/Props`) | If it's CC BY: credit, licence link and changes (recoloured). If it's the Fab Standard License: no credit is needed, and commercial use is allowed. **Jah: check the licence on the item in your Fab library.** |
| **Poly Haven**: road, grass, roof, pavement, brick and castle-wall textures, the street lamp, outdoor table set, urban facade kit | **CC0** | Yes | Nothing. A credit is a courtesy. |
| **Lion sculpture scan** by danielpett (Sketchfab, via Zenodo) | **CC0** | Yes (`Landmarks/ApproxTrafalgarLions`) | Nothing. A credit is a courtesy. |
| **Cosmo Tree Gen** by FrogCosmonaut: the ash tree. Its leaf texture is from OpenGameArt's CC0 vegetation set, and its bark is ambientCG Bark014 (CC0). | **MIT** for the generator; CC0 for the textures | The generated tree ships; the generator doesn't | MIT covers copies of the software, not its output. Shipping the notice (`LICENSE_COSMO_TREE_GEN.md`) is the safe choice. |
| **Noto Serif**, from Google Fonts | **SIL OFL 1.1** | Only as lettering baked into the street-plate textures. **No font file ships** (no font asset in the commit). | Nothing for rendered images. If a font file is ever shipped, include `OFL-NotoSerif.txt`. |
| Wikimedia Commons, Geograph and Flickr photos, Historic England listings | CC BY-SA 2.0 and 3.0 and others | **No**: the docs say "reference only, not textures" | Nothing. |
| **Not shipped, so no credit:** Dekogon *City Street Props* (an original substitute awning is used, per the README), the Old Vic Fab interior, artfletch's drinking-fountain scan, Replex's *Modular Urban houses* | — | No (none in the file list) | — |

**Credit lines.** These are **live** as `Credits.Map` (21:24), and I checked that they match word for word, with no clipping on the Credits or Victory screens. They are also in [ai-declaration.md](ai-declaration.md#credits-block-the-source-for-the-itch-page-and-game-flow-uis-creditsvictory-panel):

```
Map data © OpenStreetMap contributors, ODbL (openstreetmap.org/copyright)
Landmark models adapted from Codriver 3D (3d-assets.codriver.io), CC BY 4.0
Albert Memorial scan by artfletch (Zenodo), CC BY 4.0 · Street props by Minimaliano (Fab), CC BY 4.0
Textures and props: Poly Haven (CC0) · Trees: Cosmo Tree Gen by FrogCosmonaut (MIT) · Signs set in Noto Serif (SIL OFL 1.1)
```

On a credits screen these lines can't carry everything CC BY 4.0 asks for: the licence link, the disclaimer, and what was changed. That goes in **[THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt)**, which packaging copies to the root of the zip and which the itch page links to.

None of the credit lines say "London". The notices file does, on purpose: it names real sources such as "London Street Props", the Geofabrik "Greater London" extract and the London Eye model, because attribution has to be accurate. That doesn't break the naming rule, which covers game text and the colour names.

## 2. Problems for selling (and the jam)

### 2.1 Real trademarks and logos (jam rule 15(d), and a sale) — **fix before Sunday's final build**

Found in the docs, the asset names, and the map's two live text actors:

| What | Where | Why it's a problem |
| --- | --- | --- |
| **104 London Underground roundel markers** | `Geodata/TransitMarkers` | The roundel and "UNDERGROUND" are TfL registered trademarks, and TfL licenses them actively. **This is the worst item.** |
| Bus-stop flags drawn to TfL's bus-stop graphics standard | `Geodata/BusStops/T_BusStopFlag` | The TfL bus flag carries the roundel. |
| Readable store and venue names: **Harrods** (`Landmarks/T_HarrodsSign`), **Fortnum & Mason**, **Liberty**, **Hatchards**, **Twinings**, **The Old Vic**, **Garrick Arms**, and Cecil Court's **Watkins Books, Travis & Emery, Goldsboro Books, Marchpane** | Sign textures in the folders of the same names | Real trademarks on signs |
| **"Waterstone's"** and **"TATE BRITAIN"** | Two TextRender actors (labels "Waterstone's - Trafalgar Square - sign prototype" and "Tate Britain identification sign") | Live text with real trademarks |
| Check: **OXO Tower** face, **BT Tower** pilots, **Selfridges** frontage, the K6 kiosk "TELEPHONE" header, the Cenotaph's **RAF ensign** flag, and the **Buckingham Palace flag** | `OXOTowerFacePilot`, `BTTower*Pilot`, `Landmarks/Selfridges*`, `Geodata/K6Kiosks/T_K6_header`, `Landmarks/Cenotaph/M_Flag_raf`, `buckingham-palace-uncompressed/Materials/flag` | I couldn't read these textures without the editor. Each could show a mark: the OXO letters, the BT logo, a Selfridges sign, the RAF roundel (an MoD trade mark), or the Royal Standard. Have a look at each. |

The Piccadilly advertising panels are **fine**: the docs say they use "fictional text". Street-name plates use real street names, which is fine, and they are "not Westminster's branded nameplate artwork".

**Fix plan** (agreed with world-jump at ~21:25; world-jump is finding the instances in the editor; the orchestrator OKs changes to Jah's packages):
- **Sign textures:** swap them for generic trade words, not invented brands, so canon needs no review:
  - BOOKSELLERS: Hatchards, the Cecil Court shops
  - TEA MERCHANTS: Twinings
  - PROVISIONERS: Fortnum & Mason
  - DRAPERS: Liberty
  - EMPORIUM: Harrods
  - THEATRE: Old Vic
  - a made-up pub name for the Garrick Arms, e.g. THE LAMP & KEY

  This changes texture assets only; nothing in the map itself.
- **The two TextRender actors** aren't textures. Change their text ("Waterstone's" to BOOKSELLERS, "TATE / BRITAIN" to GALLERY), or hide them:
  - `__ExternalActors__/GrayLondon/Maps/GrayLondon_Geodata/1/FE/1PYCSCAM3NLP2FIMCXRQJY`
  - `.../E/67/J4M2QI9H1W13WMI61US781` (component `TateSignText`)
- **Transit markers and bus flags:** swap the material or texture for an original sign. A plain disc with "STATION" or "BUS STOP" will do.
- **Hiding at runtime** (a name blocklist) only as a stop-gap: hidden actors still ship in the pak.

Landmark *buildings* are fine to depict: they're visible from public places, and the UK and US both allow pictures of such buildings. Before a sale, a quick clearance check on the landmarks whose owners have registered their images is cheap. Codriver's own terms say it grants no trademark rights.

### 2.2 The Albert Memorial "source-provenance caveat" — jam: keep it, credited; sale: swap or clear it

The Zenodo record says artfletch's 1,177 photos were "mixed with frames extracted from this Youtube video" for the upper views of the steps, and it gives the video link. It states **no permission from the video's owner**. It also lists "Source: Objaverse 1.0 / Sketchfab" without saying more.

artfletch's CC BY licence can only cover artfletch's own work. So some of the geometry or texture around the upper steps may come from frames that nobody has licensed. The memorial itself (1872) is out of copyright. The risk is in the scan.

**Fix:**
- **Jam:** low risk. Keep the credit.
- **Sale:** pick one:
  - (a) revert to the generic blocks (the docs record an `albert_memorial_duplicate` rollback);
  - (b) ask artfletch whether the shipped geometry and texture use the video frames;
  - (c) re-model it as original work.

### 2.3 ODbL share-alike — needed for the jam too (any public release counts)

ODbL 4.6 says that if you publicly use a Produced Work made from a Derivative Database, you must also offer that database, or the method of making it, under the ODbL. Here that means:
- the filtered extract with its height and width estimates;
- the exclusion lists, such as `exclude_buildings.json` and the period-audit IDs;
- or the generator, such as `build_city_tiles.py`.

The docs say these live in the "development workspace", **not in this repo**.

**Fix (Jah):**
- Put the generator scripts and the exclusion and manifest JSON in a public place under the ODbL, for example a public GitHub repo or a zip on the itch page.
- Add one line to THIRD_PARTY_NOTICES.txt and the itch page saying where they are.
- A written "available on request" offer also meets 4.6, but publishing is simpler.

### 2.4 The Fab props licence isn't confirmed

See §1. CC BY and Fab Standard both allow sale. Only the credit wording changes. Low risk.

### 2.5 Not licence problems, but the team should decide

- **The game is set in real London.** The rename moved the game away from *Shades of Magic*'s Grey, Red and White London ([originality.md](originality.md)). A recognisable real London, with Big Ben, Tower Bridge and the Eye, as one of three colour-coded reflections brings the books' premise back into view, though not their names. Ideas aren't protected, so this isn't infringement. But canon says the city is **Lanthorne**.
  - **Recommendation:** keep every player-facing word "Lanthorne", Pewterside, Giltside and Frostside.
  - Never write "London" on the itch page, in the video or in the dev log.
  - Make the branded-sign fix above use invented names.
  - Whether Lanthorne is "a reflection of London" in the story is the user's call.
- **Pre-jam check (rule 7(h)).** The docs' dates fit jam work: the period audit is dated 2026-11-13 and the asset folders are stamped 20261114. But the docs describe "the original development project". **Jah should confirm it was started on or after Nov 12, and keep that project's version history**, since Epic may ask for it. The map arrives as one squashed commit, so this repo can't show its history.
- **AI declaration.** The docs describe AI-agent work ("agent_audit", "agent_assets") and **three AI-generated textures**: `T_BookshopPhoto`, `T_GroceryPhoto` and `T_BishopsgateClothesPhoto`, with their prompts kept in the workspace. **Jah: which agent and which image model?** They are added to [ai-declaration.md](ai-declaration.md) as "to confirm".
- **Cooking.** Like the mock city, `GrayLondon_Geodata` must go in `+MapsToCook` and the bat's `-map=`. It's a World Partition and PCG map, so it can't be one of the mock city's streamed side maps without work. See [sunday-checklist.md](sunday-checklist.md) T1 and T2.

## 3. What was searched, for the record

- **Text scan:** all 3,620 LFS assets, as Latin-1 and UTF-16, for `(gray|grey|red|white)[ _-]?london`, `london` and `TextRender`.
  - "Gray London" appears 684 times, all `ActorLabel` values or PCG volume names, all in `__ExternalActors__`.
  - "GrayLondon" appears in package paths.
  - "gray_london" appears in the texture name `gray_london_facade`.
  - "Red London" and "White London" never appear.
  - Only two TextRender actors exist ("Waterstone's"; "TATE" and "BRITAIN").
- **Not checkable without the editor:** text baked into textures, namely the 22+ street plates, the shop signs listed above, the Piccadilly ad atlas, the K6 header and the bus flag. The docs describe all of them, and §2.1 lists the ones to look at.
- **Our code:** `Source/` has no UI that shows a map or level name. `GetMapName()` appears only in logs and map checks. "London" in `Source/` appears only in comments and `/Game/Characters/*London/` asset paths.
