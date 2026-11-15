#include "SpellCrafting/ReflectionsSpellCraftingScreen.h"

#include "SpellCrafting/ReflectionsSpellCraftingComponent.h"
#include "SpellCrafting/ReflectionsSpellCraftingLibrary.h"
#include "SpellCrafting/ReflectionsSpellRecipeRelay.h"
#include "SpellCrafting/ReflectionsCraftedSpellSubsystem.h"
#include "Hero/ReflectionsSampleSpellDriver.h"

#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/ButtonSlot.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/EditableTextBox.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/SizeBox.h"
#include "Components/Spacer.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"

namespace
{
    const FLinearColor Gold(0.98f, 0.82f, 0.48f);
    const FLinearColor Paper(0.93f, 0.9f, 0.84f);
    const FLinearColor Dim(0.62f, 0.6f, 0.58f);
    const FLinearColor ButtonIdle(0.09f, 0.085f, 0.11f, 1.0f);
    const FLinearColor ButtonFocus(0.55f, 0.42f, 0.16f, 1.0f);
    constexpr int32 NumRows = static_cast<int32>(ECraftingRow::MAX);

    const TCHAR* RowLabel(ECraftingRow Row)
    {
        switch (Row)
        {
        case ECraftingRow::Form: return TEXT("Form");
        case ECraftingRow::Element: return TEXT("Element");
        case ECraftingRow::Behaviour1: return TEXT("Behaviour I");
        case ECraftingRow::Behaviour2: return TEXT("Behaviour II");
        case ECraftingRow::Behaviour3: return TEXT("Behaviour III");
        case ECraftingRow::Trigger: return TEXT("Trigger");
        case ECraftingRow::Power: return TEXT("Power");
        case ECraftingRow::Look: return TEXT("Look");
        default: return TEXT("");
        }
    }

    template <typename TEnum>
    TEnum Wrap(TEnum Value, int32 Delta, int32 First = 0)
    {
        const int32 Count = static_cast<int32>(TEnum::MAX) - First;
        const int32 Index = static_cast<int32>(Value) - First;
        return static_cast<TEnum>(First + ((Index + Delta) % Count + Count) % Count);
    }

    bool IsLeft(const FKey& Key) { return Key == EKeys::Left || Key == EKeys::Gamepad_DPad_Left || Key == EKeys::Gamepad_LeftStick_Left || Key == EKeys::A; }
    bool IsRight(const FKey& Key) { return Key == EKeys::Right || Key == EKeys::Gamepad_DPad_Right || Key == EKeys::Gamepad_LeftStick_Right || Key == EKeys::D; }
}

UTextBlock* UReflectionsSpellCraftingScreen::MakeText(int32 Size, const FLinearColor& Color, const FString& Text)
{
    UTextBlock* Block = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    FSlateFontInfo Font = Block->GetFont();
    Font.Size = Size;
    Block->SetFont(Font);
    Block->SetColorAndOpacity(FSlateColor(Color));
    Block->SetText(FText::FromString(Text));
    return Block;
}

UButton* UReflectionsSpellCraftingScreen::MakeButton(const FString& Label, int32 Size, bool bFocusable, UTextBlock** OutLabel)
{
    UButton* Button = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass());
    // Mouse-only arrows stay out of keyboard/controller navigation. InitIsFocusable is protected, so set the
    // construction-time property directly before the Slate widget exists.
    PRAGMA_DISABLE_DEPRECATION_WARNINGS
    Button->IsFocusable = bFocusable;
    PRAGMA_ENABLE_DEPRECATION_WARNINGS
    Button->SetBackgroundColor(ButtonIdle);
    UTextBlock* Text = MakeText(Size, Paper, Label);
    Text->SetJustification(ETextJustify::Center);
    if (UButtonSlot* Content = Cast<UButtonSlot>(Button->AddChild(Text))) Content->SetPadding(FMargin(10, 5));
    if (OutLabel) *OutLabel = Text;
    return Button;
}

void UReflectionsSpellCraftingScreen::NativeOnInitialized()
{
    Super::NativeOnInitialized();
    if (!WidgetTree || WidgetTree->RootWidget) return;
    UCanvasPanel* Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
    WidgetTree->RootWidget = Root;
    Root->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
    BuildIndicator(Root);
    BuildEditor(Root);
    SetIsFocusable(true);
}

