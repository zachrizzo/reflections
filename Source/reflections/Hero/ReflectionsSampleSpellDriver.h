#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimNotifies/AnimNotify.h"
#include "Components/ActorComponent.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "ReflectionsSampleSpellDriver.generated.h"

class UInputComponent;
class UAnimMontage;
class UAnimSequenceBase;
class USkeletalMeshComponent;
class UChildActorComponent;
class UStaticMeshComponent;
class UReflectionsSpellAimComponent;
class UInputAction;
class UInputMappingContext;
class UEnhancedInputComponent;
struct FInputActionValue;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsManaChanged, float, Mana, float, MaxMana);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FReflectionsRespawned);

/** A spell from outside the catalog, cast through the normal windup / layered montage / follow-through / cancel flow. */
struct FReflectionsExternalCast
{
    TWeakObjectPtr<UAnimSequenceBase> Animation;      // null: use AimProxy's usual clip (weak: the struct outlives frames in ActiveExternal)
    float ReleaseTime = 0.5f;                         // seconds into Animation
    FName Socket = NAME_None;                         // NAME_None: between both hands
    EHeroSpell AimProxy = EHeroSpell::ArcaneBolt;     // drives the windup timing and Aim->ResolveTarget
    float ManaCost = 0.0f;                            // checked and spent like a catalog spell
    float Cooldown = 0.0f;
    TFunction<void(const FTransform& Origin, const FVector& Target, AActor* AimTarget)> OnRelease;  // called at the release frame
};

/** Marks the frame a cast leaves the hand. Tools/SpellVFX/author_combat_casts.py places it on each combat cast. */
UCLASS(meta=(DisplayName="Spell Release"))
class REFLECTIONS_API UReflectionsSpellReleaseNotify : public UAnimNotify
{
    GENERATED_BODY()
};

/**
 * Connects the sample pawn to the MetaHuman spell set.
 *
 * Casting is layered on the upper body (ABP_HeroSampleCastBlend blends DefaultSlot above spine_01), so the
 * player keeps moving while casting. Each cast is trimmed and sped up so the spell leaves the hand about a
 * third of a second after the button press, and its follow-through can be cancelled by the next cast.
 * Input is Enhanced Input (a runtime mapping context): hold RMB / LT to aim, LMB / RT / Q casts (holding repeats),
 * Tab / RB and Shift+Tab / LB cycle spells, 1-4 select, [ ] / D-pad left-right page.
 */
