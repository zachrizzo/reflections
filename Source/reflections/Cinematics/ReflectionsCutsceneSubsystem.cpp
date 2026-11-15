#include "Cinematics/ReflectionsCutsceneSubsystem.h"

#include "Cinematics/ReflectionsCutsceneAsset.h"
#include "Cinematics/ReflectionsCutsceneSlate.h"
#include "GameFlow/ReflectionsGameFlowSubsystem.h"
#include "NPC/ReflectionsNpcSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/Skeleton.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/AudioComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "DefaultLevelSequenceInstanceData.h"
#include "Engine/GameInstance.h"
#include "Engine/GameViewportClient.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Engine/LocalPlayer.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "LevelSequence.h"
#include "LevelSequenceActor.h"
#include "LevelSequencePlayer.h"
#include "Misc/App.h"
#include "Sound/SoundBase.h"
#include "Widgets/SWeakWidget.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsCutscene, Log, All);

static TAutoConsoleVariable<int32> CVarCutsceneEnable(
    TEXT("Cutscene.Enable"), 1,
    TEXT("0 = cutscenes never start (PlayCutscene returns false, so callers carry on)."));

static TAutoConsoleVariable<int32> CVarCutsceneIntroInPIE(
    TEXT("Cutscene.IntroInPIE"), 0,
    TEXT("1 = the new-game intro also plays in PIE (off so other sessions' PIE tests are not hijacked)."));

static TAutoConsoleVariable<int32> CVarCutsceneHideHud(
    TEXT("Cutscene.HideHud"), 1,
    TEXT("1 = other viewport layers (HUDs) fade out while a cutscene plays."));

namespace ReflectionsCutscene
{
    /** Cutscene.Play sets this so a test can play the intro in PIE. One play session plays one cutscene at a time. */
    static bool bForceNextPlay = false;
    /** The view target before the cutscene (the gameplay camera system's), to put back if Sequencer didn't. */
    static TWeakObjectPtr<AActor> OriginalViewTarget;

    static const TCHAR* DataFolder = TEXT("/Game/Cinematics/Data");
    static constexpr float LetterboxSeconds = 0.7f;
    static constexpr float OutroSeconds = 0.7f;
    static constexpr float CardFadeSeconds = 0.9f;
    static constexpr float LineFadeSeconds = 0.18f;

    static FString AssetPath(FName Name)
    {
        const FString Short = FString::Printf(TEXT("DA_Cutscene_%s"), *Name.ToString());
        return FString::Printf(TEXT("%s/%s.%s"), DataFolder, *Short, *Short);
    }

    template <typename T>
    static T* LoadSoft(const TSoftObjectPtr<T>& Soft, TArray<TObjectPtr<UObject>>& Keep)
    {
        if (Soft.IsNull())
        {
            return nullptr;
        }
        T* Object = Soft.LoadSynchronous();
        if (Object)
        {
            Keep.AddUnique(Object);
        }
        else
        {
            UE_LOG(LogReflectionsCutscene, Warning, TEXT("Cutscene asset %s did not load."), *Soft.ToString());
        }
        return Object;
    }

    static AActor* RootOf(AActor* Actor)
    {
        AActor* Root = Actor;
        while (Root && Root->GetAttachParentActor())
        {
            Root = Root->GetAttachParentActor();
        }
        return Root;
    }

    /** Distance from a character's origin down to its feet (0 for other actors). */
    static float FeetOffset(const AActor* Actor)
    {
        if (const ACharacter* Character = Cast<ACharacter>(Actor))
        {
            if (const UCapsuleComponent* Capsule = Character->GetCapsuleComponent())
            {
                return Capsule->GetScaledCapsuleHalfHeight();
            }
        }
        return 0.0f;
    }

    static UObject* FindComponentByClassName(AActor* Actor, const TCHAR* ClassName)
    {
        TArray<AActor*> Candidates;
        if (Actor)
        {
            Candidates.Add(Actor);
            Actor->GetAttachedActors(Candidates, false, true);
            for (AActor* Parent = Actor->GetAttachParentActor(); Parent; Parent = Parent->GetAttachParentActor())
            {
                Candidates.Add(Parent);
            }
        }
        for (AActor* Candidate : Candidates)
        {
            for (UActorComponent* Component : Candidate->GetComponents())
            {
                if (Component && Component->GetClass()->GetName() == ClassName)
                {
                    return Component;
                }
            }
        }
        return nullptr;
    }

    static bool CallBoolSetter(UObject* Target, const TCHAR* FunctionName, bool bValue)
    {
        if (!Target)
        {
            return false;
        }
        UFunction* Function = Target->FindFunction(FunctionName);
        if (!Function || Function->ParmsSize < sizeof(bool) || Function->NumParms != 1)
        {
            return false;
        }
        TArray<uint8, TInlineAllocator<16>> Params;
        Params.SetNumZeroed(Function->ParmsSize);
        if (FBoolProperty* Prop = CastField<FBoolProperty>(Function->PropertyLink))
        {
            Prop->SetPropertyValue_InContainer(Params.GetData(), bValue);
            Target->ProcessEvent(Function, Params.GetData());
            return true;
        }
        return false;
    }

    /** The actor that moves the body: an NPC's hidden locomotion driver (by name on its reaction component), else the attach root. */
    static AActor* DriverOf(AActor* Actor)
    {
        if (!Actor)
        {
            return nullptr;
        }
        if (UObject* Npc = FindComponentByClassName(Actor, TEXT("ReflectionsNpcReactionComponent")))
        {
            for (const TCHAR* Getter : { TEXT("GetLocomotionDriver"), TEXT("GetMovementCharacter") })
            {
                UFunction* Function = Npc->FindFunction(Getter);
                FObjectPropertyBase* Return = Function ? CastField<FObjectPropertyBase>(Function->GetReturnProperty()) : nullptr;
                if (!Return || Function->NumParms != 1)
                {
                    continue;
                }
                TArray<uint8, TInlineAllocator<32>> Params;
                Params.SetNumZeroed(Function->ParmsSize);
                Npc->ProcessEvent(Function, Params.GetData());
                if (AActor* Driver = Cast<AActor>(Return->GetObjectPropertyValue_InContainer(Params.GetData())))
                {
                    return RootOf(Driver);
                }
            }
        }
        return RootOf(Actor);
    }

    /** A world or game-instance subsystem found by class path, so other modules' code needs no header here. */
    static UObject* FindSubsystemByPath(UWorld* World, const TCHAR* ClassPath)
    {
        UClass* Class = FindObject<UClass>(nullptr, ClassPath);
        if (!Class || !World)
        {
            return nullptr;
        }
        if (Class->IsChildOf(UWorldSubsystem::StaticClass()))
        {
            return World->GetSubsystemBase(TSubclassOf<UWorldSubsystem>(Class));
        }
        if (Class->IsChildOf(UGameInstanceSubsystem::StaticClass()) && World->GetGameInstance())
        {
            return World->GetGameInstance()->GetSubsystemBase(TSubclassOf<UGameInstanceSubsystem>(Class));
        }
        return nullptr;
    }

    /** Lives: SpawnPerson(FName PersonId, FVector Location, float FacingYaw) -> AActor*, by name. */
    static AActor* SpawnPerson(UWorld* World, FName PersonId, const FVector& Location, float Yaw)
    {
        UObject* Lives = FindSubsystemByPath(World, TEXT("/Script/reflections.ReflectionsLivesSubsystem"));
        UFunction* Function = Lives ? Lives->FindFunction(TEXT("SpawnPerson")) : nullptr;
        if (!Function)
        {
            return nullptr;
        }
        TArray<uint8, TInlineAllocator<64>> Params;
        Params.SetNumZeroed(Function->ParmsSize);
        FObjectPropertyBase* Return = nullptr;
        int32 Filled = 0;
        for (TFieldIterator<FProperty> It(Function); It && (It->PropertyFlags & CPF_Parm); ++It)
        {
            if (It->PropertyFlags & CPF_ReturnParm)
            {
                Return = CastField<FObjectPropertyBase>(*It);
            }
            else if (FNameProperty* NameProp = CastField<FNameProperty>(*It); NameProp && Filled == 0)
            {
                NameProp->SetPropertyValue_InContainer(Params.GetData(), PersonId); ++Filled;
            }
            else if (FStructProperty* StructProp = CastField<FStructProperty>(*It); StructProp && Filled == 1 && StructProp->Struct == TBaseStructure<FVector>::Get())
            {
                *StructProp->ContainerPtrToValuePtr<FVector>(Params.GetData()) = Location; ++Filled;
            }
            else if (FFloatProperty* FloatProp = CastField<FFloatProperty>(*It); FloatProp && Filled == 2)
            {
                FloatProp->SetPropertyValue_InContainer(Params.GetData(), Yaw); ++Filled;
            }
            else
            {
                return nullptr;  // unexpected signature
            }
        }
        if (!Return || Filled < 2)
        {
            return nullptr;
        }
        Lives->ProcessEvent(Function, Params.GetData());
        return Cast<AActor>(Return->GetObjectPropertyValue_InContainer(Params.GetData()));
    }

    static bool NameMatches(const FString& Candidate, const FString& Wanted)
    {
        return !Wanted.IsEmpty() && Candidate.Equals(Wanted, ESearchCase::IgnoreCase);
    }
}

using namespace ReflectionsCutscene;

// ---- Lifetime ----------------------------------------------------------------------------------------------

