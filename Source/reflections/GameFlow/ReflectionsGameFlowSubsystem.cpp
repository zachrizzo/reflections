#include "GameFlow/ReflectionsGameFlowSubsystem.h"

#include "Async/Async.h"
#include "AudioDevice.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/GameViewportClient.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Framework/Application/IInputProcessor.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFlow/ReflectionsGameFlowSave.h"
#include "GameFlow/ReflectionsGameFlowSlate.h"
#include "GameFlow/ReflectionsGameFlowText.h"
#include "GameFlow/ReflectionsGameFlowWorldSubsystem.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Lives/ReflectionsLivesMemory.h"
#include "Quests/ReflectionsQuestSubsystem.h"
#include "Misc/PackageName.h"
#include "MoviePlayer.h"
#include "Tasks/Task.h"
#include "UObject/Package.h"
#include "Widgets/SWindow.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsGameFlow, Log, All);

#define LOCTEXT_NAMESPACE "ReflectionsGameFlow"
#define FLOWTEXT(Key, Default) ReflectionsFlowText::Get(TEXT(Key), LOCTEXT(Key, Default))

namespace
{
    FReflectionsSaveBlob* FindBlob(TArray<FReflectionsSaveBlob>& Blobs, FName System)
    {
        return Blobs.FindByPredicate([System](const FReflectionsSaveBlob& Blob) { return Blob.System == System; });
    }

    void SetBlob(TArray<FReflectionsSaveBlob>& Blobs, FName System, const TArray<uint8>& Data)
    {
        if (FReflectionsSaveBlob* Existing = FindBlob(Blobs, System))
        {
            Existing->Data = Data;
            return;
        }
        FReflectionsSaveBlob& Added = Blobs.AddDefaulted_GetRef();
        Added.System = System;
        Added.Data = Data;
    }

    // Serialize writes across game instances, which share the same save slots.
    UE::Tasks::TTask<bool> GLastSaveWrite;

    FReflectionsSaveSlotInfo MakeSlotInfo(int32 Slot, const FReflectionsCheckpoint& Checkpoint)
    {
        FReflectionsSaveSlotInfo Info;
        Info.Slot = Slot;
        Info.bUsed = Checkpoint.bValid;
        Info.SavedAt = Checkpoint.SavedAt;
        Info.UsedAt = Checkpoint.UsedAt > Checkpoint.SavedAt ? Checkpoint.UsedAt : Checkpoint.SavedAt;
        Info.World = Checkpoint.World;
        Info.Pages = Checkpoint.Pages.Num();
        Info.InfectionCount = Checkpoint.InfectionCount;
        Info.MapPath = Checkpoint.MapPath;
        Info.Reason = Checkpoint.Reason;
        return Info;
    }
}

static TAutoConsoleVariable<FString> CVarGameFlowNewGameMap(
    TEXT("GameFlow.NewGameMap"), TEXT(""),
    TEXT("Map that Start / New Game plays (long package name). Empty: NewGameMap from config, else the loaded map."));

static TAutoConsoleVariable<int32> CVarGameFlowInfectionCap(
    TEXT("GameFlow.InfectionCap"), 0,
    TEXT("Infection cap override (0 = use the subsystem's cap)."));

/** Watches raw input so prompts can show key or button names for the device in use. */
class FReflectionsFlowInputTracker : public IInputProcessor
{
public:
    bool bGamepad = false;

    virtual void Tick(const float DeltaTime, FSlateApplication& SlateApp, TSharedRef<ICursor> Cursor) override {}

    virtual bool HandleKeyDownEvent(FSlateApplication& SlateApp, const FKeyEvent& InKeyEvent) override
    {
        bGamepad = InKeyEvent.GetKey().IsGamepadKey();
        return false;
    }

    virtual bool HandleAnalogInputEvent(FSlateApplication& SlateApp, const FAnalogInputEvent& InAnalogInputEvent) override
    {
        if (InAnalogInputEvent.GetKey().IsGamepadKey() && FMath::Abs(InAnalogInputEvent.GetAnalogValue()) > 0.35f)
        {
            bGamepad = true;
        }
        return false;
    }

    virtual bool HandleMouseMoveEvent(FSlateApplication& SlateApp, const FPointerEvent& MouseEvent) override
    {
        if (MouseEvent.GetCursorDelta().SizeSquared() > 9.0f)
        {
            bGamepad = false;
        }
        return false;
    }

    virtual bool HandleMouseButtonDownEvent(FSlateApplication& SlateApp, const FPointerEvent& MouseEvent) override
    {
        bGamepad = false;
        return false;
    }

    virtual const TCHAR* GetDebugName() const override { return TEXT("ReflectionsFlowInputTracker"); }
};

UReflectionsGameFlowSubsystem* UReflectionsGameFlowSubsystem::Get(const UObject* WorldContext)
{
    const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
    return GameInstance ? GameInstance->GetSubsystem<UReflectionsGameFlowSubsystem>() : nullptr;
}

void UReflectionsGameFlowSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);

    if (UGameplayStatics::DoesSaveGameExist(SlotName(), 0))
    {
        if (const UReflectionsGameFlowSave* Save = Cast<UReflectionsGameFlowSave>(UGameplayStatics::LoadGameFromSlot(SlotName(), 0)))
        {
            Checkpoint = Save->Checkpoint;
            SeenTips = Save->SeenTips;
        }
    }

    // Read every slot's header now, behind the startup screen, so the title and the save menus never touch the disk.
    for (int32 Slot = ReflectionsSaveSlots::Quick; Slot < ReflectionsSaveSlots::Count; ++Slot)
    {
        GetSaveSlotInfo(Slot);
    }

    if (!GIsEditor)
    {
        // Packaged and -game: the first map load shows the loading screen too, and it fades into the title. (Not in
        // PIE, where other sessions' tests expect play at once.)
        BeginLoadingScreen(LOCTEXT("LoadingStatus", "Loading..."));
        SetupMoviePlayerLoadingScreen();
    }

    if (FSlateApplication::IsInitialized())
    {
        InputTracker = MakeShared<FReflectionsFlowInputTracker>();
        FSlateApplication::Get().RegisterInputPreProcessor(InputTracker);
    }
}

void UReflectionsGameFlowSubsystem::Deinitialize()
{
    if (DeferredTicker.IsValid())
    {
        FTSTicker::GetCoreTicker().RemoveTicker(DeferredTicker);
        DeferredTicker.Reset();
    }
    FlushSaveWrites();
    TravelAssets.Reset();
    if (InputTracker.IsValid() && FSlateApplication::IsInitialized())
    {
        FSlateApplication::Get().UnregisterInputPreProcessor(InputTracker);
    }
    InputTracker.Reset();
    Super::Deinitialize();
}

UReflectionsGameFlowWorldSubsystem* UReflectionsGameFlowSubsystem::GetWorldFlow() const
{
    const UGameInstance* GameInstance = GetGameInstance();
    UWorld* World = GameInstance ? GameInstance->GetWorld() : nullptr;
    return World ? World->GetSubsystem<UReflectionsGameFlowWorldSubsystem>() : nullptr;
}

bool UReflectionsGameFlowSubsystem::IsUsingGamepad() const
{
    return InputTracker.IsValid() && InputTracker->bGamepad;
}

// ---- Infection ---------------------------------------------------------------------------------------------

void UReflectionsGameFlowSubsystem::ReportInfected(AActor* Host)
{
    if (Host)
    {
        bool bAlreadyCounted = false;
        InfectedHosts.Add(Host, &bAlreadyCounted);
        if (bAlreadyCounted)
        {
            return;
        }
        if (RestoredPlaceholders > 0 && AnonymousInfected > 0)
        {
            // A saved host coming back after a restore: it replaces its placeholder (the count stays the same).
            --RestoredPlaceholders;
            --AnonymousInfected;
            BroadcastInfection();
            return;
        }
    }
    else
    {
        ++AnonymousInfected;
    }
    UE_LOG(LogReflectionsGameFlow, Log, TEXT("Infected: %s (%d / %d)."), Host ? *Host->GetName() : TEXT("anonymous"),
        GetInfectionCount(), GetInfectionCap());
    BroadcastInfection();
    CheckInfectionCap();
}

void UReflectionsGameFlowSubsystem::ReportCured(AActor* Host)
{
    bool bChanged = false;
    if (Host)
    {
        bChanged = InfectedHosts.Remove(Host) > 0;
    }
    else if (AnonymousInfected > 0)
    {
        --AnonymousInfected;
        RestoredPlaceholders = FMath::Min(RestoredPlaceholders, AnonymousInfected);
        bChanged = true;
    }
    if (bChanged)
    {
        BroadcastInfection();
    }
}

int32 UReflectionsGameFlowSubsystem::GetInfectionCount() const
{
    return InfectedHosts.Num() + AnonymousInfected;
}

int32 UReflectionsGameFlowSubsystem::GetInfectionCap() const
{
    if (const int32 CVarCap = CVarGameFlowInfectionCap.GetValueOnGameThread(); CVarCap > 0)
    {
        return CVarCap;
    }
    return FMath::Max(1, CapOverride > 0 ? CapOverride : DefaultInfectionCap);
}

float UReflectionsGameFlowSubsystem::GetInfectionFraction() const
{
    return FMath::Clamp(static_cast<float>(GetInfectionCount()) / static_cast<float>(GetInfectionCap()), 0.0f, 1.0f);
}

bool UReflectionsGameFlowSubsystem::IsInfected(const AActor* Host) const
{
    return Host && InfectedHosts.Contains(TWeakObjectPtr<AActor>(const_cast<AActor*>(Host)));
}

