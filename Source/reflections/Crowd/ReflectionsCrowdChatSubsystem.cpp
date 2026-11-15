#include "Crowd/ReflectionsCrowdChatSubsystem.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"
#include "Voice/ReflectionsAmbientTalk.h"

#include "Components/AudioComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/AssetManager.h"
#include "Engine/DataTable.h"
#include "Engine/StreamableManager.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/PackageName.h"
#include "Sound/SoundBase.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsCrowdChat, Log, All);

namespace
{
    TAutoConsoleVariable<int32> CVarChatEnable(TEXT("Crowd.Chat.Enable"), 1,
        TEXT("Baked street conversations between NPCs standing together (the chat director)."));
    TAutoConsoleVariable<FString> CVarChatTable(TEXT("Crowd.Chat.Table"), TEXT("/Game/Audio/Jam/Voice/Ambient/DT_AmbientConversations"),
        TEXT("Long package name of audio's conversation table (rows of FReflectionsAmbientConversationRow)."));
    TAutoConsoleVariable<FString> CVarChatStoryTable(TEXT("Crowd.Chat.StoryTable"), TEXT("/Game/Audio/Jam/Voice/Ambient/DT_StoryConversations"),
        TEXT("Long package name of audio's story conversation table (named people's voices; played only by id)."));
    TAutoConsoleVariable<int32> CVarChatMaxActive(TEXT("Crowd.Chat.MaxActive"), 3,
        TEXT("Most conversations playing at once."));
    TAutoConsoleVariable<float> CVarChatHearDistance(TEXT("Crowd.Chat.HearDistance"), 2500.0f,
        TEXT("A conversation starts only while the player is this close (cm) to the group."));
    TAutoConsoleVariable<float> CVarChatMaxSpread(TEXT("Crowd.Chat.MaxSpread"), 400.0f,
        TEXT("A speaker farther than this (cm) from the group's centre ends the conversation."));
    TAutoConsoleVariable<float> CVarChatRepeatSeconds(TEXT("Crowd.Chat.RepeatSeconds"), 300.0f,
        TEXT("A conversation is not picked again for this long while another one fits."));

    const FName StreetSpot(TEXT("street"));

    /** Haunt_Market -> market. Place markers carry a prefix; audio's rows use the bare spot name. */
    FName NormalizeSpot(FName Spot)
    {
        FString Name = Spot.IsNone() ? FString() : Spot.ToString();
        for (const TCHAR* Prefix : { TEXT("Haunt_"), TEXT("Work_"), TEXT("Home_") })
        {
            if (Name.StartsWith(Prefix, ESearchCase::IgnoreCase))
            {
                Name.RightChopInline(FCString::Strlen(Prefix));
                break;
            }
        }
        return Name.IsEmpty() ? StreetSpot : FName(*Name);
    }

    bool IsCalm(const UReflectionsNpcReactionComponent* Brain)
    {
        return Brain && Brain->Reaction == EReflectionsNpcReaction::Calm;
    }

    FVector CentreOf(const TArray<AActor*>& Actors)
    {
        FVector Sum = FVector::ZeroVector;
        int32 Count = 0;
        for (const AActor* Actor : Actors)
        {
            if (!Actor) continue;
            Sum += Actor->GetActorLocation();
            ++Count;
        }
        return Count > 0 ? Sum / Count : FVector::ZeroVector;
    }

    TArray<AActor*> Resolve(const TArray<TWeakObjectPtr<AActor>>& Roles)
    {
        TArray<AActor*> Actors;
        Actors.Reserve(Roles.Num());
        for (const TWeakObjectPtr<AActor>& Role : Roles) Actors.Add(Role.Get());
        return Actors;
    }

    /** Backtracking over the (at most 4!) orders of the speakers; Unknown matches either sex. */
    bool Assign(int32 Role, const TArray<EReflectionsNpcSex>& Wanted, const TArray<EReflectionsNpcSex>& Have, TArray<int32>& Order, TArray<bool>& Used)
    {
        if (Role == Wanted.Num()) return true;
        for (int32 Speaker = 0; Speaker < Have.Num(); ++Speaker)
        {
            if (Used[Speaker]) continue;
            const bool bFits = Wanted[Role] == EReflectionsNpcSex::Unknown || Have[Speaker] == EReflectionsNpcSex::Unknown || Wanted[Role] == Have[Speaker];
            if (!bFits) continue;
            Used[Speaker] = true;
            Order[Role] = Speaker;
            if (Assign(Role + 1, Wanted, Have, Order, Used)) return true;
            Used[Speaker] = false;
        }
        return false;
    }
}

bool UReflectionsCrowdChatSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UReflectionsCrowdChatSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsCrowdChatSubsystem, STATGROUP_Tickables);
}

void UReflectionsCrowdChatSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
    {
        Npcs->OnNpcReaction.AddUniqueDynamic(this, &UReflectionsCrowdChatSubsystem::HandleNpcReaction);
    }
}

void UReflectionsCrowdChatSubsystem::Deinitialize()
{
    while (Active.Num() > 0) Finish(Active.Num() - 1, true);
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
    {
        Npcs->OnNpcReaction.RemoveDynamic(this, &UReflectionsCrowdChatSubsystem::HandleNpcReaction);
    }
    Super::Deinitialize();
}

const UDataTable* UReflectionsCrowdChatSubsystem::GetTable(bool bStory)
{
    bool& bLoaded = bStory ? bStoryTableLoaded : bTableLoaded;
    TObjectPtr<const UDataTable>& Slot = bStory ? StoryTable : Table;
    if (bLoaded) return Slot;
    bLoaded = true;
    // Audio owns the tables; they are only read. Until one exists its requests return false (callers bark instead).
    const FString Package = (bStory ? CVarChatStoryTable : CVarChatTable).GetValueOnGameThread();
    if (!FPackageName::DoesPackageExist(Package)) return nullptr;
    const UDataTable* Loaded = LoadObject<UDataTable>(nullptr, *FString::Printf(TEXT("%s.%s"), *Package, *FPackageName::GetShortName(Package)));
    if (Loaded && Loaded->GetRowStruct() && Loaded->GetRowStruct()->IsChildOf(FReflectionsAmbientConversationRow::StaticStruct()))
    {
        Slot = Loaded;
        UE_LOG(LogReflectionsCrowdChat, Log, TEXT("Chat director: %d conversations from %s."), Loaded->GetRowMap().Num(), *Package);
    }
    else if (Loaded)
    {
        UE_LOG(LogReflectionsCrowdChat, Warning, TEXT("Chat director: %s is not a table of FReflectionsAmbientConversationRow rows; it is ignored."), *Package);
    }
    return Slot;
}

bool UReflectionsCrowdChatSubsystem::CanStart(const TArray<AActor*>& Speakers) const
{
    const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!GetWorld() || !Npcs || CVarChatEnable.GetValueOnGameThread() == 0) return false;
    if (Speakers.Num() < 2 || Speakers.Num() > 4 || Active.Num() >= CVarChatMaxActive.GetValueOnGameThread()) return false;
    for (int32 Index = 0; Index < Speakers.Num(); ++Index)
    {
        const AActor* Speaker = Speakers[Index];
        if (!IsValid(Speaker) || Speakers.Find(const_cast<AActor*>(Speaker)) != Index) return false;
        if (!IsCalm(Npcs->FindNpc(Speaker)) || IsInConversation(Speaker)) return false;
    }
    // Nobody to hear it: let the caller do something cheaper.
    if (const APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0))
    {
        if (FVector::Dist(Player->GetActorLocation(), CentreOf(Speakers)) > CVarChatHearDistance.GetValueOnGameThread()) return false;
    }
    // Near the player (13 m), someone in view, a voice free, and not over the player's own conversation.
    return ReflectionsAmbientTalk::MayStartGroup(Speakers);
}

void UReflectionsCrowdChatSubsystem::StartChat(const FReflectionsAmbientConversationRow& Row, FName RowName, const TArray<AActor*>& Roles)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    const double Now = GetWorld()->GetTimeSeconds();
    FActiveChat& Chat = Active.AddDefaulted_GetRef();
    Chat.ConvId = Row.ConvId.IsNone() ? RowName : Row.ConvId;
    Chat.Lines = Row.Lines;
    Chat.NextLineAt = Now + 0.3;
    for (int32 Role = 0; Role < Roles.Num(); ++Role)
    {
        Chat.Roles.Add(Roles[Role]);
        UReflectionsNpcReactionComponent* Brain = Npcs ? Npcs->FindNpc(Roles[Role]) : nullptr;
        const FName VoiceId = Row.Speakers.IsValidIndex(Role) ? Row.Speakers[Role] : NAME_None;
        const FName Previous = Npcs ? Npcs->GetVoiceProfile(Roles[Role]).VoiceId : NAME_None;
        // Already speaking in that voice: nothing to change (and nothing to put back).
        const bool bOverride = Brain && !VoiceId.IsNone() && VoiceId != Previous;
        Chat.PreviousVoice.Add(Previous);
        Chat.bHadOverride.Add(Brain && Brain->HasVoiceOverride());
        if (bOverride) Brain->SetVoiceOverride(VoiceId);
        Chat.bOverridden.Add(bOverride);
    }
    // Load the conversation in the background (a synchronous load would stall a packaged game's frame).
    TArray<FSoftObjectPath> Waves;
    for (const FReflectionsAmbientLine& Line : Chat.Lines)
        if (!Line.Wave.IsNull() && !Line.Wave.Get()) Waves.AddUnique(Line.Wave.ToSoftObjectPath());
    if (!Waves.IsEmpty()) Chat.Loading = UAssetManager::GetStreamableManager().RequestAsyncLoad(Waves);
    Chat.LoadDeadline = Now + 3.0;
    LastPlayed.Add(Chat.ConvId, Now);
    ++Started;
    UE_LOG(LogReflectionsCrowdChat, Verbose, TEXT("Chat director: %s (%d speakers)."), *Chat.ConvId.ToString(), Roles.Num());
}

