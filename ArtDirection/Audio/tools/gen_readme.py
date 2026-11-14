"""Write ArtDirection/Audio/README.md from catalog.json + ue_report.json + processing reports."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = r"C:\Users\zachc\Documents\Unreal Projects\reflections"
OUT = os.path.join(PROJ, "ArtDirection", "Audio", "README.md")

cat = catalog.as_dicts()
ue = json.load(open(os.path.join(ROOT, "ue_report.json")))
sfxrep = json.load(open(os.path.join(ROOT, "sfx_report.json"))) if os.path.exists(os.path.join(ROOT, "sfx_report.json")) else {}
musrep = json.load(open(os.path.join(ROOT, "music_report.json"))) if os.path.exists(os.path.join(ROOT, "music_report.json")) else {}
lev = json.load(open(os.path.join(ROOT, "proc", "final", "sources.json"))) if os.path.exists(os.path.join(ROOT, "proc", "final", "sources.json")) else {}
extra = json.load(open(os.path.join(ROOT, "readme_extra.json"))) if os.path.exists(os.path.join(ROOT, "readme_extra.json")) else {}

OWN = {"spell": "spell-combat-rebuild", "world": "world-jump", "ui": "whoever owns menus/HUD", "npc": "NPC / enemy combat code (Codex, the user)", "villain": "villain session (possession + finale)"}
ATTN = {"Small": "ATT_Jam_Small (2 m inner, 25 m falloff)", "Medium": "ATT_Jam_Medium (4 m inner, 50 m falloff)", "Large": "ATT_Jam_Large (8 m inner, 100 m falloff)", None: "none (2D)"}

L = []
w = L.append
w("# Three Londons — Jam Audio")
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
w(f"- Sound effects: {catalog.SFX_MODEL}. One text prompt per sound, listed below.")
w(f"- Music: {catalog.MUS_MODEL}. One text prompt per track, listed below.")
w("- Post-processing (not AI): trim, mono downmix for SFX, peak/RMS normalization, equal-power loop crossfade, slicing of multi-take clips.")
ai = [n for n, v in ue.items() if v.get("source") == "elevenlabs"]
proc = [n for n, v in ue.items() if v.get("source") == "procedural"]
w(f"- Currently AI-generated ({len(ai)}): " + ", ".join(f"`{n}`" for n in ai) + ".")
w(f"- Currently procedural stand-ins, not AI ({len(proc)}): " + ", ".join(f"`{n}`" for n in proc) + ". "
  "`Sword_Hit` also layers Epic's Game Animation Sample foley punches that were already in the project.")
w("- No third-party or licensed audio is included in `/Game/Audio/Jam/`.")
w("")
w("## Mix setup (`/Game/Audio/Jam/Mix/`)")
w("")
w("| Asset | What it does |")
w("|---|---|")
w("| `SCL_Jam_Master` | Root sound class. |")
w("| `SCL_Jam_Music` (vol 0.7) | All music. Children: `SCL_Jam_Music_World` (London loops), `SCL_Jam_Music_Combat` (combat layer, victory sting). |")
w("| `SCL_Jam_SFX` (vol 1.0) | All gameplay sound effects. |")
w("| `SCL_Jam_UI` (vol 0.6) | Menu / HUD sounds (UI sound flag, no reverb). |")
w("| `SMX_Jam_Base` | Neutral mix with Music / SFX / UI adjusters at 1.0. Push it as the base mix and drive options sliders with `SetSoundMixClassOverride` on it. |")
w("| `SMX_Jam_Combat` | Ducks `SCL_Jam_Music_World` to 0.45 (1.5 s in, 2 s out) so the combat layer sits on top. Push when combat starts, pop when it ends. |")
w("| `SMX_Jam_StingerDuck` | Ducks all music to 0.3 for 3.5 s, then releases by itself. Push with the world-jump stinger and the victory sting. |")
w("| `ATT_Jam_Small` / `ATT_Jam_Medium` / `ATT_Jam_Large` | Natural-falloff spherical attenuation, distance low-pass, 2 m / 4 m / 8 m inner radius, 25 m / 50 m / 100 m falloff. |")
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
        if s["name"] == "Sword_Hit":
            src += ", layered over the project's GASP foley punches `/Game/Audio/Foley/SoundWaves/Combat/foley_punch_01..03` (Epic Game Animation Sample)"
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
w("The ElevenLabs flow is \"Three Londons - Jam Audio\" (one node per sound, labelled with the sound name). The scripts are in "
  "`ArtDirection/Audio/tools/` (Python 3 + numpy; MP3 decoding uses the engine's bundled libsndfile). Set `ROOT` to a work folder, then: "
  "`fetch.py` downloads a take, `process_sfx.py` / `process_music.py` trim, mono-mix, normalize, slice and loop it, `synth.py` / "
  "`synth_music.py` render the procedural stand-ins, `ue_build.py` (exec'd in the editor's Python) imports the waves and rebuilds the cues "
  "in place, and `gen_readme.py` rewrites this file from `catalog.py`.")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print(OUT, len(L), "lines")
