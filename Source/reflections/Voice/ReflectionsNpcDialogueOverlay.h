#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"

class SEditableTextBox;

/**
 * Bottom-centre dialogue overlay: the player's line and the NPC's reply as subtitles, the talk prompt near an
 * NPC, a small listening/thinking indicator, the typed-line box and a one-time AI-voice notice.
 * Never shows relay errors: when the relay fails the NPC simply answers with a bark.
 */
class SReflectionsNpcDialogueOverlay : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SReflectionsNpcDialogueOverlay) {}
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);
    virtual void Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime) override;

    void SetPrompt(const FText& InPrompt) { Prompt = InPrompt; }
    const FText& GetPrompt() const { return Prompt; }
    void SetStatus(const FText& InStatus) { StatusText = InStatus; }
    /** bAi adds the "AI voice" tag next to the speaker. KeepLines holds the subtitles on screen. */
    void ShowLine(const FString& Speaker, const FString& Text, bool bPlayer, bool bAi);
    void KeepLines() { LinesShownAt = FPlatformTime::Seconds(); }
    void ClearLines();
    void ShowNotice(const FText& InNotice, double Seconds);
    /** A short gold line above the subtitles, e.g. where an NPC pointed. */
    void ShowHint(const FText& InHint, double Seconds) { HintLine = InHint; HintUntil = FPlatformTime::Seconds() + Seconds; }
    /** The microphone is open: a pulsing ring and a meter driven by Level (0..1), and "Listening... say anything". */
    void SetListening(bool bInListening, float Level) { bListening = bInListening; TargetMicLevel = bInListening ? Level : 0.0f; }
    /** Waiting for the reply: "<Who> is thinking" with moving dots. Empty Who: off. */
    void SetThinking(const FText& Who) { ThinkingWho = Who; }
    bool IsShowingListening() const { return bListening; }
    float GetSmoothedMicLevel() const { return MicLevel; }
    bool IsShowingThinking() const { return !ThinkingWho.IsEmpty(); }

    void OpenTyping(const FText& Hint);
    void CloseTyping();
    bool IsTyping() const { return bTyping; }
    TSharedPtr<SEditableTextBox> GetTypingBox() const { return TypingBox; }
    /** The panel's top edge above the screen bottom, in Slate units, as of the last frame; 0 when nothing shows. */
    float GetPanelTopFromBottom() const { return PanelTopFromBottom; }

    TFunction<void(const FString&)> OnTypedLine;
    TFunction<void()> OnTypingCancelled;

private:
    float LinesAlpha() const;
    float NoticeAlpha() const;

    FText Prompt;
    FText StatusText;
    FText Notice;
    FText HintLine;
    double HintUntil = 0.0;
    FString NpcSpeaker;
    FString NpcLine;
    FString PlayerLine;
    bool bNpcAi = false;
    bool bTyping = false;
    double LinesShownAt = -1.0e9;
    double LineHoldSeconds = 5.0;
    double NoticeUntil = 0.0;
    TSharedPtr<SEditableTextBox> TypingBox;
    float PanelTopFromBottom = 0.0f;
    bool bListening = false;
    float TargetMicLevel = 0.0f;
    float MicLevel = 0.0f;
    FText ThinkingWho;
    static constexpr float BottomMargin = 215.0f;  // above the spell bar (health, mana, spell slots)
};
