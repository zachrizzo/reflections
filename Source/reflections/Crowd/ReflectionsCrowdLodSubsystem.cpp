#include "Crowd/ReflectionsCrowdLodSubsystem.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsCrowd, Log, All);
DECLARE_CYCLE_STAT(TEXT("Crowd LOD update"), STAT_ReflectionsCrowdLodUpdate, STATGROUP_Game);
DECLARE_CYCLE_STAT(TEXT("Crowd LOD wake"), STAT_ReflectionsCrowdLodWake, STATGROUP_Game);

namespace
{
    TAutoConsoleVariable<int32> CVarCrowdLodEnable(TEXT("Crowd.Lod.Enable"), 1,
        TEXT("Crowd walker animation LOD. 0 = every walker animates every frame."));
    TAutoConsoleVariable<float> CVarCrowdLodNear(TEXT("Crowd.Lod.NearDistance"), 1800.0f,
        TEXT("Walkers closer than this to the camera (cm) animate every frame."));
    TAutoConsoleVariable<float> CVarCrowdLodFar(TEXT("Crowd.Lod.FarDistance"), 4000.0f,
        TEXT("Walkers beyond this distance from the camera (cm) use Crowd.Lod.FarHz."));
    TAutoConsoleVariable<float> CVarCrowdLodMidHz(TEXT("Crowd.Lod.MidHz"), 30.0f,
        TEXT("Animation rate between the near and far distances."));
    TAutoConsoleVariable<float> CVarCrowdLodFarHz(TEXT("Crowd.Lod.FarHz"), 15.0f,
        TEXT("Animation rate beyond the far distance."));
    TAutoConsoleVariable<float> CVarCrowdLodHiddenHz(TEXT("Crowd.Lod.HiddenHz"), 6.0f,
        TEXT("Animation rate of walkers that were not rendered recently."));
    TAutoConsoleVariable<float> CVarCrowdLodWakeRadius(TEXT("Crowd.Lod.WakeRadius"), 2500.0f,
        TEXT("Walkers this close to a spell event or hit (cm) animate every frame for Crowd.Lod.WakeSeconds."));
    TAutoConsoleVariable<float> CVarCrowdLodWakeSeconds(TEXT("Crowd.Lod.WakeSeconds"), 9.0f,
        TEXT("How long a spell keeps nearby walkers at full animation rate (covers flee and recovery)."));

    TAutoConsoleVariable<int32> CVarCrowdLodQuietDriverCameras(TEXT("Crowd.Lod.QuietDriverCameras"), 1,
        TEXT("Switch off the gameplay camera on each walker's hidden locomotion pawn (nobody views through an NPC's pawn; ")
        TEXT("each evaluated its camera rig every frame, about 0.1 ms). Applies to walkers found after it is set."));

    const FName WalkerTag(TEXT("NPC_SampleLocomotion"));
    constexpr double UpdatePeriod = 0.25;

    /**
     * The sample locomotion pawn carries the hero's GameplayCameraComponent, which keeps evaluating its camera rig
     * on every NPC driver. Matched by class name so the crowd does not depend on the GameplayCameras module.
     */
    void QuietDriverCameras(ACharacter* Driver)
    {
        if (!Driver || Driver->IsPlayerControlled() || CVarCrowdLodQuietDriverCameras.GetValueOnGameThread() == 0) return;
        TInlineComponentArray<UActorComponent*> Components(Driver);
        for (UActorComponent* Component : Components)
        {
            bool bCamera = false;
            for (const UClass* Class = Component ? Component->GetClass() : nullptr; Class && !bCamera; Class = Class->GetSuperClass())
            {
                bCamera = Class->GetFName() == TEXT("GameplayCameraComponent") || Class->GetFName() == TEXT("GameplayCameraComponentBase");
            }
            if (!bCamera) continue;
            Component->SetComponentTickEnabled(false);
            if (Component->IsActive()) Component->Deactivate();
        }
    }
    constexpr double RescanPeriod = 2.0;

    float IntervalFor(EReflectionsCrowdLodTier Tier)
    {
        auto FromHz = [](float Hz) { return Hz > 0.0f ? 1.0f / Hz : 0.0f; };
        switch (Tier)
        {
        case EReflectionsCrowdLodTier::Mid: return FromHz(CVarCrowdLodMidHz.GetValueOnGameThread());
        case EReflectionsCrowdLodTier::Far: return FromHz(CVarCrowdLodFarHz.GetValueOnGameThread());
        case EReflectionsCrowdLodTier::Hidden: return FromHz(CVarCrowdLodHiddenHz.GetValueOnGameThread());
        default: return 0.0f;
        }
    }