UReflectionsCutsceneSubsystem* UReflectionsCutsceneSubsystem::Get(const UObject* WorldContext)
{
    const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull) : nullptr;
    return World ? World->GetSubsystem<UReflectionsCutsceneSubsystem>() : nullptr;
}

bool UReflectionsCutsceneSubsystem::IsAnyCutscenePlaying(const UObject* WorldContext)
{
    const UReflectionsCutsceneSubsystem* Sub = Get(WorldContext);
    return Sub && Sub->IsCutscenePlaying();
}

bool UReflectionsCutsceneSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

ETickableTickType UReflectionsCutsceneSubsystem::GetTickableTickType() const
{
    // Same as the base world subsystem (conditional on initialization); the override exists only for the declaration.
    return Super::GetTickableTickType();
}

TStatId UReflectionsCutsceneSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsCutsceneSubsystem, STATGROUP_Tickables);
}

void UReflectionsCutsceneSubsystem::Deinitialize()
{
    if (bActive)
    {
        // The world is going away (travel, PIE stop, quit): undo what the cutscene took, but tell nobody.
        // Quests and the villain would start scenes or add widgets in a dying world.
        bSilentTeardown = true;
        Cleanup(false);
        bSilentTeardown = false;
    }
    RemoveOverlay();
    if (HandOffCamera)
    {
        HandOffCamera->Destroy();
        HandOffCamera = nullptr;
    }
    Super::Deinitialize();
}

// ---- Public API --------------------------------------------------------------------------------------------

bool UReflectionsCutsceneSubsystem::PlayCutscene(FName Name)
{
    if (Name.IsNone())
    {
        return false;
    }
    UReflectionsCutsceneAsset* Asset = LoadObject<UReflectionsCutsceneAsset>(nullptr, *AssetPath(Name), nullptr, LOAD_NoWarn | LOAD_Quiet);
    if (!Asset)
    {
        UE_LOG(LogReflectionsCutscene, Warning, TEXT("No cutscene %s (%s)."), *Name.ToString(), *AssetPath(Name));
        return false;
    }
    return PlayCutsceneAsset(Asset, Name);
}

bool UReflectionsCutsceneSubsystem::PlayNewGameIntro()
{
    const UWorld* World = GetWorld();
    if (World && World->WorldType == EWorldType::PIE && CVarCutsceneIntroInPIE.GetValueOnGameThread() == 0)
    {
        UE_LOG(LogReflectionsCutscene, Log, TEXT("New-game intro skipped in PIE (Cutscene.IntroInPIE 0)."));
        return false;
    }
    return PlayCutscene(TEXT("Intro"));
}

bool UReflectionsCutsceneSubsystem::PlayCutsceneAsset(UReflectionsCutsceneAsset* Asset, FName Name)
{
    if (!Asset || bActive || CVarCutsceneEnable.GetValueOnGameThread() == 0)
    {
        return false;
    }
    // The intro belongs to a fresh run: in PIE it plays only on request, whoever asks (game flow, a quest step).
    if (Name == TEXT("Intro") && GetWorld() && GetWorld()->WorldType == EWorldType::PIE && CVarCutsceneIntroInPIE.GetValueOnGameThread() == 0
        && !bForceNextPlay)
    {
        UE_LOG(LogReflectionsCutscene, Log, TEXT("Intro not played in PIE (Cutscene.IntroInPIE 0; Cutscene.Play Intro forces it)."));
        return false;
    }
    bForceNextPlay = false;
    APlayerController* PC = GetController();
    APawn* Hero = GetHero();
    if (!PC || !Hero)
    {
        UE_LOG(LogReflectionsCutscene, Warning, TEXT("Cutscene %s needs a player and a hero; not started."), *Name.ToString());
        return false;
    }
    // A cutscene that is still fading out from the last one is finished off first.
    if (OverlayRoot.IsValid())
    {
        RemoveOverlay();
    }
    if (HandOffCamera)
    {
        HandOffCamera->Destroy();
        HandOffCamera = nullptr;
    }

    Current = Asset;
    CurrentName = Name;
    Loaded.Reset();
    Loaded.Add(Asset);
    LoadSoft(Asset->Sequence, Loaded);
    LoadSoft(Asset->Music, Loaded);
    for (const FReflectionsCutscenePerformance& Take : Asset->Performances) { LoadSoft(Take.Animation, Loaded); }
    for (const FReflectionsCutsceneLine& Line : Asset->Lines) { LoadSoft(Line.Voice, Loaded); }

    bActive = true;
    bEnding = false;
    bSkipped = false;
    Elapsed = 0.0f;
    EndFadeClock = -1.0f;
    RealClock = 0.0f;
    LetterboxAlpha = 0.0f;
    SkipHeld = 0.0f;
    bSkipDown = false;
    SkipPromptShownAt = -100.0f;
    SubtitleSpeaker = FText::GetEmpty();
    SubtitleText = FText::GetEmpty();
    SubtitleStart = SubtitleEnd = -100.0f;
    bHaveLastView = false;
    HoldAtTime = -1.0f;
    HoldExtraSeconds = 0.0f;
    HoldEndReal = -1.0f;
    bHolding = false;
    if (const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        bGamepad = Flow->IsUsingGamepad();
    }
    CurrentSide = TEXT("Red");
    if (const UReflectionsWorldJumpSubsystem* Jump = UReflectionsWorldJumpSubsystem::Get(this))
    {
        switch (Jump->GetCurrentWorld())
        {
        case EReflectionsWorld::Gray: CurrentSide = TEXT("Gray"); break;
        case EReflectionsWorld::White: CurrentSide = TEXT("White"); break;
        default: CurrentSide = TEXT("Red"); break;
        }
    }

    ResolveAnchor(Asset, Name);
    BeginControlTakeover();
    SpawnCast();
    ShowOverlay();
    StartSequence();

    if (USoundBase* Music = Asset->Music.Get())
    {
        MusicAudio = UGameplayStatics::SpawnSound2D(this, Music, 1.0f, 1.0f, 0.0f, nullptr, false, false);
        if (MusicAudio)
        {
            MusicAudio->FadeIn(1.0f);
        }
    }

    TickTimeline(-1.0f, 0.0f);
    UE_LOG(LogReflectionsCutscene, Log, TEXT("Cutscene %s started (%.1f s) at %s%s."), *Name.ToString(), GetTotalLength(),
        *Anchor.GetLocation().ToString(), AnchorMarker.IsValid() ? *FString::Printf(TEXT(" (marker %s)"), *AnchorMarker->GetName()) : TEXT(" (hero)"));
    OnCutsceneStarted.Broadcast(Name);
    return true;
}

void UReflectionsCutsceneSubsystem::SkipCutscene()
{
    if (!bActive || bEnding)
    {
        return;
    }
    bSkipped = true;
    bEnding = true;
    EndFadeClock = 0.0f;
    SubtitleEnd = FMath::Min(SubtitleEnd, Elapsed + LineFadeSeconds);
    if (VoiceAudio)
    {
        VoiceAudio->FadeOut(Current ? Current->SkipFadeSeconds : 0.4f, 0.0f);
    }
    UE_LOG(LogReflectionsCutscene, Log, TEXT("Cutscene %s skipped at %.1f s."), *CurrentName.ToString(), Elapsed);
}

AActor* UReflectionsCutsceneSubsystem::GetCastActor(FName Role) const
{
    for (const FCastEntry& Entry : CastEntries)
    {
        if (Entry.Role == Role)
        {
            return Entry.Actor.Get();
        }
    }
    return nullptr;
}

// ---- Tick --------------------------------------------------------------------------------------------------

