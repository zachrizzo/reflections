#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "InputCoreTypes.h"
#include "Worlds/ReflectionsWorldTypes.h"
#include "ReflectionsWorldJumpConfig.generated.h"

class UCameraShakeBase;
class UInputAction;
class UInputMappingContext;
class UMaterialInterface;
class UNiagaraSystem;
class USoundBase;
class USoundMix;

/**
 * Every tunable of the world jump in one asset. The game loads /Game/Worlds/DA_WorldJumpConfig; a level can
 * point a ReflectionsWorldAnchor at another config instead. Without any asset the C++ defaults below apply.
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsWorldJumpConfig : public UDataAsset
{
    GENERATED_BODY()

public:
    UReflectionsWorldJumpConfig();

    /** The config for this world: an anchor's override, else the project asset, else the C++ defaults. */
    static const UReflectionsWorldJumpConfig* Get(const UObject* WorldContext);

    /** Default project asset path. */
    static const TCHAR* DefaultAssetPath;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Worlds")
    EReflectionsWorldLayout Layout = EReflectionsWorldLayout::OffsetCopies;

    /** The Londons, bottom (Gray) to top (White). A jump moves one step along this list. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Worlds")
    TArray<FReflectionsWorldInfo> Worlds;

    /** World assumed when a location is not inside any anchor's bounds and no anchor is nearer. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Worlds")
    EReflectionsWorld DefaultWorld = EReflectionsWorld::Gray;

    // ---- Cost ------------------------------------------------------------------------------------------

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cost")
    EReflectionsCoinRule CoinRule = EReflectionsCoinRule::DestinationWorld;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cost", meta = (ClampMin = "0"))
    int32 CoinsPerJump = 1;

    /** Share of the hero's maximum magic a jump spends. The hero needs at least this much to jump. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cost", meta = (ClampMin = "0", ClampMax = "1"))
    float MagicCostFraction = 0.8f;

    /** Refuse to jump when the pawn has no magic component. Off: jump for free and log a warning. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cost")
    bool bRequireMagicSource = false;

    /**
     * The magic bar is found by name on the pawn's components, so the jump does not compile against the spell
     * code. The first component with one of these functions is the magic source.
     */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cost|Magic Source")
    TArray<FName> MagicGetterNames;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cost|Magic Source")
    TArray<FName> MaxMagicGetterNames;

    /** Float properties read when no max getter exists. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cost|Magic Source")
    TArray<FName> MaxMagicPropertyNames;

    /** bool Fn(float Amount): spends and returns true, or returns false and spends nothing. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cost|Magic Source")
    TArray<FName> SpendMagicNames;

    // ---- Landing -----------------------------------------------------------------------------------------

    /** Farthest the landing spot may be pushed out of a wall, a car or a lamp post before the jump is refused. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Landing", meta = (ClampMin = "0", Units = "cm"))
    float MaxNudgeDistance = 150.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Landing", meta = (ClampMin = "5", Units = "cm"))
    float NudgeStep = 25.0f;

    /** Refuse a jump that would leave the hero with nothing to stand on within MaxDropDistance. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Landing")
    bool bRequireGround = true;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Landing", meta = (ClampMin = "0", Units = "cm"))
    float MaxDropDistance = 3000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Landing")
    bool bKeepVelocity = true;

    // ---- Transition --------------------------------------------------------------------------------------

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Transition", meta = (ClampMin = "0", Units = "s"))
    float FadeOutTime = 0.12f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Transition", meta = (ClampMin = "0", Units = "s"))
    float FadeInTime = 0.45f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Transition")
    TSubclassOf<UCameraShakeBase> ArrivalCameraShake;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Transition")
    TObjectPtr<UNiagaraSystem> DepartureEffect;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Transition")
    TObjectPtr<UNiagaraSystem> ArrivalEffect;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Transition")
    TObjectPtr<USoundBase> JumpSound;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Transition")
    TObjectPtr<USoundBase> RefusedSound;

    /** Coin pickup. Also used for pages and keys when their own sound is empty. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Transition")
    TObjectPtr<USoundBase> PickupSound;

    /** Plays (2D) as the hero arrives in the new London. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Transition")
    TObjectPtr<USoundBase> ArrivalSound;

    /** Pushed on arrival, for example a short music duck that releases itself. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Transition")
    TObjectPtr<USoundMix> ArrivalSoundMix;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Book")
    TObjectPtr<USoundBase> PageSound;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Book")
    TObjectPtr<USoundBase> KeySound;

    /** Plays at a sealed door as it opens. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Book")
    TObjectPtr<USoundBase> DoorUnsealSound;

    /** Play each London's Music loop while the hero is in it. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Music")
    bool bPlayWorldMusic = true;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Music", meta = (ClampMin = "0", Units = "s"))
    float MusicFadeOutTime = 0.5f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Music", meta = (ClampMin = "0", Units = "s"))
    float MusicFadeInTime = 1.5f;

    // ---- Input -------------------------------------------------------------------------------------------

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
    TSoftObjectPtr<UInputMappingContext> MappingContext;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
    TSoftObjectPtr<UInputAction> JumpUpAction;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
    TSoftObjectPtr<UInputAction> JumpDownAction;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
    int32 MappingPriority = 2;

    /** Used to build the input at runtime when the assets above are missing. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input|Fallback")
    TArray<FKey> FallbackUpKeys;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input|Fallback")
    TArray<FKey> FallbackDownKeys;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input|Fallback", meta = (ClampMin = "0", Units = "s"))
    float FallbackHoldTime = 0.25f;

    // ---- Coat --------------------------------------------------------------------------------------------

    /** Mesh components (on the pawn or its child actors) that take the world tint. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Coat")
    TArray<FName> CoatComponentNames;

    /** Vector parameters tried, in order, on each coat material. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Coat")
    TArray<FName> TintParameterNames;

    /** Material slots to tint. Empty: every slot that has a tint parameter. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Coat")
    TArray<int32> TintMaterialSlots;

    /** Overlay used on a coat whose materials have no tint parameter. It needs a "Tint" vector parameter. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Coat")
    TSoftObjectPtr<UMaterialInterface> OverlayTintMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Coat")
    bool bUseOverlayWhenNoParameter = true;

    // ---- Tower hunt --------------------------------------------------------------------------------------

    /** Distinct pages that make the book. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Book", meta = (ClampMin = "1"))
    int32 PagesForBook = 3;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "HUD")
    bool bShowHud = true;

    const FReflectionsWorldInfo* FindWorld(EReflectionsWorld World) const;
    int32 IndexOfWorld(EReflectionsWorld World) const;
    /** The neighbouring London one step up or down; false at the top or bottom of the stack. */
    bool GetNeighbor(EReflectionsWorld From, EReflectionsJumpDirection Direction, EReflectionsWorld& Out) const;
    FText GetWorldName(EReflectionsWorld World) const;
};
