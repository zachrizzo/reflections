#pragma once

#include "CoreMinimal.h"
#include "Widgets/SLeafWidget.h"

/** One block of text over a person's head (or the clock in the corner), in viewport pixels. */
struct FReflectionsLivesLabel
{
    FVector2D Pixel = FVector2D::ZeroVector;
    bool bCenter = true;
    TArray<TPair<FString, FLinearColor>> Lines;
};

/**
 * The Lives debug view (F7): name, job, activity, next step and mood over each person, drawn in Slate on the game
 * viewport so it shows in play and in viewport captures. Takes no input.
 */
class SReflectionsLivesOverlay : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsLivesOverlay) {}
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);
    void SetLabels(TArray<FReflectionsLivesLabel>&& InLabels) { Labels = MoveTemp(InLabels); }

    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(1.0, 1.0); }
    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
        FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;

private:
    TArray<FReflectionsLivesLabel> Labels;
};
