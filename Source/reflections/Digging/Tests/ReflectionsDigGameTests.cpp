#include "Digging/ReflectionsDigSubsystem.h"

#include "CoreMinimal.h"
#include "AIController.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Digging/ReflectionsDigComponent.h"
#include "Digging/ReflectionsDigTerrain.h"
#include "Digging/ReflectionsDigTypes.h"
#include "Digging/Tests/ReflectionsDigGameTestHarness.h"
#include "Digging/Tests/ReflectionsDigTestTraces.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "Engine/EngineTypes.h"
#include "Engine/HitResult.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Navigation/PathFollowingComponent.h"
#include "NavigationData.h"
#include "NavigationSystem.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

// The tests below; their harness is in ReflectionsDigGameTestHarness.h.
using namespace ReflectionsDig::GameTest;

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
    // On grid samples, as before the grid origin moved half a cell inside the terrain's corner: the tunnel's stamps
    // then carve the same shape as before, whose floor a resting capsule clears to the tunnel's end.
    constexpr double X = 3425.0;
    constexpr double Y = 25.0;
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

    // The sweep of the character's capsule along the tunnel at capsule-centre height CentreZ; before the tunnel,
    // along the axis, it must hit the pit wall.
    auto SweepTunnelAt = [](const FDigGameScene& S, double CentreZ, FHitResult& OutHit)
    {
        const UCapsuleComponent* Capsule = S.GetCharacter()->GetCapsuleComponent();
        const FCollisionShape Shape = FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius(), Capsule->GetScaledCapsuleHalfHeight());
        const FCollisionQueryParams Params(SCENE_QUERY_STAT(ReflectionsDigGameTunnel), false, S.GetCharacter());
        return S.GetWorld()->SweepSingleByChannel(OutHit, FVector(X, Y, CentreZ), FVector(X + TunnelLengthCm, Y, CentreZ), FQuat::Identity,
            ECC_Pawn, Shape, Params);
    };
    auto SweepTunnel = [SweepTunnelAt](const FDigGameScene& S, FHitResult& OutHit)
    {
        return SweepTunnelAt(S, TunnelZ, OutHit);
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
    AddAction(Scene, TEXT("Sweep the tunnel"), [SweepTunnel, SweepTunnelAt](FDigGameScene& S)
    {
        FHitResult Hit;
        const bool bBlocked = SweepTunnel(S, Hit);
        S.Test->TestFalse(FString::Printf(TEXT("A capsule sweep along the tunnel is clear (hit %s at %s)"),
            bBlocked ? *GetNameSafe(Hit.GetComponent()) : TEXT("nothing"), *Hit.ImpactPoint.ToString()), bBlocked);

        // Walkable, not only clear: the capsule resting on the tunnel floor (its highest point along the tunnel, plus
        // the half-height and the 2.4 cm a walking character keeps above its floor) gets through too.
        TOptional<double> HighestFloorZ;
        for (double Along = 0.0; Along <= TunnelLengthCm; Along += 25.0)
        {
            const TOptional<double> FloorZ = FReflectionsDigTestTraces::TraceDownToChunkZ(S.GetWorld(), X + Along, Y, TunnelZ, TraceEndZ, S.GetCharacter());
            if (!FloorZ.IsSet())
            {
                S.Abort(FString::Printf(TEXT("No tunnel floor under X %.0f"), X + Along));
                return;
            }
            HighestFloorZ = FMath::Max(HighestFloorZ.Get(*FloorZ), *FloorZ);
        }
        const double HalfHeight = S.GetCharacter()->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
        const double RestingZ = *HighestFloorZ + HalfHeight + 2.4;
        FHitResult FloorHit;
        const bool bFloorBlocked = SweepTunnelAt(S, RestingZ, FloorHit);
        S.Test->TestFalse(FString::Printf(TEXT("A capsule sweep resting on the tunnel floor (floor %.1f, centre %.1f) is clear (hit %s at %s)"),
            *HighestFloorZ, RestingZ, bFloorBlocked ? *GetNameSafe(FloorHit.GetComponent()) : TEXT("nothing"), *FloorHit.ImpactPoint.ToString()), bFloorBlocked);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless PitTunnelAndFill: tunnel floor highest at %.1f, resting capsule centre %.1f, floor-level sweep %s"),
            *HighestFloorZ, RestingZ, bFloorBlocked ? *FString::Printf(TEXT("blocked at %s"), *FloorHit.ImpactPoint.ToString()) : TEXT("clear"));
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
        S.Test->TestTrue(FString::Printf(TEXT("The filled ground at (3425, 25) is within 60 cm of Z 0 (at %s)"),
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
        const UCharacterMovementComponent* Movement = S.GetCharacter()->GetCharacterMovement();
        S.Test->TestTrue(FString::Printf(TEXT("At rest the character walks on a chunk piece (floor %s)"), *GetNameSafe(Movement->CurrentFloor.HitResult.GetComponent())),
            Movement->IsMovingOnGround() && Cast<UReflectionsDigChunkComponent>(Movement->CurrentFloor.HitResult.GetComponent()) != nullptr);
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpikeNavmeshFollowsNewPitTest, "Reflections.DigSpike.NavmeshFollowsNewPit", DigGameTestFlags)
bool FReflectionsDigSpikeNavmeshFollowsNewPitTest::RunTest(const FString& Parameters)
{
    /** The brief's ramp: from (1800, 1600) along +X, its lowest point at (2400, 1600, -300). */
    const FDigRamp Ramp{ FVector2D(1800.0, 1600.0), FVector2D(1.0, 0.0) };
    /** On the ramp's line, 200 cm from its start: untouched ground before the dig. */
    const FVector GroundPoint(2000.0, 1600.0, GroundZ);
    constexpr double FollowLimitSeconds = 1.0;
    /** Long enough to measure a slow update; the limit above is what the test asserts. */
    constexpr double FollowTimeoutSeconds = 10.0;
    // The character only gives the terrain its focus; it stands clear of the ramp.
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, 2400.0, 600.0);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();

    struct FFollow
    {
        double NavUpdateBeforeDig = 0.0;
        /** World time of the last navigation update the terrain asked for once the ramp's collision was in. */
        double CollisionReadySeconds = 0.0;
        double CollisionReadyWallSeconds = 0.0;
        FVector Floor = FVector::ZeroVector;
        int32 Frames = 0;
    };
    TSharedRef<FFollow> Follow = MakeShared<FFollow>();
    AddWaitForNavigationAt(Scene, TEXT("The navmesh covers the ground at (2000, 1600)"), GroundPoint);
    AddAction(Scene, TEXT("Dig the ramp"), [Ramp, GroundPoint, Follow](FDigGameScene& S)
    {
        const AReflectionsDigTerrain* Terrain = S.Terrain.Get();
        if (Terrain == nullptr)
        {
            S.Abort(TEXT("The terrain is gone"));
            return;
        }
        const TOptional<FVector> OnGround = ProjectToNavigation(S, GroundPoint);
        S.Test->TestTrue(FString::Printf(TEXT("Before the dig a projection at (2000, 1600, 0) succeeds (at %s)"),
            OnGround.IsSet() ? *OnGround->ToString() : TEXT("none")), OnGround.IsSet());
        const TOptional<FVector> AtBottom = ProjectToNavigation(S, Ramp.GetLowestPoint());
        S.Test->TestFalse(FString::Printf(TEXT("Before the dig a projection at the ramp's lowest point %s fails (found %s)"),
            *Ramp.GetLowestPoint().ToString(), AtBottom.IsSet() ? *AtBottom->ToString() : TEXT("none")), AtBottom.IsSet());
        S.Test->TestFalse(TEXT("The safety floor can never affect navigation"), Terrain->GetSafetyFloor()->CanEverAffectNavigation());
        Follow->NavUpdateBeforeDig = Terrain->GetLastNavUpdateSeconds();
        S.Test->TestTrue(TEXT("The ramp's stamps change the grid"), Ramp.Dig(*S.GetSubsystem()) > 0);
    });
    AddStep(Scene, TEXT("The ramp's collision is ready"), ReadyTimeoutSeconds, [Ramp, Follow](FDigGameScene& S)
    {
        const AReflectionsDigTerrain* Terrain = S.Terrain.Get();
        if (Terrain == nullptr)
        {
            S.Abort(TEXT("The terrain is gone"));
            return true;
        }
        if (!S.GetSubsystem()->IsIdle())
        {
            return false;
        }
        Follow->CollisionReadySeconds = Terrain->GetLastNavUpdateSeconds();
        Follow->CollisionReadyWallSeconds = FPlatformTime::Seconds();
        Follow->Floor = GetRampFloor(S, Ramp);
        S.Test->TestTrue(FString::Printf(TEXT("The terrain asked navigation for an update after the dig (%.3f, before %.3f)"),
            Follow->CollisionReadySeconds, Follow->NavUpdateBeforeDig), Follow->CollisionReadySeconds > Follow->NavUpdateBeforeDig);
        S.Test->TestTrue(FString::Printf(TEXT("The ramp's floor at its lowest point is at least 250 cm deep (%.1f)"), Follow->Floor.Z),
            Follow->Floor.Z <= GroundZ - 250.0);
        UNavigationSystemV1* Navigation = GetNavigation(S);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless NavmeshFollowsNewPit: collision ready at world %.3f s (now %.3f), navigation building %s, %d build tasks left, %d running"),
            Follow->CollisionReadySeconds, S.GetWorld()->GetTimeSeconds(),
            Navigation != nullptr && Navigation->IsNavigationBuildInProgress() ? TEXT("yes") : TEXT("no"),
            Navigation != nullptr ? Navigation->GetNumRemainingBuildTasks() : -1, Navigation != nullptr ? Navigation->GetNumRunningBuildTasks() : -1);
        return true;
    });
    AddStep(Scene, TEXT("The navmesh reaches the ramp's lowest point"), FollowTimeoutSeconds, [Follow, FollowLimitSeconds](FDigGameScene& S)
    {
        ++Follow->Frames;
        const TOptional<FVector> AtBottom = ProjectToNavigation(S, Follow->Floor);
        if (!AtBottom.IsSet())
        {
            return false;
        }
        const double Seconds = S.GetWorld()->GetTimeSeconds() - Follow->CollisionReadySeconds;
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE NAV SECONDS=%.3f"), Seconds);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless NavmeshFollowsNewPit: projection onto %s succeeded at %s, %.3f s game time after the collision was ready (%.3f s wall clock after idle, frame %d of the wait)"),
            *Follow->Floor.ToString(), *AtBottom->ToString(), Seconds, FPlatformTime::Seconds() - Follow->CollisionReadyWallSeconds, Follow->Frames);
        S.Test->TestTrue(FString::Printf(TEXT("The navmesh reaches the ramp's lowest point within %.0f s of its collision being ready (took %.3f s)"),
            FollowLimitSeconds, Seconds), Seconds <= FollowLimitSeconds);
        return true;
    });
    AddCleanup(Scene);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpikeAiWalksIntoPitTest, "Reflections.DigSpike.AiWalksIntoPit", DigGameTestFlags)
