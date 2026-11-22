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

int32 FReflectionsDigCommitQueue::PopUpTo(int32 Max, TFunctionRef<void(FIntVector, FReflectionsDigChunkResult&&)> Commit)
{
    int32 Committed = 0;
    while (Committed < Max)
    {
        FEntry Entry;
        {
            FScopeLock Guard(&Lock);
            if (Entries.IsEmpty())
            {
                break;
            }
            Entry = MoveTemp(Entries[0]);
            Entries.RemoveAt(0);
        }
        Commit(Entry.Chunk, MoveTemp(Entry.Result));
        ++Committed;
    }
    return Committed;
}

int32 FReflectionsDigCommitQueue::Num() const
{
    FScopeLock Guard(&Lock);
    return Entries.Num();
}
