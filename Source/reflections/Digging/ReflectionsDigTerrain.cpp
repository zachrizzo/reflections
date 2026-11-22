#include "Digging/ReflectionsDigTerrain.h"

#include "CoreMinimal.h"
#include "AI/NavigationSystemBase.h"
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
#include "Materials/MaterialInterface.h"
#include "PhysicsEngine/BodySetup.h"

DEFINE_LOG_CATEGORY(LogReflectionsDigTerrain);

using UE::Geometry::FDynamicMesh3;

/*
 * Collision swap. Each chunk has a current set of pieces and at most one retiring set, hidden but still colliding.
 * The subsystem commits a chunk only when none of its current pieces is cooking (one cook at a time per chunk), so
 * every cook finishes and the engine never aborts one. The rules below still hold for a direct CommitChunk call,
 * which may land while a cook runs, and after a failed cook.
 * - A commit with one piece onto a chunk showing one piece reuses that component. With deferred, async collision the
 *   engine keeps its body in the scene until FinishPhysicsAsyncCook swaps the new one in.
 * - Any other commit replaces the set. Whether the current set is the newest collision that really exists is
 *   decided at commit time from the pieces' own cook state: if every current piece has collision of its own (a
 *   finished, successful cook; a reused piece still cooking keeps its older body), the retiring set is destroyed
 *   and the current set retires; otherwise the current set is destroyed and the retiring set stays. With no
 *   retiring set the current set always retires: it is the only collision there is. Through the subsystem the
 *   second case arises only after a failed cook.
 * - A retiring set replaced by pieces goes once every piece has finished cooking successfully. A failed cook keeps
 *   it, with one warning. The subsystem checks this at the start of each tick, before the commits, and again after
 *   the launches; a commit that reuses a chunk's single piece checks its own chunk first.
 * - A retiring set replaced by nothing (the chunk became all solid or all air) goes only when the whole terrain is
 *   quiet: a neighbouring chunk may still be showing the old hole into this chunk.
 * - Navigation follows the collision, not the mesh: a current piece asks for one navigation update per cook that
 *   brings its new body in (a failed cook asks for nothing), a set leaves navigation as it retires, and a destroyed
 *   piece leaves through the engine's unregister. A retiring set kept by a failed cook is the chunk's only collision,
 *   so it gets its navigation back once, until the next commit puts a new set in front of it or it is destroyed.
 *   The safety floor never affects navigation.
 */

namespace
{
    constexpr float ChunkHeightCm = ReflectionsDig::ChunkCells * ReflectionsDig::CellSizeCm;
    /** The ground surface lies this far below the top of the grid. */
    constexpr float GroundBelowGridTopCm = 400.0f;
    /** The safety floor's top lies this far below the grid floor, and it is this thick. */
    constexpr float SafetyFloorGapCm = 30.0f;
    constexpr float SafetyFloorThicknessCm = 100.0f;

    double MillisecondsSince(double StartSeconds)
    {
        return (FPlatformTime::Seconds() - StartSeconds) * 1000.0;
    }

    void DestroyPieces(TArray<TObjectPtr<UReflectionsDigChunkComponent>>& Pieces)
    {
        for (UReflectionsDigChunkComponent* Piece : Pieces)
        {
            if (Piece != nullptr)
            {
                Piece->DestroyComponent();
            }
        }
        Pieces.Reset();
    }

    bool AnyCookPending(const TArray<TObjectPtr<UReflectionsDigChunkComponent>>& Pieces)
    {
        return Pieces.ContainsByPredicate([](const UReflectionsDigChunkComponent* Piece)
        {
            return Piece != nullptr && Piece->IsCollisionCookPending();
        });
    }

    bool AnyCookFailed(const TArray<TObjectPtr<UReflectionsDigChunkComponent>>& Pieces)
    {
        return Pieces.ContainsByPredicate([](const UReflectionsDigChunkComponent* Piece)
        {
            return Piece != nullptr && Piece->DidLastCookFail();
        });
    }

    bool AllHaveCollision(const TArray<TObjectPtr<UReflectionsDigChunkComponent>>& Pieces)
    {
        return !Pieces.ContainsByPredicate([](const UReflectionsDigChunkComponent* Piece)
        {
            return Piece == nullptr || !Piece->HasCollision();
        });
    }

