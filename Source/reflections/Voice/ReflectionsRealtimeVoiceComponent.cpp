#include "Voice/ReflectionsRealtimeVoiceComponent.h"
#include "AudioCaptureCore.h"
#include "Components/AudioComponent.h"
#include "Dom/JsonObject.h"
#include "HAL/PlatformMisc.h"
#include "IWebSocket.h"
#include "Misc/Base64.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Sound/SoundWaveProcedural.h"
#include "WebSocketsModule.h"

UReflectionsRealtimeVoiceComponent::UReflectionsRealtimeVoiceComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
}
UReflectionsRealtimeVoiceComponent::~UReflectionsRealtimeVoiceComponent() = default;

void UReflectionsRealtimeVoiceComponent::SetStatus(const FString& Next)
{
    Status = Next;
    OnVoiceStatus.Broadcast(Status);
}
void UReflectionsRealtimeVoiceComponent::SendJson(const TSharedRef<FJsonObject>& Object)
{
    if (!Socket.IsValid() || !Socket->IsConnected()) return;
    FString Text;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
    if (FJsonSerializer::Serialize(Object, Writer)) Socket->Send(Text);
}
void UReflectionsRealtimeVoiceComponent::ConnectToNpc(AActor* Npc)
{
    DisconnectVoice();
    if (!IsValid(Npc)) { SetStatus(TEXT("No NPC selected.")); return; }
    const FString Token = FPlatformMisc::GetEnvironmentVariable(TEXT("REFLECTIONS_VOICE_LOCAL_TOKEN"));
    if (Token.Len() < 32) { SetStatus(TEXT("Voice relay token is not configured.")); return; }
    VoiceNpc = Npc;
    OutputWave = NewObject<USoundWaveProcedural>(this);
    OutputWave->SetSampleRate(24000);
    OutputWave->NumChannels = 1;
    OutputWave->Duration = INDEFINITELY_LOOPING_DURATION;
    OutputAudio = NewObject<UAudioComponent>(Npc);
    OutputAudio->bAutoActivate = false;
    OutputAudio->SetSound(OutputWave);
    OutputAudio->RegisterComponent();
    if (Npc->GetRootComponent()) OutputAudio->AttachToComponent(Npc->GetRootComponent(), FAttachmentTransformRules::KeepRelativeTransform);

    Socket = FWebSocketsModule::Get().CreateWebSocket(TEXT("ws://127.0.0.1:8765"));
    Socket->OnConnected().AddWeakLambda(this, [this, Token]() {
        TSharedRef<FJsonObject> Context = MakeShared<FJsonObject>();
        AActor* Target = VoiceNpc.Get();
        Context->SetStringField(TEXT("name"), IsValid(Target) ? Target->GetName().Left(80) : TEXT("Citizen"));
        if (IsValid(Target))
        {
            if (const UReflectionsNpcReactionComponent* Reaction = Target->FindComponentByClass<UReflectionsNpcReactionComponent>())
            {
                Context->SetStringField(TEXT("mood"), FString::Printf(TEXT("Reaction: %s; fear: %.2f; hostility: %.2f"),
                    *StaticEnum<EReflectionsNpcReaction>()->GetNameStringByValue(static_cast<int64>(Reaction->Reaction)), Reaction->Fear, Reaction->Hostility));
                Context->SetStringField(TEXT("description"), StaticEnum<EReflectionsNpcDisposition>()->GetNameStringByValue(static_cast<int64>(Reaction->Disposition)));
            }
        }
        TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
        Msg->SetStringField(TEXT("type"), TEXT("session.start"));
        Msg->SetStringField(TEXT("token"), Token);
        Msg->SetObjectField(TEXT("npc"), Context);
        SendJson(Msg);
        SetStatus(TEXT("Connecting to AI voice..."));
    });
    Socket->OnMessage().AddWeakLambda(this, [this](const FString& Message) { OnMessage(Message); });
    Socket->OnConnectionError().AddWeakLambda(this, [this](const FString&) { bReady = false; SetStatus(TEXT("Voice relay unavailable.")); });
    Socket->OnClosed().AddWeakLambda(this, [this](int32, const FString&, bool) { bReady = false; StopCapture(); SetStatus(TEXT("Voice disconnected.")); });
    SetStatus(TEXT("Connecting to local voice relay..."));
    Socket->Connect();
}

