#include "Digging/ReflectionsDigSubsystem.h"

#include "CoreMinimal.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Components/CapsuleComponent.h"
#include "Digging/ReflectionsDigComponent.h"
#include "Digging/ReflectionsDigTerrain.h"
#include "Digging/ReflectionsDigTypes.h"
#include "Digging/Tests/ReflectionsDigTestTraces.h"
#include "Engine/Engine.h"
#include "Engine/EngineTypes.h"
#include "Engine/HitResult.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

/*
 * Game-context tests: they run only in a -game process on the dig spike map
 * (test.ps1 -Game -Map /Game/Maps/DigSpike/L_DigSpike -Filter Reflections.DigSpike), where the game mode, world
 * subsystems and physics are live and the world ticks by itself. Each test queues latent steps that run once per frame;
 * every step has a wall-clock timeout that fails the test, and a failed step skips the rest of the test's steps except
 * the cleanup, which always runs. All tests of a run share the one map and its digs, so each digs at its own place.
 */

namespace
{
    constexpr EAutomationTestFlags DigGameTestFlags = EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter;

    /** The map's terrain: actor at (1000, -2400, 0), ground at Z 0, default size (3 x 3 x 2 chunks). */
    constexpr double GroundZ = 0.0;
    constexpr double GridFloorZ = -2800.0;
    /** The bedrock surface meshes about 25 cm above the grid floor. */
    constexpr double BedrockTopZ = GridFloorZ + 25.0;
    constexpr float DigRadiusCm = 100.0f;
    /** Downward traces start above the top of the grid and end under the safety floor (its top is 30 cm below the grid floor). */
    constexpr double TraceStartZ = 1000.0;
    constexpr double TraceEndZ = GridFloorZ - 300.0;
    constexpr double ChunkSizeCm = ReflectionsDig::ChunkCells * ReflectionsDig::CellSizeCm;