void UReflectionsSpellCraftingScreen::BuildIndicator(UCanvasPanel* Root)
{
    IndicatorPanel = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    IndicatorPanel->SetVisibility(ESlateVisibility::HitTestInvisible);
    UCanvasPanelSlot* IndicatorSlot = Root->AddChildToCanvas(IndicatorPanel);
    IndicatorSlot->SetAnchors(FAnchors(1.0f, 1.0f));
    IndicatorSlot->SetAlignment(FVector2D(1.0f, 1.0f));
    IndicatorSlot->SetPosition(FVector2D(-28.0f, -30.0f));
    IndicatorSlot->SetAutoSize(true);
    IndicatorName = MakeText(15, Gold);
    IndicatorName->SetJustification(ETextJustify::Right);
    IndicatorPanel->AddChildToVerticalBox(IndicatorName)->SetHorizontalAlignment(HAlign_Right);
    IndicatorHint = MakeText(11, Dim);
    IndicatorHint->SetJustification(ETextJustify::Right);
    IndicatorPanel->AddChildToVerticalBox(IndicatorHint)->SetHorizontalAlignment(HAlign_Right);
}

void UReflectionsSpellCraftingScreen::BuildEditor(UCanvasPanel* Root)
{
    EditorPanel = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
    EditorPanel->SetBrushColor(FLinearColor(0.015f, 0.014f, 0.022f, 0.93f));
    EditorPanel->SetPadding(FMargin(26.0f, 20.0f));
    EditorPanel->SetVisibility(ESlateVisibility::Collapsed);
    UCanvasPanelSlot* PanelSlot = Root->AddChildToCanvas(EditorPanel);
    PanelSlot->SetAnchors(FAnchors(0.5f, 0.5f));
    PanelSlot->SetAlignment(FVector2D(0.5f, 0.5f));
    PanelSlot->SetAutoSize(true);

    UVerticalBox* Main = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    EditorPanel->SetContent(Main);

    // Header: title and slot tabs.
    UHorizontalBox* Header = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
    Main->AddChildToVerticalBox(Header)->SetPadding(FMargin(0, 0, 0, 14));
    UHorizontalBoxSlot* TitleSlot = Header->AddChildToHorizontalBox(MakeText(24, Gold, TEXT("SPELL CRAFTING")));
    TitleSlot->SetVerticalAlignment(VAlign_Center);
    TitleSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
    for (int32 i = 0; i < UReflectionsSpellCraftingComponent::NumSlots; ++i)
    {
        UTextBlock* Label = nullptr;
        UButton* Tab = MakeButton(FString::Printf(TEXT("Slot %d"), i + 1), 13, true, &Label);
        Header->AddChildToHorizontalBox(Tab)->SetPadding(FMargin(4, 0));
        SlotButtons.Add(Tab);
        SlotLabels.Add(Label);
    }
    SlotButtons[0]->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnSlot0);
    SlotButtons[1]->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnSlot1);
    SlotButtons[2]->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnSlot2);
    SlotButtons[3]->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnSlot3);

    UHorizontalBox* Body = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
    Main->AddChildToVerticalBox(Body);

    // Left: the recipe rows.
    USizeBox* LeftSize = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    LeftSize->SetWidthOverride(500.0f);
    Body->AddChildToHorizontalBox(LeftSize)->SetPadding(FMargin(0, 0, 22, 0));
    UVerticalBox* Left = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    LeftSize->AddChild(Left);
    for (int32 Row = 0; Row < NumRows; ++Row)
    {
        UHorizontalBox* Line = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
        Left->AddChildToVerticalBox(Line)->SetPadding(FMargin(0, 3, 0, 0));
        USizeBox* LabelSize = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
        LabelSize->SetWidthOverride(120.0f);
        LabelSize->AddChild(MakeText(13, Dim, RowLabel(static_cast<ECraftingRow>(Row))));
        Line->AddChildToHorizontalBox(LabelSize)->SetVerticalAlignment(VAlign_Center);
        UButton* Less = MakeButton(TEXT("<"), 13, false);
        Line->AddChildToHorizontalBox(Less)->SetPadding(FMargin(0, 0, 4, 0));
        UTextBlock* Value = nullptr;
        UButton* RowButton = MakeButton(TEXT(""), 14, true, &Value);
        UHorizontalBoxSlot* RowSlot = Line->AddChildToHorizontalBox(RowButton);
        RowSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
        UButton* More = MakeButton(TEXT(">"), 13, false);
        Line->AddChildToHorizontalBox(More)->SetPadding(FMargin(4, 0, 0, 0));
        RowButtons.Add(RowButton);
        RowValues.Add(Value);
        UTextBlock* Hint = MakeText(10, Dim);
        Left->AddChildToVerticalBox(Hint)->SetPadding(FMargin(124, 1, 0, 2));
        RowHints.Add(Hint);
        // Mouse arrows and the row itself; the row also steps forward on A / Enter.
        switch (Row)
        {
        case 0: RowButton->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow0); More->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow0); Less->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnLess0); break;
        case 1: RowButton->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow1); More->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow1); Less->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnLess1); break;
        case 2: RowButton->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow2); More->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow2); Less->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnLess2); break;
        case 3: RowButton->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow3); More->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow3); Less->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnLess3); break;
        case 4: RowButton->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow4); More->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow4); Less->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnLess4); break;
        case 5: RowButton->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow5); More->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow5); Less->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnLess5); break;
        case 6: RowButton->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow6); More->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow6); Less->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnLess6); break;
        default: RowButton->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow7); More->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnRow7); Less->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnLess7); break;
        }
    }

    // Right: what the recipe became.
    USizeBox* RightSize = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    RightSize->SetWidthOverride(440.0f);
    Body->AddChildToHorizontalBox(RightSize);
    UVerticalBox* Right = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    RightSize->AddChild(Right);
    SpellName = MakeText(22, Gold);
    SpellName->SetAutoWrapText(true);
    Right->AddChildToVerticalBox(SpellName)->SetPadding(FMargin(0, 0, 0, 6));
    UHorizontalBox* Ramp = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
    Right->AddChildToVerticalBox(Ramp)->SetPadding(FMargin(0, 0, 0, 10));
    for (int32 i = 0; i < 3; ++i)
    {
        USizeBox* SwatchSize = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
        SwatchSize->SetWidthOverride(i == 0 ? 90.0f : 54.0f);
        SwatchSize->SetHeightOverride(14.0f);
        UBorder* Swatch = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
        SwatchSize->AddChild(Swatch);
        Ramp->AddChildToHorizontalBox(SwatchSize)->SetPadding(FMargin(0, 0, 4, 0));
        Swatches.Add(Swatch);
    }
    SpellStats = MakeText(13, Paper);
    Right->AddChildToVerticalBox(SpellStats)->SetPadding(FMargin(0, 0, 0, 8));
    SpellDescription = MakeText(13, FLinearColor(0.82f, 0.8f, 0.76f));
    SpellDescription->SetAutoWrapText(true);
    Right->AddChildToVerticalBox(SpellDescription)->SetPadding(FMargin(0, 0, 0, 8));
    SpellSynergies = MakeText(13, Gold);
    SpellSynergies->SetAutoWrapText(true);
    Right->AddChildToVerticalBox(SpellSynergies);

    // Describe your spell.
    UHorizontalBox* Describe = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
    Main->AddChildToVerticalBox(Describe)->SetPadding(FMargin(0, 14, 0, 0));
    DescribeBox = WidgetTree->ConstructWidget<UEditableTextBox>(UEditableTextBox::StaticClass());
    DescribeBox->SetHintText(FText::FromString(TEXT("Describe your spell: \"a slow orb of lightning that pulls enemies in\"")));
    DescribeBox->SetClearKeyboardFocusOnCommit(false);
    DescribeBox->OnTextCommitted.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnConjureCommitted);
    Describe->AddChildToHorizontalBox(DescribeBox)->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
    ConjureButton = MakeButton(TEXT("Conjure"), 13, true);
    ConjureButton->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnConjure);
    Describe->AddChildToHorizontalBox(ConjureButton)->SetPadding(FMargin(6, 0, 0, 0));

    // Actions.
    UHorizontalBox* Actions = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
    Main->AddChildToVerticalBox(Actions)->SetPadding(FMargin(0, 12, 0, 0));
    EquipButton = MakeButton(TEXT("Equip & Close  (Y / F)"), 13, true);
    EquipButton->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnEquip);
    Actions->AddChildToHorizontalBox(EquipButton)->SetPadding(FMargin(0, 0, 6, 0));
    UButton* Reroll = MakeButton(TEXT("New Look  (X / R)"), 13, true);
    Reroll->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnReroll);
    Actions->AddChildToHorizontalBox(Reroll)->SetPadding(FMargin(0, 0, 6, 0));
    UButton* Reset = MakeButton(TEXT("Starter Spell"), 13, true);
    Reset->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnReset);
    Actions->AddChildToHorizontalBox(Reset)->SetPadding(FMargin(0, 0, 6, 0));
    UButton* CloseButton = MakeButton(TEXT("Close  (B / Esc)"), 13, true);
    CloseButton->OnClicked.AddDynamic(this, &UReflectionsSpellCraftingScreen::OnClose);
    Actions->AddChildToHorizontalBox(CloseButton);

    StatusLine = MakeText(12, FLinearColor(0.6f, 0.85f, 1.0f));
    Main->AddChildToVerticalBox(StatusLine)->SetPadding(FMargin(0, 8, 0, 0));
    Main->AddChildToVerticalBox(MakeText(11, Dim,
        TEXT("Up/Down move  -  Left/Right change  -  A/Enter next  -  LB/RB or Q/E slot  -  X/R new look  -  Y/F equip  -  B/Esc close")))->SetPadding(FMargin(0, 6, 0, 0));
}

