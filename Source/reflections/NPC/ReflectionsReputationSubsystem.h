#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "ReflectionsReputationSubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FReflectionsReputationChanged, AActor*, Player, float, OldValue, float, NewValue);

/**
 * Runtime reputation score per player, -100 to 100. It only stores the score: what a spell hit, a kill or a
 * heal is worth comes from the NPC's archetype and is applied by UReflectionsNpcSubsystem. Other systems can
 * report good deeds or crimes with AdjustReputation.
 */
UCLASS()
class REFLECTIONS_API UReflectionsReputationSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual void Deinitialize() override;
    UFUNCTION(BlueprintPure, Category="NPC|Reputation")
    float GetReputation(AActor* Player) const;
    UFUNCTION(BlueprintCallable, Category="NPC|Reputation")
    void AdjustReputation(AActor* Player, float Delta);
    UPROPERTY(BlueprintAssignable, Category="NPC|Reputation")
    FReflectionsReputationChanged OnReputationChanged;
private:
    TMap<TWeakObjectPtr<AActor>, float> Scores;
};
