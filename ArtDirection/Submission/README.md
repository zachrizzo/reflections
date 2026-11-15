# Submission kit: *Reflections*, 2026 Epic AI MegaJam

**Deadline: Sun Nov 15, 8:59 PM ET = 6:59 PM MST on this PC.** Team target: 6 PM ET = 4 PM MST. Late entries are disqualified, and a human must press Submit (rule 17).

| File | What's in it |
| --- | --- |
| [rules.md](rules.md) | The official rules: deadline, zip and size, video, AI and pre-jam rules, judging and theme, plus **where our plan breaks them** |
| [originality.md](originality.md) | Everything that echoes *Shades of Magic*, the three name sets, and the chosen set (**B, "Reflections"**) |
| [rename-table.md](rename-table.md) | Every player-visible string to rename, with file, line and owner. Each owner has been sent its rows. |
| [ai-declaration.md](ai-declaration.md) | Which AI tools made what, what existed before the jam, the sourced-asset list for the form, and what couldn't be verified |
| [itch-page.md](itch-page.md) | Paste-ready itch.io page: pitch, features, controls, system requirements, credits, screenshot picks |
| [commercial-readiness.md](commercial-readiness.md) | Whether the game can be sold: licence and commercial-use status of every third-party asset and AI output, IP status after the rename, and what to redo first |
| [checks.md](checks.md) | Read-only checks: trademark sweep of the Pewterside art, Teen rating of the Frostside outfits and blood, and hold vs toggle for walk, crouch and strafe |
| [canon.md](canon.md) | Canon sheet: names, pronunciation, words never to use, and a starter voice script for the AI character voices (Google Gemini designed voices; OpenAI for the Tarnish and narrator) |
| [sunday-checklist.md](sunday-checklist.md) | **Start here on Sunday.** Tonight's prep, the minute-by-minute timeline (rehearsal train → package → smoke test → zip → upload → itch page → submit) with owners and fallbacks, the 15-minute smoke test, and the size plan |
| [video-plan.md](video-plan.md) | 55-second, 10-shot list with each shot's console set-up, and how to record the packaged build without touching the shared editor |
| [screenshots.md](screenshots.md) | The 6 itch screenshots and the cover: what's in frame and how to set each one up |
| [gray-london-review.md](gray-london-review.md) | Jah's Gray London map (merged to main 11-14): required attributions, what blocks a sale (real brands and Underground roundels, the Albert Memorial scan, ODbL share-alike), and the naming sweep (no "Gray/Red/White London" reaches players) |
| [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) | Licence notices for the zip root (OSM/ODbL, CC BY 4.0, MIT, OFL, and the AI-tool attributions). Two `[CONFIRM]` items for Jah. |

## Decisions the team still has to make

1. ~~Name set~~: **done**, set B "Reflections" (2026-11-14).
2. ~~A Director's Cut line~~: **done, both lines (2026-11-14).**
   - **In game, (a):** "Lanthorne was cut into three reflections, and only one is the version its maker meant. The Tarnish wants the final cut." It goes on the title or intro screen (game-flow-ui, row G6) and on the video's title card.
   - **On the itch page and in the dev log, (b):** "Our director's cut: spell crafting, the feature we kept scoping out, finally made it in, and now you direct the magic." Before publishing, the team confirms the line about "kept scoping out" is true for them.
2b. ~~Rating~~: **decided 2026-11-14: the game is M (Mature), and the team accepts the jam risk.** In the user's words: "If they reject it for that reason, that's fine. We're more so caring about whether or not it's a good game, because we might actually try to sell this afterwards." No more content changes for the Teen rating.
   - For the record, the Official Rules (PDF updated 2026-11-12), **page 5, rule 8, bullet 5**: "The Submission must be appropriate for a teen audience, meaning content suitable for players aged 13 and over (consistent with a "Teen" rating under the ESRB system or its equivalent);"
   - **Page 4, rule 6:** Sponsor "may remove any Submission … and disqualify an Entrant from the Contest if it believes, in its sole discretion, that the Entrant's Submission fails to conform to the Guidelines and Restrictions."
   - **Page 5, rule 9:** submissions are "pre-screened … prior to any judging".
   - So an M-rated entry may be disqualified at pre-screening. That isn't automatic, and Epic's decision is final.
   - Since a commercial release is possible, see [commercial-readiness.md](commercial-readiness.md).
3. **Team name and members.** The zip must be `TeamName_Reflections.zip`. The form needs every member's full name, their Epic-account email, and which one is **Team Owner**.
4. **The start map.** The default map is `Lvl_HeroSampleCrowd`, a copy of Epic's Game Animation Sample sandbox. Judges score Level Design, and it's sourced content. Switch the default to `/Game/MockCity/Lvl_MockCity` before the rehearsal (owners: orchestrator and game flow).
   - **Checked 11-14 ~19:00, and it's more urgent than the switch:** New Game already loads `Lvl_MockCity` (`DefaultGame.ini:82`), but **no cook setting names it**. Unless another cooked asset references it, the package would have no playable map. See [sunday-checklist.md](sunday-checklist.md#before-sunday-tonight) T1.
