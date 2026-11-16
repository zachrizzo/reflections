#pragma once
#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Voice/ReflectionsRealtimeVoiceComponent.h"
#include "ReflectionsVoiceInteractionSubsystem.generated.h"

class APlayerController;
class SReflectionsNpcDialogueOverlay;
class UInputComponent;
class UReflectionsRealtimeVoiceComponent;

/**
 * NPC talk-back for the local player. Near an NPC of the unified NPC system: hold T (keyboard) or D-pad Down
 * (gamepad) and speak, or press Enter and type. The NPC answers in voice with subtitles, through the dialogue
 * relay, or with a baked bark when there is no relay. See ArtDirection/NpcDialogue/README.md.
 * Console (non-shipping): Npc.Say <text>, Npc.SayTo <name> <text>, Npc.DialogueStatus, Npc.DialogueFallback 0|1.
 */
UCLASS()
class REFLECTIONS_API UReflectionsVoiceInteractionSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override { RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsVoiceInteractionSubsystem, STATGROUP_Tickables); }
    virtual bool IsTickable() const override;
    virtual void Deinitialize() override;
    /** On unless Reflections.NpcDialogue=0. */
    virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

    /** Sends a typed line to this NPC, as if the player had typed it next to them (tests, scripted moments). */
    UFUNCTION(BlueprintCallable, Category="NPC Dialogue")
    bool SayToNpc(AActor* Npc, const FString& Text);

    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    AActor* GetTalkTarget() const { return Target.Get(); }

    /** The dialogue panel's top edge above the screen bottom, in Slate units (DPI-scaled, like viewport widget
     *  padding), measured each frame; 0 when the panel shows nothing. Other HUD text can sit above it. */
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    float GetPanelTopFromBottom() const;

    UReflectionsRealtimeVoiceComponent* GetVoice() const { return Voice; }

    // ---- Read-outs for tests and tools ----
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    FString DescribeStatus() const;

    /** Tests: the same as pressing (true) or letting go of (false) the talk key, E / D-pad Down. */
    UFUNCTION(BlueprintCallable, Category="NPC Dialogue")
    void PressTalkKey(bool bDown);
    /** The talk prompt the player sees: the quest system's for a person with quest business, else ours. */
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    FString GetTalkPromptText() const;
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    bool IsListeningShown() const;
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    bool IsThinkingShown() const;
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    EReflectionsReplySource GetLastReplySource() const { return Voice ? Voice->GetLastReplySource() : EReflectionsReplySource::None; }
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    FString GetLastReplyId() const { return Voice ? Voice->GetLastReplyId() : FString(); }
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    FString GetLastNpcLine() const { return Voice ? Voice->GetLastNpcLine() : FString(); }
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    FString GetSpeakerName() const { return Voice ? Voice->GetSpeakerName() : FString(); }
    /** True from the end of the player's line until the NPC has finished answering. */
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    bool IsNpcBusy() const { return Voice && (Voice->IsBusy() || Voice->IsListening()); }
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    bool IsNpcSpeaking() const { return Voice && Voice->IsSpeaking(); }
    UFUNCTION(BlueprintPure, Category="NPC Dialogue")
    int32 GetReplyCount(EReflectionsReplySource Source) const { return Voice ? Voice->GetRepliesBySource(Source) : 0; }

private:
    void EnsureSetup();
    AActor* FindTalkTarget(const APawn* Pawn) const;
    bool CanTalkTo(AActor* Npc) const;
    void OnTalkPressed();
    void OnTalkReleased();
    void OnTypePressed();
    void FinishTyping();
    bool IsInEarshot(const AActor* Npc) const;

    // ---- NPC actions (the second check: the relay only offers and forwards what this reports possible) ----
    TArray<FString> GetAvailableActions(AActor* Npc) const;
    bool ExecuteAction(AActor* Npc, const FString& Name, const FString& TargetName, FString& OutReason);
    AActor* FindTarget(const FString& TargetName, const FVector& From) const;
    TMap<TWeakObjectPtr<AActor>, double> PointedAt;
    double GuardsWarnedAt = -1.0e9;
    TWeakObjectPtr<AActor> LookTargetNpc;
    FVector LookTarget = FVector::ZeroVector;
    double LookUntil = 0.0;
    void UpdateFacing(float DeltaTime);
    void ReleaseFacing();
    UFUNCTION() void OnLine(const FString& Speaker, const FString& Text, bool bPlayer, bool bFinal);

    UPROPERTY(Transient) TObjectPtr<UInputComponent> Input;
    UPROPERTY(Transient) TObjectPtr<UReflectionsRealtimeVoiceComponent> Voice;
    TSharedPtr<SReflectionsNpcDialogueOverlay> Overlay;
    TWeakObjectPtr<APlayerController> Controller;
    TWeakObjectPtr<AActor> Target;
    TWeakObjectPtr<AActor> Candidate;
    TWeakObjectPtr<AActor> Partner;
    TWeakObjectPtr<AActor> SteeredNpc;
    TWeakObjectPtr<AActor> MutedNpc;
    float CandidateTime = 0.0f;
    float FarTime = 0.0f;
    float LastPlayerHealth = -1.0f;  // a drop closes the typing box (UI-only input would leave the player stuck)
    bool bHeld = false;
    /** This press of the talk key opened (or belongs to) the quest dialogue: its release is not a voice turn. */
    bool bPressWentToQuest = false;
    /** The NPC we tagged NPC_Talking (crowd spots let go of it) for the conversation; NPC_NoStroll too if we added it. */
    TWeakObjectPtr<AActor> TalkTagNpc;
    bool bAddedNoStroll = false;
};
