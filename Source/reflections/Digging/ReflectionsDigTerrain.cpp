#include "Digging/ReflectionsDigTerrain.h"

#include "CoreMinimal.h"
#include "AI/Navigation/NavDataGatheringMode.h"
#include "AI/Navigation/NavigationTypes.h"
#include "AI/NavigationSystemBase.h"
#include "AI/NavigationSystemHelpers.h"
#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Digging/ReflectionsDigMesher.h"
#include "Digging/ReflectionsDigPieces.h"
#include "Digging/ReflectionsDigSubsystem.h"
#include "Digging/ReflectionsDigTypes.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "Engine/CollisionProfile.h"
#include "Engine/EngineTypes.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Misc/ScopeExit.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"
#include "PhysicsEngine/BodySetup.h"

DEFINE_LOG_CATEGORY(LogReflectionsDigTerrain);

using UE::Geometry::FDynamicMesh3;

/*
 * Collision swap. A chunk's pieces sit in eight slots, one per block (its octants, ReflectionsDig::BlocksPerChunk),
 * each with the hash of the mesh it shows. A slot can also hold a retiring piece, hidden but still colliding. The
 * retiring pieces whose block shows a new piece form the chunk's retiring set; it waits for the current pieces of the
 * blocks the commits that made it changed (SwapWaitMask). The subsystem commits a chunk only when none of its current
 * pieces is cooking (one cook at a time per chunk), so every cook finishes and the engine never aborts one. The rules
 * below still hold for a direct CommitChunk call, which may land while a cook runs, and after a failed cook.
 * - A commit touches only the slots whose new hash differs from the one they show (or whose piece's newest cook
 *   failed, so it does not collide with the mesh it shows). Every other slot keeps its component as it is: no new
 *   mesh, no cook, no navigation update. A commit that changes no slot does nothing at all.
 * - A commit that changes one slot with a piece before and after reuses that component. With deferred, async
 *   collision the engine keeps its body in the scene until FinishPhysicsAsyncCook swaps the new one in.
 * - Any other commit replaces the changed slots' pieces, as one set. Whether the current pieces the retiring set
 *   waits for are the newest collision that really exists is decided at commit time from the pieces' own cook state:
 *   if every one has collision of its own (a finished, successful cook; a reused piece still cooking keeps its older
 *   body), the retiring set is destroyed and the changed slots' pieces retire; otherwise the changed slots' pieces
 *   among those it waits for are destroyed and the retiring set stays, now waiting for the new pieces as well. A
 *   changed slot's piece the retiring set does not wait for always retires: it is the only collision that block has.
 *   With no retiring set the changed pieces always retire. Through the subsystem the second case arises only after a
 *   failed cook.
 * - A retiring set replaced by pieces goes, all together, once every piece it waits for has finished cooking
 *   successfully: until then it covers the blocks the commit changed as they were (a pit's new floor in a block that
 *   had no piece is waited for by the old ground above it). A failed cook keeps it, with one warning. The subsystem
 *   checks this at the start of each tick, before the commits, and again after the launches; a commit that reuses a
 *   slot's piece checks its own chunk first.
 * - A retiring piece whose block now shows nothing (the block became all solid or all air) goes only when the whole
 *   terrain is quiet: a neighbouring block may still be showing the old hole into this one.
 * - Navigation follows the collision, not the mesh: a current piece asks for one navigation update per cook that
 *   brings its new body in (a failed cook asks for nothing), a set leaves navigation as it retires, and a destroyed
 *   piece leaves through the engine's unregister. A new piece does not count for navigation until its first cook is
 *   in; that cook adds it. A retiring set kept by a failed cook is the chunk's only collision, so it gets its
 *   navigation back once, until the next commit puts a new set in front of it or it is destroyed. Each piece carries
 *   that state itself (UReflectionsDigChunkComponent::CountsForNavigation). The safety floor never affects navigation.
 * - Navigation never reads a piece's body setup: it exports the triangles of the piece's collision, built on the
 *   worker with its mesh. Reading the body would have the navigation tick build a body that has no physics meshes yet
 *   on the game thread, while the background cook builds the same data.
 */

namespace
{
    /** The ground surface lies this far below the top of the grid. */
    constexpr float GroundBelowGridTopCm = 400.0f;
    /** The safety floor's top lies this far below the grid floor, and it is this thick. */
    constexpr float SafetyFloorGapCm = 30.0f;
    constexpr float SafetyFloorThicknessCm = 100.0f;
    /** What the pieces draw with when GroundMaterial is null. */
    const TCHAR* const PlainGroundMaterialPath = TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial");

    double MillisecondsSince(double StartSeconds)
    {
        return (FPlatformTime::Seconds() - StartSeconds) * 1000.0;
    }

    constexpr int32 NumBlocks = ReflectionsDig::BlocksPerChunk;
    constexpr uint8 AllBlocks = 0xFF;
    static_assert(NumBlocks == 8, "A block mask is one byte");
    using FPieceSlots = TObjectPtr<UReflectionsDigChunkComponent>[NumBlocks];

    constexpr uint8 BlockBit(int32 Block)
    {
        return static_cast<uint8>(1u << Block);
    }

    void DestroyPiece(TObjectPtr<UReflectionsDigChunkComponent>& Piece)
    {
        if (Piece != nullptr)
        {
            Piece->DestroyComponent();
        }
        Piece = nullptr;
    }

    /** Destroys the pieces of the slots in Mask; returns how many there were. */
    int32 DestroyPieces(FPieceSlots& Slots, uint8 Mask = AllBlocks)
    {
        int32 Destroyed = 0;
        for (int32 Block = 0; Block < NumBlocks; ++Block)
        {
            if ((Mask & BlockBit(Block)) != 0 && Slots[Block] != nullptr)
            {
                DestroyPiece(Slots[Block]);
                ++Destroyed;
            }
        }
        return Destroyed;
    }

