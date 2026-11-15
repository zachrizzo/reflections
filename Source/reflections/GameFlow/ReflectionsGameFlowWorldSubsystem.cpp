#include "GameFlow/ReflectionsGameFlowWorldSubsystem.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFlow/ReflectionsGameFlowSlate.h"
#include "GameFlow/ReflectionsGameFlowSubsystem.h"
#include "GameFlow/ReflectionsGameFlowText.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "NPC/ReflectionsReputationSubsystem.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundBase.h"
#include "UObject/Package.h"
#include "Worlds/ReflectionsWorldJumpComponent.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"
#include "Worlds/ReflectionsWorldPickups.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsGameFlowWorld, Log, All);

#define LOCTEXT_NAMESPACE "ReflectionsGameFlow"
#define FLOWTEXT(Key, Default) ReflectionsFlowText::Get(TEXT(Key), LOCTEXT(Key, Default))

static TAutoConsoleVariable<int32> CVarGameFlowEnabled(
    TEXT("GameFlow.Enabled"), 1,
    TEXT("0 turns the game-flow layer off in newly started maps (no HUD, menus, tips or checkpoints)."));

static TAutoConsoleVariable<int32> CVarGameFlowTitleInPIE(
    TEXT("GameFlow.TitleInPIE"), 0,
    TEXT("1 shows the title screen when PIE starts. Packaged and -game builds always show it."));

static TAutoConsoleVariable<int32> CVarGameFlowTips(
    TEXT("GameFlow.Tips"), 1,
    TEXT("0 hides the one-time tutorial tips."));

static TAutoConsoleVariable<int32> CVarGameFlowDeathScreen(
    TEXT("GameFlow.DeathScreen"), 1,
    TEXT("1 shows the death screen (respawn / load) when the hero falls; 0 lets the driver respawn on its timer."));

// ---- Calls into other owners' components by name (no compile dependency) ----------------------------------

namespace ReflectionsFlow
{
    static UClass* FindGameClass(const TCHAR* Name)
    {
        return FindObject<UClass>(nullptr, *FString::Printf(TEXT("/Script/reflections.%s"), Name));
    }

    template <typename TProperty, typename TValue>
    static bool CallGetter(UObject* Object, FName Name, TValue& Out)
    {
        UFunction* Function = Object ? Object->FindFunction(Name) : nullptr;
        if (!Function || Function->NumParms != 1)
        {
            return false;
        }
        TProperty* Return = CastField<TProperty>(Function->GetReturnProperty());
        if (!Return)
        {
            return false;
        }
        uint8* Params = static_cast<uint8*>(FMemory_Alloca_Aligned(Function->ParmsSize, Function->GetMinAlignment()));
        FMemory::Memzero(Params, Function->ParmsSize);
        Object->ProcessEvent(Function, Params);
        Out = Return->GetPropertyValue_InContainer(Params);
        return true;
    }

    static bool CallBool(UObject* Object, FName Name, bool& Out) { return CallGetter<FBoolProperty>(Object, Name, Out); }
    static bool CallFloat(UObject* Object, FName Name, float& Out) { return CallGetter<FFloatProperty>(Object, Name, Out); }

    /** Calls a function whose only argument is a float (SpendMagic). */
    static bool CallWithFloat(UObject* Object, FName Name, float Value)
    {
        UFunction* Function = Object ? Object->FindFunction(Name) : nullptr;
        if (!Function)
        {
            return false;
        }
        FFloatProperty* Param = nullptr;
        int32 Args = 0;
        for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
        {
            if (!It->HasAnyPropertyFlags(CPF_ReturnParm))
            {
                ++Args;
                Param = CastField<FFloatProperty>(*It);
            }
        }
        if (Args != 1 || !Param)
        {
            return false;
        }
        uint8* Params = static_cast<uint8*>(FMemory_Alloca_Aligned(Function->ParmsSize, Function->GetMinAlignment()));
        FMemory::Memzero(Params, Function->ParmsSize);
        Param->SetPropertyValue_InContainer(Params, Value);
        Object->ProcessEvent(Function, Params);
        return true;
    }

    static bool CallNoArgs(UObject* Object, FName Name)
    {
        UFunction* Function = Object ? Object->FindFunction(Name) : nullptr;
        if (!Function)
        {
            return false;
        }
        for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
        {
            if (!It->HasAnyPropertyFlags(CPF_ReturnParm))
            {
                return false;  // it takes arguments: not the function we agreed on
            }
        }
        uint8* Params = static_cast<uint8*>(FMemory_Alloca_Aligned(FMath::Max(1, static_cast<int32>(Function->ParmsSize)), Function->GetMinAlignment()));
        FMemory::Memzero(Params, Function->ParmsSize);
        Object->ProcessEvent(Function, Params);
        return true;
    }


    static bool CallWithTransform(UObject* Object, FName Name, const FTransform& Transform)
    {
        UFunction* Function = Object ? Object->FindFunction(Name) : nullptr;
        if (!Function || Function->NumParms != 1)
        {
            return false;
        }
        FStructProperty* Param = nullptr;
        for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
        {
            FStructProperty* Struct = CastField<FStructProperty>(*It);
            if (Struct && Struct->Struct == TBaseStructure<FTransform>::Get() && !It->HasAnyPropertyFlags(CPF_ReturnParm))
            {
                Param = Struct;
            }
        }
        if (!Param)
        {
            return false;
        }
        uint8* Params = static_cast<uint8*>(FMemory_Alloca_Aligned(Function->ParmsSize, Function->GetMinAlignment()));
        FMemory::Memzero(Params, Function->ParmsSize);
        Param->InitializeValue_InContainer(Params);
        *Param->ContainerPtrToValuePtr<FTransform>(Params) = Transform;
        Object->ProcessEvent(Function, Params);
        Param->DestroyValue_InContainer(Params);
        return true;
    }

    static FString MapPathOf(const UWorld* World)
    {
        return World ? UWorld::RemovePIEPrefix(World->GetOutermost()->GetName()) : FString();
    }
}

// ---- Lifetime ----------------------------------------------------------------------------------------------

UReflectionsGameFlowWorldSubsystem* UReflectionsGameFlowWorldSubsystem::Get(const UObject* WorldContext)
{
    UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    return World ? World->GetSubsystem<UReflectionsGameFlowWorldSubsystem>() : nullptr;
}

bool UReflectionsGameFlowWorldSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UReflectionsGameFlowWorldSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsGameFlowWorldSubsystem, STATGROUP_Tickables);
}

void UReflectionsGameFlowWorldSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    bBegunPlay = CVarGameFlowEnabled.GetValueOnGameThread() != 0;
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        Flow->PruneStaleHosts();
        Flow->bTravelPending = false;
    }
}

void UReflectionsGameFlowWorldSubsystem::Deinitialize()
{
    if (UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this))
    {
        Progress->OnWorldChanged.RemoveAll(this);
        Progress->OnPagesChanged.RemoveAll(this);
    }
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        Flow->OnInfectionChanged.RemoveAll(this);
    }
    for (const FWatchedPickup& Watched : WatchedPickups)
    {
        if (AReflectionsWorldPickup* Pickup = Watched.Actor.Get())
        {
            Pickup->OnPickedUp.RemoveAll(this);
        }
    }
    if (APlayerController* PC = Controller.Get(); PC && PauseInput)
    {
        PC->PopInputComponent(PauseInput);
    }
    RemoveWidgets();
    Super::Deinitialize();
}

