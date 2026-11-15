#include "Cinematics/ReflectionsCutsceneSlate.h"

#include "Cinematics/ReflectionsCutsceneSubsystem.h"
#include "Brushes/SlateColorBrush.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/DrawElements.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/SBoxPanel.h"

#define LOCTEXT_NAMESPACE "ReflectionsCutscene"

namespace ReflectionsCutsceneStyle
{
    // Same palette as the game-flow menus: parchment text on ink, gold accents.
    static const FLinearColor Ink(0.012f, 0.012f, 0.018f, 1.0f);
    static const FLinearColor Paper(0.93f, 0.89f, 0.80f, 1.0f);
    static const FLinearColor PaperDim(0.62f, 0.59f, 0.53f, 1.0f);
    static const FLinearColor Gold(0.95f, 0.72f, 0.28f, 1.0f);

    static const FSlateBrush* Solid()
    {
        static const FSlateColorBrush Brush(FLinearColor::White);
        return &Brush;
    }

    static const FSlateBrush* Rounded(float Radius)
    {
        static TMap<int32, TSharedPtr<FSlateRoundedBoxBrush>> Cache;
        TSharedPtr<FSlateRoundedBoxBrush>& Entry = Cache.FindOrAdd(FMath::RoundToInt(Radius));
        if (!Entry.IsValid())
        {
            Entry = MakeShared<FSlateRoundedBoxBrush>(FLinearColor::White, Radius);
        }
        return Entry.Get();
    }

    static FSlateFontInfo Font(const TCHAR* Weight, int32 Size, int32 LetterSpacing = 0)
    {
        FSlateFontInfo Info = FCoreStyle::GetDefaultFontStyle(Weight, Size);
        Info.LetterSpacing = LetterSpacing;
        return Info;
    }

    static FLinearColor WithAlpha(FLinearColor Color, float Alpha)
    {
        Color.A *= FMath::Clamp(Alpha, 0.0f, 1.0f);
        return Color;
    }
}

using namespace ReflectionsCutsceneStyle;

void SReflectionsCutsceneOverlay::Construct(const FArguments& InArgs)
{
    Owner = InArgs._Owner;
    SetVisibility(EVisibility::HitTestInvisible);

    ChildSlot
    [
        SNew(SOverlay)
        + SOverlay::Slot().HAlign(HAlign_Fill).VAlign(VAlign_Fill)[BuildCard()]
        + SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Bottom)[BuildSubtitle()]
        + SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Bottom)[BuildSkipPrompt()]
    ];
}

void SReflectionsCutsceneOverlay::Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime)
{
    SCompoundWidget::Tick(AllottedGeometry, InCurrentTime, InDeltaTime);
    const FVector2D Size = FVector2D(AllottedGeometry.GetLocalSize());
    if (Size.X > 1.0f && Size.Y > 1.0f)
    {
        LastSize = Size;
    }
}

float SReflectionsCutsceneOverlay::GetBarHeight() const
{
    const UReflectionsCutsceneSubsystem* Sub = Owner.Get();
    if (!Sub)
    {
        return 0.0f;
    }
    const float Aspect = FMath::Max(Sub->GetLetterboxAspect(), 1.0f);
    const float Inner = LastSize.X / Aspect;
    // Never less than a thin cinematic band, even on ultra-wide screens (subtitles live in it).
    const float Full = FMath::Max((LastSize.Y - Inner) * 0.5f, LastSize.Y * 0.075f);
    return Full * FMath::SmoothStep(0.0f, 1.0f, Sub->GetLetterboxAlpha());
}

int32 SReflectionsCutsceneOverlay::OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
    FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
    const UReflectionsCutsceneSubsystem* Sub = Owner.Get();
    const FVector2f Size = AllottedGeometry.GetLocalSize();
    if (Sub)
    {
        // The scene fade sits under the text, so title cards can play over black.
        const float Black = Sub->GetBlackAlpha();
        if (Black > 0.001f)
        {
            FSlateDrawElement::MakeBox(OutDrawElements, LayerId, AllottedGeometry.ToPaintGeometry(Size, FSlateLayoutTransform()),
                Solid(), ESlateDrawEffect::None, WithAlpha(FLinearColor::Black, Black));
        }
        const float Bar = GetBarHeight();
        if (Bar > 0.5f)
        {
            const FLinearColor BarColor(0.0f, 0.0f, 0.0f, 1.0f);
            FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 1, AllottedGeometry.ToPaintGeometry(FVector2f(Size.X, Bar), FSlateLayoutTransform()),
                Solid(), ESlateDrawEffect::None, BarColor);
            FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 1,
                AllottedGeometry.ToPaintGeometry(FVector2f(Size.X, Bar), FSlateLayoutTransform(FVector2f(0.0f, Size.Y - Bar))),
                Solid(), ESlateDrawEffect::None, BarColor);
        }
    }
    return SCompoundWidget::OnPaint(Args, AllottedGeometry, MyCullingRect, OutDrawElements, LayerId + 2, InWidgetStyle, bParentEnabled);
}