    /** True if a piece in a slot of Mask passes Test. Empty slots never do. */
    template <typename FTest>
    bool AnyPiece(const FPieceSlots& Slots, uint8 Mask, FTest Test)
    {
        for (int32 Block = 0; Block < NumBlocks; ++Block)
        {
            if ((Mask & BlockBit(Block)) != 0 && Slots[Block] != nullptr && Test(*Slots[Block]))
            {
                return true;
            }
        }
        return false;
    }

    /** The slots that hold a piece. */
    uint8 FilledBlocks(const FPieceSlots& Slots)
    {
        uint8 Mask = 0;
        for (int32 Block = 0; Block < NumBlocks; ++Block)
        {
            Mask |= Slots[Block] != nullptr ? BlockBit(Block) : 0;
        }
        return Mask;
    }

    bool AnyCookPending(const FPieceSlots& Slots, uint8 Mask = AllBlocks)
    {
        return AnyPiece(Slots, Mask, [](const UReflectionsDigChunkComponent& Piece) { return Piece.IsCollisionCookPending(); });
    }

    bool AnyCookFailed(const FPieceSlots& Slots, uint8 Mask = AllBlocks)
    {
        return AnyPiece(Slots, Mask, [](const UReflectionsDigChunkComponent& Piece) { return Piece.DidLastCookFail(); });
    }

    /** Every piece in a slot of Mask has collision of its own (empty slots are skipped). */
    bool AllHaveCollision(const FPieceSlots& Slots, uint8 Mask = AllBlocks)
    {
        return !AnyPiece(Slots, Mask, [](const UReflectionsDigChunkComponent& Piece) { return !Piece.HasCollision(); });
    }

    /** Blocks whose retiring piece stands behind a current piece: the chunk's retiring set. */
    uint8 ReplacedBlocks(const FReflectionsDigTerrainChunk& State)
    {
        return FilledBlocks(State.Retiring) & FilledBlocks(State.Pieces);
    }

    /** Blocks whose retiring piece stands behind nothing: the block was emptied. */
    uint8 EmptiedBlocks(const FReflectionsDigTerrainChunk& State)
    {
        return FilledBlocks(State.Retiring) & ~FilledBlocks(State.Pieces);
    }

    /** The blocks whose current pieces the retiring set waits for. */
    uint8 SwapWaitBlocks(const FReflectionsDigTerrainChunk& State)
    {
        return (State.SwapWaitMask | ReplacedBlocks(State)) & FilledBlocks(State.Pieces);
    }

    bool HasRetiring(const FReflectionsDigTerrainChunk& State)
    {
        return FilledBlocks(State.Retiring) != 0;
    }

    bool ShowsNothing(const FReflectionsDigTerrainChunk& State)
    {
        return FilledBlocks(State.Pieces) == 0 && FilledBlocks(State.Retiring) == 0;
    }

    /**
     * Whether a chunk's retiring pieces still wait for the swap check: an emptied block's waits for a quiet terrain;
     * the retiring set waits while a cook it waits for is running, when every piece has collision of its own and the
     * swap is due, or while a failed cook (or a piece that never received a body) has not been handled yet. A cook can
     * finish between ticks, while game-thread tasks run; until the next swap check has kept the set, warned and given
     * it its navigation back, something is still to happen. Once handled, the wait stops, so a failure cannot hold
     * idle off.
     */
    bool IsSwapWaiting(const FReflectionsDigTerrainChunk& State)
    {
        if (!HasRetiring(State))
        {
            return false;
        }
        if (EmptiedBlocks(State) != 0)
        {
            return true;
        }
        const uint8 Wait = SwapWaitBlocks(State);
        if (AnyCookPending(State.Pieces, Wait))
        {
            return true;
        }
        if (AnyCookFailed(State.Pieces, Wait) || !AllHaveCollision(State.Pieces, Wait))
        {
            return !State.bCookFailureReported;
        }
        return true;
    }

    /**
     * Destroys the chunk's retiring pieces whose time has come (see the collision swap above). Returns true when the
     * chunk is now showing nothing at all, so its entry can go. bOutNewlyKept is set when this call found, for the
     * first time since the last commit, that a failed cook keeps the retiring set.
     */
    bool FinishSwap(const FIntVector& Chunk, FReflectionsDigTerrainChunk& State, bool bTerrainQuiet, bool& bOutNewlyKept)
    {
        bOutNewlyKept = false;
        if (!HasRetiring(State))
        {
            State.SwapWaitMask = 0;
            return ShowsNothing(State);
        }
        const double DestroyStart = FPlatformTime::Seconds();
        int32 Destroyed = 0;
        const uint8 Replaced = ReplacedBlocks(State);
        if (Replaced != 0)
        {
            const uint8 Wait = SwapWaitBlocks(State);
            if (AnyCookPending(State.Pieces, Wait))
            {
            }
            else if (AnyCookFailed(State.Pieces, Wait) || !AllHaveCollision(State.Pieces, Wait))
            {
                // A piece that never received a body cannot stand in for the old pieces any more than a failed cook can.
                if (!State.bCookFailureReported)
                {
                    State.bCookFailureReported = true;
                    bOutNewlyKept = true;
                    UE_LOG(LogReflectionsDigTerrain, Warning, TEXT("Chunk %s: a collision cook failed or a piece has no collision; its previous collision stays until the next commit"),
                        *Chunk.ToString());
                }
            }
            else
            {
                Destroyed += DestroyPieces(State.Retiring, Replaced);
                State.SwapWaitMask = 0;
            }
        }
        if (bTerrainQuiet)
        {
            Destroyed += DestroyPieces(State.Retiring, EmptiedBlocks(State));
        }
        if (Destroyed > 0)
        {
            UE_LOG(LogReflectionsDigTerrain, Verbose, TEXT("DIGSPIKE headless swap %s: destroyed %d retiring pieces in %.2f ms"),
                *Chunk.ToString(), Destroyed, MillisecondsSince(DestroyStart));
        }
        return ShowsNothing(State);
    }
}

