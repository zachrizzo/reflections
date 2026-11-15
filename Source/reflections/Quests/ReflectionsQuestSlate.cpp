#include "Quests/ReflectionsQuestSlate.h"

#include "Brushes/SlateColorBrush.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFlow/ReflectionsGameFlowSlate.h"
#include "GameFramework/Character.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Components/CapsuleComponent.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"
#include "Quests/ReflectionsQuestSubsystem.h"
#include "Quests/ReflectionsQuestWorldSubsystem.h"
#include "Rendering/DrawElements.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "ReflectionsQuests"

namespace ReflectionsQuestStyle
{
    // The game flow's palette: parchment on ink, gold accent.
    static const FLinearColor Ink(0.012f, 0.012f, 0.018f, 1.0f);
    static const FLinearColor Paper(0.93f, 0.89f, 0.80f, 1.0f);
    static const FLinearColor PaperDim(0.62f, 0.59f, 0.53f, 1.0f);
    static const FLinearColor Gold(0.95f, 0.72f, 0.28f, 1.0f);
    static const FLinearColor Red(0.78f, 0.10f, 0.08f, 1.0f);
    static const FLinearColor Frost(0.70f, 0.85f, 1.0f, 1.0f);

    static const FSlateBrush* Solid()
    {
        static const FSlateColorBrush Brush(FLinearColor::White);
        return &Brush;
    }

    static const FSlateBrush* Rounded(float Radius)
    {
        static TMap<int32, TSharedPtr<FSlateRoundedBoxBrush>> Cache;
        TSharedPtr<FSlateRoundedBoxBrush>& Entry = Cache.FindOrAdd(FMath::RoundToInt(Radius));
        if (!Entry.IsValid()) Entry = MakeShared<FSlateRoundedBoxBrush>(FLinearColor::White, Radius);
        return Entry.Get();
    }

    static const FSlateBrush* Ring(float Radius)
    {
        static TMap<int32, TSharedPtr<FSlateRoundedBoxBrush>> Cache;
        TSharedPtr<FSlateRoundedBoxBrush>& Entry = Cache.FindOrAdd(FMath::RoundToInt(Radius));
        if (!Entry.IsValid()) Entry = MakeShared<FSlateRoundedBoxBrush>(FLinearColor::Transparent, Radius, FLinearColor::White, 2.0f);
        return Entry.Get();
    }

    static FSlateFontInfo Font(const TCHAR* Weight, int32 Size, int32 LetterSpacing = 0)
    {
        FSlateFontInfo Info = FCoreStyle::GetDefaultFontStyle(Weight, Size);
        Info.LetterSpacing = LetterSpacing;
        return Info;
    }

    static TSharedRef<STextBlock> Text(const FText& InText, const FSlateFontInfo& InFont, const FLinearColor& Color, bool bWrap = false)
    {
        return SNew(STextBlock).Text(InText).Font(InFont).ColorAndOpacity(FSlateColor(Color)).AutoWrapText(bWrap);
    }

    static TSharedRef<SWidget> Rule(const FLinearColor& Color, float Width, float Height = 2.0f)
    {
        return SNew(SBox).WidthOverride(Width).HeightOverride(Height)[SNew(SImage).Image(Solid()).ColorAndOpacity(Color)];
    }

    static FLinearColor SideColor(EReflectionsQuestSide Side)
    {
        switch (Side)
        {
        case EReflectionsQuestSide::Pewterside: return FLinearColor(0.55f, 0.58f, 0.62f, 1.0f);
        case EReflectionsQuestSide::Giltside: return Gold;
        case EReflectionsQuestSide::Frostside: return Frost;
        default: return PaperDim;
        }
    }

    static FText SideText(EReflectionsQuestSide Side)
    {
        switch (Side)
        {
        case EReflectionsQuestSide::Pewterside: return LOCTEXT("SidePewter", "PEWTERSIDE");
        case EReflectionsQuestSide::Giltside: return LOCTEXT("SideGilt", "GILTSIDE");
        case EReflectionsQuestSide::Frostside: return LOCTEXT("SideFrost", "FROSTSIDE");
        default: return LOCTEXT("SideAll", "ALL OF LANTHORNE");
        }
    }

    static FText WorldSideText(EReflectionsWorld World)
    {
        return World == EReflectionsWorld::Gray ? LOCTEXT("WSidePewter", "Pewterside")
            : World == EReflectionsWorld::White ? LOCTEXT("WSideFrost", "Frostside") : LOCTEXT("WSideGilt", "Giltside");
    }

    static FVector2D Measure(const FString& S, const FSlateFontInfo& InFont)
    {
        if (!FSlateApplication::IsInitialized()) return FVector2D(S.Len() * InFont.Size * 0.6f, InFont.Size * 1.3f);
        const auto Size = FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(S, InFont);
        return FVector2D(Size.X, Size.Y);
    }
}

using namespace ReflectionsQuestStyle;

// ---- Markers -------------------------------------------------------------------------------------------------

void SReflectionsQuestMarkers::Construct(const FArguments& InArgs)
{
    Owner = InArgs._Owner;
    SetVisibility(EVisibility::HitTestInvisible);
}

