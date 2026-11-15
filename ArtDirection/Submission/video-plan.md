# Gameplay video: shot list, setups and capture

**Rules** ([rules.md](rules.md)):
- **30–60 s** of **recorded gameplay**, at **1920×1080 or higher**, in English.
- The form asks for a link: use YouTube, Unlisted.
- The jam's tip: show gameplay in the first five seconds.

**Target: 55 s.** Record on Sunday, 10:15–12:00 MST, from the **rehearsal build** ([sunday-checklist.md](sunday-checklist.md)). Re-record only the shots a later fix changes.

**Names on screen** follow [canon.md](canon.md): Lanthorne, Pewterside / Giltside / Frostside, mirror shards, the Tarnish, Wren Hale. **Never show:**
- the word "London";
- concept art;
- editor UI or debug text;
- the console;
- any logo except Unreal Engine's (rule 15(d)).

## How to capture

| Method | Use it? | Why |
| --- | --- | --- |
| **The packaged build, recorded with Xbox Game Bar or the NVIDIA App** | **Yes: every shot** | Its own process, so it never touches the shared editor, its open map or the PIE lock. Real frame rate, menus and subtitles included, and the game's audio. |
| The editor binaries as a standalone game: `UnrealEditor.exe "<project>\reflections.uproject" /Game/MockCity/Lvl_MockCity -game -windowed -ResX=1920 -ResY=1080` | **Tonight only, for a rough cut** if wanted | A separate process on the current train's DLL: no PIE lock, and the open editor's map isn't switched. But it's uncooked, so the first load is slow while shaders compile. It also shares `Saved/SaveGames` with the editor, so other sessions' tests may see your checkpoint. |
| In-PIE | No | The 4-minute PIE-lock slots are shared with every session. The editor runs at about 3 fps when it isn't focused, and other sessions' scripts can change the world mid-take. |
| Movie Render Queue | Optional, one establishing shot at most | It needs the shared editor switched to the map and a Level Sequence, so only after the final package (Sunday 13:30), when no session is working. It renders a camera move, not gameplay. Keep it under 5 s of the 55, because judges want recorded play (rule 1(e)). |

### Recording set-up (once per session)

1. **Make a recording copy.** Unzip `Saved/JamBuild/Zips/rehearsal_Windows.zip` into a new folder, e.g. `C:\ReflectionsRec\`. Never record from `Saved/JamBuild/Windows`, because playing writes saves and logs into it.
2. **For shot 7 only: live talk.** Put a `keys.json` with the team's development Gemini key into `C:\ReflectionsRec\reflections\Content\NpcDialogue\Relay\` (copy `keys.json.example` and fill it in). **Delete that folder after recording.** The zip script also excludes `keys.json`, but the recording copy should never be zipped.
3. **Launch:** `C:\ReflectionsRec\reflections.exe -windowed -ResX=1920 -ResY=1080`. On a 1440p or 4K monitor you can play fullscreen and record at native resolution instead.
4. **Clean the screen.** Open the console with `` ` `` (Development builds have one) and type, one at a time:
   - `DisableAllScreenMessages` (hides debug prints)
   - `scalability 3` (Epic preset)
   - `t.MaxFPS 60`
   - `GameFlow.Tips 0` (no tutorial pop-ups mid-shot)

   Close the console before recording, and cut any frames where it shows.
5. **Recorder settings:**
   - **Xbox Game Bar:** Win+Alt+R starts and stops; clips go to `Videos\Captures`. Settings → Gaming → Captures: 60 fps, High quality, and **"Capture audio when recording a game: on, microphone off"**.
   - **Or the NVIDIA App:** Alt+F9 records. Set native resolution, 60 fps, 50 Mbps, and microphone off.
6. **Takes:** before each shot, type `GameFlow.Checkpoint`. To retake, type `GameFlow.Restart`, which reloads from that checkpoint. Stepping through and picking up pages also save checkpoints by themselves. Record each shot **3–5 times**.
7. **A gamepad** gives smoother camera moves, if you have one.

## Shot list (story order, 55 s)