void UReflectionsSpellCraftingScreen::Bind(UReflectionsSpellCraftingComponent* InCrafting)
{
    Crafting = InCrafting;
    RefreshIndicator();
}

void UReflectionsSpellCraftingScreen::Open(UReflectionsSpellCraftingComponent* InCrafting)
{
    Crafting = InCrafting;
    if (!Crafting || !EditorPanel) return;
    bOpen = true;
    EditSlot = FMath::Max(0, Crafting->GetActiveSlot());
    EditorPanel->SetVisibility(ESlateVisibility::Visible);
    IndicatorPanel->SetVisibility(ESlateVisibility::Collapsed);
    if (APlayerController* PC = GetOwningPlayer())
    {
        FInputModeUIOnly Mode;
        Mode.SetWidgetToFocus(RowButtons[0]->TakeWidget());
        Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        PC->SetInputMode(Mode);
        PC->SetShowMouseCursor(true);
        PC->FlushPressedKeys();
    }
    FocusRow(0);
    Refresh();
}

void UReflectionsSpellCraftingScreen::Close()
{
    if (!bOpen) return;
    bOpen = false;
    EditorPanel->SetVisibility(ESlateVisibility::Collapsed);
    IndicatorPanel->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (Crafting) Crafting->SaveSlots();
    if (APlayerController* PC = GetOwningPlayer())
    {
        PC->SetShowMouseCursor(false);
        PC->SetInputMode(FInputModeGameOnly());
        PC->FlushPressedKeys();
    }
    RefreshIndicator();
}

