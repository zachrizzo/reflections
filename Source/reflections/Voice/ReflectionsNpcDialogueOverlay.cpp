#include "Voice/ReflectionsNpcDialogueOverlay.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/DrawElements.h"
#include "Widgets/SLeafWidget.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "ReflectionsNpcDialogue"

namespace
{
    const FLinearColor Gold(0.95f, 0.72f, 0.28f, 1.0f);
    const FLinearColor Paper(0.96f, 0.94f, 0.88f, 1.0f);
    const FLinearColor Muted(0.78f, 0.78f, 0.80f, 1.0f);
    const FLinearColor Listen(0.45f, 0.85f, 1.0f, 1.0f);

    FSlateFontInfo Font(const TCHAR* Weight, int32 Size)
    {
        return FCoreStyle::GetDefaultFontStyle(Weight, Size);
    }

    FLinearColor WithAlpha(FLinearColor Color, float Alpha)
    {
        Color.A *= Alpha;
        return Color;
    }
}


/** The listening meter: a ring that swells with the player's voice and five bars beside it; three pulsing dots while thinking. */
class SReflectionsListeningMeter : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsListeningMeter) {}
        SLATE_ATTRIBUTE(float, Level)
        SLATE_ATTRIBUTE(bool, Thinking)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs)
    {
        Level = InArgs._Level;
        Thinking = InArgs._Thinking;
    }

    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(92.0, 44.0) * Scale; }

    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& Geo, const FSlateRect& Culling, FSlateWindowElementList& Out,
        int32 LayerId, const FWidgetStyle& Style, bool bParentEnabled) const override
    {
        const double Time = FPlatformTime::Seconds();
        const float S = Scale;
        const FVector2D Centre(22.0 * S, Geo.GetLocalSize().Y * 0.5);
        if (Thinking.Get(false))
        {
            for (int32 Dot = 0; Dot < 3; ++Dot)
            {
                const float Pulse = 0.35f + 0.65f * (0.5f + 0.5f * FMath::Sin(static_cast<float>(Time) * 5.0f - Dot * 0.9f));
                const float Size = (7.0f + 4.0f * Pulse) * S;
                const FVector2D At((10.0 + Dot * 18.0) * S, Centre.Y);
                FSlateDrawElement::MakeBox(Out, LayerId, Geo.ToPaintGeometry(FVector2D(Size, Size), FSlateLayoutTransform(At - FVector2D(Size, Size) * 0.5)),
                    RoundBrush(), ESlateDrawEffect::None, Gold.CopyWithNewOpacity(Pulse));
            }
            return LayerId + 1;
        }
        const float Voice = FMath::Clamp(Level.Get(0.0f), 0.0f, 1.0f);
        // The mic dot, and a ring that breathes on its own and swells with the voice.
        const float Breath = 0.5f + 0.5f * FMath::Sin(static_cast<float>(Time) * 4.0f);
        const float RingSize = (26.0f + 6.0f * Breath + 14.0f * Voice) * S;
        FSlateDrawElement::MakeBox(Out, LayerId, Geo.ToPaintGeometry(FVector2D(RingSize, RingSize), FSlateLayoutTransform(Centre - FVector2D(RingSize, RingSize) * 0.5)),
            RingBrush(), ESlateDrawEffect::None, Listen.CopyWithNewOpacity(0.45f + 0.55f * FMath::Max(Voice, 0.3f * Breath)));
        const float DotSize = (14.0f + 6.0f * Voice) * S;
        FSlateDrawElement::MakeBox(Out, LayerId + 1, Geo.ToPaintGeometry(FVector2D(DotSize, DotSize), FSlateLayoutTransform(Centre - FVector2D(DotSize, DotSize) * 0.5)),
            RoundBrush(), ESlateDrawEffect::None, Listen);
        // Five bars that jump with the voice (each a little out of step, so it reads as a live meter).
        for (int32 Bar = 0; Bar < 5; ++Bar)
        {
            const float Wobble = 0.55f + 0.45f * FMath::Sin(static_cast<float>(Time) * (9.0f + Bar * 2.3f) + Bar * 1.7f);
            const float Height = (4.0f + 30.0f * FMath::Clamp(Voice * 2.2f * Wobble, 0.0f, 1.0f)) * S;
            const FVector2D TopLeft((50.0 + Bar * 8.0) * S, Centre.Y - Height * 0.5);
            FSlateDrawElement::MakeBox(Out, LayerId + 1, Geo.ToPaintGeometry(FVector2D(5.0 * S, Height), FSlateLayoutTransform(TopLeft)),
                RoundBrush(), ESlateDrawEffect::None, Paper.CopyWithNewOpacity(0.55f + 0.45f * Voice));
        }
        return LayerId + 2;
    }

