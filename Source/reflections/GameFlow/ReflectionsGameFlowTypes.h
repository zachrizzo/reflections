#pragma once

#include "CoreMinimal.h"
#include "Worlds/ReflectionsWorldTypes.h"
#include "ReflectionsGameFlowTypes.generated.h"

/** Which full-screen menu the game flow is showing. None while playing. */
UENUM(BlueprintType)
enum class EReflectionsFlowScreen : uint8
{
    None,
    Title,
    Pause,
    Controls,
    Credits,
    Confirm,
    Lose,
    Victory,
    /** Graphics settings (title and pause). */
    Settings,
    /** "Keep these settings?" with a 15 s revert. */
    SettingsConfirm,
    /** Pause > Save Game: the three manual slots. */
    SaveGame,
    /** Title / pause / death > Load Game: quick save, autosave and the three manual slots. */
    LoadGame,
    /** The hero fell: respawn at the last checkpoint or save, or load. */
    Death,
};

/** Save slots. The autosave is the checkpoint slot (world jumps, pages); every manual or quick save is also a checkpoint. */
namespace ReflectionsSaveSlots
{
    constexpr int32 Autosave = 0;
    constexpr int32 Quick = 1;
    constexpr int32 FirstManual = 2;
    constexpr int32 ManualCount = 3;
    constexpr int32 Count = FirstManual + ManualCount;
}

/** One-time tutorial prompts. */
UENUM(BlueprintType)
enum class EReflectionsTip : uint8
{
    Aim,
    Cast,
    Coin,
    CrossWorlds,
    Crafting,
    Count UMETA(Hidden),
};

/** One system's own state, stored with a checkpoint (UReflectionsGameFlowSubsystem::SetSaveData / GetSaveData). */
USTRUCT(BlueprintType)
struct FReflectionsSaveBlob
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") FName System;
    UPROPERTY() TArray<uint8> Data;
};

/** Everything needed to put the hero back where the last auto-save happened. */
USTRUCT(BlueprintType)
struct FReflectionsCheckpoint
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") bool bValid = false;
    /** Long package name of the map, without any PIE prefix. */
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") FString MapPath;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") EReflectionsWorld World = EReflectionsWorld::Red;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") bool bWorldJumpActive = false;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") FVector Location = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") FRotator Rotation = FRotator::ZeroRotator;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") FRotator ControlRotation = FRotator::ZeroRotator;
    /** Coins per London, indexed by EReflectionsWorld (Gray, Red, White). */
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") TArray<int32> Coins;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") TArray<FName> Pages;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") TArray<FName> Keys;
    /** Names of level-placed pickups already collected (removed again on restore). */
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") TArray<FString> CollectedPickups;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") FString Reason;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") FDateTime SavedAt;
    /**
     * When this state was last saved or loaded: "newest" sorts on it. A load stamps it (SavedAt stays: quests match
     * on SavedAt), so saves from a run the player loaded away from no longer count as the newest.
     */
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") FDateTime UsedAt;

    /** Hero health and mana when saved (-1: unknown). Restored when a save slot is loaded, not on Try again. */
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") float Health = -1.0f;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") float Mana = -1.0f;
    /** The hero's reputation (UReflectionsReputationSubsystem resets with the map; put back on every restore). */
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") bool bHasReputation = false;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") float Reputation = 0.0f;
    /** The Tarnish meter when saved (shown in the slot list; the villain's restore re-reports the hosts). */
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") int32 InfectionCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Checkpoint") int32 InfectionCap = 0;
    /** Other systems' state (SetSaveData), and copies of the save files they write with each checkpoint. */
    UPROPERTY() TArray<FReflectionsSaveBlob> SystemData;
};

/** What the Save / Load screens show for a slot. */
USTRUCT(BlueprintType)
struct FReflectionsSaveSlotInfo
{
    GENERATED_BODY()

    /** ReflectionsSaveSlots index: 0 autosave, 1 quick save, 2-4 slots 1-3. */
    UPROPERTY(BlueprintReadOnly, Category = "Save") int32 Slot = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Save") bool bUsed = false;
    UPROPERTY(BlueprintReadOnly, Category = "Save") FDateTime SavedAt;
    /** Last saved or loaded (the "newest" order). */
    UPROPERTY(BlueprintReadOnly, Category = "Save") FDateTime UsedAt;
    UPROPERTY(BlueprintReadOnly, Category = "Save") EReflectionsWorld World = EReflectionsWorld::Red;
    UPROPERTY(BlueprintReadOnly, Category = "Save") int32 Pages = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Save") int32 InfectionCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Save") FString MapPath;
    UPROPERTY(BlueprintReadOnly, Category = "Save") FString Reason;
};
