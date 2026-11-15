# Stronghold campaign rules

This C++17 core is an isolated, testable foundation for reclaiming multiple
Gray London sites. It is **not** compiled into Unreal, connected to NPCs or
quests, placed in the map, replicated, or part of the packaged game yet.

The core has explicit authority/client roles, a pending state while restoring,
strict authored-anchor identity, a defended-site objective and a separate
reviewed-person cure objective. The hold counts at most once per server frame
while an eligible player is inside. `AllReclaimed` is true only when every
configured site is reclaimed. A
defended site's hold pauses if a defender or hostile contests it, or if the
server cannot prove that its defender and zone observations are complete. It
keeps partial hold progress and uses bounded, checksummed checkpoint data.
Restore validates the exact checkpoint timestamp, site identities and all
configuration values before changing state. New sites can be added to a
matching older blob only through the explicit migration option; an absent,
empty, corrupt or mismatched blob stays pending. A maximum 0.25 s is credited
per server update so a server hitch does not count as continuous presence.

## Integration contract

- The actual server constructs the authority instance; clients cannot choose
  their role or send defense, cure, marker, time or player-location claims
  directly. For defended sites, `ConfirmDefendersCleared` and each
  `TickDefendedHold` require the reviewed defender-set ID, complete evidence,
  zero living set members, and zero hostile occupants. Unknown or unloaded
  evidence must report incomplete. Do not treat the absence of loaded actors
  as proof of an empty site. The observer must track the full reviewed set,
  dynamic hostiles, its scan/hold zones, vertical extent and streaming state
  on the server. For optional cure sites, `ConfirmCure` must only receive a
  real server-world infected-to-cured transition for the configured Person ID.
- Add a dedicated, level-placed stronghold anchor actor with an explicit
  `FGuid` `UPROPERTY` that is saved and cooked as authored data. Configure
  each site with that GUID in lowercase 32-digit form and its surveyed world
  position. `AActor::GetActorGuid()` and its external actor descriptor are
  editor-only and must **not** be used as the cooked runtime identity. The
  adapter checks the dedicated actor class, the cooked ID, position tolerance
  and exactly one loaded matching anchor, rather than adopting a story marker.
  Convert site, defender-set and person names using the same canonical UTF-8
  spelling on save and restore; GUIDs use lowercase digits without punctuation.
  The core compares these strings byte-for-byte. If the Unreal manifest uses
  `FName`, also reject case-insensitive `FName` duplicates before constructing
  the core and preserve one canonical spelling throughout the adapter.
  Keep the first anchor always loaded and verify its unique ID in the whole
  source map before cooking; loaded-actor checks alone cannot detect a second
  copy in an unloaded cell. For city-scale spatial anchors, ship and validate
  a complete authored site/anchor manifest before enabling the system.
- The adapter must derive player eligibility, possession and positions from
  the server and convert Unreal centimetres to metres in the same absolute
  coordinate frame as the reviewed anchor positions. Handle world-origin
  rebasing explicitly if it is enabled. Pass a monotonically increasing
  server frame number and the complete eligible-player list once per site;
  do not tick once per pawn. A vertical tolerance also prevents events on
  another floor from counting.
- Coordinate a **save preflight** with the GameFlow owner before enabling this
  system. `CaptureCheckpoint` creates a new checkpoint with an empty
  `SystemData`; `SetCheckpoint` then replaces the selected checkpoint, fires a
  void `OnCheckpointSaved` event and writes the result. A listener cannot veto
  that write. Merely skipping `SetSaveData` while pending would therefore
  overwrite the autosave (and possibly a manual slot) without this progress.
  Capture and encode a frozen stronghold snapshot using the candidate
  checkpoint's `SavedAt.GetTicks()` *before* replacing the current checkpoint
  or writing any slot. If the campaign is pending, the snapshot is unavailable,
  or encoding fails, abort the whole save with a visible failure and leave the
  previous checkpoint and slots intact. A transaction or equivalent API must
  also cover direct calls to `SetCheckpoint`, not only the save-menu buttons.
  Place the prepared blob under a dedicated key in the candidate checkpoint;
  do not substitute stale state or let a client write it.
