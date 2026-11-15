#include "Lives/ReflectionsLivesSubsystem.h"

#include "Lives/ReflectionsLivesMemory.h"
#include "Lives/ReflectionsLivesOverlay.h"
#include "Engine/GameViewportClient.h"
#include "Crowd/ReflectionsAmbientConversation.h"
#include "Engine/DataTable.h"
#include "Misc/PackageName.h"
#include "GameFlow/ReflectionsGameFlowSubsystem.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Debug/DebugDrawService.h"
#include "DrawDebugHelpers.h"
#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "NavigationPath.h"
#include "NavigationSystem.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsLives, Log, All);
DECLARE_CYCLE_STAT(TEXT("Lives"), STAT_ReflectionsLives, STATGROUP_Game);

namespace
{
    TAutoConsoleVariable<int32> CVarLivesEnable(TEXT("Lives.Enable"), 1, TEXT("NPC lives: identities, schedules, relationships, memory. 0 hands every body back."));
    TAutoConsoleVariable<int32> CVarLivesDebug(TEXT("Lives.Debug"), 0, TEXT("Lives overlay over each NPC: 0 off, 1 name/job/activity/next step, 2 also traits, goals and places. F7 toggles."));
    TAutoConsoleVariable<float> CVarLivesTimeScale(TEXT("Lives.TimeScale"), 1.0f, TEXT("Multiplies the speed of the Lives clock (1 = the people book's day length)."));
    TAutoConsoleVariable<float> CVarLivesFullRadius(TEXT("Lives.FullRadius"), 6000.0f, TEXT("Actor NPCs within this of the player are fully simulated (cm); farther ones are fast-forwarded."));
    TAutoConsoleVariable<int32> CVarLivesSpawnNamed(TEXT("Lives.SpawnNamed"), 1, TEXT("Spawn named people who have no actor when their schedule puts them near the player."));
    TAutoConsoleVariable<int32> CVarLivesMaxSpawned(TEXT("Lives.MaxSpawned"), 6, TEXT("Most named people Lives spawns at once."));
    TAutoConsoleVariable<float> CVarLivesSpawnRadius(TEXT("Lives.SpawnRadius"), 3500.0f, TEXT("Named people are spawned when their place is within this of the player (cm)."));
    TAutoConsoleVariable<float> CVarLivesDespawnRadius(TEXT("Lives.DespawnRadius"), 6500.0f, TEXT("People Lives spawned are removed beyond this when unseen (cm)."));
    TAutoConsoleVariable<int32> CVarLivesAutoCast(TEXT("Lives.AutoCastNamed"), 1, TEXT("Level-placed NPCs without a Lives_Person_<id> tag are cast as named people of the book first."));
    TAutoConsoleVariable<int32> CVarLivesHidePlaced(TEXT("Lives.HidePlacedInside"), 0, TEXT("Level-placed NPCs who go indoors are hidden (1) or wait at their door (0)."));
    TAutoConsoleVariable<float> CVarLivesWitnessRadius(TEXT("Lives.WitnessRadius"), 2500.0f, TEXT("How far people see a hurt, killing or conversion (cm)."));
    TAutoConsoleVariable<int32> CVarLivesStoryFallback(TEXT("Lives.UseStoryMarkers"), 1,
        TEXT("Ask the quest system's story markers (and their auto-placement) for places before placing them locally."));
    TAutoConsoleVariable<FString> CVarLivesChatDirector(TEXT("Lives.ChatDirector"), TEXT("/Script/reflections.ReflectionsCrowdChatSubsystem:PlayConversationBetween"),
        TEXT("World subsystem class path and function that plays a baked conversation: (TArray<AActor*> Speakers, [FName Spot]) -> bool."));

    const FName NoStrollTag(TEXT("NPC_NoStroll"));
    const FName SteeredTag(TEXT("Lives_Steered"));
    const FName SoldierTag(TEXT("NPC_Soldier"));
    const FName NoLifeTag(TEXT("Lives_None"));
    const FName HoldTag(TEXT("Lives_Hold"));
    const FName AmbientTag(TEXT("Crowd_Ring"));
    const TCHAR* PersonTagPrefix = TEXT("Lives_Person_");
    const TCHAR* PersonTagPrefixShort = TEXT("Person_");

    constexpr float ArriveRadius = 80.0f;
    constexpr float PlayerPauseRadius = 350.0f;
    constexpr float GreetRadius = 420.0f;
    constexpr float ChatDistance = 140.0f;

    uint32 Hash32(const FString& S) { return GetTypeHash(S) * 2654435761u + 0x9E37u; }

    bool SetWalkGait(ACharacter* Driver, bool bWalk)
    {
        // The sample character keeps its locomotion wishes in a Blueprint struct (CharacterInputState).
        if (!Driver) return false;
        FStructProperty* StateProperty = FindFProperty<FStructProperty>(Driver->GetClass(), TEXT("CharacterInputState"));
        if (!StateProperty || !StateProperty->Struct) return false;
        void* State = StateProperty->ContainerPtrToValuePtr<void>(Driver);
        bool bFound = false;
        for (TFieldIterator<FBoolProperty> It(StateProperty->Struct); It; ++It)
        {
            const FString Name = It->GetAuthoredName();
            if (Name.StartsWith(TEXT("WantsToWalk")))
            {
                It->SetPropertyValue_InContainer(State, bWalk);
                bFound = true;
            }
            else if (Name.StartsWith(TEXT("WantsToStrafe")) || Name.StartsWith(TEXT("WantsToSprint")) || Name.StartsWith(TEXT("WantsToAim")))
                It->SetPropertyValue_InContainer(State, false);
        }
        return bFound;
    }

    bool IsPlaceName(const FString& S)
    {
        return S.StartsWith(TEXT("Home_")) || S.StartsWith(TEXT("Work_")) || S.StartsWith(TEXT("Haunt_")) || S.StartsWith(TEXT("Door_")) ||
            S.StartsWith(TEXT("Place_")) || S.StartsWith(TEXT("Mk_")) || S.StartsWith(TEXT("Spot_")) || S.StartsWith(TEXT("Tower_"));
    }

    /** Mk_Gilt_Market_LanternRow -> Mk_Gilt_Market (the story book's generic kind on the same side). */
    FName GenericMarker(FName Tag)
    {
        TArray<FString> Parts;
        Tag.ToString().ParseIntoArray(Parts, TEXT("_"));
        if (Parts.Num() < 4 || Parts[0] != TEXT("Mk")) return NAME_None;
        return FName(*FString::Printf(TEXT("Mk_%s_%s"), *Parts[1], *Parts[2]));
    }

    float RadiusForKind(const FString& S)
    {
        if (S.StartsWith(TEXT("Home_")) || S.Contains(TEXT("_Home")) || S.Contains(TEXT("_Doorstep")) || S.Contains(TEXT("_Cellar")) || S.Contains(TEXT("_Shed"))) return 150.0f;
        if (S.StartsWith(TEXT("Haunt_")) || S.Contains(TEXT("_Market")) || S.Contains(TEXT("_Square")) || S.Contains(TEXT("_Yard")) || S.Contains(TEXT("_Camp"))) return 450.0f;
        return 300.0f;
    }

    FString PrettyPlace(FName Tag)
    {
        FString S = Tag.ToString();
        if (S.StartsWith(TEXT("Mk_")))
        {
            // Mk_Gilt_Market_LanternRow -> "Lantern Row"; Mk_Gilt_Home_IlseAttic -> "home"
            TArray<FString> Parts;
            S.ParseIntoArray(Parts, TEXT("_"));
            if (Parts.Num() >= 3 && Parts[2] == TEXT("Home")) return TEXT("home");
            const FString Name = Parts.Num() >= 4 ? Parts[3] : (Parts.Num() >= 3 ? Parts[2] : S);
            FString Spaced;
            for (int32 i = 0; i < Name.Len(); ++i)
            {
                if (i > 0 && FChar::IsUpper(Name[i]) && !FChar::IsUpper(Name[i - 1])) Spaced.AppendChar(TEXT(' '));
                Spaced.AppendChar(Name[i]);
            }
            return Spaced;
        }
        if (S.StartsWith(TEXT("Home_"))) return TEXT("home");
        if (S.StartsWith(TEXT("Away_"))) return TEXT("somewhere away from it");
        if (S.StartsWith(TEXT("Work_"))) return TEXT("work");
        if (S.StartsWith(TEXT("Haunt_"))) S = S.RightChop(6);
        else if (S.StartsWith(TEXT("Place_"))) S = S.RightChop(6);
        S.ReplaceInline(TEXT("_"), TEXT(" "));
        return TEXT("the ") + S.ToLower();
    }

    FString Joined(const TArray<FString>& List, const TCHAR* Sep = TEXT(", "))
    {
        return FString::Join(List, Sep);
    }

    UWorld* PickGameWorld(UWorld* Given)
    {
        if (Given && Given->IsGameWorld()) return Given;
        if (GEngine)
            for (const FWorldContext& Ctx : GEngine->GetWorldContexts())
                if (Ctx.World() && (Ctx.WorldType == EWorldType::PIE || Ctx.WorldType == EWorldType::Game)) return Ctx.World();
        return Given;
    }

    FAutoConsoleCommandWithWorldAndArgs CmdSetHour(TEXT("Lives.SetHour"), TEXT("Lives.SetHour <0-24>: sets the Lives clock."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsLivesSubsystem* Lives = UReflectionsLivesSubsystem::Get(PickGameWorld(World)))
                if (Args.Num() > 0) Lives->SetTimeOfDay(FCString::Atof(*Args[0]));
        }));
    FAutoConsoleCommandWithWorldAndArgs CmdDump(TEXT("Lives.Dump"), TEXT("Lives.Dump: one line per person."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsLivesSubsystem* Lives = UReflectionsLivesSubsystem::Get(PickGameWorld(World)))
                UE_LOG(LogReflectionsLives, Display, TEXT("%s"), *Lives->Describe());
        }));
    FAutoConsoleCommandWithWorldAndArgs CmdWitness(TEXT("Lives.TestWitness"), TEXT("Lives.TestWitness [witness name]: someone nearby that the witness knows is taken by the Tarnish."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsLivesSubsystem* Lives = UReflectionsLivesSubsystem::Get(PickGameWorld(World)))
                UE_LOG(LogReflectionsLives, Display, TEXT("TestWitness: %s"), *Lives->TestWitness(Args.Num() ? FString::Join(Args, TEXT(" ")) : FString()));
        }));
}

// ---- Component ------------------------------------------------------------------------------------------

UReflectionsLifeComponent::UReflectionsLifeComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

// ---- Setup ------------------------------------------------------------------------------------------------

UReflectionsLivesSubsystem* UReflectionsLivesSubsystem::Get(const UObject* WorldContext)
{
    const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    return World ? World->GetSubsystem<UReflectionsLivesSubsystem>() : nullptr;
}

bool UReflectionsLivesSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UReflectionsLivesSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsLivesSubsystem, STATGROUP_Tickables);
}

void UReflectionsLivesSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    bBegun = true;
    BeginDelay = 0.75f;
}

void UReflectionsLivesSubsystem::Deinitialize()
{
    if (Overlay.IsValid())
    {
        if (UWorld* World = GetWorld())
            if (UGameViewportClient* Viewport = World->GetGameViewport()) Viewport->RemoveViewportWidgetContent(Overlay.ToSharedRef());
        Overlay.Reset();
    }
    for (auto& Pair : Lives) ReleaseBody(Pair.Value);
    // Not after a New Game wiped memory (this world is the old run going away).
    if (UReflectionsLivesMemory* Mem = Memory.Get())
        if (Mem->Generation == MemoryGeneration) Mem->GameHours = LocalHours;
    Lives.Reset();
    Super::Deinitialize();
}

void UReflectionsLivesSubsystem::BeginLives()
{
    bStarted = true;
    Book.Load();
    Memory = UReflectionsLivesMemory::Get(this);
    if (UReflectionsLivesMemory* Mem = Memory.Get())
    {
        Mem->BindToGameFlow();
        // Game flow decides whether this start continues a checkpoint; people remember what they knew there.
        bool bHasCheckpoint = false;
        if (UGameInstance* GI = GetWorld()->GetGameInstance())
            if (const UReflectionsGameFlowSubsystem* Flow = GI->GetSubsystem<UReflectionsGameFlowSubsystem>())
                bHasCheckpoint = Flow->HasCheckpoint();
        Mem->SyncWithCheckpoint(bHasCheckpoint);
        MemoryGeneration = Mem->Generation;
        if (Mem->GameHours < 0.0) Mem->GameHours = Book.StartHour;
        LocalHours = Mem->GameHours;
    }
    else LocalHours = Book.StartHour;
    LastHour = FMath::FloorToInt(GetTimeOfDayHours());

    // Centre for automatic places: where the townspeople stand at the start, else the player.
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
    {
        FVector Sum = FVector::ZeroVector;
        int32 Count = 0;
        for (AActor* Actor : Npcs->GetNpcActors())
            if (Actor) { Sum += Actor->GetActorLocation(); ++Count; }
        if (Count > 0) { AutoCenter = Sum / Count; bHaveAutoCenter = true; }
    }
    if (!bHaveAutoCenter)
        if (APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0)) { AutoCenter = Player->GetActorLocation(); bHaveAutoCenter = true; }

    DiscoverPlaces();
    for (const FReflectionsPerson& Person : Book.GetNamed()) AddLife(Person);
    BindEvents();
    RefreshPopulation();
    UE_LOG(LogReflectionsLives, Log, TEXT("Lives started: %s, %d named, %d places, day %d %s"), *Book.GetSource(), Book.GetNamed().Num(), Places.Num(), GetDay(), *GetClockText());
}

void UReflectionsLivesSubsystem::BindEvents()
{
    if (bEventsBound) return;
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
    {
        Npcs->OnNpcSpellHit.AddUniqueDynamic(this, &UReflectionsLivesSubsystem::HandleNpcHit);
        Npcs->OnNpcDied.AddUniqueDynamic(this, &UReflectionsLivesSubsystem::HandleNpcDied);
        Npcs->OnNpcInfection.AddUniqueDynamic(this, &UReflectionsLivesSubsystem::HandleNpcInfection);
        bEventsBound = true;
    }
    if (UReflectionsSpellEventSubsystem* Spells = GetWorld()->GetSubsystem<UReflectionsSpellEventSubsystem>())
        Spells->OnSpellEvent.AddUniqueDynamic(this, &UReflectionsLivesSubsystem::HandleSpellEvent);
    BindCrimeEvent();
}

void UReflectionsLivesSubsystem::BindCrimeEvent()
{
    // npc-unify's OnPlayerCrime, found by name so Lives builds with or without it.
    if (bCrimeBound || !GetWorld()) return;
    const float Now = GetWorld()->GetTimeSeconds();
    if (Now < NextCrimeBindTry) return;
    NextCrimeBindTry = Now + 5.0f;
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Npcs) return;
    const FMulticastDelegateProperty* Prop = CastField<FMulticastDelegateProperty>(Npcs->GetClass()->FindPropertyByName(TEXT("OnPlayerCrime")));
    if (!Prop) return;
    bCrimeBound = true;
    const FName Handler = GET_FUNCTION_NAME_CHECKED(UReflectionsLivesSubsystem, HandlePlayerCrime);
    const UFunction* Mine = FindFunction(Handler);
    if (!Mine || !Prop->SignatureFunction || !Mine->IsSignatureCompatibleWith(Prop->SignatureFunction))
    {
        UE_LOG(LogReflectionsLives, Warning, TEXT("OnPlayerCrime has another signature than (AActor* Victim, FName Crime, AActor* Witness, FVector Location, float Heat): crimes are not heard by Lives."));
        return;
    }
    FScriptDelegate Delegate;
    Delegate.BindUFunction(this, Handler);
    Prop->AddDelegate(MoveTemp(Delegate), Npcs);
    UE_LOG(LogReflectionsLives, Log, TEXT("Listening to OnPlayerCrime."));
}

void UReflectionsLivesSubsystem::EnsureInput()
{
#if !UE_BUILD_SHIPPING
    if (DebugInput) return;
    APlayerController* PC = GetWorld()->GetFirstPlayerController();
    if (!PC || !PC->IsLocalController()) return;
    DebugInput = NewObject<UInputComponent>(PC, TEXT("LivesDebugInput"));
    DebugInput->RegisterComponent();
    DebugInput->BindKey(EKeys::F7, IE_Pressed, this, &UReflectionsLivesSubsystem::ToggleDebug).bConsumeInput = false;
    PC->PushInputComponent(DebugInput);
#endif
}

void UReflectionsLivesSubsystem::ToggleDebug()
{
    const int32 Next = GetDebugLevel() == 0 ? 1 : GetDebugLevel() == 1 ? 2 : 0;
    // F7 also switches off an overlay someone turned on from the console.
    if (Next == 0 && CVarLivesDebug.GetValueOnGameThread() != 0) CVarLivesDebug->Set(0, ECVF_SetByConsole);
    SetDebugLevel(Next);
}

void UReflectionsLivesSubsystem::SetDebugLevel(int32 Level)
{
    // Off by default: the level lives on this world's subsystem, so it never carries over to the next Play.
    DebugLevel = FMath::Clamp(Level, 0, 2);
}

int32 UReflectionsLivesSubsystem::GetDebugLevel() const
{
    return FMath::Max(DebugLevel, FMath::Clamp(CVarLivesDebug.GetValueOnGameThread(), 0, 2));
}

// ---- Clock -------------------------------------------------------------------------------------------------

float UReflectionsLivesSubsystem::GetTimeOfDayHours() const
{
    return static_cast<float>(FMath::Fmod(FMath::Max(0.0, LocalHours), 24.0));
}

int32 UReflectionsLivesSubsystem::GetDay() const
{
    return 1 + FMath::FloorToInt(FMath::Max(0.0, LocalHours) / 24.0);
}

FString UReflectionsLivesSubsystem::GetClockText() const
{
    const float H = GetTimeOfDayHours();
    const int32 Hour = FMath::FloorToInt(H);
    const int32 Minute = FMath::Clamp(FMath::FloorToInt((H - Hour) * 60.0f), 0, 59);
    return FString::Printf(TEXT("%02d:%02d"), Hour, Minute);
}

void UReflectionsLivesSubsystem::SetTimeOfDay(float Hour)
{
    const double Day = FMath::FloorToDouble(FMath::Max(0.0, LocalHours) / 24.0);
    double Next = Day * 24.0 + FMath::Fmod(FMath::Max(0.0f, Hour), 24.0f);
    if (Next < LocalHours) Next += 24.0;  // the clock never runs backwards: memories are stamped with it
    LocalHours = Next;
    if (UReflectionsLivesMemory* Mem = Memory.Get()) Mem->GameHours = LocalHours;
    for (auto& Pair : Lives) { Pair.Value.StepIndex = INDEX_NONE; Pair.Value.NextThink = 0.0f; }
}

// ---- Tick ---------------------------------------------------------------------------------------------------

void UReflectionsLivesSubsystem::Tick(float DeltaTime)
{
    SCOPE_CYCLE_COUNTER(STAT_ReflectionsLives);
    UWorld* World = GetWorld();
    if (!World || !World->IsGameWorld()) return;
    if (!bStarted)
    {
        // Give the NPC system a moment to enrol the placed townspeople first.
        BeginDelay -= DeltaTime;
        if (BeginDelay > 0.0f) return;
        BeginLives();
    }
    if (!CVarLivesEnable.GetValueOnGameThread())
    {
        for (auto& Pair : Lives) ReleaseBody(Pair.Value);
        return;
    }
    // New Game wiped memory while this (old) world is still up: it must not write the old run back in.
    if (Memory.IsValid() && Memory->Generation != MemoryGeneration) return;
    EnsureInput();
    BindEvents();
    BindCrimeEvent();

    // Clock.
    const float SecondsPerDay = FMath::Max(1.0f, Book.RealMinutesPerDay) * 60.0f;
    LocalHours += DeltaTime * (24.0 / SecondsPerDay) * FMath::Max(0.0f, CVarLivesTimeScale.GetValueOnGameThread());
    if (UReflectionsLivesMemory* Mem = Memory.Get()) Mem->GameHours = LocalHours;
    const int32 Hour = FMath::FloorToInt(GetTimeOfDayHours());
    if (Hour != LastHour)
    {
        LastHour = Hour;
        OnHourChanged.Broadcast(Hour);
    }

    const float Now = World->GetTimeSeconds();
    if (Now >= NextPopulation)
    {
        NextPopulation = Now + 0.5f;
        RefreshPopulation();
    }
    if (Now >= NextPlaceScan)
    {
        NextPlaceScan = Now + 10.0f;
        DiscoverPlaces();
    }
    if (Now >= NextSpawnCheck)
    {
        NextSpawnCheck = Now + 1.0f;
        SpawnNamedNearPlayer();
    }

    APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    const FVector PlayerLocation = Player ? Player->GetActorLocation() : AutoCenter;
    const float FullRadius = CVarLivesFullRadius.GetValueOnGameThread();
    for (auto& Pair : Lives)
    {
        FLife& Life = Pair.Value;
        AActor* Actor = Life.Actor.Get();
        if (Actor) Life.Lod = FVector::DistSquared(Actor->GetActorLocation(), PlayerLocation) <= FMath::Square(FullRadius) ? EReflectionsLifeLod::Full : EReflectionsLifeLod::Far;
        else Life.Lod = EReflectionsLifeLod::Virtual;

        if (Now >= Life.NextThink)
        {
            Life.NextThink = Now + (Life.Lod == EReflectionsLifeLod::Full ? 0.5f : Life.Lod == EReflectionsLifeLod::Far ? 1.5f : 3.0f) +
                static_cast<float>(Life.Seed % 100u) * 0.002f;
            Think(Life, Now);
        }
        if (!Actor) continue;
        if (CanSteer(Life) && (Life.bSteering || Now >= Life.ClaimNotBefore))
        {
            if (!Life.bSteering) TakeBody(Life);
            if (Life.Lod == EReflectionsLifeLod::Full && Player) TickShy(Life, Now, PlayerLocation);
            Steer(Life, DeltaTime);
            if (Life.Lod == EReflectionsLifeLod::Full) TryGreet(Life, Now, PlayerLocation);
        }
        else if (!CanSteer(Life))
        {
            // Someone who fears or hates Wren is close, but the body is not ours to move: say why (once per 10 s).
            if (Life.Lod == EReflectionsLifeLod::Full && Player && Now >= Life.NextShyNote &&
                FVector::Dist2D(Actor->GetActorLocation(), PlayerLocation) < 700.0f && GetPlayerFeeling(Life.Person.Id) > 0)
            {
                Life.NextShyNote = Now + 10.0;
                const UReflectionsNpcReactionComponent* B = Life.Brain.Get();
                UE_LOG(LogReflectionsLives, Log, TEXT("%s can't keep away from the Silverer: reaction %d, scripted %d, steered elsewhere %d, ambient %d, paused %d"),
                    *Life.Person.Name, B ? static_cast<int32>(B->Reaction) : -1, B && B->IsScripted() ? 1 : 0,
                    B && B->IsExternallySteered() && !Life.bSteering ? 1 : 0, Life.bAmbient ? 1 : 0, Life.bPaused ? 1 : 0);
            }
            ReleaseBody(Life);
            if (Life.Move == EMove::Chat || Life.Move == EMove::Meet) EndChat(Life);
        }
        // Keep their own roster voice (a street conversation may cast them as another voice while it plays).
        if (!Life.Person.VoiceId.IsNone() && Life.Move != EMove::Chat && Life.Move != EMove::Meet)
            if (UReflectionsNpcReactionComponent* Brain = Life.Brain.Get())
                if (Brain->VoiceId != Life.Person.VoiceId) Brain->SetVoiceOverride(Life.Person.VoiceId);
        if (UReflectionsLifeComponent* Comp = Life.Comp.Get())
        {
            Comp->Activity = Life.Activity;
            Comp->Place = Life.PlaceTag;
        }
    }
    UpdateOverlay();
}

