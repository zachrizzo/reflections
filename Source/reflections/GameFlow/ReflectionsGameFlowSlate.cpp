#include "GameFlow/ReflectionsGameFlowSlate.h"

#include "Brushes/SlateColorBrush.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFlow/ReflectionsGameFlowSubsystem.h"
#include "GameFlow/ReflectionsGameFlowSettings.h"
#include "GameFlow/ReflectionsGameFlowText.h"
#include "GameFlow/ReflectionsGameFlowWorldSubsystem.h"
#include "HAL/PlatformTime.h"
#include "Rendering/DrawElements.h"
#include "Styling/CoreStyle.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBackgroundBlur.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Voice/ReflectionsNpcRelayHost.h"

#define LOCTEXT_NAMESPACE "ReflectionsGameFlow"

/** Text from the one String Table (/Game/UI/ST_GameFlowText), with the built-in default. */
#define FLOWTEXT(Key, Default) ReflectionsFlowText::Get(TEXT(Key), LOCTEXT(Key, Default))

namespace ReflectionsFlowStyle
{
    // Palette: parchment text on ink, one accent per side.
    static const FLinearColor Ink(0.012f, 0.012f, 0.018f, 1.0f);
    static const FLinearColor Paper(0.93f, 0.89f, 0.80f, 1.0f);
    static const FLinearColor PaperDim(0.62f, 0.59f, 0.53f, 1.0f);
    static const FLinearColor Gray(0.55f, 0.58f, 0.62f, 1.0f);
    static const FLinearColor Red(0.78f, 0.10f, 0.08f, 1.0f);
    static const FLinearColor White(0.95f, 0.95f, 0.98f, 1.0f);
    static const FLinearColor Gold(0.95f, 0.72f, 0.28f, 1.0f);
    static const FLinearColor Plague(0.42f, 0.78f, 0.22f, 1.0f);
    static const FLinearColor Danger(0.92f, 0.16f, 0.10f, 1.0f);

    static const FSlateBrush* Solid()
    {
        static const FSlateColorBrush Brush(FLinearColor::White);
        return &Brush;
    }

    static const FSlateBrush* Rounded(float Radius)
    {
        static TMap<int32, TSharedPtr<FSlateRoundedBoxBrush>> Cache;
        const int32 Key = FMath::RoundToInt(Radius);
        TSharedPtr<FSlateRoundedBoxBrush>& Entry = Cache.FindOrAdd(Key);
        if (!Entry.IsValid())
        {
            Entry = MakeShared<FSlateRoundedBoxBrush>(FLinearColor::White, Radius);
        }
        return Entry.Get();
    }

    static const FSlateBrush* Outline(float Radius)
    {
        static TMap<int32, TSharedPtr<FSlateRoundedBoxBrush>> Cache;
        const int32 Key = FMath::RoundToInt(Radius);
        TSharedPtr<FSlateRoundedBoxBrush>& Entry = Cache.FindOrAdd(Key);
        if (!Entry.IsValid())
        {
            Entry = MakeShared<FSlateRoundedBoxBrush>(FLinearColor::Transparent, Radius, FLinearColor::White, 1.5f);
        }
        return Entry.Get();
    }

    static FSlateFontInfo Font(const TCHAR* Weight, int32 Size, int32 LetterSpacing = 0)
    {
        FSlateFontInfo Info = FCoreStyle::GetDefaultFontStyle(Weight, Size);
        Info.LetterSpacing = LetterSpacing;
        return Info;
    }

    static const FButtonStyle& ButtonStyle()
    {
        static FButtonStyle Style = []
        {
            FButtonStyle S;
            const FSlateBrush* Brush = Rounded(6.0f);
            S.SetNormal(*Brush);
            S.SetHovered(*Brush);
            S.SetPressed(*Brush);
            S.SetDisabled(*Brush);
            S.SetNormalPadding(FMargin(0));
            S.SetPressedPadding(FMargin(0));
            return S;
        }();
        return Style;
    }

    static TSharedRef<SWidget> Text(const FText& InText, const FSlateFontInfo& InFont, const FLinearColor& Color,
        ETextJustify::Type Justify = ETextJustify::Left, bool bWrap = false)
    {
        return SNew(STextBlock)
            .Text(InText)
            .Font(InFont)
            .ColorAndOpacity(FSlateColor(Color))
            .Justification(Justify)
            .AutoWrapText(bWrap);
    }

    static TSharedRef<SWidget> Rule(const FLinearColor& Color, float Width = 0.0f, float Height = 2.0f)
    {
        return SNew(SBox)
            .WidthOverride(Width > 0.0f ? FOptionalSize(Width) : FOptionalSize())
            .HeightOverride(Height)
            [
                SNew(SImage).Image(Solid()).ColorAndOpacity(Color)
            ];
    }

    // (The three side marks were removed with the one-city title: no side names on any screen now.)
}

using namespace ReflectionsFlowStyle;

// ---- Spinner and loading screen ----------------------------------------------------------------------------

/**
 * A ring of gold dots, the bright one going round. Painted from the clock alone (no UObjects, no active timer), so
 * it keeps turning on the movie player's loading thread while the game thread is busy loading a map.
 */
class SReflectionsSpinner : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsSpinner) : _Diameter(30.0f) {}
        SLATE_ARGUMENT(float, Diameter)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs)
    {
        Diameter = InArgs._Diameter;
        Dot = Rounded(4.0f);  // brushes are made here, on the game thread
        SetCanTick(false);
        ForceVolatile(true);  // repaint every frame
    }

    virtual FVector2D ComputeDesiredSize(float) const override
    {
        return FVector2D(Diameter, Diameter);
    }

    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
        FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override
    {
        constexpr int32 Dots = 8;
        const float DotSize = FMath::Max(3.0f, Diameter * 0.2f);
        const FVector2f Size = AllottedGeometry.GetLocalSize();
        const FVector2f Center = Size * 0.5f;
        const float Radius = FMath::Max(1.0f, FMath::Min(Size.X, Size.Y) * 0.5f - DotSize * 0.5f);
        const double Steps = FPlatformTime::Seconds() * 11.0;
        const int32 Lead = static_cast<int32>(FMath::Fmod(Steps, static_cast<double>(Dots)));
        const FLinearColor Tint = InWidgetStyle.GetColorAndOpacityTint();
        for (int32 Index = 0; Index < Dots; ++Index)
        {
            const float Angle = static_cast<float>(UE_TWO_PI * Index / Dots - UE_HALF_PI);
            const FVector2f Position = Center + FVector2f(FMath::Cos(Angle), FMath::Sin(Angle)) * Radius - FVector2f(DotSize * 0.5f);
            const int32 Behind = (Lead - Index + Dots) % Dots;
            FLinearColor Color = Gold * Tint;
            Color.A *= FMath::Lerp(1.0f, 0.15f, static_cast<float>(Behind) / (Dots - 1));
            FSlateDrawElement::MakeBox(OutDrawElements, LayerId,
                AllottedGeometry.ToPaintGeometry(FVector2f(DotSize, DotSize), FSlateLayoutTransform(Position)),
                Dot, ESlateDrawEffect::None, Color);
        }
        return LayerId + 1;
    }

private:
    float Diameter = 30.0f;
    const FSlateBrush* Dot = nullptr;
};

void SReflectionsLoadingScreen::Construct(const FArguments& InArgs)
{
    ChildSlot
    [
        SNew(SBorder)
        .BorderImage(Solid())
        .BorderBackgroundColor(Ink)
        .Padding(FMargin(0))
        [
            SNew(SOverlay)
            + SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Center)
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
                [
                    Text(InArgs._Title, Font(TEXT("Bold"), 54, 220), Paper, ETextJustify::Center)
                ]
                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 10, 0, 0)
                [
                    Rule(Red, 120.0f, 3.0f)
                ]
                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 22, 0, 0)
                [
                    SNew(SBox).WidthOverride(640)
                    [
                        Text(InArgs._Line, Font(TEXT("Italic"), 16), PaperDim, ETextJustify::Center, true)
                    ]
                ]
            ]
            + SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Bottom).Padding(FMargin(0, 0, 60, 52))
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 14, 0)
                [
                    SNew(SReflectionsSpinner).Diameter(30.0f)
                ]
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
                [
                    SNew(STextBlock)
                    .Text(InArgs._Status)
                    .Font(Font(TEXT("Bold"), 15, 200))
                    .ColorAndOpacity(FSlateColor(Paper))
                ]
            ]
        ]
    ];
}

TSharedRef<SReflectionsLoadingScreen> SReflectionsLoadingScreen::Create(const TAttribute<FText>& Status)
{
    // Plain-text copies: a String Table text would resolve through its table when painted, off the game thread.
    const FText Title = FText::FromString(FLOWTEXT("Game.Title", "REFLECTIONS").ToString());
    const FText Line = FText::FromString(FLOWTEXT("Game.Opening",
        "The Tarnish is spreading through Lanthorne. It takes hold of its people and fills them with dark magic.").ToString());
    return SNew(SReflectionsLoadingScreen).Status(Status).Title(Title).Line(Line);
}

// ---- Button ------------------------------------------------------------------------------------------------

