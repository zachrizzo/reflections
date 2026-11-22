#pragma once

#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Digging/ReflectionsDigComponent.h"
#include "Digging/ReflectionsDigSubsystem.h"
#include "Digging/ReflectionsDigTerrain.h"
#include "Digging/ReflectionsDigTypes.h"
#include "Digging/Tests/ReflectionsDigTestTraces.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "NavigationSystem.h"

/*
 * The harness of the game-context tests: they run only in a -game process on the dig spike map
 * (test.ps1 -Game -Map /Game/Maps/DigSpike/L_DigSpike -Filter Reflections.DigSpike), where the game mode, world
 * subsystems and physics are live and the world ticks by itself. Each test queues latent steps that run once per frame;
 * every step has a wall-clock timeout that fails the test, and a failed step skips the rest of the test's steps except
 * the cleanup, which always runs. All tests of a run share the one map and its digs, so each digs at its own place.
 * Everything here is inline, so any number of test files can include it.
 */

namespace ReflectionsDig::GameTest
{
    inline constexpr EAutomationTestFlags DigGameTestFlags = EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter;

    /** The map's terrain: actor at (1000, -2400, 0), ground at Z 0, default size (3 x 3 x 2 chunks). */
    inline constexpr double GroundZ = 0.0;
    inline constexpr double GridFloorZ = -2800.0;
    /** The bedrock surface meshes about 25 cm above the grid floor. */
    inline constexpr double BedrockTopZ = GridFloorZ + 25.0;
    inline constexpr float DigRadiusCm = ReflectionsDig::StampRadiusCm;
    /** Downward traces start above the top of the grid and end under the safety floor (its top is 30 cm below the grid floor). */
    inline constexpr double TraceStartZ = 1000.0;
    inline constexpr double TraceEndZ = GridFloorZ - 300.0;

    inline constexpr double ReadyTimeoutSeconds = 30.0;
    inline constexpr double RestTimeoutSeconds = 30.0;
    /** How long a character must keep its height (game time) to count as resting after a dig. */
    inline constexpr double RestSeconds = 0.5;
    /** A height change smaller than this does not count as moving. */
    inline constexpr double StillToleranceCm = 1.0;

    /** What one game test works on; shared by its latent steps. */
    struct FDigGameScene
    {
        FAutomationTestBase* Test = nullptr;
        TWeakObjectPtr<UWorld> World;
        TWeakObjectPtr<UReflectionsDigSubsystem> Subsystem;
        TWeakObjectPtr<AReflectionsDigTerrain> Terrain;
        TWeakObjectPtr<APlayerController> Controller;
        /** What the controller possessed before the test; possessed again in the cleanup. */
        TWeakObjectPtr<APawn> PreviousPawn;
        TWeakObjectPtr<ACharacter> Character;
        /** A step failed: the remaining steps (not the cleanup) are skipped. */
        bool bAborted = false;
        /** The lowest feet height seen on any frame of the test's steps. */
        double LowestFeetZ = TNumericLimits<double>::Max();

        /** Fails the test with Why and skips the steps still to come. */
        void Abort(const FString& Why)
        {
            Test->AddError(Why);
            bAborted = true;
        }

        UWorld* GetWorld() const { return World.Get(); }
        UReflectionsDigSubsystem* GetSubsystem() const { return Subsystem.Get(); }
        ACharacter* GetCharacter() const { return Character.Get(); }

        /** Actor Z minus the capsule half-height. */
        double GetFeetZ() const
        {
            const ACharacter* C = Character.Get();
            return C->GetActorLocation().Z - C->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
        }

        /** The chunk-only downward trace at (X, Y), skipping the character. */
        TOptional<double> TraceGroundZ(double X, double Y) const
        {
            return FReflectionsDigTestTraces::TraceDownToChunkZ(World.Get(), X, Y, TraceStartZ, TraceEndZ, Character.Get());
        }
    };

    using FDigGameSceneRef = TSharedRef<FDigGameScene>;