    /**
     * Whether a chunk's retiring set still waits for a swap that will come: a cook is running, or every piece has
     * collision of its own and the swap is due. A failed cook, or a piece that never received a body, stops the wait.
     */
    bool IsSwapWaiting(const FReflectionsDigTerrainChunk& State)
    {
        if (State.Retiring.IsEmpty())
        {
            return false;
        }
        if (State.Pieces.IsEmpty())
        {
            return true;
        }
        return AnyCookPending(State.Pieces) || (!AnyCookFailed(State.Pieces) && AllHaveCollision(State.Pieces));
    }

    /**
     * Destroys the chunk's retiring set if its time has come (see the collision swap above). Returns true when the
     * chunk was emptied and is now showing nothing at all, so its entry can go. bOutNewlyKept is set when this call
     * found, for the first time since the last commit, that a failed cook keeps the retiring set.
     */
    bool FinishSwap(const FIntVector& Chunk, FReflectionsDigTerrainChunk& State, bool bTerrainQuiet, bool& bOutNewlyKept)
    {
        bOutNewlyKept = false;
        if (State.Retiring.IsEmpty())
        {
            return false;
        }
        const double DestroyStart = FPlatformTime::Seconds();
        const int32 Destroyed = State.Retiring.Num();
        bool bEmptied = false;
        if (State.Pieces.IsEmpty())
        {
            if (!bTerrainQuiet)
            {
                return false;
            }
            DestroyPieces(State.Retiring);
            bEmptied = true;
        }
        else if (AnyCookPending(State.Pieces))
        {
            return false;
        }
        else if (AnyCookFailed(State.Pieces) || !AllHaveCollision(State.Pieces))
        {
            // A piece that never received a body cannot stand in for the old set any more than a failed cook can.
            if (!State.bCookFailureReported)
            {
                State.bCookFailureReported = true;
                bOutNewlyKept = true;
                UE_LOG(LogReflectionsDigTerrain, Warning, TEXT("Chunk %s: a collision cook failed or a piece has no collision; its previous collision stays until the next commit"),
                    *Chunk.ToString());
            }
            return false;
        }
        else
        {
            DestroyPieces(State.Retiring);
        }
        UE_LOG(LogReflectionsDigTerrain, Verbose, TEXT("DIGSPIKE headless swap %s: destroyed %d retiring pieces in %.2f ms"),
            *Chunk.ToString(), Destroyed, MillisecondsSince(DestroyStart));
        return bEmptied;
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
    Super::RebuildPhysicsData();
    UBodySetup* const LastAfter = AsyncBodySetupQueue.IsEmpty() ? nullptr : AsyncBodySetupQueue.Last().Get();
    PendingCook = LastAfter != LastBefore ? LastAfter : nullptr;
    if (AsyncBodySetupQueue.IsEmpty())
    {
        // Cooked on the spot (a world without async cooking): the body is in place.
        bHasCollision = true;
        bLastCookFailed = false;
        if (AReflectionsDigTerrain* Terrain = Cast<AReflectionsDigTerrain>(GetOwner()))
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
#if WITH_DEV_AUTOMATION_TESTS
    if (bFailNextCookForTest && FinishedBodySetup != nullptr && FinishedBodySetup == PendingCook)
    {
        // The engine's own failure path: a non-empty mesh reported as not cooked keeps the previous body.
        bFailNextCookForTest = false;
        bSuccess = false;
    }
#endif
    Super::FinishPhysicsAsyncCook(bSuccess, FinishedBodySetup);
    // Older cooks are aborted when a newer one starts and never report back; only the newest ends the wait.
    if (FinishedBodySetup != nullptr && FinishedBodySetup == PendingCook)
    {
        PendingCook = nullptr;
        // The engine swaps a finished body in only when the cook succeeded (or needed no cooking).
        bLastCookFailed = MeshBodySetup != FinishedBodySetup;
        bHasCollision |= !bLastCookFailed;
        // Navigation exports the body setup it is handed, so it is told only now that the new one is in; a failed
        // cook kept the old body, which navigation already has.
        AReflectionsDigTerrain* Terrain = Cast<AReflectionsDigTerrain>(GetOwner());
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
    const FVector OriginCm(Location.X, Location.Y, GroundHeightCm - SizeInChunks.Z * ChunkHeightCm + GroundBelowGridTopCm);
    Grid = MakeUnique<FReflectionsDigGrid>(SizeInChunks, OriginCm, GroundHeightCm);

    // The safety floor spans the whole patch, under the grid floor.
    const FVector HalfSize(SizeInChunks.X * ChunkHeightCm * 0.5, SizeInChunks.Y * ChunkHeightCm * 0.5, SafetyFloorThicknessCm * 0.5);
    SafetyFloor->SetBoxExtent(HalfSize);
    SafetyFloor->SetWorldLocation(OriginCm + FVector(HalfSize.X, HalfSize.Y, -SafetyFloorGapCm - HalfSize.Z));

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
    ReflectionsDigPieces::Build(Mesh, Result);
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

    if (Result.Pieces.IsEmpty())
    {
        Kind = TEXT("retire to empty");
        if (FReflectionsDigTerrainChunk* State = Chunks.Find(Chunk))
        {
            RetireCurrentSet(*State, DestroySeconds);
            if (State->Retiring.IsEmpty())
            {
                Chunks.Remove(Chunk);
            }
        }
    }
    else
    {
        FReflectionsDigTerrainChunk& State = Chunks.FindOrAdd(Chunk);
        TArray<UReflectionsDigChunkComponent*, TInlineAllocator<4>> Targets;
        if (Result.Pieces.Num() == 1 && State.Pieces.Num() == 1 && State.Pieces[0] != nullptr)
        {
            // One piece before and after: the engine keeps the old body until the new cook is in. A retiring set
            // whose replacement (this piece) has finished cooking goes first: every later commit to this chunk takes
            // this path and starts a new cook, so a swap check that runs only between commits would never find the
            // piece idle and the retiring set would stay for the whole hold, an invisible lid.
            bool bNewlyKept = false;
            FinishSwap(Chunk, State, /*bTerrainQuiet=*/ false, bNewlyKept);
            // A retiring set kept by a failed cook gets a new replacement cooking: it is old collision again.
            SetRetiringSetNavigation(State, /*bAffects=*/ false);
            Targets.Add(State.Pieces[0]);
        }
        else
        {
            Kind = TEXT("replace");
            RetireCurrentSet(State, DestroySeconds);
            const double CreateStart = FPlatformTime::Seconds();
            for (int32 Index = 0; Index < Result.Pieces.Num(); ++Index)
            {
                UReflectionsDigChunkComponent* Piece = CreatePieceComponent();
                State.Pieces.Add(Piece);
                Targets.Add(Piece);
            }
            ComponentSeconds += FPlatformTime::Seconds() - CreateStart;
        }
        // Only now, after the swap check above has reported a failure it found: the cooks started below are new,
        // and a failure of theirs is reported again.
        State.bCookFailureReported = false;
        for (int32 Index = 0; Index < Targets.Num(); ++Index)
        {
            // With bDeferCollisionUpdates, SetMesh only invalidates the current body setup's cooked meshes; the body
            // in the physics scene keeps its own reference to them and goes on colliding.
            const double SetStart = FPlatformTime::Seconds();
            Targets[Index]->SetMesh(MoveTemp(Result.Pieces[Index]));
            SetMeshSeconds += FPlatformTime::Seconds() - SetStart;
            // Async path: a new body setup is cooked; FinishPhysicsAsyncCook swaps it in.
            const double CookStart = FPlatformTime::Seconds();
            Targets[Index]->UpdateCollision(/*bOnlyIfPending=*/ false);
            CookStartSeconds += FPlatformTime::Seconds() - CookStart;
        }
    }

    UE_LOG(LogReflectionsDigTerrain, Verbose,
        TEXT("DIGSPIKE headless commit %s (%s, %d pieces, %d vertices): total %.2f ms, components %.2f, set mesh %.2f, cook start %.2f, destroy %.2f"),
        *Chunk.ToString(), Kind, Result.Pieces.Num(), Result.SourceVertexCount, MillisecondsSince(StartSeconds),
        ComponentSeconds * 1000.0, SetMeshSeconds * 1000.0, CookStartSeconds * 1000.0, DestroySeconds * 1000.0);
}

void AReflectionsDigTerrain::RetireCurrentSet(FReflectionsDigTerrainChunk& State, double& InOutDestroySeconds)
{
    if (State.Pieces.IsEmpty())
    {
        // The chunk was emptied: its retiring set is still the last collision it had.
        return;
    }
    const double DestroyStart = FPlatformTime::Seconds();
    if (State.Retiring.IsEmpty() || AllHaveCollision(State.Pieces))
    {
        DestroyPieces(State.Retiring);
        State.Retiring = MoveTemp(State.Pieces);
        for (UReflectionsDigChunkComponent* Old : State.Retiring)
        {
            if (Old != nullptr)
            {
                Old->SetVisibility(false);
                // Old collision: it leaves navigation now (the engine removes it from the navigation octree and
                // dirties its area), not when it is destroyed after the swap.
                Old->SetCanEverAffectNavigation(false);
            }
        }
        if (const UWorld* World = GetWorld())
        {
            LastNavUpdateSeconds = World->GetTimeSeconds();
        }
    }
    else
    {
        // The current set never got collision of its own; the retiring set is still the newest that collides. If a
        // failed cook had given it its navigation back, the new set about to cook makes it old collision again.
        DestroyPieces(State.Pieces);
        SetRetiringSetNavigation(State, /*bAffects=*/ false);
    }
    State.Pieces.Reset();
    InOutDestroySeconds += FPlatformTime::Seconds() - DestroyStart;
}

void AReflectionsDigTerrain::SetRetiringSetNavigation(FReflectionsDigTerrainChunk& State, bool bAffects)
{
    bool bChanged = false;
    for (UReflectionsDigChunkComponent* Piece : State.Retiring)
    {
        if (Piece != nullptr && Piece->CanEverAffectNavigation() != bAffects)
        {
            // The engine adds the piece to the navigation octree with its current body, or removes it, and dirties
            // its area.
            Piece->SetCanEverAffectNavigation(bAffects);
            bChanged = true;
        }
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
        DestroyPieces(State->Pieces);
        DestroyPieces(State->Retiring);
        Chunks.Remove(Chunk);
    }
}

UDynamicMeshComponent* AReflectionsDigTerrain::FindChunkComponent(FIntVector Chunk) const
{
    const FReflectionsDigTerrainChunk* State = Chunks.Find(Chunk);
    return State != nullptr && !State->Pieces.IsEmpty() ? State->Pieces[0].Get() : nullptr;
}

int32 AReflectionsDigTerrain::GetChunkPieceCount(FIntVector Chunk) const
{
    const FReflectionsDigTerrainChunk* State = Chunks.Find(Chunk);
    return State != nullptr ? State->Pieces.Num() : 0;
}

int32 AReflectionsDigTerrain::GetRetiringPieceCount(FIntVector Chunk) const
{
    const FReflectionsDigTerrainChunk* State = Chunks.Find(Chunk);
    return State != nullptr ? State->Retiring.Num() : 0;
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
        for (const TArray<TObjectPtr<UReflectionsDigChunkComponent>>* Set : { &Pair.Value.Pieces, &Pair.Value.Retiring })
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

void AReflectionsDigTerrain::UpdatePieceNavigation(UReflectionsDigChunkComponent& Piece)
{
    UWorld* World = GetWorld();
    // A retiring piece no longer affects navigation; a destroyed one has unregistered. Between EndPlay and the
    // world's end the grid is gone, so a late cook asks for nothing either.
    if (Grid == nullptr || World == nullptr || World->bIsTearingDown || !Piece.IsRegistered() || Piece.IsBeingDestroyed()
        || !Piece.CanEverAffectNavigation())
    {
        return;
    }
    FNavigationSystem::UpdateComponentData(Piece);
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
    Piece->SetCanEverAffectNavigation(true);
    if (GroundMaterial != nullptr)
    {
        Piece->SetMaterial(0, GroundMaterial);
    }
    // Registered while still empty, so creating its physics state cooks nothing on the game thread.
    Piece->RegisterComponent();
    return Piece;
}
