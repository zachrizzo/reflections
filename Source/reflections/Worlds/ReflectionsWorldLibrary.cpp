#include "Worlds/ReflectionsWorldLibrary.h"

#include "Engine/LevelStreamingAlwaysLoaded.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Worlds/ReflectionsWorldJumpComponent.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"
#include "Worlds/ReflectionsWorldPickups.h"

void UReflectionsWorldLibrary::AwardCoin(const UObject* WorldContext, EReflectionsWorld World, int32 Count)
{
    if (UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(WorldContext))
    {
        Progress->AwardCoin(World, Count);
    }
}

AReflectionsCoinPickup* UReflectionsWorldLibrary::DropCoin(const UObject* WorldContext, EReflectionsWorld World, FVector Location)
{
    UWorld* GameWorld = WorldContext ? WorldContext->GetWorld() : nullptr;
    if (!GameWorld)
    {
        return nullptr;
    }
    const FTransform Transform(FRotator::ZeroRotator, Location + FVector(0.0f, 0.0f, 40.0f));
    AReflectionsCoinPickup* Coin = GameWorld->SpawnActorDeferred<AReflectionsCoinPickup>(
        AReflectionsCoinPickup::StaticClass(), Transform, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (Coin)
    {
        Coin->CoinWorld = World;
        Coin->FinishSpawning(Transform);
    }
    return Coin;
}

EReflectionsWorld UReflectionsWorldLibrary::GetWorldAtLocation(const UObject* WorldContext, FVector Location)
{
    const UReflectionsWorldJumpWorldSubsystem* Worlds = UReflectionsWorldJumpWorldSubsystem::Get(WorldContext);
    return Worlds ? Worlds->GetWorldAtLocation(Location) : EReflectionsWorld::Gray;
}

EReflectionsWorld UReflectionsWorldLibrary::GetCurrentWorld(const UObject* WorldContext)
{
    const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(WorldContext);
    return Progress ? Progress->GetCurrentWorld() : EReflectionsWorld::Gray;
}

bool UReflectionsWorldLibrary::RequestWorldJump(const UObject* WorldContext, EReflectionsJumpDirection Direction)
{
    const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    const APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
    APawn* Pawn = PC ? PC->GetPawn() : nullptr;
    UReflectionsWorldJumpComponent* Jump = Pawn ? Pawn->FindComponentByClass<UReflectionsWorldJumpComponent>() : nullptr;
    return Jump && Jump->RequestJump(Direction);
}

int32 UReflectionsWorldLibrary::GetCoins(const UObject* WorldContext, EReflectionsWorld World)
{
    const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(WorldContext);
    return Progress ? Progress->GetCoins(World) : 0;
}

int32 UReflectionsWorldLibrary::GetPageCount(const UObject* WorldContext)
{
    const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(WorldContext);
    return Progress ? Progress->GetPageCount() : 0;
}

AActor* UReflectionsWorldLibrary::SpawnActorIntoWorld(UWorld* World, TSubclassOf<AActor> ActorClass, FTransform Transform)
{
    if (!World || !*ActorClass || !World->PersistentLevel)
    {
        return nullptr;
    }
    FActorSpawnParameters Params;
    Params.OverrideLevel = World->PersistentLevel;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Params.ObjectFlags = RF_Transactional;
    AActor* Actor = World->SpawnActor<AActor>(*ActorClass, Transform, Params);
    if (Actor)
    {
        World->MarkPackageDirty();
    }
    return Actor;
}

ULevelStreaming* UReflectionsWorldLibrary::AddOffsetSublevel(UWorld* World, TSoftObjectPtr<UWorld> Level, FTransform LevelTransform)
{
    if (!World || Level.IsNull())
    {
        return nullptr;
    }
    ULevelStreamingAlwaysLoaded* Streaming = NewObject<ULevelStreamingAlwaysLoaded>(World, NAME_None, RF_Transactional);
    Streaming->SetWorldAsset(Level);
    Streaming->LevelTransform = LevelTransform;
    World->AddStreamingLevel(Streaming);
    World->MarkPackageDirty();
    return Streaming;
}

// ---- Native ------------------------------------------------------------------------------------------------

UReflectionsWorldNativeComponent::UReflectionsWorldNativeComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void UReflectionsWorldNativeComponent::BeginPlay()
{
    Super::BeginPlay();
    if (bHomeIsSpawnWorld)
    {
        HomeWorld = UReflectionsWorldLibrary::GetWorldAtLocation(this, GetOwner()->GetActorLocation());
    }
    if (UReflectionsHealthComponent* Health = GetOwner()->FindComponentByClass<UReflectionsHealthComponent>())
    {
        Health->OnDeath.AddUniqueDynamic(this, &UReflectionsWorldNativeComponent::HandleDeath);
    }
}

void UReflectionsWorldNativeComponent::HandleDeath(AActor* Source)
{
    NotifyDefeated();
}

void UReflectionsWorldNativeComponent::NotifyDefeated()
{
    if (bRewarded || !GetOwner())
    {
        return;
    }
    bRewarded = true;
    if (bDropPickup)
    {
        UReflectionsWorldLibrary::DropCoin(this, HomeWorld, GetOwner()->GetActorLocation());
    }
    else
    {
        UReflectionsWorldLibrary::AwardCoin(this, HomeWorld, 1);
    }
}
