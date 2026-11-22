#include "Digging/ReflectionsDigSubsystem.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigCommitQueue.h"
#include "Digging/ReflectionsDigGrid.h"
#include "Digging/ReflectionsDigMesher.h"
#include "Digging/ReflectionsDigPieces.h"
#include "Digging/ReflectionsDigTerrain.h"
#include "Digging/ReflectionsDigTypes.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Tasks/Task.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsDigSubsystem, Log, All);

namespace
{
    TAutoConsoleVariable<int32> CVarMaxCommitsPerFrame(
        TEXT("reflections.Dig.MaxCommitsPerFrame"),
        2,
        TEXT("Finished dig chunk meshes committed to the terrain per frame. Values below 1 count as 1."));

    constexpr double ChunkSizeCm = ReflectionsDig::ChunkCells * ReflectionsDig::CellSizeCm;

    bool IsInFlight(const UE::Tasks::FTask& Task)
    {
        return Task.IsValid() && !Task.IsCompleted();
    }
}

bool UReflectionsDigSubsystem::Dig(FVector Center, float RadiusCm, EReflectionsDigMode Mode)
{
    AReflectionsDigTerrain* Terrain = RegisteredTerrain.Get();
    FReflectionsDigGrid* Grid = Terrain != nullptr ? Terrain->GetGrid() : nullptr;
    if (Grid == nullptr)
    {
        return false;
    }
    FReflectionsDigStamp Stamp;
    Stamp.Center = Center;
    Stamp.RadiusCm = RadiusCm;
    Stamp.Mode = Mode;
    Stamp.Material = ReflectionsDig::MaterialTopsoil;
    TArray<FIntVector> DirtyChunks;
    Grid->ApplyStamp(Stamp, DirtyChunks);
    for (const FIntVector& Chunk : DirtyChunks)
    {
        if (FChunkFlow* Flow = ChunkFlows.Find(Chunk))
        {
            Flow->bDirty = true;
        }
    }
    return !DirtyChunks.IsEmpty();
}

void UReflectionsDigSubsystem::RegisterTerrain(AReflectionsDigTerrain* Terrain)
{
    if (Terrain == nullptr || Terrain->GetGrid() == nullptr)
    {
        return;
    }
    if (const AReflectionsDigTerrain* Current = RegisteredTerrain.Get())
    {
        if (Current != Terrain)
        {
            // The spike supports one terrain per world: the ignored terrain stays ignored, even after the first one
            // unregisters (it registers only from its own BeginPlay).
            UE_LOG(LogReflectionsDigSubsystem, Warning, TEXT("Only one dig terrain per world: %s is ignored while %s is registered."),
                *Terrain->GetName(), *Current->GetName());
        }
        return;
    }
    DropTerrainState();

    RegisteredTerrain = Terrain;
    Queue = MakeShared<FReflectionsDigCommitQueue, ESPMode::ThreadSafe>();
    const FIntVector Size = Terrain->GetGrid()->GetSizeInChunks();
    for (int32 Z = 0; Z < Size.Z; ++Z)
    {
        for (int32 Y = 0; Y < Size.Y; ++Y)
        {
            for (int32 X = 0; X < Size.X; ++X)
            {
                ChunkFlows.Add(FIntVector(X, Y, Z), FChunkFlow());
            }
        }
    }
}

void UReflectionsDigSubsystem::UnregisterTerrain(AReflectionsDigTerrain* Terrain)
{
    if (Terrain != nullptr && RegisteredTerrain.Get() == Terrain)
    {
        DropTerrainState();
    }
}

void UReflectionsDigSubsystem::SetFocusOverride(TOptional<FVector> Focus)
{
    FocusOverride = Focus;
}

bool UReflectionsDigSubsystem::IsIdle() const
{
    if (GetTasksInFlight() > 0 || GetQueuedCommits() > 0)
    {
        return false;
    }
    for (const TPair<FIntVector, FChunkFlow>& Pair : ChunkFlows)
    {
        if (Pair.Value.bWanted && Pair.Value.bDirty)
        {
            return false;
        }
    }
    const AReflectionsDigTerrain* Terrain = RegisteredTerrain.Get();
    return Terrain == nullptr || !Terrain->IsWaitingOnCollision();
}

