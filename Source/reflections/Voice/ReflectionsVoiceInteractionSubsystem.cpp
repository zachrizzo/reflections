#include "Voice/ReflectionsVoiceInteractionSubsystem.h"
#include "Components/InputComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Voice/ReflectionsNpcDialogueOverlay.h"
#include "Voice/ReflectionsAmbientTalk.h"
#include "Voice/ReflectionsNpcRelayHost.h"
#include "Voice/ReflectionsNpcDialogueSettings.h"
#include "Voice/ReflectionsRealtimeVoiceComponent.h"
#include "UObject/UnrealType.h"
#include "Widgets/Input/SEditableTextBox.h"

#define LOCTEXT_NAMESPACE "ReflectionsNpcDialogue"

static TAutoConsoleVariable<bool> CVarReflectionsNpcDialogue(
    TEXT("Reflections.NpcDialogue"), true,
    TEXT("NPC talk-back (hold T / D-pad Down near an NPC, Enter to type). Read when a world starts."));

namespace
{
    constexpr float PreconnectDelay = 0.35f;
    constexpr float ConversationSeconds = 5.0f;

    UReflectionsNpcReactionComponent* NpcOf(AActor* Actor)
    {
        if (!IsValid(Actor)) return nullptr;
        if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Actor))
        {
            if (UReflectionsNpcReactionComponent* Found = Npcs->FindNpc(Actor)) return Found;
        }
        return Actor->FindComponentByClass<UReflectionsNpcReactionComponent>();
    }

    /** Calls a UFUNCTION taking one bool (e.g. SetRemarksMuted) by name; nothing happens if it doesn't exist. */
    void CallBoolSetter(UObject* Object, FName Name, bool bValue)
    {
        UFunction* Function = Object ? Object->FindFunction(Name) : nullptr;
        const FBoolProperty* Arg = Function && Function->NumParms == 1 ? CastField<FBoolProperty>(Function->PropertyLink) : nullptr;
        if (!Arg) return;
        TArray<uint8> Params;
        Params.SetNumZeroed(Function->ParmsSize);
        Arg->SetPropertyValue_InContainer(Params.GetData(), bValue);
        Object->ProcessEvent(Function, Params.GetData());
    }

    /** Calls a bool-returning, parameterless UFUNCTION by name (no header dependency). bDefault if it is absent. */
    bool CallBoolFunction(UObject* Object, FName Name, bool bDefault)
    {
        UFunction* Function = Object ? Object->FindFunction(Name) : nullptr;
        const FBoolProperty* Result = Function ? CastField<FBoolProperty>(Function->GetReturnProperty()) : nullptr;
        if (!Result || Function->NumParms != 1) return bDefault;
        TArray<uint8> Params;
        Params.SetNumZeroed(Function->ParmsSize);
        Object->ProcessEvent(Function, Params.GetData());
        return Result->GetPropertyValue_InContainer(Params.GetData());
    }
}

bool UReflectionsVoiceInteractionSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
    return Super::ShouldCreateSubsystem(Outer) && CVarReflectionsNpcDialogue.GetValueOnGameThread();
}

bool UReflectionsVoiceInteractionSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

bool UReflectionsVoiceInteractionSubsystem::IsTickable() const
{
    return GetWorld() && GetWorld()->IsGameWorld() && !HasAnyFlags(RF_ClassDefaultObject);
}

