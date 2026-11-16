#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Lives/ReflectionsLivesTypes.h"
#include "GameFlow/ReflectionsGameFlowTypes.h"
#include "ReflectionsLivesMemory.generated.h"

/** Lives' save data, embedded in game-flow checkpoints. */
UCLASS()
class REFLECTIONS_API UReflectionsLivesSave : public USaveGame
{
    GENERATED_BODY()

public:
    static constexpr int32 CurrentVersion = 1;
    /** 0 in files written before versioning (a default-valued property is not written). */
    UPROPERTY() int32 Version = 0;
    UPROPERTY() double GameHours = 0.0;
    UPROPERTY() TArray<FReflectionsPersonState> People;
    UPROPERTY() TArray<FName> StoryFlags;
};

/**
 * What every person remembers (of the player and of each other), and the game clock, across map reloads.
 *
 * It lives on the game instance and is embedded whenever game flow saves a checkpoint.
 * When a map starts and game flow has a checkpoint, the
 * people are put back to what they knew at that checkpoint; a new game (no checkpoint) forgets everything.
 */
UCLASS()
class REFLECTIONS_API UReflectionsLivesMemory : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsLivesMemory* Get(const UObject* WorldContext);

    virtual void Initialize(FSubsystemCollectionBase& Collection) override;

    /** The state of a person, created empty on first use. */
    FReflectionsPersonState& FindOrAdd(FName PersonId);
    const FReflectionsPersonState* Find(FName PersonId) const { return People.Find(PersonId); }

    /** Game hours since day 0 (TimeOfDay = fmod(GameHours, 24)); negative until a clock has started. */
    double GameHours = -1.0;
    /** Bumped by ForgetEverything (New Game): a world that started on an older generation leaves memory alone. */
    uint32 Generation = 0;

    /** Called at the start of each map: roll back to the checkpoint's snapshot, or forget everything on a new game. */
    void SyncWithCheckpoint(bool bHasCheckpoint);

    UFUNCTION(BlueprintCallable, Category="Lives")
    bool SaveSnapshot();
    UFUNCTION(BlueprintCallable, Category="Lives")
    bool LoadSnapshot();
    UFUNCTION(BlueprintCallable, Category="Lives")
    void ForgetEverything();

    const TMap<FName, FReflectionsPersonState>& GetAll() const { return People; }
    void Forget(FName PersonId) { People.Remove(PersonId); }

    /** Story flags (Hal_Home, Drifters_Stay...), set by the quest system; saved with the checkpoint. */
    TSet<FName> StoryFlags;

    static FString SlotName() { return TEXT("Reflections_Lives"); }

private:
    UReflectionsLivesSave* MakeSnapshot() const;
    bool ApplySnapshot(const UReflectionsLivesSave* Save);
    UFUNCTION() void HandleCheckpointSaved(const FReflectionsCheckpoint& Checkpoint);
    TMap<FName, FReflectionsPersonState> People;
    bool bBound = false;

public:
    /** Binds to game flow's checkpoint event (called by the world subsystem; safe to repeat). */
    void BindToGameFlow();
};