void SReflectionsFlowButton::Construct(const FArguments& InArgs)
{
    OnActivatedDelegate = InArgs._OnActivated;
    OnFocusedDelegate = InArgs._OnFocused;
    bPrimary = InArgs._Primary;

    SButton::Construct(SButton::FArguments()
        .ButtonStyle(&ButtonStyle())
        .ContentPadding(FMargin(0))
        .IsFocusable(true)
        .ButtonColorAndOpacity_Lambda([this]()
        {
            const FLinearColor Base = bPrimary ? FLinearColor(0.30f, 0.05f, 0.04f, 0.90f) : FLinearColor(0.0f, 0.0f, 0.0f, 0.45f);
            const FLinearColor Lit = bPrimary ? FLinearColor(0.70f, 0.11f, 0.08f, 0.97f) : FLinearColor(0.93f, 0.89f, 0.80f, 0.16f);
            return FSlateColor(IsHighlighted() ? Lit : Base);
        })
        .OnClicked_Lambda([this]()
        {
            OnActivatedDelegate.ExecuteIfBound();
            return FReply::Handled();
        })
        [
            SNew(SOverlay)
            + SOverlay::Slot()
            [
                SNew(SBorder)
                .BorderImage(Outline(6.0f))
                .BorderBackgroundColor_Lambda([this]()
                {
                    return FSlateColor(IsHighlighted() ? FLinearColor(0.95f, 0.72f, 0.28f, 0.95f) : FLinearColor(0.93f, 0.89f, 0.80f, 0.12f));
                })
                .Padding(FMargin(22, 11))
                [
                    SNew(SHorizontalBox)
                    + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 12, 0)
                    [
                        SNew(SBox).WidthOverride(14)
                        [
                            SNew(STextBlock)
                            .Text(FText::FromString(TEXT(">")))
                            .Font(Font(TEXT("Bold"), 16))
                            .ColorAndOpacity_Lambda([this]() { return FSlateColor(IsHighlighted() ? Gold : FLinearColor::Transparent); })
                        ]
                    ]
                    + SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
                    [
                        SNew(STextBlock)
                        .Text(InArgs._Label)
                        .Font(Font(TEXT("Bold"), 18, 60))
                        .ColorAndOpacity_Lambda([this]() { return FSlateColor(IsHighlighted() ? FLinearColor::White : Paper); })
                    ]
                    + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(16, 0, 0, 0)
                    [
                        SNew(STextBlock)
                        .Visibility(InArgs._Detail.IsSet() ? EVisibility::HitTestInvisible : EVisibility::Collapsed)
                        .Font(Font(TEXT("Regular"), 14))
                        .ColorAndOpacity_Lambda([this]() { return FSlateColor(IsHighlighted() ? Gold : PaperDim); })
                        .Text(InArgs._Detail)
                    ]
                    + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(16, 0, 0, 0)
                    [
                        SNew(STextBlock)
                        .Visibility(InArgs._Value.IsSet() ? EVisibility::HitTestInvisible : EVisibility::Collapsed)
                        .Font(Font(TEXT("Bold"), 17, 40))
                        .ColorAndOpacity_Lambda([this]() { return FSlateColor(IsHighlighted() ? Gold : Paper); })
                        .Text_Lambda([Value = InArgs._Value]() { return FText::Format(INVTEXT("<   {0}   >"), Value.Get()); })
                    ]
                ]
            ]
        ]);
}

FReply SReflectionsFlowButton::OnFocusReceived(const FGeometry& MyGeometry, const FFocusEvent& InFocusEvent)
{
    bFocused = true;
    OnFocusedDelegate.ExecuteIfBound();
    return SButton::OnFocusReceived(MyGeometry, InFocusEvent);
}

void SReflectionsFlowButton::OnFocusLost(const FFocusEvent& InFocusEvent)
{
    bFocused = false;
    SButton::OnFocusLost(InFocusEvent);
}

void SReflectionsFlowButton::OnMouseEnter(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
    SButton::OnMouseEnter(MyGeometry, MouseEvent);
    // Hover moves focus, so mouse and gamepad share one highlight.
    if (!bFocused && FSlateApplication::IsInitialized())
    {
        FSlateApplication::Get().SetUserFocus(MouseEvent.GetUserIndex(), SharedThis(this), EFocusCause::Mouse);
    }
}

FReply SReflectionsFlowButton::OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
    // The cursor may already rest on a button when a menu opens (focus goes to the first button) or after the
    // D-pad moved focus away: the next real mouse movement takes focus back.
    if (!bFocused && !MouseEvent.GetCursorDelta().IsNearlyZero() && FSlateApplication::IsInitialized())
    {
        FSlateApplication::Get().SetUserFocus(MouseEvent.GetUserIndex(), SharedThis(this), EFocusCause::Mouse);
    }
    return SButton::OnMouseMove(MyGeometry, MouseEvent);
}

// ---- HUD ---------------------------------------------------------------------------------------------------

void SReflectionsFlowHud::Construct(const FArguments& InArgs)
{
    Owner = InArgs._Owner;
    TWeakObjectPtr<UReflectionsGameFlowWorldSubsystem> Weak = Owner;

    auto FlowOf = [Weak]() -> UReflectionsGameFlowSubsystem*
    {
        return Weak.IsValid() ? UReflectionsGameFlowSubsystem::Get(Weak.Get()) : nullptr;
    };

    SetVisibility(EVisibility::HitTestInvisible);

    const float MeterWidth = 280.0f;

    ChildSlot
    [
        SNew(SOverlay)
        // "Saving..." with a spinner, bottom right, while a save is written (autosaves, quick and manual saves).
        + SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Bottom).Padding(FMargin(0, 0, 40, 36))
        [
            SNew(SHorizontalBox)
            .Visibility_Lambda([Weak, FlowOf]()
            {
                const UReflectionsGameFlowWorldSubsystem* Self = Weak.Get();
                const UReflectionsGameFlowSubsystem* Flow = FlowOf();
                return Self && Flow && Self->IsPlaying() && Flow->IsSaveIndicatorOn() && !Flow->IsLoadingScreenActive()
                    ? EVisibility::HitTestInvisible : EVisibility::Collapsed;
            })
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 10, 0)
            [
                SNew(SReflectionsSpinner).Diameter(20.0f)
            ]
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
            [
                SNew(STextBlock)
                .Text(LOCTEXT("SavingIndicator", "Saving..."))
                .Font(Font(TEXT("Bold"), 13, 200))
                .ShadowOffset(FVector2D(1.0, 1.0))
                .ColorAndOpacity(FSlateColor(Paper))
            ]
        ]
        + SOverlay::Slot()
        [
        SNew(SOverlay)
        .Visibility_Lambda([Weak]()
        {
            const UReflectionsGameFlowWorldSubsystem* Self = Weak.Get();
            if (!Self || !Self->IsPlaying() || Self->IsCraftingOpen())
            {
                return EVisibility::Collapsed;
            }
            const EReflectionsFlowScreen Screen = Self->GetScreen();
            return Screen == EReflectionsFlowScreen::None || Screen == EReflectionsFlowScreen::Pause
                ? EVisibility::HitTestInvisible : EVisibility::Collapsed;
        })

        // Tarnish (infection) meter, top right (the world-jump panel is top left, the spell HUD bottom centre).
        + SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(FMargin(0, 20, 24, 0))
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight()
            [
                SNew(SBorder)
                .BorderImage(Rounded(8.0f))
                .BorderBackgroundColor_Lambda([Weak]()
                {
                    const float Pulse = Weak.IsValid() ? Weak->GetInfectionPulse() : 0.0f;
                    return FSlateColor(FMath::Lerp(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f), FLinearColor(0.25f, 0.30f, 0.05f, 0.75f), Pulse));
                })
                .Padding(FMargin(14, 10, 14, 12))
                [
                    SNew(SBox).WidthOverride(MeterWidth)
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight()
                        [
                            SNew(SHorizontalBox)
                            + SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
                            [
                                Text(FLOWTEXT("Meter.Label", "TARNISH"), Font(TEXT("Bold"), 12, 350), Plague)
                            ]
                            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
                            [
                                SNew(STextBlock)
                                .Font(Font(TEXT("Bold"), 15))
                                .ColorAndOpacity(FSlateColor(Paper))
                                .Text_Lambda([FlowOf]()
                                {
                                    const UReflectionsGameFlowSubsystem* Flow = FlowOf();
                                    return Flow ? FText::Format(LOCTEXT("InfectionCount", "{0} / {1}"), Flow->GetInfectionCount(), Flow->GetInfectionCap())
                                                : FText::GetEmpty();
                                })
                            ]
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 7, 0, 0)
                        [
                            SNew(SBox).HeightOverride(10)
                            [
                                SNew(SOverlay)
                                + SOverlay::Slot()
                                [
                                    SNew(SImage).Image(Rounded(5.0f)).ColorAndOpacity(FLinearColor(1.0f, 1.0f, 1.0f, 0.12f))
                                ]
                                + SOverlay::Slot().HAlign(HAlign_Left)
                                [
                                    SNew(SBox)
                                    .WidthOverride_Lambda([FlowOf, MeterWidth]()
                                    {
                                        const UReflectionsGameFlowSubsystem* Flow = FlowOf();
                                        const float Fraction = Flow ? Flow->GetInfectionFraction() : 0.0f;
                                        return FOptionalSize(Fraction > 0.0f ? FMath::Max(10.0f, Fraction * MeterWidth) : 0.0f);
                                    })
                                    [
                                        SNew(SImage)
                                        .Image(Rounded(5.0f))
                                        .ColorAndOpacity_Lambda([FlowOf]()
                                        {
                                            const UReflectionsGameFlowSubsystem* Flow = FlowOf();
                                            const float Fraction = Flow ? Flow->GetInfectionFraction() : 0.0f;
                                            return FSlateColor(FMath::Lerp(Plague, Danger, FMath::SmoothStep(0.45f, 0.9f, Fraction)));
                                        })
                                    ]
                                ]
                            ]
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 6, 0, 0)
                        [
                            SNew(STextBlock)
                            .Font(Font(TEXT("Regular"), 11))
                            .AutoWrapText(true)
                            .ColorAndOpacity_Lambda([FlowOf, Weak]()
                            {
                                const UReflectionsGameFlowSubsystem* Flow = FlowOf();
                                const bool bDanger = Flow && Flow->GetInfectionFraction() >= 0.75f;
                                const float Blink = bDanger && Weak.IsValid() ? 0.65f + 0.35f * FMath::Sin(Weak->GetHudClock() * 6.0f) : 1.0f;
                                FLinearColor Color = bDanger ? Danger : PaperDim;
                                Color.A = Blink;
                                return FSlateColor(Color);
                            })
                            .Text_Lambda([FlowOf]()
                            {
                                const UReflectionsGameFlowSubsystem* Flow = FlowOf();
                                if (!Flow || Flow->GetInfectionCount() == 0)
                                {
                                    return FLOWTEXT("Meter.None", "No one is tarnished yet.");
                                }
                                if (Flow->GetInfectionFraction() >= 0.75f)
                                {
                                    return FLOWTEXT("Meter.Danger", "Lanthorne is about to fall. Burn out the Tarnish.");
                                }
                                return FLOWTEXT("Meter.Some", "If the Tarnish reaches the cap, Lanthorne falls.");
                            })
                        ]
                    ]
                ]
            ]
            // Toast ("Checkpoint saved")
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0, 8, 2, 0)
            [
                SNew(SBorder)
                .BorderImage(Rounded(6.0f))
                .Padding(FMargin(12, 6))
                .BorderBackgroundColor_Lambda([Weak]()
                {
                    return FSlateColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f * (Weak.IsValid() ? Weak->GetToastAlpha() : 0.0f)));
                })
                .Visibility_Lambda([Weak]() { return Weak.IsValid() && Weak->GetToastAlpha() > 0.0f ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Bold"), 12, 150))
                    .Text_Lambda([Weak]() { return Weak.IsValid() ? Weak->GetToastText() : FText::GetEmpty(); })
                    .ColorAndOpacity_Lambda([Weak]()
                    {
                        FLinearColor Color = Gold;
                        Color.A = Weak.IsValid() ? Weak->GetToastAlpha() : 0.0f;
                        return FSlateColor(Color);
                    })
                ]
            ]
            // Tutorial tip card, under the meter
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0, 14, 0, 0)
            [
                SNew(SBox)
                .WidthOverride(MeterWidth + 28.0f)
                .Visibility_Lambda([Weak]() { return Weak.IsValid() && Weak->GetScreen() == EReflectionsFlowScreen::None && Weak->GetTipAlpha() > 0.0f ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                [
                    SNew(SBorder)
                    .BorderImage(Rounded(8.0f))
                    .BorderBackgroundColor_Lambda([Weak]() { return FSlateColor(FLinearColor(0.02f, 0.02f, 0.03f, 0.82f * (Weak.IsValid() ? Weak->GetTipAlpha() : 0.0f))); })
                    .ColorAndOpacity_Lambda([Weak]() { return FLinearColor(1.0f, 1.0f, 1.0f, Weak.IsValid() ? Weak->GetTipAlpha() : 0.0f); })
                    .Padding(FMargin(0))
                    [
                        SNew(SHorizontalBox)
                        + SHorizontalBox::Slot().AutoWidth()
                        [
                            SNew(SBox).WidthOverride(4)[SNew(SImage).Image(Solid()).ColorAndOpacity(Gold)]
                        ]
                        + SHorizontalBox::Slot().FillWidth(1.0f).Padding(FMargin(14, 10, 14, 12))
                        [
                            SNew(SVerticalBox)
                            + SVerticalBox::Slot().AutoHeight()
                            [
                                SNew(STextBlock)
                                .Font(Font(TEXT("Bold"), 12, 300))
                                .ColorAndOpacity(FSlateColor(Gold))
                                .Text_Lambda([Weak]()
                                {
                                    return Weak.IsValid() && Weak->HasActiveTip()
                                        ? FText::Format(LOCTEXT("TipHeader", "TIP  ·  {0}"), Weak->GetTipTitle(Weak->GetActiveTip()))
                                        : FText::GetEmpty();
                                })
                            ]
                            + SVerticalBox::Slot().AutoHeight().Padding(0, 5, 0, 0)
                            [
                                SNew(STextBlock)
                                .Font(Font(TEXT("Regular"), 14))
                                .ColorAndOpacity(FSlateColor(Paper))
                                .AutoWrapText(true)
                                .Text_Lambda([Weak]()
                                {
                                    return Weak.IsValid() && Weak->HasActiveTip() ? Weak->GetTipText(Weak->GetActiveTip()) : FText::GetEmpty();
                                })
                            ]
                        ]
                    ]
                ]
            ]
        ]
        ]
    ];
}

