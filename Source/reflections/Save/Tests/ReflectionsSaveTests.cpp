#include "Save/ReflectionsSaveGame.h"

#include "CoreMinimal.h"
#include "Kismet/GameplayStatics.h"
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"
#include "Misc/Crc.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
    const FString TestSlot = TEXT("ReflectionsTest");
    constexpr EAutomationTestFlags SaveTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter;

    void DeleteTestSlot()
    {
        if (UGameplayStatics::DoesSaveGameExist(TestSlot, 0))
        {
            UGameplayStatics::DeleteGameInSlot(TestSlot, 0);
        }
    }

    TArray<uint8> LoadRaw()
    {
        TArray<uint8> Bytes;
        UGameplayStatics::LoadDataFromSlot(Bytes, TestSlot, 0);
        return Bytes;
    }

    TArray<uint8> RandomBytes()
    {
        FRandomStream Stream(1234);
        TArray<uint8> Bytes;
        Bytes.SetNumUninitialized(256);
        for (uint8& Byte : Bytes)
        {
            Byte = static_cast<uint8>(Stream.RandRange(0, 255));
        }
        return Bytes;
    }

    bool WriteVersion(int32 Version)
    {
        UReflectionsSaveGame* Data = NewObject<UReflectionsSaveGame>();
        Data->SaveVersion = Version;
        return ReflectionsSave::Write(*Data, TestSlot);
    }

    bool WriteVersionTwo()
    {
        return WriteVersion(2);
    }

    uint32 RawUint32(const TArray<uint8>& Bytes, int32 Offset)
    {
        return static_cast<uint32>(Bytes[Offset + 0])
            | (static_cast<uint32>(Bytes[Offset + 1]) << 8)
            | (static_cast<uint32>(Bytes[Offset + 2]) << 16)
            | (static_cast<uint32>(Bytes[Offset + 3]) << 24);
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSaveRoundTripTest, "Reflections.Save.RoundTrip", SaveTestFlags)
bool FReflectionsSaveRoundTripTest::RunTest(const FString& Parameters)
{
    DeleteTestSlot();

    UReflectionsSaveGame* Data = NewObject<UReflectionsSaveGame>();
    Data->DigSpotStages.Add(TEXT("Well"), 2);
    TestTrue(TEXT("Write succeeds"), ReflectionsSave::Write(*Data, TestSlot));

    const TArray<uint8> Raw = LoadRaw();
    if (TestTrue(TEXT("Raw file holds more than the header"), Raw.Num() > 16))
    {
        TestEqual(TEXT("Magic byte 0"), static_cast<int32>(Raw[0]), 0x53);
        TestEqual(TEXT("Magic byte 1"), static_cast<int32>(Raw[1]), 0x4C);
        TestEqual(TEXT("Magic byte 2"), static_cast<int32>(Raw[2]), 0x46);
        TestEqual(TEXT("Magic byte 3"), static_cast<int32>(Raw[3]), 0x52);
        TestEqual(TEXT("Header version"), RawUint32(Raw, 4), 1u);
        TestEqual(TEXT("Header length"), RawUint32(Raw, 8), static_cast<uint32>(Raw.Num() - 16));
        TestEqual(TEXT("Header CRC"), RawUint32(Raw, 12), FCrc::MemCrc32(Raw.GetData() + 16, Raw.Num() - 16));
    }

    UReflectionsSaveGame* Loaded = nullptr;
    TestEqual(TEXT("Read result"), ReflectionsSave::Read(TestSlot, Loaded), EReflectionsLoadResult::Loaded);
    if (TestNotNull(TEXT("Loaded data"), Loaded))
    {
        const uint8* Stage = Loaded->DigSpotStages.Find(TEXT("Well"));
        if (TestNotNull(TEXT("Well entry"), Stage))
        {
            TestEqual(TEXT("Well stage"), static_cast<int32>(*Stage), 2);
        }
        TestEqual(TEXT("SaveVersion"), Loaded->SaveVersion, 1);
    }

    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSaveNoFileStartsEmptyTest, "Reflections.Save.NoFileStartsEmpty", SaveTestFlags)