    const TCHAR* TierName(EReflectionsCrowdLodTier Tier)
    {
        switch (Tier)
        {
        case EReflectionsCrowdLodTier::Mid: return TEXT("Mid");
        case EReflectionsCrowdLodTier::Far: return TEXT("Far");
        case EReflectionsCrowdLodTier::Hidden: return TEXT("Hidden");
        default: return TEXT("Full");
        }
    }

    FAutoConsoleCommandWithWorldAndArgs GCrowdLodDump(TEXT("Crowd.LodDump"),
        TEXT("Log every crowd walker's animation LOD tier, camera distance and wake time."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            if (const UReflectionsCrowdLodSubsystem* Lod = World ? World->GetSubsystem<UReflectionsCrowdLodSubsystem>() : nullptr)
            {
                UE_LOG(LogReflectionsCrowd, Display, TEXT("%s"), *Lod->Describe());
            }
        }));
}

bool UReflectionsCrowdLodSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UReflectionsCrowdLodSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsCrowdLodSubsystem, STATGROUP_Tickables);
}

double UReflectionsCrowdLodSubsystem::Now() const
{
    const UWorld* World = GetWorld();
    return World ? World->GetTimeSeconds() : 0.0;
}

void UReflectionsCrowdLodSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    // Spells reach the crowd only through the unified NPC system: its stimulus feed (spell noise and every
    // other world event), the reactions it decides, and the hits it routes.
    if (UReflectionsNpcSubsystem* Npcs = InWorld.GetSubsystem<UReflectionsNpcSubsystem>())
    {
        StimulusHandle = Npcs->OnStimulus().AddUObject(this, &UReflectionsCrowdLodSubsystem::HandleStimulus);
        Npcs->OnNpcReaction.AddUniqueDynamic(this, &UReflectionsCrowdLodSubsystem::HandleNpcReaction);
        Npcs->OnNpcSpellHit.AddUniqueDynamic(this, &UReflectionsCrowdLodSubsystem::HandleNpcSpellHit);
    }
    else
    {
        UE_LOG(LogReflectionsCrowd, Warning, TEXT("Crowd LOD: no NPC subsystem in %s; walkers wake only by distance."), *InWorld.GetName());
    }
    // Locomotion pawns are spawned on the NPCs' first tick, so the first scan waits a moment.
    NextRescan = 0.5;
}

void UReflectionsCrowdLodSubsystem::Deinitialize()
{
    // The world is ending: its components go with it, so their tick intervals are not restored here.
    if (UWorld* World = GetWorld())
    {
        UReflectionsNpcSubsystem* Npcs = World->GetSubsystem<UReflectionsNpcSubsystem>();
        if (IsValid(Npcs))
        {
            Npcs->OnStimulus().Remove(StimulusHandle);
            Npcs->OnNpcReaction.RemoveDynamic(this, &UReflectionsCrowdLodSubsystem::HandleNpcReaction);
            Npcs->OnNpcSpellHit.RemoveDynamic(this, &UReflectionsCrowdLodSubsystem::HandleNpcSpellHit);
        }
    }
    StimulusHandle.Reset();
    Walkers.Reset();
    Super::Deinitialize();
}

void UReflectionsCrowdLodSubsystem::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    const UWorld* World = GetWorld();
    if (!World || !World->HasBegunPlay())
    {
        return;
    }
    const double Time = Now();
    if (Time >= NextRescan)
    {
        NextRescan = Time + RescanPeriod;
        Rescan();
    }
    if (Time >= NextUpdate)
    {
        NextUpdate = Time + UpdatePeriod;
        UpdateTiers();
    }
}

void UReflectionsCrowdLodSubsystem::CollectMeshes(FWalker& Walker) const
{
    Walker.Meshes.Reset();
    Walker.OriginalIntervals.Reset();
    Walker.Body.Reset();
    auto Add = [&Walker](USkeletalMeshComponent* Mesh)
    {
        // Leader-pose followers (garments) copy their leader's pose and never evaluate animation themselves.
        if (!Mesh || Mesh->LeaderPoseComponent.IsValid() || Walker.Meshes.Contains(Mesh)) return;
        Walker.Meshes.Add(Mesh);
        Walker.OriginalIntervals.Add(Mesh->GetComponentTickInterval());
    };
    if (ACharacter* Driver = Walker.Driver.Get())
    {
        Add(Driver->GetMesh());
    }
    if (AActor* Actor = Walker.Actor.Get())
    {
        TInlineComponentArray<USkeletalMeshComponent*> Meshes(Actor);
        for (USkeletalMeshComponent* Mesh : Meshes)
        {
            if (Mesh && Mesh->GetFName() == TEXT("Body")) Walker.Body = Mesh;
            Add(Mesh);
        }
        if (!Walker.Body.IsValid())
        {
            for (USkeletalMeshComponent* Mesh : Meshes)
                if (Mesh && Mesh->GetPhysicsAsset()) { Walker.Body = Mesh; break; }
        }
    }
}