void UReflectionsGameFlowWorldSubsystem::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (!bBegunPlay)
    {
        return;
    }
    // Menus pause the world, so keep UI clocks on real time.
    const float RealDelta = FMath::Min(static_cast<float>(FApp::GetDeltaTime()), 0.1f);
    Clock += RealDelta;

    EnsureController();
    if (!Controller.IsValid())
    {
        return;
    }
    if (!bStartHandled && Pawn.IsValid())
    {
        HandleStartAction();
    }
    if (StartHeldSince >= 0.0 && !bStartHoldConsumed && FPlatformTime::Seconds() - StartHeldSince >= 0.8)
    {
        APlayerController* PC = Controller.Get();
        const bool bStillHeld = PC && PC->IsInputKeyDown(EKeys::Gamepad_Special_Right);
        if (!bStillHeld || IsMenuOpen() || UGameplayStatics::IsGamePaused(this))
        {
            StartHeldSince = -1.0;  // released unseen, or another overlay took the input
        }
        else
        {
            bStartHoldConsumed = true;
            RequestQuickSave();
        }
    }
    if (bRestorePending && Pawn.IsValid())
    {
        bRestorePending = false;
        if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
        {
            ApplyCheckpoint(Flow->GetCheckpoint());
        }
        BeginPlaying();
    }

    if (UObject* Crafting = FindPawnComponent(TEXT("ReflectionsSpellCraftingComponent")))
    {
        bool bOpen = false;
        ReflectionsFlow::CallBool(Crafting, TEXT("IsCraftingScreenOpen"), bOpen);
        bCraftingOpen = bOpen;
    }
    else
    {
        bCraftingOpen = false;
    }

    if (QueuedNarratorAt >= 0.0f && Clock >= QueuedNarratorAt)
    {
        QueuedNarratorAt = -1.0f;
        PlayNarrator(*QueuedNarratorLine.ToString());
    }

    if (Screen == EReflectionsFlowScreen::SettingsConfirm && SettingsConfirmUntil >= 0.0f && Clock >= SettingsConfirmUntil)
    {
        HandleAction(EReflectionsFlowAction::SettingsRevert);
    }
    if (bJournalFromPause)
    {
        bool bJournalOpen = true;
        ReflectionsFlow::CallBool(GetQuestSubsystem(), TEXT("IsJournalOpen"), bJournalOpen);
        if (!bJournalOpen && Clock - JournalOpenedAt > 0.2f)
        {
            // Back to the pause menu: it still owns the pause and the UI-only input.
            bJournalFromPause = false;
            if (Menu.IsValid())
            {
                Menu->SetSuspended(false);
            }
            if (Screen == EReflectionsFlowScreen::Pause)
            {
                EnterMenuMode();
                if (Menu.IsValid())
                {
                    Menu->SetScreen(EReflectionsFlowScreen::Pause);
                }
            }
        }
    }
    if (Menu.IsValid() && IsMenuOpen() && !bJournalFromPause)
    {
        Menu->EnsureFocus();
    }
    if (bPlaying && !IsMenuOpen())
    {
        TrackPickups();
        TickRespawn();
        TickPendingCheckpoint();
        // The tip clock (and tips) wait while a cutscene plays, so the first tip comes after the intro.
        if (!IsCutscenePlaying())
        {
            PlayClock += RealDelta;
            TickTips(RealDelta);
        }
    }
}

UObject* UReflectionsGameFlowWorldSubsystem::GetCutsceneSubsystem() const
{
    UWorld* World = GetWorld();
    UClass* Class = ReflectionsFlow::FindGameClass(TEXT("ReflectionsCutsceneSubsystem"));
    if (!World || !Class || !Class->IsChildOf(UWorldSubsystem::StaticClass()))
    {
        return nullptr;
    }
    return World->GetSubsystemBase(TSubclassOf<UWorldSubsystem>(Class));
}

void UReflectionsGameFlowWorldSubsystem::StepSetting(int32 Row, int32 Delta)
{
    const int32 OldPreset = SettingsDraft.Preset;
    ReflectionsFlowSettings::Step(SettingsDraft, Row, Delta);
    if (Row == ReflectionsFlowSettings::Row_Preset && SettingsDraft.Preset != OldPreset)
    {
        ReflectionsFlowSettings::PreviewPreset(SettingsDraft.Preset, SettingsDraft.bRayTracing);
    }
    PlayUiSound(TEXT("UI_Hover"));
}

UObject* UReflectionsGameFlowWorldSubsystem::GetQuestSubsystem() const
{
    const UWorld* World = GetWorld();
    UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
    UClass* Class = ReflectionsFlow::FindGameClass(TEXT("ReflectionsQuestSubsystem"));
    if (!GameInstance || !Class || !Class->IsChildOf(UGameInstanceSubsystem::StaticClass()))
    {
        return nullptr;
    }
    return GameInstance->GetSubsystemBase(TSubclassOf<UGameInstanceSubsystem>(Class));
}

bool UReflectionsGameFlowWorldSubsystem::HasJournal() const
{
    const UObject* Quests = GetQuestSubsystem();
    return Quests && Quests->FindFunction(TEXT("OpenJournal")) && Quests->FindFunction(TEXT("IsJournalOpen"));
}

bool UReflectionsGameFlowWorldSubsystem::IsCutscenePlaying() const
{
    bool bPlayingCutscene = false;
    if (UObject* Cutscenes = GetCutsceneSubsystem())
    {
        ReflectionsFlow::CallBool(Cutscenes, TEXT("IsCutscenePlaying"), bPlayingCutscene);
    }
    return bPlayingCutscene;
}

void UReflectionsGameFlowWorldSubsystem::EnsureController()
{
    UWorld* World = GetWorld();
    APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
    if (!PC || !PC->IsLocalController() || !PC->GetLocalPlayer())
    {
        return;
    }
    if (PC != Controller.Get())
    {
        Controller = PC;
        BindPauseInput(PC);
        BuildWidgets();
        if (IsMenuOpen())
        {
            EnterMenuMode();
        }
    }
    APawn* CurrentPawn = PC->GetPawn();
    if (CurrentPawn != Pawn.Get())
    {
        Pawn = CurrentPawn;
        bWasDefeated = false;
        if (CurrentPawn && bPlaying)
        {
            PushRespawnPoint();
        }
    }
    if (!bBoundProgress)
    {
        UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
        UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
        if (Progress && Flow)
        {
            Progress->OnWorldChanged.AddUniqueDynamic(this, &UReflectionsGameFlowWorldSubsystem::HandleWorldChanged);
            Progress->OnPagesChanged.AddUniqueDynamic(this, &UReflectionsGameFlowWorldSubsystem::HandlePagesChanged);
            Flow->OnInfectionChanged.AddUniqueDynamic(this, &UReflectionsGameFlowWorldSubsystem::HandleInfectionChanged);
            bBoundProgress = true;
        }
    }
}

void UReflectionsGameFlowWorldSubsystem::BuildWidgets()
{
    RemoveWidgets();
    UWorld* World = GetWorld();
    UGameViewportClient* Viewport = World ? World->GetGameViewport() : nullptr;
    APlayerController* PC = Controller.Get();
    ULocalPlayer* Player = PC ? PC->GetLocalPlayer() : nullptr;
    if (!Viewport || !Player)
    {
        return;
    }
    SAssignNew(Hud, SReflectionsFlowHud).Owner(this);
    SAssignNew(Menu, SReflectionsFlowMenu).Owner(this);
    // Viewport content, the same layer UUserWidget::AddToViewport uses (it adds 10 to the ZOrder): spell HUD 20,
    // crafting and world-jump 30, villain HUD 35. The meter layer sits above those; the menus above everything.
    Viewport->AddViewportWidgetContent(Hud.ToSharedRef(), 40);
    Viewport->AddViewportWidgetContent(Menu.ToSharedRef(), 1000);
    WidgetPlayer = Player;
    Menu->SetScreen(Screen);
    // Load the UI cues now so the first button press does not hitch.
    for (const TCHAR* Cue : {TEXT("UI_Click"), TEXT("UI_Hover"), TEXT("UI_Confirm")})
    {
        if (!UiSounds.Contains(FName(Cue)))
        {
            const FString Path = FString::Printf(TEXT("/Game/Audio/Jam/Cues/SCue_%s.SCue_%s"), Cue, Cue);
            UiSounds.Add(FName(Cue), LoadObject<USoundBase>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet));
        }
    }
}

void UReflectionsGameFlowWorldSubsystem::RemoveWidgets()
{
    UWorld* World = GetWorld();
    UGameViewportClient* Viewport = World ? World->GetGameViewport() : nullptr;
    if (Viewport && WidgetPlayer.IsValid())
    {
        if (Hud.IsValid())
        {
            Viewport->RemoveViewportWidgetContent(Hud.ToSharedRef());
        }
        if (Menu.IsValid())
        {
            Viewport->RemoveViewportWidgetContent(Menu.ToSharedRef());
        }
    }
    Hud.Reset();
    Menu.Reset();
    WidgetPlayer.Reset();
}

void UReflectionsGameFlowWorldSubsystem::BindPauseInput(APlayerController* PC)
{
    if (!PC)
    {
        return;
    }
    PauseInput = NewObject<UInputComponent>(PC, TEXT("GameFlowPauseInput"));
    PauseInput->Priority = 20;
    // Esc stops PIE in the editor, so P works too; Start is the gamepad pause (on release: holding it quick-saves).
    PauseInput->BindKey(EKeys::Escape, IE_Pressed, this, &UReflectionsGameFlowWorldSubsystem::OnPausePressed);
    PauseInput->BindKey(EKeys::P, IE_Pressed, this, &UReflectionsGameFlowWorldSubsystem::OnPausePressed);
    PauseInput->BindKey(EKeys::Gamepad_Special_Right, IE_Pressed, this, &UReflectionsGameFlowWorldSubsystem::OnPadStartPressed);
    PauseInput->BindKey(EKeys::Gamepad_Special_Right, IE_Released, this, &UReflectionsGameFlowWorldSubsystem::OnPadStartReleased);
    // Every pad button is taken in play, so the pad's quick save is a held Start (and X / Y inside the pause menu).
    PauseInput->BindKey(EKeys::F5, IE_Pressed, this, &UReflectionsGameFlowWorldSubsystem::OnQuickSaveKey);
    PauseInput->BindKey(EKeys::F9, IE_Pressed, this, &UReflectionsGameFlowWorldSubsystem::OnQuickLoadKey);
    PC->PushInputComponent(PauseInput);
}

void UReflectionsGameFlowWorldSubsystem::OnPadStartPressed()
{
    StartHeldSince = FPlatformTime::Seconds();
    bStartHoldConsumed = false;
}

