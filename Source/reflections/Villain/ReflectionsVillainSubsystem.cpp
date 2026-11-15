#include "Villain/ReflectionsVillainSubsystem.h"

#include "Villain/ReflectionsFinalSpell.h"
#include "Villain/ReflectionsVillainConversion.h"
#include "Villain/ReflectionsVillainBoss.h"
#include "Villain/ReflectionsVillainConfig.h"
#include "Villain/ReflectionsVillainFx.h"
#include "Villain/ReflectionsVillainHud.h"
#include "Villain/ReflectionsVillainPossession.h"
#include "Villain/ReflectionsVillainText.h"

#include "GameFlow/ReflectionsGameFlowSubsystem.h"
#include "GameFlow/ReflectionsGameFlowTypes.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"
#include "UObject/Package.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"
#include "Worlds/ReflectionsWorldAnchor.h"
#include "Worlds/ReflectionsWorldJumpConfig.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"
#include "Worlds/ReflectionsWorldPickups.h"

#include "Components/BillboardComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SphereComponent.h"
#include "Engine/GameInstance.h"
#include "GameFramework/Character.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "TimerManager.h"
#include "UObject/UObjectIterator.h"

#define LOCTEXT_NAMESPACE "ReflectionsVillain"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsVillain, Log, All);

namespace
{
    double Now(const UWorld* World)
    {
        return World ? World->GetTimeSeconds() : 0.0;
    }

    /** Open floor around a point: the nearest wall in 12 directions at chest height, clamped to a usable arena. */
    float MeasureOpenRadius(UWorld* World, const FVector& Ground)
    {
        float Nearest = 1400.0f;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(VillainArena), false);
        if (APawn* Player = ReflectionsVillainFx::PlayerPawn(World))
        {
            Params.AddIgnoredActor(Player);
        }
        const FVector Start = Ground + FVector(0.0f, 0.0f, 120.0f);
        for (int32 Index = 0; Index < 12; ++Index)
        {
            const float Angle = Index * 2.0f * PI / 12.0f;
            FHitResult Hit;
            if (World->LineTraceSingleByChannel(Hit, Start, Start + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f) * 1400.0f, ECC_Visibility, Params))
            {
                Nearest = FMath::Min(Nearest, Hit.Distance);
            }
        }
        return FMath::Clamp(Nearest - 60.0f, 300.0f, 1400.0f);
    }

}

FText UReflectionsVillainSubsystem::SideName(const UObject* WorldContext, EReflectionsWorld World)
{
    // The world-jump config owns the player-facing names of the three sides.
    if (const UReflectionsWorldJumpWorldSubsystem* Jump = UReflectionsWorldJumpWorldSubsystem::Get(WorldContext))
    {
        if (const UReflectionsWorldJumpConfig* Config = Jump->GetConfig())
        {
            const FText Name = Config->GetWorldName(World);
            if (!Name.IsEmpty())
            {
                return Name;
            }
        }
    }
    return ReflectionsVillainText::FallbackSide(static_cast<int32>(World));
}

// ============================================================================================ arena marker

AReflectionsVillainArena::AReflectionsVillainArena()
{
    PrimaryActorTick.bCanEverTick = false;
    Area = CreateDefaultSubobject<USphereComponent>(TEXT("Area"));
    RootComponent = Area;
    Area->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Area->SetSphereRadius(ArenaRadius);
    Area->ShapeColor = FColor(140, 40, 220);
    Area->bHiddenInGame = true;
#if WITH_EDITORONLY_DATA
    Sprite = CreateEditorOnlyDefaultSubobject<UBillboardComponent>(TEXT("Sprite"));
    if (Sprite)
    {
        Sprite->SetupAttachment(Area);
    }
#endif
}

void AReflectionsVillainArena::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    if (Area)
    {
        Area->SetSphereRadius(ArenaRadius);
    }
}

// ============================================================================================ subsystem

UReflectionsVillainSubsystem* UReflectionsVillainSubsystem::Get(const UObject* WorldContext)
{
    const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    return World ? World->GetSubsystem<UReflectionsVillainSubsystem>() : nullptr;
}

bool UReflectionsVillainSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UReflectionsVillainSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    CacheArena();

    bool bHasAnchors = false;
    for (TActorIterator<AReflectionsWorldAnchor> It(&InWorld); It; ++It)
    {
        bHasAnchors = true;
        break;
    }
    const int32 AutoStart = ReflectionsVillainTuning::AutoStart();
    bMapEnabled = AutoStart >= 2 || (AutoStart == 1 && (bHasAnchors || bArenaFromMarker));

    if (UReflectionsWorldJumpSubsystem* Jump = UReflectionsWorldJumpSubsystem::Get(&InWorld))
    {
        Jump->OnBookComplete.AddUniqueDynamic(this, &UReflectionsVillainSubsystem::HandleBookComplete);
        // Checkpoints restore progress quietly (no OnBookComplete): reconcile on OnProgressRestored instead.
        Jump->OnProgressRestored.AddUniqueDynamic(this, &UReflectionsVillainSubsystem::HandleProgressRestored);
        Jump->OnPagesChanged.AddUniqueDynamic(this, &UReflectionsVillainSubsystem::HandlePagesChanged);
        PagesFound = Jump->GetPageCount();
        bBoundBook = true;
        if (Jump->IsBookComplete() && bMapEnabled)
        {
            // The book was finished before this map (SeparateMaps layout): he is already waiting.
            FTimerHandle Deferred;
            InWorld.GetTimerManager().SetTimer(Deferred, FTimerDelegate::CreateUObject(this, &UReflectionsVillainSubsystem::StartFinale, false), 1.0f, false);
        }
    }
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(&InWorld))
    {
        Npcs->OnNpcSpellHit.AddUniqueDynamic(this, &UReflectionsVillainSubsystem::HandleNpcSpellHit);
        Npcs->OnNpcInfection.AddUniqueDynamic(this, &UReflectionsVillainSubsystem::HandleNpcInfection);
        Npcs->OnNpcDied.AddUniqueDynamic(this, &UReflectionsVillainSubsystem::HandleNpcDied);
    }
    else if (UReflectionsSpellEventSubsystem* Events = InWorld.GetSubsystem<UReflectionsSpellEventSubsystem>())
    {
        Events->OnSpellHit.AddUniqueDynamic(this, &UReflectionsVillainSubsystem::HandleSpellHit);
    }
    if (UReflectionsGameFlowSubsystem* Flow = InWorld.GetGameInstance() ? InWorld.GetGameInstance()->GetSubsystem<UReflectionsGameFlowSubsystem>() : nullptr)
    {
        Flow->OnCheckpointSaved.AddUniqueDynamic(this, &UReflectionsVillainSubsystem::HandleCheckpointSaved);
        Flow->OnCheckpointRestored.AddUniqueDynamic(this, &UReflectionsVillainSubsystem::HandleCheckpointRestored);
        bBoundSaves = true;
    }
    BindByName(Cutscenes(), TEXT("OnCutsceneFinished"), TEXT("HandleCutsceneFinished"));
    BindByName(GameFlow(), TEXT("OnGameLost"), TEXT("HandleGameLost"));
    InWorld.GetTimerManager().SetTimer(ThinkTimer, FTimerDelegate::CreateUObject(this, &UReflectionsVillainSubsystem::Think), 0.5f, true);
    if (bMapEnabled)
    {
        // The first host is taken StartDelay seconds after the run goes live (title menu closed, intro cutscene over).
        bRunning = true;
        bSeedClockStarted = false;
    }
    // Streamed maps load their anchors and arena marker a little later: keep looking for the first two minutes.
    MapCheckUntil = Now(&InWorld) + 120.0;
    NextMapCheck = Now(&InWorld) + 1.0;
    UE_LOG(LogReflectionsVillain, Log, TEXT("Villain: map %s, possession %s, arena %s"), *InWorld.GetMapName(),
        bMapEnabled ? TEXT("on (starts once play is live)") : TEXT("off for now (no world anchor or arena yet; Villain.Start to force)"),
        bHasArena ? *ArenaCenter.ToCompactString() : TEXT("none yet"));
}

