#include "Hero/ReflectionsSpellHud.h"
#include "Hero/ReflectionsSampleSpellDriver.h"
#include "Hero/ReflectionsSpellAim.h"
#include "Components/Image.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Button.h"
#include "Components/ButtonSlot.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/InputComponent.h"
#include "Components/ProgressBar.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"

void UReflectionsSpellHudWidget::SetDriver(UReflectionsSampleSpellDriver* InDriver)
{
    Driver = InDriver;
    RefreshSelection();
}

void UReflectionsSpellHudWidget::NativeOnInitialized()
{
    Super::NativeOnInitialized();
    if (!WidgetTree || WidgetTree->RootWidget) return;
    UCanvasPanel* Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
    WidgetTree->RootWidget = Root;
    Root->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
    UTextBlock* Reticle = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    Reticle->SetText(FText::FromString(TEXT("+")));
    Reticle->SetColorAndOpacity(FSlateColor(FLinearColor(1.0f, 1.0f, 1.0f, 0.8f)));
    FSlateFontInfo ReticleFont = Reticle->GetFont(); ReticleFont.Size = 20; Reticle->SetFont(ReticleFont);
    UCanvasPanelSlot* ReticleSlot = Root->AddChildToCanvas(Reticle);
    ReticleSlot->SetAnchors(FAnchors(0.5f, 0.5f));
    ReticleSlot->SetAlignment(FVector2D(0.5f, 0.5f));
    ReticleSlot->SetAutoSize(true);
    UVerticalBox* Panel = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    UCanvasPanelSlot* PanelSlot = Root->AddChildToCanvas(Panel);
    PanelSlot->SetAnchors(FAnchors(0.5f, 1.0f));
    PanelSlot->SetAlignment(FVector2D(0.5f, 1.0f));
    PanelSlot->SetPosition(FVector2D(0, -28));
    PanelSlot->SetAutoSize(true);

    UHorizontalBox* Vitals = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
    UVerticalBoxSlot* VitalsSlot = Panel->AddChildToVerticalBox(Vitals);
    VitalsSlot->SetHorizontalAlignment(HAlign_Center);
    VitalsSlot->SetPadding(FMargin(0, 0, 0, 6));
    auto AddVital = [this, Vitals](UTextBlock*& Label, UProgressBar*& Bar, const FLinearColor& Color)
    {
        UVerticalBox* Column = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        UHorizontalBoxSlot* Slot = Vitals->AddChildToHorizontalBox(Column);
        Slot->SetPadding(FMargin(8, 0));
        Label = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
        FSlateFontInfo Font = Label->GetFont(); Font.Size = 12; Label->SetFont(Font);
        Label->SetColorAndOpacity(FSlateColor(FLinearColor::White));
        Column->AddChildToVerticalBox(Label);
        USizeBox* Box = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
        Box->SetWidthOverride(190.0f); Box->SetHeightOverride(10.0f);
        Bar = WidgetTree->ConstructWidget<UProgressBar>(UProgressBar::StaticClass());
        Bar->SetFillColorAndOpacity(Color);
        Box->AddChild(Bar); Column->AddChildToVerticalBox(Box);
    };
    UTextBlock* HealthText = nullptr;
    UProgressBar* HealthProgress = nullptr;
    AddVital(HealthText, HealthProgress, FLinearColor(0.75f, 0.08f, 0.08f));
    HealthLabel = HealthText; HealthBar = HealthProgress;
    UTextBlock* ManaText = nullptr;
    UProgressBar* ManaProgress = nullptr;
    AddVital(ManaText, ManaProgress, FLinearColor(0.08f, 0.40f, 0.95f));
    ManaLabel = ManaText; ManaBar = ManaProgress;

    TargetPanel = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    UVerticalBoxSlot* TargetSlot = Panel->AddChildToVerticalBox(TargetPanel);
    TargetSlot->SetHorizontalAlignment(HAlign_Center);
    TargetSlot->SetPadding(FMargin(0, 0, 0, 6));
    TargetLabel = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    FSlateFontInfo TargetFont = TargetLabel->GetFont(); TargetFont.Size = 12; TargetLabel->SetFont(TargetFont);
    TargetPanel->AddChildToVerticalBox(TargetLabel);
    USizeBox* TargetBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    TargetBox->SetWidthOverride(220.0f); TargetBox->SetHeightOverride(10.0f);
    TargetHealthBar = WidgetTree->ConstructWidget<UProgressBar>(UProgressBar::StaticClass());
    TargetHealthBar->SetFillColorAndOpacity(FLinearColor(0.8f, 0.12f, 0.08f));
    TargetBox->AddChild(TargetHealthBar); TargetPanel->AddChildToVerticalBox(TargetBox);
    TargetPanel->SetVisibility(ESlateVisibility::Collapsed);

    FeedbackLabel = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    FeedbackLabel->SetColorAndOpacity(FSlateColor(FLinearColor(1.0f, 0.55f, 0.35f)));
    FeedbackLabel->SetJustification(ETextJustify::Center);
    FSlateFontInfo FeedbackFont = FeedbackLabel->GetFont(); FeedbackFont.Size = 14; FeedbackLabel->SetFont(FeedbackFont);
    UVerticalBoxSlot* FeedbackSlot = Panel->AddChildToVerticalBox(FeedbackLabel);
    FeedbackSlot->SetHorizontalAlignment(HAlign_Center);

    Hint = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    Hint->SetColorAndOpacity(FSlateColor(FLinearColor(0.94f, 0.85f, 0.68f)));
    FSlateFontInfo HintFont = Hint->GetFont(); HintFont.Size = 11; Hint->SetFont(HintFont);
    UVerticalBoxSlot* HintSlot = Panel->AddChildToVerticalBox(Hint);
    HintSlot->SetHorizontalAlignment(HAlign_Center); HintSlot->SetPadding(FMargin(0, 0, 0, 6));

    UHorizontalBox* Row = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
    Panel->AddChildToVerticalBox(Row);
    for (int32 Index = 0; Index < ReflectionsSpellCatalog::PlayerSpellCount; ++Index)
    {
        UButton* Button = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass());
        UTextBlock* Label = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
        Label->SetJustification(ETextJustify::Center);
        FSlateFontInfo Font = Label->GetFont(); Font.Size = 14; Label->SetFont(Font);
        if (UButtonSlot* Content = Cast<UButtonSlot>(Button->AddChild(Label))) Content->SetPadding(FMargin(14, 9));
        UHorizontalBoxSlot* ButtonSlot = Row->AddChildToHorizontalBox(Button);
        ButtonSlot->SetPadding(FMargin(3, 0));
        SpellButtons.Add(Button); SpellLabels.Add(Label);
    }
    SpellButtons[0]->OnClicked.AddDynamic(this, &UReflectionsSpellHudWidget::SelectFirstSlot);
    SpellButtons[1]->OnClicked.AddDynamic(this, &UReflectionsSpellHudWidget::SelectSecondSlot);
    SpellButtons[2]->OnClicked.AddDynamic(this, &UReflectionsSpellHudWidget::SelectThirdSlot);
    SpellButtons[3]->OnClicked.AddDynamic(this, &UReflectionsSpellHudWidget::SelectFourthSlot);
    BuildReticle(Root);
    RefreshSelection();
}