void UReflectionsGameFlowWorldSubsystem::OnPadStartReleased()
{
    const bool bShortPress = StartHeldSince >= 0.0 && !bStartHoldConsumed;
    StartHeldSince = -1.0;
    if (bShortPress)
    {
        OnPausePressed();
    }
}

void UReflectionsGameFlowWorldSubsystem::OnQuickSaveKey()
{
    if (bPlaying && !IsMenuOpen())
    {
        RequestQuickSave();
    }
}

void UReflectionsGameFlowWorldSubsystem::OnQuickLoadKey()
{
    if (bPlaying && !IsMenuOpen())
    {
        RequestQuickLoad();
    }
}

bool UReflectionsGameFlowWorldSubsystem::IsHeroDefeated() const
{
    bool bDefeated = false;
    if (UObject* Driver = FindPawnComponent(TEXT("ReflectionsSampleSpellDriver")))
    {
        ReflectionsFlow::CallBool(Driver, TEXT("IsDefeated"), bDefeated);
    }
    return bDefeated;
}

bool UReflectionsGameFlowWorldSubsystem::CanSaveNow() const
{
    const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    const bool bScreenOk = Screen == EReflectionsFlowScreen::None || Screen == EReflectionsFlowScreen::Pause
        || Screen == EReflectionsFlowScreen::SaveGame || Screen == EReflectionsFlowScreen::Confirm;
    return Flow && bPlaying && Pawn.IsValid() && bScreenOk && !Flow->IsGameOver() && !IsCutscenePlaying() && !IsHeroDefeated();
}

void UReflectionsGameFlowWorldSubsystem::RequestQuickSave()
{
    TrackPickups();
    UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    const bool bOk = Flow && CanSaveNow() && Flow->QuickSave();
    SaveStatus = bOk ? FLOWTEXT("Save.QuickDone", "Quick saved") : FLOWTEXT("Save.CantNow", "Can't save right now");
    PlayUiSound(bOk ? TEXT("UI_Confirm") : TEXT("UI_Click"));
    ShowToast(SaveStatus);
    if (IsMenuOpen() && Menu.IsValid())
    {
        Menu->SetScreen(Screen);  // the status line
    }
}

void UReflectionsGameFlowWorldSubsystem::RequestQuickLoad()
{
    UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    if (Flow && Flow->GetSaveSlotInfo(ReflectionsSaveSlots::Quick).bUsed)
    {
        PlayUiSound(TEXT("UI_Confirm"));
        if (Flow->QuickLoad())
        {
            return;
        }
        SaveStatus = FLOWTEXT("Save.LoadFailed", "Couldn't load that save");
    }
    else
    {
        SaveStatus = FLOWTEXT("Save.NoQuick", "No quick save yet (F5, or hold Start)");
    }
    PlayUiSound(TEXT("UI_Click"));
    ShowToast(SaveStatus);
    if (IsMenuOpen() && Menu.IsValid())
    {
        Menu->SetScreen(Screen);
    }
}

void UReflectionsGameFlowWorldSubsystem::RefreshSaveScreen()
{
    if (Menu.IsValid() && (Screen == EReflectionsFlowScreen::SaveGame || Screen == EReflectionsFlowScreen::LoadGame))
    {
        Menu->SetScreen(Screen);
    }
}

void UReflectionsGameFlowWorldSubsystem::SaveSlotAction(int32 Slot)
{
    UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    if (!Flow)
    {
        return;
    }
    if (Flow->GetSaveSlotInfo(Slot).bUsed)
    {
        PlayUiSound(TEXT("UI_Click"));
        PendingSlot = Slot;
        ConfirmAction = EReflectionsFlowAction::SaveGame;
        PushScreen(EReflectionsFlowScreen::Confirm);
        return;
    }
    DoSave(Slot);
}

void UReflectionsGameFlowWorldSubsystem::DoSave(int32 Slot)
{
    TrackPickups();
    UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    const bool bOk = Flow && CanSaveNow() && Flow->SaveToSlot(Slot);
    SaveStatus = bOk ? FText::Format(FLOWTEXT("Save.Done", "Saved to {0}"), UReflectionsGameFlowSubsystem::GetSlotDisplayName(Slot))
                     : FLOWTEXT("Save.CantNow", "Can't save right now");
    PlayUiSound(bOk ? TEXT("UI_Confirm") : TEXT("UI_Click"));
    RefreshSaveScreen();
}

void UReflectionsGameFlowWorldSubsystem::LoadSlotAction(int32 Slot)
{
    UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    if (!Flow)
    {
        return;
    }
    if (!Flow->GetSaveSlotInfo(Slot).bUsed)
    {
        SaveStatus = FLOWTEXT("Save.Empty", "That slot is empty");
        PlayUiSound(TEXT("UI_Click"));
        RefreshSaveScreen();
        return;
    }
    // In play, unsaved progress would be lost: ask first (not from the title, and not when the hero is down).
    if (bPlaying && !IsHeroDefeated())
    {
        PlayUiSound(TEXT("UI_Click"));
        PendingSlot = Slot;
        ConfirmAction = EReflectionsFlowAction::LoadGame;
        PushScreen(EReflectionsFlowScreen::Confirm);
        return;
    }
    PlayUiSound(TEXT("UI_Confirm"));
    Flow->LoadFromSlot(Slot);
}

void UReflectionsGameFlowWorldSubsystem::ShowDeath()
{
    ScreenStack.Reset();
    ActiveTip = EReflectionsTip::Count;
    SaveStatus = FText::GetEmpty();
    ApplyScreen(EReflectionsFlowScreen::Death);
    UE_LOG(LogReflectionsGameFlowWorld, Log, TEXT("Hero down: death screen."));
}

void UReflectionsGameFlowWorldSubsystem::RestoreVitals(const FReflectionsCheckpoint& Checkpoint)
{
    APawn* CurrentPawn = Pawn.Get();
    if (!CurrentPawn)
    {
        return;
    }
    if (Checkpoint.Health > 0.0f)
    {
        if (UReflectionsHealthComponent* Health = CurrentPawn->FindComponentByClass<UReflectionsHealthComponent>())
        {
            Health->Health = FMath::Clamp(Checkpoint.Health, 1.0f, FMath::Max(1.0f, Health->MaxHealth));
            Health->OnHealthChanged.Broadcast(Health->Health, Health->MaxHealth, nullptr);
        }
    }
    if (Checkpoint.Mana >= 0.0f)
    {
        if (UObject* Driver = FindPawnComponent(TEXT("ReflectionsSampleSpellDriver")))
        {
            float Now = 0.0f;
            if (ReflectionsFlow::CallFloat(Driver, TEXT("GetMagic"), Now) && Now > Checkpoint.Mana + 0.5f)
            {
                ReflectionsFlow::CallWithFloat(Driver, TEXT("SpendMagic"), Now - Checkpoint.Mana);
            }
        }
    }
    UE_LOG(LogReflectionsGameFlowWorld, Log, TEXT("Restored health %.0f and mana %.0f from the save."), Checkpoint.Health, Checkpoint.Mana);
}

void UReflectionsGameFlowWorldSubsystem::OnPausePressed()
{
    if (CanOpenPause())
    {
        OpenPause();
    }
}

bool UReflectionsGameFlowWorldSubsystem::CanOpenPause() const
{
    const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    return bPlaying && !IsMenuOpen() && !bCraftingOpen && !(Flow && Flow->IsGameOver()) && !IsCutscenePlaying();
}

UObject* UReflectionsGameFlowWorldSubsystem::FindPawnComponent(const TCHAR* ClassName) const
{
    APawn* CurrentPawn = Pawn.Get();
    UClass* Class = CurrentPawn ? ReflectionsFlow::FindGameClass(ClassName) : nullptr;
    return Class ? CurrentPawn->FindComponentByClass(Class) : nullptr;
}

bool UReflectionsGameFlowWorldSubsystem::IsUsingGamepad() const
{
    const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    return Flow && Flow->IsUsingGamepad();
}

void UReflectionsGameFlowWorldSubsystem::PlayNarrator(const TCHAR* Line)
{
    const FName Key(*FString::Printf(TEXT("VO_%s"), Line));
    USoundBase* Sound = nullptr;
    if (const TObjectPtr<USoundBase>* Cached = UiSounds.Find(Key))
    {
        Sound = Cached->Get();
    }
    else
    {
        const FString Path = FString::Printf(TEXT("/Game/Audio/Jam/Voice/Cues/SCue_VO_Narrator_%s.SCue_VO_Narrator_%s"), Line, Line);
        Sound = LoadObject<USoundBase>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
        if (Sound)
        {
            UiSounds.Add(Key, Sound);  // misses are not cached: audio adds the lines while we run
        }
    }
    if (!Sound)
    {
        return;
    }
    if (Narrator)
    {
        Narrator->Stop();
    }
    // CreateSound2D marks it a UI sound, so it plays over paused menus too.
    Narrator = UGameplayStatics::SpawnSound2D(this, Sound, 1.0f, 1.0f, 0.0f, nullptr, false, true);
}

