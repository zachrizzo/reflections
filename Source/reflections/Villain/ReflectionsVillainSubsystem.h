#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Subsystems/WorldSubsystem.h"
#include "Worlds/ReflectionsWorldTypes.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "Villain/ReflectionsVillainPossession.h"
#include "ReflectionsVillainSubsystem.generated.h"

class AReflectionsVillainBoss;
class AReflectionsVillainConversion;
class AReflectionsVillainWisp;
class ACharacter;
class APawn;
class UBillboardComponent;
class UReflectionsVillainHudWidget;
class USphereComponent;
struct FReflectionsSpellHitData;
struct FReflectionsCheckpoint;

/**
 * Where his true form manifests: place one at the top of the White side's (Frostside's) tower. Without one he uses the
 * White book page's position (cached when the map starts), then the White world anchor.
 */
UCLASS(Blueprintable, meta = (DisplayName = "Reflections Villain Arena"))
class REFLECTIONS_API AReflectionsVillainArena : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsVillainArena();

    /** Radius of the fight area (attacks stay inside it; leave room to dodge). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Villain", meta = (Units = "cm"))
    float ArenaRadius = 1400.0f;

#if WITH_EDITORONLY_DATA
    UPROPERTY() TObjectPtr<UBillboardComponent> Sprite;
#endif

    UPROPERTY(VisibleAnywhere, Category = "Villain")
    TObjectPtr<USphereComponent> Area;

    virtual void OnConstruction(const FTransform& Transform) override;
};

/**
 * The villain (the Tarnish, in all player-facing text) for one map: picks hosts, hops between them, spreads infection, reports the count to
 * game flow (UReflectionsGameFlowSubsystem, called by name), and when world jump fires OnBookComplete,
 * gives the hero the Final Spell and raises his true form in White's tower.
 *
 * Console (non-Shipping): Villain.Start, Villain.Stop, Villain.Hop, Villain.Status, Villain.SpawnTestHosts [N],
 * Villain.Finale (as if the book were complete), Villain.BossHere, Villain.DamageBoss [N], Villain.CleanseAll.
 */
