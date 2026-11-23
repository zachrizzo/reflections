#pragma once

#include "CoreMinimal.h"
#include "Components/DynamicMeshComponent.h"
#include "Digging/ReflectionsDigGrid.h"
#include "Digging/ReflectionsDigPieces.h"
#include "GameFramework/Actor.h"
#include "ReflectionsDigTerrain.generated.h"

class UBodySetup;
class UBoxComponent;
class UMaterialInterface;
enum class ENavDataGatheringMode : uint8;
struct FNavigableGeometryExport;
struct FReflectionsDigMeshData;

/** The terrain's log. Its Verbose lines time each commit and swap (tests raise it to read them). */
DECLARE_LOG_CATEGORY_EXTERN(LogReflectionsDigTerrain, Log, All);

/**
 * The mesh component of one chunk piece. It knows whether its newest async collision cook is still running and how
 * its cooks ended: the engine keeps that queue protected, so this subclass watches RebuildPhysicsData and
 * FinishPhysicsAsyncCook. When a cook brings its new body in, it has its terrain tell navigation (a dynamic mesh
 * component does not do that by itself).
 *
 * Navigation never reads the piece's body setup: the piece exports its own triangles (built on the worker with its
 * mesh), so navigation can never build the piece's collision on the game thread while its background cook runs. The
 * triangles exported are those of the mesh whose collision is in: a new mesh's triangles wait for its cook.
 */
UCLASS(Transient)
class REFLECTIONS_API UReflectionsDigChunkComponent : public UDynamicMeshComponent
{
    GENERATED_BODY()

public:
    UReflectionsDigChunkComponent();

    /**
     * The navigation triangles of the mesh just set (call it together with SetMesh). Navigation exports them once a
     * cook of that mesh has brought its collision in; until then it keeps the previous mesh's.
     */
    void SetNavGeometry(FReflectionsDigNavGeometry&& InGeometry);

    /** Exports the piece's own triangles with ExportCustomMesh and returns false: the body setup export is not required. */
    virtual bool DoCustomNavigableGeometryExport(FNavigableGeometryExport& GeomExport) const override;

    /** Instant: the export runs on the game thread when navigation takes the piece in, never lazily on a worker. */
    virtual ENavDataGatheringMode GetGeometryGatheringMode() const override;

    /** Only while the piece counts for navigation (see CountsForNavigation), and then as any primitive. */
    virtual bool IsNavigationRelevant() const override;

    /**
     * Whether the piece counts for navigation: a new piece only once its first cook has brought collision in; a
     * retiring piece not at all, unless its set was kept after a failed cook and got its navigation back.
     */
    bool CountsForNavigation() const;

    /** True from the start of a collision cook until the newest one has finished. */
    bool IsCollisionCookPending() const;

    /**
     * True once a cook has brought a body in: the component has collision of its own (perhaps older than its mesh). A
     * cook that ends inside RebuildPhysicsData counts only if the body setup really holds collision data.
     */
    bool HasCollision() const;

    /** True when the newest finished cook failed (the engine kept the previous body). */
    bool DidLastCookFail() const;

#if WITH_DEV_AUTOMATION_TESTS
    /** Tests only: the piece's next cook to finish is handed to the engine as failed, so it keeps its previous body. */
    void FailNextCookForTest();
#endif

protected:
    virtual void RebuildPhysicsData() override;
    virtual void FinishPhysicsAsyncCook(bool bSuccess, UBodySetup* FinishedBodySetup) override;

private:
    friend class AReflectionsDigTerrain;

    /** Whether the piece counts for navigation; it decides, not CanEverAffectNavigation (see CountsForNavigation). */
    enum class ENavigationState : uint8
    {
        /** Created, its first cook not in yet: navigation does not take it. */
        WaitingForCollision,
        Counts,
        /** Retiring: old collision. */
        Excluded,
    };

    /**
     * Tells the engine, which caches a component's navigation relevance, that it may have changed: the piece joins
     * navigation (with its current triangles) or leaves it.
     */
    void RefreshNavigationRelevance();

    /** A cook of the mesh given with the newest SetNavGeometry has brought collision in: navigation exports its triangles from now on. */
    void PromoteNavGeometry();

    /** OnMeshChanged: the mesh is new (with deferred collision updates, the current body setup has just been cleared). */
    void NoteMeshChanged();