void UReflectionsCutsceneSubsystem::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    const float RealDelta = FMath::Min(static_cast<float>(FApp::GetDeltaTime()), 0.1f);
    RealClock += RealDelta;

    if (HandOffCamera && HandOffBlendLeft >= 0.0f)
    {
        HandOffBlendLeft -= RealDelta;
        if (HandOffBlendLeft < 0.0f)
        {
            HandOffCamera->Destroy();
            HandOffCamera = nullptr;
        }
    }

    if (!bActive)
    {
        // Outro: bars retract and the skip fade lifts after control is back.
        if (OverlayRoot.IsValid())
        {
            LetterboxAlpha = FMath::Max(0.0f, LetterboxAlpha - RealDelta / OutroSeconds);
            EndFadeClock += RealDelta;
            if (LetterboxAlpha <= 0.0f && GetBlackAlpha() <= 0.0f)
            {
                RemoveOverlay();
            }
        }
        return;
    }

    bool bGameOver = false;
    if (IsMenuBlocking(bGameOver))
    {
        if (bGameOver)
        {
            // Lose or victory screen: get out of the way at once.
            bSkipped = true;
            Cleanup(false);
            RemoveOverlay();
            return;
        }
        // Pause menu: the world (and the sequence) is paused; show the other layers while it is up.
        HideOtherLayers(false);
        return;
    }

    APlayerController* PC = TakenController.Get();
    if (!PC || !TakenHero.IsValid())
    {
        UE_LOG(LogReflectionsCutscene, Warning, TEXT("Cutscene %s lost its player or hero; ending."), *CurrentName.ToString());
        Cleanup(false);
        return;
    }

    // Other systems switch input modes on their own schedule; keep game input off while the cutscene owns it.
    if (UGameViewportClient* Viewport = GetWorld()->GetGameViewport())
    {
        if (!Viewport->IgnoreInput())
        {
            Viewport->SetIgnoreInput(true);
        }
    }
    HideOtherLayers(CVarCutsceneHideHud.GetValueOnGameThread() != 0);

    if (PC->PlayerCameraManager)
    {
        LastView = PC->PlayerCameraManager->GetCameraCacheView();
        bHaveLastView = true;
    }

    LetterboxAlpha = Current && Current->bLetterbox ? FMath::Min(1.0f, LetterboxAlpha + RealDelta / LetterboxSeconds) : 0.0f;

    const float Previous = Elapsed;
    ULevelSequencePlayer* Player = SequenceActor ? SequenceActor->GetSequencePlayer() : nullptr;

    // Conversion hold: freeze on the held shot until the villain's conversion is over.
    if (bHolding)
    {
        if (RealClock >= HoldEndReal)
        {
            bHolding = false;
            if (Player) { Player->Play(); }
        }
    }
    else if (HoldAtTime >= 0.0f && Elapsed >= HoldAtTime)
    {
        HoldAtTime = -1.0f;
        if (HoldExtraSeconds > 0.0f)
        {
            bHolding = true;
            HoldEndReal = RealClock + HoldExtraSeconds;
            if (Player) { Player->Pause(); }
            UE_LOG(LogReflectionsCutscene, Log, TEXT("Cutscene %s holds %.2f s for the conversion."), *CurrentName.ToString(), HoldExtraSeconds);
        }
    }

    const float SequenceEnd = Player ? static_cast<float>(Player->GetDuration().AsSeconds()) : 0.0f;
    if (Player && (Player->IsPlaying() || Player->IsPaused()) && !(Player->IsPaused() && !bHolding && Elapsed >= SequenceEnd - 0.05f))
    {
        Elapsed = static_cast<float>(Player->GetCurrentTime().AsSeconds() - Player->GetStartTime().AsSeconds());
    }
    else if (!GetWorld()->IsPaused() && !bHolding)
    {
        // No sequence, or it holds its last frame while the asset's Length runs on: keep the clock going.
        Elapsed += DeltaTime;
    }
    if (Elapsed > Previous)
    {
        TickTimeline(Previous, Elapsed);
    }

    // Hold to skip.
    if (Current && Current->bSkippable && !bEnding)
    {
        if (bSkipDown)
        {
            SkipHeld = FMath::Min(1.0f, SkipHeld + RealDelta / FMath::Max(Current->SkipHoldSeconds, 0.1f));
            SkipPromptShownAt = RealClock;
            if (SkipHeld >= 1.0f)
            {
                SkipCutscene();
            }
        }
        else
        {
            SkipHeld = FMath::Max(0.0f, SkipHeld - RealDelta * 3.0f);
        }
    }

    if (bEnding)
    {
        EndFadeClock += RealDelta;
        if (EndFadeClock >= (Current ? Current->SkipFadeSeconds : 0.4f))
        {
            Cleanup(false);
            EndFadeClock = 0.0f;
        }
        return;
    }

    if (Elapsed >= GetTotalLength() - KINDA_SMALL_NUMBER)
    {
        Cleanup(true);
    }
}

void UReflectionsCutsceneSubsystem::TickTimeline(float Previous, float Now)
{
    if (!Current)
    {
        return;
    }
    auto Crossed = [Previous, Now](float Time) { return Time > Previous && Time <= Now; };
    for (const FReflectionsCutscenePerformance& Take : Current->Performances)
    {
        if (Crossed(Take.StartTime)) { StartPerformance(Take); }
    }
    for (const FReflectionsCutsceneLine& Line : Current->Lines)
    {
        if (Crossed(Line.StartTime) && !bEnding && IsLineAllowed(Line)) { StartLine(Line); }
    }
    for (const FReflectionsCutsceneCue& Cue : Current->Cues)
    {
        if (Crossed(Cue.Time))
        {
            UE_LOG(LogReflectionsCutscene, Log, TEXT("Cutscene %s cue %s at %.2f s."), *CurrentName.ToString(), *Cue.Cue.ToString(), Cue.Time);
            if (!Cue.AttackerRole.IsNone() && !Cue.VictimRole.IsNone())
            {
                StartConversion(Cue);
            }
            OnCutsceneCue.Broadcast(CurrentName, Cue.Cue);
        }
    }
}

bool UReflectionsCutsceneSubsystem::IsLineAllowed(const FReflectionsCutsceneLine& Line) const
{
    auto FoundByTag = [this](FName Role)
    {
        const FCastEntry* Entry = CastEntries.FindByPredicate([Role](const FCastEntry& E) { return E.Role == Role; });
        return Entry && Entry->bFoundByTag && Entry->Actor.IsValid();
    };
    if (!Line.OnlyWithRole.IsNone() && !FoundByTag(Line.OnlyWithRole))
    {
        return false;
    }
    if (!Line.OnlyWithoutRole.IsNone() && FoundByTag(Line.OnlyWithoutRole))
    {
        return false;
    }
    return Line.OnlyInSide.IsNone() || Line.OnlyInSide == CurrentSide;
}

void UReflectionsCutsceneSubsystem::StartConversion(const FReflectionsCutsceneCue& Cue)
{
    AActor* Attacker = GetCastActor(Cue.AttackerRole);
    AActor* Victim = GetCastActor(Cue.VictimRole);
    float Length = 0.0f;
    UClass* VillainClass = FindObject<UClass>(nullptr, TEXT("/Script/reflections.ReflectionsVillainSubsystem"));
    UObject* Villain = VillainClass && VillainClass->IsChildOf(UWorldSubsystem::StaticClass())
        ? GetWorld()->GetSubsystemBase(TSubclassOf<UWorldSubsystem>(VillainClass)) : nullptr;
    UFunction* Function = Villain ? Villain->FindFunction(TEXT("BeginConversion")) : nullptr;
    if (Function && Attacker && Victim)
    {
        // float BeginConversion(AActor* Attacker, AActor* Victim): fill the two actor params, read the float back.
        TArray<uint8, TInlineAllocator<64>> Params;
        Params.SetNumZeroed(Function->ParmsSize);
        AActor* Values[] = { Attacker, Victim };
        int32 Index = 0;
        FFloatProperty* Return = nullptr;
        bool bSignatureOk = true;
        for (TFieldIterator<FProperty> It(Function); It && (It->PropertyFlags & CPF_Parm); ++It)
        {
            if (It->PropertyFlags & CPF_ReturnParm)
            {
                Return = CastField<FFloatProperty>(*It);
            }
            else if (FObjectPropertyBase* ObjectProp = CastField<FObjectPropertyBase>(*It); ObjectProp && Index < 2)
            {
                ObjectProp->SetObjectPropertyValue_InContainer(Params.GetData(), Values[Index++]);
            }
            else
            {
                bSignatureOk = false;
            }
        }
        if (bSignatureOk && Index == 2 && Return)
        {
            // The conversion drives both bodies with its own root-motion montages: give both drivers back their
            // Anim Blueprints (no single-node takes, no montages of ours) and stop steering them.
            const AActor* Drivers[] = { DriverOf(Attacker), DriverOf(Victim) };
            for (int32 TakeIndex = Takes.Num() - 1; TakeIndex >= 0; --TakeIndex)
            {
                FPlayingTake& Take = Takes[TakeIndex];
                USkeletalMeshComponent* Mesh = Take.SingleNodeMesh.Get();
                UAnimInstance* Instance = Take.AnimInstance.Get();
                const AActor* Owner = Mesh ? Mesh->GetOwner() : (Instance ? Instance->GetOwningActor() : nullptr);
                if (!Owner || (RootOf(const_cast<AActor*>(Owner)) != Drivers[0] && RootOf(const_cast<AActor*>(Owner)) != Drivers[1]))
                {
                    continue;
                }
                if (Mesh && Take.PreviousMode == EAnimationMode::AnimationBlueprint)
                {
                    Mesh->SetPlayRate(1.0f);
                    Mesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
                }
                if (Instance && Take.Montage.IsValid())
                {
                    Instance->Montage_Stop(0.15f, Take.Montage.Get());
                }
                Takes.RemoveAt(TakeIndex);
            }
            for (FCastEntry& Entry : CastEntries)
            {
                if ((Entry.Actor.Get() == Attacker || Entry.Actor.Get() == Victim) && Entry.SteeredComponent.IsValid())
                {
                    CallBoolSetter(Entry.SteeredComponent.Get(), TEXT("SetExternallySteered"), false);
                    Entry.SteeredComponent.Reset();
                }
            }
            Villain->ProcessEvent(Function, Params.GetData());
            Length = Return->GetPropertyValue_InContainer(Params.GetData());
        }
    }
    UE_LOG(LogReflectionsCutscene, Log, TEXT("Cutscene %s: conversion %s -> %s: %.2f s."), *CurrentName.ToString(),
        Attacker ? *Attacker->GetName() : TEXT("none"), Victim ? *Victim->GetName() : TEXT("none"), Length);
    if (Length > 0.0f)
    {
        if (Cue.HoldAt >= 0.0f)
        {
            HoldAtTime = Cue.HoldAt;
            HoldExtraSeconds = FMath::Max(0.0f, (Cue.Time + Length) - Cue.HoldAt);
        }
        return;
    }
    // Refused: the victim plays a fallback take instead.
    if (!Cue.FallbackVictimTake.IsNull())
    {
        FReflectionsCutscenePerformance Take;
        Take.Role = Cue.VictimRole;
        Take.StartTime = Cue.Time;
        Take.Animation = Cue.FallbackVictimTake;
        Take.bFullBody = true;
        if (UAnimSequenceBase* Anim = Cue.FallbackVictimTake.LoadSynchronous())
        {
            Loaded.AddUnique(Anim);
            StartPerformance(Take);
        }
    }
    if (Victim)
    {
        if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
        {
            Npcs->SetInfection(Victim, EReflectionsNpcInfection::Infected, Attacker);
        }
    }
}