bool FReflectionsSaveNoFileStartsEmptyTest::RunTest(const FString& Parameters)
{
    DeleteTestSlot();

    UReflectionsSaveGame* Loaded = nullptr;
    TestEqual(TEXT("Read result"), ReflectionsSave::Read(TestSlot, Loaded), EReflectionsLoadResult::NoFile);
    if (TestNotNull(TEXT("Fresh data"), Loaded))
    {
        TestEqual(TEXT("SaveVersion"), Loaded->SaveVersion, 1);
        TestEqual(TEXT("DigSpotStages empty"), Loaded->DigSpotStages.Num(), 0);
        TestEqual(TEXT("DigTerrainBlob empty"), Loaded->DigTerrainBlob.Num(), 0);
    }
    TestFalse(TEXT("Slot still absent"), UGameplayStatics::DoesSaveGameExist(TestSlot, 0));

    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSaveRefusesNewerVersionTest, "Reflections.Save.RefusesNewerVersion", SaveTestFlags)
bool FReflectionsSaveRefusesNewerVersionTest::RunTest(const FString& Parameters)
{
    DeleteTestSlot();

    TestTrue(TEXT("Write succeeds"), WriteVersionTwo());
    const TArray<uint8> Before = LoadRaw();

    UReflectionsSaveGame* Loaded = NewObject<UReflectionsSaveGame>();
    TestEqual(TEXT("Read result"), ReflectionsSave::Read(TestSlot, Loaded), EReflectionsLoadResult::NewerVersion);
    TestNull(TEXT("OutData"), Loaded);
    TestTrue(TEXT("Bytes unchanged"), LoadRaw() == Before);

    // The version is checked before length and CRC: a newer file with a bad CRC is still NewerVersion.
    TArray<uint8> BadCrc = Before;
    if (TestTrue(TEXT("Version 2 file has a payload"), BadCrc.Num() > 16))
    {
        BadCrc[16] ^= 0xFF;
        TestTrue(TEXT("Store bad-CRC bytes"), UGameplayStatics::SaveDataToSlot(BadCrc, TestSlot, 0));
        Loaded = NewObject<UReflectionsSaveGame>();
        TestEqual(TEXT("Read result with bad CRC"), ReflectionsSave::Read(TestSlot, Loaded), EReflectionsLoadResult::NewerVersion);
        TestNull(TEXT("OutData with bad CRC"), Loaded);
        TestTrue(TEXT("Bad-CRC bytes unchanged"), LoadRaw() == BadCrc);
    }

    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSaveVersionZeroIsCorruptTest, "Reflections.Save.VersionZeroIsCorrupt", SaveTestFlags)
bool FReflectionsSaveVersionZeroIsCorruptTest::RunTest(const FString& Parameters)
{
    DeleteTestSlot();

    TestTrue(TEXT("Write succeeds"), WriteVersion(0));
    const TArray<uint8> Before = LoadRaw();

    UReflectionsSaveGame* Loaded = NewObject<UReflectionsSaveGame>();
    TestEqual(TEXT("Read result"), ReflectionsSave::Read(TestSlot, Loaded), EReflectionsLoadResult::Corrupt);
    TestNull(TEXT("OutData"), Loaded);
    TestTrue(TEXT("Bytes unchanged"), LoadRaw() == Before);

    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSaveCorruptFileIsRefusedTest, "Reflections.Save.CorruptFileIsRefused", SaveTestFlags)