    /**
     * The game-thread cook detector (see GetGameThreadCookCount), run when a cook finishes and before the engine's
     * FinishPhysicsAsyncCook: counts once when the body setup in place was built by someone other than a cook of
     * this piece's current mesh. It only counts.
     */
    void CountGameThreadCook(const UBodySetup* FinishedBodySetup);

    /** The body setup of the newest cook still running, or null. */
    UPROPERTY(Transient)
    TObjectPtr<UBodySetup> PendingCook;

    bool bHasCollision = false;
    bool bLastCookFailed = false;

    ENavigationState NavigationState = ENavigationState::WaitingForCollision;
    /** The triangles navigation exports: those of the mesh whose collision is in. Empty before the first cook. */
    FReflectionsDigNavGeometry NavGeometry;
    /** From SetNavGeometry, until the next cook starts. */
    FReflectionsDigNavGeometry NewNavGeometry;
    bool bHasNewNavGeometry = false;
    /** The triangles of the mesh the newest cook builds, until it brings its collision in. */
    FReflectionsDigNavGeometry CookingNavGeometry;
    bool bHasCookingNavGeometry = false;

    /** Raised by every mesh change. */
    int32 MeshChangeSerial = 0;
    /** MeshChangeSerial when PendingCook started. */
    int32 PendingCookMeshSerial = INDEX_NONE;
    /** MeshChangeSerial while RebuildPhysicsData runs (a cook can finish inside it), else INDEX_NONE. */
    int32 RebuildMeshSerial = INDEX_NONE;
    /** The body setup a cook of this piece last brought in, and the mesh it was cooked from. */
    TWeakObjectPtr<const UBodySetup> CookedBody;
    int32 CookedBodyMeshSerial = INDEX_NONE;
    /** The body setup and mesh last counted by the detector, so one game-thread build is counted once. */
    TWeakObjectPtr<const UBodySetup> LastCountedBody;
    int32 LastCountedMeshSerial = INDEX_NONE;

#if WITH_DEV_AUTOMATION_TESTS
    bool bFailNextCookForTest = false;
#endif
};

/** The terrain's own game-thread time, summed since BeginPlay, by kind of work. For measurements; it changes nothing. */
struct FReflectionsDigTerrainTimings
{
    /** CommitChunkPieces: creating or reusing components, setting meshes, starting cooks (and the reuse path's swap check). */
    double CommitSeconds = 0.0;
    /** FinishCollisionSwaps: the swap check, destroying retiring sets. */
    double SwapCheckSeconds = 0.0;
    /** The engine's own work when a piece's cook finishes (UDynamicMeshComponent::FinishPhysicsAsyncCook). */
    double CookFinishSeconds = 0.0;
    /** All the calls that tell navigation about pieces (some run inside CommitSeconds and SwapCheckSeconds). */
    double NavUpdateSeconds = 0.0;
    /**
     * Of those, the ones after a cook brought a piece's new body in. A cook that finishes later, in its own callback,
     * is outside the commit and the swap check; one that finishes inside the commit's own collision update is counted
     * inside CommitSeconds as well.
     */
    double NavAfterCookSeconds = 0.0;
    /** Pieces given a new mesh and a new cook, and their vertices. */
    int32 CookStartPieces = 0;
    int64 CookStartVertices = 0;
};

/**
 * The mesh components of one chunk, in eight slots indexed by block (ReflectionsDig::BlocksPerChunk, block index
 * X + 2 * Y + 4 * Z). The swap rules are at the top of the class's .cpp.
 */
USTRUCT()
struct FReflectionsDigTerrainChunk
{
    GENERATED_BODY()

    /** The chunk's current pieces by block; null where the block has no surface. */
    UPROPERTY(Transient)
    TObjectPtr<UReflectionsDigChunkComponent> Pieces[8];

    /**
     * Retiring pieces by block, hidden and still colliding: in a block that shows a new piece, the newest piece that
     * really collided before it (together, the chunk's retiring set); in a block that shows nothing, its last piece.
     */
    UPROPERTY(Transient)
    TObjectPtr<UReflectionsDigChunkComponent> Retiring[8];

    /** The hash of the mesh each slot shows (FReflectionsDigChunkResult::PieceHash); 0 for an empty slot. */
    uint64 PieceHash[8] = {};

    /** Blocks whose current pieces the retiring set waits for: those the commits that made it created or changed. */
    uint8 SwapWaitMask = 0;

