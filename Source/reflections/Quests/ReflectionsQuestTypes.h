#pragma once

#include "CoreMinimal.h"
#include "Worlds/ReflectionsWorldTypes.h"
#include "ReflectionsQuestTypes.generated.h"

class UStaticMesh;

/** What an objective asks of the hero. */
UENUM(BlueprintType)
enum class EReflectionsObjectiveType : uint8
{
    /** Speak with a person (Target = people-book id). */
    TalkTo,
    /** Reach a story marker (Target = marker name, Radius). */
    GoTo,
    /** Pick up quest items (Target = item id, Count). Items spawn at Item_<ItemId> markers. */
    Collect,
    /** Bring an item to a person (Item = item id, Target = person id). */
    Deliver,
    /** Defeat Count of a kind (Target = archetype id, NPC tag, or Any / Infected / Hostile). */
    Defeat,
    /** Hit a target with a spell (Spell = spell or element; Target = person, marker or tag; Count hits). */
    SpellHit,
    /** Step through to a side (Side; Any for any jump). */
    WorldJump,
    /** Hold a spot: stay within Radius of the Target marker for Seconds (optional enemy waves). */
    Protect,
    /** A game event, counted Count times (Target = event key, Spell = argument filter). See README. */
    Event,
};

/** Where a quest sits for the hero. */
UENUM(BlueprintType)
enum class EReflectionsQuestStatus : uint8
{
    /** Not met yet (or requirements not met). */
    Unavailable,
    /** The giver can offer it. */
    Available,
    /** In progress. */
    Active,
    /** Every step done; return to the giver to turn it in. */
    ReadyToTurnIn,
    Completed,
    Failed,
};

/** Side filter for data (Any = no filter). Values 1..3 match EReflectionsWorld + 1. */
UENUM(BlueprintType)
enum class EReflectionsQuestSide : uint8
{
    Any,
    Pewterside,
    Giltside,
    Frostside,
    /** Where the hero is when the reward is given. */
    Current,
};

/** What a quest event is (OnQuestEvent). */
UENUM(BlueprintType)
enum class EReflectionsQuestEventType : uint8
{
    Offered,
    Accepted,
    Declined,
    StepStarted,
    ObjectiveProgress,
    ObjectiveComplete,
    StepComplete,
    ReadyToTurnIn,
    Completed,
    Failed,
    ChoiceMade,
    Tracked,
};

/** One scripted line: who says it, the text, and its id (voice cue /Game/Audio/Jam/Voice/Cues/SCue_VO_<Id>). */
USTRUCT(BlueprintType)
struct FReflectionsQuestLineDef
{
    GENERATED_BODY()

    /** Line id from the story bible (MQ01_03, SQ9_02). Its cue plays if it exists. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Id;
    /** People-book id (also wren_hale, the_tarnish, narrator). Empty: the step's or quest's default speaker. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Speaker;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest", meta = (MultiLine = "true")) FText Text;
    /** Seconds to wait before this line (counted from the previous one). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest", meta = (Units = "s")) float Delay = 0.0f;
};

/** Lines a person says while a step is active, when the hero talks to them (optional colour, MQ04's townsfolk). */
USTRUCT(BlueprintType)
struct FReflectionsQuestTalk
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Person;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> Lines;
};

USTRUCT(BlueprintType)
struct FReflectionsReputationGrant
{
    GENERATED_BODY()