// ---- Menus -------------------------------------------------------------------------------------------------

void SReflectionsFlowMenu::Construct(const FArguments& InArgs)
{
    Owner = InArgs._Owner;
    TWeakObjectPtr<UReflectionsGameFlowWorldSubsystem> Weak = Owner;

    ChildSlot
    [
        SNew(SOverlay)
        + SOverlay::Slot()
        [
            SNew(SBackgroundBlur)
            .BlurStrength_Lambda([this]() { return Screen == EReflectionsFlowScreen::Title ? 3.0f : 6.0f; })
        ]
        + SOverlay::Slot()
        [
            SNew(SImage)
            .Image(Solid())
            .ColorAndOpacity_Lambda([this]()
            {
                switch (Screen)
                {
                case EReflectionsFlowScreen::Lose: return FSlateColor(FLinearColor(0.10f, 0.0f, 0.0f, 0.78f));
                case EReflectionsFlowScreen::Death: return FSlateColor(FLinearColor(0.07f, 0.0f, 0.0f, 0.62f));
                case EReflectionsFlowScreen::Victory: return FSlateColor(FLinearColor(0.06f, 0.04f, 0.0f, 0.72f));
                case EReflectionsFlowScreen::Title: return FSlateColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.35f));
                default: return FSlateColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.6f));
                }
            })
        ]
        + SOverlay::Slot()
        [
            SAssignNew(Content, SBox)
        ]
    ];
    SetScreen(EReflectionsFlowScreen::None);
}

TSharedRef<SWidget> SReflectionsFlowMenu::MakeButton(const FText& Label, EReflectionsFlowAction Action, bool bPrimary,
    const TAttribute<FText>& Detail, float Width)
{
    TSharedPtr<SReflectionsFlowButton> Button;
    TSharedRef<SWidget> Widget = SNew(SBox)
        .WidthOverride(Width)
        .Padding(FMargin(0, 5))
        [
            SAssignNew(Button, SReflectionsFlowButton)
            .Label(Label)
            .Detail(Detail)
            .Primary(bPrimary)
            .OnActivated(FSimpleDelegate::CreateSP(this, &SReflectionsFlowMenu::Activate, Action))
        ];
    TWeakPtr<SReflectionsFlowButton> WeakButton = Button;
    TWeakObjectPtr<UReflectionsGameFlowWorldSubsystem> Weak = Owner;
    Button->SetOnFocused(FSimpleDelegate::CreateLambda([this, WeakButton, Weak]()
    {
        const bool bChanged = LastFocused != WeakButton;
        LastFocused = WeakButton;
        if (bChanged && !bSuppressFocusSound && Weak.IsValid())
        {
            Weak->PlayUiSound(TEXT("UI_Hover"));
        }
    }));
    Buttons.Add(Button);
    ButtonLabels.Add(Label.ToString());
    return Widget;
}

void SReflectionsFlowButton::SetOnFocused(const FSimpleDelegate& Delegate)
{
    OnFocusedDelegate = Delegate;
}

TSharedRef<SWidget> SReflectionsFlowMenu::MakePanel(TSharedRef<SWidget> InContent, float Width)
{
    return SNew(SBox)
        .HAlign(HAlign_Center)
        .VAlign(VAlign_Center)
        [
            SNew(SBox)
            .WidthOverride(Width)
            [
                SNew(SBorder)
                .BorderImage(Rounded(12.0f))
                .BorderBackgroundColor(FLinearColor(0.01f, 0.01f, 0.015f, 0.88f))
                .Padding(FMargin(40, 34))
                [
                    InContent
                ]
            ]
        ];
}

void SReflectionsFlowMenu::Activate(EReflectionsFlowAction Action)
{
    if (UReflectionsGameFlowWorldSubsystem* Self = Owner.Get())
    {
        Self->HandleAction(Action);
    }
}

void SReflectionsFlowMenu::SetScreen(EReflectionsFlowScreen InScreen)
{
    Screen = InScreen;
    Buttons.Reset();
    ButtonLabels.Reset();
    LastFocused.Reset();
    if (!Content.IsValid())
    {
        return;
    }
    TSharedRef<SWidget> Body = SNullWidget::NullWidget;
    switch (InScreen)
    {
    case EReflectionsFlowScreen::Title: Body = BuildTitle(); break;
    case EReflectionsFlowScreen::Pause: Body = BuildPause(); break;
    case EReflectionsFlowScreen::Controls: Body = BuildControls(); break;
    // Wide enough that the long licence lines mostly fit on one line: with the map credits the 820 panel used 93% of
    // the screen height, and the team names are still to come.
    case EReflectionsFlowScreen::Credits: Body = MakePanel(BuildCredits(false), 1040.0f); break;
    case EReflectionsFlowScreen::Confirm: Body = BuildConfirm(); break;
    case EReflectionsFlowScreen::Lose: Body = BuildLose(); break;
    case EReflectionsFlowScreen::Victory: Body = BuildVictory(); break;
    case EReflectionsFlowScreen::Settings: Body = BuildSettings(); break;
    case EReflectionsFlowScreen::SettingsConfirm: Body = BuildSettingsConfirm(); break;
    case EReflectionsFlowScreen::SaveGame: Body = BuildSaveGame(); break;
    case EReflectionsFlowScreen::LoadGame: Body = BuildLoadGame(); break;
    case EReflectionsFlowScreen::Death: Body = BuildDeath(); break;
    default: break;
    }
    Content->SetContent(Body);
    SetVisibility(bSuspended || InScreen == EReflectionsFlowScreen::None ? EVisibility::Collapsed : EVisibility::Visible);
    // Focus the first button once the new content has been arranged.
    FocusFrames = InScreen == EReflectionsFlowScreen::None ? 0 : 3;
}

void SReflectionsFlowMenu::Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime)
{
    SCompoundWidget::Tick(AllottedGeometry, InCurrentTime, InDeltaTime);
    if (FocusFrames > 0 && Buttons.Num() > 0 && FSlateApplication::IsInitialized())
    {
        --FocusFrames;
        TGuardValue<bool> Quiet(bSuppressFocusSound, true);
        FSlateApplication::Get().SetUserFocus(0, Buttons[0], EFocusCause::SetDirectly);
        if (Buttons[0]->HasUserFocus(0).IsSet())
        {
            FocusFrames = 0;
        }
    }
}

void SReflectionsFlowMenu::SetSuspended(bool bInSuspended)
{
    bSuspended = bInSuspended;
    SetVisibility(bSuspended || Screen == EReflectionsFlowScreen::None ? EVisibility::Collapsed : EVisibility::Visible);
}