bool FReflectionsDigSpikeAiWalksIntoPitTest::RunTest(const FString& Parameters)
{
    /**
     * Its own site, at least 1200 cm from every other game test's digs (NavmeshFollowsNewPit's ramp included), so
     * neither test's ground depends on which ran first: a ramp of the same shape from (2200, -400) along -Y, its
     * lowest point at (2200, -1000, -300).
     */
    const FDigRamp Ramp{ FVector2D(2200.0, -400.0), FVector2D(0.0, -1.0) };
    /** The AI starts on untouched ground 300 cm beyond the ramp's start and walks down it. */
    const FVector2D NpcStart(2200.0, -100.0);
    constexpr double ArriveWithinCm = 100.0;
    constexpr double ArriveTimeoutSeconds = 10.0;
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, 2400.0, 600.0);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();

    struct FWalk
    {
        TWeakObjectPtr<ACharacter> Npc;
        TWeakObjectPtr<AAIController> Brain;
        FVector Floor = FVector::ZeroVector;
        FVector Goal = FVector::ZeroVector;
        double StartSeconds = 0.0;
        /** Frames of the walk walking on a chunk piece. */
        int32 FramesOnTerrain = 0;
        int32 FramesWalking = 0;
        int32 Frames = 0;
        double LowestNpcFeetZ = TNumericLimits<double>::Max();
    };
    TSharedRef<FWalk> Walk = MakeShared<FWalk>();
    auto NpcFeetZ = [](const ACharacter& Npc)
    {
        return Npc.GetActorLocation().Z - Npc.GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
    };
    auto IsOnTerrain = [](const ACharacter& Npc)
    {
        const UCharacterMovementComponent* Movement = Npc.GetCharacterMovement();
        return Movement->IsMovingOnGround() && Cast<UReflectionsDigChunkComponent>(Movement->CurrentFloor.HitResult.GetComponent()) != nullptr;
    };

    AddAction(Scene, TEXT("Dig the ramp"), [Ramp](FDigGameScene& S)
    {
        S.Test->TestTrue(TEXT("The ramp's stamps change the grid"), Ramp.Dig(*S.GetSubsystem()) > 0);
    });
    AddStep(Scene, TEXT("Idle after the ramp"), ReadyTimeoutSeconds, [Ramp, Walk](FDigGameScene& S)
    {
        if (!S.GetSubsystem()->IsIdle())
        {
            return false;
        }
        Walk->Floor = GetRampFloor(S, Ramp);
        S.Test->TestTrue(FString::Printf(TEXT("The ramp's floor at its lowest point is at least 250 cm deep (%.1f)"), Walk->Floor.Z),
            Walk->Floor.Z <= GroundZ - 250.0);
        return true;
    });
    AddStep(Scene, TEXT("The navmesh reaches the ramp's lowest point"), NavReadyTimeoutSeconds, [Walk](FDigGameScene& S)
    {
        const TOptional<FVector> Goal = ProjectToNavigation(S, Walk->Floor);
        if (!Goal.IsSet())
        {
            return false;
        }
        Walk->Goal = *Goal;
        return true;
    });
    AddAction(Scene, TEXT("Spawn the AI character"), [NpcStart, Walk](FDigGameScene& S)
    {
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        ACharacter* Npc = S.GetWorld()->SpawnActor<ACharacter>(ACharacter::StaticClass(), FVector(NpcStart.X, NpcStart.Y, GroundZ + 200.0),
            FRotator::ZeroRotator, Params);
        AAIController* Brain = S.GetWorld()->SpawnActor<AAIController>(AAIController::StaticClass(), FVector(NpcStart.X, NpcStart.Y, GroundZ + 200.0),
            FRotator::ZeroRotator, Params);
        Walk->Npc = Npc;
        Walk->Brain = Brain;
        if (Npc == nullptr || Brain == nullptr)
        {
            S.Abort(TEXT("Could not spawn the AI character and its controller"));
            return;
        }
        Brain->Possess(Npc);
        S.Test->TestTrue(TEXT("The AI controller possesses the AI character"), Npc->GetController() == Brain);
    });
    AddStep(Scene, TEXT("The AI character stands on the terrain"), ReadyTimeoutSeconds, [Walk, IsOnTerrain](FDigGameScene& S)
    {
        const ACharacter* Npc = Walk->Npc.Get();
        if (Npc == nullptr)
        {
            S.Abort(TEXT("The AI character is gone"));
            return true;
        }
        return IsOnTerrain(*Npc);
    });
    AddAction(Scene, TEXT("Send the AI character to the ramp's lowest point"), [Walk](FDigGameScene& S)
    {
        AAIController* Brain = Walk->Brain.Get();
        if (Brain == nullptr)
        {
            S.Abort(TEXT("The AI controller is gone"));
            return;
        }
        const EPathFollowingRequestResult::Type Result = Brain->MoveToLocation(Walk->Goal, /*AcceptanceRadius=*/ 30.0f,
            /*bStopOnOverlap=*/ false, /*bUsePathfinding=*/ true, /*bProjectDestinationToNavigation=*/ false, /*bCanStrafe=*/ true,
            /*FilterClass=*/ {}, /*bAllowPartialPath=*/ false);
        S.Test->TestEqual(TEXT("The move request is accepted"), static_cast<int32>(Result), static_cast<int32>(EPathFollowingRequestResult::RequestSuccessful));
        const UPathFollowingComponent* Following = Brain->GetPathFollowingComponent();
        const FNavPathSharedPtr Path = Following != nullptr ? Following->GetPath() : FNavPathSharedPtr();
        S.Test->TestTrue(TEXT("The path is a full navmesh path"), Path.IsValid() && Path->IsValid() && !Path->IsPartial());
        Walk->StartSeconds = S.GetWorld()->GetTimeSeconds();
    });
    AddStep(Scene, TEXT("The AI character arrives within 100 cm of the ramp's lowest point"), ArriveTimeoutSeconds,
        [Walk, NpcFeetZ, IsOnTerrain, ArriveWithinCm, ArriveTimeoutSeconds](FDigGameScene& S)
    {
        const ACharacter* Npc = Walk->Npc.Get();
        if (Npc == nullptr)
        {
            S.Abort(TEXT("The AI character is gone"));
            return true;
        }
        ++Walk->Frames;
        Walk->FramesOnTerrain += IsOnTerrain(*Npc) ? 1 : 0;
        Walk->FramesWalking += Npc->GetCharacterMovement()->MovementMode == MOVE_Walking ? 1 : 0;
        Walk->LowestNpcFeetZ = FMath::Min(Walk->LowestNpcFeetZ, NpcFeetZ(*Npc));
        const FVector Feet(Npc->GetActorLocation().X, Npc->GetActorLocation().Y, NpcFeetZ(*Npc));
        const double Distance = FVector::Dist(Feet, Walk->Floor);
        if (Distance > ArriveWithinCm)
        {
            return false;
        }
        const double Seconds = S.GetWorld()->GetTimeSeconds() - Walk->StartSeconds;
        S.Test->TestTrue(FString::Printf(TEXT("The AI character arrives within %.0f s (took %.2f s)"), ArriveTimeoutSeconds, Seconds), Seconds <= ArriveTimeoutSeconds);
        // Every frame, the arrival one included: arriving by a fall, or by a frame off the terrain, does not count.
        S.Test->TestEqual(FString::Printf(TEXT("Frames of the walk walking on a chunk piece, of %d (%d with MOVE_Walking)"), Walk->Frames, Walk->FramesWalking),
            Walk->FramesOnTerrain, Walk->Frames);
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless AiWalksIntoPit: arrived %.1f cm from the lowest point %s in %.2f s game time (%d frames, %d on a chunk piece, %d walking, lowest feet %.1f)"),
            Distance, *Walk->Floor.ToString(), Seconds, Walk->Frames, Walk->FramesOnTerrain, Walk->FramesWalking, Walk->LowestNpcFeetZ);
        return true;
    });
    AddStep(Scene, TEXT("Remove the AI character"), 1.0, [Walk](FDigGameScene& S)
    {
        if (AAIController* Brain = Walk->Brain.Get())
        {
            Brain->UnPossess();
            Brain->Destroy();
        }
        if (ACharacter* Npc = Walk->Npc.Get())
        {
            Npc->Destroy();
        }
        return true;
    }, /*bAlwaysRun=*/ true);
    AddCleanup(Scene);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsDigSpikeNavigationNeverBuildsCollisionTest, "Reflections.DigSpike.NavigationNeverBuildsCollision", DigGameTestFlags)
