#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Digging/ReflectionsDigTypes.h"
#include "ReflectionsDigComponent.generated.h"

class AController;
class APawn;
class APlayerController;
class UEnhancedInputComponent;
class UInputAction;
class UInputMappingContext;
class ULocalPlayer;
struct FHitResult;
struct FInputActionValue;

/**
 * Lets its pawn dig: TryDig traces from the view point and digs what it hits within reach. A chunk piece of the dig
 * terrain loses a 100 cm sphere; an AReflectionsDigSpot digs one stage deeper and its new stage is saved. TryFill
 * fills a 100 cm sphere of terrain back in. For a locally controlled player pawn it also binds G to TryDig and H to
 * TryFill (IA_Dig and IA_Fill in IMC_Digging, built in code).
 */
UCLASS(ClassGroup = (Digging), meta = (BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsDigComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsDigComponent();

    /** How far from the pawn's location a dig reaches. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Digging", meta = (ClampMin = "0", Units = "cm"))
    float ReachCm = 250.0f;

    /**
     * Digs what is in front of the pawn once. Returns true if terrain within reach lost ground or a spot within reach
     * dug one stage deeper. A hit on the terrain's safety floor digs nothing.
     */
    UFUNCTION(BlueprintCallable, Category = "Digging")
    bool TryDig();

    /** Fills the terrain in front of the pawn once. Returns true if terrain within reach gained ground. */
    UFUNCTION(BlueprintCallable, Category = "Digging")
    bool TryFill();

    /** Returns the pawn's dig component, adding and registering one if it has none. Null pawn gives null. */
    static UReflectionsDigComponent* EnsureOnPawn(APawn* Pawn);

    /**
     * The dig ray: it starts level with the pawn along the view direction (never behind the view point), so nothing
     * between a third-person camera and the pawn can be hit, and runs ReachCm from there.
     */
    static void ComputeReachTrace(const FVector& ViewLocation, const FVector& ViewDirection, const FVector& PawnLocation,
        float ReachCm, FVector& OutStart, FVector& OutEnd);

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    /** Traces the ComputeReachTrace ray; true with OutHit filled when something is hit within ReachCm of the pawn. */
    bool TraceReach(FHitResult& OutHit) const;

    /** Digs (Remove) or fills (Add) a 100 cm sphere at a terrain hit; false unless the hit is a chunk piece and the grid changed. */
    bool StampTerrain(const FHitResult& Hit, EReflectionsDigMode Mode) const;

    void BindControls();
    void UnbindControls();
    void OnDigAction(const FInputActionValue& Value);
    void OnFillAction(const FInputActionValue& Value);

    UFUNCTION()
    void HandleControllerChanged(APawn* Pawn, AController* OldController, AController* NewController);

    UPROPERTY(Transient)
    TObjectPtr<UInputMappingContext> DigContext;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> DigAction;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> FillAction;

    UPROPERTY(Transient)
    TObjectPtr<UEnhancedInputComponent> DigInput;

    /** The controller DigInput and DigContext were added to. */
    TWeakObjectPtr<APlayerController> BoundController;

    /** The local player DigContext was added for; kept separately so the context is removed after the controller is gone. */
    TWeakObjectPtr<ULocalPlayer> BoundPlayer;
};