void SReflectionsFlowMenu::EnsureFocus()
{
    if (bSuspended || Screen == EReflectionsFlowScreen::None || Buttons.Num() == 0 || FocusFrames > 0 || !FSlateApplication::IsInitialized())
    {
        return;
    }
    if (HasFocusedDescendants())
    {
        return;
    }
    // Focus left the buttons (a click elsewhere, an alt-tab): put it back so the gamepad keeps working.
    TSharedPtr<SReflectionsFlowButton> Target = LastFocused.Pin();
    if (!Target.IsValid() || !Buttons.Contains(Target))
    {
        Target = Buttons[0];
    }
    TGuardValue<bool> Quiet(bSuppressFocusSound, true);
    FSlateApplication::Get().SetUserFocus(0, Target, EFocusCause::SetDirectly);
}

int32 SReflectionsFlowMenu::GetFocusedIndex() const
{
    for (int32 Index = 0; Index < Buttons.Num(); ++Index)
    {
        if (Buttons[Index].IsValid() && Buttons[Index]->HasUserFocus(0).IsSet())
        {
            return Index;
        }
    }
    return INDEX_NONE;
}

TArray<FString> SReflectionsFlowMenu::GetButtonLabels() const
{
    return ButtonLabels;
}

FNavigationReply SReflectionsFlowMenu::OnNavigation(const FGeometry& MyGeometry, const FNavigationEvent& InNavigationEvent)
{
    // Keep focus inside the menu and wrap around, so the gamepad never wanders into the HUD buttons below.
    if (Buttons.Num() == 0)
    {
        return FNavigationReply::Stop();
    }
    int32 Index = GetFocusedIndex();
    if (Index == INDEX_NONE)
    {
        return FNavigationReply::Explicit(Buttons[0]);
    }
    const EUINavigation Nav = InNavigationEvent.GetNavigationType();
    if (Screen == EReflectionsFlowScreen::Settings && Index < ReflectionsFlowSettings::Row_Count
        && (Nav == EUINavigation::Left || Nav == EUINavigation::Right))
    {
        if (UReflectionsGameFlowWorldSubsystem* Self = Owner.Get())
        {
            Self->StepSetting(Index, Nav == EUINavigation::Left ? -1 : 1);
        }
        return FNavigationReply::Stop();
    }
    int32 Step = 0;
    switch (InNavigationEvent.GetNavigationType())
    {
    case EUINavigation::Up:
    case EUINavigation::Left:
    case EUINavigation::Previous:
        Step = -1;
        break;
    case EUINavigation::Down:
    case EUINavigation::Right:
    case EUINavigation::Next:
        Step = 1;
        break;
    default:
        return FNavigationReply::Stop();
    }
    Index = (Index + Step + Buttons.Num()) % Buttons.Num();
    return FNavigationReply::Explicit(Buttons[Index]);
}

FReply SReflectionsFlowMenu::OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent)
{
    const FKey Key = InKeyEvent.GetKey();
    UReflectionsGameFlowWorldSubsystem* Self = Owner.Get();
    if (!Self)
    {
        return FReply::Unhandled();
    }
    const bool bBack = FSlateApplication::Get().GetNavigationActionFromKey(InKeyEvent) == EUINavigationAction::Back
        || Key == EKeys::Escape || Key == EKeys::Gamepad_FaceButton_Right;
    const bool bStart = Key == EKeys::Gamepad_Special_Right || Key == EKeys::P;
    if (InKeyEvent.IsRepeat() && (bBack || bStart))
    {
        // A held Start / B / Esc auto-repeats after ~0.2 s: one press is one step.
        return FReply::Handled();
    }
    if (bStart && Screen == EReflectionsFlowScreen::Pause)
    {
        Self->HandleAction(EReflectionsFlowAction::Resume);
        return FReply::Handled();
    }
    if (!InKeyEvent.IsRepeat())
    {
        const bool bSaveKey = Key == EKeys::F5 || Key == EKeys::Gamepad_FaceButton_Left;
        const bool bLoadKey = Key == EKeys::F9 || Key == EKeys::Gamepad_FaceButton_Top;
        if (bSaveKey && Screen == EReflectionsFlowScreen::Pause)
        {
            Self->HandleAction(EReflectionsFlowAction::QuickSave);
            return FReply::Handled();
        }
        if (bLoadKey && (Screen == EReflectionsFlowScreen::Pause || Screen == EReflectionsFlowScreen::Death))
        {
            Self->HandleAction(EReflectionsFlowAction::QuickLoad);
            return FReply::Handled();
        }
    }
    if (bBack)
    {
        Self->HandleAction(EReflectionsFlowAction::Back);
        return FReply::Handled();
    }
    // Arrow keys / D-pad reaching the menu itself become navigation; everything else is swallowed so game keys
    // do nothing behind the menu.
    const FReply Base = SCompoundWidget::OnKeyDown(MyGeometry, InKeyEvent);
    return Base.IsEventHandled() ? Base : FReply::Handled();
}

FReply SReflectionsFlowMenu::OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent)
{
    // Clicks on empty space stay in the menu (and do not move focus to the game viewport).
    return FReply::Handled();
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildFooter()
{
    TWeakObjectPtr<UReflectionsGameFlowWorldSubsystem> Weak = Owner;
    return SNew(STextBlock)
        .Font(Font(TEXT("Regular"), 12, 100))
        .ColorAndOpacity(FSlateColor(PaperDim))
        .Text_Lambda([this, Weak]()
        {
            const bool bPad = Weak.IsValid() && Weak->IsUsingGamepad();
            const bool bCanGoBack = Screen != EReflectionsFlowScreen::Title && Screen != EReflectionsFlowScreen::Lose
                && Screen != EReflectionsFlowScreen::Victory && Screen != EReflectionsFlowScreen::Death;
            if (Screen == EReflectionsFlowScreen::Pause)
            {
                return bPad ? LOCTEXT("FooterPadPause", "D-pad  Move     A  Select     B  Back     X  Quick save     Y  Quick load")
                            : LOCTEXT("FooterKeyPause", "Arrows  Move     Enter  Select     Esc  Back     F5  Quick save     F9  Quick load");
            }
            if (Screen == EReflectionsFlowScreen::Death)
            {
                return bPad ? LOCTEXT("FooterPadDeath", "D-pad / Left stick  Move     A  Select     Y  Quick load")
                            : LOCTEXT("FooterKeyDeath", "Mouse or Arrow keys  Move     Enter / Click  Select     F9  Quick load");
            }
            if (Screen == EReflectionsFlowScreen::Settings)
            {
                return bPad ? LOCTEXT("FooterPadSettings", "Up / down  Row     Left / right  Change     A  Select     B  Back")
                            : LOCTEXT("FooterKeySettings", "Up / down  Row     Left / right or Click  Change     Enter  Select     Esc  Back");
            }
            if (bPad)
            {
                return bCanGoBack ? LOCTEXT("FooterPadBack", "D-pad / Left stick  Move     A  Select     B  Back")
                                  : LOCTEXT("FooterPad", "D-pad / Left stick  Move     A  Select");
            }
            return bCanGoBack ? LOCTEXT("FooterKeyBack", "Mouse or Arrow keys  Move     Enter / Click  Select     Esc  Back")
                              : LOCTEXT("FooterKey", "Mouse or Arrow keys  Move     Enter / Click  Select");
        });
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildTitle()
{
    UReflectionsGameFlowSubsystem* Flow = Owner.IsValid() ? UReflectionsGameFlowSubsystem::Get(Owner.Get()) : nullptr;
    const int32 NewestSlot = Flow ? Flow->GetNewestSaveSlot() : INDEX_NONE;
    const bool bCanContinue = NewestSlot != INDEX_NONE;

    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    // No side marks on the title: the game is one city now (the side names live on the victory screen only).
    Column->AddSlot().AutoHeight().Padding(0, 14, 0, 0)
    [
        Text(FLOWTEXT("Game.Title", "REFLECTIONS"), Font(TEXT("Bold"), 80, 220), Paper)
    ];
    Column->AddSlot().AutoHeight().Padding(0, 6, 0, 0)[Rule(Red, 120.0f, 3.0f)];
    Column->AddSlot().AutoHeight().Padding(0, 18, 0, 0)
    [
        SNew(SBox).WidthOverride(560)
        [
            // New key (not Game.Theme): the String Table asset still holds the old Game.Theme text, and asset rows win.
            Text(FLOWTEXT("Game.Opening", "The Tarnish is spreading through Lanthorne. It takes hold of its people and fills them with dark magic."),
                Font(TEXT("Italic"), 19), Paper, ETextJustify::Left, true)
        ]
    ];
    Column->AddSlot().AutoHeight().Padding(0, 14, 0, 0)
    [
        SNew(SBox).WidthOverride(560)
        [
            Text(FLOWTEXT("Game.Summary", "Wren Hale, the Silverer, is the only one who can burn the Tarnish out of Lanthorne."),
                Font(TEXT("Regular"), 14), PaperDim, ETextJustify::Left, true)
        ]
    ];
    Column->AddSlot().AutoHeight().Padding(0, 34, 0, 0)[SNew(SSpacer)];
    if (bCanContinue)
    {
        Column->AddSlot().AutoHeight()[MakeButton(LOCTEXT("Continue", "Continue"), EReflectionsFlowAction::Continue, true)];
        Column->AddSlot().AutoHeight()[MakeButton(FLOWTEXT("Save.LoadButton", "Load Game"), EReflectionsFlowAction::LoadGame)];
        Column->AddSlot().AutoHeight()[MakeButton(LOCTEXT("NewGame", "New Game"), EReflectionsFlowAction::NewGame)];
    }
    else
    {
        Column->AddSlot().AutoHeight()[MakeButton(LOCTEXT("Start", "Start"), EReflectionsFlowAction::Start, true)];
    }
    Column->AddSlot().AutoHeight()[MakeButton(LOCTEXT("Controls", "Controls"), EReflectionsFlowAction::Controls)];
    Column->AddSlot().AutoHeight()[MakeButton(FLOWTEXT("Settings.Button", "Settings"), EReflectionsFlowAction::Settings)];
    Column->AddSlot().AutoHeight()[MakeButton(LOCTEXT("Credits", "Credits"), EReflectionsFlowAction::Credits)];
    Column->AddSlot().AutoHeight()[MakeButton(LOCTEXT("Quit", "Quit"), EReflectionsFlowAction::QuitGame)];
    if (bCanContinue)
    {
        const FReflectionsSaveSlotInfo Newest = Flow->GetSaveSlotInfo(NewestSlot);
        Column->AddSlot().AutoHeight().Padding(0, 12, 0, 0)
        [
            Text(FText::Format(FLOWTEXT("Title.Saved", "Last checkpoint: {0}, {1} mirror page(s)"),
                    FText::AsDateTime(Newest.SavedAt, EDateTimeStyle::Short, EDateTimeStyle::Short), Newest.Pages),
                Font(TEXT("Regular"), 12), PaperDim)
        ];
    }

    return SNew(SOverlay)
        // A dark band on the left so the title reads over any scene.
        + SOverlay::Slot().HAlign(HAlign_Left)
        [
            SNew(SBox).WidthOverride(1000)
            [
                SNew(SImage).Image(Solid()).ColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f))
            ]
        ]
        + SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Center).Padding(FMargin(110, 0, 0, 0))
        [
            Column
        ]
        + SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Bottom).Padding(FMargin(110, 0, 0, 40))
        [
            BuildFooter()
        ];
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildPause()
{
    UReflectionsGameFlowSubsystem* Flow = Owner.IsValid() ? UReflectionsGameFlowSubsystem::Get(Owner.Get()) : nullptr;
    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)
    [
        Text(LOCTEXT("Paused", "PAUSED"), Font(TEXT("Bold"), 40, 300), Paper)
    ];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0, 8, 0, 22)[Rule(Red, 80.0f, 3.0f)];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(LOCTEXT("Resume", "Resume"), EReflectionsFlowAction::Resume, true)];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(FLOWTEXT("Save.SaveButton", "Save Game"), EReflectionsFlowAction::SaveGame)];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(FLOWTEXT("Save.LoadButton", "Load Game"), EReflectionsFlowAction::LoadGame)];
    if (Owner.IsValid() && Owner->HasJournal())
    {
        Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(LOCTEXT("Journal", "Journal"), EReflectionsFlowAction::Journal)];
    }
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(LOCTEXT("Controls", "Controls"), EReflectionsFlowAction::Controls)];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(FLOWTEXT("Settings.Button", "Settings"), EReflectionsFlowAction::Settings)];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(LOCTEXT("Restart", "Restart from checkpoint"), EReflectionsFlowAction::Restart)];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(LOCTEXT("QuitToTitle", "Quit to title"), EReflectionsFlowAction::QuitToTitle)];
    // Straight out, without the title's map reload first (it asks first: anything since the last save is lost).
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(LOCTEXT("QuitToDesktop", "Quit to desktop"), EReflectionsFlowAction::QuitGame)];
    if (Flow)
    {
        Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0, 18, 0, 0)
        [
            Text(FText::Format(FLOWTEXT("Pause.Count", "Tarnished: {0} of {1}"), Flow->GetInfectionCount(), Flow->GetInfectionCap()),
                Font(TEXT("Regular"), 13), Plague)
        ];
    }
    if (Owner.IsValid() && !Owner->GetSaveStatus().IsEmpty())
    {
        Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0, 8, 0, 0)
        [
            Text(Owner->GetSaveStatus(), Font(TEXT("Bold"), 14), Gold)
        ];
    }
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0, 14, 0, 0)[BuildFooter()];
    return MakePanel(Column, 640.0f);
}