AActor* UReflectionsCutsceneSubsystem::FindNearestNpc(const FReflectionsCutsceneCastMember& Member) const
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Npcs)
    {
        return nullptr;
    }
    const APawn* Hero = GetHero();
    AActor* Best = nullptr;
    float BestScore = TNumericLimits<float>::Max();
    for (AActor* Npc : Npcs->GetNpcActors())
    {
        if (!Npc || Npc->IsActorBeingDestroyed() || RootOf(Npc) == Hero)
        {
            continue;
        }
        const bool bTaken = CastEntries.ContainsByPredicate([Npc](const FCastEntry& E) { return E.Actor.IsValid() && RootOf(E.Actor.Get()) == RootOf(Npc); });
        if (bTaken)
        {
            continue;
        }
        const float Distance = FVector::Dist(RootOf(Npc)->GetActorLocation(), Anchor.GetLocation());
        if (Distance > Member.SearchRadius)
        {
            continue;
        }
        const EReflectionsNpcInfection State = Npcs->GetInfection(Npc);
        if (State == EReflectionsNpcInfection::BurnedOut)
        {
            continue;
        }
        const bool bInfected = State == EReflectionsNpcInfection::Infected || State == EReflectionsNpcInfection::VillainHost;
        // Preferred kind first, then by distance.
        const float Score = Distance + ((Member.bPreferInfected != bInfected) ? 1.0e6f : 0.0f);
        if (Score < BestScore)
        {
            BestScore = Score;
            Best = Npc;
        }
    }
    return Best;
}

float UReflectionsCutsceneSubsystem::GetTotalLength() const
{
    if (!Current)
    {
        return 0.0f;
    }
    if (Current->Length > 0.0f)
    {
        return Current->Length;
    }
    if (SequenceActor)
    {
        if (const ULevelSequencePlayer* Player = SequenceActor->GetSequencePlayer())
        {
            return static_cast<float>(Player->GetDuration().AsSeconds());
        }
    }
    float End = 1.0f;
    for (const FReflectionsCutsceneLine& Line : Current->Lines) { End = FMath::Max(End, Line.StartTime + FMath::Max(Line.Duration, 3.0f)); }
    for (const FReflectionsCutsceneCard& Card : Current->Cards) { End = FMath::Max(End, Card.StartTime + Card.Duration); }
    return End + 0.5f;
}

bool UReflectionsCutsceneSubsystem::IsMenuBlocking(bool& bGameOver) const
{
    bGameOver = false;
    const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    if (!Flow)
    {
        return false;
    }
    const EReflectionsFlowScreen Screen = Flow->GetScreen();
    bGameOver = Screen == EReflectionsFlowScreen::Lose || Screen == EReflectionsFlowScreen::Victory || Screen == EReflectionsFlowScreen::Title;
    return Screen != EReflectionsFlowScreen::None;
}

// ---- Anchor and cast ---------------------------------------------------------------------------------------

bool UReflectionsCutsceneSubsystem::FindAnchor(FName AnchorName, FTransform& OutAnchor, AActor*& OutMarker) const
{
    OutMarker = nullptr;
    UWorld* World = GetWorld();
    if (!World || AnchorName.IsNone())
    {
        return false;
    }
    const FString Wanted = AnchorName.ToString();
    const FString MarkerName = FString::Printf(TEXT("CutsceneAnchor_%s"), *Wanted);
    const FName MarkerTag(*MarkerName);
    static const FName PropertyNames[] = { TEXT("AnchorName"), TEXT("CutsceneName"), TEXT("MarkerName"), TEXT("MarkerId"), TEXT("AnchorId") };

    AActor* ByName = nullptr;
    AActor* ByProperty = nullptr;
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (!Actor || Actor->IsActorBeingDestroyed())
        {
            continue;
        }
        if (Actor->Tags.Contains(MarkerTag))
        {
            OutMarker = Actor;
            break;
        }
        if (!ByName)
        {
            const FString ObjectName = Actor->GetName();
#if WITH_EDITOR
            const FString Label = Actor->GetActorLabel();
#else
            const FString Label;
#endif
            if (ObjectName.StartsWith(MarkerName, ESearchCase::IgnoreCase) || Label.StartsWith(MarkerName, ESearchCase::IgnoreCase))
            {
                ByName = Actor;
            }
        }
        if (!ByProperty)
        {
            const FString ClassName = Actor->GetClass()->GetName();
            if (ClassName.Contains(TEXT("Anchor")) || ClassName.Contains(TEXT("Marker")))
            {
                for (const FName& PropName : PropertyNames)
                {
                    const FProperty* Prop = Actor->GetClass()->FindPropertyByName(PropName);
                    if (!Prop)
                    {
                        continue;
                    }
                    FString Value;
                    if (const FNameProperty* NameProp = CastField<FNameProperty>(Prop))
                    {
                        Value = NameProp->GetPropertyValue_InContainer(Actor).ToString();
                    }
                    else if (const FStrProperty* StrProp = CastField<FStrProperty>(Prop))
                    {
                        Value = StrProp->GetPropertyValue_InContainer(Actor);
                    }
                    if (NameMatches(Value, Wanted) || NameMatches(Value, MarkerName))
                    {
                        ByProperty = Actor;
                        break;
                    }
                }
            }
        }
    }
    if (!OutMarker)
    {
        OutMarker = ByName ? ByName : ByProperty;
    }
    if (!OutMarker)
    {
        return false;
    }
    OutAnchor = OutMarker->GetActorTransform();
    OutAnchor.SetScale3D(FVector::OneVector);
    return true;
}

bool UReflectionsCutsceneSubsystem::ResolveAnchor(const UReflectionsCutsceneAsset* Asset, FName Name)
{
    const FName AnchorName = Asset->AnchorName.IsNone() ? Name : Asset->AnchorName;
    AActor* Marker = nullptr;
    FTransform Found;
    const bool bMarker = FindAnchor(AnchorName, Found, Marker);
    AnchorMarker = Marker;
    if (!bMarker)
    {
        // No marker on this map: the hero's feet and facing.
        APawn* Hero = GetHero();
        Found = FTransform(FRotator(0.0f, Hero->GetActorRotation().Yaw, 0.0f), Hero->GetActorLocation() - FVector(0.0f, 0.0f, FeetOffset(Hero)));
    }
    if (Asset->bAnchorYawOnly)
    {
        Found.SetRotation(FRotator(0.0f, Found.Rotator().Yaw, 0.0f).Quaternion());
    }
    if (Asset->bSnapAnchorToGround && bMarker)
    {
        FHitResult Hit;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(CutsceneAnchorGround), false);
        Params.AddIgnoredActor(Marker);
        if (APawn* Hero = GetHero()) { Params.AddIgnoredActor(Hero); }
        const FVector Start = Found.GetLocation() + FVector(0.0f, 0.0f, 150.0f);
        const FVector End = Found.GetLocation() - FVector(0.0f, 0.0f, 800.0f);
        if (GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params))
        {
            Found.SetLocation(Hit.ImpactPoint);
        }
    }
    Found.SetScale3D(FVector::OneVector);
    Anchor = Found;
    return bMarker;
}

AActor* UReflectionsCutsceneSubsystem::FindRoleActor(const FReflectionsCutsceneCastMember& Member) const
{
    const FString Wanted = (Member.FindTag.IsNone() ? Member.Role : Member.FindTag).ToString();
    if (Wanted.IsEmpty())
    {
        return nullptr;
    }
    const FName Tags[] = { FName(*Wanted), FName(*(TEXT("Cutscene_") + Wanted)), FName(*(TEXT("NPC_Name_") + Wanted)) };
    const APawn* Hero = GetHero();
    AActor* ByName = nullptr;
    for (TActorIterator<AActor> It(GetWorld()); It; ++It)
    {
        AActor* Actor = *It;
        if (!Actor || Actor == Hero || Actor->IsActorBeingDestroyed() || RootOf(Actor) == Hero)
        {
            continue;
        }
        for (const FName& Tag : Tags)
        {
            if (Actor->Tags.Contains(Tag))
            {
                return Actor;
            }
        }
        if (!ByName)
        {
#if WITH_EDITOR
            const FString Label = Actor->GetActorLabel();
#else
            const FString Label;
#endif
            if (Actor->GetName().Contains(Wanted) || Label.Contains(Wanted))
            {
                ByName = Actor;
            }
        }
    }
    return ByName;
}