bool UReflectionsCrowdChatSubsystem::PlayConversationById(const TArray<AActor*>& Speakers, FName ConvId)
{
    if (ConvId.IsNone() || !CanStart(Speakers)) return false;
    for (const bool bStory : { true, false })
    {
        const UDataTable* Rows = GetTable(bStory);
        if (!Rows) continue;
        for (const TPair<FName, uint8*>& Entry : Rows->GetRowMap())
        {
            const FReflectionsAmbientConversationRow* Row = reinterpret_cast<const FReflectionsAmbientConversationRow*>(Entry.Value);
            if (!Row || (Row->ConvId != ConvId && Entry.Key != ConvId)) continue;
            if (Row->Lines.IsEmpty() || Row->Speakers.Num() != Speakers.Num()) return false;
            StartChat(*Row, Entry.Key, Speakers); // the caller's order is the role order
            return true;
        }
    }
    return false;
}

int32 UReflectionsCrowdChatSubsystem::FindChat(const AActor* Actor) const
{
    if (!Actor) return INDEX_NONE;
    for (int32 Index = 0; Index < Active.Num(); ++Index)
        for (const TWeakObjectPtr<AActor>& Role : Active[Index].Roles)
            if (Role.Get() == Actor) return Index;
    return INDEX_NONE;
}

bool UReflectionsCrowdChatSubsystem::IsInConversation(const AActor* Actor) const
{
    return FindChat(Actor) != INDEX_NONE;
}

void UReflectionsCrowdChatSubsystem::StopConversation(const AActor* Actor)
{
    const int32 Index = FindChat(Actor);
    if (Index != INDEX_NONE) Finish(Index, true);
}

bool UReflectionsCrowdChatSubsystem::CastRoles(const FReflectionsAmbientConversationRow& Row, const TArray<AActor*>& Speakers, TArray<AActor*>& OutRoles)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Npcs || Row.Speakers.Num() != Speakers.Num()) return false;
    // Best: the speakers already have exactly these voices, so nobody is re-voiced.
    {
        TArray<AActor*> Exact;
        TArray<bool> Taken;
        Taken.Init(false, Speakers.Num());
        for (const FName VoiceId : Row.Speakers)
        {
            int32 Found = INDEX_NONE;
            for (int32 Speaker = 0; Speaker < Speakers.Num() && Found == INDEX_NONE; ++Speaker)
                if (!Taken[Speaker] && !VoiceId.IsNone() && Npcs->GetVoiceProfile(Speakers[Speaker]).VoiceId == VoiceId) Found = Speaker;
            if (Found == INDEX_NONE) break;
            Taken[Found] = true;
            Exact.Add(Speakers[Found]);
        }
        if (Exact.Num() == Speakers.Num())
        {
            OutRoles = MoveTemp(Exact);
            return true;
        }
    }
    TArray<EReflectionsNpcSex> Wanted, Have;
    for (const FName VoiceId : Row.Speakers)
    {
        FReflectionsNpcVoiceRow Voice;
        Wanted.Add(Npcs->FindVoiceRow(VoiceId, Voice) ? Voice.Sex : EReflectionsNpcSex::Unknown);
    }
    for (const AActor* Speaker : Speakers) Have.Add(Npcs->GetVoiceProfile(Speaker).Sex);
    TArray<int32> Order;
    Order.Init(INDEX_NONE, Speakers.Num());
    TArray<bool> Used;
    Used.Init(false, Speakers.Num());
    if (!Assign(0, Wanted, Have, Order, Used)) return false;
    OutRoles.Reset();
    for (const int32 Speaker : Order) OutRoles.Add(Speakers[Speaker]);
    return true;
}

