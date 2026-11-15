#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "ReflectionsCrowdCitySubsystem.generated.h"

class ULevelStreamingDynamic;

/**
 * The city crowd: a Mass (MetaHuman Crowd) pedestrian population that walks ZoneGraph sidewalk lanes.
 *
 * All of its level content (ZoneGraph shapes and data, the disturbance annotation, the Mass spawner) lives in a
 * separate crowd level that this subsystem streams into the host map at play time, so the host map file never
 * changes. Crowd.Mass.Enable 0 unloads it (despawning every pedestrian); 1 loads it again.
 *
 * Reactions go through the unified NPC system:
 * - every stimulus UReflectionsNpcSubsystem reports (spell noise, violence, deaths) becomes a ZoneGraph disturbance,
 *   which the pedestrians' StateTree answers by escaping along the lanes, the way Epic's crowd flees;
 * - pedestrians close to a stimulus are swapped for a full NPC actor of the matching look, enrolled as a Civilian:
 *   it hears the same stimulus, takes the spell's blast damage if it stood inside the blast, and from then on
 *   flinches, flees, dies and ragdolls like any placed civilian. At most Crowd.Mass.MaxPromoted are active at once;
 *   a calm one far from the player for a while walks out of the scene (is removed).
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsCrowdCitySubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;

    /** True while the crowd level is streamed in and visible. */
    UFUNCTION(BlueprintPure, Category="Crowd|City")
    bool IsCrowdLoaded() const;

    /** Pedestrian entities, visible ones, actor and instanced representations, from the MetaHuman Crowd plugin. */
    UFUNCTION(BlueprintCallable, Category="Crowd|City")
    FString Describe() const;

    /** Disturbances sent to the crowd since play began (for tests). */
    UFUNCTION(BlueprintPure, Category="Crowd|City")
    int32 GetDisturbancesSent() const { return DisturbancesSent; }

    /** Send a danger area to the crowd lanes directly (tests; normal play goes through NPC stimuli). */
    UFUNCTION(BlueprintCallable, Category="Crowd|City")
    void SendDisturbance(FVector Location, float Radius, float Duration);

    /** Pedestrians swapped into full NPC actors so far (alive or not). */
    UFUNCTION(BlueprintPure, Category="Crowd|City")
    int32 GetPromotedCount() const { return PromotedTotal; }

    /** Where the Mass pedestrians are (tests): every pedestrian within Radius (2D, cm) of Center; Radius <= 0 means all. */
    UFUNCTION(BlueprintCallable, Category="Crowd|City")
    TArray<FVector> GetPedestrianLocations(FVector Center, float Radius);

    /** Swap up to MaxCount pedestrians within Radius of Location into NPC actors now (tests). Returns how many. */
    UFUNCTION(BlueprintCallable, Category="Crowd|City")
    int32 PromoteNear(FVector Location, float Radius, int32 MaxCount);

private:
    struct FPromoted
    {
        TWeakObjectPtr<AActor> Actor;
        float CalmFarSeconds = 0.0f;
    };

    void LoadCrowdLevel();
    void UnloadCrowdLevel();
    void EnsureAnnotations();
    void HandleStimulus(const FReflectionsNpcStimulus& Stimulus);
    /** BudgetOverride < 0: promote up to Crowd.Mass.MaxPromoted active at once. */
    void ProcessPendingStimuli(int32 BudgetOverride = -1);
    /** InstanceIndex: the pedestrian's position in the entity config's CharacterInstances (INDEX_NONE if unknown). */
    AActor* PromoteEntityAt(const FTransform& Transform, const FReflectionsNpcStimulus* Cause, int32 InstanceIndex);
    /** The look actor for a crowd MetaHuman Instance, from Crowd.Mass.LookTable; nullptr = let the NPC system pick. */
    UClass* ResolvePromotedLook(int32 InstanceIndex);
    void TickPromoted(float DeltaTime);
    int32 CountActivePromoted() const;

    UPROPERTY(Transient)
    TObjectPtr<ULevelStreamingDynamic> CrowdLevel;

    UPROPERTY(Transient)
    TObjectPtr<AActor> AnnotationActor;

    TArray<FReflectionsNpcStimulus> PendingStimuli;
    TArray<FPromoted> Promoted;
    FString CrowdLevelPath;
    TSet<FString> WarnedLooks;
    FDelegateHandle StimulusHandle;
    double NextCheck = 0.0;
    int32 DisturbancesSent = 0;
    int32 PromotedTotal = 0;
    bool bHostMap = false;
    bool bWarnedMissing = false;
};
