#pragma once

#include "CoreMinimal.h"
#include "MassEntitySpawnDataGeneratorBase.h"
#include "ReflectionsCrowdGridGenerator.generated.h"

/** Deterministic flat grid for isolated crowd tests. This does not project to navigation. */
UCLASS(BlueprintType, meta=(DisplayName="Reflections Crowd Test Grid"))
class REFLECTIONS_API UReflectionsCrowdGridGenerator : public UMassEntitySpawnDataGeneratorBase
{
    GENERATED_BODY()
public:
    virtual void Generate(UObject& QueryOwner, TConstArrayView<FMassSpawnedEntityType> EntityTypes, int32 Count,
        FFinishedGeneratingSpawnDataSignature& FinishedGeneratingSpawnPointsDelegate) const override;

    /** Horizontal grid width, in agents; extra rows are added as needed. */
    UPROPERTY(EditAnywhere, Category="Test Grid", meta=(ClampMin="1", ClampMax="500")) int32 Columns = 10;
    UPROPERTY(EditAnywhere, Category="Test Grid", meta=(ClampMin="50.0", Units="cm")) float Spacing = 180.0f;
    /** Safety limit per test spawner; actual capacity must be measured. */
    UPROPERTY(EditAnywhere, Category="Test Grid", meta=(ClampMin="1", ClampMax="5000")) int32 MaxTestAgents = 500;
    /** Fixed random headings; uses the local stream only. */
    UPROPERTY(EditAnywhere, Category="Test Grid") int32 TestSeed = 3819;
    UPROPERTY(EditAnywhere, Category="Test Grid") bool bRandomizeHeading = true;
};