    /**
     * Queues a latent step: Update runs once per frame until it returns true. Past TimeoutSeconds of wall-clock time
     * the test fails with "<Label> timed out". Once a step has failed, later steps are skipped unless bAlwaysRun.
     * Every frame of a step also records the character's feet height in LowestFeetZ.
     */
    inline void AddStep(const FDigGameSceneRef& Scene, const FString& Label, double TimeoutSeconds, TFunction<bool(FDigGameScene&)> Update,
        bool bAlwaysRun = false)
    {
        TSharedRef<double> Deadline = MakeShared<double>(0.0);
        FAutomationTestFramework::Get().EnqueueLatentCommand(MakeShared<FFunctionLatentCommand>(
            [Scene, Label, TimeoutSeconds, Update = MoveTemp(Update), bAlwaysRun, Deadline]()
            {
                if (Scene->bAborted && !bAlwaysRun)
                {
                    return true;
                }
                if (*Deadline == 0.0)
                {
                    *Deadline = FPlatformTime::Seconds() + TimeoutSeconds;
                }
                if (!bAlwaysRun && (Scene->GetWorld() == nullptr || Scene->GetSubsystem() == nullptr || Scene->GetCharacter() == nullptr))
                {
                    Scene->Abort(FString::Printf(TEXT("%s: the world, the dig subsystem or the character is gone"), *Label));
                    return true;
                }
                if (Scene->GetCharacter() != nullptr)
                {
                    Scene->LowestFeetZ = FMath::Min(Scene->LowestFeetZ, Scene->GetFeetZ());
                }
                if (Update(*Scene))
                {
                    return true;
                }
                if (FPlatformTime::Seconds() > *Deadline)
                {
                    Scene->Abort(FString::Printf(TEXT("%s timed out after %.0f s"), *Label, TimeoutSeconds));
                    return true;
                }
                return false;
            }));
    }

    /** Queues a step that runs once. */
    inline void AddAction(const FDigGameSceneRef& Scene, const FString& Label, TFunction<void(FDigGameScene&)> Action)
    {
        AddStep(Scene, Label, 1.0, [Action = MoveTemp(Action)](FDigGameScene& S) { Action(S); return true; });
    }

    /** Freezes the character standing on the original ground at (X, Y): it cannot fall until the terrain there is ready. */
    inline void Teleport(FDigGameScene& Scene, double X, double Y)
    {
        ACharacter* Character = Scene.GetCharacter();
        const double HalfHeight = Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
        Character->SetActorLocation(FVector(X, Y, GroundZ + HalfHeight + 5.0), /*bSweep=*/ false, nullptr, ETeleportType::TeleportPhysics);
        UCharacterMovementComponent* Movement = Character->GetCharacterMovement();
        Movement->StopMovementImmediately();
        Movement->DisableMovement();
    }

    /**
     * Queues the steps that let a teleported character down at (X, Y): wait until the terrain is idle and a downward
     * trace there hits a chunk piece, then let it fall and wait until it walks on a chunk piece.
     */
    inline void AddLetDown(const FDigGameSceneRef& Scene, double X, double Y)
    {
        AddStep(Scene, FString::Printf(TEXT("The terrain at (%.0f, %.0f) is meshed"), X, Y), ReadyTimeoutSeconds, [X, Y](FDigGameScene& S)
        {
            if (!S.GetSubsystem()->IsIdle() || !S.TraceGroundZ(X, Y).IsSet())
            {
                return false;
            }
            S.GetCharacter()->GetCharacterMovement()->SetMovementMode(MOVE_Falling);
            return true;
        });
        AddStep(Scene, FString::Printf(TEXT("The character lands at (%.0f, %.0f)"), X, Y), ReadyTimeoutSeconds, [](FDigGameScene& S)
        {
            const UCharacterMovementComponent* Movement = S.GetCharacter()->GetCharacterMovement();
            return Movement->IsMovingOnGround() && Cast<UReflectionsDigChunkComponent>(Movement->CurrentFloor.HitResult.GetComponent()) != nullptr;
        });
    }