UReflectionsDigChunkComponent::UReflectionsDigChunkComponent()
{
    OnMeshChanged.AddUObject(this, &UReflectionsDigChunkComponent::NoteMeshChanged);
}

void UReflectionsDigChunkComponent::NoteMeshChanged()
{
    ++MeshChangeSerial;
}

void UReflectionsDigChunkComponent::SetNavGeometry(FReflectionsDigNavGeometry&& InGeometry)
{
    NewNavGeometry = MoveTemp(InGeometry);
    bHasNewNavGeometry = true;
}

void UReflectionsDigChunkComponent::PromoteNavGeometry()
{
    if (bHasCookingNavGeometry)
    {
        NavGeometry = MoveTemp(CookingNavGeometry);
        CookingNavGeometry = FReflectionsDigNavGeometry();
        bHasCookingNavGeometry = false;
    }
}

bool UReflectionsDigChunkComponent::DoCustomNavigableGeometryExport(FNavigableGeometryExport& GeomExport) const
{
    // Runs on the game thread (GetGeometryGatheringMode is Instant), where the arrays change.
    if (!NavGeometry.Vertices.IsEmpty() && !NavGeometry.Indices.IsEmpty())
    {
        GeomExport.ExportCustomMesh(NavGeometry.Vertices.GetData(), NavGeometry.Vertices.Num(), NavGeometry.Indices.GetData(),
            NavGeometry.Indices.Num(), GetComponentTransform());
    }
    // The default export would read the body setup, and the generator builds a body it reads that has no physics
    // meshes yet (UBodySetup::CreatePhysicsMeshes) on the spot.
    return false;
}

ENavDataGatheringMode UReflectionsDigChunkComponent::GetGeometryGatheringMode() const
{
    // With lazy gathering (a project setting) the export would run when a tile is built, possibly on a worker.
    return ENavDataGatheringMode::Instant;
}

bool UReflectionsDigChunkComponent::IsNavigationRelevant() const
{
    return NavigationState == ENavigationState::Counts && Super::IsNavigationRelevant();
}

bool UReflectionsDigChunkComponent::CountsForNavigation() const
{
    return NavigationState == ENavigationState::Counts;
}

void UReflectionsDigChunkComponent::RefreshNavigationRelevance()
{
    if (!IsRegistered())
    {
        return;
    }
    if (IsNavigationRelevant())
    {
        // With CanEverAffectNavigation on, this caches the relevance and registers the piece with navigation.
        HandleCanEverAffectNavigationChange();
    }
    else
    {
        bNavigationRelevant = false;
        FNavigationSystem::OnComponentUnregistered(*this);
    }
}

void UReflectionsDigChunkComponent::CountGameThreadCook(const UBodySetup* FinishedBodySetup)
{
    // The body in place: with deferred collision updates every mesh change clears it (InvalidatePhysicsData), so if
    // it holds cooked triangles again for a mesh no cook of this piece brought it in for, something built it here.
    const UBodySetup* Current = MeshBodySetup;
    if (Current == nullptr || Current == FinishedBodySetup || !Current->bCreatedPhysicsMeshes || Current->TriMeshGeometries.IsEmpty())
    {
        return;
    }
    if (CookedBody.Get() == Current && CookedBodyMeshSerial == MeshChangeSerial)
    {
        return;
    }
    if (LastCountedBody.Get() == Current && LastCountedMeshSerial == MeshChangeSerial)
    {
        return;
    }
    LastCountedBody = Current;
    LastCountedMeshSerial = MeshChangeSerial;
    if (AReflectionsDigTerrain* Terrain = Cast<AReflectionsDigTerrain>(GetOwner()))
    {
        ++Terrain->GameThreadCookCount;
    }
}

bool UReflectionsDigChunkComponent::IsCollisionCookPending() const
{
    return PendingCook != nullptr;
}

bool UReflectionsDigChunkComponent::HasCollision() const
{
    return bHasCollision;
}

bool UReflectionsDigChunkComponent::DidLastCookFail() const
{
    return bLastCookFailed;
}

void UReflectionsDigChunkComponent::RebuildPhysicsData()
{
    // The async path appends one new body setup to AsyncBodySetupQueue. A cook that finishes inside this call
    // (nothing to cook) has already left the queue, and the sync path empties it: neither is pending.
    UBodySetup* const LastBefore = AsyncBodySetupQueue.IsEmpty() ? nullptr : AsyncBodySetupQueue.Last().Get();
    // The cook about to start builds the newest mesh: its triangles wait with it.
    if (bHasNewNavGeometry)
    {
        CookingNavGeometry = MoveTemp(NewNavGeometry);
        NewNavGeometry = FReflectionsDigNavGeometry();
        bHasNewNavGeometry = false;
        bHasCookingNavGeometry = true;
    }
    RebuildMeshSerial = MeshChangeSerial;
    Super::RebuildPhysicsData();
    RebuildMeshSerial = INDEX_NONE;
    UBodySetup* const LastAfter = AsyncBodySetupQueue.IsEmpty() ? nullptr : AsyncBodySetupQueue.Last().Get();
    PendingCook = LastAfter != LastBefore ? LastAfter : nullptr;
    if (PendingCook != nullptr)
    {
        PendingCookMeshSerial = MeshChangeSerial;
    }
    if (AsyncBodySetupQueue.IsEmpty())
    {
        // Nothing left to wait for, but an empty queue does not prove a body: the engine's RebuildPhysicsData returns
        // early when it has no body setup, and FinishPhysicsAsyncCook keeps the old MeshBodySetup when a cook that
        // ended inside the call failed. So the piece counts as colliding only if its MeshBodySetup exists, created its
        // physics meshes without failing, and holds collision data (cooked triangle meshes or simple shapes).
        const UBodySetup* Body = MeshBodySetup;
        bHasCollision = Body != nullptr && Body->bCreatedPhysicsMeshes && !Body->bFailedToCreatePhysicsMeshes
            && (Body->TriMeshGeometries.Num() > 0 || Body->AggGeom.GetElementCount() > 0);
        bLastCookFailed = !bHasCollision;
        if (bHasCollision)
        {
            PromoteNavGeometry();
        }
        if (AReflectionsDigTerrain* Terrain = Cast<AReflectionsDigTerrain>(GetOwner()); Terrain != nullptr && bHasCollision)
        {
            Terrain->UpdatePieceNavigation(*this);
        }
    }
}

