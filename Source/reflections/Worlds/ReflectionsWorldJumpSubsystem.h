#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Subsystems/WorldSubsystem.h"
#include "Worlds/ReflectionsWorldTypes.h"
#include "ReflectionsWorldJumpSubsystem.generated.h"

class AReflectionsWorldAnchor;
class APawn;
class APlayerController;
class UReflectionsWorldJumpComponent;
class UReflectionsWorldJumpConfig;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsCoinsChanged, EReflectionsWorld, World, int32, Count);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsPagesChanged, int32, Pages, int32, PagesForBook);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FReflectionsBookComplete);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FReflectionsProgressRestored);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FReflectionsKeyAdded, FName, KeyId);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsWorldChanged, EReflectionsWorld, From, EReflectionsWorld, To);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FReflectionsWorldMessage, const FText&, Message);

/** Where the hero should appear after a SeparateMaps jump opens the next map. */
USTRUCT()
struct FReflectionsPendingArrival
{
    GENERATED_BODY()

    UPROPERTY() bool bValid = false;
    UPROPERTY() EReflectionsWorld World = EReflectionsWorld::Gray;
    UPROPERTY() FVector Location = FVector::ZeroVector;
    UPROPERTY() FRotator Rotation = FRotator::ZeroRotator;
    UPROPERTY() FRotator ControlRotation = FRotator::ZeroRotator;
    UPROPERTY() FVector Velocity = FVector::ZeroVector;
};

/**
 * The hero's world-jump progress for the whole play session (it survives map travel): which London the hero is
 * in, coins per London, book pages and keys. Enemy and NPC code awards coins here (or through
 * UReflectionsWorldLibrary::AwardCoin).
 */
UCLASS()
class REFLECTIONS_API UReflectionsWorldJumpSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsWorldJumpSubsystem* Get(const UObject* WorldContext);

    virtual void Initialize(FSubsystemCollectionBase& Collection) override;

    // ---- Current world -----------------------------------------------------------------------------------

    /** The London the hero is in. Until something sets it (one-London maps never jump), the config's DefaultWorld. */
    UFUNCTION(BlueprintPure, Category = "World Jump")
    EReflectionsWorld GetCurrentWorld() const;

    /** Records which London the hero is in. Broadcasts OnWorldChanged when it changes and bBroadcast is set. */
    UFUNCTION(BlueprintCallable, Category = "World Jump")
    void SetCurrentWorld(EReflectionsWorld World, bool bBroadcast = true);

    UPROPERTY(BlueprintAssignable, Category = "World Jump")
    FReflectionsWorldChanged OnWorldChanged;

    // ---- Coins -------------------------------------------------------------------------------------------

    /** Give the hero coins of a London (call when the hero beats one of its natives). */
    UFUNCTION(BlueprintCallable, Category = "World Jump|Coins")
    void AwardCoin(EReflectionsWorld World, int32 Count = 1);

    /** Spend coins; false and nothing spent if the hero has too few. */
    UFUNCTION(BlueprintCallable, Category = "World Jump|Coins")
    bool SpendCoin(EReflectionsWorld World, int32 Count = 1);

    UFUNCTION(BlueprintPure, Category = "World Jump|Coins")
    int32 GetCoins(EReflectionsWorld World) const;

    UPROPERTY(BlueprintAssignable, Category = "World Jump|Coins")
    FReflectionsCoinsChanged OnCoinsChanged;

    // ---- Book pages and keys -----------------------------------------------------------------------------

    /** Adds a page; false if the hero already had it. Fires OnBookComplete when the last page is found. */
    UFUNCTION(BlueprintCallable, Category = "World Jump|Book")
    bool AddPage(FName PageId);

    UFUNCTION(BlueprintPure, Category = "World Jump|Book")
    bool HasPage(FName PageId) const { return Pages.Contains(PageId); }

    /** Every page found so far (for checkpoints). */
    UFUNCTION(BlueprintPure, Category = "World Jump|Book")
    TArray<FName> GetPages() const { return Pages.Array(); }

    UFUNCTION(BlueprintPure, Category = "World Jump|Book")
    int32 GetPageCount() const { return Pages.Num(); }

    UFUNCTION(BlueprintPure, Category = "World Jump|Book")
    int32 GetPagesForBook() const;

    UFUNCTION(BlueprintPure, Category = "World Jump|Book")
    bool IsBookComplete() const { return bBookComplete; }

    UPROPERTY(BlueprintAssignable, Category = "World Jump|Book")
    FReflectionsPagesChanged OnPagesChanged;

    /** All pages found: the spell that stops the villain is ready. */
    UPROPERTY(BlueprintAssignable, Category = "World Jump|Book")
    FReflectionsBookComplete OnBookComplete;

    UFUNCTION(BlueprintCallable, Category = "World Jump|Keys")
    void AddKey(FName KeyId);

    UFUNCTION(BlueprintPure, Category = "World Jump|Keys")
    bool HasKey(FName KeyId) const { return Keys.Contains(KeyId); }

    UFUNCTION(BlueprintPure, Category = "World Jump|Keys")
    TArray<FName> GetKeys() const { return Keys.Array(); }

    UPROPERTY(BlueprintAssignable, Category = "World Jump|Keys")
    FReflectionsKeyAdded OnKeyAdded;

    // ---- Messages ----------------------------------------------------------------------------------------

    /** Short line for the world-jump HUD (refusals, pickups, locked doors). */
    UFUNCTION(BlueprintCallable, Category = "World Jump")
    void ShowWorldMessage(const FText& Message);

    UPROPERTY(BlueprintAssignable, Category = "World Jump")
    FReflectionsWorldMessage OnMessage;

    /** Clears coins, pages, keys and the current world (a new run). */
    UFUNCTION(BlueprintCallable, Category = "World Jump")
    void ResetProgress();

    /**
     * Checkpoint load: replaces coins, pages and keys in one go without firing OnCoinsChanged, OnPagesChanged,
     * OnBookComplete or OnKeyAdded (so no pickup sounds or "book is whole" banner). Book-complete state is
     * recomputed silently. Fires OnProgressRestored once so HUDs can refresh.
     */
    UFUNCTION(BlueprintCallable, Category = "World Jump")
    void RestoreProgress(const TMap<EReflectionsWorld, int32>& InCoins, const TArray<FName>& InPages, const TArray<FName>& InKeys);

    UPROPERTY(BlueprintAssignable, Category = "World Jump")
    FReflectionsProgressRestored OnProgressRestored;

    /** Coins held per London (for checkpoints). */
    UFUNCTION(BlueprintPure, Category = "World Jump|Coins")
    TMap<EReflectionsWorld, int32> GetAllCoins() const { return Coins; }

    FReflectionsPendingArrival PendingArrival;