void UReflectionsSpellHudWidget::BuildReticle(UCanvasPanel* Root)
{
    auto MakeImage = [this, Root](FVector2D Size) -> UImage*
    {
        UImage* Image = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
        Image->SetVisibility(ESlateVisibility::HitTestInvisible);
        UCanvasPanelSlot* ImageSlot = Root->AddChildToCanvas(Image);
        ImageSlot->SetAnchors(FAnchors(0.5f, 0.5f));
        ImageSlot->SetAlignment(FVector2D(0.5f, 0.5f));
        ImageSlot->SetSize(Size);
        return Image;
    };
    ReticleDot = MakeImage(FVector2D(4.0f, 4.0f));
    for (int32 Index = 0; Index < 4; ++Index)
    {
        ReticleTicks.Add(MakeImage(Index < 2 ? FVector2D(2.0f, 10.0f) : FVector2D(10.0f, 2.0f)));
        UImage* Hit = MakeImage(FVector2D(2.0f, 11.0f));
        Hit->SetRenderTransformAngle(Index % 2 == 0 ? 45.0f : -45.0f);
        HitTicks.Add(Hit);
    }
    SpellLabel = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    SpellLabel->SetVisibility(ESlateVisibility::HitTestInvisible);
    SpellLabel->SetJustification(ETextJustify::Center);
    FSlateFontInfo Font = SpellLabel->GetFont(); Font.Size = 10; SpellLabel->SetFont(Font);
    UCanvasPanelSlot* LabelSlot = Root->AddChildToCanvas(SpellLabel);
    LabelSlot->SetAnchors(FAnchors(0.5f, 0.5f));
    LabelSlot->SetAlignment(FVector2D(0.5f, 0.0f));
    LabelSlot->SetAutoSize(true);
    LabelSlot->SetPosition(FVector2D(0.0f, 34.0f));
}

