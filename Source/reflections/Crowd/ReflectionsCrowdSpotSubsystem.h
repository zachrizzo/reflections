#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "ReflectionsCrowdSpotSubsystem.generated.h"

class ACharacter;
class UReflectionsNpcReactionComponent;

/**
 * Street scenes ("scenario spots"): places where civilians stop and do something, so a street reads as people going
 * about their day rather than people walking.
 *
 * Spots come from a JSON list per map (Content/Crowd/Spots/<MapName>.json, see the CrowdInfrastructure README):
 * - chat:   2-4 people in a small ring facing in, gesturing; with two or more there, the chat director plays a
 *           conversation for the spot's place;
 * - window: 1-2 people side by side looking into a shopfront (the spot's yaw);
 * - vendor: one person calling out and waving at the street;
 * - bench:  1-2 people SITTING on a real bench of the map found near the spot (GrayLondonBench or a shelter bench),
 *           with the Game Animation Sample bench clips;
 * - lean:   one person leaning on a wall found near the spot (wall on their left);
 * - smoke:  one person standing with a pipe.
 * Claimable spots (the default) borrow a passing ring walker for 20-45 s; pinned spots spawn their own occupant
 * (SpawnNpc "Civilian") out of sight while the hero is near. Bench, lean and smoke spots may also be claimable.
 *
 * The scene itself is the NPC system's (UReflectionsNpcSubsystem::BeginNpcScene and companions): the loop plays on
 * the hidden walker, seated and leaning occupants are pinned (no movement) with their capsule collision off while
 * they sit, and the NPC system ends the scene by itself on any reaction, hit, death or taking. Slots hold weak
 * references, re-checked every 0.25 s and on OnNpcSceneEnded: the body always goes back (collision, steering, stroll).
 *
 * Tuning: Crowd.Spots.* console variables. Crowd.Spots.Enable 0 frees everyone.
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsCrowdSpotSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;

    /** Spots loaded for this map. */
    UFUNCTION(BlueprintPure, Category="Crowd|Spots")
    int32 GetSpotCount() const { return Spots.Num(); }

    /** People at a spot now (settled in their scene). */
    UFUNCTION(BlueprintPure, Category="Crowd|Spots")
    int32 GetOccupiedCount() const;

    /** One line per spot: kind, mode, whether it passed its check, slots and who is in them (tests). */
    UFUNCTION(BlueprintCallable, Category="Crowd|Spots")
    FString Describe() const;

private:
    enum class EKind : uint8 { Chat, Window, Vendor, Bench, Lean, Smoke };
    enum class EPhase : uint8 { Free, Claiming, Approaching, Holding, Leaving };

    struct FSlot
    {
        /** Where the occupant stands (or its root sits) and faces. */
        FVector Position = FVector::ZeroVector;
        float Yaw = 0.0f;
        /** Where it walks to first (in front of a bench; the slot itself otherwise). */
        FVector Approach = FVector::ZeroVector;
        TWeakObjectPtr<AActor> Occupant;
        EPhase Phase = EPhase::Free;
        double PhaseSince = 0.0;
        double LeaveAt = 0.0;
        double NextBreakAt = 0.0;
        double FreeAfter = 0.0;
        /** What this slot did to its occupant, so release undoes exactly that. */
        bool bAddedNoStroll = false;
        bool bSteered = false;
        bool bSpawned = false;
        bool bCollisionOff = false;
        TEnumAsByte<ECollisionEnabled::Type> PreviousCollision = ECollisionEnabled::QueryAndPhysics;
    };

    struct FSpot
    {
        FName Name;
        FName Place;
        EKind Kind = EKind::Chat;
        bool bPinned = false;
        FVector Location = FVector::ZeroVector;
        float Yaw = 0.0f;
        int32 SlotCount = 2;
        /** How far to look for its bench, wall or floor (cm); 0 = the kind's default (15 m, 2.5 m, 8 m). */
        float Search = 0.0f;
        bool bChecked = false;
        bool bValid = false;
        bool bActive = false;
        TArray<FSlot> Slots;
        double NextChatAt = 0.0;
    };

    void LoadSpots(const FString& MapName);
    bool CheckSpot(FSpot& Spot) const;
    bool FindStreetFloor(const FVector& Near, float SearchRadius, FVector& OutFloor) const;
    bool HasRoom(const FVector& Floor) const;
    /** Bench seats near a spot: (root on the floor under the seat, yaw facing out, approach point in front). */
    bool FindBenchSeats(FSpot& Spot) const;
    /** A wall near the floor point: the lean position (wall on the left) and its yaw. */
    bool FindLeanPlace(const FVector& Floor, float Reach, FVector& OutRoot, float& OutYaw) const;
    bool IsSeen(const FVector& Location) const;
    void TickSpot(FSpot& Spot, const FVector& Hero, double Now);
    void TickSlot(FSpot& Spot, FSlot& Slot, double Now);
    void Settle(FSpot& Spot, FSlot& Slot, ACharacter* Driver, double Now);
    void TryClaim(FSpot& Spot, FSlot& Slot, double Now);
    void TrySpawnPinned(FSpot& Spot, FSlot& Slot, double Now);
    /** Ends the scene and gives the body back. bGently: seated people stand up first (Leaving). */
    void Release(FSpot& Spot, FSlot& Slot, double Now, bool bDestroySpawned, bool bGently);
    void FinishRelease(FSlot& Slot, double Now, bool bDestroySpawned);
    void RestoreCollision(FSlot& Slot) const;
    bool IsClaimed(const AActor* Actor) const;

    UFUNCTION()
    void HandleSceneEnded(AActor* Npc, bool bDisturbed);

    TArray<FSpot> Spots;
    double NextTick = 0.0;
    int32 PinnedAlive = 0;
};
