#include "Voice/ReflectionsRealtimeVoiceComponent.h"
#include "AudioCaptureCore.h"
#include "Components/AudioComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "HAL/PlatformMisc.h"
#include "IWebSocket.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/Base64.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Guid.h"
#include "Misc/Parse.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"
#include "NPC/ReflectionsReputationSubsystem.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonReader.h"
#include "UObject/EnumProperty.h"
#include "UObject/UnrealType.h"
#include "Serialization/JsonSerializer.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundCue.h"
#include "Sound/SoundNodeWavePlayer.h"
#include "Sound/SoundWave.h"
#include "Sound/SoundWaveProcedural.h"
#include "Subsystems/WorldSubsystem.h"
#include "UObject/StructOnScope.h"
#include "Voice/ReflectionsNpcDialogueSettings.h"
#include "Voice/ReflectionsNpcRelayHost.h"
#include "WebSocketsModule.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"
#include "Worlds/ReflectionsWorldTypes.h"

DEFINE_LOG_CATEGORY(LogReflectionsNpcDialogue);

double UReflectionsRealtimeVoiceComponent::RelayDownUntil = 0.0;
bool UReflectionsRealtimeVoiceComponent::bForceFallback = false;

namespace
{
    constexpr int32 BytesPerMs = 48;           // 24 kHz mono PCM16
    constexpr int32 MaxQueuedChunks = 1200;    // about 25 s of 1024-frame microphone buffers
    constexpr double ReplyTimeoutSeconds = 15.0;
    constexpr int32 MinTurnBytes = 9600;       // 0.2 s: anything shorter is a tap on the key, not speech

    FString JsonString(const TSharedRef<FJsonObject>& Object)
    {
        FString Text;
        const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
            TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text);
        FJsonSerializer::Serialize(Object, Writer);
        return Text;
    }

    template <typename TEnum>
    FString EnumName(TEnum Value)
    {
        return StaticEnum<TEnum>()->GetNameStringByValue(static_cast<int64>(Value));
    }

    /** Reads a name-, string-, enum- or int-valued property as text. False if there is no such property. */
    bool ReadPropertyText(const UStruct* Type, const void* Container, FName Name, FString& Out)
    {
        const FProperty* Property = Type && Container ? Type->FindPropertyByName(Name) : nullptr;
        if (!Property) return false;
        const void* Value = Property->ContainerPtrToValuePtr<void>(Container);
        if (const FNameProperty* AsName = CastField<FNameProperty>(Property)) { Out = AsName->GetPropertyValue(Value).ToString(); return true; }
        if (const FStrProperty* AsString = CastField<FStrProperty>(Property)) { Out = AsString->GetPropertyValue(Value); return true; }
        if (const FEnumProperty* AsEnum = CastField<FEnumProperty>(Property))
        {
            Out = AsEnum->GetEnum()->GetNameStringByValue(AsEnum->GetUnderlyingProperty()->GetSignedIntPropertyValue(Value));
            return true;
        }
        if (const FByteProperty* AsByte = CastField<FByteProperty>(Property))
        {
            const uint8 Byte = AsByte->GetPropertyValue(Value);
            Out = AsByte->Enum ? AsByte->Enum->GetNameStringByValue(Byte) : FString::FromInt(Byte);
            return true;
        }
        if (const FIntProperty* AsInt = CastField<FIntProperty>(Property)) { Out = FString::FromInt(AsInt->GetPropertyValue(Value)); return true; }
        if (const FTextProperty* AsText = CastField<FTextProperty>(Property)) { Out = AsText->GetPropertyValue(Value).ToString(); return true; }
        return false;
    }

    /** The lives system (people, schedules, memory), found by name so there is no header dependency. */
    UObject* FindLivesSubsystem(const UObject* Context)
    {
        UClass* LivesClass = FindObject<UClass>(nullptr, TEXT("/Script/reflections.ReflectionsLivesSubsystem"));
        UWorld* World = Context ? Context->GetWorld() : nullptr;
        if (!LivesClass || !World || !LivesClass->IsChildOf(UWorldSubsystem::StaticClass())) return nullptr;
        return World->GetSubsystemBase(LivesClass);
    }

    /** The quest system (a game-instance subsystem), found by name. */
    UObject* FindQuestSubsystem(const UObject* Context)
    {
        UClass* QuestClass = FindObject<UClass>(nullptr, TEXT("/Script/reflections.ReflectionsQuestSubsystem"));
        UWorld* World = Context ? Context->GetWorld() : nullptr;
        UGameInstance* Instance = World ? World->GetGameInstance() : nullptr;
        if (!QuestClass || !Instance || !QuestClass->IsChildOf(UGameInstanceSubsystem::StaticClass())) return nullptr;
        return Instance->GetSubsystemBase(QuestClass);
    }

    /** Calls Target->Function(AActor*) with no other inputs; returns the parameter block (null if the shape differs). */
    TUniquePtr<FStructOnScope> CallWithActor(UObject* Target, FName FunctionName, AActor* Actor)
    {
        UFunction* Function = Target ? Target->FindFunction(FunctionName) : nullptr;
        if (!Function || !Actor) return nullptr;
        TUniquePtr<FStructOnScope> Params = MakeUnique<FStructOnScope>(Function);
        bool bActorSet = false;
        for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
        {
            if (It->HasAnyPropertyFlags(CPF_ReturnParm | CPF_OutParm) && !It->HasAnyPropertyFlags(CPF_ReferenceParm | CPF_ConstParm)) continue;
            const FObjectPropertyBase* Arg = CastField<FObjectPropertyBase>(*It);
            if (!Arg || bActorSet) return nullptr;
            Arg->SetObjectPropertyValue_InContainer(Params->GetStructMemory(), Actor);
            bActorSet = true;
        }
        if (!bActorSet) return nullptr;
        Target->ProcessEvent(Function, Params->GetStructMemory());
        return Params;
    }

    /** Calls Lives->Function(const AActor*) and returns its result as text (or one field of a returned struct). */
    FString CallLivesText(UObject* Lives, FName FunctionName, const AActor* Actor, FName StructField = NAME_None)
    {
        UFunction* Function = Lives ? Lives->FindFunction(FunctionName) : nullptr;
        if (!Function || !Actor) return FString();
        FStructOnScope Params(Function);
        uint8* Data = Params.GetStructMemory();
        bool bActorSet = false;
        for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
        {
            if (It->HasAnyPropertyFlags(CPF_ReturnParm)) continue;
            const FObjectPropertyBase* Arg = CastField<FObjectPropertyBase>(*It);
            if (!Arg || bActorSet) return FString();  // not the (const AActor*) signature we expect
            Arg->SetObjectPropertyValue_InContainer(Data, const_cast<AActor*>(Actor));
            bActorSet = true;
        }
        if (!bActorSet) return FString();
        Lives->ProcessEvent(Function, Data);
        const FProperty* Result = Function->GetReturnProperty();
        FString Out;
        if (const FStructProperty* AsStruct = CastField<FStructProperty>(Result))
        {
            if (!StructField.IsNone()) ReadPropertyText(AsStruct->Struct, AsStruct->ContainerPtrToValuePtr<void>(Data), StructField, Out);
        }
        else if (Result)
        {
            ReadPropertyText(Function, Data, Result->GetFName(), Out);
        }
        return Out == TEXT("None") ? FString() : Out;
    }

    /** The NPC system's voice profile, read by reflection: struct VoiceProfile {Slot, Sex}, or VoiceSlot / VoiceSex. */
    void ReadVoiceProfile(const UObject* Source, FString& Slot, FString& Sex)
    {
        if (!Source) return;
        const UClass* Class = Source->GetClass();
        for (const TCHAR* Name : {TEXT("VoiceProfile"), TEXT("Voice")})
        {
            if (const FStructProperty* Profile = CastField<FStructProperty>(Class->FindPropertyByName(Name)))
            {
                const void* Inner = Profile->ContainerPtrToValuePtr<void>(Source);
                if (Slot.IsEmpty() && !ReadPropertyText(Profile->Struct, Inner, TEXT("Slot"), Slot)) ReadPropertyText(Profile->Struct, Inner, TEXT("VoiceSlot"), Slot);
                if (Sex.IsEmpty()) ReadPropertyText(Profile->Struct, Inner, TEXT("Sex"), Sex);
                break;
            }
        }
        if (Slot.IsEmpty()) ReadPropertyText(Class, Source, TEXT("VoiceSlot"), Slot);
        if (Sex.IsEmpty() && !ReadPropertyText(Class, Source, TEXT("VoiceSex"), Sex)) ReadPropertyText(Class, Source, TEXT("Sex"), Sex);
    }

    FString LocalSpeakerName(FName Group)
    {
        if (Group == TEXT("Guard")) return TEXT("Watch Guard");
        if (Group == TEXT("Soldier")) return TEXT("Soldier");
        if (Group == TEXT("Tarnished")) return TEXT("Tarnished");
        if (Group == TEXT("Tarnish")) return TEXT("The Tarnish");
        return TEXT("Townsperson");
    }
}

