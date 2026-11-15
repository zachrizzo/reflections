#include "Worlds/ReflectionsWorldJumpSubsystem.h"

#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "TimerManager.h"
#include "UObject/Package.h"
#include "Worlds/ReflectionsWorldAnchor.h"
#include "Worlds/ReflectionsWorldJumpComponent.h"
#include "Worlds/ReflectionsWorldJumpConfig.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsWorlds, Log, All);

#define LOCTEXT_NAMESPACE "ReflectionsWorlds"

// ==== Game instance: progress =============================================================================

UReflectionsWorldJumpSubsystem* UReflectionsWorldJumpSubsystem::Get(const UObject* WorldContext)
{
    const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
    return GameInstance ? GameInstance->GetSubsystem<UReflectionsWorldJumpSubsystem>() : nullptr;
}

void UReflectionsWorldJumpSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    ResetProgress();
}

void UReflectionsWorldJumpSubsystem::ResetProgress()
{
    Coins.Reset();
    Pages.Reset();
    Keys.Reset();
    bBookComplete = false;
    bHasCurrentWorld = false;
    PendingArrival = FReflectionsPendingArrival();
}

void UReflectionsWorldJumpSubsystem::RestoreProgress(const TMap<EReflectionsWorld, int32>& InCoins, const TArray<FName>& InPages,
    const TArray<FName>& InKeys)
{
    Coins = InCoins;
    Pages.Reset();
    for (const FName& Page : InPages)
    {
        if (!Page.IsNone())
        {
            Pages.Add(Page);
        }
    }
    Keys.Reset();
    for (const FName& Key : InKeys)
    {
        if (!Key.IsNone())
        {
            Keys.Add(Key);
        }
    }
    bBookComplete = Pages.Num() >= GetPagesForBook();
    OnProgressRestored.Broadcast();
}

void UReflectionsWorldJumpSubsystem::SetCurrentWorld(EReflectionsWorld World, bool bBroadcast)
{
    const EReflectionsWorld Previous = CurrentWorld;
    const bool bChanged = !bHasCurrentWorld || Previous != World;
    CurrentWorld = World;
    bHasCurrentWorld = true;
    if (bChanged && bBroadcast)
    {
        OnWorldChanged.Broadcast(Previous, World);
    }
}

void UReflectionsWorldJumpSubsystem::AwardCoin(EReflectionsWorld World, int32 Count)
{
    if (Count <= 0)
    {
        return;
    }
    int32& Held = Coins.FindOrAdd(World);
    Held += Count;
    UE_LOG(LogReflectionsWorlds, Log, TEXT("Awarded %d %s coin(s); now %d."), Count,
        *StaticEnum<EReflectionsWorld>()->GetNameStringByValue(static_cast<int64>(World)), Held);
    OnCoinsChanged.Broadcast(World, Held);
}

bool UReflectionsWorldJumpSubsystem::SpendCoin(EReflectionsWorld World, int32 Count)
{
    if (Count <= 0)
    {
        return true;
    }
    int32* Held = Coins.Find(World);
    if (!Held || *Held < Count)
    {
        return false;
    }
    *Held -= Count;
    OnCoinsChanged.Broadcast(World, *Held);
    return true;
}

int32 UReflectionsWorldJumpSubsystem::GetCoins(EReflectionsWorld World) const
{
    const int32* Held = Coins.Find(World);
    return Held ? *Held : 0;
}

int32 UReflectionsWorldJumpSubsystem::GetPagesForBook() const
{
    const UReflectionsWorldJumpConfig* Config = UReflectionsWorldJumpConfig::Get(this);
    return Config ? Config->PagesForBook : 3;
}

bool UReflectionsWorldJumpSubsystem::AddPage(FName PageId)
{
    if (PageId.IsNone() || Pages.Contains(PageId))
    {
        return false;
    }
    Pages.Add(PageId);
    const int32 Needed = GetPagesForBook();
    OnPagesChanged.Broadcast(Pages.Num(), Needed);
    if (!bBookComplete && Pages.Num() >= Needed)
    {
        bBookComplete = true;
        UE_LOG(LogReflectionsWorlds, Log, TEXT("Book complete (%d pages)."), Pages.Num());
        OnBookComplete.Broadcast();
    }
    return true;
}

void UReflectionsWorldJumpSubsystem::AddKey(FName KeyId)
{
    if (KeyId.IsNone() || Keys.Contains(KeyId))
    {
        return;
    }
    Keys.Add(KeyId);
    OnKeyAdded.Broadcast(KeyId);
}

void UReflectionsWorldJumpSubsystem::ShowWorldMessage(const FText& Message)
{
    if (!Message.IsEmpty())
    {
        OnMessage.Broadcast(Message);
    }
}

// ==== World: anchors and auto-attach =======================================================================

UReflectionsWorldJumpWorldSubsystem* UReflectionsWorldJumpWorldSubsystem::Get(const UObject* WorldContext)
{
    const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    return World ? World->GetSubsystem<UReflectionsWorldJumpWorldSubsystem>() : nullptr;
}

bool UReflectionsWorldJumpWorldSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UReflectionsWorldJumpWorldSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    // Anchors begin play after this, and the player may not have a pawn yet, so look again shortly.
    InWorld.GetTimerManager().SetTimer(AttachTimer, FTimerDelegate::CreateUObject(this,
        &UReflectionsWorldJumpWorldSubsystem::TryAttachToLocalPlayer), 0.2f, true, 0.05f);
}

void UReflectionsWorldJumpWorldSubsystem::Deinitialize()
{
    if (APlayerController* PC = BoundController.Get())
    {
        PC->OnPossessedPawnChanged.RemoveDynamic(this, &UReflectionsWorldJumpWorldSubsystem::HandlePossessedPawnChanged);
    }
    Super::Deinitialize();
}

