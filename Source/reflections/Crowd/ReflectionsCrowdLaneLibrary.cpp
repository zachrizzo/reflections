#include "Crowd/ReflectionsCrowdLaneLibrary.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "ZoneGraphData.h"
#include "ZoneGraphSubsystem.h"

namespace
{
    const UZoneGraphSubsystem* ZoneGraphOf(const UObject* WorldContext)
    {
        const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull) : nullptr;
        return World ? World->GetSubsystem<UZoneGraphSubsystem>() : nullptr;
    }
}

int32 UReflectionsCrowdLaneLibrary::CountLanesNear(const UObject* WorldContext, FVector Center, float Radius)
{
    const UZoneGraphSubsystem* ZoneGraph = ZoneGraphOf(WorldContext);
    if (!ZoneGraph) return 0;
    const double RadiusSq = FMath::Square(static_cast<double>(Radius));
    int32 Count = 0;
    for (const FRegisteredZoneGraphData& Registered : ZoneGraph->GetRegisteredZoneGraphData())
    {
        if (!Registered.bInUse || !Registered.ZoneGraphData) continue;
        const FZoneGraphStorage& Storage = Registered.ZoneGraphData->GetStorage();
        for (const FZoneLaneData& Lane : Storage.Lanes)
        {
            for (int32 Point = Lane.PointsBegin; Point < Lane.PointsEnd && Storage.LanePoints.IsValidIndex(Point); ++Point)
            {
                if (FVector::DistSquared2D(Storage.LanePoints[Point], Center) <= RadiusSq)
                {
                    ++Count;
                    break;
                }
            }
        }
    }
    return Count;
}

FString UReflectionsCrowdLaneLibrary::DescribeLanes(const UObject* WorldContext)
{
    const UZoneGraphSubsystem* ZoneGraph = ZoneGraphOf(WorldContext);
    if (!ZoneGraph) return TEXT("no ZoneGraph subsystem in this world");
    int32 Data = 0, Lanes = 0, Points = 0;
    double Length = 0.0;
    for (const FRegisteredZoneGraphData& Registered : ZoneGraph->GetRegisteredZoneGraphData())
    {
        if (!Registered.bInUse || !Registered.ZoneGraphData) continue;
        ++Data;
        const FZoneGraphStorage& Storage = Registered.ZoneGraphData->GetStorage();
        Lanes += Storage.Lanes.Num();
        Points += Storage.LanePoints.Num();
        for (const FZoneLaneData& Lane : Storage.Lanes)
            for (int32 Point = Lane.PointsBegin + 1; Point < Lane.PointsEnd && Storage.LanePoints.IsValidIndex(Point); ++Point)
                Length += FVector::Dist(Storage.LanePoints[Point - 1], Storage.LanePoints[Point]);
    }
    return FString::Printf(TEXT("%d ZoneGraph data, %d lanes, %d lane points, %.0f m of lanes"), Data, Lanes, Points, Length / 100.0);
}