void UReflectionsVoiceInteractionSubsystem::EnsureSetup()
{
    if (Input || !GetWorld()) return;
    APlayerController* PC = GetWorld()->GetFirstPlayerController();
    if (!PC || !PC->IsLocalController() || !PC->GetPawn()) return;
    Controller = PC;
    Voice = NewObject<UReflectionsRealtimeVoiceComponent>(PC);
    Voice->RegisterComponent();
    Voice->OnDialogueLine.AddDynamic(this, &UReflectionsVoiceInteractionSubsystem::OnLine);
    TWeakObjectPtr<UReflectionsVoiceInteractionSubsystem> Self(this);
    Voice->ActionsProvider = [Self](AActor* Npc) { return Self.IsValid() ? Self->GetAvailableActions(Npc) : TArray<FString>(); };
    Voice->ActionHandler = [Self](AActor* Npc, const FString& Name, const FString& Target, FString& Reason) {
        return Self.IsValid() && Self->ExecuteAction(Npc, Name, Target, Reason);
    };
    Input = NewObject<UInputComponent>(PC);
    Input->RegisterComponent();
    // Hold to talk and release to send.
    for (const FKey& Key : {EKeys::E, EKeys::T, EKeys::Gamepad_DPad_Down})
    {
        Input->BindKey(Key, IE_Pressed, this, &UReflectionsVoiceInteractionSubsystem::OnTalkPressed).bConsumeInput = false;
        Input->BindKey(Key, IE_Released, this, &UReflectionsVoiceInteractionSubsystem::OnTalkReleased).bConsumeInput = false;
    }
    Input->BindKey(EKeys::Enter, IE_Pressed, this, &UReflectionsVoiceInteractionSubsystem::OnTypePressed).bConsumeInput = false;
    PC->PushInputComponent(Input);
    if (UGameViewportClient* Viewport = GetWorld()->GetGameViewport())
    {
        Overlay = SNew(SReflectionsNpcDialogueOverlay);
        TWeakObjectPtr<UReflectionsVoiceInteractionSubsystem> WeakThis(this);
        Overlay->OnTypedLine = [WeakThis](const FString& Line) {
            if (!WeakThis.IsValid()) return;
            WeakThis->FinishTyping();
            if (WeakThis->Voice) WeakThis->Voice->SendTypedLine(Line);
        };
        Overlay->OnTypingCancelled = [WeakThis]() { if (WeakThis.IsValid()) WeakThis->FinishTyping(); };
        Viewport->AddViewportWidgetContent(Overlay.ToSharedRef(), 50);
    }
}

bool UReflectionsVoiceInteractionSubsystem::CanTalkTo(AActor* Npc) const
{
    if (!IsValid(Npc)) return false;
    UReflectionsNpcReactionComponent* Reaction = NpcOf(Npc);
    // Not while dead, or while a scripted moment (the Tarnish taking the body) holds the NPC.
    return !Reaction || (!Reaction->IsIncapacitated() && !CallBoolFunction(Reaction, TEXT("IsScripted"), false));
}

AActor* UReflectionsVoiceInteractionSubsystem::FindTalkTarget(const APawn* Pawn) const
{
    if (!Pawn) return nullptr;
    const float Radius = GetDefault<UReflectionsNpcDialogueSettings>()->TalkRadius;
    TArray<AActor*> Npcs;
    if (UReflectionsNpcSubsystem* System = UReflectionsNpcSubsystem::Get(Pawn)) Npcs = System->GetNpcActors();
    if (Npcs.IsEmpty())
    {
        for (TActorIterator<AActor> It(GetWorld()); It; ++It) if (It->ActorHasTag(TEXT("NPC_Reactive"))) Npcs.Add(*It);
    }
    FVector View = Pawn->GetControlRotation().Vector();
    View.Z = 0.0;
    View = View.GetSafeNormal();
    AActor* Best = nullptr;
    double BestScore = TNumericLimits<double>::Max();
    for (AActor* Npc : Npcs)
    {
        if (!CanTalkTo(Npc) || Npc == Pawn) continue;
        FVector Offset = Npc->GetActorLocation() - Pawn->GetActorLocation();
        const double Distance = Offset.Size();
        if (Distance > Radius) continue;
        Offset.Z = 0.0;
        const double Facing = View.IsNearlyZero() ? 0.0 : FVector::DotProduct(View, Offset.GetSafeNormal());
        const double Score = Distance * (1.6 - Facing);  // prefer whoever the camera faces
        if (Score < BestScore) { BestScore = Score; Best = Npc; }
    }
    return Best;
}

