#include "Digging/ReflectionsDigSubsystem.h"

#include "CoreMinimal.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "CollisionQueryParams.h"
#include "Components/PointLightComponent.h"
#include "Digging/ReflectionsDigTerrain.h"
#include "Digging/ReflectionsDigTypes.h"
#include "Digging/Tests/ReflectionsDigGameTestHarness.h"
#include "Digging/Tests/ReflectionsDigTestTraces.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicRHI.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/HitResult.h"
#include "Engine/PointLight.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "ImageUtils.h"
#include "Math/RandomStream.h"
#include "Misc/App.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/OutputDevice.h"
#include "Misc/OutputDeviceRedirector.h"
#include "Misc/Paths.h"
#include "NavigationSystem.h"
#include "RenderTimer.h"
#include "RenderUtils.h"
#include "SceneInterface.h"
#include "ShaderCompiler.h"
#include "UObject/UObjectGlobals.h"
#include "UnrealClient.h"

#include <atomic>

#if WITH_DEV_AUTOMATION_TESTS

/*
 * Measurements with the real renderer, off screen (test.ps1 -Game -Render -Map /Game/Maps/DigSpike/L_DigSpike
 * -Filter Reflections.SpikePerf -TimeoutSec 2400). They are not gates: each test logs DIGSPIKE lines and passes when it
 * completed; the pass marks are applied in ArtDirection/Digging/SpikeResults.md.
 *
 * Game-thread cost is read every frame from the engine's GGameThreadTime (RenderTimer.h): the cycles from one
 * FViewport::Draw to the next minus the game thread's idle time in between (FThreadIdleStats: sleeps and event waits,
 * which include the 60 fps frame-cap wait and waits on the render thread or on tasks). Each test also logs "busy": the
 * wall time from one sample to the next minus only the frame-cap wait (FApp::GetIdleTime), which keeps every other wait.
 *
 * The tests share one world and run one after another, each at its own site (at least 1000 cm from the others' digs):
 *   CaveShots      pit and tunnel at (1800, 1400), tunnel along +X; character at (1800, 400); the tunnel, the pit and
 *                  the tunnel wall, each with hardware ray tracing on and off
 *   CollisionSize  200 digs inside the column X 4225..5800, Y 825..2400; character at (5000, -400)
 *   DigCost        shaft at (1800, -1600), then a pocket at (2000, -1600) at the bottom
 *   Seams          no digs; character at (3400, 0)
 *   ShadowCost     pit at (4000, -1600), rim digs on its +X+Y side; character at (4000, -600)
 *   StreamingCost  no digs; walk from (1100, -2300) to (5700, 2300)
 */

using namespace ReflectionsDig::GameTest;

namespace
{
    constexpr EAutomationTestFlags SpikePerfTestFlags = EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter;
    constexpr int32 IdleFrames = 300;
    /** How long shaders, the terrain and navigation must all be quiet before an idle baseline. */
    constexpr double QuietSeconds = 2.0;
    constexpr double QuietTimeoutSeconds = 1200.0;

    int32 GetConsoleInt(const TCHAR* Name, int32 Missing = -1)
    {
        const IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(Name);
        return Variable != nullptr ? Variable->GetInt() : Missing;
    }

    /** The shader platform the game world's scene renders with, if it has a scene. */
    TOptional<EShaderPlatform> GetSceneShaderPlatform()
    {
        const UWorld* World = GWorld;
        if (World == nullptr || World->Scene == nullptr)
        {
            return TOptional<EShaderPlatform>();
        }
        return World->Scene->GetShaderPlatform();
    }

    /**
     * Whether Lumen really traces with hardware ray tracing now: the same conditions as the renderer's
     * Lumen::UseHardwareRayTracing (LumenHardwareRayTracingCommon.cpp; a game view allows ray tracing), with Lumen as
     * the global illumination method.
     */
    bool IsLumenHardwareRayTracingActive()
    {
        const TOptional<EShaderPlatform> Platform = GetSceneShaderPlatform();
        return Platform.IsSet() && IsRayTracingEnabled(*Platform) && CanUseInlineRayTracing(*Platform)
            && GetConsoleInt(TEXT("r.Lumen.HardwareRayTracing"), 0) != 0 && GetConsoleInt(TEXT("r.DynamicGlobalIlluminationMethod"), 0) == 1;
    }

    double MeanOf(const TArray<double>& Values)
    {
        double Sum = 0.0;
        for (const double Value : Values)
        {
            Sum += Value;
        }
        return Values.IsEmpty() ? 0.0 : Sum / Values.Num();
    }

    double MaxOf(const TArray<double>& Values)
    {
        double Max = 0.0;
        for (const double Value : Values)
        {
            Max = FMath::Max(Max, Value);
        }
        return Max;
    }

    /** The nearest-rank percentile (0.99 for the 99th). */
    double PercentileOf(TArray<double> Values, double Fraction)
    {
        if (Values.IsEmpty())
        {
            return 0.0;
        }
        Values.Sort();
        const int32 Index = FMath::Clamp(FMath::CeilToInt(Fraction * Values.Num()) - 1, 0, Values.Num() - 1);
        return Values[Index];
    }

    /** The largest few values, largest first, as text. */
    FString TopOf(TArray<double> Values, int32 Count)
    {
        Values.Sort(TGreater<double>());
        FString Text;
        for (int32 Index = 0; Index < FMath::Min(Count, Values.Num()); ++Index)
        {
            Text += FString::Printf(TEXT("%s%.2f"), Index == 0 ? TEXT("") : TEXT(","), Values[Index]);
        }
        return Text;
    }

    /** Garbage collections since the process started (counted from the first measured window on). */
    std::atomic<int32> GGarbageCollections{ 0 };

    void WatchGarbageCollections()
    {
        static const FDelegateHandle Handle = FCoreUObjectDelegates::GetPostGarbageCollect().AddLambda([]() { ++GGarbageCollections; });
    }

    /**
     * Reads the terrain's own Verbose timing lines while it lives ("commit ... total N ms" and "swap ... in N ms"),
     * so a window knows how much of a frame went into committing chunks and destroying retiring pieces. The terrain's
     * Verbose log is raised for that time and put back afterwards. (Those lines carry the text "DIGSPIKE headless" from
     * the headless tasks that added them; in this run they are timed with the renderer on.)
     */
    struct FTerrainTimingWatch : public FOutputDevice
    {
        FTerrainTimingWatch()
            : OldVerbosity(LogReflectionsDigTerrain.GetVerbosity())
        {
            LogReflectionsDigTerrain.SetVerbosity(ELogVerbosity::Verbose);
            GLog->AddOutputDevice(this);
        }

        virtual ~FTerrainTimingWatch() override
        {
            GLog->RemoveOutputDevice(this);
            LogReflectionsDigTerrain.SetVerbosity(OldVerbosity);
        }

        virtual void Serialize(const TCHAR* Message, ELogVerbosity::Type Verbosity, const FName& Category) override
        {
            if (Category != LogReflectionsDigTerrain.GetCategoryName())
            {
                return;
            }
            const FString Text(Message);
            int32 At = Text.Find(TEXT(" total "));
            if (Text.Contains(TEXT("headless commit")) && At != INDEX_NONE)
            {
                const double Ms = FCString::Atod(*Text.Mid(At + 7));
                ++Commits;
                CommitMsTotal += Ms;
                CommitMsMax = FMath::Max(CommitMsMax, Ms);
                FrameCommitMs += Ms;
                return;
            }
            At = Text.Find(TEXT(" in "), ESearchCase::CaseSensitive, ESearchDir::FromEnd);
            if (Text.Contains(TEXT("headless swap")) && At != INDEX_NONE)
            {
                const double Ms = FCString::Atod(*Text.Mid(At + 4));
                ++Swaps;
                SwapMsTotal += Ms;
                SwapMsMax = FMath::Max(SwapMsMax, Ms);
                FrameSwapMs += Ms;
            }
        }

        virtual bool CanBeUsedOnMultipleThreads() const override { return true; }

        FString Describe() const
        {
            return FString::Printf(TEXT("commits=%d commit_ms_total=%.2f commit_ms_max=%.2f swaps=%d swap_ms_total=%.2f swap_ms_max=%.2f"),
                Commits, CommitMsTotal, CommitMsMax, Swaps, SwapMsTotal, SwapMsMax);
        }

        ELogVerbosity::Type OldVerbosity;
        int32 Commits = 0;
        double CommitMsTotal = 0.0;
        double CommitMsMax = 0.0;
        int32 Swaps = 0;
        double SwapMsTotal = 0.0;
        double SwapMsMax = 0.0;
        /** Since the window's last sample. */
        double FrameCommitMs = 0.0;
        double FrameSwapMs = 0.0;
    };