#if WITH_DEV_AUTOMATION_TESTS
void UReflectionsDigChunkComponent::FailNextCookForTest()
{
    bFailNextCookForTest = true;
}
#endif

void UReflectionsDigChunkComponent::FinishPhysicsAsyncCook(bool bSuccess, UBodySetup* FinishedBodySetup)
{
    // Before the engine swaps anything: what is in place now is what this cook is about to replace.
    CountGameThreadCook(FinishedBodySetup);
#if WITH_DEV_AUTOMATION_TESTS
    if (bFailNextCookForTest && FinishedBodySetup != nullptr && FinishedBodySetup == PendingCook)
    {
        // The engine's own failure path: a non-empty mesh reported as not cooked keeps the previous body.
        bFailNextCookForTest = false;
        bSuccess = false;
    }
#endif
    const double CookFinishStart = FPlatformTime::Seconds();
    Super::FinishPhysicsAsyncCook(bSuccess, FinishedBodySetup);
    if (AReflectionsDigTerrain* Timed = Cast<AReflectionsDigTerrain>(GetOwner()))
    {
        Timed->CookFinishSeconds += FPlatformTime::Seconds() - CookFinishStart;
    }
    if (FinishedBodySetup != nullptr && MeshBodySetup == FinishedBodySetup)
    {
        // This cook's body is in; remember which mesh it was cooked from (one that finished inside RebuildPhysicsData
        // started there).
        CookedBody = FinishedBodySetup;
        CookedBodyMeshSerial = FinishedBodySetup == PendingCook ? PendingCookMeshSerial
            : RebuildMeshSerial != INDEX_NONE ? RebuildMeshSerial : MeshChangeSerial;
    }
    // Older cooks are aborted when a newer one starts and never report back; only the newest ends the wait.
    if (FinishedBodySetup != nullptr && FinishedBodySetup == PendingCook)
    {
        PendingCook = nullptr;
        // The engine swaps a finished body in only when the cook succeeded (or needed no cooking).
        bLastCookFailed = MeshBodySetup != FinishedBodySetup;
        if (AReflectionsDigTerrain* Owner = Cast<AReflectionsDigTerrain>(GetOwner()))
        {
            ++Owner->CookCompletionCount;
        }
        bHasCollision |= !bLastCookFailed;
        // Navigation follows the collision: it is told only now that the new body is in, and from now on exports
        // this mesh's triangles. A failed cook kept the old body, whose triangles navigation already has.
        AReflectionsDigTerrain* Terrain = Cast<AReflectionsDigTerrain>(GetOwner());
        if (!bLastCookFailed)
        {
            PromoteNavGeometry();
        }
        if (!bLastCookFailed && Terrain != nullptr)
        {
            Terrain->UpdatePieceNavigation(*this);
        }
    }
}

AReflectionsDigTerrain::AReflectionsDigTerrain()
{
    PrimaryActorTick.bCanEverTick = false;
    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

    // A hard reference, so a packaged game cooks the fallback material with the terrain.
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> PlainMaterialFinder(PlainGroundMaterialPath);
    PlainGroundMaterial = PlainMaterialFinder.Object;

    SafetyFloor = CreateDefaultSubobject<UBoxComponent>(TEXT("SafetyFloor"));
    SafetyFloor->SetupAttachment(RootComponent);
    SafetyFloor->SetUsingAbsoluteLocation(true);
    SafetyFloor->SetUsingAbsoluteRotation(true);
    SafetyFloor->SetUsingAbsoluteScale(true);
    SafetyFloor->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
    SafetyFloor->SetCanEverAffectNavigation(false);
}

