#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/Input/SButton.h"
#include "GameFlow/ReflectionsGameFlowTypes.h"

class SBox;
class UReflectionsGameFlowWorldSubsystem;
enum class EReflectionsFlowAction : uint8;

/** Menu button: one highlight for mouse hover and keyboard / gamepad focus (hovering moves focus). */
class SReflectionsFlowButton : public SButton
{
public:
    SLATE_BEGIN_ARGS(SReflectionsFlowButton) : _Primary(false) {}
        SLATE_ATTRIBUTE(FText, Label)
        /** Settings rows: the value shown on the right as "<  value  >". */
        SLATE_ATTRIBUTE(FText, Value)
        /** Save slots: a smaller line on the right ("18:40  ·  Giltside  ·  2 pages"). */
        SLATE_ATTRIBUTE(FText, Detail)
        SLATE_ARGUMENT(bool, Primary)
        SLATE_EVENT(FSimpleDelegate, OnActivated)
        SLATE_EVENT(FSimpleDelegate, OnFocused)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

    virtual FReply OnFocusReceived(const FGeometry& MyGeometry, const FFocusEvent& InFocusEvent) override;
    virtual void OnFocusLost(const FFocusEvent& InFocusEvent) override;
    virtual void OnMouseEnter(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
    virtual FReply OnMouseMove(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;

    /** Focus is the one highlight: hovering (or moving the mouse over) a button takes focus. */
    bool IsHighlighted() const { return bFocused; }
    void SetOnFocused(const FSimpleDelegate& Delegate);

private:
    FSimpleDelegate OnActivatedDelegate;
    FSimpleDelegate OnFocusedDelegate;
    bool bFocused = false;
    bool bPrimary = false;
};

/** Always-on layer: infection meter (top right), toast under it, tutorial tip card. Never takes input. */
class SReflectionsFlowHud : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsFlowHud) {}
        SLATE_ARGUMENT(TWeakObjectPtr<UReflectionsGameFlowWorldSubsystem>, Owner)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

private:
    TWeakObjectPtr<UReflectionsGameFlowWorldSubsystem> Owner;
};

/**
 * Full-screen loading / saving screen: dark, the title and theme line, a spinner and one status line. Safe to paint
 * on the movie player's loading thread while a map loads: it touches no UObjects (the text is fixed when it is
 * built, unless the game thread binds Status for its own copy).
 */
class SReflectionsLoadingScreen : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsLoadingScreen) {}
        SLATE_ATTRIBUTE(FText, Status)
        SLATE_ARGUMENT(FText, Title)
        SLATE_ARGUMENT(FText, Line)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

    /** The game's loading screen (title and theme line from the String Table, copied to plain text). Game thread. */
    static TSharedRef<SReflectionsLoadingScreen> Create(const TAttribute<FText>& Status);
};

/** Full-screen menus. Rebuilds its content per screen and keeps focus inside itself. */
class SReflectionsFlowMenu : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsFlowMenu) {}
        SLATE_ARGUMENT(TWeakObjectPtr<UReflectionsGameFlowWorldSubsystem>, Owner)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

    /** Rebuilds for a screen (None hides everything). */
    void SetScreen(EReflectionsFlowScreen Screen);

    /** Focuses the first (or remembered) button again if focus wandered off the menu. */
    void EnsureFocus();

    /** Hidden (and not taking focus) while another overlay, the quest journal, sits over the pause menu. */
    void SetSuspended(bool bInSuspended);
    bool IsSuspended() const { return bSuspended; }

    virtual bool SupportsKeyboardFocus() const override { return true; }
    virtual FReply OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent) override;
    virtual FReply OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
    virtual FNavigationReply OnNavigation(const FGeometry& MyGeometry, const FNavigationEvent& InNavigationEvent) override;
    virtual void Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime) override;

    /** Button labels on the current screen, top to bottom (for tests and logs). */
    TArray<FString> GetButtonLabels() const;
    int32 GetFocusedIndex() const;

private:
    TSharedRef<SWidget> BuildTitle();
    TSharedRef<SWidget> BuildPause();
    TSharedRef<SWidget> BuildControls();
    TSharedRef<SWidget> BuildCredits(bool bEmbedded);
    TSharedRef<SWidget> BuildConfirm();
    TSharedRef<SWidget> BuildLose();
    TSharedRef<SWidget> BuildVictory();
    TSharedRef<SWidget> BuildFooter();
    TSharedRef<SWidget> BuildSettings();
    TSharedRef<SWidget> BuildSettingsConfirm();
    TSharedRef<SWidget> BuildSaveGame();
    TSharedRef<SWidget> BuildLoadGame();
    TSharedRef<SWidget> BuildDeath();
    /** A slot button: name on the left, time / side / pages (or "Empty") on the right. */
    TSharedRef<SWidget> MakeSlotButton(int32 Slot, EReflectionsFlowAction Action, bool bPrimary = false);
    /** The status line under the slots, and the shortcut hint. */
    TSharedRef<SWidget> BuildSaveStatus();
    TSharedRef<SWidget> MakeRow(const FText& Label, int32 Row);

    TSharedRef<SWidget> MakeButton(const FText& Label, EReflectionsFlowAction Action, bool bPrimary = false,
        const TAttribute<FText>& Detail = TAttribute<FText>(), float Width = 440.0f);
    TSharedRef<SWidget> MakePanel(TSharedRef<SWidget> Content, float Width);
    void Activate(EReflectionsFlowAction Action);

    TWeakObjectPtr<UReflectionsGameFlowWorldSubsystem> Owner;
    TSharedPtr<SBox> Content;
    TArray<TSharedPtr<SReflectionsFlowButton>> Buttons;
    TArray<FString> ButtonLabels;
    TWeakPtr<SReflectionsFlowButton> LastFocused;
    EReflectionsFlowScreen Screen = EReflectionsFlowScreen::None;
    int32 FocusFrames = 0;
    bool bSuppressFocusSound = false;
    bool bSuspended = false;
};
