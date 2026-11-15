# Read-only checks: trademarks, Teen rating, and hold vs toggle

The orchestrator asked for these on 2026-11-14 (around 11:30 MST). They were done from files on disk only: no editor, no PIE, nothing saved.

## 1. Trademark sweep: Pewterside costumes and props (rule 15(d))

**Result: no logos or real brands found. Nothing ships for Pewterside yet.**

- **No Pewterside (gray) NPC or prop assets exist in `Content/`.** `Characters/` has only `RedLondon`, `WhiteLondon`, `CrowdMotion` (red simple outfits), `Hero` and Epic sample characters. The gray test map `Worlds/Test/Lvl_WorldJump_Gray` is graybox, and no final city map exists yet. Pewterside currently looks like the other sides with a gray grade.
- **The concept lineups** (`ArtDirection/Three-Londons-Wardrobe/Gray London/gray-01..03.png`, the 12 NPCs) were checked at full resolution. **No logos, wordmarks, crests or brand marks** appear. The bus driver's ID badge is blank, and the newspaper and camera have no legible branding.

Watch these if Pewterside NPCs get built from the lineups:

| Asset | What | Risk | Fix if built |
| --- | --- | --- | --- |
| `gray-01-street-and-transit.png`, bus driver | Holds a folded transit map with coloured lines | Low. If turned into a texture, a London Underground-style map is TfL's protected design. | Use an invented route map, or none |
| `gray-02-river-and-night-shift.png`, paramedic | Dark-green jacket with hi-vis bands, red kit bag | Low. It reads as UK ambulance uniform, but carries no text or crest. | Keep it plain: no "AMBULANCE", NHS or cross insignia |
| `gray-03-neighborhood-and-civic.png`, retired dockworker | Waxed field jacket | Very low. It's a generic garment. | None |
| `ArtDirection/Three-Londons-Realistic/01-gray-london.png` (concept only) | **The Shard** on the skyline and a **red double-decker bus** | Not a trademark issue, but it identifies London, which the rename removes | Don't model the Shard or red buses for Pewterside, and keep this image off the itch page |

**Other sides, checked at the same time:** Red-world lineups, the merchant coat, the ferry-pilot atlas, the red tunic atlas, and the bridge guard's plain cross shield. None has any logos.

## 2. Teen rating (rule 8: 13+, no nudity)

**Result: Teen-appropriate as built. No changes required.** Two optional tweaks are listed below.

**Frostside outfits.**
- *Shipping:* the White crowd looks `BP_WhiteLook_01..06`, including `05_GuardRags` and `06_GuardBoldRunes` (IvenRook clothing `SK_Iven_*`).
  - The female guard (`IvenMetaHuman/WhiteGuard_BoldRunes.png`, `WhiteGuard_Fit_Front.png`) wears an opaque sleeveless bodice and a layered skirt. Her torso and hips are fully covered, and the runes are on her arms and legs.
  - The male guard (`iven-rook-bridge-lookout-turnaround.png`) wears a one-shoulder wrap and shorts. A bare male chest is fine for Teen.
- *Concept only:* the "rags and tattoos" lineups (`white-01..03-*-rags.png`, `*-runes.png`) show bare midriffs and shoulder-baring wraps. Chests and hips are covered in every figure, as the prompt specified ("All chests and hips are covered"). Nothing is sexualized, and none of it ships as-is.

**Blood.**
- The impact spray (`NS_BloodImpact`, scaled 0.35, intensity 0.65) is only on targets tagged `Flesh`. Per the orchestrator, that's now limited to enemies, soldiers, the tarnished and villain hosts.
- It adds a **ground spatter decal 56 cm across that lasts 12 s** (`SpellVFX/ReflectionsSpellVfxSubsystem.cpp:538-557`).
- `Blood_NPCTest.png` shows a small red puff. There's no dismemberment and no pooling.
- That's within Teen ("Blood" plus "Fantasy Violence"). Ragdoll deaths are also fine.
- *Optional:* shorten the decal to about 6 s, or tint it darker so it reads less red. Owner: spells.

**Already covered elsewhere:** the blood VFX is pre-jam content, declared in [ai-declaration.md](ai-declaration.md#sourced-and-pre-jam-material).

## 3. Walk, crouch and strafe: hold or toggle

**Result: walk, crouch and strafe are toggles, and sprint and aim are holds.** That's from the input assets and the hero Blueprint, **not yet verified in a build**.

| Action | Input action triggers | How the hero handles it | Answer |
| --- | --- | --- | --- |
| Walk (Left Ctrl) | `IA_Walk`: Pressed only | The hero's parent Blueprint `BP_SampleCMCClean2` (a copy of GASP's `SandboxCharacter_CMC`) reads `IA_Walk` and flips `WantsToWalk` with a NOT node | **Toggle** |
| Crouch (C / B) | `IA_Crouch`: Pressed only | Sets `WantsToCrouch`, with `UnCrouch` on the other branch | **Toggle** |
| Strafe (middle mouse) | `IA_Strafe`: Pressed only | Flips `WantsToStrafe` with a NOT node | **Toggle** |
| Sprint (Left Shift / L3) | `IA_Sprint`: Pressed and Released | Starts on press, stops on release | **Hold** |
| Aim (RMB / LT) | `IA_Aim`: Pressed and Released, plus `ReflectionsSpellAim.cpp:147` checks the key is held | | **Hold** |

**How sure:** a Pressed-only trigger fires once per press with no release event, so the state can only change on presses, and the two NOT nodes confirm the flipping. This matches GASP's stock design. The chain is `BP_HeroSampleCleanTest` → `BP_SampleCMCClean2`. Check it with one play of the final build. [itch-page.md](itch-page.md#controls) is updated and marks these rows unverified in build.
