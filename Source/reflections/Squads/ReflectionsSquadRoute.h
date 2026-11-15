#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ReflectionsSquadRoute.generated.h"

class USplineComponent;

/**
 * A patrol route for enemy squads. Drag the spline points in the level; the squad marches point to point
 * (navmesh paths between points when the level has a navmesh) and halts briefly at each point if asked.
 */
UCLASS(Blueprintable, meta=(DisplayName="Reflections Squad Route"))
class REFLECTIONS_API AReflectionsSquadRoute : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsSquadRoute();

    /** Closed loop (true) or walk to the end and back (false). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad Route")
    bool bLoop = true;

    /** Seconds the squad stands at attention at each route point. 0 marches straight on. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad Route", meta=(ClampMin="0", Units="s"))
    float HaltSeconds = 0.0f;

    UFUNCTION(BlueprintPure, Category="Squad Route")
    int32 GetNumPoints() const;

    UFUNCTION(BlueprintPure, Category="Squad Route")
    FVector GetPoint(int32 Index) const;

    /** Replace the route at runtime (test spawning). Points are world space. */
    UFUNCTION(BlueprintCallable, Category="Squad Route")
    void SetPoints(const TArray<FVector>& WorldPoints, bool bClosedLoop);

    USplineComponent* GetSpline() const { return Spline; }

    virtual void OnConstruction(const FTransform& Transform) override;

private:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Squad Route", meta=(AllowPrivateAccess="true"))
    TObjectPtr<USplineComponent> Spline;
};