void UReflectionsVillainSubsystem::Deinitialize()
{
    if (UWorld* World = GetWorld())
    {
        if (bBoundSaves)
        {
            if (UReflectionsGameFlowSubsystem* Flow = World->GetGameInstance() ? World->GetGameInstance()->GetSubsystem<UReflectionsGameFlowSubsystem>() : nullptr)
            {
                Flow->OnCheckpointSaved.RemoveDynamic(this, &UReflectionsVillainSubsystem::HandleCheckpointSaved);
                Flow->OnCheckpointRestored.RemoveDynamic(this, &UReflectionsVillainSubsystem::HandleCheckpointRestored);
            }
        }
        World->GetTimerManager().ClearTimer(ThinkTimer);
        if (bBoundBook)
        {
            if (UReflectionsWorldJumpSubsystem* Jump = UReflectionsWorldJumpSubsystem::Get(World))
            {
                Jump->OnBookComplete.RemoveDynamic(this, &UReflectionsVillainSubsystem::HandleBookComplete);
                Jump->OnProgressRestored.RemoveDynamic(this, &UReflectionsVillainSubsystem::HandleProgressRestored);
            }
        }
    }
    if (Hud)
    {
        Hud->RemoveFromParent();
        Hud = nullptr;
    }
    Super::Deinitialize();
}

// ---------------------------------------------------------------------------------------------- control

void UReflectionsVillainSubsystem::StartPossession()
{
    if (bFinale)
    {
        return;
    }
    bRunning = true;
    bSeedClockStarted = true;
    NextSeedTime = Now(GetWorld());
}

void UReflectionsVillainSubsystem::StopPossession()
{
    bRunning = false;
}

void UReflectionsVillainSubsystem::ForceHop()
{
    if (AActor* Current = Host.Get())
    {
        if (UReflectionsVillainPossessionComponent* Component = Current->FindComponentByClass<UReflectionsVillainPossessionComponent>())
        {
            Component->ShortenHost(0.05f);
        }
    }
    else
    {
        bRunning = !bFinale;
        NextSeedTime = 0.0;
    }
}

int32 UReflectionsVillainSubsystem::GetInfectedCount() const
{
    int32 Count = 0;
    for (const TWeakObjectPtr<AActor>& Actor : Infected)
    {
        Count += Actor.IsValid() ? 1 : 0;
    }
    return Count;
}

bool UReflectionsVillainSubsystem::IsCandidate(const AActor* Pawn, bool bAllowInfected)
{
    const APawn* AsPawn = Cast<APawn>(Pawn);
    if (!IsValid(Pawn) || Pawn->IsActorBeingDestroyed() || Pawn->IsHidden() || (AsPawn && AsPawn->IsPlayerControlled())
        || Pawn->IsA<AReflectionsVillainBoss>())
    {
        return false;
    }
    // "Friendly" townspeople can be taken (the NPC system lifts the tag while tarnished); NoVillain is the opt-out.
    static const FName Excluded[] = {TEXT("NoVillain"), TEXT("Player"), TEXT("Villain_BurnedOut")};
    for (const FName& Tag : Excluded)
    {
        if (Pawn->ActorHasTag(Tag))
        {
            return false;
        }
    }
    if (!ReflectionsVillainFx::HeadMesh(const_cast<AActor*>(Pawn)) || !ReflectionsVillainFx::IsAlive(Pawn))
    {
        return false;
    }
    switch (UReflectionsVillainPossessionComponent::StateOf(Pawn))
    {
    case EReflectionsVillainInfection::Host:
    case EReflectionsVillainInfection::BurnedOut:
        return false;
    case EReflectionsVillainInfection::Infected:
        return bAllowInfected;
    default:
        return true;
    }
}

AActor* UReflectionsVillainSubsystem::PickCandidate(const FVector& Around, float Radius, const AActor* Exclude, bool bPreferInfected,
    float MinDistance) const
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return nullptr;
    }
    struct FScored
    {
        AActor* Pawn;
        float Score;
    };
    TArray<FScored> Scored;
    const float RadiusSq = Radius * Radius;
    const float MinSq = MinDistance * MinDistance;
    for (AActor* Pawn : NpcActors())
    {
        if (Pawn == Exclude || !IsCandidate(Pawn, true))
        {
            continue;
        }
        const bool bIsInfected = UReflectionsVillainPossessionComponent::StateOf(Pawn) == EReflectionsVillainInfection::Infected;
        if (!bPreferInfected && bIsInfected)
        {
            continue;
        }
        const float DistSq = FVector::DistSquared(Around, Pawn->GetActorLocation());
        if (DistSq > RadiusSq || DistSq < MinSq)
        {
            continue;
        }
        const float Score = FMath::Sqrt(DistSq) * (bIsInfected ? 0.55f : 1.0f) * FMath::FRandRange(0.85f, 1.15f);
        Scored.Add({Pawn, Score});
    }
    if (Scored.Num() == 0)
    {
        return nullptr;
    }
    Scored.Sort([](const FScored& A, const FScored& B) { return A.Score < B.Score; });
    return Scored[FMath::RandRange(0, FMath::Min(2, Scored.Num() - 1))].Pawn;
}

void UReflectionsVillainSubsystem::LaunchWisp(const FVector& From, AActor* Target, EReflectionsVillainInfection State, bool bHop)
{
    UWorld* World = GetWorld();
    if (!World || !Target)
    {
        return;
    }
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AReflectionsVillainWisp* Wisp = World->SpawnActor<AReflectionsVillainWisp>(AReflectionsVillainWisp::StaticClass(), From, FRotator::ZeroRotator, Params);
    if (!Wisp)
    {
        return;
    }
    if (bHop)
    {
        PendingHop = Wisp;
    }
    else
    {
        ++PendingSpreads;
    }
    Wisp->Launch(Target, State, bHop);
}

void UReflectionsVillainSubsystem::TrySeed()
{
    UWorld* World = GetWorld();
    APawn* Player = ReflectionsVillainFx::PlayerPawn(World);
    NextSeedTime = Now(World) + 4.0;
    if (!Player)
    {
        return;
    }
    const FVector Around = Player->GetActorLocation();
    AActor* Target = PickCandidate(Around, ReflectionsVillainTuning::SeedRadius(), nullptr, true, 900.0f);
    if (!Target)
    {
        Target = PickCandidate(Around, ReflectionsVillainTuning::SeedRadius() * 4.0f, nullptr, true);
    }
    if (!Target)
    {
        return;
    }
    // He arrives from the sky: a streak falling onto his first body.
    const FVector From = Target->GetActorLocation() + FVector(FMath::FRandRange(-600.0f, 600.0f), FMath::FRandRange(-600.0f, 600.0f), 1600.0f);
    LaunchWisp(From, Target, EReflectionsVillainInfection::Host, true);
}

void UReflectionsVillainSubsystem::HopFrom(AActor* OldHost, const FVector& From)
{
    UWorld* World = GetWorld();
    AActor* Target = PickCandidate(From, ReflectionsVillainTuning::HopRadius(), OldHost, true);
    if (!Target)
    {
        if (APawn* Player = ReflectionsVillainFx::PlayerPawn(World))
        {
            Target = PickCandidate(Player->GetActorLocation(), ReflectionsVillainTuning::SeedRadius(), OldHost, true);
        }
    }
    if (!Target)
    {
        NextSeedTime = Now(World) + 3.0;
        return;
    }
    LaunchWisp(From + FVector(0.0f, 0.0f, 60.0f), Target, EReflectionsVillainInfection::Host, true);
}