bool UReflectionsCrowdChatSubsystem::PlayConversationBetween(const TArray<AActor*>& Speakers, FName Spot)
{
    if (!CanStart(Speakers)) return false;
    // Only the generic table: story rows carry named people's reserved voices and are played by id.
    const UDataTable* Rows = GetTable(false);
    if (!Rows) return false;

    // Rows for this place and this many speakers, then the street ones; fresh ones first, in random order.
    const double Now = GetWorld()->GetTimeSeconds();
    const double RepeatSeconds = CVarChatRepeatSeconds.GetValueOnGameThread();
    const FName Wanted = NormalizeSpot(Spot);
    struct FCandidate { FName RowName; const FReflectionsAmbientConversationRow* Row; float Score; };
    TArray<FCandidate> Candidates;
    // The voices the speakers have now (a lives person keeps theirs if a row is voiced by exactly them).
    TArray<FName> OwnVoices;
    if (const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
        for (const AActor* Speaker : Speakers) OwnVoices.Add(Npcs->GetVoiceProfile(Speaker).VoiceId);
    OwnVoices.Sort(FNameLexicalLess());
    for (const TPair<FName, uint8*>& Entry : Rows->GetRowMap())
    {
        const FReflectionsAmbientConversationRow* Row = reinterpret_cast<const FReflectionsAmbientConversationRow*>(Entry.Value);
        if (!Row || Row->Lines.IsEmpty() || Row->Speakers.Num() != Speakers.Num() || !Row->RequiredFlag.IsNone()) continue;
        const bool bHere = Row->Spot == Wanted;
        if (!bHere && Row->Spot != StreetSpot) continue;
        const FName Id = Row->ConvId.IsNone() ? Entry.Key : Row->ConvId;
        const double* Last = LastPlayed.Find(Id);
        const bool bFresh = !Last || Now - *Last > RepeatSeconds;
        TArray<FName> RowVoices = Row->Speakers;
        RowVoices.Sort(FNameLexicalLess());
        const bool bOwnVoices = RowVoices == OwnVoices && !OwnVoices.Contains(NAME_None);
        Candidates.Add({ Entry.Key, Row, (bOwnVoices ? 8.0f : 0.0f) + (bHere ? 2.0f : 0.0f) + (bFresh ? 4.0f : 0.0f) + FMath::FRand() });
    }
    Candidates.Sort([](const FCandidate& A, const FCandidate& B) { return A.Score > B.Score; });

    for (const FCandidate& Candidate : Candidates)
    {
        TArray<AActor*> Roles;
        if (!CastRoles(*Candidate.Row, Speakers, Roles)) continue;
        StartChat(*Candidate.Row, Candidate.RowName, Roles);
        return true;
    }
    return false;
}

void UReflectionsCrowdChatSubsystem::PlayLine(FActiveChat& Chat)
{
    const UWorld* World = GetWorld();
    const FReflectionsAmbientLine& Line = Chat.Lines[Chat.NextLine++];
    AActor* Speaker = Chat.Roles.IsValidIndex(Line.SpeakerIndex) ? Chat.Roles[Line.SpeakerIndex].Get() : nullptr;
    USoundBase* Sound = Line.Wave.Get();
    float Duration = Line.Duration;
    if (Speaker && Sound)
    {
        // From the speaker's head, like the NPC system's barks; the root raised to head height without a head bone.
        const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
        const UReflectionsNpcReactionComponent* Brain = Npcs ? Npcs->FindNpc(Speaker) : nullptr;
        USkeletalMeshComponent* Body = Brain ? Brain->GetBodyMesh() : nullptr;
        const bool bHead = Body && Body->IsRegistered() && Body->GetBoneIndex(TEXT("head")) != INDEX_NONE &&
            (Body->LeaderPoseComponent.IsValid() || Body->GetNumComponentSpaceTransforms() > Body->GetBoneIndex(TEXT("head")));
        UAudioComponent* Audio = bHead
            ? UGameplayStatics::SpawnSoundAttached(Sound, Body, TEXT("head"), FVector::ZeroVector, EAttachLocation::SnapToTarget, true)
            : UGameplayStatics::SpawnSoundAttached(Sound, Speaker->GetRootComponent(), NAME_None, FVector(0.0, 0.0, 160.0), EAttachLocation::KeepRelativeOffset, true);
        Chat.Playing = Audio;
        ReflectionsAmbientTalk::Track(Audio, Speaker, false);
        if (Duration <= 0.0f)
        {
            const float SoundDuration = Sound->GetDuration();
            Duration = SoundDuration > 0.0f && SoundDuration < 60.0f ? SoundDuration : 3.0f;
        }
    }
    else if (Duration <= 0.0f)
    {
        Duration = 0.0f; // a missing take is skipped
    }
    Chat.NextLineAt = World->GetTimeSeconds() + Duration + Line.GapAfter;
}

void UReflectionsCrowdChatSubsystem::Tick(float DeltaTime)
{
    if (Active.IsEmpty()) return;
    const UWorld* World = GetWorld();
    const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!World || !Npcs) return;
    const double Now = World->GetTimeSeconds();
    const float MaxSpread = CVarChatMaxSpread.GetValueOnGameThread();
    for (int32 Index = Active.Num() - 1; Index >= 0; --Index)
    {
        FActiveChat& Chat = Active[Index];
        const TArray<AActor*> Roles = Resolve(Chat.Roles);
        const FVector Centre = CentreOf(Roles);
        bool bBroken = false;
        for (const AActor* Role : Roles)
        {
            bBroken |= !IsValid(Role) || !IsCalm(Npcs->FindNpc(Role)) || FVector::Dist2D(Role->GetActorLocation(), Centre) > MaxSpread;
        }
        // The player walked away: the conversation fades out rather than playing on to nobody.
        bBroken |= !ReflectionsAmbientTalk::IsPlaceWithinHearing(World, Centre, false);
        if (bBroken)
        {
            Finish(Index, true);
            continue;
        }
        if (Now < Chat.NextLineAt) continue;
        if (Chat.NextLine >= Chat.Lines.Num())
        {
            Finish(Index, false);
            continue;
        }
        // Its wave is still loading: wait a little (a take that never arrives is skipped after the deadline).
        const FReflectionsAmbientLine& Next = Chat.Lines[Chat.NextLine];
        if (!Next.Wave.IsNull() && !Next.Wave.Get() && Chat.Loading.IsValid() && Chat.Loading->IsLoadingInProgress() && Now < Chat.LoadDeadline)
        {
            Chat.NextLineAt = Now + 0.1;
            continue;
        }
        PlayLine(Chat);
    }
}