void UReflectionsGameFlowSubsystem::SetInfectionCap(int32 Cap)
{
    CapOverride = FMath::Max(0, Cap);
    BroadcastInfection();
    CheckInfectionCap();
}

void UReflectionsGameFlowSubsystem::RestoreInfectionPlaceholders(int32 Count)
{
    const int32 Missing = FMath::Max(0, Count - GetInfectionCount());
    if (Missing <= 0)
    {
        return;
    }
    AnonymousInfected += Missing;
    RestoredPlaceholders += Missing;
    UE_LOG(LogReflectionsGameFlow, Log, TEXT("Tarnish restored to %d (%d placeholders until the villain re-reports its hosts)."), GetInfectionCount(), Missing);
    BroadcastInfection();
}

void UReflectionsGameFlowSubsystem::ResetInfection()
{
    InfectedHosts.Reset();
    AnonymousInfected = 0;
    RestoredPlaceholders = 0;
    bLosePending = false;
    BroadcastInfection();
}

void UReflectionsGameFlowSubsystem::PruneStaleHosts()
{
    const int32 Before = InfectedHosts.Num();
    for (auto It = InfectedHosts.CreateIterator(); It; ++It)
    {
        if (!It->IsValid())
        {
            It.RemoveCurrent();
        }
    }
    if (InfectedHosts.Num() != Before)
    {
        BroadcastInfection();
    }
}

void UReflectionsGameFlowSubsystem::BroadcastInfection()
{
    OnInfectionChanged.Broadcast(GetInfectionCount(), GetInfectionCap());
}

void UReflectionsGameFlowSubsystem::CheckInfectionCap()
{
    if (!IsGameOver() && !bLosePending && GetInfectionCount() >= GetInfectionCap())
    {
        bLosePending = true;
        UE_LOG(LogReflectionsGameFlow, Log, TEXT("Infection reached the cap (%d): game lost."), GetInfectionCap());
        ShowLose();
    }
}

// ---- Win / lose --------------------------------------------------------------------------------------------

void UReflectionsGameFlowSubsystem::ShowVictory()
{
    if (bWon || bLost)
    {
        return;
    }
    bWon = true;
    UE_LOG(LogReflectionsGameFlow, Log, TEXT("Victory."));
    OnVictory.Broadcast();
    if (UReflectionsGameFlowWorldSubsystem* Flow = GetWorldFlow())
    {
        Flow->ShowVictory();
    }
}

void UReflectionsGameFlowSubsystem::ShowLose()
{
    if (bWon || bLost)
    {
        return;
    }
    bLost = true;
    OnGameLost.Broadcast();
    if (UReflectionsGameFlowWorldSubsystem* Flow = GetWorldFlow())
    {
        Flow->ShowLose();
    }
}

// ---- Checkpoints -------------------------------------------------------------------------------------------

bool UReflectionsGameFlowSubsystem::SaveCheckpoint(const FString& Reason)
{
    return CaptureCheckpoint(Reason) && WriteSave();
}

bool UReflectionsGameFlowSubsystem::CaptureCheckpoint(const FString& Reason)
{
    if (bTravelPending)
    {
        return false;  // a load or restart is opening its map: this world's state must not overwrite it
    }
    UReflectionsGameFlowWorldSubsystem* Flow = GetWorldFlow();
    FReflectionsCheckpoint New;
    if (!Flow || !Flow->CaptureCheckpoint(Reason, New))
    {
        return false;
    }
    RecordCheckpoint(New);
    return true;
}

void UReflectionsGameFlowSubsystem::SetCheckpoint(const FReflectionsCheckpoint& InCheckpoint)
{
    RecordCheckpoint(InCheckpoint);
    WriteSave();
}

void UReflectionsGameFlowSubsystem::RecordCheckpoint(const FReflectionsCheckpoint& InCheckpoint)
{
    Checkpoint = InCheckpoint;
    UE_LOG(LogReflectionsGameFlow, Log, TEXT("Checkpoint (%s): %s at %s, coins %s, %d pages."), *Checkpoint.Reason,
        *Checkpoint.MapPath, *Checkpoint.Location.ToCompactString(),
        *FString::JoinBy(Checkpoint.Coins, TEXT("/"), [](int32 Value) { return FString::FromInt(Value); }),
        Checkpoint.Pages.Num());
    {
        // Handlers add their state to the same snapshot before it is serialized.
        TGuardValue<bool> Broadcasting(bBroadcastingCheckpoint, true);
        OnCheckpointSaved.Broadcast(Checkpoint);
    }
    SaveIndicatorUntil = FPlatformTime::Seconds() + 1.1;
    if (UReflectionsGameFlowWorldSubsystem* Flow = GetWorldFlow())
    {
        Flow->NotifyCheckpointSaved();
    }
}

void UReflectionsGameFlowSubsystem::ClearCheckpoint()
{
    Checkpoint = FReflectionsCheckpoint();
    WriteSave();
}

// ---- Save slots --------------------------------------------------------------------------------------------