void UReflectionsVoiceInteractionSubsystem::Tick(float DeltaTime)
{
    // Ambient NPC lines whose speaker the player has left behind fade out (ReflectionsAmbientTalk).
    ReflectionsAmbientTalk::Tick(GetWorld());
    EnsureSetup();
    APlayerController* PC = Controller.Get();
    APawn* Pawn = PC ? PC->GetPawn() : nullptr;
    if (!Voice || !Pawn) return;
    const float Radius = GetDefault<UReflectionsNpcDialogueSettings>()->TalkRadius;

    // Keep talking to the same NPC while the conversation is live, even a little out of range.
    AActor* Talking = Partner.Get();
    const bool bLive = Talking && CanTalkTo(Talking) && (Voice->IsBusy() || Voice->IsListening() ||
        Voice->SecondsSinceSpeech() < ConversationSeconds) &&
        FVector::Dist(Talking->GetActorLocation(), Pawn->GetActorLocation()) < Radius * 1.6f;
    AActor* Next = bLive ? Talking : FindTalkTarget(Pawn);
    if (!bLive && Talking) { Partner.Reset(); ReleaseFacing(); }
    Target = Next;

    // Open the relay session a moment after an NPC comes into reach, so the first reply is quick.
    if (Next != Candidate.Get()) { Candidate = Next; CandidateTime = 0.0f; }
    else CandidateTime += DeltaTime;
    if (Next && CandidateTime >= PreconnectDelay && !Voice->IsBusy() && !Voice->IsListening())
    {
        Voice->ConnectToNpc(Next);  // no-op while connected to it; reopens a session the relay ended
    }
    if (!Next && Voice->GetVoiceNpc() && !Voice->IsBusy() && !Voice->IsListening())
    {
        FarTime += DeltaTime;
        if (FarTime > 6.0f) { Voice->DisconnectVoice(); FarTime = 0.0f; }
    }
    else FarTime = 0.0f;

    if (Overlay)
    {
        const bool bTyping = Overlay->IsTyping();
        // A key saved in Settings restarted the helper: reconnect to it now.
        if (SeenRelayGeneration != UReflectionsNpcRelayHost::GetLaunchGeneration())
        {
            SeenRelayGeneration = UReflectionsNpcRelayHost::GetLaunchGeneration();
            if (!Voice->IsBusy() && !Voice->IsListening()) Voice->DisconnectVoice();
            Voice->ClearRelayDown();
        }
        // Live talk needs the player's own key; without it E gets a recorded line and the prompt says how to go live.
        const bool bLiveVoice = Voice->IsRelayAvailable();
        const FText TalkPrompt = bLiveVoice
            ? LOCTEXT("Prompt", "Hold E or D-pad Down to speak   ·   Enter to type")
            : LOCTEXT("PromptOffline", "E or D-pad Down   Talk");
        Overlay->SetPrompt(Next && (!Voice->IsListening() || !bLiveVoice) && !bTyping ? TalkPrompt : FText::GetEmpty());
        Overlay->SetStatus(FText::GetEmpty());
        // A clear listening display only while the mic is really open, then a thinking beat until the NPC answers.
        Overlay->SetListening(bLiveVoice && Voice->IsListening(), Voice->GetMicLevel());
        Overlay->SetThinking(Voice->GetState() == EReflectionsDialogueState::Thinking
            ? FText::FromString(Voice->GetSpeakerName()) : FText::GetEmpty());
        if (Voice->IsSpeaking() || Voice->IsBusy())
        {
            // Walk away mid-reply: the voice fades with distance and the subtitle goes once out of earshot.
            if (IsInEarshot(Voice->GetVoiceNpc())) Overlay->KeepLines();
            else Overlay->ClearLines();
        }
        if (bTyping && !Next) { Overlay->CloseTyping(); FinishTyping(); }
        // Hit while typing: give the player their controls back at once.
        if (const UReflectionsHealthComponent* Health = Pawn->FindComponentByClass<UReflectionsHealthComponent>())
        {
            const bool bHurt = LastPlayerHealth >= 0.0f && Health->Health < LastPlayerHealth - 0.01f;
            LastPlayerHealth = Health->Health;
            if (bHurt && Overlay->IsTyping()) { Overlay->CloseTyping(); FinishTyping(); }
        }
    }
    UpdateFacing(DeltaTime);
    // An NPC in a conversation doesn't also say its passing remarks over the reply (NPC unify's SetRemarksMuted).
    if (MutedNpc.Get() != Partner.Get())
    {
        if (AActor* Old = MutedNpc.Get()) CallBoolSetter(NpcOf(Old), TEXT("SetRemarksMuted"), false);
        MutedNpc = Partner;
        if (AActor* New = MutedNpc.Get()) CallBoolSetter(NpcOf(New), TEXT("SetRemarksMuted"), true);
    }
}

void UReflectionsVoiceInteractionSubsystem::OnTalkPressed()
{
    bHeld = true;
    if (!Voice || (Overlay && Overlay->IsTyping())) return;
    AActor* Npc = Target.Get();
    if (!Npc) return;
    Voice->ConnectToNpc(Npc);
    Partner = Npc;
    Voice->BeginPushToTalk();
}