void UReflectionsCutsceneSubsystem::SpawnCast()
{
    CastEntries.Reset();
    APawn* Hero = GetHero();
    for (const FReflectionsCutsceneCastMember& Member : Current->Cast)
    {
        FCastEntry Entry;
        Entry.Role = Member.Role;
        AActor* Actor = Member.bIsHero ? Hero : FindRoleActor(Member);
        const FTransform MarkWorld = Member.Mark * Anchor;
        if (!Actor && !Member.PersonId.IsNone())
        {
            // The real person, through the Lives system (their own look, voice and tags); it keeps them afterwards.
            Actor = SpawnPerson(GetWorld(), Member.PersonId, MarkWorld.GetLocation(), MarkWorld.Rotator().Yaw);
            if (Actor)
            {
                UE_LOG(LogReflectionsCutscene, Log, TEXT("Cutscene %s: %s spawned through Lives as %s."), *CurrentName.ToString(),
                    *Member.PersonId.ToString(), *Actor->GetName());
            }
        }
        Entry.bFoundByTag = Actor != nullptr;
        if (!Actor && Member.bFallbackToNearestNpc)
        {
            Actor = FindNearestNpc(Member);
        }
        UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
        if (!Actor && !Member.StandInArchetype.IsNone() && Npcs)
        {
            // A proper NPC (enrolled, with a crowd look) spawned on the mark.
            UClass* Look = Member.StandInClass.IsNull() ? nullptr : Member.StandInClass.LoadSynchronous();
            Actor = Npcs->SpawnNpc(Member.StandInArchetype, MarkWorld.GetLocation(), MarkWorld.Rotator().Yaw, Look);
            if (Actor)
            {
                Entry.bStandIn = true;
                Actor->Tags.AddUnique(FName(*(TEXT("Cutscene_") + Member.Role.ToString())));
            }
        }
        if (!Actor && !Member.StandInClass.IsNull())
        {
            if (UClass* Class = Member.StandInClass.LoadSynchronous())
            {
                Loaded.AddUnique(Class);
                FActorSpawnParameters Params;
                Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
                Params.ObjectFlags |= RF_Transient;
                Actor = GetWorld()->SpawnActor<AActor>(Class, MarkWorld, Params);
                if (Actor)
                {
                    Entry.bStandIn = true;
                    // Spawned at the feet mark: lift characters by their capsule.
                    Actor->SetActorLocation(MarkWorld.GetLocation() + FVector(0.0f, 0.0f, FeetOffset(Actor)), false, nullptr, ETeleportType::TeleportPhysics);
                    Actor->Tags.AddUnique(FName(*(TEXT("Cutscene_") + Member.Role.ToString())));
                }
            }
        }
        if (!Actor)
        {
            UE_LOG(LogReflectionsCutscene, Warning, TEXT("Cutscene %s: nobody to play %s."), *CurrentName.ToString(), *Member.Role.ToString());
            continue;
        }
        Entry.Actor = Actor;
        Entry.bKeep = Member.bKeepStandIn;
        if (Member.bInfectOnStart && Npcs && Npcs->GetInfection(Actor) == EReflectionsNpcInfection::None)
        {
            Npcs->SetInfection(Actor, EReflectionsNpcInfection::Infected, nullptr);
        }
        AActor* Root = Member.bIsHero ? RootOf(Actor) : DriverOf(Actor);
        if (!Member.bIsHero)
        {
            // Lives lets go of a person while this tag is on them (its own walking also uses external steering).
            Actor->Tags.AddUnique(TEXT("Lives_Hold"));
            Entry.bAddedHoldTag = true;
        }
        if (!Entry.bStandIn)
        {
            Entry.OriginalTransform = Root->GetActorTransform();
            Entry.bRestoreTransform = Member.bRestoreTransform;
            if (Member.bPlaceAtMark)
            {
                Root->SetActorLocationAndRotation(MarkWorld.GetLocation() + FVector(0.0f, 0.0f, FeetOffset(Root)),
                    FRotator(0.0f, MarkWorld.Rotator().Yaw, 0.0f), false, nullptr, ETeleportType::TeleportPhysics);
                if (APawn* Pawn = Cast<APawn>(Root); Pawn && Pawn == Hero)
                {
                    if (APlayerController* PC = GetController())
                    {
                        PC->SetControlRotation(FRotator(PC->GetControlRotation().Pitch, MarkWorld.Rotator().Yaw, 0.0f));
                    }
                }
            }
            // NPCs: someone else steers the body for now (the NPC still feels and reacts).
            if (!Member.bIsHero)
            {
                if (UObject* Npc = FindComponentByClassName(Actor, TEXT("ReflectionsNpcReactionComponent")))
                {
                    if (CallBoolSetter(Npc, TEXT("SetExternallySteered"), true))
                    {
                        Entry.SteeredComponent = Npc;
                    }
                }
                if (ACharacter* Character = Cast<ACharacter>(Root))
                {
                    if (UCharacterMovementComponent* Move = Character->GetCharacterMovement())
                    {
                        Move->StopMovementImmediately();
                    }
                }
            }
        }
        if (Member.bHidden)
        {
            Entry.bWasHidden = Actor->IsHidden();
            Entry.bHidden = true;
            Actor->SetActorHiddenInGame(true);
        }
        CastEntries.Add(Entry);
    }
    // The hero is always bindable as "Hero", even when the asset doesn't list him.
    if (!GetCastActor(TEXT("Hero")) && Hero)
    {
        FCastEntry Entry;
        Entry.Role = TEXT("Hero");
        Entry.Actor = Hero;
        Entry.OriginalTransform = Hero->GetActorTransform();
        CastEntries.Add(Entry);
    }
    ClearTheSet();
}

void UReflectionsCutsceneSubsystem::ClearTheSet()
{
    // Bystanders near the stage walk into close shots: hide every NPC that isn't cast within this radius of the
    // anchor (and hold it in place), and bring them all back exactly as they were afterwards.
    ClearedActors.Reset();
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Npcs || !Current || Current->ClearRadius <= 0.0f)
    {
        return;
    }
    TSet<AActor*> CastRoots;
    for (const FCastEntry& Entry : CastEntries)
    {
        if (AActor* Actor = Entry.Actor.Get())
        {
            CastRoots.Add(RootOf(Actor));
            CastRoots.Add(DriverOf(Actor));
            CastRoots.Add(Actor);
        }
    }
    const float RadiusSq = FMath::Square(Current->ClearRadius);
    for (AActor* Npc : Npcs->GetNpcActors())
    {
        if (!Npc || CastRoots.Contains(Npc) || CastRoots.Contains(RootOf(Npc)) || CastRoots.Contains(DriverOf(Npc)))
        {
            continue;
        }
        if (FVector::DistSquared(DriverOf(Npc)->GetActorLocation(), Anchor.GetLocation()) > RadiusSq)
        {
            continue;
        }
        TArray<AActor*> Group;
        Group.Add(Npc);
        Group.AddUnique(RootOf(Npc));
        Group.AddUnique(DriverOf(Npc));
        Npc->GetAttachedActors(Group, false, true);
        for (AActor* Member : Group)
        {
            if (Member && !Member->IsHidden())
            {
                FClearedActor Cleared;
                Cleared.Actor = Member;
                Cleared.bAddedHoldTag = !Member->Tags.Contains(TEXT("Lives_Hold"));
                ClearedActors.Add(Cleared);
                Member->SetActorHiddenInGame(true);
                if (Cleared.bAddedHoldTag)
                {
                    Member->Tags.Add(TEXT("Lives_Hold"));
                }
            }
        }
    }
    if (ClearedActors.Num() > 0)
    {
        UE_LOG(LogReflectionsCutscene, Log, TEXT("Cutscene %s: cleared %d bystander actors within %.0f m."), *CurrentName.ToString(),
            ClearedActors.Num(), Current->ClearRadius / 100.0f);
    }
}

void UReflectionsCutsceneSubsystem::RestoreTheSet()
{
    for (const FClearedActor& Cleared : ClearedActors)
    {
        if (AActor* Actor = Cleared.Actor.Get())
        {
            Actor->SetActorHiddenInGame(false);
            if (Cleared.bAddedHoldTag)
            {
                Actor->Tags.Remove(TEXT("Lives_Hold"));
            }
        }
    }
    ClearedActors.Reset();
}

// ---- Sequence ----------------------------------------------------------------------------------------------

void UReflectionsCutsceneSubsystem::StartSequence()
{
    ULevelSequence* Sequence = Current ? Current->Sequence.Get() : nullptr;
    if (!Sequence)
    {
        return;
    }
    FMovieSceneSequencePlaybackSettings Settings;
    Settings.bAutoPlay = false;
    Settings.bPauseAtEnd = true;   // hold the last frame until the hand-off
    Settings.bHideHud = true;
    Settings.bDisableMovementInput = false;  // input is handled here (and restored exactly)
    Settings.bDisableLookAtInput = false;
    Settings.FinishCompletionStateOverride = EMovieSceneCompletionModeOverride::ForceRestoreState;

    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Params.ObjectFlags |= RF_Transient;
    Params.bDeferConstruction = true;
    ALevelSequenceActor* Actor = GetWorld()->SpawnActor<ALevelSequenceActor>(Params);
    if (!Actor)
    {
        return;
    }
    Actor->PlaybackSettings = Settings;
    Actor->GetSequencePlayer()->SetPlaybackSettings(Settings);
    Actor->bOverrideInstanceData = true;
    if (UDefaultLevelSequenceInstanceData* Instance = Cast<UDefaultLevelSequenceInstanceData>(Actor->DefaultInstanceData))
    {
        // Every absolute transform in the sequence is relative to the anchor.
        Instance->TransformOriginActor = nullptr;
        Instance->TransformOrigin = Anchor;
    }
    Actor->SetSequence(Sequence);
    Actor->InitializePlayer();
    Actor->FinishSpawning(FTransform::Identity);
    SequenceActor = Actor;

    for (const FCastEntry& Entry : CastEntries)
    {
        // Only roles the sequence actually animates (most cast members are driven by takes, not tracks).
        AActor* CastActor = Entry.Actor.Get();
        if (CastActor && Sequence->FindBindingsByTag(Entry.Role).Num() > 0)
        {
            Actor->SetBindingByTag(Entry.Role, { DriverOf(CastActor) }, false);
        }
    }
    if (ULevelSequencePlayer* Player = Actor->GetSequencePlayer())
    {
        Player->Play();
    }
}

