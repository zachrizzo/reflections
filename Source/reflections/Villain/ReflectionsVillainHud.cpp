#include "Villain/ReflectionsVillainHud.h"

#include "Villain/ReflectionsVillainFx.h"

#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/ProgressBar.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"

namespace
{
    constexpr float MessageHold = 3.2f;
    constexpr float MessageFade = 0.8f;
    constexpr float BannerHold = 2.8f;
    constexpr float BannerFade = 1.0f;

    FLinearColor WithAlpha(const FLinearColor& Color, float Alpha)
    {
        return FLinearColor(Color.R, Color.G, Color.B, Alpha);
    }
}

UTextBlock* UReflectionsVillainHudWidget::MakeText(int32 Size, const FLinearColor& Color, bool bBold)
{
    UTextBlock* Text = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    FSlateFontInfo Font = Text->GetFont();
    Font.Size = Size;
    if (bBold)
    {
        Font.TypefaceFontName = TEXT("Bold");
    }
    Text->SetFont(Font);
    Text->SetColorAndOpacity(FSlateColor(Color));
    Text->SetShadowOffset(FVector2D(1.5f, 1.5f));
    Text->SetShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.85f));
    Text->SetJustification(ETextJustify::Center);
    return Text;
}

void UReflectionsVillainHudWidget::NativeOnInitialized()
{
    Super::NativeOnInitialized();
    if (!WidgetTree || WidgetTree->RootWidget)
    {
        return;
    }
    UCanvasPanel* Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
    WidgetTree->RootWidget = Root;
    Root->SetVisibility(ESlateVisibility::HitTestInvisible);

    // ---- Boss bar, top centre.
    BossBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    UCanvasPanelSlot* BossSlot = Root->AddChildToCanvas(BossBox);
    BossSlot->SetAnchors(FAnchors(0.5f, 0.0f));
    BossSlot->SetAlignment(FVector2D(0.5f, 0.0f));
    BossSlot->SetPosition(FVector2D(0.0f, 26.0f));
    BossSlot->SetAutoSize(true);
    BossName = MakeText(22, ReflectionsVillainColors::Lilac, true);
    BossBox->AddChildToVerticalBox(BossName)->SetHorizontalAlignment(HAlign_Center);
    USizeBox* BarSize = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    BarSize->SetWidthOverride(620.0f);
    BarSize->SetHeightOverride(14.0f);
    BossBar = WidgetTree->ConstructWidget<UProgressBar>(UProgressBar::StaticClass());
    BossBar->SetFillColorAndOpacity(FLinearColor(0.55f, 0.12f, 0.95f, 1.0f));
    BossBar->SetPercent(1.0f);
    BarSize->AddChild(BossBar);
    UVerticalBoxSlot* BarSlot = BossBox->AddChildToVerticalBox(BarSize);
    BarSlot->SetHorizontalAlignment(HAlign_Center);
    BarSlot->SetPadding(FMargin(0.0f, 4.0f, 0.0f, 0.0f));
    BossBox->SetVisibility(ESlateVisibility::Collapsed);

    // ---- Message line under the bar.
    MessageLabel = MakeText(18, FLinearColor::White);
    UCanvasPanelSlot* MessageSlot = Root->AddChildToCanvas(MessageLabel);
    MessageSlot->SetAnchors(FAnchors(0.5f, 0.0f));
    MessageSlot->SetAlignment(FVector2D(0.5f, 0.0f));
    MessageSlot->SetPosition(FVector2D(0.0f, 92.0f));
    MessageSlot->SetAutoSize(true);
    MessageLabel->SetVisibility(ESlateVisibility::Collapsed);

    // ---- Big banner.
    Banner = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    UCanvasPanelSlot* BannerSlot = Root->AddChildToCanvas(Banner);
    BannerSlot->SetAnchors(FAnchors(0.5f, 0.3f));
    BannerSlot->SetAlignment(FVector2D(0.5f, 0.5f));
    BannerSlot->SetAutoSize(true);
    BannerTitle = MakeText(46, FLinearColor::White, true);
    Banner->AddChildToVerticalBox(BannerTitle)->SetHorizontalAlignment(HAlign_Center);
    BannerSubtitle = MakeText(19, FLinearColor::White);
    Banner->AddChildToVerticalBox(BannerSubtitle)->SetHorizontalAlignment(HAlign_Center);
    Banner->SetVisibility(ESlateVisibility::Collapsed);

    // ---- Final Spell prompt, bottom centre above the spell bar.
    FinalBox = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
    FinalBox->SetBrushColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.5f));
    FinalBox->SetPadding(FMargin(16.0f, 6.0f));
    UCanvasPanelSlot* FinalSlot = Root->AddChildToCanvas(FinalBox);
    FinalSlot->SetAnchors(FAnchors(0.5f, 1.0f));
    FinalSlot->SetAlignment(FVector2D(0.5f, 1.0f));
    FinalSlot->SetPosition(FVector2D(0.0f, -200.0f));
    FinalSlot->SetAutoSize(true);
    FinalLabel = MakeText(18, ReflectionsVillainColors::FinalGold, true);
    FinalBox->SetContent(FinalLabel);
    FinalBox->SetVisibility(ESlateVisibility::Collapsed);
}

