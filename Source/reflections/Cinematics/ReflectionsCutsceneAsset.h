#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "ReflectionsCutsceneAsset.generated.h"

class AActor;
class ULevelSequence;
class UAnimSequenceBase;
class USoundBase;

/**
 * Someone in the cutscene. The sequence never owns a copy of a character: each cast member is a live actor found
 * at play time and bound to every sequence binding tagged with its Role. When the map has nobody to play the part
 * (a test map), StandInClass is spawned at the Mark instead, and removed afterwards.
 */
USTRUCT(BlueprintType)
struct FReflectionsCutsceneCastMember
{
    GENERATED_BODY()

    /** Binding tag in the Level Sequence, and the name used by performances and lines ("Hero", "Elder"). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    FName Role;

    /** The player's hero (the possessed pawn); ignores the search fields. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    bool bIsHero = false;

    /**
     * How to find the live actor: an actor tag (also tried: Cutscene_<Role>, NPC_Name_<Role>), else an actor whose
     * name or label contains it. Empty = Role.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    FName FindTag;

    /**
     * With StandInArchetype set, the stand-in is a real NPC spawned through the NPC system (SpawnNpc), and
     * StandInClass is its look (optional). Otherwise StandInClass itself is spawned.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    FName StandInArchetype;

    /**
     * A person from the people book (people.json id, e.g. jory_pell). Not on the map: the Lives system spawns them on
     * the Mark with their own look and voice (before any nearest-NPC or stand-in fallback).
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    FName PersonId;

    /** Spawned at the Mark when no live actor is found. Empty = the part is skipped. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    TSoftClassPtr<AActor> StandInClass;

    /** Where the actor stands, relative to the anchor (X = stage forward). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    FTransform Mark;

    /** Move the live actor onto its Mark when the cutscene starts (stand-ins always spawn on it). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    bool bPlaceAtMark = false;

    /** Put the live actor back where it was when the cutscene ends (never for the hero unless asked). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    bool bRestoreTransform = false;

    /** Hide the actor for the whole cutscene. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    bool bHidden = false;

    /** Nobody found by tag: cast the nearest NPC within SearchRadius of the anchor instead (before any stand-in). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    bool bFallbackToNearestNpc = false;

    /** With the nearest-NPC search: prefer someone already tarnished. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    bool bPreferInfected = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast", meta = (Units = "cm"))
    float SearchRadius = 4000.0f;

    /** Tarnish this actor when the cutscene starts (NPC system SetInfection(Infected)), so it has the look. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    bool bInfectOnStart = false;

    /** Leave a spawned stand-in in the world afterwards (the gameplay after the scene needs them, e.g. to fight). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cast")
    bool bKeepStandIn = false;
};

/** A body take (Kimodo or any clip) played on a cast member's driver skeleton at a time in the cutscene. */
USTRUCT(BlueprintType)
struct FReflectionsCutscenePerformance
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Performance")
    FName Role;

    /** Seconds from the start of the cutscene. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Performance", meta = (Units = "s"))
    float StartTime = 0.0f;

    /** Played as a dynamic montage on the first mesh in the actor's hierarchy that uses this clip's skeleton. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Performance")
    TSoftObjectPtr<UAnimSequenceBase> Animation;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Performance")
    FName Slot = TEXT("DefaultSlot");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Performance")
    float PlayRate = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Performance", meta = (Units = "s"))
    float BlendIn = 0.3f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Performance", meta = (Units = "s"))
    float BlendOut = 0.4f;

    /**
     * Whole body: play the clip single-node on the mesh, replacing its Anim Blueprint until the cutscene ends (the hero's
     * DefaultSlot only covers the upper body). For Wren use a clip retargeted to the hero body (RTG_MannequinToHero).
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Performance")
    bool bFullBody = false;

    /** 1 = once; more loops repeat the clip. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Performance")
    int32 LoopCount = 1;

    /** Turn the actor (yaw only) to face this role when the take starts. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Performance")
    FName FaceRole;
};

/** One spoken line: subtitle plus voice. */
USTRUCT(BlueprintType)
struct FReflectionsCutsceneLine
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Line", meta = (Units = "s"))
    float StartTime = 0.0f;

    /** 0 = the voice's length (or 3 s without a voice). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Line", meta = (Units = "s"))
    float Duration = 0.0f;

    /** Shown above the line ("WREN HALE"); empty for narration. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Line")
    FText Speaker;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Line", meta = (MultiLine = true))
    FText Text;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Line")
    TSoftObjectPtr<USoundBase> Voice;

    /** The voice plays from this cast member's head (3D); empty = 2D. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Line")
    FName SpeakerRole;

    /** Only when this role was found on the map by its tag (the real person, not a fallback or stand-in). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Line|Variant")
    FName OnlyWithRole;

    /** Only when this role was NOT found by its tag (variant lines for a generic stand-in). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Line|Variant")
    FName OnlyWithoutRole;

    /** Only on this side: Gray (Pewterside), Red (Giltside) or White (Frostside). Empty = any. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Line|Variant")
    FName OnlyInSide;
};

UENUM(BlueprintType)
enum class EReflectionsCutsceneCardStyle : uint8
{
    /** The game's wordmark ("REFLECTIONS") with a subtitle line. */
    Title,
    /** A large italic line in the middle of the frame (the theme line). */
    Caption,
    /** Small spaced capitals low in the frame ("GILTSIDE · LANTHORNE"). */
    Location,
};