// ---- Places -------------------------------------------------------------------------------------------------

void UReflectionsLivesSubsystem::DiscoverPlaces()
{
    UWorld* World = GetWorld();
    if (!World) return;
    TMap<FName, FVector> Doors;
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (!Actor || Actor->IsA<APawn>()) continue;
        TArray<FString> Candidates;
        for (const FName& Tag : Actor->Tags) Candidates.Add(Tag.ToString());
#if WITH_EDITOR
        Candidates.Add(Actor->GetActorLabel());
#endif
        // A quest marker may keep its name in a property instead.
        for (const TCHAR* PropName : { TEXT("PlaceTag"), TEXT("MarkerName"), TEXT("MarkerId"), TEXT("PlaceName"), TEXT("MarkerTag") })
        {
            if (const FNameProperty* NameProp = FindFProperty<FNameProperty>(Actor->GetClass(), PropName))
                Candidates.Add(NameProp->GetPropertyValue_InContainer(Actor).ToString());
            else if (const FStrProperty* StrProp = FindFProperty<FStrProperty>(Actor->GetClass(), PropName))
                Candidates.Add(StrProp->GetPropertyValue_InContainer(Actor));
        }
        for (const FString& S : Candidates)
        {
            if (!IsPlaceName(S)) continue;
            if (S.StartsWith(TEXT("Door_")))
            {
                Doors.Add(FName(*S.RightChop(5)), Actor->GetActorLocation());
                continue;
            }
            const FName Tag(*S);
            FReflectionsLifePlace& Place = Places.FindOrAdd(Tag);
            Place.Tag = Tag;
            Place.Location = Actor->GetActorLocation();
            Place.Door = Place.Location;
            Place.bAuto = false;
            Place.Radius = RadiusForKind(S);
            if (const FFloatProperty* R = FindFProperty<FFloatProperty>(Actor->GetClass(), TEXT("Radius")))
                Place.Radius = FMath::Max(50.0f, R->GetPropertyValue_InContainer(Actor));
            else if (const FDoubleProperty* RD = FindFProperty<FDoubleProperty>(Actor->GetClass(), TEXT("Radius")))
                Place.Radius = FMath::Max(50.0f, static_cast<float>(RD->GetPropertyValue_InContainer(Actor)));
        }
    }
    // The story book's resolution step 2: Mk_<Side>_<Kind> answers for any Mk_<Side>_<Kind>_<Name> of that kind.
    TArray<FReflectionsLifePlace> Generic;
    for (const auto& Pair : Places)
    {
        const FName G = GenericMarker(Pair.Key);
        if (G.IsNone() || Places.Contains(G) || Generic.ContainsByPredicate([G](const FReflectionsLifePlace& X) { return X.Tag == G; })) continue;
        FReflectionsLifePlace Copy = Pair.Value;
        Copy.Tag = G;
        Generic.Add(Copy);
    }
    for (const FReflectionsLifePlace& G : Generic) Places.Add(G.Tag, G);
    for (const auto& Door : Doors)
    {
        if (FReflectionsLifePlace* Place = Places.Find(Door.Key)) Place->Door = Door.Value;
        else
        {
            // A door alone (Door_Home_x) still makes a place to go in at.
            FReflectionsLifePlace& New = Places.Add(Door.Key);
            New.Tag = Door.Key;
            New.Location = New.Door = Door.Value;
            New.Radius = 150.0f;
        }
    }
    // The layout file's named places win over the map's markers (on a scripted town those may sit in a heap).
    if (!bPlaceFileLoaded) LoadPlaceFile();
    for (const FReflectionsLifePlace& P : FilePlaces) Places.Add(P.Tag, P);
}

namespace
{
    // Which pool a place name draws from when no marker answers it: homes, work (stalls), or gathering spots.
    FName PoolKindFor(const FString& S)
    {
        if (S.StartsWith(TEXT("Home_")) || S.Contains(TEXT("_Home")) || S.Contains(TEXT("_Doorstep")) || S.Contains(TEXT("_Cellar"))) return TEXT("home");
        if (S.StartsWith(TEXT("Work_")) || S.Contains(TEXT("_Workshop")) || S.Contains(TEXT("_Market")) || S.Contains(TEXT("_Stall")) ||
            S.Contains(TEXT("_Laundry")) || S.Contains(TEXT("_Shop"))) return TEXT("work");
        if (S.StartsWith(TEXT("Haunt_")) || S.StartsWith(TEXT("Spot_")) || S.Contains(TEXT("_Square")) || S.Contains(TEXT("_Fountain")) ||
            S.Contains(TEXT("_Cistern")) || S.Contains(TEXT("_Well")) || S.Contains(TEXT("_Lane")) || S.Contains(TEXT("_Inn")) || S.Contains(TEXT("_Tavern")))
            return TEXT("gather");
        return NAME_None;
    }
}

void UReflectionsLivesSubsystem::LoadPlaceFile()
{
    bPlaceFileLoaded = true;
    UWorld* World = GetWorld();
    if (!World) return;
    const FString Map = UWorld::RemovePIEPrefix(World->GetMapName());
    const FString Path = FPaths::ProjectContentDir() / TEXT("Crowd/Spots") / (Map + TEXT("_Lives.json"));
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *Path)) return;  // no layout file: markers and auto places as before
    TSharedPtr<FJsonObject> Root;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
    {
        UE_LOG(LogReflectionsLives, Warning, TEXT("Lives places: %s is not valid JSON."), *Path);
        return;
    }
    auto Read = [this](const TSharedPtr<FJsonObject>& O, float DefaultRadius)
    {
        FReflectionsLifePlace P;
        double X = 0, Y = 0, Z = 0, R = DefaultRadius;
        O->TryGetNumberField(TEXT("x"), X);
        O->TryGetNumberField(TEXT("y"), Y);
        O->TryGetNumberField(TEXT("z"), Z);
        O->TryGetNumberField(TEXT("radius"), R);
        double DX = X, DY = Y;
        O->TryGetNumberField(TEXT("door_x"), DX);
        O->TryGetNumberField(TEXT("door_y"), DY);
        FString Name;
        if (O->TryGetStringField(TEXT("name"), Name)) P.Tag = FName(*Name);
        P.Location = GroundPoint(FVector(X, Y, Z + 50.0));
        P.Door = GroundPoint(FVector(DX, DY, Z + 50.0));
        P.Radius = FMath::Clamp(static_cast<float>(R), 60.0f, 2000.0f);
        P.bAuto = false;
        return P;
    };
    const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
    if (Root->TryGetArrayField(TEXT("places"), List))
        for (const TSharedPtr<FJsonValue>& V : *List)
            if (const TSharedPtr<FJsonObject> O = V.IsValid() ? V->AsObject() : nullptr)
            {
                FReflectionsLifePlace P = Read(O, 300.0f);
                if (!P.Tag.IsNone()) FilePlaces.Add(P);
            }
    const TSharedPtr<FJsonObject>* Pools = nullptr;
    int32 PoolCount = 0;
    if (Root->TryGetObjectField(TEXT("pools"), Pools))
        for (const auto& Pair : (*Pools)->Values)
        {
            const TArray<TSharedPtr<FJsonValue>>* Points = nullptr;
            if (!Pair.Value.IsValid() || !Pair.Value->TryGetArray(Points)) continue;
            const FName Kind(*Pair.Key);
            const float DefaultRadius = Kind == TEXT("home") ? 150.0f : Kind == TEXT("work") ? 200.0f : 400.0f;
            TArray<FReflectionsLifePlace>& Pool = PlacePools.FindOrAdd(Kind);
            for (const TSharedPtr<FJsonValue>& V : *Points)
                if (const TSharedPtr<FJsonObject> O = V.IsValid() ? V->AsObject() : nullptr) { Pool.Add(Read(O, DefaultRadius)); ++PoolCount; }
        }
    const auto Count = [this](const TCHAR* Kind) { const TArray<FReflectionsLifePlace>* P = PlacePools.Find(FName(Kind)); return P ? P->Num() : 0; };
    UE_LOG(LogReflectionsLives, Log, TEXT("Lives places: %d named and %d pooled (homes %d, work %d, gather %d) from %s"), FilePlaces.Num(), PoolCount,
        Count(TEXT("home")), Count(TEXT("work")), Count(TEXT("gather")), *Path);
}

bool UReflectionsLivesSubsystem::PoolPlace(FName Where, const FVector& Near, FReflectionsLifePlace& OutPlace)
{
    const FName Kind = PoolKindFor(Where.ToString());
    const TArray<FReflectionsLifePlace>* Pool = Kind.IsNone() ? nullptr : PlacePools.Find(Kind);
    if (!Pool || Pool->Num() == 0) return false;
    int32 Index = INDEX_NONE;
    if (const int32* Known = PoolPicks.Find(Where)) Index = *Known;
    else
    {
        // Same name, same door every run; homes and stalls go one to a name until the pool runs out, squares are shared.
        const int32 N = Pool->Num();
        const int32 Start = static_cast<int32>(Hash32(Where.ToString()) % static_cast<uint32>(N));
        TSet<int32>& Used = PoolUsed.FindOrAdd(Kind);
        Index = Start;
        if (!Near.IsNearlyZero())
        {
            // Near where they are: the closest free door or stall (homes and work), or one of the three closest squares
            // (picked by name, so a crowd spreads over them), so the town's life happens where people already are.
            TArray<TPair<float, int32>> ByDistance;
            for (int32 i = 0; i < N; ++i)
                if (Kind == TEXT("gather") || !Used.Contains(i))
                    ByDistance.Emplace(FVector::DistSquared2D((*Pool)[i].Location, Near), i);
            ByDistance.Sort([](const TPair<float, int32>& A, const TPair<float, int32>& B) { return A.Key < B.Key; });
            if (ByDistance.Num() > 0)
                Index = ByDistance[Kind == TEXT("gather") ? static_cast<int32>(Hash32(Where.ToString()) % static_cast<uint32>(FMath::Min(3, ByDistance.Num()))) : 0].Value;
        }
        else if (Kind != TEXT("gather"))
            for (int32 i = 0; i < N; ++i)
                if (!Used.Contains((Start + i) % N)) { Index = (Start + i) % N; break; }
        Used.Add(Index);
        PoolPicks.Add(Where, Index);
    }
    OutPlace = (*Pool)[Index];
    OutPlace.Tag = Where;
    OutPlace.bAuto = false;
    return true;
}

FVector UReflectionsLivesSubsystem::GroundPoint(const FVector& Near) const
{
    UWorld* World = GetWorld();
    if (UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World))
    {
        FNavLocation Out;
        if (Nav->ProjectPointToNavigation(Near, Out, FVector(600.0, 600.0, 1000.0))) return Out.Location;
    }
    FHitResult Hit;
    FCollisionObjectQueryParams Objects(ECC_WorldStatic);
    if (World && World->LineTraceSingleByObjectType(Hit, Near + FVector(0, 0, 800), Near - FVector(0, 0, 2000), Objects))
        return Hit.ImpactPoint;
    return Near;
}

FReflectionsLifePlace& UReflectionsLivesSubsystem::AutoPlace(FName Tag, const FLife* For)
{
    // No marker on this map: put the place somewhere stable near the townspeople (same spot every run).
    FReflectionsLifePlace& Place = Places.Add(Tag);
    Place.Tag = Tag;
    Place.bAuto = true;
    const FString S = Tag.ToString();
    const uint32 H = Hash32(S);
    const float Angle = static_cast<float>(H % 360u);
    FVector Center = AutoCenter;
    float MinR = 800.0f, MaxR = 1500.0f;
    const bool bHome = S.StartsWith(TEXT("Home_")) || S.Contains(TEXT("_Home_")) || S.Contains(TEXT("_Doorstep_")) || S.Contains(TEXT("_Cellar_"));
    if (bHome)
    {
        Place.Radius = 150.0f;
        if (For && For->Brain.IsValid() && !For->bSpawnedByLives)
        {
            // A placed townsperson lives a few steps from where the level put them.
            Center = For->Brain->GetHomeLocation();
            MinR = 300.0f;
            MaxR = 600.0f;
        }
        else { MinR = 1300.0f; MaxR = 2000.0f; }
    }
    else if (S.StartsWith(TEXT("Work_")) || S.Contains(TEXT("_Workshop")) || S.Contains(TEXT("_Laundry")) || S.Contains(TEXT("_Infirmary")))
    {
        Place.Radius = 300.0f;
        MinR = 600.0f;
        MaxR = 1200.0f;
    }
    else
    {
        Place.Radius = RadiusForKind(S);
        MinR = 900.0f;
        MaxR = 1500.0f;
    }
    const float R = MinR + static_cast<float>((H >> 9) % 1000u) / 999.0f * (MaxR - MinR);
    Place.Location = GroundPoint(Center + FVector::ForwardVector.RotateAngleAxis(Angle, FVector::UpVector) * R);
    Place.Door = Place.Location;
    return Place;
}

bool UReflectionsLivesSubsystem::FindStoryMarker(FName Tag, FReflectionsLifePlace& OutPlace)
{
    // The quest system's marker lookup (UReflectionsStoryMarkerSubsystem::Find(Name, bAllowFallback)), called by
    // name so Lives builds without it. It also auto-places a marker when the map has none of that name.
    const FString TagText = Tag.ToString();
    const bool bStoryName = TagText.StartsWith(TEXT("Home_")) || TagText.StartsWith(TEXT("Work_")) || TagText.StartsWith(TEXT("Haunt_")) ||
        TagText.StartsWith(TEXT("Spot_")) || TagText.StartsWith(TEXT("Tower_")) || TagText.StartsWith(TEXT("Mk_"));
    if (!CVarLivesStoryFallback.GetValueOnGameThread() || !bStoryName) return false;
    UClass* Class = FindObject<UClass>(nullptr, TEXT("/Script/reflections.ReflectionsStoryMarkerSubsystem"));
    UWorldSubsystem* Sub = Class && Class->IsChildOf(UWorldSubsystem::StaticClass()) ? GetWorld()->GetSubsystemBase(Class) : nullptr;
    UFunction* Fn = Sub ? Sub->FindFunction(TEXT("Find")) : nullptr;
    if (!Fn) return false;
    uint8* Params = static_cast<uint8*>(FMemory_Alloca(FMath::Max<int32>(1, Fn->ParmsSize)));
    FMemory::Memzero(Params, Fn->ParmsSize);
    Fn->InitializeStruct(Params);
    FObjectPropertyBase* Ret = nullptr;
    bool bOk = true;
    for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
    {
        if (It->HasAnyPropertyFlags(CPF_ReturnParm)) Ret = CastField<FObjectPropertyBase>(*It);
        else if (FNameProperty* NameProp = CastField<FNameProperty>(*It)) NameProp->SetPropertyValue_InContainer(Params, Tag);
        else if (FBoolProperty* BoolProp = CastField<FBoolProperty>(*It)) BoolProp->SetPropertyValue_InContainer(Params, true);
        else bOk = false;
    }
    AActor* Marker = nullptr;
    if (bOk && Ret)
    {
        Sub->ProcessEvent(Fn, Params);
        Marker = Cast<AActor>(Ret->GetObjectPropertyValue_InContainer(Params));
    }
    Fn->DestroyStruct(Params);
    if (!Marker) return false;
    FReflectionsLifePlace& Place = Places.FindOrAdd(Tag);
    Place.Tag = Tag;
    Place.Location = Place.Door = Marker->GetActorLocation();
    Place.Radius = Tag.ToString().StartsWith(TEXT("Haunt_")) ? 450.0f : Tag.ToString().StartsWith(TEXT("Home_")) ? 150.0f : 300.0f;
    if (const FFloatProperty* R = FindFProperty<FFloatProperty>(Marker->GetClass(), TEXT("Radius")))
        Place.Radius = FMath::Clamp(R->GetPropertyValue_InContainer(Marker), 50.0f, 2000.0f);
    if (const FBoolProperty* AutoProp = FindFProperty<FBoolProperty>(Marker->GetClass(), TEXT("bAutoPlaced")))
        Place.bAuto = AutoProp->GetPropertyValue_InContainer(Marker);
    OutPlace = Place;
    return true;
}

bool UReflectionsLivesSubsystem::FindPlace(FName Tag, FReflectionsLifePlace& OutPlace)
{
    if (const FReflectionsLifePlace* Place = Places.Find(Tag))
    {
        OutPlace = *Place;
        return true;
    }
    return false;
}

TArray<FReflectionsLifePlace> UReflectionsLivesSubsystem::GetPlaces() const
{
    TArray<FReflectionsLifePlace> Out;
    Places.GenerateValueArray(Out);
    return Out;
}

// ---- Population -------------------------------------------------------------------------------------------

FString UReflectionsLivesSubsystem::UniqueName(const FReflectionsPerson& Person, int32& Salt) const
{
    if (Person.bNamed) return Person.Name;
    FString Name = Person.Name;
    for (Salt = 0; Salt < 24 && UsedNames.Contains(Name); ++Salt)
        Name = Book.Generate(Person.Id, Person.Sex, Person.Age, Person.Side, Salt + 1).Name;
    return Name;
}

UReflectionsLivesSubsystem::FLife& UReflectionsLivesSubsystem::AddLife(const FReflectionsPerson& InPerson)
{
    if (FLife* Existing = Lives.Find(InPerson.Id)) return *Existing;
    FLife& Life = Lives.Add(InPerson.Id);
    Life.Person = InPerson;
    Life.Seed = Hash32(InPerson.Id.ToString()) | 1u;
    if (Life.Person.Haunts.Num() == 0 && Book.GetGenerator().Flat.Haunts.Num() > 0)
        Life.Person.Haunts.Add(Book.GetGenerator().Flat.Haunts[Life.Seed % static_cast<uint32>(Book.GetGenerator().Flat.Haunts.Num())]);
    if (UReflectionsLivesMemory* Mem = Memory.Get())
    {
        FReflectionsPersonState& State = Mem->FindOrAdd(InPerson.Id);
        if (!State.Player.bSeeded)
        {
            // Where they start with the Silverer (story book stance), before anything has happened.
            State.Player.Opinion = FMath::Clamp(State.Player.Opinion + FReflectionsPeopleBook::StanceOpinion(InPerson.Stance), -1.0f, 1.0f);
            State.Player.bSeeded = true;
        }
        if (!Life.Person.bNamed)
        {
            // A generated person keeps the name they were first given, unless someone alive took it meanwhile.
            if (!State.GivenName.IsEmpty() && !UsedNames.Contains(State.GivenName)) Life.Person.Name = State.GivenName;
            else
            {
                int32 Salt = 0;
                Life.Person.Name = UniqueName(Life.Person, Salt);
                State.GivenName = Life.Person.Name;
            }
        }
    }
    UsedNames.Add(Life.Person.Name);
    ApplyStoryOverrides(Life);
    Life.Schedule = Book.ResolveSchedule(Life.Person);
    const FString Age = Life.Person.Age.ToString();
    Life.Speed = (Age == TEXT("Old") ? 100.0f : Age == TEXT("Young") ? 150.0f : 132.0f) + static_cast<float>(Life.Seed % 17u);
    if (!Life.Person.bNamed) LinkGeneratedFriends(Life);
    return Life;
}

void UReflectionsLivesSubsystem::LinkGeneratedFriends(FLife& Life)
{
    // Generated townsfolk know a few named people of their side (stable: picked by hash) and one other townsperson.
    const FReflectionsPeopleGenerator& G = Book.GetGenerator();
    const int32 Want = G.FriendsMin + static_cast<int32>(Life.Seed % static_cast<uint32>(FMath::Max(1, G.FriendsMax - G.FriendsMin + 1)));
    TArray<const FReflectionsPerson*> Pool;
    for (const FReflectionsPerson& P : Book.GetNamed())
        if (P.Side == Life.Person.Side) Pool.Add(&P);
    for (int32 i = 0; i < Want && Pool.Num() > 0; ++i)
    {
        const int32 Index = static_cast<int32>((Life.Seed >> (i * 5)) % static_cast<uint32>(Pool.Num()));
        Life.Person.Friends.AddUnique(Pool[Index]->Id);
        if (FLife* Other = Lives.Find(Pool[Index]->Id)) Other->Person.Friends.AddUnique(Life.Person.Id);
        Pool.RemoveAt(Index);
    }
    // Meet where a friend goes: their first haunt becomes this person's first haunt.
    if (Life.Person.Friends.Num() > 0)
        if (const FLife* Friend = Lives.Find(Life.Person.Friends[0]))
            if (Friend->Person.Haunts.Num() > 0) Life.Person.Haunts.Insert(Friend->Person.Haunts[0], 0);
    // And one acquaintance among the townsfolk already here.
    FLife* Best = nullptr;
    uint32 BestScore = MAX_uint32;
    for (auto& Pair : Lives)
    {
        if (Pair.Value.Person.bNamed || Pair.Key == Life.Person.Id || Pair.Value.bCrowdAgent != Life.bCrowdAgent) continue;
        const uint32 Score = (Pair.Value.Seed ^ Life.Seed) % 9973u;
        if (Score < BestScore) { BestScore = Score; Best = &Pair.Value; }
    }
    if (Best && Best->Person.Friends.Num() < 4)
    {
        Life.Person.Friends.AddUnique(Best->Person.Id);
        Best->Person.Friends.AddUnique(Life.Person.Id);
    }
    Life.Person.Haunts.SetNum(FMath::Min(Life.Person.Haunts.Num(), 3));
}

