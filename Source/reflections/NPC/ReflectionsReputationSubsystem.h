#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "ReflectionsReputationSubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FReflectionsReputationChanged, AActor*, Player, float, OldValue, float, NewValue);

/** Runtime reputation; callers can explicitly report good deeds or crimes. */
UCLASS()
class REFLECTIONS_API UReflectionsReputationSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual void OnWorldBeginPlay(UWorld& World) override;
    virtual void Deinitialize() override;
    UFUNCTION(BlueprintPure, Category="NPC|Reputation")
    float GetReputation(AActor* Player) const;
    UFUNCTION(BlueprintCallable, Category="NPC|Reputation")
    void AdjustReputation(AActor* Player, float Delta);
    UPROPERTY(BlueprintAssignable, Category="NPC|Reputation")
    FReflectionsReputationChanged OnReputationChanged;
private:
    UFUNCTION() void HandleSpellHit(const FReflectionsSpellHitData& Hit);
    TMap<TWeakObjectPtr<AActor>, float> Scores;
};
