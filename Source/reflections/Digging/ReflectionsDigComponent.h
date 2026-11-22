#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ReflectionsDigComponent.generated.h"

class AController;
class APawn;
class APlayerController;
class UEnhancedInputComponent;
class UInputAction;
class UInputMappingContext;
struct FHitResult;
struct FInputActionValue;

/**
 * Lets its pawn dig: TryDig traces from the view point and digs the AReflectionsDigSpot it hits within reach, saving
 * the spot's new stage. For a locally controlled player pawn it also binds G (IA_Dig in IMC_Digging, built in code).
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

    /** Digs the spot in front of the pawn once. Returns true if a spot within reach dug one stage deeper. */
    UFUNCTION(BlueprintCallable, Category = "Digging")
    bool TryDig();

    /** Returns the pawn's dig component, adding and registering one if it has none. Null pawn gives null. */
    static UReflectionsDigComponent* EnsureOnPawn(APawn* Pawn);

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    /** Traces from the view point; true with OutHit filled when something is hit within ReachCm of the pawn. */
    bool TraceReach(FHitResult& OutHit) const;

    void BindControls();
    void UnbindControls();
    void OnDigAction(const FInputActionValue& Value);

    UFUNCTION()
    void HandleControllerChanged(APawn* Pawn, AController* OldController, AController* NewController);

    UPROPERTY(Transient)
    TObjectPtr<UInputMappingContext> DigContext;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> DigAction;

    UPROPERTY(Transient)
    TObjectPtr<UEnhancedInputComponent> DigInput;

    /** The controller DigInput and DigContext were added to. */
    TWeakObjectPtr<APlayerController> BoundController;
};
