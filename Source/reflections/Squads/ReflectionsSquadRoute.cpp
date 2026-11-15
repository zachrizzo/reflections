#include "Squads/ReflectionsSquadRoute.h"

#include "Components/SplineComponent.h"

AReflectionsSquadRoute::AReflectionsSquadRoute()
{
    PrimaryActorTick.bCanEverTick = false;
    Spline = CreateDefaultSubobject<USplineComponent>(TEXT("Route"));
    SetRootComponent(Spline);
    Spline->ClearSplinePoints(false);
    // A default square patrol, 15 m a side, so a freshly placed route is usable as is.
    Spline->AddSplinePoint(FVector(0.0, 0.0, 0.0), ESplineCoordinateSpace::Local, false);
    Spline->AddSplinePoint(FVector(1500.0, 0.0, 0.0), ESplineCoordinateSpace::Local, false);
    Spline->AddSplinePoint(FVector(1500.0, 1500.0, 0.0), ESplineCoordinateSpace::Local, false);
    Spline->AddSplinePoint(FVector(0.0, 1500.0, 0.0), ESplineCoordinateSpace::Local, false);
    for (int32 Index = 0; Index < Spline->GetNumberOfSplinePoints(); ++Index)
    {
        Spline->SetSplinePointType(Index, ESplinePointType::Linear, false);
    }
    Spline->SetClosedLoop(true, false);
    Spline->UpdateSpline();
    SetActorHiddenInGame(true);
}

void AReflectionsSquadRoute::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    if (Spline)
    {
        Spline->SetClosedLoop(bLoop, true);
    }
}

int32 AReflectionsSquadRoute::GetNumPoints() const
{
    return Spline ? Spline->GetNumberOfSplinePoints() : 0;
}

FVector AReflectionsSquadRoute::GetPoint(int32 Index) const
{
    if (!Spline || Spline->GetNumberOfSplinePoints() == 0)
    {
        return GetActorLocation();
    }
    const int32 Count = Spline->GetNumberOfSplinePoints();
    return Spline->GetLocationAtSplinePoint(((Index % Count) + Count) % Count, ESplineCoordinateSpace::World);
}

void AReflectionsSquadRoute::SetPoints(const TArray<FVector>& WorldPoints, bool bClosedLoop)
{
    if (!Spline)
    {
        return;
    }
    bLoop = bClosedLoop;
    Spline->ClearSplinePoints(false);
    for (const FVector& Point : WorldPoints)
    {
        Spline->AddSplinePoint(Point, ESplineCoordinateSpace::World, false);
    }
    for (int32 Index = 0; Index < Spline->GetNumberOfSplinePoints(); ++Index)
    {
        Spline->SetSplinePointType(Index, ESplinePointType::Linear, false);
    }
    Spline->SetClosedLoop(bClosedLoop, false);
    Spline->UpdateSpline();
}
