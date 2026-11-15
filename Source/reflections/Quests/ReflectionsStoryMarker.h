#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Subsystems/WorldSubsystem.h"
#include "Worlds/ReflectionsWorldTypes.h"
#include "ReflectionsStoryMarker.generated.h"

class UArrowComponent;
class UBillboardComponent;
class UTextRenderComponent;
class AReflectionsStoryMarker;

/** Which side of Lanthorne a marker belongs to. Auto: from the world-jump anchor box it stands in. */
UENUM(BlueprintType)
enum class EReflectionsMarkerSide : uint8
{
    Auto,
    Pewterside,
    Giltside,
    Frostside,
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FReflectionsStoryMarkerPlaced, FName, Name, AReflectionsStoryMarker*, Marker, bool, bAutoPlaced);

/**
 * The one marker actor for story placement. The map designer drops these into the real map; quests, NPC daily lives
 * and cutscenes look them up by name, so no system ever needs to edit the map.
 *
 * Names (set MarkerName, or add the name as an actor Tag; one marker may carry several names):
 *   Home_<PersonId>        where a person lives (front door / bed area)          Home_GiltMaren
 *   Work_<Job>             a workplace (a stall, the exchange, a guard post)     Work_CoinExchange
 *   Haunt_<Place>          somewhere people hang out (tavern, square, bridge)    Haunt_LampSquare
 *   QuestGiver_<PersonId>  where a quest giver stands when waiting for the hero  QuestGiver_GiltMaren
 *   CutsceneAnchor_<Name>  origin and facing of a cutscene                        CutsceneAnchor_Intro
 *   Tower_<Side>           foot of a side's tower (Pewterside|Giltside|Frostside) Tower_Giltside
 *   Spot_<Name>            any quest location (go to, protect, a spell target)   Spot_OldWell
 *   Item_<ItemId>          where a quest item lies                               Item_LostLedger
 *   Mk_<Pew|Gilt|Frost>_<Kind>_<Name>  the story bible's places (people.json markers) Mk_Gilt_Square_BellSquare
 *
 * Any actor tagged with one of these names works too (a Target Point is fine): the subsystem adopts it.
 *
 * The actor's rotation is the facing (people at QuestGiver_ face along the arrow; cutscenes use it as the camera
 * rig's forward). Radius is the area the name covers (go-to and protect zones, home wander radius).
 *
 * Lookups go through UReflectionsStoryMarkerSubsystem. When a name is missing (test maps, a map still being built),
 * the subsystem places a marker itself on a nav-reachable point near the matching side, so everything runs before
 * the real map lands. Those are flagged bAutoPlaced and logged.
 */
UCLASS(Blueprintable, meta = (DisplayName = "Reflections Story Marker"))
class REFLECTIONS_API AReflectionsStoryMarker : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsStoryMarker();

    /** Main name, e.g. Home_GiltMaren. Extra names can be added as actor Tags. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Story Marker")
    FName MarkerName;

    /** Side of the city. Auto reads the world-jump anchor box the marker stands in. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Story Marker")
    EReflectionsMarkerSide Side = EReflectionsMarkerSide::Auto;

    /** Size of the area this name stands for (go-to and protect zones, wander radius). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Story Marker", meta = (Units = "cm", ClampMin = "50"))
    float Radius = 300.0f;

    /** Free text for the map designer and tools (not shown to players). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Story Marker", meta = (MultiLine = "true"))
    FString Notes;

    /** True for markers the subsystem placed because the map had none of that name. */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Story Marker")
    bool bAutoPlaced = false;

    /** Every name this marker answers to (MarkerName first, then matching tags). */
    UFUNCTION(BlueprintPure, Category = "Story Marker")
    TArray<FName> GetNames() const;

    UFUNCTION(BlueprintPure, Category = "Story Marker")
    bool HasName(FName Name) const;

    /** The side the marker is in (Auto resolved through the world-jump anchors; Giltside if there are none). */
    UFUNCTION(BlueprintPure, Category = "Story Marker")
    EReflectionsWorld GetResolvedSide() const;

    /** Splits "Home_GiltMaren" into kind "Home" and key "GiltMaren". */
    static bool SplitName(FName Name, FString& OutKind, FString& OutKey);

    /** Known kind prefixes (Home, Work, Haunt, QuestGiver, CutsceneAnchor, Tower, Spot, Item). */
    static bool IsStoryName(FName Name);

    virtual void OnConstruction(const FTransform& Transform) override;
#if WITH_EDITOR
    virtual void PostEditChangeProperty(FPropertyChangedEvent& Event) override;