    constexpr double ReadyTimeoutSeconds = 30.0;
    constexpr double RestTimeoutSeconds = 30.0;
    /** How long a character must keep its height (game time) to count as resting after a dig. */
    constexpr double RestSeconds = 0.5;
    /** A height change smaller than this does not count as moving. */
    constexpr double StillToleranceCm = 1.0;

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
    void AddStep(const FDigGameSceneRef& Scene, const FString& Label, double TimeoutSeconds, TFunction<bool(FDigGameScene&)> Update,
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
    void AddAction(const FDigGameSceneRef& Scene, const FString& Label, TFunction<void(FDigGameScene&)> Action)
    {
        AddStep(Scene, Label, 1.0, [Action = MoveTemp(Action)](FDigGameScene& S) { Action(S); return true; });
    }

    /** Freezes the character standing on the original ground at (X, Y): it cannot fall until the terrain there is ready. */
    void Teleport(FDigGameScene& Scene, double X, double Y)
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
    void AddLetDown(const FDigGameSceneRef& Scene, double X, double Y)
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
    void AddWaitForRest(const FDigGameSceneRef& Scene, const FString& Label)
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
    TSharedPtr<FDigGameScene> StartScene(FAutomationTestBase& Test, double X, double Y)
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
    void AddCleanup(const FDigGameSceneRef& Scene)
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
    FIntVector ChunkAt(const AReflectionsDigTerrain& Terrain, const FVector& Position)
    {
        const FVector Local = (Position - Terrain.GetGrid()->GetOriginCm()) / ChunkSizeCm;
        return FIntVector(FMath::FloorToInt(Local.X), FMath::FloorToInt(Local.Y), FMath::FloorToInt(Local.Z));
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpikeHarnessRunsInGameTest, "Reflections.DigSpike.HarnessRunsInGame", DigGameTestFlags)
bool FReflectionsDigSpikeHarnessRunsInGameTest::RunTest(const FString& Parameters)
{
    UWorld* World = GWorld;
    if (!TestNotNull(TEXT("GWorld"), World))
    {
        return false;
    }
    TestTrue(TEXT("GWorld is a game world"), World->IsGameWorld());
    const FString PackageName = World->GetOutermost()->GetName();
    TestTrue(FString::Printf(TEXT("The map %s is L_DigSpike"), *PackageName), PackageName.EndsWith(TEXT("L_DigSpike")));

    // The wrapper caps the game process at 60 frames a second; 60 consecutive frames must take about a second.
    struct FFrameClock
    {
        int32 Frames = -1;
        double StartSeconds = 0.0;
    };
    TSharedRef<FFrameClock> Clock = MakeShared<FFrameClock>();
    FAutomationTestFramework::Get().EnqueueLatentCommand(MakeShared<FFunctionLatentCommand>([this, Clock]()
    {
        const double Now = FPlatformTime::Seconds();
        if (Clock->Frames < 0)
        {
            Clock->StartSeconds = Now;
        }
        if (++Clock->Frames < 60)
        {
            return false;
        }
        const double Elapsed = Now - Clock->StartSeconds;
        TestTrue(FString::Printf(TEXT("60 consecutive frames take between 0.8 and 1.5 s (took %.3f s)"), Elapsed), Elapsed >= 0.8 && Elapsed <= 1.5);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless HarnessRunsInGame: 60 frames in %.3f s"), Elapsed);
        return true;
    }));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpikePitTunnelAndFillTest, "Reflections.DigSpike.PitTunnelAndFill", DigGameTestFlags)
bool FReflectionsDigSpikePitTunnelAndFillTest::RunTest(const FString& Parameters)
{
    constexpr double X = 3400.0;
    constexpr double Y = 0.0;
    /** The tunnel runs along +X at the height of the pit's lowest stamp. */
    constexpr double TunnelZ = -300.0;
    constexpr double TunnelLengthCm = 500.0;
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, X, Y);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();
    TSharedRef<double> StartFeetZ = MakeShared<double>(0.0);

    AddAction(Scene, TEXT("Dig the pit"), [StartFeetZ](FDigGameScene& S)
    {
        *StartFeetZ = S.GetFeetZ();
        for (double Z = GroundZ; Z >= TunnelZ; Z -= DigRadiusCm)
        {
            S.Test->TestTrue(FString::Printf(TEXT("The pit stamp at Z %.0f digs"), Z), S.GetSubsystem()->Dig(FVector(X, Y, Z), DigRadiusCm, EReflectionsDigMode::Remove));
        }
    });
    AddWaitForRest(Scene, TEXT("The character rests in the pit"));
    AddAction(Scene, TEXT("Check the pit"), [StartFeetZ](FDigGameScene& S)
    {
        const TOptional<double> Bottom = S.TraceGroundZ(X, Y);
        if (S.Test->TestTrue(TEXT("The downward trace hits the pit bottom"), Bottom.IsSet()))
        {
            S.Test->TestTrue(FString::Printf(TEXT("The pit is at least 300 cm deep (bottom at %.1f)"), *Bottom), *Bottom <= GroundZ - 300.0);
        }
        const double FeetZ = S.GetFeetZ();
        S.Test->TestTrue(FString::Printf(TEXT("The character is at least 250 cm lower (feet %.1f, at the start %.1f)"), FeetZ, *StartFeetZ),
            FeetZ <= *StartFeetZ - 250.0);
        S.Test->TestTrue(FString::Printf(TEXT("The character is above the grid floor (feet %.1f)"), FeetZ), FeetZ > GridFloorZ);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless PitTunnelAndFill: pit bottom at %s, feet from %.1f to %.1f"),
            Bottom.IsSet() ? *FString::SanitizeFloat(*Bottom) : TEXT("no terrain hit"), *StartFeetZ, FeetZ);
    });

