#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Framework/Application/IInputProcessor.h"

class UReflectionsCutsceneSubsystem;

/**
 * Cutscene presentation layer: letterbox bars, fade to black, subtitles (inside the lower bar), title cards and the
 * hold-to-skip prompt. Styled like the game-flow menus (parchment on ink, gold accents). Never takes input.
 */
class SReflectionsCutsceneOverlay : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsCutsceneOverlay) {}
        SLATE_ARGUMENT(TWeakObjectPtr<UReflectionsCutsceneSubsystem>, Owner)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

    virtual void Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime) override;
    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
        FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;

    /** Height of one letterbox bar right now, in slate units. */
    float GetBarHeight() const;

private:
    TSharedRef<SWidget> BuildSubtitle();
    TSharedRef<SWidget> BuildCard();
    TSharedRef<SWidget> BuildSkipPrompt();

    TWeakObjectPtr<UReflectionsCutsceneSubsystem> Owner;
    FVector2D LastSize = FVector2D(1920.0f, 1080.0f);
};

/** Watches keys for hold-to-skip and the last input device, without consuming anything. */
class FReflectionsCutsceneInput : public IInputProcessor
{
public:
    explicit FReflectionsCutsceneInput(TWeakObjectPtr<UReflectionsCutsceneSubsystem> InOwner) : Owner(InOwner) {}

    virtual void Tick(const float DeltaTime, FSlateApplication& SlateApp, TSharedRef<ICursor> Cursor) override {}
    virtual bool HandleKeyDownEvent(FSlateApplication& SlateApp, const FKeyEvent& InKeyEvent) override;
    virtual bool HandleKeyUpEvent(FSlateApplication& SlateApp, const FKeyEvent& InKeyEvent) override;
    virtual bool HandleAnalogInputEvent(FSlateApplication& SlateApp, const FAnalogInputEvent& InAnalogInputEvent) override;
    virtual bool HandleMouseButtonDownEvent(FSlateApplication& SlateApp, const FPointerEvent& MouseEvent) override;
    virtual const TCHAR* GetDebugName() const override { return TEXT("ReflectionsCutsceneInput"); }

    static bool IsSkipKey(const FKey& Key);

private:
    TWeakObjectPtr<UReflectionsCutsceneSubsystem> Owner;
};
