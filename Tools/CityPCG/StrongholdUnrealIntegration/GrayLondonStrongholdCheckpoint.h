#pragma once

#include "CoreMinimal.h"
#include "StrongholdCampaign.h"

class UWorld;
struct FReflectionsCheckpoint;

// Integration-ready native helpers, kept outside Source until the GameFlow
// owner can coordinate their save and restore hooks. They do not subscribe
// themselves, create a campaign, place an actor, or expose a client RPC.
namespace GrayLondonStrongholds
{
namespace UnrealCheckpoint
{
// True only on the game thread in an authority-owned Gray London game/PIE world.
bool IsAuthorityGameWorld(UWorld* World);

// Call only on the explicit authoritative fresh-run path before its first
// scheduled checkpoint. A missing save is not, by itself, a fresh run.
bool BeginFresh(UWorld* World, Campaign& CampaignState);

// Prepare the entire stronghold blob on the candidate checkpoint *before*
// GameFlow installs or writes it. On failure Candidate remains unchanged.
bool PrepareSave(UWorld* World, const Campaign& CampaignState, FReflectionsCheckpoint& Candidate);

// Validate the selected stronghold blob and exact configured sites without
// changing the checkpoint or live campaign. This uses strict migration only;
// missing/legacy blobs are not interpreted as a fresh game. The owner must
// call it before stamping slots, restoring mirrored files or replacing the
// selected checkpoint, and keep that selection and configuration unchanged.
// It validates only the stronghold data, not other systems' mirrored files.
bool PreflightLoad(UWorld* World, const FReflectionsCheckpoint& Selected, const Campaign& CampaignState);

// The owner calls this before installing or applying the selected checkpoint,
// and retains the returned generation for that exact load request.
bool BeginRestore(UWorld* World, const FReflectionsCheckpoint& Selected,
                  Campaign& CampaignState, std::uint64_t& Generation);

// The callback and selected checkpoint must have the same exact stronghold
// blob, in addition to the same map and timestamp. The core checks Generation.
bool CompleteRestore(UWorld* World, const FReflectionsCheckpoint& Restored,
                     const FReflectionsCheckpoint& Selected, Campaign& CampaignState,
                     std::uint64_t Generation);
}
}