    /** What happened in a frame of a measured window. */
    constexpr uint8 FrameTagCommit = 1;
    constexpr uint8 FrameTagReleaseOrRestore = 2;
    constexpr uint8 FrameTagCollection = 4;

    TArray<FIntVector> GetAllChunks(const AReflectionsDigTerrain& Terrain);

    /** A frame slower than this is logged with what happened in it. */
    constexpr double SpikeMs = 16.0;

    /** Per-frame timings of one measured window, one sample per frame. */
    struct FFrameWindow
    {
        /** GGameThreadTime of the frame: game-thread work without any idle time. */
        TArray<double> GameMs;
        /** Wall time since the previous sample minus the frame-cap wait: every other wait included. */
        TArray<double> BusyMs;
        /** GRenderThreadTime of the frame. */
        TArray<double> RenderMs;
        /** The graphics card's time for the latest finished frame (RHIGetGPUFrameCycles; it lags a frame or two). */
        TArray<double> GpuMs;
        double LastWallSeconds = 0.0;
        /** What happened in each frame (EFrameTag bits), for the windows that tag their frames (Start). */
        TArray<uint8> Tags;
        int32 Collections = 0;
        int32 Releases = 0;
        int32 Restores = 0;
        double ReleaseMsTotal = 0.0;
        double ReleaseMsMaxFrame = 0.0;
        TArray<bool> ChunkShown;
        int32 LastReleaseCount = -1;
        double LastReleaseSeconds = 0.0;
        /** Frames over SpikeMs, with what the terrain, navigation and the garbage collector did in them. */
        TArray<FString> Spikes;
        int32 LastGarbageCollections = -1;
        int32 LastNavUpdates = -1;
        double LastNavSeconds = 0.0;
        /** Set while the window is measured (Start/Stop); null for the idle baseline. */
        TUniquePtr<FTerrainTimingWatch> Watch;

        void Start()
        {
            WatchGarbageCollections();
            Watch = MakeUnique<FTerrainTimingWatch>();
        }

        void Stop() { Watch.Reset(); }

        void Sample(const FDigGameScene* Scene = nullptr)
        {
            WatchGarbageCollections();
            const double Now = FPlatformTime::Seconds();
            const double Game = FPlatformTime::ToMilliseconds(GGameThreadTime);
            GameMs.Add(Game);
            RenderMs.Add(FPlatformTime::ToMilliseconds(GRenderThreadTime));
            GpuMs.Add(FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles(0)));
            const double Busy = LastWallSeconds > 0.0 ? FMath::Max(0.0, (Now - LastWallSeconds - FApp::GetIdleTime()) * 1000.0) : 0.0;
            if (LastWallSeconds > 0.0)
            {
                BusyMs.Add(Busy);
            }
            LastWallSeconds = Now;

            const int32 TotalCollections = GGarbageCollections.load();
            const AReflectionsDigTerrain* Terrain = Scene != nullptr ? Scene->Terrain.Get() : nullptr;
            const int32 NavUpdates = Terrain != nullptr ? Terrain->GetNavUpdateCount() : 0;
            const double NavSeconds = Terrain != nullptr ? Terrain->GetNavUpdateSeconds() : 0.0;
            if (Game > SpikeMs && Spikes.Num() < 20)
            {
                UNavigationSystemV1* Navigation = Scene != nullptr ? GetNavigation(*Scene) : nullptr;
                Spikes.Add(FString::Printf(TEXT("frame=%d game_ms=%.2f busy_ms=%.2f render_ms=%.2f commits=%d commit_ms=%.2f swap_ms=%.2f nav_updates=%d nav_ms=%.2f gc=%d nav_tasks_running=%d tasks_in_flight=%d"),
                    GameMs.Num() - 1, Game, Busy, RenderMs.Last(), Scene != nullptr && Scene->GetSubsystem() != nullptr ? Scene->GetSubsystem()->GetCommitsLastTick() : -1,
                    Watch.IsValid() ? Watch->FrameCommitMs : -1.0, Watch.IsValid() ? Watch->FrameSwapMs : -1.0,
                    LastNavUpdates >= 0 ? NavUpdates - LastNavUpdates : -1, LastNavUpdates >= 0 ? (NavSeconds - LastNavSeconds) * 1000.0 : -1.0,
                    LastGarbageCollections >= 0 ? TotalCollections - LastGarbageCollections : -1,
                    Navigation != nullptr ? Navigation->GetNumRunningBuildTasks() : -1,
                    Scene != nullptr && Scene->GetSubsystem() != nullptr ? Scene->GetSubsystem()->GetTasksInFlight() : -1));
            }
            // The frame's tags: chunk commits in this tick, chunks released or restored (a chunk that stopped or
            // started showing pieces), and a garbage collection since the previous sample.
            uint8 Tag = 0;
            const int32 NewCollections = LastGarbageCollections >= 0 ? TotalCollections - LastGarbageCollections : 0;
            Collections += NewCollections;
            Tag |= NewCollections > 0 ? FrameTagCollection : 0;
            if (Terrain != nullptr && Terrain->GetGrid() != nullptr)
            {
                Tag |= Scene->GetSubsystem() != nullptr && Scene->GetSubsystem()->GetCommitsLastTick() > 0 ? FrameTagCommit : 0;
                const TArray<FIntVector> Chunks = GetAllChunks(*Terrain);
                ChunkShown.SetNum(Chunks.Num());
                int32 FrameRestores = 0;
                for (int32 Index = 0; Index < Chunks.Num(); ++Index)
                {
                    const bool bShown = Terrain->GetChunkPieceCount(Chunks[Index]) > 0;
                    FrameRestores += bShown && !ChunkShown[Index] && GameMs.Num() > 1 ? 1 : 0;
                    ChunkShown[Index] = bShown;
                }
                const int32 FrameReleases = LastReleaseCount >= 0 ? Terrain->GetChunkReleaseCount() - LastReleaseCount : 0;
                const double FrameReleaseMs = LastReleaseCount >= 0 ? (Terrain->GetChunkReleaseSeconds() - LastReleaseSeconds) * 1000.0 : 0.0;
                LastReleaseCount = Terrain->GetChunkReleaseCount();
                LastReleaseSeconds = Terrain->GetChunkReleaseSeconds();
                Releases += FrameReleases;
                Restores += FrameRestores;
                ReleaseMsTotal += FrameReleaseMs;
                ReleaseMsMaxFrame = FMath::Max(ReleaseMsMaxFrame, FrameReleaseMs);
                Tag |= FrameReleases > 0 || FrameRestores > 0 ? FrameTagReleaseOrRestore : 0;
            }
            Tags.Add(Tag);
            LastGarbageCollections = TotalCollections;
            LastNavUpdates = NavUpdates;
            LastNavSeconds = NavSeconds;
            if (Watch.IsValid())
            {
                Watch->FrameCommitMs = 0.0;
                Watch->FrameSwapMs = 0.0;
            }
        }

        int32 Num() const { return GameMs.Num(); }

        /** "frames=.. mean=.. p99=.. max=.." of each series, for the extra lines. */
        FString Describe() const
        {
            return FString::Printf(TEXT("frames=%d game_mean=%.3f game_median=%.3f game_p99=%.3f game_max=%.3f game_top5=%s busy_mean=%.3f busy_p99=%.3f busy_max=%.3f render_mean=%.3f render_max=%.3f gpu_mean=%.3f gpu_max=%.3f frames_over_16ms=%d collections=%d"),
                Num(), MeanOf(GameMs), PercentileOf(GameMs, 0.5), PercentileOf(GameMs, 0.99), MaxOf(GameMs), *TopOf(GameMs, 5), MeanOf(BusyMs), PercentileOf(BusyMs, 0.99),
                MaxOf(BusyMs), MeanOf(RenderMs), MaxOf(RenderMs), MeanOf(GpuMs), MaxOf(GpuMs), GameMs.FilterByPredicate([](double Ms) { return Ms > SpikeMs; }).Num(),
                Collections);
        }

