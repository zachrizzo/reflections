#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/SLeafWidget.h"

class SBox;
class SReflectionsFlowButton;
class SVerticalBox;
class UReflectionsQuestWorldSubsystem;

/** Paints the tracked objective's pointer (clamped to the screen edge) and the marks over quest people. */
class SReflectionsQuestMarkers : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsQuestMarkers) {}
        SLATE_ARGUMENT(TWeakObjectPtr<UReflectionsQuestWorldSubsystem>, Owner)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);
    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements,
        int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;
    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(1, 1); }

private:
    TWeakObjectPtr<UReflectionsQuestWorldSubsystem> Owner;
};

/** Always-on quest layer: tracker (top right, under the Tarnish meter), banners, subtitles, pointer and marks. */
class SReflectionsQuestHud : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsQuestHud) {}
        SLATE_ARGUMENT(TWeakObjectPtr<UReflectionsQuestWorldSubsystem>, Owner)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

private:
    TWeakObjectPtr<UReflectionsQuestWorldSubsystem> Owner;
};

/** The journal: quests on the left, the selected quest's notes on the right. A / Enter tracks, B / Esc / J closes. */
class SReflectionsQuestJournal : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsQuestJournal) {}
        SLATE_ARGUMENT(TWeakObjectPtr<UReflectionsQuestWorldSubsystem>, Owner)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);
    /** Rebuilds the list from the quest state (keeps the selection). */
    void Refresh();

    virtual bool SupportsKeyboardFocus() const override { return true; }
    virtual FReply OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent) override;
    virtual void Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime) override;

    FName GetSelected() const { return Selected; }

private:
    void Select(FName QuestId);
    void RebuildDetails();
    void EnsureFocus();

    TWeakObjectPtr<UReflectionsQuestWorldSubsystem> Owner;
    TSharedPtr<SVerticalBox> List;
    TSharedPtr<SBox> Details;
    TArray<TSharedPtr<SReflectionsFlowButton>> Buttons;
    TArray<FName> Ids;
    FName Selected;
    int32 SeenRevision = -1;
    int32 FocusFrames = 0;
};

/** Talk card with a quest person: their lines, then buttons (accept, not now, hand over, choices, goodbye). */
class SReflectionsQuestTalk : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsQuestTalk) {}
        SLATE_ARGUMENT(TWeakObjectPtr<UReflectionsQuestWorldSubsystem>, Owner)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

    virtual bool SupportsKeyboardFocus() const override { return true; }
    virtual FReply OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent) override;
    virtual void Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime) override;

private:
    void Rebuild();
    TWeakObjectPtr<UReflectionsQuestWorldSubsystem> Owner;
    TSharedPtr<SVerticalBox> Options;
    TArray<TSharedPtr<SReflectionsFlowButton>> Buttons;
    int32 SeenRevision = -1;
    int32 FocusFrames = 0;
};
