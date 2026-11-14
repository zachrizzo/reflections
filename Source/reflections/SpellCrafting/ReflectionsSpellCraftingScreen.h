#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "SpellCrafting/ReflectionsSpellCraftingTypes.h"
#include "ReflectionsSpellCraftingScreen.generated.h"

class UBorder;
class UButton;
class UCanvasPanel;
class UEditableTextBox;
class UHorizontalBox;
class UTextBlock;
class UVerticalBox;
class UReflectionsSpellCraftingComponent;

/** One editable line of the recipe. */
UENUM()
enum class ECraftingRow : uint8 { Form, Element, Behaviour1, Behaviour2, Behaviour3, Trigger, Power, Look, MAX };

/**
 * Code-built crafting screen (no widget Blueprint), usable with mouse and keyboard or a controller.
 *
 * Up/Down (D-pad, stick, arrows) move between rows, Left/Right change the focused row, A/Enter steps it forward.
 * LB/RB or Q/E switch slots, X or R re-rolls the look, Y or F equips the slot, B/Esc/K/View closes.
 * The mouse can click any row or its arrows. Every change applies to the slot at once and is saved on close.
 * While closed it shows a small indicator for the active crafted slot.
 */
UCLASS()
class REFLECTIONS_API UReflectionsSpellCraftingScreen : public UUserWidget
{
    GENERATED_BODY()

public:
    void Bind(UReflectionsSpellCraftingComponent* InCrafting);
    void Open(UReflectionsSpellCraftingComponent* InCrafting);
    void Close();
    bool IsOpen() const { return bOpen; }

protected:
    virtual void NativeOnInitialized() override;
    virtual void NativeTick(const FGeometry& Geometry, float DeltaSeconds) override;
    virtual FReply NativeOnPreviewKeyDown(const FGeometry& Geometry, const FKeyEvent& KeyEvent) override;
    virtual FReply NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& KeyEvent) override;

private:
    UTextBlock* MakeText(int32 Size, const FLinearColor& Color, const FString& Text = FString());
    UButton* MakeButton(const FString& Label, int32 Size, bool bFocusable, UTextBlock** OutLabel = nullptr);
    void BuildEditor(UCanvasPanel* Root);
    void BuildIndicator(UCanvasPanel* Root);

    void Step(ECraftingRow Row, int32 Delta);
    void SelectSlot(int32 NewSlot);
    void Refresh();
    void RefreshIndicator();
    int32 FocusedRow() const;
    void FocusRow(int32 Row);
    FString RowValue(ECraftingRow Row, FString& OutHint) const;

    UFUNCTION() void OnRow0(); UFUNCTION() void OnRow1(); UFUNCTION() void OnRow2(); UFUNCTION() void OnRow3();
    UFUNCTION() void OnRow4(); UFUNCTION() void OnRow5(); UFUNCTION() void OnRow6(); UFUNCTION() void OnRow7();
    UFUNCTION() void OnLess0(); UFUNCTION() void OnLess1(); UFUNCTION() void OnLess2(); UFUNCTION() void OnLess3();
    UFUNCTION() void OnLess4(); UFUNCTION() void OnLess5(); UFUNCTION() void OnLess6(); UFUNCTION() void OnLess7();
    UFUNCTION() void OnSlot0(); UFUNCTION() void OnSlot1(); UFUNCTION() void OnSlot2(); UFUNCTION() void OnSlot3();
    UFUNCTION() void OnEquip();
    UFUNCTION() void OnReset();
    UFUNCTION() void OnClose();
    UFUNCTION() void OnConjure();
    UFUNCTION() void OnConjureCommitted(const FText& Text, ETextCommit::Type Method);
    UFUNCTION() void OnReroll();

    UPROPERTY(Transient) TObjectPtr<UReflectionsSpellCraftingComponent> Crafting;
    UPROPERTY(Transient) TObjectPtr<UBorder> EditorPanel;
    UPROPERTY(Transient) TObjectPtr<UVerticalBox> IndicatorPanel;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> IndicatorName;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> IndicatorHint;
    UPROPERTY(Transient) TArray<TObjectPtr<UButton>> SlotButtons;
    UPROPERTY(Transient) TArray<TObjectPtr<UTextBlock>> SlotLabels;
    UPROPERTY(Transient) TArray<TObjectPtr<UButton>> RowButtons;
    UPROPERTY(Transient) TArray<TObjectPtr<UTextBlock>> RowValues;
    UPROPERTY(Transient) TArray<TObjectPtr<UTextBlock>> RowHints;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> SpellName;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> SpellStats;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> SpellDescription;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> SpellSynergies;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> StatusLine;
    UPROPERTY(Transient) TArray<TObjectPtr<UBorder>> Swatches;
    UPROPERTY(Transient) TObjectPtr<UEditableTextBox> DescribeBox;
    UPROPERTY(Transient) TObjectPtr<UButton> ConjureButton;
    UPROPERTY(Transient) TObjectPtr<UButton> EquipButton;

    int32 EditSlot = 0;
    bool bOpen = false;
    FString Status;
    double StatusUntil = 0.0;
};
