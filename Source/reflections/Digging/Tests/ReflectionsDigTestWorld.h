#pragma once

#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"
#include "Tests/AutomationCommon.h"

/**
 * A throwaway game world for automation tests: a game-type UWorld with a physics scene and a game instance,
 * registered with GEngine and already begun play (under the engine's AGameModeBase), so spawned actors run
 * BeginPlay. It is ticked only by Tick.
 * Creation and teardown follow the engine's FTestWorldWrapper; the destructor ends play, destroys the world
 * and collects garbage, then checks that nothing still holds the world.
 */
struct FReflectionsDigTestWorld
{
    /** The world, or nullptr if it could not be created (the reason is logged as an error). */
    UWorld* World = nullptr;

    FReflectionsDigTestWorld()
    {
        IgnoreMissingProjectContent();

        bool bReady = Wrapper.CreateTestWorld(EWorldType::Game);
        if (bReady)
        {
            // Use the plain engine game mode, not the project's default, so the world does not depend on game content.
            Wrapper.GetTestWorld()->GetWorldSettings()->DefaultGameMode = AGameModeBase::StaticClass();
            bReady = Wrapper.BeginPlayInTestWorld();
        }
        if (bReady)
        {
            World = Wrapper.GetTestWorld();
        }
        else
        {
            TArray<FString> Errors;
            Wrapper.AppendErrorMessages(Errors);
            for (const FString& Error : Errors)
            {
                UE_LOG(LogTemp, Error, TEXT("FReflectionsDigTestWorld: %s"), *Error);
            }
        }
    }

    ~FReflectionsDigTestWorld()
    {
        if (Wrapper.GetTestWorld() != nullptr)
        {
            Wrapper.DestroyTestWorld(/*bForceGarbageCollect=*/ true);
        }
        World = nullptr;
    }

    FReflectionsDigTestWorld(const FReflectionsDigTestWorld&) = delete;
    FReflectionsDigTestWorld& operator=(const FReflectionsDigTestWorld&) = delete;

    /** Advances the world (actors, components, physics, world subsystems) by Frames ticks of DeltaSeconds each. */
    void Tick(int32 Frames = 1, float DeltaSeconds = 1.0f / 60.0f)
    {
        for (int32 Frame = 0; World != nullptr && Frame < Frames; ++Frame)
        {
            Wrapper.TickTestWorld(DeltaSeconds);
        }
    }

    /** Spawns a T and runs its construction and BeginPlay. Spawning ignores collision. */
    template <typename T>
    T* Spawn(const FVector& Location = FVector::ZeroVector, const FRotator& Rotation = FRotator::ZeroRotator)
    {
        if (World == nullptr)
        {
            return nullptr;
        }
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        return World->SpawnActor<T>(T::StaticClass(), Location, Rotation, Params);
    }

    /** Spawns a T without running construction or BeginPlay; set it up, then call FinishSpawning. */
    template <typename T>
    T* SpawnDeferred(const FVector& Location = FVector::ZeroVector, const FRotator& Rotation = FRotator::ZeroRotator)
    {
        if (World == nullptr)
        {
            return nullptr;
        }
        const FTransform Transform(Rotation, Location);
        T* Actor = World->SpawnActorDeferred<T>(T::StaticClass(), Transform, nullptr, nullptr,
            ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (Actor != nullptr)
        {
            PendingSpawns.Add(Actor, Transform);
        }
        return Actor;
    }

    /** Finishes an actor from SpawnDeferred at the transform it was spawned with (construction, then BeginPlay). */
    template <typename T>
    T* FinishSpawning(T* Actor)
    {
        FTransform Transform;
        if (Actor == nullptr || !PendingSpawns.RemoveAndCopyValue(Actor, Transform))
        {
            UE_LOG(LogTemp, Error, TEXT("FReflectionsDigTestWorld: FinishSpawning needs an actor from SpawnDeferred"));
            return nullptr;
        }
        Actor->FinishSpawning(Transform);
        return Actor;
    }

private:
    /**
     * The spell VFX world subsystem starts in every game world and warns when its /Game assets are absent, as they
     * are in a content-less checkout. Those warnings say nothing about the test, so the running test ignores them
     * (negative occurrences: any number, including none, so a full checkout passes too).
     * The expected-message verbosity is a minimum, so Error-level lines matching those two patterns are ignored as
     * well; a test that loads those assets on purpose must not rely on this helper to report a failure.
     */
    static void IgnoreMissingProjectContent()
    {
        if (FAutomationTestBase* Test = FAutomationTestFramework::Get().GetCurrentTest())
        {
            Test->AddExpectedMessage(TEXT("Failed to find object '\\w+ /Game/(Characters/Hero/SpellVFX|Blueprints/Combat/Blood)/"),
                ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, -1);
            Test->AddExpectedMessage(TEXT("Spell VFX: run Tools/SpellVFX/build_spell_niagara.py"),
                ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, -1, /*IsRegex=*/ false);
        }
    }

    FTestWorldWrapper Wrapper;
    TMap<AActor*, FTransform> PendingSpawns;
};

#endif // WITH_DEV_AUTOMATION_TESTS