5. **The blood VFX** came from the team's September project and ships. Declare it (already in [ai-declaration.md](ai-declaration.md)), or have spells swap in a jam-made hit effect.
6. **Coin Rule** (optional, de-risks IP): switch world jump from "a shard of the destination" to "any shard" or "a shard of where you are". See [originality.md](originality.md#changes-worth-making-in-any-case).
7. **Optional prizes:** a dev log (needed for Glass Box; it must be linked before the deadline), and answering the **OpenAI** question. Codex and gpt-image qualify; draft answer in [ai-declaration.md](ai-declaration.md#short-form-for-the-itch-page).
8. **Who records the video and when.** A person has to play it. Start by 2 PM MST Sunday.

## Still open with other sessions

- **Renames sent 2026-11-14 ~10:45 MST** to world-jump (W1–W31), game-flow-ui (G1–G6), villain-finale (V1–V3) and packaging (P1–P3). Audio was sent its README correction. Spells and spell crafting have no rows.
  - **villain-finale: done** (V1–V3). I checked the code: no "London" outside comments, and the boss bar, messages and finale banner use "The Tarnish" and "The Mirror Is Whole".
  - **world-jump: done** (W1–W31; the C++ text goes live with the next build train, and the assets are already saved). I checked that the name sources (data asset, C++ defaults and enum) now say Pewterside, Giltside and Frostside, the key is `GiltTowerKey`, and no world-jump asset contains "… London". "London" survives only in code comments, which players never see. **W28 is still open:** page titles on pickups in the *final* map belong to whoever places them there (orchestrator to assign). **W32**, the Coin Rule, waits for the user.
  - **game-flow-ui: done** (G1–G6, lands on the next build train). I checked the source and the string table. All player-facing menu text lives in **one String Table, `/Game/UI/ST_GameFlowText`** (mirror CSV `ArtDirection/GameFlow/ST_GameFlowText.csv`), so later renames need no rebuild. `Credits.Team` still reads "Team names to come". The theme line sits under the title. The `Game.Tagline` follow-up is **done**: it now matches the itch tagline, both in the table and in the code's fallback (`ReflectionsGameFlowSlate.cpp:711`). No game-flow text describes the sides by magic or by who rules them any more.
  - **Packaging: done** (checked in `Config/DefaultGame.ini:3-5`): `ProjectName=Reflections`, Displayed Title "Reflections", and the description. The window title takes effect in the next package. `CompanyName` waits for the team name (decision 3); send it to packaging.
- **Bindings: all confirmed** in [itch-page.md](itch-page.md#controls), including the Final Spell (F / X). The only thing left is playing once to see whether walk, crouch and strafe are hold or toggle.
- **Unassigned (orchestrator):** the "1 M" height labels on the sample level blocks. The voice prototype is now NPC talk-back (NPC dialogue session): the "London" wording and the token message are gone.
- **NPC talk-back is Gemini only** (the user's decision, 11-14 18:15). Live replies use `gemini-3.5-transcribe-live`, `gemini-3.5-flash-lite` and `gemini-3.8-flash-tts`. They run only with a Gemini key in `keys.json` next to the bundled helper. Without one, people use baked lines and talking makes no network calls. OpenAI is dev-only now.
  - The AI declaration, the itch page and its new [privacy note](itch-page.md#privacy-talking-to-people) are updated, and the new `Credits.Tools` is **live**. game-flow-ui saved it at 18:42, with the CSV and the C++ fallback matching. I checked that the CSV matches ai-declaration.md line for line (9 lines). In `ArtDirection/GameFlow/Screenshots/14_victory_credits_gemini.png` all 9 lines fit on the Victory panel with no clipping.
  - **Open:** does the zip ship a dedicated key for judging, or do players bring their own? The itch page assumes their own and has the alternative sentence ready.

## Sunday checklist

The full plan, with times, owners and fallbacks, is [sunday-checklist.md](sunday-checklist.md). In short:

- [ ] **Tonight:** cook the mock city (T1), switch the start map (T2), get the team names (T3), decide on the key (T4) and the recorder (T5), join the jam and draft the itch page (T6)
- [ ] 09:00 rehearsal train → package with `--with-npc-relay` → zip → smoke test
- [ ] 10:15–12:00 record the video and screenshots from the rehearsal build
- [ ] 12:00 freeze → 12:15 final train → package → clean-folder test → 13:30 go/no-go
- [ ] 13:35 upload the zip; edit and upload the video; fill in the itch page; set it Public
- [ ] **15:00 the Team Owner submits** (target 16:00 MST, deadline 18:59 MST), and saves a screenshot of the confirmation