| # | Time | Shot | Set-up (console in `code`) | Play |
| --- | --- | --- | --- | --- |
| 1 | 0:00–0:05 | **Cold open: a step through.** Wren runs down Bell Lane in warm Giltside, holds the key, and the flash cuts to grey Pewterside. The new side's name comes up. | New Game, then hold Space for 1 s to skip the intro. The two Pewterside shards lie on Bell Lane in front of you; pick both up. Wait until magic is full (a step costs 80). Then `GameFlow.Checkpoint`. | Run toward the camera's view, **hold Z** (pad **R3**) mid-run. Keep running after the cut: the hero keeps their exact spot. |
| 2 | 0:05–0:09 | **Title and theme.** The title screen: *REFLECTIONS*, with "Lanthorne was cut into three reflections, and only one is the version its maker meant. The Tarnish wants the final cut." | Relaunch the game; the title shows on every launch | Record **5 s** without touching anything. Judges score the theme, so the line must be readable for at least 4 s. |
| 3 | 0:09–0:15 | **The threat: tarnished sorcerers.** A tarnished townsperson with a violet aura tackles another, who rises tarnished. Both turn and throw the Tarnish's black-violet bolts and slow homing wisps at Wren. The Tarnish meter ticks up. | Giltside, Bell Square. `Villain.SpawnTestHosts 1`, then stand about 12 m from a calm person and type `Villain.Convert` (the nearest tarnished person converts the clean person nearest you). | Stand still for the tackle, then strafe as the bolts come in. Keep the meter (top right) in frame. |
| 4 | 0:15–0:21 | **Spells with weight.** Aim (reticle and preview), a Fire Bolt into a tarnished sorcerer, who ragdolls; a Water Bolt's heavy knockback into a second. | `Npc.Spawn Enemy 2 900` for two hostile targets, or `Npc.Weaken 5` to leave the nearest unnamed person on 5 health and hold it still for 15 s, for a sure one-hit kill. Spawned people are unnamed extras, so the story's people are never harmed. | Hold RMB / LT, cast with LMB / RT. Pick the spells with 1–4 (`]` for the next page). End on the body hitting the ground. |
| 5 | 0:21–0:27 | **Giltside's soldiers.** A Lamp Company column marches past. One stray spell, and the casters channel and flick their wands while the swordsmen close in. | A squad patrols 8–16 m from the start on its own. If it doesn't, type `Squads.SpawnTest 1`. Giltside squads only fight when provoked. `Squads.Reform` resets them between takes. | Film the march for 2 s, then hit one soldier. Back off so both the wand casts and the charge stay in frame. |
| 6 | 0:27–0:33 | **Spell crafting: "you direct the magic".** The crafting screen for under 2 s, then the spell Wren wrote, cast into a group. Caption in the edit: *"Your director's cut: write your own spells."* | `Crafting.Set 0 a homing ice orb that splits into three and bounces`, so the screen opens on a good spell. Point it at Shot 5's soldiers, or at `Npc.Spawn Enemy 3 900`. | **K**, show the description, Enter, **F** to equip, Esc, **5** to select, cast. |
| 7 | 0:33–0:39 | **Talk to anyone, live.** Wren asks someone on Lantern Row "Have you seen anyone with burning eyes?". They turn and answer in their own voice, with subtitles and the **AI VOICE** tag. | `keys.json` in the recording copy (set-up step 2). Walk to a named person on Lantern Row; the quest tracker points to Ilse Varrow there. Talk once off camera, so the first-use notice is gone. | **Hold T** and speak, or press **Enter** and type the line. Caption the player's line in the edit if subtitles don't show it. **If live replies fail, drop this shot.** Recorded lines don't sell "live". |
| 8 | 0:39–0:45 | **Mirror pages.** The Gilt Tower key, the sealed door opening, page 2, then a step up from inside the tower straight into the sealed Frost Tower: page 3, and the banner **"The Mirror Is Whole"**. | Play the route once: Pewterside's Weigh-House roof for page 1, then the key by the Watch post at the Lantern Gate. The page pickups save checkpoints. Wait for full magic inside the Gilt Tower, then `GameFlow.Checkpoint`. | Walk into the door with the key, grab page 2, **hold X** (pad **Y**) to step up, grab page 3. Let the MirrorWhole cutscene run for 2 s, then cut. |
| 9 | 0:45–0:53 | **Finale on the Frost crown.** The Tarnish's true form rises from the cracked glass, its telegraphed attacks land around Wren, and the Final Spell homes in. The Tarnish dissolves: *"The Tarnish is burned out. Lanthorne is itself again."* | Climb the ramps inside the Frost Tower to the crown. For retakes: `Villain.Finale` (starts the finale), `Villain.BossHere` (the boss in front of you), and `Villain.DamageBoss N` to leave it one or two Final Spells from death. `Villain.Status` shows its health; a Final Spell does 125. **Check on the rehearsal build that `Villain.Finale` also gives the Final Spell**; if not, take retakes from the page-3 checkpoint. | Dodge one telegraph, then press **F** (pad **X**) until it dies. Hold on the dissolve and the victory text for 2 s. |
| 10 | 0:53–0:56 | **End card.** *REFLECTIONS*, the team name, "Made in Unreal Engine 5.9 in four days for the 2026 Epic AI MegaJam". | Added in the edit | The Unreal Engine logo is the only logo allowed, used per Epic's branding rules |

**If a shot won't work, drop it in this order:** 7 (live talk), 5 (soldiers), 3 (conversion). Stretch shots 4 and 8 to fill. Shots 1, 2, 4, 6, 8 and 9 are the core: step-through, theme, combat, crafting, progression and the finale.

**Music and sound:** keep the game's own audio. The in-game music is Eleven Music by ElevenLabs, already credited. Add no other music and no voice-over.

## Edit and upload

1. Edit in **Clipchamp** (built into Windows 11) or DaVinci Resolve: cut to the list, then add the shot-6 caption and the end card.
2. Export H.264 at **1920×1080, 60 fps, 16–20 Mbps**. The length must read **0:30–1:00**: aim for 0:55, so a trim can't push it over.
3. Upload to YouTube as **Unlisted**:
   - **Title:** *Reflections: 2026 Epic AI MegaJam gameplay*
   - **Description:** the itch link, plus "Voices are AI-generated (Google Gemini, OpenAI)."
4. Wait for **HD processing**, then check the link in a private window and paste it into the itch page and the form.

## Who and when

A person has to play and record; agents can't drive the game smoothly enough. Allow about **105 minutes** to record (10:15–12:00) and **70 minutes** to edit and upload (13:35–14:45), per [sunday-checklist.md](sunday-checklist.md). Stills come from the same session: see [screenshots.md](screenshots.md).