namespace
{
    FVector HeadPoint(AActor* Actor)
    {
        if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Actor))
        {
            if (UReflectionsNpcReactionComponent* C = Npcs->FindNpc(Actor))
            {
                if (ACharacter* Body = Cast<ACharacter>(C->GetMovementCharacter()))
                {
                    return Body->GetActorLocation() + FVector(0, 0, Body->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() + 45.0f);
                }
            }
        }
        if (const ACharacter* Character = Cast<ACharacter>(Actor))
        {
            return Character->GetActorLocation() + FVector(0, 0, Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() + 45.0f);
        }
        return Actor->GetActorLocation() + FVector(0, 0, 210.0f);
    }

    void DrawPill(FSlateWindowElementList& Out, int32 Layer, const FGeometry& Geo, const FVector2D& Center, const FString& S, const FSlateFontInfo& InFont,
        const FLinearColor& TextColor, float Alpha)
    {
        const FVector2D TextSize = Measure(S, InFont);
        const FVector2D Pad(12.0f, 5.0f);
        const FVector2D Size = TextSize + Pad * 2.0f;
        const FVector2D TopLeft = Center - Size * 0.5f;
        FSlateDrawElement::MakeBox(Out, Layer, Geo.ToPaintGeometry(Size, FSlateLayoutTransform(TopLeft)), Rounded(8.0f), ESlateDrawEffect::None,
            FLinearColor(0.0f, 0.0f, 0.0f, 0.62f * Alpha));
        FSlateDrawElement::MakeText(Out, Layer + 1, Geo.ToPaintGeometry(TextSize, FSlateLayoutTransform(TopLeft + Pad)), S, InFont, ESlateDrawEffect::None,
            TextColor.CopyWithNewOpacity(Alpha));
    }
}

int32 SReflectionsQuestMarkers::OnPaint(const FPaintArgs& Args, const FGeometry& Geo, const FSlateRect& MyCullingRect, FSlateWindowElementList& Out,
    int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
    UReflectionsQuestWorldSubsystem* Self = Owner.Get();
    APlayerController* PC = Self ? Self->GetController() : nullptr;
    UWorld* World = Self ? Self->GetWorld() : nullptr;
    UGameViewportClient* Viewport = World ? World->GetGameViewport() : nullptr;
    if (!PC || !Viewport || !PC->PlayerCameraManager || !Self->ShouldShowHud()) return LayerId;

    FVector2D ViewportSize;
    Viewport->GetViewportSize(ViewportSize);
    const FVector2D LocalSize = FVector2D(Geo.GetLocalSize());
    if (ViewportSize.X < 1.0 || LocalSize.X < 1.0) return LayerId;
    const FVector2D ToLocal = LocalSize / ViewportSize;
    const FVector CamLoc = PC->PlayerCameraManager->GetCameraLocation();
    const FRotator CamRot = PC->PlayerCameraManager->GetCameraRotation();
    const FVector Forward = CamRot.Vector();
    const FVector Right = FRotationMatrix(CamRot).GetScaledAxis(EAxis::Y);
    const FVector Up = FRotationMatrix(CamRot).GetScaledAxis(EAxis::Z);
    const float Pulse = 0.85f + 0.15f * FMath::Sin(Self->GetClock() * 4.0f);

    // Marks over quest people.
    for (const FReflectionsQuestMark& Mark : Self->GetMarks())
    {
        AActor* A = Mark.Actor.Get();
        if (!A) continue;
        const FVector Head = HeadPoint(A);
        if (FVector::DotProduct(Head - CamLoc, Forward) <= 0.0) continue;
        FVector2D Screen;
        if (!PC->ProjectWorldLocationToScreen(Head, Screen, false)) continue;
        const FVector2D P = Screen * ToLocal;
        const float Dist = FVector::Dist(CamLoc, Head);
        const float Scale = FMath::GetMappedRangeValueClamped(FVector2f(400.0f, 4000.0f), FVector2f(1.0f, 0.6f), Dist);
        const float Size = 30.0f * Scale;
        const FLinearColor Color = Mark.Glyph == TEXT('?') ? Gold : Mark.Glyph == TEXT('!') ? Gold : Paper;
        FSlateDrawElement::MakeBox(Out, LayerId, Geo.ToPaintGeometry(FVector2D(Size, Size), FSlateLayoutTransform(P - FVector2D(Size, Size) * 0.5f)),
            Rounded(Size * 0.5f), ESlateDrawEffect::None, FLinearColor(0.0f, 0.0f, 0.0f, 0.55f));
        FSlateDrawElement::MakeBox(Out, LayerId + 1, Geo.ToPaintGeometry(FVector2D(Size, Size), FSlateLayoutTransform(P - FVector2D(Size, Size) * 0.5f)),
            Ring(Size * 0.5f), ESlateDrawEffect::None, Color.CopyWithNewOpacity(Pulse));
        const FString Glyph = Mark.Glyph == TEXT('*') ? FString(TEXT("...")) : FString(1, &Mark.Glyph);
        const FSlateFontInfo GlyphFont = Font(TEXT("Bold"), FMath::RoundToInt((Mark.Glyph == TEXT('*') ? 11.0f : 17.0f) * Scale));
        const FVector2D GlyphSize = Measure(Glyph, GlyphFont);
        FSlateDrawElement::MakeText(Out, LayerId + 2, Geo.ToPaintGeometry(GlyphSize, FSlateLayoutTransform(P - GlyphSize * 0.5f)), Glyph, GlyphFont,
            ESlateDrawEffect::None, Color);
    }

    // Talk prompt by the person's head.
    if (AActor* Prompt = Self->GetPromptTarget())
    {
        const FText PromptText = Self->GetPromptText();
        FVector2D Screen;
        const FVector Head = HeadPoint(Prompt) + FVector(0, 0, 10);
        if (!PromptText.IsEmpty() && FVector::DotProduct(Head - CamLoc, Forward) > 0.0 && PC->ProjectWorldLocationToScreen(Head, Screen, false))
        {
            DrawPill(Out, LayerId + 3, Geo, Screen * ToLocal + FVector2D(0, 34), PromptText.ToString(), Font(TEXT("Bold"), 13, 40), Paper, 1.0f);
        }
    }

    // Pointer to the tracked objective.
    const FReflectionsQuestTarget& Target = Self->GetTrackedTarget();
    APawn* Hero = Self->GetHero();
    if (!Target.bValid || Target.bOtherSide || !Hero) return LayerId + 4;
    const float Meters = FVector::Dist(Hero->GetActorLocation(), Target.Location) / 100.0f;
    if (Meters * 100.0f < FMath::Max(150.0f, Target.Radius * 0.5f)) return LayerId + 4;  // arrived
    const FVector Aim = Target.Location + FVector(0, 0, 120.0f);
    const FVector Dir = Aim - CamLoc;
    const FVector2D Center = LocalSize * 0.5f;
    const float Margin = 70.0f;
    FVector2D P;
    bool bOnScreen = false;
    FVector2D Screen;
    if (FVector::DotProduct(Dir, Forward) > 0.0 && PC->ProjectWorldLocationToScreen(Aim, Screen, false))
    {
        P = Screen * ToLocal;
        bOnScreen = P.X > Margin && P.X < LocalSize.X - Margin && P.Y > Margin && P.Y < LocalSize.Y - Margin;
    }
    if (!bOnScreen)
    {
        FVector2D D(FVector::DotProduct(Dir, Right), -FVector::DotProduct(Dir, Up));
        if (FVector::DotProduct(Dir, Forward) <= 0.0 && D.IsNearlyZero()) D = FVector2D(0, 1);
        D.Normalize();
        const FVector2D Half = Center - FVector2D(Margin, Margin);
        const float T = FMath::Min(D.X != 0.0 ? Half.X / FMath::Abs(D.X) : 1.0e6f, D.Y != 0.0 ? Half.Y / FMath::Abs(D.Y) : 1.0e6f);
        P = Center + D * T;
    }
    const float Size = 22.0f;
    FSlateDrawElement::MakeRotatedBox(Out, LayerId + 4, Geo.ToPaintGeometry(FVector2D(Size, Size), FSlateLayoutTransform(P - FVector2D(Size, Size) * 0.5f)),
        Solid(), ESlateDrawEffect::None, PI * 0.25f, TOptional<FVector2D>(), FSlateDrawElement::RelativeToElement, Gold.CopyWithNewOpacity(0.92f * Pulse));
    FSlateDrawElement::MakeRotatedBox(Out, LayerId + 5, Geo.ToPaintGeometry(FVector2D(Size * 0.45f, Size * 0.45f), FSlateLayoutTransform(P - FVector2D(Size, Size) * 0.225f)),
        Solid(), ESlateDrawEffect::None, PI * 0.25f, TOptional<FVector2D>(), FSlateDrawElement::RelativeToElement, Ink);
    if (!bOnScreen)
    {
        // A short arrow from the diamond toward the target.
        const FVector2D D = (P - Center).GetSafeNormal();
        const FVector2D Tip = P + D * 24.0f;
        const FVector2D Side(-D.Y, D.X);
        TArray<FVector2D> Arrow = {Tip - D * 10.0f + Side * 7.0f, Tip, Tip - D * 10.0f - Side * 7.0f};
        FSlateDrawElement::MakeLines(Out, LayerId + 5, Geo.ToPaintGeometry(), Arrow, ESlateDrawEffect::None, Gold, true, 3.0f);
    }
    const FString Label = FString::Printf(TEXT("%d m"), FMath::RoundToInt(Meters));
    const FVector2D LabelAt = P + FVector2D(0, bOnScreen ? 30.0f : (P.Y > Center.Y ? -32.0f : 32.0f));
    DrawPill(Out, LayerId + 6, Geo, LabelAt, Label, Font(TEXT("Bold"), 12, 40), Gold, 0.95f);
    return LayerId + 8;
}

