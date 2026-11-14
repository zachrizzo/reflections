#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "ReflectionsNpcPopulationSubsystem.generated.h"

/** Adds reaction support only to level actors explicitly tagged NPC_Reactive. */
UCLASS()
class REFLECTIONS_API UReflectionsNpcPopulationSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual void OnWorldBeginPlay(UWorld& World) override;
    /** Actors enrolled for reactions during this world's initialization. */
    const TArray<TWeakObjectPtr<AActor>>& GetReactiveActors() const { return ReactiveActors; }

private:
    TArray<TWeakObjectPtr<AActor>> ReactiveActors;
};