void UReflectionsVillainSubsystem::Think()
{
    UWorld* World = GetWorld();
    if (!World || bVictory)
    {
        return;
    }
    for (auto It = Infected.CreateIterator(); It; ++It)
    {
        if (!It->IsValid())
        {
            It.RemoveCurrent();
        }
    }
    // Meter bands (story MQ_BAND_01-03): once each, the first time the Tarnish count crosses 25 / 50 / 75 %.
    if (UObject* Flow = GameFlow())
    {
        const int32 Band = FMath::Clamp(FMath::FloorToInt(CallFloat(Flow, TEXT("GetInfectionFraction")) * 4.0f), 0, 3);
        if (Band > BandReached)
        {
            BandReached = Band;
            static const TCHAR* BandLines[] = {TEXT("MQ_BAND_01"), TEXT("MQ_BAND_02"), TEXT("MQ_BAND_03")};
            ReflectionsVillainFx::Sound2D(World, ReflectionsVillainAssets::StoryLine(BandLines[Band - 1]), 0.9f);
        }
    }
    if ((PendingInfectedIds.Num() > 0 || !PendingHostId.IsEmpty()) && Now(World) <= RestoreUntil)
    {
        TryRestoreSaved();
    }
    // Also keep looking while the true form waits at a fallback spot: its marker may sit in a sublevel loaded later.
    if (Now(World) >= NextMapCheck && (Now(World) <= MapCheckUntil || (bFinale && !bArenaFromMarker)))
    {
        NextMapCheck = Now(World) + 2.0;
        RecheckMap();
    }
    if (bFinale)
    {
        if (bFinaleAnnounced)
        {
            EnsureFinalSpell();
        }
        if (!Boss.IsValid())
        {
            SpawnBossAtArena();
        }
        return;
    }
    AActor* Current = Host.Get();
    if (Host.IsValid() && (!IsValid(Current) || !ReflectionsVillainFx::IsAlive(Current)))
    {
        // The player killed his host: he leaves the body at once.
        Host = nullptr;
        Current = nullptr;
        if (bRunning && !PendingHop.IsValid())
        {
            HopFrom(nullptr, LastHostLocation);
        }
    }
    if (Current)
    {
        LastHostLocation = Current->GetActorLocation();
    }
    if (bRunning && !bSeedClockStarted)
    {
        if (!IsRunLive())
        {
            return;
        }
        bSeedClockStarted = true;
        NextSeedTime = Now(World) + ReflectionsVillainTuning::StartDelay();
        UE_LOG(LogReflectionsVillain, Log, TEXT("Villain: play is live; the Tarnish takes its first host in %.0f s."), ReflectionsVillainTuning::StartDelay());
    }
    if (!bRunning || Current || PendingHop.IsValid() || Now(World) < NextSeedTime || !IsRunLive())
    {
        return;
    }
    if (TotalHosts > 0)
    {
        HopFrom(nullptr, LastHostLocation);
    }
    else
    {
        TrySeed();
    }
}

// ---------------------------------------------------------------------------------------------- events

void UReflectionsVillainSubsystem::NotifyStateChanged(UReflectionsVillainPossessionComponent* Component, EReflectionsVillainInfection Old,
    EReflectionsVillainInfection New)
{
    AActor* Actor = Component ? Component->GetOwner() : nullptr;
    if (!Actor)
    {
        return;
    }
    const bool bWasCounted = Old == EReflectionsVillainInfection::Infected || Old == EReflectionsVillainInfection::Host;
    const bool bIsCounted = New == EReflectionsVillainInfection::Infected || New == EReflectionsVillainInfection::Host;
    if (!bWasCounted && bIsCounted)
    {
        Infected.Add(Actor);
        ++TotalInfections;
        if (!UReflectionsNpcSubsystem::Get(this))
        {
            CallGameFlow(TEXT("ReportInfected"), Actor);
        }
    }
    else if (bWasCounted && !bIsCounted)
    {
        Infected.Remove(Actor);
        if (!UReflectionsNpcSubsystem::Get(this))
        {
            CallGameFlow(TEXT("ReportCured"), Actor);
        }
    }
    if (New == EReflectionsVillainInfection::Host)
    {
        Host = Actor;
        LastHostLocation = Actor->GetActorLocation();
        ++TotalHosts;
        if (bRestoring)
        {
            return;   // a loaded save: he was already here, no taunt or banner
        }
        ReflectionsVillainFx::Voice(GetWorld(), TotalHosts > 1 ? ReflectionsVillainAssets::VoHop() : ReflectionsVillainAssets::VoTaunt(), Actor);
        const APawn* Player = ReflectionsVillainFx::PlayerPawn(GetWorld());
        if (TotalHosts == 1)
        {
            ReflectionsVillainFx::Sound2D(GetWorld(), ReflectionsVillainAssets::VoTauntHead(), 0.9f);
        }
        else if (Player && FVector::Dist(Player->GetActorLocation(), LastHostLocation) > 2800.0f && FMath::RandBool())
        {
            // Too far to hear the body: it whispers in the player's head instead.
            ReflectionsVillainFx::Sound2D(GetWorld(), ReflectionsVillainAssets::VoHopHead(), 0.7f);
        }
        if (TotalHosts == 1)
        {
            ShowMessage(ReflectionsVillainText::FirstHost(), ReflectionsVillainColors::Lilac);
        }
    }
    else if (Old == EReflectionsVillainInfection::Host && Host.Get() == Actor)
    {
        Host = nullptr;
        LastHostLocation = Actor->GetActorLocation();
    }
    if (New == EReflectionsVillainInfection::BurnedOut)
    {
        Actor->Tags.AddUnique(TEXT("Villain_BurnedOut"));
    }
}

void UReflectionsVillainSubsystem::SpreadFrom(AActor* FromHost)
{
    if (!ReflectionsVillainTuning::RangedSpread())
    {
        return;
    }
    if (!FromHost || bFinale || GetInfectedCount() + PendingSpreads >= ReflectionsVillainTuning::MaxInfected())
    {
        return;
    }
    AActor* Target = PickCandidate(FromHost->GetActorLocation(), ReflectionsVillainTuning::InfectRadius(), FromHost, false);
    if (Target)
    {
        LaunchWisp(FromHost->GetActorLocation() + FVector(0.0f, 0.0f, 70.0f), Target, EReflectionsVillainInfection::Infected, false);
    }
}

void UReflectionsVillainSubsystem::HostExpired(UReflectionsVillainPossessionComponent* Component)
{
    AActor* OldHost = Component ? Component->GetOwner() : nullptr;
    if (!OldHost)
    {
        return;
    }
    const FVector From = OldHost->GetActorLocation();
    Component->BurnOut(ReflectionsVillainTuning::KillHostsOnBurnout());
    if (bRunning && !bFinale && !PendingHop.IsValid())
    {
        HopFrom(OldHost, From);
    }
}

void UReflectionsVillainSubsystem::WispFinished(AReflectionsVillainWisp* Wisp, bool bSuccess)
{
    if (!Wisp)
    {
        return;
    }
    if (Wisp->IsHop())
    {
        if (PendingHop.Get() == Wisp)
        {
            PendingHop = nullptr;
        }
        if (!bSuccess)
        {
            LastHostLocation = Wisp->GetActorLocation();
            NextSeedTime = Now(GetWorld()) + 0.5;
        }
    }
    else
    {
        PendingSpreads = FMath::Max(0, PendingSpreads - 1);
    }
}

void UReflectionsVillainSubsystem::NotifyRift(AActor* Actor, EReflectionsWorld From, EReflectionsWorld To)
{
    static double LastRiftMessage = -100.0;
    const double Time = Now(GetWorld());
    if (Time - LastRiftMessage > 8.0)
    {
        LastRiftMessage = Time;
        ShowMessage(ReflectionsVillainText::Rift(SideName(this, To)), ReflectionsVillainColors::Lilac);
    }
}

void UReflectionsVillainSubsystem::HandleNpcInfection(AActor* Npc, EReflectionsNpcInfection State, AActor* Source)
{
    // Someone else tarnished (or cured) this NPC through the NPC system: give it the matching look.
    static const EReflectionsVillainInfection Map[] = {EReflectionsVillainInfection::None, EReflectionsVillainInfection::Infected,
        EReflectionsVillainInfection::Host, EReflectionsVillainInfection::BurnedOut};
    const uint8 Index = static_cast<uint8>(State);
    if (!IsValid(Npc) || Index >= UE_ARRAY_COUNT(Map))
    {
        return;
    }
    const EReflectionsVillainInfection Want = Map[Index];
    const UReflectionsVillainPossessionComponent* Component = Npc->FindComponentByClass<UReflectionsVillainPossessionComponent>();
    const EReflectionsVillainInfection Have = Component ? Component->GetState() : EReflectionsVillainInfection::None;
    if (Want != Have)
    {
        UReflectionsVillainPossessionComponent::Apply(Npc, Want, Source);
    }
}

void UReflectionsVillainSubsystem::HandleNpcSpellHit(AActor* Npc, const FReflectionsSpellHitData& Hit)
{
    FReflectionsSpellHitData Copy = Hit;
    Copy.Target = Npc;
    HandleSpellHit(Copy);
}

FString UReflectionsVillainSubsystem::StableId(const AActor* Actor)
{
    if (!IsValid(Actor))
    {
        return FString();
    }
    for (const FName& Tag : Actor->Tags)
    {
        const FString Text = Tag.ToString();
        if (Text.StartsWith(TEXT("Person_")))
        {
            return TEXT("P:") + Text.RightChop(7);
        }
    }
    if (Actor->IsNetStartupActor() && Actor->GetLevel())
    {
        return FString::Printf(TEXT("A:%s.%s"), *UWorld::RemovePIEPrefix(Actor->GetLevel()->GetOutermost()->GetName()), *Actor->GetName());
    }
    return FString();
}