void UReflectionsCutsceneSubsystem::StartPerformance(const FReflectionsCutscenePerformance& Take)
{
    UAnimSequenceBase* Anim = Take.Animation.Get();
    AActor* Actor = GetCastActor(Take.Role);
    if (!Anim || !Actor)
    {
        return;
    }
    AActor* Root = DriverOf(Actor);
    if (!Take.FaceRole.IsNone())
    {
        if (AActor* Target = GetCastActor(Take.FaceRole))
        {
            const FVector To = DriverOf(Target)->GetActorLocation() - Root->GetActorLocation();
            if (To.SizeSquared2D() > 1.0f)
            {
                Root->SetActorRotation(FRotator(0.0f, To.Rotation().Yaw, 0.0f), ETeleportType::TeleportPhysics);
            }
        }
    }

    // The first mesh in the actor's hierarchy that uses the clip's skeleton (the hidden driver for MetaHumans).
    TArray<AActor*> Hierarchy;
    Hierarchy.Add(Root);
    Root->GetAttachedActors(Hierarchy, false, true);
    // The look actor may follow its driver without being attached to it.
    if (!Hierarchy.Contains(Actor))
    {
        Hierarchy.Add(Actor);
        Actor->GetAttachedActors(Hierarchy, false, true);
    }
    const USkeleton* Skeleton = Anim->GetSkeleton();
    USkeletalMeshComponent* Best = nullptr;
    for (AActor* Candidate : Hierarchy)
    {
        TInlineComponentArray<USkeletalMeshComponent*> Meshes(Candidate);
        for (USkeletalMeshComponent* Mesh : Meshes)
        {
            const USkeletalMesh* MeshAsset = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
            if (!MeshAsset || !Skeleton)
            {
                continue;
            }
            if (MeshAsset->GetSkeleton() == Skeleton || Skeleton->IsCompatibleMesh(MeshAsset))
            {
                Best = Mesh;
                break;
            }
        }
        if (Best)
        {
            break;
        }
    }
    if (!Best)
    {
        UE_LOG(LogReflectionsCutscene, Warning, TEXT("Cutscene %s: no mesh on %s uses %s's skeleton."), *CurrentName.ToString(), *Actor->GetName(), *Anim->GetName());
        return;
    }
    // NPCs: whole-body clips go through the NPC system's own walker playback (the visible crowd MetaHuman follows its
    // hidden walker). Swapping a crowd body's Anim Blueprint for a single clip is what crashed the game today.
    UObject* NpcComponent = Take.Role == TEXT("Hero") ? nullptr : FindComponentByClassName(Actor, TEXT("ReflectionsNpcReactionComponent"));
    if (UReflectionsNpcReactionComponent* Npc = Cast<UReflectionsNpcReactionComponent>(NpcComponent))
    {
        if (Npc->PlayOnWalker(Anim, FMath::Max(Take.PlayRate, 0.01f)))
        {
            UE_LOG(LogReflectionsCutscene, Log, TEXT("Cutscene %s: %s plays %s on its walker."), *CurrentName.ToString(), *Take.Role.ToString(), *Anim->GetName());
            return;
        }
    }
    const bool bNpcBody = NpcComponent && Best->GetOwner() != DriverOf(Actor);

    UAnimInstance* AnimInstance = Best->GetAnimInstance();
    UAnimMontage* Montage = nullptr;
    if ((!Take.bFullBody || bNpcBody) && AnimInstance && Best->GetAnimationMode() == EAnimationMode::AnimationBlueprint)
    {
        Montage = AnimInstance->PlaySlotAnimationAsDynamicMontage(Anim, Take.Slot, Take.BlendIn, Take.BlendOut,
            FMath::Max(Take.PlayRate, 0.01f), FMath::Max(Take.LoopCount, 1));
    }
    FPlayingTake Playing;
    if (Montage)
    {
        Playing.AnimInstance = AnimInstance;
        Playing.Montage = Montage;
    }
    else if (bNpcBody)
    {
        UE_LOG(LogReflectionsCutscene, Warning, TEXT("Cutscene %s: %s skipped on %s (never swap a crowd body's Anim Blueprint)."),
            *CurrentName.ToString(), *Anim->GetName(), *Best->GetName());
        return;
    }
    else
    {
        // No slot for it (a MetaHuman face, a mesh without an Anim Blueprint): play it single-node and put the
        // Anim Blueprint back afterwards. The face's post-process graph (RigLogic) still runs on top.
        const bool bAlreadySingle = Takes.ContainsByPredicate([Best](const FPlayingTake& T) { return T.SingleNodeMesh.Get() == Best; });
        if (!bAlreadySingle)
        {
            Playing.SingleNodeMesh = Best;
            Playing.PreviousMode = Best->GetAnimationMode();
            Playing.PreviousClass = Best->GetAnimClass();
        }
        Best->PlayAnimation(Anim, Take.LoopCount > 1);
        Best->SetPlayRate(FMath::Max(Take.PlayRate, 0.01f));
    }
    Takes.Add(Playing);
    UE_LOG(LogReflectionsCutscene, Log, TEXT("Cutscene %s: %s plays %s on %s (%s)."), *CurrentName.ToString(), *Take.Role.ToString(),
        *Anim->GetName(), *Best->GetName(), Montage ? TEXT("montage") : TEXT("single node"));
}

void UReflectionsCutsceneSubsystem::StartLine(const FReflectionsCutsceneLine& Line)
{
    USoundBase* Voice = Line.Voice.Get();
    float Duration = Line.Duration;
    if (Duration <= 0.0f)
    {
        Duration = Voice && Voice->GetDuration() < 60.0f ? Voice->GetDuration() + 0.35f : 3.0f;
    }
    SubtitleSpeaker = Line.Speaker;
    SubtitleText = Line.Text;
    SubtitleStart = Elapsed;
    SubtitleEnd = Elapsed + Duration;

    if (VoiceAudio)
    {
        VoiceAudio->Stop();
        VoiceAudio = nullptr;
    }
    if (!Voice)
    {
        return;
    }
    // Cutscene voices are dialogue at a clear level (the cues have no attenuation), so they play 2D. The waves carry
    // their own subtitles for gameplay barks; the cutscene shows its own, so the engine's are suppressed here.
    VoiceAudio = UGameplayStatics::CreateSound2D(this, Voice, 1.0f, 1.0f, 0.0f, nullptr, false, true);
    if (VoiceAudio)
    {
        VoiceAudio->bSuppressSubtitles = true;
        VoiceAudio->Play();
    }
}

// ---- Control -----------------------------------------------------------------------------------------------

APlayerController* UReflectionsCutsceneSubsystem::GetController() const
{
    UWorld* World = GetWorld();
    return World ? World->GetFirstPlayerController() : nullptr;
}

APawn* UReflectionsCutsceneSubsystem::GetHero() const
{
    const APlayerController* PC = GetController();
    return PC ? PC->GetPawn() : nullptr;
}

void UReflectionsCutsceneSubsystem::BeginControlTakeover()
{
    APlayerController* PC = GetController();
    APawn* Hero = GetHero();
    TakenController = PC;
    TakenHero = Hero;
    if (!PC || !Hero)
    {
        return;
    }
    if (UGameViewportClient* Viewport = GetWorld()->GetGameViewport())
    {
        bSavedIgnoreViewportInput = Viewport->IgnoreInput();
        Viewport->SetIgnoreInput(true);
    }
    OriginalViewTarget = PC->GetViewTarget();
    PC->FlushPressedKeys();
    PC->SetIgnoreMoveInput(true);
    PC->SetIgnoreLookInput(true);
    Hero->ConsumeMovementInputVector();
    if (ACharacter* Character = Cast<ACharacter>(Hero))
    {
        if (UCharacterMovementComponent* Move = Character->GetCharacterMovement())
        {
            Move->StopMovementImmediately();
        }
    }
    bSavedCanBeDamaged = Hero->CanBeDamaged();
    if (Current && Current->bHeroInvulnerable)
    {
        Hero->SetCanBeDamaged(false);
    }
    // The spell driver re-asserts its aim pose and casts on the body every tick; it rests while a cutscene plays.
    PausedDriver.Reset();
    if (UActorComponent* Driver = Cast<UActorComponent>(FindComponentByClassName(Hero, TEXT("ReflectionsSampleSpellDriver"))))
    {
        if (Driver->IsComponentTickEnabled())
        {
            Driver->SetComponentTickEnabled(false);
            PausedDriver = Driver;
        }
    }
    bTookControl = true;
}

void UReflectionsCutsceneSubsystem::EndControlTakeover()
{
    if (!bTookControl)
    {
        return;
    }
    bTookControl = false;
    APlayerController* PC = TakenController.Get();
    APawn* Hero = TakenHero.Get();
    // A game-flow menu (lose, victory) owns input now: leave its UI-only mode alone.
    bool bGameOver = false;
    if (!IsMenuBlocking(bGameOver))
    {
        if (UGameViewportClient* Viewport = GetWorld() ? GetWorld()->GetGameViewport() : nullptr)
        {
            Viewport->SetIgnoreInput(bSavedIgnoreViewportInput);
        }
    }
    if (PC)
    {
        PC->FlushPressedKeys();
        PC->SetIgnoreMoveInput(false);
        PC->SetIgnoreLookInput(false);
    }
    if (Hero)
    {
        Hero->SetCanBeDamaged(bSavedCanBeDamaged);
    }
    if (UActorComponent* Driver = PausedDriver.Get())
    {
        Driver->SetComponentTickEnabled(true);
    }
    PausedDriver.Reset();
}