FString UReflectionsGameFlowSubsystem::SaveSlotFileName(int32 Slot)
{
    if (Slot == ReflectionsSaveSlots::Autosave)
    {
        return SlotName();
    }
    if (Slot == ReflectionsSaveSlots::Quick)
    {
        return TEXT("Reflections_QuickSave");
    }
    return FString::Printf(TEXT("Reflections_Save_%d"), Slot - ReflectionsSaveSlots::FirstManual + 1);
}

FText UReflectionsGameFlowSubsystem::GetSlotDisplayName(int32 Slot)
{
    if (Slot == ReflectionsSaveSlots::Autosave)
    {
        return FLOWTEXT("Save.Autosave", "Autosave");
    }
    if (Slot == ReflectionsSaveSlots::Quick)
    {
        return FLOWTEXT("Save.Quick", "Quick save");
    }
    return FText::Format(FLOWTEXT("Save.Slot", "Slot {0}"), Slot - ReflectionsSaveSlots::FirstManual + 1);
}

bool UReflectionsGameFlowSubsystem::SaveToSlot(int32 Slot)
{
    return SaveSlot(Slot, true, {});
}

bool UReflectionsGameFlowSubsystem::SaveToSlotAsync(int32 Slot, TFunction<void(bool)> OnSaved)
{
    return SaveSlot(Slot, false, MoveTemp(OnSaved));
}

bool UReflectionsGameFlowSubsystem::SaveSlot(int32 Slot, bool bWait, TFunction<void(bool)> OnSaved)
{
    if (Slot < ReflectionsSaveSlots::Quick || Slot >= ReflectionsSaveSlots::Count || IsGameOver())
    {
        return false;
    }
    // A save is also a checkpoint: every system stores its state through OnCheckpointSaved first.
    const FString Reason = Slot == ReflectionsSaveSlots::Quick ? FString(TEXT("Quick save"))
        : FString::Printf(TEXT("Slot %d"), Slot - ReflectionsSaveSlots::FirstManual + 1);
    return CaptureCheckpoint(Reason) && WriteSave(Slot, bWait, MoveTemp(OnSaved));
}

bool UReflectionsGameFlowSubsystem::LoadFromSlot(int32 Slot)
{
    if (bTravelPending || bQuitPending || Slot < 0 || Slot >= ReflectionsSaveSlots::Count)
    {
        return false;
    }
    FlushSaveWrites();  // a save of this slot may still be on its way to the disk
    FReflectionsCheckpoint Loaded;
    if (Slot == ReflectionsSaveSlots::Autosave && Checkpoint.bValid)
    {
        Loaded = Checkpoint;
    }
    else
    {
        const UReflectionsGameFlowSave* Save = Cast<UReflectionsGameFlowSave>(UGameplayStatics::LoadGameFromSlot(SaveSlotFileName(Slot), 0));
        if (!Save || Save->Version > UReflectionsGameFlowSave::CurrentVersion)
        {
            return false;
        }
        Loaded = Save->Checkpoint;
    }
    if (!Loaded.bValid || Loaded.MapPath.IsEmpty() ||
        (Loaded.MapPath != CurrentMapPath() && !FPackageName::DoesPackageExist(Loaded.MapPath)))
    {
        return false;
    }
    // This state is now the one in use: it (and its slot) sort as the newest, ahead of saves from the run left behind.
    Loaded.UsedAt = FDateTime::UtcNow();
    UE_LOG(LogReflectionsGameFlow, Log, TEXT("Loading %s (%s, %s)."), *SaveSlotFileName(Slot), *Loaded.Reason, *Loaded.SavedAt.ToString());
    Checkpoint = MoveTemp(Loaded);
    WriteSave(Slot == ReflectionsSaveSlots::Autosave ? INDEX_NONE : Slot);
    ResumeSavedCheckpoint();
    return true;
}

bool UReflectionsGameFlowSubsystem::QuickSave()
{
    return SaveToSlot(ReflectionsSaveSlots::Quick);
}

bool UReflectionsGameFlowSubsystem::QuickLoad()
{
    return GetSaveSlotInfo(ReflectionsSaveSlots::Quick).bUsed && LoadFromSlot(ReflectionsSaveSlots::Quick);
}

FReflectionsSaveSlotInfo UReflectionsGameFlowSubsystem::GetSaveSlotInfo(int32 Slot) const
{
    if (Slot == ReflectionsSaveSlots::Autosave)
    {
        return MakeSlotInfo(Slot, Checkpoint);
    }
    if (const FReflectionsSaveSlotInfo* Cached = SlotCache.Find(Slot))
    {
        return *Cached;
    }
    FReflectionsSaveSlotInfo Info;
    Info.Slot = Slot;
    if (Slot > ReflectionsSaveSlots::Autosave && Slot < ReflectionsSaveSlots::Count)
    {
        const FString File = SaveSlotFileName(Slot);
        if (const UReflectionsGameFlowSave* Save = Cast<UReflectionsGameFlowSave>(UGameplayStatics::LoadGameFromSlot(File, 0));
            Save && Save->Version <= UReflectionsGameFlowSave::CurrentVersion)
        {
            Info = MakeSlotInfo(Slot, Save->Checkpoint);
        }
    }
    SlotCache.Add(Slot, Info);
    return Info;
}

