#pragma once

#include "CoreMinimal.h"
#include "Worlds/ReflectionsWorldPickups.h"
#include "ReflectionsQuestItem.generated.h"

/**
 * A quest item lying in the world (a ledger, a locket). Walk into it to take it. The quest system spawns these at
 * Item_<ItemId> markers for Collect objectives; the map designer may also place them by hand.
 */
UCLASS(Blueprintable, meta = (DisplayName = "Reflections Quest Item"))
class REFLECTIONS_API AReflectionsQuestItem : public AReflectionsWorldPickup
{
    GENERATED_BODY()

public:
    AReflectionsQuestItem();

    /** Item id the quests count (Collect objective Target, Deliver objective Item). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest Item", meta = (ExposeOnSpawn = "true"))
    FName ItemId;

    /** Shown when picked up ("You found the red ledger."). Empty: the item id. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest Item")
    FText ItemName;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest Item")
    FLinearColor Color = FLinearColor(0.95f, 0.72f, 0.28f);

    /** Spawned by the quest system (not hand-placed). */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Quest Item")
    bool bQuestSpawned = false;

protected:
    virtual void BeginPlay() override;
    virtual bool GiveTo(APawn* Collector) override;
    virtual FLinearColor GetDefaultColor() const override { return Color; }
};