UReflectionsRealtimeVoiceComponent::UReflectionsRealtimeVoiceComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bTickEvenWhenPaused = false;
}
UReflectionsRealtimeVoiceComponent::~UReflectionsRealtimeVoiceComponent() = default;

void UReflectionsRealtimeVoiceComponent::SetForceFallback(bool bForce)
{
    bForceFallback = bForce;
}

bool UReflectionsRealtimeVoiceComponent::IsRelayAvailable() const
{
    // A helper this game started is still starting up: barks until it listens, without marking it down.
    if (UReflectionsNpcRelayHost::IsLaunchedRelayRunning() && !UReflectionsNpcRelayHost::IsLaunchedRelayReady()) return false;
    return !bForceFallback && !UReflectionsNpcDialogueSettings::ResolveRelayUrl().IsEmpty() &&
        FPlatformTime::Seconds() >= RelayDownUntil;
}

void UReflectionsRealtimeVoiceComponent::SetStatus(const FString& Next)
{
    if (Status == Next) return;
    Status = Next;
    OnVoiceStatus.Broadcast(Status);
}

void UReflectionsRealtimeVoiceComponent::SendJson(const TSharedRef<FJsonObject>& Object)
{
    if (!Socket.IsValid() || !Socket->IsConnected()) return;
    Socket->Send(JsonString(Object));
}

// ---- Persona -------------------------------------------------------------------------------------------

FName UReflectionsRealtimeVoiceComponent::PersonaGroup(AActor* Npc)
{
    const UReflectionsNpcSubsystem* Npcs = IsValid(Npc) ? UReflectionsNpcSubsystem::Get(Npc) : nullptr;
    const UReflectionsNpcReactionComponent* Reaction = Npcs ? Npcs->FindNpc(Npc) : nullptr;
    if (!Reaction && IsValid(Npc)) Reaction = Npc->FindComponentByClass<UReflectionsNpcReactionComponent>();
    if (!Reaction) return TEXT("Civilian");
    if (Reaction->Infection == EReflectionsNpcInfection::VillainHost) return TEXT("Tarnish");
    if (Reaction->Infection == EReflectionsNpcInfection::Infected) return TEXT("Tarnished");
    switch (Reaction->Disposition)
    {
    case EReflectionsNpcDisposition::Guard: return TEXT("Guard");
    case EReflectionsNpcDisposition::Enemy: return TEXT("Soldier");
    case EReflectionsNpcDisposition::Infected: return TEXT("Tarnished");
    case EReflectionsNpcDisposition::VillainHost: return TEXT("Tarnish");
    default: return TEXT("Civilian");
    }
}

TArray<FString> UReflectionsRealtimeVoiceComponent::GetQuestActions(AActor* Npc)
{
    TArray<FString> Actions;
    UObject* Quests = FindQuestSubsystem(Npc);
    TUniquePtr<FStructOnScope> Params = CallWithActor(Quests, TEXT("GetQuestActions"), Npc);
    const UFunction* Function = Params ? Cast<UFunction>(Params->GetStruct()) : nullptr;
    const FArrayProperty* Result = Function ? CastField<FArrayProperty>(Function->GetReturnProperty()) : nullptr;
    const FStrProperty* Inner = Result ? CastField<FStrProperty>(Result->Inner) : nullptr;
    if (!Inner) return Actions;
    FScriptArrayHelper Array(Result, Result->ContainerPtrToValuePtr<void>(Params->GetStructMemory()));
    for (int32 Index = 0; Index < Array.Num() && Actions.Num() < 16; ++Index)
    {
        Actions.Add(Inner->GetPropertyValue(Array.GetRawPtr(Index)).Left(80));
    }
    return Actions;
}

FString UReflectionsRealtimeVoiceComponent::GetQuestContext(AActor* Npc)
{
    TUniquePtr<FStructOnScope> Params = CallWithActor(FindQuestSubsystem(Npc), TEXT("GetQuestContext"), Npc);
    const UFunction* Function = Params ? Cast<UFunction>(Params->GetStruct()) : nullptr;
    const FStrProperty* Result = Function ? CastField<FStrProperty>(Function->GetReturnProperty()) : nullptr;
    return Result ? Result->GetPropertyValue_InContainer(Params->GetStructMemory()).Left(4000) : FString();
}

bool UReflectionsRealtimeVoiceComponent::HandleQuestTalkPressed(AActor* Npc)
{
    TUniquePtr<FStructOnScope> Params = CallWithActor(FindQuestSubsystem(Npc), TEXT("HandleTalkPressed"), Npc);
    const UFunction* Function = Params ? Cast<UFunction>(Params->GetStruct()) : nullptr;
    const FBoolProperty* Result = Function ? CastField<FBoolProperty>(Function->GetReturnProperty()) : nullptr;
    return Result && Result->GetPropertyValue_InContainer(Params->GetStructMemory());
}

void UReflectionsRealtimeVoiceComponent::NotifyQuestTalkedTo(AActor* Npc)
{
    CallWithActor(FindQuestSubsystem(Npc), TEXT("NotifyTalkedTo"), Npc);
}

bool UReflectionsRealtimeVoiceComponent::ExecuteQuestAction(AActor* Npc, const FString& Action, FString& OutReason, FString& OutSay)
{
    UObject* Quests = FindQuestSubsystem(Npc);
    UFunction* Function = Quests ? Quests->FindFunction(TEXT("ExecuteQuestAction")) : nullptr;
    if (!Function || !IsValid(Npc)) { OutReason = TEXT("no quest system"); return false; }
    FStructOnScope Params(Function);
    uint8* Data = Params.GetStructMemory();
    const FStrProperty* ReasonOut = nullptr;
    const FStrProperty* SayOut = nullptr;
    bool bActor = false, bAction = false;
    for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
    {
        if (It->HasAnyPropertyFlags(CPF_ReturnParm)) continue;
        if (const FObjectPropertyBase* AsObject = CastField<FObjectPropertyBase>(*It)) { AsObject->SetObjectPropertyValue_InContainer(Data, Npc); bActor = true; }
        else if (const FStrProperty* AsString = CastField<FStrProperty>(*It))
        {
            const bool bOut = It->HasAnyPropertyFlags(CPF_OutParm) && !It->HasAnyPropertyFlags(CPF_ConstParm);
            if (!bOut && !bAction) { AsString->SetPropertyValue_InContainer(Data, Action); bAction = true; }
            else if (bOut && It->GetName().Contains(TEXT("Say"))) SayOut = AsString;
            else if (bOut) ReasonOut = AsString;
        }
    }
    if (!bActor || !bAction) { OutReason = TEXT("unexpected quest call"); return false; }
    Quests->ProcessEvent(Function, Data);
    if (ReasonOut) OutReason = ReasonOut->GetPropertyValue_InContainer(Data).Left(120);
    if (SayOut) OutSay = SayOut->GetPropertyValue_InContainer(Data).Left(300);
    const FBoolProperty* Result = CastField<FBoolProperty>(Function->GetReturnProperty());
    return Result && Result->GetPropertyValue_InContainer(Data);
}