    // The sweep of the character's capsule along the tunnel axis; before the tunnel it must hit the pit wall.
    auto SweepTunnel = [](const FDigGameScene& S, FHitResult& OutHit)
    {
        const UCapsuleComponent* Capsule = S.GetCharacter()->GetCapsuleComponent();
        const FCollisionShape Shape = FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius(), Capsule->GetScaledCapsuleHalfHeight());
        const FCollisionQueryParams Params(SCENE_QUERY_STAT(ReflectionsDigGameTunnel), false, S.GetCharacter());
        return S.GetWorld()->SweepSingleByChannel(OutHit, FVector(X, Y, TunnelZ), FVector(X + TunnelLengthCm, Y, TunnelZ), FQuat::Identity,
            ECC_Pawn, Shape, Params);
    };
    AddAction(Scene, TEXT("Dig the tunnel"), [SweepTunnel](FDigGameScene& S)
    {
        FHitResult Wall;
        S.Test->TestTrue(TEXT("Before the tunnel the sweep hits the pit wall"), SweepTunnel(S, Wall));
        // Two rows of stamps 80 cm apart: a tunnel about 280 cm high, so the 176 cm capsule fits with room to spare.
        bool bAllDug = true;
        for (double Along = 0.0; Along <= TunnelLengthCm; Along += 50.0)
        {
            bAllDug &= S.GetSubsystem()->Dig(FVector(X + Along, Y, TunnelZ - 40.0), DigRadiusCm, EReflectionsDigMode::Remove);
            bAllDug &= S.GetSubsystem()->Dig(FVector(X + Along, Y, TunnelZ + 40.0), DigRadiusCm, EReflectionsDigMode::Remove);
        }
        S.Test->TestTrue(TEXT("Every tunnel stamp digs"), bAllDug);
    });
    AddWaitForRest(Scene, TEXT("The character rests after the tunnel"));
    AddAction(Scene, TEXT("Sweep the tunnel"), [SweepTunnel](FDigGameScene& S)
    {
        FHitResult Hit;
        const bool bBlocked = SweepTunnel(S, Hit);
        S.Test->TestFalse(FString::Printf(TEXT("A capsule sweep along the tunnel is clear (hit %s at %s)"),
            bBlocked ? *GetNameSafe(Hit.GetComponent()) : TEXT("nothing"), *Hit.ImpactPoint.ToString()), bBlocked);
        Teleport(S, 2400.0, 0.0);
    });
    AddLetDown(Scene, 2400.0, 0.0);
    AddAction(Scene, TEXT("Fill the pit"), [](FDigGameScene& S)
    {
        // Bottom up; the top stamp's sphere reaches Z 0, the original ground.
        for (double Z = TunnelZ; Z <= GroundZ - DigRadiusCm; Z += DigRadiusCm)
        {
            S.Test->TestTrue(FString::Printf(TEXT("The fill stamp at Z %.0f fills"), Z), S.GetSubsystem()->Dig(FVector(X, Y, Z), DigRadiusCm, EReflectionsDigMode::Add));
        }
    });
    AddStep(Scene, TEXT("Idle after the fill"), ReadyTimeoutSeconds, [](FDigGameScene& S) { return S.GetSubsystem()->IsIdle(); });
    AddAction(Scene, TEXT("Check the fill"), [](FDigGameScene& S)
    {
        const TOptional<double> Ground = S.TraceGroundZ(X, Y);
        S.Test->TestTrue(FString::Printf(TEXT("The filled ground at (3400, 0) is within 60 cm of Z 0 (at %s)"),
            Ground.IsSet() ? *FString::SanitizeFloat(*Ground) : TEXT("no terrain hit")), Ground.IsSet() && FMath::Abs(*Ground - GroundZ) <= 60.0);
        S.Test->TestTrue(FString::Printf(TEXT("The character never went below the grid floor (lowest feet %.1f)"), S.LowestFeetZ),
            S.LowestFeetZ > GridFloorZ);
    });
    AddCleanup(Scene);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpikeDigDownToBedrockTest, "Reflections.DigSpike.DigDownToBedrock", DigGameTestFlags)
