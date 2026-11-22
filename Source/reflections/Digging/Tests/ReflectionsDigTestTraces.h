#pragma once

#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "CollisionQueryParams.h"
#include "Digging/ReflectionsDigTerrain.h"
#include "Engine/EngineTypes.h"
#include "Engine/HitResult.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

/** Downward traces the dig tests share, in editor test worlds and in the game process alike. */
struct FReflectionsDigTestTraces
{
    /** The first hit of a visibility trace from (X, Y, StartZ) straight down to (X, Y, EndZ), whatever it hit. Ignored, if set, is skipped. */
    static TOptional<FHitResult> TraceDown(const UWorld* World, double X, double Y, double StartZ, double EndZ,
        const AActor* Ignored = nullptr)
    {
        FHitResult Hit;
        const FCollisionQueryParams Params(SCENE_QUERY_STAT(ReflectionsDigTestTrace), /*bTraceComplex=*/ false, Ignored);
        if (World != nullptr && World->LineTraceSingleByChannel(Hit, FVector(X, Y, StartZ), FVector(X, Y, EndZ), ECC_Visibility, Params))
        {
            return Hit;
        }
        return TOptional<FHitResult>();
    }

    /**
     * Z of the first hit of that trace, only when the hit is a chunk piece of the terrain. Nothing, or anything else
     * (such as the safety floor under the grid), gives no value.
     */
    static TOptional<double> TraceDownToChunkZ(const UWorld* World, double X, double Y, double StartZ, double EndZ,
        const AActor* Ignored = nullptr)
    {
        const TOptional<FHitResult> Hit = TraceDown(World, X, Y, StartZ, EndZ, Ignored);
        if (Hit.IsSet() && Cast<UReflectionsDigChunkComponent>(Hit->GetComponent()) != nullptr)
        {
            return Hit->ImpactPoint.Z;
        }
        return TOptional<double>();
    }
};

#endif // WITH_DEV_AUTOMATION_TESTS