void UReflectionsLivesSubsystem::RefreshPopulation()
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Npcs) return;
    // Forget bodies that are gone. A ring passer-by is forgotten with its body, unless the player gave them a reason
    // to remember (then they stay a virtual person).
    TArray<FName> GoneAmbient;
    for (auto& Pair : Lives)
    {
        FLife& Life = Pair.Value;
        if (Life.Actor.IsStale() || (!Life.Actor.IsValid() && Life.Brain.IsStale()))
        {
            if (Life.bAmbient)
            {
                const FReflectionsPersonState* S = Memory.IsValid() ? Memory->Find(Pair.Key) : nullptr;
                // Kept only for something that matters (not a spell cast nearby or a word).
                const FReflectionsPlayerMemory* M = S ? &S->Player : nullptr;
                if (!S || (!S->bKilledByPlayer && M->Hurt + M->Helped + M->SavedFriend + M->HurtFriend + M->KilledFriend + M->Crimes + M->QuestsDone == 0))
                    GoneAmbient.Add(Pair.Key);
            }
            Life.Actor.Reset();
            Life.Brain.Reset();
            Life.Comp.Reset();
            Life.bSteering = false;
            Life.bSpawnedByLives = false;
            Life.Move = EMove::None;
        }
    }
    // The dead stay out of sight, whoever else shows or hides bodies.
    for (int32 i = GoneBodies.Num() - 1; i >= 0; --i)
    {
        AActor* Gone = GoneBodies[i].Get();
        if (!Gone) { GoneBodies.RemoveAt(i); continue; }
        if (!Gone->IsHidden()) Gone->SetActorHiddenInGame(true);
        if (UReflectionsNpcReactionComponent* GoneBrain = Npcs->FindNpc(Gone))
            if (ACharacter* Driver = GoneBrain->GetLocomotionDriver())
                if (!Driver->IsHidden()) Driver->SetActorHiddenInGame(true);
    }
    for (const FName Id : GoneAmbient)
    {
        if (const FLife* Life = Lives.Find(Id)) UsedNames.Remove(Life->Person.Name);
        Lives.Remove(Id);
        if (UReflectionsLivesMemory* Mem = Memory.Get()) Mem->Forget(Id);
    }
    for (AActor* Actor : Npcs->GetNpcActors())
    {
        if (!Actor || Actor->FindComponentByClass<UReflectionsLifeComponent>()) continue;
        UReflectionsNpcReactionComponent* Brain = Npcs->FindNpc(Actor);
        if (!Brain || Actor->ActorHasTag(NoLifeTag) || Actor->ActorHasTag(SoldierTag)) continue;
        switch (Brain->Disposition)
        {
        case EReflectionsNpcDisposition::Enemy:
        case EReflectionsNpcDisposition::Infected:
        case EReflectionsNpcDisposition::VillainHost:
            continue;
        default:
            break;
        }
        Embody(Actor, Brain);
    }
}

UReflectionsLivesSubsystem::FLife* UReflectionsLivesSubsystem::Embody(AActor* Actor, UReflectionsNpcReactionComponent* Brain)
{
    UReflectionsLivesMemory* Mem = Memory.Get();
    // 1) A tag names the person.
    FName Id = NAME_None;
    for (const FName& Tag : Actor->Tags)
    {
        const FString S = Tag.ToString();
        if (S.StartsWith(PersonTagPrefix)) { Id = FName(*S.RightChop(FCString::Strlen(PersonTagPrefix))); break; }
        if (S.StartsWith(PersonTagPrefixShort)) { Id = FName(*S.RightChop(FCString::Strlen(PersonTagPrefixShort))); break; }
    }
    const EReflectionsNpcSex LookSex = UReflectionsNpcSubsystem::GetLookSex(Actor);
    const FName Sex = LookSex == EReflectionsNpcSex::Female ? FName(TEXT("F")) : LookSex == EReflectionsNpcSex::Male ? FName(TEXT("M")) : NAME_None;
    auto Available = [this, Mem](FName PersonId)
    {
        const FLife* L = Lives.Find(PersonId);
        const FReflectionsPersonState* S = Mem ? Mem->Find(PersonId) : nullptr;
        return (!L || !L->Actor.IsValid()) && !(S && (S->bDead || S->bTarnished));
    };
    if (!Id.IsNone() && FindLife(Id) && FindLife(Id)->Actor.IsValid() && FindLife(Id)->Actor.Get() != Actor) Id = NAME_None;

    // 2) A level-placed townsperson is cast as a named person of the book (same sex; a matching look first).
    // (A body whose sex is unknown never gets a named person: a mismatched body is worse than an absent person.)
    if (Id.IsNone() && CVarLivesAutoCast.GetValueOnGameThread() && Actor->IsNetStartupActor() && !Sex.IsNone())
    {
        const FString ClassName = Actor->GetClass()->GetName();
        const FReflectionsPerson* Pick = nullptr;
        // The body: its sex (above), whether it is dressed as a guard, and its age (crowd-looks' Look_* tags).
        FName BodyAge = NAME_None;
        bool bGuardBody = Brain->Disposition == EReflectionsNpcDisposition::Guard || ClassName.Contains(TEXT("Guard"));
        bool bSoldierBody = false;
        for (const FName& Tag : Actor->Tags)
        {
            const FString T = Tag.ToString();
            if (T.StartsWith(TEXT("Look_Age_"))) BodyAge = FName(*T.RightChop(9));
            if (T == TEXT("Look_Role_Guard") || T == TEXT("Look_Role_Soldier")) bGuardBody = true;
            if (T == TEXT("Look_Role_Soldier")) bSoldierBody = true;
            if (T == TEXT("Look_Role_Civilian") || T == TEXT("Look_Role_Caster")) bGuardBody = false;
        }
        // Rags are Frostside's and red is Giltside's: a person goes only into a body of their own side.
        const FName Side = BodySide(Actor);
        // Two passes: first everything must fit (sex, guard or not, age), then the age may differ. A body that
        // fits nobody becomes a generated townsperson rather than the wrong named one.
        for (int32 Pass = 0; Pass < 2 && !Pick; ++Pass)
            for (const FReflectionsPerson& P : Book.GetNamed())
            {
                if (!Available(P.Id) || P.Sex != Sex || !SameSide(P.Side, Side)) continue;
                // Soldiers go in soldier bodies (a guard's on the second pass), guards in guard bodies, and guard
                // or soldier bodies take nobody else. (Squads' marching soldiers have no life at all: NPC_Soldier.)
                const FString Arch = P.Archetype.ToString();
                const FString Role = P.LookRole.ToString();
                const bool bSoldierPerson = IsSoldierPerson(P);
                const bool bGuardPerson = !bSoldierPerson && (Arch == TEXT("Guard") || Role == TEXT("Guard"));
                if (bSoldierPerson) { if (!bSoldierBody && !(Pass == 1 && bGuardBody)) continue; }
                else if (bGuardPerson != bGuardBody) continue;
                if (Pass == 0 && !BodyAge.IsNone() && P.Age != BodyAge) continue;
                if (!P.Look.IsEmpty() && ClassName.Contains(P.Look)) { Pick = &P; break; }
                if (!Pick && (P.Look.IsEmpty() || Pass == 1)) Pick = &P;
            }
        if (Pick) Id = Pick->Id;
    }

    // 3) Everyone else is a generated townsperson, stable per actor (level actors by name, spawned ones by place).
    if (Id.IsNone())
    {
        FString Key = Actor->IsNetStartupActor() ? Actor->GetLevel()->GetOutermost()->GetName() + TEXT(".") + Actor->GetName()
            : FString::Printf(TEXT("spawn_%d_%d"), static_cast<int32>(FMath::RoundToInt(Actor->GetActorLocation().X / 100.0)), static_cast<int32>(FMath::RoundToInt(Actor->GetActorLocation().Y / 100.0)));
        Key = UWorld::RemovePIEPrefix(Key);
        Id = FName(*FString::Printf(TEXT("gen_%08x"), Hash32(Key)));
        // This placed townsperson was killed by the player in an earlier run: the dead stay dead.
        if (Actor->IsNetStartupActor() && Mem)
            if (const FReflectionsPersonState* Dead = Mem->Find(Id))
                if (Dead->bDead && Dead->bKilledByPlayer)
                {
                    Actor->Tags.AddUnique(NoLifeTag);
                    Actor->Tags.AddUnique(NoStrollTag);
                    Actor->Tags.AddUnique(FName(TEXT("Lives_Gone")));
                    GoneBodies.AddUnique(Actor);
                    Actor->SetActorHiddenInGame(true);
                    Actor->SetActorEnableCollision(false);
                    if (ACharacter* Driver = Brain->GetLocomotionDriver())
                    {
                        Driver->SetActorHiddenInGame(true);
                        Driver->SetActorEnableCollision(false);
                    }
                    UE_LOG(LogReflectionsLives, Log, TEXT("%s stays gone: %s was killed by the Silverer."), *Actor->GetName(), *Dead->GivenName);
                    return nullptr;
                }
        for (int32 Salt = 1; !Available(Id) && Salt < 8; ++Salt)
            Id = FName(*FString::Printf(TEXT("gen_%08x_%d"), Hash32(Key), Salt));
    }

    FLife* Life = FindLife(Id);
    if (!Life)
    {
        const FReflectionsPerson* NamedPerson = Book.FindNamed(Id);
        FName Age = NAME_None;
        const FName Side = BodySide(Actor);
        for (const FName& Tag : Actor->Tags)
        {
            const FString S = Tag.ToString();
            if (S.StartsWith(TEXT("Look_Age_"))) Age = FName(*S.RightChop(9));
        }
        if (NamedPerson && !SameSide(NamedPerson->Side, Side))
            UE_LOG(LogReflectionsLives, Warning, TEXT("%s is tagged as %s (%s) but wears a %s look."), *Actor->GetName(), *NamedPerson->Name,
                *NamedPerson->Side.ToString(), *Side.ToString());
        Life = &AddLife(NamedPerson ? *NamedPerson : Book.Generate(Id, Sex, Age, Side, 0));
    }
    Life->Actor = Actor;
    Life->Brain = Brain;
    // The crowd's stroll lets the body go on its next refresh (1 s) once it sees NPC_NoStroll; claim after that.
    Life->ClaimNotBefore = GetWorld()->GetTimeSeconds() + 1.2f;
    Life->Move = EMove::None;
    Life->StepIndex = INDEX_NONE;
    Life->NextThink = 0.0f;
    UReflectionsLifeComponent* Comp = NewObject<UReflectionsLifeComponent>(Actor);
    Comp->PersonId = Life->Person.Id;
    Comp->PersonName = Life->Person.Name;
    Comp->RegisterComponent();
    Life->Comp = Comp;
    Life->bAmbient = Actor->ActorHasTag(AmbientTag);
    if (!Life->bAmbient)
    {
        Actor->Tags.AddUnique(NoStrollTag);
        Actor->Tags.AddUnique(SteeredTag);
    }
    Actor->Tags.AddUnique(FName(*(FString(PersonTagPrefix) + Life->Person.Id.ToString())));
    // A named person speaks in their own roster voice (story book voice_id).
    if (!Life->Person.VoiceId.IsNone() && Brain->VoiceId != Life->Person.VoiceId) Brain->SetVoiceOverride(Life->Person.VoiceId);
    // The quest system finds people (and avoids spawning a second one) by Person_<id>.
    Actor->Tags.AddUnique(FName(*(FString(PersonTagPrefixShort) + Life->Person.Id.ToString())));
    UE_LOG(LogReflectionsLives, Log, TEXT("%s is %s (%s, %s)"), *Actor->GetName(), *Life->Person.Name, *Life->Person.JobTitle, *Life->Person.Id.ToString());
    return Life;
}

void UReflectionsLivesSubsystem::Disembody(FLife& Life, bool bDestroySpawned)
{
    ReleaseBody(Life);
    AActor* Actor = Life.Actor.Get();
    if (Actor && bDestroySpawned && Life.bSpawnedByLives) Actor->Destroy();
    Life.Actor.Reset();
    Life.Brain.Reset();
    Life.Comp.Reset();
    Life.bSpawnedByLives = false;
    Life.Move = EMove::None;
    Life.ChatWith = NAME_None;
}

void UReflectionsLivesSubsystem::SpawnNamedNearPlayer()
{
    APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Player || !Npcs) return;
    const FVector P = Player->GetActorLocation();
    int32 Spawned = 0;
    for (auto& Pair : Lives)
    {
        FLife& Life = Pair.Value;
        AActor* Actor = Life.Actor.Get();
        if (!Life.bSpawnedByLives || !Actor) continue;
        // People Lives brought in go away again when they go indoors or are far behind the player.
        const bool bFar = FVector::Dist2D(Actor->GetActorLocation(), P) > CVarLivesDespawnRadius.GetValueOnGameThread() && !Actor->WasRecentlyRendered(1.0f);
        const bool bCalm = Life.Brain.IsValid() && Life.Brain->Reaction == EReflectionsNpcReaction::Calm;
        if (bCalm && (bFar || Life.bInside)) Disembody(Life, true);
        else ++Spawned;
    }
    if (!CVarLivesSpawnNamed.GetValueOnGameThread()) return;
    UReflectionsLivesMemory* Mem = Memory.Get();
    for (auto& Pair : Lives)
    {
        if (Spawned >= CVarLivesMaxSpawned.GetValueOnGameThread()) break;
        FLife& Life = Pair.Value;
        if (!Life.Person.bNamed || Life.Actor.IsValid() || Life.StepIndex == INDEX_NONE || Life.bIndoorStep) continue;
        if (const FReflectionsPersonState* S = Mem ? Mem->Find(Life.Person.Id) : nullptr)
            if (S->bDead || S->bTarnished) continue;
        if (FVector::Dist2D(Life.PlaceLocation, P) > CVarLivesSpawnRadius.GetValueOnGameThread()) continue;
        // Come out at the door of where they are, a little to the side.
        const FVector Where = GroundPoint(Life.PlaceLocation + FVector((Life.Seed % 200u) - 100.0f, ((Life.Seed >> 8) % 200u) - 100.0f, 0.0f));
        if (SpawnLife(Life, Where, static_cast<float>(Life.Seed % 360u)))
        {
            Life.bSpawnedByLives = true;
            ++Spawned;
        }
    }
}

AActor* UReflectionsLivesSubsystem::SpawnLife(FLife& Life, const FVector& Where, float FacingYaw)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Npcs) return nullptr;
    {
        // A look of the right sex and side, and dressed for the job (soldier, guard, townsperson).
        const bool bSoldier = IsSoldierPerson(Life.Person);
        const bool bGuard = !bSoldier && (Life.Person.Archetype == TEXT("Guard") || Life.Person.LookRole == TEXT("Guard"));
        TSubclassOf<AActor> Look = nullptr;
        TArray<UClass*> Strict, Relaxed;
        // The team's fixed list plus the archetypes' looks for this person's side (Pewterside's grey PewLook_* live
        // only in the archetypes), so a side with its own clothes never borrows another's.
        TArray<TSoftClassPtr<AActor>> Candidates = UReflectionsNpcSubsystem::TeamLooks();
        {
            const FString SideKey = Life.Person.Side.ToString().Left(4);
            const FName FullSide = SideKey.Equals(TEXT("Gilt"), ESearchCase::IgnoreCase) ? FName(TEXT("Giltside"))
                : SideKey.Equals(TEXT("Fros"), ESearchCase::IgnoreCase) ? FName(TEXT("Frostside"))
                : SideKey.Equals(TEXT("Pewt"), ESearchCase::IgnoreCase) ? FName(TEXT("Pewterside")) : NAME_None;
            if (!FullSide.IsNone())
            {
                const FName Arch = bSoldier ? FName(TEXT("AlliedSoldier")) : bGuard ? FName(TEXT("Guard")) : FName(TEXT("Civilian"));
                for (const TSoftClassPtr<AActor>& Soft : Npcs->GetLooksForSide(Arch, FullSide)) Candidates.AddUnique(Soft);
            }
        }
        for (const TSoftClassPtr<AActor>& Soft : Candidates)
            if (UClass* Class = Soft.LoadSynchronous())
            {
                const AActor* Cdo = Class->GetDefaultObject<AActor>();
                const EReflectionsNpcSex S = UReflectionsNpcSubsystem::GetLookSex(Cdo);
                if (S == EReflectionsNpcSex::Unknown || (!Life.Person.Sex.IsNone() && (Life.Person.Sex == TEXT("F")) != (S == EReflectionsNpcSex::Female))) continue;
                if (!SameSide(Life.Person.Side, BodySide(Cdo))) continue;  // never the other side's clothes
                const FString Role = BodyRole(Cdo).ToString();
                if (!Life.Person.Look.IsEmpty() && Class->GetName().Contains(Life.Person.Look)) { Strict.Reset(); Strict.Add(Class); break; }
                const bool bArmed = Role == TEXT("Soldier") || Role == TEXT("Guard");
                if (bSoldier ? Role == TEXT("Soldier") : bGuard ? Role == TEXT("Guard") : !bArmed) Strict.Add(Class);
                else if ((bSoldier || bGuard) && bArmed) Relaxed.Add(Class);
            }
        TArray<UClass*> Matching = Strict.Num() ? Strict : Relaxed;
        // Pewterside has no looks of its own yet: it borrows Giltside's (npc-unify's rule).
        if (Matching.Num() == 0 && FReflectionsPeopleBook::MarkerSide(Life.Person.Side) == TEXT("Pew") && !Life.Person.Side.IsNone())
            for (const TSoftClassPtr<AActor>& Soft : UReflectionsNpcSubsystem::TeamLooks())
                if (UClass* Class = Soft.LoadSynchronous())
                {
                    const AActor* Cdo = Class->GetDefaultObject<AActor>();
                    const EReflectionsNpcSex S = UReflectionsNpcSubsystem::GetLookSex(Cdo);
                    if (S == EReflectionsNpcSex::Unknown || (!Life.Person.Sex.IsNone() && (Life.Person.Sex == TEXT("F")) != (S == EReflectionsNpcSex::Female))) continue;
                    const FString Role = BodyRole(Cdo).ToString();
                    const bool bArmed = Role == TEXT("Soldier") || Role == TEXT("Guard");
                    if (SameSide(TEXT("Giltside"), BodySide(Cdo)) && (bSoldier || bGuard) == bArmed) Matching.Add(Class);
                }
        // Every face once before any face twice (crowd-looks: "it's all copied"), and never two alike within 30 m.
        if (Matching.Num() > 1 && !(Strict.Num() == 1 && !Life.Person.Look.IsEmpty()))
        {
            UClass* Best = nullptr;
            int32 BestScore = MAX_int32;
            for (int32 i = 0; i < Matching.Num(); ++i)
            {
                UClass* Class = Matching[(i + static_cast<int32>(Life.Seed % static_cast<uint32>(Matching.Num()))) % Matching.Num()];
                int32 Wearers = 0;
                bool bNear = false;
                for (TActorIterator<AActor> It(GetWorld(), Class); It; ++It)
                    if (It->GetClass() == Class)
                    {
                        ++Wearers;
                        if (FVector::Dist2D(It->GetActorLocation(), Where) < 3000.0f) bNear = true;
                    }
                // Unused faces first, then the person's age band (Look_Age_*), and never a twin close by.
                bool bAgeMismatch = false;
                if (!Life.Person.Age.IsNone())
                    for (const FName& Tag : Class->GetDefaultObject<AActor>()->Tags)
                        if (Tag.ToString().StartsWith(TEXT("Look_Age_")))
                            bAgeMismatch = !Tag.ToString().RightChop(9).Equals(Life.Person.Age.ToString(), ESearchCase::IgnoreCase);
                const int32 Score = Wearers * 2 + (bAgeMismatch ? 1 : 0) + (bNear ? 1000 : 0);
                if (Score < BestScore) { BestScore = Score; Best = Class; }
            }
            Look = Best;
        }
        else if (Matching.Num()) Look = Matching[0];
        else if (!Life.Person.Sex.IsNone()) return nullptr;  // no look of their sex and side: better absent than in the wrong body
        FName Archetype = Life.Person.Archetype.IsNone() ? FName(TEXT("Civilian")) : Life.Person.Archetype;
        // A soldier of the town is not an enemy: the squads' Soldier archetypes attack the player on sight.
        if (bSoldier && (Archetype == TEXT("Soldier") || Archetype == TEXT("SoldierCaster") || Archetype == TEXT("Enemy")))
            Archetype = Npcs->FindArchetype(TEXT("AlliedSoldier")) ? FName(TEXT("AlliedSoldier")) : FName(TEXT("Guard"));
        if (!Npcs->FindArchetype(Archetype)) Archetype = bSoldier || bGuard ? FName(TEXT("Guard")) : FName(TEXT("Civilian"));
        if (!Npcs->FindArchetype(Archetype)) Archetype = TEXT("Civilian");
        AActor* Actor = Npcs->SpawnNpc(Archetype, Where, FacingYaw, Look);
        if (!Actor) return nullptr;
        Actor->Tags.AddUnique(FName(*(FString(PersonTagPrefix) + Life.Person.Id.ToString())));
        Actor->Tags.AddUnique(FName(*(FString(PersonTagPrefixShort) + Life.Person.Id.ToString())));
        if (UReflectionsNpcReactionComponent* Brain = Npcs->FindNpc(Actor))
            if (Embody(Actor, Brain)) return Actor;
        return Actor;
    }
}

AActor* UReflectionsLivesSubsystem::SpawnPerson(FName PersonId, FVector Location, float FacingYaw)
{
    if (!bStarted) BeginLives();
    FLife* Life = FindLife(PersonId);
    if (!Life) return nullptr;
    if (AActor* Existing = Life->Actor.Get()) return Existing;
    if (const FReflectionsPersonState* S = Memory.IsValid() ? Memory->Find(PersonId) : nullptr)
        if (S->bDead || S->bTarnished) return nullptr;
    AActor* Actor = SpawnLife(*Life, Location, FacingYaw);
    if (FLife* Embodied = FindLife(PersonId)) Embodied->bSpawnedByLives = false;  // asked for: stays until someone removes it
    return Actor;
}

