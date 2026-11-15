#include "Crowd/ReflectionsCrowdGridGenerator.h"
#include "MassSpawnLocationProcessor.h"
#include "MassSpawnerTypes.h"
#include "GameFramework/Actor.h"

void UReflectionsCrowdGridGenerator::Generate(UObject& QueryOwner, TConstArrayView<FMassSpawnedEntityType> EntityTypes, int32 Count,
    FFinishedGeneratingSpawnDataSignature& FinishedGeneratingSpawnPointsDelegate) const
{
    TArray<FMassEntitySpawnDataGeneratorResult> Results;
    if (Count <= 0 || EntityTypes.IsEmpty())
    {
        FinishedGeneratingSpawnPointsDelegate.Execute(Results);
        return;
    }
    const int32 SafeCount = FMath::Min(Count, FMath::Clamp(MaxTestAgents, 1, 5000));
    if (SafeCount < Count) { UE_LOG(LogTemp, Warning, TEXT("Crowd test spawn capped at %d of %d requested entities"), SafeCount, Count); }
    BuildResultsFromEntityTypes(SafeCount, EntityTypes, Results);
    const AActor* OwnerActor = Cast<AActor>(&QueryOwner);
    const FTransform ParentTransform = OwnerActor ? OwnerActor->GetActorTransform() : FTransform::Identity;
    const int32 GridColumns = FMath::Clamp(Columns, 1, 500);
    const int32 GridRows = FMath::DivideAndRoundUp(SafeCount, GridColumns);
    const float GridSpacing = FMath::Max(Spacing, 50.0f);
    FRandomStream Random(TestSeed);
    int32 Next = 0;
    for (FMassEntitySpawnDataGeneratorResult& Result : Results)
    {
        Result.SpawnDataProcessor = UMassSpawnLocationProcessor::StaticClass();
        Result.SpawnData.InitializeAs<FMassTransformsSpawnData>();
        FMassTransformsSpawnData& Data = Result.SpawnData.GetMutable<FMassTransformsSpawnData>();
        Data.bRandomize = false;
        Data.Transforms.Reserve(Result.NumEntities);
        for (int32 I = 0; I < Result.NumEntities; ++I, ++Next)
        {
            const float X = (static_cast<float>(Next % GridColumns) - (GridColumns - 1) * 0.5f) * GridSpacing;
            const float Y = (static_cast<float>(Next / GridColumns) - (GridRows - 1) * 0.5f) * GridSpacing;
            const FRotator Heading(0.0f, bRandomizeHeading ? Random.FRandRange(-180.0f, 180.0f) : 0.0f, 0.0f);
            const FTransform Local(Heading, FVector(X, Y, 0));
            Data.Transforms.Add(Local * ParentTransform);
        }
    }
    FinishedGeneratingSpawnPointsDelegate.Execute(Results);
}

