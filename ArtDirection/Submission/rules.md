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

Modifier prizes we qualify for: **Best Team** (two or more people, US$5,000), **Render Royalty** (visuals), **Glass Box** (needs a dev log submitted with the entry), and the **OpenAI Awards** (Codex, gpt-image, the OpenAI-voiced Tarnish and narrator, and the gpt-4o-transcribe check of every voice line count as "OpenAI models or products… during development"; live NPC replies are Gemini and don't). A team can win one main prize and one modifier prize. Winners are announced by Jan 29, 2027.

## Where the current plan breaks the rules, or risks it

| # | Risk | Rule | Severity | What to do |
| --- | --- | --- | --- | --- |
| 1 | **Someone else's IP.** The premise, three stacked Londons named Gray, Red and White, crossing between them with a coin from the destination world, the hero's special long coat, and a shadow that possesses people, closely follows V.E. Schwab's *Shades of Magic*. One concept-art prompt names the book outright: `ArtDirection/Three-Londons-Wardrobe/prompts.md:108` asks for a coat "inspired by Kell's high-collared, many-sided coat from A Darker Shade of Magic". | 8, 15(a), 15(g) | **High: disqualification** | Rename every player-visible name, and reframe the worlds' identities. See [originality.md](originality.md). Never quote the prompt file publicly, and leave the book out of the itch page, the dev log and the video. |
| 2 | **Nothing ties the game to the theme.** No code, README or HUD text in the repo mentions Director's Cut. | 7(g) and the Theme score | **High** | Choose a framing that carries the theme. Each name set in [originality.md](originality.md) includes one. Show it in the first 10 seconds of the video and in the itch pitch. |
| 3 | **Pre-jam and sourced content has to be declared, and some of it ships.** GASP (sample hero, mannequins, Paragon, Echo, foley) and Advanced Locomotion V4 came over from the team's September project `action_fighting_UE59`. So did the team's own **blood and explosion VFX** (made Sep 30 – Oct 8), and the blood effect **ships**. The **start map `Lvl_HeroSampleCrowd` is a copy of GASP's sandbox level.** | 1(d), 7(e), 7(h), 15(c), plus the Level Design score | **Medium–high** | List everything in the sourced-asset field (draft in [ai-declaration.md](ai-declaration.md#sourced-and-pre-jam-material)). Make the jam-built world-jump map the start map before the final build. Declare the blood VFX, or replace it. The custom spell, crafting and world-jump gameplay clears 7(e). |
| 4 | **Live AI in the build.** The spell-recipe relay is safe: without the relay's launch token it reports "not configured" and the crafting screen uses its offline parser (`SpellCrafting/ReflectionsSpellRecipeRelay.cpp:20-27`). The NPC talk-back (**T**) is owned by the NPC dialogue session and is **Google Gemini only** since 11-14 18:15. The game starts a bundled helper (`Content/NpcDialogue/Relay/NpcDialogueRelay.exe`), and only if `keys.json` with a Gemini key sits next to it. Then the player's speech or typed line goes to Google. Without a key, NPCs answer with baked lines and talking makes no network calls. OpenAI isn't used at runtime. | 7(f), 8 (privacy) | **Low**: judges need nothing extra, and without a key nothing is sent. Medium if the team ships a key: anyone with the zip can copy it. | Keep the in-game notice ("…sent to Google…") and the "AI VOICE" tag. The itch page carries the [privacy note](itch-page.md#privacy-talking-to-people). If the team ships a key, follow the NPC dialogue README's dedicated-key steps (a new key, restricted, on a capped prepay balance, deleted after judging). Antivirus may flag the PyInstaller helper, so scan the zip; if the helper is blocked, the game just uses baked lines. |
| 5 | **Rating.** The rule requires Teen. **The team has decided on M and accepts the risk** (2026-11-14, README decision 2b). The current content was assessed as Teen-compatible ([checks.md](checks.md)), but labelling the game M invites a rule-8 rejection. | 6, 8, 9 | **Accepted risk**: Epic *may* disqualify at pre-screening | None; the team's call. Don't change content for Teen. |
| 6 | **Trademarks.** *Update 11-15 15:15: Gray London no longer cooks. The shipped map is MedievalLondon, which references no branded signs, so this risk is **low** unless Gray London comes back.* Jah's Gray London map has real marks: **104 London Underground roundels**, TfL-style bus flags, and readable **Harrods, Fortnum & Mason, Liberty, Hatchards, Twinings, Old Vic, Garrick Arms, Waterstone's and TATE BRITAIN** signs, plus four Cecil Court shop names. A few more to look at: OXO Tower, BT Tower, the RAF ensign. | 15(d) | **Medium–high**: a judge who sees a roundel or a Harrods sign sees a rule-15(d) breach | Hide or rename those actors before the final build (map owner). List and fixes: [gray-london-review.md](gray-london-review.md#21-real-trademarks-and-logos-jam-rule-15d-and-a-sale--fix-before-sundays-final-build). Also check costumes for police crests or bus-livery logos. |
| 7 | **Video resolution.** Most existing captures are 1600×545 or 1600×857. | 7(c) | Low | Capture at 1920×1080 or higher (see [video-plan.md](video-plan.md)). |
| 8 | **Size budget.** The test zip is 823 MB. Each extra MetaHuman adds about 50–60 MB, and `/NNEDenoiser` (about 100 MB) is still in. | Jam page | Medium | The packaging session tracks this. Use butler only if the zip exceeds 1 GB. |
| 9 | **Who submits.** | 17 | Must do | The Team Owner submits by hand on itch.io. No agent may press Submit. |