void UReflectionsLivesSubsystem::SetLifePaused(AActor* Actor, bool bPaused)
{
    if (FLife* Life = FindLifeByActor(Actor))
    {
        Life->bPaused = bPaused;
        if (bPaused)
        {
            EndChat(*Life);
            ReleaseBody(*Life);
        }
        else
        {
            Life->StepIndex = INDEX_NONE;  // pick the day up again from where they stand
            Life->NextThink = 0.0f;
        }
    }
}

bool UReflectionsLivesSubsystem::HasStoryFlag(FName Flag) const
{
    return Memory.IsValid() && Memory->StoryFlags.Contains(Flag);
}

void UReflectionsLivesSubsystem::SetStoryFlag(FName Flag, bool bOn)
{
    UReflectionsLivesMemory* Mem = Memory.Get();
    if (!Mem || Flag.IsNone()) return;
    if (bOn) Mem->StoryFlags.Add(Flag);
    else Mem->StoryFlags.Remove(Flag);
    // SQ10: the Silverer's record is cleaned. What witnesses saw fades to hearsay and half the crimes' weight is forgiven
    // (deaths of loved ones are not).
    if (bOn && Flag == TEXT("Silverer_RecordClean"))
    {
        if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this)) Npcs->ClearPlayerHeat();
        TArray<FName> Witnesses;
        for (const TPair<FName, FReflectionsPersonState>& Pair : Mem->GetAll())
            if (Pair.Value.Player.Crimes > 0) Witnesses.Add(Pair.Key);
        for (const FName Id : Witnesses)
        {
            FReflectionsPersonState& S = Mem->FindOrAdd(Id);
            for (FString& E : S.Events) E.ReplaceInline(TEXT("saw the Silverer"), TEXT("heard the Silverer"));
            S.Player.Opinion = FMath::Min(S.Player.KilledFriend ? S.Player.Opinion : 0.0f, S.Player.Opinion + 0.15f * static_cast<float>(S.Player.Crimes));
            S.Player.Crimes = 0;
            if (S.Player.LastDeed == EReflectionsPlayerDeed::WitnessedCrime) S.Player.LastDeedNote = TEXT("was said to have broken the law, but the record is clean now");
        }
    }
    // Flags can change where people live and how their day goes: everyone re-plans.
    for (auto& Pair : Lives)
    {
        ApplyStoryOverrides(Pair.Value);
        Pair.Value.Schedule = Book.ResolveSchedule(Pair.Value.Person);
        Pair.Value.StepIndex = INDEX_NONE;
        Pair.Value.NextThink = 0.0f;
    }
    UE_LOG(LogReflectionsLives, Log, TEXT("Story flag %s %s"), *Flag.ToString(), bOn ? TEXT("set") : TEXT("cleared"));
}

void UReflectionsLivesSubsystem::ApplyStoryOverrides(FLife& Life) const
{
    // Story flags that move people (side-quests.md). Hal_Home: Hal is home from the cellar, working the Lamplight bar.
    static const FName HalId(TEXT("hal_fairweather"));
    static const FName GoldieId(TEXT("goldie_fairweather"));
    if (Life.Person.Id == HalId)
    {
        const FReflectionsPerson* Book_ = Book.FindNamed(HalId);
        const FReflectionsPerson* Goldie = Book.FindNamed(GoldieId);
        if (HasStoryFlag(TEXT("Hal_Home")) && Goldie)
        {
            Life.Person.ScheduleKey = TEXT("innkeeper");
            Life.Person.Schedule.Reset();
            Life.Person.Work = Goldie->Work;
            Life.Person.Home = Goldie->Home;
        }
        else if (Book_)
        {
            Life.Person.ScheduleKey = Book_->ScheduleKey;
            Life.Person.Work = Book_->Work;
            Life.Person.Home = Book_->Home;
        }
    }
}

UReflectionsLivesSubsystem::FLife* UReflectionsLivesSubsystem::FindLifeByActor(const AActor* Actor)
{
    return const_cast<FLife*>(static_cast<const UReflectionsLivesSubsystem*>(this)->FindLifeByActor(Actor));
}

const UReflectionsLivesSubsystem::FLife* UReflectionsLivesSubsystem::FindLifeByActor(const AActor* Actor) const
{
    if (!Actor) return nullptr;
    const UReflectionsLifeComponent* Comp = Actor->FindComponentByClass<UReflectionsLifeComponent>();
    if (!Comp)
        if (const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
            if (const UReflectionsNpcReactionComponent* Brain = Npcs->FindNpc(Actor))
                if (Brain->GetOwner()) Comp = Brain->GetOwner()->FindComponentByClass<UReflectionsLifeComponent>();
    return Comp ? Lives.Find(Comp->PersonId) : nullptr;
}

int32 UReflectionsLivesSubsystem::GetEmbodiedCount() const
{
    int32 Count = 0;
    for (const auto& Pair : Lives) Count += Pair.Value.Actor.IsValid() ? 1 : 0;
    return Count;
}

// ---- Schedule -----------------------------------------------------------------------------------------------

EReflectionsLifeActivity UReflectionsLivesSubsystem::ActivityFor(FName Do)
{
    const FString S = Do.ToString().ToLower();
    if (S == TEXT("wake")) return EReflectionsLifeActivity::Wake;
    if (S == TEXT("work")) return EReflectionsLifeActivity::Work;
    if (S == TEXT("eat")) return EReflectionsLifeActivity::Eat;
    if (S == TEXT("errand")) return EReflectionsLifeActivity::Errand;
    if (S == TEXT("social") || S == TEXT("chat")) return EReflectionsLifeActivity::Social;
    if (S == TEXT("stroll")) return EReflectionsLifeActivity::Stroll;
    if (S == TEXT("shop")) return EReflectionsLifeActivity::Shop;
    if (S == TEXT("hide")) return EReflectionsLifeActivity::Hide;
    if (S == TEXT("guard")) return EReflectionsLifeActivity::Guard;
    if (S == TEXT("worship")) return EReflectionsLifeActivity::Worship;
    if (S == TEXT("home")) return EReflectionsLifeActivity::Home;
    if (S == TEXT("sleep")) return EReflectionsLifeActivity::Sleep;
    if (S == TEXT("patrol")) return EReflectionsLifeActivity::Patrol;
    return EReflectionsLifeActivity::Haunt;
}

int32 UReflectionsLivesSubsystem::CurrentStepIndex(const FLife& Life, float Hour) const
{
    if (Life.Schedule.Num() == 0) return INDEX_NONE;
    // Steps are sorted by hour; before the first step of the day, the last step of yesterday still runs.
    int32 Index = Life.Schedule.Num() - 1;
    for (int32 i = 0; i < Life.Schedule.Num(); ++i)
        if (Life.Schedule[i].At <= Hour) Index = i;
    return Index;
}

FName UReflectionsLivesSubsystem::ResolveWhere(const FLife& Life, const FReflectionsScheduleStep& Step, int32 StepIndex, int32 Depth) const
{
    const FString W = Step.Where.ToString();
    const TArray<FName>& Haunts = Life.Person.Haunts;
    auto Haunt = [&](int32 Offset) -> FName
    {
        if (Haunts.Num() == 0) return FName(TEXT("Haunt_Square"));
        return Haunts[(GetDay() + StepIndex + Offset) % Haunts.Num()];
    };
    const EReflectionsLifeActivity A = ActivityFor(Step.Do);
    const int32 Hour = FMath::FloorToInt(GetTimeOfDayHours());
    if (W == TEXT("home")) return Life.Person.Home;
    if (W == TEXT("barracks"))
        return Life.Person.Home.ToString().Contains(TEXT("Barracks")) ? Life.Person.Home
            : FName(*(TEXT("Mk_") + FReflectionsPeopleBook::MarkerSide(Life.Person.Side) + TEXT("_Home_Barracks")));
    if (W == TEXT("tavern"))
    {
        for (const FName H : Haunts)
            if (H.ToString().Contains(TEXT("Inn")) || H.ToString().Contains(TEXT("Tavern"))) return H;
        return FName(*(TEXT("Mk_") + FReflectionsPeopleBook::MarkerSide(Life.Person.Side) + TEXT("_Inn")));
    }
    // A patrol walks between work and the haunt, an hour each.
    if (W == TEXT("work")) return (A == EReflectionsLifeActivity::Patrol && Haunts.Num() && (Hour % 2) == 1) ? Haunt(0) : Life.Person.Work;
    // A stroll moves on to another haunt every game hour.
    if (W == TEXT("haunt")) return Haunt(A == EReflectionsLifeActivity::Stroll ? Hour : 0);
    if (W == TEXT("clique"))
    {
        if (!Life.Person.CliqueSpot.IsNone()) return Life.Person.CliqueSpot;
        FReflectionsScheduleStep Social = Step;
        Social.Where = TEXT("social");
        return ResolveWhere(Life, Social, StepIndex, Depth);
    }
    if (W == TEXT("social"))
    {
        // Go where a friend or relative is out right now; else to a favourite haunt.
        if (Depth == 0)
        {
            TArray<FName> Known = Life.Person.Friends;
            for (const FReflectionsKin& Kin : Life.Person.Family) Known.AddUnique(Kin.Id);
            for (int32 i = 0; i < Known.Num(); ++i)
            {
                const FLife* Other = FindLife(Known[(i + GetDay()) % Known.Num()]);
                if (!Other || Other->Schedule.Num() == 0) continue;
                const int32 OtherStep = CurrentStepIndex(*Other, GetTimeOfDayHours());
                const FReflectionsScheduleStep& S = Other->Schedule[OtherStep];
                const EReflectionsLifeActivity OtherActivity = ActivityFor(S.Do);
                if (OtherActivity == EReflectionsLifeActivity::Sleep || OtherActivity == EReflectionsLifeActivity::Home || OtherActivity == EReflectionsLifeActivity::Work) continue;
                const FName Where = ResolveWhere(*Other, S, OtherStep, Depth + 1);
                if (Where.ToString().StartsWith(TEXT("Haunt_"))) return Where;
            }
        }
        return Haunt(0);
    }
    return Step.Where;
}

FString UReflectionsLivesSubsystem::NextStepText(const FLife& Life) const
{
    if (Life.Schedule.Num() == 0 || Life.StepIndex == INDEX_NONE) return TEXT("-");
    const int32 Next = (Life.StepIndex + 1) % Life.Schedule.Num();
    const FReflectionsScheduleStep& S = Life.Schedule[Next];
    const int32 H = FMath::FloorToInt(S.At);
    const int32 M = FMath::FloorToInt((S.At - H) * 60.0f);
    return FString::Printf(TEXT("%02d:%02d %s @ %s"), H, M, *ActivityText(ActivityFor(S.Do)), *PrettyPlace(ResolveWhere(Life, S, Next)));
}

FName UReflectionsLivesSubsystem::CurrentBand() const
{
    float Fraction = 0.0f;
    if (const UGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance() : nullptr)
        if (const UReflectionsGameFlowSubsystem* Flow = GI->GetSubsystem<UReflectionsGameFlowSubsystem>())
            Fraction = Flow->GetInfectionFraction();
    const FReflectionsInfectionBand* Band = Book.BandFor(Fraction);
    return Band ? Band->Band : NAME_None;
}

void UReflectionsLivesSubsystem::Think(FLife& Life, float Now)
{
    UReflectionsLivesMemory* Mem = Memory.Get();
    FReflectionsPersonState* State = Mem ? &Mem->FindOrAdd(Life.Person.Id) : nullptr;
    if (State)
    {
        RefreshMood(*State);
        if (State->bDead || State->bTarnished)
        {
            Life.Activity = EReflectionsLifeActivity::Idle;
            return;
        }
    }
    const float Hour = GetTimeOfDayHours();
    const int32 StepIndex = CurrentStepIndex(Life, Hour);
    if (StepIndex == INDEX_NONE) return;
    const FReflectionsScheduleStep& Step = Life.Schedule[StepIndex];

    EReflectionsLifeActivity Activity = ActivityFor(Step.Do);
    FName Where = ResolveWhere(Life, Step, StepIndex);
    uint32 VigilSeed = 0;
    FName DoorOwner = Life.Person.Id;  // whose door a generic home means (the lost one's, at a vigil)

    // The street's mood (the Tarnish meter's band) bends everyone's day, by archetype (story book infection_overrides).
    const FName Band = CurrentBand();
    if (!Band.IsNone() && Band != TEXT("quiet"))
    {
        FString Arch = Life.Person.Archetype.ToString();
        if (Arch.IsEmpty() && Life.Brain.IsValid())
            Arch = Life.Brain->Disposition == EReflectionsNpcDisposition::Timid ? TEXT("Timid") : Life.Brain->Disposition == EReflectionsNpcDisposition::Brave ? TEXT("Brave")
                : Life.Brain->Disposition == EReflectionsNpcDisposition::Guard ? TEXT("Guard") : TEXT("Civilian");
        const bool bTimid = Arch == TEXT("Timid"), bBrave = Arch == TEXT("Brave"), bGuard = Arch == TEXT("Guard") || Arch == TEXT("Soldier");
        const bool bCivilian = !bTimid && !bBrave && !bGuard;
        if (Band == TEXT("spreading"))
        {
            if (bTimid && Activity == EReflectionsLifeActivity::Social) { Activity = EReflectionsLifeActivity::Home; Where = Life.Person.Home; }
        }
        else if (Band == TEXT("rising"))
        {
            if (bTimid && Activity != EReflectionsLifeActivity::Sleep) { Activity = EReflectionsLifeActivity::Hide; Where = Life.Person.Home; }
            else if (bCivilian && (Activity == EReflectionsLifeActivity::Stroll || Activity == EReflectionsLifeActivity::Shop)) { Activity = EReflectionsLifeActivity::Home; Where = Life.Person.Home; }
            else if (bBrave && Activity == EReflectionsLifeActivity::Social) { Activity = EReflectionsLifeActivity::Guard; Where = Life.Person.Work; }
            else if (bGuard && Activity == EReflectionsLifeActivity::Patrol) Activity = EReflectionsLifeActivity::Guard;
        }
        else if (Band == TEXT("brink") && Activity != EReflectionsLifeActivity::Sleep)
        {
            if (bTimid || bCivilian) { Activity = EReflectionsLifeActivity::Hide; Where = Life.Person.Home; }
            else if (bBrave) { Activity = EReflectionsLifeActivity::Guard; Where = Life.Person.CliqueSpot.IsNone() ? Life.Person.Work : Life.Person.CliqueSpot; }
            else { Activity = EReflectionsLifeActivity::Guard; Where = Life.Person.Work; }
        }
    }

    // What happened to them bends the day: fear and grief send them home, a fresh shock sends them away first.
    if (State)
    {
        const bool bAvoiding = State->AvoidUntilHours > LocalHours;
        if (Life.AvoidStepUntilHours > LocalHours && bAvoiding)
        {
            Activity = EReflectionsLifeActivity::Avoid;
            Where = FName(*(TEXT("Away_") + Life.Person.Id.ToString()));
        }
        else if (State->Mood == EReflectionsLifeMood::Afraid || State->Mood == EReflectionsLifeMood::Grieving)
        {
            Activity = State->Mood == EReflectionsLifeMood::Grieving ? EReflectionsLifeActivity::Grieve : EReflectionsLifeActivity::Home;
            Where = Life.Person.Home;
            // Evenings, the bereaved keep vigil outside the home of the one they lost.
            if (State->Mood == EReflectionsLifeMood::Grieving && Hour >= 17.0f && Hour < 23.0f && !State->ConcernFor.IsNone() && Memory.IsValid())
                if (const FReflectionsPersonState* Lost = Memory->Find(State->ConcernFor))
                    if (Lost->bDead)
                        if (const FLife* LostLife = FindLife(State->ConcernFor))
                            if (!LostLife->Person.Home.IsNone())
                            {
                                Activity = EReflectionsLifeActivity::Vigil;
                                Where = LostLife->Person.Home;
                                VigilSeed = LostLife->Seed;
                                DoorOwner = State->ConcernFor;
                            }
        }
        else if (bAvoiding)
        {
            // Never back to where it happened while the memory is fresh: another haunt, or home.
            FReflectionsLifePlace Place;
            if (FindPlace(Where, Place) && FVector::Dist2D(Place.Location, State->AvoidLocation) < 2000.0f)
            {
                FName Alternative = Life.Person.Home;
                for (const FName H : Life.Person.Haunts)
                {
                    FReflectionsLifePlace Other;
                    if (FindPlace(H, Other) && FVector::Dist2D(Other.Location, State->AvoidLocation) >= 2000.0f) { Alternative = H; break; }
                }
                Where = Alternative;
                if (Where == Life.Person.Home) Activity = EReflectionsLifeActivity::Home;
            }
        }
    }

    // Walking away from the player: the day waits until they are clear (TickShy hands it back).
    if (Life.bShy && Life.Actor.IsValid()) return;
    const bool bChanged = StepIndex != Life.StepIndex || Where != Life.PlaceTag || Activity != Life.Activity;
    if (!bChanged)
    {
        if (Life.Actor.IsValid() && Life.Lod == EReflectionsLifeLod::Full) TryMeet(Life, Now);
        // Far away and unseen: skip the walk, be where the schedule says.
        if (Life.Lod == EReflectionsLifeLod::Far && Life.Move == EMove::Travel && Life.bSteering)
            if (AActor* Actor = Life.Actor.Get())
                if (!Actor->WasRecentlyRendered(1.0f))
                    if (ACharacter* Driver = DriverOf(Life))
                    {
                        const float Half = Driver->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
                        Driver->SetActorLocation(Life.Goal + FVector(0, 0, Half + 2.0f), false, nullptr, ETeleportType::TeleportPhysics);
                        Life.PathIndex = Life.Path.Num();
                    }
        return;
    }

    if (Life.ChatWith != NAME_None) EndChat(Life);
    Life.StepIndex = StepIndex;
    Life.PlaceTag = Where;
    Life.Activity = Activity;
    Life.bIndoorStep = Activity == EReflectionsLifeActivity::Home || Activity == EReflectionsLifeActivity::Sleep || Activity == EReflectionsLifeActivity::Grieve ||
        Activity == EReflectionsLifeActivity::Hide;

    if (Activity == EReflectionsLifeActivity::Avoid && State)
    {
        // Away from where it happened, about 15 m, on the far side.
        const FVector From = Life.Actor.IsValid() ? Life.Actor->GetActorLocation() : AutoCenter;
        FVector Dir = (From - State->AvoidLocation).GetSafeNormal2D();
        if (Dir.IsNearlyZero()) Dir = FVector::ForwardVector;
        Life.PlaceLocation = GroundPoint(From + Dir * 1500.0f);
        Life.PlaceRadius = 300.0f;
    }
    else
    {
        FReflectionsLifePlace Place;
        // Resolution: the exact marker, its quest-system name, the generic kind on that side, the quest system's
        // own placement of that name, and last a stable spot near the townspeople.
        const FName Alias = Book.StoryNameFor(Where);
        if (!FindPlace(Where, Place) && !(!Alias.IsNone() && FindPlace(Alias, Place)) && !FindPlace(GenericMarker(Where), Place) &&
            (Life.bAmbient || !FindStoryMarker(Alias.IsNone() ? Where : Alias, Place)))
            Place = AutoPlace(Where, &Life);
        else Places.FindOrAdd(Where) = Place;  // the person's own name for it, found the same way next time
        // On a scripted town, a place no real marker answers takes a real house door, stall or square spot.
        FReflectionsLifePlace Pooled;
        const FVector Near = Life.Actor.IsValid() ? (Life.Brain.IsValid() && !Life.bSpawnedByLives ? Life.Brain->GetHomeLocation() : Life.Actor->GetActorLocation()) : FVector::ZeroVector;
        // The generic street of homes (Mk_<Side>_Home) is each person's own door there: one pooled door per owner.
        const FString WhereText = Where.ToString();
        const bool bGenericHome = WhereText.StartsWith(TEXT("Mk_")) && WhereText.EndsWith(TEXT("_Home"));
        bool bPooledDoor = false;
        if (bGenericHome && PoolPlace(FName(*(WhereText + TEXT("_") + DoorOwner.ToString())), DoorOwner == Life.Person.Id ? Near : FVector::ZeroVector, Pooled))
        {
            Place = Pooled;
            bPooledDoor = true;
        }
        else if (Place.bAuto && PoolPlace(Where, Near, Pooled))
        {
            Place = Pooled;
            Places.FindOrAdd(Where) = Place;
        }
        const bool bVigil = Activity == EReflectionsLifeActivity::Vigil;
        Life.PlaceLocation = (Life.bIndoorStep || bVigil) ? Place.Door : Place.Location;
        Life.PlaceRadius = bVigil ? 150.0f : Place.Radius;
        // A generic home (Mk_<Side>_Home: the street of homes) is shared: each person has their own door along it
        // (a vigil is kept at the lost one's door).
        const uint32 DoorSeed = bVigil && VigilSeed ? VigilSeed : Life.Seed;
        if (bGenericHome && !bPooledDoor)
            Life.PlaceLocation = GroundPoint(Life.PlaceLocation + FVector::ForwardVector.RotateAngleAxis(static_cast<float>(DoorSeed % 360u), FVector::UpVector) *
                (250.0f + static_cast<float>((DoorSeed >> 9) % 400u)));
    }

    if (AActor* Actor = Life.Actor.Get())
    {
        if (Life.bInside && !Life.bIndoorStep) ComeOut(Life);
        if (Life.bInside && Life.bIndoorStep && FVector::Dist2D(Actor->GetActorLocation(), Life.PlaceLocation) < 400.0f) return;
        if (Life.bInside) ComeOut(Life);
        // Each person heads for their own spot at the place (two friends aimed at one point shove each other forever).
        const float Spread = Life.bIndoorStep ? 60.0f : FMath::Max(80.0f, Life.PlaceRadius * 0.4f);
        const FVector Spot = Life.PlaceLocation + FVector::ForwardVector.RotateAngleAxis(static_cast<float>((Life.Seed >> 3) % 360u), FVector::UpVector) *
            (Spread * (0.5f + static_cast<float>((Life.Seed >> 13) % 50u) / 100.0f));
        SetGoal(Life, Life.bIndoorStep ? Spot : GroundPoint(Spot), EMove::Travel);
    }
    else
    {
        Life.bInside = Life.bIndoorStep;
    }
    OnLifeEvent.Broadcast(Life.Person.Id, Life.Actor.Get(), FString::Printf(TEXT("%s: %s at %s"), *GetClockText(), *ActivityText(Activity), *Where.ToString()));
}

// ---- Bodies -------------------------------------------------------------------------------------------------

ACharacter* UReflectionsLivesSubsystem::DriverOf(const FLife& Life) const
{
    const UReflectionsNpcReactionComponent* Brain = Life.Brain.Get();
    return Brain ? Brain->GetLocomotionDriver() : nullptr;
}

bool UReflectionsLivesSubsystem::CanSteer(const FLife& Life) const
{
    const UReflectionsNpcReactionComponent* Brain = Life.Brain.Get();
    if (!Brain || !Life.Actor.IsValid() || !DriverOf(Life)) return false;
    if (Brain->IsIncapacitated() || Brain->Reaction != EReflectionsNpcReaction::Calm || Brain->IsScripted()) return false;
    if (Brain->GetInfection() != EReflectionsNpcInfection::None) return false;
    switch (Brain->Disposition)
    {
    case EReflectionsNpcDisposition::Enemy:
    case EReflectionsNpcDisposition::Infected:
    case EReflectionsNpcDisposition::VillainHost:
        return false;
    default:
        break;
    }
    if (Life.bAmbient || Life.Actor->ActorHasTag(SoldierTag) || Life.Actor->ActorHasTag(HoldTag) || Life.Actor->ActorHasTag(AmbientTag) || Life.bPaused) return false;
    // Someone else (a squad, a cutscene, the stroll before it let go) has the body: wait.
    if (Brain->IsExternallySteered() && !Life.bSteering) return false;
    return true;
}

void UReflectionsLivesSubsystem::TakeBody(FLife& Life)
{
    UReflectionsNpcReactionComponent* Brain = Life.Brain.Get();
    if (!Brain) return;
    Brain->SetExternallySteered(true);
    Life.bSteering = true;
    Life.bGaitSet = SetWalkGait(DriverOf(Life), true);
    // Resume what they were doing from where they stand now.
    if (Life.StepIndex == INDEX_NONE) Life.Move = EMove::None;  // nothing planned yet: Think gives the first goal
    else if (Life.Move == EMove::Travel || Life.Move == EMove::Mill || Life.Move == EMove::None)
        SetGoal(Life, Life.Move == EMove::None ? Life.PlaceLocation : Life.Goal, Life.Move == EMove::None ? EMove::Travel : Life.Move);
}

void UReflectionsLivesSubsystem::ReleaseBody(FLife& Life)
{
    if (!Life.bSteering) return;
    Life.bSteering = false;
    if (UReflectionsNpcReactionComponent* Brain = Life.Brain.Get())
    {
        // Only clear the flag if nobody else set it in the meantime is unknowable; the NPC system re-steers itself.
        Brain->SetExternallySteered(false);
    }
    SetWalkGait(DriverOf(Life), false);
    if (Life.bShy)
    {
        Life.bShy = false;
        Life.bShyRun = false;
        Life.StepIndex = INDEX_NONE;
    }
    if (Life.bHeld) ComeOut(Life);
}

void UReflectionsLivesSubsystem::SetGoal(FLife& Life, const FVector& Goal, EMove Move)
{
    Life.Goal = Goal;
    Life.Move = Move;
    Life.Path.Reset();
    Life.PathIndex = 0;
    Life.StuckTime = 0.0f;
    ACharacter* Driver = DriverOf(Life);
    if (!Driver) return;
    const FVector Start = Driver->GetActorLocation();
    Life.LastPos = Start;
    if (UNavigationPath* Path = UNavigationSystemV1::FindPathToLocationSynchronously(GetWorld(), Start, Goal, Driver))
        if (Path->IsValid() && Path->PathPoints.Num() > 1)
        {
            Life.Path = Path->PathPoints;
            Life.PathIndex = 1;
        }
    if (Life.Path.Num() == 0)
    {
        Life.Path = { Start, Goal };
        Life.PathIndex = 1;
    }
}

void UReflectionsLivesSubsystem::FacePoint(FLife& Life, const FVector& Point, float DeltaTime)
{
    ACharacter* Driver = DriverOf(Life);
    if (!Driver) return;
    const FVector To = (Point - Driver->GetActorLocation()).GetSafeNormal2D();
    if (To.IsNearlyZero()) return;
    const FRotator Want(0.0, To.Rotation().Yaw, 0.0);
    Driver->SetActorRotation(FMath::RInterpTo(Driver->GetActorRotation(), Want, DeltaTime, 4.0f));
}

void UReflectionsLivesSubsystem::GoInside(FLife& Life)
{
    Life.bInside = true;
    Life.Move = EMove::Inside;
    AActor* Actor = Life.Actor.Get();
    if (!Actor || Life.bSpawnedByLives) return;  // spawned people are removed by SpawnNamedNearPlayer
    if (CVarLivesHidePlaced.GetValueOnGameThread())
    {
        Actor->SetActorHiddenInGame(true);
        Actor->SetActorEnableCollision(false);
        if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this)) Npcs->HoldNpc(Actor, 3600.0f);
        Life.bHeld = true;
    }
}

