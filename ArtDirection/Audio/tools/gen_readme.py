"""Write ArtDirection/Audio/README.md from catalog.json + ue_report.json + processing reports."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog
import voice_script as VS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = r"C:\Users\zachc\Documents\Unreal Projects\reflections"
OUT = os.path.join(PROJ, "ArtDirection", "Audio", "README.md")

cat = catalog.as_dicts()
ue = json.load(open(os.path.join(ROOT, "ue_report.json")))
sfxrep = json.load(open(os.path.join(ROOT, "sfx_report.json"))) if os.path.exists(os.path.join(ROOT, "sfx_report.json")) else {}
musrep = json.load(open(os.path.join(ROOT, "music_report.json"))) if os.path.exists(os.path.join(ROOT, "music_report.json")) else {}
lev = json.load(open(os.path.join(ROOT, "proc", "final", "sources.json"))) if os.path.exists(os.path.join(ROOT, "proc", "final", "sources.json")) else {}
vrep_p = os.path.join(ROOT, "voice", "ue_report.json")
vrep = json.load(open(vrep_p)) if os.path.exists(vrep_p) else {}
extra = json.load(open(os.path.join(ROOT, "readme_extra.json"))) if os.path.exists(os.path.join(ROOT, "readme_extra.json")) else {}

OWN = {"spell": "spell-combat-rebuild", "world": "world-jump", "ui": "whoever owns menus/HUD", "npc": "NPC / enemy combat code (Codex, the user)", "villain": "villain session (possession + finale)"}
ATTN = {"Small": "ATT_Jam_Small (2 m inner, 25 m falloff)", "Medium": "ATT_Jam_Medium (4 m inner, 50 m falloff)", "Large": "ATT_Jam_Large (8 m inner, 100 m falloff)", None: "none (2D)"}

L = []
w = L.append
w("# Reflections — Jam Audio")
w("")
w("All game audio for the jam build lives under `/Game/Audio/Jam/`. Sounds come from two sources, marked per asset below: "
  "AI generation with ElevenLabs (through the ElevenLabs Creative connector), and procedural numpy synthesis used as stand-ins while "
  "the ElevenLabs free tier throttles generation. Everything was trimmed, made mono (SFX), level-matched and loop-crossfaded locally, "
  "then imported as SoundWaves. Prompts were written for this project and name no artist, franchise or game.")
w("")
w("**Gameplay code should reference the cues (`/Game/Audio/Jam/Cues/SCue_*`), not the waves.** Cues carry the sound class, "
  "attenuation, volume and the randomized variation / pitch spread.")
w("")
w("## AI declaration (for the jam submission)")
w("")
_vm_p = os.path.join(ROOT, "voice", "manifest.json")
_vm = json.load(open(_vm_p)) if os.path.exists(_vm_p) else {}
_live_ids = {l[0] for l in VS.LINES}
_eng = {}
for _id, _m in _vm.items():
    if _id not in _live_ids or _id.startswith("Narrator_"):  # the narrator moved to a Gemini designed voice
        continue
    if "engine" in _m:
        _eng[_m["engine"]] = _eng.get(_m["engine"], 0) + 1
w("- Character voices: OpenAI's realtime audio model, baked offline into WAVs (no runtime API use). Engine per line: "
  + (", ".join(f"`{e}` x{n}" for e, n in _eng.items()) if _eng else "not generated yet")
  + f"; `{VS.MODEL}` is the fallback when a take's transcript doesn't match the script. Prompts (actor rules, per-character brief, pronunciation) "
  "and every line are in `ArtDirection/Audio/VoiceScript.md`. The voices are AI-generated, not performed by actors, and the credits must say so.")
_nc_p = os.path.join(ROOT, "voice", "narrator_choice.json")
_nc = json.load(open(_nc_p)) if os.path.exists(_nc_p) else {}
_nj_p = os.path.join(ROOT, "voice", "narrator_judgement.json")
_nj = json.load(open(_nj_p)) if os.path.exists(_nj_p) else {}
if _nc:
    _tot = lambda k: sum(v for kk, v in _nj.get("scores", {}).get(k, {}).items() if isinstance(v, (int, float)))
    w(f"- Narrator ({len(_nc.get('lines', {}))} lines, `SCue_VO_Narrator_<Line>`): a Google Gemini designed voice "
      f"(`{_nc.get('GeminiVoice')}`, candidate {_nc.get('Candidate')} of 3: a retired Yorkshire lamplighter, weathered and close). "
      "It replaced the OpenAI narrator after the user found it \"too clean\". Gemini audio judging picked it "
      f"({_tot(_nc.get('Candidate', 'A'))}/50 against {_tot('OLD')}/50 for the old voice; `voice/narrator_judgement.json`). "
      "Post-processing (not AI): a quiet room-tone bed, a short warm room reverb and light saturation, with no noise gate "
      "(`tools/narrator_audition.py`). Comparison clip: `reel/Reflections_narrator_old_vs_new.mp3`.")
_gm_p = os.path.join(ROOT, "voice", "gemini", "manifest.json")
_gm = json.load(open(_gm_p)) if os.path.exists(_gm_p) else {}
_nv = len(json.load(open(os.path.join(ROOT, "voice", "roster.json"), encoding="utf-8")))
w(f"- Crowd voices ({_nv} NPC voices): Google Gemini Voice design (`gemini-3.8-flash-tts`) made one voice per character from a "
  "written brief (`ArtDirection/Audio/data/voice_roster.json`); the lines are synthesized offline with Gemini 3.8 Flash TTS "
  "and accepted only when a transcript matches the script word for word: OpenAI `gpt-4o-transcribe` for the lines made "
  "before the evening of 2026-11-14, Gemini 3.8 Flash audio transcription since then (`tools/stt_compare.py`: it passed "
  "29 of 30 takes OpenAI heard exactly and caught all 10 deliberately wrong takes, the same as OpenAI). Wordless "
  "grunts and gasps (`React_Effort`) have no words to check and are exempt. These baked lines "
  "make no API calls at runtime. The optional live-reply helper (NPC dialogue session) uses the same designed voices "
  "with a Gemini key the user supplies, and is declared in its own README. " + (f"Status: {len(_gm)} lines generated." if _gm else "Status: voices designed; lines not generated yet."))
w("- Crowd scripts: the conversations, remarks, replies, barks, possessed mutters and fillers were drafted by Google "
  "Gemini 3.8 Flash (text) from the project's canon brief, then machine-checked (never-say words, Teen-safe wording, "
  "length) and passed through an AI editor pass. Every line is unique to its speaker: `tools/uniq_check.py` fails "
  "the build on any line two characters share. The full script is `ArtDirection/Audio/AmbientScript.md`.")
w(f"- ElevenLabs ({catalog.MUS_MODEL}): only the three music loops `MUS_Gray_Loop`, `MUS_Red_Loop` and `MUS_White_Loop`. "
  "They were made on the ElevenLabs free tier, so the credits must say \"Music: Eleven Music / elevenlabs.io\", and they "
  "are on the before-sale replacement list (the free tier is not cleared for commercial use). The three ElevenLabs SFX "
  "(`Fire_Cast`, `Fire_Impact`, `Water_Impact`) were replaced by procedural versions on 2026-11-14.")
w("- Post-processing (not AI): trim, mono downmix for SFX, peak/RMS normalization, equal-power loop crossfade, slicing of multi-take clips.")
ai = [n for n, v in ue.items() if v.get("source") == "elevenlabs"]
proc = [n for n, v in ue.items() if v.get("source") == "procedural"]
w(f"- Currently AI-generated ({len(ai)}): " + ", ".join(f"`{n}`" for n in ai) + ".")
w(f"- Currently procedural stand-ins, not AI ({len(proc)}): " + ", ".join(f"`{n}`" for n in proc) + ". "
  "These are synthesized from scratch (numpy); no recorded or sampled audio is used.")
w("- No third-party or licensed audio is included in `/Game/Audio/Jam/`.")
w("")
w("## Mix setup (`/Game/Audio/Jam/Mix/`)")
w("")
w("| Asset | What it does |")
w("|---|---|")
w("| `SCL_Jam_Master` | Root sound class. |")
w("| `SCL_Jam_Music` (vol 0.7) | All music. Children: `SCL_Jam_Music_World` (world loops), `SCL_Jam_Music_Combat` (combat layer, victory sting). |")
w("| `SCL_Jam_SFX` (vol 1.0) | All gameplay sound effects. |")
w("| `SCL_Jam_UI` (vol 0.6) | Menu / HUD sounds (UI sound flag, no reverb). |")
w("| `SMX_Jam_Base` | Neutral mix with Music / SFX / UI adjusters at 1.0. Push it as the base mix and drive options sliders with `SetSoundMixClassOverride` on it. |")
w("| `SMX_Jam_Combat` | Ducks `SCL_Jam_Music_World` (the world loops) to 0.45 (1.5 s in, 2 s out) so the combat layer sits on top. Push when combat starts, pop when it ends. |")
w("| `SMX_Jam_StingerDuck` | Ducks all music to 0.3 for 3.5 s, then releases by itself. Push with the world-jump stinger and the victory sting. |")
w("| `ATT_Jam_Small` / `ATT_Jam_Medium` / `ATT_Jam_Large` | Natural-falloff spherical attenuation, distance low-pass, 2 m / 4 m / 8 m inner radius, 25 m / 50 m / 100 m falloff. |")
w("| `ATT_Jam_NPCVoice` | Speech from a position: spatialized, full volume within 3 m, natural falloff to silence by ~28 m, distance low-pass (air absorption), light occlusion. On every NPC and Tarnish voice cue; play those attached to the speaker's head bone (`SpawnSoundAttached(..., \"head\")`). The narrator and the `_Head` Tarnish variants are 2D. |")
w("| `SUB_Jam_Main` + `SFXP_Jam_Limiter` | Every jam sound class defaults to this submix; its limiter (-1.5 dB threshold, 3 ms look-ahead) keeps stacked spells over music from clipping. It feeds the master submix. |")
w("")
w("Levels are baked into the waves by a loudness pass (BS.1770 K-weighted): music loops at -20 LUFS integrated (combat layer -21, "
  "victory -17); SFX normalized on their loudest 400 ms window to per-sound targets (impacts -12 to -13 LUFS, casts -16, sword -14 to -17, "
  "pickups -18/-19, loops -22 to -25, UI -24/-30), peaks limited to -1 dBFS with at most 3 dB of gain reduction. "
  "Every cue plays at volume 1.0 and every SFX cue randomizes pitch (about +/-3 to 8%) and volume (0.92 to 1.0). "
  "Sound class volumes (music 0.7, UI 0.6) put music about 7 dB under spell casts, so nothing needs to be pushed for sound to work; the mixes are optional extras.")
w("")
w("## Final vs stand-in")
w("")
w("| Cue | Status |")
w("|---|---|")
for _n, _v in ue.items():
    _st = "**final** (ElevenLabs)" if _v.get("source") == "elevenlabs" else "stand-in (procedural; ElevenLabs take queued)"
    w(f"| `SCue_{_n}` | {_st} |")
w("")
w("## Event → sound map")
w("")
w("| Event | Play this | How | Owner |")
w("|---|---|---|---|")
for s in cat["sfx"] + cat["music"]:
    r = ue.get(s["name"])
    if not r:
        continue
    how = []
    if s in cat["music"]:
        how.append("2D, looping" if s["loop"] else "2D one-shot")
    else:
        if s["loop"]:
            how.append("spawn attached, looping — stop/fade it out when the effect ends")
        elif s["att"]:
            how.append("PlaySoundAtLocation / SpawnSoundAttached")
        else:
            how.append("PlaySound2D")
    w(f"| {s['event']} | `{r['cue']}` | {', '.join(how)} | {OWN[s['owner']]} |")
w("")
w("## Sound effects")
w("")
w("Generator: " + catalog.SFX_MODEL + ". Waves are mono 44.1 kHz, peak-normalized to -1 dBFS; levels are set on the cue.")
w("")
for s in cat["sfx"]:
    r = ue.get(s["name"])
    if not r:
        continue
    w(f"### {s['name']}")
    w("")
    w(f"- Cue: `{r['cue']}` — class `SCL_Jam_{s['cls']}`, attenuation {ATTN[s['att']]}, volume {s['vol']}"
      + (f", pitch {s['pitch'][0]}–{s['pitch'][1]}" if s["pitch"] else "") + (", looping" if s["loop"] else ""))
    w(f"- Waves ({len(r['waves'])}): " + ", ".join(f"`{p.split('/')[-1]}` ({d:.2f} s)" for p, d in zip(r["waves"], r["dur"])))
    if s["name"] in lev:
        lv = lev[s["name"]]
        w(f"- Loudness: target {lv['target_lufs']} LUFS momentary max; result " + ", ".join(str(f["out_lufs"]) for f in lv["files"]) + " (peaks <= -1 dBFS)")
    if r.get("source") == "procedural":
        src = f"- Source: **procedural stand-in** (not AI): numpy synthesis, `synth.py` function `S_{s['name']}`"
        w(src + ". Will be replaced in place by the ElevenLabs take below when the free tier allows.")
        w(f"- Queued ElevenLabs prompt: \"{s['prompt']}\"")
    else:
        w(f"- Source: **ElevenLabs** ({catalog.SFX_MODEL})")
        w(f"- Prompt: \"{s['prompt']}\"")
        gen = f"- Generation: {s['gen_s']} s requested, prompt influence {s['influence']}" + (", loop mode on" if s["loop"] else "")
        if s.get("multi"):
            gen += "; one clip holding several separate takes, sliced into variations on silence"
        w(gen)
    if s["name"] in extra:
        w(f"- Note: {extra[s['name']]}")
    w("")
w("## Music")
w("")
w("Generator: " + catalog.MUS_MODEL + ". Stereo 48 kHz. Loops are cut before the model's outro and closed with an equal-power "
  "crossfade at a point matched on the spectral/onset envelope, so they wrap without a gap or click.")
w("")
for m in cat["music"]:
    r = ue.get(m["name"])
    if not r:
        continue
    info = musrep.get(m["name"], {})
    w(f"### {m['name']}")
    w("")
    w(f"- Cue: `{r['cue']}` — class `SCL_Jam_{m['cls']}`, volume {m['vol']}" + (", looping" if m["loop"] else ""))
    w(f"- Wave: `{r['waves'][0].split('/')[-1]}` ({r['dur'][0]:.1f} s" + (", loop" if m["loop"] else "") + ")")
    if m["name"] in lev:
        w(f"- Loudness: {lev[m['name']]['files'][0]['out_lufs']} LUFS integrated")
    if r.get("source") == "procedural":
        w(f"- Source: **procedural stand-in** (not AI): numpy synthesis, `synth_music.py`. Will be replaced in place by the ElevenLabs take below.")
        w(f"- Queued ElevenLabs prompt: \"{m['prompt']}\"")
    else:
        w(f"- Source: **ElevenLabs** ({catalog.MUS_MODEL})")
        w(f"- Prompt: \"{m['prompt']}\"")
        w(f"- Generation: {m['gen_s']} s requested, instrumental")
    if info.get("start_s") is not None and m["loop"] and r.get("source") != "procedural":
        w(f"- Loop: source {info['start_s']:.2f}–{info['E_s']:.2f} s, crossfade match score {info['match']:.2f}")
    if m["name"] in extra:
        w(f"- Note: {extra[m['name']]}")
    w("")
w("## Voices (OpenAI realtime audio model)")
w("")
w("Model: OpenAI realtime audio (see the AI declaration above). Waves: `/Game/Audio/Jam/Voice/<Group>/SW_VO_<LineId>` (mono 24 kHz, trimmed, character FX, leveled, subtitles set). "
  "Cues: `/Game/Audio/Jam/Voice/Cues/`. NPC and Tarnish voices are 3D (`ATT_Jam_NPCVoice`, attach to the speaker's head); the narrator and `SCue_VO_Tarnish_Taunt_Head` / `_Hop_Head` are 2D. Sound class `SCL_Jam_Voice` routes through the jam limiter. Concurrency: `SCON_Jam_Barks` "
  "(3 at a time, 0.5 s retrigger), `SCON_Jam_Tarnish` and `SCON_Jam_Narrator` (one at a time). "
  + ("Status: generated and imported." if vrep else "Status: **planned**; generation waits for the user's API key."))
w("")
w("| Cue | Lines | When | Owner |")
w("|---|---|---|---|")
_seen = set()
for g, (owner, event, mode) in VS.GROUPS.items():
    if VS.base_group(g) != g:
        b = VS.base_group(g)
        if b in _seen:
            continue
        _seen.add(b)
        og, ev, _d, _fx, n, _pool = VS.NPC_GROUPS[b]
        who = {"villain": "villain session", "npc": "npc-unify (NPC reactions)", "soldier": "soldier-squads", "talk": "NPC dialogue session (talk-back fallback)", "gameflow": "game-flow-ui"}[og]
        w(f"| `SCue_VO_{b}_<F1..F3,M1..M3>` (+ fallback `SCue_VO_{b}`) | {n} per voice slot | {ev} | {who} |")
        continue
    lines = [l for l in VS.LINES if l[1] == g]
    who = {"villain": "villain session", "npc": "npc-unify (NPC reactions)", "soldier": "soldier-squads", "talk": "NPC dialogue session (talk-back fallback)", "gameflow": "game-flow-ui"}[owner]
    if mode == "random":
        w(f"| `SCue_VO_{g}` | {len(lines)} (random) | {event} | {who} |")
    else:
        for l in lines:
            w(f"| `SCue_VO_{l[0]}` | 1 | \"{l[3]}\" | {who} |")
w("")
w("Full line list, voices and delivery instructions: `ArtDirection/Audio/VoiceScript.md`.")
w("")
w("## Crowd voices (Gemini roster, one voice per NPC)")
w("")
w(f"{_nv} designed voices (`DT_NpcVoiceRoster`, row name = VoiceId `V001`–`V{_nv:03d}`; NPC unify picks one per NPC by sex, side and "
  "character). Every cue is 3D (`ATT_Jam_NPCVoice`, attach to the head), class `SCL_Jam_Voice`. Cue path: "
  "`/Game/Audio/Jam/Voice/Cues/<Group>/SCue_VO_<Group>_<VoiceId>`, found by `FindVoiceCue(Actor, Group)` before the "
  "6-slot cues above. No line is shared between two voices.")
w("")
w("| Group | Voices | Lines per voice | When | Owner |")
w("|---|---|---|---|---|")
for _g, _v, _n, _when, _who in [
        ("Remark", "all", 2, "calm NPC, player within ~4.5 m, 60–90 s cooldown", "npc-unify"),
        ("Reply", "all", 3, "the player talks to the NPC (Talk resolves here)", "NPC dialogue session"),
        ("Filler", "all", 2, "short beat before a reply", "NPC dialogue session"),
        ("Civilian_Fear", "civilians", 3, "flee / hit / sees the tarnished", "npc-unify"),
        ("Guard_Alert", "guards", 3, "guard enters Alert", "npc-unify"),
        ("Guard_Attack", "guards", 2, "guard starts attacking", "npc-unify"),
        ("Soldier_Command", "soldiers", 4, "squad commands in combat", "soldier-squads"),
        ("Tarnished_Mutter", "all", 2, "after the NPC is taken (tarnished FX baked in)", "npc-unify"),
        ("React_Hurt", "all", 2, "hit, neither killed nor thrown", "npc-unify"),
        ("React_Knocked", "all", 2, "thrown by a blast or water and survives", "npc-unify"),
        ("React_Burning", "all", 3, "on fire: at the start, then every 1.5-2.5 s while burning", "npc-unify"),
        ("React_Shocked", "all", 2, "a lightning hit starts the convulsion", "npc-unify"),
        ("React_Death", "all", 2, "a lethal hit (instead of the fear or alert bark)", "npc-unify"),
        ("React_Effort", "all", 2, "wordless grunts (no trigger yet)", "npc-unify"),
        ("Heat_CallGuards", "civilians", 2, "a witness of an assault or murder by the player", "npc-unify"),
        ("Heat_Halt", "guards", 3, "a guard turns on the player", "npc-unify"),
        ("Heat_Alarm", "soldiers", 2, "a soldier turns on the player; a squad's retaliation", "npc-unify, soldier-squads"),
        ("Soldier_Charge", "soldiers", 2, "the squad breaks formation to engage (leader)", "soldier-squads"),
        ("Soldier_Hold", "soldiers", 1, "casters open a volley", "soldier-squads"),
        ("Soldier_AllyDown", "soldiers", 1, "a squadmate is killed (nearest comrade)", "soldier-squads"),
        ("Soldier_EnemyDown", "soldiers", 2, "the squad's target is killed", "soldier-squads"),
        ("Soldier_Retreat", "soldiers", 1, "standing down after losing the target", "soldier-squads"),
        ("Soldier_Victory", "soldiers", 1, "target dead and nobody left to fight", "soldier-squads")]:
    w(f"| `{_g}` | {_v} | {_n} | {_when} | {_who} |")
w("")
_hc_p = os.path.join(ROOT, "voice", "hero_choice.json")
_hc = json.load(open(_hc_p)) if os.path.exists(_hc_p) else {}
_st_p = os.path.join(ROOT, "voice", "script", "story.json")
_st = json.load(open(_st_p, encoding="utf-8")) if os.path.exists(_st_p) else {}
w("## Story voices (ArtDirection/Story)")
w("")
w(f"- **Scripted lines:** {len(_st.get('Scripted', {}))} main-quest, side-quest and cutscene lines as `/Game/Audio/Jam/Voice/Cues/SCue_VO_<LineId>` "
  "(waves in `/Game/Audio/Jam/Voice/Story/`). Cutscene cues and 2D lines (MQ07_02, MQ_BAND_01-03, MQ_LOSE_01, Wren's quest lines) "
  "have no attenuation; MQ09_01-05 and townspeople's quest lines use `ATT_Jam_NPCVoice`. MQ05_01/CS03_03 and MQ05_02/CS03_04 share one take.")
w(f"- **Wren Hale (hero):** Gemini designed voice `{_hc.get('GeminiVoice', 'not chosen')}` (candidate {_hc.get('Candidate', '?')}). "
  "The user asked for a unique, captivating designed voice (never the original); four candidates read the same lines and "
  "Gemini's audio understanding picked B (`voice/hero_judgement.json`).")
w("- **The Tarnish:** its story lines use its existing OpenAI voice and FX, matching the lines already in the game.")
w(f"- **Named people ({len(_st.get('Map', {}))}):** each has a reserved roster voice (`bEnabled = false` in `DT_NpcVoiceRoster`) and story barks "
  "as groups Greet, Idle, SeeTarnished, Flee, SpellNear, Thanks, Dread, Farewell, Cured, TarnishedLine (`/Cues/<Group>/SCue_VO_<Group>_<VoiceId>`), "
  "also fed into Civilian_Fear, Remark, Reply and Tarnished_Mutter. Story-clique conversations are in `/Game/Audio/Jam/Voice/Ambient/DT_StoryConversations` "
  "(played by lives via PlayConversationById, with Band and RequiredFlag).")
w("- **Fill voices:** reserving the named people's voices left gaps, so extra unnamed voices were added: V121-V132 "
  "(Pewterside civilians, `tools/add_pewterside.py`) and V133-V137 (women guards: 2 Giltside, 2 Pewterside, 1 Frostside, "
  "`tools/add_guards.py`). Before V133-V137, every Giltside and Pewterside women's guard voice was reserved, so a third unnamed "
  "woman guard fell back to a civilian voice.")
w("- **Acceptance:** a take is kept when a transcript matches the script word for word, or letter for letter once spacing, "
  "apostrophes and interjections are ignored; any spelling of \"Silverer\" passes (user decision). A few takes whose only difference "
  "is a misheard name or accent word are kept with a note in `voice/gemini/manifest.json`.")
w("")
w("Street conversations: `/Game/Audio/Jam/Voice/Ambient/<CliqueId>/SW_AMB_<ConvId>_<n>`, listed in "
  "`/Game/Audio/Jam/Voice/Ambient/DT_AmbientConversations` for the crowd director (48 cliques × 6 conversations).")
w("")
if extra.get("_gaps"):
    w("## Not generated / known gaps")
    w("")
    for g in extra["_gaps"]:
        w(f"- {g}")
    w("")
w("## Size")
w("")
w(extra.get("_size", ""))
w("")
w("## Regenerating")
w("")
w("The ElevenLabs flow is id `NoxuIlopg9X9ZlS5daRm` (one node per sound, labelled with the sound name). The scripts are in "
  "`ArtDirection/Audio/tools/` (Python 3 + numpy; MP3 decoding uses the engine's bundled libsndfile). Set `ROOT` to a work folder, then: "
  "`fetch.py` downloads a take, `process_sfx.py` / `process_music.py` trim, mono-mix, normalize, slice and loop it, `synth.py` / "
  "`synth_music.py` render the procedural stand-ins, `ue_build.py` (exec'd in the editor's Python) imports the waves and rebuilds the cues "
  "in place, and `gen_readme.py` rewrites this file from `catalog.py`.")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print(OUT, len(L), "lines")
