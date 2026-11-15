// Console commands for testing spell crafting in Play-in-Editor or a development build. Not compiled into Shipping.

#include "SpellCrafting/ReflectionsSpellCraftingComponent.h"
#include "SpellCrafting/ReflectionsSpellCraftingLibrary.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "NPC/ReflectionsNpcSubsystem.h"

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

    /** The team's MetaHuman NPC looks: the Red London crowd first, then White London. Mannequins only if none load. */
    const TCHAR* const DummyLooks[] = {
        TEXT("/Game/Characters/CrowdMotion/SimpleRed/BridgeGuard/BP_BridgeGuard_SimpleRed.BP_BridgeGuard_SimpleRed_C"),
        TEXT("/Game/Characters/CrowdMotion/SimpleRed/CoinClerk/BP_CoinClerk_SimpleRed.BP_CoinClerk_SimpleRed_C"),
        TEXT("/Game/Characters/CrowdMotion/SimpleRed/ArchiveApprentice/BP_ArchiveApprentice_SimpleRed.BP_ArchiveApprentice_SimpleRed_C"),
        TEXT("/Game/Characters/CrowdMotion/SimpleRed/FestivalDrummer/BP_FestivalDrummer_SimpleRed.BP_FestivalDrummer_SimpleRed_C"),
        TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_01_Plain.BP_WhiteLook_01_Plain_C"),
        TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_02_Cap.BP_WhiteLook_02_Cap_C"),
        TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_03_Mantle.BP_WhiteLook_03_Mantle_C"),
        TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_04_CapMantle.BP_WhiteLook_04_CapMantle_C"),
        TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_05_GuardRags.BP_WhiteLook_05_GuardRags_C"),
        TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_06_GuardBoldRunes.BP_WhiteLook_06_GuardBoldRunes_C"),
    };

    /** Fallback when no MetaHuman look loads: a bare mannequin character with health. */
    void SpawnMannequin(UWorld* World, const FVector& Floor, const FVector& Forward, bool bEnemy)
    {
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
        ACharacter* Dummy = World->SpawnActor<ACharacter>(ACharacter::StaticClass(), Floor + FVector(0, 0, 110.0f), (-Forward).Rotation(), Params);
        if (!Dummy) return;
        Dummy->Tags.Add(bEnemy ? FName(TEXT("NPC_CombatEnemy")) : FName(TEXT("Friendly")));
        Dummy->Tags.Add(TEXT("CraftingDummy"));
        // Without a controller a Character stays in MOVE_None and ignores launches.
        Dummy->GetCharacterMovement()->bRunPhysicsWithNoController = true;
        Dummy->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
        if (USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple")))
        {
            Dummy->GetMesh()->SetSkeletalMeshAsset(Mesh);
            Dummy->GetMesh()->SetRelativeLocationAndRotation(FVector(0, 0, -90.0f), FRotator(0, -90.0f, 0));
        }
        UReflectionsHealthComponent* Health = NewObject<UReflectionsHealthComponent>(Dummy, TEXT("Health"));
        Health->MaxHealth = 120.0f;
        Health->RegisterComponent();
        Health->ResetHealth();
    }

    /**
     * Test crowd laid out in front of the player, so pulls, chains and splits have targets: the team's MetaHuman NPC
     * Blueprints, tagged like the placed crowd and enrolled in the NPC system as enemies (default) or civilians.
     */
    FAutoConsoleCommandWithWorldAndArgs DummyCommand(TEXT("Crafting.Dummies"),
        TEXT("Crafting.Dummies [count=6] [distance=900] [enemy|civilian|mixed]: spawns the team's MetaHuman NPCs in front of the player, enrolled in the NPC system."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
        {
            APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
            APawn* Pawn = PC ? PC->GetPawn() : nullptr;
            if (!Pawn) return;
            const int32 Count = FMath::Clamp(IntArg(Args, 0, 6), 1, 24);
            const float Distance = float(IntArg(Args, 1, 900));
            const FString Mix = Args.IsValidIndex(2) ? Args[2].ToLower() : FString(TEXT("enemy"));
            const FVector Forward = PC->GetControlRotation().Vector().GetSafeNormal2D();
            const FVector Right = FVector::CrossProduct(FVector::UpVector, Forward);
            UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(World);
            TArray<UClass*> Looks;
            for (const TCHAR* Path : DummyLooks)
                if (UClass* Look = LoadClass<AActor>(nullptr, Path, nullptr, LOAD_NoWarn | LOAD_Quiet)) Looks.Add(Look);
            static int32 LookCursor = 0;
            for (int32 i = 0; i < Count; ++i)
            {
                const float Column = (i % 3) - 1.0f;
                const float Row = float(i / 3);
                FVector Location = Pawn->GetActorLocation() + Forward * (Distance + Row * 260.0f) + Right * Column * 230.0f;
                // Crowd bodies are placed by their feet: stand them on whatever is below.
                FHitResult Floor;
                const FCollisionQueryParams Query(SCENE_QUERY_STAT(CraftingDummyFloor), false, Pawn);
                if (World->LineTraceSingleByChannel(Floor, Location + FVector(0, 0, 300.0f), Location - FVector(0, 0, 900.0f), ECC_Visibility, Query))
                    Location = Floor.ImpactPoint;
                const bool bEnemy = Mix == TEXT("civilian") ? false : (Mix == TEXT("mixed") ? (i % 2 == 0) : true);
                if (!Npcs || Looks.Num() == 0)
                {
                    SpawnMannequin(World, Location, Forward, bEnemy);
                    continue;
                }
                // Crowd bodies face their +Y, so turn them a quarter less to face the player.
                const FTransform Spawn(FRotator(0.0, (-Forward).Rotation().Yaw - 90.0, 0.0), Location);
                AActor* Npc = World->SpawnActorDeferred<AActor>(Looks[LookCursor++ % Looks.Num()], Spawn, nullptr, nullptr,
                    ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
                if (!Npc) continue;
                // The tags the placed crowd carries: reactive, a capsule spells can hit, the sample-locomotion driver.
                for (const TCHAR* Tag : {TEXT("NPC_Reactive"), TEXT("NPC_HitProxy"), TEXT("NPC_SampleLocomotion"), TEXT("CraftingDummy")})
                    Npc->Tags.AddUnique(FName(Tag));
                if (bEnemy)
                {
                    Npc->Tags.Remove(FName(TEXT("Friendly")));
                    Npc->Tags.AddUnique(FName(TEXT("NPC_CombatEnemy")));
                }
                else
                {
                    Npc->Tags.AddUnique(FName(TEXT("Friendly")));
                }
                Npc->FinishSpawning(Spawn);
                Npcs->EnrollActor(Npc, Npcs->FindArchetype(bEnemy ? FName(TEXT("Enemy")) : FName(TEXT("Civilian"))));
            }
        }));

    FAutoConsoleCommandWithWorld ClearDummiesCommand(TEXT("Crafting.ClearDummies"), TEXT("Removes the test characters."),
        FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
        {
            if (!World) return;
            // Destroying an enrolled NPC also removes its hidden locomotion driver.
            for (TActorIterator<AActor> It(World); It; ++It)
            {
                if (It->ActorHasTag(TEXT("CraftingDummy"))) It->Destroy();
            }
        }));
}
#endif
