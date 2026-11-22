#pragma once

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigPieces.h"
#include "HAL/CriticalSection.h"

/**
 * Finished chunk pieces waiting for the game thread: at most one per chunk, oldest-queued chunk first.
 * Knows nothing about UObjects. Every member takes the queue's lock, so Push is safe from any thread.
 */
class REFLECTIONS_API FReflectionsDigCommitQueue
{
public:
    /** Any thread. A second push for a chunk still queued replaces its result and keeps its place in line. */
    void Push(FIntVector Chunk, FReflectionsDigChunkResult&& Result);

    /**
     * Game thread. Takes up to Max entries, oldest-queued chunk first, and hands each to Commit. A chunk for which
     * CanCommit is false is skipped and keeps its place in line. Both callbacks run outside the lock. Returns how
     * many it committed (skipped chunks do not count).
     */
    int32 PopUpTo(int32 Max, TFunctionRef<bool(FIntVector)> CanCommit, TFunctionRef<void(FIntVector, FReflectionsDigChunkResult&&)> Commit);

    /** Chunks waiting. */
    int32 Num() const;

private:
    struct FEntry
    {
        FIntVector Chunk;
        FReflectionsDigChunkResult Result;
    };

    mutable FCriticalSection Lock;
    /** In the order each chunk was first pushed. */
    TArray<FEntry> Entries;
};