void UReflectionsLivesSubsystem::ComeOut(FLife& Life)
{
    Life.bInside = false;
    if (Life.Move == EMove::Inside) Life.Move = EMove::None;
    AActor* Actor = Life.Actor.Get();
    if (!Actor || !Life.bHeld) return;
    Life.bHeld = false;
    Actor->SetActorHiddenInGame(false);
    Actor->SetActorEnableCollision(true);
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this)) Npcs->ReleaseNpc(Actor);
}

void UReflectionsLivesSubsystem::Steer(FLife& Life, float DeltaTime)
{
    ACharacter* Driver = DriverOf(Life);
    AActor* Actor = Life.Actor.Get();
    if (!Driver || !Actor) return;
    // The dialogue (or another system) cleared the flag: take it back, we still own the walk.
    if (Life.Brain.IsValid() && !Life.Brain->IsExternallySteered()) Life.Brain->SetExternallySteered(true);
    if (!Life.bGaitSet) Life.bGaitSet = SetWalkGait(Driver, true);
    const FVector Here = Driver->GetActorLocation();

    if (Life.Move == EMove::Chat || Life.Move == EMove::Meet)
    {
        TickChat(Life, DeltaTime);
        if (Life.Move == EMove::Chat) return;
    }
    if (Life.Move == EMove::Inside || Life.Move == EMove::None) return;

    // People stop when the player walks up to them (and dialogue may turn them to face the player).
    if (APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0))
        if (!Life.bShy && FVector::DistSquared2D(Here, Player->GetActorLocation()) < FMath::Square(PlayerPauseRadius))
        {
            Life.StuckTime = 0.0f;
            Life.LastPos = Here;
            return;
        }

    if (Life.Idle > 0.0f)
    {
        Life.Idle -= DeltaTime;
        Life.LastPos = Here;
        return;
    }

    if (Life.PathIndex >= Life.Path.Num())
    {
        // Arrived.
        if (Life.bShy)
        {
            Life.Idle = 1.0f;  // far enough: wait there until TickShy gives the day back
            Life.LastPos = Here;
            return;
        }
        if (Life.Move == EMove::Travel)
        {
            if (Life.bIndoorStep && FVector::Dist2D(Here, Life.PlaceLocation) < 300.0f)
            {
                GoInside(Life);
                return;
            }
            Life.Move = EMove::Mill;
        }
        if (Life.Move == EMove::Meet) return;
        // Mill around the place: a few steps, a pause, another few steps.
        const FReflectionsPersonality& P = Life.Person.Personality;
        Life.Seed = Life.Seed * 1664525u + 1013904223u;
        if (Life.Activity == EReflectionsLifeActivity::Guard || Life.Activity == EReflectionsLifeActivity::Vigil)
        {
            // On watch: stand at the post, now and then a step and a look around.
            Life.Idle = 20.0f + static_cast<float>(Life.Seed % 1500u) / 100.0f;
            SetGoal(Life, GroundPoint(Life.PlaceLocation + FVector::ForwardVector.RotateAngleAxis(static_cast<float>((Life.Seed >> 8) % 360u), FVector::UpVector) * 60.0f), EMove::Mill);
            return;
        }
        const float Patrol = Life.Activity == EReflectionsLifeActivity::Patrol ? 2.0f : 1.0f;
        Life.Idle = (4.0f + static_cast<float>(Life.Seed % 700u) / 100.0f) * (1.4f - P.Chattiness * 0.6f) / Patrol;
        const float Angle = static_cast<float>((Life.Seed >> 8) % 360u);
        const float Dist = Life.PlaceRadius * Patrol * (0.3f + static_cast<float>((Life.Seed >> 16) % 70u) / 100.0f);
        SetGoal(Life, GroundPoint(Life.PlaceLocation + FVector::ForwardVector.RotateAngleAxis(Angle, FVector::UpVector) * Dist), EMove::Mill);
        return;
    }

    const FVector Target = Life.Path[Life.PathIndex];
    const bool bLast = Life.PathIndex == Life.Path.Num() - 1;
    if (FVector::DistSquared2D(Here, Target) < FMath::Square(bLast ? ArriveRadius : 60.0f))
    {
        ++Life.PathIndex;
        return;
    }
    const FVector Direction = (Target - Here).GetSafeNormal2D();
    const float MaxSpeed = FMath::Max(1.0f, Driver->GetCharacterMovement()->GetMaxSpeed());
    Driver->AddMovementInput(Direction, FMath::Clamp(Life.Speed / MaxSpeed, 0.1f, 1.0f), true);

    // Stuck on something: try a new path twice, then call it arrived.
    const float Moved = FVector::Dist2D(Here, Life.LastPos);
    Life.LastPos = Here;
    Life.StuckTime = Moved < 20.0f * DeltaTime ? Life.StuckTime + DeltaTime : FMath::Max(0.0f, Life.StuckTime - DeltaTime);
    if (Life.StuckTime > 2.5f)
    {
        const int32 Repaths = Life.Repaths + 1;
        if (Repaths > 2) Life.PathIndex = Life.Path.Num();
        else
        {
            SetGoal(Life, Life.Goal, Life.Move);
            Life.Repaths = Repaths;
        }
        Life.StuckTime = 0.0f;
    }
    else if (Life.PathIndex >= Life.Path.Num()) Life.Repaths = 0;
}

// ---- Relationships -------------------------------------------------------------------------------------------

FString UReflectionsLivesSubsystem::RelationTo(const FLife& Who, FName Other) const
{
    if (Other.IsNone() || Other == Who.Person.Id) return FString();
    for (const FReflectionsKin& Kin : Who.Person.Family)
        if (Kin.Id == Other) return Kin.Relation.IsEmpty() ? TEXT("family") : Kin.Relation;
    if (Who.Person.Friends.Contains(Other)) return TEXT("friend");
    if (Who.Person.Rivals.Contains(Other)) return TEXT("rival");
    if (!Who.Person.Clique.IsNone())
        if (const FLife* O = FindLife(Other))
            if (O->Person.Clique == Who.Person.Clique) return TEXT("one of their crowd");
    // Friendship written only on the other side still counts.
    if (const FLife* O = FindLife(Other))
    {
        for (const FReflectionsKin& Kin : O->Person.Family)
            if (Kin.Id == Who.Person.Id) return TEXT("family");
        if (O->Person.Friends.Contains(Who.Person.Id)) return TEXT("friend");
    }
    return FString();
}

void UReflectionsLivesSubsystem::TryMeet(FLife& Life, float Now)
{
    if (Life.Move != EMove::Mill || Life.ChatWith != NAME_None || !Life.bSteering) return;
    switch (Life.Activity)
    {
    case EReflectionsLifeActivity::Social:
    case EReflectionsLifeActivity::Haunt:
    case EReflectionsLifeActivity::Eat:
    case EReflectionsLifeActivity::Errand:
    case EReflectionsLifeActivity::Wake:
    case EReflectionsLifeActivity::Work:
    case EReflectionsLifeActivity::Stroll:
    case EReflectionsLifeActivity::Shop:
        break;
    default:
        return;
    }
    const FReflectionsPersonality& P = Life.Person.Personality;
    // Chatty people look for company more often; at work only a quick word with someone they know.
    Life.Seed = Life.Seed * 1664525u + 1013904223u;
    const float Chance = Life.Activity == EReflectionsLifeActivity::Social ? 0.35f + P.Chattiness * 0.5f : 0.08f + P.Chattiness * 0.2f;
    if (static_cast<float>(Life.Seed % 1000u) / 1000.0f > Chance) return;
    AActor* Actor = Life.Actor.Get();
    if (!Actor) return;
    FLife* Best = nullptr;
    float BestDist = 1200.0f;
    for (auto& Pair : Lives)
    {
        FLife& Other = Pair.Value;
        if (&Other == &Life || !Other.Actor.IsValid() || !Other.bSteering || Other.ChatWith != NAME_None || Other.Move != EMove::Mill) continue;
        const float Dist = FVector::Dist2D(Actor->GetActorLocation(), Other.Actor->GetActorLocation());
        if (Dist > BestDist) continue;
        const bool bKnown = Knows(Life, Other.Person.Id);
        const bool bChatty = P.Chattiness > 0.65f && Other.Person.Personality.Chattiness > 0.65f;
        if (!bKnown && !bChatty) continue;
        if (RelationTo(Life, Other.Person.Id) == TEXT("rival")) continue;
        const double* Last = Life.LastChatHours.Find(Other.Person.Id);
        if (Last && LocalHours - *Last < 2.0) continue;
        Best = &Other;
        BestDist = Dist;
    }
    if (!Best) return;
    // Walk up to each other and stand a step apart.
    const FVector A = Actor->GetActorLocation();
    const FVector B = Best->Actor->GetActorLocation();
    const FVector Mid = (A + B) * 0.5;
    const FVector Dir = (B - A).GetSafeNormal2D();
    Life.ChatWith = Best->Person.Id;
    Best->ChatWith = Life.Person.Id;
    Life.ChatLines = 0;
    Life.NextChatLine = 0.6f;
    Best->NextChatLine = 1000.0f;  // the one who came over leads the talk
    Life.ChatRemaining = Best->ChatRemaining = 16.0f + (P.Chattiness + Best->Person.Personality.Chattiness) * 9.0f;
    Life.Idle = Best->Idle = 0.0f;
    SetGoal(Life, GroundPoint(Mid - Dir * (ChatDistance * 0.5f)), EMove::Meet);
    SetGoal(*Best, GroundPoint(Mid + Dir * (ChatDistance * 0.5f)), EMove::Meet);
    Life.LastChatHours.Add(Best->Person.Id, LocalHours);
    Best->LastChatHours.Add(Life.Person.Id, LocalHours);
    const FString Relation = RelationTo(Life, Best->Person.Id);
    const FString What = FString::Printf(TEXT("met %s (%s) at %s"), *Best->Person.Name, Relation.IsEmpty() ? TEXT("a chatty stranger") : *Relation, *PrettyPlace(Life.PlaceTag));
    if (UReflectionsLivesMemory* Mem = Memory.Get()) AddEvent(Mem->FindOrAdd(Life.Person.Id), What);
    OnLifeEvent.Broadcast(Life.Person.Id, Actor, What);
}

void UReflectionsLivesSubsystem::TickChat(FLife& Life, float DeltaTime)
{
    FLife* Other = FindLife(Life.ChatWith);
    if (!Other || !Other->Actor.IsValid() || !Life.Actor.IsValid() || Other->ChatWith != Life.Person.Id || !Other->bSteering)
    {
        EndChat(Life);
        return;
    }
    const float Dist = FVector::Dist2D(Life.Actor->GetActorLocation(), Other->Actor->GetActorLocation());
    if (Life.Move == EMove::Meet)
    {
        if (Dist < ChatDistance + 80.0f || Life.PathIndex >= Life.Path.Num())
        {
            Life.Move = EMove::Chat;
            Life.Path.Reset();
        }
        else return;  // keep walking (Steer continues)
    }
    FacePoint(Life, Other->Actor->GetActorLocation(), DeltaTime);
    Life.ChatRemaining -= DeltaTime;
    if (Other->Move != EMove::Chat && Other->Move != EMove::Meet) { EndChat(Life); return; }
    Life.NextChatLine -= DeltaTime;
    if (Life.NextChatLine <= 0.0f && Other->Move == EMove::Chat)
    {
        // The leader speaks first and keeps the turns: A, B, A, B...
        const bool bLeaderTurn = (Life.ChatLines % 2) == 0;
        if (Life.ChatLines == 0)
        {
            // A baked conversation if the crowd's director can play one for these two; else turns of barks.
            bool bPlayed = TryStoryConversation(Life, *Other);
            const FString Director = CVarLivesChatDirector.GetValueOnGameThread();
            FString ClassPath, FuncName;
            if (!bPlayed && Director.Split(TEXT(":"), &ClassPath, &FuncName))
                if (UClass* Class = FindObject<UClass>(nullptr, *ClassPath))
                    if (Class->IsChildOf(UWorldSubsystem::StaticClass()))
                        if (UWorldSubsystem* Sub = GetWorld()->GetSubsystemBase(Class))
                            if (UFunction* Fn = Sub->FindFunction(FName(*FuncName)))
                            {
                                uint8* Params = static_cast<uint8*>(FMemory_Alloca(FMath::Max<int32>(1, Fn->ParmsSize)));
                                FMemory::Memzero(Params, Fn->ParmsSize);
                                Fn->InitializeStruct(Params);
                                bool bOk = true;
                                FBoolProperty* Ret = nullptr;
                                for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
                                {
                                    if (It->HasAnyPropertyFlags(CPF_ReturnParm)) { Ret = CastField<FBoolProperty>(*It); continue; }
                                    if (FArrayProperty* Arr = CastField<FArrayProperty>(*It))
                                    {
                                        if (!CastField<FObjectPropertyBase>(Arr->Inner)) { bOk = false; break; }
                                        TArray<AActor*>* Speakers = Arr->ContainerPtrToValuePtr<TArray<AActor*>>(Params);
                                        Speakers->Add(Life.Actor.Get());
                                        Speakers->Add(Other->Actor.Get());
                                    }
                                    else if (FNameProperty* NameProp = CastField<FNameProperty>(*It))
                                        NameProp->SetPropertyValue_InContainer(Params, Life.PlaceTag);
                                    else { bOk = false; break; }
                                }
                                if (bOk)
                                {
                                    Sub->ProcessEvent(Fn, Params);
                                    bPlayed = !Ret || Ret->GetPropertyValue_InContainer(Params);
                                }
                                Fn->DestroyStruct(Params);
                            }
            if (bPlayed)
            {
                Life.ChatLines = 1000;  // the director has the lines; just stand together until it is done
                Life.NextChatLine = 1000.0f;
                Life.bDirectorChat = true;
                Life.ChatRemaining = 60.0f;
                Life.NextDirectorCheck = 2.0f;
                return;
            }
        }
        if (Life.ChatLines < 1000)
        {
            PlayChatLine(bLeaderTurn ? Life : *Other, bLeaderTurn ? *Other : Life);
            ++Life.ChatLines;
            Life.NextChatLine = 3.2f + static_cast<float>(Life.Seed % 150u) / 100.0f;
        }
    }
    if (Life.bDirectorChat)
    {
        Life.NextDirectorCheck -= DeltaTime;
        bool bTalking = true;
        if (Life.NextDirectorCheck <= 0.0f)
        {
            Life.NextDirectorCheck = 0.5f;
            if (CallDirector(TEXT("IsInConversation"), Life.Actor.Get(), bTalking) && !bTalking) Life.ChatRemaining = 0.0f;
        }
    }
    if (Life.ChatRemaining <= 0.0f)
    {
        EndChat(*Other);
        EndChat(Life);
    }
}

bool UReflectionsLivesSubsystem::CallDirectorConversation(const TCHAR* Function, const TArray<AActor*>& Speakers, FName Arg) const
{
    FString ClassPath, Unused;
    if (!CVarLivesChatDirector.GetValueOnGameThread().Split(TEXT(":"), &ClassPath, &Unused)) return false;
    UClass* Class = FindObject<UClass>(nullptr, *ClassPath);
    UWorldSubsystem* Sub = Class && Class->IsChildOf(UWorldSubsystem::StaticClass()) ? GetWorld()->GetSubsystemBase(Class) : nullptr;
    UFunction* Fn = Sub ? Sub->FindFunction(Function) : nullptr;
    if (!Fn) return false;
    uint8* Params = static_cast<uint8*>(FMemory_Alloca(FMath::Max<int32>(1, Fn->ParmsSize)));
    FMemory::Memzero(Params, Fn->ParmsSize);
    Fn->InitializeStruct(Params);
    bool bOk = true;
    FBoolProperty* Ret = nullptr;
    for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
    {
        if (It->HasAnyPropertyFlags(CPF_ReturnParm)) Ret = CastField<FBoolProperty>(*It);
        else if (FArrayProperty* Arr = CastField<FArrayProperty>(*It))
        {
            if (!CastField<FObjectPropertyBase>(Arr->Inner)) { bOk = false; break; }
            *Arr->ContainerPtrToValuePtr<TArray<AActor*>>(Params) = Speakers;
        }
        else if (FNameProperty* NameProp = CastField<FNameProperty>(*It)) NameProp->SetPropertyValue_InContainer(Params, Arg);
        else { bOk = false; break; }
    }
    bool bResult = false;
    if (bOk)
    {
        Sub->ProcessEvent(Fn, Params);
        bResult = !Ret || Ret->GetPropertyValue_InContainer(Params);
    }
    for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It) It->DestroyValue_InContainer(Params);
    return bOk && bResult;
}

