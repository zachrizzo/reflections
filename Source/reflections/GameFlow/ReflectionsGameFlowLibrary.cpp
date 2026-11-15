#include "GameFlow/ReflectionsGameFlowLibrary.h"

#include "Engine/World.h"
#include "GameFlow/ReflectionsGameFlowSlate.h"
#include "GameFlow/ReflectionsGameFlowSubsystem.h"
#include "GameFlow/ReflectionsGameFlowWorldSubsystem.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"

void UReflectionsGameFlowLibrary::ReportInfected(const UObject* WorldContext, AActor* Host)
{
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(WorldContext))
    {
        Flow->ReportInfected(Host);
    }
}

void UReflectionsGameFlowLibrary::ReportCured(const UObject* WorldContext, AActor* Host)
{
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(WorldContext))
    {
        Flow->ReportCured(Host);
    }
}

int32 UReflectionsGameFlowLibrary::GetInfectionCount(const UObject* WorldContext)
{
    const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(WorldContext);
    return Flow ? Flow->GetInfectionCount() : 0;
}

int32 UReflectionsGameFlowLibrary::GetInfectionCap(const UObject* WorldContext)
{
    const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(WorldContext);
    return Flow ? Flow->GetInfectionCap() : 0;
}

void UReflectionsGameFlowLibrary::ShowVictory(const UObject* WorldContext)
{
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(WorldContext))
    {
        Flow->ShowVictory();
    }
}

bool UReflectionsGameFlowLibrary::SaveCheckpoint(const UObject* WorldContext, const FString& Reason)
{
    UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(WorldContext);
    return Flow && Flow->SaveCheckpoint(Reason);
}

bool UReflectionsGameFlowLibrary::IsGameOver(const UObject* WorldContext)
{
    const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(WorldContext);
    return Flow && Flow->IsGameOver();
}

// ---- Debug console commands (not in Shipping) --------------------------------------------------------------

#if !UE_BUILD_SHIPPING
namespace ReflectionsFlowCommands
{
    static int32 ArgInt(const TArray<FString>& Args, int32 Index, int32 Default)
    {
        return Args.IsValidIndex(Index) ? FCString::Atoi(*Args[Index]) : Default;
    }

    static EReflectionsTip ParseTip(const FString& Name)
    {
        if (Name.StartsWith(TEXT("Cast"), ESearchCase::IgnoreCase)) return EReflectionsTip::Cast;
        if (Name.StartsWith(TEXT("Coin"), ESearchCase::IgnoreCase)) return EReflectionsTip::Coin;
        if (Name.StartsWith(TEXT("Cross"), ESearchCase::IgnoreCase) || Name.StartsWith(TEXT("World"), ESearchCase::IgnoreCase)) return EReflectionsTip::CrossWorlds;
        if (Name.StartsWith(TEXT("Craft"), ESearchCase::IgnoreCase)) return EReflectionsTip::Crafting;
        return EReflectionsTip::Aim;
    }