bool FReflectionsSaveCorruptFileIsRefusedTest::RunTest(const FString& Parameters)
{
    DeleteTestSlot();

    const TArray<uint8> Garbage = RandomBytes();
    TestTrue(TEXT("Store garbage"), UGameplayStatics::SaveDataToSlot(Garbage, TestSlot, 0));

    UReflectionsSaveGame* Loaded = NewObject<UReflectionsSaveGame>();
    TestEqual(TEXT("Read result"), ReflectionsSave::Read(TestSlot, Loaded), EReflectionsLoadResult::Corrupt);
    TestNull(TEXT("OutData"), Loaded);
    TestTrue(TEXT("Bytes unchanged"), LoadRaw() == Garbage);

    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSaveTruncatedFileIsRefusedTest, "Reflections.Save.TruncatedFileIsRefused", SaveTestFlags)
bool FReflectionsSaveTruncatedFileIsRefusedTest::RunTest(const FString& Parameters)
{
    DeleteTestSlot();

    UReflectionsSaveGame* Data = NewObject<UReflectionsSaveGame>();
    for (int32 Index = 0; Index < 50; ++Index)
    {
        Data->DigSpotStages.Add(FName(*FString::Printf(TEXT("Spot%d"), Index)), static_cast<uint8>(Index % 4));
    }
    TestTrue(TEXT("Write succeeds"), ReflectionsSave::Write(*Data, TestSlot));

    TArray<uint8> Raw = LoadRaw();
    Raw.SetNum(Raw.Num() / 2);
    TestTrue(TEXT("Store truncated bytes"), UGameplayStatics::SaveDataToSlot(Raw, TestSlot, 0));

    UReflectionsSaveGame* Loaded = NewObject<UReflectionsSaveGame>();
    TestEqual(TEXT("Read result"), ReflectionsSave::Read(TestSlot, Loaded), EReflectionsLoadResult::Corrupt);
    TestNull(TEXT("OutData"), Loaded);

    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSaveUpdateWritesThroughActiveSlotTest, "Reflections.Save.UpdateWritesThroughActiveSlot", SaveTestFlags)
bool FReflectionsSaveUpdateWritesThroughActiveSlotTest::RunTest(const FString& Parameters)
{
    DeleteTestSlot();

    {
        ReflectionsSave::FScopedSlotOverride Override(TestSlot);
        if (!TestEqual(TEXT("ActiveSlot inside override"), ReflectionsSave::ActiveSlot(), TestSlot))
        {
            return false; // Never let Update reach the real slot.
        }

        TestTrue(TEXT("First update"), ReflectionsSave::Update([](UReflectionsSaveGame& Save)
        {
            Save.DigSpotStages.Add(TEXT("Pump"), 1);
        }));
        TestTrue(TEXT("Second update"), ReflectionsSave::Update([](UReflectionsSaveGame& Save)
        {
            Save.DigSpotStages.Add(TEXT("Well"), 2);
        }));

        UReflectionsSaveGame* Loaded = nullptr;
        TestEqual(TEXT("Read result"), ReflectionsSave::Read(TestSlot, Loaded), EReflectionsLoadResult::Loaded);
        if (TestNotNull(TEXT("Loaded data"), Loaded))
        {
            TestEqual(TEXT("Entry count"), Loaded->DigSpotStages.Num(), 2);
            const uint8* Pump = Loaded->DigSpotStages.Find(TEXT("Pump"));
            const uint8* Well = Loaded->DigSpotStages.Find(TEXT("Well"));
            if (TestNotNull(TEXT("Pump entry"), Pump))
            {
                TestEqual(TEXT("Pump stage"), static_cast<int32>(*Pump), 1);
            }
            if (TestNotNull(TEXT("Well entry"), Well))
            {
                TestEqual(TEXT("Well stage"), static_cast<int32>(*Well), 2);
            }
        }
    }
    TestEqual(TEXT("ActiveSlot after override"), ReflectionsSave::ActiveSlot(), ReflectionsSave::DefaultSlot);

    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSaveUpdateLeavesBadFileAloneTest, "Reflections.Save.UpdateLeavesBadFileAlone", SaveTestFlags)
