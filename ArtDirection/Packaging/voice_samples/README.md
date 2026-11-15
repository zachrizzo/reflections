# Voice size options: listen before choosing

Packaging, Sun 15 Nov ~02:40. Nothing in the game was changed: no SoundWave setting and no config. These are WAV exports of six shipped lines (editor `SoundWaveToolset.ExportWav`), plus band-limited copies.

## Listen

**`ALL_lines_A24k_B16k_C12k.wav`** (114 s) plays each line three times, then a longer pause before the next line:
1. **A**: as it ships now (24 kHz).
2. **B**: what a 16 kHz cook keeps (up to ~8 kHz).
3. **C**: what a 12 kHz cook keeps (up to ~6 kHz).

The order is Ambient bark (muster yard), Roster reply (V057), Tarnish cutscene line (CS02_04), Narrator, Story SQ5_01, Story SQ5_10. Each line also has its own `__A_ / __B_ / __C_` files.

Only the lost bandwidth is reproduced here. The cooked build also adds Bink Audio codec artifacts, which can't be made outside the engine, so the real B and C will sound slightly worse than these files.

## What the numbers say (measured on tonight's 01:10 build)

- **Size:** voice is **103.5 MB** in the pak: 3,435 SoundWaves (102.4 MB), plus cues.
  - Ambient barks (1,330 waves, 108 min): 43.4 MB.
  - Roster lines (1,831 waves, 123 min): 50.5 MB.
  - Story, narrator, cutscenes and the rest: ~9 MB.
- **Format:** every wave was imported at **24 kHz mono**. The project's 48 kHz maximum doesn't upsample, so the game already cooks them at 24 kHz. The codec is Bink Audio (the project default).
- **Compression quality is not a lever.** The ambient barks are at quality 25 and the lines at 40, but they cook at almost the same bitrate: 56.3 vs 57.4 kbit/s. Lowering quality further would save next to nothing.
- **Sample rate is the lever.** These are estimates: Bink's bitrate roughly follows the sample rate, to be confirmed by a test cook of ~20 waves once you pick.

  | Option | Voice in pak | Saves | How |
  |---|---|---|---|
  | A: as now (24 kHz) | 102 MB | 0 | |
  | B: 16 kHz | ~68 MB | **~−34 MB** | The platform's "Low" tier is 12 kHz, so `LowSampleRate=16000` in `DefaultEngine.ini` (orchestrator) plus *Sample Rate = Low* on the voice waves (audio, bulk edit) |
  | C: 12 kHz | ~51 MB | **~−51 MB** | *Sample Rate = Low* on the voice waves (audio, bulk edit) |
  | Fewer ambient variants (half of the 1,330 barks) | ~80 MB | ~−22 MB | Audio drops variants. No quality change; can be combined with B or C |

- **B or C on the barks only** (they play under the world mix and are heard less closely) saves about −14 MB (B) or −22 MB (C), and leaves story, narrator and replies at 24 kHz.
