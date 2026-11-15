#include "StrongholdCampaign.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <utility>

namespace GrayLondonStrongholds
{
namespace
{
// Do not credit long gaps as continuous player presence after a server hitch.
constexpr double MaximumHoldStepSeconds = 0.25;
constexpr std::size_t MaximumSites = 256;
constexpr std::size_t MaximumIdentityBytes = 512;
constexpr std::size_t MaximumBlobBytes = 1024 * 1024;

bool ValidIdentity(const std::string& value)
{
    return !value.empty() && value.size() <= MaximumIdentityBytes &&
        std::none_of(value.begin(), value.end(), [](unsigned char c) { return c < 32 || c == 127; });
}

bool ValidAnchorId(const AnchorId& value)
{
    return value.AuthoredGuid.size() == 32 && value.AuthoredGuid.find_first_not_of('0') != std::string::npos &&
        std::all_of(value.AuthoredGuid.begin(), value.AuthoredGuid.end(), [](char c)
            { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); });
}

bool ValidPoint(const Point& value)
{
    return std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z);
}

bool ValidConfig(const SiteConfig& config)
{
    const bool validObjective =
        (config.Condition == ClearCondition::CurePerson && ValidIdentity(config.PersonId) && config.DefenderSetId.empty()) ||
        (config.Condition == ClearCondition::DefeatDefenders && config.PersonId.empty() && ValidIdentity(config.DefenderSetId));
    return ValidIdentity(config.Id) && validObjective && ValidAnchorId(config.Anchor) &&
        ValidPoint(config.ExpectedAnchorPositionM) && std::isfinite(config.AnchorPositionToleranceM) &&
        config.AnchorPositionToleranceM >= 0.0 &&
        std::isfinite(config.ObjectiveRadiusM) && config.ObjectiveRadiusM > 0.0 &&
        std::isfinite(config.HoldRadiusM) && config.HoldRadiusM > 0.0 &&
        std::isfinite(config.VerticalToleranceM) && config.VerticalToleranceM > 0.0 &&
        std::isfinite(config.HoldSeconds) && config.HoldSeconds > 0.0;
}

bool SameConfig(const SiteConfig& a, const SiteConfig& b)
{
    return a.Id == b.Id && a.Anchor.AuthoredGuid == b.Anchor.AuthoredGuid && a.PersonId == b.PersonId &&
        a.Condition == b.Condition && a.DefenderSetId == b.DefenderSetId &&
        a.ExpectedAnchorPositionM.x == b.ExpectedAnchorPositionM.x &&
        a.ExpectedAnchorPositionM.y == b.ExpectedAnchorPositionM.y &&
        a.ExpectedAnchorPositionM.z == b.ExpectedAnchorPositionM.z &&
        a.AnchorPositionToleranceM == b.AnchorPositionToleranceM &&
        a.ObjectiveRadiusM == b.ObjectiveRadiusM && a.HoldRadiusM == b.HoldRadiusM &&
        a.VerticalToleranceM == b.VerticalToleranceM && a.HoldSeconds == b.HoldSeconds;
}

bool ValidAnchor(const SiteConfig& config, const AnchorObservation& anchor)
{
    return anchor.Loaded && anchor.DedicatedAnchorClass && anchor.LevelPlaced &&
        anchor.MatchingAnchorCount == 1 && ValidPoint(anchor.Position) &&
        config.Anchor.AuthoredGuid == anchor.Identity.AuthoredGuid &&
        std::hypot(anchor.Position.x - config.ExpectedAnchorPositionM.x,
                   anchor.Position.y - config.ExpectedAnchorPositionM.y,
                   anchor.Position.z - config.ExpectedAnchorPositionM.z) <= config.AnchorPositionToleranceM;
}

bool Inside(const Point& point, const Point& center, double radius, double vertical)
{
    return ValidPoint(point) && std::hypot(point.x - center.x, point.y - center.y) <= radius &&
        std::abs(point.z - center.z) <= vertical;
}

bool DefendersCleared(const SiteConfig& config, const DefenseObservation& defense)
{
    return config.Condition == ClearCondition::DefeatDefenders && defense.EvidenceComplete &&
        defense.DefenderSetId == config.DefenderSetId && defense.LivingDefenders == 0 &&
        defense.HostilesInHoldZone == 0;
}