bool UReflectionsGameFlowWorldSubsystem::IsNarratorSpeaking() const
{
    return Narrator && Narrator->IsPlaying();
}

void UReflectionsGameFlowWorldSubsystem::PlayUiSound(const TCHAR* CueName)
{
    const FName Key(CueName);
    USoundBase* Sound = nullptr;
    if (const TObjectPtr<USoundBase>* Cached = UiSounds.Find(Key))
    {
        Sound = Cached->Get();
    }
    else
    {
        const FString Path = FString::Printf(TEXT("/Game/Audio/Jam/Cues/SCue_%s.SCue_%s"), CueName, CueName);
        Sound = LoadObject<USoundBase>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
        UiSounds.Add(Key, Sound);  // a miss is cached too, so a missing cue costs one lookup
    }
    if (Sound)
    {
        UGameplayStatics::PlaySound2D(this, Sound, 1.0f, 1.0f, 0.0f, nullptr, nullptr, true);
    }
}

// ---- Start, screens, input modes ---------------------------------------------------------------------------

void UReflectionsGameFlowWorldSubsystem::HandleStartAction()
{
    bStartHandled = true;
    UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    if (!Flow)
    {
        BeginPlaying();
        return;
    }
    EReflectionsFlowStart Start = Flow->ConsumeStartAction();
    if (Start != EReflectionsFlowStart::Restore)
    {
        Flow->bRestoreVitals = false;  // a load whose restore never ran must not leak into a later Try again
    }
    if (Start == EReflectionsFlowStart::Launch)
    {
        // First launch of the packaged game: benchmark, clamp to High, borderless + VSync, before the title shows.
        ReflectionsFlowSettings::RunFirstLaunchSetup();
        const bool bTitle = !GIsEditor || CVarGameFlowTitleInPIE.GetValueOnGameThread() != 0;
        if (!bTitle)
        {
            // PIE without the title: a fresh run in this map; the old save's checkpoint would point elsewhere.
            Flow->ClearCheckpoint();
            BeginPlaying(true);
            return;
        }
        Start = EReflectionsFlowStart::Title;
    }
    switch (Start)
    {
    case EReflectionsFlowStart::Title:
        ShowTitle();
        break;
    case EReflectionsFlowStart::Restore:
        bRestorePending = true;
        break;
    case EReflectionsFlowStart::Play:
    case EReflectionsFlowStart::None:
    default:
        // Play after "New Game" from a map that was not fresh is a fresh run; Play after a restart is not.
        BeginPlaying(Start == EReflectionsFlowStart::Play && Flow->bPendingFreshRun);
        Flow->bPendingFreshRun = false;
        break;
    }
    UE_LOG(LogReflectionsGameFlowWorld, Log, TEXT("Game flow started in %s (start action %d)."),
        *ReflectionsFlow::MapPathOf(GetWorld()), static_cast<int32>(Start));
}

void UReflectionsGameFlowWorldSubsystem::BeginPlaying(bool bFreshRun)
{
    const bool bFirst = !bPlaying;
    bPlaying = true;
    bStartHandled = true;
    ResumeGame();
    UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    if (!Flow)
    {
        return;
    }
    if (bFirst && Flow->bMenuInputActive && !IsMenuOpen())
    {
        // This map was opened from a menu (Try again, Restart, Continue, New Game): the viewport client still
        // ignores game input from the UI-only mode, and focus points at the old map's menu.
        EnterGameMode();
    }
    if (!Flow->HasCheckpoint() || Flow->GetCheckpoint().MapPath != ReflectionsFlow::MapPathOf(GetWorld()))
    {
        // A first checkpoint at the map's start, so a death or "Try again" always has somewhere to go.
        ScheduleCheckpoint(TEXT("Start"), 3);
    }
    else if (bFirst)
    {
        PushRespawnPoint();
    }
    // A fresh run (Start / New Game, not Restore / Continue / Try again) opens with the cutscene session's
    // new-game intro, in game mode. It voices the theme line itself (SCue_VO_Narrator_Intro, timed with its card).
    bool bIntroCutscene = false;
    if (bFreshRun && bFirst)
    {
        if (UObject* Cutscenes = GetCutsceneSubsystem())
        {
            ReflectionsFlow::CallBool(Cutscenes, TEXT("PlayNewGameIntro"), bIntroCutscene);
            UE_LOG(LogReflectionsGameFlowWorld, Log, TEXT("New-game intro cutscene: %s."), bIntroCutscene ? TEXT("playing") : TEXT("did not start"));
        }
    }
    if (bIntroCutscene)
    {
        Flow->bIntroPlayed = true;
        QueuedNarratorAt = -1.0f;
        if (Narrator)
        {
            Narrator->Stop();
        }
    }
    else if (bFirst && !Flow->bIntroPlayed)
    {
        // No title screen and no intro cutscene: the narrated theme line plays as play starts.
        Flow->bIntroPlayed = true;
        QueuedNarratorLine = TEXT("Intro");
        QueuedNarratorAt = Clock + 0.5f;
    }
}

void UReflectionsGameFlowWorldSubsystem::ShowTitle()
{
    // With a cutscene system the intro cutscene voices the theme line after Start; the title only shows it.
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
        Flow && !Flow->bIntroPlayed && !ReflectionsFlow::FindGameClass(TEXT("ReflectionsCutsceneSubsystem")))
    {
        Flow->bIntroPlayed = true;
        QueuedNarratorLine = TEXT("Intro");
        QueuedNarratorAt = Clock + 1.0f;
    }
    ScreenStack.Reset();
    ApplyScreen(EReflectionsFlowScreen::Title);
}

void UReflectionsGameFlowWorldSubsystem::OpenPause()
{
    ScreenStack.Reset();
    SaveStatus = FText::GetEmpty();
    PlayUiSound(TEXT("UI_Click"));
    ApplyScreen(EReflectionsFlowScreen::Pause);
}

void UReflectionsGameFlowWorldSubsystem::ShowLose()
{
    ScreenStack.Reset();
    ActiveTip = EReflectionsTip::Count;
    PlayUiSound(TEXT("Villain_Manifest"));
    ApplyScreen(EReflectionsFlowScreen::Lose);
}

void UReflectionsGameFlowWorldSubsystem::ShowVictory()
{
    // After the victory sting.
    QueuedNarratorLine = TEXT("Victory");
    QueuedNarratorAt = Clock + 2.5f;
    ScreenStack.Reset();
    ActiveTip = EReflectionsTip::Count;
    PlayUiSound(TEXT("MUS_Victory_Sting"));
    ApplyScreen(EReflectionsFlowScreen::Victory);
}

void UReflectionsGameFlowWorldSubsystem::PushScreen(EReflectionsFlowScreen NewScreen)
{
    if (Screen != EReflectionsFlowScreen::None)
    {
        ScreenStack.Push(Screen);
    }
    ApplyScreen(NewScreen);
}

void UReflectionsGameFlowWorldSubsystem::ResumeGame()
{
    bJournalFromPause = false;
    if (Menu.IsValid())
    {
        Menu->SetSuspended(false);
    }
    ScreenStack.Reset();
    ApplyScreen(EReflectionsFlowScreen::None);
}

void UReflectionsGameFlowWorldSubsystem::ApplyScreen(EReflectionsFlowScreen NewScreen)
{
    const bool bWasOpen = IsMenuOpen();
    Screen = NewScreen;
    if (NewScreen == EReflectionsFlowScreen::None)
    {
        if (bWasOpen || bPausedByMenu)
        {
            EnterGameMode();
        }
    }
    else
    {
        EnterMenuMode();
    }
    if (Menu.IsValid())
    {
        Menu->SetScreen(NewScreen);
    }
}

void UReflectionsGameFlowWorldSubsystem::EnterMenuMode()
{
    APlayerController* PC = Controller.Get();
    if (!PC)
    {
        return;
    }
    // Always (re)assert the pause: an overlay that closed over the menu (the quest journal) may have unpaused.
    if (!UGameplayStatics::IsGamePaused(this))
    {
        UGameplayStatics::SetGamePaused(this, true);
    }
    bPausedByMenu = UGameplayStatics::IsGamePaused(this);
    StartHeldSince = -1.0;
    PC->FlushPressedKeys();
    PC->bShowMouseCursor = true;
    FInputModeUIOnly Mode;
    if (Menu.IsValid())
    {
        Mode.SetWidgetToFocus(Menu);
    }
    Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
    PC->SetInputMode(Mode);
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        Flow->bMenuInputActive = true;
    }
}

void UReflectionsGameFlowWorldSubsystem::EnterGameMode()
{
    if (bPausedByMenu)
    {
        UGameplayStatics::SetGamePaused(this, false);
        bPausedByMenu = false;
    }
    APlayerController* PC = Controller.Get();
    if (!PC)
    {
        return;
    }
    PC->FlushPressedKeys();
    PC->bShowMouseCursor = false;
    PC->SetInputMode(FInputModeGameOnly());
    if (FSlateApplication::IsInitialized())
    {
        FSlateApplication::Get().SetAllUserFocusToGameViewport();
    }
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        Flow->bMenuInputActive = false;
    }
}