void UReflectionsCrowdLodSubsystem::Rescan()
{
    UWorld* World = GetWorld();
    Walkers.RemoveAll([](const FWalker& Walker) { return !Walker.Actor.IsValid(); });
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (!IsValid(Actor) || !Actor->ActorHasTag(WalkerTag)) continue;
        // The unified NPC component attaches the visible walker to its hidden locomotion pawn.
        ACharacter* Driver = Cast<ACharacter>(Actor->GetAttachParentActor());
        FWalker* Existing = Walkers.FindByPredicate([Actor](const FWalker& Walker) { return Walker.Actor.Get() == Actor; });
        if (Existing)
        {
            if (Existing->Driver.Get() != Driver)
            {
                ApplyTier(*Existing, EReflectionsCrowdLodTier::Full, true);
                Existing->Driver = Driver;
                CollectMeshes(*Existing);
                QuietDriverCameras(Driver);
            }
            continue;
        }
        FWalker& Walker = Walkers.AddDefaulted_GetRef();
        Walker.Actor = Actor;
        Walker.Driver = Driver;
        CollectMeshes(Walker);
        QuietDriverCameras(Driver);
    }
}

void UReflectionsCrowdLodSubsystem::ApplyTier(FWalker& Walker, EReflectionsCrowdLodTier Tier, bool bForce)
{
    if (Walker.Tier == Tier && !bForce) return;
    Walker.Tier = Tier;
    const float Interval = IntervalFor(Tier);
    for (int32 Index = 0; Index < Walker.Meshes.Num(); ++Index)
    {
        if (USkeletalMeshComponent* Mesh = Walker.Meshes[Index].Get())
        {
            const float Target = Tier == EReflectionsCrowdLodTier::Full ? Walker.OriginalIntervals[Index] : Interval;
            // Waking must take effect on the next frame, not after the remaining slow-tick cooldown.
            if (Tier == EReflectionsCrowdLodTier::Full) Mesh->SetComponentTickIntervalAndCooldown(Target);
            else Mesh->SetComponentTickInterval(Target);
        }
    }
}

void UReflectionsCrowdLodSubsystem::RestoreAll()
{
    for (FWalker& Walker : Walkers)
    {
        ApplyTier(Walker, EReflectionsCrowdLodTier::Full, true);
    }
}

void UReflectionsCrowdLodSubsystem::UpdateTiers()
{
    SCOPE_CYCLE_COUNTER(STAT_ReflectionsCrowdLodUpdate);
    const bool bEnabled = CVarCrowdLodEnable.GetValueOnGameThread() != 0;
    if (!bEnabled)
    {
        if (bWasEnabled) RestoreAll();
        bWasEnabled = false;
        return;
    }
    bWasEnabled = true;

    UWorld* World = GetWorld();
    FVector ViewLocation = FVector::ZeroVector;
    bool bHasView = false;
    if (APlayerController* Controller = World ? World->GetFirstPlayerController() : nullptr)
    {
        FRotator ViewRotation;
        Controller->GetPlayerViewPoint(ViewLocation, ViewRotation);
        bHasView = true;
    }
    const float Near = CVarCrowdLodNear.GetValueOnGameThread();
    const float Far = FMath::Max(Near, CVarCrowdLodFar.GetValueOnGameThread());
    const double Time = Now();

    for (FWalker& Walker : Walkers)
    {
        const AActor* Actor = Walker.Actor.Get();
        if (!Actor) continue;
        Walker.LastDistance = bHasView ? FVector::Dist(ViewLocation, Actor->GetActorLocation()) : 0.0f;
        EReflectionsCrowdLodTier Tier = EReflectionsCrowdLodTier::Full;
        const USkeletalMeshComponent* Body = Walker.Body.Get();
        const bool bPhysics = Body && Body->IsAnySimulatingPhysics();
        if (bHasView && Time >= Walker.AwakeUntil && !bPhysics)
        {
            if (!Actor->WasRecentlyRendered(0.3f)) Tier = EReflectionsCrowdLodTier::Hidden;
            else if (Walker.LastDistance > Far) Tier = EReflectionsCrowdLodTier::Far;
            else if (Walker.LastDistance > Near) Tier = EReflectionsCrowdLodTier::Mid;
        }
        ApplyTier(Walker, Tier);
    }
}