void UReflectionsVoiceInteractionSubsystem::OnTalkReleased()
{
    bHeld = false;
    if (Voice) Voice->EndPushToTalk();
}

void UReflectionsVoiceInteractionSubsystem::OnTypePressed()
{
    APlayerController* PC = Controller.Get();
    AActor* Npc = Target.Get();
    if (!Voice || !Overlay || !PC || !Npc || Overlay->IsTyping() || Voice->IsListening()) return;
    Voice->ConnectToNpc(Npc);
    Partner = Npc;
    Overlay->OpenTyping(FText::Format(LOCTEXT("TypeHint", "Say something to the {0}...  (Enter to send, Esc to cancel)"),
        FText::FromString(Voice->GetSpeakerName().ToLower())));
    FInputModeUIOnly Mode;
    Mode.SetWidgetToFocus(Overlay->GetTypingBox());
    Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
    PC->SetInputMode(Mode);
}

void UReflectionsVoiceInteractionSubsystem::FinishTyping()
{
    if (APlayerController* PC = Controller.Get())
    {
        PC->SetInputMode(FInputModeGameOnly());
    }
}

bool UReflectionsVoiceInteractionSubsystem::SayToNpc(AActor* Npc, const FString& Text)
{
    EnsureSetup();
    if (!Voice || !IsValid(Npc)) return false;
    // No live reply (a model call and speech) for an NPC the player could not hear anyway.
    if (!ReflectionsAmbientTalk::IsWithinHearing(Npc, false)) return false;
    Voice->ConnectToNpc(Npc);
    Partner = Npc;
    Target = Npc;
    return Voice->SendTypedLine(Text);
}

void UReflectionsVoiceInteractionSubsystem::OnLine(const FString& Speaker, const FString& Text, bool bPlayer, bool bFinal)
{
    if (!Overlay || !GetDefault<UReflectionsNpcDialogueSettings>()->bShowSubtitles || Text.IsEmpty()) return;
    if (!bPlayer && !IsInEarshot(Voice ? Voice->GetVoiceNpc() : nullptr)) return;
    const EReflectionsReplySource Source = Voice ? Voice->GetLastReplySource() : EReflectionsReplySource::None;
    const bool bAi = Source == EReflectionsReplySource::Generated || Source == EReflectionsReplySource::Cached;
    Overlay->ShowLine(Speaker, Text, bPlayer, bAi);
}

bool UReflectionsVoiceInteractionSubsystem::IsInEarshot(const AActor* Npc) const
{
    const APawn* Pawn = Controller.IsValid() ? Controller->GetPawn() : nullptr;
    if (!Npc || !Pawn) return false;
    return FVector::Dist(Npc->GetActorLocation(), Pawn->GetActorLocation()) <= GetDefault<UReflectionsNpcDialogueSettings>()->SubtitleRadius;
}

namespace
{
    const FName NoStrollTag(TEXT("NPC_NoStroll"));
    /** In a conversation with the player: crowd spots let go of it, a halted squad stops turning it to its slot. */
    const FName TalkingTag(TEXT("NPC_Talking"));

}

