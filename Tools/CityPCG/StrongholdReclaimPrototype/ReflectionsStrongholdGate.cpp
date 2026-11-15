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
    OnRep_Pennants();
    if (GetNetMode() == NM_Client || !HasAuthority()) return;
    if (!ensureMsgf(!ReclaimUnlock.IsNone(), TEXT("Stronghold gate %s needs its site unlock"), *GetName())) return;

    if (UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this))
    {
        BoundQuests = Quests;
        Quests->OnUnlock.AddUniqueDynamic(this, &AReflectionsStrongholdGate::HandleUnlock);
        Quests->OnQuestsChanged.AddUniqueDynamic(this, &AReflectionsStrongholdGate::RefreshFromQuests);
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
