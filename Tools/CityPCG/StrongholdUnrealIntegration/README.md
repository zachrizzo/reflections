# Gray London stronghold checkpoint adapter

This is concrete native integration code held **outside `Source`** until the
GameFlow owner can review and coordinate it. It is not part of the game and
does not create a stronghold, bind itself to GameFlow, start a quest, place an
anchor, replicate site state, or show a victory UI. The campaign core has its
own tests; these adapters have not yet been compiled or tested against Unreal.

`GrayLondonStrongholdCheckpoint` uses the current `FReflectionsCheckpoint`
fields and existing campaign codec to:

- accept only game-thread operations in an authoritative Gray London game or
  PIE world, normalizing the PIE prefix and rejecting clients, editor worlds
  or another map;
- encode a ready authority campaign with the candidate's exact `SavedAt`, and
  put the bytes in a **copy** of the candidate under a unique system key;
  failures leave the input checkpoint unchanged;
- start a restore generation before applying a selected checkpoint and only
  complete it when the selected and restored callback share the same map,
  timestamp, and exact unique stronghold blob. The core also checks the saved
  configuration, checksum, schema and generation. On the game thread,
  `BeginFresh` or `BeginRestore` without a valid authoritative Gray London
  world invalidates any authority-owned campaign rather than retaining an old
  ready result. A matching pending `CompleteRestore` callback without that
  authority cancels its token, without canceling a newer request or changing an
  already-ready campaign. Calls from another thread return failure before
  inspecting the world or mutating state; the owner must suppress stale output
  and schedule invalidation on the game thread.

This is a preflight helper, not a save transaction by itself. The GameFlow
owner needs to prepare a candidate **before** `SetCheckpoint` overwrites the
current checkpoint, broadcasts `OnCheckpointSaved`, writes the autosave, or
lets `SaveToSlot` write a manual slot. A failed preflight must return failure
from the common save path and retain the previous checkpoint and slots. The
public C++ `SetCheckpoint` entry point also needs to be made transactional or
constrained so direct callers cannot bypass the preflight. Writing a blob from
the existing void `OnCheckpointSaved` callback is too late to abort.

Preflight only prevents a save when its stronghold snapshot cannot be made; it
does **not** make disk writes transactional. `WriteSave` starts an async
autosave without tracking completion or ordering. `SaveToSlot` calls
`SaveCheckpoint` before writing the requested manual/quick slot, so the
autosave may already change if that later write fails. Checkpoint listeners can
also write separate quest/lives files. A durable all-or-nothing save therefore
needs a coordinated serialized commit/recovery design across the checkpoint
and its participating systems, with actual write failures propagated. Do not
describe this adapter's preflight as a disk transaction.

An authority-owned campaign must be created from reviewed cooked site data.
The GameFlow owner must call `BeginFresh` on the actual explicit fresh-run
path, including PIE's fresh start, before the first scheduled checkpoint. For
load, Continue, Restart and Try Again, the owner must call `BeginRestore`
before replacing or applying the selected checkpoint, associate its returned
generation with that particular request, and call `CompleteRestore` when the
matching `OnCheckpointRestored` arrives. Existing `ContinueFromCheckpoint` can
apply a checkpoint immediately without travel. `OpenMap` also omits `?listen`,
so host/guest reconnect behavior remains an explicit LAN integration task.
Missing, corrupt and pre-feature saves stay pending until a deliberate migration
is designed; clients must never supply authoritative cure, hold, or save data.
`PreflightLoad` checks a selected blob's checksum, timestamp and exact reviewed
site configuration on a copy of the authority campaign, leaving the original
campaign and checkpoint untouched. It accepts a configured, not-yet-started
campaign without starting a fresh run. GameFlow's current `LoadFromSlot` stamps
the slot, restores mirrored files and replaces the active checkpoint; the owner
must wire preflight before all of those side effects and retain that exact
selection and configuration. The preflight covers stronghold data only, not
other systems' mirrored files or durable rollback. The matching restore
callback must still pass its generation and blob checks after travel. A
pre-feature save with no stronghold blob fails closed; a valid schema 1
cure-only blob remains compatible with its exact cure-site configuration.
Preflight and restore are strict only: although the
core has an explicit add-new-sites migration, this adapter does not expose or
test that policy.
The current GameFlow save/load entry points lack a multiplayer authority guard;
host ownership must cover direct callers as well as menu actions. Its world
subsystem's `EnsureController` accepts only the first local controller, so the
existing capture/apply path cannot simply be reused on a dedicated server.

The dedicated cooked anchor, server-verified defenders, zone evaluation,
nonspatial replication owner, quest/victory bridge and real LAN tests remain
unimplemented. No surveyed pilot anchor, world Z, or defender set is fabricated by
this adapter. Before runtime use, also confirm map-wide anchor uniqueness and
the tested core's build location with the owners; `StrongholdCampaign.h/.cpp`
must be available to the module without maintaining an unchecked duplicate.
The runtime module must receive only `GrayLondonStrongholdCheckpoint.h/.cpp`,
`GrayLondonStrongholdOutcome.h/.cpp`, and the chosen core files, never
`test_stubs/` or `test_checkpoint_adapter.cpp`.

## Available stronghold visuals

`ArtDirection/CityPCG/MedievalOpening/StrongholdKit/Source/` contains the
reviewed gate frame and matching occupied/reclaimed pennant GLBs. The existing
combined watch gate is a cooked-content candidate; the three split visuals are
not yet Unreal `Content` assets, placed actors, or part of the packaged game.
Run `python -B Tools/CityPCG/test_stronghold_kit.py` for their independent
geometry, pivot, material and reproducibility checks. Editor import, cooked
materials and in-game appearance still require their own coordinated review.