bool FReflectionsDigSpikeDigDownToBedrockTest::RunTest(const FString& Parameters)
{
    constexpr double X = 4800.0;
    constexpr double Y = -1600.0;
    /** The character counts as stopped once its Z has not changed for this long (game time). */
    constexpr double StoppedSeconds = 2.0;
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, X, Y);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();

    struct FDescent
    {
        double StartFeetZ = 0.0;
        double StartSeconds = 0.0;
        double LastZ = TNumericLimits<double>::Max();
        double LastChangeSeconds = 0.0;
        int32 Digs = 0;
        /** Wall-clock time of the newest dig not yet followed by idle, or 0. */
        double DigIssuedSeconds = 0.0;
        double LongestDigToIdleSeconds = 0.0;
    };
    TSharedRef<FDescent> Descent = MakeShared<FDescent>();
    AddStep(Scene, TEXT("Dig down until the character stops for 2 s"), 180.0, [Descent](FDigGameScene& S)
    {
        const double Now = S.GetWorld()->GetTimeSeconds();
        const FVector Location = S.GetCharacter()->GetActorLocation();
        if (Descent->LastZ == TNumericLimits<double>::Max())
        {
            Descent->StartFeetZ = S.GetFeetZ();
            Descent->StartSeconds = Now;
            Descent->LastChangeSeconds = Now;
            Descent->LastZ = Location.Z;
        }
        if (S.GetFeetZ() < GridFloorZ)
        {
            S.Abort(FString::Printf(TEXT("The character's feet went below the grid floor (%.1f)"), S.GetFeetZ()));
            return true;
        }
        if (FMath::Abs(Location.Z - Descent->LastZ) > StillToleranceCm)
        {
            Descent->LastZ = Location.Z;
            Descent->LastChangeSeconds = Now;
        }
        // Dig under the feet whenever the last dig has fully landed (meshed and its collision swapped).
        if (S.GetSubsystem()->IsIdle())
        {
            const double WallNow = FPlatformTime::Seconds();
            if (Descent->DigIssuedSeconds > 0.0)
            {
                Descent->LongestDigToIdleSeconds = FMath::Max(Descent->LongestDigToIdleSeconds, WallNow - Descent->DigIssuedSeconds);
                Descent->DigIssuedSeconds = 0.0;
            }
            if (S.GetSubsystem()->Dig(FVector(Location.X, Location.Y, S.GetFeetZ()), DigRadiusCm, EReflectionsDigMode::Remove))
            {
                ++Descent->Digs;
                Descent->DigIssuedSeconds = WallNow;
            }
        }
        return Now - Descent->LastChangeSeconds >= StoppedSeconds;
    });
    AddAction(Scene, TEXT("Check the rest on bedrock"), [Descent](FDigGameScene& S)
    {
        const double HalfHeight = S.GetCharacter()->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
        const double Z = S.GetCharacter()->GetActorLocation().Z;
        const double Expected = BedrockTopZ + HalfHeight;
        S.Test->TestTrue(FString::Printf(TEXT("The character rests within 60 cm of the bedrock top plus its half-height (Z %.1f, expected %.1f)"), Z, Expected),
            FMath::Abs(Z - Expected) <= 60.0);
        S.Test->TestTrue(FString::Printf(TEXT("The character's feet were never below the grid floor (lowest %.1f)"), S.LowestFeetZ),
            S.LowestFeetZ > GridFloorZ);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless DigDownToBedrock: feet from %.1f to %.1f (%.1f cm) in %.2f s game time with %d digs; longest dig-to-idle %.1f ms wall clock"),
            Descent->StartFeetZ, S.GetFeetZ(), Descent->StartFeetZ - S.GetFeetZ(), Descent->LastChangeSeconds - Descent->StartSeconds,
            Descent->Digs, Descent->LongestDigToIdleSeconds * 1000.0);
    });
    AddCleanup(Scene);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpikeFloorStaysWhileCollisionRecooksTest, "Reflections.DigSpike.FloorStaysWhileCollisionRecooks", DigGameTestFlags)