int32 UReflectionsGameFlowSubsystem::GetNewestSaveSlot(bool bExcludeAutosave) const
{
    int32 Best = INDEX_NONE;
    FDateTime BestTime;
    for (int32 Slot = bExcludeAutosave ? ReflectionsSaveSlots::Quick : ReflectionsSaveSlots::Autosave; Slot < ReflectionsSaveSlots::Count; ++Slot)
    {
        const FReflectionsSaveSlotInfo Info = GetSaveSlotInfo(Slot);
        // Ties (a manual save is also the autosave) go to the lower slot: the autosave, which is in memory.
        if (Info.bUsed && (Best == INDEX_NONE || Info.UsedAt > BestTime))
        {
            Best = Slot;
            BestTime = Info.UsedAt;
        }
    }
    return Best;
}

void UReflectionsGameFlowSubsystem::SetSaveData(FName System, const TArray<uint8>& Data)
{
    if (System.IsNone())
    {
        return;
    }
    SetBlob(Checkpoint.SystemData, System, Data);
    if (!bBroadcastingCheckpoint && Checkpoint.bValid)
    {
        WriteSave();  // stored outside a checkpoint: keep the autosave file in step
    }
}

bool UReflectionsGameFlowSubsystem::GetSaveData(FName System, TArray<uint8>& Data) const
{
    const FReflectionsSaveBlob* Blob = Checkpoint.SystemData.FindByPredicate([System](const FReflectionsSaveBlob& B) { return B.System == System; });
    if (!Blob)
    {
        return false;
    }
    Data = Blob->Data;
    return true;
}

void UReflectionsGameFlowSubsystem::MarkTipSeen(EReflectionsTip Tip)
{
    const int32 Bit = 1 << static_cast<int32>(Tip);
    if ((SeenTips & Bit) == 0)
    {
        SeenTips |= Bit;
        WriteSave();
    }
}

void UReflectionsGameFlowSubsystem::ResetTips()
{
    SeenTips = 0;
    WriteSave();
}

bool UReflectionsGameFlowSubsystem::WriteSave(int32 Slot, bool bWait, TFunction<void(bool)> OnSaved)
{
    UReflectionsGameFlowSave* Save = NewObject<UReflectionsGameFlowSave>();
    Save->Version = UReflectionsGameFlowSave::CurrentVersion;
    Save->Checkpoint = Checkpoint;
    Save->SeenTips = SeenTips;
    TArray<uint8> Bytes;
    if (!UGameplayStatics::SaveGameToMemory(Save, Bytes)) return false;
    const FString Autosave = SlotName();
    const FString Extra = Slot == INDEX_NONE ? FString() : SaveSlotFileName(Slot);
    const FReflectionsSaveSlotInfo Info = MakeSlotInfo(Slot, Checkpoint);
    const TWeakObjectPtr<UReflectionsGameFlowSubsystem> WeakThis(this);
    TArray<UE::Tasks::FTask> Prerequisites;
    if (GLastSaveWrite.IsValid()) Prerequisites.Add(GLastSaveWrite);
    GLastSaveWrite = UE::Tasks::Launch(UE_SOURCE_LOCATION,
        [Bytes = MoveTemp(Bytes), Autosave, Extra, Info, WeakThis, bWait, OnSaved = MoveTemp(OnSaved)]() mutable
    {
        const bool bExtraSaved = Extra.IsEmpty() || UGameplayStatics::SaveDataToSlot(Bytes, Extra, 0);
        const bool bAutosaved = UGameplayStatics::SaveDataToSlot(Bytes, Autosave, 0);
        if (!bExtraSaved || !bAutosaved)
        {
            UE_LOG(LogReflectionsGameFlow, Warning, TEXT("Save write failed (checkpoint: %d, slot %s: %d)."),
                bAutosaved, *Extra, bExtraSaved);
        }
        const bool bSaved = Extra.IsEmpty() ? bAutosaved : bExtraSaved;
        if (!bWait && (!Extra.IsEmpty() || OnSaved))
        {
            AsyncTask(ENamedThreads::GameThread, [WeakThis, Info, bSaved, OnSaved = MoveTemp(OnSaved)]() mutable
            {
                if (UReflectionsGameFlowSubsystem* Flow = WeakThis.Get())
                {
                    if (bSaved && Info.Slot != INDEX_NONE)
                    {
                        const FReflectionsSaveSlotInfo* Current = Flow->SlotCache.Find(Info.Slot);
                        if (!Current || Info.UsedAt >= Current->UsedAt) Flow->SlotCache.Add(Info.Slot, Info);
                    }
                    if (OnSaved) OnSaved(bSaved);
                }
            });
        }
        return bSaved;
    }, Prerequisites, UE::Tasks::ETaskPriority::BackgroundNormal);
    if (!bWait) return true;
    const bool bSaved = GLastSaveWrite.GetResult();
    if (bSaved && Slot != INDEX_NONE) SlotCache.Add(Slot, Info);
    return bSaved;
}