The kit's Trinity yard location is a survey hint, not a verified stronghold
anchor or permission to replace an existing gate. Its old `NpcCured`/`Protect`
quest example and quest-unlock visibility recipe do **not** check defenders or
contestation, and are not the defender-clear implementation described here.
For a future reviewed site, drive the pennant from the replicated authority
site state: occupied shows occupied cloth, reclaimed shows reclaimed cloth, and
pending shows neither until its state is known. Preserve the frame, existing
street clearance and collision, and validate the placement after streaming.

`test_checkpoint_adapter.cpp` compiles the **same adapter implementation**
against small Unreal-shaped test doubles, not Unreal itself. It exercises
authority and map checks, non-mutating load preflight and unchanged candidates,
strict treatment of pre-feature and added-site snapshots, schema 1 compatibility,
duplicate keys,
restore generations, same-timestamp differing blobs, corrupt data, and a
two-defended-site capture/save/restore sequence. It also covers the distinct
city-reclaimed transition, repeated observations, restore, client worlds and
off-thread calls. After a
coordinated safe test window, run from the project root:

```powershell
python -B Tools/CityPCG/StrongholdUnrealIntegration/run_tests.py
```

The runner inherits the existing shared lease/train/editor/memory guard and
its process-tree cancellation path. It does not interpret prose reservations
in the shared queue: check the queue and coordinate a genuinely unreserved
window before starting. This stand-alone test does not prove Unreal compilation,
actor streaming, save-slot persistence, or multiplayer behavior.

## Concrete gameplay hooks still required

- Create an authority-owned campaign with one cooked site definition per
  reviewed base. For defended bases choose `DefeatDefenders` and a distinct
  stable defender-set ID; cure is a separate optional condition. The server
  must account for that set and every hostile inside the hold volume, including
  unloaded or not-yet-spawned actors. Only a complete observation with no
  living defenders or contesting hostiles can open or advance that site's
  hold. `UReflectionsNpcSubsystem::GetNpcActors`, `IsHostileToPlayer` and
  `OnNpcDied` are candidate inputs, but the current death/infection broadcasts
  are world-local and do not by themselves prove server authority or complete
  streaming coverage. Coordinate with the encounter owner; do not edit the
  people system from this adapter. `GetNpcActors()` only enumerates currently
  registered weak components; `IsHostileToPlayer()` is also false when an NPC
  cannot be resolved or is incapacitated. Neither proves a defender absent or
  defeated. `UReflectionsHealthComponent::Health` starts at zero and is filled
  in `BeginPlay`, so an uninitialized or missing health component is unknown,
  not a confirmed defeat. The authority registry must retain each reviewed
  defender's spawn, alive and defeated state across streaming and restore.
  `AReflectionsSquad::GetAliveCount` likewise excludes invalid actors, while
  failed spawns are skipped and despawning resets the member list; zero does
  not prove the authored set was defeated. Gate encounter spawning until
  restore is ready. Suppress old defenders for reclaimed sites, and explicitly
  restore or deliberately reset occupied-site defenders: the current stronghold
  blob stores site stage and hold time, not individual enemy deaths.
- In the authority world, enumerate server player controllers and their
  eligible possessed pawns once per frame, convert positions to the reviewed
  absolute coordinate frame and feed `TickDefendedHold`. Never use a client's
  location, claimed kill or claimed time, and do not tick once per player.
  Validate the dedicated anchor's cooked ID, class, reviewed position and
  uniqueness. Each incomplete observation pauses progress.
- `CityOutcomeBridge::Observe` returns a separate `CityReclaimed` transition
  only on the authority game thread when the observed campaign changes from
  not reclaimed to all reclaimed within the same ready generation. It returns
  pending/in-progress/reclaimed state for publication, without touching GameFlow
  or quests. Bind and observe immediately after an explicit fresh campaign,
  before accepting captures, and again after every authoritative capture.
  Observe and publish pending immediately when restore begins or authority is
  lost; retain pending on failure, then publish the result after a successful
  restore. Before any campaign instance is replaced call `Reset` on the game
  thread. A restored or newly observed already-reclaimed campaign publishes
  reclaimed state without replaying the transition. If the owner misses the
  live transition while unbound or without authority, it sees the reclaimed
  state but no event; persisted one-time rewards and reliable delivery need
  their own idempotent integration.
- Replicate every site's pending/occupied/reclaimed state and the city outcome
  on a persistent, always-loaded authority object; streamed visuals and late
  joiners read that source. The host alone evaluates the bridge.
  The existing `UReflectionsGameFlowSubsystem::ShowVictory()` shows victory in
  its local game instance and is not a replicated LAN notification, so the
  winning result must also reach each guest before showing their UI. Its
  `OnVictory` listener in `UReflectionsQuestWorldSubsystem::HandleVictory`
  emits both `BossDefeated` and `Victory`; using it for base capture would also
  signal a boss defeat. Coordinate a distinct city-reclaimed win event or an
  intentional shared ending with the quest and GameFlow owners. Any quest
  event/unlock bridge must be coordinated with the quest owner. Re-occupation
  after a site is already reclaimed is not implemented by this core.

  `UReflectionsQuestSubsystem::NotifyEvent(TEXT("CityReclaimed"), NAME_None)`
  is a candidate host-side quest hook, but it increments active objectives and
  does not provide durable exactly-once delivery. Store/reconcile idempotent
  quest rewards with the same committed campaign outcome before reporting a
  durable win. `ShowVictory` sets `bWon`, after which `SaveToSlot` refuses a
  save. The local world-subsystem victory screen also calls `SetGamePaused` via
  `EnterMenuMode`; calling it directly neither sets `bWon` nor supplies LAN-safe
  presentation. A separate city outcome and host/guest UI path need an explicit
  save-before-terminal-state policy and multiplayer pause behavior.