void UReflectionsCutsceneSubsystem::Cleanup(bool bBlendCamera)
{
    if (!bActive)
    {
        return;
    }
    const FName Name = CurrentName;
    const bool bWasSkipped = bSkipped;
    // A scene that ends on black (the Ending) cuts under the black and lifts it afterwards, like a skip.
    const bool bEndedBlack = GetBlackAlpha() > 0.5f;
    if (bEndedBlack)
    {
        bBlendCamera = false;
    }

    // Body takes blend out.
    for (const FPlayingTake& Take : Takes)
    {
        if (UAnimInstance* Instance = Take.AnimInstance.Get())
        {
            if (UAnimMontage* Montage = Take.Montage.Get())
            {
                Instance->Montage_Stop(bBlendCamera ? 0.35f : 0.1f, Montage);
            }
        }
        if (USkeletalMeshComponent* Mesh = Take.SingleNodeMesh.Get())
        {
            Mesh->SetPlayRate(1.0f);
            if (Take.PreviousMode == EAnimationMode::AnimationBlueprint)
            {
                Mesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
                if (UClass* PreviousClass = Take.PreviousClass.Get(); PreviousClass && Mesh->GetAnimClass() != PreviousClass)
                {
                    Mesh->SetAnimInstanceClass(PreviousClass);
                }
            }
            else
            {
                Mesh->Stop();
            }
        }
    }
    Takes.Reset();
    if (VoiceAudio)
    {
        VoiceAudio->FadeOut(0.25f, 0.0f);
        VoiceAudio = nullptr;
    }
    if (MusicAudio)
    {
        MusicAudio->FadeOut(1.5f, 0.0f);
        MusicAudio = nullptr;
    }

    // The sequence restores what it animated; spawnable cameras go with it.
    if (SequenceActor)
    {
        if (ULevelSequencePlayer* Player = SequenceActor->GetSequencePlayer())
        {
            Player->Stop();
        }
        SequenceActor->Destroy();
        SequenceActor = nullptr;
    }

    for (const FCastEntry& Entry : CastEntries)
    {
        AActor* Actor = Entry.Actor.Get();
        if (!Actor)
        {
            continue;
        }
        if (Entry.bStandIn && !Entry.bKeep)
        {
            AActor* Root = RootOf(Actor);
            if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
            {
                Npcs->ReleaseActor(Actor);
            }
            TArray<AActor*> Attached;
            Root->GetAttachedActors(Attached, true, true);
            for (AActor* Child : Attached)
            {
                Child->Destroy();
            }
            Root->Destroy();
            continue;
        }
        if (Entry.bHidden)
        {
            Actor->SetActorHiddenInGame(Entry.bWasHidden);
        }
        if (Entry.bRestoreTransform)
        {
            // Same actor the transform was captured from (the NPC's locomotion driver).
            (Entry.Role == TEXT("Hero") ? RootOf(Actor) : DriverOf(Actor))->SetActorTransform(Entry.OriginalTransform, false, nullptr, ETeleportType::TeleportPhysics);
        }
        if (UObject* Npc = Entry.SteeredComponent.Get())
        {
            CallBoolSetter(Npc, TEXT("SetExternallySteered"), false);
        }
        if (Entry.bAddedHoldTag)
        {
            Actor->Tags.Remove(TEXT("Lives_Hold"));
        }
    }
    CastEntries.Reset();
    RestoreTheSet();

    // Camera back to the hero: from where the last shot was, onto a gameplay camera pointing along his facing.
    APlayerController* PC = TakenController.Get();
    APawn* Hero = TakenHero.Get();
    if (PC && Hero)
    {
        if (Current && Current->bHandOffBehindHero)
        {
            PC->SetControlRotation(FRotator(Current->HandOffPitch, Hero->GetActorRotation().Yaw, 0.0f));
        }
        // Back to the view target from before the cutscene (the gameplay camera system's), never to the bare pawn:
        // with GameplayCameras a pawn view target falls back to its eye point (the "camera at floor level" bug).
        AActor* Gameplay = OriginalViewTarget.Get();
        if (!Gameplay)
        {
            Gameplay = Hero;
        }
        const float Blend = Current ? Current->HandOffBlendSeconds : 0.0f;
        if (bBlendCamera && Blend > 0.0f && bHaveLastView)
        {
            FActorSpawnParameters Params;
            Params.ObjectFlags |= RF_Transient;
            Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            HandOffCamera = GetWorld()->SpawnActor<ACameraActor>(LastView.Location, LastView.Rotation, Params);
            if (HandOffCamera)
            {
                if (UCameraComponent* Camera = HandOffCamera->GetCameraComponent())
                {
                    Camera->SetFieldOfView(LastView.FOV);
                    Camera->SetConstraintAspectRatio(false);
                }
                PC->SetViewTarget(HandOffCamera);
                PC->SetViewTargetWithBlend(Gameplay, Blend, EViewTargetBlendFunction::VTBlend_EaseInOut, 2.0f);
                HandOffBlendLeft = Blend + 0.1f;
            }
            else if (PC->GetViewTarget() != Gameplay)
            {
                PC->SetViewTarget(Gameplay);
            }
        }
        else
        {
            // Sequencer's camera-cut track has already restored the view target; only fix it if it didn't.
            if (PC->GetViewTarget() != Gameplay)
            {
                PC->SetViewTarget(Gameplay);
            }
            if (PC->PlayerCameraManager)
            {
                PC->PlayerCameraManager->SetGameCameraCutThisFrame();
            }
        }
    }

    EndControlTakeover();
    HideOtherLayers(false);
    SubtitleText = FText::GetEmpty();
    SubtitleSpeaker = FText::GetEmpty();
    SubtitleEnd = -100.0f;
    SkipHeld = 0.0f;
    bSkipDown = false;
    bActive = false;
    bEnding = false;
    // After a skip, lift the black over the outro.
    EndFadeClock = (bWasSkipped || bEndedBlack) ? 0.0f : 100.0f;
    Played.Add(Name);
    if (FSlateApplication::IsInitialized() && InputProcessor.IsValid())
    {
        FSlateApplication::Get().UnregisterInputPreProcessor(InputProcessor);
        InputProcessor.Reset();
    }
    UE_LOG(LogReflectionsCutscene, Log, TEXT("Cutscene %s finished%s; control returned."), *Name.ToString(), bWasSkipped ? TEXT(" (skipped)") : TEXT(""));
    if (!bSilentTeardown)
    {
        NotifyQuests(Name);
        OnCutsceneFinished.Broadcast(Name, bWasSkipped);
    }
}

void UReflectionsCutsceneSubsystem::NotifyQuests(FName Name)
{
    // Quest steps can wait on "CutsceneDone <Name>": UReflectionsQuestSubsystem::NotifyEvent(FName, FName), by name.
    UObject* Quests = FindSubsystemByPath(GetWorld(), TEXT("/Script/reflections.ReflectionsQuestSubsystem"));
    UFunction* Function = Quests ? Quests->FindFunction(TEXT("NotifyEvent")) : nullptr;
    if (!Function)
    {
        return;
    }
    TArray<uint8, TInlineAllocator<64>> Params;
    Params.SetNumZeroed(Function->ParmsSize);
    const FName Values[] = { TEXT("CutsceneDone"), Name };
    int32 Index = 0;
    for (TFieldIterator<FProperty> It(Function); It && (It->PropertyFlags & CPF_Parm) && !(It->PropertyFlags & CPF_ReturnParm); ++It)
    {
        if (FNameProperty* NameProp = CastField<FNameProperty>(*It); NameProp && Index < 2)
        {
            NameProp->SetPropertyValue_InContainer(Params.GetData(), Values[Index++]);
        }
        else
        {
            return;  // unexpected signature: don't guess
        }
    }
    if (Index == 2)
    {
        Quests->ProcessEvent(Function, Params.GetData());
    }
}

// ---- Overlay -----------------------------------------------------------------------------------------------

void UReflectionsCutsceneSubsystem::ShowOverlay()
{
    UGameViewportClient* Viewport = GetWorld()->GetGameViewport();
    if (!Viewport)
    {
        return;
    }
    if (!Overlay.IsValid())
    {
        Overlay = SNew(SReflectionsCutsceneOverlay).Owner(this);
        OverlayRoot = SNew(SWeakWidget).PossiblyNullContent(Overlay);
        // Above every HUD layer (spell 20 .. dialogue 50), below the game-flow menus (1000).
        Viewport->AddViewportWidgetContent(OverlayRoot.ToSharedRef(), 900);
    }
    if (FSlateApplication::IsInitialized() && !InputProcessor.IsValid())
    {
        InputProcessor = MakeShared<FReflectionsCutsceneInput>(this);
        FSlateApplication::Get().RegisterInputPreProcessor(InputProcessor);
    }
}