void UReflectionsVillainSubsystem::HandleCheckpointSaved(const FReflectionsCheckpoint& Checkpoint)
{
    UWorld* World = GetWorld();
    UReflectionsGameFlowSubsystem* Flow = World && World->GetGameInstance() ? World->GetGameInstance()->GetSubsystem<UReflectionsGameFlowSubsystem>() : nullptr;
    if (!Flow)
    {
        return;
    }
    TArray<FString> InfectedIds;
    FString HostId;
    float HostLeft = 0.0f;
    for (const TWeakObjectPtr<AActor>& Weak : Infected)
    {
        AActor* Actor = Weak.Get();
        const FString Id = StableId(Actor);
        if (Id.IsEmpty() || !ReflectionsVillainFx::IsAlive(Actor))
        {
            continue;   // runtime-only bodies (spawned crowd) cannot be found again after a load
        }
        const UReflectionsVillainPossessionComponent* Component = Actor->FindComponentByClass<UReflectionsVillainPossessionComponent>();
        if (Component && Component->IsHost())
        {
            HostId = Id;
            HostLeft = Component->GetHostTimeLeft();
        }
        else
        {
            InfectedIds.Add(Id);
        }
    }
    int32 Version = 1;
    int32 Hosts = TotalHosts;
    int32 Infections = TotalInfections;
    int32 Band = BandReached;
    uint8 bClock = bSeedClockStarted ? 1 : 0;
    TArray<uint8> Bytes;
    FMemoryWriter Writer(Bytes);
    Writer << Version << InfectedIds << HostId << HostLeft << Hosts << Infections << Band << bClock;
    Flow->SetSaveData(TEXT("Villain"), Bytes);
    UE_LOG(LogReflectionsVillain, Log, TEXT("Villain: saved %d tarnished, host %s (%.0f s left)."), InfectedIds.Num(),
        HostId.IsEmpty() ? TEXT("none") : *HostId, HostLeft);
}

void UReflectionsVillainSubsystem::HandleCheckpointRestored(const FReflectionsCheckpoint& Checkpoint)
{
    UWorld* World = GetWorld();
    UReflectionsGameFlowSubsystem* Flow = World && World->GetGameInstance() ? World->GetGameInstance()->GetSubsystem<UReflectionsGameFlowSubsystem>() : nullptr;
    TArray<uint8> Bytes;
    if (!Flow || !Flow->GetSaveData(TEXT("Villain"), Bytes) || Bytes.Num() == 0)
    {
        return;
    }
    FMemoryReader Reader(Bytes);
    int32 Version = 0;
    Reader << Version;
    if (Version != 1)
    {
        return;
    }
    int32 Hosts = 0;
    int32 Infections = 0;
    int32 Band = 0;
    uint8 bClock = 0;
    PendingInfectedIds.Reset();
    Reader << PendingInfectedIds << PendingHostId << PendingHostLeft << Hosts << Infections << Band << bClock;
    if (Reader.IsError())
    {
        PendingInfectedIds.Reset();
        PendingHostId.Reset();
        return;
    }
    // Tallies first, so a restored host is not his "first" and the meter bands do not replay.
    TotalHosts = FMath::Max(TotalHosts, Hosts - (PendingHostId.IsEmpty() ? 0 : 1));
    TotalInfections = FMath::Max(TotalInfections, Infections);
    BandReached = FMath::Max(BandReached, Band);
    if (bClock && bRunning)
    {
        bSeedClockStarted = true;   // he was already at work: no fresh 20 s grace
        NextSeedTime = Now(World) + 4.0;
    }
    RestoreUntil = Now(World) + 10.0;
    UE_LOG(LogReflectionsVillain, Log, TEXT("Villain: restoring %d tarnished and host %s from the save."), PendingInfectedIds.Num(),
        PendingHostId.IsEmpty() ? TEXT("none") : *PendingHostId);
    TryRestoreSaved();
}

void UReflectionsVillainSubsystem::TryRestoreSaved()
{
    if (PendingInfectedIds.Num() == 0 && PendingHostId.IsEmpty())
    {
        return;
    }
    TMap<FString, AActor*> ById;
    for (AActor* Actor : NpcActors())
    {
        const FString Id = StableId(Actor);
        if (!Id.IsEmpty())
        {
            ById.Add(Id, Actor);
        }
    }
    TGuardValue<bool> Guard(bRestoring, true);
    if (!PendingHostId.IsEmpty() && !bFinale)
    {
        if (AActor** Found = ById.Find(PendingHostId); Found && IsCandidate(*Found, true))
        {
            if (UReflectionsVillainPossessionComponent* Component = UReflectionsVillainPossessionComponent::Apply(*Found, EReflectionsVillainInfection::Host))
            {
                Component->RestoreHostTime(PendingHostLeft);
            }
            PendingHostId.Reset();
        }
    }
    for (int32 Index = PendingInfectedIds.Num() - 1; Index >= 0; --Index)
    {
        AActor** Found = ById.Find(PendingInfectedIds[Index]);
        if (Found && IsCandidate(*Found, false))
        {
            UReflectionsVillainPossessionComponent::Apply(*Found, EReflectionsVillainInfection::Infected);
            PendingInfectedIds.RemoveAt(Index);
        }
    }
}

void UReflectionsVillainSubsystem::HandleNpcDied(AActor* Npc, AActor* Killer)
{
    if (UReflectionsVillainPossessionComponent* Component = Npc ? Npc->FindComponentByClass<UReflectionsVillainPossessionComponent>() : nullptr)
    {
        UE_LOG(LogReflectionsVillain, Verbose, TEXT("Villain: %s died tarnished (killer %s)."), *Npc->GetName(), Killer ? *Killer->GetName() : TEXT("none"));
        Component->HandleOwnerDied();
    }
}

void UReflectionsVillainSubsystem::HandleSpellHit(const FReflectionsSpellHitData& Hit)
{
    // His own magic never cures: a Tarnish bolt from a tarnished caster (or the true form) leaves the target tarnished.
    // Soldiers' and the player's spells do cure, and the NPC system moves the meter.
    if (const AActor* Caster = Hit.Caster.Get())
    {
        const EReflectionsVillainInfection CasterState = UReflectionsVillainPossessionComponent::StateOf(Caster);
        if (Caster->IsA<AReflectionsVillainBoss>() || CasterState == EReflectionsVillainInfection::Infected
            || CasterState == EReflectionsVillainInfection::Host)
        {
            return;
        }
    }
    AActor* Target = Hit.Target.Get();
    UReflectionsVillainPossessionComponent* Component = Target ? Target->FindComponentByClass<UReflectionsVillainPossessionComponent>() : nullptr;
    if (!Component)
    {
        return;
    }
    static double LastCureMessage = -100.0;
    if (Component->GetState() == EReflectionsVillainInfection::Infected)
    {
        Component->Cleanse();
        const double Time = Now(GetWorld());
        const APawn* Player = ReflectionsVillainFx::PlayerPawn(GetWorld());
        const bool bSeen = Player && (Hit.Caster.Get() == Player || FVector::Dist(Player->GetActorLocation(), Target->GetActorLocation()) < 3000.0f);
        if (bSeen && Time - LastCureMessage > 10.0)
        {
            LastCureMessage = Time;
            ShowMessage(ReflectionsVillainText::Cured(), ReflectionsVillainColors::FinalWhite);
            ReflectionsVillainFx::Voice(GetWorld(), ReflectionsVillainAssets::VoCured(), Target, 0.9f);
        }
    }
    else if (Component->IsHost())
    {
        // Hurt in his body, he flees early.
        Component->ShortenHost(0.6f);
    }
}

void UReflectionsVillainSubsystem::HandleBookComplete()
{
    BeginFinale();
}

void UReflectionsVillainSubsystem::HandleProgressRestored()
{
    // A loaded checkpoint that already has the whole mirror: Final Spell and true form, without the announcement.
    const UReflectionsWorldJumpSubsystem* Jump = UReflectionsWorldJumpSubsystem::Get(this);
    if (Jump && Jump->IsBookComplete() && !bFinale)
    {
        StartFinale(false);
    }
}

// ---------------------------------------------------------------------------------------------- NPC access

