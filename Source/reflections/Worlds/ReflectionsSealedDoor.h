#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ReflectionsSealedDoor.generated.h"

class UBoxComponent;
class UMaterialInstanceDynamic;
class UPointLightComponent;
class UStaticMeshComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FReflectionsDoorOpened);

/** A door that blocks the way until the player carries the matching key, then slides up out of the frame. */
UCLASS(Blueprintable, meta = (DisplayName = "Reflections Sealed Door"))
class REFLECTIONS_API AReflectionsSealedDoor : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsSealedDoor();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door")
    FName RequiredKey = TEXT("GiltTowerKey");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door")
    bool bConsumeKey = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door")
    FText LockedMessage;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door")
    FText OpenedMessage;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door", meta = (Units = "cm"))
    FVector DoorSize = FVector(30.0f, 220.0f, 320.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door", meta = (ClampMin = "0.05", Units = "s"))
    float OpenTime = 1.2f;

    UPROPERTY(BlueprintAssignable, Category = "Door")
    FReflectionsDoorOpened OnOpened;

    UFUNCTION(BlueprintCallable, Category = "Door")
    void Open();

    UFUNCTION(BlueprintPure, Category = "Door")
    bool IsOpen() const { return bOpen; }

    virtual void OnConstruction(const FTransform& Transform) override;

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

private:
    UFUNCTION()
    void HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
        int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

    UPROPERTY(VisibleAnywhere, Category = "Door")
    TObjectPtr<USceneComponent> Root;

    UPROPERTY(VisibleAnywhere, Category = "Door")
    TObjectPtr<UStaticMeshComponent> Panel;

    UPROPERTY(VisibleAnywhere, Category = "Door")
    TObjectPtr<UBoxComponent> Trigger;

    UPROPERTY(VisibleAnywhere, Category = "Door")
    TObjectPtr<UPointLightComponent> SealLight;

    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> PanelMaterial;

    float OpenAlpha = 0.0f;
    double LastLockedMessageTime = -100.0;
    bool bOpen = false;
};