        /**
         * The frames' cost above Baseline (the idle median), by what happened in them: frames with a commit and no
         * collection; frames with a release or a restore and no collection; frames with a collection; frames with none
         * of these (the background noise). A frame with a commit and a release counts in both of the first two.
         */
        FString DescribeAttribution(double Baseline, int32 IdleCollections) const
        {
            TArray<double> Commit, ReleaseOrRestore, Collection, Quiet;
            for (int32 Index = 0; Index < GameMs.Num() && Index < Tags.Num(); ++Index)
            {
                const double Above = GameMs[Index] - Baseline;
                const uint8 Tag = Tags[Index];
                if (Tag & FrameTagCollection)
                {
                    Collection.Add(Above);
                    continue;
                }
                if (Tag & FrameTagCommit)
                {
                    Commit.Add(Above);
                }
                if (Tag & FrameTagReleaseOrRestore)
                {
                    ReleaseOrRestore.Add(Above);
                }
                if (Tag == 0)
                {
                    Quiet.Add(Above);
                }
            }
            return FString::Printf(TEXT("idle_median_ms=%.3f commit_frames=%d commit_mean_ms=%.3f commit_p99_ms=%.3f commit_max_ms=%.3f release_restore_frames=%d release_restore_mean_ms=%.3f release_restore_p99_ms=%.3f release_restore_max_ms=%.3f collection_frames=%d collection_max_ms=%.3f quiet_frames=%d quiet_max_ms=%.3f collections_window=%d collections_idle_same_length=%d releases=%d restores=%d release_ms_total=%.3f release_ms_max_frame=%.3f"),
                Baseline, Commit.Num(), MeanOf(Commit), PercentileOf(Commit, 0.99), Commit.IsEmpty() ? 0.0 : FMath::Max(Commit),
                ReleaseOrRestore.Num(), MeanOf(ReleaseOrRestore), PercentileOf(ReleaseOrRestore, 0.99), ReleaseOrRestore.IsEmpty() ? 0.0 : FMath::Max(ReleaseOrRestore),
                Collection.Num(), Collection.IsEmpty() ? 0.0 : FMath::Max(Collection), Quiet.Num(), Quiet.IsEmpty() ? 0.0 : FMath::Max(Quiet),
                Collections, IdleCollections, Releases, Restores, ReleaseMsTotal, ReleaseMsMaxFrame);
        }

        /** Logs the window's summary, its terrain timings and its spikes under DIGSPIKE <Tag>. */
        void Log(const TCHAR* Tag) const
        {
            UE_LOG(LogTemp, Display, TEXT("DIGSPIKE %s %s"), Tag, *Describe());
            if (Watch.IsValid())
            {
                UE_LOG(LogTemp, Display, TEXT("DIGSPIKE %s_TERRAIN %s"), Tag, *Watch->Describe());
            }
            for (const FString& Spike : Spikes)
            {
                UE_LOG(LogTemp, Display, TEXT("DIGSPIKE %s_SPIKE %s"), Tag, *Spike);
            }
        }
    };

    using FFrameWindowRef = TSharedRef<FFrameWindow>;

    /**
     * Queues a wait until shaders have finished compiling, the terrain is idle and navigation is not building, all at
     * once for QuietSeconds of wall clock. Logs how long it waited.
     */
    void AddWaitForQuiet(const FDigGameSceneRef& Scene, const FString& TestName)
    {
        struct FQuiet
        {
            double StartSeconds = 0.0;
            double QuietSince = -1.0;
            int32 MostShaderJobs = 0;
        };
        TSharedRef<FQuiet> Quiet = MakeShared<FQuiet>();
        AddStep(Scene, TEXT("Shaders, terrain and navigation are quiet"), QuietTimeoutSeconds, [Quiet, TestName](FDigGameScene& S)
        {
            const double Now = FPlatformTime::Seconds();
            if (Quiet->StartSeconds == 0.0)
            {
                Quiet->StartSeconds = Now;
            }
            const int32 ShaderJobs = GShaderCompilingManager != nullptr ? GShaderCompilingManager->GetNumRemainingJobs() : 0;
            Quiet->MostShaderJobs = FMath::Max(Quiet->MostShaderJobs, ShaderJobs);
            const bool bShaders = GShaderCompilingManager == nullptr || !GShaderCompilingManager->IsCompiling();
            UNavigationSystemV1* Navigation = GetNavigation(S);
            const bool bNavigation = Navigation == nullptr || !Navigation->IsNavigationBuildInProgress();
            if (!bShaders || !bNavigation || !S.GetSubsystem()->IsIdle())
            {
                Quiet->QuietSince = -1.0;
                return false;
            }
            if (Quiet->QuietSince < 0.0)
            {
                Quiet->QuietSince = Now;
            }
            if (Now - Quiet->QuietSince < QuietSeconds)
            {
                return false;
            }
            UE_LOG(LogTemp, Display, TEXT("DIGSPIKE QUIET test=%s waited_s=%.1f most_shader_jobs=%d lumen_hwrt=%d"),
                *TestName, Now - Quiet->StartSeconds, Quiet->MostShaderJobs, IsLumenHardwareRayTracingActive() ? 1 : 0);
            return true;
        });
    }

    /** Queues a step that samples Frames frames (IdleFrames unless given) into Window. */
    void AddIdleWindow(const FDigGameSceneRef& Scene, const FFrameWindowRef& Window, int32 Frames = IdleFrames)
    {
        AddStep(Scene, TEXT("Sample the idle frames"), 120.0, [Window, Frames](FDigGameScene& S)
        {
            Window->Sample(&S);
            return Window->Num() >= Frames;
        });
    }

    /** The navmesh's game-thread request counters of the terrain at one moment. */
    struct FNavCounters
    {
        int32 Count = 0;
        double Seconds = 0.0;

        static FNavCounters Read(const FDigGameScene& Scene)
        {
            const AReflectionsDigTerrain* Terrain = Scene.Terrain.Get();
            return Terrain != nullptr ? FNavCounters{ Terrain->GetNavUpdateCount(), Terrain->GetNavUpdateSeconds() } : FNavCounters();
        }
    };

    /** The terrain's chunks in a fixed order (X fastest). */
    TArray<FIntVector> GetAllChunks(const AReflectionsDigTerrain& Terrain)
    {
        TArray<FIntVector> Chunks;
        const FIntVector Size = Terrain.GetGrid()->GetSizeInChunks();
        for (int32 Z = 0; Z < Size.Z; ++Z)
        {
            for (int32 Y = 0; Y < Size.Y; ++Y)
            {
                for (int32 X = 0; X < Size.X; ++X)
                {
                    Chunks.Add(FIntVector(X, Y, Z));
                }
            }
        }
        return Chunks;
    }

    /** A console variable set for a test and put back in its cleanup. */
    struct FSavedConsoleInt
    {
        FString Name;
        int32 OldValue = 0;
        bool bSaved = false;

        /** Remembers the current value (once) and sets Value; returns the value now in effect. */
        int32 Set(int32 Value)
        {
            IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(*Name);
            if (Variable == nullptr)
            {
                return -1;
            }
            if (!bSaved)
            {
                OldValue = Variable->GetInt();
                bSaved = true;
            }
            Variable->Set(Value, ECVF_SetByCode);
            return Variable->GetInt();
        }

        void Restore()
        {
            IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(*Name);
            if (bSaved && Variable != nullptr)
            {
                Variable->Set(OldValue, ECVF_SetByCode);
            }
            bSaved = false;
        }
    };

    /** A spawned camera the player views through; the view goes back to the character in the cleanup. */
    ACameraActor* SpawnViewCamera(FDigGameScene& Scene, const FVector& Location, const FVector& LookAt)
    {
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        ACameraActor* Camera = Scene.GetWorld()->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), Location, (LookAt - Location).Rotation(), Params);
        if (Camera != nullptr)
        {
            Camera->GetCameraComponent()->SetFieldOfView(90.0f);
            if (APlayerController* Controller = Scene.Controller.Get())
            {
                Controller->SetViewTargetWithBlend(Camera, 0.0f);
            }
        }
        return Camera;
    }

    void RemoveViewCamera(FDigGameScene& Scene, TWeakObjectPtr<ACameraActor>& Camera)
    {
        APlayerController* Controller = Scene.Controller.Get();
        if (Controller != nullptr && Scene.GetCharacter() != nullptr)
        {
            Controller->SetViewTargetWithBlend(Scene.GetCharacter(), 0.0f);
        }
        if (ACameraActor* Actor = Camera.Get())
        {
            Actor->Destroy();
        }
        Camera.Reset();
    }

    /** Digs a pit at (X, Y): stamps of RadiusCm from the ground down to DepthCm, every 100 cm. Returns how many changed the grid. */
    int32 DigPit(UReflectionsDigSubsystem& Subsystem, double X, double Y, double DepthCm, float RadiusCm)
    {
        int32 Changed = 0;
        for (double Z = GroundZ; Z >= GroundZ - DepthCm; Z -= 100.0)
        {
            Changed += Subsystem.Dig(FVector(X, Y, Z), RadiusCm, EReflectionsDigMode::Remove) ? 1 : 0;
        }
        return Changed;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSpikePerfRendererIsOnTest, "Reflections.SpikePerf.RendererIsOn", SpikePerfTestFlags)