void UReflectionsSpellHudWidget::UpdateReticle()
{
    const UReflectionsSpellAimComponent* Aim = Driver ? Driver->GetAim() : nullptr;
    if (!Aim || !ReticleDot) return;
    const float Alpha = Driver->IsDefeated() ? 0.0f : Aim->GetAimAlpha();
    const bool bLocked = Aim->HasAssistTarget();
    const FLinearColor Element = Aim->GetElementColor();
    FLinearColor Tint = FMath::Lerp(FLinearColor(0.95f, 0.95f, 0.95f), FMath::Lerp(Element, FLinearColor::White, 0.35f), Alpha);
    if (bLocked) Tint = FMath::Lerp(Tint, FLinearColor(1.0f, 0.3f, 0.2f), 0.75f);
    Tint.A = Driver->IsDefeated() ? 0.0f : 0.45f + 0.55f * Alpha;

    // Ticks open on each cast and close while aiming.
    const float Spread = 7.0f + 9.0f * (1.0f - Alpha) + 16.0f * Aim->GetCastSpread() - (bLocked ? 2.0f : 0.0f);
    const FVector2D Offsets[4] = {{0.0f, -1.0f}, {0.0f, 1.0f}, {-1.0f, 0.0f}, {1.0f, 0.0f}};
    for (int32 Index = 0; Index < ReticleTicks.Num(); ++Index)
    {
        if (UCanvasPanelSlot* TickSlot = Cast<UCanvasPanelSlot>(ReticleTicks[Index]->Slot))
        {
            TickSlot->SetPosition(Offsets[Index] * (Spread + 5.0f));
        }
        ReticleTicks[Index]->SetColorAndOpacity(Tint);
    }
    ReticleDot->SetColorAndOpacity(Tint);

    const float Marker = Aim->GetHitMarker();
    const FLinearColor MarkerColor = Aim->WasKillMarker() ? FLinearColor(1.0f, 0.2f, 0.15f, Marker) : FLinearColor(1.0f, 1.0f, 1.0f, Marker);
    const FVector2D Diagonals[4] = {{1.0f, -1.0f}, {1.0f, 1.0f}, {-1.0f, 1.0f}, {-1.0f, -1.0f}};
    for (int32 Index = 0; Index < HitTicks.Num(); ++Index)
    {
        if (UCanvasPanelSlot* HitSlot = Cast<UCanvasPanelSlot>(HitTicks[Index]->Slot))
        {
            HitSlot->SetPosition(Diagonals[Index] * (9.0f + 5.0f * (1.0f - Marker)));
        }
        HitTicks[Index]->SetColorAndOpacity(MarkerColor);
    }

    if (SpellLabel)
    {
        SpellLabel->SetText(FText::FromString(FString(ReflectionsSpellCatalog::Get(Driver->GetSelectedSpell()).Name).ToUpper()));
        FLinearColor LabelColor = FMath::Lerp(Element, FLinearColor::White, 0.45f);
        LabelColor.A = Alpha;
        SpellLabel->SetColorAndOpacity(FSlateColor(LabelColor));
    }
}