- On `OnCheckpointRestored`, require the callback checkpoint and the subsystem's
  selected checkpoint to have the same `SavedAt`; retrieve the blob, decode it,
  and complete the matching restore generation. The adapter must associate the
  generation with the actual load request, including the in-place Continue
  path; obtaining the latest generation only when the callback fires cannot
  distinguish a stale callback. A missing or corrupt blob remains pending until
  an explicitly designed legacy migration.
- Invalidate state **before** a load starts, and call `BeginFreshCampaign` only
  from an explicit authoritative New Game/fresh-run hook. Existing GameFlow
  has no such general callback, and `ClearCheckpoint` also supports deleting a
  save; absence of a checkpoint is not sufficient evidence of a fresh run.
- A persistent replicated authority object must distribute each site's pending,
  occupied or reclaimed state to all clients, including late joiners and
  streamed-in visuals. Bind objective completion and the existing win flow to
  the authority's state; neither action is implemented by this pure core.
- GameFlow's present `OpenLevel` path does not specify `?listen`. Test host
  rehosting and guest reconnect when loading, and add a coordinated LAN travel
  path if players should remain connected. Dedicated-server restore also needs
  a flow that does not require the first local pawn.
- Restrict the subsystem and every supplied observation to the actual
  `/Game/GrayLondon/Maps/GrayLondon_Geodata` world, normalizing PIE prefixes.
  Do not infer the world from a marker name. The core itself has no map field
  and depends on the adapter for this check.

`OnCheckpointSaved` is broadcast after GameFlow installs the new checkpoint
and before it writes the save. `OnCheckpointRestored` fires after the pawn and
world progress are restored. The pure codec's CRC detects accidental damaged
bytes; it is not a cryptographic signature against a malicious save editor.
See `Tools/CityPCG/StrongholdReclaimPrototype/README.md` for the previous
quest-backed gate review and marker/network constraints.

The `GLSH` blob uses little-endian integers and IEEE-754 binary64 values:
magic, 16-bit schema, 64-bit checkpoint ticks, 16-bit site count, then each
site's length-prefixed ID and anchor GUID. Schema 1 stores a cure-person ID;
schema 2 stores an objective-mode byte and its person or defender-set ID.
Both then store anchor position/tolerance and objective parameters, stage
byte and held seconds, followed by a CRC-32. New captures use schema 2. The
decoder and encoder retain schema-1 compatibility for cure-only sites; schema
1 refuses defended sites rather than losing their objective mode.
The decoder rejects an unknown schema, trailing bytes, invalid state/config,
non-finite values, duplicate IDs, more than 256 sites and blobs over 1 MiB.
An independently generated Python `struct`/`zlib` fixture checks this wire
format in the standalone test.

## Tests

Status: the earlier cure-only standalone core passed with MSVC C++17 on 15
November 2026. The subsequent defender-clear mode and schema-2 changes have
**not yet been compiled or run**. The v1 and v2 wire fixtures have separate
independent Python checks. Neither version is integrated into Unreal gameplay
or tested in LAN.

From the project root, run `python Tools/CityPCG/StrongholdRuntimeCore/run_tests.py`.
The Windows runner finds the installed Visual Studio x64 compiler, requires a
free shared editor lock and finished build train, checks for at least 4 GiB
physical and 10 GiB commit headroom, compiles only these two small C++ files
with warnings treated as errors, and writes artifacts to a new
directory under `Saved`. Its newer Windows job-based cancellation path has
passed fake-child tests but has not yet been exercised with a real compiler
process. The checks cover client isolation, anchor/person and
vertical matching, co-op hold timing, victory, restore generations, rollback,
explicit site migration, and damaged or malformed checkpoint bytes. They do
not replace Unreal automation, multiplayer, cook or gameplay testing.

The train-status guard can be checked without compiling C++:
`python -B -m unittest discover -s Tools/CityPCG/StrongholdRuntimeCore -p test_runner_guard.py`.
The independently encoded C++ wire-format fixture can also be checked without
compiling: `python -B -m unittest discover -s Tools/CityPCG/StrongholdRuntimeCore -p test_checkpoint_fixture.py`.
This validates the fixture only, not the C++ encoder or decoder.