namespace
{
    FText SideText(EReflectionsWorld World)
    {
        // One city now: the save slots name the place, not a side (the map is one city, no stepping through).
        (void)World;
        return FLOWTEXT("Save.Place", "Lanthorne");
    }

    FText SlotDetail(const FReflectionsSaveSlotInfo& Info)
    {
        if (!Info.bUsed)
        {
            return FLOWTEXT("Save.EmptySlot", "Empty");
        }
        return FText::Format(FLOWTEXT("Save.Detail", "{0}   -   {1}   -   {2} {2}|plural(one=page,other=pages)"),
            FText::AsDateTime(Info.SavedAt, EDateTimeStyle::Short, EDateTimeStyle::Short), SideText(Info.World), Info.Pages);
    }
}

namespace
{
    /** Death screen rows: just the time and the side, so "Respawn at last save" keeps its room. */
    FText ShortSlotDetail(const FReflectionsSaveSlotInfo& Info)
    {
        return FText::Format(FLOWTEXT("Save.ShortDetail", "{0}   -   {1}"),
            FText::AsTime(Info.SavedAt, EDateTimeStyle::Short), SideText(Info.World));
    }
}

TSharedRef<SWidget> SReflectionsFlowMenu::MakeSlotButton(int32 Slot, EReflectionsFlowAction Action, bool bPrimary)
{
    const UReflectionsGameFlowSubsystem* Flow = Owner.IsValid() ? UReflectionsGameFlowSubsystem::Get(Owner.Get()) : nullptr;
    const FReflectionsSaveSlotInfo Info = Flow ? Flow->GetSaveSlotInfo(Slot) : FReflectionsSaveSlotInfo();
    return MakeButton(UReflectionsGameFlowSubsystem::GetSlotDisplayName(Slot), Action, bPrimary, SlotDetail(Info), 640.0f);
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildSaveStatus()
{
    const FText Status = Owner.IsValid() ? Owner->GetSaveStatus() : FText::GetEmpty();
    return Text(Status.IsEmpty() ? FText::FromString(TEXT(" ")) : Status, Font(TEXT("Bold"), 14), Gold);
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildSaveGame()
{
    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    Column->AddSlot().AutoHeight()[Text(FLOWTEXT("Save.SaveTitle", "SAVE GAME"), Font(TEXT("Bold"), 32, 300), Paper)];
    Column->AddSlot().AutoHeight().Padding(0, 8, 0, 18)[Rule(Red, 80.0f, 3.0f)];
    for (int32 Index = 0; Index < ReflectionsSaveSlots::ManualCount; ++Index)
    {
        Column->AddSlot().AutoHeight()[MakeSlotButton(ReflectionsSaveSlots::FirstManual + Index,
            static_cast<EReflectionsFlowAction>(static_cast<int32>(EReflectionsFlowAction::SaveSlot1) + Index), Index == 0)];
    }
    Column->AddSlot().AutoHeight().Padding(0, 10, 0, 0)[BuildSaveStatus()];
    Column->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
    [
        Text(FLOWTEXT("Save.SaveNote", "Saving also sets your checkpoint: if you fall, you get up here. Quick save: F5, or hold Start."),
            Font(TEXT("Regular"), 13), PaperDim, ETextJustify::Left, true)
    ];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Left).Padding(0, 14, 0, 0)[MakeButton(LOCTEXT("Back", "Back"), EReflectionsFlowAction::Back)];
    Column->AddSlot().AutoHeight().Padding(0, 10, 0, 0)[BuildFooter()];
    return MakePanel(Column, 720.0f);
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildLoadGame()
{
    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    Column->AddSlot().AutoHeight()[Text(FLOWTEXT("Save.LoadTitle", "LOAD GAME"), Font(TEXT("Bold"), 32, 300), Paper)];
    Column->AddSlot().AutoHeight().Padding(0, 8, 0, 18)[Rule(Red, 80.0f, 3.0f)];
    const EReflectionsFlowAction Actions[] = {EReflectionsFlowAction::LoadQuick, EReflectionsFlowAction::LoadAutosave,
        EReflectionsFlowAction::LoadSlot1, EReflectionsFlowAction::LoadSlot2, EReflectionsFlowAction::LoadSlot3};
    const int32 Slots[] = {ReflectionsSaveSlots::Quick, ReflectionsSaveSlots::Autosave, ReflectionsSaveSlots::FirstManual,
        ReflectionsSaveSlots::FirstManual + 1, ReflectionsSaveSlots::FirstManual + 2};
    // Only the first row (where focus starts) is drawn as the primary button, as on every other screen.
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(Slots); ++Index)
    {
        Column->AddSlot().AutoHeight()[MakeSlotButton(Slots[Index], Actions[Index], Index == 0)];
    }
    Column->AddSlot().AutoHeight().Padding(0, 10, 0, 0)[BuildSaveStatus()];
    Column->AddSlot().AutoHeight().Padding(0, 6, 0, 0)
    [
        Text(FLOWTEXT("Save.LoadNote2", "The autosave follows you: it saves at every checkpoint. Quick load: F9."),
            Font(TEXT("Regular"), 13), PaperDim, ETextJustify::Left, true)
    ];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Left).Padding(0, 14, 0, 0)[MakeButton(LOCTEXT("Back", "Back"), EReflectionsFlowAction::Back)];
    Column->AddSlot().AutoHeight().Padding(0, 10, 0, 0)[BuildFooter()];
    return MakePanel(Column, 720.0f);
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildDeath()
{
    const UReflectionsGameFlowSubsystem* Flow = Owner.IsValid() ? UReflectionsGameFlowSubsystem::Get(Owner.Get()) : nullptr;
    const FReflectionsSaveSlotInfo Checkpoint = Flow ? Flow->GetSaveSlotInfo(ReflectionsSaveSlots::Autosave) : FReflectionsSaveSlotInfo();
    const int32 LastSave = Flow ? Flow->GetNewestSaveSlot(true) : INDEX_NONE;
    const FReflectionsSaveSlotInfo Save = Flow && LastSave != INDEX_NONE ? Flow->GetSaveSlotInfo(LastSave) : FReflectionsSaveSlotInfo();

    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)
    [
        Text(FLOWTEXT("Death.Title", "YOU FELL"), Font(TEXT("Bold"), 46, 300), Danger, ETextJustify::Center)
    ];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0, 10, 0, 0)[Rule(Danger, 120.0f, 3.0f)];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0, 18, 0, 26)
    [
        SNew(SBox).WidthOverride(620)
        [
            Text(FLOWTEXT("Death.Body", "Get up where you last saved or reached a checkpoint, or load another save."),
                Font(TEXT("Regular"), 17), Paper, ETextJustify::Center, true)
        ]
    ];
    // The newer of the last checkpoint and the last manual / quick save is the default (first, highlighted).
    // A save is also a checkpoint, so the respawn is the default unless the checkpoint was cleared.
    const FText RespawnLabel = Checkpoint.bUsed && (Checkpoint.Reason.StartsWith(TEXT("Slot")) || Checkpoint.Reason.StartsWith(TEXT("Quick")))
        ? FLOWTEXT("Death.RespawnSave", "Respawn at last save") : FLOWTEXT("Death.RespawnCheckpoint", "Respawn at last checkpoint");
    const TAttribute<FText> RespawnDetail = Checkpoint.bUsed ? TAttribute<FText>(ShortSlotDetail(Checkpoint)) : TAttribute<FText>();
    const bool bSaveNewer = Save.bUsed && (!Checkpoint.bUsed || Save.UsedAt > Checkpoint.UsedAt);
    auto AddRespawn = [&](bool bPrimary)
    {
        Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(RespawnLabel, EReflectionsFlowAction::Respawn, bPrimary, RespawnDetail, 640.0f)];
    };
    auto AddLoadLast = [&](bool bPrimary)
    {
        Column->AddSlot().AutoHeight().HAlign(HAlign_Center)
        [
            MakeButton(FText::Format(FLOWTEXT("Death.LoadLast", "Load last save ({0})"), UReflectionsGameFlowSubsystem::GetSlotDisplayName(LastSave)),
                EReflectionsFlowAction::LoadLatest, bPrimary, ShortSlotDetail(Save), 640.0f)
        ];
    };
    if (bSaveNewer)
    {
        AddLoadLast(true);
        AddRespawn(false);
    }
    else
    {
        AddRespawn(true);
        if (Save.bUsed)
        {
            AddLoadLast(false);
        }
    }
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(FLOWTEXT("Save.LoadButton", "Load Game"), EReflectionsFlowAction::LoadGame, false, TAttribute<FText>(), 640.0f)];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(LOCTEXT("QuitToTitle", "Quit to title"), EReflectionsFlowAction::ReturnToTitle, false, TAttribute<FText>(), 640.0f)];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0, 8, 0, 0)[BuildSaveStatus()];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0, 12, 0, 0)[BuildFooter()];
    return SNew(SBox).HAlign(HAlign_Center).VAlign(VAlign_Center)[Column];
}

