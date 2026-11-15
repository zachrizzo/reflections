#include "Voice/ReflectionsNpcDialogueOverlay.h"
#include "Framework/Application/SlateApplication.h"
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
    .Padding(FMargin(40.0f, 0.0f, 40.0f, 215.0f))  // above the spell bar (health, mana, spell slots)
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
                            + SVerticalBox::Slot().AutoHeight()
                            [
                                SNew(STextBlock)
                                .Visibility_Lambda([Weak]() { return Weak.IsValid() && Weak.Pin()->bNpcAi ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                                .Font(Font(TEXT("Regular"), 9))
                                .Text(LOCTEXT("AiTag", "AI VOICE"))
                                .ColorAndOpacity_Lambda([Alpha]() { return FSlateColor(WithAlpha(FLinearColor(0.7f, 0.7f, 0.72f, 0.8f), Alpha())); })
                            ]
                        ]
                        + SHorizontalBox::Slot().FillWidth(1.0f)
                        [
                            SNew(STextBlock)
                            .Font(Font(TEXT("Regular"), 18))
                            .WrapTextAt(680.0f)
                            .Text_Lambda([Weak]() { return Weak.IsValid() ? FText::FromString(Weak.Pin()->NpcLine) : FText::GetEmpty(); })
                            .ColorAndOpacity_Lambda([Alpha]() { return FSlateColor(WithAlpha(Paper, Alpha())); })
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
