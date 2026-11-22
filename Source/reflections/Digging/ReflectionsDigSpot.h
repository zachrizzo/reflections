#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ReflectionsDigSpot.generated.h"

class UStaticMesh;
class UStaticMeshComponent;

/**
 * A patch of ground dug in stages. Each DigOnce shows the next stage mesh; reaching the last stage
 * uncovers one BuriedFindClass actor. SetStage (used when restoring a save) never uncovers the find.
 * On BeginPlay a spot with a SpotId restores its stage from the active save slot.
 */
UCLASS()
class REFLECTIONS_API AReflectionsDigSpot : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsDigSpot();

    /** Stable id the save uses to remember how far this spot was dug. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Digging")
    FName SpotId;

    /** One mesh per stage: index 0 is untouched ground, the last is fully dug. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Digging")
    TArray<TObjectPtr<UStaticMesh>> StageMeshes;

    /** Spawned once at the spot's location and rotation (unit scale) when a dig reaches the last stage. Optional. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Digging")
    TSubclassOf<AActor> BuriedFindClass;

    /** Digs one stage deeper. Returns false, changing nothing, at the last stage or with no meshes. */
    UFUNCTION(BlueprintCallable, Category = "Digging")
    bool DigOnce();

    UFUNCTION(BlueprintPure, Category = "Digging")
    int32 GetStage() const;

    /** Jumps to a stage, clamped to 0..last, and shows its mesh. Never spawns the find; landing on the last stage uses it up. */
    UFUNCTION(BlueprintCallable, Category = "Digging")
    void SetStage(int32 NewStage);

    /** The root component; collision profile BlockAll. */
    UStaticMeshComponent* GetMeshComponent() const;

    virtual void OnConstruction(const FTransform& Transform) override;

protected:
    virtual void BeginPlay() override;

private:
    int32 GetLastStage() const;
    void ShowStage();

    UPROPERTY(VisibleAnywhere, Category = "Digging")
    TObjectPtr<UStaticMeshComponent> MeshComponent;

    int32 Stage = 0;
    bool bFindSpawned = false;
};
