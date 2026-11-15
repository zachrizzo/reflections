#include "Crowd/ReflectionsCrowdLodSubsystem.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "Components/CapsuleComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
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

    TAutoConsoleVariable<int32> CVarCrowdLodReground(TEXT("Crowd.Lod.Reground"), 1,
        TEXT("Lift a walker's hidden driver back onto a walkable surface 3-45 cm above its feet (Gray London's roads are one-sided ")
        TEXT("sheets at 28 cm over the 10 cm city ground: a walker stepping off the pavement slides under them and wades through the road)."));

    TAutoConsoleVariable<int32> CVarCrowdLodRegroundCorpses(TEXT("Crowd.Lod.RegroundCorpses"), 1,
        TEXT("For 8 s after a walker dies into a ragdoll, lift the whole ragdoll when its torso (pelvis or spine body) lies under a ")
        TEXT("broad walkable surface 1-45 cm above it (one-sided road sheets and city ground: a body that slid or started under one rests below it)."));

    const FName WalkerTag(TEXT("NPC_SampleLocomotion"));
    constexpr double UpdatePeriod = 0.25;
    constexpr double CorpseWindow = 8.0;
    constexpr int32 MaxCorpseLifts = 4;
    /** Lifts since start (all worlds; tests read them through Describe). */
    int64 GRegroundLifts = 0;
    int64 GCorpseLifts = 0;

    /**
     * A road or city-ground sheet, not furniture: what was hit spans more than 5 m both ways (a whole OSM tile).
     * Gray London places its benches, bins and bollards with instanced components whose bounds cover every instance,
     * so for those the hit instance's own bounds count, not the component's.
     */
    bool IsBroadFloor(const FHitResult& Hit)
    {
        const UPrimitiveComponent* Component = Hit.GetComponent();
        if (!Component || Hit.ImpactNormal.Z < 0.7f) return false;
        FVector Extent = Component->Bounds.BoxExtent;
        if (const UInstancedStaticMeshComponent* Instances = Cast<UInstancedStaticMeshComponent>(Component))
        {
            FTransform Instance;
            const UStaticMesh* Mesh = Instances->GetStaticMesh();
            if (!Mesh || !Instances->GetInstanceTransform(Hit.Item, Instance, true)) return false;
            Extent = Mesh->GetBounds().TransformBy(Instance).BoxExtent;
        }
        return FMath::Min(Extent.X, Extent.Y) > 250.0;
    }

    /** One line trace down from the capsule centre; returns 1 when the driver was lifted onto the surface above its feet. */
    int32 RegroundDriver(ACharacter* Driver)
    {
        if (!Driver || Driver->IsPlayerControlled()) return 0;
        UCharacterMovementComponent* Movement = Driver->GetCharacterMovement();
        UCapsuleComponent* Capsule = Driver->GetCapsuleComponent();
        // Only walkers on the ground: not falling, not pinned in a scene (None), not seated (collision off).
        if (!Movement || !Capsule || Movement->MovementMode != MOVE_Walking || Capsule->GetCollisionEnabled() == ECollisionEnabled::NoCollision) return 0;
        const FVector Centre = Driver->GetActorLocation();
        const float Bottom = Centre.Z - Capsule->GetScaledCapsuleHalfHeight();
        FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdReground), true, Driver);
        TArray<AActor*> Attached;
        Driver->GetAttachedActors(Attached);
        Params.AddIgnoredActors(Attached);
        FHitResult Hit;
        if (!Driver->GetWorld()->LineTraceSingleByObjectType(Hit, Centre, FVector(Centre.X, Centre.Y, Bottom - 5.0f),
            FCollisionObjectQueryParams(ECC_WorldStatic), Params)) return 0;
        const float Lift = Hit.ImpactPoint.Z - Bottom;
        if (Lift < 3.0f || Lift > 45.0f || !IsBroadFloor(Hit)) return 0;
        Driver->SetActorLocation(Centre + FVector(0.0, 0.0, Lift + 1.0f), false, nullptr, ETeleportType::TeleportPhysics);
        ++GRegroundLifts;
        return 1;
    }

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
    const bool bUpdate = Time >= NextUpdate;
    if (bUpdate)
    {
        NextUpdate = Time + UpdatePeriod;
        UpdateTiers();
    }
    const bool bReground = CVarCrowdLodReground.GetValueOnGameThread() != 0;
    const bool bCorpses = CVarCrowdLodRegroundCorpses.GetValueOnGameThread() != 0;
    for (FWalker& Walker : Walkers)
    {
        // Near, visible walkers every frame (no visible dip at a road edge); the rest with the tier update.
        const bool bNear = Walker.Tier == EReflectionsCrowdLodTier::Full || Walker.Tier == EReflectionsCrowdLodTier::Mid;
        if (bReground && (bNear || bUpdate)) RegroundDriver(Walker.Driver.Get());
        if (bCorpses) TickCorpse(Walker, Time);
    }
}