    /** People-book id. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Person;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") float Amount = 10.0f;
};

USTRUCT(BlueprintType)
struct FReflectionsQuestReward
{
    GENERATED_BODY()

    /** Mirror shards (world-jump coins). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") int32 Coins = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") EReflectionsQuestSide CoinSide = EReflectionsQuestSide::Current;
    /** Refills this much mana at once (capped at the bar). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") float Mana = 0.0f;
    /** Standing with people; the town's overall reputation moves by half of the total. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsReputationGrant> Reputation;
    /** Flags other systems can read with UReflectionsQuestSubsystem::HasUnlock (spells, doors, dialogue). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FName> Unlocks;
    /** Quest items handed to the hero. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FName> Items;

    bool IsEmpty() const { return Coins <= 0 && Mana <= 0.0f && Reputation.IsEmpty() && Unlocks.IsEmpty() && Items.IsEmpty(); }
};

USTRUCT(BlueprintType)
struct FReflectionsQuestObjective
{
    GENERATED_BODY()

    /** Unique inside the step. Empty: o1, o2... */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Id;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") EReflectionsObjectiveType Type = EReflectionsObjectiveType::TalkTo;
    /** Tracker line ("Find Maren's ledger"). {count}/{total} are filled in. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FText Text;
    /** Person id, marker name, item id, archetype/tag or event key (see EReflectionsObjectiveType). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Target;
    /** Deliver: the item. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Item;
    /** SpellHit: spell (Fire, IceShard...) or element (Fire, Ice, Water, Lightning, Earth, Air, Arcane, Life). Event: argument filter. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Spell;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest", meta = (ClampMin = "1")) int32 Count = 1;
    /** GoTo / Protect zone and SpellHit marker radius; 0 = the marker's own radius. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest", meta = (Units = "cm")) float Radius = 0.0f;
    /** Protect: seconds to hold. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest", meta = (Units = "s")) float Seconds = 0.0f;
    /** WorldJump: destination side. Others: only counts on this side. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") EReflectionsQuestSide Side = EReflectionsQuestSide::Any;
    /** Defeat / Protect: NPC archetype to spawn when the objective starts (Soldier, Infected...). None: spawn nothing. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName SpawnArchetype;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") int32 SpawnCount = 0;
    /** Where spawns appear and where the pointer goes (marker name). Empty: worked out from the type. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Marker;
    /** Not needed to finish the step. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") bool bOptional = false;
    /** Not shown in the tracker or journal (a branch the player should not see, a trigger zone). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") bool bHidden = false;
    /** Hints, most vague first (give_hint walks through them). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FText> Hints;
    /** Said when this objective completes ("talk to" objectives: what the person says when spoken to). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> CompleteLines;
    /** Said as progress grows: entry i plays when progress first reaches i + 1 (not on the final count). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> ProgressLines;
    /** Quest items handed over when this objective completes. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FName> GiveItems;
    /** Where spawns appear when not at Marker (SQ6: hunters come from the rift, the zone is the camp). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName SpawnMarker;
};

USTRUCT(BlueprintType)
struct FReflectionsQuestChoice
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Id;
    /** Button text ("Tell the guard"). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FText Text;
    /** Line the person answers with. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FText Response;
    /** Line id of the response (voice cue). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName ResponseId;
    /** Step to go to. None: the next step. "End": finish the quest. "Fail": fail it. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName NextStep;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FReflectionsQuestReward Reward;
    /** Journal line recorded for this choice. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FText Journal;
};

USTRUCT(BlueprintType)
struct FReflectionsQuestStep
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Id;
    /** Journal heading for this part. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FText Title;
    /** Journal paragraph, written in the hero's notebook voice. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest", meta = (MultiLine = "true")) FText Description;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestObjective> Objectives;
    /** Done when any required objective is done (default: all). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") bool bAnyObjective = false;
    /** A choice: shown when the hero talks to ChoicePerson (or at once when ChoicePerson is empty). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestChoice> Choices;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName ChoicePerson;
    /** Lines spoken when the step starts (subtitles with voice; in the talk card when it is open). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> Lines;
    /** Default speaker for lines without one (else the quest's giver). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Speaker;
    /** Lines spoken when the step completes. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> CompleteLines;
    /** Optional lines per person while this step is active, used when the hero talks to them. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestTalk> Talk;
    /**
     * Cutscene to play when the step starts (cutscene system's PlayCutscene). A step with a cutscene and no objectives
     * waits for it to end (CutsceneDone); if it cannot play (missing, already seen) the step goes on at once.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Cutscene;
    /** Finishes the step this many seconds after it starts, whatever is left (0: never). Cutscenes hold the clock. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest", meta = (Units = "s")) float TimeoutSeconds = 0.0f;
    /** Cutscene to play when the step completes (the next step starts meanwhile). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName CutsceneOnComplete;
    /** Objectives must be done in order (each one counts only once those before it are done). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") bool bOrdered = false;
    /** Quest items handed over when the step starts (the letter to deliver). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FName> GiveItems;
    /** Step after this one. None: the next in the list. "End" finishes the quest. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName NextStep;
    /** Given when the step completes. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FReflectionsQuestReward Reward;
    /** Optional cue on start: /Game/Audio/Jam/Voice/Cues/Quest/SCue_VO_Quest_<QuestId>_<StepId> plays if it exists. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") bool bPlayVoiceCue = true;
};

USTRUCT(BlueprintType)
struct FReflectionsQuestDef
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Id;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FText Title;
    /** One or two lines for the journal header and the offer card. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest", meta = (MultiLine = "true")) FText Summary;
    /** The main story (always listed first, starts by itself, cannot be declined). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") bool bMain = false;
    /** Person who offers it and takes it back (people-book id). Empty: starts by itself. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Giver;
    /** Side the quest belongs to (journal grouping, giver fallback placement). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") EReflectionsQuestSide Side = EReflectionsQuestSide::Any;
    /** Start without a giver as soon as requirements are met. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") bool bAutoStart = false;
    /** Quests that must be completed first. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FName> RequiresQuests;
    /** Unlock flags that must be set first ("MainStep:Pages" style flags are set by the main quest). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FName> RequiresUnlocks;
    /** Return to the giver when the steps are done (else it completes on the last step). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") bool bTurnIn = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> OfferLines;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> AcceptLines;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> DeclineLines;
    /** Said by the giver while the quest is under way. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> ReminderLines;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> TurnInLines;
    /** Said once each, the first time the hero talks to or comes within 3 m of the line's speaker after the quest is done. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> AfterLines;
    /** Said once when the quest fails. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestLineDef> FailLines;
    /** Fails the quest if this person dies while it is under way (people-book id). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName FailIfDies;
    /** People turned tarnished when the quest is accepted (spawned at their marker if missing), kept from the Tarnish's hops. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FName> StartsTarnished;
    /** Given on turn-in (or on the last step for bTurnIn = false). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FReflectionsQuestReward Reward;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FReflectionsQuestStep> Steps;
    /** Journal order inside its group (lower first). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") int32 SortOrder = 100;
    /** Test content (hidden unless Quest.ShowTestQuests 1). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") bool bTest = false;

    const FReflectionsQuestStep* FindStep(FName StepId, int32* OutIndex = nullptr) const;
};

/** A quest item's name for the HUD and the journal. */
USTRUCT(BlueprintType)
struct FReflectionsQuestItemDef
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Id;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FText Name;
    /** What the item looks like lying in the world. Empty: the glowing pickup shape. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TSoftObjectPtr<UStaticMesh> Mesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest", meta = (ClampMin = "0.01")) float MeshScale = 1.0f;
};

/** One person from the story bible's people book, as far as quests need them. */
USTRUCT(BlueprintType)
struct FReflectionsQuestPerson
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Id;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FText DisplayName;
    /** Short role line under the name ("Coin clerk, Giltside Exchange"). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FText Title;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") EReflectionsQuestSide Side = EReflectionsQuestSide::Giltside;
    /** NPC archetype when the quest system has to spawn them (Civilian, Guard...). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Archetype = TEXT("Civilian");
    /** Optional look Blueprint (soft class path) when spawning; empty lets the NPC system pick by sex. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FSoftClassPath Look;
    /** "F" or "M" (only used to pick a look when spawning). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName Sex;
    /** Said when the hero talks to them with nothing quest-related to say. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") TArray<FText> IdleLines;
    /** Story marker where they are spawned if the map has nobody tagged Person_<Id> (people.json markers.work). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Quest") FName SpawnMarker;
};

// ---- Runtime state ---------------------------------------------------------------------------------------------

USTRUCT(BlueprintType)
struct FReflectionsObjectiveState
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Quest") FName Id;
    UPROPERTY(BlueprintReadOnly, Category = "Quest") int32 Progress = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Quest") bool bDone = false;
    /** Protect: seconds held so far. */
    UPROPERTY(BlueprintReadOnly, Category = "Quest") float Held = 0.0f;
    /** give_hint: how many hints have been given. */
    UPROPERTY(BlueprintReadOnly, Category = "Quest") int32 HintsGiven = 0;
    /** Spawns already made for this objective (so a reload does not double them). */
    UPROPERTY(BlueprintReadOnly, Category = "Quest") bool bSpawned = false;
};