UCLASS(ClassGroup=(Combat), BlueprintType, meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsSampleSpellDriver : public UActorComponent
{
    GENERATED_BODY()
public:
    UReflectionsSampleSpellDriver();
    /** Optional second take for each spell. A missing take keeps the original animation. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Hero|Spells")
    TMap<EHeroSpell, FHeroSpellDefinition> AlternateSpells;
    /** Upper-body casting on a body Anim Blueprint with the DefaultSlot blended above the spine. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Hero|Spells")
    bool bUseLayeredCasting = true;
    /** Real seconds from button press to the spell leaving the hand for bolts. Heavier spells add a little. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Hero|Spells|Feel", meta=(ClampMin="0.1", Units="s"))
    float CastWindup = 0.28f;
    /** Real seconds of follow-through kept after release before the cast blends out. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Hero|Spells|Feel", meta=(ClampMin="0.05", Units="s"))
    float FollowThrough = 0.3f;
    /** After release, the next cast may interrupt the follow-through after this long. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Hero|Spells|Feel", meta=(ClampMin="0", Units="s"))
    float CancelWindow = 0.1f;
    /** Fastest speed-up applied to a long source clip. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Hero|Spells|Feel", meta=(ClampMin="1"))
    float MaxPlayRate = 1.9f;

    UFUNCTION(BlueprintCallable, Category="Hero|Spells")
    bool CastSpell(EHeroSpell Spell);
    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    bool IsCasting() const { return ActiveMontage != nullptr; }
    UFUNCTION(BlueprintCallable, Category="Hero|Spells")
    void SetSelectedSpell(EHeroSpell Spell);
    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    EHeroSpell GetSelectedSpell() const { return SelectedSpell; }
    UFUNCTION(BlueprintCallable, Category="Hero|Spells")
    bool CastSelectedSpell() { return CastSpell(SelectedSpell); }
    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    int32 GetSpellPage() const { return 0; }
    UFUNCTION(BlueprintCallable, Category="Hero|Spells")
    void ChangeSpellPage(int32 Delta);
    UFUNCTION(BlueprintCallable, Category="Hero|Spells")
    void SelectSpellSlot(int32 Slot);
    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    FString GetSpellSlotName(int32 Slot) const;

    UReflectionsSpellAimComponent* GetAim() const { return Aim; }

    /** Mana pool spent by each spell's ManaCost; refills after a short pause in casting. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Hero|Spells|Resources", meta=(ClampMin="1"))
    float MaxMana = 100.0f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Hero|Spells|Resources", meta=(ClampMin="0"))
    float ManaRegenPerSecond = 4.5f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Hero|Spells|Resources", meta=(ClampMin="0", Units="s"))
    float ManaRegenDelay = 1.75f;

    /** Health the hero regains per second once out of combat (no damage for HealthRegenDelay). 0 turns it off. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Hero|Spells|Resources", meta=(ClampMin="0"))
    float HealthRegenPerSecond = 3.0f;

    /** Seconds without taking damage before health starts coming back. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Hero|Spells|Resources", meta=(ClampMin="0", Units="s"))
    float HealthRegenDelay = 6.0f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Hero|Spells|Resources", meta=(ClampMin="0", Units="s"))
    float RespawnDelay = 5.0f;

    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    float GetMana() const { return Mana; }

    /** The magic bar: fires whenever mana changes (spend, refill, respawn). */
    UPROPERTY(BlueprintAssignable, Category="Hero|Spells|Resources")
    FReflectionsManaChanged OnManaChanged;
    /** Spends mana if there is enough; otherwise sets the usual "not enough mana" feedback and returns false. */
    UFUNCTION(BlueprintCallable, Category="Hero|Spells|Resources")
    bool TrySpendMana(float Amount);
    /** Same as TrySpendMana without feedback text; spends nothing and returns false if Amount exceeds the bar. */
    UFUNCTION(BlueprintCallable, Category="Hero|Spells|Resources")
    bool SpendMagic(float Amount);
    /** Adds mana up to the max (quest rewards, pickups). Ignored while defeated or for Amount <= 0. */
    UFUNCTION(BlueprintCallable, Category="Hero|Spells|Resources")
    void RestoreMana(float Amount) { if (!bDefeated && Amount > 0.0f) SetMana(Mana + Amount); }
    UFUNCTION(BlueprintPure, Category="Hero|Spells|Resources")
    float GetMagic() const { return Mana; }
    UFUNCTION(BlueprintPure, Category="Hero|Spells|Resources")
    float GetMaxMagic() const { return MaxMana; }

    /** Casts an outside spell through the normal flow; OnRelease fires at the release frame. */
    bool CastExternal(const FReflectionsExternalCast& Cast);
    /** If set and it returns true, the primary cast (LMB / RT, including held repeat) was handled externally. */
    TFunction<bool()> PrimaryCastOverride;
    /** True while the most recent input came from a gamepad (HUD prompts, aim assist strength). */
    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    bool IsUsingGamepad() const { return bUsingGamepad; }
    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    float GetSpellManaCost(EHeroSpell Spell) const;
    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    float GetSpellCooldownRemaining(EHeroSpell Spell) const;
    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    bool IsDefeated() const { return bDefeated; }
    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    float GetRespawnTimeRemaining() const;
    /** Where Respawn() puts the hero (game flow moves it to the latest checkpoint). Defaults to the BeginPlay transform. */
    UFUNCTION(BlueprintCallable, Category="Hero|Spells")
    void SetRespawnTransform(const FTransform& Transform);
    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    FTransform GetRespawnTransform() const { return SpawnTransform; }
    /** Fires at the end of Respawn(), after the teleport and the health and mana reset. */
    UPROPERTY(BlueprintAssignable, Category="Hero|Spells")
    FReflectionsRespawned OnRespawned;
    /** Respawns now instead of waiting out RespawnDelay (the death screen's Respawn button). Does nothing unless defeated. */
    UFUNCTION(BlueprintCallable, Category="Hero|Spells")
    void RespawnNow() { if (bDefeated) Respawn(); }
    /** Short message after a refused cast (no mana, recharging); empty when there is nothing to say. */
    UFUNCTION(BlueprintPure, Category="Hero|Spells")
    FString GetCastFeedback() const;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;
private:
    void BindControls();
    void SelectFirstSlot(); void SelectSecondSlot(); void SelectThirdSlot(); void SelectFourthSlot();
    void PreviousSpell(); void NextSpell();
    void CastSelected();
    void PrimaryPressed();
    void PrimaryReleased();
    void FinishCast(UAnimMontage* Montage, bool bInterrupted);
    void Release();
    void LoadCombatClips();
    bool ResolveCast(EHeroSpell Spell, int32 Count, FHeroSpellDefinition& Out, bool& bOutBothHands) const;
    bool ReadyForNextCast(bool bRepeat) const;
    void UpdateAimPose();
    FVector ReleaseLocation() const;
    bool CanAfford(EHeroSpell Spell);
    bool PlayCast(EHeroSpell Spell, const FHeroSpellDefinition& Definition, bool bBoth);
    void SetMana(float Value);
    void UpdateInputDevice(APlayerController* PC);
    void OnCastAction(const FInputActionValue& Value);
    /** Swallows sample debug keys (see BindControls); does nothing on purpose. */
    void IgnoreInput(const FInputActionValue& Value) {}
    void OnCastReleased(const FInputActionValue& Value);
    void SetFeedback(const FString& Text);
    UFUNCTION() void OnOwnerDied(AActor* Source);
    void Respawn();

    UPROPERTY(Transient) TObjectPtr<UEnhancedInputComponent> SpellInput;
    UPROPERTY(Transient) TObjectPtr<UInputMappingContext> SpellContext;
    UPROPERTY(Transient) TArray<TObjectPtr<UInputAction>> SpellActions;
    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> Body;
    UPROPERTY(Transient) TObjectPtr<UAnimMontage> ActiveMontage;
    UPROPERTY(Transient) TObjectPtr<UAnimMontage> AimMontage;
    UPROPERTY(Transient) TSubclassOf<UAnimInstance> RetargetClass;
    UPROPERTY(Transient) TObjectPtr<AReflectionsHeroCharacter> SpellDefaults;
    UPROPERTY(Transient) TObjectPtr<UReflectionsSpellAimComponent> Aim;
    UPROPERTY(Transient) FHeroSpellDefinition ActiveDefinition;
    UPROPERTY(Transient) TMap<FName, TObjectPtr<UAnimSequenceBase>> CombatClips;
    TMap<EHeroSpell, int32> CastCounts;
    EHeroSpell ActiveSpell = EHeroSpell::Healing;
    EHeroSpell SelectedSpell = EHeroSpell::Firestorm;
    float CastClock = 0.0f;
    float ReleaseClock = 0.0f;
    bool bReleased = false;
    bool bBothHands = false;
    bool bStopping = false;
    bool bMovementLocked = false;
    bool bRestorePending = false;
    bool bPrimaryHeld = false;
    float Mana = 100.0f;
    double LastCastTime = -100.0;
    /** Out-of-combat health regen: when the hero last lost health, its last seen health, and regen not yet applied. */
    double LastDamageTime = -100.0;
    float LastSeenHealth = -1.0f;
    float PendingRegen = 0.0f;
    UFUNCTION()
    void OnOwnerHealthChanged(float Health, float MaxHealth, AActor* Source);
    double FeedbackUntil = 0.0;
    double RespawnAt = 0.0;
    FString Feedback;
    FTransform SpawnTransform;
    bool bRespawnTransformSet = false;
    TMap<EHeroSpell, double> CooldownUntil;
    bool bDefeated = false;
    bool bUsingGamepad = false;
    TOptional<FReflectionsExternalCast> ActiveExternal;
    double ExternalCooldownUntil = 0.0;
};
