#include "ReflectionsStrongholdGate.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/World.h"
#include "Net/UnrealNetwork.h"
#include "Quests/ReflectionsQuestSubsystem.h"

AReflectionsStrongholdGate::AReflectionsStrongholdGate()
{
    PrimaryActorTick.bCanEverTick = false;
    bReplicates = true;
    // Relevance cannot open an actor channel until the client has loaded its level.
    // The pilot needs an always-loaded actor or persistent per-site state before streaming tests.
    bAlwaysRelevant = true;
    NetDormancy = DORM_Never;
    SetReplicateMovement(false);

    Frame = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Frame"));
    SetRootComponent(Frame);
    OccupiedPennants = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("OccupiedPennants"));
    OccupiedPennants->SetupAttachment(Frame);
    ReclaimedPennants = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ReclaimedPennants"));
    ReclaimedPennants->SetupAttachment(Frame);

    for (UStaticMeshComponent* Mesh : {Frame.Get(), OccupiedPennants.Get(), ReclaimedPennants.Get()})
    {
        Mesh->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
        Mesh->SetCanEverAffectNavigation(false);
    }
    OccupiedPennants->SetVisibility(false);
    ReclaimedPennants->SetVisibility(false);
}

void AReflectionsStrongholdGate::BeginPlay()
{
    Super::BeginPlay();
    // A streamed startup actor can retain an old enum. A spatial visual actor needs the
    // current persistent state before applying either pennant variant on stream-in.
    OnRep_Pennants();
    if (GetNetMode() == NM_Client || !HasAuthority()) return;
    if (!ensureMsgf(!ReclaimUnlock.IsNone(), TEXT("Stronghold gate %s needs its site unlock"), *GetName())) return;

    if (UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this))
    {
        BoundQuests = Quests;
        Quests->OnUnlock.AddUniqueDynamic(this, &AReflectionsStrongholdGate::HandleUnlock);
        Quests->OnQuestsChanged.AddUniqueDynamic(this, &AReflectionsStrongholdGate::RefreshFromQuests);
        // Prototype only: BeginPlay may precede checkpoint application. Require a successful
        // matching quest snapshot or an explicit fresh campaign baseline before publishing.
        RefreshFromQuests();
    }
}

void AReflectionsStrongholdGate::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (UReflectionsQuestSubsystem* Quests = BoundQuests.Get())
    {
        Quests->OnUnlock.RemoveDynamic(this, &AReflectionsStrongholdGate::HandleUnlock);
        Quests->OnQuestsChanged.RemoveDynamic(this, &AReflectionsStrongholdGate::RefreshFromQuests);
    }
    BoundQuests.Reset();
    Super::EndPlay(EndPlayReason);
}

void AReflectionsStrongholdGate::HandleUnlock(FName Unlock, FName)
{
    if (Unlock == ReclaimUnlock) RefreshFromQuests();
}

void AReflectionsStrongholdGate::RefreshFromQuests()
{
    if (GetNetMode() == NM_Client || !HasAuthority()) return;
    const UReflectionsQuestSubsystem* Quests = BoundQuests.Get();
    if (!Quests) return;

    // A mismatched quest snapshot can leave old unlocks in memory. A generic quest-change
    // or GameFlow-restored broadcast alone cannot establish campaign readiness.
    const EReflectionsStrongholdPennants Desired = Quests->HasUnlock(ReclaimUnlock)
        ? EReflectionsStrongholdPennants::Reclaimed
        : EReflectionsStrongholdPennants::Occupied;
    if (Pennants == Desired) return;

    Pennants = Desired;
    OnRep_Pennants();
    ForceNetUpdate();
}

void AReflectionsStrongholdGate::OnRep_Pennants()
{
    OccupiedPennants->SetVisibility(Pennants == EReflectionsStrongholdPennants::Occupied);
    ReclaimedPennants->SetVisibility(Pennants == EReflectionsStrongholdPennants::Reclaimed);
}

void AReflectionsStrongholdGate::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(AReflectionsStrongholdGate, Pennants);
}
