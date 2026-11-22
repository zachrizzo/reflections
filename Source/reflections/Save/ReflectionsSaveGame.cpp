#include "Save/ReflectionsSaveGame.h"

#include "Kismet/GameplayStatics.h"
#include "Misc/Crc.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsSave, Log, All);

namespace ReflectionsSave
{
    const FString DefaultSlot = TEXT("Reflections");

    namespace
    {
        constexpr uint32 Magic = 0x52464C53;
        constexpr int32 HeaderSize = 4 * sizeof(uint32);
        constexpr int32 UserIndex = 0;

        /** The slot of the innermost live FScopedSlotOverride, or null. */
        const FString* GOverrideSlot = nullptr;

        void PutUint32(TArray<uint8>& Bytes, int32 Offset, uint32 Value)
        {
            Bytes[Offset + 0] = static_cast<uint8>(Value);
            Bytes[Offset + 1] = static_cast<uint8>(Value >> 8);
            Bytes[Offset + 2] = static_cast<uint8>(Value >> 16);
            Bytes[Offset + 3] = static_cast<uint8>(Value >> 24);
        }

        uint32 GetUint32(const TArray<uint8>& Bytes, int32 Offset)
        {
            return static_cast<uint32>(Bytes[Offset + 0])
                | (static_cast<uint32>(Bytes[Offset + 1]) << 8)
                | (static_cast<uint32>(Bytes[Offset + 2]) << 16)
                | (static_cast<uint32>(Bytes[Offset + 3]) << 24);
        }
    }

    const FString& ActiveSlot()
    {
        return GOverrideSlot ? *GOverrideSlot : DefaultSlot;
    }

    bool Write(const UReflectionsSaveGame& Data, const FString& Slot)
    {
        TArray<uint8> Payload;
        if (!UGameplayStatics::SaveGameToMemory(const_cast<UReflectionsSaveGame*>(&Data), Payload))
        {
            return false;
        }

        TArray<uint8> Bytes;
        Bytes.SetNumUninitialized(HeaderSize);
        PutUint32(Bytes, 0, Magic);
        PutUint32(Bytes, 4, static_cast<uint32>(Data.SaveVersion));
        PutUint32(Bytes, 8, static_cast<uint32>(Payload.Num()));
        PutUint32(Bytes, 12, FCrc::MemCrc32(Payload.GetData(), Payload.Num()));
        Bytes.Append(Payload);

        return UGameplayStatics::SaveDataToSlot(Bytes, Slot, UserIndex);
    }

    EReflectionsLoadResult Read(const FString& Slot, UReflectionsSaveGame*& OutData)
    {
        OutData = nullptr;

        if (!UGameplayStatics::DoesSaveGameExist(Slot, UserIndex))
        {
            OutData = NewObject<UReflectionsSaveGame>();
            return EReflectionsLoadResult::NoFile;
        }

        TArray<uint8> Bytes;
        if (!UGameplayStatics::LoadDataFromSlot(Bytes, Slot, UserIndex)
            || Bytes.Num() < HeaderSize
            || GetUint32(Bytes, 0) != Magic)
        {
            return EReflectionsLoadResult::Corrupt;
        }

        const int32 Version = static_cast<int32>(GetUint32(Bytes, 4));
        if (Version > LatestVersion)
        {
            return EReflectionsLoadResult::NewerVersion;
        }

        const uint32 Length = GetUint32(Bytes, 8);
        if (Length != static_cast<uint32>(Bytes.Num() - HeaderSize))
        {
            return EReflectionsLoadResult::Corrupt;
        }

        const TArray<uint8> Payload(Bytes.GetData() + HeaderSize, static_cast<int32>(Length));
        if (FCrc::MemCrc32(Payload.GetData(), Payload.Num()) != GetUint32(Bytes, 12))
        {
            return EReflectionsLoadResult::Corrupt;
        }

        UReflectionsSaveGame* Data = Cast<UReflectionsSaveGame>(UGameplayStatics::LoadGameFromMemory(Payload));
        if (!Data)
        {
            return EReflectionsLoadResult::Corrupt;
        }

        Data->SaveVersion = Version;
        OutData = Data;
        return EReflectionsLoadResult::Loaded;
    }

    bool Update(TFunctionRef<void(UReflectionsSaveGame&)> Mutate)
    {
        const FString& Slot = ActiveSlot();
        UReflectionsSaveGame* Data = nullptr;
        const EReflectionsLoadResult Result = Read(Slot, Data);

        if (Result == EReflectionsLoadResult::NewerVersion || Result == EReflectionsLoadResult::Corrupt)
        {
            UE_LOG(LogReflectionsSave, Warning, TEXT("Save slot '%s' is %s; not updating it, progress will not be saved."),
                *Slot, Result == EReflectionsLoadResult::NewerVersion ? TEXT("from a newer version") : TEXT("corrupt"));
            return false;
        }

        Mutate(*Data);
        return Write(*Data, Slot);
    }

    FScopedSlotOverride::FScopedSlotOverride(const FString& InSlot)
        : Slot(InSlot)
        , Previous(GOverrideSlot)
    {
        GOverrideSlot = &Slot;
    }

    FScopedSlotOverride::~FScopedSlotOverride()
    {
        GOverrideSlot = Previous;
    }
}