void UReflectionsSpellHudWidget::NativeTick(const FGeometry& Geometry, float DeltaSeconds)
{
    Super::NativeTick(Geometry, DeltaSeconds);
    RefreshSelection();
    UpdateReticle();
}

void UReflectionsSpellHudWidget::RefreshSelection()
{
    if (!Driver) return;
    const UReflectionsHealthComponent* Health = Driver->GetOwner() ? Driver->GetOwner()->FindComponentByClass<UReflectionsHealthComponent>() : nullptr;
    if (Health && HealthLabel && HealthBar)
    {
        const FString Shield = Health->Shield > 0.0f ? FString::Printf(TEXT("  +%.0f shield"), Health->Shield) : FString();
        HealthLabel->SetText(FText::FromString(FString::Printf(TEXT("HEALTH %.0f / %.0f%s"), Health->Health, Health->MaxHealth, *Shield)));
        HealthBar->SetPercent(Health->MaxHealth > 0.0f ? FMath::Clamp(Health->Health / Health->MaxHealth, 0.0f, 1.0f) : 0.0f);
    }
    if (ManaLabel && ManaBar)
    {
        ManaLabel->SetText(FText::FromString(FString::Printf(TEXT("MANA %.0f / %.0f"), Driver->GetMana(), Driver->MaxMana)));
        ManaBar->SetPercent(FMath::Clamp(Driver->GetMana() / FMath::Max(1.0f, Driver->MaxMana), 0.0f, 1.0f));
    }
    if (TargetPanel && TargetLabel && TargetHealthBar)
    {
        const APawn* Pawn = Cast<APawn>(Driver->GetOwner());
        const APlayerController* Controller = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
        const UReflectionsHealthComponent* TargetHealth = nullptr;
        if (Controller && GetWorld() && !Driver->IsDefeated())
        {
            FVector ViewLocation; FRotator ViewRotation;
            Controller->GetPlayerViewPoint(ViewLocation, ViewRotation);
            FCollisionQueryParams Query(SCENE_QUERY_STAT(CombatTarget), false, Pawn);
            TArray<AActor*> Attached;
            Pawn->GetAttachedActors(Attached, true, true);
            Query.AddIgnoredActors(Attached);
            FHitResult Hit;
            if (GetWorld()->LineTraceSingleByChannel(Hit, ViewLocation, ViewLocation + ViewRotation.Vector() * 3500.0f, ECC_Visibility, Query))
                if (const AActor* Actor = Hit.GetActor())
                {
                    // NPC rebuild: removed the NPC hit-proxy resolve and hostility check; any actor with health shows
                    TargetHealth = Actor->FindComponentByClass<UReflectionsHealthComponent>();
                }
        }
        if (TargetHealth && TargetHealth->Health > 0.0f)
        {
            TargetPanel->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
            TargetLabel->SetText(FText::FromString(FString::Printf(TEXT("OPPONENT  %.0f / %.0f"), TargetHealth->Health, TargetHealth->MaxHealth)));
            TargetHealthBar->SetPercent(FMath::Clamp(TargetHealth->Health / FMath::Max(1.0f, TargetHealth->MaxHealth), 0.0f, 1.0f));
        }
        else TargetPanel->SetVisibility(ESlateVisibility::Collapsed);
    }
    if (FeedbackLabel)
    {
        const FString Feedback = Driver->IsDefeated()
            ? FString::Printf(TEXT("Defeated - respawning in %.1f"), Driver->GetRespawnTimeRemaining())
            : Driver->GetCastFeedback();
        FeedbackLabel->SetText(FText::FromString(Feedback));
    }
    if (Hint) Hint->SetText(FText::FromString(Driver->IsUsingGamepad()
        ? TEXT("HOLD LT AIM  |  RT CAST  |  LB / RB SELECT SPELL")
        : TEXT("HOLD RMB AIM  |  LMB / Q CAST  |  1-4 SELECT  |  HOLD RIGHT ALT FOR MOUSE")));
    for (int32 Index = 0; Index < SpellButtons.Num(); ++Index)
    {
        const EHeroSpell Spell = ReflectionsSpellCatalog::PlayerSpells[Index];
        const bool bSelected = Spell == Driver->GetSelectedSpell();
        const float Cooldown = Driver->GetSpellCooldownRemaining(Spell);
        const FString Status = Cooldown > 0.0f ? FString::Printf(TEXT("%.1fs"), Cooldown) : FString::Printf(TEXT("%.0f mana"), Driver->GetSpellManaCost(Spell));
        SpellLabels[Index]->SetText(FText::FromString(FString::Printf(TEXT("%d  %s\n%s"), Index + 1, *Driver->GetSpellSlotName(Index), *Status)));
        SpellButtons[Index]->SetBackgroundColor(bSelected ? FLinearColor(0.65f, 0.36f, 0.08f, 0.98f) : FLinearColor(0.035f, 0.045f, 0.07f, 0.88f));
        SpellLabels[Index]->SetColorAndOpacity(FSlateColor(bSelected ? FLinearColor(1.f, 0.92f, 0.73f) : FLinearColor(0.76f, 0.79f, 0.84f)));
    }
}
void UReflectionsSpellHudWidget::SelectFirstSlot() { if (Driver) Driver->SelectSpellSlot(0); }
void UReflectionsSpellHudWidget::SelectSecondSlot() { if (Driver) Driver->SelectSpellSlot(1); }
void UReflectionsSpellHudWidget::SelectThirdSlot() { if (Driver) Driver->SelectSpellSlot(2); }
void UReflectionsSpellHudWidget::SelectFourthSlot() { if (Driver) Driver->SelectSpellSlot(3); }