// ---- HUD -----------------------------------------------------------------------------------------------------

void SReflectionsQuestHud::Construct(const FArguments& InArgs)
{
    Owner = InArgs._Owner;
    TWeakObjectPtr<UReflectionsQuestWorldSubsystem> Weak = Owner;
    SetVisibility(EVisibility::HitTestInvisible);
    const float Width = 300.0f;

    TSharedRef<SVerticalBox> Lines = SNew(SVerticalBox);
    for (int32 i = 0; i < 7; ++i)
    {
        Lines->AddSlot().AutoHeight().Padding(0, 5, 0, 0)
        [
            SNew(SHorizontalBox)
            .Visibility_Lambda([Weak, i]() { return Weak.IsValid() && Weak->GetTrackerLines().IsValidIndex(i) ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top).Padding(0, 5, 9, 0)
            [
                SNew(SBox).WidthOverride(9).HeightOverride(9)
                [
                    SNew(SImage).Image(Rounded(2.0f)).ColorAndOpacity_Lambda([Weak, i]()
                    {
                        const TArray<FReflectionsTrackerLine>* L = Weak.IsValid() ? &Weak->GetTrackerLines() : nullptr;
                        if (!L || !L->IsValidIndex(i)) return FSlateColor(Paper);
                        return FSlateColor((*L)[i].bDone ? Gold : (*L)[i].bOptional ? PaperDim.CopyWithNewOpacity(0.5f) : FLinearColor(1, 1, 1, 0.22f));
                    })
                ]
            ]
            + SHorizontalBox::Slot().FillWidth(1.0f)
            [
                SNew(STextBlock)
                .Font(Font(TEXT("Regular"), 14))
                .AutoWrapText(true)
                .Text_Lambda([Weak, i]()
                {
                    const TArray<FReflectionsTrackerLine>* L = Weak.IsValid() ? &Weak->GetTrackerLines() : nullptr;
                    if (!L || !L->IsValidIndex(i)) return FText::GetEmpty();
                    return (*L)[i].bOptional && !(*L)[i].bDone ? FText::Format(LOCTEXT("TrackOptional", "{0} (optional)"), (*L)[i].Text) : (*L)[i].Text;
                })
                .ColorAndOpacity_Lambda([Weak, i]()
                {
                    const TArray<FReflectionsTrackerLine>* L = Weak.IsValid() ? &Weak->GetTrackerLines() : nullptr;
                    if (!L || !L->IsValidIndex(i)) return FSlateColor(Paper);
                    return FSlateColor((*L)[i].bDone ? PaperDim : (*L)[i].bOptional ? PaperDim : Paper);
                })
            ]
        ];
    }

    ChildSlot
    [
        SNew(SOverlay)
        .Visibility_Lambda([Weak]() { return Weak.IsValid() && Weak->ShouldShowHud() ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })

        + SOverlay::Slot()
        [
            SNew(SReflectionsQuestMarkers).Owner(Owner)
        ]

        // Tracker: right side, under game flow's stack (Tarnish meter, toast, tip card end near y 255).
        + SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(FMargin(0, 272, 24, 0))
        [
            SNew(SBorder)
            .Visibility_Lambda([Weak]() { return Weak.IsValid() && !Weak->GetTrackedTitle().IsEmpty() ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
            .BorderImage(Rounded(8.0f))
            .BorderBackgroundColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.45f))
            .Padding(FMargin(14, 10, 14, 12))
            [
                SNew(SBox).WidthOverride(Width)
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        SNew(SHorizontalBox)
                        + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0, 0, 8, 0)
                        [
                            SNew(SBox).WidthOverride(8).HeightOverride(8)[SNew(SImage).Image(Rounded(1.0f)).ColorAndOpacity(Gold)]
                        ]
                        + SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
                        [
                            SNew(STextBlock)
                            .Font(Font(TEXT("Bold"), 12, 250))
                            .ColorAndOpacity(FSlateColor(Gold))
                            .Text_Lambda([Weak]() { return Weak.IsValid() ? Weak->GetTrackedTitle().ToUpper() : FText::GetEmpty(); })
                        ]
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0, 2, 0, 0)[Lines]
                    + SVerticalBox::Slot().AutoHeight().Padding(18, 6, 0, 0)
                    [
                        SNew(STextBlock)
                        .Font(Font(TEXT("Bold"), 12, 30))
                        .ColorAndOpacity_Lambda([Weak]()
                        {
                            return FSlateColor(Weak.IsValid() && Weak->GetTrackedTarget().bOtherSide ? Frost : PaperDim);
                        })
                        .Visibility_Lambda([Weak]() { return Weak.IsValid() && Weak->GetTrackedTarget().bValid ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                        .Text_Lambda([Weak]()
                        {
                            const UReflectionsQuestWorldSubsystem* Self = Weak.Get();
                            const APawn* Hero = Self ? Self->GetHero() : nullptr;
                            if (!Self || !Hero || !Self->GetTrackedTarget().bValid) return FText::GetEmpty();
                            const FReflectionsQuestTarget& T = Self->GetTrackedTarget();
                            if (T.bOtherSide) return FText::Format(LOCTEXT("TrackOtherSide", "On {0}: step through"), WorldSideText(T.Side));
                            return FText::Format(LOCTEXT("TrackDistance", "{0} m away"), FMath::RoundToInt(FVector::Dist(Hero->GetActorLocation(), T.Location) / 100.0f));
                        })
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(18, 8, 0, 0)
                    [
                        SNew(STextBlock)
                        .Font(Font(TEXT("Regular"), 11, 60))
                        .ColorAndOpacity(FSlateColor(PaperDim.CopyWithNewOpacity(0.8f)))
                        .Text_Lambda([Weak]()
                        {
                            return Weak.IsValid() && Weak->IsUsingGamepad() ? LOCTEXT("JournalHintPad", "Start > Journal") : LOCTEXT("JournalHintKey", "L  Journal");
                        })
                    ]
                ]
            ]
        ]

        // Banner: top centre.
        + SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Top).Padding(FMargin(0, 96, 0, 0))
        [
            SNew(SBorder)
            .BorderImage(Rounded(10.0f))
            .Visibility_Lambda([Weak]()
            {
                FText K, T, D; FLinearColor C; float A = 0.0f;
                return Weak.IsValid() && Weak->GetBanner(K, T, D, C, A) ? EVisibility::HitTestInvisible : EVisibility::Collapsed;
            })
            .ColorAndOpacity_Lambda([Weak]()
            {
                FText K, T, D; FLinearColor C; float A = 0.0f;
                if (Weak.IsValid()) Weak->GetBanner(K, T, D, C, A);
                return FLinearColor(1, 1, 1, A);
            })
            .BorderBackgroundColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.62f))
            .Padding(FMargin(36, 14, 36, 16))
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Bold"), 12, 400))
                    .ColorAndOpacity_Lambda([Weak]()
                    {
                        FText K, T, D; FLinearColor C = Gold; float A = 0.0f;
                        if (Weak.IsValid()) Weak->GetBanner(K, T, D, C, A);
                        return FSlateColor(C);
                    })
                    .Text_Lambda([Weak]() { FText K, T, D; FLinearColor C; float A; if (Weak.IsValid()) Weak->GetBanner(K, T, D, C, A); return K; })
                ]
                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 6, 0, 0)
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Bold"), 24, 40))
                    .ColorAndOpacity(FSlateColor(Paper))
                    .Text_Lambda([Weak]() { FText K, T, D; FLinearColor C; float A; if (Weak.IsValid()) Weak->GetBanner(K, T, D, C, A); return T; })
                ]
                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0, 6, 0, 0)
                [
                    SNew(SBox).MaxDesiredWidth(560)
                    [
                        SNew(STextBlock)
                        .Font(Font(TEXT("Regular"), 14))
                        .Justification(ETextJustify::Center)
                        .AutoWrapText(true)
                        .ColorAndOpacity(FSlateColor(PaperDim))
                        .Visibility_Lambda([Weak]() { FText K, T, D; FLinearColor C; float A; return Weak.IsValid() && Weak->GetBanner(K, T, D, C, A) && !D.IsEmpty() ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
                        .Text_Lambda([Weak]() { FText K, T, D; FLinearColor C; float A; if (Weak.IsValid()) Weak->GetBanner(K, T, D, C, A); return D; })
                    ]
                ]
            ]
        ]

        // Narration subtitle: above the dialogue overlay and the spell bar.
        + SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Bottom)
            .Padding(TAttribute<FMargin>::CreateLambda([Weak]() { return FMargin(0, 0, 0, 300.0f + (Weak.IsValid() ? Weak->GetSubtitleLift() : 0.0f)); }))
        [
            SNew(SBorder)
            .BorderImage(Rounded(8.0f))
            .BorderBackgroundColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f))
            .Padding(FMargin(18, 8))
            .Visibility_Lambda([Weak]() { FText S, L; float A; return Weak.IsValid() && Weak->GetSubtitle(S, L, A) ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
            .ColorAndOpacity_Lambda([Weak]() { FText S, L; float A = 0.0f; if (Weak.IsValid()) Weak->GetSubtitle(S, L, A); return FLinearColor(1, 1, 1, A); })
            [
                SNew(SBox).MaxDesiredWidth(720)
                [
                    SNew(STextBlock)
                    .Font(Font(TEXT("Regular"), 16))
                    .AutoWrapText(true)
                    .Justification(ETextJustify::Center)
                    .ColorAndOpacity(FSlateColor(Paper))
                    .Text_Lambda([Weak]()
                    {
                        FText S, L; float A;
                        if (!Weak.IsValid() || !Weak->GetSubtitle(S, L, A)) return FText::GetEmpty();
                        return S.IsEmpty() ? L : FText::Format(LOCTEXT("SubtitleFmt", "{0}:  {1}"), S, L);
                    })
                ]
            ]
        ]
    ];
}

