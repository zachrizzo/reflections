#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "ReflectionsSpellRagdollSubsystem.generated.h"

/** Transfers a lethal spell's impulse to an NPC's newly enabled ragdoll. */
UCLASS()
class REFLECTIONS_API UReflectionsSpellRagdollSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;

private:
    UFUNCTION()
    void OnSpellHit(const FReflectionsSpellHitData& Hit);
};
