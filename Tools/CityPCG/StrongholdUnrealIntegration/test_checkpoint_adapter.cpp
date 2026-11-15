#include "GrayLondonStrongholdCheckpoint.h"
#include "GrayLondonStrongholdOutcome.h"
#include "Engine/World.h"
#include "GameFlow/ReflectionsGameFlowTypes.h"

#include <iostream>
#include <string>

using namespace GrayLondonStrongholds;
namespace Bridge = GrayLondonStrongholds::UnrealCheckpoint;

namespace
{
int Failures = 0;
#define CHECK(Expression) do { if (!(Expression)) { std::cerr << __LINE__ << ": " << #Expression << '\n'; ++Failures; } } while (false)
const char* GrayMap = "/Game/GrayLondon/Maps/GrayLondon_Geodata";

SiteConfig Config()
{
    return {"TrinityWatchYard", {std::string(31, '0') + 'a'}, "reviewed-person",
            {10.0, 20.0, 0.0}, 0.25, 7.0, 2.5, 2.0, 12.0};
}

FReflectionsCheckpoint Candidate(std::int64_t Ticks)
{
    FReflectionsCheckpoint Result;
    Result.bValid = true;
    Result.MapPath = FString(GrayMap);
    Result.SavedAt = FDateTime(Ticks);
    Result.Sentinel = 17;
    FReflectionsSaveBlob& Other = Result.SystemData.AddDefaulted_GetRef();
    Other.System = FName("OtherSystem");
    const uint8 Byte = 42;
    Other.Data.Append(&Byte, 1);
    return Result;
}

bool SameCheckpoint(const FReflectionsCheckpoint& A, const FReflectionsCheckpoint& B)
{
    if (A.bValid != B.bValid || !(A.MapPath == B.MapPath) || A.SavedAt != B.SavedAt ||
        A.Sentinel != B.Sentinel || A.SystemData.Num() != B.SystemData.Num()) return false;
    for (int32 Index = 0; Index < A.SystemData.Num(); ++Index)
    {
        if (!(A.SystemData[Index].System == B.SystemData[Index].System) ||
            A.SystemData[Index].Data != B.SystemData[Index].Data) return false;
    }
    return true;
}

FReflectionsSaveBlob& StrongholdBlob(FReflectionsCheckpoint& Checkpoint)
{
    for (FReflectionsSaveBlob& Blob : Checkpoint.SystemData)
    {
        if (Blob.System == FName("GrayLondonStrongholdsV1")) return Blob;
    }
    throw "test requires a stronghold blob";
}

void TestSavePreflight()
{
    UWorld Host(NM_ListenServer, FString(GrayMap));
    UWorld Client(NM_Client, FString(GrayMap));
    UWorld OtherWorld(NM_Standalone, FString("/Game/Other/Map"));
    UWorld EditorWorld(NM_Standalone, FString(GrayMap), false);
    UWorld PieHost(NM_ListenServer, FString("/Game/GrayLondon/Maps/UEDPIE_0_GrayLondon_Geodata"));
    Campaign State(Role::Authority, {Config()});
    FReflectionsCheckpoint Value = Candidate(100);
    FReflectionsCheckpoint Before = Value;

    CHECK(!Bridge::PrepareSave(&Host, State, Value) && SameCheckpoint(Value, Before));
    CHECK(!Bridge::BeginFresh(&Client, State) && !State.IsReady());
    CHECK(!Bridge::BeginFresh(&OtherWorld, State) && !State.IsReady());
    CHECK(!Bridge::BeginFresh(&EditorWorld, State) && !State.IsReady());
    CHECK(Bridge::BeginFresh(&PieHost, State) && State.IsReady());
    CHECK(!Bridge::PrepareSave(&Client, State, Value) && SameCheckpoint(Value, Before));
    CHECK(!Bridge::PrepareSave(&OtherWorld, State, Value) && SameCheckpoint(Value, Before));
    CHECK(!Bridge::PrepareSave(&EditorWorld, State, Value) && SameCheckpoint(Value, Before));
    GFakeGameThread = false;
    CHECK(!Bridge::PrepareSave(&Host, State, Value) && SameCheckpoint(Value, Before));
    GFakeGameThread = true;

    Value.MapPath = FString("/Game/Other/Map");
    Before = Value;
    CHECK(!Bridge::PrepareSave(&Host, State, Value) && SameCheckpoint(Value, Before));
    Value = Candidate(0);
    Before = Value;
    CHECK(!Bridge::PrepareSave(&Host, State, Value) && SameCheckpoint(Value, Before));
    Value = Candidate(100);
    CHECK(Bridge::PrepareSave(&Host, State, Value));
    CHECK(Value.Sentinel == 17 && Value.SystemData.Num() == 2 && Value.SystemData[0].Data.Num() == 1);

    // An existing blob is replaced exactly once and another system's data stays intact.
    CHECK(Bridge::PrepareSave(&Host, State, Value) && Value.SystemData.Num() == 2);
    FReflectionsSaveBlob& Duplicate = Value.SystemData.AddDefaulted_GetRef();
    Duplicate.System = FName("graylondonstrongholdsv1");
    Before = Value;
    CHECK(!Bridge::PrepareSave(&Host, State, Value) && SameCheckpoint(Value, Before));

    Campaign ClientState(Role::Client, {Config()});
    Value = Candidate(100);
    Before = Value;
    CHECK(!Bridge::PrepareSave(&Host, ClientState, Value) && SameCheckpoint(Value, Before));
}

void TestLoadPreflight()
{
    UWorld Host(NM_ListenServer, FString(GrayMap));
    UWorld Client(NM_Client, FString(GrayMap));
    UWorld OtherWorld(NM_Standalone, FString("/Game/Other/Map"));
    UWorld EditorWorld(NM_Standalone, FString(GrayMap), false);
    SiteConfig Site = Config();
    Site.PersonId.clear();
    Site.Condition = ClearCondition::DefeatDefenders;
    Site.DefenderSetId = "watch-yard-defenders";
    Campaign Live(Role::Authority, {Site});
    CHECK(Bridge::BeginFresh(&Host, Live));
    FReflectionsCheckpoint Selected = Candidate(100);
    CHECK(Bridge::PrepareSave(&Host, Live, Selected));
    const FReflectionsCheckpoint Before = Selected;

    // Validate an older occupied snapshot while the live campaign has moved
    // into a hold. Neither that progress nor its generation may be changed.
    const AnchorObservation Anchor{Site.Anchor, Site.ExpectedAnchorPositionM, 1, true, true, true};
    const DefenseObservation Defense{Site.DefenderSetId, 0, 0, true};
    CHECK(Live.ConfirmDefendersCleared(Site.Id, Anchor, Defense));
    CHECK(Live.TickDefendedHold(Site.Id, Anchor, Defense, {{{10.0, 20.0, 0.0}, true}}, 1, .25));
    const std::uint64_t OriginalGeneration = Live.Generation();
    CHECK(Bridge::PreflightLoad(&Host, Selected, Live));
    CHECK(Live.IsReady() && Live.Generation() == OriginalGeneration && Live.HeldSeconds(Site.Id) == .25);
    CHECK(SameCheckpoint(Selected, Before));

    // A configured, not-yet-started authority can validate a saved run without
    // silently beginning a fresh campaign or publishing the saved state.
    Campaign Cold(Role::Authority, {Site});
    CHECK(Bridge::PreflightLoad(&Host, Selected, Cold));
    CHECK(!Cold.IsReady() && Cold.Generation() == 0 && Cold.SiteDisplay(Site.Id) == Display::Pending);

    Campaign ClientState(Role::Client, {Site});
    CHECK(!Bridge::PreflightLoad(&Host, Selected, ClientState));
    CHECK(!Bridge::PreflightLoad(nullptr, Selected, Live));
    CHECK(!Bridge::PreflightLoad(&Client, Selected, Live));
    CHECK(!Bridge::PreflightLoad(&OtherWorld, Selected, Live));
    CHECK(!Bridge::PreflightLoad(&EditorWorld, Selected, Live));
    FReflectionsCheckpoint OffThreadSave = Selected;
    GFakeIsValidCalls = 0;
    GFakeGameThread = false;
    CHECK(!Bridge::PreflightLoad(&Host, Selected, Live));
    CHECK(!Bridge::PrepareSave(&Host, Live, OffThreadSave));
    CHECK(!Bridge::IsAuthorityGameWorld(&Host));
    CHECK(GFakeIsValidCalls == 0 && SameCheckpoint(OffThreadSave, Selected));
    GFakeGameThread = true;
    CHECK(Bridge::IsAuthorityGameWorld(&Host) && GFakeIsValidCalls == 1);
    CHECK(!Bridge::IsAuthorityGameWorld(nullptr) && GFakeIsValidCalls == 2);

    const FReflectionsCheckpoint Missing = Candidate(100);
    CHECK(!Bridge::PreflightLoad(&Host, Missing, Live));
    CHECK(!Bridge::PreflightLoad(&Host, Missing, Cold));
    CHECK(!Cold.IsReady() && Cold.Generation() == 0);
    FReflectionsCheckpoint Invalid = Selected;
    Invalid.bValid = false;
    CHECK(!Bridge::PreflightLoad(&Host, Invalid, Live));
    Invalid = Selected;
    Invalid.MapPath = FString("/Game/Other/Map");
    CHECK(!Bridge::PreflightLoad(&Host, Invalid, Live));
    Invalid = Selected;
    Invalid.SavedAt = FDateTime(101);
    CHECK(!Bridge::PreflightLoad(&Host, Invalid, Live));
    Invalid = Selected;
    Invalid.SavedAt = FDateTime(0);
    CHECK(!Bridge::PreflightLoad(&Host, Invalid, Live));
    Invalid = Selected;
    StrongholdBlob(Invalid).Data.Reset();
    CHECK(!Bridge::PreflightLoad(&Host, Invalid, Live));
    Invalid = Selected;
    StrongholdBlob(Invalid).Data[3] ^= 1;
    CHECK(!Bridge::PreflightLoad(&Host, Invalid, Live));
    Invalid = Selected;
    Invalid.SystemData.AddDefaulted_GetRef().System = FName("graylondonstrongholdsv1");
    CHECK(!Bridge::PreflightLoad(&Host, Invalid, Live));
    Invalid = Selected;
    std::vector<uint8> Oversized(1024 * 1024 + 1, 0);
    FReflectionsSaveBlob& OversizedBlob = StrongholdBlob(Invalid);
    OversizedBlob.Data.Reset();
    OversizedBlob.Data.Append(Oversized.data(), static_cast<int32>(Oversized.size()));
    CHECK(!Bridge::PreflightLoad(&Host, Invalid, Live));

    SiteConfig Changed = Site;
    Changed.HoldSeconds += 1.0;
    Campaign WrongConfig(Role::Authority, {Changed});
    CHECK(!Bridge::PreflightLoad(&Host, Selected, WrongConfig));
    SiteConfig Added = Site;
    Added.Id = "SecondWatchYard";
    Added.Anchor.AuthoredGuid = std::string(31, '0') + 'b';
    Added.DefenderSetId = "second-yard-defenders";
    Campaign AddedSite(Role::Authority, {Site, Added});
    CHECK(!Bridge::PreflightLoad(&Host, Selected, AddedSite));  // no implicit migration
    CHECK(!AddedSite.IsReady() && AddedSite.Generation() == 0);
    CHECK(Live.IsReady() && Live.Generation() == OriginalGeneration && Live.HeldSeconds(Site.Id) == .25);
    CHECK(SameCheckpoint(Selected, Before));

    // GLSH schema 1 is an explicitly supported cure-only blob, distinct from
    // a pre-feature save that has no stronghold blob at all.
    const SiteConfig CureSite = Config();
    Campaign CureSource(Role::Authority, {CureSite});
    CHECK(Bridge::BeginFresh(&Host, CureSource));
    Checkpoint CureSnapshot;
    CHECK(CureSource.CaptureCheckpoint(200, CureSnapshot));
    CureSnapshot.Schema = 1;
    std::vector<std::uint8_t> CureBytes;
    CHECK(EncodeCheckpoint(CureSnapshot, CureBytes));
    FReflectionsCheckpoint CureSelected = Candidate(200);
    FReflectionsSaveBlob& CureBlob = CureSelected.SystemData.AddDefaulted_GetRef();
    CureBlob.System = FName("GrayLondonStrongholdsV1");
    CureBlob.Data.Append(CureBytes.data(), static_cast<int32>(CureBytes.size()));
    Campaign ColdCure(Role::Authority, {CureSite});
    CHECK(Bridge::PreflightLoad(&Host, CureSelected, ColdCure));
    CHECK(!ColdCure.IsReady() && ColdCure.Generation() == 0);

    // Preflighting another selection cannot complete or cancel a live restore.
    std::uint64_t Generation = 0;
    CHECK(Bridge::BeginRestore(&Host, Selected, Live, Generation));
    CHECK(Bridge::PreflightLoad(&Host, Selected, Live));
    CHECK(!Bridge::PreflightLoad(&Host, Missing, Live));
    CHECK(!Live.IsReady() && Live.Generation() == Generation);
    CHECK(Bridge::CompleteRestore(&Host, Selected, Selected, Live, Generation));
    CHECK(Live.IsReady() && Live.HeldSeconds(Site.Id) == 0.0);
}

void TestRestoreAssociation()
{
    UWorld Host(NM_ListenServer, FString(GrayMap));
    const SiteConfig Site = Config();
    Campaign State(Role::Authority, {Site});
    CHECK(Bridge::BeginFresh(&Host, State));
    FReflectionsCheckpoint Occupied = Candidate(100);
    CHECK(Bridge::PrepareSave(&Host, State, Occupied));

    AnchorObservation Anchor{Site.Anchor, Site.ExpectedAnchorPositionM, 1, true, true, true};
    CHECK(State.ConfirmCure(Site.Id, Anchor, Site.PersonId, Site.ExpectedAnchorPositionM));
    FReflectionsCheckpoint Holding = Candidate(100);  // same clock tick, different state
    CHECK(Bridge::PrepareSave(&Host, State, Holding));
    std::uint64_t OldGeneration = 0, NewGeneration = 0;
    CHECK(Bridge::BeginRestore(&Host, Occupied, State, OldGeneration));
    CHECK(!State.IsReady());
    CHECK(!Bridge::CompleteRestore(&Host, Occupied, Holding, State, OldGeneration));
    CHECK(!State.IsReady());
    CHECK(Bridge::BeginRestore(&Host, Holding, State, NewGeneration));
    CHECK(NewGeneration != OldGeneration);
    CHECK(!Bridge::CompleteRestore(&Host, Holding, Holding, State, OldGeneration));
    CHECK(Bridge::CompleteRestore(&Host, Holding, Holding, State, NewGeneration));
    CHECK(State.IsReady());

    // Missing, altered, and duplicated checkpoint blobs cannot publish state.
    CHECK(Bridge::BeginRestore(&Host, Occupied, State, NewGeneration));
    FReflectionsCheckpoint Missing = Candidate(100);
    CHECK(!Bridge::CompleteRestore(&Host, Missing, Missing, State, NewGeneration));
    FReflectionsCheckpoint Damaged = Occupied;
    StrongholdBlob(Damaged).Data[3] ^= 1;
    CHECK(!Bridge::CompleteRestore(&Host, Damaged, Damaged, State, NewGeneration));
    FReflectionsCheckpoint Duplicate = Occupied;
    Duplicate.SystemData.AddDefaulted_GetRef().System = FName("GrayLondonStrongholdsV1");
    CHECK(!Bridge::CompleteRestore(&Host, Duplicate, Duplicate, State, NewGeneration));
    CHECK(!State.IsReady());
    CHECK(Bridge::CompleteRestore(&Host, Occupied, Occupied, State, NewGeneration));
    CHECK(State.IsReady());

    FReflectionsCheckpoint Invalid = Candidate(0);
    CHECK(!Bridge::BeginRestore(&Host, Invalid, State, NewGeneration));
    CHECK(!State.IsReady());
}

void TestRestoreAfterAuthorityWorldLoss()
{
    UWorld Host(NM_ListenServer, FString(GrayMap));
    UWorld Client(NM_Client, FString(GrayMap));
    UWorld OtherWorld(NM_Standalone, FString("/Game/Other/Map"));
    UWorld EditorWorld(NM_Standalone, FString(GrayMap), false);
    Campaign State(Role::Authority, {Config()});
    const FReflectionsCheckpoint Selected = Candidate(100);
    std::uint64_t Generation = 99;

    CHECK(Bridge::BeginFresh(&Host, State));
    CHECK(!Bridge::BeginRestore(nullptr, Selected, State, Generation));
    CHECK(!State.IsReady() && Generation == 0);

    CHECK(Bridge::BeginFresh(&Host, State));
    CHECK(!Bridge::BeginRestore(&OtherWorld, Selected, State, Generation));
    CHECK(!State.IsReady() && Generation == 0);

    CHECK(Bridge::BeginFresh(&Host, State));
    CHECK(!Bridge::BeginRestore(&EditorWorld, Selected, State, Generation));
    CHECK(!State.IsReady() && Generation == 0);

    CHECK(Bridge::BeginFresh(&Host, State));
    CHECK(!Bridge::BeginRestore(&Client, Selected, State, Generation));
    CHECK(!State.IsReady() && Generation == 0);

    CHECK(Bridge::BeginFresh(&Host, State));
    FReflectionsCheckpoint Saved = Candidate(100);
    CHECK(Bridge::PrepareSave(&Host, State, Saved));
    std::uint64_t OldGeneration = 0;
    CHECK(Bridge::BeginRestore(&Host, Saved, State, OldGeneration));
    CHECK(!Bridge::BeginRestore(nullptr, Saved, State, Generation));
    CHECK(!Bridge::CompleteRestore(&Host, Saved, Saved, State, OldGeneration));
    CHECK(!State.IsReady());

    // A non-game-thread call must not race or mutate the campaign; the owner
    // must reschedule invalidation on the game thread and suppress old output.
    CHECK(Bridge::BeginFresh(&Host, State));
    GFakeGameThread = false;
    CHECK(!Bridge::BeginRestore(&Host, Selected, State, Generation));
    CHECK(State.IsReady() && Generation == 0);
    GFakeGameThread = true;
    CHECK(!Bridge::BeginRestore(nullptr, Selected, State, Generation));
    CHECK(!State.IsReady());

    Campaign ClientState(Role::Client, {Config()});
    CHECK(!Bridge::BeginRestore(nullptr, Selected, ClientState, Generation));
    CHECK(!ClientState.IsReady() && ClientState.Generation() == 0 && Generation == 0);
}

void TestRestoreCallbackAfterAuthorityWorldLoss()
{
    UWorld Host(NM_ListenServer, FString(GrayMap));
    UWorld Client(NM_Client, FString(GrayMap));
    Campaign State(Role::Authority, {Config()});
    CHECK(Bridge::BeginFresh(&Host, State));
    FReflectionsCheckpoint Saved = Candidate(100);
    CHECK(Bridge::PrepareSave(&Host, State, Saved));

    std::uint64_t OldGeneration = 0, NewGeneration = 0;
    CHECK(Bridge::BeginRestore(&Host, Saved, State, OldGeneration));
    CHECK(!Bridge::CompleteRestore(nullptr, Saved, Saved, State, OldGeneration));
    CHECK(!Bridge::CompleteRestore(&Host, Saved, Saved, State, OldGeneration));
    CHECK(!State.IsReady());

    CHECK(Bridge::BeginRestore(&Host, Saved, State, OldGeneration));
    CHECK(Bridge::BeginRestore(&Host, Saved, State, NewGeneration));
    CHECK(!Bridge::CompleteRestore(&Client, Saved, Saved, State, OldGeneration));
    CHECK(Bridge::CompleteRestore(&Host, Saved, Saved, State, NewGeneration));
    CHECK(State.IsReady());
    CHECK(!Bridge::CompleteRestore(nullptr, Saved, Saved, State, NewGeneration));
    CHECK(State.IsReady());

    // An off-thread callback cannot mutate a pending request. The owner must
    // suppress output and reschedule any authority-loss invalidation.
    CHECK(Bridge::BeginRestore(&Host, Saved, State, NewGeneration));
    GFakeGameThread = false;
    CHECK(!Bridge::CompleteRestore(nullptr, Saved, Saved, State, NewGeneration));
    GFakeGameThread = true;
    CHECK(!Bridge::CompleteRestore(nullptr, Saved, Saved, State, NewGeneration));
    CHECK(!Bridge::CompleteRestore(&Host, Saved, Saved, State, NewGeneration));
    CHECK(!State.IsReady());
}

void TestFreshAfterAuthorityWorldLoss()
{
    UWorld Host(NM_ListenServer, FString(GrayMap));
    UWorld Client(NM_Client, FString(GrayMap));
    UWorld OtherWorld(NM_Standalone, FString("/Game/Other/Map"));
    UWorld EditorWorld(NM_Standalone, FString(GrayMap), false);
    Campaign State(Role::Authority, {Config()});
    CityOutcomeBridge City;

    for (UWorld* InvalidWorld : {static_cast<UWorld*>(nullptr), &Client, &OtherWorld, &EditorWorld})
    {
        CHECK(Bridge::BeginFresh(&Host, State) && State.IsReady());
        CHECK(!Bridge::BeginFresh(InvalidWorld, State));
        CHECK(!State.IsReady() && State.SiteDisplay(Config().Id) == Display::Pending);
        CHECK(City.Observe(&Host, State).State == CityOutcome::Pending);
    }

    // Invalidating a pending restore also prevents its old callback from
    // publishing state later when the Gray London authority world returns.
    CHECK(Bridge::BeginFresh(&Host, State));
    FReflectionsCheckpoint Saved = Candidate(100);
    CHECK(Bridge::PrepareSave(&Host, State, Saved));
    std::uint64_t Generation = 0;
    CHECK(Bridge::BeginRestore(&Host, Saved, State, Generation));
    CHECK(!Bridge::BeginFresh(nullptr, State));
    CHECK(!Bridge::CompleteRestore(&Host, Saved, Saved, State, Generation));
    CHECK(!State.IsReady());

    // As for restore, callers on another thread must suppress output and
    // reschedule invalidation; the adapter must not race campaign ownership.
    CHECK(Bridge::BeginFresh(&Host, State));
    GFakeGameThread = false;
    CHECK(!Bridge::BeginFresh(nullptr, State) && State.IsReady());
    GFakeGameThread = true;
    CHECK(!Bridge::BeginFresh(nullptr, State) && !State.IsReady());

    Campaign ClientState(Role::Client, {Config()});
    CHECK(!Bridge::BeginFresh(nullptr, ClientState));
    CHECK(!Bridge::BeginFresh(&Host, ClientState));
    CHECK(!ClientState.IsReady() && ClientState.Generation() == 0);
}

void TestDefendedSitesSaveAndRestore()
{
    UWorld Host(NM_ListenServer, FString(GrayMap));
    SiteConfig First = Config();
    First.PersonId.clear();
    First.Condition = ClearCondition::DefeatDefenders;
    First.DefenderSetId = "watch-yard-defenders";
    SiteConfig Second = First;
    Second.Id = "SecondWatchYard";
    Second.Anchor.AuthoredGuid = std::string(31, '0') + 'b';
    Second.DefenderSetId = "second-yard-defenders";
    Campaign State(Role::Authority, {First, Second});
    CHECK(Bridge::BeginFresh(&Host, State));

    const std::vector<PlayerObservation> Players{{{10.0, 20.0, 0.0}, true}};
    std::uint64_t Frame = 0;
    for (const SiteConfig* Site : {&First, &Second})
    {
        const AnchorObservation Anchor{Site->Anchor, Site->ExpectedAnchorPositionM, 1, true, true, true};
        const DefenseObservation Defenders{Site->DefenderSetId, 0, 0, true};
        CHECK(State.ConfirmDefendersCleared(Site->Id, Anchor, Defenders));
        for (int Step = 0; Step < 48; ++Step)
            CHECK(State.TickDefendedHold(Site->Id, Anchor, Defenders, Players, ++Frame, .25));
    }
    CHECK(State.AllReclaimed());
    FReflectionsCheckpoint Saved = Candidate(200);
    CHECK(Bridge::PrepareSave(&Host, State, Saved));
    CHECK(Bridge::BeginFresh(&Host, State) && !State.AllReclaimed());
    std::uint64_t Generation = 0;
    CHECK(Bridge::BeginRestore(&Host, Saved, State, Generation));
    CHECK(Bridge::CompleteRestore(&Host, Saved, Saved, State, Generation));
    CHECK(State.AllReclaimed());
}

void TestDistinctCityReclaimedEvent()
{
    UWorld Host(NM_ListenServer, FString(GrayMap));
    UWorld Client(NM_Client, FString(GrayMap));
    UWorld EditorWorld(NM_Standalone, FString(GrayMap), false);
    SiteConfig First = Config();
    First.PersonId.clear();
    First.Condition = ClearCondition::DefeatDefenders;
    First.DefenderSetId = "watch-yard-defenders";
    SiteConfig Second = First;
    Second.Id = "SecondWatchYard";
    Second.Anchor.AuthoredGuid = std::string(31, '0') + 'b';
    Second.DefenderSetId = "second-yard-defenders";
    Campaign State(Role::Authority, {First, Second});
    CityOutcomeBridge City;

    Campaign ClientState(Role::Client, {First, Second});
    auto Update = City.Observe(&Host, ClientState);
    CHECK(Update.State == CityOutcome::Pending && Update.Event == CityEvent::None);
    Update = City.Observe(&EditorWorld, State);
    CHECK(Update.State == CityOutcome::Pending && Update.Event == CityEvent::None);

    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::Pending && Update.Event == CityEvent::None);
    CHECK(Bridge::BeginFresh(&Host, State));
    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::InProgress && Update.Event == CityEvent::None);

    const std::vector<PlayerObservation> Players{{{10.0, 20.0, 0.0}, true}};
    std::uint64_t Frame = 0;
    auto Reclaim = [&](const SiteConfig& Site)
    {
        const AnchorObservation Anchor{Site.Anchor, Site.ExpectedAnchorPositionM, 1, true, true, true};
        const DefenseObservation Defenders{Site.DefenderSetId, 0, 0, true};
        CHECK(State.ConfirmDefendersCleared(Site.Id, Anchor, Defenders));
        for (int Step = 0; Step < 48; ++Step)
            CHECK(State.TickDefendedHold(Site.Id, Anchor, Defenders, Players, ++Frame, .25));
    };
    Reclaim(First);
    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::InProgress && Update.Event == CityEvent::None);
    Reclaim(Second);
    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::Reclaimed && Update.Event == CityEvent::CityReclaimed);
    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::Reclaimed && Update.Event == CityEvent::None);

    FReflectionsCheckpoint Saved = Candidate(300);
    CHECK(Bridge::PrepareSave(&Host, State, Saved));
    std::uint64_t Generation = 0;
    CHECK(Bridge::BeginRestore(&Host, Saved, State, Generation));
    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::Pending && Update.Event == CityEvent::None);
    CHECK(Bridge::CompleteRestore(&Host, Saved, Saved, State, Generation));
    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::Reclaimed && Update.Event == CityEvent::None);

    // A client world cannot emit an authority event. Regaining authority
    // publishes the existing state without replaying its completion.
    Update = City.Observe(&Client, State);
    CHECK(Update.State == CityOutcome::Pending && Update.Event == CityEvent::None);
    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::Reclaimed && Update.Event == CityEvent::None);

    // Off-thread observations neither emit nor mutate the baseline.
    CHECK(Bridge::BeginFresh(&Host, State));
    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::InProgress && Update.Event == CityEvent::None);
    GFakeGameThread = false;
    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::Pending && Update.Event == CityEvent::None);
    GFakeGameThread = true;
    Reclaim(First);
    Reclaim(Second);
    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::Reclaimed && Update.Event == CityEvent::CityReclaimed);

    // A newly bound bridge observes an already-won campaign as state, not a
    // fresh transition; the owner must bind before captures to receive it.
    City.Reset();
    Update = City.Observe(&Host, State);
    CHECK(Update.State == CityOutcome::Reclaimed && Update.Event == CityEvent::None);
}
}

int main()
{
    TestSavePreflight();
    TestLoadPreflight();
    TestRestoreAssociation();
    TestRestoreAfterAuthorityWorldLoss();
    TestRestoreCallbackAfterAuthorityWorldLoss();
    TestFreshAfterAuthorityWorldLoss();
    TestDefendedSitesSaveAndRestore();
    TestDistinctCityReclaimedEvent();
    if (Failures)
    {
        std::cerr << Failures << " adapter checks failed\n";
        return 1;
    }
    std::cout << "Stronghold checkpoint adapter checks passed (test doubles, not Unreal)\n";
    return 0;
}