// ---- Journal -------------------------------------------------------------------------------------------------

void SReflectionsQuestJournal::Construct(const FArguments& InArgs)
{
    Owner = InArgs._Owner;
    TWeakObjectPtr<UReflectionsQuestWorldSubsystem> Weak = Owner;
    SAssignNew(List, SVerticalBox);
    SAssignNew(Details, SBox);
    SetVisibility(TAttribute<EVisibility>::CreateLambda([Weak]() {
        return Weak.IsValid() && Weak->IsJournalOpen() ? EVisibility::Visible : EVisibility::Collapsed;
    }));

    ChildSlot
    [
        SNew(SOverlay)
        + SOverlay::Slot()
        [
            SNew(SImage).Image(Solid()).ColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f))
        ]
        + SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Center)
        [
            SNew(SBorder)
            .BorderImage(Rounded(12.0f))
            .BorderBackgroundColor(FLinearColor(0.01f, 0.01f, 0.015f, 0.92f))
            .Padding(FMargin(36, 30))
            [
                SNew(SBox).WidthOverride(1120).HeightOverride(640)
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        Text(LOCTEXT("JournalTitle", "JOURNAL"), Font(TEXT("Bold"), 30, 300), Paper)
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0, 8, 0, 18)[Rule(Red, 80.0f, 3.0f)]
                    + SVerticalBox::Slot().FillHeight(1.0f)
                    [
                        SNew(SHorizontalBox)
                        + SHorizontalBox::Slot().AutoWidth()
                        [
                            SNew(SBox).WidthOverride(380)
                            [
                                SNew(SScrollBox)
                                .ScrollBarVisibility(EVisibility::Collapsed)
                                + SScrollBox::Slot()[List.ToSharedRef()]
                            ]
                        ]
                        + SHorizontalBox::Slot().AutoWidth().Padding(26, 0)
                        [
                            SNew(SBox).WidthOverride(1.5f)[SNew(SImage).Image(Solid()).ColorAndOpacity(FLinearColor(1, 1, 1, 0.1f))]
                        ]
                        + SHorizontalBox::Slot().FillWidth(1.0f)
                        [
                            SNew(SScrollBox)
                            + SScrollBox::Slot()[Details.ToSharedRef()]
                        ]
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0, 16, 0, 0)
                    [
                        SNew(STextBlock)
                        .Font(Font(TEXT("Bold"), 12, 120))
                        .ColorAndOpacity(FSlateColor(PaperDim))
                        .Text_Lambda([Weak]()
                        {
                            return Weak.IsValid() && Weak->IsUsingGamepad()
                                ? LOCTEXT("JournalFooterPad", "D-pad  Choose     A  Track     B  Close")
                                : LOCTEXT("JournalFooterKey", "Arrows  Choose     Enter  Track     Esc / L  Close");
                        })
                    ]
                ]
            ]
        ]
    ];
}

