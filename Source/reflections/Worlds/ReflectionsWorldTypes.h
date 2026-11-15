#pragma once

#include "CoreMinimal.h"
#include "Engine/Scene.h"
#include "ReflectionsWorldTypes.generated.h"

class USoundBase;
class UStaticMesh;

/** The three stacked Londons, bottom to top. */
UENUM(BlueprintType)
enum class EReflectionsWorld : uint8
{
    Gray  UMETA(DisplayName = "Pewterside"),
    Red   UMETA(DisplayName = "Giltside"),
    White UMETA(DisplayName = "Frostside"),
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

/** How a pickup looks: a mesh fitted to a display size, turned to face the player. */
USTRUCT(BlueprintType)
struct FReflectionsPickupLook
{
    GENERATED_BODY()

    /** Empty: the gray-box shape. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Pickup")
    TObjectPtr<UStaticMesh> Mesh;

    /** The mesh is scaled so its longest side is this long (real-scale props are tiny as pickups). 0: the mesh's own size. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Pickup", meta = (ClampMin = "0", Units = "cm"))
    float DisplaySize = 40.0f;

    /** Turn applied under the spin, for example Roll 90 to stand a flat coin on its edge. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Pickup")
    FRotator Rotation = FRotator::ZeroRotator;
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

    /** Where this side's mirror page is found, for page pickups with no title of their own ("the Gilt Tower"). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    FText PageSource;

    /** Colour of this London's coins. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    FLinearColor CoinColor = FLinearColor::White;

    /** What this London's coin (mirror shard) pickups look like. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    FReflectionsPickupLook CoinLook;

    /** Music loop for this London (2D). Empty: no world-jump music here. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    TObjectPtr<USoundBase> Music;

    /** Colour grade applied inside this London's anchor bounds (OffsetCopies). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "World")
    FPostProcessSettings Grade;
};