    /** A failed cook kept the retiring set; it has been reported. */
    bool bCookFailureReported = false;
};
static_assert(ReflectionsDig::BlocksPerChunk == 8, "FReflectionsDigTerrainChunk has one slot per block");

/**
 * A diggable patch of ground. It owns the grid, one or more mesh components per chunk and a safety floor under the
 * grid; the dig subsystem decides what is meshed and when. The actor must be unrotated and unscaled: its X and Y are
 * the patch's minimum corner and the ground surface lies 400 cm below the top of the grid. The grid origin sits half a
 * cell (25 cm) inside that corner in X and Y, so the meshed ground spans exactly the patch. One terrain per world.
 */
UCLASS()
class REFLECTIONS_API AReflectionsDigTerrain : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsDigTerrain();

    UPROPERTY(EditAnywhere, Category = "Digging")
    FIntVector SizeInChunks = FIntVector(3, 3, 2);

    /** World Z of the ground surface. */
    UPROPERTY(EditAnywhere, Category = "Digging")
    float GroundHeightCm = 0.0f;

    /** With a focus, chunks whose box is farther than this from it are not meshed. */
    UPROPERTY(EditAnywhere, Category = "Digging")
    float MeshRadiusCm = 2400.0f;

    /** What the pieces draw with. When null they use the plain engine material /Engine/BasicShapes/BasicShapeMaterial, never the engine default. */
    UPROPERTY(EditAnywhere, Category = "Digging")
    TObjectPtr<UMaterialInterface> GroundMaterial;

    /** Builds the mesh's pieces on the game thread, then commits them. For tests and tools; the subsystem builds on workers. */
    void CommitChunk(FIntVector Chunk, FReflectionsDigMeshData&& Mesh);

    /**
     * Shows a chunk's new pieces (positions relative to the grid origin), one slot per block. Only the slots whose
     * hash changed are touched; an empty slot retires its block's piece. The previous collision of the blocks a commit
     * changes stays until all their new collision has finished cooking (see the collision swap in the class's .cpp).
     */
    void CommitChunkPieces(FIntVector Chunk, FReflectionsDigChunkResult&& Result);

    /** Destroys the chunk's components at once, retiring ones included. */
    void ReleaseChunk(FIntVector Chunk);

    /** The chunk's first current piece (lowest block index), or null. */
    UDynamicMeshComponent* FindChunkComponent(FIntVector Chunk) const;

    /** How many of the chunk's slots hold a current piece. */
    int32 GetChunkPieceCount(FIntVector Chunk) const;

    /** The Index-th filled slot's piece (0 to GetChunkPieceCount - 1, lowest block index first), or null. */
    UDynamicMeshComponent* GetChunkPiece(FIntVector Chunk, int32 Index) const;

    /** The current piece of one block's slot (0 to ReflectionsDig::BlocksPerChunk - 1), or null. */
    UDynamicMeshComponent* GetChunkBlockPiece(FIntVector Chunk, int32 Block) const;

    /** The chunk's retiring pieces: hidden, still colliding until their swap. */
    int32 GetRetiringPieceCount(FIntVector Chunk) const;

    /** Slots given a new mesh by commits, summed since BeginPlay. For measurements and tests. */
    int32 GetPiecesChangedCount() const;

    /** Filled slots commits left alone because their hash had not changed, summed since BeginPlay. For measurements and tests. */
    int32 GetPiecesKeptCount() const;

    /** Null before BeginPlay and after EndPlay. */
    FReflectionsDigGrid* GetGrid() const;

    /** The largest vertex count among every piece that still collides, retiring ones included; 0 with none. */
    int32 GetLargestCollisionVertexCount() const;

    /**
     * Destroys retiring sets whose time has come: one replaced by pieces once every piece has cooked successfully,
     * one replaced by nothing only when bTerrainQuiet (no task in flight, no queued commit, no cook pending anywhere and
     * no wanted chunk dirty, so no mesh task is still to start).
     */
    void FinishCollisionSwaps(bool bTerrainQuiet);

    /** True while any of the chunk's current pieces has a collision cook running (the subsystem then holds its next commit). */
    bool IsChunkCooking(FIntVector Chunk) const;

    /** True while any piece, current or retiring, has a collision cook running. */
    bool HasCookPending() const;

    /**
     * True while any cook runs or any retiring set still waits for the swap check. A set kept by a failed cook waits
     * only until the swap check has handled the failure.
     */
    bool IsWaitingOnCollision() const;

    /** The blocking box under the whole patch, its top 30 cm below the grid floor. It never affects navigation. */
    UBoxComponent* GetSafetyFloor() const;

    /**
     * World time of the last navigation update the terrain asked for: a piece's collision came in, or a set retired.
     * Negative before the first.
     */
    double GetLastNavUpdateSeconds() const;

    /**
     * How many navigation updates the terrain has asked for: each call that tells navigation about one piece (its new
     * body is in, or it starts or stops affecting navigation). For measurements; it changes nothing.
     */
    int32 GetNavUpdateCount() const;

    /** The game-thread seconds spent inside those calls, summed. The navigation system's own later work is not in it. */
    double GetNavUpdateSeconds() const;

    /** How many chunks ReleaseChunk has released (chunks that showed anything), and the game-thread seconds it took. For measurements. */
    int32 GetChunkReleaseCount() const;
    /** How many newest collision cooks of its pieces have finished, failed ones included. For measurements. */
    int32 GetCookCompletionCount() const;

    /**
     * How many times a piece's collision was built on the game thread by someone else while its own background cook
     * ran: a cook finished and found the body setup it was about to replace with its physics meshes created and at
     * least one triangle mesh, although the piece's mesh had changed since a cook of the piece last brought that body
     * in, or no cook of the piece ever did. Checked before the engine's FinishPhysicsAsyncCook runs. It must stay 0;
     * it only counts.
     */
    int32 GetGameThreadCookCount() const;
    /** The terrain's own game-thread time by kind of work, summed since BeginPlay. For measurements. */
    FReflectionsDigTerrainTimings GetTimings() const;
    double GetChunkReleaseSeconds() const;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    friend class UReflectionsDigChunkComponent;

    /**
     * A piece's new body is in place: navigation takes the piece's triangles again, and a new piece waiting for its
     * first collision joins navigation now. Only for a piece of a live terrain that does not leave navigation; a
     * retiring or unregistered piece, or a world being torn down, asks for nothing.
     */
    void UpdatePieceNavigation(UReflectionsDigChunkComponent& Piece);

    UReflectionsDigChunkComponent* CreatePieceComponent();
    /**
     * Moves the current pieces of ChangedBlocks out of the way of new ones, keeping the newest collision that really
     * exists. A piece that retires stops affecting navigation at once: it is old collision.
     */
    void RetireCurrentSet(FReflectionsDigTerrainChunk& State, uint8 ChangedBlocks, double& InOutDestroySeconds);

    /** Lets the chunk's retiring set affect navigation, or not, telling navigation only for pieces that change. */
    void SetRetiringSetNavigation(FReflectionsDigTerrainChunk& State, bool bAffects);

    UPROPERTY(VisibleAnywhere, Category = "Digging")
    TObjectPtr<UBoxComponent> SafetyFloor;

    TUniquePtr<FReflectionsDigGrid> Grid;

    /** GroundMaterial, or the plain engine material when that is null; resolved at BeginPlay and set on each new piece. */
    UPROPERTY(Transient)
    TObjectPtr<UMaterialInterface> PieceMaterial;

    /** /Engine/BasicShapes/BasicShapeMaterial, found in the constructor so it is a hard reference (cooked with the terrain). */
    UPROPERTY()
    TObjectPtr<UMaterialInterface> PlainGroundMaterial;

    double LastNavUpdateSeconds = -1.0;
    int32 NavUpdateCount = 0;
    double NavUpdateSeconds = 0.0;
    int32 ReleaseCount = 0;
    int32 CookCompletionCount = 0;
    int32 GameThreadCookCount = 0;
    double CommitSeconds = 0.0;
    double SwapCheckSeconds = 0.0;
    double CookFinishSeconds = 0.0;
    double NavAfterCookSeconds = 0.0;
    int32 CookStartPieces = 0;
    int64 CookStartVertices = 0;
    double ReleaseSeconds = 0.0;
    int32 PiecesChangedCount = 0;
    int32 PiecesKeptCount = 0;

    /** Rebuilt from the grid at run time, never saved. */
    UPROPERTY(Transient)
    TMap<FIntVector, FReflectionsDigTerrainChunk> Chunks;
};