FString UReflectionsRealtimeVoiceComponent::GetPersonName(AActor* Npc)
{
    return CallLivesText(FindLivesSubsystem(Npc), TEXT("GetPersonaFacts"), Npc, TEXT("Name")).Left(40);
}

void UReflectionsRealtimeVoiceComponent::RememberTalk(AActor* Npc)
{
    UObject* Lives = FindLivesSubsystem(Npc);
    UFunction* Function = Lives ? Lives->FindFunction(TEXT("RememberPlayer")) : nullptr;
    if (!Function || !IsValid(Npc)) return;
    FStructOnScope Params(Function);
    uint8* Data = Params.GetStructMemory();
    bool bActor = false, bDeed = false;
    for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
    {
        if (It->HasAnyPropertyFlags(CPF_ReturnParm)) continue;
        if (const FObjectPropertyBase* AsObject = CastField<FObjectPropertyBase>(*It)) { AsObject->SetObjectPropertyValue_InContainer(Data, Npc); bActor = true; }
        else if (const FEnumProperty* AsEnum = CastField<FEnumProperty>(*It))
        {
            const int64 Talked = AsEnum->GetEnum()->GetValueByNameString(TEXT("Talked"));
            if (Talked == INDEX_NONE) return;
            AsEnum->GetUnderlyingProperty()->SetIntPropertyValue(AsEnum->ContainerPtrToValuePtr<void>(Data), Talked);
            bDeed = true;
        }
        else if (const FByteProperty* AsByte = CastField<FByteProperty>(*It))
        {
            const int64 Talked = AsByte->Enum ? AsByte->Enum->GetValueByNameString(TEXT("Talked")) : INDEX_NONE;
            if (Talked == INDEX_NONE) return;
            AsByte->SetPropertyValue_InContainer(Data, static_cast<uint8>(Talked));
            bDeed = true;
        }
        else if (const FFloatProperty* AsFloat = CastField<FFloatProperty>(*It)) AsFloat->SetPropertyValue_InContainer(Data, 1.0f);
        else if (const FDoubleProperty* AsDouble = CastField<FDoubleProperty>(*It)) AsDouble->SetPropertyValue_InContainer(Data, 1.0);
        else if (const FIntProperty* AsInt = CastField<FIntProperty>(*It)) AsInt->SetPropertyValue_InContainer(Data, 1);
    }
    if (bActor && bDeed) Lives->ProcessEvent(Function, Data);
}

FString UReflectionsRealtimeVoiceComponent::GetVoiceId(AActor* Npc)
{
    if (!IsValid(Npc)) return FString();
    const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Npc);
    const UReflectionsNpcReactionComponent* Reaction = Npcs ? Npcs->FindNpc(Npc) : nullptr;
    if (!Reaction) Reaction = Npc->FindComponentByClass<UReflectionsNpcReactionComponent>();
    FString VoiceId;
    for (const UObject* Source : {static_cast<const UObject*>(Reaction), static_cast<const UObject*>(Npc)})
    {
        if (!Source || !VoiceId.IsEmpty()) continue;
        if (!ReadPropertyText(Source->GetClass(), Source, TEXT("VoiceId"), VoiceId))
        {
            if (const FStructProperty* Profile = CastField<FStructProperty>(Source->GetClass()->FindPropertyByName(TEXT("VoiceProfile"))))
            {
                ReadPropertyText(Profile->Struct, Profile->ContainerPtrToValuePtr<void>(Source), TEXT("VoiceId"), VoiceId);
            }
        }
    }
    return VoiceId == TEXT("None") ? FString() : VoiceId.Left(40);
}

TSharedRef<FJsonObject> UReflectionsRealtimeVoiceComponent::BuildNpcContext(AActor* Npc, APawn* Player, const TArray<FString>& Actions)
{
    TSharedRef<FJsonObject> Context = MakeShared<FJsonObject>();
    if (!IsValid(Npc)) return Context;
    Context->SetStringField(TEXT("npc_id"), Npc->GetName().Left(64));
    // The lives system's person: a stable id across runs (the reply cache keys a person's own lines by it), their
    // name, and a whitelisted character sheet (job, traits, speech style, what they remember of the player).
    if (UObject* Lives = FindLivesSubsystem(Npc))
    {
        const FString PersonId = CallLivesText(Lives, TEXT("GetPersonId"), Npc);
        if (!PersonId.IsEmpty()) Context->SetStringField(TEXT("npc_id"), (TEXT("person_") + PersonId).Left(64));
        const FString Sheet = CallLivesText(Lives, TEXT("GetPersonaText"), Npc);
        if (!Sheet.IsEmpty()) Context->SetStringField(TEXT("persona_text"), Sheet.Left(1500));
        const FString Name = CallLivesText(Lives, TEXT("GetPersonaFacts"), Npc, TEXT("Name"));
        if (!Name.IsEmpty()) Context->SetStringField(TEXT("name"), Name.Left(40));
    }
    const FString QuestNotes = GetQuestContext(Npc);
    if (!QuestNotes.IsEmpty()) Context->SetStringField(TEXT("quests"), QuestNotes);
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Npc);
    const UReflectionsNpcReactionComponent* Reaction = Npcs ? Npcs->FindNpc(Npc) : nullptr;
    if (!Reaction) Reaction = Npc->FindComponentByClass<UReflectionsNpcReactionComponent>();
    if (Reaction)
    {
        const UReflectionsNpcArchetype* Archetype = Reaction->GetActiveArchetype();
        Context->SetStringField(TEXT("archetype"), Archetype && !Archetype->ArchetypeId.IsNone()
            ? Archetype->ArchetypeId.ToString() : EnumName(Reaction->Disposition));
        Context->SetStringField(TEXT("disposition"), EnumName(Reaction->Disposition));
        Context->SetStringField(TEXT("reaction"), EnumName(Reaction->Reaction));
        Context->SetStringField(TEXT("infection"), EnumName(Reaction->Infection));
        Context->SetNumberField(TEXT("fear"), FMath::RoundToDouble(Reaction->Fear * 100.0) / 100.0);
        Context->SetNumberField(TEXT("hostility"), FMath::RoundToDouble(Reaction->Hostility * 100.0) / 100.0);
    }
    // Side: the anchor box the NPC stands in, else this map's side, else the world-jump config's DefaultWorld
    // (one map with no world jump, as on Gray London). Never the hero's never-set CurrentWorld (Gray by default).
    EReflectionsWorld Side = EReflectionsWorld::Red;
    if (const UReflectionsWorldJumpWorldSubsystem* Worlds = UReflectionsWorldJumpWorldSubsystem::Get(Npc))
    {
        Side = Worlds->GetWorldAtLocation(Npc->GetActorLocation());
    }
    else if (const UReflectionsWorldJumpSubsystem* Jump = UReflectionsWorldJumpSubsystem::Get(Npc))
    {
        Side = Jump->GetCurrentWorld();
    }
    Context->SetStringField(TEXT("side"), EnumName(Side));
    FString Slot, Sex;
    GetVoiceProfile(Npc, Slot, Sex);
    if (!Slot.IsEmpty()) Context->SetStringField(TEXT("voice_slot"), Slot);
    if (!Sex.IsEmpty()) Context->SetStringField(TEXT("sex"), Sex);
    const FString VoiceId = GetVoiceId(Npc);
    if (!VoiceId.IsEmpty()) Context->SetStringField(TEXT("voice_id"), VoiceId);
    // The designed Gemini voice that NPC unify copied from audio's roster row (read fresh: scenes may override it).
    if (Reaction)
    {
        FString GeminiVoice;
        if (ReadPropertyText(Reaction->GetClass(), Reaction, TEXT("GeminiVoice"), GeminiVoice) && !GeminiVoice.IsEmpty())
        {
            Context->SetStringField(TEXT("gemini_voice"), GeminiVoice.Left(48));
        }
    }
    TArray<TSharedPtr<FJsonValue>> ActionValues;
    for (const FString& Action : Actions) ActionValues.Add(MakeShared<FJsonValueString>(Action));
    Context->SetArrayField(TEXT("actions"), ActionValues);
    if (UWorld* World = Npc->GetWorld())
    {
        if (const UReflectionsReputationSubsystem* Reputation = World->GetSubsystem<UReflectionsReputationSubsystem>())
        {
            Context->SetNumberField(TEXT("reputation"), FMath::RoundToDouble(Reputation->GetReputation(Player)));
        }
    }
    return Context;
}

