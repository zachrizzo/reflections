#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "Templates/Function.h"
#include "ReflectionsSaveGame.generated.h"

/** Everything the game persists. The slot holds a checked header in front of these bytes (see ReflectionsSave::Write). */
UCLASS()
class REFLECTIONS_API UReflectionsSaveGame : public USaveGame
{
    GENERATED_BODY()

public:
    /** Format version of the data. On load it is set from the file header. */
    UPROPERTY()
    int32 SaveVersion = 1;

    /** Dig spot id -> how many stages of it have been dug. */
    UPROPERTY()
    TMap<FName, uint8> DigSpotStages;

    /** Ids of the dig spots whose find the player has taken. A spot restored at its last stage without one gives it again. */
    UPROPERTY()
    TSet<FName> DigSpotFindsCollected;

    /** Dug terrain (unused until stage 3). */
    UPROPERTY()
    TArray<uint8> DigTerrainBlob;
};

enum class EReflectionsLoadResult : uint8
{
    Loaded,
    NoFile,
    NewerVersion,
    Corrupt
};

namespace ReflectionsSave
{
    inline constexpr int32 LatestVersion = 1;

    /** The real save slot: "Reflections". */
    REFLECTIONS_API extern const FString DefaultSlot;

    /** The slot Update works on: DefaultSlot unless an FScopedSlotOverride is alive. */
    REFLECTIONS_API const FString& ActiveSlot();

    /** Writes Data to Slot with the checked header. Returns false if the data could not be serialized or stored. */
    REFLECTIONS_API bool Write(const UReflectionsSaveGame& Data, const FString& Slot);

    /**
     * Reads Slot. Never writes, deletes or renames the file. OutData is null unless the result is Loaded or NoFile.
     * The returned save object is not rooted: use it at once or hold it in a UPROPERTY.
     */
    REFLECTIONS_API EReflectionsLoadResult Read(const FString& Slot, UReflectionsSaveGame*& OutData);

    /**
     * Reads ActiveSlot(), applies Mutate and writes it back under LatestVersion (whatever SaveVersion says). Refuses (returns false, no write, one LogReflectionsSave
     * warning per refused call) on a newer or corrupt file. The save object passed to Mutate is not rooted: use it
     * inside Mutate only, or hold what you need in a UPROPERTY.
     */
    REFLECTIONS_API bool Update(TFunctionRef<void(UReflectionsSaveGame&)> Mutate);

    /** Points ActiveSlot() at another slot for its lifetime (tests); restores the previous slot when destroyed. */
    struct REFLECTIONS_API FScopedSlotOverride
    {
        explicit FScopedSlotOverride(const FString& Slot);
        ~FScopedSlotOverride();

        FScopedSlotOverride(const FScopedSlotOverride&) = delete;
        FScopedSlotOverride& operator=(const FScopedSlotOverride&) = delete;

    private:
        FString Slot;
        const FString* Previous;
    };
}
