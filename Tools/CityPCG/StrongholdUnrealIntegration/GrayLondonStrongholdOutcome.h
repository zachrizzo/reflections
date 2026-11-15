#pragma once

#include "GrayLondonStrongholdCheckpoint.h"

namespace GrayLondonStrongholds
{
// This is a separate city-reclaimed signal. It does not invoke GameFlow's
// OnVictory (which currently also signals BossDefeated) or any quest event.
enum class CityOutcome { Pending, InProgress, Reclaimed };
enum class CityEvent { None, CityReclaimed };

struct CityOutcomeUpdate
{
    CityOutcome State = CityOutcome::Pending;
    CityEvent Event = CityEvent::None;
};

// The authority owner observes on the game thread after each set of campaign changes. It
// publishes State to its persistent replicated object and dispatches Event
// locally on the server. This is not an actor, delegate, RPC, or replication.
class CityOutcomeBridge
{
public:
    CityOutcomeUpdate Observe(UWorld* World, const Campaign& CampaignState);
    // The owner calls this on the game thread before replacing the Campaign instance, including
    // when an allocator could reuse the same memory address.
    void Reset();

private:
    const Campaign* ObservedCampaign = nullptr;  // identity only; never dereferenced
    std::uint64_t ObservedGeneration = 0;
    bool bHasBaseline = false;
    bool bWasReclaimed = false;
};
}
