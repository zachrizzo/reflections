#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Worlds/ReflectionsWorldTypes.h"
#include "ReflectionsWorldAnchor.generated.h"

class UBillboardComponent;
class UBoxComponent;
class UPostProcessComponent;
class UReflectionsWorldJumpConfig;
class UTextRenderComponent;

/**
 * Marks one London in an OffsetCopies layout. Put one in each copy on the same landmark (for example the
 * same corner of the same building). A jump moves the hero by (destination anchor - current anchor), so the
 * hero lands at the same spot and height. The box says which London a location belongs to.
 */
UCLASS(Blueprintable, meta = (DisplayName = "Reflections World Anchor"))
class REFLECTIONS_API AReflectionsWorldAnchor : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsWorldAnchor();

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World Jump")
    EReflectionsWorld World = EReflectionsWorld::Gray;

    /** Optional: use this config in this level instead of /Game/Worlds/DA_WorldJumpConfig. Set it on one anchor. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World Jump")
    TObjectPtr<UReflectionsWorldJumpConfig> ConfigOverride;

    /** Apply this London's colour grade (from the config) inside the bounds. Off if the map has its own volumes. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World Jump")
    bool bApplyWorldGrade = true;

    /** Locations inside this box belong to this London. Size it to cover the whole copy. */
    UFUNCTION(BlueprintPure, Category = "World Jump")
    bool ContainsLocation(const FVector& Location) const;

    UBoxComponent* GetBounds() const { return Bounds; }

#if WITH_EDITOR
    virtual void PostEditChangeProperty(FPropertyChangedEvent& Event) override;
#endif
    virtual void OnConstruction(const FTransform& Transform) override;

protected:
    virtual void BeginPlay() override;

private:
    void RefreshLabel();
    void RefreshGrade();

    UPROPERTY(VisibleAnywhere, Category = "World Jump")
    TObjectPtr<USceneComponent> Root;

    UPROPERTY(VisibleAnywhere, Category = "World Jump")
    TObjectPtr<UBoxComponent> Bounds;

    UPROPERTY(VisibleAnywhere, Category = "World Jump")
    TObjectPtr<UTextRenderComponent> Label;

    UPROPERTY(VisibleAnywhere, Category = "World Jump")
    TObjectPtr<UPostProcessComponent> Grade;

#if WITH_EDITORONLY_DATA
    UPROPERTY()
    TObjectPtr<UBillboardComponent> Sprite;
#endif
};
