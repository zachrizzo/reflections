#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Templates/Function.h"
#include "Templates/SubclassOf.h"
#include "UObject/SoftObjectPath.h"
#include "UObject/SoftObjectPtr.h"
#include "ReflectionsSwordTest.generated.h"

class AActor;
class AController;
class APawn;
class APlayerController;
class UAnimInstance;
class UAnimMontage;
class UEnhancedInputComponent;
class UInputAction;
class UInputMappingContext;
class ULocalPlayer;
class UReflectionsSampleSpellDriver;
class USkeletalMeshComponent;
class UStaticMesh;
class UStaticMeshComponent;
struct FHitResult;
struct FInputActionValue;

/** Which part of the sword library a move comes from: its folder, or failing that its name. */
enum class EReflectionsSwordMoveKind : uint8
{
    Cut,
    Thrust,
    Combo,
    Footwork,
    Guard,
    Other,
};

/** One move found by the asset registry scan; loaded the first time it plays. */
struct FReflectionsSwordMove
{
    FSoftObjectPath Path;
    FString Name;
    EReflectionsSwordMoveKind Kind = EReflectionsSwordMoveKind::Other;
};

/**
 * TEMPORARY test harness for the sword animation library (/Game/Animation/SwordLibrary). Not the melee system.
 *
 * X draws / puts away a stand-in sword (SM_Frostside_MirrorSword) on the Body's hand_r bone. While it is out, the
 * spell driver's primary cast (LMB / Q / RT, holding repeats) plays the next Cut or Thrust instead of a spell, and F
 * plays the next Combo; the console command Sword.Play <filter> plays anything else (Footwork, Guards, a name).
 * Moves play full body the way a non-layered cast does: the Body switches to BP_HeroAnimation and movement stops
 * until the move ends; a travelling move's root motion is applied to the capsule here, because CharacterMovement
 * only reads root motion from the character's own mesh. Around each Hit notify the blade (guard to tip) is swept
 * and what it touches is logged and drawn. Sword.Test 0 turns all of it off.
 * AReflectionsSampleGameMode adds it to the player pawn at runtime, like the dig component.
 * See ArtDirection/VideoToAnim/SwordCombatPatch.md.
 */
