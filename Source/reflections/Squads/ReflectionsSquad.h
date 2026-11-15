#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Squads/ReflectionsSquadTypes.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "ReflectionsSquad.generated.h"

class AReflectionsSquadRoute;
class UAnimSequence;
class UAnimSequenceBase;
class UBillboardComponent;
class UNiagaraSystem;
class USkeletalMeshComponent;
class UStaticMesh;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FReflectionsSquadStateChanged, EReflectionsSquadState, State, AActor*, Cause);

/**
 * Spawner and squad controller in one: place it in a level, point it at a Reflections Squad Route, and it
 * spawns 4-6 soldiers that march the route in formation. On sighting the player (or when hit) the squad breaks
 * formation: melee soldiers close in through the NPC system's enemy behaviour, casters keep range and throw
 * real spells. When the player is gone the squad reforms and marches on.
 *
 * The squad never owns a soldier's life: health, hit reactions, fleeing, death, ragdoll, coins and infection
 * all come from the NPC system (see ReflectionsSquadNpcBridge).
 */
UCLASS(Blueprintable, meta=(DisplayName="Reflections Squad Spawner"))
class REFLECTIONS_API AReflectionsSquad : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsSquad();

    // ---- Setup ---------------------------------------------------------------------------------------------

    /** Route to patrol. Without one the squad holds position where the spawner stands. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad")
    TObjectPtr<AReflectionsSquadRoute> Route;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad", meta=(ClampMin="1", ClampMax="8"))
    int32 SquadSize = 5;

    /** How many of the squad are casters (they march at the rear). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad", meta=(ClampMin="0", ClampMax="8"))
    int32 CasterCount = 2;

    /**
     * Take soldier looks from the NPC system's Soldier / SoldierCaster archetypes (their Looks lists, kept filled by
     * the crowd looks owner). MeleeLooks / CasterLooks below are used when this is off or an archetype list is empty.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad")
    bool bUseArchetypeLooks = true;

    /** Fallback looks for melee soldiers, used in turn. MetaHuman look actors only (with a "Body" mesh). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad")
    TArray<TSoftClassPtr<AActor>> MeleeLooks;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad")
    TArray<TSoftClassPtr<AActor>> CasterLooks;

    /** Frost raiders (hostile) or Gilt guards (allied). With bFactionFromSide the side level decides. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad")
    EReflectionsSquadFaction Faction = EReflectionsSquadFaction::Frost;

    /** Take the faction from the side level the spawner stands in: Giltside = Gilt, Frostside = Frost. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad")
    bool bFactionFromSide = true;

    /** Prop each melee soldier carries in the right hand (Codex's held props: grip at the pivot, blade along +X). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Weapons")
    TSoftObjectPtr<UStaticMesh> MeleeWeapon;

    /** Prop each caster carries in the right hand: the wand its channel and flick gestures are made for. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Weapons")
    TSoftObjectPtr<UStaticMesh> CasterWeapon;

    /** Body socket the props go on. A body without it gets them on hand_r at WeaponGrip instead. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Weapons")
    FName WeaponSocket = TEXT("weapon_r");

    /** Grip on hand_r: palm centre, +X out of the fist on the thumb side (spell crafting's weapon_r numbers). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Weapons")
    FTransform WeaponGrip = FTransform(FRotator(73.2f, -142.3f, 0.0f), FVector(-3.8f, -0.1f, 0.1f));

    /** Shield on the left arm of Gilt melee soldiers (Codex's patrol shield: face along X, grip at the pivot). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Weapons")
    TSoftObjectPtr<UStaticMesh> ShieldMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Weapons")
    FName ShieldBone = TEXT("hand_l");

    /** Shield placement on ShieldBone. Identity = fitted on each soldier from its live hand pose: face out to the
     *  soldier's left, upright, grip at the pivot. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Weapons")
    FTransform ShieldGrip = FTransform::Identity;

    /** Spells the casters throw; caster N uses entry N (wrapping). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad")
    TArray<EHeroSpell> CasterSpells;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad")
    bool bSpawnOnBeginPlay = true;

    /** Spawn a fresh squad this long after the last soldier dies. 0 = never. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad", meta=(ClampMin="0", Units="s"))
    float RespawnDelay = 0.0f;

    /** Turns off eyelash/peach-fuzz grooms on soldiers; invisible at gameplay distance, saves GPU. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Performance")
    bool bStripFineGrooms = true;

    // ---- Formation -----------------------------------------------------------------------------------------

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Formation")
    EReflectionsSquadFormation Formation = EReflectionsSquadFormation::Column;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Formation", meta=(ClampMin="50", Units="cm/s"))
    float MarchSpeed = 150.0f;

    /** Distance between ranks. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Formation", meta=(ClampMin="60", Units="cm"))
    float RankSpacing = 170.0f;

    /** Distance between files (side by side). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Formation", meta=(ClampMin="60", Units="cm"))
    float FileSpacing = 125.0f;

    /** How fast the formation's heading turns at corners. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Formation", meta=(ClampMin="5", Units="deg"))
    float TurnRate = 45.0f;

    /** Soldiers catch up to their slot at up to this multiple of the march speed. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Formation", meta=(ClampMin="1"))
    float CatchUpFactor = 1.7f;

    // ---- Combat --------------------------------------------------------------------------------------------

    /** Seen in front of any soldier within this distance (with line of sight). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat", meta=(Units="cm"))
    float SightRadius = 2200.0f;

    /** Noticed in any direction within this distance. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat", meta=(Units="cm"))
    float AlertRadius = 700.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat", meta=(Units="deg"))
    float SightHalfAngle = 70.0f;

    /** In a fight, a soldier keeps the player in sight up to this distance (with a clear line). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat", meta=(Units="cm"))
    float LoseRadius = 6000.0f;

    /** The squad stands down and reforms once no soldier has seen the player for this long. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat", meta=(Units="s", ClampMin="1"))
    float LoseSightTime = 8.0f;

    /** When this squad goes into a fight, other squads with a soldier this close join it (the alarm). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat", meta=(Units="cm"))
    float AlarmRadius = 4000.0f;

    /** A crime the NPC system reports (the player hurting a civilian) this close to a soldier starts a fight. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat", meta=(Units="cm"))
    float CrimeAlarmRadius = 2500.0f;

    /** Melee soldiers run the player down themselves and hand over to the NPC melee motor inside this range. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat", meta=(Units="cm"))
    float MeleeHandOverRange = 650.0f;

    /** 0 = the NPC system's Soldier / SoldierCaster archetype (70 / 55). Set to give this squad its own value. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat", meta=(ClampMin="0"))
    float SoldierHealth = 0.0f;

    /** 0 = the Soldier archetype's melee damage. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat", meta=(ClampMin="0"))
    float MeleeDamage = 0.0f;

    /**
     * Take caster spells, damage scale, range band, cooldown, windup and cast clip from the NPC system's
     * SoldierCaster archetype at spawn (one place for the tuning). Off uses the values below.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat|Casting")
    bool bUseArchetypeCasterTuning = true;

    /** Battle orders from the squad (audio's SCue_VO_Soldier_Command_<voice>), on engaging and every few seconds. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat")
    bool bBarkOrders = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat", meta=(Units="s", EditCondition="bBarkOrders"))
    FVector2D BarkInterval = FVector2D(6.0f, 10.0f);

    /** Casters try to stay between these distances from the player. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat|Casting", meta=(Units="cm"))
    float CasterMinRange = 800.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat|Casting", meta=(Units="cm"))
    float CasterMaxRange = 1500.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat|Casting", meta=(Units="cm"))
    float CastRange = 2300.0f;

    /** Each caster waits a random time in this range between casts. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat|Casting", meta=(Units="s"))
    FVector2D CastCooldown = FVector2D(3.6f, 5.2f);

    /** Two casters never start a cast closer together than this, so volleys stay readable. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat|Casting", meta=(Units="s"))
    float SquadCastSpacing = 1.1f;

    /** Telegraph time: the spell visibly gathers in the caster's hand before it leaves. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat|Casting", meta=(Units="s"))
    float CastWindup = 0.75f;

    /** Scales catalog spell damage for enemy casters (player spells are tuned for NPC health pools). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat|Casting", meta=(ClampMin="0"))
    float CasterDamageScale = 0.5f;

    /** Fraction of the player's motion the casters lead; below 1 so sidestepping dodges. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Combat|Casting", meta=(ClampMin="0", ClampMax="1"))
    float AimLead = 0.45f;

    /**
     * Cast gestures played on the soldier body. Each caster uses the first clip whose skeleton matches its body
     * (MetaHuman looks come on more than one skeleton asset); none matching = cast without a gesture.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Animation")
    TArray<TSoftObjectPtr<UAnimSequence>> CastAnimations;

    /** Seconds into the cast clip (at play rate 1) where the hand is thrown forward. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Animation", meta=(Units="s"))
    float CastAnimationRelease = 0.87f;

    /**
     * Two-part cast gesture, preferred over CastAnimations when a release clip matches the caster's body: the channel
     * loop plays while the spell gathers (the telegraph), then the release clip plays so its strike lands as the spell
     * leaves. Matched to each body's skeleton like CastAnimations. The channel loop starts where its pose best matches
     * the release clip's first frame, so the cut between them barely shows. Clear ReleaseAnimations to use
     * CastAnimations only.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Animation")
    TArray<TSoftObjectPtr<UAnimSequence>> ChannelAnimations;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Animation")
    TArray<TSoftObjectPtr<UAnimSequence>> ReleaseAnimations;

    /**
     * The cast gesture as it plays by default (Squads.BodyClips 0): the same channel and flick made for the hidden
     * walker's skeleton, played as montages on the walker. The visible body's animation is never switched: a body
     * ragdolled in single-clip mode crashed the editor (16:16).
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Animation")
    TSoftObjectPtr<UAnimSequenceBase> WalkerChannelAnimation;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Animation")
    TSoftObjectPtr<UAnimSequenceBase> WalkerReleaseAnimation;

    /** Seconds into the release clip (at play rate 1) where the hand snaps forward: the spell leaves here. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Animation", meta=(Units="s"))
    float ReleaseAnimationStrike = 0.27f;

    /**
     * Optional in-place march loops for the body while in formation, matched to each body's skeleton like
     * CastAnimations. Empty (or no match) uses the NPC system's locomotion walk.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Animation")
    TArray<TSoftObjectPtr<UAnimSequence>> MarchAnimations;

    /** Boots-in-step loop that rides on the lead soldier while the squad marches (audio's SCue_March_Loop). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Audio")
    TSoftObjectPtr<USoundBase> MarchLoop;

    /** Played on a shield-carrying soldier that takes a blow (one of the two at random). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Audio")
    TArray<TSoftObjectPtr<USoundBase>> ShieldHitSounds;

    /** Ground speed the march loops were authored at; their play rate follows each soldier's real speed. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Squad|Animation", meta=(Units="cm/s"))
    float MarchAnimationSpeed = 155.0f;

    // ---- Runtime -------------------------------------------------------------------------------------------

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Squad|Runtime")
    EReflectionsSquadState State = EReflectionsSquadState::Inactive;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Squad|Runtime")
    TArray<FReflectionsSquadMember> Members;

    UPROPERTY(BlueprintAssignable, Category="Squad")
    FReflectionsSquadStateChanged OnSquadStateChanged;

    UFUNCTION(BlueprintCallable, Category="Squad")
    void SpawnSquad();

    UFUNCTION(BlueprintCallable, Category="Squad")
    void DespawnSquad();

    /** Break formation and fight Target (normally the player). */
    UFUNCTION(BlueprintCallable, Category="Squad")
    void Engage(AActor* Target);

    /** Stop fighting and march again from the nearest route point. */
    UFUNCTION(BlueprintCallable, Category="Squad")
    void Reform();

    /** Any living soldier within Radius of Location (2D). */
    bool HasMemberWithin(const FVector& Location, float Radius) const;

    UFUNCTION(BlueprintPure, Category="Squad")
    int32 GetAliveCount() const;

    /** Test helper: start a cast now on the first ready caster. Returns false if none can. */
    UFUNCTION(BlueprintCallable, Category="Squad")
    bool DebugForceCast();

    /** Test helper: kill every soldier through the normal damage path. */
    UFUNCTION(BlueprintCallable, Category="Squad")
    void DebugKillAll();

    FVector GetAnchorLocation() const { return AnchorLocation; }
    float GetAnchorYaw() const { return AnchorYaw; }

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void Tick(float DeltaSeconds) override;