private:
    /** 1.5x the first cut: it has to read at a glance from across the screen. */
    static constexpr float Scale = 1.5f;
    static const FSlateBrush* RoundBrush()
    {
        static const FSlateRoundedBoxBrush Brush(FLinearColor::White, 18.0f);
        return &Brush;
    }
    static const FSlateBrush* RingBrush()
    {
        static const FSlateRoundedBoxBrush Brush(FLinearColor::Transparent, 45.0f, FLinearColor::White, 3.5f);
        return &Brush;
    }

    TAttribute<float> Level;
    TAttribute<bool> Thinking;
};

void SReflectionsNpcDialogueOverlay::Construct(const FArguments& InArgs)
{
    TWeakPtr<SReflectionsNpcDialogueOverlay> Weak = SharedThis(this);
    auto Alpha = [Weak]() { return Weak.IsValid() ? Weak.Pin()->LinesAlpha() : 0.0f; };

    SAssignNew(TypingBox, SEditableTextBox)
        .Font(Font(TEXT("Regular"), 16))
        .MinDesiredWidth(560.0f)
        .SelectAllTextWhenFocused(true)
        .ClearKeyboardFocusOnCommit(false)
        .RevertTextOnEscape(true)
        .OnTextCommitted_Lambda([Weak](const FText& Text, ETextCommit::Type Commit)
        {
            TSharedPtr<SReflectionsNpcDialogueOverlay> Self = Weak.Pin();
            if (!Self || !Self->bTyping) return;
            if (Commit == ETextCommit::OnEnter && !Text.IsEmptyOrWhitespace())
            {
                const FString Line = Text.ToString();
                Self->CloseTyping();
                if (Self->OnTypedLine) Self->OnTypedLine(Line);
            }
            else if (Commit == ETextCommit::OnCleared || Commit == ETextCommit::OnEnter || Commit == ETextCommit::OnUserMovedFocus)
            {
                Self->CloseTyping();
                if (Self->OnTypingCancelled) Self->OnTypingCancelled();
            }
        });

    ChildSlot
    .HAlign(HAlign_Center)
    .VAlign(VAlign_Bottom)
    .Padding(FMargin(40.0f, 0.0f, 40.0f, BottomMargin))
    [
        SNew(SBox)
        .MaxDesiredWidth(980.0f)
        [
            SNew(SVerticalBox)
            // One-time notice about AI voices.
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 0, 0, 10)
            [
                SNew(SBorder)
                .Visibility_Lambda([Weak]() { return Weak.IsValid() && Weak.Pin()->NoticeAlpha() > 0.0f ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
                .BorderBackgroundColor_Lambda([Weak]() { return FSlateColor(FLinearColor(0.02f, 0.02f, 0.03f, 0.75f * (Weak.IsValid() ? Weak.Pin()->NoticeAlpha() : 0.0f))); })
                .Padding(FMargin(14, 7))
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Italic"), 12))
                    .AutoWrapText(true)
                    .Justification(ETextJustify::Center)
                    .Text_Lambda([Weak]() { return Weak.IsValid() ? Weak.Pin()->Notice : FText::GetEmpty(); })
                    .ColorAndOpacity_Lambda([Weak]() { return FSlateColor(WithAlpha(Muted, Weak.IsValid() ? Weak.Pin()->NoticeAlpha() : 0.0f)); })
                ]
            ]
            // Where an NPC pointed.
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 0, 0, 8)
            [
                SNew(STextBlock)
                .Visibility_Lambda([Weak]() { return Weak.IsValid() && FPlatformTime::Seconds() < Weak.Pin()->HintUntil ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                .Font(Font(TEXT("Bold"), 16))
                .ShadowOffset(FVector2D(1.0, 1.0))
                .Text_Lambda([Weak]() { return Weak.IsValid() ? Weak.Pin()->HintLine : FText::GetEmpty(); })
                .ColorAndOpacity(FSlateColor(Gold))
            ]
            // Subtitles: the player's line, then the NPC's reply.
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
            [
                SNew(SBorder)
                .Visibility_Lambda([Weak, Alpha]() { return Alpha() > 0.0f && Weak.IsValid() && (!Weak.Pin()->NpcLine.IsEmpty() || !Weak.Pin()->PlayerLine.IsEmpty()) ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
                .BorderBackgroundColor_Lambda([Alpha]() { return FSlateColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f * Alpha())); })
                .Padding(FMargin(18, 10, 18, 12))
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 4)
                    [
                        SNew(STextBlock)
                        .Visibility_Lambda([Weak]() { return Weak.IsValid() && !Weak.Pin()->PlayerLine.IsEmpty() ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                        .Font(Font(TEXT("Regular"), 15))
                        .WrapTextAt(760.0f)
                        .Text_Lambda([Weak]() { return Weak.IsValid() ? FText::Format(LOCTEXT("PlayerLine", "You: {0}"), FText::FromString(Weak.Pin()->PlayerLine)) : FText::GetEmpty(); })
                        .ColorAndOpacity_Lambda([Alpha]() { return FSlateColor(WithAlpha(Muted, Alpha())); })
                    ]
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        SNew(SHorizontalBox)
                        .Visibility_Lambda([Weak]() { return Weak.IsValid() && !Weak.Pin()->NpcLine.IsEmpty() ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                        + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top).Padding(0, 0, 8, 0)
                        [
                            SNew(SVerticalBox)
                            + SVerticalBox::Slot().AutoHeight()
                            [
                                SNew(STextBlock)
                                .Font(Font(TEXT("Bold"), 18))
                                .Text_Lambda([Weak]() { return Weak.IsValid() ? FText::FromString(Weak.Pin()->NpcSpeaker + TEXT(":")) : FText::GetEmpty(); })
                                .ColorAndOpacity_Lambda([Alpha]() { return FSlateColor(WithAlpha(Gold, Alpha())); })
                            ]
                        ]
                        + SHorizontalBox::Slot().FillWidth(1.0f)
                        [
                            SNew(STextBlock)
                            .Font(Font(TEXT("Regular"), 18))
                            .WrapTextAt(680.0f)
                            .AutoWrapText(true)  // a long speaker name ("Sergeant Maud Kettering") leaves less than 680
                            .Text_Lambda([Weak]() { return Weak.IsValid() ? FText::FromString(Weak.Pin()->NpcLine) : FText::GetEmpty(); })
                            .ColorAndOpacity_Lambda([Alpha]() { return FSlateColor(WithAlpha(Paper, Alpha())); })
                        ]
                    ]
                ]
            ]
            // Listening (the mic is open) or thinking (waiting for the reply): the player can see the NPC hears them.
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 12, 0, 0)
            [
                SNew(SBorder)
                .Visibility_Lambda([Weak]() { return Weak.IsValid() && (Weak.Pin()->bListening || !Weak.Pin()->ThinkingWho.IsEmpty()) ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
                .BorderBackgroundColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.6f))
                .Padding(FMargin(16, 8, 20, 8))
                [
                    SNew(SHorizontalBox)
                    + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 14, 0)
                    [
                        SNew(SReflectionsListeningMeter)
                        .Level_Lambda([Weak]() { return Weak.IsValid() ? Weak.Pin()->MicLevel : 0.0f; })
                        .Thinking_Lambda([Weak]() { return Weak.IsValid() && !Weak.Pin()->bListening && !Weak.Pin()->ThinkingWho.IsEmpty(); })
                    ]
                    + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight()
                        [
                            SNew(STextBlock)
                            .Font(Font(TEXT("Bold"), 20))
                            .Text_Lambda([Weak]()
                            {
                                if (!Weak.IsValid()) return FText::GetEmpty();
                                const TSharedPtr<SReflectionsNpcDialogueOverlay> Self = Weak.Pin();
                                if (Self->bListening) return LOCTEXT("Listening", "Listening... say anything");
                                const int32 Dots = 1 + static_cast<int32>(FPlatformTime::Seconds() * 2.5) % 3;
                                return FText::Format(LOCTEXT("Thinking", "{0} is thinking{1}"), Self->ThinkingWho, FText::FromString(FString::ChrN(Dots, TEXT('.'))));
                            })
                            .ColorAndOpacity_Lambda([Weak]() { return FSlateColor(Weak.IsValid() && Weak.Pin()->bListening ? Listen : Paper); })
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 2, 0, 0)
                        [
                            SNew(STextBlock)
                            .Visibility_Lambda([Weak]() { return Weak.IsValid() && Weak.Pin()->bListening ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                            .Font(Font(TEXT("Regular"), 12))
                            .Text(LOCTEXT("ListeningHint", "Let go to send"))
                            .ColorAndOpacity(FSlateColor(Muted))
                        ]
                    ]
                ]
            ]
            // Typed line.
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 12, 0, 0)
            [
                SNew(SBox)
                .Visibility_Lambda([Weak]() { return Weak.IsValid() && Weak.Pin()->bTyping ? EVisibility::Visible : EVisibility::Collapsed; })
                [
                    TypingBox.ToSharedRef()
                ]
            ]
            // Prompt and listening / thinking indicator.
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 10, 0, 0)
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 10, 0)
                [
                    SNew(STextBlock)
                    .Visibility_Lambda([Weak]() { return Weak.IsValid() && !Weak.Pin()->StatusText.IsEmpty() ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                    .Font(Font(TEXT("Bold"), 13))
                    .Text_Lambda([Weak]() { return Weak.IsValid() ? Weak.Pin()->StatusText : FText::GetEmpty(); })
                    .ColorAndOpacity(FSlateColor(FLinearColor(1.0f, 0.45f, 0.35f, 0.95f)))
                ]
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
                [
                    SNew(SBorder)
                    .Visibility_Lambda([Weak]() { return Weak.IsValid() && !Weak.Pin()->Prompt.IsEmpty() && !Weak.Pin()->bTyping ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                    .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
                    .BorderBackgroundColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.45f))
                    .Padding(FMargin(12, 5))
                    [
                        SNew(STextBlock)
                        .Font(Font(TEXT("Bold"), 12))
                        .Text_Lambda([Weak]() { return Weak.IsValid() ? Weak.Pin()->Prompt : FText::GetEmpty(); })
                        .ColorAndOpacity(FSlateColor(FLinearColor(0.93f, 0.89f, 0.80f, 0.9f)))
                    ]
                ]
            ]
        ]
    ];
}