const UReflectionsWorldJumpConfig* UReflectionsWorldJumpWorldSubsystem::GetConfig() const
{
    return UReflectionsWorldJumpConfig::Get(GetWorld());
}

bool UReflectionsWorldJumpWorldSubsystem::IsWorldJumpActive() const
{
    const UWorld* World = GetWorld();
    if (!World)
    {
        return false;
    }
    if (TActorIterator<AReflectionsWorldAnchor>(const_cast<UWorld*>(World)))
    {
        return true;
    }
    EReflectionsWorld Unused;
    return GetWorldOfThisMap(Unused);
}

AReflectionsWorldAnchor* UReflectionsWorldJumpWorldSubsystem::FindAnchor(EReflectionsWorld World) const
{
    for (TActorIterator<AReflectionsWorldAnchor> It(GetWorld()); It; ++It)
    {
        if (It->World == World)
        {
            return *It;
        }
    }
    return nullptr;
}

EReflectionsWorld UReflectionsWorldJumpWorldSubsystem::GetWorldAtLocation(const FVector& Location) const
{
    const UReflectionsWorldJumpConfig* Config = GetConfig();
    AReflectionsWorldAnchor* Nearest = nullptr;
    double NearestDistance = TNumericLimits<double>::Max();
    for (TActorIterator<AReflectionsWorldAnchor> It(GetWorld()); It; ++It)
    {
        if (It->ContainsLocation(Location))
        {
            return It->World;
        }
        const double Distance = FVector::DistSquared(It->GetActorLocation(), Location);
        if (Distance < NearestDistance)
        {
            NearestDistance = Distance;
            Nearest = *It;
        }
    }
    if (Nearest)
    {
        return Nearest->World;
    }
    EReflectionsWorld MapWorld;
    if (GetWorldOfThisMap(MapWorld))
    {
        return MapWorld;
    }
    return Config ? Config->DefaultWorld : EReflectionsWorld::Gray;
}

bool UReflectionsWorldJumpWorldSubsystem::TranslateBetweenWorlds(const FVector& Location, EReflectionsWorld From,
    EReflectionsWorld To, FVector& OutLocation) const
{
    const AReflectionsWorldAnchor* FromAnchor = FindAnchor(From);
    const AReflectionsWorldAnchor* ToAnchor = FindAnchor(To);
    if (!FromAnchor || !ToAnchor)
    {
        return false;
    }
    // Copies are pure translations of each other, so only the anchor positions matter.
    OutLocation = Location - FromAnchor->GetActorLocation() + ToAnchor->GetActorLocation();
    return true;
}

bool UReflectionsWorldJumpWorldSubsystem::GetWorldOfThisMap(EReflectionsWorld& Out) const
{
    const UReflectionsWorldJumpConfig* Config = GetConfig();
    const UWorld* World = GetWorld();
    if (!Config || !World || Config->Layout != EReflectionsWorldLayout::SeparateMaps)
    {
        return false;
    }
    FString MapName = World->GetOutermost()->GetName();
    MapName = UWorld::RemovePIEPrefix(MapName);
    for (const FReflectionsWorldInfo& Info : Config->Worlds)
    {
        if (!Info.Map.IsNull() && Info.Map.ToSoftObjectPath().GetLongPackageName() == MapName)
        {
            Out = Info.World;
            return true;
        }
    }
    return false;
}

UReflectionsWorldJumpComponent* UReflectionsWorldJumpWorldSubsystem::EnsureComponent(APawn* Pawn)
{
    if (!Pawn)
    {
        return nullptr;
    }
    if (UReflectionsWorldJumpComponent* Existing = Pawn->FindComponentByClass<UReflectionsWorldJumpComponent>())
    {
        return Existing;
    }
    UReflectionsWorldJumpComponent* Component = NewObject<UReflectionsWorldJumpComponent>(Pawn, TEXT("WorldJump"));
    Component->RegisterComponent();
    Pawn->AddInstanceComponent(Component);
    UE_LOG(LogReflectionsWorlds, Log, TEXT("World jump attached to %s."), *Pawn->GetName());
    return Component;
}

void UReflectionsWorldJumpWorldSubsystem::TryAttachToLocalPlayer()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }
    if (!IsWorldJumpActive())
    {
        // Not a world-jump map. Streaming sublevels can bring anchors in late, so give them a few seconds.
        if (++AttachAttempts > 50)
        {
            World->GetTimerManager().ClearTimer(AttachTimer);
        }
        return;
    }
    APlayerController* PC = World->GetFirstPlayerController();
    if (!PC || !PC->IsLocalController())
    {
        return;
    }
    if (BoundController.Get() != PC)
    {
        PC->OnPossessedPawnChanged.AddUniqueDynamic(this, &UReflectionsWorldJumpWorldSubsystem::HandlePossessedPawnChanged);
        BoundController = PC;
    }
    if (APawn* Pawn = PC->GetPawn())
    {
        EnsureComponent(Pawn);
        World->GetTimerManager().ClearTimer(AttachTimer);
    }
}

void UReflectionsWorldJumpWorldSubsystem::HandlePossessedPawnChanged(APawn* OldPawn, APawn* NewPawn)
{
    if (OldPawn)
    {
        if (UReflectionsWorldJumpComponent* Old = OldPawn->FindComponentByClass<UReflectionsWorldJumpComponent>())
        {
            Old->Shutdown();
        }
    }
    if (NewPawn && IsWorldJumpActive())
    {
        UReflectionsWorldJumpComponent* Component = EnsureComponent(NewPawn);
        if (Component)
        {
            Component->Startup();
        }
    }
}

#undef LOCTEXT_NAMESPACE