// ------------------------------------------------------------------------------------------------ editing
void UReflectionsSpellCraftingScreen::Step(ECraftingRow Row, int32 Delta)
{
    if (!Crafting) return;
    FCraftedSpellRecipe R = Crafting->GetSlotRecipe(EditSlot);
    auto StepModifier = [&R, Delta](int32 Index)
    {
        // Behaviour slots hold None or any behaviour not already used by another slot.
        TArray<ECraftedSpellModifier> Mods = R.Modifiers;
        while (Mods.Num() <= Index) Mods.Add(ECraftedSpellModifier::None);
        ECraftedSpellModifier Value = Mods[Index];
        for (int32 Tries = 0; Tries < static_cast<int32>(ECraftedSpellModifier::MAX); ++Tries)
        {
            Value = Wrap(Value, Delta);
            bool bUsed = false;
            for (int32 i = 0; i < Mods.Num(); ++i) if (i != Index && Mods[i] == Value && Value != ECraftedSpellModifier::None) bUsed = true;
            if (!bUsed) break;
        }
        // Slot I can never be empty: every spell has at least one behaviour.
        if (Index == 0 && Value == ECraftedSpellModifier::None) Value = Wrap(Value, Delta >= 0 ? 1 : -1);
        Mods[Index] = Value;
        R.Modifiers.Reset();
        for (ECraftedSpellModifier M : Mods) if (M != ECraftedSpellModifier::None) R.Modifiers.Add(M);
    };
    switch (Row)
    {
    case ECraftingRow::Form: R.Form = Wrap(R.Form, Delta); break;
    case ECraftingRow::Element: R.Element = Wrap(R.Element, Delta); break;
    case ECraftingRow::Behaviour1: StepModifier(0); break;
    case ECraftingRow::Behaviour2: StepModifier(FMath::Min(1, R.Modifiers.Num())); break;
    case ECraftingRow::Behaviour3: StepModifier(FMath::Min(2, R.Modifiers.Num())); break;
    case ECraftingRow::Trigger: R.Trigger = Wrap(R.Trigger, Delta); break;
    case ECraftingRow::Power: R.Power = 1 + ((R.Power - 1 + Delta) % 5 + 5) % 5; break;
    case ECraftingRow::Look: R.LookVariant = FMath::Max(0, R.LookVariant + Delta); break;
    default: break;
    }
    R.CustomName.Reset();
    Crafting->SetSlotRecipe(EditSlot, R, false);
    if (UReflectionsCraftedSpellSubsystem* S = UReflectionsCraftedSpellSubsystem::Get(this)) S->PlayUiCue(TEXT("SCue_UI_Click"));
    Refresh();
}