int32 UReflectionsDigSubsystem::GetTasksInFlight() const
{
    int32 Count = 0;
    for (const TPair<FIntVector, FChunkFlow>& Pair : ChunkFlows)
    {
        Count += IsInFlight(Pair.Value.Task) ? 1 : 0;
    }
    for (const UE::Tasks::FTask& Task : DetachedTasks)
    {
        Count += IsInFlight(Task) ? 1 : 0;
    }
    return Count;
}

int32 UReflectionsDigSubsystem::GetQueuedCommits() const
{
    return Queue.IsValid() ? Queue->Num() : 0;
}

int32 UReflectionsDigSubsystem::GetCommitsLastTick() const
{
    return CommitsLastTick;
}

void UReflectionsDigSubsystem::Deinitialize()
{
    DropTerrainState();
    // The tasks touch nothing of ours, but they run this module's code: let them end before the world goes.
    for (const UE::Tasks::FTask& Task : DetachedTasks)
    {
        Task.Wait();
    }
    DetachedTasks.Reset();
    Super::Deinitialize();
}

void UReflectionsDigSubsystem::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    CommitsLastTick = 0;
    DetachedTasks.RemoveAll([](const UE::Tasks::FTask& Task) { return !IsInFlight(Task); });

    AReflectionsDigTerrain* Terrain = RegisteredTerrain.Get();
    if (Terrain == nullptr || Terrain->GetGrid() == nullptr)
    {
        // A terrain that went without unregistering.
        if (!ChunkFlows.IsEmpty() || Queue.IsValid())
        {
            DropTerrainState();
        }
        return;
    }
    // Quiet: nothing in flight, nothing queued, nothing cooking, and no wanted chunk dirty (at the start of a tick a
    // dirty chunk has not been launched yet, so it is work to come just like a task in flight). Only then may a
    // chunk that became empty drop the collision it still keeps, since a neighbour may still show the old hole into it.
    auto IsTerrainQuiet = [this, Terrain]()
    {
        if (GetTasksInFlight() > 0 || GetQueuedCommits() > 0 || Terrain->HasCookPending())
        {
            return false;
        }
        for (const TPair<FIntVector, FChunkFlow>& Pair : ChunkFlows)
        {
            if (Pair.Value.bWanted && Pair.Value.bDirty)
            {
                return false;
            }
        }
        return true;
    };
    UpdateStreaming(*Terrain);
    // Swaps run before the commits (a cook that finished since the last tick retires its old set before a new
    // commit can start another cook) and again after the launches.
    Terrain->FinishCollisionSwaps(IsTerrainQuiet());
    CommitFinishedMeshes(*Terrain);
    LaunchMeshTasks(*Terrain);
    Terrain->FinishCollisionSwaps(IsTerrainQuiet());
}

TStatId UReflectionsDigSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsDigSubsystem, STATGROUP_Tickables);
}

bool UReflectionsDigSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TOptional<FVector> UReflectionsDigSubsystem::FindFocus() const
{
    if (FocusOverride.IsSet())
    {
        return FocusOverride;
    }
    if (const UWorld* World = GetWorld())
    {
        for (FConstPlayerControllerIterator It = World->GetPlayerControllerIterator(); It; ++It)
        {
            const APlayerController* Controller = It->Get();
            if (Controller != nullptr && Controller->IsLocalController())
            {
                if (const APawn* Pawn = Controller->GetPawn())
                {
                    return Pawn->GetActorLocation();
                }
                break;
            }
        }
    }
    return TOptional<FVector>();
}