bool FReflectionsDigSpikeFloorStaysWhileCollisionRecooksTest::RunTest(const FString& Parameters)
{
    constexpr double X = 4800.0;
    constexpr double Y = 1600.0;
    constexpr int32 Frames = 300;
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, X, Y);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();

    struct FRecook
    {
        int32 Frame = 0;
        int32 Digs = 0;
        double StartFeetZ = 0.0;
        double StartSeconds = 0.0;
        /** Frames whose trace was answered by old collision (a retiring piece, or a piece whose new mesh is still cooking), and the longest run of them. */
        int32 OldCollisionRun = 0;
        int32 LongestOldCollisionRun = 0;
        int32 OldCollisionFrames = 0;
    };
    TSharedRef<FRecook> Recook = MakeShared<FRecook>();
    AddStep(Scene, TEXT("Dig under the feet for 300 frames"), 120.0, [Recook](FDigGameScene& S)
    {
        const FVector Location = S.GetCharacter()->GetActorLocation();
        if (Recook->Frame == 0)
        {
            Recook->StartFeetZ = S.GetFeetZ();
            Recook->StartSeconds = FPlatformTime::Seconds();
        }
        else
        {
            // This frame's check sees the digs of every frame before it.
            const TOptional<FHitResult> Hit = FReflectionsDigTestTraces::TraceDown(S.GetWorld(), Location.X, Location.Y, Location.Z, TraceEndZ, S.GetCharacter());
            const bool bOnTerrain = Hit.IsSet() && Cast<UReflectionsDigChunkComponent>(Hit->GetComponent()) != nullptr && Hit->ImpactPoint.Z > GridFloorZ;
            if (!bOnTerrain)
            {
                S.Abort(FString::Printf(TEXT("Frame %d: the downward trace from the character (Z %.1f) hits %s at %s, not terrain above the grid floor"),
                    Recook->Frame, Location.Z, Hit.IsSet() ? *GetNameSafe(Hit->GetComponent()) : TEXT("nothing"),
                    Hit.IsSet() ? *Hit->ImpactPoint.ToString() : TEXT("-")));
                return true;
            }
            // Old collision answers when the hit piece is retiring (hidden, colliding until its replacement has
            // cooked) or is a reused piece whose new mesh is still cooking (its body is still the previous mesh's).
            const UReflectionsDigChunkComponent* Piece = Cast<UReflectionsDigChunkComponent>(Hit->GetComponent());
            if (!Piece->IsVisible() || Piece->IsCollisionCookPending())
            {
                ++Recook->OldCollisionFrames;
                Recook->LongestOldCollisionRun = FMath::Max(Recook->LongestOldCollisionRun, ++Recook->OldCollisionRun);
            }
            else
            {
                Recook->OldCollisionRun = 0;
            }
        }
        if (Recook->Frame == Frames)
        {
            return true;
        }
        Recook->Digs += S.GetSubsystem()->Dig(FVector(Location.X, Location.Y, S.GetFeetZ()), DigRadiusCm, EReflectionsDigMode::Remove) ? 1 : 0;
        ++Recook->Frame;
        return false;
    });
    AddAction(Scene, TEXT("Check the character"), [Recook](FDigGameScene& S)
    {
        S.Test->TestTrue(FString::Printf(TEXT("The character ends above the grid floor (feet %.1f)"), S.GetFeetZ()), S.GetFeetZ() > GridFloorZ);
        S.Test->TestTrue(FString::Printf(TEXT("The character's feet were never below the grid floor (lowest %.1f)"), S.LowestFeetZ),
            S.LowestFeetZ > GridFloorZ);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless FloorStaysWhileCollisionRecooks: %d frames in %.2f s, %d digs changed the grid, feet from %.1f to %.1f (%.1f cm); trace answered by old collision on %d frames, at most %d in a row"),
            Recook->Frame, FPlatformTime::Seconds() - Recook->StartSeconds, Recook->Digs, Recook->StartFeetZ, S.GetFeetZ(),
            Recook->StartFeetZ - S.GetFeetZ(), Recook->OldCollisionFrames, Recook->LongestOldCollisionRun);
    });
    AddCleanup(Scene);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpikePitSurvivesUnloadAndReturnTest, "Reflections.DigSpike.PitSurvivesUnloadAndReturn", DigGameTestFlags)