void UReflectionsCrowdChatSubsystem::HandleNpcReaction(AActor* Npc, EReflectionsNpcReaction Reaction, AActor* Cause, FVector Location)
{
    if (Reaction == EReflectionsNpcReaction::Calm) return;
    const int32 Index = FindChat(Npc);
    if (Index != INDEX_NONE) Finish(Index, true);
}

void UReflectionsCrowdChatSubsystem::Finish(int32 Index, bool bInterrupted)
{
    if (!Active.IsValidIndex(Index)) return;
    // Out of the list first: listeners may start a new conversation from the event.
    FActiveChat Chat = MoveTemp(Active[Index]);
    Active.RemoveAt(Index);
    if (Chat.Loading.IsValid()) Chat.Loading->CancelHandle();
    if (UAudioComponent* Audio = Chat.Playing.Get())
    {
        if (bInterrupted) Audio->FadeOut(0.25f, 0.0f);
    }
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    for (int32 Role = 0; Role < Chat.Roles.Num(); ++Role)
    {
        UReflectionsNpcReactionComponent* Brain = Npcs ? Npcs->FindNpc(Chat.Roles[Role].Get()) : nullptr;
        if (!Brain || !Chat.bOverridden.IsValidIndex(Role) || !Chat.bOverridden[Role]) continue;
        // Give back exactly what it had: another system's override (a lives person's voice), or its own voice.
        if (Chat.bHadOverride[Role] && !Chat.PreviousVoice[Role].IsNone()) Brain->SetVoiceOverride(Chat.PreviousVoice[Role]);
        else Brain->ClearVoiceOverride();
    }
    if (bInterrupted) ++Interrupted;
    OnConversationFinished.Broadcast(Resolve(Chat.Roles), Chat.ConvId, bInterrupted);
}

FString UReflectionsCrowdChatSubsystem::Describe() const
{
    FString Text = FString::Printf(TEXT("Chat director: table %s, story table %s, active %d, started %d, interrupted %d"),
        Table ? *Table->GetName() : (bTableLoaded ? TEXT("missing") : TEXT("not loaded")),
        StoryTable ? *StoryTable->GetName() : (bStoryTableLoaded ? TEXT("missing") : TEXT("not loaded")), Active.Num(), Started, Interrupted);
    for (const FActiveChat& Chat : Active)
    {
        Text += FString::Printf(TEXT("\n  %s: line %d/%d, %d speakers"), *Chat.ConvId.ToString(), Chat.NextLine, Chat.Lines.Num(), Chat.Roles.Num());
    }
    return Text;
}