void UReflectionsGameFlowWorldSubsystem::HandleAction(EReflectionsFlowAction Action)
{
    UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    switch (Action)
    {
    case EReflectionsFlowAction::Start:
    case EReflectionsFlowAction::NewGame:
        if (Action == EReflectionsFlowAction::NewGame && Flow && Flow->HasCheckpoint() && Screen != EReflectionsFlowScreen::Confirm)
        {
            // New Game replaces the autosave: ask first (the manual and quick saves are kept).
            PlayUiSound(TEXT("UI_Click"));
            ConfirmAction = EReflectionsFlowAction::NewGame;
            PushScreen(EReflectionsFlowScreen::Confirm);
            break;
        }
        PlayUiSound(TEXT("UI_Confirm"));
        if (Flow)
        {
            Flow->StartNewGame();
        }
        else
        {
            BeginPlaying();
        }
        break;
    case EReflectionsFlowAction::Continue:
        PlayUiSound(TEXT("UI_Confirm"));
        if (Flow)
        {
            Flow->ContinueFromCheckpoint();
        }
        break;
    case EReflectionsFlowAction::Controls:
        PlayUiSound(TEXT("UI_Click"));
        PushScreen(EReflectionsFlowScreen::Controls);
        break;
    case EReflectionsFlowAction::Credits:
        PlayUiSound(TEXT("UI_Click"));
        PushScreen(EReflectionsFlowScreen::Credits);
        break;
    case EReflectionsFlowAction::QuitGame:
        PlayUiSound(TEXT("UI_Click"));
        if (Flow)
        {
            Flow->QuitGame();
        }
        break;
    case EReflectionsFlowAction::Resume:
        PlayUiSound(TEXT("UI_Confirm"));
        ResumeGame();
        break;
    case EReflectionsFlowAction::Restart:
    case EReflectionsFlowAction::QuitToTitle:
        PlayUiSound(TEXT("UI_Click"));
        ConfirmAction = Action;
        PushScreen(EReflectionsFlowScreen::Confirm);
        break;
    case EReflectionsFlowAction::ConfirmYes:
        PlayUiSound(TEXT("UI_Confirm"));
        if (ConfirmAction == EReflectionsFlowAction::SaveGame)
        {
            // Overwrite confirmed: back on the Save screen, which shows the new time.
            ApplyScreen(ScreenStack.Num() > 0 ? ScreenStack.Pop() : EReflectionsFlowScreen::SaveGame);
            DoSave(PendingSlot);
            break;
        }
        if (ConfirmAction == EReflectionsFlowAction::LoadGame)
        {
            if (!Flow || !Flow->LoadFromSlot(PendingSlot))
            {
                SaveStatus = FLOWTEXT("Save.LoadFailed", "Couldn't load that save");
                ApplyScreen(ScreenStack.Num() > 0 ? ScreenStack.Pop() : EReflectionsFlowScreen::LoadGame);
            }
            break;
        }
        if (ConfirmAction == EReflectionsFlowAction::NewGame)
        {
            if (Flow)
            {
                Flow->StartNewGame();
            }
            break;
        }
        if (Flow)
        {
            if (ConfirmAction == EReflectionsFlowAction::Restart)
            {
                Flow->RestartFromCheckpoint();
            }
            else
            {
                Flow->ReturnToTitle();
            }
        }
        break;
    case EReflectionsFlowAction::TryAgain:
        PlayUiSound(TEXT("UI_Confirm"));
        if (Flow)
        {
            Flow->RestartFromCheckpoint();
        }
        break;
    case EReflectionsFlowAction::Settings:
        PlayUiSound(TEXT("UI_Click"));
        SettingsDraft = ReflectionsFlowSettings::ReadCurrent();
        SettingsOriginal = SettingsDraft;
        ReflectionsFlowSettings::CaptureQualityBaseline();
        PushScreen(EReflectionsFlowScreen::Settings);
        break;
    case EReflectionsFlowAction::SettingsApply:
        PlayUiSound(TEXT("UI_Confirm"));
        if (ReflectionsFlowSettings::Apply(SettingsDraft))
        {
            SettingsConfirmUntil = Clock + 15.0f;
            PushScreen(EReflectionsFlowScreen::SettingsConfirm);
        }
        else
        {
            ReflectionsFlowSettings::KeepVideoMode();
            SettingsOriginal = SettingsDraft;
            ReflectionsFlowSettings::CaptureQualityBaseline();
        }
        break;
    case EReflectionsFlowAction::SettingsDefaults:
        PlayUiSound(TEXT("UI_Click"));
        SettingsDraft = ReflectionsFlowSettings::AutoDetect();
        ReflectionsFlowSettings::PreviewPreset(SettingsDraft.Preset, SettingsDraft.bRayTracing);
        break;
    case EReflectionsFlowAction::SettingsKeep:
        PlayUiSound(TEXT("UI_Confirm"));
        ReflectionsFlowSettings::KeepVideoMode();
        SettingsConfirmUntil = -1.0f;
        SettingsOriginal = SettingsDraft;
        ReflectionsFlowSettings::CaptureQualityBaseline();
        if (ScreenStack.Num() > 0)
        {
            ApplyScreen(ScreenStack.Pop());
        }
        break;
    case EReflectionsFlowAction::SettingsRevert:
        PlayUiSound(TEXT("UI_Click"));
        ReflectionsFlowSettings::RevertVideoMode();
        SettingsConfirmUntil = -1.0f;
        SettingsDraft = ReflectionsFlowSettings::ReadCurrent();
        SettingsOriginal = SettingsDraft;
        ReflectionsFlowSettings::CaptureQualityBaseline();
        if (ScreenStack.Num() > 0)
        {
            ApplyScreen(ScreenStack.Pop());
        }
        break;
    case EReflectionsFlowAction::Journal:
        PlayUiSound(TEXT("UI_Click"));
        if (HasJournal() && ReflectionsFlow::CallNoArgs(GetQuestSubsystem(), TEXT("OpenJournal")))
        {
            // The journal draws under the menus (Z 990 < 1000): step aside, keep the pause, come back on close.
            bJournalFromPause = true;
            JournalOpenedAt = Clock;
            if (Menu.IsValid())
            {
                Menu->SetSuspended(true);
            }
        }
        break;
    case EReflectionsFlowAction::ReturnToTitle:
        PlayUiSound(TEXT("UI_Click"));
        if (Flow)
        {
            Flow->ReturnToTitle();
        }
        break;
    case EReflectionsFlowAction::SaveGame:
    case EReflectionsFlowAction::LoadGame:
        PlayUiSound(TEXT("UI_Click"));
        SaveStatus = FText::GetEmpty();
        PushScreen(Action == EReflectionsFlowAction::SaveGame ? EReflectionsFlowScreen::SaveGame : EReflectionsFlowScreen::LoadGame);
        break;
    case EReflectionsFlowAction::SaveSlot1:
    case EReflectionsFlowAction::SaveSlot2:
    case EReflectionsFlowAction::SaveSlot3:
        SaveSlotAction(ReflectionsSaveSlots::FirstManual + (static_cast<int32>(Action) - static_cast<int32>(EReflectionsFlowAction::SaveSlot1)));
        break;
    case EReflectionsFlowAction::LoadAutosave:
        LoadSlotAction(ReflectionsSaveSlots::Autosave);
        break;
    case EReflectionsFlowAction::LoadQuick:
        LoadSlotAction(ReflectionsSaveSlots::Quick);
        break;
    case EReflectionsFlowAction::LoadSlot1:
    case EReflectionsFlowAction::LoadSlot2:
    case EReflectionsFlowAction::LoadSlot3:
        LoadSlotAction(ReflectionsSaveSlots::FirstManual + (static_cast<int32>(Action) - static_cast<int32>(EReflectionsFlowAction::LoadSlot1)));
        break;
    case EReflectionsFlowAction::QuickSave:
        RequestQuickSave();
        break;
    case EReflectionsFlowAction::QuickLoad:
        RequestQuickLoad();
        break;
    case EReflectionsFlowAction::Respawn:
        PlayUiSound(TEXT("UI_Confirm"));
        ResumeGame();
        // The driver gets the hero up on its own timer (it waited while the screen paused the game), at the
        // checkpoint (SetRespawnTransform). RespawnNow, when the driver offers it, skips the rest of the wait.
        if (!ReflectionsFlow::CallNoArgs(FindPawnComponent(TEXT("ReflectionsSampleSpellDriver")), TEXT("RespawnNow")))
        {
            ShowToast(FLOWTEXT("Death.GettingUp", "Getting up..."), 2.0f);
        }
        break;
    case EReflectionsFlowAction::LoadLatest:
        if (Flow)
        {
            const int32 Newest = Flow->GetNewestSaveSlot(true);
            PlayUiSound(TEXT("UI_Confirm"));
            if (Newest == INDEX_NONE || !Flow->LoadFromSlot(Newest))
            {
                Flow->RestartFromCheckpoint();
            }
        }
        break;
    case EReflectionsFlowAction::Back:
        if (Screen == EReflectionsFlowScreen::Death && ScreenStack.Num() == 0)
        {
            break;  // the hero is down: pick one of the options
        }
        if (Screen == EReflectionsFlowScreen::SettingsConfirm)
        {
            HandleAction(EReflectionsFlowAction::SettingsRevert);
            break;
        }
        if (Screen == EReflectionsFlowScreen::Settings)
        {
            // Unapplied changes are dropped: put every scalability group back as it was when Settings opened.
            ReflectionsFlowSettings::RestoreQualityBaseline(SettingsOriginal.bRayTracing);
            SettingsDraft = SettingsOriginal;
        }
        if (ScreenStack.Num() > 0)
        {
            PlayUiSound(TEXT("UI_Click"));
            ApplyScreen(ScreenStack.Pop());
        }
        else if (Screen == EReflectionsFlowScreen::Pause)
        {
            PlayUiSound(TEXT("UI_Click"));
            ResumeGame();
        }
        break;
    }
}

