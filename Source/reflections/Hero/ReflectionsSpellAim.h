#pragma once

#include "CoreMinimal.h"
#include "Camera/CameraModifier.h"
#include "Components/ActorComponent.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "ReflectionsSpellAim.generated.h"

class UDecalComponent;
class UInputAction;
class UMaterialInstanceDynamic;
class UMaterialInterface;

/** What the ground preview shows for the selected spell. */
UENUM()
enum class EReflectionsAimPreview : uint8
{
    None,
    HitMarker,
    Blast,
    GroundArea,
    Cone,
    Self
};

/**
 * Procedural camera feel for spells: aim zoom, a cast kick and decaying impact shake.
 * It runs after the gameplay camera rig, so it layers on top of whichever rig is active.
 */
UCLASS()
class REFLECTIONS_API UReflectionsSpellCameraModifier : public UCameraModifier
{
    GENERATED_BODY()

public:
    virtual bool ModifyCamera(float DeltaTime, FMinimalViewInfo& InOutPOV) override;

    /** 0..1 blend toward the aiming field of view. */
    float AimAlpha = 0.0f;
    /** Degrees removed from the field of view at full aim. */
    float AimZoomDegrees = 14.0f;

    void AddKick(float Amount) { Kick = FMath::Min(1.5f, Kick + Amount); }
    void AddTrauma(float Amount) { Trauma = FMath::Min(1.0f, Trauma + Amount); }

    static UReflectionsSpellCameraModifier* Get(const APlayerController* Controller);

private:
    float Kick = 0.0f;
    float Trauma = 0.0f;
    float Clock = 0.0f;
};

/**
 * Hold-to-aim support for spell casting: reads the existing IA_Aim (RMB / left trigger),
 * traces from the camera to find what the reticle is on, applies light aim assist toward
 * nearby enemies and draws a ground preview for the selected spell.
 */
UCLASS(ClassGroup=(Combat), meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsSpellAimComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsSpellAimComponent();

    UPROPERTY(EditAnywhere, Category="Aim", meta=(Units="cm"))
    float MaxAimDistance = 5000.0f;

    /** Ground-targeted area spells land no farther than this from the caster. */
    UPROPERTY(EditAnywhere, Category="Aim", meta=(Units="cm"))
    float MaxAreaCastDistance = 1800.0f;

    /** Half-angle of the cone in which enemies attract the shot. */
    UPROPERTY(EditAnywhere, Category="Aim|Assist", meta=(Units="deg"))
    float AssistConeDegrees = 7.0f;

    /** Max degrees per second the camera is nudged toward an enemy under the reticle while aiming. */
    UPROPERTY(EditAnywhere, Category="Aim|Assist")
    float AssistTurnRate = 5.0f;

    UFUNCTION(BlueprintPure, Category="Aim")
    bool IsAiming() const { return bAiming; }

    UFUNCTION(BlueprintPure, Category="Aim")
    float GetAimAlpha() const { return AimAlpha; }

    bool HasAssistTarget() const { return AssistTarget.IsValid(); }
    AActor* GetAssistTarget() const { return AssistTarget.Get(); }
    FVector GetAimPoint() const { return AimPoint; }
    FLinearColor GetElementColor() const { return ElementColor; }

    /** Where a spell released from Origin should go, resolved this frame (with assist). */
    FVector ResolveTarget(EHeroSpell Spell, const FVector& Origin, AActor*& OutTarget) const;

    /** Feedback hooks used by the HUD. */
    void NotifyCast();
    void NotifyHit(bool bKilled);
    float GetCastSpread() const { return CastSpread; }
    float GetHitMarker() const { return HitMarker; }
    bool WasKillMarker() const { return bKillMarker; }

    void SetSelectedSpell(EHeroSpell Spell) { SelectedSpell = Spell; }
    /** Gamepad aiming gets a wider assist cone and a stronger pull. */
    void SetUsingGamepad(bool bInGamepad) { bGamepad = bInGamepad; }

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
    APlayerController* GetLocalController() const;
    bool ReadAimInput(APlayerController* Controller) const;
    void UpdateAimTrace(APlayerController* Controller, float DeltaTime);
    void UpdatePreview();
    EReflectionsAimPreview PreviewFor(EHeroSpell Spell, float& OutRadius) const;
    FVector GroundBelow(const FVector& Point) const;
    FVector ClampToRange(const FVector& Point, float Range) const;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> AimAction;

    UPROPERTY(Transient)
    TObjectPtr<UDecalComponent> Preview;

    UPROPERTY(Transient)
    TObjectPtr<UMaterialInstanceDynamic> PreviewMaterial;

    UPROPERTY(Transient)
    TObjectPtr<UReflectionsSpellCameraModifier> CameraModifier;

    TWeakObjectPtr<AActor> AssistTarget;
    FVector AimPoint = FVector::ZeroVector;
    FVector AimNormal = FVector::UpVector;
    FVector ViewLocation = FVector::ZeroVector;
    FVector ViewDirection = FVector::ForwardVector;
    FLinearColor ElementColor = FLinearColor::White;
    EHeroSpell SelectedSpell = EHeroSpell::Fire;
    float AimAlpha = 0.0f;
    float CastSpread = 0.0f;
    float HitMarker = 0.0f;
    bool bKillMarker = false;
    bool bAiming = false;
    bool bAimHit = false;
    bool bGamepad = false;
};
