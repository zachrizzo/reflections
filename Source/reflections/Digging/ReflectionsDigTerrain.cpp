#include "Digging/ReflectionsDigTerrain.h"

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "Digging/ReflectionsDigMesher.h"
#include "Digging/ReflectionsDigSubsystem.h"
#include "Digging/ReflectionsDigTypes.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicMesh/DynamicMeshAttributeSet.h"
#include "Engine/EngineTypes.h"
#include "Engine/World.h"
#include "IndexTypes.h"
#include "Materials/MaterialInterface.h"
#include "PhysicsEngine/BodySetup.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsDigTerrain, Log, All);

using UE::Geometry::FDynamicMesh3;
using UE::Geometry::FIndex3i;

namespace
{
    constexpr float ChunkHeightCm = ReflectionsDig::ChunkCells * ReflectionsDig::CellSizeCm;
    /** The ground surface lies this far below the top of the grid. */
    constexpr float GroundBelowGridTopCm = 400.0f;
    /**
     * More slabs than any chunk needs: a slab one cube layer thick holds at most about 3 * 34 * 34 vertices,
     * far under the limit, and 64 slabs are thinner than that. Reaching it would mean a broken mesh.
     */
    constexpr int32 MaxSlabs = 64;

    /** For each of NumSlabs equal-height slabs between MinZ and MaxZ, the triangles whose centroid it holds. */
    TArray<TArray<int32>> AssignTrianglesToSlabs(const FReflectionsDigMeshData& Mesh, float MinZ, float MaxZ, int32 NumSlabs)
    {
        TArray<TArray<int32>> Slabs;
        Slabs.SetNum(NumSlabs);
        const int32 NumTriangles = Mesh.Triangles.Num() / 3;
        const float SlabHeight = (MaxZ - MinZ) / static_cast<float>(NumSlabs);
        for (int32 Triangle = 0; Triangle < NumTriangles; ++Triangle)
        {
            int32 Slab = 0;
            if (SlabHeight > 0.0f)
            {
                const float CentroidZ = (Mesh.Positions[Mesh.Triangles[3 * Triangle]].Z
                    + Mesh.Positions[Mesh.Triangles[3 * Triangle + 1]].Z
                    + Mesh.Positions[Mesh.Triangles[3 * Triangle + 2]].Z) / 3.0f;
                Slab = FMath::Clamp(FMath::FloorToInt32((CentroidZ - MinZ) / SlabHeight), 0, NumSlabs - 1);
            }
            Slabs[Slab].Add(Triangle);
        }
        return Slabs;
    }

    /** The most vertices any slab uses (each slab counts every vertex its triangles touch once). */
    int32 LargestSlabVertexCount(const FReflectionsDigMeshData& Mesh, const TArray<TArray<int32>>& Slabs)
    {
        TArray<int32> LastSlabOfVertex;
        LastSlabOfVertex.Init(INDEX_NONE, Mesh.Positions.Num());
        int32 Largest = 0;
        for (int32 Slab = 0; Slab < Slabs.Num(); ++Slab)
        {
            int32 Count = 0;
            for (const int32 Triangle : Slabs[Slab])
            {
                for (int32 Corner = 0; Corner < 3; ++Corner)
                {
                    int32& Last = LastSlabOfVertex[Mesh.Triangles[3 * Triangle + Corner]];
                    if (Last != Slab)
                    {
                        Last = Slab;
                        ++Count;
                    }
                }
            }
            Largest = FMath::Max(Largest, Count);
        }
        return Largest;
    }

