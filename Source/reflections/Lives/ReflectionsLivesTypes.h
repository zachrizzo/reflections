#pragma once

#include "CoreMinimal.h"
#include "ReflectionsLivesTypes.generated.h"

/** What a person is doing right now. Schedule steps name one; reactions and meetings add the rest. */
UENUM(BlueprintType)
enum class EReflectionsLifeActivity : uint8
{
    Idle,
    Wake,
    Work,
    Eat,
    Errand,
    Haunt,
    Social,
    Worship,
    Home,
    Sleep,
    Patrol,
    /** Talking with someone they know. */
    Chat,
    /** Saw someone they love hurt, killed or taken. */
    Grieve,
    /** Keeping away from a place where something terrible happened. */
    Avoid,
    /** Indoors: not in the street until the next outdoor step. */
    Inside,
    /** Standing watch at a post, facing out. */
    Guard,
    /** Doors shut at home (the Tarnish is close). */
    Hide,
    Stroll,
    Shop,
    /** Mourning outside the home of someone they loved who was killed. */
    Vigil,
    /** Keeping away from the Silverer (fear or hatred after what the player did). */
    Shun,
};

/** How a person feels for a while after something happened to them or someone they know. */
UENUM(BlueprintType)
enum class EReflectionsLifeMood : uint8
{
    Content,
    Cheerful,
    Wary,
    Afraid,
    Grieving,
    Angry,
};

/** Something the player did that a person remembers. */
UENUM(BlueprintType)
enum class EReflectionsPlayerDeed : uint8
{
    Helped,
    Hurt,
    CastNear,
    SavedFriend,
    HurtFriend,
    KilledFriend,
    CompletedQuest,
    Talked,
    /** Saw the player commit a crime (npc-unify's OnPlayerCrime): theft, assault, murder... */
    WitnessedCrime,
};

/** How much of a life is simulated right now. */
UENUM(BlueprintType)
enum class EReflectionsLifeLod : uint8
{
    /** An actor near the player: walks, meets, reacts. */
    Full,
    /** An actor far away: its schedule is fast-forwarded (it is put where it should be when nobody sees it). */
    Far,
    /** No actor (a named person off screen, a Mass pedestrian): only the schedule is advanced. */
    Virtual,
};

USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsPersonality
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Lives") TArray<FString> Traits;
    /** 0..1: how kindly they take help and how warmly they greet. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Lives") float Warmth = 0.5f;
    /** 0..1: fear or anger when something bad happens. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Lives") float Courage = 0.5f;
    /** 0..1: how hard they hold a grudge. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Lives") float Temper = 0.3f;
    /** 0..1: how much they seek out friends and talk. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Lives") float Chattiness = 0.5f;
};

USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsKin
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Lives") FName Id;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Lives") FString Relation;
};

/** One step of a day: from hour At (0..24) until the next step, do Do at Where. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsScheduleStep
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Lives") float At = 8.0f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Lives") FName Do = TEXT("haunt");
    /** home | work | haunt | social | a place marker tag (Haunt_Market). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Lives") FName Where = TEXT("haunt");
};

/** A person of the people book (ArtDirection/Story/people.json) or one generated from its rules. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsPerson
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category="Lives") FName Id;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Name;
    /** F or M. */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName Sex;
    /** Young | Adult | Old. */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName Age = TEXT("Adult");
    /** Giltside | Frostside | Pewterside (the story bible's side names). */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName Side = TEXT("Giltside");
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName Job;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString JobTitle;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName Archetype;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Look;
    /** The kind of body they need (story book look_role: Civilian, Guard, Soldier, Caster). */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName LookRole;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName Home;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName Work;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FName> Haunts;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FReflectionsPersonality Personality;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Summary;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString SpeechStyle;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Quirk;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> Likes;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> Dislikes;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Fear;
    /** For quests only: never part of the dialogue persona. */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Secret;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FReflectionsKin> Family;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FName> Friends;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FName> Rivals;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName ScheduleKey;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FReflectionsScheduleStep> Schedule;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName Quest;
    /** What they want most (story book). */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Want;
    /** Safe facts they share freely. */
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> Knows;
    /** Words or subjects they avoid. */
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> NeverSays;
    /** Their starting view of the Silverer ("grudging", "proud and afraid for him"). */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Stance;
    /** A line in their voice about the Silverer (a style sample for live replies, not to be repeated word for word). */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString StanceLine;
    /** Habits and verbal tics. */
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> Tics;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> FavouriteWords;
    /** Every quest they are part of (story.quests). */
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FName> Quests;
    /** Their clique (story book), whose spot is where they chat. */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName Clique;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName CliqueSpot;
    /** Their voice in audio's roster (V001...). */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName VoiceId;
    /** True for people written in the book; false for generated townsfolk. */
    UPROPERTY(BlueprintReadOnly, Category="Lives") bool bNamed = false;
};

