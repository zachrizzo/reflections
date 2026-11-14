#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Worlds/ReflectionsWorldTypes.h"
#include "ReflectionsWorldPickups.generated.h"

class APawn;
class UMaterialInstanceDynamic;
class UPointLightComponent;
class USphereComponent;
class UStaticMeshComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FReflectionsPickedUp, APawn*, Collector);

/** Floating, spinning thing the player walks into. Subclasses decide what it gives. */
UCLASS(Abstract, Blueprintable)
class REFLECTIONS_API AReflectionsWorldPickup : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsWorldPickup();

    UPROPERTY(BlueprintAssignable, Category = "Pickup")
    FReflectionsPickedUp OnPickedUp;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pickup")
    float SpinDegreesPerSecond = 90.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pickup", meta = (Units = "cm"))
    float BobHeight = 12.0f;

    /** Colour of the mesh and the glow. */
    UFUNCTION(BlueprintCallable, Category = "Pickup")
    void SetGlowColor(const FLinearColor& Color);

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

    /** Give the item. Return false to leave the pickup in place. */
    virtual bool GiveTo(APawn* Collector) PURE_VIRTUAL(AReflectionsWorldPickup::GiveTo, return false;);
    virtual FLinearColor GetDefaultColor() const { return FLinearColor::White; }

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pickup")
    TObjectPtr<USphereComponent> Trigger;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pickup")
    TObjectPtr<USceneComponent> Spinner;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pickup")
    TObjectPtr<UStaticMeshComponent> Mesh;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Pickup")
    TObjectPtr<UPointLightComponent> Glow;

private:
    UFUNCTION()
    void HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
        int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> Material;
    float Clock = 0.0f;
    FVector SpinnerBase = FVector::ZeroVector;
    bool bCollected = false;
};

/** A one-use coin from one London. Beat a native of that London to earn one. */
UCLASS(Blueprintable, meta = (DisplayName = "Reflections World Coin"))
class REFLECTIONS_API AReflectionsCoinPickup : public AReflectionsWorldPickup
{
    GENERATED_BODY()

public:
    AReflectionsCoinPickup();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Coin", meta = (ExposeOnSpawn = "true"))
    EReflectionsWorld CoinWorld = EReflectionsWorld::Red;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Coin", meta = (ClampMin = "1"))
    int32 Count = 1;

    virtual void OnConstruction(const FTransform& Transform) override;

protected:
    virtual bool GiveTo(APawn* Collector) override;
    virtual FLinearColor GetDefaultColor() const override;
};

/** One page of the book. Three different pages make the spell. */
UCLASS(Blueprintable, meta = (DisplayName = "Reflections Book Page"))
class REFLECTIONS_API AReflectionsBookPagePickup : public AReflectionsWorldPickup
{
    GENERATED_BODY()

public:
    AReflectionsBookPagePickup();

    /** Unique per page (for example GrayTowerPage). Empty: the actor's name. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Page")
    FName PageId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Page")
    FText PageTitle;

protected:
    virtual bool GiveTo(APawn* Collector) override;
    virtual FLinearColor GetDefaultColor() const override { return FLinearColor(1.0f, 0.86f, 0.55f); }
};

/** A key that opens a ReflectionsSealedDoor with the same KeyId. */
UCLASS(Blueprintable, meta = (DisplayName = "Reflections Key"))
class REFLECTIONS_API AReflectionsKeyPickup : public AReflectionsWorldPickup
{
    GENERATED_BODY()

public:
    AReflectionsKeyPickup();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Key")
    FName KeyId = TEXT("RedTowerKey");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Key")
    FText KeyName;

protected:
    virtual bool GiveTo(APawn* Collector) override;
    virtual FLinearColor GetDefaultColor() const override { return FLinearColor(1.0f, 0.62f, 0.12f); }
};