void UReflectionsSpellCraftingScreen::SelectSlot(int32 NewSlot)
{
    EditSlot = (NewSlot % UReflectionsSpellCraftingComponent::NumSlots + UReflectionsSpellCraftingComponent::NumSlots) % UReflectionsSpellCraftingComponent::NumSlots;
    Refresh();
}

FString UReflectionsSpellCraftingScreen::RowValue(ECraftingRow Row, FString& OutHint) const
{
    const FCraftedSpellRecipe R = Crafting ? Crafting->GetSlotRecipe(EditSlot) : FCraftedSpellRecipe();
    using L = UReflectionsSpellCraftingLibrary;
    auto Mod = [&R, &OutHint](int32 Index)
    {
        const ECraftedSpellModifier M = R.Modifiers.IsValidIndex(Index) ? R.Modifiers[Index] : ECraftedSpellModifier::None;
        OutHint = L::ModifierHint(M);
        return L::ModifierLabel(M);
    };
    switch (Row)
    {
    case ECraftingRow::Form: OutHint = L::FormHint(R.Form); return L::FormLabel(R.Form);
    case ECraftingRow::Element: OutHint = L::ElementHint(R.Element); return L::ElementLabel(R.Element);
    case ECraftingRow::Behaviour1: return Mod(0);
    case ECraftingRow::Behaviour2: return Mod(1);
    case ECraftingRow::Behaviour3: return Mod(2);
    case ECraftingRow::Trigger: OutHint = L::TriggerHint(R.Trigger); return L::TriggerLabel(R.Trigger);
    case ECraftingRow::Power:
        OutHint = TEXT("More damage and size; mana cost grows faster.");
        return FString::Printf(TEXT("%s%s  (%d)"), *FString::ChrN(R.Power, TEXT('*')), *FString::ChrN(5 - R.Power, TEXT('.')), R.Power);
    case ECraftingRow::Look:
        OutHint = TEXT("Same spell, different colours, shape and motion.");
        return FString::Printf(TEXT("Variant %d"), R.LookVariant + 1);
    default: return FString();
    }
}

