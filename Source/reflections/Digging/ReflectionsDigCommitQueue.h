#pragma once

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigMesher.h"
#include "HAL/CriticalSection.h"

/**
 * Finished chunk meshes waiting for the game thread: at most one per chunk, oldest-queued chunk first.
 * Knows nothing about UObjects. Every member takes the queue's lock, so Push is safe from any thread.
 */
class REFLECTIONS_API FReflectionsDigCommitQueue
{
public:
    /** Any thread. A second push for a chunk still queued replaces its mesh and keeps its place in line. */
    void Push(FIntVector Chunk, FReflectionsDigMeshData&& Mesh);

    /**
     * Game thread. Takes up to Max entries, oldest-queued chunk first, and hands each to Commit (called
     * outside the lock). Returns how many it committed.
     */
    int32 PopUpTo(int32 Max, TFunctionRef<void(FIntVector, FReflectionsDigMeshData&&)> Commit);

    /** Chunks waiting. */
    int32 Num() const;

private:
    struct FEntry
    {
        FIntVector Chunk;
        FReflectionsDigMeshData Mesh;
    };

    mutable FCriticalSection Lock;
    /** In the order each chunk was first pushed. */
    TArray<FEntry> Entries;
};