TSharedRef<SWidget> SReflectionsCutsceneOverlay::BuildSubtitle()
{
    TWeakObjectPtr<UReflectionsCutsceneSubsystem> Weak = Owner;
    TWeakPtr<SReflectionsCutsceneOverlay> Self = SharedThis(this);
    return SNew(SBox)
        .WidthOverride(1180.0f)
        .Padding_Lambda([Self]()
        {
            // Centred in the lower bar; above the bottom edge when bars are thin or off.
            const TSharedPtr<SReflectionsCutsceneOverlay> Pinned = Self.Pin();
            const float Bar = Pinned.IsValid() ? Pinned->GetBarHeight() : 0.0f;
            return FMargin(0.0f, 0.0f, 0.0f, FMath::Max(Bar * 0.5f - 34.0f, 44.0f));
        })
        .Visibility_Lambda([Weak]() { return Weak.IsValid() && Weak->GetSubtitleAlpha() > 0.001f ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 0.0f, 0.0f, 4.0f)
            [
                SNew(STextBlock)
                .Font(Font(TEXT("Bold"), 12, 380))
                .Justification(ETextJustify::Center)
                .Text_Lambda([Weak]() { return Weak.IsValid() ? Weak->GetSubtitleSpeaker() : FText::GetEmpty(); })
                .Visibility_Lambda([Weak]() { return Weak.IsValid() && !Weak->GetSubtitleSpeaker().IsEmpty() ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                .ColorAndOpacity_Lambda([Weak]() { return FSlateColor(WithAlpha(Gold, Weak.IsValid() ? Weak->GetSubtitleAlpha() : 0.0f)); })
            ]
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
            [
                SNew(STextBlock)
                .Font(Font(TEXT("Regular"), 21))
                .Justification(ETextJustify::Center)
                .AutoWrapText(true)
                .Text_Lambda([Weak]() { return Weak.IsValid() ? Weak->GetSubtitleText() : FText::GetEmpty(); })
                .ShadowOffset(FVector2D(1.5f, 1.5f))
                .ShadowColorAndOpacity_Lambda([Weak]() { return WithAlpha(FLinearColor(0.0f, 0.0f, 0.0f, 0.85f), Weak.IsValid() ? Weak->GetSubtitleAlpha() : 0.0f); })
                .ColorAndOpacity_Lambda([Weak]() { return FSlateColor(WithAlpha(Paper, Weak.IsValid() ? Weak->GetSubtitleAlpha() : 0.0f)); })
            ]
        ];
}

TSharedRef<SWidget> SReflectionsCutsceneOverlay::BuildCard()
{
    TWeakObjectPtr<UReflectionsCutsceneSubsystem> Weak = Owner;
    TWeakPtr<SReflectionsCutsceneOverlay> Self = SharedThis(this);

    auto CardAlpha = [Weak](int32 WantStyle) -> float
    {
        int32 Style = -1; FText Text, Sub; float Alpha = 0.0f;
        if (Weak.IsValid() && Weak->GetCard(Style, Text, Sub, Alpha) && Style == WantStyle)
        {
            return Alpha;
        }
        return 0.0f;
    };
    auto CardText = [Weak](bool bSub) -> FText
    {
        int32 Style = -1; FText Text, Sub; float Alpha = 0.0f;
        if (Weak.IsValid() && Weak->GetCard(Style, Text, Sub, Alpha))
        {
            return bSub ? Sub : Text;
        }
        return FText::GetEmpty();
    };
    auto VisibleFor = [CardAlpha](int32 Style) { return CardAlpha(Style) > 0.001f ? EVisibility::HitTestInvisible : EVisibility::Collapsed; };

    return SNew(SOverlay)
        // Title: the wordmark with a line under it, centred.
        + SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Center)
        [
            SNew(SVerticalBox)
            .Visibility_Lambda([VisibleFor]() { return VisibleFor(0); })
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
            [
                SNew(STextBlock)
                .Font(Font(TEXT("Bold"), 76, 260))
                .Text_Lambda([CardText]() { return CardText(false); })
                .ColorAndOpacity_Lambda([CardAlpha]() { return FSlateColor(WithAlpha(Paper, CardAlpha(0))); })
            ]
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 10.0f, 0.0f, 14.0f)
            [
                SNew(SBox).WidthOverride(220.0f).HeightOverride(2.0f)
                [
                    SNew(SImage).Image(Solid()).ColorAndOpacity_Lambda([CardAlpha]() { return FSlateColor(WithAlpha(Gold, 0.85f * CardAlpha(0))); })
                ]
            ]
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
            [
                SNew(SBox).WidthOverride(980.0f)
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Italic"), 20))
                    .Justification(ETextJustify::Center)
                    .AutoWrapText(true)
                    .Text_Lambda([CardText]() { return CardText(true); })
                    .ColorAndOpacity_Lambda([CardAlpha]() { return FSlateColor(WithAlpha(Paper, CardAlpha(0))); })
                ]
            ]
        ]
        // Caption: one large italic line in the middle of the frame.
        + SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Center)
        [
            SNew(SBox)
            .WidthOverride(1120.0f)
            .Visibility_Lambda([VisibleFor]() { return VisibleFor(1); })
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Italic"), 28))
                    .Justification(ETextJustify::Center)
                    .AutoWrapText(true)
                    .LineHeightPercentage(1.15f)
                    .Text_Lambda([CardText]() { return CardText(false); })
                    .ShadowOffset(FVector2D(2.0f, 2.0f))
                    .ShadowColorAndOpacity_Lambda([CardAlpha]() { return WithAlpha(FLinearColor(0.0f, 0.0f, 0.0f, 0.8f), CardAlpha(1)); })
                    .ColorAndOpacity_Lambda([CardAlpha]() { return FSlateColor(WithAlpha(Paper, CardAlpha(1))); })
                ]
                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.0f, 16.0f, 0.0f, 0.0f)
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Bold"), 13, 420))
                    .Justification(ETextJustify::Center)
                    .Text_Lambda([CardText]() { return CardText(true); })
                    .ColorAndOpacity_Lambda([CardAlpha]() { return FSlateColor(WithAlpha(Gold, CardAlpha(1))); })
                ]
            ]
        ]
        // Location stamp: small spaced capitals, lower left, just above the bar.
        + SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Bottom)
        [
            SNew(SBox)
            .Visibility_Lambda([VisibleFor]() { return VisibleFor(2); })
            .Padding_Lambda([Self]()
            {
                const TSharedPtr<SReflectionsCutsceneOverlay> Pinned = Self.Pin();
                const float Bar = Pinned.IsValid() ? Pinned->GetBarHeight() : 0.0f;
                return FMargin(96.0f, 0.0f, 0.0f, Bar + 36.0f);
            })
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot().AutoHeight()
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Bold"), 15, 520))
                    .Text_Lambda([CardText]() { return CardText(false); })
                    .ShadowOffset(FVector2D(1.0f, 1.0f))
                    .ShadowColorAndOpacity_Lambda([CardAlpha]() { return WithAlpha(FLinearColor(0.0f, 0.0f, 0.0f, 0.8f), CardAlpha(2)); })
                    .ColorAndOpacity_Lambda([CardAlpha]() { return FSlateColor(WithAlpha(Paper, CardAlpha(2))); })
                ]
                + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 6.0f, 0.0f, 0.0f)
                [
                    SNew(SBox).WidthOverride(64.0f).HeightOverride(2.0f)
                    [
                        SNew(SImage).Image(Solid()).ColorAndOpacity_Lambda([CardAlpha]() { return FSlateColor(WithAlpha(Gold, CardAlpha(2))); })
                    ]
                ]
                + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 6.0f, 0.0f, 0.0f)
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Italic"), 13))
                    .Text_Lambda([CardText]() { return CardText(true); })
                    .ColorAndOpacity_Lambda([CardAlpha]() { return FSlateColor(WithAlpha(PaperDim, CardAlpha(2))); })
                ]
            ]
        ];
}

