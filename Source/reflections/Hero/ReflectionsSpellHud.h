#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/ActorComponent.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "ReflectionsSpellHud.generated.h"

class UButton;
class UImage;
class UInputComponent;
class UReflectionsSampleSpellDriver;
class UTextBlock;
class UProgressBar;
class UVerticalBox;

/** Code-built HUD so the spell controls work without a widget Blueprint asset. */
UCLASS()
class REFLECTIONS_API UReflectionsSpellHudWidget : public UUserWidget
{
    GENERATED_BODY()
public:
    void SetDriver(UReflectionsSampleSpellDriver* InDriver);
protected:
    virtual void NativeOnInitialized() override;
    virtual void NativeTick(const FGeometry& Geometry, float DeltaSeconds) override;
private:
    void RefreshSelection();
    UFUNCTION() void SelectFirstSlot();
    UFUNCTION() void SelectSecondSlot();
    UFUNCTION() void SelectThirdSlot();
    UFUNCTION() void SelectFourthSlot();
    UPROPERTY(Transient) TObjectPtr<UReflectionsSampleSpellDriver> Driver;
    UPROPERTY(Transient) TArray<TObjectPtr<UButton>> SpellButtons;
    UPROPERTY(Transient) TArray<TObjectPtr<UTextBlock>> SpellLabels;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> Hint;
    void BuildReticle(class UCanvasPanel* Root);
    void UpdateReticle();
    /** Four spread ticks, a centre dot, four hit-marker ticks and the selected spell's name. */
    UPROPERTY(Transient) TArray<TObjectPtr<UImage>> ReticleTicks;
    UPROPERTY(Transient) TObjectPtr<UImage> ReticleDot;
    UPROPERTY(Transient) TArray<TObjectPtr<UImage>> HitTicks;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> SpellLabel;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> HealthLabel;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> ManaLabel;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> FeedbackLabel;
    UPROPERTY(Transient) TObjectPtr<UProgressBar> HealthBar;
    UPROPERTY(Transient) TObjectPtr<UProgressBar> ManaBar;
    UPROPERTY(Transient) TObjectPtr<UVerticalBox> TargetPanel;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> TargetLabel;
    UPROPERTY(Transient) TObjectPtr<UProgressBar> TargetHealthBar;
};

/** Attach to the local sample pawn to create and manage its spell HUD. */
UCLASS(ClassGroup=(UI), meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsSpellHudComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UReflectionsSpellHudComponent();
protected:
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
private:
    void EnableMouse();
    void DisableMouse();
    UPROPERTY(Transient) TObjectPtr<UReflectionsSpellHudWidget> Hud;
    UPROPERTY(Transient) TObjectPtr<UInputComponent> MouseInput;
    UPROPERTY(Transient) TObjectPtr<APlayerController> LocalPlayerController;
    bool bMouseEnabledByHud = false;
};

