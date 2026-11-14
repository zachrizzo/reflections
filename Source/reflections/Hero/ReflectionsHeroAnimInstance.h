#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "ReflectionsHeroAnimInstance.generated.h"

class UAnimSequence;


/** Native hero pose driver with velocity blending and a full-body spell slot. */
UCLASS(Blueprintable)
class UReflectionsHeroAnimInstance : public UAnimInstance
{
    GENERATED_BODY()

public:
    static const FName SpellSlot;

    UPROPERTY(EditDefaultsOnly, Category = "Hero|Locomotion")
    TObjectPtr<UAnimSequence> Idle;

    UPROPERTY(EditDefaultsOnly, Category = "Hero|Locomotion")
    TObjectPtr<UAnimSequence> Walk;

    UPROPERTY(EditDefaultsOnly, Category = "Hero|Locomotion")
    TObjectPtr<UAnimSequence> Jog;

    UPROPERTY(EditDefaultsOnly, Category = "Hero|Locomotion")
    TObjectPtr<UAnimSequence> CrouchIdle;

    UPROPERTY(EditDefaultsOnly, Category = "Hero|Locomotion")
    TObjectPtr<UAnimSequence> CrouchWalk;

    UPROPERTY(EditDefaultsOnly, Category = "Hero|Locomotion")
    TObjectPtr<UAnimSequence> Takeoff;

    UPROPERTY(EditDefaultsOnly, Category = "Hero|Locomotion")
    TObjectPtr<UAnimSequence> Fall;

    UPROPERTY(EditDefaultsOnly, Category = "Hero|Locomotion")
    TObjectPtr<UAnimSequence> Land;

protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override;
};