bool UReflectionsLivesSubsystem::TryStoryConversation(FLife& A, FLife& B)
{
    // Only clique-mates with their own roster voices have story conversations.
    if (A.Person.Clique.IsNone() || A.Person.Clique != B.Person.Clique || A.Person.VoiceId.IsNone() || B.Person.VoiceId.IsNone()) return false;
    if (!bTriedStoryConversations)
    {
        bTriedStoryConversations = true;
        if (FPackageName::DoesPackageExist(TEXT("/Game/Audio/Jam/Voice/Ambient/DT_StoryConversations")))
            StoryConversations = LoadObject<UDataTable>(nullptr, TEXT("/Game/Audio/Jam/Voice/Ambient/DT_StoryConversations.DT_StoryConversations"));
    }
    const UDataTable* Table = StoryConversations;
    const UScriptStruct* RowStruct = Table ? Table->GetRowStruct() : nullptr;
    if (!RowStruct || !RowStruct->IsChildOf(FReflectionsAmbientConversationRow::StaticStruct())) return false;
    const FString Band = CurrentBand().ToString().ToLower();
    const FString Clique = A.Person.Clique.ToString();
    auto TextField = [RowStruct](const uint8* Row, const TCHAR* Name) -> FString
    {
        if (const FProperty* Prop = RowStruct->FindPropertyByName(Name))
        {
            if (const FNameProperty* N = CastField<FNameProperty>(Prop)) return N->GetPropertyValue_InContainer(Row).ToString();
            if (const FStrProperty* S = CastField<FStrProperty>(Prop)) return S->GetPropertyValue_InContainer(Row);
        }
        return FString();
    };
    static const TCHAR* Bands[] = { TEXT("quiet"), TEXT("spreading"), TEXT("rising"), TEXT("brink") };
    const FReflectionsAmbientConversationRow* Pick = nullptr;
    for (const auto& Pair : Table->GetRowMap())
    {
        const uint8* RowData = Pair.Value;
        const FReflectionsAmbientConversationRow* Row = reinterpret_cast<const FReflectionsAmbientConversationRow*>(RowData);
        if (!Row || Row->Speakers.Num() != 2 || !Row->CliqueId.ToString().Equals(Clique, ESearchCase::IgnoreCase)) continue;
        if (!((Row->Speakers[0] == A.Person.VoiceId && Row->Speakers[1] == B.Person.VoiceId) || (Row->Speakers[0] == B.Person.VoiceId && Row->Speakers[1] == A.Person.VoiceId))) continue;
        const FName ConvId = Row->ConvId.IsNone() ? Pair.Key : Row->ConvId;
        if (A.PlayedConversations.Contains(ConvId) || B.PlayedConversations.Contains(ConvId)) continue;
        // The street's band and story flags the row needs (columns once audio fills them; until then, the id's words).
        FString RowBand = TextField(RowData, TEXT("Band")).ToLower();
        const FString Id = ConvId.ToString().ToLower();
        if (RowBand.IsEmpty())
            for (const TCHAR* B_ : Bands)
                if (Id.Contains(FString(TEXT("_")) + B_)) RowBand = B_;
        if (!RowBand.IsEmpty() && RowBand != Band && !(Band.IsEmpty() && RowBand == TEXT("quiet"))) continue;
        const FString Flag = TextField(RowData, TEXT("RequiredFlag"));
        if (!Flag.IsEmpty() && Flag != TEXT("None") && !HasStoryFlag(FName(*Flag))) continue;
        Pick = Row;
        // A row made for this band (or flag) beats a generic one.
        if (!RowBand.IsEmpty() || !Flag.IsEmpty()) break;
    }
    if (!Pick) return false;
    const FName ConvId = Pick->ConvId;
    TArray<AActor*> Speakers;
    Speakers.Add(Pick->Speakers[0] == A.Person.VoiceId ? A.Actor.Get() : B.Actor.Get());
    Speakers.Add(Pick->Speakers[0] == A.Person.VoiceId ? B.Actor.Get() : A.Actor.Get());
    if (!CallDirectorConversation(TEXT("PlayConversationById"), Speakers, ConvId)) return false;
    A.PlayedConversations.Add(ConvId);
    B.PlayedConversations.Add(ConvId);
    UE_LOG(LogReflectionsLives, Log, TEXT("%s and %s: story conversation %s"), *A.Person.Name, *B.Person.Name, *ConvId.ToString());
    return true;
}

bool UReflectionsLivesSubsystem::CallDirector(const TCHAR* Function, AActor* Actor, bool& bOutResult) const
{
    FString ClassPath, Unused;
    if (!CVarLivesChatDirector.GetValueOnGameThread().Split(TEXT(":"), &ClassPath, &Unused)) return false;
    UClass* Class = FindObject<UClass>(nullptr, *ClassPath);
    UWorldSubsystem* Sub = Class && Class->IsChildOf(UWorldSubsystem::StaticClass()) ? GetWorld()->GetSubsystemBase(Class) : nullptr;
    UFunction* Fn = Sub ? Sub->FindFunction(Function) : nullptr;
    if (!Fn) return false;
    uint8* Params = static_cast<uint8*>(FMemory_Alloca(FMath::Max<int32>(1, Fn->ParmsSize)));
    FMemory::Memzero(Params, Fn->ParmsSize);
    Fn->InitializeStruct(Params);
    bool bOk = true;
    FBoolProperty* Ret = nullptr;
    for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
    {
        if (It->HasAnyPropertyFlags(CPF_ReturnParm)) Ret = CastField<FBoolProperty>(*It);
        else if (FObjectPropertyBase* Obj = CastField<FObjectPropertyBase>(*It)) Obj->SetObjectPropertyValue_InContainer(Params, Actor);
        else bOk = false;
    }
    if (bOk) Sub->ProcessEvent(Fn, Params);
    bOutResult = bOk && Ret && Ret->GetPropertyValue_InContainer(Params);
    Fn->DestroyStruct(Params);
    return bOk;
}

bool UReflectionsLivesSubsystem::PlayChatLine(FLife& Speaker, FLife& Listener)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    AActor* Actor = Speaker.Actor.Get();
    if (!Npcs || !Actor) return false;
    // Line groups by temperament; audio's roster decides which of the person's own lines plays.
    static const FName Groups[] = { TEXT("Remark"), TEXT("Talk"), TEXT("Chat") };
    const FName Group = Groups[(Speaker.Seed + static_cast<uint32>(Listener.ChatLines)) % 3u];
    if (!Npcs->FindVoiceCue(Actor, Group)) return false;
    Npcs->PlayBark(Actor, Group);
    return true;
}

void UReflectionsLivesSubsystem::EndChat(FLife& Life)
{
    if (Life.ChatWith == NAME_None) return;
    const FName Other = Life.ChatWith;
    if (Life.bDirectorChat)
    {
        // Our end of the talk (a new step, a reaction): stop the baked conversation too.
        bool bIgnored = false;
        CallDirector(TEXT("StopConversation"), Life.Actor.Get(), bIgnored);
        Life.bDirectorChat = false;
    }
    Life.ChatWith = NAME_None;
    Life.ChatRemaining = 0.0f;
    if (Life.Move == EMove::Chat || Life.Move == EMove::Meet)
    {
        Life.Move = EMove::Mill;
        Life.Path.Reset();
        Life.PathIndex = 0;
        Life.Idle = 1.5f;
    }
    if (FLife* O = FindLife(Other))
        if (O->ChatWith == Life.Person.Id) EndChat(*O);
}

void UReflectionsLivesSubsystem::TryGreet(FLife& Life, double Now, const FVector& PlayerLocation)
{
    AActor* Actor = Life.Actor.Get();
    if (!Actor || Now < Life.NextGreetTime || Life.Move == EMove::Chat || Life.bInside) return;
    if (FVector::DistSquared2D(Actor->GetActorLocation(), PlayerLocation) > FMath::Square(GreetRadius)) return;
    Life.NextGreetTime = Now + 75.0 + (Life.Seed % 30u);
    const FName Group = GetGreetingGroup(Actor);
    if (Group.IsNone()) return;
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
        if (Npcs->FindVoiceCue(Actor, Group)) Npcs->PlayBark(Actor, Group);
}

// ---- Witnessing and memory -----------------------------------------------------------------------------------

bool UReflectionsLivesSubsystem::IsPlayer(const AActor* Actor)
{
    const APawn* Pawn = Cast<APawn>(Actor);
    if (!Pawn && Actor) Pawn = Cast<APawn>(Actor->GetInstigator());
    return Pawn && Pawn->IsPlayerControlled();
}

void UReflectionsLivesSubsystem::HandleNpcHit(AActor* Npc, const FReflectionsSpellHitData& Hit)
{
    Witness(Npc, Hit.Spell == EHeroSpell::Healing ? EWitnessed::Healed : EWitnessed::Hurt, Hit.Caster, Hit.Location);
}

void UReflectionsLivesSubsystem::HandleNpcDied(AActor* Npc, AActor* Killer)
{
    Witness(Npc, EWitnessed::Killed, Killer, Npc ? Npc->GetActorLocation() : FVector::ZeroVector);
}

void UReflectionsLivesSubsystem::HandleNpcInfection(AActor* Npc, EReflectionsNpcInfection State, AActor* Source)
{
    const FLife* Life = FindLifeByActor(Npc);
    const FReflectionsPersonState* PS = (Life && Memory.IsValid()) ? Memory->Find(Life->Person.Id) : nullptr;
    if (State == EReflectionsNpcInfection::Infected || State == EReflectionsNpcInfection::VillainHost)
        Witness(Npc, EWitnessed::Taken, Source, Npc ? Npc->GetActorLocation() : FVector::ZeroVector);
    else if (PS && PS->bTarnished)
        Witness(Npc, EWitnessed::Saved, Source, Npc ? Npc->GetActorLocation() : FVector::ZeroVector);
}

void UReflectionsLivesSubsystem::HandleSpellEvent(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity)
{
    if (!IsPlayer(Caster) || Spell == EHeroSpell::Healing) return;
    for (auto& Pair : Lives)
    {
        FLife& Life = Pair.Value;
        AActor* Actor = Life.Actor.Get();
        if (!Actor || LocalHours - Life.LastCastNearHours < 0.5) continue;
        if (FVector::DistSquared(Actor->GetActorLocation(), Location) > FMath::Square(800.0f)) continue;
        Life.LastCastNearHours = LocalHours;
        RememberPlayerById(Life.Person.Id, EReflectionsPlayerDeed::CastNear, 1.0f, TEXT("cast spells right next to me"));
    }
}

void UReflectionsLivesSubsystem::Witness(AActor* Victim, EWitnessed What, AActor* Instigator, const FVector& Where)
{
    if (!Victim || !bStarted) return;
    UReflectionsLivesMemory* Mem = Memory.Get();
    FLife* VictimLife = FindLifeByActor(Victim);
    const bool bPlayer = IsPlayer(Instigator);
    const FString VictimName = VictimLife ? VictimLife->Person.Name : FString(TEXT("a stranger"));

    // The victim's own memory.
    if (VictimLife && Mem)
    {
        FReflectionsPersonState& VS = Mem->FindOrAdd(VictimLife->Person.Id);
        switch (What)
        {
        case EWitnessed::Hurt: if (bPlayer) RememberPlayerById(VictimLife->Person.Id, EReflectionsPlayerDeed::Hurt, 1.0f, TEXT("hit me with a spell")); break;
        case EWitnessed::Healed: if (bPlayer) RememberPlayerById(VictimLife->Person.Id, EReflectionsPlayerDeed::Helped, 1.0f, TEXT("healed me")); break;
        case EWitnessed::Killed:
            VS.bDead = true;
            if (bPlayer)
            {
                VS.bKilledByPlayer = true;
                AddEvent(VS, TEXT("was killed by the Silverer"));
            }
            break;
        case EWitnessed::Taken: VS.bTarnished = true; AddEvent(VS, TEXT("was taken by the Tarnish")); break;
        case EWitnessed::Saved:
            VS.bTarnished = false;
            AddEvent(VS, TEXT("was freed from the Tarnish"));
            if (bPlayer) RememberPlayerById(VictimLife->Person.Id, EReflectionsPlayerDeed::Helped, 2.0f, TEXT("freed me from the Tarnish"));
            break;
        }
    }

    const float Radius = CVarLivesWitnessRadius.GetValueOnGameThread();
    const bool bBig = What == EWitnessed::Killed || What == EWitnessed::Taken || What == EWitnessed::Saved;
    for (auto& Pair : Lives)
    {
        FLife& W = Pair.Value;
        if (&W == VictimLife) continue;
        if (const FReflectionsPersonState* WS = Mem ? Mem->Find(W.Person.Id) : nullptr)
            if (WS->bDead || WS->bTarnished) continue;
        const FString Relation = VictimLife ? RelationTo(W, VictimLife->Person.Id) : FString();
        AActor* WActor = W.Actor.Get();
        bool bSaw = false;
        if (WActor && (!W.Brain.IsValid() || !W.Brain->IsIncapacitated()) && !W.bInside)
        {
            const float Dist = FVector::Dist(WActor->GetActorLocation(), Where);
            bSaw = Dist < Radius && (Dist < 800.0f || UReflectionsNpcReactionComponent::HasLineOfSight(WActor, Victim, DriverOf(W)));
            // Strangers only take in the small things (a hit, a heal) when close.
            if (bSaw && Relation.IsEmpty() && !bBig && Dist > 1200.0f) bSaw = false;
        }
        if (!bSaw && (Relation.IsEmpty() || !bBig)) continue;
        ReactTo(W, VictimLife, VictimName, What, bPlayer, Where, bSaw, Relation);
    }
}

void UReflectionsLivesSubsystem::ReactTo(FLife& W, const FLife* VictimLife, const FString& VictimName, EWitnessed What, bool bPlayerDidIt,
    const FVector& Where, bool bSaw, const FString& Relation)
{
    UReflectionsLivesMemory* Mem = Memory.Get();
    if (!Mem) return;
    FReflectionsPersonState& S = Mem->FindOrAdd(W.Person.Id);
    const FReflectionsPersonality& P = W.Person.Personality;
    const bool bKnown = !Relation.IsEmpty() && Relation != TEXT("rival");
    const FString Who = bKnown ? FString::Printf(TEXT("%s (%s)"), *VictimName, *Relation) : VictimName;
    const FName VictimId = VictimLife ? VictimLife->Person.Id : NAME_None;
    FString Text;
    FName Bark = NAME_None;
    auto Avoid = [&](float Hours)
    {
        S.AvoidLocation = Where;
        S.AvoidUntilHours = FMath::Max(S.AvoidUntilHours, LocalHours + Hours);
        if (bSaw) W.AvoidStepUntilHours = LocalHours + 0.75;
    };
    switch (What)
    {
    case EWitnessed::Killed:
        Text = bSaw ? FString::Printf(TEXT("saw %s killed%s"), *Who, bPlayerDidIt ? TEXT(" by the Silverer") : TEXT(""))
                    : FString::Printf(TEXT("heard %s was killed"), *Who);
        if (bKnown)
        {
            // Family mourn a full day or more, friends half a day; a death at the player's hand cuts deeper.
            const bool bFamily = Relation != TEXT("friend") && Relation != TEXT("one of their crowd");
            const float Hours = (bFamily ? 16.0f : 8.0f) * (bPlayerDidIt ? 1.5f : 1.0f);
            // Grief first (vigil included); a hot-tempered, brave one turns it on the killer.
            SetMood(W.Person.Id, (P.Temper > 0.6f && P.Courage > 0.5f && bPlayerDidIt) ? EReflectionsLifeMood::Angry : EReflectionsLifeMood::Grieving, Hours, VictimId);
            S.ConcernFor = VictimId;
            if (!VictimId.IsNone()) S.Mourns.AddUnique(VictimId);
            Avoid(14.0f);
            if (bPlayerDidIt) RememberPlayerById(W.Person.Id, EReflectionsPlayerDeed::KilledFriend, bFamily ? 1.5f : 1.0f, FString::Printf(TEXT("killed %s"), *VictimName));
            Bark = TEXT("Grief");
        }
        else
        {
            SetMood(W.Person.Id, EReflectionsLifeMood::Afraid, 1.0f + (1.0f - P.Courage) * 3.0f, NAME_None);
            Avoid(6.0f);
            if (bPlayerDidIt) RememberPlayerById(W.Person.Id, EReflectionsPlayerDeed::HurtFriend, 0.5f, TEXT("killed someone in front of me"));
        }
        break;
    case EWitnessed::Taken:
        Text = bSaw ? FString::Printf(TEXT("saw %s taken by the Tarnish"), *Who) : FString::Printf(TEXT("heard %s was taken by the Tarnish"), *Who);
        if (bKnown)
        {
            SetMood(W.Person.Id, P.Courage >= 0.6f ? EReflectionsLifeMood::Angry : EReflectionsLifeMood::Grieving, 8.0f, VictimId);
            Avoid(10.0f);
            Bark = TEXT("Grief");
        }
        else
        {
            SetMood(W.Person.Id, EReflectionsLifeMood::Afraid, 1.5f + (1.0f - P.Courage) * 2.5f, NAME_None);
            Avoid(6.0f);
        }
        break;
    case EWitnessed::Hurt:
        Text = FString::Printf(TEXT("saw %s hurt%s"), *Who, bPlayerDidIt ? TEXT(" by the Silverer") : TEXT(""));
        if (bKnown && bPlayerDidIt)
        {
            RememberPlayerById(W.Person.Id, EReflectionsPlayerDeed::HurtFriend, 1.0f, FString::Printf(TEXT("hurt %s"), *VictimName));
            SetMood(W.Person.Id, P.Temper > 0.5f ? EReflectionsLifeMood::Angry : EReflectionsLifeMood::Wary, 2.0f, VictimId);
        }
        else if (bKnown) SetMood(W.Person.Id, EReflectionsLifeMood::Wary, 1.5f, VictimId);
        else if (bPlayerDidIt) RememberPlayerById(W.Person.Id, EReflectionsPlayerDeed::CastNear, 1.0f, TEXT("hurt a stranger in front of me"));
        break;
    case EWitnessed::Healed:
        if (!bPlayerDidIt) return;
        Text = FString::Printf(TEXT("saw the Silverer heal %s"), *Who);
        if (bKnown) RememberPlayerById(W.Person.Id, EReflectionsPlayerDeed::SavedFriend, 0.5f, FString::Printf(TEXT("healed %s"), *VictimName));
        else RememberPlayerById(W.Person.Id, EReflectionsPlayerDeed::Helped, 0.25f, TEXT("healed a stranger"));
        break;
    case EWitnessed::Saved:
        Text = FString::Printf(TEXT("%s %s freed from the Tarnish"), bSaw ? TEXT("saw") : TEXT("heard"), *Who);
        if (bKnown)
        {
            if (S.ConcernFor == VictimId) S.MoodUntilHours = LocalHours;  // grief lifts
            SetMood(W.Person.Id, EReflectionsLifeMood::Cheerful, 4.0f, VictimId);
            if (bPlayerDidIt) RememberPlayerById(W.Person.Id, EReflectionsPlayerDeed::SavedFriend, 1.5f, FString::Printf(TEXT("freed %s from the Tarnish"), *VictimName));
        }
        break;
    }
    AddEvent(S, Text);
    W.LastReactionText = Text;
    W.LastReactionTime = GetWorld()->GetTimeSeconds();
    W.StepIndex = INDEX_NONE;  // re-plan the day now
    W.NextThink = 0.0f;
    if (!Bark.IsNone() && bSaw && W.Actor.IsValid())
        if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
            if (Npcs->FindVoiceCue(W.Actor.Get(), Bark)) Npcs->PlayBark(W.Actor.Get(), Bark);
    UE_LOG(LogReflectionsLives, Log, TEXT("%s %s"), *W.Person.Name, *Text);
    OnLifeEvent.Broadcast(W.Person.Id, W.Actor.Get(), Text);
}

void UReflectionsLivesSubsystem::AddEvent(FReflectionsPersonState& State, const FString& Text)
{
    if (Text.IsEmpty()) return;
    State.Events.Add(FString::Printf(TEXT("day %d %s: %s"), GetDay(), *GetClockText(), *Text));
    while (State.Events.Num() > 5) State.Events.RemoveAt(0);
}

void UReflectionsLivesSubsystem::SetMood(FName PersonId, EReflectionsLifeMood Mood, float Hours, FName ConcernFor)
{
    UReflectionsLivesMemory* Mem = Memory.Get();
    if (!Mem) return;
    FReflectionsPersonState& S = Mem->FindOrAdd(PersonId);
    // A stronger feeling replaces a weaker one; the same feeling lasts longer.
    auto Weight = [](EReflectionsLifeMood M)
    {
        switch (M)
        {
        case EReflectionsLifeMood::Grieving: return 5;
        case EReflectionsLifeMood::Angry: return 4;
        case EReflectionsLifeMood::Afraid: return 3;
        case EReflectionsLifeMood::Wary: return 2;
        case EReflectionsLifeMood::Cheerful: return 1;
        default: return 0;
        }
    };
    const bool bActive = S.MoodUntilHours > LocalHours;
    if (bActive && Weight(S.Mood) > Weight(Mood) && Mood != EReflectionsLifeMood::Cheerful) return;
    S.Mood = Mood;
    S.MoodUntilHours = FMath::Max(bActive && S.Mood == Mood ? S.MoodUntilHours : 0.0, LocalHours + Hours);
    if (!ConcernFor.IsNone()) S.ConcernFor = ConcernFor;
}

void UReflectionsLivesSubsystem::RefreshMood(FReflectionsPersonState& State) const
{
    if (State.Mood != EReflectionsLifeMood::Content && State.MoodUntilHours <= LocalHours)
    {
        State.Mood = EReflectionsLifeMood::Content;
        State.ConcernFor = NAME_None;
    }
}

void UReflectionsLivesSubsystem::RememberPlayer(AActor* Actor, EReflectionsPlayerDeed Deed, float Weight)
{
    if (const FLife* Life = FindLifeByActor(Actor)) RememberPlayerById(Life->Person.Id, Deed, Weight);
}

void UReflectionsLivesSubsystem::RememberPlayerById(FName PersonId, EReflectionsPlayerDeed Deed, float Weight, const FString& Note)
{
    UReflectionsLivesMemory* Mem = Memory.Get();
    if (!Mem || PersonId.IsNone()) return;
    FReflectionsPersonState& S = Mem->FindOrAdd(PersonId);
    FReflectionsPlayerMemory& M = S.Player;
    const FLife* Life = FindLife(PersonId);
    const FReflectionsPersonality P = Life ? Life->Person.Personality : FReflectionsPersonality();
    float Delta = 0.0f;
    switch (Deed)
    {
    case EReflectionsPlayerDeed::Helped: ++M.Helped; Delta = 0.15f * (0.6f + P.Warmth); break;
    case EReflectionsPlayerDeed::Hurt: ++M.Hurt; Delta = -0.25f * (0.6f + P.Temper); break;
    case EReflectionsPlayerDeed::CastNear: ++M.CastNear; Delta = -0.03f * (1.2f - P.Courage); break;
    case EReflectionsPlayerDeed::SavedFriend: ++M.SavedFriend; Delta = 0.3f * (0.6f + P.Warmth); break;
    case EReflectionsPlayerDeed::HurtFriend: ++M.HurtFriend; Delta = -0.2f * (0.6f + P.Temper); break;
    case EReflectionsPlayerDeed::KilledFriend: ++M.KilledFriend; Delta = -0.6f * (0.6f + P.Temper); break;
    case EReflectionsPlayerDeed::CompletedQuest: ++M.QuestsDone; Delta = 0.35f; break;
    case EReflectionsPlayerDeed::Talked: ++M.Talks; Delta = M.Talks <= 10 ? 0.02f * (0.5f + P.Warmth) : 0.0f; break;
    case EReflectionsPlayerDeed::WitnessedCrime: ++M.Crimes; Delta = -0.3f * (0.6f + P.Temper * 0.6f); break;
    }
    M.Opinion = FMath::Clamp(M.Opinion + Delta * Weight, -1.0f, 1.0f);
    if (Deed != EReflectionsPlayerDeed::Talked || !M.bHasLastDeed)
    {
        M.LastDeed = Deed;
        M.bHasLastDeed = true;
        M.LastDeedHours = LocalHours;
        M.LastDeedNote = Note.IsEmpty() ? DeedText(Deed) : Note;
    }
}

