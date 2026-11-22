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
class UReflectionsDigSubsystem;
struct FHitResult;
struct FInputActionValue;

/**
 * Lets its pawn dig: TryDig traces from the view point and digs what it hits within reach. An AReflectionsDigSpot digs
 * one stage deeper and its new stage is saved; anything else is handed to the dig subsystem, which digs a sphere out of
 * its terrain if the hit is that terrain's ground. TryFill fills a sphere of terrain back in the same way. For a
 * locally controlled player pawn it also binds G to TryDig (IA_Dig in IMC_Digging, always) and H to TryFill (IA_Fill in
 * IMC_DigFill, only while the pawn's world has a dig terrain); both are built in code.
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

    /**
     * Fills the terrain in front of the pawn once. Returns true if terrain within reach gained ground. A fill whose
     * sphere would reach into the pawn (its capsule, for a character; its colliding bounds otherwise) does nothing.
     */
    UFUNCTION(BlueprintCallable, Category = "Digging")
    bool TryFill();

    /**
     * Whether H is mapped to TryFill: with a local player, whether IMC_DigFill is in its Enhanced Input subsystem;
     * without one (a pawn nobody controls locally), whether it would be, which is whether the world has a dig terrain.
     */
    bool IsFillMapped() const;

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

    /** True when a ReflectionsDig::StampRadiusCm sphere at Center reaches into the pawn's capsule or colliding bounds. */
    bool StampWouldReachPawn(const FVector& Center) const;

    void BindControls();
    void UnbindControls();
    /** Adds IMC_DigFill to the bound local player while the world has a terrain, and removes it otherwise. */
    void ApplyFillMapping();
    void HandleTerrainRegisteredChanged();
    void OnDigAction(const FInputActionValue& Value);
    void OnFillAction(const FInputActionValue& Value);

    UFUNCTION()
    void HandleControllerChanged(APawn* Pawn, AController* OldController, AController* NewController);

    UPROPERTY(Transient)
    TObjectPtr<UInputMappingContext> DigContext;

    /** Holds only H to IA_Fill, so it can be added and removed on its own. */
    UPROPERTY(Transient)
    TObjectPtr<UInputMappingContext> FillContext;

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

    /** The dig subsystem whose OnTerrainRegisteredChanged this component listens to, from BeginPlay to EndPlay. */
    TWeakObjectPtr<UReflectionsDigSubsystem> TerrainSource;
    FDelegateHandle TerrainChangedHandle;

    /** Whether the world had a dig terrain when this component last looked: H is mapped exactly then. */
    bool bWorldHasTerrain = false;
};
