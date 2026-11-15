#pragma once

#include "CoreMinimal.h"
#include "Squads/ReflectionsSquadTypes.h"

class AActor;
class ACharacter;
class UAnimSequence;
class USkeletalMeshComponent;

/**
 * The only place squad code touches the NPC system. Soldiers are ordinary NPCs of a "soldier" archetype:
 * the NPC system owns their health, hit reactions, fleeing, death, ragdoll, coin drop and infection report.
 * The squad only supplies where to stand while in formation, and who to fight.
 *
 * When the unified NPC subsystem lands, only ReflectionsSquadNpcBridge.cpp changes.
 */
class AReflectionsSquad;

namespace ReflectionsSquadNpc
{
    struct FSoldierSpec
    {
        EReflectionsSquadRole Role = EReflectionsSquadRole::Melee;
        /** 0 = the NPC system's Soldier / SoldierCaster archetype value. */
        float MaxHealth = 0.0f;
        /** 0 = the archetype value. */
        float MeleeDamage = 0.0f;
        /** Gilt guards: the NPC system's AlliedSoldier / AlliedSoldierCaster types (Guard until they exist). */
        bool bAllied = false;
    };

    /** Caster numbers kept on the NPC system's SoldierCaster archetype (one place for the tuning). */
    struct FCasterTuning
    {
        bool bValid = false;
        TArray<EHeroSpell> Spells;
        float DamageScale = 0.6f;
        float MinRange = 500.0f;
        float MaxRange = 1400.0f;
        FVector2D Cooldown = FVector2D(3.0, 5.0);
        float Windup = 0.7f;
        TSoftObjectPtr<UAnimSequence> CastAnimation;
    };

    bool GetCasterTuning(const UObject* WorldContext, FCasterTuning& Out, FName ArchetypeId = TEXT("SoldierCaster"));

    /** Play a clip made for the hidden walker's skeleton as a montage on it; the body follows. False if it can't. */
    bool PlayOnWalker(AActor* Soldier, class UAnimSequenceBase* Clip, float Rate);

    /** Says a line of Group (Soldier_Charge, Soldier_AllyDown...) in the soldier's own voice. False if it has none. */
    bool PlayBark(AActor* Speaker, FName Group);

    /** The NPC system's tarnished: infected townsfolk and the villain's hosts. */
    bool IsTarnished(const AActor* Actor);

    /** Every NPC the NPC system runs. */
    TArray<AActor*> GetNpcActors(const UObject* WorldContext);

    /** Bind / unbind the squad's handlers to OnNpcSpellHit, OnNpcDied and (when the NPC system has it) OnPlayerCrime. */
    void BindNpcEvents(AReflectionsSquad* Squad, bool bBind);

    /**
     * Calls Fn(Offender, Location) whenever the NPC system reports a crime: its subsystem's native multicast
     * OnCrime(AActor* Offender, AActor* Victim, const FVector& Location, float Severity), found at compile time.
     * Returns an invalid handle while the NPC system has no such delegate.
     */
    FDelegateHandle BindCrimes(const UObject* WorldContext, TFunction<void(AActor*, const FVector&)> Fn);
    void UnbindCrimes(const UObject* WorldContext, FDelegateHandle Handle);

    /** The NPC system itself puts a weapon in this soldier's hand (its archetype names a WeaponProp). */
    bool NpcCarriesWeapon(AActor* Soldier);

    /** The NPC system itself puts a shield on this soldier's left arm (its archetype names a Combat.ShieldProp). */
    bool NpcCarriesShield(AActor* Soldier);

    /** Soldier looks the NPC system keeps on the Soldier / SoldierCaster archetype (crowd looks fills them). */
    bool GetArchetypeLooks(const UObject* WorldContext, bool bCaster, TArray<TSoftClassPtr<AActor>>& Out);

    /**
     * Looks for a squad of one side (user rule: the red people stay in the red world, the rag-clad in the white).
     * Uses the NPC system's GetLooksAt(ArchetypeId, Location) when it has one; otherwise the archetype's looks whose
     * asset names carry the side ("Gilt" / "Frost" / "Pew"). Side empty = no filter. Never returns another side's look.
     */
    bool GetSideLooks(const UObject* WorldContext, FName ArchetypeId, const FVector& Location, const FString& Side,
        TArray<TSoftClassPtr<AActor>>& Out);
    bool GetArchetypeLooks(const UObject* WorldContext, FName ArchetypeId, TArray<TSoftClassPtr<AActor>>& Out);

    /** F1..F3 / M1..M3 voice slot the NPC system gave this soldier (empty if none). */
    FString GetVoiceSuffix(AActor* Soldier);

    /** Enrol a freshly spawned look actor as a soldier NPC. Call once, right after spawning. */
    void Enrol(AActor* Soldier, const FSoldierSpec& Spec);

    /** The character that moves the soldier (the NPC system's hidden locomotion driver). Null until ready. */
    ACharacter* GetDriver(AActor* Soldier);

    /** The visible body (MetaHuman "Body" mesh) that animations and telegraphs attach to. */
    USkeletalMeshComponent* GetBody(AActor* Soldier);

    bool IsAlive(AActor* Soldier);
    float GetHealth(AActor* Soldier);

    /** The NPC system decided this soldier is running away (low health, panic). */
    bool WantsToFlee(AActor* Soldier);

    /** The NPC system has the soldier fighting or investigating on its own (it was hit or heard magic). */
    bool IsAggravated(AActor* Soldier);

    /** Melee soldiers: hand over to (or take back from) the NPC system's enemy melee behaviour. */
    void SetMeleeTarget(AActor* Soldier, AActor* Target);

    /** True while the squad moves the body; false lets the NPC system move it. */
    void SetSteered(AActor* Soldier, bool bSteered);

    /** Give the soldier back to the NPC system entirely; the squad stops steering it. */
    void Release(AActor* Soldier);

    /** Debug/testing: kill a soldier through the normal damage path. */
    void Kill(AActor* Soldier, AActor* Instigator);
}