USTRUCT(BlueprintType)
struct FReflectionsQuestState
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Quest") FName QuestId;
    UPROPERTY(BlueprintReadOnly, Category = "Quest") EReflectionsQuestStatus Status = EReflectionsQuestStatus::Unavailable;
    UPROPERTY(BlueprintReadOnly, Category = "Quest") FName StepId;
    UPROPERTY(BlueprintReadOnly, Category = "Quest") TArray<FReflectionsObjectiveState> Objectives;
    /** Finished steps and choices in order ("step:<id>", "choice:<step>:<choice>"), for the journal. */
    UPROPERTY(BlueprintReadOnly, Category = "Quest") TArray<FName> Log;
    UPROPERTY(BlueprintReadOnly, Category = "Quest") bool bDeclined = false;
    UPROPERTY(BlueprintReadOnly, Category = "Quest") bool bSeen = false;
    /** The after lines have been said. */
    UPROPERTY(BlueprintReadOnly, Category = "Quest") bool bAfterSaid = false;
    UPROPERTY(BlueprintReadOnly, Category = "Quest") double StartedAt = 0.0;
    /** Why the quest ended or changed course, for the journal ("Hal is dead. ..."). */
    UPROPERTY(BlueprintReadOnly, Category = "Quest") FText EndNote;
    /** The giver died: the quest can still be finished, and ends itself with no one to return to. */
    UPROPERTY(BlueprintReadOnly, Category = "Quest") bool bGiverLost = false;
};

