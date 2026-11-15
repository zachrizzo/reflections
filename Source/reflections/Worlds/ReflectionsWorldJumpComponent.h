#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Worlds/ReflectionsWorldTypes.h"
#include "ReflectionsWorldJumpComponent.generated.h"

class APlayerController;
class UAudioComponent;
class USoundBase;
class UEnhancedInputComponent;
class UInputAction;
class UInputMappingContext;
class UMaterialInstanceDynamic;
class UMeshComponent;
class UReflectionsWorldHudWidget;
class UReflectionsWorldJumpConfig;

/**
 * Lives on the local player's pawn (the world subsystem adds it in world-jump maps). Owns the jump input, the
 * cost (one coin + most of the hero's magic), the safe-landing search, the flash transition, the per-world coat
 * tint and the world-jump HUD.
 */
UCLASS(ClassGroup = (WorldJump), BlueprintType, meta = (BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsWorldJumpComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsWorldJumpComponent();

    /** Jump one London up or down. False (with an on-screen reason) when the jump is not possible. */
    UFUNCTION(BlueprintCallable, Category = "World Jump")
    bool RequestJump(EReflectionsJumpDirection Direction);

    /** Whether a jump would work right now, and why not. Does not spend anything. */
    UFUNCTION(BlueprintCallable, Category = "World Jump")
    bool CanJump(EReflectionsJumpDirection Direction, FText& OutReason, EReflectionsWorld& OutDestination) const;

    UFUNCTION(BlueprintPure, Category = "World Jump")
    bool IsJumping() const { return bJumping; }

    UFUNCTION(BlueprintPure, Category = "World Jump")
    EReflectionsWorld GetCurrentWorld() const;

    /** Current and maximum magic from the pawn's magic component. False when the pawn has none. */
    UFUNCTION(BlueprintPure, Category = "World Jump")
    bool GetMagic(float& Current, float& Max) const;

    /** Magic a jump costs right now (a share of the maximum). */
    UFUNCTION(BlueprintPure, Category = "World Jump")
    float GetJumpMagicCost() const;

    /** True when the magic component can actually be spent (it has a SpendMagic-style function). */
    UFUNCTION(BlueprintPure, Category = "World Jump")
    bool CanDrainMagic() const;

    /** Tints the hero's coat for a London. Runtime material instances only: no asset is changed. */
    UFUNCTION(BlueprintCallable, Category = "World Jump")
    void ApplyCoatTint(EReflectionsWorld World);

    /** Keys bound to a jump direction, for prompts ("X / L3"). */
    FText GetKeysText(EReflectionsJumpDirection Direction) const;

    /** Which coin a jump to Destination would spend, by the config's rule; false if the hero has none. */
    bool PickCoin(EReflectionsWorld Destination, EReflectionsWorld& OutCoin) const;

    const UReflectionsWorldJumpConfig* GetConfig() const { return Config; }

    /** Binds input and shows the HUD. Safe to call more than once. */
    void Startup();
    /** Unbinds input and hides the HUD (the pawn lost its player). */
    void Shutdown();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;

private:
    APlayerController* GetPlayerController() const;
    void BindInput();
    void UnbindInput();
    void BuildFallbackInput();
    void HandleJumpUp();
    void HandleJumpDown();

    bool FindSafeLanding(const FVector& Desired, FVector& OutLanding, FText& OutReason, EReflectionsWorld Destination) const;
    bool IsSpotFree(const FVector& Location) const;
    bool HasGroundBelow(const FVector& Location) const;

    void BeginTransition(EReflectionsWorld Destination, const FVector& Landing);
    void CompleteTransition();
    void ArriveAt(const FVector& Landing, EReflectionsWorld Destination);
    void FinishSeparateMapArrival();
    void Refuse(const FText& Reason);

    UObject* FindMagicSource() const;
    bool SpendMagic(float Amount);

    void GatherCoatMeshes(TArray<UMeshComponent*>& Out) const;
    void RetryCoatTint();
    void RefreshHud();
    void UpdateMusic(EReflectionsWorld World);
    void PlayUiSound(USoundBase* Sound, USoundBase* Fallback = nullptr);

    UFUNCTION() void HandleWorldChanged(EReflectionsWorld From, EReflectionsWorld To);
    UFUNCTION() void HandleMessage(const FText& Message);
    UFUNCTION() void HandleBookComplete();
    UFUNCTION() void HandlePagesChanged(int32 Pages, int32 PagesForBook);
    UFUNCTION() void HandleCoinsChanged(EReflectionsWorld World, int32 Count);
    UFUNCTION() void HandleKeyAdded(FName KeyId);
    UFUNCTION() void HandleProgressRestored();

    UPROPERTY(Transient) TObjectPtr<UReflectionsWorldJumpConfig> Config;
    UPROPERTY(Transient) TObjectPtr<UEnhancedInputComponent> JumpInput;
    UPROPERTY(Transient) TObjectPtr<UInputMappingContext> ActiveContext;
    UPROPERTY(Transient) TObjectPtr<UInputAction> UpAction;
    UPROPERTY(Transient) TObjectPtr<UInputAction> DownAction;
    UPROPERTY(Transient) TObjectPtr<UReflectionsWorldHudWidget> Hud;
    UPROPERTY(Transient) TMap<TObjectPtr<UMeshComponent>, TObjectPtr<UMaterialInstanceDynamic>> OverlayTints;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> Music;
    TMap<EReflectionsWorld, int32> SeenCoins;
    TWeakObjectPtr<APlayerController> InputController;

    FTimerHandle TransitionTimer;
    FTimerHandle TintRetryTimer;
    FTimerHandle ArrivalTimer;
    EReflectionsWorld PendingWorld = EReflectionsWorld::Gray;
    FVector PendingLanding = FVector::ZeroVector;
    EReflectionsWorld TintRetryWorld = EReflectionsWorld::Gray;
    int32 TintRetries = 0;
    double LastJumpTime = -100.0;
    bool bStarted = false;
    bool bJumping = false;
    bool bWarnedNoMagic = false;
};