void AReflectionsDigTerrain::BeginPlay()
{
    Super::BeginPlay();

    if (!GetActorQuat().IsIdentity() || !GetActorScale3D().Equals(FVector::OneVector))
    {
        UE_LOG(LogReflectionsDigTerrain, Warning, TEXT("%s must be unrotated and unscaled; its chunks ignore its rotation and scale."), *GetName());
    }
    const FVector Location = GetActorLocation();
    // Cells are sample points and the mesher puts its vertices at cube centres, so the meshed ground starts half a
    // cell after the grid origin's first sample. With the origin half a cell inside the actor's corner, the ground
    // spans exactly the patch: X and Y from the actor's location to SizeInChunks chunks further.
    const double HalfCellCm = ReflectionsDig::CellSizeCm * 0.5;
    const FVector OriginCm(Location.X + HalfCellCm, Location.Y + HalfCellCm, GroundHeightCm - SizeInChunks.Z * ReflectionsDig::ChunkSizeCm + GroundBelowGridTopCm);
    Grid = MakeUnique<FReflectionsDigGrid>(SizeInChunks, OriginCm, GroundHeightCm);

    // The pieces never draw with the engine's default material: on this mesh (normals only, no texture coordinates,
    // no tangents) it turned a lit view along a tunnel pure black. GroundMaterial itself is left as it is.
    PieceMaterial = GroundMaterial;
    if (PieceMaterial == nullptr)
    {
        PieceMaterial = PlainGroundMaterial;
        if (PieceMaterial == nullptr)
        {
            UE_LOG(LogReflectionsDigTerrain, Warning, TEXT("%s has no GroundMaterial and %s could not be loaded; its pieces use the engine default material."),
                *GetName(), PlainGroundMaterialPath);
        }
    }

    // The safety floor spans the whole patch (from the actor's corner, not the grid origin), under the grid floor.
    const FVector HalfSize(SizeInChunks.X * ReflectionsDig::ChunkSizeCm * 0.5, SizeInChunks.Y * ReflectionsDig::ChunkSizeCm * 0.5, SafetyFloorThicknessCm * 0.5);
    SafetyFloor->SetBoxExtent(HalfSize);
    SafetyFloor->SetWorldLocation(FVector(Location.X + HalfSize.X, Location.Y + HalfSize.Y, OriginCm.Z - SafetyFloorGapCm - HalfSize.Z));

    if (UReflectionsDigSubsystem* Subsystem = GetWorld()->GetSubsystem<UReflectionsDigSubsystem>())
    {
        Subsystem->RegisterTerrain(this);
    }
}

void AReflectionsDigTerrain::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (UReflectionsDigSubsystem* Subsystem = GetWorld()->GetSubsystem<UReflectionsDigSubsystem>())
    {
        Subsystem->UnregisterTerrain(this);
    }
    TArray<FIntVector> Shown;
    Chunks.GetKeys(Shown);
    for (const FIntVector& Chunk : Shown)
    {
        ReleaseChunk(Chunk);
    }
    Grid.Reset();

    Super::EndPlay(EndPlayReason);
}

void AReflectionsDigTerrain::CommitChunk(FIntVector Chunk, FReflectionsDigMeshData&& Mesh)
{
    FReflectionsDigChunkResult Result;
    // The chunk's local cell (0, 0, 0) relative to the grid origin, as FReflectionsDigGrid::CopyChunkSamples gives it.
    ReflectionsDigPieces::Build(Mesh, FVector3f(Chunk * ReflectionsDig::ChunkCells) * ReflectionsDig::CellSizeCm, Result);
    CommitChunkPieces(Chunk, MoveTemp(Result));
}

void AReflectionsDigTerrain::CommitChunkPieces(FIntVector Chunk, FReflectionsDigChunkResult&& Result)
{
    if (Grid == nullptr)
    {
        ReleaseChunk(Chunk);
        return;
    }
    if (Result.DroppedTriangles > 0)
    {
        UE_LOG(LogReflectionsDigTerrain, Warning, TEXT("Chunk %s: %d of %d triangles could not be added to its pieces"),
            *Chunk.ToString(), Result.DroppedTriangles, Result.SourceTriangleCount);
    }

    const double StartSeconds = FPlatformTime::Seconds();
    double ComponentSeconds = 0.0;
    double SetMeshSeconds = 0.0;
    double CookStartSeconds = 0.0;
    double DestroySeconds = 0.0;
    const TCHAR* Kind = TEXT("reuse");

    // The slots this result changes: a new hash, or a piece whose newest cook failed (it does not collide with the
    // mesh it shows, so the commit cooks it again, as a whole-chunk commit used to). Every other filled slot is kept.
    const FReflectionsDigTerrainChunk* Shown = Chunks.Find(Chunk);
    uint8 Changed = 0;
    int32 Kept = 0;
    for (int32 Block = 0; Block < NumBlocks; ++Block)
    {
        const UReflectionsDigChunkComponent* Current = Shown != nullptr ? Shown->Pieces[Block].Get() : nullptr;
        const uint64 ShownHash = Shown != nullptr ? Shown->PieceHash[Block] : 0;
        const bool bFailed = Current != nullptr && !Current->IsCollisionCookPending() && Current->DidLastCookFail();
        if (Result.PieceHash[Block] != ShownHash || bFailed)
        {
            Changed |= BlockBit(Block);
        }
        else if (Current != nullptr)
        {
            ++Kept;
        }
    }
    PiecesKeptCount += Kept;
    const int32 NumChanged = FMath::CountBits(static_cast<uint64>(Changed));

    if (Changed == 0)
    {
        // Nothing to do: no component, cook or navigation work, and nothing for the chunk to wait on.
        Kind = TEXT("unchanged");
    }
    else
    {
        FReflectionsDigTerrainChunk& State = Chunks.FindOrAdd(Chunk);
        TArray<int32, TInlineAllocator<NumBlocks>> Targets;
        const int32 Single = NumChanged == 1 ? static_cast<int32>(FMath::CountTrailingZeros(static_cast<uint32>(Changed))) : INDEX_NONE;
        if (Single != INDEX_NONE && State.Pieces[Single] != nullptr && Result.Pieces[Single].TriangleCount() > 0)
        {
            // One slot changes, with a piece before and after: the engine keeps the old body until the new cook is
            // in. A retiring set whose replacement has finished cooking goes first: every later commit to this block
            // takes this path and starts a new cook, so a swap check that runs only between commits would never find
            // the piece idle and the retiring set would stay for the whole hold, an invisible lid.
            bool bNewlyKept = false;
            FinishSwap(Chunk, State, /*bTerrainQuiet=*/ false, bNewlyKept);
            // A retiring set kept by a failed cook gets a new replacement cooking: it is old collision again.
            SetRetiringSetNavigation(State, /*bAffects=*/ false);
            Targets.Add(Single);
        }
        else
        {
            Kind = TEXT("replace");
            RetireCurrentSet(State, Changed, DestroySeconds);
            const double CreateStart = FPlatformTime::Seconds();
            for (int32 Block = 0; Block < NumBlocks; ++Block)
            {
                if ((Changed & BlockBit(Block)) != 0 && Result.Pieces[Block].TriangleCount() > 0)
                {
                    State.Pieces[Block] = CreatePieceComponent();
                    // The retiring set (if any) waits for every piece this commit creates.
                    State.SwapWaitMask |= BlockBit(Block);
                    Targets.Add(Block);
                }
            }
            ComponentSeconds += FPlatformTime::Seconds() - CreateStart;
        }
        // Only now, after the swap check above has reported a failure it found: the cooks started below are new,
        // and a failure of theirs is reported again.
        State.bCookFailureReported = false;
        for (const int32 Block : Targets)
        {
            // With bDeferCollisionUpdates, SetMesh only invalidates the current body setup's cooked meshes; the body
            // in the physics scene keeps its own reference to them and goes on colliding.
            UReflectionsDigChunkComponent* Piece = State.Pieces[Block];
            ++CookStartPieces;
            ++PiecesChangedCount;
            CookStartVertices += Result.Pieces[Block].VertexCount();
            const double SetStart = FPlatformTime::Seconds();
            Piece->SetMesh(MoveTemp(Result.Pieces[Block]));
            // Its triangles for navigation, which exports them once the cook below has brought them in.
            Piece->SetNavGeometry(MoveTemp(Result.NavGeometry[Block]));
            SetMeshSeconds += FPlatformTime::Seconds() - SetStart;
            // Async path: a new body setup is cooked; FinishPhysicsAsyncCook swaps it in.
            const double CookStart = FPlatformTime::Seconds();
            Piece->UpdateCollision(/*bOnlyIfPending=*/ false);
            CookStartSeconds += FPlatformTime::Seconds() - CookStart;
        }
        for (int32 Block = 0; Block < NumBlocks; ++Block)
        {
            if ((Changed & BlockBit(Block)) != 0)
            {
                State.PieceHash[Block] = Result.PieceHash[Block];
            }
        }
        if (ShowsNothing(State))
        {
            Chunks.Remove(Chunk);
        }
    }

    UE_LOG(LogReflectionsDigTerrain, Verbose,
        TEXT("DIGSPIKE headless commit %s (%s, %d pieces, %d vertices, %d changed, %d kept): total %.2f ms, components %.2f, set mesh %.2f, cook start %.2f, destroy %.2f"),
        *Chunk.ToString(), Kind, Result.NumPieces(), Result.SourceVertexCount, NumChanged, Kept, MillisecondsSince(StartSeconds),
        ComponentSeconds * 1000.0, SetMeshSeconds * 1000.0, CookStartSeconds * 1000.0, DestroySeconds * 1000.0);
    CommitSeconds += FPlatformTime::Seconds() - StartSeconds;
}