void UReflectionsCutsceneSubsystem::RemoveOverlay()
{
    HideOtherLayers(false);
    if (OverlayRoot.IsValid())
    {
        if (UWorld* World = GetWorld())
        {
            if (UGameViewportClient* Viewport = World->GetGameViewport())
            {
                Viewport->RemoveViewportWidgetContent(OverlayRoot.ToSharedRef());
            }
        }
    }
    OverlayRoot.Reset();
    Overlay.Reset();
    if (FSlateApplication::IsInitialized() && InputProcessor.IsValid())
    {
        FSlateApplication::Get().UnregisterInputPreProcessor(InputProcessor);
    }
    InputProcessor.Reset();
}

void UReflectionsCutsceneSubsystem::HideOtherLayers(bool bHide)
{
    if (!bHide)
    {
        for (const FHiddenLayer& Layer : HiddenLayers)
        {
            if (TSharedPtr<SWidget> Widget = Layer.Widget.Pin())
            {
                Widget->SetRenderOpacity(Layer.Opacity);
            }
        }
        HiddenLayers.Reset();
        bLayersHidden = false;
        return;
    }
    if (!OverlayRoot.IsValid())
    {
        return;
    }
    // Every other layer in the viewport overlay (HUDs, dialogue, tips) goes transparent. Opacity is a plain value,
    // so it restores exactly, without touching anyone's visibility bindings.
    TSharedPtr<SWidget> Parent = OverlayRoot->GetParentWidget();
    FChildren* Children = Parent.IsValid() ? Parent->GetChildren() : nullptr;
    if (!Children)
    {
        return;
    }
    for (int32 Index = 0; Index < Children->Num(); ++Index)
    {
        TSharedRef<SWidget> Child = Children->GetChildAt(Index);
        if (Child == OverlayRoot.ToSharedRef())
        {
            continue;
        }
        const bool bKnown = HiddenLayers.ContainsByPredicate([&Child](const FHiddenLayer& Layer) { return Layer.Widget.Pin() == Child; });
        if (!bKnown)
        {
            FHiddenLayer Layer;
            Layer.Widget = Child;
            Layer.Opacity = Child->GetRenderOpacity();
            HiddenLayers.Add(Layer);
            Child->SetRenderOpacity(0.0f);
        }
    }
    bLayersHidden = true;
}

// ---- Overlay state -----------------------------------------------------------------------------------------

float UReflectionsCutsceneSubsystem::GetLetterboxAspect() const
{
    return Current ? Current->LetterboxAspect : 2.39f;
}

float UReflectionsCutsceneSubsystem::GetBlackAlpha() const
{
    float Black = 0.0f;
    if (Current && bActive)
    {
        // The latest fade that has started decides.
        const FReflectionsCutsceneFade* Latest = nullptr;
        for (const FReflectionsCutsceneFade& Fade : Current->Fades)
        {
            if (Fade.StartTime <= Elapsed && (!Latest || Fade.StartTime >= Latest->StartTime))
            {
                Latest = &Fade;
            }
        }
        if (Latest)
        {
            const float T = Latest->Duration > 0.0f ? FMath::Clamp((Elapsed - Latest->StartTime) / Latest->Duration, 0.0f, 1.0f) : 1.0f;
            Black = FMath::Lerp(Latest->From, Latest->To, FMath::SmoothStep(0.0f, 1.0f, T));
        }
        if (bEnding)
        {
            const float FadeSeconds = FMath::Max(Current->SkipFadeSeconds, 0.05f);
            Black = FMath::Max(Black, FMath::Clamp(EndFadeClock / FadeSeconds, 0.0f, 1.0f));
        }
    }
    else if (!bActive && OverlayRoot.IsValid())
    {
        // Outro after a skip: black lifts over half a second.
        Black = 1.0f - FMath::Clamp(EndFadeClock / 0.5f, 0.0f, 1.0f);
    }
    return FMath::Clamp(Black, 0.0f, 1.0f);
}

float UReflectionsCutsceneSubsystem::GetSkipPromptAlpha() const
{
    if (!bActive || !Current || !Current->bSkippable || bEnding)
    {
        return 0.0f;
    }
    // Shown briefly at the start, and again for 3 s after any input.
    const float Since = RealClock - SkipPromptShownAt;
    const float Input = Since < 3.0f ? 1.0f : FMath::Clamp(1.0f - (Since - 3.0f) / 0.6f, 0.0f, 1.0f);
    const float Start = RealClock > 1.2f && RealClock < 5.0f ? FMath::Min(1.0f, FMath::Min((RealClock - 1.2f) / 0.5f, (5.0f - RealClock) / 0.6f)) : 0.0f;
    return FMath::Max(FMath::Max(Input, Start), SkipHeld > 0.0f ? 1.0f : 0.0f);
}

bool UReflectionsCutsceneSubsystem::IsUsingGamepad() const
{
    return bGamepad;
}

float UReflectionsCutsceneSubsystem::GetSubtitleAlpha() const
{
    if (SubtitleText.IsEmpty())
    {
        return 0.0f;
    }
    const float In = FMath::Clamp((Elapsed - SubtitleStart) / LineFadeSeconds, 0.0f, 1.0f);
    const float Out = FMath::Clamp((SubtitleEnd - Elapsed) / LineFadeSeconds, 0.0f, 1.0f);
    return FMath::Min(In, Out);
}

bool UReflectionsCutsceneSubsystem::GetCard(int32& OutStyle, FText& OutText, FText& OutSubText, float& OutAlpha) const
{
    if (!Current || !bActive)
    {
        return false;
    }
    for (const FReflectionsCutsceneCard& Card : Current->Cards)
    {
        if (!Card.OnlyInSide.IsNone() && Card.OnlyInSide != CurrentSide)
        {
            continue;
        }
        if (Elapsed >= Card.StartTime && Elapsed < Card.StartTime + Card.Duration)
        {
            const float Fade = FMath::Min(CardFadeSeconds, Card.Duration * 0.5f);
            const float In = FMath::Clamp((Elapsed - Card.StartTime) / FMath::Max(Fade, 0.01f), 0.0f, 1.0f);
            const float Out = FMath::Clamp((Card.StartTime + Card.Duration - Elapsed) / FMath::Max(Fade, 0.01f), 0.0f, 1.0f);
            OutStyle = static_cast<int32>(Card.Style);
            OutText = Card.Text;
            OutSubText = Card.SubText;
            OutAlpha = FMath::SmoothStep(0.0f, 1.0f, FMath::Min(In, Out)) * (bEnding ? 1.0f - FMath::Clamp(EndFadeClock / 0.3f, 0.0f, 1.0f) : 1.0f);
            return true;
        }
    }
    return false;
}

void UReflectionsCutsceneSubsystem::NotifySkipKey(bool bDown, bool bInGamepad)
{
    bGamepad = bInGamepad;
    bSkipDown = bDown && bActive;
    if (bDown)
    {
        SkipPromptShownAt = RealClock;
    }
}

void UReflectionsCutsceneSubsystem::NotifyAnyInput(bool bInGamepad)
{
    bGamepad = bInGamepad;
    if (bActive)
    {
        SkipPromptShownAt = RealClock;
    }
}

// ---- Console -----------------------------------------------------------------------------------------------

static FAutoConsoleCommandWithWorldAndArgs GCutscenePlayCommand(
    TEXT("Cutscene.Play"),
    TEXT("Cutscene.Play <Name>: plays /Game/Cinematics/Data/DA_Cutscene_<Name>."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (UReflectionsCutsceneSubsystem* Sub = World ? World->GetSubsystem<UReflectionsCutsceneSubsystem>() : nullptr)
        {
            ReflectionsCutscene::bForceNextPlay = true;
            const bool bOk = Args.Num() > 0 && Sub->PlayCutscene(FName(*Args[0]));
            ReflectionsCutscene::bForceNextPlay = false;
            UE_LOG(LogReflectionsCutscene, Display, TEXT("Cutscene.Play %s: %s"), Args.Num() > 0 ? *Args[0] : TEXT("?"), bOk ? TEXT("started") : TEXT("not started"));
        }
    }));

static FAutoConsoleCommandWithWorldAndArgs GCutsceneSkipCommand(
    TEXT("Cutscene.Skip"),
    TEXT("Skips the cutscene that is playing."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (UReflectionsCutsceneSubsystem* Sub = World ? World->GetSubsystem<UReflectionsCutsceneSubsystem>() : nullptr)
        {
            Sub->SkipCutscene();
        }
    }));

static FAutoConsoleCommandWithWorldAndArgs GCutsceneStatusCommand(
    TEXT("Cutscene.Status"),
    TEXT("Logs the cutscene state and where each anchor resolves."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (UReflectionsCutsceneSubsystem* Sub = World ? World->GetSubsystem<UReflectionsCutsceneSubsystem>() : nullptr)
        {
            UE_LOG(LogReflectionsCutscene, Display, TEXT("Cutscene: playing=%d name=%s t=%.2f"), Sub->IsCutscenePlaying() ? 1 : 0,
                *Sub->GetCurrentCutscene().ToString(), Sub->GetCutsceneTime());
            for (const FString& Arg : Args)
            {
                FTransform Found; AActor* Marker = nullptr;
                const bool bFound = Sub->FindAnchor(FName(*Arg), Found, Marker);
                UE_LOG(LogReflectionsCutscene, Display, TEXT("  anchor %s: %s %s"), *Arg, bFound ? *Marker->GetName() : TEXT("none (hero fallback)"),
                    bFound ? *Found.GetLocation().ToString() : TEXT(""));
            }
        }
    }));
