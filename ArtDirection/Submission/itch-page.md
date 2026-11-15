# itch.io page draft: *Reflections*

Paste-ready text for the project page (Dashboard → Create new project), using the chosen names ([originality.md](originality.md)). Fields in **[brackets]** need a human. Controls marked ✔ are confirmed by the owning session; ○ came from code and still needs confirming.

Before posting, check the page never says "London", "Three Londons", or the book's or author's name.

**Final text as of 2026-11-14 ~19:00.** On Sunday, remove the feature bullet for anything that failed the smoke test ([sunday-checklist.md](sunday-checklist.md#smoke-test-15-minutes)):

| Feature bullet | Proven by |
| --- | --- |
| One city, three sides | Smoke steps 4 and 6 |
| Spells with weight | Step 5 |
| Spell crafting | Step 8 |
| The tarnished | Video shot 3 (`Villain.Convert`) |
| Soldiers in the streets | Video shot 5 |
| People with lives, and talk to anyone | Steps 4 and 7 |
| Mirror pages and the finale | Video shots 8 and 9 |

If the zip ships without the Gemini helper (for example, if Defender flagged it), cut the "With your own Google Gemini API key…" sentence and the privacy note down to: "People answer with recorded lines; the game makes no network calls to talk."

---

## Page settings

| Field | Value |
| --- | --- |
| Title | **Reflections** |
| Project URL | `[team-account].itch.io/reflections` |
| Short description / tagline | Three reflections of one city, and a Tarnish creeping through all of them. |
| Classification | Games |
| Kind of project | Downloadable |
| Release status | Prototype |
| Pricing | No payments |
| Upload | `[TeamName]_Reflections.zip`, tagged **Windows**. Mark it as the executable download. |
| Genre | Action |
| Tags | `magic`, `third-person`, `parallel-worlds`, `spellcasting`, `unreal-engine`, `fantasy`, `atmospheric`, `game-jam` |
| AI generation disclosure | **Yes**: code, animation, audio, voices and concept art used generative AI, and optional live NPC replies use Google Gemini (see [ai-declaration.md](ai-declaration.md)) |
| Jam | Join the jam first (tonight, [sunday-checklist.md](sunday-checklist.md) T6). Set the page **Public**, then submit to **2026 Epic AI MegaJam** |
| Cover image | 630×500 (shown at 315×250): Wren mid-cast in Giltside, title in the top third ([screenshots.md](screenshots.md#cover-image)) |
| Screenshots | 6, at 1920×1080, in the order in [screenshots.md](screenshots.md) |
| Gameplay video | YouTube link from [video-plan.md](video-plan.md) |

---

## Description (paste from here)

> **Reflections** · made in four days for the 2026 Epic AI MegaJam
>
> Lanthorne has three reflections. **Pewterside** is grey and dull. **Giltside** is warm and lantern-lit. **Frostside** is cracked, bleached and cold. They share every street and every stone. Something called **the Tarnish** is creeping through all three, taking over faces one by one.
>
> You are **Wren Hale, the Silverer**, one of the few who can step through the glass. Every step costs most of your magic and a **mirror shard** of the side you're going to. Your silvered coat takes on each side's light.
>
> Lanthorne was cut into three reflections, and only one is the version its maker meant. The Tarnish wants the final cut.
>
> **Our director's cut:** spell crafting, the feature we kept scoping out, finally made it in, and now you direct the magic. Describe a spell or build it from parts, and cast what you wrote. **[team: confirm "kept scoping out" is true for you, or reword]**
>
> ### Features
> - **One city, three sides.** Same streets, different light, people and dangers. Step through mid-run and keep your exact spot: drop into Pewterside to reach a roof, or step up inside one tower and arrive inside another.
> - **Spells with weight.** Aim and cast fire, water, lightning, ice, earth, arcane and healing, each with its own cast animation, reticle preview and impact. Bodies ragdoll, and water knocks people flat.
> - **Spell crafting.** Combine a form (bolt, orb, ray, nova, wave, rain, rune, aura), an element, up to three behaviours (split, bounce, pierce, chain, gravity, homing, echo…) and a trigger into thousands of spells, then cast them from four slots.
> - **The tarnished.** The people the Tarnish takes become dark sorcerers. They hurl its black-violet bolts and slow homing wisps at you, and tackle townspeople to turn them. If the Tarnish meter fills, Lanthorne is lost.
> - **Soldiers in the streets.** Giltside's Lamp Companies march the lanes and fight only if provoked. Frostside's soldiers attack on sight. Casters channel and flick their wands; swordsmen close in.
> - **People with lives.** Dozens of named townsfolk keep homes, routines and conversations, in more than 130 distinct AI-generated voices. **Talk to anyone**: hold T and speak, or type.
> - **Mirror pages and the finale.** Follow the main quest across all three sides for the three hidden pages: a rooftop, a sealed tower and the tower behind it. Make the mirror whole, then face the Tarnish's true form on the Frost crown with the Final Spell.
>
> ### AI voices
> Every voice in the game is AI-generated, not performed by actors. Lanthorne's people, Wren and the story are spoken in more than 130 voices designed with **Google Gemini**. The Tarnish and the narrator use **OpenAI** voice models. Every line was generated ahead of time and checked word for word against the script.
>
> **Talk to anyone.** Hold T and speak, or press Enter and type. With your own Google Gemini API key, people answer live in their own voice: **gemini-3.5-transcribe-live** hears you, **gemini-3.5-flash-lite** writes the reply, and **gemini-3.8-flash-tts** speaks it. Without a key, they answer with recorded lines.
>
> ### Privacy: talking to people
> - **Nothing is sent unless you add a key.** The download contains no API key. Live replies switch on only if you put your own Google Gemini key in `keys.json`. To do that, copy `keys.json.example` (in `reflections\Content\NpcDialogue\Relay\` inside the game folder) to `keys.json` and paste the key in. Google's Gemini API terms require you to be 18 or older.
> - **Only when you talk to someone.** With a key, the game sends data while you hold T or when you send a typed line. Nothing is sent at any other time.
> - **What's sent, and to whom.** It goes to **Google**, straight from your PC, under your key and Google's terms. It contains your speech (streamed only while you hold T) or your typed line, that person's in-game details and your recent conversation with them, and the reply text, which Google checks and turns into speech. We run no server and receive none of it.
> - **What stays on your PC.** Generated replies are saved with the text of the line that prompted them, so a person can reuse a reply that fits. Your audio isn't kept. The key is read only by the small helper program the game starts. It's sent only to Google, in a request header, and never written to a log.
> - **What the game tells you.** The first time you talk, it says so ("What you say to them is sent to Google to make their reply"), and every live reply is tagged **AI VOICE**.
> - **Without a key,** people answer with recorded lines, and talking makes no network calls.
>
> **[Use this instead of the first bullet only if the team ships a dedicated key in the zip:]** "The jam build includes a capped key for judging, so live replies work out of the box. It will be switched off after judging."
>
> ### Controls
> **[table below]**
>
> ### Requirements
> Windows 10 or 11 (64-bit), a DirectX 12 GPU with Shader Model 6. Details below.
>
> ### Credits
> **[Team name]**: **[member names and roles]**
> Directed by **[Team name]** and built with AI agents in Unreal Engine 5.9.
>
> - Code: Claude Code (Anthropic), OpenAI Codex
> - Wardrobe textures and references: OpenAI image generation
> - 3D garments: Tencent Hunyuan3D-2 (Powered by Tencent Hunyuan)
> - Spell animations: NVIDIA Kimodo text-to-motion (Kimodo-SOMA-RP-v1.1, licensed by NVIDIA Corporation under the NVIDIA Open Model License)
> - Characters: Epic MetaHuman Creator
> - Character voices: AI-generated with Google Gemini (designed voices, Gemini 3.8 Flash TTS) and OpenAI (gpt-realtime-2.1, gpt-4o-mini-tts), not human actors
> - Live NPC replies: Google Gemini (gemini-3.5-transcribe-live, gemini-3.5-flash-lite, gemini-3.8-flash-tts). What you say to NPCs is sent to Google.
> - Music: Eleven Music by ElevenLabs (elevenlabs.io)
> - Fire and water spell sounds: ElevenLabs (elevenlabs.io); all other sounds procedurally synthesized
> - Built on Epic's Game Animation Sample and Third Person template
> - Map data © OpenStreetMap contributors, ODbL ([openstreetmap.org/copyright](https://www.openstreetmap.org/copyright)). The derived map data and the scripts that made it: **[link, Jah]**
> - Landmark models adapted from [Codriver 3D](https://3d-assets.codriver.io/), CC BY 4.0
> - Albert Memorial scan by artfletch ([Zenodo](https://zenodo.org/records/10307114)), CC BY 4.0 · Street props by Minimaliano (Fab), CC BY 4.0
> - Textures and props: [Poly Haven](https://polyhaven.com/) (CC0) · Trees: [Cosmo Tree Gen](https://github.com/FrogCosmonaut/cosmo_tree_gen) by FrogCosmonaut (MIT) · Signs set in Noto Serif (SIL OFL 1.1)
> - Full licence notices: `THIRD_PARTY_NOTICES.txt` in the download
>
> **Sourced and pre-jam content:** Epic's Game Animation Sample (locomotion, mannequins, prototype blocks), the Unreal Engine Third Person template, Epic MetaHuman presets and grooms, and the team's own blood-impact effect from an earlier project. The city map is generated from OpenStreetMap data, with landmark models from Codriver 3D, an Albert Memorial scan by artfletch, and Poly Haven and Fab street assets (all credited above). Everything else was made during the jam. **[Drop the blood-impact clause if the effect is replaced before the final build.]**

---

## Controls

| Action | Keyboard & mouse | Gamepad (Xbox layout) | Source |
| --- | --- | --- | --- |
| Move | W A S D | Left stick | ✔ spells session, from `IMC_Sandbox` |
| Look | Mouse | Right stick | ✔ spells |
| Jump | Space | A | ✔ spells |
| Sprint (hold) | Left Shift | L3 (click left stick) | ✔ spells; hold per `IA_Sprint` triggers |
| Walk (toggle) | Left Ctrl | Tilt the stick partway | ✔ spells; toggle per the input assets ([checks.md](checks.md#3-walk-crouch-and-strafe-hold-or-toggle)), not yet verified in build |
| Crouch (toggle) | C | B | ✔ spells; toggle per the input assets, not yet verified in build |
| Strafe (toggle) | Middle mouse button | — | ✔ spells; toggle per the input assets, not yet verified in build |
| Aim | Right mouse (hold) | LT (hold) | ✔ in-game hint, `ReflectionsSpellHud.cpp:274-275` |
| Cast selected spell (hold to repeat) | Left mouse or Q | RT | ✔ in-game hint |
| Select spell 1–4 | 1 2 3 4 | — | ✔ in-game hint |
| Next / previous spell | Tab / Shift+Tab | RB / LB | ✔ in-game hint |
| Next / previous spell page | ] / [ | D-pad Right / Left | ✔ in-game hint |
| Open spell crafting | K | View (⧉) | ✔ in-game hint, `ReflectionsSpellCraftingScreen.cpp:435` |
| Select crafted spell 5–8 | 5 6 7 8 | D-pad Up | ✔ in-game hint |
| Crafting screen | ↑↓ move · ←→ change · Enter next · Q/E slot · R new look · F equip · Esc close | Stick/D-pad · A next · LB/RB slot · X new look · Y equip · B close | ✔ screen footer, `ReflectionsSpellCraftingScreen.cpp:258` |
| Step up into the next side | X (hold 0.25 s) | Y (hold) | ✔ world-jump HUD prompt |
| Step down into the previous side | Z (hold 0.25 s) | R3 (hold) | ✔ world-jump HUD prompt |
| Pick up mirror pages, shards, keys | Walk over them | Walk over them | ✔ world-jump. There's no interact button, and sealed doors open when you reach them carrying the key. |
| Free the mouse cursor (HUD buttons) | Right Alt (hold) | — | ✔ in-game hint |
| Talk to someone nearby | Hold T and speak, or Enter to type a line | Hold D-pad Down | ✔ NPC dialogue session. Live replies use Google Gemini and need the player's own key; without one, people answer with recorded lines. |
| Final Spell (once the mirror is whole; homes on the Tarnish) | F | X (left face button) | ✔ villain-finale, `ReflectionsFinalSpell.cpp:101-102` |
| Pause / menu (P or Start also closes it) | Esc or P | Start (☰) | ✔ game-flow-ui |
| Menus | Arrows to move · Enter / Space to select · Esc to go back · mouse hover and click | D-pad or left stick · A select · B back | ✔ game-flow-ui |

Leave off the page: the **arrow keys** (the sample's debug movement), and **V** / **1–4** on the legacy `ReflectionsHeroCharacter`, which isn't the jam hero. Before publishing, play the final build once to check walk, crouch and strafe (hold or toggle).

## Minimum system requirements

Only one machine has run it: **Windows 11, AMD Ryzen 7 9700X, 32 GB RAM, NVIDIA RTX 5080**. The game log there showed 0 errors. Nobody has run it on lower-end hardware, so the figures below are **estimates** from the project's render settings (DX12, Shader Model 6 only, Lumen global illumination and reflections, ray tracing enabled), not measurements.

| | Minimum (estimate) | Recommended (estimate) |
| --- | --- | --- |
| OS | Windows 10 64-bit (22H2) or Windows 11 | Windows 11 |
| CPU | 6 cores, e.g. Ryzen 5 3600 / Core i5-10600 | 8 cores, e.g. Ryzen 7 5800X / Core i7-12700 |
| RAM | 16 GB | 16–32 GB |
| GPU | DirectX 12 with Shader Model 6 and 6 GB VRAM, e.g. GTX 1660 Super / RX 5600 XT | 8 GB+ VRAM, e.g. RTX 3060 Ti / RX 6700 XT |
| Disk | 3 GB free (the train #5 zip was 0.73 GB and unpacked to 1.1 GB; **re-measure the final zip on Sunday** and update this) | SSD |

To turn the estimates into facts, a teammate with an older GPU runs the zip and notes the FPS before Sunday 2 PM.

## Screenshots

**The list to shoot on Sunday is in [screenshots.md](screenshots.md):** 6 stills plus the cover, all from the rehearsal build's recording copy. The table below covers the existing captures, which come from **test maps and the GASP sample**: graybox floors, grid cubes, and the old "RED LONDON" banners. Use one only if Sunday's shots fail, and never one marked No:

| # | File | Size | Shows | Usable? |
| --- | --- | --- | --- | --- |
| 1 | `Saved/Screenshots/WindowsEditor/HighresScreenshot00008.png` | 2510×1339 | Hero in a crowd, fireball mid-air | **Yes**: best of the set, no HUD |
| 2 | `ArtDirection/SpellVFX/FireImpact_NPCTest.png` | 2510×1339 | Fireball impact on an NPC, crowd | **Yes** (no HUD) |
| 3 | `Saved/SpellCombatTest/heal_greater_2.png` | 1600×857 | Greater Heal swirl with full HUD | Yes, but upscale, or crop to 16:9 at 1600 wide |
| 4 | `Saved/SpellCraftingShots/06_screen_rain.png` | 1600×545 | Spell-crafting screen over gameplay | Crop only; the ultra-wide strip is too short |
| 5 | `Saved/Screenshots/WindowsEditor/Hero_Sandbox_Levitation.png` | 1600×900 | Hero levitating | Yes |
| 6 | `Saved/Screenshots/WindowsEditor/CrowdLooks_QA.png` | 1600×900 | Three costumed townsfolk | Character sheet, not gameplay. Dev log only. |
| 7 | `ArtDirection/WorldJump/Screenshots/07_red_rooftop.png` | 1600×857 | World jump arrival on a rooftop | **No**: "RED LONDON" banner and HUD text |
| 8 | `Saved/JamBuild/Logs/launch_matched.png` | 1944×1139 | The packaged build running | No: window frame and graybox. Dev log only. |

Don't use any concept art from `ArtDirection/Three-Londons*` on the page. It's titled with the old names, and the hero coat art was prompted with the book's name.

## Credits and asset list (for the page footer)

The credits and the sourced-content line are now **inside the description** above, word for word from [ai-declaration.md](ai-declaration.md#credits-block-the-source-for-the-itch-page-and-game-flow-uis-creditsvictory-panel). The in-game `Credits.Tools` matches them. The long sourced-asset list for the **submission form** is in [ai-declaration.md](ai-declaration.md#sourced-and-pre-jam-material).