void UReflectionsRealtimeVoiceComponent::GetVoiceProfile(AActor* Npc, FString& OutSlot, FString& OutSex)
{
    OutSlot.Reset();
    OutSex.Reset();
    if (!IsValid(Npc)) return;
    const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Npc);
    const UReflectionsNpcReactionComponent* Reaction = Npcs ? Npcs->FindNpc(Npc) : nullptr;
    if (!Reaction) Reaction = Npc->FindComponentByClass<UReflectionsNpcReactionComponent>();
    ReadVoiceProfile(Reaction, OutSlot, OutSex);
    if (OutSlot.IsEmpty() || OutSex.IsEmpty()) ReadVoiceProfile(Npc, OutSlot, OutSex);
    // Accept "F2", "Female"/"Male" (or enum names ending in them) and a bare slot number with a sex.
    if (OutSex.EndsWith(TEXT("Female")) || OutSex.Equals(TEXT("F"), ESearchCase::IgnoreCase)) OutSex = TEXT("Female");
    else if (OutSex.EndsWith(TEXT("Male")) || OutSex.Equals(TEXT("M"), ESearchCase::IgnoreCase)) OutSex = TEXT("Male");
    else OutSex.Reset();
    OutSlot = OutSlot.Right(2).ToUpper();
    if (OutSlot.Len() == 1 && OutSlot[0] >= TEXT('0') && OutSlot[0] <= TEXT('3') && !OutSex.IsEmpty())
    {
        OutSlot = FString::Printf(TEXT("%c%d"), OutSex == TEXT("Female") ? TEXT('F') : TEXT('M'), FMath::Max(1, OutSlot[0] - TEXT('0')));
    }
    const bool bValid = OutSlot.Len() == 2 && (OutSlot[0] == TEXT('F') || OutSlot[0] == TEXT('M')) && OutSlot[1] >= TEXT('1') && OutSlot[1] <= TEXT('3');
    if (!bValid) OutSlot.Reset();
    else if (OutSex.IsEmpty()) OutSex = OutSlot[0] == TEXT('F') ? TEXT("Female") : TEXT("Male");
}

USceneComponent* UReflectionsRealtimeVoiceComponent::GetVoiceAnchor(AActor* Npc, FName& OutSocket, FVector& OutOffset)
{
    OutSocket = NAME_None;
    OutOffset = FVector(0.0, 0.0, 160.0);
    if (!IsValid(Npc)) return nullptr;
    const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Npc);
    const UReflectionsNpcReactionComponent* Reaction = Npcs ? Npcs->FindNpc(Npc) : nullptr;
    if (!Reaction) Reaction = Npc->FindComponentByClass<UReflectionsNpcReactionComponent>();
    USkeletalMeshComponent* Body = Reaction ? Reaction->GetBodyMesh() : nullptr;
    if (!Body) Body = Npc->FindComponentByClass<USkeletalMeshComponent>();
    static const FName Head(TEXT("head"));
    if (Body && Body->DoesSocketExist(Head))
    {
        OutSocket = Head;
        OutOffset = FVector::ZeroVector;
        return Body;
    }
    return Npc->GetRootComponent();
}

USoundAttenuation* UReflectionsRealtimeVoiceComponent::GetVoiceAttenuation()
{
    const FSoftObjectPath& Path = GetDefault<UReflectionsNpcDialogueSettings>()->VoiceAttenuation;
    if (Path.IsNull() || !FPackageName::DoesPackageExist(Path.GetLongPackageName())) return nullptr;
    return Cast<USoundAttenuation>(Path.TryLoad());
}

FString UReflectionsRealtimeVoiceComponent::GetSpeakerName() const
{
    if (!Speaker.IsEmpty()) return Speaker;
    const FString Person = GetPersonName(VoiceNpc.Get());
    return Person.IsEmpty() ? LocalSpeakerName(PersonaGroup(VoiceNpc.Get())) : Person;
}

// ---- Connection ----------------------------------------------------------------------------------------

FString UReflectionsRealtimeVoiceComponent::ReadLocalToken(const FString& Url) const
{
    if (!UReflectionsNpcDialogueSettings::IsLoopbackUrl(Url)) return FString();
    FString Token = FPlatformMisc::GetEnvironmentVariable(TEXT("REFLECTIONS_VOICE_LOCAL_TOKEN"));
    if (Token.Len() >= 32) return Token;
    FString Path;
    if (!FParse::Value(FCommandLine::Get(), TEXT("NpcRelayTokenFile="), Path))
    {
        Path = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("NpcDialogue"), TEXT("relay.token"));
    }
    Token.Reset();
    FFileHelper::LoadFileToString(Token, *Path);
    Token.TrimStartAndEndInline();
    return Token.Len() >= 32 ? Token : FString();
}

FString UReflectionsRealtimeVoiceComponent::ClientId()
{
    static FString Cached;
    if (!Cached.IsEmpty()) return Cached;
    const FString Path = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("NpcDialogue"), TEXT("client_id.txt"));
    FFileHelper::LoadFileToString(Cached, *Path);
    Cached.TrimStartAndEndInline();
    if (Cached.Len() < 16 || Cached.Len() > 40)
    {
        Cached = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphens);
        FFileHelper::SaveStringToFile(Cached, *Path);
    }
    return Cached;
}

void UReflectionsRealtimeVoiceComponent::ConnectToNpc(AActor* Npc)
{
    if (IsValid(Npc) && Npc == VoiceNpc.Get() && (Socket.IsValid() || (bOffline && !IsRelayAvailable()))) return;
    DisconnectVoice();
    if (!IsValid(Npc)) return;
    VoiceNpc = Npc;
    Speaker.Reset();
    bOffline = true;
    const FString Url = UReflectionsNpcDialogueSettings::ResolveRelayUrl();
    if (!IsRelayAvailable()) return;  // barks only
    const FString Token = ReadLocalToken(Url);
    if (UReflectionsNpcDialogueSettings::IsLoopbackUrl(Url) && Token.IsEmpty())
    {
        // The development relay isn't running (it writes Saved/NpcDialogue/relay.token on start).
        RelayDownUntil = FPlatformTime::Seconds() + 5.0;
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("No local relay token; NPCs use barks. Start Tools/RealtimeVoice/Start-NpcDialogueRelay.ps1."));
        return;
    }
    bOffline = false;
    ConnectStarted = FPlatformTime::Seconds();
    Socket = FWebSocketsModule::Get().CreateWebSocket(Url, TEXT(""));
    Socket->OnConnected().AddWeakLambda(this, [this, Token]() {
        TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
        Msg->SetStringField(TEXT("type"), TEXT("session.start"));
        Msg->SetNumberField(TEXT("protocol"), 2);
        if (!Token.IsEmpty()) Msg->SetStringField(TEXT("token"), Token);
        const FString& Key = GetDefault<UReflectionsNpcDialogueSettings>()->ClientKey;
        if (!Key.IsEmpty()) Msg->SetStringField(TEXT("client_key"), Key);
        Msg->SetStringField(TEXT("client_id"), ClientId());
        const TSharedRef<FJsonObject> Context = BuildNpcContext(VoiceNpc.Get(), UGameplayStatics::GetPlayerPawn(this, 0),
            ActionsProvider ? ActionsProvider(VoiceNpc.Get()) : TArray<FString>());
        LastContextJson = JsonString(Context);
        Msg->SetObjectField(TEXT("npc"), Context);
        SendJson(Msg);
    });
    Socket->OnMessage().AddWeakLambda(this, [this](const FString& Message) { OnMessage(Message); });
    // Socket callbacks only raise flags: the socket must not be released from inside its own callback.
    Socket->OnConnectionError().AddWeakLambda(this, [this, Url](const FString& Error) {
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("Dialogue relay %s: connection error: %s"), *Url, *Error.Left(200));
        bSocketFailed = true;
    });
    Socket->OnClosed().AddWeakLambda(this, [this](int32 Code, const FString&, bool) {
        bSocketClosed = true;
        bClosedForRestart = Code == 4000;
        bClosedBusy = Code == 1013;
    });
    Socket->Connect();
}