TArray<AActor*> UReflectionsVillainSubsystem::NpcActors() const
{
    TArray<AActor*> Result;
    UWorld* World = GetWorld();
    if (!World)
    {
        return Result;
    }
    TSet<AActor*> Drivers;
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(World))
    {
        for (AActor* Npc : Npcs->GetNpcActors())
        {
            if (IsValid(Npc))
            {
                Result.AddUnique(Npc);
                if (UReflectionsNpcReactionComponent* Component = Npcs->FindNpc(Npc))
                {
                    if (ACharacter* Driver = Component->GetLocomotionDriver())
                    {
                        Drivers.Add(Driver);
                    }
                }
            }
        }
    }
    for (TActorIterator<APawn> It(World); It; ++It)
    {
        if (!Drivers.Contains(*It))
        {
            Result.AddUnique(*It);
        }
    }
    return Result;
}

ACharacter* UReflectionsVillainSubsystem::DriverOf(AActor* Npc) const
{
    auto Animated = [](ACharacter* Character)
    {
        return Character && Character->GetMesh() && Character->GetMesh()->GetAnimInstance() ? Character : nullptr;
    };
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(GetWorld()))
    {
        if (UReflectionsNpcReactionComponent* Component = Npcs->FindNpc(Npc))
        {
            if (ACharacter* Driver = Animated(Component->GetMovementCharacter()))
            {
                return Driver;
            }
        }
    }
    return Animated(Cast<ACharacter>(Npc));
}

// ---------------------------------------------------------------------------------------------- conversion

bool UReflectionsVillainSubsystem::IsConverting(const AActor* Actor) const
{
    for (const TWeakObjectPtr<AReflectionsVillainConversion>& Conversion : Conversions)
    {
        if (Conversion.IsValid() && Conversion->Involves(Actor))
        {
            return true;
        }
    }
    return false;
}

float UReflectionsVillainSubsystem::BeginConversion(AActor* Attacker, AActor* Victim)
{
    UWorld* World = GetWorld();
    auto Refuse = [Attacker, Victim](const TCHAR* Why)
    {
        UE_LOG(LogReflectionsVillain, Verbose, TEXT("BeginConversion %s -> %s refused: %s"), *GetNameSafe(Attacker), *GetNameSafe(Victim), Why);
        return 0.0f;
    };
    if (!World || !IsValid(Attacker) || !IsValid(Victim) || Attacker == Victim || bVictory)
    {
        return Refuse(TEXT("invalid actors or the game is won"));
    }
    if (IsConverting(Attacker) || IsConverting(Victim))
    {
        return Refuse(TEXT("already converting"));
    }
    ACharacter* A = DriverOf(Attacker);
    ACharacter* V = DriverOf(Victim);
    const EReflectionsVillainInfection From = UReflectionsVillainPossessionComponent::StateOf(Attacker);
    if (!A || !V || A == V)
    {
        return Refuse(TEXT("no animated driver character"));
    }
    if (From != EReflectionsVillainInfection::Infected && From != EReflectionsVillainInfection::Host)
    {
        return Refuse(TEXT("attacker is not tarnished"));
    }
    if (!IsCandidate(Victim, false))
    {
        return Refuse(TEXT("victim cannot be taken (player, tarnished, friendly, dead or no visible body)"));
    }
    if (FVector::Dist(A->GetActorLocation(), V->GetActorLocation()) > 700.0f)
    {
        return Refuse(TEXT("too far apart"));
    }
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AReflectionsVillainConversion* Conversion = World->SpawnActor<AReflectionsVillainConversion>(AReflectionsVillainConversion::StaticClass(),
        A->GetActorLocation(), FRotator::ZeroRotator, Params);
    if (!Conversion)
    {
        return 0.0f;
    }
    Conversions.Add(Conversion);
    const float Length = Conversion->Begin(Attacker, Victim, A, V);
    if (Length <= 0.0f)
    {
        Conversions.Remove(Conversion);
        Conversion->Destroy();
    }
    return Length;
}

void UReflectionsVillainSubsystem::ConversionFinished(AReflectionsVillainConversion* Conversion, bool bConverted)
{
    Conversions.RemoveAll([Conversion](const TWeakObjectPtr<AReflectionsVillainConversion>& Item)
    {
        return !Item.IsValid() || Item.Get() == Conversion;
    });
}

float UReflectionsVillainSubsystem::ConvertNearest()
{
    UWorld* World = GetWorld();
    APawn* Player = ReflectionsVillainFx::PlayerPawn(World);
    if (!World || !Player)
    {
        return 0.0f;
    }
    // Victim: the clean NPC nearest the player. Attacker: the nearest tarnished one, else a fresh NPC made tarnished.
    AActor* Victim = PickCandidate(Player->GetActorLocation(), 4000.0f, nullptr, false);
    if (!Victim)
    {
        return 0.0f;
    }
    AActor* Attacker = nullptr;
    float Best = TNumericLimits<float>::Max();
    for (const TWeakObjectPtr<AActor>& Item : Infected)
    {
        if (AActor* Actor = Item.Get())
        {
            const float Distance = FVector::Dist(Actor->GetActorLocation(), Victim->GetActorLocation());
            if (Distance < Best && !IsConverting(Actor))
            {
                Best = Distance;
                Attacker = Actor;
            }
        }
    }
    if (!Attacker || Best > 700.0f)
    {
        Attacker = PickCandidate(Victim->GetActorLocation(), 4000.0f, Victim, false);
        if (!Attacker)
        {
            return 0.0f;
        }
        UReflectionsVillainPossessionComponent::Apply(Attacker, EReflectionsVillainInfection::Infected);
        // Bring it to arm's length (move whatever walks for it); the tackle alignment does the rest.
        AActor* Mover = DriverOf(Attacker) ? static_cast<AActor*>(DriverOf(Attacker)) : Attacker;
        const FVector Away = (Attacker->GetActorLocation() - Victim->GetActorLocation()).GetSafeNormal2D();
        Mover->SetActorLocation(Victim->GetActorLocation() + (Away.IsNearlyZero() ? FVector::ForwardVector : Away) * 300.0f, false,
            nullptr, ETeleportType::TeleportPhysics);
    }
    const float Length = BeginConversion(Attacker, Victim);
    if (Length > 0.0f)
    {
        // The NPC system holds both when its own hunt calls BeginConversion; this test path asks for the hold itself
        // (HoldNpc(Actor, Seconds), by name so it is harmless before that function exists).
        UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(World);
        UFunction* Hold = Npcs ? Npcs->FindFunction(TEXT("HoldNpc")) : nullptr;
        for (AActor* Actor : {Attacker, Victim})
        {
            if (!Hold)
            {
                break;
            }
            uint8* Params = static_cast<uint8*>(FMemory_Alloca_Aligned(FMath::Max<int32>(1, Hold->ParmsSize), Hold->GetMinAlignment()));
            FMemory::Memzero(Params, FMath::Max<int32>(1, Hold->ParmsSize));
            for (TFieldIterator<FProperty> It(Hold); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
            {
                It->InitializeValue_InContainer(Params);
                if (It->HasAnyPropertyFlags(CPF_ReturnParm | CPF_OutParm))
                {
                    continue;
                }
                if (FObjectPropertyBase* Object = CastField<FObjectPropertyBase>(*It))
                {
                    Object->SetObjectPropertyValue_InContainer(Params, Actor);
                }
                else if (FFloatProperty* Float = CastField<FFloatProperty>(*It))
                {
                    Float->SetPropertyValue_InContainer(Params, Length + 1.0f);
                }
                else if (FDoubleProperty* Double = CastField<FDoubleProperty>(*It))
                {
                    Double->SetPropertyValue_InContainer(Params, Length + 1.0);
                }
            }
            Npcs->ProcessEvent(Hold, Params);
            for (TFieldIterator<FProperty> It(Hold); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
            {
                It->DestroyValue_InContainer(Params);
            }
        }
    }
    return Length;
}

// ---------------------------------------------------------------------------------------------- finale

void UReflectionsVillainSubsystem::RecheckMap()
{
    UWorld* World = GetWorld();
    if (!World || bVictory)
    {
        return;
    }
    const bool bMarkerBefore = bArenaFromMarker;
    if (!bArenaFromMarker)
    {
        for (TActorIterator<AReflectionsVillainArena> It(World); It; ++It)
        {
            CacheArena();
            break;
        }
    }
    if (bArenaFromMarker && !bMarkerBefore)
    {
        UE_LOG(LogReflectionsVillain, Log, TEXT("Villain: arena marker streamed in at %s (radius %.0f)."), *ArenaCenter.ToCompactString(), ArenaRadius);
        // A true form already waiting at a fallback spot (book completed or restored before the sublevel loaded) moves there.
        if (AReflectionsVillainBoss* Waiting = Boss.Get(); Waiting && Waiting->GetBossState() == EReflectionsVillainBossState::Dormant)
        {
            Waiting->InitArena(ArenaCenter, ArenaRadius);
        }
    }
    if (!bMapEnabled && !bFinale && ReflectionsVillainTuning::AutoStart() == 1)
    {
        bool bHasAnchors = bArenaFromMarker;
        for (TActorIterator<AReflectionsWorldAnchor> It(World); It && !bHasAnchors; ++It)
        {
            bHasAnchors = true;
        }
        if (bHasAnchors)
        {
            bMapEnabled = true;
            bRunning = true;
            bSeedClockStarted = false;
            UE_LOG(LogReflectionsVillain, Log, TEXT("Villain: world anchors streamed in; possession on (starts once play is live)."));
        }
    }
}

bool UReflectionsVillainSubsystem::IsRunLive() const
{
    if (IsCutscenePlaying())
    {
        return false;
    }
    const UWorld* World = GetWorld();
    const UGameInstance* Instance = World ? World->GetGameInstance() : nullptr;
    if (const UReflectionsGameFlowSubsystem* Flow = Instance ? Instance->GetSubsystem<UReflectionsGameFlowSubsystem>() : nullptr)
    {
        // Game flow's IsRunLive: play has begun in this map (title dismissed or restore applied), no menu, not game over.
        // It also covers the first frames of a map load, where the screen already reads None behind the coming title.
        if (!Flow->IsRunLive())
        {
            return false;
        }
    }
    return !World || !World->IsPaused();
}

void UReflectionsVillainSubsystem::CacheArena()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }
    for (TActorIterator<AReflectionsVillainArena> It(World); It; ++It)
    {
        ArenaCenter = ReflectionsVillainFx::Ground(World, It->GetActorLocation(), *It, 100.0f, 2000.0f);
        ArenaRadius = It->ArenaRadius;
        bHasArena = true;
        bArenaFromMarker = true;
        return;
    }
    if (bHasArena)
    {
        return;
    }
    // Read the anchors directly (not through the world-jump subsystem, which may not have indexed them yet when
    // this runs at map start): the White page inside the White anchor's box, else the White anchor itself.
    AReflectionsWorldAnchor* WhiteAnchor = nullptr;
    for (TActorIterator<AReflectionsWorldAnchor> It(World); It; ++It)
    {
        if (It->World == EReflectionsWorld::White)
        {
            WhiteAnchor = *It;
            break;
        }
    }
    if (!WhiteAnchor)
    {
        return;
    }
    for (TActorIterator<AReflectionsBookPagePickup> It(World); It; ++It)
    {
        if (WhiteAnchor->ContainsLocation(It->GetActorLocation()))
        {
            ArenaCenter = ReflectionsVillainFx::Ground(World, It->GetActorLocation(), *It, 100.0f, 2000.0f);
            ArenaRadius = MeasureOpenRadius(World, ArenaCenter);
            bHasArena = true;
            return;
        }
    }
    ArenaCenter = ReflectionsVillainFx::Ground(World, WhiteAnchor->GetActorLocation(), WhiteAnchor, 500.0f, 5000.0f);
    ArenaRadius = MeasureOpenRadius(World, ArenaCenter);
    bHasArena = true;
}