private:
    UPROPERTY() TMap<EReflectionsWorld, int32> Coins;
    UPROPERTY() TSet<FName> Pages;
    UPROPERTY() TSet<FName> Keys;
    EReflectionsWorld CurrentWorld = EReflectionsWorld::Gray;
    bool bHasCurrentWorld = false;
    bool bBookComplete = false;
};

/**
 * Per-map side of the world jump: finds the anchors, says which London a location is in, and gives the local
 * player's pawn a UReflectionsWorldJumpComponent. It stays dormant in maps without anchors (so other people's
 * test maps are untouched) unless the config's SeparateMaps layout lists the map.
 */
UCLASS()
class REFLECTIONS_API UReflectionsWorldJumpWorldSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsWorldJumpWorldSubsystem* Get(const UObject* WorldContext);

    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;

protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

public:

    /** True when this map takes part in world jumping. */
    UFUNCTION(BlueprintPure, Category = "World Jump")
    bool IsWorldJumpActive() const;

    const UReflectionsWorldJumpConfig* GetConfig() const;

    /** The anchor of a London in this map, or null. */
    AReflectionsWorldAnchor* FindAnchor(EReflectionsWorld World) const;

    /** Which London a location belongs to: the anchor box containing it, else the nearest anchor. */
    UFUNCTION(BlueprintPure, Category = "World Jump")
    EReflectionsWorld GetWorldAtLocation(const FVector& Location) const;

    /** The same spot in another London (OffsetCopies). False if either anchor is missing. */
    bool TranslateBetweenWorlds(const FVector& Location, EReflectionsWorld From, EReflectionsWorld To, FVector& OutLocation) const;

    /** For SeparateMaps: the London this map is, if listed. */
    bool GetWorldOfThisMap(EReflectionsWorld& Out) const;

    /** Adds the jump component to a pawn if it has none. */
    UReflectionsWorldJumpComponent* EnsureComponent(APawn* Pawn);

private:
    void TryAttachToLocalPlayer();
    UFUNCTION() void HandlePossessedPawnChanged(APawn* OldPawn, APawn* NewPawn);

    FTimerHandle AttachTimer;
    TWeakObjectPtr<APlayerController> BoundController;
    int32 AttachAttempts = 0;
};