// ---- HUD state ---------------------------------------------------------------------------------------------

void UReflectionsGameFlowWorldSubsystem::ShowToast(const FText& Text, float Seconds)
{
    ToastText = Text;
    ToastStarted = Clock;
    ToastDuration = Seconds;
}

float UReflectionsGameFlowWorldSubsystem::GetToastAlpha() const
{
    const float Age = Clock - ToastStarted;
    if (Age < 0.0f || Age > ToastDuration)
    {
        return 0.0f;
    }
    return FMath::Clamp(FMath::Min(Age / 0.2f, (ToastDuration - Age) / 0.5f), 0.0f, 1.0f);
}

float UReflectionsGameFlowWorldSubsystem::GetInfectionPulse() const
{
    const float Age = Clock - InfectionChangedAt;
    return Age >= 0.0f && Age < 1.2f ? 1.0f - Age / 1.2f : 0.0f;
}

float UReflectionsGameFlowWorldSubsystem::GetTipAlpha() const
{
    if (ActiveTip == EReflectionsTip::Count)
    {
        return 0.0f;
    }
    const float Age = PlayClock - TipStarted;
    return FMath::Clamp(FMath::Min(Age / 0.3f, (TipDuration - Age) / 0.5f), 0.0f, 1.0f);
}

FText UReflectionsGameFlowWorldSubsystem::GetTipTitle(EReflectionsTip Tip) const
{
    switch (Tip)
    {
    case EReflectionsTip::Aim: return FLOWTEXT("Tip.Aim.Title", "Aim");
    case EReflectionsTip::Cast: return FLOWTEXT("Tip.Cast.Title", "Cast");
    case EReflectionsTip::Coin: return FLOWTEXT("Tip.Shard.Title", "Mirror shards");
    case EReflectionsTip::CrossWorlds: return FLOWTEXT("Tip.Step.Title", "Step through");
    case EReflectionsTip::Crafting: return FLOWTEXT("Tip.Craft.Title", "Spell crafting");
    default: return FText::GetEmpty();
    }
}

FText UReflectionsGameFlowWorldSubsystem::GetTipText(EReflectionsTip Tip) const
{
    const bool bPad = IsUsingGamepad();
    switch (Tip)
    {
    case EReflectionsTip::Aim:
        return bPad ? FLOWTEXT("Tip.Aim.Pad", "Hold LT to aim your magic. A reticle shows where the spell will land.")
                    : FLOWTEXT("Tip.Aim.Keys", "Hold Right Mouse to aim your magic. A reticle shows where the spell will land.");
    case EReflectionsTip::Cast:
        return bPad ? FLOWTEXT("Tip.Cast.Pad", "RT casts the selected spell (hold to repeat). RB / LB switch spells.")
                    : FLOWTEXT("Tip.Cast.Keys", "Left Mouse or Q casts the selected spell. Tab switches spells, 1-4 picks one.");
    case EReflectionsTip::Coin:
        return FLOWTEXT("Tip.Shard", "Mirror shards let you step through. Stepping through also takes most of your magic.");
    case EReflectionsTip::CrossWorlds:
        return bPad ? FLOWTEXT("Tip.Step.Pad", "You can step through now. Hold Y to step up into the next side, R3 to step down. It takes a mirror shard and most of your magic.")
                    : FLOWTEXT("Tip.Step.Keys", "You can step through now. Hold X to step up into the next side, Z to step down. It takes a mirror shard and most of your magic.");
    case EReflectionsTip::Crafting:
        return bPad ? FLOWTEXT("Tip.Craft.Pad", "Press View to open Spell Crafting and build your own spells. D-pad Up picks a crafted spell.")
                    : FLOWTEXT("Tip.Craft.Keys", "Press K to open Spell Crafting and build your own spells. Keys 5-8 pick a crafted spell.");
    default:
        return FText::GetEmpty();
    }
}

void UReflectionsGameFlowWorldSubsystem::ShowTip(EReflectionsTip Tip)
{
    if (Tip == EReflectionsTip::Count)
    {
        return;
    }
    ActiveTip = Tip;
    TipStarted = PlayClock;
    TipDuration = Tip == EReflectionsTip::CrossWorlds ? 9.0f : 7.0f;
    TipQueue.Remove(Tip);
    if (Tip == EReflectionsTip::Aim) AimTipShownAt = PlayClock;
    if (Tip == EReflectionsTip::Cast) CastTipShownAt = PlayClock;
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        Flow->MarkTipSeen(Tip);
    }
    PlayUiSound(TEXT("UI_Hover"));
    switch (Tip)
    {
    case EReflectionsTip::Aim: PlayNarrator(TEXT("Tip_Aim")); break;
    case EReflectionsTip::Cast: PlayNarrator(TEXT("Tip_Cast")); break;
    case EReflectionsTip::Coin: PlayNarrator(TEXT("Tip_Shard")); break;
    case EReflectionsTip::CrossWorlds: PlayNarrator(TEXT("Tip_StepThrough")); break;
    case EReflectionsTip::Crafting: PlayNarrator(TEXT("Tip_Crafting")); break;
    default: break;
    }
}

void UReflectionsGameFlowWorldSubsystem::TickTips(float DeltaTime)
{
    UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    APawn* CurrentPawn = Pawn.Get();
    if (!Flow || !CurrentPawn)
    {
        return;
    }
    UObject* Driver = FindPawnComponent(TEXT("ReflectionsSampleSpellDriver"));
    UObject* Aim = FindPawnComponent(TEXT("ReflectionsSpellAimComponent"));
    bool bAiming = false;
    if (Aim)
    {
        ReflectionsFlow::CallBool(Aim, TEXT("IsAiming"), bAiming);
    }
    bool bDefeated = false;
    if (Driver)
    {
        ReflectionsFlow::CallBool(Driver, TEXT("IsDefeated"), bDefeated);
    }

    // The active tip ends on time, or early once the player does what it says.
    if (ActiveTip != EReflectionsTip::Count)
    {
        const float Age = PlayClock - TipStarted;
        if (ActiveTip == EReflectionsTip::Aim && bAiming && Age > 1.5f && TipDuration - Age > 0.5f)
        {
            // Done what it says: the card goes, and so does the rest of its line.
            TipDuration = Age + 0.5f;
            if (Narrator)
            {
                Narrator->Stop();
            }
        }
        else if (IsNarratorSpeaking() && TipDuration - Age < 0.6f && Age < 20.0f)
        {
            // The narrator is still reading the tip (the new voice runs up to 13.5 s): keep the card up with it.
            TipDuration = Age + 0.6f;
        }
        if (Age >= TipDuration)
        {
            ActiveTip = EReflectionsTip::Count;
            LastTipEnded = PlayClock;
        }
    }
    if (CVarGameFlowTips.GetValueOnGameThread() == 0 || bDefeated)
    {
        return;
    }

    auto Want = [this, Flow](EReflectionsTip Tip)
    {
        if (!Flow->HasSeenTip(Tip) && ActiveTip != Tip && !TipQueue.Contains(Tip))
        {
            TipQueue.Add(Tip);
        }
    };

    if (Driver && PlayClock > 2.5f)
    {
        Want(EReflectionsTip::Aim);
    }
    if (Driver && Flow->HasSeenTip(EReflectionsTip::Aim) && ActiveTip != EReflectionsTip::Aim
        && (bAiming || (AimTipShownAt >= 0.0f && PlayClock - AimTipShownAt > 14.0f) || AimTipShownAt < 0.0f))
    {
        Want(EReflectionsTip::Cast);
    }
    if (Flow->HasSeenTip(EReflectionsTip::Cast) && FindPawnComponent(TEXT("ReflectionsSpellCraftingComponent"))
        && (CastTipShownAt < 0.0f || PlayClock - CastTipShownAt > 20.0f))
    {
        Want(EReflectionsTip::Crafting);
    }

    if (PlayClock - CoinScanClock > 0.5f)
    {
        CoinScanClock = PlayClock;
        bCoinNearby = false;
        const FVector Here = CurrentPawn->GetActorLocation();
        for (TActorIterator<AReflectionsCoinPickup> It(GetWorld()); It; ++It)
        {
            if (FVector::DistSquared(It->GetActorLocation(), Here) < FMath::Square(2500.0f))
            {
                bCoinNearby = true;
                break;
            }
        }
        bCanCrossWorlds = false;
        if (const UReflectionsWorldJumpComponent* Jump = CurrentPawn->FindComponentByClass<UReflectionsWorldJumpComponent>())
        {
            FText Reason;
            EReflectionsWorld Destination = EReflectionsWorld::Red;
            bCanCrossWorlds = Jump->CanJump(EReflectionsJumpDirection::Up, Reason, Destination)
                || Jump->CanJump(EReflectionsJumpDirection::Down, Reason, Destination);
        }
    }
    if (bCoinNearby)
    {
        Want(EReflectionsTip::Coin);
    }
    else if (const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this))
    {
        if (Progress->GetCoins(EReflectionsWorld::Gray) + Progress->GetCoins(EReflectionsWorld::Red) + Progress->GetCoins(EReflectionsWorld::White) > 0)
        {
            Want(EReflectionsTip::Coin);
        }
    }
    if (bCanCrossWorlds)
    {
        Want(EReflectionsTip::CrossWorlds);
    }

    if (ActiveTip == EReflectionsTip::Count && PlayClock - LastTipEnded > 1.2f && TipQueue.Num() > 0
        && !IsNarratorSpeaking() && QueuedNarratorAt < 0.0f)
    {
        // Crossing is the most time-sensitive prompt; otherwise first come, first served.
        const EReflectionsTip Next = TipQueue.Contains(EReflectionsTip::CrossWorlds) ? EReflectionsTip::CrossWorlds : TipQueue[0];
        ShowTip(Next);
    }
}

