#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ReflectionsDigSpot.generated.h"

class UStaticMesh;
class UStaticMeshComponent;

/**
 * A patch of ground dug in stages. Each DigOnce shows the next stage mesh; reaching the last stage
 * uncovers one BuriedFindClass actor. SetStage never uncovers the find.
 * On BeginPlay a spot with a SpotId restores its stage from the active save slot; restored at its last stage, it
 * uncovers its find again unless MarkFindCollected was called for it.
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

    /**
     * Records in the active save that the player took this spot's find, so a restored spot no longer uncovers it.
     * Does nothing for a spot without a SpotId. The find is spawned owned by its spot (in the spot's level), so whatever
     * takes it reaches the spot through the find's GetOwner().
     */
    UFUNCTION(BlueprintCallable, Category = "Digging")
    void MarkFindCollected();

    /** The root component; collision profile BlockAll. */
    UStaticMeshComponent* GetMeshComponent() const;

    virtual void OnConstruction(const FTransform& Transform) override;

protected:
    virtual void BeginPlay() override;

private:
    int32 GetLastStage() const;
    void ShowStage();
    /** Spawns BuriedFindClass at the spot's location and rotation, unit scale, unless a find was already given. */
    void SpawnFind();

    UPROPERTY(VisibleAnywhere, Category = "Digging")
    TObjectPtr<UStaticMeshComponent> MeshComponent;

    int32 Stage = 0;
    bool bFindSpawned = false;
    /** The player took this spot's find (from the save, or MarkFindCollected). */
    bool bFindCollected = false;
};
