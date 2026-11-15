# Graphics settings screen: spec for game-flow

Owner: game-flow (`Source/reflections/GameFlow/`, Slate in code). Written by the perf session. Measurements and reasons are in `ArtDirection/Perf/README.md`.

## Why the game needs this screen

Today no code touches `UGameUserSettings`:
- Every PC starts at **Epic**, with hardware ray tracing, at desktop resolution, with **no frame cap** and **VSync off**.
- A judge on a 4K monitor or a mid-range GPU gets the most expensive settings, and has no way to lower them.

## Entry points

- Title screen: **Settings**, between Controls and Credits.
- Pause menu: **Settings**, between Controls and Restart from checkpoint.
- It uses the same focus, keyboard, gamepad and mouse rules as the other menus (wrapping focus, B or Esc to go back, and so on).

## Rows

All rows go through `UGameUserSettings* S = GEngine->GetGameUserSettings();`.

| Row | Values | Code |
|---|---|---|
| Quality preset | Low / Medium / High / Epic, and "Custom" (shown, not selectable) | `S->SetOverallScalabilityLevel(0..3)`; read it back with `S->GetOverallScalabilityLevel()`, which returns -1 for Custom |
| Resolution | List from `UKismetSystemLibrary::GetSupportedFullscreenResolutions` (Fullscreen) or `GetConvenientWindowedResolutions` (Windowed) | `S->SetScreenResolution(FIntPoint)` |
| Window mode | Fullscreen / Borderless / Windowed | `S->SetFullscreenMode(EWindowMode::Fullscreen / WindowedFullscreen / Windowed)` |
| Render scale | 50 / 67 / 75 / 87 / 100 % | `S->SetResolutionScaleNormalized(0.5..1.0)`. TSR upscales, so 67 % at 1440p and 50 % at 4K still look sharp. |
| VSync | On / Off | `S->SetVSyncEnabled(bool)` |
| Frame cap | 30 / 60 / 90 / 120 / 144 / Unlimited | `S->SetFrameRateLimit(0 = unlimited)` |
| Ray-traced lighting | On / Off (Epic default On, High and below default Off) | Console var `r.Lumen.HardwareRayTracing` 1/0. Store it in your own save or in `GameUserSettings.ini` under `[/Script/reflections.ReflectionsGameFlow]`; the preset rows in `DefaultScalability.ini` set it per level. |
| Auto-detect | Button | `S->RunHardwareBenchmark(); S->ApplyHardwareBenchmarkResults();` then apply the clamp below |

Buttons: **Apply**, **Back** (Back discards changes that weren't applied), and **Defaults** (runs auto-detect).

- **Apply:** `S->ApplySettings(false); S->SaveSettings();`
- **Resolution or window mode changed:** show a 15-second "Keep these settings?" confirm, then `S->ConfirmVideoMode()` or `S->RevertVideoMode()` and apply again. A wrong mode on a TV must never leave the player stuck.
- **Gamepad:** left and right change a row's value. Changes take effect only on Apply, except the preset row, which previews immediately (it's cheap).

## First launch: the most important part

On the first run, when no settings were saved (`S->GetLastCPUBenchmarkResult() < 0`, or your own `bSettingsInitialised` flag in the checkpoint save):
1. Run `S->RunHardwareBenchmark(10, 1.f, 1.f); S->ApplyHardwareBenchmarkResults();`.
2. **Clamp** the result to **High** (`SetOverallScalabilityLevel(FMath::Min(S->GetOverallScalabilityLevel(), 2))`). The engine's thresholds were tuned for older GPUs and pick Epic far too eagerly for this game. Players can still choose Epic. The perf session will measure a GPU-index threshold for auto-Epic on Sunday.
3. Set **Borderless** at the desktop resolution, with **VSync on** and the frame cap at **Unlimited** (VSync paces it). This holds on 120/144 Hz monitors too.
   - Most of those have VRR (G-Sync/FreeSync), so 75–130 fps shows smoothly.
   - A 60 cap would throw away half the smoothness a strong PC gets: combat runs at 75 fps on the RTX 5080.
   - Players on a fixed-refresh monitor who see uneven pacing can pick 60 in the Frame cap row.
4. **Render scale:** 100 % up to 1440p; at 4K or above, 50 % (TSR).
5. `S->ApplySettings(false); S->SaveSettings();`

Do this before the title screen fades in, so the player never sees a hitch from a mode switch mid-menu.

## Shipping notes

- Also persist the "Ray-traced lighting" row. `ApplySettings` re-applies scalability groups, so set `r.Lumen.HardwareRayTracing` **after** `SetOverallScalabilityLevel` and after `ApplySettings`.
- Strings go in `ST_GameFlowText`: `Settings.Title`, `Settings.Preset`, `Settings.Resolution`, `Settings.WindowMode`, `Settings.RenderScale`, `Settings.VSync`, `Settings.FrameCap`, `Settings.RayTracing`, `Settings.AutoDetect`, `Settings.Apply`, `Settings.Keep`, `Settings.Reverting` (`{0}` seconds).
- Footer tip on the preset row: "High holds 60 fps on most mid-range PCs. Epic adds ray-traced lighting."
