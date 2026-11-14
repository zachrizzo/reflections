# Jam rules: what the 2026 Epic AI MegaJam requires

Read on 2026-11-14 at about 10:30 MST from the [jam page](https://itch.io/jam/2026-epic-ai-megajam) and the [Official Rules (English PDF, 19 pages, last updated 2026-11-12)](https://epicgames.box.com/s/a7xcgl07fqoieeb99sjtd3juhj4agc4z). Rule numbers below are the PDF's section numbers. If the page and the PDF disagree, the PDF wins.

## Deadline

| | |
| --- | --- |
| Contest period (rule 4) | **12:00 AM ET, Thu Nov 12 → 8:59 PM ET, Sun Nov 15, 2026** |
| Same deadline in other zones | 5:59 PM PST · **6:59 PM MST (this PC, UTC−7)** · 01:59 UTC Mon Nov 16 |
| itch.io countdown | Shows "Submissions open … to November 15th 2026 at 6:59 PM" in local time, which matches |
| Late entries | Disqualified. Proof of submission isn't proof of receipt (rule 3). |
| Team target | 6 PM ET = **4 PM MST**, which leaves three hours of slack for the upload |

DST ended on Nov 1, so ET is EST (UTC−5) and PT is PST (UTC−8) on the deadline day.

## Theme

**DIRECTOR'S CUT.** "Your vision, your edits, your final cut. Every developer has that one feature that didn't quite make it… Now's your chance to finally build it. Using AI agents? You're directing those too."

- Rule 7(g): a submission **must demonstrate use of the Contest Theme**.
- Theme is also one of the seven scored criteria.

## Build, zip and size

| Requirement | Source |
| --- | --- |
| A packaged build. Unpackaged projects aren't accepted. | Jam page |
| Windows 10 or 11 (also allowed: macOS, Android, iOS). The jam recommends a **Development** build; Shipping is also accepted on Windows. | Jam page, rule 1(b) |
| Zip named **`TeamName_GameName.zip`** | Jam page |
| **Under 1 GB** for desktop. Bigger builds must go up with butler or Blendo Itch Uploader. | Jam page |
| Must run without any additional software | Rule 7(f) |
| Upload to the team's **own itch.io project page** first, then submit that project to the jam. One submission per team. | Jam page, rule 2 |
| **A human entrant** has to submit. An AI agent or other automated means can't. | Rule 17 |

## What the submission form needs

- Team name, each member's **full name** and the **email on their Epic Games account**, with one member named **Team Owner** (rule 1(c)). Prizes go to the Team Owner.
- Game name.
- Gameplay video link.
- **Sourced (non-original) assets, listed** (rule 1(d), 15(c)). Sourced assets aren't scored. Content the team generated with AI tools **doesn't count** as a sourced asset.
- Dev log link: optional, but required for the Glass Box prize, and it has to be submitted with the entry before the deadline (rule 10).
- "Tools you used": optional, but required for partner prizes such as Hyper3D's cash pool.
- OpenAI question: optional. Answering it makes the entry eligible for the **OpenAI Award** (US$5,000 in API credits for the Best Overall UE entry that makes the best use of OpenAI models or products). See below.
- NVIDIA RTX questions: optional, and only relevant for Render Royalty with NvRTX or DLSS features.

## Video

- **30–60 seconds** of **recorded gameplay** (rule 1(e)).
- At **1920×1080 or higher** (rule 7(c)).
- Must be in English (rule 7(i)). The jam's tip is to show gameplay in the first five seconds.

## AI use and pre-jam work

- AI tools are allowed for code, assets and in-game systems (rule 7(a)). **No AI-use declaration is mandatory.** The amount of AI disclosed is "considered for context only and will not, on its own, increase or decrease a Submission's score" (rule 9).
- Before Nov 12 you may prepare **AI tools, agent configs, MCP settings, prompt libraries and scripts**. Epic may ask to see them or the version-control history (rule 7(h)).
- **All other game content** (gameplay, levels, art) must be made during the contest period, apart from noted sourced assets (rule 7(h)). The jam page: "Declare anything you made earlier."
- The entry must be "custom gameplay that exceeds" Epic's starter templates, and must not be "an obvious extension" of an Epic tutorial (reusing its project, levels or assets with only minor changes) (rules 7(d) and 7(e)).

## Content rules (rule 8, rule 15)

- Nothing that infringes copyright, trademark, privacy or publicity rights. Epic will **disqualify** a submission it believes may infringe copyright (rule 15(g)).
- **No trademarks or logos** except the Unreal Engine logo, used per Epic's branding guidelines (rule 15(d)).
- Must suit a **Teen (13+)** audience: no nudity, nothing obscene, and no illegal substances.
- All in-game text and audio must be **in English** (rule 7(i)).

## Judging (rule 9)

Each criterion is scored 1–5. A tie is re-scored with Fun Factor counted double.

| Criterion | What judges look for (jam page) |
| --- | --- |
| Ambition and innovation | Something you couldn't usually pull off in four days: a new mechanic, a bold style, or a bigger scope |
| Theme | A fresh, clever take on Director's Cut |
| Fun factor | Fun and satisfying |
| Gameplay | Solid, original mechanics that feel good |
| Visuals | A strong, consistent look |
| Level design and progression | Spaces that support the gameplay and guide the player |
| Audio | Sound and music that add to the experience |

Modifier prizes we qualify for: **Best Team** (two or more people, US$5,000), **Render Royalty** (visuals), **Glass Box** (needs a dev log submitted with the entry), and the **OpenAI Awards** (Codex and the OpenAI-powered dev relays count as "OpenAI models or products… during development"). A team can win one main prize and one modifier prize. Winners are announced by Jan 29, 2027.

## Where the current plan breaks the rules, or risks it

| # | Risk | Rule | Severity | What to do |
| --- | --- | --- | --- | --- |
| 1 | **Someone else's IP.** The premise, three stacked Londons named Gray, Red and White, crossing between them with a coin from the destination world, the hero's special long coat, and a shadow that possesses people, closely follows V.E. Schwab's *Shades of Magic*. One concept-art prompt names the book outright: `ArtDirection/Three-Londons-Wardrobe/prompts.md:108` asks for a coat "inspired by Kell's high-collared, many-sided coat from A Darker Shade of Magic". | 8, 15(a), 15(g) | **High: disqualification** | Rename every player-visible name, and reframe the worlds' identities. See [originality.md](originality.md). Never quote the prompt file publicly, and leave the book out of the itch page, the dev log and the video. |
| 2 | **Nothing ties the game to the theme.** No code, README or HUD text in the repo mentions Director's Cut. | 7(g) and the Theme score | **High** | Choose a framing that carries the theme. Each name set in [originality.md](originality.md) includes one. Show it in the first 10 seconds of the video and in the itch pitch. |
| 3 | **Pre-jam and sourced content has to be declared.** The project builds on Epic's Game Animation Sample hero (`Hero/Sample`, `GM_HeroSample`), template `Variant_*` code, mannequins, Paragon, Advanced Locomotion and MetaHumans. | 1(d), 7(e), 7(h), 15(c) | Medium | List them all in the form's sourced-asset field (draft in [ai-declaration.md](ai-declaration.md)). The custom spell, crafting and world-jump gameplay clears 7(e). |
| 4 | **Dev-only OpenAI relays sit in a Development build.** `UReflectionsSpellRecipeRelay` is compiled out of Shipping only, and the jam ships Development. The NPC voice prototype binds **T** and shows connection status on screen. | 7(f) | Medium | Confirm with spell-crafting that the relay falls back silently with no Python running. Hide or disable the T voice prompt in the jam build. The voice prototype has no listed owner. |
| 5 | **Teen rating.** There's a blood VFX test (`ArtDirection/SpellVFX/Blood_NPCTest.png`), ragdoll deaths, and White London's "rags and tattoos" outfits with "large exposed areas of skin". | 8 | Low | Keep blood stylized and brief, and check the outfits in the final build. |
| 6 | **Trademarks.** Gray London is modern London: a bus driver, transit workers, river crews. | 15(d) | Low | Check for TfL roundels, red-bus livery logos, police crests or real brands on props and costumes. |
| 7 | **Video resolution.** Most existing captures are 1600×545 or 1600×857. | 7(c) | Low | Capture at 1920×1080 or higher (see [video-plan.md](video-plan.md)). |
| 8 | **Size budget.** The test zip is 823 MB. Each extra MetaHuman adds about 50–60 MB, and `/NNEDenoiser` (about 100 MB) is still in. | Jam page | Medium | The packaging session tracks this. Use butler only if the zip exceeds 1 GB. |
| 9 | **Who submits.** | 17 | Must do | The Team Owner submits by hand on itch.io. No agent may press Submit. |