FReflectionsPlayerMemory UReflectionsLivesSubsystem::GetPlayerMemory(FName PersonId) const
{
    const FReflectionsPersonState* S = Memory.IsValid() ? Memory->Find(PersonId) : nullptr;
    return S ? S->Player : FReflectionsPlayerMemory();
}

EReflectionsLifeMood UReflectionsLivesSubsystem::GetMood(FName PersonId) const
{
    const FReflectionsPersonState* S = Memory.IsValid() ? Memory->Find(PersonId) : nullptr;
    return S && S->MoodUntilHours > LocalHours ? S->Mood : EReflectionsLifeMood::Content;
}

bool UReflectionsLivesSubsystem::IsQuestAvailable(FName PersonId) const
{
    const FReflectionsPersonState* S = Memory.IsValid() ? Memory->Find(PersonId) : nullptr;
    if (!S) return true;
    if (S->bDead || S->bTarnished || S->Player.Opinion < -0.3f) return false;
    const EReflectionsLifeMood Mood = GetMood(PersonId);
    return Mood != EReflectionsLifeMood::Grieving && Mood != EReflectionsLifeMood::Afraid;
}

void UReflectionsLivesSubsystem::CompleteQuestFor(FName PersonId)
{
    RememberPlayerById(PersonId, EReflectionsPlayerDeed::CompletedQuest, 1.0f, TEXT("did what I asked"));
    if (UReflectionsLivesMemory* Mem = Memory.Get()) AddEvent(Mem->FindOrAdd(PersonId), TEXT("the Silverer did what I asked"));
}

// ---- Identity and persona --------------------------------------------------------------------------------------

FName UReflectionsLivesSubsystem::GetPersonId(const AActor* Actor) const
{
    const FLife* Life = FindLifeByActor(Actor);
    return Life ? Life->Person.Id : NAME_None;
}

AActor* UReflectionsLivesSubsystem::FindActorForPerson(FName PersonId) const
{
    const FLife* Life = FindLife(PersonId);
    return Life ? Life->Actor.Get() : nullptr;
}

FString UReflectionsLivesSubsystem::GetPersonName(FName PersonId) const
{
    if (const FLife* Life = FindLife(PersonId)) return Life->Person.Name;
    if (const FReflectionsPerson* P = Book.FindNamed(PersonId)) return P->Name;
    return FString();
}

bool UReflectionsLivesSubsystem::FindPerson(FName PersonId, FReflectionsPerson& OutPerson) const
{
    if (const FLife* Life = FindLife(PersonId)) { OutPerson = Life->Person; return true; }
    if (const FReflectionsPerson* P = Book.FindNamed(PersonId)) { OutPerson = *P; return true; }
    return false;
}

FString UReflectionsLivesSubsystem::DeedText(EReflectionsPlayerDeed Deed)
{
    switch (Deed)
    {
    case EReflectionsPlayerDeed::Helped: return TEXT("helped me");
    case EReflectionsPlayerDeed::Hurt: return TEXT("hurt me");
    case EReflectionsPlayerDeed::CastNear: return TEXT("cast spells near me");
    case EReflectionsPlayerDeed::SavedFriend: return TEXT("saved someone I love");
    case EReflectionsPlayerDeed::HurtFriend: return TEXT("hurt someone I love");
    case EReflectionsPlayerDeed::KilledFriend: return TEXT("killed someone I love");
    case EReflectionsPlayerDeed::CompletedQuest: return TEXT("did what I asked");
    case EReflectionsPlayerDeed::Talked: return TEXT("talked with me");
    case EReflectionsPlayerDeed::WitnessedCrime: return TEXT("committed a crime in front of me");
    }
    return FString();
}

FString UReflectionsLivesSubsystem::MoodText(EReflectionsLifeMood Mood)
{
    switch (Mood)
    {
    case EReflectionsLifeMood::Cheerful: return TEXT("cheerful");
    case EReflectionsLifeMood::Wary: return TEXT("wary");
    case EReflectionsLifeMood::Afraid: return TEXT("afraid");
    case EReflectionsLifeMood::Grieving: return TEXT("grieving");
    case EReflectionsLifeMood::Angry: return TEXT("angry");
    default: return TEXT("content");
    }
}

FString UReflectionsLivesSubsystem::ActivityText(EReflectionsLifeActivity Activity)
{
    switch (Activity)
    {
    case EReflectionsLifeActivity::Wake: return TEXT("Waking");
    case EReflectionsLifeActivity::Work: return TEXT("Working");
    case EReflectionsLifeActivity::Eat: return TEXT("Eating");
    case EReflectionsLifeActivity::Errand: return TEXT("Errand");
    case EReflectionsLifeActivity::Haunt: return TEXT("Passing time");
    case EReflectionsLifeActivity::Social: return TEXT("Seeing friends");
    case EReflectionsLifeActivity::Worship: return TEXT("Worship");
    case EReflectionsLifeActivity::Home: return TEXT("Home");
    case EReflectionsLifeActivity::Sleep: return TEXT("Sleeping");
    case EReflectionsLifeActivity::Patrol: return TEXT("Patrol");
    case EReflectionsLifeActivity::Chat: return TEXT("Chatting");
    case EReflectionsLifeActivity::Grieve: return TEXT("Grieving");
    case EReflectionsLifeActivity::Avoid: return TEXT("Getting away");
    case EReflectionsLifeActivity::Inside: return TEXT("Inside");
    case EReflectionsLifeActivity::Guard: return TEXT("On watch");
    case EReflectionsLifeActivity::Hide: return TEXT("Hiding");
    case EReflectionsLifeActivity::Stroll: return TEXT("Strolling");
    case EReflectionsLifeActivity::Shop: return TEXT("Shopping");
    case EReflectionsLifeActivity::Vigil: return TEXT("Keeping vigil");
    case EReflectionsLifeActivity::Shun: return TEXT("Keeping away from the Silverer");
    default: return TEXT("Idle");
    }
}

FString UReflectionsLivesSubsystem::PlayerMemoryText(const FLife& Life) const
{
    const FReflectionsPlayerMemory M = GetPlayerMemory(Life.Person.Id);
    TArray<FString> Parts;
    auto Times = [](int32 N) { return N == 1 ? FString(TEXT("once")) : N == 2 ? FString(TEXT("twice")) : FString::Printf(TEXT("%d times"), N); };
    if (M.KilledFriend) Parts.Add(TEXT("they killed someone you love"));
    if (M.HurtFriend) Parts.Add(TEXT("they hurt someone you love"));
    if (M.Hurt) Parts.Add(TEXT("they hurt you with a spell ") + Times(M.Hurt));
    if (M.SavedFriend) Parts.Add(TEXT("they saved someone you love"));
    if (M.Helped) Parts.Add(TEXT("they healed or helped you ") + Times(M.Helped));
    if (M.QuestsDone) Parts.Add(TEXT("they did you a favour"));
    if (M.Crimes) Parts.Add(TEXT("you saw them commit a crime ") + Times(M.Crimes));
    if (M.CastNear >= 2) Parts.Add(TEXT("they throw spells around near you"));
    if (M.Talks) Parts.Add(TEXT("you have talked ") + Times(M.Talks));
    const int32 Strong = GetPlayerFeeling(Life.Person.Id);
    FString Feeling = M.Opinion > 0.5f ? TEXT("You trust them.") : M.Opinion > 0.15f ? TEXT("You like them.")
        : Strong == 2 ? TEXT("You hate them and want them gone; you don't hide it.")
        : Strong == 1 ? TEXT("You are afraid of them and want to get away.")
        : M.Opinion < -0.15f ? TEXT("You don't trust them.") : TEXT("You don't know what to make of them.");
    // The dead they loved who died at the Silverer's hand stay with them after the first grief.
    if (const FReflectionsPersonState* S = Memory.IsValid() ? Memory->Find(Life.Person.Id) : nullptr)
    {
        TArray<FString> Lost;
        for (const FName Id : S->Mourns)
            if (const FReflectionsPersonState* D = Memory->Find(Id))
                if (D->bKilledByPlayer) Lost.Add(GetPersonName(Id));
        if (Lost.Num()) Feeling += FString::Printf(TEXT(" They killed %s; you will never forgive it."), *Joined(Lost));
    }
    const FString& Player = Book.GetPlayerName();
    FString Start;
    if (!Life.Person.Stance.IsEmpty()) Start = FString::Printf(TEXT(" Your view of them to begin with: %s."), *Life.Person.Stance);
    if (Parts.Num() == 0) return FString::Printf(TEXT("About %s: you have not dealt with them yet. %s%s"), *Player, *Feeling, *Start);
    FString Out = FString::Printf(TEXT("About %s: "), *Player) + Joined(Parts, TEXT("; ")) + TEXT(". ") + Feeling + Start;
    if (!M.LastDeedNote.IsEmpty()) Out += FString::Printf(TEXT(" Last time they %s."), *M.LastDeedNote);
    return Out;
}

FReflectionsPersonaFacts UReflectionsLivesSubsystem::GetPersonaFacts(const AActor* Actor) const
{
    FReflectionsPersonaFacts F;
    const FLife* Life = FindLifeByActor(Actor);
    if (!Life) return F;
    const FReflectionsPerson& P = Life->Person;
    F.bValid = true;
    F.PersonId = P.Id;
    F.Name = P.Name;
    F.JobTitle = P.JobTitle;
    F.Age = P.Age.ToString();
    F.Side = P.Side.ToString();
    F.Traits = P.Personality.Traits;
    F.Summary = P.Summary;
    F.SpeechStyle = P.SpeechStyle;
    F.Quirk = P.Quirk;
    F.Likes = P.Likes;
    F.Dislikes = P.Dislikes;
    F.Fear = P.Fear;
    F.Want = P.Want;
    F.Knows = P.Knows;
    if (F.Knows.Num() > 4) F.Knows.SetNum(4);
    F.Tics = P.Tics;
    F.FavouriteWords = P.FavouriteWords;
    F.Stance = P.Stance;
    F.StanceLine = P.StanceLine;
    F.NeverSays = P.NeverSays;
    F.InfectionBand = CurrentBand().ToString();
    for (const FReflectionsKin& Kin : P.Family)
    {
        const FString Name = GetPersonName(Kin.Id);
        if (!Name.IsEmpty()) F.People.Add(FString::Printf(TEXT("%s (%s)"), *Name, *Kin.Relation));
    }
    for (const FName Friend : P.Friends)
    {
        const FString Name = GetPersonName(Friend);
        if (!Name.IsEmpty()) F.People.Add(FString::Printf(TEXT("%s (friend)"), *Name));
    }
    for (const FName Rival : P.Rivals)
    {
        const FString Name = GetPersonName(Rival);
        if (!Name.IsEmpty()) F.People.Add(FString::Printf(TEXT("%s (you can't stand them)"), *Name));
    }
    FString Activity = ActivityText(Life->Activity).ToLower();
    if (Life->ChatWith != NAME_None) Activity = FString::Printf(TEXT("chatting with %s"), *GetPersonName(Life->ChatWith));
    F.Activity = Life->Activity == EReflectionsLifeActivity::Avoid ? FString(TEXT("getting away from where it happened"))
        : Life->Activity == EReflectionsLifeActivity::Shun ? FString(TEXT("keeping out of the Silverer's way"))
        : FString::Printf(TEXT("%s at %s"), *Activity, *PrettyPlace(Life->PlaceTag));
    const EReflectionsLifeMood Mood = GetMood(P.Id);
    F.Mood = MoodText(Mood);
    if (const FReflectionsPersonState* S = Memory.IsValid() ? Memory->Find(P.Id) : nullptr)
    {
        if (Mood != EReflectionsLifeMood::Content && !S->ConcernFor.IsNone())
            F.Mood += FString::Printf(TEXT(" (because of %s)"), *GetPersonName(S->ConcernFor));
        F.RecentEvents = S->Events;
        F.Opinion = S->Player.Opinion;
    }
    F.PlayerMemory = PlayerMemoryText(*Life);
    F.TimeOfDay = GetClockText();
    return F;
}

FString UReflectionsLivesSubsystem::GetPersonaText(const AActor* Actor) const
{
    const FReflectionsPersonaFacts F = GetPersonaFacts(Actor);
    if (!F.bValid) return FString();
    TArray<FString> Lines;
    Lines.Add(FString::Printf(TEXT("You are %s, %s %s from %s."), *F.Name, F.Age == TEXT("Old") ? TEXT("an old") : F.Age == TEXT("Young") ? TEXT("a young") : TEXT("a"),
        *F.JobTitle.ToLower(), *F.Side));
    if (F.Traits.Num()) Lines.Add(TEXT("Personality: ") + Joined(F.Traits) + TEXT("."));
    if (!F.Summary.IsEmpty()) Lines.Add(F.Summary);
    if (!F.SpeechStyle.IsEmpty()) Lines.Add(TEXT("How you talk: ") + F.SpeechStyle);
    if (F.Tics.Num()) Lines.Add(TEXT("Your habits: ") + Joined(F.Tics, TEXT("; ")) + TEXT("."));
    else if (!F.Quirk.IsEmpty()) Lines.Add(TEXT("Habit: you ") + F.Quirk + TEXT("."));
    if (F.FavouriteWords.Num()) Lines.Add(TEXT("Words you like to use: ") + Joined(F.FavouriteWords) + TEXT("."));
    if (!F.StanceLine.IsEmpty()) Lines.Add(FString::Printf(TEXT("How you sound (a sample, never repeat it word for word): \"%s\""), *F.StanceLine));
    TArray<FString> Taste;
    if (F.Likes.Num()) Taste.Add(TEXT("you like ") + Joined(F.Likes));
    if (F.Dislikes.Num()) Taste.Add(TEXT("you dislike ") + Joined(F.Dislikes));
    if (!F.Fear.IsEmpty())
    {
        FString Fear = F.Fear.TrimStartAndEnd();
        Fear.RemoveFromEnd(TEXT("."));
        if (Fear.Len() > 1 && FChar::IsUpper(Fear[0]) && !FChar::IsUpper(Fear[1])) Fear[0] = FChar::ToLower(Fear[0]);
        Taste.Add(TEXT("what you fear: ") + Fear);
    }
    if (Taste.Num()) Lines.Add(Joined(Taste, TEXT("; ")) + TEXT("."));
    if (!F.Want.IsEmpty()) Lines.Add(TEXT("What you want: ") + F.Want);
    if (F.People.Num()) Lines.Add(TEXT("People in your life: ") + Joined(F.People) + TEXT("."));
    if (F.Knows.Num()) Lines.Add(TEXT("Things you know and share freely: ") + Joined(F.Knows, TEXT(" ")));
    if (F.NeverSays.Num()) Lines.Add(TEXT("Never say: ") + Joined(F.NeverSays, TEXT("; ")) + TEXT("."));
    for (const FReflectionsInfectionBand& B : Book.GetInfectionBands())
        if (B.Band.ToString() == F.InfectionBand && !B.StreetMood.IsEmpty()) Lines.Add(TEXT("The street right now: ") + B.StreetMood);
    Lines.Add(FString::Printf(TEXT("It is %s. You are %s. You feel %s."), *F.TimeOfDay, *F.Activity, *F.Mood));
    if (F.RecentEvents.Num()) Lines.Add(TEXT("Lately: ") + Joined(F.RecentEvents, TEXT("; ")) + TEXT("."));
    Lines.Add(F.PlayerMemory);
    return FString::Join(Lines, TEXT("\n"));
}

FName UReflectionsLivesSubsystem::GetGreetingGroup(const AActor* Actor) const
{
    const FLife* Life = FindLifeByActor(Actor);
    if (!Life) return NAME_None;
    const EReflectionsLifeMood Mood = GetMood(Life->Person.Id);
    const float Opinion = GetPlayerMemory(Life->Person.Id).Opinion;
    if (Mood == EReflectionsLifeMood::Grieving) return TEXT("Greet_Grieving");
    if (Mood == EReflectionsLifeMood::Afraid || Opinion < -0.6f) return TEXT("Greet_Afraid");
    if (Opinion < -0.25f || Mood == EReflectionsLifeMood::Angry) return TEXT("Greet_Cold");
    if (Opinion > 0.3f) return TEXT("Greet_Warm");
    return Life->Person.Personality.Chattiness > 0.6f ? FName(TEXT("Greet_Neutral")) : NAME_None;
}

FString UReflectionsLivesSubsystem::GetGreetingHint(const AActor* Actor) const
{
    const FLife* Life = FindLifeByActor(Actor);
    if (!Life) return FString();
    const FReflectionsPlayerMemory M = GetPlayerMemory(Life->Person.Id);
    const FName Group = GetGreetingGroup(Actor);
    const FString Because = M.LastDeedNote.IsEmpty() ? FString() : FString::Printf(TEXT(" They remember the Silverer %s."), *M.LastDeedNote);
    if (Group == TEXT("Greet_Grieving")) return TEXT("Barely looks up; grief is all they can talk about.") + Because;
    if (Group == TEXT("Greet_Afraid")) return TEXT("Flinches and wants the Silverer gone.") + Because;
    if (Group == TEXT("Greet_Cold")) return TEXT("Cold and short with the Silverer.") + Because;
    if (Group == TEXT("Greet_Warm")) return TEXT("Glad to see the Silverer, greets them like a friend.") + Because;
    return Life->Person.Personality.Chattiness > 0.6f ? TEXT("Curious about the stranger, happy to chat.") : TEXT("Polite but guarded with a stranger.");
}

// ---- Crimes, fear and hatred of the player ------------------------------------------------------------------

int32 UReflectionsLivesSubsystem::GetPlayerFeeling(FName PersonId) const
{
    const FReflectionsPersonState* S = Memory.IsValid() ? Memory->Find(PersonId) : nullptr;
    if (!S || S->bDead || S->Player.Opinion > -0.35f) return 0;
    const FLife* Life = FindLife(PersonId);
    const FReflectionsPersonality P = Life ? Life->Person.Personality : FReflectionsPersonality();
    const bool bActive = S->MoodUntilHours > LocalHours;
    if ((bActive && S->Mood == EReflectionsLifeMood::Angry) || (P.Temper > 0.6f && P.Courage > 0.5f)) return 2;
    return 1;
}

void UReflectionsLivesSubsystem::TickShy(FLife& Life, double Now, const FVector& PlayerLocation)
{
    AActor* Actor = Life.Actor.Get();
    ACharacter* Driver = DriverOf(Life);
    if (!Actor || !Driver) return;
    if (Life.bShy)
    {
        if (Now < Life.ShyUntil) return;
        // Clear of the player: their own pace again, and the day picks up where they are.
        Life.bShy = false;
        if (Life.bShyRun) SetWalkGait(Driver, true);
        Life.bShyRun = false;
        Life.StepIndex = INDEX_NONE;
        Life.NextThink = 0.0f;
        return;
    }
    if (Life.bInside || Life.Move == EMove::Inside) return;
    const float Dist = FVector::Dist2D(Actor->GetActorLocation(), PlayerLocation);
    if (Dist > 700.0f) return;
    const int32 Feeling = GetPlayerFeeling(Life.Person.Id);
    if (Feeling == 0) return;
    if (Life.Move == EMove::Chat || Life.Move == EMove::Meet) EndChat(Life);
    // Away from the player: the frightened far and (if not brave) at a run, the hateful a few steps and a cold look.
    FVector Dir = (Actor->GetActorLocation() - PlayerLocation).GetSafeNormal2D();
    if (Dir.IsNearlyZero()) Dir = FVector::ForwardVector.RotateAngleAxis(static_cast<float>(Life.Seed % 360u), FVector::UpVector);
    Dir = Dir.RotateAngleAxis(static_cast<float>(static_cast<int32>(Life.Seed % 61u) - 30), FVector::UpVector);
    SetGoal(Life, GroundPoint(Actor->GetActorLocation() + Dir * (Feeling == 1 ? 1600.0f : 900.0f)), EMove::Travel);
    Life.Idle = 0.0f;
    Life.bShy = true;
    Life.bShyRun = Feeling == 1 && Life.Person.Personality.Courage < 0.5f;
    if (Life.bShyRun) SetWalkGait(Driver, false);
    Life.ShyUntil = Now + (Feeling == 1 ? 9.0 : 6.0);
    Life.Activity = EReflectionsLifeActivity::Shun;
    UE_LOG(LogReflectionsLives, Log, TEXT("%s keeps away from the Silverer (%s, %.0f cm)"), *Life.Person.Name,
        Feeling == 1 ? TEXT("afraid") : TEXT("hates them"), Dist);
    if (Now >= Life.NextGreetTime)
    {
        Life.NextGreetTime = Now + 40.0 + (Life.Seed % 20u);
        const FName Group = Feeling == 1 ? FName(TEXT("Greet_Afraid")) : FName(TEXT("Greet_Cold"));
        if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
            if (Npcs->FindVoiceCue(Actor, Group)) Npcs->PlayBark(Actor, Group);
    }
}

void UReflectionsLivesSubsystem::HandlePlayerCrime(AActor* Victim, FName Crime, AActor* Witness, FVector Location, float Heat)
{
    ReportPlayerCrime(Crime, Victim, Location, Witness);
}