TSharedRef<SWidget> SReflectionsCutsceneOverlay::BuildSkipPrompt()
{
    TWeakObjectPtr<UReflectionsCutsceneSubsystem> Weak = Owner;
    TWeakPtr<SReflectionsCutsceneOverlay> Self = SharedThis(this);
    auto Alpha = [Weak]() { return Weak.IsValid() ? Weak->GetSkipPromptAlpha() : 0.0f; };

    return SNew(SBox)
        .Visibility_Lambda([Alpha]() { return Alpha() > 0.001f ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
        .Padding_Lambda([Self]()
        {
            const TSharedPtr<SReflectionsCutsceneOverlay> Pinned = Self.Pin();
            const float Bar = Pinned.IsValid() ? Pinned->GetBarHeight() : 0.0f;
            return FMargin(0.0f, 0.0f, 56.0f, FMath::Max(Bar * 0.5f - 16.0f, 28.0f));
        })
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right)
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.0f, 0.0f, 10.0f, 0.0f)
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Regular"), 12, 120))
                    .Text(LOCTEXT("HoldTo", "HOLD"))
                    .ColorAndOpacity_Lambda([Alpha]() { return FSlateColor(WithAlpha(PaperDim, Alpha())); })
                ]
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
                [
                    SNew(SBorder)
                    .BorderImage(Rounded(4.0f))
                    .Padding(FMargin(8.0f, 2.0f))
                    .BorderBackgroundColor_Lambda([Alpha]() { return FSlateColor(WithAlpha(FLinearColor(0.93f, 0.89f, 0.80f, 0.16f), Alpha())); })
                    [
                        SNew(STextBlock)
                        .Font(Font(TEXT("Bold"), 12, 120))
                        .Text_Lambda([Weak]()
                        {
                            return Weak.IsValid() && Weak->IsUsingGamepad() ? LOCTEXT("PadSkip", "A") : LOCTEXT("KeySkip", "SPACE");
                        })
                        .ColorAndOpacity_Lambda([Alpha]() { return FSlateColor(WithAlpha(Paper, Alpha())); })
                    ]
                ]
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(10.0f, 0.0f, 0.0f, 0.0f)
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Regular"), 12, 120))
                    .Text(LOCTEXT("ToSkip", "TO SKIP"))
                    .ColorAndOpacity_Lambda([Alpha]() { return FSlateColor(WithAlpha(PaperDim, Alpha())); })
                ]
            ]
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Fill).Padding(0.0f, 7.0f, 0.0f, 0.0f)
            [
                SNew(SBox).HeightOverride(2.0f)
                [
                    SNew(SOverlay)
                    + SOverlay::Slot()
                    [
                        SNew(SImage).Image(Solid()).ColorAndOpacity_Lambda([Alpha]() { return FSlateColor(WithAlpha(FLinearColor(1.0f, 1.0f, 1.0f, 0.12f), Alpha())); })
                    ]
                    + SOverlay::Slot().HAlign(HAlign_Left)
                    [
                        SNew(SBox)
                        .WidthOverride_Lambda([Weak]() { return FOptionalSize(150.0f * (Weak.IsValid() ? Weak->GetSkipProgress() : 0.0f)); })
                        [
                            SNew(SImage).Image(Solid()).ColorAndOpacity_Lambda([Alpha]() { return FSlateColor(WithAlpha(Gold, Alpha())); })
                        ]
                    ]
                ]
            ]
        ];
}