namespace
{
    struct FControlRow
    {
        FText Action;
        FText Keys;
        FText Pad;
    };

    TArray<FControlRow> ControlRows()
    {
        // Bindings as the code binds them: IMC_Sandbox (movement), UReflectionsSampleSpellDriver (spells, sprint on
        // the pad), IMC_WorldJump (crossing), UReflectionsSpellCraftingComponent (crafting), game flow (pause).
        return {
            {LOCTEXT("CMove", "Move"), LOCTEXT("KMove", "W A S D"), LOCTEXT("PMove", "Left stick")},
            {LOCTEXT("CLook", "Look"), LOCTEXT("KLook", "Mouse"), LOCTEXT("PLook", "Right stick")},
            {LOCTEXT("CJump", "Jump"), LOCTEXT("KJump", "Space"), LOCTEXT("PJump", "A")},
            {LOCTEXT("CSprint", "Sprint"), LOCTEXT("KSprint", "Left Shift"), LOCTEXT("PSprint", "L3 (click left stick)")},
            {LOCTEXT("CWalk", "Walk"), LOCTEXT("KWalk", "Left Ctrl"), LOCTEXT("PWalk", "Tilt the stick partway")},
            {LOCTEXT("CCrouch", "Crouch"), LOCTEXT("KCrouch", "C"), LOCTEXT("PCrouch", "B")},
            {LOCTEXT("CStrafe", "Strafe"), LOCTEXT("KStrafe", "Middle mouse"), FText::FromString(TEXT("-"))},
            {LOCTEXT("CAim", "Aim"), LOCTEXT("KAim", "Right mouse (hold)"), LOCTEXT("PAim", "LT (hold)")},
            {LOCTEXT("CCast", "Cast selected spell (hold to repeat)"), LOCTEXT("KCast", "Left mouse or Q"), LOCTEXT("PCast", "RT")},
            {LOCTEXT("CSlot", "Select spell 1-4"), LOCTEXT("KSlot", "1 2 3 4"), FText::FromString(TEXT("-"))},
            {LOCTEXT("CNext", "Next / previous spell"), LOCTEXT("KNext", "Tab / Shift+Tab"), LOCTEXT("PNext", "RB / LB")},
            {LOCTEXT("CPage", "Next / previous spell page"), LOCTEXT("KPage", "] / ["), LOCTEXT("PPage", "D-pad right / left")},
            {LOCTEXT("CCraft", "Open spell crafting"), LOCTEXT("KCraft", "K"), LOCTEXT("PCraft", "View")},
            {LOCTEXT("CCrafted", "Select crafted spell 5-8"), LOCTEXT("KCrafted", "5 6 7 8"), LOCTEXT("PCrafted", "D-pad up")},
            {LOCTEXT("CMouse", "Free the mouse cursor (HUD buttons)"), LOCTEXT("KMouse", "Right Alt (hold)"), FText::FromString(TEXT("-"))},
            {LOCTEXT("CJournal", "Journal"), LOCTEXT("KJournal", "L"), LOCTEXT("PJournal", "Start > Journal")},
            {LOCTEXT("CSpeak", "Speak with quest people"), LOCTEXT("KSpeak", "E"), LOCTEXT("PSpeak", "D-pad down")},
            {LOCTEXT("CPause", "Pause / menu"), LOCTEXT("KPause", "Esc or P"), LOCTEXT("PPause", "Start")},
            {LOCTEXT("CQuickSave", "Quick save / quick load"), LOCTEXT("KQuickSave", "F5 / F9"), LOCTEXT("PQuickSave", "Hold Start / Start > Y")},
        };
    }
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildControls()
{
    TSharedRef<SVerticalBox> Table = SNew(SVerticalBox);
    auto Row = [&Table](const FText& Action, const FText& Keys, const FText& Pad, bool bHeader, bool bShade)
    {
        const FSlateFontInfo RowFont = bHeader ? Font(TEXT("Bold"), 13, 250) : Font(TEXT("Regular"), 15);
        const FLinearColor ActionColor = bHeader ? Gold : PaperDim;
        const FLinearColor KeyColor = bHeader ? Gold : Paper;
        Table->AddSlot().AutoHeight()
        [
            SNew(SBorder)
            .BorderImage(Rounded(4.0f))
            .BorderBackgroundColor(FLinearColor(1.0f, 1.0f, 1.0f, bShade ? 0.035f : 0.0f))
            .Padding(FMargin(12, bHeader ? 4 : 6))
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().FillWidth(1.55f).VAlign(VAlign_Center)[Text(Action, RowFont, ActionColor)]
                + SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)[Text(Keys, RowFont, KeyColor)]
                + SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)[Text(Pad, RowFont, KeyColor)]
            ]
        ];
    };
    Row(LOCTEXT("HAction", "ACTION"), LOCTEXT("HKeys", "KEYBOARD & MOUSE"), LOCTEXT("HPad", "CONTROLLER"), true, false);
    const TArray<FControlRow> Rows = ControlRows();
    for (int32 Index = 0; Index < Rows.Num(); ++Index)
    {
        Row(Rows[Index].Action, Rows[Index].Keys, Rows[Index].Pad, false, Index % 2 == 0);
    }

    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    Column->AddSlot().AutoHeight()[Text(LOCTEXT("ControlsTitle", "CONTROLS"), Font(TEXT("Bold"), 32, 300), Paper)];
    Column->AddSlot().AutoHeight().Padding(0, 8, 0, 18)[Rule(Red, 80.0f, 3.0f)];
    Column->AddSlot().AutoHeight()[Table];
    Column->AddSlot().AutoHeight().Padding(0, 14, 0, 0)
    [
        Text(FLOWTEXT("Controls.Note2", "In menus: D-pad or stick to move, A to select, B to go back."),
            Font(TEXT("Regular"), 12), PaperDim, ETextJustify::Left, true)
    ];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Left).Padding(0, 16, 0, 0)[MakeButton(LOCTEXT("Back", "Back"), EReflectionsFlowAction::Back, true)];
    Column->AddSlot().AutoHeight().Padding(0, 10, 0, 0)[BuildFooter()];
    return MakePanel(Column, 1120.0f);
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildCredits(bool bEmbedded)
{
    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    if (!bEmbedded)
    {
        Column->AddSlot().AutoHeight()[Text(LOCTEXT("CreditsTitle", "CREDITS"), Font(TEXT("Bold"), 32, 300), Paper)];
        Column->AddSlot().AutoHeight().Padding(0, 8, 0, 18)[Rule(Red, 80.0f, 3.0f)];
    }
    // The lead credit first and largest; anyone else who worked on the game goes under it (Credits.Crew, one per
    // line, empty by default). Then the licence block, small, at the end: only what the licences ask for.
    // New keys on purpose: the old Credits.* rows in /Game/UI/ST_GameFlowText still hold the jam-era text.
    Column->AddSlot().AutoHeight().Padding(0, 4, 0, 4)
    [
        Text(FLOWTEXT("Credits.LeadRole", "CREATED BY"), Font(TEXT("Bold"), 13, 300), Gold)
    ];
    Column->AddSlot().AutoHeight()
    [
        Text(FLOWTEXT("Credits.Lead", "Jah Markabawi"), Font(TEXT("Bold"), bEmbedded ? 30 : 38, 60), Paper)
    ];
    const TArray<FText> Crew = ReflectionsFlowText::GetLines(TEXT("Credits.Crew"), FText::GetEmpty());
    if (Crew.Num() > 0)
    {
        Column->AddSlot().AutoHeight().Padding(0, 14, 0, 0)[SNew(SSpacer)];
        for (const FText& Entry : Crew)
        {
            Column->AddSlot().AutoHeight().Padding(0, 2)[Text(Entry, Font(TEXT("Regular"), 16), Paper, ETextJustify::Left, true)];
        }
    }
    Column->AddSlot().AutoHeight().Padding(0, bEmbedded ? 18 : 26, 0, 8)
    [
        Text(FLOWTEXT("Credits.NoticesHead", "LICENSES AND THIRD-PARTY NOTICES"), Font(TEXT("Bold"), 11, 250), PaperDim)
    ];
    // From ArtDirection/Submission/THIRD_PARTY_NOTICES.txt (what ships with the MedievalLondon map), plus the
    // Unreal Engine notice from Epic's EULA and the voice disclosure OpenAI's usage policies ask for.
    const TArray<FText> Notices = ReflectionsFlowText::GetLines(TEXT("Credits.Notices"), LOCTEXT("Credits.Notices",
        "Reflections uses the Unreal® Engine. Unreal® is a trademark or registered trademark of Epic Games, Inc. in the United States of America and elsewhere.\n"
        "Unreal® Engine, Copyright 1998–2026, Epic Games, Inc. All rights reserved.\n"
        "Includes content from Epic Games' Game Animation Sample and Third Person template. Characters made with MetaHuman.\n"
        "Map data © OpenStreetMap contributors, available under the Open Database License (ODbL): openstreetmap.org/copyright\n"
        "Spell animations: NVIDIA Kimodo (Kimodo-SOMA-RP-v1.1), licensed by NVIDIA Corporation under the NVIDIA Open Model License.\n"
        "3D garments: Tencent Hunyuan3D-2. Powered by Tencent Hunyuan.\n"
        "Music: Eleven Music by ElevenLabs (elevenlabs.io). Fire and water spell sounds: ElevenLabs (elevenlabs.io).\n"
        "Character voices are synthesized with Google Gemini and OpenAI text-to-speech; they are not human actors.\n"
        "Market well modelled with TripoSR (MIT License). Cobblestone and grass textures: Poly Haven (CC0).\n"
        "Portions of this software are copyright © The FreeType Project (www.freetype.org). All rights reserved.\n"
        "Full licence texts: THIRD_PARTY_NOTICES.txt"));
    for (const FText& Entry : Notices)
    {
        Column->AddSlot().AutoHeight().Padding(0, 1)
        [
            Text(Entry, Font(TEXT("Regular"), bEmbedded ? 11 : 12), PaperDim, ETextJustify::Left, true)
        ];
    }
    if (!bEmbedded)
    {
        Column->AddSlot().AutoHeight().HAlign(HAlign_Left).Padding(0, 22, 0, 0)[MakeButton(LOCTEXT("Back", "Back"), EReflectionsFlowAction::Back, true)];
        Column->AddSlot().AutoHeight().Padding(0, 10, 0, 0)[BuildFooter()];
    }
    return Column;
}