// ---- Checkpoints -------------------------------------------------------------------------------------------

void UReflectionsGameFlowWorldSubsystem::HandleWorldChanged(EReflectionsWorld From, EReflectionsWorld To)
{
    if (bPlaying && !bApplyingCheckpoint && Clock >= SuppressAutosaveUntil)
    {
        ScheduleCheckpoint(TEXT("World jump"));
    }
}

void UReflectionsGameFlowWorldSubsystem::HandlePagesChanged(int32 Pages, int32 PagesForBook)
{
    if (bPlaying && !bApplyingCheckpoint)
    {
        ScheduleCheckpoint(TEXT("Page"));
    }
}

void UReflectionsGameFlowWorldSubsystem::HandleInfectionChanged(int32 Count, int32 Cap)
{
    InfectionChangedAt = Clock;
}

void UReflectionsGameFlowWorldSubsystem::HandlePickedUp(APawn* Collector)
{
    // The pickup destroys itself right after this broadcast; the next tick sees which one went.
    bPickupEventPending = true;
}

void UReflectionsGameFlowWorldSubsystem::ScheduleCheckpoint(const FString& Reason, int32 Frames)
{
    PendingCheckpointReason = Reason;
    PendingCheckpointFrames = FMath::Max(PendingCheckpointFrames, Frames);
}

void UReflectionsGameFlowWorldSubsystem::TickPendingCheckpoint()
{
    if (PendingCheckpointFrames < 0)
    {
        return;
    }
    // SeparateMaps: world jump places the hero at the arrival point on a short timer after the map opens.
    const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    if (Progress && Progress->PendingArrival.bValid)
    {
        PendingCheckpointFrames = FMath::Max(PendingCheckpointFrames, 3);
        return;
    }
    if (--PendingCheckpointFrames >= 0)
    {
        return;
    }
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        if (!Flow->IsGameOver() && !Flow->SaveCheckpoint(PendingCheckpointReason))
        {
            PendingCheckpointFrames = 5;  // no pawn yet (or defeated): try again shortly
        }
    }
}

void UReflectionsGameFlowWorldSubsystem::TrackPickups()
{
    if (bPickupEventPending)
    {
        bPickupEventPending = false;
        for (int32 Index = WatchedPickups.Num() - 1; Index >= 0; --Index)
        {
            const FWatchedPickup& Watched = WatchedPickups[Index];
            const AReflectionsWorldPickup* Pickup = Watched.Actor.Get();
            if (!Pickup || Pickup->IsActorBeingDestroyed())
            {
                CollectedPickups.AddUnique(Watched.Name);
                if (!Watched.PageId.IsNone())
                {
                    CollectedPageIds.AddUnique(Watched.PageId);
                }
                WatchedPickups.RemoveAtSwap(Index);
            }
        }
    }
    if (PlayClock - PickupScanClock < 1.0f)
    {
        return;
    }
    PickupScanClock = PlayClock;
    for (TActorIterator<AReflectionsWorldPickup> It(GetWorld()); It; ++It)
    {
        AReflectionsWorldPickup* Pickup = *It;
        // Only level-placed pickups: their names are stable across a reload. Dropped coins are not tracked.
        if (!Pickup->IsNetStartupActor() || Pickup->IsActorBeingDestroyed())
        {
            continue;
        }
        const bool bKnown = WatchedPickups.ContainsByPredicate([Pickup](const FWatchedPickup& W) { return W.Actor.Get() == Pickup; });
        if (bKnown)
        {
            continue;
        }
        FWatchedPickup Entry;
        Entry.Actor = Pickup;
        Entry.Name = Pickup->GetName();
        if (const AReflectionsBookPagePickup* Page = Cast<AReflectionsBookPagePickup>(Pickup))
        {
            Entry.PageId = Page->PageId.IsNone() ? Page->GetFName() : Page->PageId;
        }
        Pickup->OnPickedUp.AddUniqueDynamic(this, &UReflectionsGameFlowWorldSubsystem::HandlePickedUp);
        WatchedPickups.Add(Entry);
    }
}

bool UReflectionsGameFlowWorldSubsystem::CaptureCheckpoint(const FString& Reason, FReflectionsCheckpoint& Out) const
{
    APawn* CurrentPawn = Pawn.Get();
    if (!CurrentPawn)
    {
        return false;
    }
    bool bDefeated = false;
    if (UObject* Driver = FindPawnComponent(TEXT("ReflectionsSampleSpellDriver")))
    {
        ReflectionsFlow::CallBool(Driver, TEXT("IsDefeated"), bDefeated);
    }
    if (bDefeated)
    {
        return false;
    }
    Out = FReflectionsCheckpoint();
    Out.bValid = true;
    Out.MapPath = ReflectionsFlow::MapPathOf(GetWorld());
    Out.Location = CurrentPawn->GetActorLocation();
    Out.Rotation = CurrentPawn->GetActorRotation();
    const APlayerController* PC = Controller.Get();
    Out.ControlRotation = PC ? PC->GetControlRotation() : Out.Rotation;
    Out.Reason = Reason;
    Out.SavedAt = FDateTime::UtcNow();
    Out.UsedAt = Out.SavedAt;
    Out.CollectedPickups = CollectedPickups;

    if (UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this))
    {
        Out.World = Progress->GetCurrentWorld();
        const UReflectionsWorldJumpWorldSubsystem* Worlds = UReflectionsWorldJumpWorldSubsystem::Get(this);
        Out.bWorldJumpActive = Worlds && Worlds->IsWorldJumpActive();
        const TMap<EReflectionsWorld, int32> Coins = Progress->GetAllCoins();
        for (const EReflectionsWorld World : {EReflectionsWorld::Gray, EReflectionsWorld::Red, EReflectionsWorld::White})
        {
            const int32* Count = Coins.Find(World);
            Out.Coins.Add(Count ? *Count : 0);
        }
        Out.Pages = Progress->GetPages();
        Out.Keys = Progress->GetKeys();
    }

    if (const UReflectionsHealthComponent* Health = CurrentPawn->FindComponentByClass<UReflectionsHealthComponent>())
    {
        Out.Health = Health->Health;
    }
    if (UObject* Driver = FindPawnComponent(TEXT("ReflectionsSampleSpellDriver")))
    {
        float Mana = -1.0f;
        if (ReflectionsFlow::CallFloat(Driver, TEXT("GetMagic"), Mana))
        {
            Out.Mana = Mana;
        }
    }
    if (const UReflectionsReputationSubsystem* Reputation = GetWorld()->GetSubsystem<UReflectionsReputationSubsystem>())
    {
        Out.bHasReputation = true;
        Out.Reputation = Reputation->GetReputation(CurrentPawn);
    }
    if (const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        Out.InfectionCount = Flow->GetInfectionCount();
        Out.InfectionCap = Flow->GetInfectionCap();
    }
    return true;
}