bool UReflectionsVillainSubsystem::GetArena(FVector& OutCenter, float& OutRadius) const
{
    OutCenter = ArenaCenter;
    OutRadius = ArenaRadius;
    return bHasArena;
}

void UReflectionsVillainSubsystem::EnsureFinalSpell()
{
    APawn* Player = ReflectionsVillainFx::PlayerPawn(GetWorld());
    if (Player && !Player->FindComponentByClass<UReflectionsFinalSpellComponent>())
    {
        UReflectionsFinalSpellComponent* Spell = NewObject<UReflectionsFinalSpellComponent>(Player, TEXT("FinalSpell"));
        Spell->RegisterComponent();
    }
}

void UReflectionsVillainSubsystem::SpawnBossAtArena()
{
    UWorld* World = GetWorld();
    if (!World || Boss.IsValid() || bVictory)
    {
        return;
    }
    if (!bHasArena)
    {
        CacheArena();
    }
    if (!bHasArena)
    {
        APawn* Player = ReflectionsVillainFx::PlayerPawn(World);
        if (!Player)
        {
            return;
        }
        ArenaCenter = ReflectionsVillainFx::Ground(World, Player->GetActorLocation() + Player->GetActorForwardVector() * 1500.0f, Player);
        bHasArena = true;
        UE_LOG(LogReflectionsVillain, Warning, TEXT("Villain: no arena marker, White page or White anchor; using a point in front of the player."));
    }
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AReflectionsVillainBoss* NewBoss = World->SpawnActor<AReflectionsVillainBoss>(AReflectionsVillainBoss::StaticClass(),
        ArenaCenter + FVector(0.0f, 0.0f, 150.0f), FRotator::ZeroRotator, Params);
    if (NewBoss)
    {
        NewBoss->InitArena(ArenaCenter, ArenaRadius);
        Boss = NewBoss;
        UE_LOG(LogReflectionsVillain, Log, TEXT("Villain: true form waiting at %s (radius %.0f)"), *ArenaCenter.ToCompactString(), ArenaRadius);
    }
}

void UReflectionsVillainSubsystem::BeginFinale()
{
    StartFinale(true);
}

void UReflectionsVillainSubsystem::StartFinale(bool bAnnounce)
{
    if (bFinale || bVictory)
    {
        return;
    }
    bFinale = true;
    bRunning = false;
    // He leaves his body to gather himself in the tower.
    if (AActor* Current = Host.Get())
    {
        if (UReflectionsVillainPossessionComponent* Component = Current->FindComponentByClass<UReflectionsVillainPossessionComponent>())
        {
            Component->Cleanse();
        }
    }
    CacheArena();
    SpawnBossAtArena();
    if (!bAnnounce)
    {
        // A loaded checkpoint: no banner, no cutscene, the Final Spell straight away.
        bFinaleAnnounced = true;
        EnsureFinalSpell();
        return;
    }
    // The "Mirror Is Whole" cutscene (CS05) starts here. While it (or any cutscene quests started off the same
    // event) plays, the banner, sting, Final Spell and manifest wait for OnCutsceneFinished (skipped or not).
    if (CallBool(Cutscenes(), TEXT("PlayCutscene"), TEXT("MirrorWhole")))
    {
        bAwaitMirrorCutscene = true;
        bMirrorCutscenePlayed = true;
        return;
    }
    if (UWorld* World = GetWorld())
    {
        FTimerHandle Check;
        World->GetTimerManager().SetTimer(Check, FTimerDelegate::CreateWeakLambda(this, [this]()
        {
            if (IsCutscenePlaying())
            {
                bAwaitMirrorCutscene = true;
                bMirrorCutscenePlayed = true;
            }
            else
            {
                AnnounceFinale();
            }
        }), 0.5f, false);
    }
}

AReflectionsVillainBoss* UReflectionsVillainSubsystem::SpawnBossNearPlayer()
{
    UWorld* World = GetWorld();
    APawn* Player = ReflectionsVillainFx::PlayerPawn(World);
    if (!World || !Player)
    {
        return nullptr;
    }
    if (AReflectionsVillainBoss* Old = Boss.Get())
    {
        Old->Destroy();
        Boss = nullptr;
    }
    bVictory = false;
    ArenaCenter = ReflectionsVillainFx::Ground(World, Player->GetActorLocation() + Player->GetActorForwardVector() * 1300.0f, Player);
    ArenaRadius = 1400.0f;
    bHasArena = true;
    if (!bFinale)
    {
        BeginFinale();
    }
    else
    {
        SpawnBossAtArena();
    }
    return Boss.Get();
}

void UReflectionsVillainSubsystem::NotifyBossDefeated(AReflectionsVillainBoss* DefeatedBoss)
{
    if (bVictory)
    {
        return;
    }
    bVictory = true;
    CleanseAll();
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }
    FTimerHandle Victory;
    World->GetTimerManager().SetTimer(Victory, FTimerDelegate::CreateWeakLambda(this, [this]()
    {
        // The story's ending cutscene first (CS06), then game flow's victory screen when it finishes.
        if (CallBool(Cutscenes(), TEXT("PlayCutscene"), TEXT("Ending")))
        {
            bAwaitEnding = true;
            FTimerHandle Safety;
            GetWorld()->GetTimerManager().SetTimer(Safety, FTimerDelegate::CreateWeakLambda(this, [this]()
            {
                if (bAwaitEnding)
                {
                    ShowVictoryNow();
                }
            }), 75.0f, false);
            return;
        }
        ShowVictoryNow();
    }), 2.5f, false);
}