bool ValidSavedSite(const SiteSnapshot& entry)
{
    if (!ValidConfig(entry.Config) || !std::isfinite(entry.HeldSeconds) || entry.HeldSeconds < 0.0)
    {
        return false;
    }
    switch (entry.Current)
    {
    case Stage::AwaitingCure: return entry.HeldSeconds == 0.0;
    case Stage::Holding: return entry.HeldSeconds < entry.Config.HoldSeconds;
    case Stage::Reclaimed: return entry.HeldSeconds == entry.Config.HoldSeconds;
    }
    return false;
}

bool UniqueConfig(const SiteConfig& a, const SiteConfig& b)
{
    return a.Id != b.Id && a.Anchor.AuthoredGuid != b.Anchor.AuthoredGuid &&
        (a.Condition != ClearCondition::DefeatDefenders || b.Condition != ClearCondition::DefeatDefenders ||
         a.DefenderSetId != b.DefenderSetId);
}

bool ValidCheckpoint(const Checkpoint& checkpoint)
{
    if ((checkpoint.Schema != 1 && checkpoint.Schema != 2) || checkpoint.SavedAtTicks <= 0 || checkpoint.Sites.empty() ||
        checkpoint.Sites.size() > MaximumSites) return false;
    for (std::size_t i = 0; i < checkpoint.Sites.size(); ++i)
    {
        if (!ValidSavedSite(checkpoint.Sites[i]) ||
            (checkpoint.Schema == 1 && checkpoint.Sites[i].Config.Condition != ClearCondition::CurePerson)) return false;
        for (std::size_t j = 0; j < i; ++j)
        {
            if (!UniqueConfig(checkpoint.Sites[i].Config, checkpoint.Sites[j].Config)) return false;
        }
    }
    return true;
}

std::uint32_t Checksum(const std::vector<std::uint8_t>& bytes, std::size_t count)
{
    std::uint32_t result = 0xffffffffu;
    for (std::size_t i = 0; i < count; ++i)
    {
        result ^= bytes[i];
        for (int bit = 0; bit < 8; ++bit)
            result = (result >> 1) ^ ((result & 1u) ? 0xedb88320u : 0u);
    }
    return ~result;
}

void AppendUnsigned(std::vector<std::uint8_t>& bytes, std::uint64_t value, unsigned width)
{
    for (unsigned i = 0; i < width; ++i) bytes.push_back(static_cast<std::uint8_t>(value >> (8 * i)));
}

void AppendString(std::vector<std::uint8_t>& bytes, const std::string& value)
{
    AppendUnsigned(bytes, value.size(), 2);
    bytes.insert(bytes.end(), value.begin(), value.end());
}

void AppendDouble(std::vector<std::uint8_t>& bytes, double value)
{
    static_assert(sizeof(double) == sizeof(std::uint64_t) && std::numeric_limits<double>::is_iec559,
                  "Checkpoint format requires IEEE-754 binary64");
    std::uint64_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    AppendUnsigned(bytes, bits, 8);
}

class Reader
{
public:
    Reader(const std::vector<std::uint8_t>& source, std::size_t end) : Source(source), End(end) {}

    bool Unsigned(unsigned width, std::uint64_t& value)
    {
        if (width > 8 || Position > End || width > End - Position) return false;
        value = 0;
        for (unsigned i = 0; i < width; ++i) value |= std::uint64_t(Source[Position++]) << (8 * i);
        return true;
    }

    bool String(std::string& value)
    {
        std::uint64_t length = 0;
        if (!Unsigned(2, length) || !length || length > MaximumIdentityBytes || length > End - Position) return false;
        value.assign(reinterpret_cast<const char*>(Source.data() + Position), static_cast<std::size_t>(length));
        Position += static_cast<std::size_t>(length);
        return ValidIdentity(value);
    }

    bool Double(double& value)
    {
        std::uint64_t bits = 0;
        if (!Unsigned(8, bits)) return false;
        std::memcpy(&value, &bits, sizeof(value));
        return std::isfinite(value);
    }

    bool Finished() const { return Position == End; }

private:
    const std::vector<std::uint8_t>& Source;
    std::size_t End = 0;
    std::size_t Position = 0;
};
}

