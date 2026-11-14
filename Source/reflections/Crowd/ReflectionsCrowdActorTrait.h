#pragma once
#include "CoreMinimal.h"
#include "MassEntityTraitBase.h"
#include "ReflectionsCrowdActorTrait.generated.h"

/** Provides actor linkage required by the MetaHuman Crowd visualization trait. */
UCLASS()
class REFLECTIONS_API UReflectionsCrowdActorTrait : public UMassEntityTraitBase
{
    GENERATED_BODY()
protected:
    virtual void BuildTemplate(FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const override;
};