private:
    struct FTrailPoint
    {
        FVector Location;
        float Distance;
    };

    void SetState(EReflectionsSquadState Next, AActor* Cause);
    void CacheRoute();
    void SeedTrail(const FVector& Head, float Yaw);
    void PushTrail(const FVector& Head);
    bool SampleTrail(float Behind, FVector& OutLocation, FVector& OutDirection) const;
    void BuildLeg(const FVector& From);
    void AdvanceAnchor(float DeltaSeconds, float Pace);
    FVector ComputeSlot(int32 SlotIndex, int32 SlotCount) const;
    void TickFormation(float DeltaSeconds, bool bReforming);
    void SteerTo(FReflectionsSquadMember& Member, const FVector& Goal, const FVector& FlowVelocity, float MaxSpeed, float DeltaSeconds);
    void FaceYaw(ACharacter* Driver, float Yaw, float DeltaSeconds);
    void TickAwareness(float DeltaSeconds);
    void TickCombat(float DeltaSeconds);
    void TickCaster(FReflectionsSquadMember& Member, AActor* Player, float DeltaSeconds);
    void StartCast(FReflectionsSquadMember& Member, AActor* Player);
    void ReleaseCast(FReflectionsSquadMember& Member, AActor* Player);
    void EndCast(FReflectionsSquadMember& Member, bool bRestoreAnimation);
    void UpdateMarchAnimation(FReflectionsSquadMember& Member, bool bMarching);
    void Bark(AActor* Speaker);
    /** Start, follow or fade the march loop with the squad's state. */
    void UpdateMarchSound();
    static bool HasShield(const AActor* Soldier);
    /** A shield that is not the squad's own: the look's, or the NPC system's (named or tagged "...Shield..."). */
    static bool HasOtherShield(const AActor* Soldier);
    /** A battle line (audio's Soldier_* groups) from Speaker; with bFallback the command cue when it has none. */
    void BarkEvent(AActor* Speaker, FName Group, bool bFallback = false);
    AActor* FirstActiveSoldier() const;
    void AttachWeapon(AActor* Soldier, bool bCaster);
    void AttachShield(AActor* Soldier);
    /** Once the soldier is animating: set the shield's grip (fitted from the live hand unless ShieldGrip is set). */
    /** True once placed (or nothing to place); false while the body is still in its reference pose. */
    bool PlaceShield(FReflectionsSquadMember& Member);
    class UStaticMeshComponent* AttachProp(AActor* Soldier, UStaticMesh* Mesh, FName Parent, const FTransform& Relative, FName Tag);
    /** A soldier of this squad was hit or killed by Attacker (spell caster, killer). */
    void OnMemberAttacked(AActor* Attacker);
    /** Nearest enemy any soldier sees: the other faction's soldiers, and for Gilt the tarnished (and a provoking player). */
    AActor* FindHostileInSight();
    /** Point the melee soldiers the NPC motor already fights with at a new target. */
    void RetargetMelee(AActor* Target);
    /** "Giltside" / "Frostside" / "Pewterside" from the spawner's streamed level (or the nearest placed squad's), else empty. */
    FString GetSide() const;
    /** Engage, and with bRaiseAlarm also bring in other squads within AlarmRadius (they don't pass it on). */
    void EngageInternal(AActor* Target, bool bRaiseAlarm);
    void HandleCrime(AActor* Offender, const FVector& Location);
    /** Next point toward Goal: the navmesh path's next corner when this squad paths on a navmesh, else Goal. */
    FVector NextPathPoint(const FVector& From, const FVector& Goal) const;
    static UAnimSequence* ClipFor(const TArray<TObjectPtr<UAnimSequence>>& Clips, const USkeletalMeshComponent* Body);
    /** Time in the channel loop whose pose is closest to the release clip's first frame (arms and upper spine). */
    static float MatchChannelEnd(const UAnimSequence* Channel, const UAnimSequence* Release);
    void RefreshMembers();
    bool HasLineOfSight(AActor* From, AActor* To) const;
    AActor* GetPlayer() const;
    FVector GroundAt(const FVector& Location, bool* bOutHit = nullptr) const;
    void DrawDebug() const;

    UFUNCTION()
    void HandleSpellEvent(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity);