bool FReflectionsDigSpikeNavigationNeverBuildsCollisionTest::RunTest(const FString& Parameters)
{
    /**
     * Its own site: buried chunk (2, 1, 0), X 4225..5825, Y -775..825, Z -2800..-1200, which no other game test digs
     * (the nearest digs are DigDownToBedrock's shaft at (4800, -1600) and FloorStaysWhileCollisionRecooks' at
     * (4800, 1600), both over 800 cm from its cavities). The character stands on the ground above it.
     */
    const FVector2D Above(5025.0, 25.0);
    static constexpr int32 SplitAboveVertices = 12000;
    /**
     * Ten digs 0.1 s apart: a tunnel along +X on the bedrock, between two rows of cavities, from (4825, 25, -2700):
     * five places 50 cm apart, each dug at the bedrock and 80 cm higher (as PitTunnelAndFill's tunnel), so its floor
     * is wide and tall enough for the navmesh's agent. It ends at (5025, 25), as far from the lattice's cavities as
     * the lattice allows, so the navmesh found there is the tunnel's.
     */
    static constexpr int32 Digs = 10;
    static constexpr double DigEverySeconds = 0.1;
    const FVector TunnelStart(4825.0, 25.0, -2700.0);
    /** The tunnel's end on the bedrock, before the digs. */
    const FVector TunnelEndFloor(5025.0, 25.0, BedrockTopZ);
    constexpr double TunnelStepCm = 50.0;
    constexpr double TunnelUpperCm = 80.0;
    constexpr double FollowLimitSeconds = 1.0;
    constexpr double FollowTimeoutSeconds = 10.0;
    const TSharedPtr<FDigGameScene> Started = StartScene(*this, Above.X, Above.Y);
    if (!Started.IsValid())
    {
        return false;
    }
    const FDigGameSceneRef Scene = Started.ToSharedRef();

    struct FBusy
    {
        FIntVector Chunk = FIntVector::ZeroValue;
        int32 Passes = 0;
        int32 CooksBeforeDigs = 0;
        double NextDigSeconds = -1.0;
        int32 Issued = 0;
        int32 Changed = 0;
        FVector LastDig = FVector::ZeroVector;
        FVector Floor = FVector::ZeroVector;
        double IdleSeconds = 0.0;
    };
    TSharedRef<FBusy> Busy = MakeShared<FBusy>();
    auto ChunkVertices = [](const AReflectionsDigTerrain& Terrain, const FIntVector& Chunk)
    {
        int32 Vertices = 0;
        for (int32 Index = 0; Index < Terrain.GetChunkPieceCount(Chunk); ++Index)
        {
            const UDynamicMeshComponent* Piece = Terrain.GetChunkPiece(Chunk, Index);
            Vertices += Piece != nullptr && Piece->GetMesh() != nullptr ? Piece->GetMesh()->VertexCount() : 0;
        }
        return Vertices;
    };

    // Riddle the chunk with radius-100 cavities on a 200 cm lattice (a second, offset lattice if the first does not
    // take it above 12,000 vertices), as SpikePerf.BusyChunkCost does.
    for (const double Offset : { 0.0, 100.0 })
    {
        AddAction(Scene, TEXT("Riddle the busy chunk"), [Busy, Offset, ChunkVertices](FDigGameScene& S)
        {
            const AReflectionsDigTerrain* Terrain = S.Terrain.Get();
            if (Terrain == nullptr || Terrain->GetGrid() == nullptr)
            {
                S.Abort(TEXT("The terrain is gone"));
                return;
            }
            Busy->Chunk = ChunkAt(*Terrain, FVector(5025.0, 25.0, -2000.0));
            if (Busy->Passes > 0 && ChunkVertices(*Terrain, Busy->Chunk) > SplitAboveVertices)
            {
                return;
            }
            ++Busy->Passes;
            for (double Z = -2700.0 + Offset; Z <= -1300.0; Z += 200.0)
            {
                for (double Y = -675.0 + Offset; Y <= 725.0; Y += 200.0)
                {
                    for (double X = 4325.0 + Offset; X <= 5725.0; X += 200.0)
                    {
                        S.GetSubsystem()->Dig(FVector(X, Y, Z), DigRadiusCm, EReflectionsDigMode::Remove);
                    }
                }
            }
        });
        AddStep(Scene, TEXT("Idle after riddling"), 120.0, [](FDigGameScene& S) { return S.GetSubsystem()->IsIdle(); });
    }
    AddWaitForNavigationAt(Scene, TEXT("The navmesh covers the ground above the busy chunk"), FVector(Above.X, Above.Y, GroundZ));
    AddAction(Scene, TEXT("Check the busy chunk is split"), [Busy, ChunkVertices, TunnelEndFloor](FDigGameScene& S)
    {
        const TOptional<FVector> Before = ProjectToNavigation(S, TunnelEndFloor);
        S.Test->TestFalse(FString::Printf(TEXT("Premise: before the digs a projection onto the tunnel's end %s fails (found %s)"),
            *TunnelEndFloor.ToString(), Before.IsSet() ? *Before->ToString() : TEXT("none")), Before.IsSet());
        const AReflectionsDigTerrain* Terrain = S.Terrain.Get();
        const int32 Vertices = ChunkVertices(*Terrain, Busy->Chunk);
        Busy->CooksBeforeDigs = Terrain->GetGameThreadCookCount();
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless NavigationNeverBuildsCollision: chunk %s riddled in %d passes, %d pieces, %d vertices; game-thread cooks so far %d"),
            *Busy->Chunk.ToString(), Busy->Passes, Terrain->GetChunkPieceCount(Busy->Chunk), Vertices, Busy->CooksBeforeDigs);
        if (!S.Test->TestTrue(FString::Printf(TEXT("Premise: chunk %s is above %d vertices (%d)"), *Busy->Chunk.ToString(), SplitAboveVertices, Vertices),
            Vertices > SplitAboveVertices))
        {
            S.bAborted = true;
        }
    });
    AddStep(Scene, TEXT("Dig inside the busy chunk ten times 0.1 s apart"), 30.0, [Busy, TunnelStart, TunnelStepCm, TunnelUpperCm](FDigGameScene& S)
    {
        const double Now = S.GetWorld()->GetTimeSeconds();
        if (Busy->NextDigSeconds < 0.0)
        {
            Busy->NextDigSeconds = Now;
        }
        if (Now < Busy->NextDigSeconds)
        {
            return false;
        }
        Busy->NextDigSeconds += DigEverySeconds;
        Busy->LastDig = TunnelStart + FVector(TunnelStepCm * (Busy->Issued / 2), 0.0, Busy->Issued % 2 == 0 ? 0.0 : TunnelUpperCm);
        Busy->Changed += S.GetSubsystem()->Dig(Busy->LastDig, DigRadiusCm, EReflectionsDigMode::Remove) ? 1 : 0;
        return ++Busy->Issued >= Digs;
    });
    AddStep(Scene, TEXT("Idle after the ten digs"), 60.0, [Busy](FDigGameScene& S)
    {
        if (!S.GetSubsystem()->IsIdle())
        {
            return false;
        }
        Busy->IdleSeconds = S.GetWorld()->GetTimeSeconds();
        const TOptional<double> FloorZ = FReflectionsDigTestTraces::TraceDownToChunkZ(S.GetWorld(), Busy->LastDig.X, Busy->LastDig.Y, Busy->LastDig.Z,
            TraceEndZ, S.GetCharacter());
        Busy->Floor = FVector(Busy->LastDig.X, Busy->LastDig.Y, FloorZ.IsSet() ? *FloorZ : Busy->LastDig.Z - DigRadiusCm);
        const int32 Cooks = S.Terrain.IsValid() ? S.Terrain->GetGameThreadCookCount() : -1;
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless NavigationNeverBuildsCollision: %d of %d digs changed the grid; game-thread cooks %d (%d before the digs); last dug floor %s"),
            Busy->Changed, Busy->Issued, Cooks, Busy->CooksBeforeDigs, FloorZ.IsSet() ? *Busy->Floor.ToString() : TEXT("not hit"));
        S.Test->TestTrue(FString::Printf(TEXT("The ten digs changed the grid (%d did)"), Busy->Changed), Busy->Changed > 0);
        S.Test->TestTrue(TEXT("A trace from the last dig hits its floor"), FloorZ.IsSet());
        S.Test->TestEqual(TEXT("No piece's collision was built on the game thread (GetGameThreadCookCount)"), Cooks, 0);
        return true;
    });
    AddStep(Scene, TEXT("The navmesh reaches the last dug floor"), FollowTimeoutSeconds, [Busy, FollowLimitSeconds](FDigGameScene& S)
    {
        const TOptional<FVector> OnFloor = ProjectToNavigation(S, Busy->Floor);
        if (!OnFloor.IsSet())
        {
            return false;
        }
        const double Seconds = S.GetWorld()->GetTimeSeconds() - Busy->IdleSeconds;
        UE_LOG(LogTemp, Display, TEXT("DIGSPIKE headless NavigationNeverBuildsCollision: projection onto %s succeeded at %s, %.3f s game time after idle"),
            *Busy->Floor.ToString(), *OnFloor->ToString(), Seconds);
        S.Test->TestTrue(FString::Printf(TEXT("The navmesh reaches the last dug floor within %.0f s of idle (took %.3f s)"), FollowLimitSeconds, Seconds),
            Seconds <= FollowLimitSeconds);
        return true;
    });
    AddCleanup(Scene);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