void AReflectionsDigTerrain::RetireCurrentSet(FReflectionsDigTerrainChunk& State, uint8 ChangedBlocks, double& InOutDestroySeconds)
{
    const double DestroyStart = FPlatformTime::Seconds();
    if (ReplacedBlocks(State) == 0)
    {
        // No retiring set: this commit starts a new one, waiting only for the pieces it creates.
        State.SwapWaitMask = 0;
    }
    // The current pieces the retiring set waits for: are they the newest collision that really exists?
    const uint8 Wait = SwapWaitBlocks(State);
    const bool bHasRetiringSet = ReplacedBlocks(State) != 0;
    const bool bReplacementCollides = !bHasRetiringSet || AllHaveCollision(State.Pieces, Wait);
    if (bHasRetiringSet && bReplacementCollides)
    {
        // The swap is due: the retiring set goes now, as the swap check would have destroyed it.
        DestroyPieces(State.Retiring, ReplacedBlocks(State));
        State.SwapWaitMask = 0;
    }
    bool bRetired = false;
    for (int32 Block = 0; Block < NumBlocks; ++Block)
    {
        if ((ChangedBlocks & BlockBit(Block)) == 0 || State.Pieces[Block] == nullptr)
        {
            // Unchanged, or the block had no piece: an emptied block's retiring piece is still the last collision it had.
            continue;
        }
        if (bReplacementCollides || (Wait & BlockBit(Block)) == 0)
        {
            // The piece is the newest collision its block has: it retires. (A block with a retiring piece is always
            // one the retiring set waits for, so here the slot has none left.)
            DestroyPiece(State.Retiring[Block]);
            UReflectionsDigChunkComponent* Old = State.Pieces[Block];
            State.Retiring[Block] = Old;
            Old->SetVisibility(false);
            // Old collision: it leaves navigation now (the engine removes it from the navigation octree and dirties
            // its area), not when it is destroyed after the swap. A cook of it still running brings nothing to
            // navigation.
            const double NavStart = FPlatformTime::Seconds();
            Old->NavigationState = UReflectionsDigChunkComponent::ENavigationState::Excluded;
            Old->SetCanEverAffectNavigation(false);
            NavUpdateSeconds += FPlatformTime::Seconds() - NavStart;
            ++NavUpdateCount;
            bRetired = true;
        }
        else
        {
            // Part of a replacement that never got collision of its own: the retiring set (or nothing, for a block
            // that had no piece before it) is still the newest that collides there.
            DestroyPiece(State.Pieces[Block]);
        }
        State.Pieces[Block] = nullptr;
    }
    if (bRetired)
    {
        if (const UWorld* World = GetWorld())
        {
            LastNavUpdateSeconds = World->GetTimeSeconds();
        }
    }
    // If a failed cook had given the retiring set its navigation back, the new pieces about to cook make it old
    // collision again.
    SetRetiringSetNavigation(State, /*bAffects=*/ false);
    InOutDestroySeconds += FPlatformTime::Seconds() - DestroyStart;
}

