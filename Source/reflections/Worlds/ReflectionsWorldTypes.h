#pragma once

#include "CoreMinimal.h"
#include "Engine/Scene.h"
#include "ReflectionsWorldTypes.generated.h"

class USoundBase;

/** The three stacked Londons, bottom to top. */
UENUM(BlueprintType)
enum class EReflectionsWorld : uint8
{
    Gray  UMETA(DisplayName = "Gray London"),
    Red   UMETA(DisplayName = "Red London"),
    White UMETA(DisplayName = "White London"),
};

/** How the three Londons are laid out on disk. */
UENUM(BlueprintType)
enum class EReflectionsWorldLayout : uint8
{
    /**
     * All three Londons are loaded at once in one map, each copy shifted by a fixed vector and marked by a
     * ReflectionsWorldAnchor. A jump is an instant teleport by the difference of two anchors: no loading.
     * Three separate maps fit this too, as streaming sublevels (or Level Instances) with a level offset.
     */
    OffsetCopies,
    /** Each London is its own map and a jump opens the other map. Works anywhere, but has a load hitch. */
    SeparateMaps,
};

/** Which world's coin a jump spends. */
UENUM(BlueprintType)
enum class EReflectionsCoinRule : uint8
{
    /** A coin from the London you are going to (a token of that world opens the way). */
    DestinationWorld,
    /** A coin from the London you are standing in. */
    CurrentWorld,
    /** Any coin; the destination's first, then the current world's, then any other. */
    AnyWorld,
};

UENUM(BlueprintType)
enum class EReflectionsJumpDirection : uint8
{
    /** Toward White London. */
    Up,
    /** Toward Gray London. */
    Down,
};

/** Look and data for one London. */
USTRUCT(BlueprintType)
struct FReflectionsWorldInfo
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    EReflectionsWorld World = EReflectionsWorld::Red;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    FText DisplayName;

    /** SeparateMaps layout only: the map that is this London. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    TSoftObjectPtr<UWorld> Map;

    /** Colour the hero's coat takes in this London. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    FLinearColor CoatTint = FLinearColor::White;

    /** HUD text colour and the colour of the jump flash. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    FLinearColor ThemeColor = FLinearColor::White;

    /** Colour of this London's coins. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    FLinearColor CoinColor = FLinearColor::White;

    /** Music loop for this London (2D). Empty: no world-jump music here. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    TObjectPtr<USoundBase> Music;

    /** Colour grade applied inside this London's anchor bounds (OffsetCopies). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    FPostProcessSettings Grade;
};