void SReflectionsQuestJournal::Refresh()
{
    UReflectionsQuestWorldSubsystem* Self = Owner.Get();
    UReflectionsQuestSubsystem* Quests = Self ? UReflectionsQuestSubsystem::Get(Self) : nullptr;
    if (!Quests) return;
    List->ClearChildren();
    Buttons.Reset();
    Ids = Quests->GetJournalQuests();
    if (Selected.IsNone() || !Ids.Contains(Selected)) Selected = Quests->GetTrackedQuest();
    if (!Ids.Contains(Selected)) Selected = Ids.IsEmpty() ? NAME_None : Ids[0];

    int32 LastGroup = -1;
    for (const FName& Id : Ids)
    {
        const FReflectionsQuestDef* Def = Quests->FindQuest(Id);
        const EReflectionsQuestStatus Status = Quests->GetStatus(Id);
        if (!Def) continue;
        const int32 Group = Status == EReflectionsQuestStatus::Completed || Status == EReflectionsQuestStatus::Failed ? 1 : 0;
        if (Group != LastGroup)
        {
            List->AddSlot().AutoHeight().Padding(0, LastGroup < 0 ? 0 : 16, 0, 8)
            [
                Text(Group == 0 ? LOCTEXT("JournalOpen", "UNDER WAY") : LOCTEXT("JournalDone", "FINISHED"), Font(TEXT("Bold"), 12, 300), Gold)
            ];
            LastGroup = Group;
        }
        FText Label = Def->Title;
        if (Id == Quests->GetTrackedQuest()) Label = FText::Format(LOCTEXT("JournalTracked", "{0}   ◆"), Label);
        if (Status == EReflectionsQuestStatus::ReadyToTurnIn) Label = FText::Format(LOCTEXT("JournalReady", "{0}   (return)"), Label);
        TSharedPtr<SReflectionsFlowButton> Button;
        const FName QuestId = Id;
        List->AddSlot().AutoHeight().Padding(0, 0, 0, 6)
        [
            SAssignNew(Button, SReflectionsFlowButton)
            .Label(Label)
            .Primary(Def->bMain && Group == 0)
            .OnFocused_Lambda([this, QuestId]() { Select(QuestId); })
            .OnActivated_Lambda([this, QuestId]()
            {
                if (UReflectionsQuestSubsystem* Q = Owner.IsValid() ? UReflectionsQuestSubsystem::Get(Owner.Get()) : nullptr)
                {
                    const EReflectionsQuestStatus S = Q->GetStatus(QuestId);
                    if (S == EReflectionsQuestStatus::Active || S == EReflectionsQuestStatus::ReadyToTurnIn) Q->SetTrackedQuest(QuestId);
                }
            })
        ];
        Buttons.Add(Button);
    }
    if (Ids.IsEmpty())
    {
        List->AddSlot().AutoHeight()[Text(LOCTEXT("JournalEmpty", "Nothing written yet."), Font(TEXT("Regular"), 15), PaperDim)];
    }
    RebuildDetails();
    FocusFrames = 3;
    if (Self) SeenRevision = Self->GetRevision();
}