bool FReflectionsDigSpikePitSurvivesUnloadAndReturnTest::RunTest(const FString& Parameters)
{
    constexpr double PitX = 1400.0;
    constexpr double PitY = -2000.0;
    constexpr double AwayX = 5400.0;
    constexpr double AwayY = 2000.0;
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, PitX, PitY);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();

    struct FPit
    {
        double BottomZ = 0.0;
        FIntVector Chunk = FIntVector::ZeroValue;
        double LeftSeconds = 0.0;
    };
    TSharedRef<FPit> Pit = MakeShared<FPit>();
    AddAction(Scene, TEXT("Dig the pit"), [](FDigGameScene& S)
    {
        S.Test->TestTrue(TEXT("The first pit stamp digs"), S.GetSubsystem()->Dig(FVector(PitX, PitY, GroundZ), DigRadiusCm, EReflectionsDigMode::Remove));
        S.Test->TestTrue(TEXT("The second pit stamp digs"), S.GetSubsystem()->Dig(FVector(PitX, PitY, GroundZ - DigRadiusCm), DigRadiusCm, EReflectionsDigMode::Remove));
    });
    AddWaitForRest(Scene, TEXT("The character rests in the pit"));
    AddAction(Scene, TEXT("Record the pit and leave"), [Pit](FDigGameScene& S)
    {
        const TOptional<double> Bottom = S.TraceGroundZ(PitX, PitY);
        if (!Bottom.IsSet() || *Bottom > GroundZ - 100.0)
        {
            S.Abort(FString::Printf(TEXT("The downward trace finds no pit at (%.0f, %.0f) (%s)"), PitX, PitY,
                Bottom.IsSet() ? *FString::SanitizeFloat(*Bottom) : TEXT("no terrain hit")));
            return;
        }
        const AReflectionsDigTerrain* Terrain = S.Terrain.Get();
        if (Terrain == nullptr || Terrain->GetGrid() == nullptr)
        {
            S.Abort(TEXT("The terrain is gone"));
            return;
        }
        Pit->BottomZ = *Bottom;
        Pit->Chunk = ChunkAt(*Terrain, FVector(PitX, PitY, *Bottom));
        Pit->LeftSeconds = FPlatformTime::Seconds();
        Teleport(S, AwayX, AwayY);
    });
    AddStep(Scene, TEXT("The pit's chunk is released"), ReadyTimeoutSeconds, [Pit](FDigGameScene& S)
    {
        const AReflectionsDigTerrain* Terrain = S.Terrain.Get();
        if (Terrain == nullptr)
        {
            S.Abort(TEXT("The terrain is gone"));
            return true;
        }
        if (Terrain->FindChunkComponent(Pit->Chunk) != nullptr || Terrain->GetChunkPieceCount(Pit->Chunk) != 0)
        {
            return false;
        }
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless PitSurvivesUnloadAndReturn: chunk %s released %.3f s after the teleport"),
            *Pit->Chunk.ToString(), FPlatformTime::Seconds() - Pit->LeftSeconds);
        return true;
    });
    AddLetDown(Scene, AwayX, AwayY);
    AddAction(Scene, TEXT("Return to the pit"), [](FDigGameScene& S) { Teleport(S, PitX, PitY); });
    AddLetDown(Scene, PitX, PitY);
    AddStep(Scene, TEXT("Idle after the return"), ReadyTimeoutSeconds, [](FDigGameScene& S) { return S.GetSubsystem()->IsIdle(); });
    AddAction(Scene, TEXT("Check the pit"), [Pit](FDigGameScene& S)
    {
        const TOptional<double> Bottom = S.TraceGroundZ(PitX, PitY);
        S.Test->TestTrue(FString::Printf(TEXT("The pit bottom is within 5 cm of the recorded %.1f (at %s)"), Pit->BottomZ,
            Bottom.IsSet() ? *FString::SanitizeFloat(*Bottom) : TEXT("no terrain hit")), Bottom.IsSet() && FMath::Abs(*Bottom - Pit->BottomZ) <= 5.0);
    });
    AddCleanup(Scene);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