void UReflectionsRealtimeVoiceComponent::OnMessage(const FString& Message)
{
    TSharedPtr<FJsonObject> Json;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Message), Json) || !Json.IsValid()) return;
    FString Type; if (!Json->TryGetStringField(TEXT("type"), Type)) return;
    if (Type == TEXT("session.ready")) { bReady = true; SetStatus(TEXT("AI voice ready: hold T to speak.")); }
    else if (Type == TEXT("response.output_audio.delta"))
    {
        FString Encoded; TArray<uint8> Bytes;
        if (OutputWave && Json->TryGetStringField(TEXT("delta"), Encoded) && FBase64::Decode(Encoded, Bytes) && Bytes.Num() > 0 && Bytes.Num() <= 100000)
        {
            OutputWave->QueueAudio(Bytes.GetData(), Bytes.Num());
            if (OutputAudio && !OutputAudio->IsPlaying()) OutputAudio->Play();
        }
    }
    else if (Type == TEXT("response.done")) { bResponseDone = true; }
    else if (Type == TEXT("relay.error")) { bWaitingResponse = false; SetStatus(TEXT("Voice service error.")); }
}

void UReflectionsRealtimeVoiceComponent::BeginPushToTalk()
{
    if (!bReady || bWaitingResponse || bRecording.Load()) return;
    Capture = MakeUnique<Audio::FAudioCapture>();
    Audio::FAudioCaptureDeviceParams Params;
    Params.bUseHardwareAEC = true;
    ResamplePosition = 0;
    SentBytes = 0;
    bRecording.Store(true);
    const bool bOpened = Capture->OpenAudioCaptureStream(Params,
        [this](const void* Buffer, int32 Frames, int32 Channels, int32 Rate, double, bool) {
            if (!bRecording.Load() || !Buffer || Channels <= 0 || Rate <= 0 || Frames <= 0 || QueuedChunks.Load() >= 100) return;
            const float* Input = static_cast<const float*>(Buffer);
            TArray<uint8> Data;
            const double Step = static_cast<double>(Rate) / 24000.0;
            while (ResamplePosition < Frames)
            {
                const int32 Frame = static_cast<int32>(ResamplePosition);
                float Mono = 0;
                for (int32 Channel = 0; Channel < Channels; ++Channel) Mono += Input[Frame * Channels + Channel];
                Mono = FMath::Clamp(Mono / Channels, -1.0f, 1.0f);
                const int16 Sample = static_cast<int16>(Mono * 32767.0f);
                Data.Add(static_cast<uint8>(Sample & 255)); Data.Add(static_cast<uint8>((Sample >> 8) & 255));
                ResamplePosition += Step;
            }
            ResamplePosition -= Frames;
            if (Data.Num()) { ++QueuedChunks; PendingAudio.Enqueue(MoveTemp(Data)); }
        }, 1024);
    if (!bOpened || !Capture->StartStream()) { StopCapture(); SetStatus(TEXT("Microphone unavailable.")); return; }
    SetStatus(TEXT("Listening to microphone..."));
}
void UReflectionsRealtimeVoiceComponent::FlushCaptured()
{
    TArray<uint8> Data;
    while (PendingAudio.Dequeue(Data))
    {
        --QueuedChunks;
        SentBytes += Data.Num();
        TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
        Msg->SetStringField(TEXT("type"), TEXT("input_audio_buffer.append"));
        Msg->SetStringField(TEXT("audio"), FBase64::Encode(Data));
        SendJson(Msg);
    }
}
void UReflectionsRealtimeVoiceComponent::StopCapture()
{
    bRecording.Store(false);
    if (Capture) { if (Capture->IsStreamOpen()) Capture->AbortStream(); Capture.Reset(); }
}
void UReflectionsRealtimeVoiceComponent::EndPushToTalk()
{
    if (!bRecording.Load()) return;
    StopCapture(); FlushCaptured();
    TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
    Msg->SetStringField(TEXT("type"), SentBytes ? TEXT("turn.end") : TEXT("turn.clear"));
    SendJson(Msg);
    bWaitingResponse = SentBytes > 0; bResponseDone = false;
    SetStatus(bWaitingResponse ? TEXT("NPC is responding...") : TEXT("No microphone audio captured."));
}
void UReflectionsRealtimeVoiceComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* Tick)
{
    Super::TickComponent(DeltaTime, TickType, Tick);
    if (bRecording.Load()) FlushCaptured();
    if (bWaitingResponse && bResponseDone && (!OutputWave || OutputWave->GetAvailableAudioByteCount() == 0))
    { bWaitingResponse = false; bResponseDone = false; SetStatus(TEXT("AI voice ready: hold T to speak.")); }
}
void UReflectionsRealtimeVoiceComponent::DisconnectVoice()
{
    StopCapture();
    if (Socket) { Socket->Close(); Socket.Reset(); }
    if (OutputAudio) { OutputAudio->Stop(); OutputAudio->DestroyComponent(); OutputAudio = nullptr; }
    OutputWave = nullptr; VoiceNpc.Reset(); bReady = false; bWaitingResponse = false; bResponseDone = false;
    TArray<uint8> Discard; while (PendingAudio.Dequeue(Discard)) {} QueuedChunks.Store(0);
}
void UReflectionsRealtimeVoiceComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    DisconnectVoice(); Super::EndPlay(Reason);
}