    /** Queues a wait until the terrain is idle and the character has walked on a chunk piece without changing height for RestSeconds. */
    inline void AddWaitForRest(const FDigGameSceneRef& Scene, const FString& Label)
    {
        struct FRest
        {
            double LastZ = TNumericLimits<double>::Max();
            double StillSince = 0.0;
        };
        TSharedRef<FRest> Rest = MakeShared<FRest>();
        AddStep(Scene, Label, RestTimeoutSeconds, [Rest](FDigGameScene& S)
        {
            const double Now = S.GetWorld()->GetTimeSeconds();
            const double Z = S.GetCharacter()->GetActorLocation().Z;
            const UCharacterMovementComponent* Movement = S.GetCharacter()->GetCharacterMovement();
            const bool bOnTerrain = Movement->IsMovingOnGround()
                && Cast<UReflectionsDigChunkComponent>(Movement->CurrentFloor.HitResult.GetComponent()) != nullptr;
            if (FMath::Abs(Z - Rest->LastZ) > StillToleranceCm || !bOnTerrain || !S.GetSubsystem()->IsIdle())
            {
                Rest->LastZ = Z;
                Rest->StillSince = Now;
                return false;
            }
            return Now - Rest->StillSince >= RestSeconds;
        });
    }

    /**
     * Starts a game test: spawns a plain ACharacter frozen on the original ground at (X, Y), has the first player
     * controller possess it, adds the dig component and queues the steps that let it down onto the terrain. Returns
     * null (after reporting why) when the game world is not ready; then nothing was spawned.
     */
    inline TSharedPtr<FDigGameScene> StartScene(FAutomationTestBase& Test, double X, double Y)
    {
        UWorld* World = GWorld;
        if (!Test.TestNotNull(TEXT("GWorld"), World) || !Test.TestTrue(TEXT("GWorld is a game world"), World->IsGameWorld()))
        {
            return nullptr;
        }
        UReflectionsDigSubsystem* Subsystem = World->GetSubsystem<UReflectionsDigSubsystem>();
        APlayerController* Controller = World->GetFirstPlayerController();
        TActorIterator<AReflectionsDigTerrain> TerrainIt(World);
        AReflectionsDigTerrain* Terrain = TerrainIt ? *TerrainIt : nullptr;
        if (!Test.TestNotNull(TEXT("Dig subsystem"), Subsystem) || !Test.TestNotNull(TEXT("First player controller"), Controller)
            || !Test.TestNotNull(TEXT("Dig terrain in the map"), Terrain))
        {
            return nullptr;
        }

        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        ACharacter* Character = World->SpawnActor<ACharacter>(ACharacter::StaticClass(), FVector(X, Y, 200.0), FRotator::ZeroRotator, Params);
        if (!Test.TestNotNull(TEXT("Character"), Character))
        {
            return nullptr;
        }

        TSharedRef<FDigGameScene> Scene = MakeShared<FDigGameScene>();
        Scene->Test = &Test;
        Scene->World = World;
        Scene->Subsystem = Subsystem;
        Scene->Terrain = Terrain;
        Scene->Controller = Controller;
        Scene->PreviousPawn = Controller->GetPawn();
        Scene->Character = Character;

        Controller->Possess(Character);
        Test.TestTrue(TEXT("The first player controller possesses the character"), Character->GetController() == Controller);
        Test.TestNotNull(TEXT("Dig component on the character"), UReflectionsDigComponent::EnsureOnPawn(Character));
        Teleport(*Scene, X, Y);
        AddLetDown(Scene, X, Y);
        return Scene;
    }

    /**
     * Queues the cleanup, which always runs: destroys the character, gives the controller its previous pawn back and
     * waits until the terrain is idle again, so the next test starts on a quiet terrain.
     */
    inline void AddCleanup(const FDigGameSceneRef& Scene)
    {
        AddStep(Scene, TEXT("Cleanup"), 1.0, [](FDigGameScene& S)
        {
            if (ACharacter* Character = S.GetCharacter())
            {
                Character->Destroy();
            }
            APlayerController* Controller = S.Controller.Get();
            APawn* Previous = S.PreviousPawn.Get();
            if (Controller != nullptr && Previous != nullptr)
            {
                Controller->Possess(Previous);
            }
            return true;
        }, /*bAlwaysRun=*/ true);
        AddStep(Scene, TEXT("Idle after the cleanup"), ReadyTimeoutSeconds, [](FDigGameScene& S)
        {
            return S.GetSubsystem() == nullptr || S.GetSubsystem()->IsIdle();
        }, /*bAlwaysRun=*/ true);
    }