bool EncodeCheckpoint(const Checkpoint& checkpoint, std::vector<std::uint8_t>& bytes)
{
    if (!ValidCheckpoint(checkpoint)) return false;
    std::vector<std::uint8_t> result{'G', 'L', 'S', 'H'};
    AppendUnsigned(result, checkpoint.Schema, 2);
    AppendUnsigned(result, static_cast<std::uint64_t>(checkpoint.SavedAtTicks), 8);
    AppendUnsigned(result, checkpoint.Sites.size(), 2);
    for (const SiteSnapshot& entry : checkpoint.Sites)
    {
        const SiteConfig& config = entry.Config;
        AppendString(result, config.Id);
        AppendString(result, config.Anchor.AuthoredGuid);
        if (checkpoint.Schema == 1)
        {
            AppendString(result, config.PersonId);
        }
        else
        {
            AppendUnsigned(result, static_cast<unsigned>(config.Condition), 1);
            AppendString(result, config.Condition == ClearCondition::CurePerson ? config.PersonId : config.DefenderSetId);
        }
        AppendDouble(result, config.ExpectedAnchorPositionM.x);
        AppendDouble(result, config.ExpectedAnchorPositionM.y);
        AppendDouble(result, config.ExpectedAnchorPositionM.z);
        AppendDouble(result, config.AnchorPositionToleranceM);
        AppendDouble(result, config.ObjectiveRadiusM);
        AppendDouble(result, config.HoldRadiusM);
        AppendDouble(result, config.VerticalToleranceM);
        AppendDouble(result, config.HoldSeconds);
        AppendUnsigned(result, static_cast<unsigned>(entry.Current), 1);
        AppendDouble(result, entry.HeldSeconds);
    }
    if (result.size() + 4 > MaximumBlobBytes) return false;
    AppendUnsigned(result, Checksum(result, result.size()), 4);
    bytes = std::move(result);
    return true;
}

bool DecodeCheckpoint(const std::vector<std::uint8_t>& bytes, Checkpoint& checkpoint)
{
    if (bytes.size() < 4 + 2 + 8 + 2 + 4 || bytes.size() > MaximumBlobBytes) return false;
    const std::size_t payload = bytes.size() - 4;
    std::uint32_t recorded = 0;
    for (unsigned i = 0; i < 4; ++i) recorded |= std::uint32_t(bytes[payload + i]) << (8 * i);
    if (Checksum(bytes, payload) != recorded || bytes[0] != 'G' || bytes[1] != 'L' ||
        bytes[2] != 'S' || bytes[3] != 'H') return false;
    Reader reader(bytes, payload);
    std::uint64_t magic = 0, schema = 0, timestamp = 0, count = 0;
    if (!reader.Unsigned(4, magic) || !reader.Unsigned(2, schema) || !reader.Unsigned(8, timestamp) ||
        !reader.Unsigned(2, count) || (schema != 1 && schema != 2) || timestamp == 0 ||
        timestamp > static_cast<std::uint64_t>((std::numeric_limits<std::int64_t>::max)()) ||
        count == 0 || count > MaximumSites) return false;
    Checkpoint result;
    result.Schema = static_cast<unsigned>(schema);
    result.SavedAtTicks = static_cast<std::int64_t>(timestamp);
    result.Sites.reserve(static_cast<std::size_t>(count));
    for (std::uint64_t i = 0; i < count; ++i)
    {
        SiteSnapshot entry;
        SiteConfig& config = entry.Config;
        std::uint64_t stage = 0, condition = 0;
        if (!reader.String(config.Id) || !reader.String(config.Anchor.AuthoredGuid)) return false;
        if (schema == 1)
        {
            if (!reader.String(config.PersonId)) return false;
        }
        else
        {
            if (!reader.Unsigned(1, condition) || condition > static_cast<unsigned>(ClearCondition::DefeatDefenders)) return false;
            config.Condition = static_cast<ClearCondition>(condition);
            std::string& objective = config.Condition == ClearCondition::CurePerson ? config.PersonId : config.DefenderSetId;
            if (!reader.String(objective)) return false;
        }
        if (!reader.Double(config.ExpectedAnchorPositionM.x) ||
            !reader.Double(config.ExpectedAnchorPositionM.y) || !reader.Double(config.ExpectedAnchorPositionM.z) ||
            !reader.Double(config.AnchorPositionToleranceM) || !reader.Double(config.ObjectiveRadiusM) ||
            !reader.Double(config.HoldRadiusM) || !reader.Double(config.VerticalToleranceM) ||
            !reader.Double(config.HoldSeconds) || !reader.Unsigned(1, stage) ||
            stage > static_cast<unsigned>(Stage::Reclaimed) || !reader.Double(entry.HeldSeconds)) return false;
        entry.Current = static_cast<Stage>(stage);
        result.Sites.push_back(std::move(entry));
    }
    if (!reader.Finished() || !ValidCheckpoint(result)) return false;
    checkpoint = std::move(result);
    return true;
}