void UReflectionsCrowdLodSubsystem::WakeNear(FVector Location, float Radius)
{
    SCOPE_CYCLE_COUNTER(STAT_ReflectionsCrowdLodWake);
    const double Until = Now() + CVarCrowdLodWakeSeconds.GetValueOnGameThread();
    const float RadiusSquared = FMath::Square(FMath::Max(0.0f, Radius));
    for (FWalker& Walker : Walkers)
    {
        const AActor* Actor = Walker.Actor.Get();
        if (!Actor || FVector::DistSquared(Actor->GetActorLocation(), Location) > RadiusSquared) continue;
        Walker.AwakeUntil = FMath::Max(Walker.AwakeUntil, Until);
        ApplyTier(Walker, EReflectionsCrowdLodTier::Full);
    }
}

void UReflectionsCrowdLodSubsystem::WakeActor(const AActor* Actor)
{
    if (!Actor) return;
    const double Until = Now() + CVarCrowdLodWakeSeconds.GetValueOnGameThread();
    for (FWalker& Walker : Walkers)
    {
        if (Walker.Actor.Get() != Actor && Walker.Driver.Get() != Actor) continue;
        Walker.AwakeUntil = FMath::Max(Walker.AwakeUntil, Until);
        ApplyTier(Walker, EReflectionsCrowdLodTier::Full);
        return;
    }
}

void UReflectionsCrowdLodSubsystem::HandleStimulus(const FReflectionsNpcStimulus& Stimulus)
{
    WakeNear(Stimulus.Location, FMath::Max(Stimulus.Radius, CVarCrowdLodWakeRadius.GetValueOnGameThread()));
}

void UReflectionsCrowdLodSubsystem::HandleNpcReaction(AActor* Npc, EReflectionsNpcReaction Reaction, AActor* Cause, FVector Location)
{
    // Anything but calm is visible behaviour (flinch, flee, investigate, attack, fall): animate it at full rate.
    if (Reaction != EReflectionsNpcReaction::Calm) WakeActor(Npc);
}

void UReflectionsCrowdLodSubsystem::HandleNpcSpellHit(AActor* Npc, const FReflectionsSpellHitData& Hit)
{
    WakeActor(Npc);
    WakeNear(Hit.Location, CVarCrowdLodWakeRadius.GetValueOnGameThread());
}

FString UReflectionsCrowdLodSubsystem::Describe() const
{
    const double Time = Now();
    FString Out = FString::Printf(TEXT("Crowd LOD: %d walkers (Full %d, Mid %d, Far %d, Hidden %d), enabled %d"),
        Walkers.Num(), CountInTier(EReflectionsCrowdLodTier::Full), CountInTier(EReflectionsCrowdLodTier::Mid),
        CountInTier(EReflectionsCrowdLodTier::Far), CountInTier(EReflectionsCrowdLodTier::Hidden),
        CVarCrowdLodEnable.GetValueOnGameThread());
    for (const FWalker& Walker : Walkers)
    {
        const AActor* Actor = Walker.Actor.Get();
        if (!Actor) continue;
        Out += FString::Printf(TEXT("\n  %s: %s, %.0f cm, awake %.1f s, %d meshes, driver %s"),
            *Actor->GetActorNameOrLabel(), TierName(Walker.Tier), Walker.LastDistance,
            FMath::Max(0.0, Walker.AwakeUntil - Time), Walker.Meshes.Num(),
            Walker.Driver.IsValid() ? *Walker.Driver->GetName() : TEXT("none"));
    }
    return Out;
}

int32 UReflectionsCrowdLodSubsystem::CountInTier(EReflectionsCrowdLodTier Tier) const
{
    int32 Count = 0;
    for (const FWalker& Walker : Walkers)
        if (Walker.Actor.IsValid() && Walker.Tier == Tier) ++Count;
    return Count;
}

EReflectionsCrowdLodTier UReflectionsCrowdLodSubsystem::GetTier(const AActor* Walker) const
{
    for (const FWalker& Entry : Walkers)
        if (Entry.Actor.Get() == Walker) return Entry.Tier;
    return EReflectionsCrowdLodTier::Full;
}
