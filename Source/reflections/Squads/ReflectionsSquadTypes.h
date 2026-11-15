#pragma once

#include "CoreMinimal.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "ReflectionsSquadTypes.generated.h"

class AActor;
class UNiagaraComponent;
class UPointLightComponent;

/** How a squad lines up while it marches. */
UENUM(BlueprintType)
enum class EReflectionsSquadFormation : uint8
{
    /** Single file; every soldier walks the leader's footsteps. */
    Column,
    /** Leader in front, then pairs; walks the leader's footsteps. */
    ColumnOfTwos,
    /** Shoulder to shoulder; the line wheels at corners. */
    Line
};

UENUM(BlueprintType)
enum class EReflectionsSquadRole : uint8
{
    /** Closes in with the NPC system's enemy melee behaviour. */
    Melee,
    /** Keeps range and casts real spells through the spell system. */
    Caster
};

UENUM(BlueprintType)
enum class EReflectionsSquadState : uint8
{
    Inactive,
    Marching,
    Halted,
    Engaged,
    Reforming,
    Destroyed
};

UENUM(BlueprintType)
enum class EReflectionsSquadMemberState : uint8
{
    /** Spawned, waiting for the NPC system to give it a locomotion driver. */
    Pending,
    InFormation,
    Fighting,
    /** Handed back to the NPC system (fleeing); the squad no longer steers it. */
    Released,
    Dead
};

UENUM(BlueprintType)
enum class EReflectionsSquadCastPhase : uint8
{
    Ready,
    Windup,
    Recover
};

/** Whose soldiers these are. */
UENUM(BlueprintType)
enum class EReflectionsSquadFaction : uint8
{
    /** White London raiders in rags (Frostside): hostile to the player. */
    Frost,
    /** Captain Brask's men in red (Giltside): allied. They fight the tarnished and Frost soldiers on sight and turn on
     *  the player only when the player attacks them or a civilian near them. */
    Gilt
};

/** Runtime record for one soldier. The NPC system owns its health, reactions, death and ragdoll. */
USTRUCT(BlueprintType)
struct FReflectionsSquadMember
{
    GENERATED_BODY()

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Squad")
    TObjectPtr<AActor> Actor = nullptr;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Squad")
    EReflectionsSquadRole Role = EReflectionsSquadRole::Melee;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Squad")
    EReflectionsSquadMemberState State = EReflectionsSquadMemberState::Pending;

    /** Spell this caster throws (its signature element, so players can read who is who). */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Squad")
    EHeroSpell Spell = EHeroSpell::Fire;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Squad")
    EReflectionsSquadCastPhase CastPhase = EReflectionsSquadCastPhase::Ready;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Squad")
    int32 CastsReleased = 0;

    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> Telegraph = nullptr;
    UPROPERTY(Transient) TObjectPtr<UPointLightComponent> TelegraphLight = nullptr;
    UPROPERTY(Transient) TObjectPtr<UClass> SavedAnimClass = nullptr;

    float CastTime = 0.0f;
    float CastReleaseAt = 0.0f;
    float CastEnd = 0.0f;
    /** Two-part cast gesture: cut from the channel loop to this release clip at ReleaseClipAt (<0: none pending). */
    TWeakObjectPtr<class UAnimSequence> ReleaseClip;
    float ReleaseClipAt = -1.0f;
    float ReleaseRate = 1.0f;
    /** The cast gesture runs on the hidden walker (crash-safe), not on the visible body. */
    bool bWalkerGesture = false;
    float CastCooldown = 0.0f;
    bool bMarchClipActive = false;
    /** Melee: seconds left fanning out around the target before the NPC melee motor takes over. */
    float DeployTime = 0.0f;
    /** Melee: the squad is running this soldier down to the player (the NPC motor takes over up close). */
    bool bCharging = false;
    float RepathTimer = 0.0f;
    /** Gilt melee: the shield has been fitted to the animating hand. */
    bool bShieldPlaced = false;
    FVector ChargeWaypoint = FVector::ZeroVector;
    float FlankAngle = 0.0f;
    float LastHealth = -1.0f;
    float SightTimer = 0.0f;
    bool bHasSight = false;
    bool bReleased = false;
    float StrafeSign = 1.0f;
    float StrafeTimer = 0.0f;
    float SlotError = 0.0f;
};
