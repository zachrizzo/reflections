#pragma once

#include "CoreMinimal.h"
#include "AudioCaptureCore.h"
#include "Components/ActorComponent.h"
#include "Containers/Queue.h"
#include "ReflectionsRealtimeVoiceComponent.generated.h"

class IWebSocket;
class UAudioComponent;
class USoundWaveProcedural;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FReflectionsVoiceStatus, const FString&, Status);

/** Development-only, loopback voice client. The OpenAI key never enters the game. */
UCLASS(ClassGroup=(Voice), BlueprintType, meta=(BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsRealtimeVoiceComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UReflectionsRealtimeVoiceComponent();
    virtual ~UReflectionsRealtimeVoiceComponent();

    /** Start the local relay separately first. Supply the NPC being addressed. */
    UFUNCTION(BlueprintCallable, Category="Voice") void ConnectToNpc(AActor* Npc);
    UFUNCTION(BlueprintCallable, Category="Voice") void BeginPushToTalk();
    UFUNCTION(BlueprintCallable, Category="Voice") void EndPushToTalk();
    UFUNCTION(BlueprintCallable, Category="Voice") void DisconnectVoice();
    AActor* GetVoiceNpc() const { return VoiceNpc.Get(); }
    bool IsVoiceReady() const { return bReady; }
    UPROPERTY(BlueprintAssignable, Category="Voice") FReflectionsVoiceStatus OnVoiceStatus;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Voice") FString Status;
protected:
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTick) override;
private:
    void SetStatus(const FString& Next);
    void OnMessage(const FString& Message);
    void SendJson(const TSharedRef<class FJsonObject>& Object);
    void FlushCaptured();
    void StopCapture();
    TSharedPtr<IWebSocket> Socket;
    TUniquePtr<Audio::FAudioCapture> Capture;
    TQueue<TArray<uint8>, EQueueMode::Mpsc> PendingAudio;
    TAtomic<int32> QueuedChunks{0};
    TAtomic<bool> bRecording{false};
    double ResamplePosition = 0;
    bool bReady = false;
    bool bWaitingResponse = false;
    bool bResponseDone = false;
    int32 SentBytes = 0;
    TWeakObjectPtr<AActor> VoiceNpc;
    UPROPERTY(Transient) TObjectPtr<USoundWaveProcedural> OutputWave;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> OutputAudio;
};