    /**
     * One piece's dynamic mesh: its own copy of the vertices the triangles use, with the mesher's per-vertex
     * normals in the primary normal overlay (one element per vertex, which the scene proxy renders with).
     * FDynamicMesh3 refuses a triangle on an edge that already has two; such a triangle gets its own vertex copies.
     */
    FDynamicMesh3 BuildPieceMesh(const FReflectionsDigMeshData& Mesh, const TArray<int32>& Triangles)
    {
        FDynamicMesh3 Piece;
        Piece.EnableAttributes();
        UE::Geometry::FDynamicMeshNormalOverlay* Normals = Piece.Attributes()->PrimaryNormals();
        TArray<int32> PieceVertexOf;
        PieceVertexOf.Init(INDEX_NONE, Mesh.Positions.Num());

        // Vertex and normal element IDs stay equal: each vertex appends exactly one element.
        auto AppendVertex = [&Piece, Normals, &Mesh](int32 Source)
        {
            const int32 Vertex = Piece.AppendVertex(FVector3d(Mesh.Positions[Source]));
            Normals->AppendElement(Mesh.Normals[Source]);
            return Vertex;
        };

        for (const int32 Triangle : Triangles)
        {
            FIndex3i Corners;
            for (int32 Corner = 0; Corner < 3; ++Corner)
            {
                const int32 Source = Mesh.Triangles[3 * Triangle + Corner];
                int32& Vertex = PieceVertexOf[Source];
                if (Vertex == INDEX_NONE)
                {
                    Vertex = AppendVertex(Source);
                }
                Corners[Corner] = Vertex;
            }
            int32 NewTriangle = Piece.AppendTriangle(Corners);
            if (NewTriangle == FDynamicMesh3::NonManifoldID)
            {
                for (int32 Corner = 0; Corner < 3; ++Corner)
                {
                    Corners[Corner] = AppendVertex(Mesh.Triangles[3 * Triangle + Corner]);
                }
                NewTriangle = Piece.AppendTriangle(Corners);
            }
            if (NewTriangle >= 0)
            {
                Normals->SetTriangle(NewTriangle, Corners);
            }
        }
        return Piece;
    }

