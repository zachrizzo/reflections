#include "GrayLondonStrongholdCheckpoint.h"

#include "Engine/World.h"
#include "GameFlow/ReflectionsGameFlowTypes.h"
#include "UObject/Package.h"

#include <vector>

namespace GrayLondonStrongholds
{
namespace UnrealCheckpoint
{
namespace
{
constexpr const TCHAR* GrayLondonPackage = TEXT("/Game/GrayLondon/Maps/GrayLondon_Geodata");
constexpr std::size_t MaxBlobBytes = 1024 * 1024;

FName BlobKey()
{
    return FName(TEXT("GrayLondonStrongholdsV1"));
}

bool AuthorityInGrayLondon(UWorld* World)
{
    return IsInGameThread() && IsValid(World) && World->IsGameWorld() && World->GetNetMode() != NM_Client &&
        UWorld::RemovePIEPrefix(World->GetOutermost()->GetName()).Equals(GrayLondonPackage, ESearchCase::CaseSensitive);
}

bool ValidCheckpoint(const FReflectionsCheckpoint& Checkpoint)
{
    return Checkpoint.bValid && Checkpoint.SavedAt.GetTicks() > 0 &&
        Checkpoint.MapPath.Equals(GrayLondonPackage, ESearchCase::CaseSensitive);
}

const FReflectionsSaveBlob* FindUniqueBlob(const FReflectionsCheckpoint& Checkpoint, bool& Duplicate)
{
    const FReflectionsSaveBlob* Found = nullptr;
    Duplicate = false;
    for (const FReflectionsSaveBlob& Blob : Checkpoint.SystemData)
    {
        if (Blob.System == BlobKey())
        {
            if (Found)
            {
                Duplicate = true;
                return nullptr;
            }
            Found = &Blob;
        }
    }
    return Found;
}
}

bool IsAuthorityGameWorld(UWorld* World)
{
    return AuthorityInGrayLondon(World);
}

bool BeginFresh(UWorld* World, Campaign& CampaignState)
{
    // As with restore, a fresh-run attempt after world/authority loss must
    // not leave the previous campaign visible when a valid world returns.
    // Off-thread callers may not mutate state and must retry on the game thread.
    if (!IsInGameThread()) return false;
    if (!AuthorityInGrayLondon(World))
    {
        std::uint64_t IgnoredGeneration = 0;
        CampaignState.BeginRestore(0, IgnoredGeneration);
        return false;
    }
    return CampaignState.BeginFreshCampaign();
}

bool PrepareSave(UWorld* World, const Campaign& CampaignState, FReflectionsCheckpoint& Candidate)
{
    if (!AuthorityInGrayLondon(World) || !ValidCheckpoint(Candidate)) return false;
    bool Duplicate = false;
    FindUniqueBlob(Candidate, Duplicate);
    if (Duplicate) return false;

    Checkpoint State;
    std::vector<std::uint8_t> Bytes;
    if (!CampaignState.CaptureCheckpoint(Candidate.SavedAt.GetTicks(), State) ||
        !EncodeCheckpoint(State, Bytes) || Bytes.empty() || Bytes.size() > MaxBlobBytes) return false;

    // Build a complete candidate before changing the caller's checkpoint.
    FReflectionsCheckpoint Staged = Candidate;
    FReflectionsSaveBlob* Target = nullptr;
    for (FReflectionsSaveBlob& Blob : Staged.SystemData)
    {
        if (Blob.System == BlobKey())
        {
            Target = &Blob;
            break;
        }
    }
    if (!Target)
    {
        Target = &Staged.SystemData.AddDefaulted_GetRef();
        Target->System = BlobKey();
    }
    Target->Data.Reset();
    Target->Data.Append(Bytes.data(), static_cast<int32>(Bytes.size()));
    Candidate = MoveTemp(Staged);
    return true;
}

bool PreflightLoad(UWorld* World, const FReflectionsCheckpoint& Selected, const Campaign& CampaignState)
{
    if (!AuthorityInGrayLondon(World) || !ValidCheckpoint(Selected)) return false;
    bool Duplicate = false;
    const FReflectionsSaveBlob* Blob = FindUniqueBlob(Selected, Duplicate);
    if (Duplicate || !Blob || Blob->Data.Num() <= 0 || Blob->Data.Num() > static_cast<int32>(MaxBlobBytes))
        return false;

    const uint8* Start = Blob->Data.GetData();
    const std::vector<std::uint8_t> Bytes(Start, Start + Blob->Data.Num());
    Checkpoint State;
    if (!DecodeCheckpoint(Bytes, State)) return false;

    // The existing core already validates the timestamp and complete site
    // configuration. Restore a copy so a rejection cannot change the live
    // campaign, its generation, or a previously pending request.
    Campaign ValidationState = CampaignState;
    std::uint64_t Generation = 0;
    return ValidationState.BeginRestore(Selected.SavedAt.GetTicks(), Generation) &&
        ValidationState.CompleteRestore(Generation, State, Migration::Strict);
}

bool BeginRestore(UWorld* World, const FReflectionsCheckpoint& Selected,
                  Campaign& CampaignState, std::uint64_t& Generation)
{
    Generation = 0;
    // Never mutate campaign state off the game thread. If the previous
    // authority-owned campaign outlives its world (or the world becomes a
    // client), invalidate it rather than leaving its old result visible.
    // Campaign::BeginRestore itself rejects Role::Client instances.
    if (!IsInGameThread()) return false;
    if (!AuthorityInGrayLondon(World))
    {
        CampaignState.BeginRestore(0, Generation);
        return false;
    }
    // Even a malformed selected checkpoint must invalidate previously ready
    // state rather than leave a reclaimed flag active during a failed load.
    return CampaignState.BeginRestore(ValidCheckpoint(Selected) ? Selected.SavedAt.GetTicks() : 0, Generation);
}

bool CompleteRestore(UWorld* World, const FReflectionsCheckpoint& Restored,
                     const FReflectionsCheckpoint& Selected, Campaign& CampaignState,
                     std::uint64_t Generation)
{
    if (!IsInGameThread()) return false;
    if (!AuthorityInGrayLondon(World))
    {
        // World loss cancels only this pending restore, never a newer request
        // or an already-restored campaign receiving an old callback.
        if (Generation != 0 && Generation == CampaignState.Generation() && !CampaignState.IsReady())
        {
            std::uint64_t IgnoredGeneration = 0;
            CampaignState.BeginRestore(0, IgnoredGeneration);
        }
        return false;
    }
    if (!ValidCheckpoint(Restored) || !ValidCheckpoint(Selected) ||
        Restored.SavedAt != Selected.SavedAt) return false;
    bool RestoredDuplicate = false, SelectedDuplicate = false;
    const FReflectionsSaveBlob* RestoredBlob = FindUniqueBlob(Restored, RestoredDuplicate);
    const FReflectionsSaveBlob* SelectedBlob = FindUniqueBlob(Selected, SelectedDuplicate);
    if (RestoredDuplicate || SelectedDuplicate || !RestoredBlob || !SelectedBlob ||
        RestoredBlob->Data.Num() <= 0 || RestoredBlob->Data.Num() > static_cast<int32>(MaxBlobBytes) ||
        RestoredBlob->Data != SelectedBlob->Data) return false;

    const uint8* Start = RestoredBlob->Data.GetData();
    const std::vector<std::uint8_t> Bytes(Start, Start + RestoredBlob->Data.Num());
    Checkpoint State;
    return DecodeCheckpoint(Bytes, State) && CampaignState.CompleteRestore(Generation, State);
}
}
}
