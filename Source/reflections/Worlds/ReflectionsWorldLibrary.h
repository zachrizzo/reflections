#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Worlds/ReflectionsWorldTypes.h"
#include "ReflectionsWorldLibrary.generated.h"

class AReflectionsCoinPickup;
class AVolume;
class ULevelStreaming;

/**
 * One-line calls for gameplay code (enemies, NPCs, quests). Include "Worlds/ReflectionsWorldLibrary.h".
 *
 *   UReflectionsWorldLibrary::AwardCoin(this, EReflectionsWorld::Red);              // straight into the purse
 *   UReflectionsWorldLibrary::DropCoin(this, EReflectionsWorld::White, Location);    // a coin to walk over
 *   UReflectionsWorldLibrary::GetWorldAtLocation(this, GetActorLocation());          // which London is this?
 */
UCLASS()
class REFLECTIONS_API UReflectionsWorldLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "World Jump", meta = (WorldContext = "WorldContext"))
    static void AwardCoin(const UObject* WorldContext, EReflectionsWorld World, int32 Count = 1);

    /** Spawns a coin pickup of a London at Location (pops it slightly off the ground). */
    UFUNCTION(BlueprintCallable, Category = "World Jump", meta = (WorldContext = "WorldContext"))
    static AReflectionsCoinPickup* DropCoin(const UObject* WorldContext, EReflectionsWorld World, FVector Location);

    UFUNCTION(BlueprintPure, Category = "World Jump", meta = (WorldContext = "WorldContext"))
    static EReflectionsWorld GetWorldAtLocation(const UObject* WorldContext, FVector Location);

    /** The London the player is in. */
    UFUNCTION(BlueprintPure, Category = "World Jump", meta = (WorldContext = "WorldContext"))
    static EReflectionsWorld GetCurrentWorld(const UObject* WorldContext);

    /** Jump the local player one London up or down (same checks and cost as the button). */
    UFUNCTION(BlueprintCallable, Category = "World Jump", meta = (WorldContext = "WorldContext"))
    static bool RequestWorldJump(const UObject* WorldContext, EReflectionsJumpDirection Direction);

    UFUNCTION(BlueprintPure, Category = "World Jump", meta = (WorldContext = "WorldContext"))
    static int32 GetCoins(const UObject* WorldContext, EReflectionsWorld World);

    UFUNCTION(BlueprintPure, Category = "World Jump", meta = (WorldContext = "WorldContext"))
    static int32 GetPageCount(const UObject* WorldContext);

    /** Editor scripting: spawn an actor into a level asset's world that is not the open level (builds test maps). */
    UFUNCTION(BlueprintCallable, Category = "World Jump|Editor")
    static AActor* SpawnActorIntoWorld(UWorld* World, TSubclassOf<AActor> ActorClass, FTransform Transform);

    /** Editor scripting: add an always-loaded sublevel with a transform (how three maps become offset copies). */
    UFUNCTION(BlueprintCallable, Category = "World Jump|Editor")
    static ULevelStreaming* AddOffsetSublevel(UWorld* World, TSoftObjectPtr<UWorld> Level, FTransform LevelTransform);

    /** Editor scripting: give a spawned volume (nav mesh bounds and the like) a box shape, half-size in cm. */
    UFUNCTION(BlueprintCallable, Category = "World Jump|Editor")
    static bool SetVolumeBox(AVolume* Volume, FVector HalfExtent);
};

/**
 * Put this on an NPC or enemy to make it a native of a London: when its health component reports death (or
 * gameplay code calls NotifyDefeated), it drops one coin of its home London, wherever it died. A native that
 * leaked through a rift still drops its home coin.
 */
UCLASS(ClassGroup = (WorldJump), BlueprintType, meta = (BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsWorldNativeComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsWorldNativeComponent();

    /** Use the London the actor spawned in as its home (ignores HomeWorld). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World Native")
    bool bHomeIsSpawnWorld = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World Native", meta = (EditCondition = "!bHomeIsSpawnWorld"))
    EReflectionsWorld HomeWorld = EReflectionsWorld::Red;

    /** Drop a pickup (true) or put the coin straight in the purse (false). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "World Native")
    bool bDropPickup = true;

    UFUNCTION(BlueprintCallable, Category = "World Native")
    void NotifyDefeated();

protected:
    virtual void BeginPlay() override;

private:
    UFUNCTION() void HandleDeath(AActor* Source);
    bool bRewarded = false;
};