void UReflectionsDigSubsystem::UpdateStreaming(AReflectionsDigTerrain& Terrain)
{
    const TOptional<FVector> Focus = FindFocus();
    const FVector OriginCm = Terrain.GetGrid()->GetOriginCm();
    const double RadiusSquared = FMath::Square(static_cast<double>(Terrain.MeshRadiusCm));
    for (TPair<FIntVector, FChunkFlow>& Pair : ChunkFlows)
    {
        FChunkFlow& Flow = Pair.Value;
        if (Focus.IsSet())
        {
            const FBox ChunkBox(OriginCm + FVector(Pair.Key) * ChunkSizeCm, OriginCm + FVector(Pair.Key + FIntVector(1, 1, 1)) * ChunkSizeCm);
            Flow.bWanted = Terrain.MeshRadiusCm >= 0.0f && ChunkBox.ComputeSquaredDistanceToPoint(*Focus) <= RadiusSquared;
        }
        else
        {
            Flow.bWanted = true;
        }

        if (!Flow.bWanted)
        {
            // Whatever led here (a stale result committed after the chunk was left, say), an unwanted chunk shows nothing.
            Terrain.ReleaseChunk(Pair.Key);
            Flow.bMeshRequested = false;
        }
        else if (!Flow.bMeshRequested)
        {
            Flow.bDirty = true;
        }
    }
}

void UReflectionsDigSubsystem::CommitFinishedMeshes(AReflectionsDigTerrain& Terrain)
{
    const int32 Budget = FMath::Max(1, CVarMaxCommitsPerFrame.GetValueOnGameThread());
    // One cook at a time per chunk: a chunk whose current pieces are still cooking waits, its result keeps its place.
    Queue->PopUpTo(Budget, [&Terrain](FIntVector Chunk) { return !Terrain.IsChunkCooking(Chunk); }, [this, &Terrain](FIntVector Chunk, FReflectionsDigChunkResult&& Result)
    {
        const FChunkFlow* Flow = ChunkFlows.Find(Chunk);
        if (Flow == nullptr || !Flow->bWanted)
        {
            return;
        }
        Terrain.CommitChunkPieces(Chunk, MoveTemp(Result));
        ++CommitsLastTick;
    });
}

void UReflectionsDigSubsystem::LaunchMeshTasks(AReflectionsDigTerrain& Terrain)
{
    const FReflectionsDigGrid& Grid = *Terrain.GetGrid();
    // Copy every launching chunk's samples first, then launch them together, so the chunks of one dig mesh in
    // parallel instead of each task racing the next chunk's copy.
    TArray<FChunkFlow*, TInlineAllocator<8>> Launching;
    TArray<FReflectionsDigChunkSamples, TInlineAllocator<8>> AllSamples;
    for (TPair<FIntVector, FChunkFlow>& Pair : ChunkFlows)
    {
        FChunkFlow& Flow = Pair.Value;
        // At most one task per chunk: a chunk dirtied while its task runs waits here until that task has returned.
        if (!Flow.bWanted || !Flow.bDirty || IsInFlight(Flow.Task))
        {
            continue;
        }
        Flow.bDirty = false;
        Flow.bMeshRequested = true;
        Launching.Add(&Flow);
        Grid.CopyChunkSamples(Pair.Key, AllSamples.AddDefaulted_GetRef());
    }
    for (int32 Index = 0; Index < Launching.Num(); ++Index)
    {
        // The worker owns its samples and shares only the queue; it never touches the grid, this subsystem or any UObject.
        Launching[Index]->Task = UE::Tasks::Launch(TEXT("ReflectionsDigMeshChunk"),
            [Samples = MoveTemp(AllSamples[Index]), TaskQueue = Queue]()
            {
                FReflectionsDigMeshData Mesh;
                ReflectionsDigMesher::BuildFromSamples(Samples, Mesh);
                FReflectionsDigChunkResult Result;
                ReflectionsDigPieces::Build(Mesh, Result);
                TaskQueue->Push(Samples.Chunk, MoveTemp(Result));
            });
    }
}

void UReflectionsDigSubsystem::DropTerrainState()
{
    for (const TPair<FIntVector, FChunkFlow>& Pair : ChunkFlows)
    {
        if (IsInFlight(Pair.Value.Task))
        {
            DetachedTasks.Add(Pair.Value.Task);
        }
    }
    ChunkFlows.Reset();
    Queue.Reset();
    RegisteredTerrain.Reset();
}