void UReflectionsSpellCraftingScreen::Refresh()
{
    if (!Crafting || !SpellName) return;
    for (int32 Row = 0; Row < NumRows && Row < RowValues.Num(); ++Row)
    {
        FString Hint;
        RowValues[Row]->SetText(FText::FromString(RowValue(static_cast<ECraftingRow>(Row), Hint)));
        RowHints[Row]->SetText(FText::FromString(Hint));
    }
    for (int32 i = 0; i < SlotLabels.Num(); ++i)
    {
        const bool bEquipped = Crafting->GetActiveSlot() == i;
        SlotLabels[i]->SetText(FText::FromString(FString::Printf(TEXT("%s%d%s"), i == EditSlot ? TEXT("[ ") : TEXT(""), i + 1,
            bEquipped ? (i == EditSlot ? TEXT(" * ]") : TEXT(" *")) : (i == EditSlot ? TEXT(" ]") : TEXT("")))));
    }
    const FCraftedSpellResolved& S = Crafting->GetSlotSpell(EditSlot);
    SpellName->SetText(FText::FromString(S.Name));
    SpellName->SetColorAndOpacity(FSlateColor(FLinearColor::LerpUsingHSV(S.Look.ColorA, FLinearColor::White, 0.25f)));
    if (Swatches.Num() == 3)
    {
        Swatches[0]->SetBrushColor(S.Look.ColorA);
        Swatches[1]->SetBrushColor(S.Look.ColorB);
        Swatches[2]->SetBrushColor(S.Look.ColorC * 2.0f);
    }
    const bool bMana = Crafting->IsUsingSpellCoreCast();
    FString Stats = FString::Printf(TEXT("Mana %d   Cooldown %.1f s   %s %d"), FMath::RoundToInt(S.ManaCost), S.Cooldown,
        S.Heal > 0.0f ? TEXT("Heal") : TEXT("Damage"), FMath::RoundToInt(S.Heal > 0.0f ? S.Heal : S.Damage));
    if (S.Radius > 0.0f) Stats += FString::Printf(TEXT("   Radius %d"), FMath::RoundToInt(S.Radius));
    if (!bMana) Stats += TEXT("\n(the spell core's mana hook is not connected yet: casting is free)");
    SpellStats->SetText(FText::FromString(Stats));
    SpellDescription->SetText(FText::FromString(S.Description));
    FString Synergies;
    for (const FString& Note : S.SynergyNotes) Synergies += TEXT("+ ") + Note + TEXT("\n");
    SpellSynergies->SetText(FText::FromString(Synergies.IsEmpty() ? TEXT("No synergy yet: some behaviours, elements and forms transform each other.") : Synergies.TrimEnd()));
    SpellSynergies->SetColorAndOpacity(FSlateColor(Synergies.IsEmpty() ? Dim : Gold));
}

void UReflectionsSpellCraftingScreen::RefreshIndicator()
{
    if (!IndicatorName || !Crafting) return;
    const int32 Active = Crafting->GetActiveSlot();
    FString Feedback = Crafting->GetFeedback();
    if (Active >= 0)
    {
        const FCraftedSpellResolved& S = Crafting->GetSlotSpell(Active);
        const float Cooldown = Crafting->GetCooldownRemaining(Active);
        IndicatorName->SetText(FText::FromString(FString::Printf(TEXT("[%d] %s   %d mana%s"), Active + 5, *S.Name, FMath::RoundToInt(S.ManaCost),
            Cooldown > 0.0f ? *FString::Printf(TEXT("   %.1f s"), Cooldown) : TEXT(""))));
        IndicatorName->SetColorAndOpacity(FSlateColor(FLinearColor::LerpUsingHSV(S.Look.ColorA, FLinearColor::White, 0.3f)));
    }
    else
    {
        IndicatorName->SetText(FText::GetEmpty());
    }
    IndicatorHint->SetText(FText::FromString(!Feedback.IsEmpty() && (Active < 0 || Feedback != Crafting->GetSlotSpell(Active).Name) ? Feedback
        : TEXT("K / View: craft spells    5-8 / D-pad Up: crafted slots")));
}

