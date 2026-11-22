#include "Digging/ReflectionsDigCommitQueue.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigPieces.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
    constexpr EAutomationTestFlags DigQueueTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;

    /** A result told apart from others by its SourceTriangleCount. */
    FReflectionsDigChunkResult MakeResult(int32 TriangleCount)
    {
        FReflectionsDigChunkResult Result;
        Result.SourceTriangleCount = TriangleCount;
        Result.SourceVertexCount = TriangleCount * 3;
        return Result;
    }

    struct FPopped
    {
        FIntVector Chunk;
        int32 Triangles = 0;
    };

    TArray<FPopped> PopAll(FReflectionsDigCommitQueue& Queue, int32 Max)
    {
        TArray<FPopped> Popped;
        Queue.PopUpTo(Max, [&Popped](FIntVector Chunk, FReflectionsDigChunkResult&& Result)
        {
            Popped.Add({ Chunk, Result.SourceTriangleCount });
        });
        return Popped;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigQueueKeepsOnlyNewestPerChunkTest, "Reflections.Digging.Queue.KeepsOnlyNewestPerChunk", DigQueueTestFlags)
bool FReflectionsDigQueueKeepsOnlyNewestPerChunkTest::RunTest(const FString& Parameters)
{
    FReflectionsDigCommitQueue Queue;
    const FIntVector Chunk(1, 2, 0);
    for (int32 Triangles = 1; Triangles <= 5; ++Triangles)
    {
        Queue.Push(Chunk, MakeResult(Triangles));
    }
    TestEqual(TEXT("Num after five pushes for one chunk"), Queue.Num(), 1);

    const TArray<FPopped> Popped = PopAll(Queue, 10);
    if (TestEqual(TEXT("Meshes popped"), Popped.Num(), 1))
    {
        TestEqual(TEXT("Popped chunk"), Popped[0].Chunk, Chunk);
        TestEqual(TEXT("Popped mesh is the newest (5 triangles)"), Popped[0].Triangles, 5);
    }
    TestEqual(TEXT("Num after popping"), Queue.Num(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigQueuePopRespectsBudgetTest, "Reflections.Digging.Queue.PopRespectsBudget", DigQueueTestFlags)
bool FReflectionsDigQueuePopRespectsBudgetTest::RunTest(const FString& Parameters)
{
    FReflectionsDigCommitQueue Queue;
    for (int32 Index = 0; Index < 6; ++Index)
    {
        Queue.Push(FIntVector(Index, 0, 0), MakeResult(Index + 1));
    }

    TArray<FIntVector> Committed;
    const int32 Count = Queue.PopUpTo(2, [&Committed](FIntVector Chunk, FReflectionsDigChunkResult&& Result)
    {
        Committed.Add(Chunk);
    });
    TestEqual(TEXT("PopUpTo(2) returns"), Count, 2);
    if (TestEqual(TEXT("Chunks committed"), Committed.Num(), 2))
    {
        TestEqual(TEXT("First committed is the first pushed"), Committed[0], FIntVector(0, 0, 0));
        TestEqual(TEXT("Second committed is the second pushed"), Committed[1], FIntVector(1, 0, 0));
    }
    TestEqual(TEXT("Num after the pop"), Queue.Num(), 4);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigQueueReplacingKeepsPlaceInLineTest, "Reflections.Digging.Queue.ReplacingKeepsPlaceInLine", DigQueueTestFlags)
bool FReflectionsDigQueueReplacingKeepsPlaceInLineTest::RunTest(const FString& Parameters)
{
    FReflectionsDigCommitQueue Queue;
    const FIntVector A(0, 0, 1);
    const FIntVector B(1, 0, 1);
    Queue.Push(A, MakeResult(1));
    Queue.Push(B, MakeResult(2));
    Queue.Push(A, MakeResult(3));

    const TArray<FPopped> Popped = PopAll(Queue, 10);
    if (TestEqual(TEXT("Meshes popped"), Popped.Num(), 2))
    {
        TestEqual(TEXT("First popped is A"), Popped[0].Chunk, A);
        TestEqual(TEXT("A's popped mesh is the newer one (3 triangles)"), Popped[0].Triangles, 3);
        TestEqual(TEXT("Second popped is B"), Popped[1].Chunk, B);
        TestEqual(TEXT("B's mesh (2 triangles)"), Popped[1].Triangles, 2);
    }
    return true;
}

#endif
