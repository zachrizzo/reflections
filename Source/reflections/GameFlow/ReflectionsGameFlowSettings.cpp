#include "GameFlow/ReflectionsGameFlowSettings.h"

#include "Engine/Engine.h"
#include "GameFlow/ReflectionsGameFlowText.h"
#include "GameFramework/GameUserSettings.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/ConfigCacheIni.h"
#include "Scalability.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsSettings, Log, All);

#define LOCTEXT_NAMESPACE "ReflectionsGameFlow"
#define FLOWTEXT(Key, Default) ReflectionsFlowText::Get(TEXT(Key), LOCTEXT(Key, Default))

namespace ReflectionsFlowSettings
{
    namespace
    {
        Scalability::FQualityLevels QualityBaseline;
        bool bHasQualityBaseline = false;

        const TCHAR* RtSection = TEXT("/Script/reflections.ReflectionsGameFlow");
        const TCHAR* RtKey = TEXT("bHardwareRayTracing");

        UGameUserSettings* Settings()
        {
            return GEngine ? GEngine->GetGameUserSettings() : nullptr;
        }

        int32 NearestIndex(const TArray<float>& Values, float Value)
        {
            int32 Best = 0;
            for (int32 Index = 1; Index < Values.Num(); ++Index)
            {
                if (FMath::Abs(Values[Index] - Value) < FMath::Abs(Values[Best] - Value))
                {
                    Best = Index;
                }
            }
            return Best;
        }

        int32 CapIndex(float Limit)
        {
            const TArray<int32>& Caps = FrameCaps();
            if (Limit <= 0.0f)
            {
                return Caps.Num() - 1;
            }
            int32 Best = 0;
            for (int32 Index = 0; Index < Caps.Num() - 1; ++Index)
            {
                if (FMath::Abs(Caps[Index] - Limit) < FMath::Abs(Caps[Best] - Limit))
                {
                    Best = Index;
                }
            }
            return Best;
        }

        bool LoadRayTracingChoice(bool& bOut)
        {
            return GConfig && GConfig->GetBool(RtSection, RtKey, bOut, GGameUserSettingsIni);
        }

        void SnapResolution(FReflectionsVideoDraft& Draft)
        {
            const TArray<FIntPoint> List = ResolutionsFor(Draft.WindowMode);
            if (List.Num() > 0 && !List.Contains(Draft.Resolution))
            {
                Draft.Resolution = List.Last();  // the lists are smallest first
            }
        }
    }

    const TArray<float>& RenderScales()
    {
        static const TArray<float> Values = {0.5f, 0.67f, 0.75f, 0.87f, 1.0f};
        return Values;
    }

    const TArray<int32>& FrameCaps()
    {
        static const TArray<int32> Values = {30, 60, 90, 120, 144, 0};
        return Values;
    }

    bool CanChangeVideoMode()
    {
        return !GIsEditor && Settings() != nullptr;
    }

