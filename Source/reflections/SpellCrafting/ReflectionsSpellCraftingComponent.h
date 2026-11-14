#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "SpellCrafting/ReflectionsSpellCraftingTypes.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "ReflectionsSpellCraftingComponent.generated.h"

class APlayerController; class UAnimMontage;
class UAnimSequenceBase;
class UInputComponent;
class USkeletalMeshComponent;
class UReflectionsSampleSpellDriver;
class UReflectionsSpellCraftingScreen;
class UReflectionsSpellRecipeRelay;

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FReflectionsCraftedSlotsChanged);

/**
 * The player's crafted spells: four saved slots, the crafting screen, and casting through the spell core's
 * aim / cast flow. Added automatically to the local spell-casting pawn by UReflectionsCraftedSpellSubsystem.
 *
 * Keyboard: K opens the crafting screen, 5-8 select a crafted slot (again to return to the catalog spells),
 * left mouse casts. Controller: View/Back opens the screen, D-pad Up cycles slots, RT casts; LB/RB/1-4 return to the catalog.
 */
UCLASS(ClassGroup=(Combat), BlueprintType, meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsSpellCraftingComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UReflectionsSpellCraftingComponent();

    static constexpr int32 NumSlots = 4;

    UFUNCTION(BlueprintPure, Category="Spell Crafting")
    FCraftedSpellRecipe GetSlotRecipe(int32 Slot) const;
    const FCraftedSpellResolved& GetSlotSpell(int32 Slot) const;

    /** Stores a recipe in a slot (and saves). */
    UFUNCTION(BlueprintCallable, Category="Spell Crafting")
    void SetSlotRecipe(int32 Slot, const FCraftedSpellRecipe& Recipe, bool bSave = true);

    /** Makes a crafted slot the one the primary cast uses. -1 returns to the catalog spells. */
    UFUNCTION(BlueprintCallable, Category="Spell Crafting")
    void SelectCraftedSlot(int32 Slot);

    UFUNCTION(BlueprintPure, Category="Spell Crafting")
    int32 GetActiveSlot() const { return ActiveSlot; }

    UFUNCTION(BlueprintPure, Category="Spell Crafting")
    bool HasActiveCraftedSpell() const { return ActiveSlot >= 0; }

    /** Casts the active crafted slot through the normal aim/cast flow. */
    UFUNCTION(BlueprintCallable, Category="Spell Crafting")
    bool CastActive();

    /** Casts any resolved spell (used by the crafting screen's preview too). */
    bool CastResolved(const FCraftedSpellResolved& Spell, int32 SlotForCooldown);

    UFUNCTION(BlueprintCallable, Category="Spell Crafting") void ToggleCraftingScreen();
    UFUNCTION(BlueprintCallable, Category="Spell Crafting") void OpenCraftingScreen();
    UFUNCTION(BlueprintCallable, Category="Spell Crafting") void CloseCraftingScreen();
    UFUNCTION(BlueprintPure, Category="Spell Crafting") bool IsCraftingScreenOpen() const;

    float GetCooldownRemaining(int32 Slot) const;
    FString GetFeedback() const;
    bool IsUsingSpellCoreCast() const { return bCoreCastAvailable; }
    UReflectionsSampleSpellDriver* GetDriver() const { return Driver; }

    /** Dev-only: asks the local relay to turn a sentence into a recipe. Falls back to the offline parser. */
    void DescribeSpell(const FString& Text, TFunction<void(bool bOk, const FCraftedSpellRecipe& Recipe, const FString& Source)> Done);

    UPROPERTY(BlueprintAssignable, Category="Spell Crafting")
    FReflectionsCraftedSlotsChanged OnSlotsChanged;

    UFUNCTION(BlueprintCallable, Category="Spell Crafting") void SaveSlots();
    UFUNCTION(BlueprintCallable, Category="Spell Crafting") void LoadSlots();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;

private:
    struct FGesture
    {
        UAnimSequenceBase* Animation = nullptr;
        float ReleaseTime = 0.5f;
        FName Socket = NAME_None;
    };

    void BindControls();
    void UpdateCastCapture();
    /** A catalog pick (1-4, Tab, LB/RB, pages) always hands the cast button back to the catalog spells. */
    UFUNCTION() void OnCatalogSpellChanged(EHeroSpell Spell);
    bool CatalogSelectionMoved() const;
    void SelectSlot1(); void SelectSlot2(); void SelectSlot3(); void SelectSlot4();
    void CycleSlot();
    void PrimaryPressed();
    void PrimaryReleased();
    bool PrimaryOverride();
    FGesture ResolveGesture(ECraftedSpellForm Form);
    void FindBody();
    FVector HandLocation(FName Socket) const;
    void ReleaseNow(const FCraftedSpellResolved& Spell, const FTransform& Origin, const FVector& Target, AActor* AimTarget);
    bool SpendMana(float Cost);
    void SetFeedback(const FString& Text, float Seconds = 1.6f);
    void RefreshAimProxy();
    void ResolveAll();

    UPROPERTY(Transient) TObjectPtr<UReflectionsSampleSpellDriver> Driver;
    UPROPERTY(Transient) TObjectPtr<UInputComponent> CraftInput;
    UPROPERTY(Transient) TObjectPtr<UInputComponent> CastCapture;
    UPROPERTY(Transient) TObjectPtr<APlayerController> InputController;
    UPROPERTY(Transient) TObjectPtr<UReflectionsSpellCraftingScreen> Screen;
    UPROPERTY(Transient) TObjectPtr<UReflectionsSpellRecipeRelay> Relay;
    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> Body;
    UPROPERTY(Transient) TObjectPtr<UAnimMontage> FallbackMontage;
    UPROPERTY(Transient) TMap<FName, TObjectPtr<UAnimSequenceBase>> GestureCache;

    TArray<FCraftedSpellRecipe> Slots;
    TArray<FCraftedSpellResolved> Resolved;
    TArray<double> CooldownUntil;
    int32 ActiveSlot = -1;
    int32 CastCount = 0;
    bool bPrimaryHeld = false;
    bool bCoreCastAvailable = false;
    bool bBound = false;
    bool bCapturePushed = false;
    EHeroSpell CatalogAtSelect = EHeroSpell::Fire;

    // Fallback cast (used only when the spell core does not expose an external cast).
    FCraftedSpellResolved PendingSpell;
    FGesture PendingGesture;
    bool bPendingRelease = false;
    double PendingStarted = 0.0;
    double LastCastTime = -10.0;

    FString Feedback;
    double FeedbackUntil = 0.0;
};