void UReflectionsRealtimeVoiceComponent::FailToBarks(bool bMarkRelayDown)
{
    if (bMarkRelayDown)
    {
        // Busy (sessions overlapping while switching NPCs) is momentary: try again shortly, not after the full wait.
        RelayDownUntil = FPlatformTime::Seconds() + (bClosedBusy ? 3.0 : GetDefault<UReflectionsNpcDialogueSettings>()->RelayRetrySeconds);
        bClosedBusy = false;
    }
    const bool bOwedReply = bTurnEndPending || !PendingTypedLine.IsEmpty() ||
        (bAwaitingReply && LastSource == EReflectionsReplySource::None);
    const bool bWasRecording = bRecording.Load();
    CloseSocket();
    bOffline = true;
    bTurnEndPending = false;
    PendingTypedLine.Reset();
    StopCapture();
    TArray<uint8> Discard; while (PendingAudio.Dequeue(Discard)) {} QueuedChunks.Store(0);
    if (bOwedReply)
    {
        bAwaitingReply = false;
        PlayBark();
    }
    else if (bWasRecording)
    {
        // Still held, now with the microphone closed: the bark plays on release (see EndPushToTalk).
        bAwaitingReply = false;
        bRecording.Store(true);
    }
}

void UReflectionsRealtimeVoiceComponent::FlushPending()
{
    if (!bReady) return;
    FlushCaptured();
    if (bTurnEndPending)
    {
        bTurnEndPending = false;
        SendContextIfChanged();
        TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
        Msg->SetStringField(TEXT("type"), SentBytes >= MinTurnBytes ? TEXT("turn.end") : TEXT("turn.clear"));
        SendJson(Msg);
        if (SentBytes < MinTurnBytes) bAwaitingReply = false;
    }
    if (!PendingTypedLine.IsEmpty())
    {
        const FString Line = MoveTemp(PendingTypedLine);
        PendingTypedLine.Reset();
        SendContextIfChanged();
        TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
        Msg->SetStringField(TEXT("type"), TEXT("text.turn"));
        Msg->SetStringField(TEXT("text"), Line);
        SendJson(Msg);
    }
}

void UReflectionsRealtimeVoiceComponent::SendContextIfChanged()
{
    AActor* Npc = VoiceNpc.Get();
    if (!bReady || !IsValid(Npc)) return;
    const TSharedRef<FJsonObject> Context = BuildNpcContext(Npc, UGameplayStatics::GetPlayerPawn(this, 0),
        ActionsProvider ? ActionsProvider(Npc) : TArray<FString>());
    const FString Text = JsonString(Context);
    if (Text == LastContextJson) return;
    LastContextJson = Text;
    TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
    Msg->SetStringField(TEXT("type"), TEXT("context.update"));
    Msg->SetObjectField(TEXT("npc"), Context);
    SendJson(Msg);
}

// ---- Relay events --------------------------------------------------------------------------------------

void UReflectionsRealtimeVoiceComponent::OnMessage(const FString& Message)
{
    TSharedPtr<FJsonObject> Json;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Message), Json) || !Json.IsValid()) return;
    FString Type; if (!Json->TryGetStringField(TEXT("type"), Type)) return;
    if (bStaleTurn)
    {
        if (Type == TEXT("response.done") || Type == TEXT("reply.unavailable")) { bStaleTurn = false; return; }
        if (Type == TEXT("reply.start") || Type == TEXT("response.output_audio.delta") || Type == TEXT("reply.text") ||
            Type == TEXT("reply.text.delta") || Type == TEXT("reply.thinking") || Type == TEXT("npc.action")) return;
    }
    if (Type == TEXT("response.output_audio.delta"))
    {
        FString Encoded; TArray<uint8> Bytes;
        if (Json->TryGetStringField(TEXT("delta"), Encoded) && FBase64::Decode(Encoded, Bytes) && Bytes.Num() > 0 &&
            Bytes.Num() <= 200000 && Bytes.Num() % 2 == 0)
        {
            EnsureOutput();
            OutputWave->QueueAudio(Bytes.GetData(), Bytes.Num());
            QueuedOutputBytes += Bytes.Num();
            if (IsValid(OutputAudio) && !OutputAudio->IsPlaying()) OutputAudio->Play();
            SetStatus(TEXT("Speaking"));
        }
    }
    else if (Type == TEXT("reply.text.delta"))
    {
        FString Delta;
        if (Json->TryGetStringField(TEXT("delta"), Delta)) { NpcText += Delta; BroadcastNpcLine(false); }
    }
    else if (Type == TEXT("reply.text"))
    {
        FString Text;
        if (Json->TryGetStringField(TEXT("text"), Text)) { NpcText = Text; BroadcastNpcLine(true); }
    }
    else if (Type == TEXT("transcript.player"))
    {
        FString Text;
        if (Json->TryGetStringField(TEXT("text"), Text) && !Text.IsEmpty())
        {
            PlayerText = Text.Left(300);
            OnDialogueLine.Broadcast(TEXT("You"), PlayerText, true, true);
        }
    }
    else if (Type == TEXT("reply.start"))
    {
        FString Source, ReplyId;
        Json->TryGetStringField(TEXT("source"), Source);
        Json->TryGetStringField(TEXT("reply_id"), ReplyId);
        BeginReply(Source == TEXT("cached") ? EReflectionsReplySource::Cached : EReflectionsReplySource::Generated, ReplyId);
    }
    else if (Type == TEXT("response.done"))
    {
        bResponseDone = true;
        FString State; Json->TryGetStringField(TEXT("status"), State);
        // No text: what players say must not reach the game log or crash reports.
        UE_LOG(LogReflectionsNpcDialogue, Verbose, TEXT("%s reply %s from %s (%s)"),
            LastSource == EReflectionsReplySource::Cached ? TEXT("CACHED") : TEXT("GENERATED"),
            LastReplyId.IsEmpty() ? TEXT("-") : *LastReplyId, *GetSpeakerName(), *State);
    }
    else if (Type == TEXT("session.ready"))
    {
        bReady = true;
        bool bRelayOffline = false;
        Json->TryGetStringField(TEXT("speaker"), Speaker);
        Json->TryGetBoolField(TEXT("offline"), bRelayOffline);
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("Dialogue session ready: %s%s in %.2f s"), *Speaker,
            bRelayOffline ? TEXT(" (relay answering from saved replies only)") : TEXT(""), FPlatformTime::Seconds() - ConnectStarted);
        SetStatus(TEXT("Ready"));
        FlushPending();
    }
    else if (Type == TEXT("reply.unavailable") || Type == TEXT("relay.error"))
    {
        FString Reason; Json->TryGetStringField(TEXT("reason"), Reason);
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("Relay had no reply (%s); playing a bark."), Reason.IsEmpty() ? *Type : *Reason);
        if (bAwaitingReply || Type == TEXT("reply.unavailable"))
        {
            bAwaitingReply = false;
            PlayBark();
        }
    }
    else if (Type == TEXT("reply.thinking"))
    {
        SetStatus(TEXT("Thinking"));
    }
    else if (Type == TEXT("npc.action"))
    {
        FString Name, Target, Reason;
        Json->TryGetStringField(TEXT("name"), Name);
        Json->TryGetStringField(TEXT("target"), Target);
        // The relay only sends actions it offered; the game checks again before doing anything.
        const bool bOk = ActionHandler && ActionHandler(VoiceNpc.Get(), Name.Left(40), Target.Left(80), Reason);
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("NPC action %s %s: %s%s"), *Name, *Target, bOk ? TEXT("done") : TEXT("refused"),
            Reason.IsEmpty() ? TEXT("") : *(TEXT(" (") + Reason + TEXT(")")));
        TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
        Msg->SetStringField(TEXT("type"), TEXT("action.result"));
        Msg->SetStringField(TEXT("name"), Name.Left(40));
        Msg->SetStringField(TEXT("target"), Target.Left(40));
        Msg->SetBoolField(TEXT("ok"), bOk);
        // An action may report a line it showed (the quest system's hint or pitch): "reason|say" from the handler.
        FString ReasonOnly = Reason, Say;
        Reason.Split(TEXT("|say:"), &ReasonOnly, &Say);
        Msg->SetStringField(TEXT("reason"), ReasonOnly.Left(80));
        if (!Say.IsEmpty()) Msg->SetStringField(TEXT("say"), Say.Left(200));
        SendJson(Msg);
    }
    else if (Type == TEXT("session.restart"))
    {
        // The NPC became a different kind of speaker (taken by the Tarnish): reconnect from Tick.
        bRestartPending = true;
    }
}

