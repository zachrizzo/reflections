#include "Lives/ReflectionsLivesOverlay.h"

#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/DrawElements.h"
#include "Styling/CoreStyle.h"

void SReflectionsLivesOverlay::Construct(const FArguments& InArgs)
{
    SetVisibility(EVisibility::HitTestInvisible);
}

int32 SReflectionsLivesOverlay::OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
    FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
    if (Labels.Num() == 0 || !FSlateApplication::IsInitialized()) return LayerId;
    const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
    const FSlateFontInfo Font = FCoreStyle::GetDefaultFontStyle("Regular", 10);
    const FSlateBrush* White = FCoreStyle::Get().GetBrush("WhiteBrush");
    // Labels come in viewport pixels; the widget is laid out in Slate units (pixels / DPI scale).
    const float Scale = FMath::Max(0.01f, AllottedGeometry.Scale);
    for (const FReflectionsLivesLabel& Label : Labels)
    {
        float MaxW = 0.0f, TotalH = 0.0f;
        TArray<FVector2f> Sizes;
        for (const TPair<FString, FLinearColor>& Line : Label.Lines)
        {
            const auto Size = Measure->Measure(Line.Key, Font);
            Sizes.Add(FVector2f(static_cast<float>(Size.X), static_cast<float>(Size.Y)));
            MaxW = FMath::Max(MaxW, static_cast<float>(Size.X));
            TotalH += static_cast<float>(Size.Y) + 1.0f;
        }
        const FVector2f Anchor(static_cast<float>(Label.Pixel.X) / Scale, static_cast<float>(Label.Pixel.Y) / Scale);
        const float Left = Label.bCenter ? Anchor.X - MaxW * 0.5f : Anchor.X;
        const float Top = Label.bCenter ? Anchor.Y - TotalH : Anchor.Y;
        FSlateDrawElement::MakeBox(OutDrawElements, LayerId,
            AllottedGeometry.ToPaintGeometry(FVector2f(MaxW + 12.0f, TotalH + 8.0f), FSlateLayoutTransform(FVector2f(Left - 6.0f, Top - 4.0f))),
            White, ESlateDrawEffect::None, FLinearColor(0.0f, 0.0f, 0.0f, 0.6f));
        float Y = Top;
        for (int32 i = 0; i < Label.Lines.Num(); ++i)
        {
            const float X = Label.bCenter ? Anchor.X - Sizes[i].X * 0.5f : Anchor.X;
            FSlateDrawElement::MakeText(OutDrawElements, LayerId + 1,
                AllottedGeometry.ToPaintGeometry(Sizes[i], FSlateLayoutTransform(FVector2f(X, Y))),
                Label.Lines[i].Key, Font, ESlateDrawEffect::None, Label.Lines[i].Value);
            Y += Sizes[i].Y + 1.0f;
        }
    }
    return LayerId + 2;
}
