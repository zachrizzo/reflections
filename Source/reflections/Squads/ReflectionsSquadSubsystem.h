#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "ReflectionsSquadSubsystem.generated.h"

class AReflectionsSquad;

/**
 * Test and debug entry points for enemy squads. Map owners place AReflectionsSquad + AReflectionsSquadRoute
 * actors directly; this subsystem only spawns throwaway test squads at PIE time (nothing is saved).
 *
 * Console (non-shipping): Squads.SpawnTest [count] | Squads.Clear | Squads.Engage | Squads.Reform |
 * Squads.Cast | Squads.KillAll | Squads.Dump. CVar Squads.AutoTest 1 spawns two test squads automatically
 * when Lvl_HeroSampleCrowd begins play. CVar Squads.Debug 1/2 draws routes, anchors and slots.
 * CVar Squads.StartPatrol (default 1) raises one squad patrolling in sight of the player start on the showcase maps
 * (Lvl_HeroSampleCrowd, Lvl_MockCity) when no squad already patrols within 40 m of it; set 0 before PIE for an empty
 * start. Squads.Clear removes it too.
 */
UCLASS()
class REFLECTIONS_API UReflectionsSquadSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;

    /** Spawn test squads around the player: a column of five and a line of five, on ground-checked routes. */
    UFUNCTION(BlueprintCallable, Category="Squads")
    void SpawnTestSquads(int32 Count = 2);

    /** Spawn one allied Gilt test squad (swords and shields) beside the player. */
    UFUNCTION(BlueprintCallable, Category="Squads")
    void SpawnGiltTestSquad();

    /** Remove squads (and routes) that SpawnTestSquads created. */
    UFUNCTION(BlueprintCallable, Category="Squads")
    void ClearTestSquads();

    UFUNCTION(BlueprintPure, Category="Squads")
    TArray<AReflectionsSquad*> GetSquads() const;

    /**
     * Raise the alarm: every squad with a soldier within Radius of Location turns on Offender (and brings in its
     * neighbours). For systems that see a crime the squads cannot, e.g. the NPC witness system or a quest.
     */
    UFUNCTION(BlueprintCallable, Category="Squads")
    void RaiseAlarm(AActor* Offender, FVector Location, float Radius = 2500.0f);

private:
    /** Showcase maps: one squad patrolling in sight of the player start, unless a squad already patrols near it. */
    void SpawnStartPatrol();

    TArray<TWeakObjectPtr<AActor>> TestActors;
    TWeakObjectPtr<AActor> StartPatrol;
};