bool UReflectionsGameFlowWorldSubsystem::ApplyCheckpoint(const FReflectionsCheckpoint& Checkpoint)
{
    APawn* CurrentPawn = Pawn.Get();
    if (!Checkpoint.bValid || !CurrentPawn)
    {
        return false;
    }
    TGuardValue<bool> Guard(bApplyingCheckpoint, true);

    if (UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this))
    {
        // Quiet restore: replaces coins, pages and keys without firing OnCoinsChanged / OnPagesChanged /
        // OnBookComplete / OnKeyAdded (so no pickup sounds and no second finale); OnProgressRestored lets HUDs resync.
        TMap<EReflectionsWorld, int32> Coins;
        const EReflectionsWorld Worlds[] = {EReflectionsWorld::Gray, EReflectionsWorld::Red, EReflectionsWorld::White};
        for (int32 Index = 0; Index < UE_ARRAY_COUNT(Worlds); ++Index)
        {
            if (Checkpoint.Coins.IsValidIndex(Index) && Checkpoint.Coins[Index] > 0)
            {
                Coins.Add(Worlds[Index], Checkpoint.Coins[Index]);
            }
        }
        Progress->RestoreProgress(Coins, Checkpoint.Pages, Checkpoint.Keys);
        if (Checkpoint.bWorldJumpActive)
        {
            // Re-tints the coat and swaps the music for the saved side (world jump reacts to OnWorldChanged).
            Progress->SetCurrentWorld(Checkpoint.World, true);
        }
    }

    CollectedPickups = Checkpoint.CollectedPickups;
    CollectedPageIds = Checkpoint.Pages;
    for (TActorIterator<AReflectionsWorldPickup> It(GetWorld()); It; ++It)
    {
        if (It->IsNetStartupActor() && CollectedPickups.Contains(It->GetName()))
        {
            It->Destroy();
        }
    }

    CurrentPawn->SetActorLocationAndRotation(Checkpoint.Location, FRotator(0.0f, Checkpoint.Rotation.Yaw, 0.0f), false, nullptr, ETeleportType::TeleportPhysics);
    if (ACharacter* Character = Cast<ACharacter>(CurrentPawn))
    {
        if (UCharacterMovementComponent* Movement = Character->GetCharacterMovement())
        {
            Movement->StopMovementImmediately();
        }
    }
    TArray<AActor*> Actors;
    CurrentPawn->GetAttachedActors(Actors, true, true);
    Actors.Add(CurrentPawn);
    for (AActor* Actor : Actors)
    {
        TInlineComponentArray<USkeletalMeshComponent*> Meshes(Actor);
        for (USkeletalMeshComponent* Mesh : Meshes)
        {
            Mesh->ForceClothNextUpdateTeleportAndReset();
        }
    }
    if (APlayerController* PC = Controller.Get())
    {
        PC->SetControlRotation(Checkpoint.ControlRotation);
        if (PC->PlayerCameraManager)
        {
            PC->PlayerCameraManager->SetGameCameraCutThisFrame();
        }
    }
    PushRespawnPoint();
    // World jump confirms the side from the new location within ~0.1 s; that OnWorldChanged is not a new checkpoint.
    SuppressAutosaveUntil = Clock + 1.0f;

    UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    const bool bFromSave = Flow && Flow->bRestoreVitals;
    if (Flow)
    {
        Flow->bRestoreVitals = false;
    }
    if (Checkpoint.bHasReputation)
    {
        // Reputation lives per map (it reset with the reload): put the saved score back.
        if (UReflectionsReputationSubsystem* Reputation = GetWorld()->GetSubsystem<UReflectionsReputationSubsystem>())
        {
            const float Delta = Checkpoint.Reputation - Reputation->GetReputation(CurrentPawn);
            if (!FMath::IsNearlyZero(Delta))
            {
                Reputation->AdjustReputation(CurrentPawn, Delta);
            }
        }
    }
    if (bFromSave)
    {
        // Loading a slot brings back the saved health and mana; Try again and Restart start fresh.
        RestoreVitals(Checkpoint);
    }
    if (Flow)
    {
        // The Tarnish meter keeps its saved count through every restore (playtest run 3).
        Flow->RestoreInfectionPlaceholders(Checkpoint.InfectionCount);
    }
    ShowToast(bFromSave ? FText::Format(FLOWTEXT("Save.Loaded", "Loaded: {0}"), FText::FromString(Checkpoint.Reason))
                        : LOCTEXT("Restored", "Back at your last checkpoint"));
    UE_LOG(LogReflectionsGameFlowWorld, Log, TEXT("Restored checkpoint (%s) at %s%s."), *Checkpoint.Reason, *Checkpoint.Location.ToCompactString(),
        bFromSave ? TEXT(" (loaded save)") : TEXT(""));
    if (Flow)
    {
        // Quests, lives, the villain...: their own state (GetSaveData) goes back now.
        const FReflectionsCheckpoint Restored = Checkpoint;
        Flow->OnCheckpointRestored.Broadcast(Restored);
    }
    return true;
}

void UReflectionsGameFlowWorldSubsystem::NotifyCheckpointSaved()
{
    PushRespawnPoint();
    if (!IsCutscenePlaying())
    {
        ShowToast(LOCTEXT("Saved", "Checkpoint saved"));
    }
}

void UReflectionsGameFlowWorldSubsystem::PushRespawnPoint()
{
    const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    if (!Flow || !Flow->HasCheckpoint() || Flow->GetCheckpoint().MapPath != ReflectionsFlow::MapPathOf(GetWorld()))
    {
        return;
    }
    if (UObject* Driver = FindPawnComponent(TEXT("ReflectionsSampleSpellDriver")))
    {
        const FReflectionsCheckpoint& Checkpoint = Flow->GetCheckpoint();
        ReflectionsFlow::CallWithTransform(Driver, TEXT("SetRespawnTransform"),
            FTransform(FRotator(0.0f, Checkpoint.Rotation.Yaw, 0.0f), Checkpoint.Location));
    }
}

void UReflectionsGameFlowWorldSubsystem::TickRespawn()
{
    UObject* Driver = FindPawnComponent(TEXT("ReflectionsSampleSpellDriver"));
    if (!Driver)
    {
        return;
    }
    bool bDefeated = false;
    ReflectionsFlow::CallBool(Driver, TEXT("IsDefeated"), bDefeated);
    if (bDefeated && !bWasDefeated)
    {
        DefeatedAt = Clock;
        bDeathShown = false;
    }
    if (bDefeated && !bDeathShown && DefeatedAt >= 0.0f && Clock - DefeatedAt >= 1.2f && CVarGameFlowDeathScreen.GetValueOnGameThread() != 0)
    {
        const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
        if (!(Flow && Flow->IsGameOver()) && !IsCutscenePlaying())
        {
            // After the fall reads: pause and offer the respawn (default) or a load. The driver's timer waits.
            bDeathShown = true;
            bWasDefeated = bDefeated;
            ShowDeath();
            return;
        }
    }
    if (bWasDefeated && !bDefeated)
    {
        const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
        if (Flow && Flow->HasCheckpoint() && Flow->GetCheckpoint().MapPath == ReflectionsFlow::MapPathOf(GetWorld()))
        {
            const FReflectionsCheckpoint& Checkpoint = Flow->GetCheckpoint();
            APawn* CurrentPawn = Pawn.Get();
            // The driver (SetRespawnTransform) already put the hero at the checkpoint position and yaw. Without the
            // hook, move the hero there now: same frame as the driver's respawn, before it renders.
            if (!Driver->FindFunction(TEXT("SetRespawnTransform")) && CurrentPawn
                && FVector::DistSquared(CurrentPawn->GetActorLocation(), Checkpoint.Location) > FMath::Square(150.0f))
            {
                CurrentPawn->SetActorLocationAndRotation(Checkpoint.Location, FRotator(0.0f, Checkpoint.Rotation.Yaw, 0.0f), false, nullptr, ETeleportType::TeleportPhysics);
            }
            // Both paths: the camera looks the way it did at the checkpoint, with a cut instead of a swoop.
            if (APlayerController* PC = Controller.Get())
            {
                PC->SetControlRotation(Checkpoint.ControlRotation);
                if (PC->PlayerCameraManager)
                {
                    PC->PlayerCameraManager->SetGameCameraCutThisFrame();
                }
            }
            ShowToast(LOCTEXT("Respawned", "Back at your last checkpoint"));
            UE_LOG(LogReflectionsGameFlowWorld, Log, TEXT("Respawned at the checkpoint (%s)."), *Checkpoint.Location.ToCompactString());
        }
    }
    bWasDefeated = bDefeated;
}

// ---- Debug input -------------------------------------------------------------------------------------------

bool UReflectionsGameFlowWorldSubsystem::SimulateKey(const FString& KeyName)
{
    const FKey Key(*KeyName);
    if (!Key.IsValid() || !FSlateApplication::IsInitialized())
    {
        return false;
    }
    FSlateApplication& Slate = FSlateApplication::Get();
    const FKeyEvent Down(Key, FModifierKeysState(), 0, false, 0, 0);
    const FKeyEvent Up(Key, FModifierKeysState(), 0, false, 0, 0);
    const bool bHandled = Slate.ProcessKeyDownEvent(Down);
    Slate.ProcessKeyUpEvent(Up);
    return bHandled;
}

#undef LOCTEXT_NAMESPACE