TSharedRef<SWidget> SReflectionsFlowMenu::MakeRow(const FText& Label, int32 Row)
{
    TSharedPtr<SReflectionsFlowButton> Button;
    TWeakObjectPtr<UReflectionsGameFlowWorldSubsystem> Weak = Owner;
    TSharedRef<SWidget> Widget = SNew(SBox)
        .WidthOverride(640)
        .Padding(FMargin(0, 3))
        [
            SAssignNew(Button, SReflectionsFlowButton)
            .Label(Label)
            .Value_Lambda([Weak, Row]()
            {
                return Weak.IsValid() ? ReflectionsFlowSettings::ValueText(Weak->GetSettingsDraft(), Row) : FText::GetEmpty();
            })
            .OnActivated(FSimpleDelegate::CreateLambda([Weak, Row]()
            {
                if (Weak.IsValid())
                {
                    Weak->StepSetting(Row, 1);  // a click cycles forward
                }
            }))
        ];
    TWeakPtr<SReflectionsFlowButton> WeakButton = Button;
    Button->SetOnFocused(FSimpleDelegate::CreateLambda([this, WeakButton, Weak]()
    {
        const bool bChanged = LastFocused != WeakButton;
        LastFocused = WeakButton;
        if (bChanged && !bSuppressFocusSound && Weak.IsValid())
        {
            Weak->PlayUiSound(TEXT("UI_Hover"));
        }
    }));
    Buttons.Add(Button);
    ButtonLabels.Add(Label.ToString());
    return Widget;
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildSettings()
{
    using namespace ReflectionsFlowSettings;
    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    Column->AddSlot().AutoHeight()[Text(FLOWTEXT("Settings.Title", "SETTINGS"), Font(TEXT("Bold"), 32, 300), Paper)];
    Column->AddSlot().AutoHeight().Padding(0, 8, 0, 16)[Rule(Red, 80.0f, 3.0f)];
    // Rows first: their indices match ReflectionsFlowSettings::ERow (left / right change them).
    Column->AddSlot().AutoHeight()[MakeRow(FLOWTEXT("Settings.Preset", "Quality preset"), Row_Preset)];
    Column->AddSlot().AutoHeight()[MakeRow(FLOWTEXT("Settings.Resolution", "Resolution"), Row_Resolution)];
    Column->AddSlot().AutoHeight()[MakeRow(FLOWTEXT("Settings.WindowMode", "Window mode"), Row_WindowMode)];
    Column->AddSlot().AutoHeight()[MakeRow(FLOWTEXT("Settings.RenderScale", "Render scale"), Row_RenderScale)];
    Column->AddSlot().AutoHeight()[MakeRow(FLOWTEXT("Settings.VSync", "VSync"), Row_VSync)];
    Column->AddSlot().AutoHeight()[MakeRow(FLOWTEXT("Settings.FrameCap", "Frame cap"), Row_FrameCap)];
    Column->AddSlot().AutoHeight()[MakeRow(FLOWTEXT("Settings.RayTracing", "Ray-traced lighting"), Row_RayTracing)];
    Column->AddSlot().AutoHeight().Padding(0, 10, 0, 6)
    [
        SNew(SBox).WidthOverride(640)
        [
            Text(CanChangeVideoMode()
                    ? FLOWTEXT("Settings.Note", "High holds 60 fps on most mid-range PCs. Epic adds ray-traced lighting.")
                    : FLOWTEXT("Settings.NotePIE", "High holds 60 fps on most mid-range PCs. Epic adds ray-traced lighting. (In the editor, resolution and window mode are left alone.)"),
                Font(TEXT("Regular"), 13), PaperDim, ETextJustify::Left, true)
        ]
    ];
    // Privacy: live voice talk with townsfolk sends the player's speech to Google (only with the player's own key).
    Column->AddSlot().AutoHeight().Padding(0, 0, 0, 8)
    [
        SNew(SBox).WidthOverride(640)
        [
            Text(FLOWTEXT("Settings.VoicePrivacy", "Voice chat sends what you say to Google to generate replies. It stays off unless you add your own Google API key."),
                Font(TEXT("Regular"), 12), PaperDim, ETextJustify::Left, true)
        ]
    ];
    // The player's own Gemini API key for live talk: written to keys.json next to the voice helper, never shown again,
    // never logged. Saving restarts the helper, so talk goes live without restarting the game.
    {
        TSharedPtr<SEditableTextBox> KeyBox;
        TSharedRef<SHorizontalBox> KeyRow = SNew(SHorizontalBox);
        KeyRow->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 12, 0)
            [Text(FLOWTEXT("Settings.GeminiKey", "Gemini API key"), Font(TEXT("Bold"), 15), Paper)];
        KeyRow->AddSlot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(0, 0, 10, 0)
        [
            SAssignNew(KeyBox, SEditableTextBox)
            .IsPassword(true)
            .Font(Font(TEXT("Regular"), 14))
            .HintText(FLOWTEXT("Settings.GeminiKeyHint", "Paste your key"))
        ];
        KeyRow->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 12, 0)
        [
            SNew(SButton)
            .OnClicked_Lambda([KeyBox]()
            {
                if (KeyBox.IsValid())
                {
                    UReflectionsNpcRelayHost::SaveGeminiKey(KeyBox->GetText().ToString());
                    KeyBox->SetText(FText::GetEmpty());
                }
                return FReply::Handled();
            })
            [
                Text(FLOWTEXT("Settings.GeminiKeySave", "Save"), Font(TEXT("Bold"), 14), Paper)
            ]
        ];
        KeyRow->AddSlot().AutoWidth().VAlign(VAlign_Center)
        [
            SNew(STextBlock)
            .Font(Font(TEXT("Regular"), 14))
            .Text_Lambda([]() { return UReflectionsNpcRelayHost::HasGeminiKey() ? FLOWTEXT("Settings.GeminiKeySaved", "Saved") : FLOWTEXT("Settings.GeminiKeyNone", "No key"); })
            .ColorAndOpacity_Lambda([]() { return FSlateColor(UReflectionsNpcRelayHost::HasGeminiKey() ? Paper : PaperDim); })
        ];
        Column->AddSlot().AutoHeight().Padding(0, 0, 0, 12)[SNew(SBox).WidthOverride(640)[KeyRow]];
    }
    Column->AddSlot().AutoHeight()[MakeButton(FLOWTEXT("Settings.Apply", "Apply"), EReflectionsFlowAction::SettingsApply, true)];
    Column->AddSlot().AutoHeight()[MakeButton(FLOWTEXT("Settings.AutoDetect", "Auto-detect"), EReflectionsFlowAction::SettingsDefaults)];
    Column->AddSlot().AutoHeight()[MakeButton(LOCTEXT("Back", "Back"), EReflectionsFlowAction::Back)];
    Column->AddSlot().AutoHeight().Padding(0, 10, 0, 0)[BuildFooter()];
    return MakePanel(Column, 740.0f);
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildSettingsConfirm()
{
    TWeakObjectPtr<UReflectionsGameFlowWorldSubsystem> Weak = Owner;
    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    Column->AddSlot().AutoHeight()[Text(FLOWTEXT("Settings.Keep", "Keep these settings?"), Font(TEXT("Bold"), 24), Paper, ETextJustify::Left, true)];
    Column->AddSlot().AutoHeight().Padding(0, 12, 0, 22)
    [
        SNew(STextBlock)
        .Font(Font(TEXT("Regular"), 15))
        .ColorAndOpacity(FSlateColor(PaperDim))
        .Text_Lambda([Weak]()
        {
            const int32 Seconds = Weak.IsValid() ? FMath::CeilToInt(Weak->GetSettingsConfirmSecondsLeft()) : 0;
            return FText::Format(FLOWTEXT("Settings.Reverting", "Reverting in {0} s"), Seconds);
        })
    ];
    Column->AddSlot().AutoHeight()[MakeButton(FLOWTEXT("Settings.KeepButton", "Keep"), EReflectionsFlowAction::SettingsKeep, true)];
    Column->AddSlot().AutoHeight()[MakeButton(FLOWTEXT("Settings.RevertButton", "Revert"), EReflectionsFlowAction::SettingsRevert)];
    Column->AddSlot().AutoHeight().Padding(0, 12, 0, 0)[BuildFooter()];
    return MakePanel(Column, 600.0f);
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildConfirm()
{
    const UReflectionsGameFlowWorldSubsystem* Self = Owner.Get();
    if (Self && (Self->GetConfirmAction() == EReflectionsFlowAction::SaveGame || Self->GetConfirmAction() == EReflectionsFlowAction::LoadGame))
    {
        const bool bSave = Self->GetConfirmAction() == EReflectionsFlowAction::SaveGame;
        const FText SlotName = UReflectionsGameFlowSubsystem::GetSlotDisplayName(Self->GetPendingSlot());
        TSharedRef<SVerticalBox> Box = SNew(SVerticalBox);
        Box->AddSlot().AutoHeight()
        [
            Text(FText::Format(bSave ? FLOWTEXT("Save.ConfirmSave", "Overwrite {0}?") : FLOWTEXT("Save.ConfirmLoad", "Load {0}?"), SlotName),
                Font(TEXT("Bold"), 24), Paper, ETextJustify::Left, true)
        ];
        Box->AddSlot().AutoHeight().Padding(0, 12, 0, 22)
        [
            Text(bSave ? FLOWTEXT("Save.ConfirmSaveBody", "The save already in this slot is replaced by where you are now.")
                       : FLOWTEXT("Save.ConfirmLoadBody", "Anything since your last save is lost. You'll be back where this save was made."),
                Font(TEXT("Regular"), 15), PaperDim, ETextJustify::Left, true)
        ];
        Box->AddSlot().AutoHeight()[MakeButton(bSave ? FLOWTEXT("Save.Overwrite", "Overwrite") : FLOWTEXT("Save.Load", "Load"), EReflectionsFlowAction::ConfirmYes, true)];
        Box->AddSlot().AutoHeight()[MakeButton(LOCTEXT("Cancel", "Cancel"), EReflectionsFlowAction::Back)];
        Box->AddSlot().AutoHeight().Padding(0, 12, 0, 0)[BuildFooter()];
        return MakePanel(Box, 600.0f);
    }
    if (Self && Self->GetConfirmAction() == EReflectionsFlowAction::NewGame)
    {
        TSharedRef<SVerticalBox> Box = SNew(SVerticalBox);
        Box->AddSlot().AutoHeight()[Text(FLOWTEXT("Save.ConfirmNew", "Start a new game?"), Font(TEXT("Bold"), 24), Paper, ETextJustify::Left, true)];
        Box->AddSlot().AutoHeight().Padding(0, 12, 0, 22)
        [
            Text(FLOWTEXT("Save.ConfirmNewBody", "The autosave is replaced by the new run. Your quick save and Slots 1-3 are kept."),
                Font(TEXT("Regular"), 15), PaperDim, ETextJustify::Left, true)
        ];
        Box->AddSlot().AutoHeight()[MakeButton(LOCTEXT("NewGame", "New Game"), EReflectionsFlowAction::ConfirmYes, true)];
        Box->AddSlot().AutoHeight()[MakeButton(LOCTEXT("Cancel", "Cancel"), EReflectionsFlowAction::Back)];
        Box->AddSlot().AutoHeight().Padding(0, 12, 0, 0)[BuildFooter()];
        return MakePanel(Box, 600.0f);
    }
    if (Self && Self->GetConfirmAction() == EReflectionsFlowAction::QuitGame)
    {
        TSharedRef<SVerticalBox> Box = SNew(SVerticalBox);
        Box->AddSlot().AutoHeight()[Text(LOCTEXT("ConfirmDesktopTitle", "Quit to desktop?"), Font(TEXT("Bold"), 24), Paper, ETextJustify::Left, true)];
        Box->AddSlot().AutoHeight().Padding(0, 12, 0, 22)
        [
            Text(LOCTEXT("ConfirmDesktopBody", "Your saves and last checkpoint are kept. Anything since then is lost."),
                Font(TEXT("Regular"), 15), PaperDim, ETextJustify::Left, true)
        ];
        Box->AddSlot().AutoHeight()[MakeButton(LOCTEXT("ConfirmDesktop", "Quit"), EReflectionsFlowAction::ConfirmYes, true)];
        Box->AddSlot().AutoHeight()[MakeButton(LOCTEXT("Cancel", "Cancel"), EReflectionsFlowAction::Back)];
        Box->AddSlot().AutoHeight().Padding(0, 12, 0, 0)[BuildFooter()];
        return MakePanel(Box, 600.0f);
    }
    const bool bRestart = !Self || Self->GetConfirmAction() == EReflectionsFlowAction::Restart;
    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    Column->AddSlot().AutoHeight()
    [
        Text(bRestart ? LOCTEXT("ConfirmRestartTitle", "Restart from the last checkpoint?") : LOCTEXT("ConfirmQuitTitle", "Quit to the title screen?"),
            Font(TEXT("Bold"), 24), Paper, ETextJustify::Left, true)
    ];
    Column->AddSlot().AutoHeight().Padding(0, 12, 0, 22)
    [
        Text(bRestart ? LOCTEXT("ConfirmRestartBody", "You go back to your last auto-save. Anything since then is lost.")
                      : LOCTEXT("ConfirmQuitBody", "Your last checkpoint is kept. Choose Continue on the title screen to pick up from there."),
            Font(TEXT("Regular"), 15), PaperDim, ETextJustify::Left, true)
    ];
    Column->AddSlot().AutoHeight()[MakeButton(bRestart ? LOCTEXT("ConfirmRestart", "Restart") : LOCTEXT("ConfirmQuit", "Quit to title"), EReflectionsFlowAction::ConfirmYes, true)];
    Column->AddSlot().AutoHeight()[MakeButton(LOCTEXT("Cancel", "Cancel"), EReflectionsFlowAction::Back)];
    Column->AddSlot().AutoHeight().Padding(0, 12, 0, 0)[BuildFooter()];
    return MakePanel(Column, 600.0f);
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildLose()
{
    UReflectionsGameFlowSubsystem* Flow = Owner.IsValid() ? UReflectionsGameFlowSubsystem::Get(Owner.Get()) : nullptr;
    const int32 Count = Flow ? Flow->GetInfectionCount() : 0;
    const int32 Cap = Flow ? Flow->GetInfectionCap() : 0;
    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)
    [
        Text(FLOWTEXT("Lose.Title", "THE TARNISH HAS TAKEN LANTHORNE"), Font(TEXT("Bold"), 46, 200), Danger, ETextJustify::Center)
    ];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0, 10, 0, 0)[Rule(Danger, 140.0f, 3.0f)];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0, 20, 0, 30)
    [
        SNew(SBox).WidthOverride(620)
        [
            Text(FText::Format(FLOWTEXT("Lose.Body2", "The Tarnish reached {0} of {1}. Its hold on Lanthorne is complete."), Count, Cap),
                Font(TEXT("Regular"), 17), Paper, ETextJustify::Center, true)
        ]
    ];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(LOCTEXT("TryAgain", "Try again from checkpoint"), EReflectionsFlowAction::TryAgain, true)];
    if (Flow && Flow->HasAnySave())
    {
        Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(FLOWTEXT("Save.LoadButton", "Load Game"), EReflectionsFlowAction::LoadGame)];
    }
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center)[MakeButton(LOCTEXT("LoseQuit", "Quit to title"), EReflectionsFlowAction::ReturnToTitle)];
    Column->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0, 16, 0, 0)[BuildFooter()];
    return SNew(SBox).HAlign(HAlign_Center).VAlign(VAlign_Center)[Column];
}