void UReflectionsSpellCraftingScreen::NativeTick(const FGeometry& Geometry, float DeltaSeconds)
{
    Super::NativeTick(Geometry, DeltaSeconds);
    if (!bOpen)
    {
        RefreshIndicator();
        return;
    }
    // Make keyboard/controller focus obvious: the focused button glows.
    auto Paint = [](UButton* Button)
    {
        if (Button) Button->SetBackgroundColor(Button->HasKeyboardFocus() ? ButtonFocus : ButtonIdle);
    };
    for (UButton* Button : RowButtons) Paint(Button);
    for (UButton* Button : SlotButtons) Paint(Button);
    Paint(ConjureButton);
    Paint(EquipButton);
    const UWorld* World = GetWorld();
    if (StatusLine && World) StatusLine->SetText(FText::FromString(World->GetTimeSeconds() < StatusUntil ? Status : FString()));
}

int32 UReflectionsSpellCraftingScreen::FocusedRow() const
{
    for (int32 i = 0; i < RowButtons.Num(); ++i) if (RowButtons[i] && RowButtons[i]->HasKeyboardFocus()) return i;
    return INDEX_NONE;
}

void UReflectionsSpellCraftingScreen::FocusRow(int32 Row)
{
    if (RowButtons.IsValidIndex(Row) && RowButtons[Row]) RowButtons[Row]->SetKeyboardFocus();
}

FReply UReflectionsSpellCraftingScreen::NativeOnPreviewKeyDown(const FGeometry& Geometry, const FKeyEvent& KeyEvent)
{
    if (!bOpen) return Super::NativeOnPreviewKeyDown(Geometry, KeyEvent);
    if (DescribeBox && DescribeBox->HasKeyboardFocus())
    {
        // Typing: only leave the text box with Escape or a controller.
        if (KeyEvent.GetKey() == EKeys::Escape || KeyEvent.GetKey() == EKeys::Gamepad_FaceButton_Right)
        {
            FocusRow(0);
            return FReply::Handled();
        }
        return FReply::Unhandled();
    }
    const FKey Key = KeyEvent.GetKey();
    const int32 Row = FocusedRow();
    if (Row != INDEX_NONE && (IsLeft(Key) || IsRight(Key)))
    {
        Step(static_cast<ECraftingRow>(Row), IsLeft(Key) ? -1 : 1);
        return FReply::Handled();
    }
    return Super::NativeOnPreviewKeyDown(Geometry, KeyEvent);
}

FReply UReflectionsSpellCraftingScreen::NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& KeyEvent)
{
    if (!bOpen) return Super::NativeOnKeyDown(Geometry, KeyEvent);
    const FKey Key = KeyEvent.GetKey();
    if (Key == EKeys::Escape || Key == EKeys::Gamepad_FaceButton_Right || Key == EKeys::K || Key == EKeys::Gamepad_Special_Left)
    {
        Close();
        return FReply::Handled();
    }
    if (Key == EKeys::Gamepad_LeftShoulder || Key == EKeys::Q || Key == EKeys::PageUp) { SelectSlot(EditSlot - 1); return FReply::Handled(); }
    if (Key == EKeys::Gamepad_RightShoulder || Key == EKeys::E || Key == EKeys::PageDown) { SelectSlot(EditSlot + 1); return FReply::Handled(); }
    if (Key == EKeys::Gamepad_FaceButton_Left || Key == EKeys::R) { OnReroll(); return FReply::Handled(); }
    if (Key == EKeys::Gamepad_FaceButton_Top || Key == EKeys::F) { OnEquip(); return FReply::Handled(); }
    if (Key == EKeys::Gamepad_LeftTrigger || Key == EKeys::Gamepad_RightTrigger) { if (DescribeBox) DescribeBox->SetKeyboardFocus(); return FReply::Handled(); }
    return Super::NativeOnKeyDown(Geometry, KeyEvent);
}