void UReflectionsGameFlowSubsystem::FlushSaveWrites()
{
    if (GLastSaveWrite.IsValid())
    {
        GLastSaveWrite.Wait();
        GLastSaveWrite = UE::Tasks::TTask<bool>();
    }
}

bool UReflectionsGameFlowSubsystem::IsSaveIndicatorOn() const
{
    return FPlatformTime::Seconds() < SaveIndicatorUntil;
}

void UReflectionsGameFlowSubsystem::BeginLoadingScreen(const FText& Status)
{
    bLoadingScreen = true;
    LoadingStatus = Status;
}

// ---- Flow --------------------------------------------------------------------------------------------------

FString UReflectionsGameFlowSubsystem::CurrentMapPath() const
{
    const UGameInstance* GameInstance = GetGameInstance();
    const UWorld* World = GameInstance ? GameInstance->GetWorld() : nullptr;
    return World ? UWorld::RemovePIEPrefix(World->GetOutermost()->GetName()) : FString();
}

void UReflectionsGameFlowSubsystem::OpenMap(const FString& MapPath)
{
    UGameInstance* GameInstance = GetGameInstance();
    UWorld* World = GameInstance ? GameInstance->GetWorld() : nullptr;
    if (!World || MapPath.IsEmpty())
    {
        return;
    }
    FString Target = MapPath;
    if (!FPackageName::DoesPackageExist(Target))
    {
        // A map that isn't cooked (or was renamed) would drop the engine back to the default map and spend the
        // start action there: stay in this map instead.
        UE_LOG(LogReflectionsGameFlow, Error, TEXT("Map %s does not exist in this build; reloading %s instead."), *Target, *CurrentMapPath());
        Target = CurrentMapPath();
    }
    TravelAssets.Reset();
    if (Target == CurrentMapPath())
    {
        // The hero's assets can be reused, but the old pawn and its level must be collected.
        const APlayerController* Player = World->GetFirstPlayerController();
        if (Player && Player->GetPawn())
        {
            TArray<AActor*> Parts;
            Player->GetPawn()->GetAttachedActors(Parts, true, true);
            Parts.Add(Player->GetPawn());
            const auto KeepAsset = [this](UObject* Asset)
            {
                if (Asset && !Asset->GetOutermost()->ContainsMap()) TravelAssets.Add(Asset);
            };
            KeepAsset(Player->GetClass());
            for (const AActor* Part : Parts)
            {
                KeepAsset(Part->GetClass());
                TInlineComponentArray<USkeletalMeshComponent*> Meshes(Part);
                for (USkeletalMeshComponent* Mesh : Meshes)
                {
                    KeepAsset(Mesh->GetSkeletalMeshAsset());
                    KeepAsset(Mesh->GetAnimClass());
                }
            }
        }
    }
    bTravelPending = true;
    // The click or key that got here runs before this frame's paint. Show the loading screen now and open the map a
    // few frames later, once that screen is on the monitor: LoadMap blocks the game thread for seconds, and the
    // screen used to freeze on the menu for the whole load.
    BeginLoadingScreen(LOCTEXT("LoadingStatus", "Loading..."));
    DeferredMap = Target;
    DeferredFrames = 3;
    DeferredSince = FPlatformTime::Seconds();
    StartDeferredTicker();
}

void UReflectionsGameFlowSubsystem::StartDeferredTicker()
{
    if (!DeferredTicker.IsValid())
    {
        DeferredTicker = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateUObject(this, &UReflectionsGameFlowSubsystem::TickDeferred));
    }
}

bool UReflectionsGameFlowSubsystem::TickDeferred(float DeltaTime)
{
    if (DeferredMap.IsEmpty() && !bQuitPending)
    {
        DeferredTicker.Reset();
        return false;
    }
    // Two frames presented (the render thread runs a frame behind) and a moment: then the load may block.
    if (--DeferredFrames > 0 || FPlatformTime::Seconds() - DeferredSince < 0.06)
    {
        return true;
    }
    DeferredTicker.Reset();
    if (bQuitPending)
    {
        FinishQuit();
        return false;
    }
    const FString Target = DeferredMap;
    DeferredMap.Reset();
    UGameInstance* GameInstance = GetGameInstance();
    UWorld* World = GameInstance ? GameInstance->GetWorld() : nullptr;
    if (!World)
    {
        bTravelPending = false;
        EndLoadingScreen();
        return false;
    }
    FlushSaveWrites();  // the new map's systems read what these wrote
    SetupMoviePlayerLoadingScreen();
    UGameplayStatics::SetGamePaused(World, false);
    UE_LOG(LogReflectionsGameFlow, Log, TEXT("Opening %s."), *Target);
    UGameplayStatics::OpenLevel(World, FName(*Target));
    return false;
}