Campaign::Campaign(Role role, std::vector<SiteConfig> configs) : Authority(role)
{
    if (configs.empty() || configs.size() > MaximumSites) return;
    for (const SiteConfig& config : configs)
    {
        if (!ValidConfig(config) || std::any_of(Sites.begin(), Sites.end(), [&](const Site& site)
            {
                return !UniqueConfig(site.Config, config);
            }))
        {
            Sites.clear();
            return;
        }
        Sites.push_back({config});
    }
    bConfigured = true;
}

Campaign::Site* Campaign::Find(const std::string& id)
{
    auto match = std::find_if(Sites.begin(), Sites.end(), [&](const Site& site) { return site.Config.Id == id; });
    return match == Sites.end() ? nullptr : &*match;
}

const Campaign::Site* Campaign::Find(const std::string& id) const
{
    auto match = std::find_if(Sites.begin(), Sites.end(), [&](const Site& site) { return site.Config.Id == id; });
    return match == Sites.end() ? nullptr : &*match;
}

bool Campaign::BeginFreshCampaign()
{
    if (!Authorized()) return false;
    if (CurrentGeneration == (std::numeric_limits<std::uint64_t>::max)())
    {
        bReady = false;
        return false;
    }
    ++CurrentGeneration;
    for (Site& site : Sites)
    {
        site.Current = Stage::AwaitingCure;
        site.HeldSeconds = 0.0;
        site.LastFrame = 0;
    }
    ExpectedSavedAtTicks = 0;
    bReady = true;
    return true;
}

bool Campaign::BeginRestore(std::int64_t expectedSavedAtTicks, std::uint64_t& generation)
{
    if (!Authorized()) return false;
    bReady = false;
    ExpectedSavedAtTicks = 0;
    generation = 0;
    if (expectedSavedAtTicks <= 0 || CurrentGeneration == (std::numeric_limits<std::uint64_t>::max)()) return false;
    ++CurrentGeneration;
    generation = CurrentGeneration;
    ExpectedSavedAtTicks = expectedSavedAtTicks;
    return true;
}

bool Campaign::CompleteRestore(std::uint64_t generation, const Checkpoint& snapshot, Migration migration)
{
    if (!Authorized() || bReady || generation != CurrentGeneration || ExpectedSavedAtTicks <= 0 ||
        !ValidCheckpoint(snapshot) || snapshot.SavedAtTicks != ExpectedSavedAtTicks ||
        (migration != Migration::Strict && migration != Migration::DefaultNewSitesToOccupied)) return false;
    if (migration == Migration::Strict && snapshot.Sites.size() != Sites.size()) return false;
    if (snapshot.Sites.size() > Sites.size()) return false;
    std::vector<Site> restored;
    restored.reserve(Sites.size());
    for (const Site& configured : Sites)
    {
        const SiteSnapshot* found = nullptr;
        for (const SiteSnapshot& entry : snapshot.Sites)
        {
            if (entry.Config.Id != configured.Config.Id) continue;
            if (found || !ValidSavedSite(entry) || !SameConfig(entry.Config, configured.Config)) return false;
            found = &entry;
        }
        if (!found && migration == Migration::Strict) return false;
        restored.push_back({configured.Config, found ? found->Current : Stage::AwaitingCure,
                            found ? found->HeldSeconds : 0.0, 0});
    }
    // Reject unknown entries as well as duplicates, including when migrating.
    for (const SiteSnapshot& entry : snapshot.Sites)
    {
        if (!Find(entry.Config.Id)) return false;
    }
    Sites = std::move(restored);
    ExpectedSavedAtTicks = 0;
    bReady = true;
    return true;
}

