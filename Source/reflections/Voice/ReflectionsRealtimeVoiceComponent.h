#pragma once

#include "CoreMinimal.h"
#include "AudioCaptureCore.h"
#include "Components/ActorComponent.h"
#include "Containers/Queue.h"
#include "ReflectionsRealtimeVoiceComponent.generated.h"

class FJsonObject;
class IWebSocket;
class UAudioComponent;
class USceneComponent;
class USoundAttenuation;
class USoundWaveProcedural;

DECLARE_LOG_CATEGORY_EXTERN(LogReflectionsNpcDialogue, Log, All);

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FReflectionsVoiceStatus, const FString&, Status);
/** A subtitle: the player's line (bPlayer) or the NPC's line so far. bFinal when the line is complete. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FReflectionsDialogueLine, const FString&, Speaker, const FString&, Text, bool, bPlayer, bool, bFinal);

UENUM(BlueprintType)
enum class EReflectionsDialogueState : uint8
{
    Idle,
    Connecting,
    Ready,
    Listening,
    Thinking,
    Speaking,
};

/** Where the last NPC reply came from. */
UENUM(BlueprintType)
enum class EReflectionsReplySource : uint8 { None, Generated, Cached, Bark };

/**
 * The player's side of a conversation with one NPC. Talks to the dialogue relay (Tools/RealtimeVoice), which
 * holds the Gemini key; the key never enters the game. Hold to talk (microphone) or send a typed line; the NPC
 * answers in voice with subtitles. With no relay, or when the relay fails or is over its limits, the NPC
 * answers with a baked bark instead and nothing about the failure is shown.
 */
UCLASS(ClassGroup=(Voice), BlueprintType, meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsRealtimeVoiceComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UReflectionsRealtimeVoiceComponent();
    virtual ~UReflectionsRealtimeVoiceComponent();

    /** Opens a relay session for this NPC (no-op if already connected to it). Falls back to barks if none. */
    UFUNCTION(BlueprintCallable, Category="Voice") void ConnectToNpc(AActor* Npc);
    /** Starts the microphone. Audio is held until the session is ready. Interrupts the NPC if it is speaking. */
    UFUNCTION(BlueprintCallable, Category="Voice") void BeginPushToTalk();
    UFUNCTION(BlueprintCallable, Category="Voice") void EndPushToTalk();
    /** A typed line instead of speech. Returns false if empty. */
    UFUNCTION(BlueprintCallable, Category="Voice") bool SendTypedLine(const FString& Text);
    /** Stops the NPC mid-sentence (the relay trims the model's memory to what was heard). */
    UFUNCTION(BlueprintCallable, Category="Voice") void Interrupt();
    UFUNCTION(BlueprintCallable, Category="Voice") void DisconnectVoice();

    AActor* GetVoiceNpc() const { return VoiceNpc.Get(); }
    bool IsVoiceReady() const { return bReady; }
    bool IsConnecting() const { return Socket.IsValid() && !bReady; }
    bool IsListening() const { return bRecording.Load(); }
    /** The helper was (re)started (a key was saved): try it again now rather than after the retry wait. */
    void ClearRelayDown() { RelayDownUntil = 0.0; }
    /** How loud the microphone is right now (0..1, the last chunk's peak), for the listening meter; 0 when not listening. */
    float GetMicLevel() const { return bRecording.Load() ? MicLevelMilli.Load() / 1000.0f : 0.0f; }
    bool IsSpeaking() const;
    /** True while a reply is being prepared or played (between the end of the player's turn and the NPC finishing). */
    bool IsBusy() const { return bAwaitingReply || IsSpeaking(); }
    EReflectionsDialogueState GetState() const;
    EReflectionsReplySource GetLastReplySource() const { return LastSource; }
    const FString& GetLastReplyId() const { return LastReplyId; }
    const FString& GetLastNpcLine() const { return NpcText; }
    const FString& GetLastPlayerLine() const { return PlayerText; }
    FString GetSpeakerName() const;
    /** False while barks are used because the relay is missing, failed recently, or was forced off. */
    bool IsRelayAvailable() const;
    /** Seconds since the NPC stopped speaking (large when it never spoke). */
    double SecondsSinceSpeech() const;
    int32 GetRepliesBySource(EReflectionsReplySource Source) const;

    /** Testing aid: true = act as if no relay is configured. */
    static void SetForceFallback(bool bForce);

    /** Persona facts for the relay, from the unified NPC system (archetype, reaction, side, reputation...). */
    static TSharedRef<FJsonObject> BuildNpcContext(AActor* Npc, APawn* Player, const TArray<FString>& Actions = TArray<FString>());
    /** The NPC's roster voice (a designed Gemini voice) from the NPC system's voice profile, if it has one. */
    static FString GetVoiceId(AActor* Npc);
    /** The lives system's name for this person ("Mara Vell"), if it has one. */
    static FString GetPersonName(AActor* Npc);
    /** Tells the lives system the player talked to this person (RememberPlayer ..., Talked, 1). */
    static void RememberTalk(AActor* Npc);

    // ---- Quest system (UReflectionsQuestSubsystem, called by name: no header dependency) ----
    /** Quest actions possible with this NPC now ("offer_quest:lost_ring", "turn_in:lost_ring", ...). */
    static TArray<FString> GetQuestActions(AActor* Npc);
    /** Performs a quest action after the quest system's own re-check. OutSay: a line to show (hint, pitch, thanks). */
    static bool ExecuteQuestAction(AActor* Npc, const FString& Action, FString& OutReason, FString& OutSay);
    /** The quest system's notes about this person (JSON), sent to the relay as "quests". */
    static FString GetQuestContext(AActor* Npc);
    /** Opens the quest talk card if this person has quest business (the non-voice path). True if it opened. */
    static bool HandleQuestTalkPressed(AActor* Npc);
    /** Counts a finished voice exchange for "talk to X" objectives. */
    static void NotifyQuestTalkedTo(AActor* Npc);

    /** Set by the interaction subsystem: the actions possible for an NPC right now ("point_the_way:gilt_tower"). */
    TFunction<TArray<FString>(AActor*)> ActionsProvider;
    /** Set by the interaction subsystem: performs an action the relay chose; false + reason if it can't. */
    TFunction<bool(AActor*, const FString&, const FString&, FString&)> ActionHandler;
    /** Civilian, Guard, Soldier, Tarnished or Tarnish: picks barks and the subtitle name without a relay. */
    static FName PersonaGroup(AActor* Npc);
    /** The NPC's voice slot from the NPC system's voice profile ("F1".."F3", "M1".."M3"), and its sex. Empty if none. */
    static void GetVoiceProfile(AActor* Npc, FString& OutSlot, FString& OutSex);
    /** Where an NPC's voice comes from: its head bone, else 1.6 m above its root. */
    static USceneComponent* GetVoiceAnchor(AActor* Npc, FName& OutSocket, FVector& OutOffset);
    static USoundAttenuation* GetVoiceAttenuation();

    UPROPERTY(BlueprintAssignable, Category="Voice") FReflectionsVoiceStatus OnVoiceStatus;
    UPROPERTY(BlueprintAssignable, Category="Voice") FReflectionsDialogueLine OnDialogueLine;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Voice") FString Status;

protected:
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTick) override;