void UReflectionsGameFlowSubsystem::SetupMoviePlayerLoadingScreen() const
{
    // The movie player paints its own copy of the loading screen on the loading thread while LoadMap blocks, so the
    // spinner keeps turning. It is off in the editor: there the in-game copy is what stays on screen.
    if (GIsEditor || !IsMoviePlayerEnabled())
    {
        return;
    }
    IGameMoviePlayer* MoviePlayer = GetMoviePlayer();
    if (!MoviePlayer || !MoviePlayer->IsInitialized())
    {
        return;
    }
    FLoadingScreenAttributes Attributes;
    Attributes.bAutoCompleteWhenLoadingCompletes = true;
    Attributes.bMoviesAreSkippable = false;
    Attributes.bWaitForManualStop = false;
    Attributes.WidgetLoadingScreen = SReflectionsLoadingScreen::Create(FText::FromString(LoadingStatus.ToString()));
    MoviePlayer->SetupLoadingScreen(Attributes);
}

void UReflectionsGameFlowSubsystem::RestartFromCheckpoint()
{
    ResetInfection();
    ClearGameOver();
    const bool bHas = Checkpoint.bValid && !Checkpoint.MapPath.IsEmpty();
    if (!bHas)
    {
        // No checkpoint to restore from: start the map clean.
        if (UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(GetGameInstance()->GetWorld()))
        {
            Progress->ResetProgress();
        }
    }
    PendingStart = bHas ? EReflectionsFlowStart::Restore : EReflectionsFlowStart::Play;
    OpenMap(bHas ? Checkpoint.MapPath : CurrentMapPath());
}

void UReflectionsGameFlowSubsystem::ReturnToTitle()
{
    ResetInfection();
    ClearGameOver();
    PendingStart = EReflectionsFlowStart::Title;
    OpenMap(CurrentMapPath());
}

void UReflectionsGameFlowSubsystem::StartNewGame()
{
    ClearCheckpoint();
    // People forget the old run too: otherwise the start checkpoint (before Lives starts up) would snapshot the
    // previous run's people and flags, and Lives would load them back.
    if (UReflectionsLivesMemory* Lives = GetGameInstance()->GetSubsystem<UReflectionsLivesMemory>())
    {
        Lives->ForgetEverything();
    }
    // Quests too (their own in-world reset misses a New Game that opens another map).
    if (UReflectionsQuestSubsystem* Quests = GetGameInstance()->GetSubsystem<UReflectionsQuestSubsystem>())
    {
        Quests->ResetAll();
    }
    ResetInfection();
    ClearGameOver();
    if (UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(GetGameInstance()->GetWorld()))
    {
        Progress->ResetProgress();
    }
    UReflectionsGameFlowWorldSubsystem* Flow = GetWorldFlow();
    const FString NewGamePackage = GetNewGameMapPackage();
    const bool bOtherMap = !NewGamePackage.IsEmpty() && NewGamePackage != CurrentMapPath();
    if (Flow && Flow->IsMapFresh() && !bOtherMap)
    {
        Flow->BeginPlaying(true);
    }
    else
    {
        bPendingFreshRun = true;
        PendingStart = EReflectionsFlowStart::Play;
        OpenMap(bOtherMap ? NewGamePackage : CurrentMapPath());
    }
}

FString UReflectionsGameFlowSubsystem::GetNewGameMapPackage() const
{
    FString Path = CVarGameFlowNewGameMap.GetValueOnGameThread();
    if (Path.IsEmpty())
    {
        Path = NewGameMap.GetLongPackageName();
    }
    // Accept "/Game/X/Lvl" or "/Game/X/Lvl.Lvl".
    int32 Dot = INDEX_NONE;
    if (Path.FindChar(TEXT('.'), Dot))
    {
        Path.LeftInline(Dot);
    }
    return Path;
}

void UReflectionsGameFlowSubsystem::ContinueFromCheckpoint()
{
    // Continue picks up the newest save: a manual or quick save newer than the autosave is loaded instead.
    const int32 Newest = GetNewestSaveSlot();
    if (Newest > ReflectionsSaveSlots::Autosave && LoadFromSlot(Newest))
    {
        return;
    }
    if (!Checkpoint.bValid)
    {
        StartNewGame();
        return;
    }
    ResumeSavedCheckpoint();
}