void UReflectionsRealtimeVoiceComponent::BeginReply(EReflectionsReplySource Source, const FString& ReplyId)
{
    StopPlayback();
    LastSource = Source;
    LastReplyId = ReplyId;
    ReplyCounts.FindOrAdd(Source)++;
    NpcText.Reset();
    bResponseDone = false;
    bAwaitingReply = true;
}

void UReflectionsRealtimeVoiceComponent::BroadcastNpcLine(bool bFinal)
{
    OnDialogueLine.Broadcast(GetSpeakerName(), NpcText, false, bFinal);
}

int32 UReflectionsRealtimeVoiceComponent::GetRepliesBySource(EReflectionsReplySource Source) const
{
    const int32* Count = ReplyCounts.Find(Source);
    return Count ? *Count : 0;
}

// ---- Playback ------------------------------------------------------------------------------------------

namespace
{
    USoundWaveProcedural* MakeReplyWave(UObject* Outer)
    {
        USoundWaveProcedural* Wave = NewObject<USoundWaveProcedural>(Outer);
        Wave->SetSampleRate(24000);
        Wave->NumChannels = 1;
        Wave->Duration = INDEFINITELY_LOOPING_DURATION;
        Wave->bLooping = false;
        // Out of earshot the reply must keep playing silently: a virtualized source never pulls its audio, the stream
        // never drains, and the voice stays busy (no talking to anyone else) until the player walks back.
        Wave->VirtualizationMode = EVirtualizationMode::PlayWhenSilent;
        return Wave;
    }
}

void UReflectionsRealtimeVoiceComponent::EnsureOutput()
{
    AActor* Npc = VoiceNpc.Get();
    if (OutputWave && IsValid(OutputAudio)) return;
    OutputWave = MakeReplyWave(this);
    // The reply comes from the NPC's head and fades with distance like any other NPC voice.
    AActor* Host = IsValid(Npc) ? Npc : GetOwner();
    FName VoiceSocket;
    FVector Offset;
    USceneComponent* Anchor = GetVoiceAnchor(Host, VoiceSocket, Offset);
    OutputAudio = NewObject<UAudioComponent>(Host);
    OutputAudio->bAutoActivate = false;
    OutputAudio->bAllowSpatialization = true;
    OutputAudio->bSuppressSubtitles = true;
    if (USoundAttenuation* Attenuation = GetVoiceAttenuation())
    {
        OutputAudio->AttenuationSettings = Attenuation;
    }
    else
    {
        OutputAudio->bOverrideAttenuation = true;
        FSoundAttenuationSettings& Falloff = OutputAudio->AttenuationOverrides;
        Falloff.bAttenuate = true;
        Falloff.bSpatialize = true;
        Falloff.AttenuationShape = EAttenuationShape::Sphere;
        Falloff.AttenuationShapeExtents = FVector(300.0f, 0.0f, 0.0f);  // full volume within 3 m
        Falloff.FalloffDistance = 2500.0f;                               // silent by about 28 m
    }
    OutputAudio->SetSound(OutputWave);
    if (Anchor) OutputAudio->SetupAttachment(Anchor, VoiceSocket);
    OutputAudio->SetRelativeLocation(Offset);
    OutputAudio->RegisterComponent();
    QueuedOutputBytes = 0;
}

void UReflectionsRealtimeVoiceComponent::StopPlayback()
{
    if (IsValid(OutputAudio)) OutputAudio->Stop();
    // A fresh wave for the next reply. ResetAudio() zeroes the byte count later, on the audio thread: a cached reply
    // queued in the same frame drove it negative, so the stream never drained and the NPC stayed "Thinking".
    if (OutputWave)
    {
        OutputWave = MakeReplyWave(this);
        if (IsValid(OutputAudio)) OutputAudio->SetSound(OutputWave);
    }
    QueuedOutputBytes = 0;
    if (IsValid(BarkAudio)) BarkAudio->Stop();
    BarkAudio = nullptr;
}

bool UReflectionsRealtimeVoiceComponent::IsSpeaking() const
{
    const bool bStream = IsValid(OutputAudio) && OutputAudio->IsPlaying() && OutputWave && OutputWave->GetAvailableAudioByteCount() > 0;
    return bStream || (IsValid(BarkAudio) && BarkAudio->IsPlaying());
}

double UReflectionsRealtimeVoiceComponent::SecondsSinceSpeech() const
{
    return IsSpeaking() ? 0.0 : FPlatformTime::Seconds() - SpeechEndedAt;
}

void UReflectionsRealtimeVoiceComponent::Interrupt()
{
    if (!IsSpeaking() && !bAwaitingReply) return;
    const int64 Remaining = OutputWave ? OutputWave->GetAvailableAudioByteCount() : 0;
    const int32 PlayedMs = static_cast<int32>(FMath::Max<int64>(0, QueuedOutputBytes - Remaining) / BytesPerMs);
    StopPlayback();
    if (bReady)
    {
        TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
        Msg->SetStringField(TEXT("type"), TEXT("response.cancel"));
        Msg->SetNumberField(TEXT("played_ms"), PlayedMs);
        SendJson(Msg);
    }
    bAwaitingReply = false;
    bResponseDone = false;
    SpeechEndedAt = FPlatformTime::Seconds();
}

