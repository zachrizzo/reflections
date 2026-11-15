#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "ReflectionsCrowdYieldSubsystem.generated.h"

class ACharacter;
class UReflectionsNpcReactionComponent;

/**
 * "Make way": calm civilians step aside out of the path of a marching squad (actors tagged NPC_Soldier) and of a
 * running player, then go back to what they were doing.
 *
 * Who counts as a civilian, whether it is calm and which character walks for it all come from the unified NPC
 * system (UReflectionsNpcSubsystem::GetNpcActors / FindNpc, the NPC component's Reaction and movement character).
 * The yield is one extra movement input per frame on that character, added on top of the NPC's own movement; an
 * NPC that is fleeing, investigating, fighting or down is left entirely to the NPC system. Squads call nothing.
 * Tuning: Crowd.Yield.* console variables.
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsCrowdYieldSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;

    /** Civilians stepping aside this frame. */
    UFUNCTION(BlueprintPure, Category="Crowd|Yield")
    int32 GetYieldingCount() const { return YieldingCount; }

    /** Total frames on which any civilian stepped aside since play began (for tests). */
    UFUNCTION(BlueprintPure, Category="Crowd|Yield")
    int32 GetYieldFrames() const { return YieldFrames; }

    UFUNCTION(BlueprintPure, Category="Crowd|Yield")
    bool IsYielding(const AActor* Npc) const;

private:
    struct FYielder
    {
        TWeakObjectPtr<AActor> Npc;
        TWeakObjectPtr<UReflectionsNpcReactionComponent> Brain;
        FVector LastDirection = FVector::ZeroVector;
        float HoldRemaining = 0.0f;
        uint32 Seed = 0;
    };
    struct FMover
    {
        TWeakObjectPtr<ACharacter> Character;
        float HalfWidth = 0.0f;
    };

    void Refresh();

    TArray<FYielder> Yielders;
    TArray<FMover> Movers;
    double NextRefresh = 0.0;
    int32 YieldingCount = 0;
    int32 YieldFrames = 0;
};
