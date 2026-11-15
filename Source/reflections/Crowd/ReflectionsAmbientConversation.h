#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "Sound/SoundBase.h"
#include "ReflectionsAmbientConversation.generated.h"

/** One spoken line of a baked street conversation. */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsAmbientLine
{
    GENERATED_BODY()

    /** Index into the conversation's Speakers (role order). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient")
    int32 SpeakerIndex = 0;

    /** The baked line (already carries the NPC voice attenuation). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient")
    TSoftObjectPtr<USoundBase> Wave;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient")
    FText Subtitle;

    /** Seconds; 0 = read the sound's own duration. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient", meta=(ClampMin="0", Units="s"))
    float Duration = 0.0f;

    /** Pause after this line before the next speaker starts. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient", meta=(ClampMin="0", Units="s"))
    float GapAfter = 0.35f;
};

/**
 * A baked conversation between a clique of 2-4 fixed voices, played by the crowd's chat director.
 * Audio fills two tables of these rows:
 * - /Game/Audio/Jam/Voice/Ambient/DT_AmbientConversations: generic voices, cast onto any NPCs of the right sex;
 * - /Game/Audio/Jam/Voice/Ambient/DT_StoryConversations: named people's reserved voices, only played by id
 *   (UReflectionsCrowdChatSubsystem::PlayConversationById) for those people.
 */
USTRUCT(BlueprintType)
struct REFLECTIONS_API FReflectionsAmbientConversationRow : public FTableRowBase
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient")
    FName ConvId;

    /** Which London (e.g. Red, White, Gray) the conversation belongs to. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient")
    FName Side;

    /** Where it fits: market, gate, tavern, bridge, tower, street. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient")
    FName Spot;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient")
    FName CliqueId;

    /** Story conversations: the story band it belongs to. Read by whoever picks story conversations (lives); the director does not judge it. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient")
    FName Band;

    /** Story conversations: a story flag that must be set. Rows with one are never picked at random for passers-by. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient")
    FName RequiredFlag;

    /** Voice ids of the speakers, in role order (SpeakerIndex refers into this). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient")
    TArray<FName> Speakers;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ambient")
    TArray<FReflectionsAmbientLine> Lines;
};