void SReflectionsQuestJournal::Select(FName QuestId)
{
    if (Selected == QuestId) return;
    Selected = QuestId;
    RebuildDetails();
}

void SReflectionsQuestJournal::RebuildDetails()
{
    UReflectionsQuestWorldSubsystem* Self = Owner.Get();
    UReflectionsQuestSubsystem* Quests = Self ? UReflectionsQuestSubsystem::Get(Self) : nullptr;
    const FReflectionsQuestDef* Def = Quests ? Quests->FindQuest(Selected) : nullptr;
    const FReflectionsQuestState* S = Quests ? Quests->FindState(Selected) : nullptr;
    TSharedRef<SVerticalBox> Col = SNew(SVerticalBox);
    if (!Def || !S)
    {
        Details->SetContent(Col);
        return;
    }
    Col->AddSlot().AutoHeight()[Text(Def->Title, Font(TEXT("Bold"), 24, 40), Paper, true)];
    FText Sub = Def->bMain ? LOCTEXT("JournalMain", "THE STORY") : SideText(Def->Side);
    if (!Def->Giver.IsNone()) Sub = FText::Format(LOCTEXT("JournalFrom", "{0}   ·   FROM {1}"), Sub, Quests->GetPersonName(Def->Giver).ToUpper());
    Col->AddSlot().AutoHeight().Padding(0, 6, 0, 0)[Text(Sub, Font(TEXT("Bold"), 11, 250), SideColor(Def->Side))];
    if (!Def->Summary.IsEmpty())
    {
        Col->AddSlot().AutoHeight().Padding(0, 14, 0, 0)[Text(Def->Summary, Font(TEXT("Italic"), 15), PaperDim, true)];
    }

    const FReflectionsQuestStep* Step = S->Status == EReflectionsQuestStatus::Active ? Def->FindStep(S->StepId) : nullptr;
    if (Step)
    {
        Col->AddSlot().AutoHeight().Padding(0, 22, 0, 4)[Text(Step->Title.IsEmpty() ? LOCTEXT("JournalNow", "NOW") : Step->Title.ToUpper(), Font(TEXT("Bold"), 13, 300), Gold)];
        if (!Step->Description.IsEmpty()) Col->AddSlot().AutoHeight().Padding(0, 2, 0, 6)[Text(Step->Description, Font(TEXT("Regular"), 15), Paper, true)];
        for (int32 i = 0; i < Step->Objectives.Num(); ++i)
        {
            const FReflectionsObjectiveState* OS = S->Objectives.IsValidIndex(i) ? &S->Objectives[i] : nullptr;
            const bool bDone = OS && OS->bDone;
            FText Line = Quests->FormatObjective(Step->Objectives[i], OS);
            if (Step->Objectives[i].bOptional) Line = FText::Format(LOCTEXT("JournalOptional", "{0} (optional)"), Line);
            Col->AddSlot().AutoHeight().Padding(0, 5, 0, 0)
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth().Padding(0, 4, 10, 0).VAlign(VAlign_Top)
                [
                    SNew(SBox).WidthOverride(11).HeightOverride(11)
                    [
                        SNew(SImage).Image(bDone ? Rounded(2.0f) : Ring(2.0f)).ColorAndOpacity(bDone ? Gold : Paper.CopyWithNewOpacity(0.6f))
                    ]
                ]
                + SHorizontalBox::Slot().FillWidth(1.0f)[Text(Line, Font(TEXT("Regular"), 15), bDone ? PaperDim : Paper, true)]
            ];
        }
    }
    else if (S->Status == EReflectionsQuestStatus::ReadyToTurnIn)
    {
        Col->AddSlot().AutoHeight().Padding(0, 22, 0, 4)[Text(LOCTEXT("JournalReturnHead", "ALMOST DONE"), Font(TEXT("Bold"), 13, 300), Gold)];
        Col->AddSlot().AutoHeight()[Text(FText::Format(LOCTEXT("JournalReturn", "Return to {0}."), Quests->GetPersonName(Def->Giver)), Font(TEXT("Regular"), 15), Paper, true)];
    }
    else if (S->Status == EReflectionsQuestStatus::Completed)
    {
        Col->AddSlot().AutoHeight().Padding(0, 22, 0, 4)[Text(LOCTEXT("JournalCompleteHead", "DONE"), Font(TEXT("Bold"), 13, 300), Gold)];
    }
    else if (S->Status == EReflectionsQuestStatus::Failed)
    {
        Col->AddSlot().AutoHeight().Padding(0, 22, 0, 4)[Text(LOCTEXT("JournalFailedHead", "FAILED"), Font(TEXT("Bold"), 13, 300), Red)];
    }
    if (!S->EndNote.IsEmpty())
    {
        Col->AddSlot().AutoHeight().Padding(0, S->Status == EReflectionsQuestStatus::Failed ? 0 : 18, 0, 0)[Text(S->EndNote, Font(TEXT("Italic"), 15), S->Status == EReflectionsQuestStatus::Failed ? Paper : PaperDim, true)];
    }

    // What happened so far, newest first.
    if (!S->Log.IsEmpty())
    {
        Col->AddSlot().AutoHeight().Padding(0, 24, 0, 4)[Text(LOCTEXT("JournalSoFar", "SO FAR"), Font(TEXT("Bold"), 13, 300), PaperDim)];
        for (int32 i = S->Log.Num() - 1; i >= 0; --i)
        {
            const FString Entry = S->Log[i].ToString();
            FText Line;
            TArray<FString> Parts;
            Entry.ParseIntoArray(Parts, TEXT(":"));
            if (Parts.Num() >= 2 && Parts[0] == TEXT("step"))
            {
                if (const FReflectionsQuestStep* Done = Def->FindStep(FName(*Parts[1]))) Line = Done->Title;
            }
            else if (Parts.Num() >= 3 && Parts[0] == TEXT("choice"))
            {
                if (const FReflectionsQuestStep* At = Def->FindStep(FName(*Parts[1])))
                {
                    if (const FReflectionsQuestChoice* C = At->Choices.FindByPredicate([&Parts](const FReflectionsQuestChoice& E) { return E.Id == FName(*Parts[2]); }))
                    {
                        Line = C->Journal.IsEmpty() ? FText::Format(LOCTEXT("JournalChose", "I chose: {0}"), C->Text) : C->Journal;
                    }
                }
            }
            if (!Line.IsEmpty())
            {
                Col->AddSlot().AutoHeight().Padding(0, 3, 0, 0)[Text(FText::Format(LOCTEXT("JournalLogLine", "—  {0}"), Line), Font(TEXT("Regular"), 14), PaperDim, true)];
            }
        }
    }
    if (!Def->Reward.IsEmpty() && S->Status != EReflectionsQuestStatus::Completed)
    {
        const FText Reward = Quests->DescribeReward(Def->Reward);
        if (!Reward.IsEmpty())
        {
            Col->AddSlot().AutoHeight().Padding(0, 24, 0, 4)[Text(LOCTEXT("JournalReward", "REWARD"), Font(TEXT("Bold"), 13, 300), PaperDim)];
            Col->AddSlot().AutoHeight()[Text(Reward, Font(TEXT("Regular"), 14), Paper, true)];
        }
    }
    Details->SetContent(Col);
}