void UReflectionsVoiceInteractionSubsystem::UpdateFacing(float DeltaTime)
{
    AActor* Npc = Partner.Get();
    APawn* Pawn = Controller.IsValid() ? Controller->GetPawn() : nullptr;
    if (!GetDefault<UReflectionsNpcDialogueSettings>()->bFaceSpeaker || !Npc || !Pawn) { ReleaseFacing(); return; }
    UReflectionsNpcReactionComponent* Reaction = NpcOf(Npc);
    if (!Reaction) return;
    const EReflectionsNpcReaction Mood = Reaction->Reaction;
    const bool bCanTurn = Mood == EReflectionsNpcReaction::Calm || Mood == EReflectionsNpcReaction::Alert ||
        Mood == EReflectionsNpcReaction::Investigating;
    if (!bCanTurn || Reaction->GetEngagedTarget()) { ReleaseFacing(); return; }
    // A different NPC than last tick: hand the old one back to its routine first.
    if (TalkTagNpc.IsValid() && TalkTagNpc.Get() != Npc) ReleaseFacing();
    // Tagged for the conversation (every tick: a crowd spot that lets go removes the NPC_NoStroll it added):
    // crowd strolling lets go of NPC_NoStroll, crowd spots of NPC_Talking.
    TalkTagNpc = Npc;
    Npc->Tags.AddUnique(TalkingTag);
    if (!Npc->ActorHasTag(NoStrollTag))
    {
        Npc->Tags.Add(NoStrollTag);
        bAddedNoStroll = true;
    }
    const FVector Point = Pawn->GetActorLocation();
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (SteeredNpc.Get() != Npc)
    {
        if (Reaction->IsExternallySteered()) return;
        Reaction->SetExternallySteered(true);
        SteeredNpc = Npc;
        // It stops walking for the conversation.
        if (ACharacter* Mover = Reaction->GetMovementCharacter())
        {
            if (UCharacterMovementComponent* Movement = Mover->GetCharacterMovement()) Movement->StopMovementImmediately();
        }
    }
    if (Npcs) Npcs->TurnNpcTowards(Npc, Point, DeltaTime);
}

void UReflectionsVoiceInteractionSubsystem::ReleaseFacing()
{
    if (AActor* Npc = SteeredNpc.Get())
    {
        if (UReflectionsNpcReactionComponent* Reaction = NpcOf(Npc)) Reaction->SetExternallySteered(false);
    }
    SteeredNpc.Reset();
    // Back to its routine: crowd strolling and spots may take it again.
    if (AActor* Npc = TalkTagNpc.Get())
    {
        Npc->Tags.Remove(TalkingTag);
        if (bAddedNoStroll) Npc->Tags.Remove(NoStrollTag);
    }
    TalkTagNpc.Reset();
    bAddedNoStroll = false;
}

TArray<FString> UReflectionsVoiceInteractionSubsystem::GetAvailableActions(AActor* Npc) const
{
    if (!CanTalkTo(Npc)) return {};
    return {TEXT("end_conversation")};
}

bool UReflectionsVoiceInteractionSubsystem::ExecuteAction(AActor* Npc, const FString& Name, const FString& TargetName, FString& OutReason)
{
    if (Name != TEXT("end_conversation") || !CanTalkTo(Npc) || Partner.Get() != Npc)
    {
        OutReason = TEXT("not possible right now");
        return false;
    }
    Partner.Reset();
    ReleaseFacing();
    return true;
}

void UReflectionsVoiceInteractionSubsystem::PressTalkKey(bool bDown)
{
    EnsureSetup();
    if (bDown) OnTalkPressed();
    else OnTalkReleased();
}

FString UReflectionsVoiceInteractionSubsystem::GetTalkPromptText() const
{
    return Overlay ? Overlay->GetPrompt().ToString() : FString();
}

bool UReflectionsVoiceInteractionSubsystem::IsListeningShown() const
{
    return Overlay && Overlay->IsShowingListening();
}

bool UReflectionsVoiceInteractionSubsystem::IsThinkingShown() const
{
    return Overlay && Overlay->IsShowingThinking();
}

FString UReflectionsVoiceInteractionSubsystem::DescribeStatus() const
{
    if (!Voice) return TEXT("NPC dialogue: no local player yet.");
    const FString Url = UReflectionsNpcDialogueSettings::ResolveRelayUrl();
    return FString::Printf(TEXT("NPC dialogue: relay %s (%s); target %s; partner %s; state %d; replies generated %d, cached %d, barks %d; last %s"),
        Url.IsEmpty() ? TEXT("(none: barks only)") : *Url, Voice->IsRelayAvailable() ? TEXT("available") : TEXT("barks"),
        Target.IsValid() ? *Target->GetName() : TEXT("-"), Partner.IsValid() ? *Partner->GetName() : TEXT("-"),
        static_cast<int32>(Voice->GetState()), Voice->GetRepliesBySource(EReflectionsReplySource::Generated),
        Voice->GetRepliesBySource(EReflectionsReplySource::Cached), Voice->GetRepliesBySource(EReflectionsReplySource::Bark),
        *Voice->GetLastReplyId());
}