void UReflectionsSpellCraftingScreen::OnRow0() { Step(ECraftingRow::Form, 1); FocusRow(0); }
void UReflectionsSpellCraftingScreen::OnRow1() { Step(ECraftingRow::Element, 1); FocusRow(1); }
void UReflectionsSpellCraftingScreen::OnRow2() { Step(ECraftingRow::Behaviour1, 1); FocusRow(2); }
void UReflectionsSpellCraftingScreen::OnRow3() { Step(ECraftingRow::Behaviour2, 1); FocusRow(3); }
void UReflectionsSpellCraftingScreen::OnRow4() { Step(ECraftingRow::Behaviour3, 1); FocusRow(4); }
void UReflectionsSpellCraftingScreen::OnRow5() { Step(ECraftingRow::Trigger, 1); FocusRow(5); }
void UReflectionsSpellCraftingScreen::OnRow6() { Step(ECraftingRow::Power, 1); FocusRow(6); }
void UReflectionsSpellCraftingScreen::OnRow7() { Step(ECraftingRow::Look, 1); FocusRow(7); }
void UReflectionsSpellCraftingScreen::OnLess0() { Step(ECraftingRow::Form, -1); }
void UReflectionsSpellCraftingScreen::OnLess1() { Step(ECraftingRow::Element, -1); }
void UReflectionsSpellCraftingScreen::OnLess2() { Step(ECraftingRow::Behaviour1, -1); }
void UReflectionsSpellCraftingScreen::OnLess3() { Step(ECraftingRow::Behaviour2, -1); }
void UReflectionsSpellCraftingScreen::OnLess4() { Step(ECraftingRow::Behaviour3, -1); }
void UReflectionsSpellCraftingScreen::OnLess5() { Step(ECraftingRow::Trigger, -1); }
void UReflectionsSpellCraftingScreen::OnLess6() { Step(ECraftingRow::Power, -1); }
void UReflectionsSpellCraftingScreen::OnLess7() { Step(ECraftingRow::Look, -1); }
void UReflectionsSpellCraftingScreen::OnSlot0() { SelectSlot(0); }
void UReflectionsSpellCraftingScreen::OnSlot1() { SelectSlot(1); }
void UReflectionsSpellCraftingScreen::OnSlot2() { SelectSlot(2); }
void UReflectionsSpellCraftingScreen::OnSlot3() { SelectSlot(3); }

void UReflectionsSpellCraftingScreen::OnEquip()
{
    if (!Crafting) return;
    Crafting->SelectCraftedSlot(EditSlot);
    if (UReflectionsCraftedSpellSubsystem* S = UReflectionsCraftedSpellSubsystem::Get(this)) S->PlayUiCue(TEXT("SCue_UI_Confirm"));
    Close();
}

void UReflectionsSpellCraftingScreen::OnReset()
{
    if (!Crafting) return;
    Crafting->SetSlotRecipe(EditSlot, UReflectionsSpellCraftingLibrary::Preset(EditSlot), false);
    Refresh();
}

void UReflectionsSpellCraftingScreen::OnClose()
{
    Close();
}

void UReflectionsSpellCraftingScreen::OnReroll()
{
    Step(ECraftingRow::Look, 1);
}

void UReflectionsSpellCraftingScreen::OnConjureCommitted(const FText& Text, ETextCommit::Type Method)
{
    if (Method == ETextCommit::OnEnter) OnConjure();
}

void UReflectionsSpellCraftingScreen::OnConjure()
{
    if (!Crafting || !DescribeBox) return;
    const FString Text = DescribeBox->GetText().ToString().TrimStartAndEnd();
    if (Text.IsEmpty())
    {
        DescribeBox->SetKeyboardFocus();
        return;
    }
    Status = UReflectionsSpellRecipeRelay::IsConfigured() ? TEXT("Asking the dev relay...") : TEXT("Interpreting...");
    StatusUntil = GetWorld() ? GetWorld()->GetTimeSeconds() + 10.0 : 0.0;
    const int32 TargetSlot = EditSlot;
    TWeakObjectPtr<UReflectionsSpellCraftingScreen> WeakThis(this);
    Crafting->DescribeSpell(Text, [WeakThis, TargetSlot](bool bOk, const FCraftedSpellRecipe& Recipe, const FString& Source)
    {
        UReflectionsSpellCraftingScreen* Self = WeakThis.Get();
        if (!Self || !Self->Crafting) return;
        if (bOk) Self->Crafting->SetSlotRecipe(TargetSlot, Recipe, false);
        Self->Status = Source;
        Self->StatusUntil = Self->GetWorld() ? Self->GetWorld()->GetTimeSeconds() + 4.0 : 0.0;
        Self->Refresh();
    });
}