void AReflectionsDigTerrain::SetRetiringSetNavigation(FReflectionsDigTerrainChunk& State, bool bAffects)
{
    using ENavigationState = UReflectionsDigChunkComponent::ENavigationState;
    const ENavigationState Wanted = bAffects ? ENavigationState::Counts : ENavigationState::Excluded;
    bool bChanged = false;
    for (UReflectionsDigChunkComponent* Piece : State.Retiring)
    {
        if (Piece == nullptr || (Piece->CanEverAffectNavigation() == bAffects && Piece->NavigationState == Wanted))
        {
            continue;
        }
        // The engine adds the piece to the navigation octree with the triangles of its collision, or removes it, and
        // dirties its area. The piece's own state goes first: it decides whether the piece is relevant.
        const double NavStart = FPlatformTime::Seconds();
        Piece->NavigationState = Wanted;
        if (Piece->CanEverAffectNavigation() != bAffects)
        {
            Piece->SetCanEverAffectNavigation(bAffects);
        }
        else
        {
            Piece->RefreshNavigationRelevance();
        }
        NavUpdateSeconds += FPlatformTime::Seconds() - NavStart;
        ++NavUpdateCount;
        bChanged = true;
    }
    const UWorld* World = GetWorld();
    if (bChanged && World != nullptr)
    {
        LastNavUpdateSeconds = World->GetTimeSeconds();
    }
}

void AReflectionsDigTerrain::ReleaseChunk(FIntVector Chunk)
{
    if (FReflectionsDigTerrainChunk* State = Chunks.Find(Chunk))
    {
        const double ReleaseStart = FPlatformTime::Seconds();
        DestroyPieces(State->Pieces);
        // The hashes go with the entry: a chunk shown again is built from scratch.
        DestroyPieces(State->Retiring);
        Chunks.Remove(Chunk);
        ReleaseSeconds += FPlatformTime::Seconds() - ReleaseStart;
        ++ReleaseCount;
    }
}

FReflectionsDigTerrainTimings AReflectionsDigTerrain::GetTimings() const
{
    FReflectionsDigTerrainTimings Timings;
    Timings.CommitSeconds = CommitSeconds;
    Timings.SwapCheckSeconds = SwapCheckSeconds;
    Timings.CookFinishSeconds = CookFinishSeconds;
    Timings.NavUpdateSeconds = NavUpdateSeconds;
    Timings.NavAfterCookSeconds = NavAfterCookSeconds;
    Timings.CookStartPieces = CookStartPieces;
    Timings.CookStartVertices = CookStartVertices;
    return Timings;
}

int32 AReflectionsDigTerrain::GetCookCompletionCount() const
{
    return CookCompletionCount;
}

int32 AReflectionsDigTerrain::GetGameThreadCookCount() const
{
    return GameThreadCookCount;
}

int32 AReflectionsDigTerrain::GetChunkReleaseCount() const
{
    return ReleaseCount;
}

double AReflectionsDigTerrain::GetChunkReleaseSeconds() const
{
    return ReleaseSeconds;
}

UDynamicMeshComponent* AReflectionsDigTerrain::FindChunkComponent(FIntVector Chunk) const
{
    return GetChunkPiece(Chunk, 0);
}

int32 AReflectionsDigTerrain::GetChunkPieceCount(FIntVector Chunk) const
{
    const FReflectionsDigTerrainChunk* State = Chunks.Find(Chunk);
    return State != nullptr ? FMath::CountBits(static_cast<uint64>(FilledBlocks(State->Pieces))) : 0;
}

UDynamicMeshComponent* AReflectionsDigTerrain::GetChunkPiece(FIntVector Chunk, int32 Index) const
{
    const FReflectionsDigTerrainChunk* State = Chunks.Find(Chunk);
    if (State == nullptr || Index < 0)
    {
        return nullptr;
    }
    for (int32 Block = 0; Block < NumBlocks; ++Block)
    {
        if (State->Pieces[Block] != nullptr && Index-- == 0)
        {
            return State->Pieces[Block].Get();
        }
    }
    return nullptr;
}

UDynamicMeshComponent* AReflectionsDigTerrain::GetChunkBlockPiece(FIntVector Chunk, int32 Block) const
{
    const FReflectionsDigTerrainChunk* State = Chunks.Find(Chunk);
    return State != nullptr && Block >= 0 && Block < NumBlocks ? State->Pieces[Block].Get() : nullptr;
}

int32 AReflectionsDigTerrain::GetRetiringPieceCount(FIntVector Chunk) const
{
    const FReflectionsDigTerrainChunk* State = Chunks.Find(Chunk);
    return State != nullptr ? FMath::CountBits(static_cast<uint64>(FilledBlocks(State->Retiring))) : 0;
}

int32 AReflectionsDigTerrain::GetPiecesChangedCount() const
{
    return PiecesChangedCount;
}

int32 AReflectionsDigTerrain::GetPiecesKeptCount() const
{
    return PiecesKeptCount;
}

FReflectionsDigGrid* AReflectionsDigTerrain::GetGrid() const
{
    return Grid.Get();
}

int32 AReflectionsDigTerrain::GetLargestCollisionVertexCount() const
{
    int32 Largest = 0;
    for (const TPair<FIntVector, FReflectionsDigTerrainChunk>& Pair : Chunks)
    {
        for (const FPieceSlots* Set : { &Pair.Value.Pieces, &Pair.Value.Retiring })
        {
            for (const UReflectionsDigChunkComponent* Piece : *Set)
            {
                if (Piece != nullptr && Piece->GetMesh() != nullptr)
                {
                    Largest = FMath::Max(Largest, Piece->GetMesh()->VertexCount());
                }
            }
        }
    }
    return Largest;
}