void UReflectionsVoiceInteractionSubsystem::Deinitialize()
{
    ReleaseFacing();
    if (AActor* Old = MutedNpc.Get()) CallBoolSetter(NpcOf(Old), TEXT("SetRemarksMuted"), false);
    if (APlayerController* PC = Controller.Get()) { if (Input) PC->PopInputComponent(Input); }
    if (Input) Input->DestroyComponent();
    if (Voice) { Voice->DisconnectVoice(); Voice->DestroyComponent(); }
    if (Overlay)
    {
        if (UWorld* World = GetWorld()) { if (UGameViewportClient* Viewport = World->GetGameViewport()) Viewport->RemoveViewportWidgetContent(Overlay.ToSharedRef()); }
        Overlay.Reset();
    }
    Input = nullptr; Voice = nullptr;
    Super::Deinitialize();
}

#if !UE_BUILD_SHIPPING
namespace
{
    UReflectionsVoiceInteractionSubsystem* DialogueOf(UWorld* World)
    {
        return World ? World->GetSubsystem<UReflectionsVoiceInteractionSubsystem>() : nullptr;
    }

    FAutoConsoleCommandWithWorldAndArgs GNpcSay(TEXT("Npc.Say"), TEXT("Npc.Say <text>: type a line to the NPC in reach (or the last one talked to)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World) {
            UReflectionsVoiceInteractionSubsystem* Dialogue = DialogueOf(World);
            AActor* Npc = Dialogue ? Dialogue->GetTalkTarget() : nullptr;
            if (!Npc) { UE_LOG(LogReflectionsNpcDialogue, Warning, TEXT("Npc.Say: no NPC in reach.")); return; }
            Dialogue->SayToNpc(Npc, FString::Join(Args, TEXT(" ")));
        }));

    FAutoConsoleCommandWithWorldAndArgs GNpcSayTo(TEXT("Npc.SayTo"), TEXT("Npc.SayTo <actor name or label part> <text>: type a line to that NPC, wherever it is."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World) {
            UReflectionsVoiceInteractionSubsystem* Dialogue = DialogueOf(World);
            UReflectionsNpcSubsystem* Npcs = World ? UReflectionsNpcSubsystem::Get(World) : nullptr;
            if (!Dialogue || !Npcs || Args.Num() < 2) { UE_LOG(LogReflectionsNpcDialogue, Warning, TEXT("Npc.SayTo <name> <text>")); return; }
            AActor* Found = nullptr;
            for (AActor* Npc : Npcs->GetNpcActors())
            {
                if (Npc && (Npc->GetName().Contains(Args[0])
#if WITH_EDITOR
                    || Npc->GetActorLabel().Contains(Args[0])
#endif
                    )) { Found = Npc; break; }
            }
            if (!Found) { UE_LOG(LogReflectionsNpcDialogue, Warning, TEXT("Npc.SayTo: no NPC named like %s."), *Args[0]); return; }
            TArray<FString> Rest(Args);
            Rest.RemoveAt(0);
            Dialogue->SayToNpc(Found, FString::Join(Rest, TEXT(" ")));
        }));

    FAutoConsoleCommandWithWorld GNpcStatus(TEXT("Npc.DialogueStatus"), TEXT("Prints the NPC dialogue state."),
        FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World) {
            if (UReflectionsVoiceInteractionSubsystem* Dialogue = DialogueOf(World)) UE_LOG(LogReflectionsNpcDialogue, Display, TEXT("%s"), *Dialogue->DescribeStatus());
        }));

    FAutoConsoleCommandWithWorldAndArgs GNpcFallback(TEXT("Npc.DialogueFallback"), TEXT("Npc.DialogueFallback 1: act as if there were no relay (barks only). 0: normal."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World) {
            const bool bForce = Args.Num() > 0 && Args[0] == TEXT("1");
            UReflectionsRealtimeVoiceComponent::SetForceFallback(bForce);
            if (UReflectionsVoiceInteractionSubsystem* Dialogue = DialogueOf(World)) { if (Dialogue->GetVoice()) Dialogue->GetVoice()->DisconnectVoice(); }
            UE_LOG(LogReflectionsNpcDialogue, Display, TEXT("NPC dialogue fallback %s."), bForce ? TEXT("forced on") : TEXT("off"));
        }));
}
#endif

float UReflectionsVoiceInteractionSubsystem::GetPanelTopFromBottom() const
{
    return Overlay.IsValid() ? Overlay->GetPanelTopFromBottom() : 0.0f;
}

#undef LOCTEXT_NAMESPACE