UReflectionsSpellHudComponent::UReflectionsSpellHudComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
}
void UReflectionsSpellHudComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaTime, TickType, TickFunction);
    if (Hud) return;
    APawn* Pawn = Cast<APawn>(GetOwner());
    APlayerController* PC = Pawn && Pawn->IsLocallyControlled() ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
    UReflectionsSampleSpellDriver* Driver = Pawn ? Pawn->FindComponentByClass<UReflectionsSampleSpellDriver>() : nullptr;
    if (!PC || !Driver) return;
    LocalPlayerController = PC;
    Hud = CreateWidget<UReflectionsSpellHudWidget>(PC, UReflectionsSpellHudWidget::StaticClass());
    if (!Hud) return;
    Hud->SetDriver(Driver);
    Hud->AddToViewport(10);
    MouseInput = NewObject<UInputComponent>(PC, TEXT("SpellHudMouseInput"));
    MouseInput->RegisterComponent();
    MouseInput->BindKey(EKeys::RightAlt, IE_Pressed, this, &UReflectionsSpellHudComponent::EnableMouse);
    MouseInput->BindKey(EKeys::RightAlt, IE_Released, this, &UReflectionsSpellHudComponent::DisableMouse);
    PC->PushInputComponent(MouseInput);
}
void UReflectionsSpellHudComponent::EnableMouse()
{
    if (!LocalPlayerController || bMouseEnabledByHud) return;
    bMouseEnabledByHud = true;
    FInputModeGameAndUI Mode;
    Mode.SetHideCursorDuringCapture(false);
    Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
    LocalPlayerController->SetInputMode(Mode);
    LocalPlayerController->SetShowMouseCursor(true);
}
void UReflectionsSpellHudComponent::DisableMouse()
{
    if (!LocalPlayerController || !bMouseEnabledByHud) return;
    bMouseEnabledByHud = false;
    LocalPlayerController->SetShowMouseCursor(false);
    LocalPlayerController->SetInputMode(FInputModeGameOnly());
}
void UReflectionsSpellHudComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    DisableMouse();
    if (LocalPlayerController && MouseInput) LocalPlayerController->PopInputComponent(MouseInput);
    if (Hud) Hud->RemoveFromParent();
    Super::EndPlay(EndPlayReason);
}