    static FAutoConsoleCommandWithWorldAndArgs Title(TEXT("GameFlow.Title"), TEXT("Show the title screen now."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(World)) Flow->ShowTitle();
        }));

    static FAutoConsoleCommandWithWorldAndArgs Pause(TEXT("GameFlow.Pause"), TEXT("Toggle the pause menu."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(World))
            {
                if (Flow->GetScreen() == EReflectionsFlowScreen::Pause) Flow->ResumeGame();
                else Flow->OpenPause();
            }
        }));

    static FAutoConsoleCommandWithWorldAndArgs Controls(TEXT("GameFlow.Controls"), TEXT("Open the controls screen."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(World)) Flow->PushScreen(EReflectionsFlowScreen::Controls);
        }));

    static FAutoConsoleCommandWithWorldAndArgs Credits(TEXT("GameFlow.Credits"), TEXT("Open the credits screen."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(World)) Flow->PushScreen(EReflectionsFlowScreen::Credits);
        }));

    static FAutoConsoleCommandWithWorldAndArgs Resume(TEXT("GameFlow.Resume"), TEXT("Close every menu."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(World)) Flow->ResumeGame();
        }));

    static FAutoConsoleCommandWithWorldAndArgs Infect(TEXT("GameFlow.Infect"), TEXT("GameFlow.Infect [N]: add N anonymous infections (default 1)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World))
            {
                for (int32 Index = 0, Count = FMath::Max(1, ArgInt(Args, 0, 1)); Index < Count; ++Index) Flow->ReportInfected(nullptr);
            }
        }));

    static FAutoConsoleCommandWithWorldAndArgs Cure(TEXT("GameFlow.Cure"), TEXT("GameFlow.Cure [N]: remove N anonymous infections (default 1)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World))
            {
                for (int32 Index = 0, Count = FMath::Max(1, ArgInt(Args, 0, 1)); Index < Count; ++Index) Flow->ReportCured(nullptr);
            }
        }));

    static FAutoConsoleCommandWithWorldAndArgs Cap(TEXT("GameFlow.Cap"), TEXT("GameFlow.Cap N: set the infection cap for this run (0 = default)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World)) Flow->SetInfectionCap(ArgInt(Args, 0, 0));
        }));

    static FAutoConsoleCommandWithWorldAndArgs Lose(TEXT("GameFlow.Lose"), TEXT("Show the lose screen."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World)) Flow->ShowLose();
        }));

    static FAutoConsoleCommandWithWorldAndArgs Victory(TEXT("GameFlow.Victory"), TEXT("Show the victory screen (as the villain's death will)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World)) Flow->ShowVictory();
        }));

    static FAutoConsoleCommandWithWorldAndArgs Checkpoint(TEXT("GameFlow.Checkpoint"), TEXT("Save a checkpoint now."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World)) Flow->SaveCheckpoint(TEXT("Console"));
        }));

    static FAutoConsoleCommandWithWorldAndArgs Restart(TEXT("GameFlow.Restart"), TEXT("Restart from the last checkpoint (reloads the map)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World)) Flow->RestartFromCheckpoint();
        }));

    /** "q" = the quick slot, "a" / "0" = the autosave, 1-3 = manual slots. */
    static int32 ParseSlot(const TArray<FString>& Args, int32 Default)
    {
        if (!Args.IsValidIndex(0))
        {
            return Default;
        }
        const FString Arg = Args[0].ToLower();
        if (Arg.StartsWith(TEXT("q")))
        {
            return ReflectionsSaveSlots::Quick;
        }
        if (Arg.StartsWith(TEXT("a")) || Arg == TEXT("0"))
        {
            return ReflectionsSaveSlots::Autosave;
        }
        return ReflectionsSaveSlots::FirstManual + FMath::Clamp(FCString::Atoi(*Arg), 1, ReflectionsSaveSlots::ManualCount) - 1;
    }

    static FAutoConsoleCommandWithWorldAndArgs Save(TEXT("GameFlow.Save"), TEXT("GameFlow.Save [1-3|q]: save to a manual slot (default 1) or the quick slot."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World))
            {
                const int32 Slot = ParseSlot(Args, ReflectionsSaveSlots::FirstManual);
                UE_LOG(LogTemp, Log, TEXT("GameFlow.Save %d: %s"), Slot, Flow->SaveToSlot(Slot) ? TEXT("saved") : TEXT("FAILED"));
            }
        }));

    static FAutoConsoleCommandWithWorldAndArgs Load(TEXT("GameFlow.Load"), TEXT("GameFlow.Load [1-3|q|a]: load a slot (default: the newest)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World))
            {
                const int32 Slot = ParseSlot(Args, Flow->GetNewestSaveSlot());
                UE_LOG(LogTemp, Log, TEXT("GameFlow.Load %d: %s"), Slot, Flow->LoadFromSlot(Slot) ? TEXT("loading") : TEXT("FAILED"));
            }
        }));

    static FAutoConsoleCommandWithWorldAndArgs SaveMenu(TEXT("GameFlow.SaveMenu"), TEXT("Open the Save Game screen (over the pause menu)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(World))
            {
                Flow->OpenPause();
                Flow->HandleAction(EReflectionsFlowAction::SaveGame);
            }
        }));

    static FAutoConsoleCommandWithWorldAndArgs LoadMenu(TEXT("GameFlow.LoadMenu"), TEXT("Open the Load Game screen (over the pause menu)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(World))
            {
                Flow->OpenPause();
                Flow->HandleAction(EReflectionsFlowAction::LoadGame);
            }
        }));

    static FAutoConsoleCommandWithWorldAndArgs Kill(TEXT("GameFlow.Kill"), TEXT("Kill the player's pawn (tests the respawn at the checkpoint)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
            if (APawn* Pawn = PC ? PC->GetPawn() : nullptr)
            {
                UGameplayStatics::ApplyDamage(Pawn, 100000.0f, PC, Pawn, nullptr);
            }
        }));

    static FAutoConsoleCommandWithWorldAndArgs Tip(TEXT("GameFlow.Tip"), TEXT("GameFlow.Tip Aim|Cast|Coin|Cross|Craft: show a tutorial tip now."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(World)) Flow->ShowTip(ParseTip(Args.IsValidIndex(0) ? Args[0] : FString()));
        }));

    static FAutoConsoleCommandWithWorldAndArgs ResetTips(TEXT("GameFlow.ResetTips"), TEXT("Forget which tips were seen."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World)) Flow->ResetTips();
        }));

    static FAutoConsoleCommandWithWorldAndArgs DeleteSave(TEXT("GameFlow.DeleteSave"), TEXT("Forget the checkpoint (Continue disappears)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World)) Flow->ClearCheckpoint();
        }));

    static FAutoConsoleCommandWithWorldAndArgs Key(TEXT("GameFlow.Key"), TEXT("GameFlow.Key <KeyName>: press and release a key through Slate (Enter, Escape, Gamepad_DPad_Down, Gamepad_FaceButton_Bottom...)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (Args.IsValidIndex(0))
            {
                const bool bHandled = UReflectionsGameFlowWorldSubsystem::SimulateKey(Args[0]);
                UE_LOG(LogTemp, Log, TEXT("GameFlow.Key %s -> %s"), *Args[0], bHandled ? TEXT("handled") : TEXT("unhandled"));
            }
        }));

    static FAutoConsoleCommandWithWorldAndArgs Dump(TEXT("GameFlow.Dump"), TEXT("Log the game-flow state."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(World);
            const UReflectionsGameFlowWorldSubsystem* WorldFlow = UReflectionsGameFlowWorldSubsystem::Get(World);
            if (!Flow || !WorldFlow)
            {
                UE_LOG(LogTemp, Log, TEXT("GameFlow: not active in this world."));
                return;
            }
            const FReflectionsCheckpoint& CP = Flow->GetCheckpoint();
            UE_LOG(LogTemp, Log, TEXT("GameFlow: screen=%s playing=%d infection=%d/%d gameover=%d victory=%d gamepad=%d checkpoint=%s (%s) %s at %s"),
                *StaticEnum<EReflectionsFlowScreen>()->GetNameStringByValue(static_cast<int64>(WorldFlow->GetScreen())),
                WorldFlow->IsPlaying(), Flow->GetInfectionCount(), Flow->GetInfectionCap(), Flow->IsGameOver(), Flow->IsVictory(),
                Flow->IsUsingGamepad(), CP.bValid ? TEXT("yes") : TEXT("no"), *CP.Reason, *CP.MapPath, *CP.Location.ToCompactString());
        }));
}
#endif