public:
    // Bound by the NPC bridge to the NPC system's events (public so the bridge can bind them).
    UFUNCTION()
    void HandleNpcSpellHit(AActor* Npc, const FReflectionsSpellHitData& Hit);
    UFUNCTION()
    void HandleNpcDied(AActor* Npc, AActor* Killer);
    UFUNCTION()
    void HandlePlayerCrime(AActor* Victim, FName Crime, AActor* Witness, FVector Location, float Heat);

    /** This squad would fight Actor (the player for Frost or once provoked; the other faction; the tarnished for Gilt). */
    bool IsHostileTarget(const AActor* Actor) const;
    bool IsMember(const AActor* Actor) const;

private:

    UPROPERTY(VisibleAnywhere, Category="Squad")
    TObjectPtr<USceneComponent> SceneRoot;

#if WITH_EDITORONLY_DATA
    UPROPERTY()
    TObjectPtr<UBillboardComponent> Sprite;
#endif

    UPROPERTY(Transient) TArray<TObjectPtr<UAnimSequence>> LoadedCastAnimations;
    UPROPERTY(Transient) TArray<TObjectPtr<UAnimSequence>> LoadedMarchAnimations;
    UPROPERTY(Transient) TArray<TObjectPtr<UAnimSequence>> LoadedChannelAnimations;
    UPROPERTY(Transient) TArray<TObjectPtr<UAnimSequence>> LoadedReleaseAnimations;
    UPROPERTY(Transient) TObjectPtr<UAnimSequenceBase> LoadedWalkerChannel;
    UPROPERTY(Transient) TObjectPtr<UAnimSequenceBase> LoadedWalkerRelease;
    /** Per channel clip (kept alive by LoadedChannelAnimations): loop time to be at when the release clip starts. */
    TMap<const UAnimSequence*, float> ChannelEnds;
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> TelegraphSystem;
    TWeakObjectPtr<AActor> Foe;

    TArray<FVector> Waypoints;
    TArray<FVector> LegPoints;
    TArray<FTrailPoint> Trail;
    int32 WaypointIndex = 0;
    int32 WaypointStep = 1;
    int32 LegIndex = 0;
    FVector AnchorLocation = FVector::ZeroVector;
    FVector AnchorVelocity = FVector::ZeroVector;
    float AnchorYaw = 0.0f;
    float TrailHead = 0.0f;
    float HaltRemaining = 0.0f;
    float AwarenessTimer = 0.0f;
    float LostTimer = 0.0f;
    float ReformTimer = 0.0f;
    /** After standing down, ignore the NPCs' own lingering aggression for a while. */
    float AggravationGrace = 0.0f;
    float BarkTimer = 0.0f;
    bool bWarnedCastClip = false;
    float SightCheckTimer = 0.0f;
    UPROPERTY(Transient) TObjectPtr<class UAudioComponent> MarchAudio;
    TWeakObjectPtr<AActor> MarchAudioCarrier;
    /** Gilt: the player attacked us or a civilian near us; hostile to the player until the squad stands down. */
    bool bProvokedByPlayer = false;
    bool bFoeInSight = true;
    FDelegateHandle CrimeHandle;
    float RespawnTimer = 0.0f;
    float LastSquadCast = -100.0f;
    float Pace = 1.0f;
    int32 SquadSeed = 0;
    bool bUseNavigation = false;
};