/** What one person remembers of the player. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsPlayerMemory
{
    GENERATED_BODY()

    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") int32 Helped = 0;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") int32 Hurt = 0;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") int32 CastNear = 0;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") int32 SavedFriend = 0;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") int32 HurtFriend = 0;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") int32 KilledFriend = 0;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") int32 QuestsDone = 0;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") int32 Talks = 0;
    /** Crimes by the player this person saw. */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") int32 Crimes = 0;
    /** -1 (hates the player) .. 1 (would die for them). */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") float Opinion = 0.0f;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") EReflectionsPlayerDeed LastDeed = EReflectionsPlayerDeed::Talked;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") bool bHasLastDeed = false;
    /** Game hours (absolute) of the last deed. */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") double LastDeedHours = 0.0;
    /** "healed me by the bridge", "burned Tom Vell"... */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") FString LastDeedNote;
    /** The starting stance of the people book has been turned into an opinion. */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") bool bSeeded = false;
};

/** Everything about a person that changes in play and must survive checkpoints. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsPersonState
{
    GENERATED_BODY()

    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") FName Id;
    /** The name a generated person was given (kept so it never changes between runs). */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") FString GivenName;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") FReflectionsPlayerMemory Player;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") EReflectionsLifeMood Mood = EReflectionsLifeMood::Content;
    /** Game hours (absolute) when the mood fades back to Content. */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") double MoodUntilHours = 0.0;
    /** Somewhere to keep away from until AvoidUntilHours. */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") FVector AvoidLocation = FVector::ZeroVector;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") double AvoidUntilHours = 0.0;
    /** Who they grieve or fear for (person id). */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") FName ConcernFor;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") bool bDead = false;
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") bool bTarnished = false;
    /** Dead by the player's hand (the dead stay dead: their body is not given to anyone else's life again). */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") bool bKilledByPlayer = false;
    /** Loved ones the player killed (person ids). Mourned for good: part of the persona after the grief fades. */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") TArray<FName> Mourns;
    /** Newest last, at most 5: "saw Tom Vell taken by the Tarnish". Part of the persona. */
    UPROPERTY(SaveGame, BlueprintReadOnly, Category="Lives") TArray<FString> Events;
};

/** The whitelisted facts the dialogue persona may use. Never the secret or quest internals. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsPersonaFacts
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category="Lives") bool bValid = false;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FName PersonId;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Name;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString JobTitle;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Age;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Side;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> Traits;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Summary;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString SpeechStyle;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Quirk;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> Likes;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> Dislikes;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Fear;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Want;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> Knows;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> NeverSays;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> Tics;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> FavouriteWords;
    /** Their starting view of the Silverer, and a sample line of theirs about him. */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Stance;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString StanceLine;
    /** How the street feels now (the Tarnish meter's band: quiet, spreading, rising, brink). */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString InfectionBand;
    /** "Tom Vell (husband)", "Jo Ash (friend)". */
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> People;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Activity;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString Mood;
    /** One sentence: what they think of the player and why. */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString PlayerMemory;
    UPROPERTY(BlueprintReadOnly, Category="Lives") float Opinion = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Lives") TArray<FString> RecentEvents;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FString TimeOfDay;
};

/** A place people go: a quest marker (Home_<id>, Work_<job>, Haunt_<place>) or one placed automatically. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsLifePlace
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category="Lives") FName Tag;
    UPROPERTY(BlueprintReadOnly, Category="Lives") FVector Location = FVector::ZeroVector;
    /** Where people go in and out (Door_<tag> marker, else Location). */
    UPROPERTY(BlueprintReadOnly, Category="Lives") FVector Door = FVector::ZeroVector;
    /** People mill around within this of Location. */
    UPROPERTY(BlueprintReadOnly, Category="Lives") float Radius = 350.0f;
    UPROPERTY(BlueprintReadOnly, Category="Lives") bool bAuto = false;
};