void UReflectionsGameFlowSubsystem::ResumeSavedCheckpoint()
{
    ResetInfection();
    ClearGameOver();
    // Continue resumes a save: the saved health and mana come back too.
    bRestoreVitals = true;
    UReflectionsGameFlowWorldSubsystem* Flow = GetWorldFlow();
    if (Flow && Checkpoint.MapPath == CurrentMapPath() && Flow->IsMapFresh())
    {
        // In place, no reload: the loading screen still covers the jump and the first frames of streaming there.
        BeginLoadingScreen(LOCTEXT("LoadingStatus", "Loading..."));
        Flow->ApplyCheckpoint(Checkpoint);
        Flow->BeginPlaying();
    }
    else
    {
        PendingStart = EReflectionsFlowStart::Restore;
        OpenMap(Checkpoint.MapPath);
    }
}

void UReflectionsGameFlowSubsystem::QuitGame()
{
    if (bQuitPending)
    {
        return;
    }
    bQuitPending = true;
    if (Checkpoint.bValid)
    {
        WriteSave();  // FinishQuit waits for it: nothing is left half-written
    }
    // The screen goes up this frame; the exit follows once it is presented.
    BeginLoadingScreen(Checkpoint.bValid ? LOCTEXT("SavingStatus", "Saving...") : FText::GetEmpty());
    DeferredFrames = 2;
    DeferredSince = FPlatformTime::Seconds();
    StartDeferredTicker();
}

void UReflectionsGameFlowSubsystem::FinishQuit()
{
    UGameInstance* GameInstance = GetGameInstance();
    UWorld* World = GameInstance ? GameInstance->GetWorld() : nullptr;
    FlushSaveWrites();
    if (GIsEditor)
    {
        // Never 'quit' or RequestExit in the editor: the quit exec and the exit request both end the process, and
        // that closes the shared editor. The screen is dropped and play goes on; the editor's Stop button ends PIE.
        UE_LOG(LogReflectionsGameFlow, Warning, TEXT("Quit to desktop in the editor: the editor stays open; stop PIE to end the session."));
        bQuitPending = false;
        EndLoadingScreen();
        return;
    }
    if (!GIsEditor)
    {
        // The engine's teardown of a big map takes seconds. Let the sound and the window go now, so quitting feels
        // instant; the process finishes shutting down out of sight.
        if (FAudioDevice* Audio = World ? World->GetAudioDeviceRaw() : nullptr)
        {
            Audio->SetTransientPrimaryVolume(0.0f);
        }
        if (GEngine && GEngine->GameViewport)
        {
            if (TSharedPtr<SWindow> Window = GEngine->GameViewport->GetWindow())
            {
                Window->HideWindow();
            }
        }
    }
    UE_LOG(LogReflectionsGameFlow, Log, TEXT("Quitting."));
    if (World)
    {
        UKismetSystemLibrary::QuitGame(World, World->GetFirstPlayerController(), EQuitPreference::Quit, false);
    }
    else
    {
        FPlatformMisc::RequestExit(false);
    }
}

bool UReflectionsGameFlowSubsystem::IsRunLive() const
{
    const UReflectionsGameFlowWorldSubsystem* Flow = GetWorldFlow();
    return Flow && Flow->IsPlaying() && !Flow->IsMenuOpen() && !IsGameOver();
}

EReflectionsFlowScreen UReflectionsGameFlowSubsystem::GetScreen() const
{
    const UReflectionsGameFlowWorldSubsystem* Flow = GetWorldFlow();
    return Flow ? Flow->GetScreen() : EReflectionsFlowScreen::None;
}

TArray<FString> UReflectionsGameFlowSubsystem::GetMenuButtonLabels() const
{
    const UReflectionsGameFlowWorldSubsystem* Flow = GetWorldFlow();
    const TSharedPtr<SReflectionsFlowMenu> Menu = Flow ? Flow->GetMenuWidget() : nullptr;
    return Menu.IsValid() && Flow->IsMenuOpen() ? Menu->GetButtonLabels() : TArray<FString>();
}

int32 UReflectionsGameFlowSubsystem::GetMenuFocusedIndex() const
{
    const UReflectionsGameFlowWorldSubsystem* Flow = GetWorldFlow();
    const TSharedPtr<SReflectionsFlowMenu> Menu = Flow ? Flow->GetMenuWidget() : nullptr;
    return Menu.IsValid() && Flow->IsMenuOpen() ? Menu->GetFocusedIndex() : INDEX_NONE;
}

FString UReflectionsGameFlowSubsystem::GetActiveTipName() const
{
    const UReflectionsGameFlowWorldSubsystem* Flow = GetWorldFlow();
    if (!Flow || !Flow->HasActiveTip())
    {
        return FString();
    }
    return StaticEnum<EReflectionsTip>()->GetNameStringByValue(static_cast<int64>(Flow->GetActiveTip()));
}

EReflectionsFlowStart UReflectionsGameFlowSubsystem::ConsumeStartAction()
{
    const EReflectionsFlowStart Start = PendingStart;
    PendingStart = EReflectionsFlowStart::None;
    TravelAssets.Reset();
    return Start;
}

#undef FLOWTEXT
#undef LOCTEXT_NAMESPACE