void UReflectionsRealtimeVoiceComponent::PlayBark()
{
    AActor* Npc = VoiceNpc.Get();
    if (!IsValid(Npc)) return;
    StopPlayback();
    const FName Group = PersonaGroup(Npc);
    EReflectionsNpcReaction Mood = EReflectionsNpcReaction::Calm;
    if (const UReflectionsNpcReactionComponent* Reaction = Npc->FindComponentByClass<UReflectionsNpcReactionComponent>()) Mood = Reaction->Reaction;
    const bool bScared = Mood == EReflectionsNpcReaction::Fleeing || Mood == EReflectionsNpcReaction::Alert;
    TArray<FName> Keys;
    if (Group == TEXT("Guard"))
    {
        if (Mood == EReflectionsNpcReaction::Attacking) Keys.Add(TEXT("Guard_Attack"));
        if (bScared || Mood == EReflectionsNpcReaction::Investigating) Keys.Add(TEXT("Guard_Alert"));
        Keys.Append({TEXT("Guard_Talk"), TEXT("Guard_Alert")});
    }
    else if (Group == TEXT("Soldier")) Keys.Append({TEXT("Soldier_Talk"), TEXT("Soldier_Command")});
    else if (Group == TEXT("Tarnished")) Keys.Add(TEXT("Tarnished_Mutter"));
    else if (Group == TEXT("Tarnish")) Keys.Add(TEXT("Tarnish_Taunt"));
    else
    {
        if (bScared) Keys.Add(TEXT("Civilian_Fear"));
        Keys.Append({TEXT("Civilian_Talk"), TEXT("Civilian_Fear")});
    }
    USoundBase* Sound = nullptr;
    const UReflectionsNpcDialogueSettings* Settings = GetDefault<UReflectionsNpcDialogueSettings>();
    FString Slot, Sex;
    GetVoiceProfile(Npc, Slot, Sex);
    const auto TryLoad = [](const FSoftObjectPath& Path) -> USoundBase* {
        return !Path.IsNull() && FPackageName::DoesPackageExist(Path.GetLongPackageName()) ? Cast<USoundBase>(Path.TryLoad()) : nullptr;
    };
    for (const FName& Key : Keys)
    {
        if (const FSoftObjectPath* Path = Settings->FallbackCues.Find(Key))
        {
            // Talk lines exist per voice (SCue_VO_Guard_Talk_<VoiceId>) and per slot (SCue_VO_Guard_Talk_M2): the NPC's
            // own lines first, so a withheld or failed reply never becomes a line another character also says.
            if (Key.ToString().EndsWith(TEXT("_Talk")))
            {
                // Per-voice lines sit in a folder per character (Cues/Guard_Talk/SCue_VO_Guard_Talk_V103).
                const FString Folder = FPaths::GetPath(Path->GetLongPackageName());
                for (const FString& Suffix : {GetVoiceId(Npc), Slot})
                {
                    if (Sound || Suffix.IsEmpty()) continue;
                    const FString Asset = Path->GetAssetName() + TEXT("_") + Suffix;
                    for (const FString& Dir : {Folder / Key.ToString(), Folder})
                    {
                        if (!Sound) Sound = TryLoad(FSoftObjectPath(Dir / Asset + TEXT(".") + Asset));
                    }
                }
            }
            if (!Sound) Sound = TryLoad(*Path);
        }
        if (Sound) break;
    }
    FString Line;
    USoundAttenuation* Attenuation = nullptr;
    float Volume = 1.0f;
    if (USoundCue* Cue = Cast<USoundCue>(Sound))
    {
        // Pick the line ourselves so the subtitle matches what is heard.
        TArray<USoundNodeWavePlayer*> Players;
        Cue->RecursiveFindNode<USoundNodeWavePlayer>(Cue->FirstNode, Players);
        TArray<USoundWave*> Waves;
        for (USoundNodeWavePlayer* Player : Players) if (Player && Player->GetSoundWave()) Waves.Add(Player->GetSoundWave());
        static TWeakObjectPtr<USoundWave> LastWave;
        if (Waves.Num() == 1)
        {
            // One line (a per-slot cue): play the cue itself so its concurrency and mix settings apply.
            if (Waves[0]->Subtitles.Num()) Line = Waves[0]->Subtitles[0].Text.ToString();
        }
        else if (Waves.Num() > 1)
        {
            // Not the same line twice in a row, when the cue has another one.
            TArray<USoundWave*> Others = Waves;
            Others.Remove(LastWave.Get());
            if (Others.Num() > 0) Waves = MoveTemp(Others);
            USoundWave* Wave = Waves[FMath::RandRange(0, Waves.Num() - 1)];
            LastWave = Wave;
            Attenuation = Cue->AttenuationSettings ? Cue->AttenuationSettings.Get() : GetVoiceAttenuation();
            Volume = Cue->VolumeMultiplier;
            if (Wave->Subtitles.Num()) Line = Wave->Subtitles[0].Text.ToString();
            Sound = Wave;
        }
    }
    LastSource = EReflectionsReplySource::Bark;
    LastReplyId = Sound ? Sound->GetName() : FString();
    ReplyCounts.FindOrAdd(EReflectionsReplySource::Bark)++;
    NpcText = Line;
    if (Sound)
    {
        FName VoiceSocket;
        FVector Offset;
        USceneComponent* Anchor = GetVoiceAnchor(Npc, VoiceSocket, Offset);
        if (!Attenuation && !Cast<USoundCue>(Sound)) Attenuation = GetVoiceAttenuation();
        // Our own component (not SpawnSoundAttached) so the engine's subtitle text is suppressed: the overlay shows it.
        BarkAudio = NewObject<UAudioComponent>(Npc);
        BarkAudio->bAutoActivate = false;
        BarkAudio->bAutoDestroy = true;
        BarkAudio->bStopWhenOwnerDestroyed = true;
        BarkAudio->bSuppressSubtitles = true;
        BarkAudio->bAllowSpatialization = true;
        BarkAudio->SetSound(Sound);
        BarkAudio->SetVolumeMultiplier(Volume);
        if (Attenuation) BarkAudio->AttenuationSettings = Attenuation;
        if (Anchor) BarkAudio->SetupAttachment(Anchor, VoiceSocket);
        BarkAudio->SetRelativeLocation(Offset);
        BarkAudio->RegisterComponent();
        BarkAudio->Play();
    }
    if (!Line.IsEmpty()) BroadcastNpcLine(true);
    UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("BARK %s from %s: \"%s\""), Sound ? *Sound->GetName() : TEXT("(none found)"),
        *GetSpeakerName(), *Line);
    SpeechEndedAt = FPlatformTime::Seconds();
}

// ---- Microphone and typed lines ------------------------------------------------------------------------

