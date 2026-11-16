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
#include "Quests/ReflectionsQuestWorldSubsystem.h"
#include "Squads/ReflectionsSquad.h"
#include "Squads/ReflectionsSquadSubsystem.h"
#include "Voice/ReflectionsNpcDialogueOverlay.h"
#include "Voice/ReflectionsAmbientTalk.h"
#include "Voice/ReflectionsNpcRelayHost.h"
#include "Worlds/ReflectionsSealedDoor.h"
#include "Worlds/ReflectionsWorldPickups.h"
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
    // One talk key: E on the keyboard (T still works), D-pad Down on a pad. OnTalkPressed decides: a person with quest
    // business gets the quest dialogue, anyone else live voice. The quest system binds neither while this exists.
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
        // The quest system shows "E  Talk to <name>" for a person with quest business; then E is the quest's.
        const UReflectionsQuestWorldSubsystem* Quests = UReflectionsQuestWorldSubsystem::Get(this);
        const bool bQuestPrompt = Quests && Quests->GetPromptTarget() && !Quests->GetPromptText().IsEmpty();
        const bool bQuestBusy = Quests && (Quests->IsTalkOpen() || Quests->IsJournalOpen());
        const bool bPad = Quests && Quests->IsUsingGamepad();
        // A key saved in Settings restarted the helper: reconnect to it now.
        if (SeenRelayGeneration != UReflectionsNpcRelayHost::GetLaunchGeneration())
        {
            SeenRelayGeneration = UReflectionsNpcRelayHost::GetLaunchGeneration();
            if (!Voice->IsBusy() && !Voice->IsListening()) Voice->DisconnectVoice();
            Voice->ClearRelayDown();
        }
        // Live talk needs the player's own key; without it E gets a recorded line and the prompt says how to go live.
        const bool bLiveVoice = Voice->IsRelayAvailable();
        FText TalkPrompt;
        if (bLiveVoice) TalkPrompt = bPad ? LOCTEXT("PromptPad", "Hold D-pad Down to speak") : LOCTEXT("Prompt", "Hold E to speak   ·   Enter to type");
        else if (!UReflectionsNpcRelayHost::HasGeminiKey()) TalkPrompt = LOCTEXT("PromptNoKey", "Add your Gemini API key in Settings to talk with characters in real time.");
        else TalkPrompt = bPad ? LOCTEXT("PromptPadOffline", "D-pad Down   Talk") : LOCTEXT("PromptOffline", "E   Talk");
        // Without live talk the hint stays up while E is held (the NPC answers with a recorded line on release).
        Overlay->SetPrompt(Next && (!Voice->IsListening() || !bLiveVoice) && !bTyping && !bQuestPrompt && !bQuestBusy ? TalkPrompt : FText::GetEmpty());
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
    bPressWentToQuest = false;
    if (!Voice || (Overlay && Overlay->IsTyping())) return;
    // Exactly one system acts on each press. The quest dialogue first: while it (or the journal) is open the key is
    // its own; and a person with quest business (the quest system's "E  Talk to <name>") opens it.
    if (UReflectionsQuestWorldSubsystem* Quests = UReflectionsQuestWorldSubsystem::Get(this))
    {
        if (Quests->IsTalkOpen() || Quests->IsJournalOpen()) { bPressWentToQuest = true; return; }
        AActor* QuestNpc = Quests->GetPromptTarget();
        if (QuestNpc && !Quests->GetPromptText().IsEmpty() && Quests->OpenTalk(QuestNpc, true)) { bPressWentToQuest = true; return; }
    }
    AActor* Npc = Target.Get();
    if (!Npc) return;
    // Anyone else: hold to speak, let go to send.
    Voice->ConnectToNpc(Npc);
    Partner = Npc;
    Voice->BeginPushToTalk();
}