UCLASS()
class REFLECTIONS_API UReflectionsVillainSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsVillainSubsystem* Get(const UObject* WorldContext);

    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;

    // ---- Control ------------------------------------------------------------------------------------------
    /** Lets him take hosts (normally automatic). */
    UFUNCTION(BlueprintCallable, Category = "Villain")
    void StartPossession();
    UFUNCTION(BlueprintCallable, Category = "Villain")
    void StopPossession();
    /** Forces an immediate hop out of the current host. */
    UFUNCTION(BlueprintCallable, Category = "Villain")
    void ForceHop();
    /** What OnBookComplete triggers; callable directly for tests. */
    UFUNCTION(BlueprintCallable, Category = "Villain")
    void BeginFinale();
    /** Spawns his true form in front of the player (test). */
    AReflectionsVillainBoss* SpawnBossNearPlayer();
    void SpawnTestHosts(int32 Count);
    void CleanseAll();
    FString DescribeStatus() const;

    UFUNCTION(BlueprintPure, Category = "Villain")
    bool IsFinale() const { return bFinale; }
    UFUNCTION(BlueprintPure, Category = "Villain")
    bool IsPossessionRunning() const { return bRunning; }
    UFUNCTION(BlueprintPure, Category = "Villain")
    AActor* GetHost() const { return Host.Get(); }
    UFUNCTION(BlueprintPure, Category = "Villain")
    int32 GetInfectedCount() const;
    AReflectionsVillainBoss* GetBoss() const { return Boss.Get(); }

    // ---- Conversion (the NPC system calls this when a tarnished NPC reaches a clean one) -------------------
    /**
     * Tackle, black wisp, turn. Returns the sequence length in seconds (suspend both NPCs that long; the victim
     * is SetInfection(Infected) at the end), or 0 if refused: busy, the player, already tarnished, too far, or
     * no driver mesh / tackle clips. Safe to call by name.
     */
    UFUNCTION(BlueprintCallable, Category = "Villain")
    float BeginConversion(AActor* Attacker, AActor* Victim);

    /**
     * For scripted beats (cutscenes): BeginConversion without the pacing gap, after bringing the attacker's walker to
     * arm's length of the victim's, and holding both NPCs for the length of the sequence. Same return. Safe by name.
     */
    UFUNCTION(BlueprintCallable, Category = "Villain")
    float BeginConversionScripted(AActor* Attacker, AActor* Victim);

    /** True while the actor is in a conversion (either side). */
    UFUNCTION(BlueprintPure, Category = "Villain")
    bool IsConverting(const AActor* Actor) const;

    /** Test: the nearest tarnished NPC (or a fresh one) converts the nearest clean NPC to the player. */
    float ConvertNearest();
    void ConversionFinished(AReflectionsVillainConversion* Conversion, bool bConverted);

    // ---- Called by possession, wisps and the boss ---------------------------------------------------------
    void NotifyStateChanged(UReflectionsVillainPossessionComponent* Component, EReflectionsVillainInfection Old, EReflectionsVillainInfection New);
    void SpreadFrom(AActor* FromHost);
    void HostExpired(UReflectionsVillainPossessionComponent* Component);
    void WispFinished(AReflectionsVillainWisp* Wisp, bool bSuccess);
    void NotifyRift(AActor* Actor, EReflectionsWorld From, EReflectionsWorld To);
    void NotifyBossDefeated(AReflectionsVillainBoss* DefeatedBoss);

    /** Short line under the boss bar / top of the screen. */
    void ShowMessage(const FText& Text, const FLinearColor& Color);
    UReflectionsVillainHudWidget* GetOrCreateHud();

    /** Where his true form waits (ground point) and the arena radius. */
    UFUNCTION(BlueprintPure, Category = "Villain")
    bool GetArena(FVector& OutCenter, float& OutRadius) const;

    /** Player-facing name of a side (from the world-jump config: Pewterside, Giltside, Frostside). */
    static FText SideName(const UObject* WorldContext, EReflectionsWorld World);
    /** The finale side's name for player text, or empty on a one-side map (no world jump): the lines then name no side. */
    static FText ArenaSideName(const UObject* WorldContext);

    /** The finale's announcement has been shown (after any mirror-whole cutscene): the true form may rise. */
    bool CanManifest() const;
    /** Host spread interval: faster once the first mirror page is found (story MQ05). */
    float InfectIntervalNow() const;
    /** A cutscene from the cutscene subsystem is playing (by name; false if there is none). */
    bool IsCutscenePlaying() const;

    /** True if the pawn may become a host or be infected. */
    static bool IsCandidate(const AActor* Actor, bool bAllowInfected);
    /** Why Actor cannot be taken (nullptr: it can). bIgnoreOptOut: a scripted beat may take a NoVillain person. */
    static const TCHAR* CandidateProblem(const AActor* Actor, bool bAllowInfected, bool bIgnoreOptOut);

protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
    void Think();
    void TrySeed();
    void HopFrom(AActor* OldHost, const FVector& From);
    /** The character whose mesh animates this NPC: its hidden locomotion pawn, or itself if it is a Character. */
    ACharacter* DriverOf(AActor* Npc) const;
    /** Every actor that can be possessed: the NPC system's NPCs plus plain NPC pawns (test hosts). */
    TArray<AActor*> NpcActors() const;
    AActor* PickCandidate(const FVector& Around, float Radius, const AActor* Exclude, bool bPreferInfected, float MinDistance = 0.0f) const;
    void LaunchWisp(const FVector& From, AActor* Target, EReflectionsVillainInfection State, bool bHop);
    void CacheArena();
    /** Streamed maps (the mock city) load their world anchors and the arena marker after BeginPlay: look again. */
    void RecheckMap();
    /** Gameplay is live: no title/pause menu, no cutscene, not game over. Possession waits for this (after the intro). */
    bool IsRunLive() const;
    /** This is the map New Game opens (game flow's NewGameMap): a gameplay map even without world anchors. */
    bool IsNewGameMap() const;
    /** Asks the NPC system to hold Actor still for Seconds (HoldNpc, by name). */
    void HoldNpcFor(AActor* Actor, float Seconds) const;
    void EnsureFinalSpell();
    void SpawnBossAtArena();

    UFUNCTION() void HandleBookComplete();
    UFUNCTION() void HandleProgressRestored();
    /** BeginFinale with or without the banner and sound (quiet for a loaded checkpoint). Safe to call twice. */
    void StartFinale(bool bAnnounce);
    UFUNCTION() void HandleSpellHit(const FReflectionsSpellHitData& Hit);
    UFUNCTION() void HandleNpcSpellHit(AActor* Npc, const FReflectionsSpellHitData& Hit);
    UFUNCTION() void HandleNpcInfection(AActor* Npc, EReflectionsNpcInfection State, AActor* Source);
    /** A tarnished body died (soldiers fight them on sight): clear its look and his count. The meter itself is the NPC system's. */
    UFUNCTION() void HandleNpcDied(AActor* Npc, AActor* Killer);
    /** Game flow save slots: who is tarnished, who hosts him and for how long, his tallies (key "Villain"). */
    UFUNCTION() void HandleCheckpointSaved(const FReflectionsCheckpoint& Checkpoint);
    UFUNCTION() void HandleCheckpointRestored(const FReflectionsCheckpoint& Checkpoint);
    /** A save-stable id: the Lives person ("P:<id>"), else a level-placed actor ("A:<level>.<name>"); empty if neither. */
    static FString StableId(const AActor* Actor);
    void TryRestoreSaved();
    UFUNCTION() void HandleCutsceneFinished(FName Cutscene, bool bSkipped);
    UFUNCTION() void HandlePagesChanged(int32 Pages, int32 PagesForBook);
    UFUNCTION() void HandleGameLost();
    void AnnounceFinale();
    void ShowVictoryNow();
    UObject* Cutscenes() const;
    bool CallBool(UObject* Target, FName Function, FName NameArg = NAME_None) const;
    float CallFloat(UObject* Target, FName Function) const;
    void BindByName(UObject* Target, FName Delegate, FName Handler);

    // Game flow (by name, no compile dependency): ReportInfected / ReportCured / ShowVictory.
    UObject* GameFlow() const;
    void CallGameFlow(FName Function, AActor* Arg) const;

    UPROPERTY(Transient) TObjectPtr<UReflectionsVillainHudWidget> Hud;

    TWeakObjectPtr<AActor> Host;
    TWeakObjectPtr<AReflectionsVillainWisp> PendingHop;
    TWeakObjectPtr<AReflectionsVillainBoss> Boss;
    TSet<TWeakObjectPtr<AActor>> Infected;
    TArray<TWeakObjectPtr<AReflectionsVillainConversion>> Conversions;
    FTimerHandle ThinkTimer;
    FVector LastHostLocation = FVector::ZeroVector;
    FVector ArenaCenter = FVector::ZeroVector;
    float ArenaRadius = 1400.0f;
    double NextSeedTime = 0.0;
    int32 PendingSpreads = 0;
    int32 TotalHosts = 0;
    int32 TotalInfections = 0;
    bool bHasArena = false;
    bool bArenaFromMarker = false;
    bool bMapEnabled = false;
    /** The StartDelay countdown to the first host starts when the run first goes live, not at map load. */
    bool bSeedClockStarted = false;
    double NextMapCheck = 0.0;
    double MapCheckUntil = 0.0;
    /** Tackle pacing: no new conversion before this time (Villain.ConvertInterval). */
    double NextConversionTime = 0.0;
    int32 ConversionsStarted = 0;
    /** Villain.Convert (tests) ignores the pacing gap. */
    bool bIgnoreConvertGap = false;
    /** BeginConversionScripted is running: the victim may carry the NoVillain opt-out (story beats turn named people). */
    bool bScriptedConversion = false;
    /** Saved tarnished still to find after a load (people are assigned to bodies a moment after the map starts). */
    TArray<FString> PendingInfectedIds;
    FString PendingHostId;
    float PendingHostLeft = 0.0f;
    double RestoreUntil = 0.0;
    bool bRestoring = false;
    bool bBoundSaves = false;
    bool bRunning = false;
    bool bFinale = false;
    bool bVictory = false;
    bool bBoundBook = false;
    bool bFinaleAnnounced = false;
    bool bAwaitMirrorCutscene = false;
    bool bMirrorCutscenePlayed = false;
    bool bAwaitEnding = false;
    int32 PagesFound = 0;
    int32 BandReached = 0;
};