TSharedRef<SWidget> SReflectionsFlowMenu::BuildVictory()
{
    TSharedRef<SVerticalBox> Left = SNew(SVerticalBox);
    Left->AddSlot().AutoHeight().Padding(0, 14, 0, 0)
    [
        Text(FLOWTEXT("Victory.Title", "THE TARNISH\nIS BURNED OUT"), Font(TEXT("Bold"), 50, 160), Gold)
    ];
    Left->AddSlot().AutoHeight().Padding(0, 8, 0, 0)[Rule(Gold, 140.0f, 3.0f)];
    Left->AddSlot().AutoHeight().Padding(0, 20, 0, 30)
    [
        SNew(SBox).WidthOverride(520)
        [
            Text(FLOWTEXT("Victory.Body2", "The Final Spell burned the Tarnish out of its last face. The tarnished wake, and Lanthorne is itself again."),
                Font(TEXT("Regular"), 17), Paper, ETextJustify::Left, true)
        ]
    ];
    Left->AddSlot().AutoHeight()[MakeButton(LOCTEXT("VictoryTitleBtn", "Return to title"), EReflectionsFlowAction::ReturnToTitle, true)];
    Left->AddSlot().AutoHeight()[MakeButton(LOCTEXT("VictoryQuit", "Quit game"), EReflectionsFlowAction::QuitGame)];
    Left->AddSlot().AutoHeight().Padding(0, 14, 0, 0)[BuildFooter()];

    return SNew(SBox).HAlign(HAlign_Center).VAlign(VAlign_Center)
    [
        SNew(SHorizontalBox)
        + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 60, 0)
        [
            Left
        ]
        + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
        [
            SNew(SBox).WidthOverride(760)   // 660 before the map credits; the whole row stays under 1440 (4:3)
            [
                SNew(SBorder)
                .BorderImage(Rounded(12.0f))
                .BorderBackgroundColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.6f))
                .Padding(FMargin(32, 26))
                [
                    BuildCredits(true)
                ]
            ]
        ]
    ];
}

#undef LOCTEXT_NAMESPACE