bool FReflectionsSpikePerfRendererIsOnTest::RunTest(const FString& Parameters)
{
    const bool bNullRhi = FApp::IsNullRHIRequested() || !FApp::CanEverRender();
    TestFalse(TEXT("The process does not use the null RHI"), bNullRhi);
    const UGameViewportClient* ViewportClient = GEngine != nullptr ? GEngine->GameViewport.Get() : nullptr;
    const FViewport* Viewport = ViewportClient != nullptr ? ViewportClient->Viewport : nullptr;
    TestNotNull(TEXT("A game viewport exists"), Viewport);
    const FIntPoint Size = Viewport != nullptr ? Viewport->GetSizeXY() : FIntPoint::ZeroValue;
    const TOptional<EShaderPlatform> Platform = GetSceneShaderPlatform();
    TestTrue(TEXT("The game world has a scene"), Platform.IsSet());
    UE_LOG(LogTemp, Display, TEXT("DIGSPIKE RENDER rhi=%s raytracing=%d lumen_hwrt=%d resolution=%dx%d"),
        *FApp::GetGraphicsRHI().Replace(TEXT(" "), TEXT("")), IsRayTracingEnabled() ? 1 : 0, IsLumenHardwareRayTracingActive() ? 1 : 0, Size.X, Size.Y);
    UE_LOG(LogTemp, Display, TEXT("DIGSPIKE RENDER detail null_rhi=%d shader_platform=%d inline_rt=%d rt_shaders=%d r.Lumen.HardwareRayTracing=%d r.DynamicGlobalIlluminationMethod=%d r.RayTracing.Enable=%d r.Shadow.Virtual.Enable=%d"),
        bNullRhi ? 1 : 0, Platform.IsSet() ? static_cast<int32>(*Platform) : -1,
        Platform.IsSet() && CanUseInlineRayTracing(*Platform) ? 1 : 0, Platform.IsSet() && CanUseRayTracingShaders(*Platform) ? 1 : 0,
        GetConsoleInt(TEXT("r.Lumen.HardwareRayTracing")), GetConsoleInt(TEXT("r.DynamicGlobalIlluminationMethod")),
        GetConsoleInt(TEXT("r.RayTracing.Enable")), GetConsoleInt(TEXT("r.Shadow.Virtual.Enable")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSpikePerfDigCostTest, "Reflections.SpikePerf.DigCost", SpikePerfTestFlags)
bool FReflectionsSpikePerfDigCostTest::RunTest(const FString& Parameters)
{
    constexpr double X = 1800.0;
    constexpr double Y = -1600.0;
    constexpr double WindowSeconds = 30.0;
    constexpr double DigEverySeconds = 0.1;
    /** At the bottom, a pocket beside the shaft is dug out and filled back in turn, so every dig still changes the ground. */
    const FVector Pocket(X + 200.0, Y, BedrockTopZ + 125.0);
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, X, Y);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();
    const FFrameWindowRef Idle = MakeShared<FFrameWindow>();
    const FFrameWindowRef Digging = MakeShared<FFrameWindow>();

    struct FDigWindow
    {
        double StartSeconds = -1.0;
        double NextDigSeconds = 0.0;
        double CursorZ = 0.0;
        bool bAtBottom = false;
        bool bFillNext = false;
        double BottomAtSeconds = -1.0;
        int32 Attempts = 0;
        int32 Changed = 0;
        int32 DownDigs = 0;
        int32 PocketDigs = 0;
        double StartFeetZ = 0.0;
        double DigCallMaxMs = 0.0;
        double DigCallTotalMs = 0.0;
        int32 MostCommitsInATick = 0;
        FNavCounters NavAtStart;
    };
    TSharedRef<FDigWindow> Window = MakeShared<FDigWindow>();

    AddWaitForRest(Scene, TEXT("The character rests at the dig site"));
    AddWaitForQuiet(Scene, TEXT("DigCost"));
    // As long as the dig window, so garbage collections can be compared between the two.
    AddIdleWindow(Scene, Idle, 1800);
    AddStep(Scene, TEXT("Dig under the character every 0.1 s for 30 s"), 180.0, [Digging, Window, X, Y, WindowSeconds, DigEverySeconds, Pocket](FDigGameScene& S)
    {
        const double Now = S.GetWorld()->GetTimeSeconds();
        if (Window->StartSeconds < 0.0)
        {
            Window->StartSeconds = Now;
            Window->NextDigSeconds = Now;
            Window->StartFeetZ = S.GetFeetZ();
            Window->CursorZ = S.GetFeetZ();
            Window->NavAtStart = FNavCounters::Read(S);
            Digging->Start();
        }
        Digging->Sample(&S);
        Window->MostCommitsInATick = FMath::Max(Window->MostCommitsInATick, S.GetSubsystem()->GetCommitsLastTick());
        if (Now - Window->StartSeconds >= WindowSeconds)
        {
            return true;
        }
        if (Now < Window->NextDigSeconds)
        {
            return false;
        }
        Window->NextDigSeconds += DigEverySeconds;
        ++Window->Attempts;
        UReflectionsDigSubsystem& Subsystem = *S.GetSubsystem();
        const double CallStart = FPlatformTime::Seconds();
        bool bChanged = false;
        if (!Window->bAtBottom)
        {
            // Straight down under the character: from its feet, or deeper when the ground there is already dug.
            Window->CursorZ = FMath::Min(Window->CursorZ, S.GetFeetZ());
            for (int32 Try = 0; Try < 4 && !bChanged; ++Try)
            {
                if (Window->CursorZ < BedrockTopZ + 50.0)
                {
                    Window->bAtBottom = true;
                    Window->BottomAtSeconds = Now - Window->StartSeconds;
                    break;
                }
                bChanged = Subsystem.Dig(FVector(X, Y, Window->CursorZ), DigRadiusCm, EReflectionsDigMode::Remove);
                if (!bChanged)
                {
                    Window->CursorZ -= 50.0;
                }
            }
            Window->DownDigs += bChanged ? 1 : 0;
        }
        if (Window->bAtBottom && !bChanged)
        {
            bChanged = Subsystem.Dig(Pocket, DigRadiusCm, Window->bFillNext ? EReflectionsDigMode::Add : EReflectionsDigMode::Remove);
            Window->bFillNext = !Window->bFillNext;
            Window->PocketDigs += bChanged ? 1 : 0;
        }
        const double CallMs = (FPlatformTime::Seconds() - CallStart) * 1000.0;
        Window->DigCallMaxMs = FMath::Max(Window->DigCallMaxMs, CallMs);
        Window->DigCallTotalMs += CallMs;
        Window->Changed += bChanged ? 1 : 0;
        return false;
    });
    AddAction(Scene, TEXT("Log the dig cost"), [Idle, Digging, Window](FDigGameScene& S)
    {
        const FNavCounters NavNow = FNavCounters::Read(S);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE DIG idle_mean_ms=%.3f idle_max_ms=%.3f dig_max_ms=%.3f dig_p99_ms=%.3f dig_mean_ms=%.3f digs=%d nav_updates=%d nav_ms_total=%.3f"),
            MeanOf(Idle->GameMs), MaxOf(Idle->GameMs), MaxOf(Digging->GameMs), PercentileOf(Digging->GameMs, 0.99), MeanOf(Digging->GameMs),
            Window->Changed, NavNow.Count - Window->NavAtStart.Count, (NavNow.Seconds - Window->NavAtStart.Seconds) * 1000.0);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE DIG_EXTRA site=(1800,-1600) attempts=%d down_digs=%d pocket_digs=%d bottom_at_s=%.2f feet_start=%.1f feet_end=%.1f dig_call_max_ms=%.3f dig_call_total_ms=%.3f most_commits_in_a_tick=%d lumen_hwrt=%d"),
            Window->Attempts, Window->DownDigs, Window->PocketDigs, Window->BottomAtSeconds, Window->StartFeetZ, S.GetFeetZ(),
            Window->DigCallMaxMs, Window->DigCallTotalMs, Window->MostCommitsInATick, IsLumenHardwareRayTracingActive() ? 1 : 0);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE DIG_ATTRIB %s"), *Digging->DescribeAttribution(PercentileOf(Idle->GameMs, 0.5), Idle->Collections));
        Idle->Log(TEXT("DIG_IDLE"));
        Digging->Log(TEXT("DIG_WINDOW"));
        Digging->Stop();
        S.Test->TestTrue(TEXT("The dig window dug"), Window->Changed > 0);
    });
    AddCleanup(Scene);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSpikePerfStreamingCostTest, "Reflections.SpikePerf.StreamingCost", SpikePerfTestFlags)