void SReflectionsQuestJournal::EnsureFocus()
{
    if (!FSlateApplication::IsInitialized()) return;
    TSharedPtr<SReflectionsFlowButton> Want;
    for (int32 i = 0; i < Ids.Num() && i < Buttons.Num(); ++i)
    {
        if (Ids[i] == Selected) Want = Buttons[i];
    }
    if (!Want && Buttons.Num() > 0) Want = Buttons[0];
    if (Want) FSlateApplication::Get().SetAllUserFocus(Want, EFocusCause::Navigation);
    else FSlateApplication::Get().SetAllUserFocus(SharedThis(this), EFocusCause::SetDirectly);
}

void SReflectionsQuestJournal::Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime)
{
    SCompoundWidget::Tick(AllottedGeometry, InCurrentTime, InDeltaTime);
    UReflectionsQuestWorldSubsystem* Self = Owner.Get();
    if (!Self || !Self->IsJournalOpen()) return;
    if (Self->GetRevision() != SeenRevision)
    {
        Refresh();
    }
    if (FocusFrames > 0 && --FocusFrames == 0)
    {
        EnsureFocus();
    }
    // Keep focus inside the journal (a click on empty space or a controller reconnect can drop it).
    if (FSlateApplication::IsInitialized() && !HasFocusedDescendants() && !HasAnyUserFocus().IsSet() && FocusFrames == 0)
    {
        EnsureFocus();
    }
}

FReply SReflectionsQuestJournal::OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent)
{
    const FKey Key = InKeyEvent.GetKey();
    if (Key == EKeys::Escape || Key == EKeys::L || Key == EKeys::Gamepad_FaceButton_Right || Key == EKeys::Gamepad_Special_Right || Key == EKeys::P)
    {
        if (UReflectionsQuestWorldSubsystem* Self = Owner.Get()) Self->CloseJournal();
        return FReply::Handled();
    }
    return SCompoundWidget::OnKeyDown(MyGeometry, InKeyEvent);
}

// ---- Talk card -----------------------------------------------------------------------------------------------