void UReflectionsVillainSubsystem::ShowVictoryNow()
{
    bAwaitEnding = false;
    if (GameFlow())
    {
        CallGameFlow(TEXT("ShowVictory"), nullptr);
    }
    else if (UReflectionsVillainHudWidget* Widget = GetOrCreateHud())
    {
        Widget->ShowBanner(ReflectionsVillainText::VictoryTitle(), ReflectionsVillainText::VictorySubtitle(), ReflectionsVillainColors::FinalGold);
    }
}

void UReflectionsVillainSubsystem::AnnounceFinale()
{
    bAwaitMirrorCutscene = false;
    if (bFinaleAnnounced)
    {
        return;
    }
    bFinaleAnnounced = true;
    EnsureFinalSpell();
    if (UReflectionsVillainHudWidget* Widget = GetOrCreateHud())
    {
        // After the cutscene its own caption already said "The Mirror Is Whole": show only the second line.
        Widget->ShowBanner(bMirrorCutscenePlayed ? FText::GetEmpty() : ReflectionsVillainText::MirrorWholeTitle(),
            ReflectionsVillainText::MirrorWholeSubtitle(SideName(this, EReflectionsWorld::White)), ReflectionsVillainColors::FinalGold);
    }
    ReflectionsVillainFx::Sound2D(GetWorld(), ReflectionsVillainAssets::FinalSpellSound(), 0.8f);
}

bool UReflectionsVillainSubsystem::CanManifest() const
{
    return bFinaleAnnounced && !IsCutscenePlaying();
}

float UReflectionsVillainSubsystem::InfectIntervalNow() const
{
    return ReflectionsVillainTuning::InfectInterval() * (PagesFound >= 1 ? 0.75f : 1.0f);
}

bool UReflectionsVillainSubsystem::IsCutscenePlaying() const
{
    return CallBool(Cutscenes(), TEXT("IsCutscenePlaying"));
}

void UReflectionsVillainSubsystem::HandleCutsceneFinished(FName Cutscene, bool bSkipped)
{
    if (bAwaitMirrorCutscene)
    {
        AnnounceFinale();
    }
    if (bAwaitEnding && Cutscene == TEXT("Ending"))
    {
        ShowVictoryNow();
    }
}

void UReflectionsVillainSubsystem::HandlePagesChanged(int32 Pages, int32 PagesForBook)
{
    if (Pages == 2 && PagesFound < 2)
    {
        // Story MQ07_02: "Two leaves. You're building us a door, Silverer."
        ReflectionsVillainFx::Sound2D(GetWorld(), ReflectionsVillainAssets::StoryLine(TEXT("MQ07_02")), 0.9f);
    }
    PagesFound = Pages;
}

void UReflectionsVillainSubsystem::HandleGameLost()
{
    // Story MQ_LOSE_01 under game flow's lose screen; a UI sound so it plays while the game is paused.
    if (USoundBase* Line = ReflectionsVillainAssets::StoryLine(TEXT("MQ_LOSE_01")))
    {
        UGameplayStatics::PlaySound2D(this, Line, 1.0f, 1.0f, 0.0f, nullptr, nullptr, true);
    }
}

UObject* UReflectionsVillainSubsystem::Cutscenes() const
{
    UWorld* World = GetWorld();
    static TWeakObjectPtr<UClass> Cached;
    UClass* Class = Cached.Get();
    if (!Class)
    {
        Class = FindObject<UClass>(nullptr, TEXT("/Script/reflections.ReflectionsCutsceneSubsystem"));
        Cached = Class;
    }
    if (!World || !Class || !Class->IsChildOf(UWorldSubsystem::StaticClass()))
    {
        return nullptr;
    }
    return World->GetSubsystemBase(TSubclassOf<UWorldSubsystem>(Class));
}