bool FReflectionsSpikePerfStreamingCostTest::RunTest(const FString& Parameters)
{
    const FVector2D From(1100.0, -2300.0);
    const FVector2D To(5700.0, 2300.0);
    constexpr double WalkSeconds = 20.0;
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, From.X, From.Y);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();
    const FFrameWindowRef Idle = MakeShared<FFrameWindow>();
    const FFrameWindowRef Walking = MakeShared<FFrameWindow>();

    struct FWalk
    {
        double StartSeconds = -1.0;
        double EndWallSeconds = 0.0;
        TArray<FIntVector> Chunks;
        TArray<bool> Shown;
        int32 Released = 0;
        int32 Restored = 0;
        int32 ShownAtStart = 0;
        int32 MostCommitsInATick = 0;
    };
    TSharedRef<FWalk> Walk = MakeShared<FWalk>();
    auto CountShown = [](const AReflectionsDigTerrain& Terrain, const TArray<FIntVector>& Chunks, TArray<bool>& OutShown)
    {
        OutShown.SetNum(Chunks.Num());
        int32 Count = 0;
        for (int32 Index = 0; Index < Chunks.Num(); ++Index)
        {
            OutShown[Index] = Terrain.GetChunkPieceCount(Chunks[Index]) > 0;
            Count += OutShown[Index] ? 1 : 0;
        }
        return Count;
    };

    AddWaitForRest(Scene, TEXT("The character rests at the start corner"));
    AddWaitForQuiet(Scene, TEXT("StreamingCost"));
    // As long as the walk, so garbage collections can be compared between the two.
    AddIdleWindow(Scene, Idle, 1200);
    AddStep(Scene, TEXT("Move the character corner to corner over 20 s"), 120.0, [Walking, Walk, From, To, WalkSeconds, CountShown](FDigGameScene& S)
    {
        const AReflectionsDigTerrain* Terrain = S.Terrain.Get();
        if (Terrain == nullptr)
        {
            S.Abort(TEXT("The terrain is gone"));
            return true;
        }
        const double Now = S.GetWorld()->GetTimeSeconds();
        if (Walk->StartSeconds < 0.0)
        {
            Walk->StartSeconds = Now;
            Walk->Chunks = GetAllChunks(*Terrain);
            Walk->ShownAtStart = CountShown(*Terrain, Walk->Chunks, Walk->Shown);
            Walking->Start();
        }
        Walking->Sample(&S);
        Walk->MostCommitsInATick = FMath::Max(Walk->MostCommitsInATick, S.GetSubsystem()->GetCommitsLastTick());
        // What the last tick did: count every chunk that stopped or started showing pieces.
        TArray<bool> ShownNow;
        CountShown(*Terrain, Walk->Chunks, ShownNow);
        for (int32 Index = 0; Index < ShownNow.Num(); ++Index)
        {
            Walk->Released += Walk->Shown[Index] && !ShownNow[Index] ? 1 : 0;
            Walk->Restored += !Walk->Shown[Index] && ShownNow[Index] ? 1 : 0;
        }
        Walk->Shown = MoveTemp(ShownNow);
        const double Alpha = FMath::Clamp((Now - Walk->StartSeconds) / WalkSeconds, 0.0, 1.0);
        const FVector2D At = FMath::Lerp(From, To, Alpha);
        Teleport(S, At.X, At.Y);
        if (Alpha >= 1.0)
        {
            Walk->EndWallSeconds = FPlatformTime::Seconds();
            return true;
        }
        return false;
    });
    AddStep(Scene, TEXT("Idle after the walk"), ReadyTimeoutSeconds, [Walk](FDigGameScene& S) { return S.GetSubsystem()->IsIdle(); });
    AddAction(Scene, TEXT("Log the streaming cost"), [Idle, Walking, Walk](FDigGameScene& S)
    {
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE STREAM idle_max_ms=%.3f max_ms=%.3f p99_ms=%.3f chunks_released=%d chunks_restored=%d"),
            MaxOf(Idle->GameMs), MaxOf(Walking->GameMs), PercentileOf(Walking->GameMs, 0.99), Walk->Released, Walk->Restored);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE STREAM_EXTRA from=(1100,-2300) to=(5700,2300) walk_s=%.1f idle_mean_ms=%.3f mean_ms=%.3f chunks_shown_at_start=%d most_commits_in_a_tick=%d idle_after_walk_s=%.3f lumen_hwrt=%d"),
            S.GetWorld()->GetTimeSeconds() - Walk->StartSeconds, MeanOf(Idle->GameMs), MeanOf(Walking->GameMs), Walk->ShownAtStart, Walk->MostCommitsInATick,
            FPlatformTime::Seconds() - Walk->EndWallSeconds, IsLumenHardwareRayTracingActive() ? 1 : 0);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE STREAM_ATTRIB %s"), *Walking->DescribeAttribution(PercentileOf(Idle->GameMs, 0.5), Idle->Collections));
        Idle->Log(TEXT("STREAM_IDLE"));
        Walking->Log(TEXT("STREAM_WINDOW"));
        Walking->Stop();
        S.Test->TestTrue(TEXT("Chunks were released and restored during the walk"), Walk->Released > 0 && Walk->Restored > 0);
    });
    AddCleanup(Scene);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSpikePerfCollisionSizeTest, "Reflections.SpikePerf.CollisionSize", SpikePerfTestFlags)
bool FReflectionsSpikePerfCollisionSizeTest::RunTest(const FString& Parameters)
{
    /**
     * The digs fill one chunk column, (2, 2, *): X 4225..5800, Y 825..2400 (the grid origin, and so every chunk border,
     * sits half a cell inside the actor's corner), from the grid floor's bedrock up to the ground.
     */
    const FBox DigBox(FVector(4225.0, 825.0, -2700.0), FVector(5800.0, 2400.0, GroundZ));
    constexpr int32 Digs = 200;
    constexpr int32 Seed = 20261122;
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, 5000.0, -400.0);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();
    const FFrameWindowRef Burst = MakeShared<FFrameWindow>();
    TSharedRef<int32> Changed = MakeShared<int32>(0);

    AddWaitForRest(Scene, TEXT("The character rests beside the dig column"));
    AddWaitForQuiet(Scene, TEXT("CollisionSize"));
    AddAction(Scene, TEXT("Dig 200 seeded random points"), [Burst, DigBox, Changed, Digs, Seed](FDigGameScene& S)
    {
        Burst->Start();
        FRandomStream Random(Seed);
        for (int32 Index = 0; Index < Digs; ++Index)
        {
            const FVector Point(Random.FRandRange(DigBox.Min.X, DigBox.Max.X), Random.FRandRange(DigBox.Min.Y, DigBox.Max.Y),
                Random.FRandRange(DigBox.Min.Z, DigBox.Max.Z));
            *Changed += S.GetSubsystem()->Dig(Point, DigRadiusCm, EReflectionsDigMode::Remove) ? 1 : 0;
        }
    });
    AddStep(Scene, TEXT("Idle after the 200 digs"), 120.0, [Burst](FDigGameScene& S)
    {
        Burst->Sample(&S);
        return S.GetSubsystem()->IsIdle();
    });
    AddAction(Scene, TEXT("Log the collision size"), [Burst, Changed](FDigGameScene& S)
    {
        const AReflectionsDigTerrain* Terrain = S.Terrain.Get();
        if (Terrain == nullptr)
        {
            S.Abort(TEXT("The terrain is gone"));
            return;
        }
        int32 MostPieces = 0;
        FIntVector MostPiecesChunk = FIntVector::ZeroValue;
        for (const FIntVector& Chunk : GetAllChunks(*Terrain))
        {
            if (Terrain->GetChunkPieceCount(Chunk) > MostPieces)
            {
                MostPieces = Terrain->GetChunkPieceCount(Chunk);
                MostPiecesChunk = Chunk;
            }
        }
        // Each piece is its own collision mesh; a chunk's pieces together are its whole collision.
        TMap<FIntVector, int32> ChunkVertices;
        TArray<UReflectionsDigChunkComponent*> Pieces;
        Terrain->GetComponents(Pieces);
        for (const UReflectionsDigChunkComponent* Piece : Pieces)
        {
            if (Piece->IsVisible() && Piece->GetMesh() != nullptr)
            {
                ChunkVertices.FindOrAdd(ChunkAt(*Terrain, Piece->Bounds.Origin)) += Piece->GetMesh()->VertexCount();
            }
        }
        int32 MostChunkVertices = 0;
        for (const TPair<FIntVector, int32>& Pair : ChunkVertices)
        {
            MostChunkVertices = FMath::Max(MostChunkVertices, Pair.Value);
        }
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE COLLISION largest_vertices=%d pieces_max_per_chunk=%d"), Terrain->GetLargestCollisionVertexCount(), MostPieces);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE COLLISION_EXTRA column=X4225..5800,Y825..2400 seed=%d digs_changed=%d most_pieces_chunk=%s chunk_vertices_max=%d"),
            20261122, *Changed, *MostPiecesChunk.ToString(), MostChunkVertices);
        Burst->Log(TEXT("COLLISION_BURST"));
        Burst->Stop();
    });
    AddCleanup(Scene);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSpikePerfSeamsTest, "Reflections.SpikePerf.Seams", SpikePerfTestFlags)
