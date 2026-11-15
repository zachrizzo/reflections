#include "GrayLondonStrongholdOutcome.h"

namespace GrayLondonStrongholds
{
CityOutcomeUpdate CityOutcomeBridge::Observe(UWorld* World, const Campaign& CampaignState)
{
    // Returning a pending result off-thread must not race the server-owned
    // baseline. The owner schedules observation/reset on the game thread.
    if (!IsInGameThread()) return {};
    if (!UnrealCheckpoint::IsAuthorityGameWorld(World) || !CampaignState.IsReady() ||
        CampaignState.Generation() == 0)
    {
        Reset();
        return {};
    }

    const bool bReclaimed = CampaignState.AllReclaimed();
    CityOutcomeUpdate Result;
    Result.State = bReclaimed ? CityOutcome::Reclaimed : CityOutcome::InProgress;
    if (bHasBaseline && ObservedCampaign == &CampaignState &&
        ObservedGeneration == CampaignState.Generation() && !bWasReclaimed && bReclaimed)
    {
        Result.Event = CityEvent::CityReclaimed;
    }

    // A fresh generation, a restored save, or a newly attached observer is a
    // baseline. Publish its state, but do not repeat a prior completion event.
    ObservedCampaign = &CampaignState;
    ObservedGeneration = CampaignState.Generation();
    bHasBaseline = true;
    bWasReclaimed = bReclaimed;
    return Result;
}

void CityOutcomeBridge::Reset()
{
    ObservedCampaign = nullptr;
    ObservedGeneration = 0;
    bHasBaseline = false;
    bWasReclaimed = false;
}
}