bool UReflectionsVillainSubsystem::CallBool(UObject* Target, FName Function, FName NameArg) const
{
    UFunction* Func = Target ? Target->FindFunction(Function) : nullptr;
    if (!Func)
    {
        return false;
    }
    uint8* Params = static_cast<uint8*>(FMemory_Alloca_Aligned(FMath::Max<int32>(1, Func->ParmsSize), Func->GetMinAlignment()));
    FMemory::Memzero(Params, FMath::Max<int32>(1, Func->ParmsSize));
    bool bResult = false;
    for (TFieldIterator<FProperty> It(Func); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
    {
        It->InitializeValue_InContainer(Params);
        if (FNameProperty* NameParam = CastField<FNameProperty>(*It); NameParam && !It->HasAnyPropertyFlags(CPF_ReturnParm | CPF_OutParm))
        {
            NameParam->SetPropertyValue_InContainer(Params, NameArg);
        }
    }
    Target->ProcessEvent(Func, Params);
    for (TFieldIterator<FProperty> It(Func); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
    {
        if (FBoolProperty* Return = CastField<FBoolProperty>(*It); Return && It->HasAnyPropertyFlags(CPF_ReturnParm))
        {
            bResult = Return->GetPropertyValue_InContainer(Params);
        }
        It->DestroyValue_InContainer(Params);
    }
    return bResult;
}

float UReflectionsVillainSubsystem::CallFloat(UObject* Target, FName Function) const
{
    UFunction* Func = Target ? Target->FindFunction(Function) : nullptr;
    if (!Func || Func->NumParms != 1)
    {
        return 0.0f;
    }
    uint8* Params = static_cast<uint8*>(FMemory_Alloca_Aligned(FMath::Max<int32>(1, Func->ParmsSize), Func->GetMinAlignment()));
    FMemory::Memzero(Params, FMath::Max<int32>(1, Func->ParmsSize));
    Target->ProcessEvent(Func, Params);
    float Result = 0.0f;
    for (TFieldIterator<FProperty> It(Func); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
    {
        if (FFloatProperty* Float = CastField<FFloatProperty>(*It))
        {
            Result = Float->GetPropertyValue_InContainer(Params);
        }
        else if (FDoubleProperty* Double = CastField<FDoubleProperty>(*It))
        {
            Result = static_cast<float>(Double->GetPropertyValue_InContainer(Params));
        }
    }
    return Result;
}

void UReflectionsVillainSubsystem::BindByName(UObject* Target, FName Delegate, FName Handler)
{
    FMulticastDelegateProperty* Property = Target ? CastField<FMulticastDelegateProperty>(Target->GetClass()->FindPropertyByName(Delegate)) : nullptr;
    if (!Property || !FindFunction(Handler))
    {
        return;
    }
    FScriptDelegate Bound;
    Bound.BindUFunction(this, Handler);
    Property->AddDelegate(MoveTemp(Bound), Target);
}

void UReflectionsVillainSubsystem::CleanseAll()
{
    TArray<TWeakObjectPtr<AActor>> Copy = Infected.Array();
    for (const TWeakObjectPtr<AActor>& Actor : Copy)
    {
        if (AActor* Resolved = Actor.Get())
        {
            if (UReflectionsVillainPossessionComponent* Component = Resolved->FindComponentByClass<UReflectionsVillainPossessionComponent>())
            {
                Component->Cleanse();
            }
        }
    }
}

void UReflectionsVillainSubsystem::SpawnTestHosts(int32 Count)
{
    UWorld* World = GetWorld();
    APawn* Player = ReflectionsVillainFx::PlayerPawn(World);
    if (!World || !Player)
    {
        return;
    }
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
    const FVector Center = Player->GetActorLocation();
    for (int32 Index = 0; Index < Count; ++Index)
    {
        const float Angle = (Index + FMath::FRand() * 0.5f) * 2.0f * PI / FMath::Max(1, Count);
        const float Radius = FMath::FRandRange(500.0f, 1500.0f);
        const FVector Point = Center + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f) * Radius;
        const FVector Ground = ReflectionsVillainFx::Ground(World, Point, Player, 300.0f, 3000.0f);
        World->SpawnActor<AReflectionsVillainTestHost>(AReflectionsVillainTestHost::StaticClass(), Ground + FVector(0.0f, 0.0f, 95.0f),
            FRotator(0.0f, FMath::FRandRange(0.0f, 360.0f), 0.0f), Params);
    }
}

FString UReflectionsVillainSubsystem::DescribeStatus() const
{
    const AActor* Current = Host.Get();
    const AReflectionsVillainBoss* TrueForm = Boss.Get();
    return FString::Printf(TEXT("Villain: map %s, running %d, finale %d, victory %d | host %s | infected %d (total infections %d, hosts %d) | "
        "pending hop %d, spreads %d | arena %s r%.0f | boss %s %.0f/%.0f | game flow %s"),
        bMapEnabled ? TEXT("enabled") : TEXT("disabled"), bRunning, bFinale, bVictory, Current ? *Current->GetName() : TEXT("none"),
        GetInfectedCount(), TotalInfections, TotalHosts, PendingHop.IsValid(), PendingSpreads,
        bHasArena ? *ArenaCenter.ToCompactString() : TEXT("none"), ArenaRadius,
        TrueForm ? *TrueForm->DescribeState() : TEXT("none"), TrueForm ? TrueForm->GetHealth() : 0.0f, TrueForm ? TrueForm->GetMaxHealth() : 0.0f,
        GameFlow() ? TEXT("found") : TEXT("missing"));
}

// ---------------------------------------------------------------------------------------------- HUD

UReflectionsVillainHudWidget* UReflectionsVillainSubsystem::GetOrCreateHud()
{
    if (Hud)
    {
        return Hud;
    }
    UWorld* World = GetWorld();
    APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
    if (!PC || !PC->IsLocalController())
    {
        return nullptr;
    }
    Hud = CreateWidget<UReflectionsVillainHudWidget>(PC, UReflectionsVillainHudWidget::StaticClass());
    if (Hud)
    {
        Hud->AddToViewport(25);
    }
    return Hud;
}

void UReflectionsVillainSubsystem::ShowMessage(const FText& Text, const FLinearColor& Color)
{
    if (UReflectionsVillainHudWidget* Widget = GetOrCreateHud())
    {
        Widget->ShowMessage(Text, Color);
    }
    UE_LOG(LogReflectionsVillain, Log, TEXT("Villain message: %s"), *Text.ToString());
}

// ---------------------------------------------------------------------------------------------- game flow bridge

UObject* UReflectionsVillainSubsystem::GameFlow() const
{
    const UWorld* World = GetWorld();
    UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
    if (!GameInstance)
    {
        return nullptr;
    }
    static TWeakObjectPtr<UClass> Cached;
    UClass* Class = Cached.Get();
    if (!Class)
    {
        Class = FindObject<UClass>(nullptr, TEXT("/Script/reflections.ReflectionsGameFlowSubsystem"));
        Cached = Class;
    }
    if (!Class || !Class->IsChildOf(UGameInstanceSubsystem::StaticClass()))
    {
        return nullptr;
    }
    return GameInstance->GetSubsystemBase(TSubclassOf<UGameInstanceSubsystem>(Class));
}

void UReflectionsVillainSubsystem::CallGameFlow(FName Function, AActor* Arg) const
{
    UObject* Target = GameFlow();
    UFunction* Func = Target ? Target->FindFunction(Function) : nullptr;
    if (!Func)
    {
        UE_LOG(LogReflectionsVillain, Verbose, TEXT("Villain: game flow %s not available"), *Function.ToString());
        return;
    }
    uint8* Params = static_cast<uint8*>(FMemory_Alloca_Aligned(FMath::Max<int32>(1, Func->ParmsSize), Func->GetMinAlignment()));
    FMemory::Memzero(Params, FMath::Max<int32>(1, Func->ParmsSize));
    for (TFieldIterator<FProperty> It(Func); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
    {
        It->InitializeValue_InContainer(Params);
        if (Arg && !It->HasAnyPropertyFlags(CPF_ReturnParm | CPF_OutParm))
        {
            if (FObjectPropertyBase* Object = CastField<FObjectPropertyBase>(*It))
            {
                if (Arg->IsA(Object->PropertyClass))
                {
                    Object->SetObjectPropertyValue_InContainer(Params, Arg);
                }
            }
        }
    }
    Target->ProcessEvent(Func, Params);
    for (TFieldIterator<FProperty> It(Func); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
    {
        It->DestroyValue_InContainer(Params);
    }
}

// ---------------------------------------------------------------------------------------------- console

#if !UE_BUILD_SHIPPING
namespace
{
    UReflectionsVillainSubsystem* ConsoleVillain(UWorld* World)
    {
        UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(World);
        if (!Villain)
        {
            UE_LOG(LogReflectionsVillain, Warning, TEXT("Villain commands need a game or PIE world."));
        }
        return Villain;
    }

    FAutoConsoleCommandWithWorldAndArgs CmdStart(TEXT("Villain.Start"), TEXT("Let the villain take hosts in this map now."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            if (UReflectionsVillainSubsystem* V = ConsoleVillain(World)) { V->StartPossession(); }
        }));
    FAutoConsoleCommandWithWorldAndArgs CmdStop(TEXT("Villain.Stop"), TEXT("Stop the villain taking new hosts."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            if (UReflectionsVillainSubsystem* V = ConsoleVillain(World)) { V->StopPossession(); }
        }));
    FAutoConsoleCommandWithWorldAndArgs CmdHop(TEXT("Villain.Hop"), TEXT("Make the villain leave his host now (or take a first host)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            if (UReflectionsVillainSubsystem* V = ConsoleVillain(World)) { V->ForceHop(); }
        }));
    FAutoConsoleCommandWithWorldAndArgs CmdStatus(TEXT("Villain.Status"), TEXT("Log the villain's state."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            if (UReflectionsVillainSubsystem* V = ConsoleVillain(World)) { UE_LOG(LogReflectionsVillain, Display, TEXT("%s"), *V->DescribeStatus()); }
        }));
    FAutoConsoleCommandWithWorldAndArgs CmdHosts(TEXT("Villain.SpawnTestHosts"), TEXT("Spawn N wandering test NPCs around the player (default 6)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsVillainSubsystem* V = ConsoleVillain(World)) { V->SpawnTestHosts(Args.Num() > 0 ? FCString::Atoi(*Args[0]) : 6); }
        }));
    FAutoConsoleCommandWithWorldAndArgs CmdFinale(TEXT("Villain.Finale"), TEXT("Act as if the book were complete: Final Spell + his true form at the arena."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            if (UReflectionsVillainSubsystem* V = ConsoleVillain(World)) { V->BeginFinale(); }
        }));
    FAutoConsoleCommandWithWorldAndArgs CmdBossHere(TEXT("Villain.BossHere"), TEXT("Raise his true form 13 m in front of the player (test arena)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            if (UReflectionsVillainSubsystem* V = ConsoleVillain(World)) { V->SpawnBossNearPlayer(); }
        }));
    FAutoConsoleCommandWithWorldAndArgs CmdDamage(TEXT("Villain.DamageBoss"), TEXT("Hit his true form with N Final Spell damage (default 125)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            UReflectionsVillainSubsystem* V = ConsoleVillain(World);
            if (AReflectionsVillainBoss* B = V ? V->GetBoss() : nullptr)
            {
                ReflectionsVillainFx::Damage(B, Args.Num() > 0 ? FCString::Atof(*Args[0]) : ReflectionsVillainTuning::FinalSpellDamage(),
                    ReflectionsVillainFx::PlayerPawn(World), B->GetActorLocation() + FVector(300.0f, 0.0f, 0.0f), 0.0f,
                    UReflectionsFinalSpellDamageType::StaticClass());
            }
        }));
    FAutoConsoleCommandWithWorldAndArgs CmdConvert(TEXT("Villain.Convert"), TEXT("Nearest tarnished NPC tackles and converts the clean NPC nearest the player."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            if (UReflectionsVillainSubsystem* V = ConsoleVillain(World))
            {
                // Show refusal reasons for the test command.
                LogReflectionsVillain.SetVerbosity(ELogVerbosity::Verbose);
                UE_LOG(LogReflectionsVillain, Display, TEXT("Villain.Convert: %.2f s"), V->ConvertNearest());
            }
        }));
    FAutoConsoleCommandWithWorldAndArgs CmdCleanse(TEXT("Villain.CleanseAll"), TEXT("Drive the villain out of every NPC."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            if (UReflectionsVillainSubsystem* V = ConsoleVillain(World)) { V->CleanseAll(); }
        }));
}
#endif

#undef LOCTEXT_NAMESPACE