bool FReflectionsSpikePerfSeamsTest::RunTest(const FString& Parameters)
{
    constexpr int32 PerLine = 100;
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, 3400.0, 0.0);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();

    AddWaitForRest(Scene, TEXT("The character rests in the middle of the patch"));
    AddWaitForQuiet(Scene, TEXT("Seams"));
    AddAction(Scene, TEXT("Trace along the borders and the join"), [PerLine](FDigGameScene& S)
    {
        struct FLine
        {
            const TCHAR* Name;
            /** True: X is fixed and the samples run along Y. */
            bool bAlongY;
            double Fixed;
        };
        // The join with the cube ground, and the chunk borders inside the patch.
        const FLine Lines[] = {
            { TEXT("join X=1000"), true, 1000.0 },
            { TEXT("border X=2625"), true, 2625.0 },
            { TEXT("border X=4225"), true, 4225.0 },
            { TEXT("border Y=-775"), false, -775.0 },
            { TEXT("border Y=825"), false, 825.0 },
        };
        int32 Traces = 0;
        int32 Misses = 0;
        int32 OnChunks = 0;
        int32 OnGround = 0;
        double LowestHitZ = TNumericLimits<double>::Max();
        double HighestHitZ = -TNumericLimits<double>::Max();
        for (const FLine& Line : Lines)
        {
            const double Lo = Line.bAlongY ? -2400.0 : 1000.0;
            // The other lines this one crosses: the sample nearest each crossing goes exactly onto it.
            const TArray<double> Crossings = Line.bAlongY ? TArray<double>{ -775.0, 825.0 } : TArray<double>{ 1000.0, 2625.0, 4225.0 };
            int32 LineMisses = 0;
            for (int32 Index = 0; Index < PerLine; ++Index)
            {
                double Along = Lo + 24.0 + 48.0 * Index;
                for (const double Crossing : Crossings)
                {
                    if (FMath::Abs(Along - Crossing) < 24.0)
                    {
                        Along = Crossing;
                    }
                }
                // Exactly on the line, 1 cm before it and 1 cm past it, in turn.
                const double Across = Line.Fixed + static_cast<double>(Index % 3 - 1);
                const double TX = Line.bAlongY ? Across : Along;
                const double TY = Line.bAlongY ? Along : Across;
                const TOptional<FHitResult> Hit = FReflectionsDigTestTraces::TraceDown(S.GetWorld(), TX, TY, TraceStartZ, TraceEndZ, S.GetCharacter());
                ++Traces;
                const bool bChunk = Hit.IsSet() && Cast<UReflectionsDigChunkComponent>(Hit->GetComponent()) != nullptr;
                const bool bGround = Hit.IsSet() && Cast<AStaticMeshActor>(Hit->GetActor()) != nullptr;
                // A miss falls through the ground: nothing, the safety floor, anything else, or a hit under the grid floor.
                if (!(bChunk || bGround) || Hit->ImpactPoint.Z <= GridFloorZ)
                {
                    ++Misses;
                    ++LineMisses;
                    if (Misses <= 20)
                    {
                        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE SEAMS_MISS line=\"%s\" at=(%.1f,%.1f) hit=%s z=%s"), Line.Name, TX, TY,
                            Hit.IsSet() ? *GetNameSafe(Hit->GetComponent()) : TEXT("nothing"),
                            Hit.IsSet() ? *FString::SanitizeFloat(Hit->ImpactPoint.Z) : TEXT("-"));
                    }
                    continue;
                }
                OnChunks += bChunk ? 1 : 0;
                OnGround += bGround ? 1 : 0;
                LowestHitZ = FMath::Min(LowestHitZ, Hit->ImpactPoint.Z);
                HighestHitZ = FMath::Max(HighestHitZ, Hit->ImpactPoint.Z);
            }
            UE_LOG(LogTemp, Display, TEXT("DIGSPIKE SEAMS_LINE line=\"%s\" traces=%d misses=%d"), Line.Name, PerLine, LineMisses);
        }
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE SEAMS traces=%d misses=%d"), Traces, Misses);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE SEAMS_EXTRA on_chunk_pieces=%d on_cube_ground=%d lowest_hit_z=%.1f highest_hit_z=%.1f"),
            OnChunks, OnGround, LowestHitZ, HighestHitZ);
        S.Test->TestEqual(TEXT("Traces made"), Traces, 500);

        // Not among the 500: how close to each outer edge of the patch a trace still finds ground (1 cm steps inwards
        // from 2 cm outside the edge, on the patch's middle lines). A gap here is the patch's own edge, not a seam.
        struct FEdge
        {
            const TCHAR* Name;
            FVector2D Outside;
            FVector2D Inwards;
        };
        const FEdge Edges[] = {
            { TEXT("X=1000 (cube ground side)"), FVector2D(998.0, 0.0), FVector2D(1.0, 0.0) },
            { TEXT("X=5800"), FVector2D(5802.0, 0.0), FVector2D(-1.0, 0.0) },
            { TEXT("Y=-2400"), FVector2D(3400.0, -2402.0), FVector2D(0.0, 1.0) },
            { TEXT("Y=2400"), FVector2D(3400.0, 2402.0), FVector2D(0.0, -1.0) },
        };
        for (const FEdge& Edge : Edges)
        {
            int32 Step = 0;
            for (; Step <= 200; ++Step)
            {
                const FVector2D At = Edge.Outside + Edge.Inwards * Step;
                const TOptional<FHitResult> Hit = FReflectionsDigTestTraces::TraceDown(S.GetWorld(), At.X, At.Y, TraceStartZ, TraceEndZ, S.GetCharacter());
                if (Hit.IsSet() && Hit->ImpactPoint.Z > GridFloorZ)
                {
                    break;
                }
            }
            UE_LOG(LogTemp, Display, TEXT("DIGSPIKE SEAMS_EDGE edge=\"%s\" first_ground_cm_inside_edge=%d"), Edge.Name, Step - 2);
        }
    });
    AddCleanup(Scene);
    return true;
}

namespace
{
    /** One screenshot the game viewport hands over (the engine saves nothing itself while the delegate is bound). */
    struct FShotCapture
    {
        FDelegateHandle Handle;
        bool bRequested = false;
        bool bCaptured = false;
        int32 Width = 0;
        int32 Height = 0;
        TArray<FColor> Pixels;
        double RequestedAt = 0.0;
        double SettleFrom = -1.0;
        int32 SettleFrames = 0;
    };
    using FShotCaptureRef = TSharedRef<FShotCapture>;

