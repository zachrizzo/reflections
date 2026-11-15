#include "StrongholdCampaign.h"

#include <cmath>
#include <iostream>
#include <limits>
#include <vector>

using namespace GrayLondonStrongholds;

namespace
{
int Failures = 0;
#define CHECK(test) do { if (!(test)) { std::cerr << __FILE__ << ':' << __LINE__ << ": " << #test << '\n'; ++Failures; } } while (false)

SiteConfig Config(const std::string& id)
{
    return {id, {std::string(31, '0') + (id == "A" ? 'a' : id == "B" ? 'b' : 'c')},
            "person-" + id, {10.0, 20.0, 0.0}, .25, 7.0, 2.5, 2.0, 12.0};
}

AnchorObservation Marker(const SiteConfig& config)
{
    return {config.Anchor, {10.0, 20.0, 0.0}, 1, true, true, true};
}

PlayerObservation Player(double x = 10.0, double y = 20.0, double z = 0.0, bool eligible = true)
{
    return {{x, y, z}, eligible};
}

void Cure(Campaign& campaign, const SiteConfig& config)
{
    CHECK(campaign.ConfirmCure(config.Id, Marker(config), config.PersonId, {10.0, 20.0, 0.0}));
}

void HoldToCompletion(Campaign& campaign, const SiteConfig& config, std::uint64_t& frame)
{
    for (int i = 0; i < 48; ++i) CHECK(campaign.TickHold(config.Id, Marker(config), {Player()}, ++frame, 0.25));
    CHECK(campaign.SiteDisplay(config.Id) == Display::Reclaimed);
}

void TestConfigurationAndClients()
{
    const auto a = Config("A");
    auto bad = a;
    bad.HoldSeconds = std::numeric_limits<double>::quiet_NaN();
    Campaign missing(Role::Authority, {});
    Campaign invalid(Role::Authority, {bad});
    Campaign duplicate(Role::Authority, {a, a});
    auto duplicateMarker = Config("B");
    duplicateMarker.Anchor = a.Anchor;
    Campaign sharedMarker(Role::Authority, {a, duplicateMarker});
    auto duplicateGuid = Config("C");
    duplicateGuid.Anchor.AuthoredGuid = a.Anchor.AuthoredGuid;
    Campaign sharedGuid(Role::Authority, {a, duplicateGuid});
    auto zeroGuid = a; zeroGuid.Anchor.AuthoredGuid = std::string(32, '0');
    auto upperGuid = a; upperGuid.Anchor.AuthoredGuid.back() = 'A';
    Campaign zeroAnchor(Role::Authority, {zeroGuid});
    Campaign noncanonicalAnchor(Role::Authority, {upperGuid});
    CHECK(!missing.IsConfigured() && !invalid.IsConfigured() && !duplicate.IsConfigured() &&
          !sharedMarker.IsConfigured() && !sharedGuid.IsConfigured() && !zeroAnchor.IsConfigured() &&
          !noncanonicalAnchor.IsConfigured());
    CHECK(!missing.BeginFreshCampaign() && !missing.AllReclaimed());

    Campaign client(Role::Client, {a});
    std::uint64_t generation = 81;
    Checkpoint output;
    output.SavedAtTicks = 91;
    CHECK(client.IsConfigured() && !client.BeginFreshCampaign());
    CHECK(!client.BeginRestore(13, generation) && generation == 81);
    CHECK(!client.CaptureCheckpoint(13, output) && output.SavedAtTicks == 91);
    CHECK(!client.ConfirmCure(a.Id, Marker(a), a.PersonId, {10.0, 20.0, 0.0}));
    CHECK(!client.TickHold(a.Id, Marker(a), {Player()}, 1, .25));
    CHECK(client.SiteDisplay(a.Id) == Display::Pending && !client.AllReclaimed());
}

void TestAuthoritativeCureGuards()
{
    const auto a = Config("A");
    Campaign campaign(Role::Authority, {a});
    auto marker = Marker(a);
    CHECK(campaign.SiteDisplay(a.Id) == Display::Pending);
    CHECK(!campaign.ConfirmCure(a.Id, marker, a.PersonId, marker.Position));
    CHECK(campaign.BeginFreshCampaign() && campaign.SiteDisplay(a.Id) == Display::Occupied);
    CHECK(!campaign.ConfirmCure("missing", marker, a.PersonId, marker.Position));
    CHECK(!campaign.ConfirmCure(a.Id, marker, "someone-else", marker.Position));
    CHECK(!campaign.ConfirmCure(a.Id, marker, a.PersonId, {17.01, 20.0, 0.0}));
    CHECK(!campaign.ConfirmCure(a.Id, marker, a.PersonId, {10.0, 20.0, 2.01}));
    CHECK(!campaign.ConfirmCure(a.Id, marker, a.PersonId,
                               {std::numeric_limits<double>::quiet_NaN(), 20.0, 0.0}));
    marker.Loaded = false;
    CHECK(!campaign.ConfirmCure(a.Id, marker, a.PersonId, {10.0, 20.0, 0.0}));
    marker = Marker(a); marker.DedicatedAnchorClass = false;
    CHECK(!campaign.ConfirmCure(a.Id, marker, a.PersonId, {10.0, 20.0, 0.0}));
    marker = Marker(a); marker.LevelPlaced = false;
    CHECK(!campaign.ConfirmCure(a.Id, marker, a.PersonId, {10.0, 20.0, 0.0}));
    marker = Marker(a); marker.MatchingAnchorCount = 2;
    CHECK(!campaign.ConfirmCure(a.Id, marker, a.PersonId, {10.0, 20.0, 0.0}));
    marker = Marker(a); marker.Identity.AuthoredGuid = Config("B").Anchor.AuthoredGuid;
    CHECK(!campaign.ConfirmCure(a.Id, marker, a.PersonId, {10.0, 20.0, 0.0}));
    marker = Marker(a); marker.Position.x += .26;
    CHECK(!campaign.ConfirmCure(a.Id, marker, a.PersonId, {10.0, 20.0, 0.0}));
    marker = Marker(a); marker.Position.z = std::numeric_limits<double>::infinity();
    CHECK(!campaign.ConfirmCure(a.Id, marker, a.PersonId, {10.0, 20.0, 0.0}));
    CHECK(campaign.ConfirmCure(a.Id, Marker(a), a.PersonId, {17.0, 20.0, 2.0}));
    CHECK(!campaign.ConfirmCure(a.Id, Marker(a), a.PersonId, {10.0, 20.0, 0.0}));
}

void TestHoldingAndVictory()
{
    const auto a = Config("A"), b = Config("B");
    Campaign campaign(Role::Authority, {a, b});
    CHECK(campaign.BeginFreshCampaign());
    CHECK(!campaign.TickHold(a.Id, Marker(a), {Player()}, 1, .25));
    Cure(campaign, a);
    CHECK(!campaign.TickHold(a.Id, Marker(a), {}, 1, .25));
    CHECK(!campaign.TickHold(a.Id, Marker(a), {Player(10.0, 20.0, 0.0, false)}, 2, .25));
    CHECK(!campaign.TickHold(a.Id, Marker(a), {Player(12.51, 20.0)}, 3, .25));
    CHECK(!campaign.TickHold(a.Id, Marker(a), {Player(10.0, 20.0, 2.01)}, 4, .25));
    auto missing = Marker(a); missing.Loaded = false;
    CHECK(!campaign.TickHold(a.Id, missing, {Player()}, 5, .25));
    CHECK(!campaign.TickHold(a.Id, Marker(a), {Player()}, 0, .25));
    CHECK(!campaign.TickHold(a.Id, Marker(a), {Player()}, 6, std::numeric_limits<double>::quiet_NaN()));
    CHECK(campaign.TickHold(a.Id, Marker(a), {Player(), Player()}, 6, 3.0));
    CHECK(campaign.HeldSeconds(a.Id) == .25);  // one frame, hitch capped
    CHECK(!campaign.TickHold(a.Id, Marker(a), {Player()}, 6, .25));
    CHECK(!campaign.TickHold(a.Id, Marker(a), {Player()}, 5, .25));
    CHECK(campaign.HeldSeconds(a.Id) == .25);
    std::uint64_t frame = 6;
    for (int i = 0; i < 47; ++i) CHECK(campaign.TickHold(a.Id, Marker(a), {Player()}, ++frame, .25));
    CHECK(campaign.SiteDisplay(a.Id) == Display::Reclaimed && !campaign.AllReclaimed());
    CHECK(!campaign.TickHold(a.Id, Marker(a), {Player()}, ++frame, .25));
    Cure(campaign, b);
    HoldToCompletion(campaign, b, frame);
    CHECK(campaign.AllReclaimed());
}

void TestCheckpointAndRollback()
{
    const auto a = Config("A"), b = Config("B");
    Campaign campaign(Role::Authority, {a, b});
    CHECK(campaign.BeginFreshCampaign());
    Checkpoint empty;
    CHECK(campaign.CaptureCheckpoint(100, empty));
    Cure(campaign, a);
    std::uint64_t frame = 0;
    HoldToCompletion(campaign, a, frame);
    Cure(campaign, b);
    CHECK(campaign.TickHold(b.Id, Marker(b), {Player()}, ++frame, .25));
    Checkpoint partial;
    CHECK(campaign.CaptureCheckpoint(200, partial));

    std::uint64_t oldGeneration = 0, generation = 0;
    CHECK(campaign.BeginRestore(100, oldGeneration));
    CHECK(campaign.SiteDisplay(a.Id) == Display::Pending && !campaign.AllReclaimed());
    CHECK(!campaign.CaptureCheckpoint(300, empty));
    CHECK(!campaign.ConfirmCure(a.Id, Marker(a), a.PersonId, {10.0, 20.0, 0.0}));
    CHECK(campaign.BeginRestore(200, generation) && generation != oldGeneration);
    CHECK(!campaign.CompleteRestore(oldGeneration, partial));
    auto wrong = partial; wrong.SavedAtTicks = 201;
    CHECK(!campaign.CompleteRestore(generation, wrong));
    wrong = partial; wrong.Schema = 99;
    CHECK(!campaign.CompleteRestore(generation, wrong));
    wrong = partial; wrong.Sites[0].Config.PersonId = "different";
    CHECK(!campaign.CompleteRestore(generation, wrong));
    wrong = partial; wrong.Sites[1].HeldSeconds = std::numeric_limits<double>::infinity();
    CHECK(!campaign.CompleteRestore(generation, wrong));
    wrong = partial; wrong.Sites[1].Current = Stage::Reclaimed;
    CHECK(!campaign.CompleteRestore(generation, wrong));
    wrong = partial; wrong.Sites[1] = wrong.Sites[0];
    CHECK(!campaign.CompleteRestore(generation, wrong));
    CHECK(campaign.SiteDisplay(a.Id) == Display::Pending);
    CHECK(campaign.CompleteRestore(generation, partial));
    CHECK(campaign.SiteDisplay(a.Id) == Display::Reclaimed && campaign.SiteDisplay(b.Id) == Display::Occupied);
    CHECK(campaign.HeldSeconds(b.Id) == .25 && !campaign.AllReclaimed());
    CHECK(!campaign.CompleteRestore(generation, partial));

    CHECK(campaign.BeginRestore(100, generation));
    CHECK(campaign.CompleteRestore(generation, empty));
    CHECK(campaign.SiteDisplay(a.Id) == Display::Occupied && campaign.HeldSeconds(a.Id) == 0.0);
    CHECK(!campaign.BeginRestore(0, generation));
    CHECK(campaign.SiteDisplay(a.Id) == Display::Pending && !campaign.AllReclaimed());
}

void TestAddingSitesToExistingSave()
{
    const auto a = Config("A"), b = Config("B");
    Campaign before(Role::Authority, {a});
    CHECK(before.BeginFreshCampaign());
    Cure(before, a);
    std::uint64_t frame = 0;
    HoldToCompletion(before, a, frame);
    Checkpoint old;
    CHECK(before.CaptureCheckpoint(1000, old));

    Campaign after(Role::Authority, {a, b});
    std::uint64_t generation = 0;
    CHECK(after.BeginRestore(1000, generation));
    CHECK(!after.CompleteRestore(generation, old));
    CHECK(after.SiteDisplay(a.Id) == Display::Pending);
    CHECK(after.CompleteRestore(generation, old, Migration::DefaultNewSitesToOccupied));
    CHECK(after.SiteDisplay(a.Id) == Display::Reclaimed && after.SiteDisplay(b.Id) == Display::Occupied);
    CHECK(!after.AllReclaimed());

    CHECK(after.BeginRestore(1000, generation));
    auto unknown = old; unknown.Sites[0].Config.Id = "unknown";
    CHECK(!after.CompleteRestore(generation, unknown, Migration::DefaultNewSitesToOccupied));
    CHECK(after.SiteDisplay(a.Id) == Display::Pending);
    auto empty = old; empty.Sites.clear();
    CHECK(!after.CompleteRestore(generation, empty, Migration::DefaultNewSitesToOccupied));
    CHECK(after.SiteDisplay(a.Id) == Display::Pending);
}

void RewriteChecksum(std::vector<std::uint8_t>& bytes)
{
    std::uint32_t crc = 0xffffffffu;
    for (std::size_t i = 0; i + 4 < bytes.size(); ++i)
    {
        crc ^= bytes[i];
        for (int bit = 0; bit < 8; ++bit) crc = (crc & 1u) ? ((crc >> 1) ^ 0xedb88320u) : (crc >> 1);
    }
    crc = ~crc;
    for (int i = 0; i < 4; ++i) bytes[bytes.size() - 4 + i] = static_cast<std::uint8_t>(crc >> (i * 8));
}

void TestWireCompatibility()
{
    // Independently encoded with Python struct ('<HQH', '<8d', '<Bd') and zlib.crc32.
    const std::vector<std::uint8_t> expected = {
        0x47, 0x4c, 0x53, 0x48, 0x01, 0x00, 0x15, 0xcd, 0x5b, 0x07, 0x00, 0x00,
        0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x41, 0x20, 0x00, 0x30, 0x30, 0x30,
        0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30,
        0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30,
        0x30, 0x30, 0x30, 0x30, 0x61, 0x08, 0x00, 0x70, 0x65, 0x72, 0x73, 0x6f,
        0x6e, 0x2d, 0x41, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x24, 0x40, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x34, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xd0, 0x3f, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x1c, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x04, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x40, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x28, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0xa0, 0xb0, 0xb5, 0xfb,
    };
    Campaign campaign(Role::Authority, {Config("A")});
    CHECK(campaign.BeginFreshCampaign());
    Checkpoint snapshot;
    CHECK(campaign.CaptureCheckpoint(123456789, snapshot));
    std::vector<std::uint8_t> bytes;
    CHECK(EncodeCheckpoint(snapshot, bytes) && bytes == expected);
    Checkpoint parsed;
    CHECK(DecodeCheckpoint(expected, parsed) && parsed.SavedAtTicks == 123456789);
}

void TestCheckpointCodec()
{
    const auto a = Config("A"), b = Config("B");
    Campaign source(Role::Authority, {a, b});
    CHECK(source.BeginFreshCampaign());
    Cure(source, a);
    std::uint64_t frame = 0;
    HoldToCompletion(source, a, frame);
    Cure(source, b);
    CHECK(source.TickHold(b.Id, Marker(b), {Player()}, ++frame, .25));
    Checkpoint snapshot;
    CHECK(source.CaptureCheckpoint(123456789, snapshot));
    std::vector<std::uint8_t> bytes{9, 8, 7};
    CHECK(EncodeCheckpoint(snapshot, bytes));
    CHECK(bytes.size() > 32 && bytes[0] == 'G' && bytes[1] == 'L' && bytes[2] == 'S' && bytes[3] == 'H');
    Checkpoint decoded;
    CHECK(DecodeCheckpoint(bytes, decoded));
    CHECK(decoded.SavedAtTicks == 123456789 && decoded.Sites.size() == 2);
    CHECK(decoded.Sites[0].Current == Stage::Reclaimed && decoded.Sites[1].HeldSeconds == .25);
    Campaign restored(Role::Authority, {a, b});
    std::uint64_t generation = 0;
    CHECK(restored.BeginRestore(123456789, generation));
    CHECK(restored.CompleteRestore(generation, decoded));
    CHECK(restored.SiteDisplay(a.Id) == Display::Reclaimed && restored.HeldSeconds(b.Id) == .25);

    auto badSnapshot = snapshot;
    badSnapshot.Sites[1].Config = badSnapshot.Sites[0].Config;
    std::vector<std::uint8_t> unchanged{1, 2, 3};
    CHECK(!EncodeCheckpoint(badSnapshot, unchanged) && unchanged == std::vector<std::uint8_t>({1, 2, 3}));
    badSnapshot = snapshot;
    badSnapshot.Sites[1].Current = Stage::AwaitingCure;
    CHECK(!EncodeCheckpoint(badSnapshot, unchanged) && unchanged == std::vector<std::uint8_t>({1, 2, 3}));
    badSnapshot = snapshot;
    badSnapshot.Sites[0].Config.PersonId = std::string("bad\0id", 6);
    CHECK(!EncodeCheckpoint(badSnapshot, unchanged));

    auto expectRejected = [](const std::vector<std::uint8_t>& invalid)
    {
        Checkpoint output;
        output.SavedAtTicks = 777;
        CHECK(!DecodeCheckpoint(invalid, output) && output.SavedAtTicks == 777);
    };
    for (std::size_t length = 0; length < bytes.size(); ++length)
        expectRejected(std::vector<std::uint8_t>(bytes.begin(), bytes.begin() + length));
    auto invalid = bytes; invalid[20] ^= 1; expectRejected(invalid);  // bad checksum
    invalid = bytes; invalid[0] = 'X'; RewriteChecksum(invalid); expectRejected(invalid);
    invalid = bytes; invalid[4] = 2; RewriteChecksum(invalid); expectRejected(invalid);  // schema
    invalid = bytes; for (int i = 6; i < 14; ++i) invalid[i] = 0;
    RewriteChecksum(invalid); expectRejected(invalid);  // invalid SavedAt
    invalid = bytes; invalid[14] = 0xff; invalid[15] = 0xff;
    RewriteChecksum(invalid); expectRejected(invalid);  // excessive site count
    invalid = bytes; invalid[16] = 0xff; invalid[17] = 0xff;
    RewriteChecksum(invalid); expectRejected(invalid);  // excessive string length
    invalid = bytes; invalid[18] = 0;
    RewriteChecksum(invalid); expectRejected(invalid);  // embedded NUL
    invalid = bytes; invalid.insert(invalid.end() - 4, 0x42);
    RewriteChecksum(invalid); expectRejected(invalid);  // extra payload bytes
}
}

int main()
{
    TestConfigurationAndClients();
    TestAuthoritativeCureGuards();
    TestHoldingAndVictory();
    TestCheckpointAndRollback();
    TestAddingSitesToExistingSave();
    TestWireCompatibility();
    TestCheckpointCodec();
    if (Failures)
    {
        std::cerr << Failures << " stronghold checks failed\n";
        return 1;
    }
    std::cout << "Stronghold authority, identity, hold, checkpoint and migration checks passed\n";
    return 0;
}