void SReflectionsQuestTalk::Construct(const FArguments& InArgs)
{
    Owner = InArgs._Owner;
    TWeakObjectPtr<UReflectionsQuestWorldSubsystem> Weak = Owner;
    SAssignNew(Options, SVerticalBox);
    SetVisibility(TAttribute<EVisibility>::CreateLambda([Weak]() {
        return Weak.IsValid() && Weak->IsTalkOpen() ? EVisibility::Visible : EVisibility::Collapsed;
    }));
    ChildSlot
    [
        SNew(SOverlay)
        + SOverlay::Slot()
        [
            SNew(SImage).Image(Solid()).ColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.25f))
        ]
        + SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Bottom).Padding(FMargin(0, 0, 0, 90))
        [
            SNew(SBorder)
            .BorderImage(Rounded(12.0f))
            .BorderBackgroundColor(FLinearColor(0.01f, 0.01f, 0.015f, 0.92f))
            .Padding(FMargin(32, 24, 32, 24))
            [
                SNew(SBox).WidthOverride(780)
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        SNew(SHorizontalBox)
                        + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom)
                        [
                            SNew(STextBlock)
                            .Font(Font(TEXT("Bold"), 16, 200))
                            .ColorAndOpacity(FSlateColor(Gold))
                            .Text_Lambda([Weak]() { return Weak.IsValid() ? Weak->GetTalkSpeaker().ToUpper() : FText::GetEmpty(); })
                        ]
                        + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom).Padding(14, 0, 0, 1)
                        [
                            SNew(STextBlock)
                            .Font(Font(TEXT("Regular"), 13, 40))
                            .ColorAndOpacity(FSlateColor(PaperDim))
                            .Text_Lambda([Weak]() { return Weak.IsValid() ? Weak->GetTalkSpeakerTitle() : FText::GetEmpty(); })
                        ]
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0, 6, 0, 14)[Rule(Red, 60.0f, 2.0f)]
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        SNew(STextBlock)
                        .Font(Font(TEXT("Regular"), 18))
                        .AutoWrapText(true)
                        .ColorAndOpacity(FSlateColor(Paper))
                        .Text_Lambda([Weak]() { return Weak.IsValid() ? Weak->GetTalkLine() : FText::GetEmpty(); })
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0, 20, 0, 0)[Options.ToSharedRef()]
                ]
            ]
        ]
    ];
}

void SReflectionsQuestTalk::Rebuild()
{
    UReflectionsQuestWorldSubsystem* Self = Owner.Get();
    Options->ClearChildren();
    Buttons.Reset();
    if (!Self) return;
    SeenRevision = Self->GetTalkRevision();
    TWeakObjectPtr<UReflectionsQuestWorldSubsystem> Weak = Owner;
    if (!Self->IsTalkOnLastLine())
    {
        TSharedPtr<SReflectionsFlowButton> Button;
        Options->AddSlot().AutoHeight()
        [
            SAssignNew(Button, SReflectionsFlowButton)
            .Label(LOCTEXT("TalkNext", "Continue"))
            .Primary(true)
            .OnActivated_Lambda([Weak]() { if (Weak.IsValid()) Weak->AdvanceTalk(); })
        ];
        Buttons.Add(Button);
    }
    else
    {
        const TArray<FReflectionsTalkOption>& Opts = Self->GetTalkOptions();
        for (const FReflectionsTalkOption& Option : Opts)
        {
            TSharedPtr<SReflectionsFlowButton> Button;
            Options->AddSlot().AutoHeight().Padding(0, 0, 0, 6)
            [
                SAssignNew(Button, SReflectionsFlowButton)
                .Label(Option.Label)
                .Primary(Option.bPrimary)
                .OnActivated_Lambda([Weak, Action = Option.Action]() { if (Weak.IsValid()) Weak->ChooseTalkAction(Action); })
            ];
            Buttons.Add(Button);
        }
    }
    FocusFrames = 2;
}

void SReflectionsQuestTalk::Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime)
{
    SCompoundWidget::Tick(AllottedGeometry, InCurrentTime, InDeltaTime);
    UReflectionsQuestWorldSubsystem* Self = Owner.Get();
    if (!Self || !Self->IsTalkOpen())
    {
        SeenRevision = -1;
        return;
    }
    if (Self->GetTalkRevision() != SeenRevision) Rebuild();
    if (FocusFrames > 0 && --FocusFrames == 0 && Buttons.Num() > 0 && FSlateApplication::IsInitialized())
    {
        FSlateApplication::Get().SetAllUserFocus(Buttons[0], EFocusCause::Navigation);
    }
    if (FocusFrames == 0 && Buttons.Num() > 0 && FSlateApplication::IsInitialized() && !HasFocusedDescendants())
    {
        FSlateApplication::Get().SetAllUserFocus(Buttons[0], EFocusCause::Navigation);
    }
}

FReply SReflectionsQuestTalk::OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent)
{
    const FKey Key = InKeyEvent.GetKey();
    UReflectionsQuestWorldSubsystem* Self = Owner.Get();
    if (Self && (Key == EKeys::Escape || Key == EKeys::Gamepad_FaceButton_Right || Key == EKeys::Gamepad_Special_Right))
    {
        // Back: skip to the buttons, then leave.
        if (!Self->IsTalkOnLastLine())
        {
            while (Self->AdvanceTalk()) {}
        }
        else
        {
            const TArray<FReflectionsTalkOption>& Opts = Self->GetTalkOptions();
            const int32 Bye = Opts.IndexOfByPredicate([](const FReflectionsTalkOption& O) { return O.Action == TEXT("goodbye"); });
            if (Bye != INDEX_NONE) Self->ChooseTalkOption(Bye);
            else Self->CloseTalk();
        }
        return FReply::Handled();
    }
    if (Self && Key == EKeys::E && !Self->IsTalkOnLastLine())
    {
        Self->AdvanceTalk();
        return FReply::Handled();
    }
    return SCompoundWidget::OnKeyDown(MyGeometry, InKeyEvent);
}

#undef LOCTEXT_NAMESPACE
