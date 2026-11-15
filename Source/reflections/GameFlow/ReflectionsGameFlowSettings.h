#pragma once

#include "CoreMinimal.h"

/** The Settings screen's working copy of the video settings (applied only on Apply, except the preset preview). */
struct FReflectionsVideoDraft
{
    /** 0 Low .. 3 Epic; -1 Custom (shown, not selectable). */
    int32 Preset = 2;
    FIntPoint Resolution = FIntPoint(1920, 1080);
    /** EWindowMode::Type: 0 Fullscreen, 1 Borderless (WindowedFullscreen), 2 Windowed. */
    int32 WindowMode = 1;
    int32 RenderScaleIndex = 4;
    bool bVSync = true;
    int32 FrameCapIndex = 5;
    bool bRayTracing = false;
};

/**
 * Graphics settings through UGameUserSettings (ArtDirection/Perf/GraphicsSettings-Spec.md): the Settings screen's
 * read / apply / keep-or-revert, the hardware auto-detect, and the first-launch setup. Never touches the editor's own
 * window: everything that changes the video mode is skipped in PIE.
 */
namespace ReflectionsFlowSettings
{
    enum ERow : int32
    {
        Row_Preset,
        Row_Resolution,
        Row_WindowMode,
        Row_RenderScale,
        Row_VSync,
        Row_FrameCap,
        Row_RayTracing,
        Row_Count,
    };

    REFLECTIONS_API const TArray<float>& RenderScales();
    /** Frame caps in fps; 0 = unlimited. */
    REFLECTIONS_API const TArray<int32>& FrameCaps();

    /** The settings as they are now (saved, plus the stored ray-tracing choice). */
    REFLECTIONS_API FReflectionsVideoDraft ReadCurrent();

    /** Resolutions offered for a window mode (Borderless: just the desktop). */
    REFLECTIONS_API TArray<FIntPoint> ResolutionsFor(int32 WindowMode);

    /** Step one row's value by Delta (wraps). Keeps the draft consistent (resolution list, ray tracing default). */
    REFLECTIONS_API void Step(FReflectionsVideoDraft& Draft, int32 Row, int32 Delta);

    /** Value text for a row ("High", "1920 x 1080", "67 %", ...). */
    REFLECTIONS_API FText ValueText(const FReflectionsVideoDraft& Draft, int32 Row);

    /** Applies and saves the draft. True when the resolution or window mode changed (ask keep-or-revert). */
    REFLECTIONS_API bool Apply(const FReflectionsVideoDraft& Draft);
    REFLECTIONS_API void KeepVideoMode();
    REFLECTIONS_API void RevertVideoMode();

    /** Live preview of a quality preset (no save). */
    REFLECTIONS_API void PreviewPreset(int32 Preset, bool bRayTracing);

    /** Remember every scalability group as it is now (Settings opened, or settings applied). */
    REFLECTIONS_API void CaptureQualityBaseline();
    /** Put the remembered groups (and the ray-tracing value) back exactly: Back drops a previewed preset even when the
     *  starting point was "Custom", which no single preset number can restore. */
    REFLECTIONS_API void RestoreQualityBaseline(bool bRayTracing);

    /** Hardware benchmark, clamped to High, borderless at the desktop resolution, VSync on, uncapped. Not applied. */
    REFLECTIONS_API FReflectionsVideoDraft AutoDetect();

    /** Packaged / -game only: the first launch (no benchmark saved yet) auto-detects and applies. Later launches
     *  re-apply the stored ray-tracing choice. Returns true when it changed the video mode. */
    REFLECTIONS_API bool RunFirstLaunchSetup();

    /** Ray-traced lighting (r.Lumen.HardwareRayTracing, set after the scalability groups) and its stored choice. */
    REFLECTIONS_API void ApplyRayTracing(bool bOn);

    /** False in PIE (and anywhere the video mode belongs to the editor). */
    REFLECTIONS_API bool CanChangeVideoMode();
}