void UReflectionsVillainHudWidget::SetBoss(const FText& Name, float Fraction, bool bVisible)
{
    if (!BossBox)
    {
        return;
    }
    BossBox->SetVisibility(bVisible ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    BossName->SetText(Name);
    TargetFraction = FMath::Clamp(Fraction, 0.0f, 1.0f);
    if (!bVisible)
    {
        ShownFraction = TargetFraction;
    }
}

void UReflectionsVillainHudWidget::ShowMessage(const FText& Text, const FLinearColor& Color)
{
    if (!MessageLabel)
    {
        return;
    }
    MessageLabel->SetText(Text);
    MessageColor = Color;
    MessageTime = MessageHold + MessageFade;
    MessageLabel->SetColorAndOpacity(FSlateColor(Color));
    MessageLabel->SetVisibility(ESlateVisibility::HitTestInvisible);
}

void UReflectionsVillainHudWidget::ShowBanner(const FText& Title, const FText& Subtitle, const FLinearColor& Color)
{
    if (!Banner)
    {
        return;
    }
    BannerTitle->SetText(Title);
    BannerSubtitle->SetText(Subtitle);
    BannerColor = Color;
    BannerTime = BannerHold + BannerFade;
    Banner->SetVisibility(ESlateVisibility::HitTestInvisible);
}

void UReflectionsVillainHudWidget::SetFinalSpell(bool bVisible, const FText& Text, bool bReady)
{
    if (!FinalBox)
    {
        return;
    }
    FinalBox->SetVisibility(bVisible ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    FinalLabel->SetText(Text);
    bFinalReady = bReady;
}

void UReflectionsVillainHudWidget::NativeTick(const FGeometry& Geometry, float DeltaTime)
{
    Super::NativeTick(Geometry, DeltaTime);
    if (BossBar)
    {
        ShownFraction = FMath::FInterpTo(ShownFraction, TargetFraction, DeltaTime, 5.0f);
        BossBar->SetPercent(ShownFraction);
    }
    if (MessageTime > 0.0f)
    {
        MessageTime -= DeltaTime;
        const float Alpha = FMath::Clamp(MessageTime / MessageFade, 0.0f, 1.0f);
        MessageLabel->SetColorAndOpacity(FSlateColor(WithAlpha(MessageColor, Alpha)));
        if (MessageTime <= 0.0f)
        {
            MessageLabel->SetVisibility(ESlateVisibility::Collapsed);
        }
    }
    if (BannerTime > 0.0f)
    {
        BannerTime -= DeltaTime;
        const float Alpha = FMath::Clamp(BannerTime / BannerFade, 0.0f, 1.0f);
        BannerTitle->SetColorAndOpacity(FSlateColor(WithAlpha(BannerColor, Alpha)));
        BannerSubtitle->SetColorAndOpacity(FSlateColor(WithAlpha(FLinearColor(0.92f, 0.9f, 0.95f), Alpha)));
        if (BannerTime <= 0.0f)
        {
            Banner->SetVisibility(ESlateVisibility::Collapsed);
        }
    }
    if (FinalLabel)
    {
        FinalPulse += DeltaTime;
        const float Glow = bFinalReady ? 0.8f + 0.2f * FMath::Sin(FinalPulse * 4.0f) : 0.45f;
        FinalLabel->SetColorAndOpacity(FSlateColor(WithAlpha(ReflectionsVillainColors::FinalGold, Glow)));
    }
}