void AReflectionsDigTerrain::FinishCollisionSwaps(bool bTerrainQuiet)
{
    const double SwapStart = FPlatformTime::Seconds();
    ON_SCOPE_EXIT
    {
        SwapCheckSeconds += FPlatformTime::Seconds() - SwapStart;
    };
    TArray<FIntVector, TInlineAllocator<4>> Emptied;
    for (TPair<FIntVector, FReflectionsDigTerrainChunk>& Pair : Chunks)
    {
        bool bNewlyKept = false;
        if (FinishSwap(Pair.Key, Pair.Value, bTerrainQuiet, bNewlyKept))
        {
            Emptied.Add(Pair.Key);
        }
        if (bNewlyKept)
        {
            // The kept set is the chunk's only collision now: without navigation the navmesh would show a hole over
            // ground that still collides. Once per failure; the next commit takes it out again, destroying takes it out.
            SetRetiringSetNavigation(Pair.Value, /*bAffects=*/ true);
        }
    }
    for (const FIntVector& Chunk : Emptied)
    {
        Chunks.Remove(Chunk);
    }
}

bool AReflectionsDigTerrain::IsChunkCooking(FIntVector Chunk) const
{
    const FReflectionsDigTerrainChunk* State = Chunks.Find(Chunk);
    return State != nullptr && AnyCookPending(State->Pieces);
}

bool AReflectionsDigTerrain::HasCookPending() const
{
    for (const TPair<FIntVector, FReflectionsDigTerrainChunk>& Pair : Chunks)
    {
        if (AnyCookPending(Pair.Value.Pieces) || AnyCookPending(Pair.Value.Retiring))
        {
            return true;
        }
    }
    return false;
}

bool AReflectionsDigTerrain::IsWaitingOnCollision() const
{
    for (const TPair<FIntVector, FReflectionsDigTerrainChunk>& Pair : Chunks)
    {
        if (AnyCookPending(Pair.Value.Pieces) || AnyCookPending(Pair.Value.Retiring) || IsSwapWaiting(Pair.Value))
        {
            return true;
        }
    }
    return false;
}

UBoxComponent* AReflectionsDigTerrain::GetSafetyFloor() const
{
    return SafetyFloor;
}

double AReflectionsDigTerrain::GetLastNavUpdateSeconds() const
{
    return LastNavUpdateSeconds;
}

int32 AReflectionsDigTerrain::GetNavUpdateCount() const
{
    return NavUpdateCount;
}

double AReflectionsDigTerrain::GetNavUpdateSeconds() const
{
    return NavUpdateSeconds;
}

void AReflectionsDigTerrain::UpdatePieceNavigation(UReflectionsDigChunkComponent& Piece)
{
    using ENavigationState = UReflectionsDigChunkComponent::ENavigationState;
    UWorld* World = GetWorld();
    // A retiring piece no longer counts for navigation; a destroyed one has unregistered. Between EndPlay and the
    // world's end the grid is gone, so a late cook asks for nothing either.
    if (Grid == nullptr || World == nullptr || World->bIsTearingDown || !Piece.IsRegistered() || Piece.IsBeingDestroyed()
        || Piece.NavigationState == ENavigationState::Excluded)
    {
        return;
    }
    const double NavStart = FPlatformTime::Seconds();
    if (Piece.NavigationState == ENavigationState::WaitingForCollision)
    {
        // Its first collision is in: only now does the new piece join navigation, with these triangles.
        Piece.NavigationState = ENavigationState::Counts;
        Piece.RefreshNavigationRelevance();
    }
    else
    {
        FNavigationSystem::UpdateComponentData(Piece);
    }
    NavUpdateSeconds += FPlatformTime::Seconds() - NavStart;
    NavAfterCookSeconds += FPlatformTime::Seconds() - NavStart;
    ++NavUpdateCount;
    LastNavUpdateSeconds = World->GetTimeSeconds();
}

UReflectionsDigChunkComponent* AReflectionsDigTerrain::CreatePieceComponent()
{
    UReflectionsDigChunkComponent* Piece = NewObject<UReflectionsDigChunkComponent>(this, NAME_None, RF_Transient);
    Piece->SetupAttachment(GetRootComponent());
    // At the grid origin in world space, unrotated and unscaled, whatever the actor's transform.
    Piece->SetUsingAbsoluteLocation(true);
    Piece->SetUsingAbsoluteRotation(true);
    Piece->SetUsingAbsoluteScale(true);
    Piece->SetRelativeTransform(FTransform(Grid->GetOriginCm()));

    Piece->SetComplexAsSimpleCollisionEnabled(true, /*bImmediateUpdate=*/ false);
    Piece->bUseAsyncCooking = true;
    Piece->SetDeferredCollisionUpdatesEnabled(true, /*bImmediateUpdate=*/ false);
    Piece->bDisableMeshUVHitResults = true;
    Piece->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Piece->SetCollisionObjectType(ECC_WorldStatic);
    Piece->SetCollisionResponseToAllChannels(ECR_Block);
    // Navigation takes the piece's own triangles (DoCustomNavigableGeometryExport), never its body setup, and only
    // once its first cook is in (until then IsNavigationRelevant is false, so registering adds nothing).
    Piece->SetCustomNavigableGeometry(EHasCustomNavigableGeometry::Yes);
    Piece->SetCanEverAffectNavigation(true);
    if (PieceMaterial != nullptr)
    {
        Piece->SetMaterial(0, PieceMaterial);
    }
    // Registered while still empty, so creating its physics state cooks nothing on the game thread.
    Piece->RegisterComponent();
    return Piece;
}