void UReflectionsRealtimeVoiceComponent::BeginPushToTalk()
{
    if (!VoiceNpc.IsValid() || bRecording.Load()) return;
    Interrupt();
    bStaleTurn = false;  // a new turn: what comes next is its reply
    ResamplePosition = 0;
    SentBytes = 0;
    HeldBytes = 0;
    MaxRecordBytes = 24000 * 2 * FMath::Clamp(GetDefault<UReflectionsNpcDialogueSettings>()->MaxRecordSeconds, 1.0f, 60.0f);
    LastSource = EReflectionsReplySource::None;
    if (bOffline)
    {
        // No relay: there is nothing to send speech to, so the microphone stays closed.
        bRecording.Store(true);
        SetStatus(TEXT("Listening"));
        return;
    }
    Capture = MakeUnique<Audio::FAudioCapture>();
    Audio::FAudioCaptureDeviceParams Params;
    Params.bUseHardwareAEC = true;
    bRecording.Store(true);
    const bool bOpened = Capture->OpenAudioCaptureStream(Params,
        [this](const void* Buffer, int32 Frames, int32 Channels, int32 Rate, double, bool) {
            if (!bRecording.Load() || !Buffer || Channels <= 0 || Rate <= 0 || Frames <= 0 || QueuedChunks.Load() >= MaxQueuedChunks) return;
            const float* Input = static_cast<const float*>(Buffer);
            TArray<uint8> Data;
            Data.Reserve(Frames);
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
    if (!bOpened || !Capture->StartStream())
    {
        // No microphone: keep the hold, and answer with a bark on release (typing still reaches the relay).
        if (Capture) { Capture.Reset(); }
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("Microphone unavailable; press Enter to type a line instead."));
    }
    SetStatus(TEXT("Listening"));
}

void UReflectionsRealtimeVoiceComponent::FlushCaptured()
{
    if (!bReady) return;  // held in PendingAudio until the session is ready
    TArray<uint8> Data;
    while (PendingAudio.Dequeue(Data))
    {
        --QueuedChunks;
        if (SentBytes + Data.Num() > MaxRecordBytes) continue;
        SentBytes += Data.Num();
        for (int32 Offset = 0; Offset < Data.Num(); Offset += 24000)
        {
            TArray<uint8> Slice(Data.GetData() + Offset, FMath::Min(24000, Data.Num() - Offset));
            TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
            Msg->SetStringField(TEXT("type"), TEXT("input_audio_buffer.append"));
            Msg->SetStringField(TEXT("audio"), FBase64::Encode(Slice));
            SendJson(Msg);
        }
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
    const bool bHadMic = Capture.IsValid();
    StopCapture();
    if (bOffline || !bHadMic)
    {
        TArray<uint8> Discard; while (PendingAudio.Dequeue(Discard)) {} QueuedChunks.Store(0);
        PlayBark();
        SetStatus(TEXT(""));
        return;
    }
    AwaitStarted = FPlatformTime::Seconds();
    if (!bReady)
    {
        bTurnEndPending = QueuedChunks.Load() > 0;
        bAwaitingReply = bTurnEndPending;
        SetStatus(bAwaitingReply ? TEXT("Thinking") : TEXT(""));
        return;
    }
    FlushCaptured();
    SendContextIfChanged();
    TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
    Msg->SetStringField(TEXT("type"), SentBytes >= MinTurnBytes ? TEXT("turn.end") : TEXT("turn.clear"));
    SendJson(Msg);
    bAwaitingReply = SentBytes >= MinTurnBytes;
    bResponseDone = false;
    SetStatus(bAwaitingReply ? TEXT("Thinking") : TEXT(""));
}

bool UReflectionsRealtimeVoiceComponent::SendTypedLine(const FString& Text)
{
    FString Line = Text.TrimStartAndEnd().Left(300);
    if (Line.IsEmpty() || !VoiceNpc.IsValid()) return false;
    Interrupt();
    bStaleTurn = false;
    PlayerText = Line;
    LastSource = EReflectionsReplySource::None;
    OnDialogueLine.Broadcast(TEXT("You"), Line, true, true);
    if (bOffline)
    {
        PlayBark();
        return true;
    }
    AwaitStarted = FPlatformTime::Seconds();
    bAwaitingReply = true;
    bResponseDone = false;
    SetStatus(TEXT("Thinking"));
    if (!bReady)
    {
        PendingTypedLine = Line;
        return true;
    }
    SendContextIfChanged();
    TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
    Msg->SetStringField(TEXT("type"), TEXT("text.turn"));
    Msg->SetStringField(TEXT("text"), Line);
    SendJson(Msg);
    return true;
}

// ---- Tick ----------------------------------------------------------------------------------------------

EReflectionsDialogueState UReflectionsRealtimeVoiceComponent::GetState() const
{
    if (bRecording.Load()) return EReflectionsDialogueState::Listening;
    if (IsSpeaking()) return EReflectionsDialogueState::Speaking;
    if (bAwaitingReply) return EReflectionsDialogueState::Thinking;
    if (Socket.IsValid() && !bReady) return EReflectionsDialogueState::Connecting;
    if (bReady) return EReflectionsDialogueState::Ready;
    return EReflectionsDialogueState::Idle;
}

void UReflectionsRealtimeVoiceComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* Tick)
{
    Super::TickComponent(DeltaTime, TickType, Tick);
    const double Now = FPlatformTime::Seconds();
    if (bSocketFailed)
    {
        bSocketFailed = false;
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("Dialogue relay unreachable; NPCs use barks for %.0f s."),
            GetDefault<UReflectionsNpcDialogueSettings>()->RelayRetrySeconds);
        FailToBarks(true);
    }
    if (bSocketClosed)
    {
        bSocketClosed = false;
        const bool bOwed = (bAwaitingReply && LastSource == EReflectionsReplySource::None) || bTurnEndPending || !PendingTypedLine.IsEmpty();
        // Closed before it was ever ready (busy, refused, upstream failure): barks for a while, no retry loop.
        if (bOwed || !bReady) FailToBarks(!bClosedForRestart);
        else CloseSocket();  // an idle or long session ended: the next ConnectToNpc opens a new one
    }
    if (bRestartPending)
    {
        bRestartPending = false;
        TWeakObjectPtr<AActor> Npc = VoiceNpc;
        CloseSocket();
        VoiceNpc.Reset();
        if (Npc.IsValid()) ConnectToNpc(Npc.Get());
    }
    if (bRecording.Load() && Capture)
    {
        FlushCaptured();
        if (SentBytes >= MaxRecordBytes) EndPushToTalk();  // the longest utterance the relay accepts
    }
    if (Socket.IsValid() && !bReady && Now - ConnectStarted > GetDefault<UReflectionsNpcDialogueSettings>()->ConnectTimeoutSeconds)
    {
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("Dialogue relay did not answer in time; NPCs use barks for a while."));
        FailToBarks(true);
    }
    if (bAwaitingReply && LastSource == EReflectionsReplySource::None && Now - AwaitStarted > ReplyTimeoutSeconds)
    {
        // Too late to be worth hearing: the relay drops the turn, and anything already on its way is ignored.
        if (bReady)
        {
            TSharedRef<FJsonObject> Msg = MakeShared<FJsonObject>();
            Msg->SetStringField(TEXT("type"), TEXT("response.cancel"));
            Msg->SetNumberField(TEXT("played_ms"), 0);
            SendJson(Msg);
        }
        bStaleTurn = true;
        bAwaitingReply = false;
        PlayBark();
    }
    // The audio component lives on the NPC: if the NPC is gone, nothing will ever drain the stream.
    const bool bStreamDrained = !OutputWave || !IsValid(OutputAudio) || OutputWave->GetAvailableAudioByteCount() <= 0;
    // Backstop: a reply whose audio was never pulled (audio device trouble) ends once it is long overdue.
    const double ReplySeconds = static_cast<double>(QueuedOutputBytes) / (BytesPerMs * 1000.0);
    const bool bOverdue = Now - AwaitStarted > ReplyTimeoutSeconds + ReplySeconds + 10.0;
    if (bAwaitingReply && bResponseDone && !bStreamDrained && bOverdue)
    {
        UE_LOG(LogReflectionsNpcDialogue, Log, TEXT("A reply's audio never finished playing; ending the turn."));
        StopPlayback();
    }
    if (bAwaitingReply && bResponseDone && (bStreamDrained || bOverdue))
    {
        bAwaitingReply = false;
        bResponseDone = false;
        SpeechEndedAt = Now;
        SetStatus(bReady ? TEXT("Ready") : TEXT(""));
    }
    if (BarkAudio && (!IsValid(BarkAudio) || !BarkAudio->IsPlaying()))
    {
        BarkAudio = nullptr;
        SpeechEndedAt = Now;
    }
}

void UReflectionsRealtimeVoiceComponent::CloseSocket()
{
    if (TSharedPtr<IWebSocket> Old = MoveTemp(Socket))
    {
        Old->OnConnected().Clear(); Old->OnMessage().Clear(); Old->OnConnectionError().Clear(); Old->OnClosed().Clear();
        Old->Close();
    }
    bReady = false;
    LastContextJson.Reset();
}

void UReflectionsRealtimeVoiceComponent::DisconnectVoice()
{
    StopCapture();
    CloseSocket();
    StopPlayback();
    if (IsValid(OutputAudio)) OutputAudio->DestroyComponent();
    OutputAudio = nullptr;
    OutputWave = nullptr;
    VoiceNpc.Reset();
    bReady = false; bOffline = false; bAwaitingReply = false; bResponseDone = false; bTurnEndPending = false;
    bStaleTurn = false;
    PendingTypedLine.Reset();
    LastContextJson.Reset();
    Speaker.Reset();
    TArray<uint8> Discard; while (PendingAudio.Dequeue(Discard)) {} QueuedChunks.Store(0);
    SetStatus(TEXT(""));
}

void UReflectionsRealtimeVoiceComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    DisconnectVoice(); Super::EndPlay(Reason);
}
