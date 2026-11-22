#include "Digging/ReflectionsDigCommitQueue.h"

#include "CoreMinimal.h"
#include "Misc/ScopeLock.h"

void FReflectionsDigCommitQueue::Push(FIntVector Chunk, FReflectionsDigChunkResult&& Result)
{
    FScopeLock Guard(&Lock);
    for (FEntry& Entry : Entries)
    {
        if (Entry.Chunk == Chunk)
        {
            Entry.Result = MoveTemp(Result);
            return;
        }
    }
    Entries.Add(FEntry{ Chunk, MoveTemp(Result) });
}

int32 FReflectionsDigCommitQueue::PopUpTo(int32 Max, TFunctionRef<bool(FIntVector)> CanCommit, TFunctionRef<void(FIntVector, FReflectionsDigChunkResult&&)> Commit)
{
    // The order as it stands now; chunks pushed while this runs wait for the next call.
    TArray<FIntVector, TInlineAllocator<32>> Order;
    {
        FScopeLock Guard(&Lock);
        for (const FEntry& Entry : Entries)
        {
            Order.Add(Entry.Chunk);
        }
    }
    int32 Committed = 0;
    for (const FIntVector& Chunk : Order)
    {
        if (Committed >= Max)
        {
            break;
        }
        // Skipped chunks stay where they are, so they keep their place in line.
        if (!CanCommit(Chunk))
        {
            continue;
        }
        FReflectionsDigChunkResult Result;
        {
            FScopeLock Guard(&Lock);
            const int32 Index = Entries.IndexOfByPredicate([&Chunk](const FEntry& Entry) { return Entry.Chunk == Chunk; });
            if (Index == INDEX_NONE)
            {
                continue;
            }
            Result = MoveTemp(Entries[Index].Result);
            Entries.RemoveAt(Index);
        }
        Commit(Chunk, MoveTemp(Result));
        ++Committed;
    }
    return Committed;
}

int32 FReflectionsDigCommitQueue::Num() const
{
    FScopeLock Guard(&Lock);
    return Entries.Num();
}
