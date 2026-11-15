# Sunday checklist: build, package, test, upload, submit

All times are **MST, the clock on this PC** (ET is 2 hours ahead).
- **Team target: submitted by 4:00 PM MST** (6 PM ET).
- **Hard deadline: 6:59 PM MST** (8:59 PM ET). Late entries are disqualified ([rules.md](rules.md)).
- **A human must press Submit** (rule 17). No agent may submit.

The plan below submits at **15:00 (3 PM MST)**: an hour before the target and four hours before the deadline. Times use the 24-hour clock. Every step lists its owner, when it counts as done, and what to do if it fails.

**Fallback zips, best first:**
1. **Final:** the 12:15 train's package.
2. **Rehearsal:** the 9:00 train's package, kept as `Saved/JamBuild/Zips/rehearsal_Windows.zip`.
3. **`Saved/JamBuild/Zips/train5_Windows.zip`** (734 MB, Saturday 12:50, clean). **It's a weak last resort.** It starts on the GASP sample map, so there's no world jump, mock city, Gemini voices or finale map. Use it only if both Sunday packages fail.

## Before Sunday (tonight)

| # | What | Owner | Why it can't wait |
| --- | --- | --- | --- |
| T1 | **Cook the mock city.** `NewGameMap` is `/Game/MockCity/Lvl_MockCity` (`Config/DefaultGame.ini:82`), but no cook setting names it: not `+MapsToCook` (only `Lvl_HeroSampleCrowd`, line 11), not `[AlwaysCookMaps]`, not `DirectoriesToAlwaysCook`, not the `-map=` in `PackageJamBuild.bat`. Unless some cooked asset happens to reference it, the package won't contain it, and **New Game in a packaged build would have no map to load**. No package has been made since train #5, so nobody has checked. Adding it costs nothing. Add `Lvl_MockCity` and `Lvl_MockCity_Pewterside` / `_Giltside` / `_Frostside` to `+MapsToCook` and to the bat's `-map=` (joined with `+`). | Packaging (config), cleared by the orchestrator | The rehearsal has to cook the real map |
| T2 | **Start map.** Set `GameDefaultMap` (`Config/DefaultEngine.ini:2`) to `/Game/MockCity/Lvl_MockCity`. The title screen overlays whatever loads first, so otherwise judges see the GASP sample behind the title. Leave `EditorStartupMap` as it is. | Orchestrator + game flow | Level Design is scored, and the sample is declared sourced content |
| T3 | **Team name, every member's full name and Epic-account email, and the Team Owner.** These give the zip name `TeamName_Reflections.zip`, `CompanyName` and `Credits.Team`. | User | Packaging, credits and the form need them |
| T4 | **Ship a Gemini key in the zip, or not?** The recommendation is **no**: players bring their own key, and the itch page is written that way. If yes, follow the dedicated-key steps in `ArtDirection/NpcDialogue/README.md` and use the marked alternative sentence in [itch-page.md](itch-page.md#privacy-talking-to-people). | User | It changes what the package contains |
| T5 | **Who records the video, and on which machine.** | User | Recording starts at 10:15 |
| T6 | **itch prep.** The Team Owner logs in to itch.io, clicks **Join jam** on the [jam page](https://itch.io/jam/2026-epic-ai-megajam), and creates the project as a **Draft** (Dashboard → Create new project). Paste the text from [itch-page.md](itch-page.md) now, so Sunday is only the upload. | Team Owner (human) | It takes 20 minutes on a calm evening, and longer on Sunday |
| T7 | **YouTube.** The recorder checks they can upload an Unlisted video longer than 15 s (the account may need phone verification). | Recorder (human) | Verification can take a day |
| T8 | **Optional: the dev log for the Glass Box prize.** It must be linked when you submit. Decide whether to write one. | User | It needs writing time |

## Sunday timeline

| Time (MST) | ET | Step | Owner | Done when | If it fails |
| --- | --- | --- | --- | --- | --- |
| **07:30** | 09:30 | Status check: overnight sessions, open blockers, T1–T5 answered | Orchestrator | Plan posted to every session | Chase the T3–T5 answers with the user first |
| 08:00 | 10:00 | **Fix window opens.** Only blocker fixes, each sent to the orchestrator first | All C++/content owners | — | — |
| **09:00** | 11:00 | **Rehearsal train R.** The editor closes, and `Build.bat` builds both targets from one source ([packaging README](../Packaging/README.md#how-to-package), step 1). No `Source/` edits while the editor is closed. | Orchestrator | Editor and game built, editor back up | Read the compile error and send it to its owner. Re-run at 9:30. |
| 09:25 | 11:25 | **SAVE FREEZE start**, announced to every asset-saving session and written in `SAVE-FREEZE-STATUS.md`. Wait for `Content/` to be quiet for 60 s. | Packaging | Freeze posted | — |
| 09:27 | 11:27 | `ArtDirection\Packaging\PackageJamBuild.bat --with-npc-relay`. **The flag matters:** without it the Gemini helper doesn't ship, and live talk can't work even with a key. The new maps make the cook longer; allow 20 min. | Packaging | `COOK COMMAND COMPLETED`, UAT exit 0, `NpcDialogueRelay.exe` staged, no `keys.json` | A cook error names the asset. Send it to its owner, end the freeze, and re-run after the fix. Still broken at 11:00 → keep going with train #11's editor for video and note the gap. |
| 09:50 | 11:50 | **SAVE FREEZE end.** Zip with `ZipJamBuild.ps1 -Source Saved\JamBuild\Windows -Dest Saved\JamBuild\Zips\rehearsal_Windows.zip`. Never zip by hand: the script drops `Saved/`, `*.sav`, `*.log` and `keys.json`. | Packaging | Zip made; **size noted** | Over 1 GB: see [Size](#size) |
| 09:55 | 11:55 | **Smoke test R** ([checklist below](#smoke-test-15-minutes)): a human plays, an agent reads the log | Human + packaging | Results posted to the orchestrator | Each failure becomes a fix ticket, or a cut |
| 10:10 | 12:10 | **Triage.** Fix what can be fixed by 11:45. Cut the rest: turn it off by setting, or leave it off the itch page and the video. | Orchestrator + user | Fix list with owners | — |
| **10:15–12:00** | 12:15–14:00 | **Record the video and screenshots from the rehearsal build**, in its own unzipped copy ([video-plan.md](video-plan.md), [screenshots.md](screenshots.md)). If a later fix changes a shot, re-record only that shot from the final build. | Recorder | All 10 shots with 3+ takes; 6 stills | A shot that won't work gets dropped (see the video plan's drop order) |
| 10:15–11:45 | | Perf soak on the rehearsal build, offscreen (`ArtDirection/Perf/tools/run_off.ps1`) | Perf | Soak result posted | A crash goes into triage |
| **12:00** | 14:00 | **CODE AND CONTENT FREEZE** for every session. After this, only fixes the orchestrator approves for the final train. | Orchestrator | Freeze announced | — |
| **12:15** | 14:15 | **Final train F**, the same as 9:00 | Orchestrator | Built | Re-run once at 12:45. Still failing → **use the rehearsal zip**. |
| 12:40 | 14:40 | SAVE FREEZE; `PackageJamBuild.bat --with-npc-relay` | Packaging | Cook complete, exit 0 | Rehearsal zip |
| 13:00 | 15:00 | Freeze end. Zip: `ZipJamBuild.ps1 -Source Saved\JamBuild\Windows -Dest Saved\JamBuild\Zips\<TeamName>_Reflections.zip` | Packaging | Zip under 1 GB, right name | [Size](#size) |
| 13:05 | 15:05 | **Clean-folder test:** unzip into a new empty folder, scan it with Windows Defender (right-click → Scan), launch `reflections.exe`, and run the smoke test | Human + packaging | Smoke test passes, Defender clean | Defender flags the helper → the game still works with baked lines; re-zip without `NpcDialogue\Relay` and change the itch talk paragraph. Smoke test fails → rehearsal zip. |
| **13:30** | 15:30 | **GO / NO-GO:** final zip, rehearsal zip or train5 | Orchestrator + user | Zip chosen and named `<TeamName>_Reflections.zip` | — |
| 13:35 | 15:35 | **Upload the zip** to the itch draft page: Uploads → choose the file → tick **Windows**, and set "This file will be played in the browser" to off. Browser upload of about 0.8–1 GB can take 10–40 min. | Team Owner | Upload shows "Processed" | Upload fails twice → butler ([Size](#size)) |
| 13:35–14:45 | 15:35–16:45 | **Edit the video** ([video-plan.md](video-plan.md#edit-and-upload)), export at 1080p60, upload to YouTube **Unlisted**, and wait for HD processing | Recorder | Link plays at 1080p, length 0:30–1:00 | Over 60 s → trim the finale. No HD yet → it still counts; 1080p appears when processing ends. |
| 14:00 | 16:00 | **Fill in the itch page** from [itch-page.md](itch-page.md): description (with the features that failed the smoke test removed), controls, credits, privacy note, tags, AI disclosure, cover and screenshots | Team Owner (an agent can prepare the text) | Every field filled | — |
| 14:45 | 16:45 | Video link onto the page (embed) and into the notes for the form | Team Owner | — | — |
| 14:50 | 16:50 | Set the page to **Public**. Check it in a private window: the page loads, the zip downloads, the video plays, and there's no "London" or debug text | Team Owner | Checked | — |
| **15:00** | 17:00 | **SUBMIT** on the jam page → **Submit your project** → pick the page. Form: team name; every member's full name and Epic-account email; the Team Owner; game name *Reflections*; video link; sourced assets (paste from [ai-declaration.md](ai-declaration.md#sourced-and-pre-jam-material)); tools used; the optional OpenAI answer; dev log link if any. | **Team Owner (human only)** | Submission confirmed | Form error → fix the field and retry. The itch jam page lets you edit a submission until the deadline. |
| 15:10 | 17:10 | Save a screenshot of the confirmation; post "SUBMITTED" to the orchestrator | Team Owner | — | — |
| 15:15–18:59 | 17:15–20:59 | **Buffer.** Changes are allowed, and are safest made through the itch page, not the jam form. | — | — | — |
| **16:30** | 18:30 | **Hard trigger:** if not submitted yet, submit **whatever is uploaded now**, then improve the page | Team Owner | Submitted | — |
| **18:00** | 20:00 | **Last resort:** nothing uploaded → upload `train5_Windows.zip` renamed to `<TeamName>_Reflections.zip`, plus any video, and submit | Team Owner | Submitted | — |

## Smoke test (15 minutes)

Unzip into a **new, empty folder**, then:

1. Launch `reflections.exe` with no arguments. The window title is "Reflections". The title screen shows **REFLECTIONS** with the theme line underneath.
2. **No Continue button** on first launch. If there is one, a save shipped in the zip.
3. **New Game.** The intro cutscene plays, and holding Space for 1 s skips it.
4. You start in **Giltside**, outside the Lamplight: warm lamps, people walking. The HUD shows health, mana, spells 1–4 and the Tarnish meter.
5. Aim (RMB) and cast Fire Bolt (LMB) at something. Kill an enemy or a tarnished person: they ragdoll and nothing crashes.
6. Pick up the two Pewterside shards on Bell Lane. When magic is full, hold **Z** to step down into Pewterside: the colour grade changes and the side's name comes up.
7. Hold **T** next to someone. Without a key you hear a recorded line and see no error text. With a key you get a live reply, the first-talk notice and the **AI VOICE** tag.
8. **K** opens spell crafting, and Esc closes it.
9. **Esc** opens the pause menu: Resume works, and Quit to title works.
10. Look out for: the word "London", debug text, checkerboard textures, T-poses, mannequins, and sound that cuts out.
11. Optional, about 3 min, by console (`` ` ``): `Villain.Finale`, then `Villain.BossHere`, then **F** until the boss dies. The victory screen and credits show; the credits name Gemini and OpenAI, and the team.
12. Quit. Open `reflections\Saved\Logs\reflections.log` in that folder and count lines with `Error:` and `Fatal`. Post the count.
13. **Delete that test folder.** Never zip it.

**Pass** = steps 1–9 work with no crash. Problems in steps 10–11 go to triage; they don't block the go.

## Size

The train #5 zip was 734 MB. Since then the package has gained:
- the mock city, with Codex's city kit and props;
- about 3,300 Gemini voice waves (audio estimated 31–48 MB cooked);
- more MetaHuman looks (packaging measured about 50–60 MB per extra MetaHuman);
- the 28 MB Gemini helper.

**The rehearsal at 9:50 gives the real number.**

If it's over 1 GB:
1. Apply the packaging README's fallbacks: drop SM5 shaders (about −65 MB), and lower the audio quality on ambient voices.
2. Or upload with **butler**, itch's command-line uploader, which the jam page allows for builds over 1 GB. Butler is a download from itch.io: **ask the user before installing it**, then run `butler push <TeamName>_Reflections.zip <account>/reflections:windows`.

## Roles

| Role | Who | Sunday jobs |
| --- | --- | --- |
| Orchestrator | `local_6f701af5` | Trains, freezes, triage, go/no-go |
| Packaging and playtest lead | the packaging session | Package, zip, smoke-test log, size |
| Submission | this session | itch text, form answers, last checks of names and credits; on request, the go/no-go notes |
| Owners on call for fixes | game flow `local_0b912c4f`, world jump `local_830b60d0`, villain `local_dd0eeffa`, NPC unify `local_c650e0ab`, squads `local_cf45fc1d`, spells `local_07d1c5bc`, crafting `local_f926586a`, audio `local_8ac9a603`, NPC dialogue `local_7ede22ac`, perf `local_0825a76a` | Fixes until 12:00 only |
| Recorder | a person (T5) | Video and screenshots |
| Team Owner | a person (T3) | itch page, upload, **Submit** |