void SReflectionsNpcDialogueOverlay::Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime)
{
    SCompoundWidget::Tick(AllottedGeometry, InCurrentTime, InDeltaTime);
    // The meter jumps up with the voice and falls back gently.
    const float Rate = TargetMicLevel > MicLevel ? 18.0f : 5.0f;
    MicLevel = FMath::FInterpTo(MicLevel, TargetMicLevel, InDeltaTime, Rate);
    // Collapsed parts take no height, so this follows whatever shows (notice, hint, lines, typing box, prompt).
    const float Height = ChildSlot.GetWidget()->GetDesiredSize().Y;
    PanelTopFromBottom = Height > 1.0f ? BottomMargin + Height : 0.0f;
}

void SReflectionsNpcDialogueOverlay::ShowLine(const FString& Speaker, const FString& Text, bool bPlayer, bool bAi)
{
    if (bPlayer)
    {
        PlayerLine = Text;
        NpcLine.Reset();
    }
    else
    {
        NpcSpeaker = Speaker;
        NpcLine = Text;
        bNpcAi = bAi;
    }
    const int32 Words = Text.Len() / 6;
    LineHoldSeconds = FMath::Clamp(2.5 + Words * 0.3, 3.0, 8.0);
    LinesShownAt = FPlatformTime::Seconds();
}