    FReflectionsVideoDraft ReadCurrent()
    {
        FReflectionsVideoDraft Draft;
        UGameUserSettings* S = Settings();
        if (!S)
        {
            return Draft;
        }
        Draft.Preset = S->GetOverallScalabilityLevel();
        Draft.WindowMode = static_cast<int32>(S->GetFullscreenMode());
        Draft.Resolution = S->GetScreenResolution();
        Draft.RenderScaleIndex = NearestIndex(RenderScales(), S->GetResolutionScaleNormalized());
        Draft.bVSync = S->IsVSyncEnabled();
        Draft.FrameCapIndex = CapIndex(S->GetFrameRateLimit());
        bool bRt = false;
        if (LoadRayTracingChoice(bRt))
        {
            Draft.bRayTracing = bRt;
        }
        else if (const IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Lumen.HardwareRayTracing")))
        {
            Draft.bRayTracing = CVar->GetInt() != 0;
        }
        return Draft;
    }

    TArray<FIntPoint> ResolutionsFor(int32 WindowMode)
    {
        TArray<FIntPoint> List;
        if (WindowMode == static_cast<int32>(EWindowMode::WindowedFullscreen))
        {
            if (UGameUserSettings* S = Settings())
            {
                List.Add(S->GetDesktopResolution());
            }
            return List;
        }
        if (WindowMode == static_cast<int32>(EWindowMode::Fullscreen))
        {
            UKismetSystemLibrary::GetSupportedFullscreenResolutions(List);
        }
        else
        {
            UKismetSystemLibrary::GetConvenientWindowedResolutions(List);
        }
        // Distinct, smallest first.
        TArray<FIntPoint> Unique;
        for (const FIntPoint& Point : List)
        {
            Unique.AddUnique(Point);
        }
        Unique.Sort([](const FIntPoint& A, const FIntPoint& B) { return A.X * A.Y < B.X * B.Y; });
        if (Unique.Num() == 0)
        {
            if (UGameUserSettings* S = Settings())
            {
                Unique.Add(S->GetDesktopResolution());
            }
        }
        return Unique;
    }

    void Step(FReflectionsVideoDraft& Draft, int32 Row, int32 Delta)
    {
        auto Wrap = [](int32 Value, int32 Count) { return Count > 0 ? (Value % Count + Count) % Count : 0; };
        switch (Row)
        {
        case Row_Preset:
            Draft.Preset = Wrap(FMath::Max(Draft.Preset, 0) + Delta, 4);
            Draft.bRayTracing = Draft.Preset == 3;  // Epic adds ray-traced lighting; High and below go without
            break;
        case Row_Resolution:
        {
            const TArray<FIntPoint> List = ResolutionsFor(Draft.WindowMode);
            if (List.Num() > 0)
            {
                const int32 Current = List.IndexOfByKey(Draft.Resolution);
                Draft.Resolution = List[Wrap((Current == INDEX_NONE ? List.Num() - 1 : Current) + Delta, List.Num())];
            }
            break;
        }
        case Row_WindowMode:
        {
            // Fullscreen (0) <-> Borderless (1) <-> Windowed (2)
            Draft.WindowMode = Wrap(Draft.WindowMode + Delta, 3);
            SnapResolution(Draft);
            break;
        }
        case Row_RenderScale:
            Draft.RenderScaleIndex = Wrap(Draft.RenderScaleIndex + Delta, RenderScales().Num());
            break;
        case Row_VSync:
            Draft.bVSync = !Draft.bVSync;
            break;
        case Row_FrameCap:
            Draft.FrameCapIndex = Wrap(Draft.FrameCapIndex + Delta, FrameCaps().Num());
            break;
        case Row_RayTracing:
            Draft.bRayTracing = !Draft.bRayTracing;
            break;
        default:
            break;
        }
    }

    FText ValueText(const FReflectionsVideoDraft& Draft, int32 Row)
    {
        switch (Row)
        {
        case Row_Preset:
            switch (Draft.Preset)
            {
            case 0: return FLOWTEXT("Settings.Low", "Low");
            case 1: return FLOWTEXT("Settings.Medium", "Medium");
            case 2: return FLOWTEXT("Settings.High", "High");
            case 3: return FLOWTEXT("Settings.Epic", "Epic");
            default: return FLOWTEXT("Settings.Custom", "Custom");
            }
        case Row_Resolution:
            return FText::FromString(FString::Printf(TEXT("%d x %d"), Draft.Resolution.X, Draft.Resolution.Y));
        case Row_WindowMode:
            switch (Draft.WindowMode)
            {
            case 0: return FLOWTEXT("Settings.Fullscreen", "Fullscreen");
            case 1: return FLOWTEXT("Settings.Borderless", "Borderless");
            default: return FLOWTEXT("Settings.Windowed", "Windowed");
            }
        case Row_RenderScale:
            return FText::FromString(FString::Printf(TEXT("%d %%"), FMath::RoundToInt(RenderScales()[FMath::Clamp(Draft.RenderScaleIndex, 0, RenderScales().Num() - 1)] * 100.0f)));
        case Row_VSync:
            return Draft.bVSync ? FLOWTEXT("Settings.On", "On") : FLOWTEXT("Settings.Off", "Off");
        case Row_FrameCap:
        {
            const int32 Cap = FrameCaps()[FMath::Clamp(Draft.FrameCapIndex, 0, FrameCaps().Num() - 1)];
            return Cap <= 0 ? FLOWTEXT("Settings.Unlimited", "Unlimited") : FText::FromString(FString::Printf(TEXT("%d fps"), Cap));
        }
        case Row_RayTracing:
            return Draft.bRayTracing ? FLOWTEXT("Settings.On", "On") : FLOWTEXT("Settings.Off", "Off");
        default:
            return FText::GetEmpty();
        }
    }

    void ApplyRayTracing(bool bOn)
    {
        if (IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Lumen.HardwareRayTracing")))
        {
            // Game-setting priority beats the scalability groups, so the preset row cannot flip it back.
            CVar->Set(bOn ? 1 : 0, ECVF_SetByGameSetting);
        }
        if (GConfig)
        {
            GConfig->SetBool(RtSection, RtKey, bOn, GGameUserSettingsIni);
            GConfig->Flush(false, GGameUserSettingsIni);
        }
    }

    bool Apply(const FReflectionsVideoDraft& Draft)
    {
        UGameUserSettings* S = Settings();
        if (!S)
        {
            return false;
        }
        const FIntPoint TargetResolution = Draft.WindowMode == static_cast<int32>(EWindowMode::WindowedFullscreen)
            ? S->GetDesktopResolution() : Draft.Resolution;
        const bool bVideoModeChanged = CanChangeVideoMode()
            && (S->GetScreenResolution() != TargetResolution || static_cast<int32>(S->GetFullscreenMode()) != Draft.WindowMode);
        if (Draft.Preset >= 0)
        {
            S->SetOverallScalabilityLevel(Draft.Preset);
        }
        if (CanChangeVideoMode())
        {
            S->SetFullscreenMode(static_cast<EWindowMode::Type>(Draft.WindowMode));
            S->SetScreenResolution(TargetResolution);
        }
        S->SetResolutionScaleNormalized(RenderScales()[FMath::Clamp(Draft.RenderScaleIndex, 0, RenderScales().Num() - 1)]);
        S->SetVSyncEnabled(Draft.bVSync);
        S->SetFrameRateLimit(static_cast<float>(FrameCaps()[FMath::Clamp(Draft.FrameCapIndex, 0, FrameCaps().Num() - 1)]));
        if (CanChangeVideoMode())
        {
            S->ApplySettings(false);
        }
        else
        {
            S->ApplyNonResolutionSettings();  // PIE: never resize the editor
        }
        S->SaveSettings();
        // After ApplySettings: it re-applies the scalability groups.
        ApplyRayTracing(Draft.bRayTracing);
        UE_LOG(LogReflectionsSettings, Log, TEXT("Applied: preset %d, %dx%d mode %d, scale %.2f, vsync %d, cap %d, RT %d."),
            Draft.Preset, TargetResolution.X, TargetResolution.Y, Draft.WindowMode, RenderScales()[Draft.RenderScaleIndex],
            Draft.bVSync, FrameCaps()[Draft.FrameCapIndex], Draft.bRayTracing);
        return bVideoModeChanged;
    }

    void KeepVideoMode()
    {
        if (UGameUserSettings* S = Settings())
        {
            S->ConfirmVideoMode();
            S->SaveSettings();
        }
    }

    void RevertVideoMode()
    {
        if (UGameUserSettings* S = Settings())
        {
            S->RevertVideoMode();
            if (CanChangeVideoMode())
            {
                S->ApplySettings(false);
            }
            S->SaveSettings();
        }
    }

    void PreviewPreset(int32 Preset, bool bRayTracing)
    {
        UGameUserSettings* S = Settings();
        if (!S || Preset < 0)
        {
            return;
        }
        S->SetOverallScalabilityLevel(Preset);
        S->ApplyNonResolutionSettings();
        if (IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Lumen.HardwareRayTracing")))
        {
            CVar->Set(bRayTracing ? 1 : 0, ECVF_SetByGameSetting);
        }
    }

    void CaptureQualityBaseline()
    {
        QualityBaseline = Scalability::GetQualityLevels();
        bHasQualityBaseline = true;
    }

    void RestoreQualityBaseline(bool bRayTracing)
    {
        if (bHasQualityBaseline)
        {
            Scalability::SetQualityLevels(QualityBaseline, true);
            if (UGameUserSettings* S = Settings())
            {
                S->ScalabilityQuality = QualityBaseline;  // the cached copy SaveSettings would write
            }
        }
        if (IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Lumen.HardwareRayTracing")))
        {
            CVar->Set(bRayTracing ? 1 : 0, ECVF_SetByGameSetting);
        }
    }

    FReflectionsVideoDraft AutoDetect()
    {
        UGameUserSettings* S = Settings();
        FReflectionsVideoDraft Draft = ReadCurrent();
        if (!S)
        {
            return Draft;
        }
        S->RunHardwareBenchmark(10, 1.0f, 1.0f);
        S->ApplyHardwareBenchmarkResults();
        const int32 Detected = S->GetOverallScalabilityLevel();
        // The engine's thresholds pick Epic too eagerly for this game: clamp to High (players can still pick Epic).
        Draft.Preset = Detected < 0 ? 2 : FMath::Min(Detected, 2);
        Draft.bRayTracing = false;
        Draft.WindowMode = static_cast<int32>(EWindowMode::WindowedFullscreen);
        Draft.Resolution = S->GetDesktopResolution();
        Draft.bVSync = true;
        Draft.FrameCapIndex = FrameCaps().Num() - 1;  // unlimited: VSync paces it
        Draft.RenderScaleIndex = Draft.Resolution.Y >= 2160 ? 0 : RenderScales().Num() - 1;  // TSR from 50 % at 4K
        UE_LOG(LogReflectionsSettings, Log, TEXT("Auto-detect: benchmark level %d -> preset %d at %dx%d."),
            Detected, Draft.Preset, Draft.Resolution.X, Draft.Resolution.Y);
        return Draft;
    }

    bool RunFirstLaunchSetup()
    {
        UGameUserSettings* S = Settings();
        if (!S || !CanChangeVideoMode())
        {
            return false;
        }
        if (S->GetLastCPUBenchmarkResult() >= 0.0f)
        {
            bool bRt = false;
            if (LoadRayTracingChoice(bRt))
            {
                ApplyRayTracing(bRt);
            }
            return false;
        }
        const FReflectionsVideoDraft Draft = AutoDetect();
        const bool bChanged = Apply(Draft);
        S->ConfirmVideoMode();
        S->SaveSettings();
        return bChanged;
    }
}

#undef FLOWTEXT
#undef LOCTEXT_NAMESPACE