    FString GetShotDirectory()
    {
        return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("ArtDirection/Digging/SpikeShots")));
    }

    /**
     * Queues a screenshot: waits until shaders are done and at least SettleSeconds (wall clock) and 120 frames have
     * passed since the step began, requests it, waits for the pixels, saves them as <Name>.png and logs what was in
     * effect and how bright the image is.
     */
    void AddShot(const FDigGameSceneRef& Scene, const FShotCaptureRef& Capture, const FString& Name, int32 HwrtRequested, double SettleSeconds)
    {
        AddStep(Scene, FString::Printf(TEXT("Shot %s"), *Name), 300.0, [Capture, Name, HwrtRequested, SettleSeconds](FDigGameScene& S)
        {
            const double Now = FPlatformTime::Seconds();
            if (!Capture->bRequested)
            {
                if (Capture->SettleFrom < 0.0)
                {
                    Capture->SettleFrom = Now;
                    Capture->SettleFrames = 0;
                }
                ++Capture->SettleFrames;
                const bool bShaders = GShaderCompilingManager == nullptr || !GShaderCompilingManager->IsCompiling();
                if (!bShaders || Now - Capture->SettleFrom < SettleSeconds || Capture->SettleFrames < 120)
                {
                    return false;
                }
                Capture->bCaptured = false;
                Capture->bRequested = true;
                Capture->RequestedAt = Now;
                FScreenshotRequest::RequestScreenshot(/*bInShowUI=*/ false);
                return false;
            }
            if (!Capture->bCaptured)
            {
                return false;
            }
            // Brightness: mean luma (0..255) and the share of pixels darker than 8.
            double LumaSum = 0.0;
            int32 Dark = 0;
            for (const FColor& Pixel : Capture->Pixels)
            {
                const double Luma = 0.2126 * Pixel.R + 0.7152 * Pixel.G + 0.0722 * Pixel.B;
                LumaSum += Luma;
                Dark += Luma < 8.0 ? 1 : 0;
            }
            const int32 Count = FMath::Max(1, Capture->Pixels.Num());
            const FString Path = FPaths::Combine(GetShotDirectory(), Name + TEXT(".png"));
            TArray64<uint8> Png;
            FImageUtils::PNGCompressImageArray(Capture->Width, Capture->Height, TArrayView64<const FColor>(Capture->Pixels.GetData(), Capture->Pixels.Num()), Png);
            IFileManager::Get().MakeDirectory(*GetShotDirectory(), /*Tree=*/ true);
            const bool bSaved = !Png.IsEmpty() && FFileHelper::SaveArrayToFile(Png, *Path);
            S.Test->TestTrue(FString::Printf(TEXT("Saved %s"), *Path), bSaved);
            UE_LOG(LogTemp, Display, TEXT("DIGSPIKE SHOT name=%s hwrt_requested=%d r.Lumen.HardwareRayTracing=%d hwrt_active=%d size=%dx%d mean_luma=%.1f dark_pct=%.1f saved=%d"),
                *Name, HwrtRequested, GetConsoleInt(TEXT("r.Lumen.HardwareRayTracing")), IsLumenHardwareRayTracingActive() ? 1 : 0,
                Capture->Width, Capture->Height, LumaSum / Count, 100.0 * Dark / Count, bSaved ? 1 : 0);
            // Where the rendered view really was, and what it looked at first (a trace along its centre line).
            const APlayerController* Controller = S.Controller.Get();
            if (Controller != nullptr && Controller->PlayerCameraManager != nullptr)
            {
                const FVector ViewAt = Controller->PlayerCameraManager->GetCameraLocation();
                const FVector Forward = Controller->PlayerCameraManager->GetCameraRotation().Vector();
                FHitResult Hit;
                const bool bHit = S.GetWorld()->LineTraceSingleByChannel(Hit, ViewAt, ViewAt + Forward * 5000.0, ECC_Visibility,
                    FCollisionQueryParams(SCENE_QUERY_STAT(ReflectionsDigShotView), false, S.GetCharacter()));
                UE_LOG(LogTemp, Display, TEXT("DIGSPIKE SHOT_VIEW name=%s view_target=%s camera=(%.0f,%.0f,%.0f) forward=(%.2f,%.2f,%.2f) first_hit=%s distance=%.0f"),
                    *Name, *GetNameSafe(Controller->PlayerCameraManager->GetViewTarget()), ViewAt.X, ViewAt.Y, ViewAt.Z, Forward.X, Forward.Y, Forward.Z,
                    bHit ? *GetNameSafe(Hit.GetComponent()) : TEXT("nothing"), bHit ? Hit.Distance : -1.0);
            }
            Capture->bRequested = false;
            Capture->SettleFrom = -1.0;
            Capture->Pixels.Reset();
            return true;
        });
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSpikePerfCaveShotsTest, "Reflections.SpikePerf.CaveShots", SpikePerfTestFlags)
bool FReflectionsSpikePerfCaveShotsTest::RunTest(const FString& Parameters)
{
    constexpr double PitX = 1800.0;
    constexpr double PitY = 1400.0;
    /** The tunnel runs along +X at the height of the pit's lowest stamp. */
    constexpr double TunnelZ = -300.0;
    constexpr double TunnelLengthCm = 500.0;
    /** Lumen and the automatic exposure need a moment after a light, the view or a setting changes. */
    constexpr double SettleSeconds = 8.0;
    /**
     * For the shots only: the cave light just inside the tunnel's mouth, under its roof, and dimmed from the map's
     * 5000, so the walls fade with distance down the tunnel instead of glowing around a light in the middle of the
     * view. Put back in the cleanup.
     */
    const FVector LightInTunnel(PitX + 100.0, PitY, TunnelZ + 80.0);
    constexpr float ShotLightIntensity = 300.0f;
    const FVector TunnelCamera(PitX - 50.0, PitY, TunnelZ + 40.0);
    const FVector TunnelLookAt(PitX + TunnelLengthCm, PitY, TunnelZ);
    /** From above the rim, looking down into the pit towards the tunnel's mouth. */
    const FVector PitCamera(PitX - 250.0, PitY - 150.0, 220.0);
    const FVector PitLookAt(PitX + 50.0, PitY, TunnelZ);
    /** Inside the tunnel, 150 cm along it, looking across at its +Y wall. */
    const FVector WallCamera(PitX + 150.0, PitY, TunnelZ + 20.0);
    const FVector WallLookAt(PitX + 150.0, PitY + 300.0, TunnelZ + 20.0);
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, PitX, PitY - 1000.0);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();

    struct FCave
    {
        TWeakObjectPtr<APointLight> Light;
        FVector LightHome = FVector::ZeroVector;
        TWeakObjectPtr<ACameraActor> Camera;
        float LightIntensityHome = 0.0f;
        FSavedConsoleInt Hwrt{ TEXT("r.Lumen.HardwareRayTracing") };
    };
    TSharedRef<FCave> Cave = MakeShared<FCave>();
    const FShotCaptureRef Capture = MakeShared<FShotCapture>();

    AddWaitForRest(Scene, TEXT("The character rests beside the cave site"));
    AddAction(Scene, TEXT("Dig the pit and the tunnel"), [](FDigGameScene& S)
    {
        S.Test->TestTrue(TEXT("The pit digs"), DigPit(*S.GetSubsystem(), PitX, PitY, GroundZ - TunnelZ, DigRadiusCm) > 0);
        // Two rows of stamps 80 cm apart: a tunnel about 280 cm high.
        int32 Changed = 0;
        for (double Along = 0.0; Along <= TunnelLengthCm; Along += 50.0)
        {
            Changed += S.GetSubsystem()->Dig(FVector(PitX + Along, PitY, TunnelZ - 40.0), DigRadiusCm, EReflectionsDigMode::Remove) ? 1 : 0;
            Changed += S.GetSubsystem()->Dig(FVector(PitX + Along, PitY, TunnelZ + 40.0), DigRadiusCm, EReflectionsDigMode::Remove) ? 1 : 0;
        }
        S.Test->TestTrue(TEXT("The tunnel digs"), Changed > 0);
    });
    AddWaitForQuiet(Scene, TEXT("CaveShots"));
    AddAction(Scene, TEXT("Put the cave light in the tunnel and bind the screenshot"), [Cave, Capture, LightInTunnel, ShotLightIntensity, TunnelCamera, TunnelLookAt](FDigGameScene& S)
    {
        APointLight* Light = nullptr;
        for (TActorIterator<APointLight> It(S.GetWorld()); It; ++It)
        {
#if WITH_EDITOR
            if (It->GetActorLabel() == TEXT("DigSpike_CaveLight1"))
            {
                Light = *It;
                break;
            }
#endif
            // Without labels: the map puts CaveLight1 at (2800, -600, 250).
            if (Light == nullptr && It->GetActorLocation().Equals(FVector(2800.0, -600.0, 250.0), 1.0))
            {
                Light = *It;
            }
        }
        if (Light == nullptr)
        {
            S.Abort(TEXT("DigSpike_CaveLight1 is not in the map"));
            return;
        }
        Cave->Light = Light;
        Cave->LightHome = Light->GetActorLocation();
        Cave->LightIntensityHome = Light->GetLightComponent()->Intensity;
        Light->SetActorLocation(LightInTunnel);
        Light->GetLightComponent()->SetIntensity(ShotLightIntensity);
        Cave->Camera = SpawnViewCamera(S, TunnelCamera, TunnelLookAt);
        if (!Cave->Camera.IsValid())
        {
            S.Abort(TEXT("Could not spawn the view camera"));
            return;
        }
        Capture->Handle = UGameViewportClient::OnScreenshotCaptured().AddLambda([Capture](int32 Width, int32 Height, const TArray<FColor>& Colors)
        {
            if (Capture->bRequested && !Capture->bCaptured)
            {
                Capture->Width = Width;
                Capture->Height = Height;
                Capture->Pixels = Colors;
                Capture->bCaptured = true;
            }
        });
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE CAVE light=%s moved from %s to %s, intensity %.0f (unitless) instead of %.0f; ground material %s"),
            *Light->GetName(), *Cave->LightHome.ToString(), *LightInTunnel.ToString(), ShotLightIntensity, Cave->LightIntensityHome,
            *GetNameSafe(S.Terrain.IsValid() ? S.Terrain->GroundMaterial.Get() : nullptr));
    });
    auto AddView = [Scene, Cave](const FVector& Location, const FVector& LookAt, int32 Hwrt)
    {
        AddAction(Scene, TEXT("Set the view and the ray tracing"), [Cave, Location, LookAt, Hwrt](FDigGameScene& S)
        {
            if (ACameraActor* Camera = Cave->Camera.Get())
            {
                Camera->SetActorLocationAndRotation(Location, (LookAt - Location).Rotation());
            }
            const int32 InEffect = Cave->Hwrt.Set(Hwrt);
            S.Test->TestEqual(TEXT("r.Lumen.HardwareRayTracing took the value asked for"), InEffect, Hwrt);
        });
    };
    AddView(TunnelCamera, TunnelLookAt, 1);
    AddShot(Scene, Capture, TEXT("tunnel_hwrt_on"), 1, SettleSeconds);
    AddView(PitCamera, PitLookAt, 1);
    AddShot(Scene, Capture, TEXT("pit_hwrt_on"), 1, SettleSeconds);
    AddView(WallCamera, WallLookAt, 1);
    AddShot(Scene, Capture, TEXT("tunnel_wall_hwrt_on"), 1, SettleSeconds);
    AddView(TunnelCamera, TunnelLookAt, 0);
    AddShot(Scene, Capture, TEXT("tunnel_hwrt_off"), 0, SettleSeconds);
    AddView(PitCamera, PitLookAt, 0);
    AddShot(Scene, Capture, TEXT("pit_hwrt_off"), 0, SettleSeconds);
    AddView(WallCamera, WallLookAt, 0);
    AddShot(Scene, Capture, TEXT("tunnel_wall_hwrt_off"), 0, SettleSeconds);
    AddStep(Scene, TEXT("Restore the light, the view and the settings"), 1.0, [Cave, Capture](FDigGameScene& S)
    {
        Cave->Hwrt.Restore();
        if (Capture->Handle.IsValid())
        {
            UGameViewportClient::OnScreenshotCaptured().Remove(Capture->Handle);
            Capture->Handle.Reset();
        }
        if (Capture->bRequested && !Capture->bCaptured)
        {
            FScreenshotRequest::Reset();
        }
        if (APointLight* Light = Cave->Light.Get())
        {
            Light->SetActorLocation(Cave->LightHome);
            Light->GetLightComponent()->SetIntensity(Cave->LightIntensityHome);
        }
        if (S.GetWorld() != nullptr)
        {
            RemoveViewCamera(S, Cave->Camera);
        }
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE CAVE restored r.Lumen.HardwareRayTracing=%d hwrt_active=%d"),
            GetConsoleInt(TEXT("r.Lumen.HardwareRayTracing")), IsLumenHardwareRayTracingActive() ? 1 : 0);
        return true;
    }, /*bAlwaysRun=*/ true);
    AddCleanup(Scene);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSpikePerfShadowCostTest, "Reflections.SpikePerf.ShadowCost", SpikePerfTestFlags)