void SReflectionsNpcDialogueOverlay::ClearLines()
{
    PlayerLine.Reset();
    NpcLine.Reset();
    LinesShownAt = -1.0e9;
}

float SReflectionsNpcDialogueOverlay::LinesAlpha() const
{
    const double Age = FPlatformTime::Seconds() - LinesShownAt;
    if (Age < LineHoldSeconds) return 1.0f;
    return static_cast<float>(FMath::Clamp(1.0 - (Age - LineHoldSeconds) / 0.6, 0.0, 1.0));
}

void SReflectionsNpcDialogueOverlay::ShowNotice(const FText& InNotice, double Seconds)
{
    Notice = InNotice;
    NoticeUntil = FPlatformTime::Seconds() + Seconds;
}

float SReflectionsNpcDialogueOverlay::NoticeAlpha() const
{
    return static_cast<float>(FMath::Clamp((NoticeUntil - FPlatformTime::Seconds()) / 0.6, 0.0, 1.0));
}

void SReflectionsNpcDialogueOverlay::OpenTyping(const FText& Hint)
{
    bTyping = true;
    TypingBox->SetText(FText::GetEmpty());
    TypingBox->SetHintText(Hint);
    if (FSlateApplication::IsInitialized())
    {
        FSlateApplication::Get().SetAllUserFocus(TypingBox, EFocusCause::SetDirectly);
    }
}

void SReflectionsNpcDialogueOverlay::CloseTyping()
{
    bTyping = false;
}

#undef LOCTEXT_NAMESPACE