bool FReflectionsSaveUpdateLeavesBadFileAloneTest::RunTest(const FString& Parameters)
{
    // Update logs one LogReflectionsSave warning on every refused call; Occurrences > 0 means exactly that many.
    AddExpectedError(TEXT("LogReflectionsSave"), EAutomationExpectedErrorFlags::Contains, 2);

    DeleteTestSlot();

    {
        ReflectionsSave::FScopedSlotOverride Override(TestSlot);
        if (!TestEqual(TEXT("ActiveSlot inside override"), ReflectionsSave::ActiveSlot(), TestSlot))
        {
            return false; // Never let Update reach the real slot.
        }

        const TArray<uint8> Garbage = RandomBytes();
        TestTrue(TEXT("Store garbage"), UGameplayStatics::SaveDataToSlot(Garbage, TestSlot, 0));
        bool bMutateCalled = false;
        TestFalse(TEXT("Update on corrupt file"), ReflectionsSave::Update([&bMutateCalled](UReflectionsSaveGame&)
        {
            bMutateCalled = true;
        }));
        TestFalse(TEXT("Mutate not called on corrupt file"), bMutateCalled);
        TestTrue(TEXT("Corrupt bytes unchanged"), LoadRaw() == Garbage);

        DeleteTestSlot();
        TestTrue(TEXT("Write version 2"), WriteVersionTwo());
        const TArray<uint8> Newer = LoadRaw();
        bMutateCalled = false;
        TestFalse(TEXT("Update on newer file"), ReflectionsSave::Update([&bMutateCalled](UReflectionsSaveGame&)
        {
            bMutateCalled = true;
        }));
        TestFalse(TEXT("Mutate not called on newer file"), bMutateCalled);
        TestTrue(TEXT("Newer bytes unchanged"), LoadRaw() == Newer);
    }

    DeleteTestSlot();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsSaveUpdateStampsTheLatestVersionTest, "Reflections.Save.UpdateStampsTheLatestVersion", SaveTestFlags)
bool FReflectionsSaveUpdateStampsTheLatestVersionTest::RunTest(const FString& Parameters)
{
    DeleteTestSlot();

    {
        ReflectionsSave::FScopedSlotOverride Override(TestSlot);
        if (!TestEqual(TEXT("ActiveSlot inside override"), ReflectionsSave::ActiveSlot(), TestSlot))
        {
            return false; // Never let Update reach the real slot.
        }

        TestTrue(TEXT("Write a valid file"), WriteVersion(ReflectionsSave::LatestVersion));
        // While LatestVersion is 1 no older valid file exists, so the object's version is changed inside Mutate, after
        // the read: whatever SaveVersion says when the object is written back, the header must say LatestVersion.
        const int32 Stale = ReflectionsSave::LatestVersion + 1;
        TestTrue(TEXT("Update succeeds"), ReflectionsSave::Update([Stale](UReflectionsSaveGame& Save)
        {
            Save.SaveVersion = Stale;
            Save.DigSpotStages.Add(TEXT("Pump"), 1);
        }));

        const TArray<uint8> Raw = LoadRaw();
        if (TestTrue(TEXT("Raw file holds more than the header"), Raw.Num() > 16))
        {
            TestEqual(TEXT("Header version after Update"), RawUint32(Raw, 4), static_cast<uint32>(ReflectionsSave::LatestVersion));
        }
        UReflectionsSaveGame* Loaded = nullptr;
        TestEqual(TEXT("The updated file reads back"), ReflectionsSave::Read(TestSlot, Loaded), EReflectionsLoadResult::Loaded);
        if (TestNotNull(TEXT("Loaded data"), Loaded))
        {
            TestEqual(TEXT("SaveVersion after reading back"), Loaded->SaveVersion, ReflectionsSave::LatestVersion);
            TestTrue(TEXT("The update's change is kept"), Loaded->DigSpotStages.Contains(TEXT("Pump")));
        }
    }

    DeleteTestSlot();
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