private:
    void SetStatus(const FString& Next);
    void OnMessage(const FString& Message);
    void SendJson(const TSharedRef<FJsonObject>& Object);
    void SendSessionStart();
    void SendContextIfChanged();
    void FlushCaptured();
    void FlushPending();
    void StopCapture();
    void StopPlayback();
    void EnsureOutput();
    void FailToBarks(bool bMarkRelayDown);
    void CloseSocket();
    void PlayBark();
    void BeginReply(EReflectionsReplySource Source, const FString& ReplyId);
    void BroadcastNpcLine(bool bFinal);
    FString ReadLocalToken(const FString& Url) const;
    static FString ClientId();

    TSharedPtr<IWebSocket> Socket;
    TUniquePtr<Audio::FAudioCapture> Capture;
    TQueue<TArray<uint8>, EQueueMode::Mpsc> PendingAudio;
    TAtomic<int32> QueuedChunks{0};
    TAtomic<bool> bRecording{false};
    TAtomic<int32> MicLevelMilli{0};
    double ResamplePosition = 0;
    bool bReady = false;
    bool bOffline = false;
    bool bAwaitingReply = false;
    bool bResponseDone = false;
    /** The game gave up on the last turn (it barked): anything the relay still sends for that turn is ignored. */
    bool bStaleTurn = false;
    bool bTurnEndPending = false;
    bool bSocketFailed = false;
    bool bSocketClosed = false;
    bool bClosedForRestart = false;
    bool bClosedBusy = false;
    bool bRestartPending = false;
    FString PendingTypedLine;
    int32 SentBytes = 0;
    int32 HeldBytes = 0;
    int32 MaxRecordBytes = 0;
    double ConnectStarted = 0.0;
    double AwaitStarted = 0.0;
    double SpeechEndedAt = -1.0e9;
    int64 QueuedOutputBytes = 0;
    FString LastContextJson;
    FString Speaker;
    FString NpcText;
    FString PlayerText;
    FString LastReplyId;
    EReflectionsReplySource LastSource = EReflectionsReplySource::None;
    TMap<EReflectionsReplySource, int32> ReplyCounts;
    TWeakObjectPtr<AActor> VoiceNpc;
    UPROPERTY(Transient) TObjectPtr<USoundWaveProcedural> OutputWave;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> OutputAudio;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> BarkAudio;
    static double RelayDownUntil;
    static bool bForceFallback;
};
