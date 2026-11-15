#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Quests/ReflectionsQuestTypes.h"
#include "ReflectionsQuestPack.generated.h"

/**
 * Quest content: quests and the people they involve. The game loads every pack listed in
 * UReflectionsQuestSubsystem::Packs (default /Game/Quests/DA_QuestPack_Story), on top of the built-in main quest and
 * test quest, and a pack quest with the same id replaces a built-in one.
 *
 * Author in the Details panel, or paste JSON (schema: ArtDirection/Quests/README.md) into SourceJson / PeopleJson
 * and press Import Json. Tools/Quests/import_story.py does that from the story bible's files.
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsQuestPack : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Quests")
    TArray<FReflectionsQuestDef> Quests;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Quests")
    TArray<FReflectionsQuestPerson> People;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Quests")
    TArray<FReflectionsQuestItemDef> Items;

    /** Story marker name -> map tag that stands for it (people.json markers.story_names, inverted). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Quests")
    TMap<FName, FName> MarkerAliases;

    /** Quest JSON ({"quests": [...]}). Import Json turns it into Quests. */
    UPROPERTY(EditAnywhere, Category = "Quests|Source", meta = (MultiLine = "true"))
    FString SourceJson;

    /** People JSON ({"people": [...]}, the story bible's people.json). Import Json turns it into People. */
    UPROPERTY(EditAnywhere, Category = "Quests|Source", meta = (MultiLine = "true"))
    FString PeopleJson;

    /** Result of the last import (errors and counts). */
    UPROPERTY(VisibleAnywhere, Category = "Quests|Source")
    FString ImportReport;

    /** Rebuilds Quests and People from the JSON fields (an empty field leaves its list alone). */
    UFUNCTION(CallInEditor, BlueprintCallable, Category = "Quests")
    bool ImportJson();

    /** Parses quest JSON. Accepts {"quests": [...]}, a bare array, or one quest object. */
    static bool ParseQuests(const FString& Json, TArray<FReflectionsQuestDef>& OutQuests, FString& OutReport);

    /** Parses people JSON. Accepts {"people": [...]}, a bare array, or an object keyed by id. */
    static bool ParsePeople(const FString& Json, TArray<FReflectionsQuestPerson>& OutPeople, FString& OutReport);

    /** The quest file's "items" list ({id, name}). */
    static void ParseItems(const FString& Json, TArray<FReflectionsQuestItemDef>& OutItems);

    /** people.json markers.story_names ({"Mk_Gilt_Square_BellSquare": "Spot_BellSquare"}) as story name -> map tag. */
    static void ParseMarkerAliases(const FString& Json, TMap<FName, FName>& OutAliases);
};