UCLASS(ClassGroup = (Combat))
class REFLECTIONS_API UReflectionsSwordTestComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsSwordTestComponent();

    /** False when the Sword.Test console variable is 0. */
    static bool IsEnabled();

    /** Returns the pawn's sword test component, adding and registering one if it has none. Null pawn or Sword.Test 0 gives null. */
    static UReflectionsSwordTestComponent* EnsureOnPawn(APawn* Pawn);

    UPROPERTY(EditAnywhere, Category = "Sword Test")
    TSoftObjectPtr<UStaticMesh> SwordMesh;

    /** The bone the sword rides on. A bone, not a socket: the shared metahuman_base_skel must not be edited or saved. */
    UPROPERTY(EditAnywhere, Category = "Sword Test")
    FName GripBone;

    /** The sword's place in GripBone space. The clips carry the matching wrist correction. Live: an edit shows next frame. */
    UPROPERTY(EditAnywhere, Category = "Sword Test", meta = (Units = "cm"))
    FVector GripLocation;

    /** The sword's rotation in GripBone space (Pitch 59.13, Yaw -158.21, Roll 128.29; Details shows X = Roll, Y = Pitch, Z = Yaw). */
    UPROPERTY(EditAnywhere, Category = "Sword Test")
    FRotator GripRotation;

    /** The blade runs along the sword mesh's +X axis: guard end... (cm, mesh space). */
    UPROPERTY(EditAnywhere, Category = "Sword Test|Hits", meta = (Units = "cm"))
    float BladeStart = 22.0f;

    /** ...to tip. */
    UPROPERTY(EditAnywhere, Category = "Sword Test|Hits", meta = (Units = "cm"))
    float BladeTip = 86.0f;

    UPROPERTY(EditAnywhere, Category = "Sword Test|Hits", meta = (Units = "cm", ClampMin = "0"))
    float BladeRadius = 4.0f;

    /** Points along the blade whose path since the last frame is swept. */
    UPROPERTY(EditAnywhere, Category = "Sword Test|Hits", meta = (ClampMin = "2", ClampMax = "12"))
    int32 BladeSamples = 5;

    /** The blade is traced from this long before each Hit notify (montage seconds)... */
    UPROPERTY(EditAnywhere, Category = "Sword Test|Hits", meta = (Units = "s", ClampMin = "0"))
    float HitWindowBefore = 0.08f;

    /** ...to this long after it. */
    UPROPERTY(EditAnywhere, Category = "Sword Test|Hits", meta = (Units = "s", ClampMin = "0"))
    float HitWindowAfter = 0.06f;

    /** Also report world geometry (walls, ground) the blade touches. Pawns, dynamic objects and physics bodies always are. */
    UPROPERTY(EditAnywhere, Category = "Sword Test|Hits")
    bool bTraceWorldStatic = false;

    /** Scanned (with subfolders) for montages each time the sword is drawn and by Sword.List. Folders starting with _ are skipped. */
    UPROPERTY(EditAnywhere, Category = "Sword Test|Library")
    FString MontageFolder;

    /** Scanned for clips, played as DefaultSlot montages (0.12 s in, 0.2 s out), only when MontageFolder has no montages. */
    UPROPERTY(EditAnywhere, Category = "Sword Test|Library")
    FString ClipFolder;

    /** The anim class a full-body move plays on: the one UReflectionsSampleSpellDriver::PlayCast uses for a non-layered cast. */
    UPROPERTY(EditAnywhere, Category = "Sword Test", meta = (MetaClass = "/Script/Engine.AnimInstance"))
    FSoftClassPath FullBodyAnimClass;

    /** Turn to the camera's heading as a move starts, so the move goes where the player looks. */
    UPROPERTY(EditAnywhere, Category = "Sword Test")
    bool bFaceCameraOnAttack = true;

    UFUNCTION(BlueprintCallable, Category = "Sword Test")
    void SetEquipped(bool bEquip);

    UFUNCTION(BlueprintPure, Category = "Sword Test")
    bool IsEquipped() const { return bEquipped; }

    UFUNCTION(BlueprintPure, Category = "Sword Test")
    bool IsAttacking() const { return ActiveMontage != nullptr; }

    /** Plays the next Cut or Thrust, cycling through both. */
    bool PlayNextStrike();

    /** Plays the next Combo. */
    bool PlayNextCombo();

    /** Plays the next move whose kind (Cut, Thrust, Combo, Footwork, Guard) or name contains Filter, ignoring case; draws the sword first. */
    bool PlayNextMatching(const FString& Filter);

    /** Scans the library again, for moves saved while playing. */
    void Rescan();

    /** Rescans and logs every move with its kind, length, root motion and hit times (loads them all). */
    void LogLibrary();

    /** Logs the grip and shows it on screen. */
    void LogGrip() const;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
    bool PlayNext(const FString& CursorKey, TFunctionRef<bool(const FReflectionsSwordMove&)> Match);
    bool CanStartMove() const;
    bool StartMove(const FReflectionsSwordMove& Move);
    void OnMoveEnded(UAnimMontage* Montage, bool bInterrupted, int32 Serial);
    void StopMove();
    /** Puts the Body's anim class back and turns movement on again after a full-body move. */
    void RestoreBody();
    void ApplyRootMotion();
    void UpdateHitWindow(float Position);
    void TraceBlade(int32 Window, float Position);
    void ReportHit(const FHitResult& Hit, int32 Window, float Position);
    USkeletalMeshComponent* FindBody() const;

    void HookSpellDriver();
    void UnhookSpellDriver();
    /** The spell driver's primary cast override: true (handled) whenever the sword is out, so no spell is cast. */
    bool HandlePrimaryCast();

    void BindControls();
    void UnbindControls();
    void OnToggleAction(const FInputActionValue& Value);
    void OnComboAction(const FInputActionValue& Value);
    void OnStrikeAction(const FInputActionValue& Value);

    UFUNCTION()
    void HandleControllerChanged(APawn* Pawn, AController* OldController, AController* NewController);

    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> Body;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> Sword;
    UPROPERTY(Transient) TObjectPtr<UAnimMontage> ActiveMontage;
    /** The Body's anim class before a full-body move switched it; put back when the move ends. */
    UPROPERTY(Transient) TSubclassOf<UAnimInstance> RestoreClass;
    UPROPERTY(Transient) TObjectPtr<UReflectionsSampleSpellDriver> Driver;
    UPROPERTY(Transient) TObjectPtr<UInputMappingContext> SwordContext;
    UPROPERTY(Transient) TObjectPtr<UInputAction> ToggleAction;
    UPROPERTY(Transient) TObjectPtr<UInputAction> ComboAction;
    UPROPERTY(Transient) TObjectPtr<UInputAction> StrikeAction;
    UPROPERTY(Transient) TObjectPtr<UEnhancedInputComponent> SwordInput;

    TWeakObjectPtr<APlayerController> BoundController;
    TWeakObjectPtr<ULocalPlayer> BoundPlayer;
    /** Whatever override the spell driver had before; still called while the sword is away, put back at EndPlay. */
    TFunction<bool()> PreviousPrimaryCastOverride;

    TArray<FReflectionsSwordMove> Moves;
    /** Last move index played per cycle (strikes, combos, each Sword.Play filter). */
    TMap<FString, int32> Cursors;
    FString ActiveName;
    /** Montage seconds of the playing move's Hit notifies. */
    TArray<float> HitTimes;
    TArray<FVector> PreviousBlade;
    /** Actors already reported in the open hit window (identity only, never dereferenced). */
    TSet<const AActor*> WindowHits;
    int32 WindowIndex = INDEX_NONE;
    int32 MoveSerial = 0;
    int32 MoveHits = 0;
    float LastPosition = 0.0f;
    /** For the end-of-move log line: where and when the move started, and how much root motion reached the capsule. */
    FVector MoveStartLocation = FVector::ZeroVector;
    double MoveStartTime = 0.0;
    float RootMotionApplied = 0.0f;
    double LastNoMoveWarning = -100.0;
    bool bEquipped = false;
    bool bHookedDriver = false;
    bool bMoveRootMotion = false;
    bool bMovementLocked = false;
    bool bRestorePending = false;
};