bool Campaign::CaptureCheckpoint(std::int64_t savedAtTicks, Checkpoint& snapshot) const
{
    if (!Authorized() || !bReady || savedAtTicks <= 0) return false;
    Checkpoint result;
    result.SavedAtTicks = savedAtTicks;
    for (const Site& site : Sites) result.Sites.push_back({site.Config, site.Current, site.HeldSeconds});
    snapshot = std::move(result);
    return true;
}

bool Campaign::ConfirmCure(const std::string& id, const AnchorObservation& anchor,
                           const std::string& person, const Point& position)
{
    if (!Authorized() || !bReady) return false;
    Site* site = Find(id);
    if (!site || site->Config.Condition != ClearCondition::CurePerson || site->Current != Stage::AwaitingCure ||
        person != site->Config.PersonId ||
        !ValidAnchor(site->Config, anchor) ||
        !Inside(position, anchor.Position, site->Config.ObjectiveRadiusM, site->Config.VerticalToleranceM)) return false;
    site->Current = Stage::Holding;
    return true;
}

bool Campaign::ConfirmDefendersCleared(const std::string& id, const AnchorObservation& anchor,
                                       const DefenseObservation& defense)
{
    if (!Authorized() || !bReady) return false;
    Site* site = Find(id);
    if (!site || site->Current != Stage::AwaitingObjective || !ValidAnchor(site->Config, anchor) ||
        !DefendersCleared(site->Config, defense)) return false;
    site->Current = Stage::Holding;
    return true;
}

bool Campaign::TickHold(const std::string& id, const AnchorObservation& anchor,
                        const std::vector<PlayerObservation>& players,
                        std::uint64_t frame, double deltaSeconds)
{
    if (!Authorized() || !bReady) return false;
    Site* site = Find(id);
    if (!site || site->Config.Condition != ClearCondition::CurePerson) return false;
    return TickValidated(*site, anchor, players, frame, deltaSeconds, true);
}

bool Campaign::TickDefendedHold(const std::string& id, const AnchorObservation& anchor,
                                const DefenseObservation& defense, const std::vector<PlayerObservation>& players,
                                std::uint64_t frame, double deltaSeconds)
{
    if (!Authorized() || !bReady) return false;
    Site* site = Find(id);
    if (!site || site->Config.Condition != ClearCondition::DefeatDefenders) return false;
    return TickValidated(*site, anchor, players, frame, deltaSeconds, DefendersCleared(site->Config, defense));
}

bool Campaign::TickValidated(Site& site, const AnchorObservation& anchor,
                             const std::vector<PlayerObservation>& players,
                             std::uint64_t frame, double deltaSeconds, bool objectiveUncontested)
{
    if (site.Current != Stage::Holding || frame == 0 || frame <= site.LastFrame ||
        !std::isfinite(deltaSeconds) || deltaSeconds <= 0.0) return false;
    site.LastFrame = frame;
    if (!objectiveUncontested || !ValidAnchor(site.Config, anchor)) return false;
    const bool present = std::any_of(players.begin(), players.end(), [&](const PlayerObservation& player)
    {
        return player.Eligible && Inside(player.Position, anchor.Position, site.Config.HoldRadiusM,
                                         site.Config.VerticalToleranceM);
    });
    if (!present) return false;
    site.HeldSeconds = (std::min)(site.Config.HoldSeconds,
                                  site.HeldSeconds + (std::min)(deltaSeconds, MaximumHoldStepSeconds));
    if (site.HeldSeconds >= site.Config.HoldSeconds) site.Current = Stage::Reclaimed;
    return true;
}

Display Campaign::SiteDisplay(const std::string& id) const
{
    if (!bReady || !bConfigured) return Display::Pending;
    const Site* site = Find(id);
    if (!site) return Display::Pending;
    return site->Current == Stage::Reclaimed ? Display::Reclaimed : Display::Occupied;
}

double Campaign::HeldSeconds(const std::string& id) const
{
    if (!bReady || !bConfigured) return 0.0;
    const Site* site = Find(id);
    return site ? site->HeldSeconds : 0.0;
}

bool Campaign::AllReclaimed() const
{
    return Authorized() && bReady && !Sites.empty() && std::all_of(Sites.begin(), Sites.end(),
        [](const Site& site) { return site.Current == Stage::Reclaimed; });
}
}
