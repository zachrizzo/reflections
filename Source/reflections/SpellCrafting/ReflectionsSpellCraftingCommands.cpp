// Console commands for testing spell crafting in Play-in-Editor or a development build. Not compiled into Shipping.

#include "SpellCrafting/ReflectionsSpellCraftingComponent.h"
#include "SpellCrafting/ReflectionsSpellCraftingLibrary.h"
#include "Hero/ReflectionsSpellCombat.h"

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"

#if !UE_BUILD_SHIPPING
namespace
{
    UReflectionsSpellCraftingComponent* FindCrafting(UWorld* World)
    {
        APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
        APawn* Pawn = PC ? PC->GetPawn() : nullptr;
        return Pawn ? Pawn->FindComponentByClass<UReflectionsSpellCraftingComponent>() : nullptr;
    }

    int32 IntArg(const TArray<FString>& Args, int32 Index, int32 Default)
    {
        return Args.IsValidIndex(Index) && Args[Index].IsNumeric() ? FCString::Atoi(*Args[Index]) : Default;
    }

    FAutoConsoleCommandWithWorldAndArgs SlotCommand(TEXT("Crafting.Slot"),
        TEXT("Crafting.Slot <0-3|-1>: make a crafted slot the active cast (-1 returns to the catalog spells)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsSpellCraftingComponent* Crafting = FindCrafting(World)) Crafting->SelectCraftedSlot(IntArg(Args, 0, -1));
        }));

    FAutoConsoleCommandWithWorldAndArgs PresetCommand(TEXT("Crafting.Preset"),
        TEXT("Crafting.Preset <slot> <preset 0-3>: 0 bouncing ice splitter, 1 gravity orb, 2 healing rain that follows you, 3 storm eye."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsSpellCraftingComponent* Crafting = FindCrafting(World))
            {
                Crafting->SetSlotRecipe(IntArg(Args, 0, 0), UReflectionsSpellCraftingLibrary::Preset(IntArg(Args, 1, 0)));
            }
        }));

    FAutoConsoleCommandWithWorldAndArgs SetCommand(TEXT("Crafting.Set"),
        TEXT("Crafting.Set <slot> <recipe JSON | a sentence>: store a recipe, e.g. Crafting.Set 1 a slow orb of lightning that pulls enemies in."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            UReflectionsSpellCraftingComponent* Crafting = FindCrafting(World);
            if (!Crafting || Args.Num() < 2) return;
            TArray<FString> Rest(Args);
            Rest.RemoveAt(0);
            const FString Text = FString::Join(Rest, TEXT(" "));
            FCraftedSpellRecipe Recipe;
            const bool bOk = Text.StartsWith(TEXT("{")) ? UReflectionsSpellCraftingLibrary::FromJson(Text, Recipe)
                : UReflectionsSpellCraftingLibrary::ParseDescription(Text, Recipe);
            if (bOk) Crafting->SetSlotRecipe(IntArg(Args, 0, 0), Recipe);
            UE_LOG(LogTemp, Display, TEXT("Crafting.Set: %s -> %s"), bOk ? TEXT("ok") : TEXT("not understood"),
                bOk ? *UReflectionsSpellCraftingLibrary::Resolve(Recipe).Name : *Text);
        }));

    FAutoConsoleCommandWithWorldAndArgs CastCommand(TEXT("Crafting.Cast"),
        TEXT("Crafting.Cast [slot]: cast a crafted slot (default: the active one) through the normal cast flow."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            if (UReflectionsSpellCraftingComponent* Crafting = FindCrafting(World))
            {
                if (Args.Num() > 0) Crafting->SelectCraftedSlot(IntArg(Args, 0, 0));
                const bool bCast = Crafting->CastActive();
                UE_LOG(LogTemp, Display, TEXT("Crafting.Cast: %s"), bCast ? TEXT("cast") : *Crafting->GetFeedback());
            }
        }));

    FAutoConsoleCommandWithWorld OpenCommand(TEXT("Crafting.Open"), TEXT("Opens or closes the crafting screen."),
        FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
        {
            if (UReflectionsSpellCraftingComponent* Crafting = FindCrafting(World)) Crafting->ToggleCraftingScreen();
        }));

    FAutoConsoleCommandWithWorld DumpCommand(TEXT("Crafting.Dump"), TEXT("Logs every slot's recipe, name, cost and synergies."),
        FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
        {
            UReflectionsSpellCraftingComponent* Crafting = FindCrafting(World);
            if (!Crafting) return;
            for (int32 Slot = 0; Slot < UReflectionsSpellCraftingComponent::NumSlots; ++Slot)
            {
                const FCraftedSpellResolved& S = Crafting->GetSlotSpell(Slot);
                UE_LOG(LogTemp, Display, TEXT("Slot %d%s: %s | %.0f mana | %s | %s | %s"), Slot, Crafting->GetActiveSlot() == Slot ? TEXT("*") : TEXT(""),
                    *S.Name, S.ManaCost, *UReflectionsSpellCraftingLibrary::ToJson(S.Recipe), *FString::Join(S.SynergyNotes, TEXT("; ")), *S.Description);
            }
        }));

    /** Test crowd: standing characters with health, laid out in front of the player, so pulls, chains and splits have targets. */
    FAutoConsoleCommandWithWorldAndArgs DummyCommand(TEXT("Crafting.Dummies"),
        TEXT("Crafting.Dummies [count=6] [distance=900]: spawns standing test characters in front of the player."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
            APawn* Pawn = PC ? PC->GetPawn() : nullptr;
            if (!Pawn) return;
            const int32 Count = FMath::Clamp(IntArg(Args, 0, 6), 1, 24);
            const float Distance = float(IntArg(Args, 1, 900));
            USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"));
            const FVector Forward = PC->GetControlRotation().Vector().GetSafeNormal2D();
            const FVector Right = FVector::CrossProduct(FVector::UpVector, Forward);
            for (int32 i = 0; i < Count; ++i)
            {
                const float Column = (i % 3) - 1.0f;
                const float Row = float(i / 3);
                const FVector Location = Pawn->GetActorLocation() + Forward * (Distance + Row * 260.0f) + Right * Column * 230.0f + FVector(0, 0, 20.0f);
                FActorSpawnParameters Params;
                Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
                ACharacter* Dummy = World->SpawnActor<ACharacter>(ACharacter::StaticClass(), Location, (-Forward).Rotation(), Params);
                if (!Dummy) continue;
                Dummy->Tags.Add(TEXT("NPC_CombatEnemy"));
                Dummy->Tags.Add(TEXT("CraftingDummy"));
                if (Mesh)
                {
                    Dummy->GetMesh()->SetSkeletalMeshAsset(Mesh);
                    Dummy->GetMesh()->SetRelativeLocationAndRotation(FVector(0, 0, -90.0f), FRotator(0, -90.0f, 0));
                }
                UReflectionsHealthComponent* Health = NewObject<UReflectionsHealthComponent>(Dummy, TEXT("Health"));
                Health->MaxHealth = 120.0f;
                Health->RegisterComponent();
                Health->ResetHealth();
            }
        }));

    FAutoConsoleCommandWithWorld ClearDummiesCommand(TEXT("Crafting.ClearDummies"), TEXT("Removes the test characters."),
        FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
        {
            if (!World) return;
            for (TActorIterator<ACharacter> It(World); It; ++It)
            {
                if (It->ActorHasTag(TEXT("CraftingDummy"))) It->Destroy();
            }
        }));
}
#endif
