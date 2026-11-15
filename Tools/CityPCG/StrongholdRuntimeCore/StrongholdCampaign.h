#pragma once

// Pure C++ rules for a future authority-owned Gray London stronghold system.
// This file has no Unreal, networking, file I/O or NPC dependencies. The
// integration must construct it on the real server and provide server-derived
// actor, anchor and player observations; clients must not choose the role.

#include <cstdint>
#include <string>
#include <vector>

namespace GrayLondonStrongholds
{
enum class Role { Authority, Client };
enum class Stage { AwaitingCure, Holding, Reclaimed };
enum class Display { Pending, Occupied, Reclaimed };
enum class Migration { Strict, DefaultNewSitesToOccupied };

struct Point
{
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

// This ID is an explicit cooked FGuid property authored on a dedicated
// stronghold anchor. It is NOT AActor::GetActorGuid(), an editor-only value.
struct AnchorId
{
    std::string AuthoredGuid;
};

struct SiteConfig
{
    std::string Id;
    AnchorId Anchor;
    std::string PersonId;
    Point ExpectedAnchorPositionM;
    double AnchorPositionToleranceM = 0.0;
    double CureRadiusM = 0.0;
    double HoldRadiusM = 0.0;
    double VerticalToleranceM = 0.0;
    double HoldSeconds = 0.0;
};

// The server adapter must count all live dedicated anchors for this ID and
// reject aliases, dynamic proxies and ambiguous/duplicated anchor IDs.
struct AnchorObservation
{
    AnchorId Identity;
    Point Position;
    unsigned MatchingAnchorCount = 0;
    bool Loaded = false;
    bool DedicatedAnchorClass = false;
    bool LevelPlaced = false;
};

struct PlayerObservation
{
    Point Position;
    // The server adapter derives this from a live, eligible, possessed player.
    bool Eligible = false;
};

struct SiteSnapshot
{
    SiteConfig Config;
    Stage Current = Stage::AwaitingCure;
    double HeldSeconds = 0.0;
};

struct Checkpoint
{
    unsigned Schema = 1;
    // Store the exact selected FReflectionsCheckpoint::SavedAt ticks.
    std::int64_t SavedAtTicks = 0;
    std::vector<SiteSnapshot> Sites;
};

// Encode/decode the complete state for GameFlow's checkpoint-owned byte blob.
// The bounded binary format rejects truncation, corruption and extra data.
// On failure the output argument remains unchanged.
bool EncodeCheckpoint(const Checkpoint& checkpoint, std::vector<std::uint8_t>& bytes);
bool DecodeCheckpoint(const std::vector<std::uint8_t>& bytes, Checkpoint& checkpoint);

class Campaign
{
public:
    Campaign(Role role, std::vector<SiteConfig> configs);

    bool IsConfigured() const { return bConfigured; }
    bool IsReady() const { return bConfigured && bReady; }
    std::uint64_t Generation() const { return CurrentGeneration; }

    // A fresh-game signal must come from the authoritative game-flow path,
    // not an empty checkpoint or a client request.
    bool BeginFreshCampaign();

    // Enter Pending before starting checkpoint load/travel. The generation
    // returned here must accompany its eventual restoration callback.
    bool BeginRestore(std::int64_t expectedSavedAtTicks, std::uint64_t& generation);
    bool CompleteRestore(std::uint64_t generation, const Checkpoint& snapshot,
                         Migration migration = Migration::Strict);

    // The caller supplies the new checkpoint's SavedAt and serializes this
    // state into the GameFlow checkpoint's own system-data blob.
    bool CaptureCheckpoint(std::int64_t savedAtTicks, Checkpoint& snapshot) const;

    // Only call this after a real server-world cure transition. Never expose
    // it directly as an RPC accepting a client-reported cure.
    bool ConfirmCure(const std::string& site, const AnchorObservation& anchor,
                     const std::string& person, const Point& curePosition);

    // The adapter passes all eligible server-owned player observations once
    // per frame. Repeated or older frame IDs never add time a second time.
    bool TickHold(const std::string& site, const AnchorObservation& anchor,
                  const std::vector<PlayerObservation>& players,
                  std::uint64_t serverFrame, double deltaSeconds);

    Display SiteDisplay(const std::string& site) const;
    double HeldSeconds(const std::string& site) const;
    bool AllReclaimed() const;

private:
    struct Site
    {
        SiteConfig Config;
        Stage Current = Stage::AwaitingCure;
        double HeldSeconds = 0.0;
        std::uint64_t LastFrame = 0;
    };

    Site* Find(const std::string& id);
    const Site* Find(const std::string& id) const;
    bool Authorized() const { return bConfigured && Authority == Role::Authority; }

    const Role Authority;
    bool bConfigured = false;
    bool bReady = false;
    std::uint64_t CurrentGeneration = 0;
    std::int64_t ExpectedSavedAtTicks = 0;
    std::vector<Site> Sites;
};
}