#endif

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    void RefreshLabel();

    UPROPERTY(VisibleAnywhere, Category = "Story Marker")
    TObjectPtr<USceneComponent> Root;

    UPROPERTY(VisibleAnywhere, Category = "Story Marker")
    TObjectPtr<UArrowComponent> Facing;

#if WITH_EDITORONLY_DATA
    UPROPERTY()
    TObjectPtr<UTextRenderComponent> Label;

    UPROPERTY()
    TObjectPtr<UBillboardComponent> Sprite;
#endif
};

/**
 * Finds story markers by name, and places missing ones (see AReflectionsStoryMarker). Any system can use it:
 *
 *   #include "Quests/ReflectionsStoryMarker.h"
 *   if (AReflectionsStoryMarker* Home = UReflectionsStoryMarkerSubsystem::FindMarker(this, TEXT("Home_GiltMaren")))
 *       MoveTo(Home->GetActorLocation());
 *
 * Console: Story.Markers (list), Story.ShowMarkers 0|1 (debug draw), Story.MarkerFallback 0|1 (auto-place missing).
 */
UCLASS()
class REFLECTIONS_API UReflectionsStoryMarkerSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    static UReflectionsStoryMarkerSubsystem* Get(const UObject* WorldContext);

    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    /** One-liner: the marker with this name, placing a fallback when the map has none (and fallback is on). */
    UFUNCTION(BlueprintCallable, Category = "Story Marker", meta = (WorldContext = "WorldContext"))
    static AReflectionsStoryMarker* FindMarker(const UObject* WorldContext, FName Name, bool bAllowFallback = true);

    /** The marker's location and facing. False if there is no such marker and none could be placed. */
    UFUNCTION(BlueprintCallable, Category = "Story Marker", meta = (WorldContext = "WorldContext"))
    static bool GetMarkerTransform(const UObject* WorldContext, FName Name, FTransform& OutTransform, bool bAllowFallback = true);

    /** Looks up a marker; places one if missing and allowed. */
    UFUNCTION(BlueprintCallable, Category = "Story Marker")
    AReflectionsStoryMarker* Find(FName Name, bool bAllowFallback = true);

    /** Every marker of a kind ("Home", "Work", "Haunt"...), hand-placed and auto-placed. */
    UFUNCTION(BlueprintCallable, Category = "Story Marker")
    TArray<AReflectionsStoryMarker*> FindByKind(const FString& Kind) const;

    /** Every marker in the map. */
    UFUNCTION(BlueprintCallable, Category = "Story Marker")
    TArray<AReflectionsStoryMarker*> GetAllMarkers() const;

    /** Names that had to be auto-placed in this map (what the map designer still needs to drop). */
    UFUNCTION(BlueprintPure, Category = "Story Marker")
    TArray<FName> GetAutoPlacedNames() const;

    /**
     * Side hint for a fallback, for names whose key does not say the side (Home_<PersonId> etc.). The quest system
     * fills this from the people book; others may add their own.
     */
    void SetSideHint(FName Name, EReflectionsWorld Side) { SideHints.Add(Name, Side); }

    /** Another name the map may use for a story name (people.json markers.story_names: Spot_BellSquare <- Mk_Gilt_Square_BellSquare). */
    void SetAlias(FName StoryName, FName MapName) { Aliases.Add(StoryName, MapName); }

    /** Fires when a marker registers (hand-placed at begin play, or auto-placed). */
    UPROPERTY(BlueprintAssignable, Category = "Story Marker")
    FReflectionsStoryMarkerPlaced OnMarkerPlaced;

    void Register(AReflectionsStoryMarker* Marker);
    void Unregister(AReflectionsStoryMarker* Marker);

    /** Text for Story.Markers. */
    FString Describe() const;

protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
    AReflectionsStoryMarker* PlaceFallback(FName Name);
    /** A marker named Name at another actor (a tagged actor, or a stand-in place of the same kind). */
    AReflectionsStoryMarker* Adopt(FName Name, AActor* Source, bool bStandIn);
    bool FindFallbackPoint(FName Name, const FString& Kind, const FString& Key, EReflectionsWorld Side, FVector& OutPoint, FVector& OutFaceToward) const;
    bool SideFromKey(const FString& Key, EReflectionsWorld& Out) const;
    FVector OriginForSide(EReflectionsWorld Side) const;

    TArray<TWeakObjectPtr<AReflectionsStoryMarker>> Markers;
    TMap<FName, EReflectionsWorld> SideHints;
    TMap<FName, FName> Aliases;
    TSet<FName> FailedFallbacks;
    FDelegateHandle DrawHandle;
};
