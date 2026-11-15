#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ReflectionsStrongholdGate.generated.h"

class UReflectionsQuestSubsystem;
class UStaticMeshComponent;

UENUM()
enum class EReflectionsStrongholdPennants : uint8
{
    Pending,
    Occupied,
    Reclaimed
};

/**
 * Review-only cosmetic gate for the authoritative campaign's site unlock.
 * Keep this outside Source until the restore handshake, LAN travel policy,
 * streaming-state ownership and objective guards in README.md are in place.
 */
UCLASS()
class REFLECTIONS_API AReflectionsStrongholdGate : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsStrongholdGate();
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UPROPERTY(EditInstanceOnly, Category = "Stronghold")
    FName ReclaimUnlock;

    UPROPERTY(VisibleAnywhere, Category = "Stronghold")
    TObjectPtr<UStaticMeshComponent> Frame;

    UPROPERTY(VisibleAnywhere, Category = "Stronghold")
    TObjectPtr<UStaticMeshComponent> OccupiedPennants;

    UPROPERTY(VisibleAnywhere, Category = "Stronghold")
    TObjectPtr<UStaticMeshComponent> ReclaimedPennants;

    UPROPERTY(ReplicatedUsing = OnRep_Pennants)
    EReflectionsStrongholdPennants Pennants = EReflectionsStrongholdPennants::Pending;

    TWeakObjectPtr<UReflectionsQuestSubsystem> BoundQuests;

    UFUNCTION() void OnRep_Pennants();
    UFUNCTION() void HandleUnlock(FName Unlock, FName QuestId);
    UFUNCTION() void RefreshFromQuests();
};