bool FReflectionsSpikePerfShadowCostTest::RunTest(const FString& Parameters)
{
    constexpr double PitX = 4000.0;
    constexpr double PitY = -1600.0;
    constexpr float PitRadiusCm = 150.0f;
    constexpr double WindowSeconds = 10.0;
    constexpr double DigEverySeconds = 0.1;
    /** The sun (pitch -45, yaw 30) shines towards +X+Y: the camera stands on the sun's side and looks at the lit far rim. */
    const FVector CameraAt(PitX - 700.0, PitY - 400.0, 450.0);
    const FVector LookAt(PitX, PitY, -200.0);
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, PitX, PitY + 1000.0);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();
    const FFrameWindowRef Idle = MakeShared<FFrameWindow>();
    const FFrameWindowRef Digging = MakeShared<FFrameWindow>();
    struct FShadow
    {
        TWeakObjectPtr<ACameraActor> Camera;
        double StartSeconds = -1.0;
        double NextDigSeconds = 0.0;
        int32 Attempts = 0;
        int32 Changed = 0;
    };
    TSharedRef<FShadow> Shadow = MakeShared<FShadow>();

    AddWaitForRest(Scene, TEXT("The character rests beside the shadow site"));
    AddAction(Scene, TEXT("Dig the sun-lit pit and look at it"), [Shadow, CameraAt, LookAt, PitRadiusCm](FDigGameScene& S)
    {
        S.Test->TestTrue(TEXT("The pit digs"), DigPit(*S.GetSubsystem(), PitX, PitY, 300.0, PitRadiusCm) > 0);
        Shadow->Camera = SpawnViewCamera(S, CameraAt, LookAt);
        if (!Shadow->Camera.IsValid())
        {
            S.Abort(TEXT("Could not spawn the view camera"));
        }
    });
    AddWaitForQuiet(Scene, TEXT("ShadowCost"));
    AddIdleWindow(Scene, Idle);
    AddStep(Scene, TEXT("Dig beside the sun-lit pit edge for 10 s"), 120.0, [Digging, Shadow, WindowSeconds, DigEverySeconds](FDigGameScene& S)
    {
        const double Now = S.GetWorld()->GetTimeSeconds();
        if (Shadow->StartSeconds < 0.0)
        {
            Shadow->StartSeconds = Now;
            Shadow->NextDigSeconds = Now;
            Digging->Start();
        }
        Digging->Sample(&S);
        if (Now - Shadow->StartSeconds >= WindowSeconds)
        {
            return true;
        }
        if (Now < Shadow->NextDigSeconds)
        {
            return false;
        }
        Shadow->NextDigSeconds += DigEverySeconds;
        // Along the rim on the pit's lit +X+Y side, sweeping to and fro and slowly outwards, so each stamp bites new ground.
        const int32 K = Shadow->Attempts++;
        const double Angle = FMath::DegreesToRadians(45.0 + 60.0 * FMath::Sin(K * 0.5));
        const double Radius = 200.0 + 2.0 * K;
        const FVector At(PitX + Radius * FMath::Cos(Angle), PitY + Radius * FMath::Sin(Angle), GroundZ);
        Shadow->Changed += S.GetSubsystem()->Dig(At, DigRadiusCm, EReflectionsDigMode::Remove) ? 1 : 0;
        return false;
    });
    AddAction(Scene, TEXT("Log the shadow cost"), [Idle, Digging, Shadow](FDigGameScene& S)
    {
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE SHADOW idle_max_ms=%.3f max_ms=%.3f mean_ms=%.3f"), MaxOf(Idle->GameMs), MaxOf(Digging->GameMs), MeanOf(Digging->GameMs));
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE SHADOW_EXTRA pit=(4000,-1600) idle_mean_ms=%.3f p99_ms=%.3f attempts=%d digs=%d render_idle_mean_ms=%.3f render_idle_max_ms=%.3f render_mean_ms=%.3f render_max_ms=%.3f vsm=%d lumen_hwrt=%d"),
            MeanOf(Idle->GameMs), PercentileOf(Digging->GameMs, 0.99), Shadow->Attempts, Shadow->Changed, MeanOf(Idle->RenderMs), MaxOf(Idle->RenderMs),
            MeanOf(Digging->RenderMs), MaxOf(Digging->RenderMs), GetConsoleInt(TEXT("r.Shadow.Virtual.Enable")), IsLumenHardwareRayTracingActive() ? 1 : 0);
        Idle->Log(TEXT("SHADOW_IDLE"));
        Digging->Log(TEXT("SHADOW_WINDOW"));
        Digging->Stop();
    });
    AddStep(Scene, TEXT("Restore the view"), 1.0, [Shadow](FDigGameScene& S)
    {
        if (S.GetWorld() != nullptr)
        {
            RemoveViewCamera(S, Shadow->Camera);
        }
        return true;
    }, /*bAlwaysRun=*/ true);
    AddCleanup(Scene);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