void UReflectionsCrowdLodSubsystem::TickCorpse(FWalker& Walker, double Time)
{
    USkeletalMeshComponent* Body = Walker.Body.Get();
    AActor* Actor = Walker.Actor.Get();
    const ACharacter* Driver = Walker.Driver.Get();
    const UCapsuleComponent* Capsule = Driver ? Driver->GetCapsuleComponent() : nullptr;
    // Dead: the whole body (root included) simulates and the driver no longer collides. Hit jolts and knockdowns
    // simulate part of the body only, or none of it, and keep the driver.
    const bool bRagdoll = Body && Actor && Body->IsSimulatingPhysics()
        && (!Capsule || Capsule->GetCollisionEnabled() == ECollisionEnabled::NoCollision);
    if (!bRagdoll)
    {
        Walker.RagdollSince = -1.0;
        Walker.CorpseLifts = 0;
        return;
    }
    if (Walker.RagdollSince < 0.0) Walker.RagdollSince = Time;
    if (Time - Walker.RagdollSince > CorpseWindow || Walker.CorpseLifts >= MaxCorpseLifts || Time < Walker.NextCorpseCheck) return;
    Walker.NextCorpseCheck = Time + 0.1;

    // The physics bodies themselves (not the bone pose). Only the torso (pelvis and spine) decides: a corpse whose
    // torso lies under a broad walkable surface is under the road. Feet and hands sink a few cm into every floor
    // (road middle and pavement alike, train #23 test), and lifting for them only bounced corpses that were at rest.
    TArray<FVector, TInlineAllocator<8>> Centres;
    int32 Simulating = 0;
    float Lowest = TNumericLimits<float>::Max(), Highest = TNumericLimits<float>::Lowest();
    for (const FBodyInstance* Instance : Body->Bodies)
    {
        if (!Instance || !Instance->IsInstanceSimulatingPhysics()) continue;
        const FVector Centre = Instance->GetUnrealWorldTransform().GetLocation();
        ++Simulating;
        Lowest = FMath::Min(Lowest, static_cast<float>(Centre.Z));
        Highest = FMath::Max(Highest, static_cast<float>(Centre.Z));
        const FString Bone = Body->GetBoneName(Instance->InstanceBoneIndex).ToString();
        if (Bone == TEXT("pelvis") || Bone.StartsWith(TEXT("spine_"))) Centres.Add(Centre);
    }
    // A collapsed ragdoll (every body at one height) is broken, not under a sheet: lifting it would only bounce it.
    if (Simulating < 4 || Highest - Lowest < 1.0f || Centres.Num() == 0) return;
    UWorld* World = GetWorld();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CrowdCorpseReground), true, Actor);
    const FCollisionObjectQueryParams Statics(ECC_WorldStatic);
    float Lift = 0.0f;
    for (const FVector& Centre : Centres)
    {
        FHitResult Hit;
        if (!World->LineTraceSingleByObjectType(Hit, Centre + FVector(0.0, 0.0, 50.0), Centre, Statics, Params) || Hit.bStartPenetrating) continue;
        const float Above = Hit.ImpactPoint.Z - Centre.Z;
        if (Above < 1.0f || Above > 45.0f || !IsBroadFloor(Hit)) continue;
        // Enough to bring that torso body's centre a body radius over the surface; extra height only drops back.
        Lift = FMath::Max(Lift, Above + 14.0f);
    }
    if (Lift <= 0.0f) return;
    for (FBodyInstance* Instance : Body->Bodies)
    {
        if (!Instance || !Instance->IsInstanceSimulatingPhysics()) continue;
        FTransform Transform = Instance->GetUnrealWorldTransform();
        Transform.AddToTranslation(FVector(0.0, 0.0, Lift));
        Instance->SetBodyTransform(Transform, ETeleportType::TeleportPhysics);
        FVector Velocity = Instance->GetUnrealWorldVelocity();
        if (Velocity.Z < 0.0)
        {
            Velocity.Z = 0.0;
            Instance->SetLinearVelocity(Velocity, false);
        }
    }
    ++Walker.CorpseLifts;
    ++GCorpseLifts;
    UE_LOG(LogReflectionsCrowd, Verbose, TEXT("Crowd LOD: lifted %s's ragdoll %.0f cm out from under a floor sheet (lift %d)."),
        *Actor->GetName(), Lift, Walker.CorpseLifts);
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
    FString Out = FString::Printf(TEXT("Crowd LOD: %d walkers (Full %d, Mid %d, Far %d, Hidden %d), enabled %d, reground %d (%lld lifts), corpses %d (%lld lifts)"),
        Walkers.Num(), CountInTier(EReflectionsCrowdLodTier::Full), CountInTier(EReflectionsCrowdLodTier::Mid),
        CountInTier(EReflectionsCrowdLodTier::Far), CountInTier(EReflectionsCrowdLodTier::Hidden),
        CVarCrowdLodEnable.GetValueOnGameThread(), CVarCrowdLodReground.GetValueOnGameThread(), GRegroundLifts,
        CVarCrowdLodRegroundCorpses.GetValueOnGameThread(), GCorpseLifts);
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