// ---- Input -------------------------------------------------------------------------------------------------

bool FReflectionsCutsceneInput::IsSkipKey(const FKey& Key)
{
    return Key == EKeys::SpaceBar || Key == EKeys::Enter || Key == EKeys::Gamepad_FaceButton_Bottom;
}

bool FReflectionsCutsceneInput::HandleKeyDownEvent(FSlateApplication& SlateApp, const FKeyEvent& InKeyEvent)
{
    if (UReflectionsCutsceneSubsystem* Sub = Owner.Get())
    {
        const bool bPad = InKeyEvent.GetKey().IsGamepadKey();
        Sub->NotifyAnyInput(bPad);
        if (IsSkipKey(InKeyEvent.GetKey()) && !InKeyEvent.IsRepeat())
        {
            Sub->NotifySkipKey(true, bPad);
        }
    }
    return false;
}

bool FReflectionsCutsceneInput::HandleKeyUpEvent(FSlateApplication& SlateApp, const FKeyEvent& InKeyEvent)
{
    if (UReflectionsCutsceneSubsystem* Sub = Owner.Get())
    {
        if (IsSkipKey(InKeyEvent.GetKey()))
        {
            Sub->NotifySkipKey(false, InKeyEvent.GetKey().IsGamepadKey());
        }
    }
    return false;
}

bool FReflectionsCutsceneInput::HandleAnalogInputEvent(FSlateApplication& SlateApp, const FAnalogInputEvent& InAnalogInputEvent)
{
    if (FMath::Abs(InAnalogInputEvent.GetAnalogValue()) > 0.5f)
    {
        if (UReflectionsCutsceneSubsystem* Sub = Owner.Get())
        {
            Sub->NotifyAnyInput(true);
        }
    }
    return false;
}

bool FReflectionsCutsceneInput::HandleMouseButtonDownEvent(FSlateApplication& SlateApp, const FPointerEvent& MouseEvent)
{
    if (UReflectionsCutsceneSubsystem* Sub = Owner.Get())
    {
        Sub->NotifyAnyInput(false);
    }
    return false;
}

#undef LOCTEXT_NAMESPACE
