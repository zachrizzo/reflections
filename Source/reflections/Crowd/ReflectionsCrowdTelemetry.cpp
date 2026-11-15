#include "Crowd/ReflectionsCrowdTelemetry.h"
#include "MetaHumanCrowdStatsLibrary.h"
#include "HAL/PlatformTime.h"
#include "HAL/FileManager.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

AReflectionsCrowdTelemetry::AReflectionsCrowdTelemetry()
{
    PrimaryActorTick.bCanEverTick = true;
}
void AReflectionsCrowdTelemetry::BeginPlay()
{
    Super::BeginPlay();
    StartTime = PreviousTime = FPlatformTime::Seconds();
    Rows = TEXT("elapsed_seconds,frame_ms,crowd_entities,visible,actors,instanced_skinned_meshes\n");
}
void AReflectionsCrowdTelemetry::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (bSaved) return;
    const double Now = FPlatformTime::Seconds();
    const double FrameMs = (Now - PreviousTime) * 1000.0;
    PreviousTime = Now;
    const double Elapsed = Now - StartTime;
    if (Elapsed < WarmupSeconds) return;
    if (Now >= NextStatsTime)
    {
        const FMetaHumanCrowdStats Stats = UMetaHumanCrowdStatsLibrary::GatherMetaHumanCrowdStats(this);
        Entities = Stats.NumEntities; Visible = Stats.NumVisible; Actors = Stats.NumActors; Instanced = Stats.NumISKMs;
        NextStatsTime = Now + 1.0;
    }
    Rows += FString::Printf(TEXT("%.4f,%.4f,%d,%d,%d,%d\n"), Elapsed, FrameMs,
        Entities, Visible, Actors, Instanced);
    ++Samples;
    if (Elapsed >= WarmupSeconds + CaptureSeconds) SaveCapture();
}
void AReflectionsCrowdTelemetry::SaveCapture()
{
    if (bSaved || Samples == 0) return;
    bSaved = true;
    const FString Folder = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Profiling"), TEXT("ReflectionsCrowd"));
    IFileManager::Get().MakeDirectory(*Folder, true);
    const FString Path = FPaths::Combine(Folder, FString::Printf(TEXT("crowd_%s.csv"), *FDateTime::Now().ToString(TEXT("%Y%m%d_%H%M%S"))));
    if (FFileHelper::SaveStringToFile(Rows, *Path)) { UE_LOG(LogTemp, Display, TEXT("Crowd telemetry: %s (%d frames)"), *Path, Samples); }
    else { UE_LOG(LogTemp, Error, TEXT("Failed to write crowd telemetry: %s"), *Path); }
}
void AReflectionsCrowdTelemetry::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    SaveCapture();
    Super::EndPlay(EndPlayReason);
}


