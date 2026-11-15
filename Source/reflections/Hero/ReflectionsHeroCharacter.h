#pragma once

#include "CoreMinimal.h"
#include "reflectionsCharacter.h"
#include "ReflectionsHeroCharacter.generated.h"

class UAnimMontage;
class UAnimSequenceBase;
class UChildActorComponent;
class UMaterialInterface;
class USkeletalMeshComponent;
class UAnimInstance;
class UStaticMesh;
class UStaticMeshComponent;

UENUM(BlueprintType)
enum class EHeroSpell : uint8
{
    Healing,
    Levitation,
    Water,
    Fire,
    FlameBurst,
    Firestorm,
    IceShard,
    FrostNova,
    TidalSurge,
    WaterOrb,
    ChainLightning,
    LightningBolt,
    ThunderWave,
    StoneShard,
    EarthShock,
    ForcePush,
    ArcaneBolt,
    GreaterHeal,
    HealingPulse,
    Shield,
    MAX UMETA(Hidden)
};

USTRUCT(BlueprintType)
struct FHeroSpellDefinition
{
    GENERATED_BODY()

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    TObjectPtr<UAnimSequenceBase> Animation;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, meta = (ClampMin = "0.0", Units = "s"))
    float ReleaseTime = 0.0f;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    TObjectPtr<UStaticMesh> PreviewMesh;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    TObjectPtr<UMaterialInterface> PreviewMaterial;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    FName ProjectileSocket;
};

USTRUCT(BlueprintType)
struct FHeroCoatVariant
{
    GENERATED_BODY()

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    TObjectPtr<UMaterialInterface> Outer;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    TObjectPtr<UMaterialInterface> Tails;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    TObjectPtr<UMaterialInterface> Lining;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    TObjectPtr<UMaterialInterface> Piping;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FHeroSpellReleased, EHeroSpell, Spell, FTransform, Origin);

/** Player controls, movement and montage playback for the modular hero Blueprint. */
UCLASS()
class AReflectionsHeroCharacter : public AreflectionsCharacter
{
    GENERATED_BODY()

public:
    AReflectionsHeroCharacter();

    UFUNCTION(BlueprintCallable, Category = "Hero|Spells")
    bool CastHeroSpell(EHeroSpell Spell);

    UFUNCTION(BlueprintPure, Category = "Hero|Spells")
    bool IsCastingHeroSpell() const { return ActiveCast != nullptr; }

    const FHeroSpellDefinition* FindSpellDefinition(EHeroSpell Spell) const { return Spells.Find(Spell); }

    UPROPERTY(BlueprintAssignable, Category = "Hero|Spells")
    FHeroSpellReleased OnHeroSpellReleased;

    UFUNCTION(BlueprintCallable, Category = "Hero|Visual")
    bool SetCoatVariant(int32 Index);

    virtual void DoMove(float Right, float Forward) override;
    virtual bool CanJumpInternal_Implementation() const override;

protected:
    virtual void BeginPlay() override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    virtual void Tick(float DeltaSeconds) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Hero|Visual")
    TObjectPtr<UChildActorComponent> HeroVisual;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Hero|Visual")
    TSubclassOf<UAnimInstance> BodyAnimationClass;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Hero|Movement")
    float WalkSpeed = 170.0f;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Hero|Movement")
    float JogSpeed = 400.0f;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Hero|Movement")
    float SprintSpeed = 595.0f;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Hero|Spells")
    TMap<EHeroSpell, FHeroSpellDefinition> Spells;

    UPROPERTY(EditDefaultsOnly, Category = "Hero|Visual")
    TArray<FHeroCoatVariant> CoatVariants;

private:
    void CycleCoat();
    void StartSprint();
    void StopSprint();
    void StartWalk();
    void StopWalk();
    void StartCrouch();
    void StopCrouch();
    void RefreshSpeed();
    void UpdateVisualHeight(float Lift);

    void Heal();
    void Levitate();
    void CastWater();
    void CastFire();
    void ReleaseHeroSpell(const FHeroSpellDefinition& Spell);
    void FinishHeroSpell(UAnimMontage* Montage, bool bInterrupted);
    void MoveSpellPreview(float DeltaSeconds);

    UPROPERTY(Transient)
    TObjectPtr<USkeletalMeshComponent> AnimatedBody;

    UPROPERTY(Transient)
    TObjectPtr<UAnimMontage> ActiveCast;

    UPROPERTY(VisibleAnywhere, Category = "Hero|Spells")
    TObjectPtr<UStaticMeshComponent> SpellPreview;

    EHeroSpell ActiveSpell = EHeroSpell::Healing;
    float PreviewTime = 0.0f;
    int32 CoatVariantIndex = 0;
    bool bCastReleased = false;
    bool bSprintHeld = false;
    bool bWalkHeld = false;
};
