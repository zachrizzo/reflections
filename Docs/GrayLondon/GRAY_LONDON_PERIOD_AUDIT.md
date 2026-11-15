# Gray London: rapid period and skyline audit

Audit date: 2026-11-13. The active user prioritizes broad visual immersion; these are high-confidence, high-visibility discrepancies only, not an exhaustive historic reconstruction. All numerical IDs below are the `id` stored in the project's `london-latest.json` / `london-2014.json` and consumed by `build_city_tiles.py` (osmium area IDs). They are not necessarily the raw OSM way IDs. Add to `exclude_buildings.json` using these exact project IDs.

## One Blackfriars, completed 2018

Source: project engineer https://www.robertbird.com/rbg-projects/one-blackfriars/ . Affected tile `Tile_p02_p00`. Exclude main `779762582` and all 28 included parts `1543400716` through `1543400770`, inclusive, step 2. All lie fully inside the current tower footprint. No 2014 building polygon overlaps the current tower footprint in the extract; that is a mapping gap, not proof the 2000s site was empty. Do not invent a predecessor.

## 100 Bishopsgate, completed 2019

Source: contractor https://www.multiplex.global/news/watch-as-100-bishopsgate-joins-the-london-skyline/ . Affected tile `Tile_p03_p01`. Exclude the current development outline `1405630556` and the unmistakably modern 40-floor tower/roof parts `1331231848`, `1331956170`, `1331956174`. The overlapping undated six-storey polygon `1338202656` is fully inside the current complex but its historic identity is not verified; review before suppressing it. 2014 polygon `332862104` intersects the south edge of the current site, has only `building=yes`, and is NOT proven to represent a 2009 predecessor: by Nov 2014 old buildings had been demolished (https://www.cityam.com/another-city-tower-offing-brookfield-buys-rest-100-bishopsgate/). It is supplied for inspection in `historical_predecessors_2014.json`; do not automatically restore.

## 8 Bishopsgate, completed 2023

Sources: developer https://www.mec.co.jp/news/mec230713_8bishopsgate/230809_8bishopsgate%E7%AB%A3%E5%B7%A5_final_ENG.pdf ; City of London names both prior buildings https://news.cityoflondon.gov.uk/city-of-london-corporation-approves-revised-plans-for-taller-bishopsgate-office-tower/ . Affected tile `Tile_p03_p01`. Exclude main `2273703680` AND included parts `2273703682`, `2273703684`, `2273703686`, `2273703688`, `2273703690`, `2273703692`, `2273703694`, `2273703696`. The outline is currently absent from the manifest because overlapping parts suppress it, but will reappear when the parts are removed unless explicitly excluded. The 2014 mapped predecessor features `310861010` (150 Leadenhall Street, Tokio Marine) and `340043410` (6–8 Bishopsgate, 20 levels) are available with full geometry and tags in `historical_predecessors_2014.json`; the City source establishes these were the pre-redevelopment buildings. Their exact 2000s appearance is not verified.

## The Shard, completed 2012

Source: Southwark planning report https://docs.planning.org.uk/20210430/54/QS10PYKBMY200/xoajakveotuptoi4.pdf . Affected tile `Tile_p03_p00`. Main 62221474 has an explicit 2012 start_date and is already excluded by the generator, but the included undated parts remain. Exclude `453475824`, `1330343378`, `1330343380`, `1332249650`, `1332249652`, `1332249654`, `1332249656`, `1332249658`, `1332249660`, `1332249662`, `1332249664`, `1332253900`. The 2014 shape of `453475824` was explicitly tagged 305.7m and 72 levels, proving it is Shard geometry despite its presence in the comparison snapshot. Southwark Towers was the predecessor and its demolition began in 2008 (https://docs.planning.org.uk/20210430/54/QS10PYKBMY200/bw22bl6dvmox2tm7.pdf); the 2014 data cannot restore it. Select a clear 2000s reference year before treating the late-2008/2009 construction site as a finished building.

## Scope and checks

The current manifest has 121 geodata tiles, 4,022,201 source mesh faces and 133,000 unique included building area IDs. 93,248 of these IDs were not found in the 2014 extract; this means mapping/ID coverage changed and does NOT prove they were built later. Do not blanket-remove them. The generator only filters explicit `start_date > 2009` on building features; undated post-period buildings and new parts remain. Global attribution, interior/shop coverage, movement under/over bridges, Thames collision openings and playable boundary all still require verification. Follow the existing selected tile build, Blender export and Unreal reimport workflow sequentially and preserve existing material slots and exclusions. These counts describe source manifests, not runtime frame rate or a count of independent real-world buildings.

## Subsequent correction: News Building
The News Building / The Place (completed 2013) was also excluded by project IDs 343229388, 1551139658, 1551139660, and 1551139662. Guy's Tower is retained. The predecessor New London Bridge House has a documented height but its footprint was not verified, so no replacement has been fabricated. The Shard parent outline 62221474 is now explicitly excluded. Sources: https://www.sellar.com/projects/news-building/ and https://moderngov.southwark.gov.uk/documents/g3228/Public%20reports%20pack%20Tuesday%2023-Mar-2010%2019.00%20Planning%20Committee%20decommissioned%20for%20planning%20com.pdf?T=10.

## Subsequent correction: 20 Fenchurch Street
The 2014 tower's 211 source parts and its parent are excluded. The source-only correction removed 3,016 attributed triangles and the result was inspected after reload; a sample at the site hits ground. The earlier building was demolished in 2008, but its footprint remains unverified, so no predecessor has been reconstructed. [City planning report](https://democracy.cityoflondon.gov.uk/Data/Planning%20and%20Transportation%20Committee/20110511/Agenda/%2408%20-%20Redevelopment%20of%2020%20Fenchurch%20Street%20-%20Potential%20Acquisition%20of%20Land%20for%20Planning%20Purposes.doc.pdf); [Landsec](https://www.landsec.com/en/about/about-landsec/80).


## Subsequent additions: Bishopsgate sites
The 2011 Heron Tower’s eight undated source parts were removed. Two approximate office blocks now represent the earlier Kempson House and Bishops House, both under demolition by 2007; their shapes and heights are estimates and do not reproduce the 2009 construction site. Two additional approximate blocks occupy part of the 100 Bishopsgate site, with storey counts based on the City’s inventory and estimated footprints and façades. These additions are described in `GRAY_LONDON_DATA_SOURCES.md` and the open-and-status guide. They are playable approximations, not measured reconstructions.