/** On-screen text that isn't dialogue: title cards, captions, location stamps. */
USTRUCT(BlueprintType)
struct FReflectionsCutsceneCard
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Card", meta = (Units = "s"))
    float StartTime = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Card", meta = (Units = "s"))
    float Duration = 4.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Card")
    EReflectionsCutsceneCardStyle Style = EReflectionsCutsceneCardStyle::Caption;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Card", meta = (MultiLine = true))
    FText Text;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Card", meta = (MultiLine = true))
    FText SubText;

    /** Only on this side: Gray, Red or White. Empty = any. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Card")
    FName OnlyInSide;
};

/** A named moment other systems can react to (OnCutsceneCue), for example the villain's manifest. */
USTRUCT(BlueprintType)
struct FReflectionsCutsceneCue
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cue", meta = (Units = "s"))
    float Time = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cue")
    FName Cue;

    /**
     * Optional: at this cue, the villain's conversion (UReflectionsVillainSubsystem::BeginConversion) runs with the
     * actors playing these roles. Its length decides how long the cutscene holds at HoldAt.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cue|Conversion")
    FName AttackerRole;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cue|Conversion")
    FName VictimRole;

    /** Cutscene time to freeze at (on the held shot) until the conversion is over. < 0 = never hold. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cue|Conversion", meta = (Units = "s"))
    float HoldAt = -1.0f;

    /** Body take for the victim when the conversion was refused (0 returned). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cue|Conversion")
    TSoftObjectPtr<UAnimSequenceBase> FallbackVictimTake;
};

/** A fade to or from black at a time in the cutscene (sequence fade tracks also work). */
USTRUCT(BlueprintType)
struct FReflectionsCutsceneFade
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fade", meta = (Units = "s"))
    float StartTime = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fade", meta = (Units = "s"))
    float Duration = 1.0f;

    /** Black amount at the start and end of the fade (0 = clear, 1 = black). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fade")
    float From = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fade")
    float To = 0.0f;
};

/**
 * One cutscene: /Game/Cinematics/Data/DA_Cutscene_<Name>. The Level Sequence holds the cameras (spawnables, with
 * transforms relative to the anchor), camera cuts and any props or effects; this asset holds who plays which part,
 * their body takes, the lines and the on-screen text. Everything is placed relative to the anchor, so the same
 * cutscene plays on any map. See ArtDirection/Cinematics/README.md.
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsCutsceneAsset : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    /** Cameras, cuts, props. Optional: without one the gameplay camera stays and only the text and lines play. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene")
    TSoftObjectPtr<ULevelSequence> Sequence;

    /** Looks for the CutsceneAnchor_<AnchorName> marker; without one the hero's feet and facing are the origin. Empty = Name. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene|Anchor")
    FName AnchorName;

    /** Drop the anchor onto the ground under it (keeps marker placement forgiving). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene|Anchor")
    bool bSnapAnchorToGround = true;

    /** Ignore the anchor's pitch and roll. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene|Anchor")
    bool bAnchorYawOnly = true;

    /** Length when there is no sequence (or to cut a sequence short). 0 = the sequence's length. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene", meta = (Units = "s"))
    float Length = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene")
    TArray<FReflectionsCutsceneCastMember> Cast;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene")
    TArray<FReflectionsCutscenePerformance> Performances;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene")
    TArray<FReflectionsCutsceneLine> Lines;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene")
    TArray<FReflectionsCutsceneCard> Cards;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene")
    TArray<FReflectionsCutsceneCue> Cues;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene")
    TArray<FReflectionsCutsceneFade> Fades;

    /** Music or ambience for the whole cutscene (2D), faded out at the end. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene")
    TSoftObjectPtr<USoundBase> Music;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene|Presentation")
    bool bLetterbox = true;

    /** Aspect ratio inside the bars. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene|Presentation")
    float LetterboxAspect = 2.39f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene|Presentation")
    bool bSkippable = true;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene|Presentation", meta = (Units = "s"))
    float SkipHoldSeconds = 1.0f;

    /** Fade to black and back when skipped. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene|Presentation", meta = (Units = "s"))
    float SkipFadeSeconds = 0.45f;

    /** Camera blend from the last shot back to the gameplay camera. 0 = cut. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene|Hand-off", meta = (Units = "s"))
    float HandOffBlendSeconds = 1.2f;

    /** Point the gameplay camera along the hero's facing when control returns (so it lands behind Wren). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene|Hand-off")
    bool bHandOffBehindHero = true;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene|Hand-off")
    float HandOffPitch = -12.0f;

    /** NPCs that aren't cast and stand within this distance of the anchor are hidden for the scene (0 = keep them). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene", meta = (Units = "cm"))
    float ClearRadius = 1500.0f;

    /** Nothing can hurt the hero while the cutscene plays. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cutscene")
    bool bHeroInvulnerable = true;
};