    /**
     * The chunk's pieces: one mesh at or under MaxPieceVertices, otherwise the fewest equal-height horizontal
     * slabs (over the mesh's Z extent) in which every piece holds at most MaxPieceVertices vertices.
     * Empty slabs make no piece.
     */
    TArray<FDynamicMesh3> BuildPieces(const FReflectionsDigMeshData& Mesh)
    {
        float MinZ = TNumericLimits<float>::Max();
        float MaxZ = TNumericLimits<float>::Lowest();
        for (const FVector3f& Position : Mesh.Positions)
        {
            MinZ = FMath::Min(MinZ, Position.Z);
            MaxZ = FMath::Max(MaxZ, Position.Z);
        }

        TArray<FDynamicMesh3> Pieces;
        for (int32 NumSlabs = 1; NumSlabs <= MaxSlabs; ++NumSlabs)
        {
            const TArray<TArray<int32>> Slabs = AssignTrianglesToSlabs(Mesh, MinZ, MaxZ, NumSlabs);
            const bool bLastTry = NumSlabs == MaxSlabs;
            if (!bLastTry && LargestSlabVertexCount(Mesh, Slabs) > ReflectionsDig::MaxPieceVertices)
            {
                continue;
            }
            Pieces.Reset();
            bool bFits = true;
            for (const TArray<int32>& Slab : Slabs)
            {
                if (!Slab.IsEmpty())
                {
                    const FDynamicMesh3& Piece = Pieces.Add_GetRef(BuildPieceMesh(Mesh, Slab));
                    bFits &= Piece.VertexCount() <= ReflectionsDig::MaxPieceVertices;
                }
            }
            if (bFits || bLastTry)
            {
                if (!bFits)
                {
                    UE_LOG(LogReflectionsDigTerrain, Warning, TEXT("A chunk mesh of %d vertices does not fit %d slabs of %d vertices"),
                        Mesh.Positions.Num(), MaxSlabs, ReflectionsDig::MaxPieceVertices);
                }
                break;
            }
        }
        return Pieces;
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
}

void UReflectionsDigChunkComponent::SetMeshAndCook(FDynamicMesh3&& NewMesh)
{
    // With bDeferCollisionUpdates, SetMesh only invalidates the current body setup's cooked meshes; the body
    // in the physics scene keeps its own reference to them and goes on colliding.
    SetMesh(MoveTemp(NewMesh));
    // Async path: a new body setup is cooked; FinishPhysicsAsyncCook swaps it in and recreates the physics state.
    UpdateCollision(/*bOnlyIfPending=*/ false);
}

bool UReflectionsDigChunkComponent::IsCollisionCookPending() const
{
    return PendingCook != nullptr;
}

void UReflectionsDigChunkComponent::RebuildPhysicsData()
{
    // The async path appends one new body setup to AsyncBodySetupQueue. A cook that finishes inside this call
    // (nothing to cook) has already left the queue, and the sync path empties it: neither is pending.
    UBodySetup* const LastBefore = AsyncBodySetupQueue.IsEmpty() ? nullptr : AsyncBodySetupQueue.Last().Get();
    Super::RebuildPhysicsData();
    UBodySetup* const LastAfter = AsyncBodySetupQueue.IsEmpty() ? nullptr : AsyncBodySetupQueue.Last().Get();
    PendingCook = LastAfter != LastBefore ? LastAfter : nullptr;
}

void UReflectionsDigChunkComponent::FinishPhysicsAsyncCook(bool bSuccess, UBodySetup* FinishedBodySetup)
{
    Super::FinishPhysicsAsyncCook(bSuccess, FinishedBodySetup);
    // Older cooks are aborted when a newer one starts and never report back; only the newest clears the flag.
    if (FinishedBodySetup == PendingCook)
    {
        PendingCook = nullptr;
    }
}

AReflectionsDigTerrain::AReflectionsDigTerrain()
{
    PrimaryActorTick.bCanEverTick = false;
    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
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
    TArray<FIntVector> Committed;
    Chunks.GetKeys(Committed);
    for (const FIntVector& Chunk : Committed)
    {
        ReleaseChunk(Chunk);
    }
    Grid.Reset();

    Super::EndPlay(EndPlayReason);
}

void AReflectionsDigTerrain::CommitChunk(FIntVector Chunk, FReflectionsDigMeshData&& Mesh)
{
    if (Mesh.IsEmpty() || Grid == nullptr)
    {
        ReleaseChunk(Chunk);
        return;
    }
    TArray<FDynamicMesh3> NewPieces = BuildPieces(Mesh);
    if (NewPieces.IsEmpty())
    {
        ReleaseChunk(Chunk);
        return;
    }

    FReflectionsDigTerrainChunk& State = Chunks.FindOrAdd(Chunk);
    if (NewPieces.Num() == 1 && State.Pieces.Num() == 1 && State.Pieces[0] != nullptr)
    {
        // One piece before and after: reuse it. The engine keeps its old body until the new cook is in.
        State.Pieces[0]->SetMeshAndCook(MoveTemp(NewPieces[0]));
        return;
    }

    // The set of pieces changes (or is split): the slabs move, so one piece's old body may not cover what another
    // piece's new body leaves out. Keep the previous set colliding (hidden) until every new piece has cooked.
    if (State.Retiring.IsEmpty())
    {
        State.Retiring = MoveTemp(State.Pieces);
        for (UReflectionsDigChunkComponent* Old : State.Retiring)
        {
            if (Old != nullptr)
            {
                Old->SetVisibility(false);
            }
        }
    }
    else
    {
        // The retiring set is the last one that finished cooking; the current set never did, so drop it.
        DestroyPieces(State.Pieces);
    }
    State.Pieces.Reset();
    for (FDynamicMesh3& PieceMesh : NewPieces)
    {
        UReflectionsDigChunkComponent* Piece = CreatePieceComponent();
        Piece->SetMeshAndCook(MoveTemp(PieceMesh));
        State.Pieces.Add(Piece);
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

FReflectionsDigGrid* AReflectionsDigTerrain::GetGrid() const
{
    return Grid.Get();
}

int32 AReflectionsDigTerrain::GetLargestCollisionVertexCount() const
{
    int32 Largest = 0;
    for (const TPair<FIntVector, FReflectionsDigTerrainChunk>& Pair : Chunks)
    {
        for (const UReflectionsDigChunkComponent* Piece : Pair.Value.Pieces)
        {
            if (Piece != nullptr && Piece->GetMesh() != nullptr)
            {
                Largest = FMath::Max(Largest, Piece->GetMesh()->VertexCount());
            }
        }
    }
    return Largest;
}

void AReflectionsDigTerrain::FinishCollisionSwaps()
{
    for (TPair<FIntVector, FReflectionsDigTerrainChunk>& Pair : Chunks)
    {
        FReflectionsDigTerrainChunk& State = Pair.Value;
        if (!State.Retiring.IsEmpty() && !AnyCookPending(State.Pieces))
        {
            DestroyPieces(State.Retiring);
        }
    }
}

bool AReflectionsDigTerrain::IsWaitingOnCollision() const
{
    for (const TPair<FIntVector, FReflectionsDigTerrainChunk>& Pair : Chunks)
    {
        if (!Pair.Value.Retiring.IsEmpty() || AnyCookPending(Pair.Value.Pieces))
        {
            return true;
        }
    }
    return false;
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