USTRUCT()
struct FReflectionsQuestItemCount
{
    GENERATED_BODY()
    UPROPERTY() FName Item;
    UPROPERTY() int32 Count = 0;
};

USTRUCT()
struct FReflectionsPersonStanding
{
    GENERATED_BODY()
    UPROPERTY() FName Person;
    UPROPERTY() float Value = 0.0f;
};

/** Everything the quest system saves with a checkpoint. */
USTRUCT()
struct FReflectionsQuestSnapshot
{
    GENERATED_BODY()

    UPROPERTY() bool bValid = false;
    UPROPERTY() TArray<FReflectionsQuestState> Quests;
    UPROPERTY() TArray<FReflectionsQuestItemCount> Items;
    UPROPERTY() TArray<FReflectionsPersonStanding> Standing;
    UPROPERTY() TArray<FName> Unlocks;
    UPROPERTY() FName Tracked;
    /** People who died (quests never spawn or offer through them again). */
    UPROPERTY() TArray<FName> Dead;
    /** Matches the game-flow checkpoint it was taken with. */
    UPROPERTY() FDateTime CheckpointSavedAt;
};

namespace ReflectionsQuest
{
    inline EReflectionsQuestSide SideOf(EReflectionsWorld World) { return static_cast<EReflectionsQuestSide>(static_cast<uint8>(World) + 1); }
    inline bool ToWorld(EReflectionsQuestSide Side, EReflectionsWorld& Out)
    {
        if (Side < EReflectionsQuestSide::Pewterside || Side > EReflectionsQuestSide::Frostside) return false;
        Out = static_cast<EReflectionsWorld>(static_cast<uint8>(Side) - 1);
        return true;
    }
    inline bool Matches(EReflectionsQuestSide Filter, EReflectionsWorld World)
    {
        return Filter == EReflectionsQuestSide::Any || Filter == EReflectionsQuestSide::Current || Filter == SideOf(World);
    }
    inline FReflectionsQuestLineDef Line(FName Speaker, const FText& Text, FName Id = NAME_None)
    {
        FReflectionsQuestLineDef L;
        L.Id = Id;
        L.Speaker = Speaker;
        L.Text = Text;
        return L;
    }
    static const FName End(TEXT("End"));
    static const FName Fail(TEXT("Fail"));
}