void UReflectionsLivesSubsystem::ReportPlayerCrime(FName Crime, AActor* Victim, FVector Location, AActor* Witness)
{
    if (!bStarted || !GetWorld()) return;
    UReflectionsLivesMemory* Mem = Memory.Get();
    if (!Mem) return;
    if (Location.IsNearlyZero() && Victim) Location = Victim->GetActorLocation();
    FLife* VictimLife = FindLifeByActor(Victim);
    const FString C = Crime.ToString().ToLower();
    const bool bViolent = C.Contains(TEXT("murder")) || C.Contains(TEXT("kill")) || C.Contains(TEXT("assault")) || C.Contains(TEXT("arson"));

    // The victim remembers what was done to them (a killing is remembered by those left behind instead).
    if (VictimLife && !bViolent)
    {
        const double Now = GetWorld()->GetTimeSeconds();
        if (Now - VictimLife->LastCrimeTime > 3.0)
        {
            VictimLife->LastCrimeTime = Now;
            const FString Note = C.Contains(TEXT("theft")) || C.Contains(TEXT("steal")) ? FString(TEXT("stole from me"))
                : C.Contains(TEXT("assault")) ? FString(TEXT("attacked me")) : FString::Printf(TEXT("wronged me (%s)"), *C);
            RememberPlayerById(VictimLife->Person.Id, EReflectionsPlayerDeed::Hurt, bViolent ? 1.0f : 0.6f, Note);
            AddEvent(Mem->FindOrAdd(VictimLife->Person.Id), TEXT("the Silverer ") + Note);
        }
    }

    // One named witness (npc-unify reports once per witness), or everyone who saw or heard it.
    if (Witness)
    {
        if (FLife* W = FindLifeByActor(Witness))
            if (W != VictimLife) CrimeSeenBy(*W, Crime, VictimLife, Location, true);
        return;
    }
    const float Radius = bViolent ? CVarLivesWitnessRadius.GetValueOnGameThread() : 1200.0f;
    for (auto& Pair : Lives)
    {
        FLife& W = Pair.Value;
        AActor* WActor = W.Actor.Get();
        if (&W == VictimLife || !WActor || W.bInside || (W.Brain.IsValid() && W.Brain->IsIncapacitated())) continue;
        if (const FReflectionsPersonState* WS = Mem->Find(W.Person.Id))
            if (WS->bDead || WS->bTarnished) continue;
        const float Dist = FVector::Dist(WActor->GetActorLocation(), Location);
        if (Dist > Radius) continue;
        if (Dist > 800.0f && !(Victim ? UReflectionsNpcReactionComponent::HasLineOfSight(WActor, Victim, DriverOf(W)) : true)) continue;
        CrimeSeenBy(W, Crime, VictimLife, Location, true);
    }
}

void UReflectionsLivesSubsystem::CrimeSeenBy(FLife& W, FName Crime, const FLife* VictimLife, const FVector& Where, bool bSaw)
{
    UReflectionsLivesMemory* Mem = Memory.Get();
    if (!Mem || !GetWorld()) return;
    const double Now = GetWorld()->GetTimeSeconds();
    if (Now - W.LastCrimeTime < 3.0) return;  // the same crime reported twice
    W.LastCrimeTime = Now;
    FReflectionsPersonState& S = Mem->FindOrAdd(W.Person.Id);
    const FReflectionsPersonality& P = W.Person.Personality;
    const FString C = Crime.ToString().ToLower();
    const bool bMurder = C.Contains(TEXT("murder")) || C.Contains(TEXT("kill"));
    const bool bViolent = bMurder || C.Contains(TEXT("assault")) || C.Contains(TEXT("arson"));
    const FString Relation = VictimLife ? RelationTo(W, VictimLife->Person.Id) : FString();
    const bool bKnown = !Relation.IsEmpty() && Relation != TEXT("rival");
    const FString Victim = VictimLife ? (bKnown ? FString::Printf(TEXT("%s (%s)"), *VictimLife->Person.Name, *Relation) : VictimLife->Person.Name) : FString(TEXT("someone"));
    FString Verb;
    float Severity = 0.4f;
    if (bMurder) { Verb = FString::Printf(TEXT("murder %s"), *Victim); Severity = 1.0f; }
    else if (C.Contains(TEXT("assault"))) { Verb = FString::Printf(TEXT("attack %s"), *Victim); Severity = 0.6f; }
    else if (C.Contains(TEXT("arson"))) { Verb = TEXT("set a fire"); Severity = 0.7f; }
    else if (C.Contains(TEXT("theft")) || C.Contains(TEXT("steal"))) { Verb = FString::Printf(TEXT("steal from %s"), *Victim); Severity = 0.35f; }
    else if (C.Contains(TEXT("trespass"))) { Verb = TEXT("break in where they had no business"); Severity = 0.2f; }
    else { Verb = FString::Printf(TEXT("commit a crime (%s)"), *C); }
    if (bKnown) Severity *= 1.5f;
    const FString Text = FString::Printf(TEXT("%s the Silverer %s"), bSaw ? TEXT("saw") : TEXT("heard"), *Verb);
    // A killing in front of them is also a death (grief, fear) through OnNpcDied; here only what the crime adds.
    const bool bDeathAlsoSeen = bMurder && Now - W.LastReactionTime < 3.0;
    RememberPlayerById(W.Person.Id, EReflectionsPlayerDeed::WitnessedCrime, Severity, Verb);
    if (!bDeathAlsoSeen)
    {
        if (bViolent)
        {
            SetMood(W.Person.Id, (P.Courage > 0.6f && P.Temper > 0.5f) || bKnown ? EReflectionsLifeMood::Angry : EReflectionsLifeMood::Afraid,
                2.0f + (1.0f - P.Courage) * 4.0f, bKnown && VictimLife ? VictimLife->Person.Id : NAME_None);
            S.AvoidLocation = Where;
            S.AvoidUntilHours = FMath::Max(S.AvoidUntilHours, LocalHours + 4.0);
            if (bSaw) W.AvoidStepUntilHours = LocalHours + 0.5;
        }
        else SetMood(W.Person.Id, bKnown ? EReflectionsLifeMood::Angry : EReflectionsLifeMood::Wary, 2.0f, bKnown && VictimLife ? VictimLife->Person.Id : NAME_None);
        AddEvent(S, Text);
        W.LastReactionText = Text;
        W.LastReactionTime = Now;
        W.StepIndex = INDEX_NONE;
        W.NextThink = 0.0f;
    }
    UE_LOG(LogReflectionsLives, Log, TEXT("%s %s"), *W.Person.Name, *Text);
    OnLifeEvent.Broadcast(W.Person.Id, W.Actor.Get(), Text);
}

// ---- Bodies' side and role (crowd-looks' Look_* tags, else the look's name) ------------------------------------

FName UReflectionsLivesSubsystem::BodySide(const AActor* Body)
{
    if (!Body) return NAME_None;
    for (const FName& Tag : Body->Tags)
    {
        const FString T = Tag.ToString();
        if (T.StartsWith(TEXT("Look_Side_"))) return FName(*T.RightChop(10));
    }
    // Older looks without tags: red is Giltside's, the white rag looks Frostside's, grey Pewterside's.
    const FString N = Body->GetClass()->GetName();
    if (N.Contains(TEXT("Gilt")) || N.Contains(TEXT("Red"))) return TEXT("Giltside");
    if (N.Contains(TEXT("Frost")) || N.Contains(TEXT("White")) || N.Contains(TEXT("Rag"))) return TEXT("Frostside");
    if (N.Contains(TEXT("Pew")) || N.Contains(TEXT("Gray")) || N.Contains(TEXT("Grey"))) return TEXT("Pewterside");
    return NAME_None;
}

FName UReflectionsLivesSubsystem::BodyRole(const AActor* Body)
{
    if (!Body) return NAME_None;
    for (const FName& Tag : Body->Tags)
    {
        const FString T = Tag.ToString();
        if (T.StartsWith(TEXT("Look_Role_"))) return FName(*T.RightChop(10));
    }
    return Body->GetClass()->GetName().Contains(TEXT("Guard")) ? FName(TEXT("Guard")) : NAME_None;
}

bool UReflectionsLivesSubsystem::SameSide(FName A, FName B)
{
    // Unknown on either side: nothing to go against. "Gilt" and "Giltside" are the same side.
    if (A.IsNone() || B.IsNone()) return true;
    return A.ToString().Left(4).Equals(B.ToString().Left(4), ESearchCase::IgnoreCase);
}

bool UReflectionsLivesSubsystem::IsSoldierPerson(const FReflectionsPerson& Person)
{
    const FString Arch = Person.Archetype.ToString();
    return Arch == TEXT("Soldier") || Arch == TEXT("SoldierCaster") || Person.LookRole == TEXT("Soldier") ||
        Person.ScheduleKey.ToString().StartsWith(TEXT("soldier"));
}

// ---- Crowd bridge ------------------------------------------------------------------------------------------------

FName UReflectionsLivesSubsystem::ClaimPersonForCrowdAgent(int32 AgentKey)
{
    if (const FName* Known = CrowdAgents.Find(AgentKey)) return *Known;
    if (!bStarted) BeginLives();
    const FName Id(*FString::Printf(TEXT("crowd_%d"), AgentKey));
    FLife* Life = FindLife(Id);
    if (!Life)
    {
        FReflectionsPerson Person = Book.Generate(Id, NAME_None, NAME_None, NAME_None, 0);
        Life = &AddLife(Person);
    }
    Life->bCrowdAgent = true;
    CrowdAgents.Add(AgentKey, Id);
    return Id;
}

bool UReflectionsLivesSubsystem::GetPersonGoal(FName PersonId, FVector& OutGoal) const
{
    const FLife* Life = FindLife(PersonId);
    if (!Life || Life->StepIndex == INDEX_NONE || Life->bIndoorStep) return false;
    if (const FReflectionsPersonState* S = Memory.IsValid() ? Memory->Find(PersonId) : nullptr)
        if (S->bDead || S->bTarnished) return false;
    OutGoal = Life->PlaceLocation;
    return true;
}

// ---- Debug ----------------------------------------------------------------------------------------------------------

FString UReflectionsLivesSubsystem::Describe() const
{
    TArray<FString> Out;
    Out.Add(FString::Printf(TEXT("Lives: day %d %s, %d people (%d with a body), %d places, book: %s"),
        GetDay(), *GetClockText(), Lives.Num(), GetEmbodiedCount(), Places.Num(), *Book.GetSource()));
    for (const auto& Pair : Lives)
    {
        const FLife& L = Pair.Value;
        const AActor* Actor = L.Actor.Get();
        static const TCHAR* LodNames[] = { TEXT("full"), TEXT("far"), TEXT("virtual") };
        static const TCHAR* MoveNames[] = { TEXT("none"), TEXT("travel"), TEXT("mill"), TEXT("meet"), TEXT("chat"), TEXT("inside") };
        Out.Add(FString::Printf(TEXT("  %-14s %-20s %-14s %-12s @ %-22s %-7s %-6s mood=%s opinion=%+.2f %s goal=%.0fcm%s"),
            *L.Person.Id.ToString(), *L.Person.Name, *L.Person.JobTitle, *ActivityText(L.Activity), *L.PlaceTag.ToString(),
            LodNames[static_cast<int32>(L.Lod)], MoveNames[static_cast<int32>(L.Move)], *MoodText(GetMood(L.Person.Id)),
            GetPlayerMemory(L.Person.Id).Opinion, Actor ? *Actor->GetName() : TEXT("-"),
            Actor ? FVector::Dist2D(Actor->GetActorLocation(), L.Goal) : 0.0f,
            L.ChatWith != NAME_None ? *FString::Printf(TEXT(" chat=%s"), *L.ChatWith.ToString()) : TEXT("")));
    }
    return FString::Join(Out, TEXT("\n"));
}

FString UReflectionsLivesSubsystem::TestWitness(const FString& WitnessName)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Npcs) return FString();
    APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    FLife* Witness = nullptr;
    FLife* Victim = nullptr;
    float Best = TNumericLimits<float>::Max();
    for (auto& WPair : Lives)
    {
        FLife& W = WPair.Value;
        if (!W.Actor.IsValid() || W.bInside) continue;
        if (!WitnessName.IsEmpty() && !W.Person.Name.Contains(WitnessName) && W.Person.Id.ToString() != WitnessName) continue;
        for (auto& VPair : Lives)
        {
            FLife& V = VPair.Value;
            if (&V == &W || !V.Actor.IsValid() || !V.Brain.IsValid() || V.Brain->GetInfection() != EReflectionsNpcInfection::None) continue;
            const float Dist = FVector::Dist(W.Actor->GetActorLocation(), V.Actor->GetActorLocation());
            if (Dist > CVarLivesWitnessRadius.GetValueOnGameThread() * 0.8f) continue;
            // Prefer a pair who know each other, near the player (so the test can be seen).
            const float Score = Dist + (Knows(W, V.Person.Id) ? 0.0f : 5000.0f) + (Player ? FVector::Dist(Player->GetActorLocation(), W.Actor->GetActorLocation()) * 0.25f : 0.0f);
            if (Score < Best) { Best = Score; Witness = &W; Victim = &V; }
        }
    }
    if (!Witness || !Victim) return FString();
    if (!Knows(*Witness, Victim->Person.Id))
    {
        // For the test only: make them friends so the reaction is the one we want to see.
        Witness->Person.Friends.AddUnique(Victim->Person.Id);
        Victim->Person.Friends.AddUnique(Witness->Person.Id);
    }
    const FString Result = FString::Printf(TEXT("%s (%s) sees %s taken"), *Witness->Person.Name, *RelationTo(*Witness, Victim->Person.Id), *Victim->Person.Name);
    Npcs->SetInfection(Victim->Actor.Get(), EReflectionsNpcInfection::Infected, nullptr);
    return Result;
}

void UReflectionsLivesSubsystem::UpdateOverlay()
{
    const int32 Level = GetDebugLevel();
    UWorld* World = GetWorld();
    UGameViewportClient* Viewport = World ? World->GetGameViewport() : nullptr;
    if (Level <= 0 || !bStarted || !Viewport)
    {
        if (Overlay.IsValid()) Overlay->SetLabels(TArray<FReflectionsLivesLabel>());
        return;
    }
    if (!Overlay.IsValid())
    {
        Overlay = SNew(SReflectionsLivesOverlay);
        Viewport->AddViewportWidgetContent(Overlay.ToSharedRef(), 45);
    }
    APlayerController* Local = World->GetFirstPlayerController();
    if (!Local || !Local->PlayerCameraManager) return;
    const FVector CamLoc = Local->PlayerCameraManager->GetCameraLocation();
    const FVector CamFwd = Local->PlayerCameraManager->GetCameraRotation().Vector();
    const float Now = World->GetTimeSeconds();
    TArray<FReflectionsLivesLabel> Labels;
    auto DrawLines = [&Labels](float X, float Y, const TArray<TPair<FString, FColor>>& Lines, bool bCenter)
    {
        FReflectionsLivesLabel& Label = Labels.AddDefaulted_GetRef();
        Label.Pixel = FVector2D(X, Y);
        Label.bCenter = bCenter;
        for (const auto& L : Lines) Label.Lines.Emplace(L.Key, FLinearColor(L.Value));
    };
    auto Project = [Local](const FVector& World_) { FVector2D Out; UGameplayStatics::ProjectWorldToScreen(Local, World_, Out, false); return Out; };

    // The clock, top left.
    {
        TArray<TPair<FString, FColor>> Header;
        Header.Emplace(FString::Printf(TEXT("LIVES  Day %d  %s   (%.0f real min/day, x%.1f)   %d people, %d here   F7: overlay"),
            GetDay(), *GetClockText(), Book.RealMinutesPerDay, CVarLivesTimeScale.GetValueOnGameThread(), Lives.Num(), GetEmbodiedCount()), FColor(255, 220, 120));
        if (Level >= 2) Header.Emplace(FString::Printf(TEXT("book: %s   places: %d"), *Book.GetSource(), Places.Num()), FColor(180, 180, 180));
        DrawLines(20.0f, 185.0f, Header, false);  // below the world-jump panel (top left)
    }

    TArray<TTuple<float, FVector2D, TArray<TPair<FString, FColor>>>> Pending;
    for (const auto& Pair : Lives)
    {
        const FLife& L = Pair.Value;
        const AActor* Actor = L.Actor.Get();
        if (!Actor || (L.bHeld && Actor->IsHidden())) continue;
        // Just above the head bone (the bounds of a MetaHuman include far more than the body).
        FVector Head = Actor->GetActorLocation() + FVector(0.0, 0.0, 195.0);
        if (const UReflectionsNpcReactionComponent* Brain = L.Brain.Get())
            if (const USkeletalMeshComponent* Body = Brain->GetBodyMesh())
                if (Body->GetBoneIndex(TEXT("head")) != INDEX_NONE) Head = Body->GetBoneLocation(TEXT("head")) + FVector(0.0, 0.0, 40.0);
        const FVector ToHead = Head - CamLoc;
        const float Dist = ToHead.Size();
        if (Dist > 4500.0f || FVector::DotProduct(ToHead.GetSafeNormal(), CamFwd) < 0.2f) continue;
        const bool bNear = Dist < 1800.0f;
        const FVector2D Screen = Project(Head);
        const EReflectionsLifeMood Mood = GetMood(L.Person.Id);
        FColor MoodColor = FColor(170, 230, 170);
        switch (Mood)
        {
        case EReflectionsLifeMood::Grieving: MoodColor = FColor(150, 170, 255); break;
        case EReflectionsLifeMood::Afraid: MoodColor = FColor(255, 200, 90); break;
        case EReflectionsLifeMood::Angry: MoodColor = FColor(255, 110, 100); break;
        case EReflectionsLifeMood::Wary: MoodColor = FColor(230, 210, 150); break;
        case EReflectionsLifeMood::Cheerful: MoodColor = FColor(140, 255, 200); break;
        default: break;
        }
        FString Doing = ActivityText(L.Activity);
        if (L.Move == EMove::Chat || L.Move == EMove::Meet) Doing = FString::Printf(TEXT("%s with %s"), L.Move == EMove::Chat ? TEXT("Chatting") : TEXT("Going to meet"), *GetPersonName(L.ChatWith));
        else if (L.Move == EMove::Travel) Doing += TEXT(" (on the way)");
        else if (L.bInside) Doing += TEXT(" (inside)");
        TArray<TPair<FString, FColor>> Lines;
        Lines.Emplace(FString::Printf(TEXT("%s  -  %s"), *L.Person.Name, *L.Person.JobTitle), L.Person.bNamed ? FColor(255, 230, 140) : FColor::White);
        Lines.Emplace(FString::Printf(TEXT("Now: %s @ %s"), *Doing, *PrettyPlace(L.PlaceTag)), FColor(230, 230, 230));
        Lines.Emplace(FString::Printf(TEXT("Next: %s"), *NextStepText(L)), FColor(170, 170, 170));
        const FReflectionsPlayerMemory M = GetPlayerMemory(L.Person.Id);
        FString MoodLine = FString::Printf(TEXT("Mood: %s   Opinion of you: %+.2f"), *MoodText(Mood), M.Opinion);
        if (const FReflectionsPersonState* S = Memory.IsValid() ? Memory->Find(L.Person.Id) : nullptr)
            if (Mood != EReflectionsLifeMood::Content && !S->ConcernFor.IsNone()) MoodLine += FString::Printf(TEXT("   (%s)"), *GetPersonName(S->ConcernFor));
        Lines.Emplace(MoodLine, MoodColor);
        if (Now - L.LastReactionTime < 12.0f && !L.LastReactionText.IsEmpty()) Lines.Emplace(TEXT("! ") + L.LastReactionText, MoodColor);
        if (Level >= 2)
        {
            Lines.Emplace(FString::Printf(TEXT("%s | %s | %s"), *Joined(L.Person.Personality.Traits), L.Lod == EReflectionsLifeLod::Full ? TEXT("full") : TEXT("far"),
                *L.Person.Id.ToString()), FColor(150, 150, 150));
            DrawDebugLine(GetWorld(), Actor->GetActorLocation(), L.Goal + FVector(0, 0, 20), MoodColor, false, -1.0f, 0, 1.5f);
        }
        // Far people get their name and what they are doing; near ones the whole card.
        if (!bNear) Lines.SetNum(FMath::Min(Lines.Num(), 2));
        Pending.Emplace(Dist, Screen, MoveTemp(Lines));
    }

    // Nearest first; a card that would cover one already placed moves up a little, or is left out if far away.
    Pending.Sort([](const auto& A, const auto& B) { return A.template Get<0>() < B.template Get<0>(); });
    TArray<FBox2D> Taken;
    for (auto& Item : Pending)
    {
        const TArray<TPair<FString, FColor>>& Lines = Item.template Get<2>();
        int32 Chars = 0;
        for (const auto& Line : Lines) Chars = FMath::Max(Chars, Line.Key.Len());
        const FVector2D Size(Chars * 6.5 + 12.0, Lines.Num() * 15.0 + 8.0);
        FVector2D Anchor = Item.template Get<1>();
        bool bPlaced = false;
        for (int32 Try = 0; Try < 4 && !bPlaced; ++Try)
        {
            const FBox2D Box(FVector2D(Anchor.X - Size.X * 0.5, Anchor.Y - Size.Y), FVector2D(Anchor.X + Size.X * 0.5, Anchor.Y));
            if (!Taken.ContainsByPredicate([&Box](const FBox2D& Other) { return Other.Intersect(Box); }))
            {
                Taken.Add(Box);
                DrawLines(Anchor.X, Anchor.Y, Lines, true);
                bPlaced = true;
            }
            else Anchor.Y -= Size.Y * 0.6;
        }
    }

    if (Level >= 2)
        for (const auto& Pair : Places)
        {
            const FReflectionsLifePlace& Place = Pair.Value;
            if (FVector::Dist(Place.Location, CamLoc) > 6000.0f) continue;
            DrawDebugCircle(GetWorld(), Place.Location + FVector(0, 0, 10), Place.Radius, 24, Place.bAuto ? FColor(120, 120, 255) : FColor(80, 255, 120),
                false, -1.0f, 0, 2.0f, FVector::ForwardVector, FVector::RightVector, false);
            const FVector2D S = Project(Place.Location + FVector(0, 0, 60));
            if (FVector::DotProduct((Place.Location - CamLoc).GetSafeNormal(), CamFwd) > 0.2f)
            {
                TArray<TPair<FString, FColor>> L;
                L.Emplace(Place.Tag.ToString() + (Place.bAuto ? TEXT(" (auto)") : TEXT("")), FColor(160, 200, 255));
                DrawLines(S.X, S.Y, L, true);
            }
        }
    Overlay->SetLabels(MoveTemp(Labels));
}
