#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Lives/ReflectionsLivesTypes.h"
#include "ReflectionsPeopleBook.generated.h"

/**
 * The people book as a cooked asset: the text of ArtDirection/Story/people.json, so packaged builds have it.
 * /Game/Lives/DA_PeopleBook. Editor builds read the JSON file itself first, so edits show on the next Play.
 * Re-import: UReflectionsPeopleBookAsset::ImportFromFile (Python: unreal.ReflectionsPeopleBookAsset.import_from_file).
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsPeopleBookAsset : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Lives", meta=(MultiLine=true))
    FString Json;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Lives")
    FString SourcePath;

    /** Reads a people.json into Asset->Json (does not save the package). False if the file is missing or not valid. */
    UFUNCTION(BlueprintCallable, Category="Lives")
    static bool ImportFromFile(UReflectionsPeopleBookAsset* Asset, const FString& FilePath);
};

/** Rules for townsfolk who are not written in the book: per-side pools (story book) over flat pools (stub, built-in). */
struct FReflectionsPeopleGenerator
{
    struct FJob { FName Job; FString Title; int32 Weight = 1; FName Schedule; FName Side; };
    struct FPools
    {
        TArray<FString> FirstNamesF;
        TArray<FString> FirstNamesM;
        TArray<FString> Surnames;
        TArray<FJob> Jobs;
        TArray<FString> SpeechStyles;
        TArray<FString> Fears;
        TArray<FString> Wants;
        /** Places of this side people may hang out at (named places of the story book). */
        TArray<FName> Haunts;
    };
    FPools Flat;
    TMap<FName, FPools> Sides;
    /** One trait from each column (story book: temper, how they treat others, what drives them). */
    TArray<TArray<FString>> TraitColumns;
    /** Flat trait list: two or three are picked. */
    TArray<FString> Traits;
    TArray<FString> Quirks;
    TArray<FString> Likes;
    TArray<FString> Secrets;
    /** Names nobody may have. */
    TArray<FString> NeverNames;
    TArray<FName> Schedules;
    int32 FriendsMin = 1;
    int32 FriendsMax = 3;
};

/** A clique of the story book: people who meet at a spot. */
struct FReflectionsClique
{
    FName Id;
    FString Name;
    FName Spot;
    FName Side;
    TArray<FName> Members;
    FString Dynamic;
};

/** One band of the Tarnish meter (quiet, spreading, rising, brink) and how the street feels. */
struct FReflectionsInfectionBand
{
    FName Band;
    float From = 0.0f;
    float To = 1.0f;
    FString StreetMood;
};

/** The parsed book: named people, schedule templates, cliques, generator rules, day length. */
class REFLECTIONS_API FReflectionsPeopleBook
{
public:
    /** Loads, most authoritative first: the JSON files (editor), /Game/Lives/DA_PeopleBook, the built-in stub. */
    void Load();
    bool ParseJson(const FString& Text, const FString& Source);

    const TArray<FReflectionsPerson>& GetNamed() const { return Named; }
    const FReflectionsPerson* FindNamed(FName Id) const;
    const TArray<FReflectionsScheduleStep>* FindSchedule(FName Key) const { return Schedules.Find(Key); }
    const FReflectionsPeopleGenerator& GetGenerator() const { return Generator; }
    const FString& GetSource() const { return Source; }
    const FReflectionsClique* FindClique(FName Id) const { return Cliques.Find(Id); }
    const TArray<FReflectionsInfectionBand>& GetInfectionBands() const { return InfectionBands; }
    /** The band for an infection fraction 0..1 (None if the book has no bands). */
    const FReflectionsInfectionBand* BandFor(float Fraction) const;
    /** The name the player goes by in persona text ("Wren, the Silverer"). */
    const FString& GetPlayerName() const { return PlayerName; }
    /** The quest system's name for a story-book marker (Mk_Gilt_Market_LanternRow -> Spot_LanternRow), None if none. */
    FName StoryNameFor(FName Marker) const { const FName* N = StoryNames.Find(Marker); return N ? *N : NAME_None; }

    /** A townsperson from the generator rules, the same every time for the same Id and Salt. */
    FReflectionsPerson Generate(FName Id, FName Sex, FName Age, FName Side, int32 Salt) const;

    /** The schedule a person follows: their own steps, their schedule key, the job's, or a built-in day. */
    TArray<FReflectionsScheduleStep> ResolveSchedule(const FReflectionsPerson& Person) const;

    /** Opinion of the player a starting stance stands for ("grudging" -0.1, "admiring" +0.3...). */
    static float StanceOpinion(const FString& Stance);
    /** Giltside -> Gilt, Pewterside -> Pew, Frostside -> Frost (the Mk_ marker side). */
    static FString MarkerSide(FName Side);

    float RealMinutesPerDay = 24.0f;
    float StartHour = 8.0f;

private:
    void AddBuiltIns();
    FName ScheduleForJob(const FString& JobTitle) const;
    TArray<FReflectionsPerson> Named;
    TMap<FName, TArray<FReflectionsScheduleStep>> Schedules;
    TMap<FName, FReflectionsClique> Cliques;
    TArray<FReflectionsInfectionBand> InfectionBands;
    TArray<FName> NamedPlaces;
    TMap<FName, FName> StoryNames;
    FReflectionsPeopleGenerator Generator;
    FString Source;
    FString PlayerName = TEXT("the Silverer");
};
