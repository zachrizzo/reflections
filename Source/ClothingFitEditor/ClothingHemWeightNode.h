#pragma once

#include "Dataflow/DataflowNode.h"
#include "GeometryCollection/ManagedArrayCollection.h"
#include "ClothingHemWeightNode.generated.h"

USTRUCT(Meta=(DataflowCloth))
struct FClothingHemWeightNode : public FDataflowNode
{
    GENERATED_BODY()
    DATAFLOW_NODE_DEFINE_INTERNAL(FClothingHemWeightNode, "ClothingHemWeight", "Cloth", "Hem travel gradient");

public:
    UPROPERTY(Meta=(DataflowInput, DataflowOutput, DataflowPassthrough="Collection"))
    FManagedArrayCollection Collection;

    UPROPERTY(EditAnywhere, Category="Hem")
    float FreeBelowCm = 99.f;

    UPROPERTY(EditAnywhere, Category="Hem")
    float PinAboveCm = 115.f;

    FClothingHemWeightNode(const UE::Dataflow::FNodeParameters& Parameters, FGuid Guid = FGuid::NewGuid());
    virtual void Evaluate(UE::Dataflow::FContext& Context, const FDataflowOutput* Out) const override;
};