    /** The chunk that holds a world position of the map's terrain. */
    inline FIntVector ChunkAt(const AReflectionsDigTerrain& Terrain, const FVector& Position)
    {
        const FVector Local = (Position - Terrain.GetGrid()->GetOriginCm()) / ChunkSizeCm;
        return FIntVector(FMath::FloorToInt(Local.X), FMath::FloorToInt(Local.Y), FMath::FloorToInt(Local.Z));
    }

    /** How far around a point the navmesh is searched: 50 cm across, 100 cm up and down (the untouched ground is 300 cm above a ramp's bottom). */
    inline const FVector NavProbeExtent(50.0, 50.0, 100.0);
    /** How long the navigation system may take to cover the patch after the map loads. */
    inline constexpr double NavReadyTimeoutSeconds = 30.0;

    /**
     * A ramp into the ground: stamps of radius 150 every 50 cm along its direction, each 25 cm lower (a 27 degree
     * slope, walkable), from the ground at its start down to 300 cm deep.
     */
    struct FDigRamp
    {
        static constexpr float StampRadiusCm = 150.0f;
        static constexpr double StepAlongCm = 50.0;
        static constexpr double StepDownCm = 25.0;
        static constexpr int32 Steps = 12;

        FVector2D Start;
        FVector2D Direction;

        /** The bottom of the last stamp: 600 cm along, 300 cm deep. */
        FVector GetLowestPoint() const
        {
            const FVector2D At = Start + Direction * (StepAlongCm * Steps);
            return FVector(At.X, At.Y, GroundZ - StepDownCm * Steps);
        }

        /** Digs every stamp; returns how many changed the grid (none when the ramp is already dug). */
        int32 Dig(UReflectionsDigSubsystem& Subsystem) const
        {
            int32 Changed = 0;
            for (int32 Step = 1; Step <= Steps; ++Step)
            {
                const FVector2D At = Start + Direction * (StepAlongCm * Step);
                const double CentreZ = GroundZ + StampRadiusCm - StepDownCm * Step;
                Changed += Subsystem.Dig(FVector(At.X, At.Y, CentreZ), StampRadiusCm, EReflectionsDigMode::Remove) ? 1 : 0;
            }
            return Changed;
        }
    };

    inline UNavigationSystemV1* GetNavigation(const FDigGameScene& Scene)
    {
        return FNavigationSystem::GetCurrent<UNavigationSystemV1>(Scene.GetWorld());
    }

    /** The navmesh point near Point (within NavProbeExtent), if there is one. */
    inline TOptional<FVector> ProjectToNavigation(const FDigGameScene& Scene, const FVector& Point)
    {
        FNavLocation Projected;
        const UNavigationSystemV1* Navigation = GetNavigation(Scene);
        if (Navigation != nullptr && Navigation->ProjectPointToNavigation(Point, Projected, NavProbeExtent))
        {
            return Projected.Location;
        }
        return TOptional<FVector>();
    }

    /** The terrain floor under a ramp's lowest point (a chunk-only trace), or the planned depth when the trace finds none. */
    inline FVector GetRampFloor(const FDigGameScene& Scene, const FDigRamp& Ramp)
    {
        const FVector Lowest = Ramp.GetLowestPoint();
        const TOptional<double> FloorZ = Scene.TraceGroundZ(Lowest.X, Lowest.Y);
        return FVector(Lowest.X, Lowest.Y, FloorZ.IsSet() ? *FloorZ : Lowest.Z);
    }

    /** Queues a wait until the navigation system has no build work left and the navmesh covers Point. */
    inline void AddWaitForNavigationAt(const FDigGameSceneRef& Scene, const FString& Label, const FVector& Point)
    {
        AddStep(Scene, Label, NavReadyTimeoutSeconds, [Point](FDigGameScene& S)
        {
            UNavigationSystemV1* Navigation = GetNavigation(S);
            return Navigation != nullptr && !Navigation->IsNavigationBuildInProgress() && S.GetSubsystem()->IsIdle()
                && ProjectToNavigation(S, Point).IsSet();
        });
    }
}

#endif // WITH_DEV_AUTOMATION_TESTS