void UReflectionsVoiceInteractionSubsystem::OnTalkReleased()
{
    bHeld = false;
    if (bPressWentToQuest) { bPressWentToQuest = false; return; }
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
    if (!bPlayer && bFinal && bAi && Voice)
    {
        UReflectionsRealtimeVoiceComponent::RememberTalk(Voice->GetVoiceNpc());
        UReflectionsRealtimeVoiceComponent::NotifyQuestTalkedTo(Voice->GetVoiceNpc());
    }
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

    /** A soldier whose squad stands still (not marching, fighting or reforming): it may turn in place to talk. */
    bool IsInIdleSquad(const AActor* Npc)
    {
        const UWorld* World = Npc ? Npc->GetWorld() : nullptr;
        const UReflectionsSquadSubsystem* Squads = World ? World->GetSubsystem<UReflectionsSquadSubsystem>() : nullptr;
        if (!Squads) return false;
        for (const AReflectionsSquad* Squad : Squads->GetSquads())
        {
            if (Squad && Squad->IsMember(Npc))
            {
                return Squad->State == EReflectionsSquadState::Halted || Squad->State == EReflectionsSquadState::Inactive;
            }
        }
        return false;
    }
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
    // While pointing the way, face the target instead of the player.
    const bool bPointing = LookTargetNpc.Get() == Npc && FPlatformTime::Seconds() < LookUntil;
    const FVector Point = bPointing ? LookTarget : Pawn->GetActorLocation();
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (SteeredNpc.Get() != Npc)
    {
        // Someone else still moves it. A crowd stroll or spot lets go within a tick or two. A squad keeps its
        // soldiers: one whose squad stands idle turns in place (yaw only), never while marching or fighting.
        // The lives system's schedules (Lives_Steered) hand the body over while the player is near.
        if (Reaction->IsExternallySteered() && !Npc->ActorHasTag(TEXT("Lives_Steered")))
        {
            if (Npcs && IsInIdleSquad(Npc)) Npcs->TurnNpcTowards(Npc, Point, DeltaTime);
            return;
        }
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

namespace
{
    constexpr double PointCooldown = 20.0;
    constexpr double WarnCooldown = 30.0;
    constexpr float GuardSearchRadius = 3000.0f;

    const TCHAR* TargetLabel(const FString& Target)
    {
        if (Target == TEXT("nearest_mirror_page")) return TEXT("Mirror page");
        if (Target == TEXT("nearest_shard")) return TEXT("Mirror shard");
        return TEXT("The Gilt Tower");
    }

    FString Bearing(const APlayerController* PC, const FVector& From, const FVector& To)
    {
        FVector Offset = To - From;
        Offset.Z = 0.0;
        const float ViewYaw = PC ? PC->GetControlRotation().Yaw : 0.0f;
        float Delta = FRotator::NormalizeAxis(Offset.Rotation().Yaw - ViewYaw);
        static const TCHAR* Names[] = {TEXT("ahead"), TEXT("ahead and to the right"), TEXT("to your right"), TEXT("behind you, to the right"),
            TEXT("behind you"), TEXT("behind you, to the left"), TEXT("to your left"), TEXT("ahead and to the left")};
        const int32 Sector = FMath::RoundToInt((Delta < 0.0f ? Delta + 360.0f : Delta) / 45.0f) % 8;
        return Names[Sector];
    }
}

AActor* UReflectionsVoiceInteractionSubsystem::FindTarget(const FString& TargetName, const FVector& From) const
{
    UWorld* World = GetWorld();
    if (!World) return nullptr;
    AActor* Best = nullptr;
    double BestDistance = TNumericLimits<double>::Max();
    const auto Consider = [&](AActor* Candidate) {
        if (!IsValid(Candidate) || Candidate->IsHidden() || Candidate->IsActorBeingDestroyed()) return;
        const double Distance = FVector::DistSquared(From, Candidate->GetActorLocation());
        if (Distance < BestDistance) { BestDistance = Distance; Best = Candidate; }
    };
    if (TargetName == TEXT("nearest_mirror_page")) for (TActorIterator<AReflectionsBookPagePickup> It(World); It; ++It) Consider(*It);
    else if (TargetName == TEXT("nearest_shard")) for (TActorIterator<AReflectionsCoinPickup> It(World); It; ++It) Consider(*It);
    else if (TargetName == TEXT("gilt_tower")) for (TActorIterator<AReflectionsSealedDoor> It(World); It; ++It) Consider(*It);
    return Best;
}

TArray<FString> UReflectionsVoiceInteractionSubsystem::GetAvailableActions(AActor* Npc) const
{
    TArray<FString> Actions;
    if (!CanTalkTo(Npc)) return Actions;
    const FName Group = UReflectionsRealtimeVoiceComponent::PersonaGroup(Npc);
    const bool bFriendlyKind = Group == TEXT("Civilian") || Group == TEXT("Guard") || Group == TEXT("Soldier");
    const double Now = FPlatformTime::Seconds();
    const double* Pointed = PointedAt.Find(Npc);
    if (bFriendlyKind && (!Pointed || Now - *Pointed > PointCooldown))
    {
        for (const TCHAR* Goal : {TEXT("nearest_mirror_page"), TEXT("nearest_shard"), TEXT("gilt_tower")})
        {
            if (FindTarget(Goal, Npc->GetActorLocation())) Actions.Add(FString(TEXT("point_the_way:")) + Goal);
        }
    }
    for (const TCHAR* Topic : {TEXT("sides"), TEXT("tarnish"), TEXT("shards"), TEXT("pages"), TEXT("final_spell"), TEXT("gilt_tower")})
    {
        Actions.Add(FString(TEXT("share_lore:")) + Topic);
    }
    if (Group == TEXT("Civilian") && Now - GuardsWarnedAt > WarnCooldown)
    {
        if (const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Npc))
        {
            for (AActor* Other : Npcs->GetNpcActors())
            {
                if (Other && Other != Npc && UReflectionsRealtimeVoiceComponent::PersonaGroup(Other) == TEXT("Guard") &&
                    FVector::Dist(Other->GetActorLocation(), Npc->GetActorLocation()) < GuardSearchRadius)
                {
                    Actions.Add(TEXT("warn_guards"));
                    break;
                }
            }
        }
    }
    Actions.Add(TEXT("end_conversation"));
    Actions.Append(UReflectionsRealtimeVoiceComponent::GetQuestActions(Npc));
    return Actions;
}

bool UReflectionsVoiceInteractionSubsystem::ExecuteAction(AActor* Npc, const FString& Name, const FString& TargetName, FString& OutReason)
{
    // Second check: the same rules that produced the offer, against the state right now.
    const FString Key = TargetName.IsEmpty() || TargetName == TEXT("none") ? Name : Name + TEXT(":") + TargetName;
    static const TSet<FString> QuestVerbs = {TEXT("offer_quest"), TEXT("accept"), TEXT("decline"), TEXT("turn_in"),
        TEXT("give_hint"), TEXT("choose"), TEXT("talk"), TEXT("deliver")};
    if (QuestVerbs.Contains(Name))
    {
        // The quest system re-checks against its live state; its line goes on screen and back to the relay.
        FString Say;
        const bool bOk = IsValid(Npc) && GetAvailableActions(Npc).Contains(Key) &&
            UReflectionsRealtimeVoiceComponent::ExecuteQuestAction(Npc, Key, OutReason, Say);
        if (bOk && Overlay && !Say.IsEmpty()) Overlay->ShowHint(FText::FromString(Say), 8.0);
        if (!Say.IsEmpty()) OutReason += TEXT("|say:") + Say;
        return bOk;
    }
    if (!IsValid(Npc) || !GetAvailableActions(Npc).Contains(Key))
    {
        OutReason = TEXT("not possible right now");
        return false;
    }
    APlayerController* PC = Controller.Get();
    APawn* Pawn = PC ? PC->GetPawn() : nullptr;
    if (!Pawn || FVector::Dist(Pawn->GetActorLocation(), Npc->GetActorLocation()) > GetDefault<UReflectionsNpcDialogueSettings>()->TalkRadius * 2.0f)
    {
        OutReason = TEXT("too far away");
        return false;
    }
    if (Name == TEXT("point_the_way"))
    {
        AActor* Goal = FindTarget(TargetName, Npc->GetActorLocation());
        if (!Goal) { OutReason = TEXT("nothing to point at"); return false; }
        PointedAt.Add(Npc, FPlatformTime::Seconds());
        LookTargetNpc = Npc;
        LookTarget = Goal->GetActorLocation();
        LookUntil = FPlatformTime::Seconds() + 4.0;
        if (Overlay)
        {
            const int32 Meters = FMath::RoundToInt(FVector::Dist(Pawn->GetActorLocation(), LookTarget) / 100.0f);
            Overlay->ShowHint(FText::FromString(FString::Printf(TEXT("%s: %d m, %s"), TargetLabel(TargetName), Meters,
                *Bearing(PC, Pawn->GetActorLocation(), LookTarget))), 9.0);
        }
        return true;
    }
    if (Name == TEXT("share_lore"))
    {
        return true;  // the words are the effect
    }
    if (Name == TEXT("warn_guards"))
    {
        UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Npc);
        if (!Npcs) { OutReason = TEXT("no one to hear"); return false; }
        FReflectionsNpcStimulus Alarm;
        Alarm.Kind = EReflectionsNpcStimulusKind::Alarm;
        Alarm.Location = Npc->GetActorLocation();
        Alarm.Intensity = 20.0f;
        Alarm.Radius = GuardSearchRadius;
        Alarm.Instigator = Npc;
        Npcs->ReportStimulus(Alarm);
        GuardsWarnedAt = FPlatformTime::Seconds();
        return true;
    }
    if (Name == TEXT("end_conversation"))
    {
        Partner.Reset();
        ReleaseFacing();
        return true;
    }
    OutReason = TEXT("unknown action");
    return false;
}

void UReflectionsVoiceInteractionSubsystem::PressTalkKey(bool bDown)
{
    EnsureSetup();
    if (bDown) OnTalkPressed();
    else OnTalkReleased();
}

FString UReflectionsVoiceInteractionSubsystem::GetTalkPromptText() const
{
    const UReflectionsQuestWorldSubsystem* Quests = UReflectionsQuestWorldSubsystem::Get(this);
    if (Quests && Quests->GetPromptTarget())
    {
        const FText QuestPrompt = Quests->GetPromptText();
        if (!QuestPrompt.IsEmpty()) return QuestPrompt.ToString();
    }
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
