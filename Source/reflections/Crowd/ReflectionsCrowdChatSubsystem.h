#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Crowd/ReflectionsAmbientConversation.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "ReflectionsCrowdChatSubsystem.generated.h"

class UAudioComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FReflectionsCrowdChatFinished, const TArray<AActor*>&, Speakers, FName, ConvId, bool, bInterrupted);

/**
 * Plays baked street conversations between NPCs who are standing together (the chat director).
 *
 * The caller owns the bodies: it brings the speakers together, keeps them still and facing each other, and lets
 * them go when the conversation ends. The director only talks: it picks a row of audio's conversation table for
 * the place and the number of speakers, gives each speaker the row's roster voice of the right sex for the
 * conversation (UReflectionsNpcReactionComponent::SetVoiceOverride), plays the lines in turn from each speaker's
 * head, and gives the voices back at the end.
 *
 * Any non-calm reaction of a speaker, a speaker going away, or StopConversation ends it early.
 * Called by the lives session by reflection: /Script/reflections.ReflectionsCrowdChatSubsystem:PlayConversationBetween.
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsCrowdChatSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;

    /**
     * Start a conversation between these NPCs (2-4) at a place: a spot name (market, gate, tavern, bridge, tower,
     * street) or a place marker name (Haunt_Market, Work_Baker...: the prefix is dropped). False when no row fits,
     * a speaker is already talking or not calm, the player is too far to hear it, or enough are already playing;
     * the caller then does something else (a bark).
     */
    UFUNCTION(BlueprintCallable, Category="Crowd|Chat")
    bool PlayConversationBetween(const TArray<AActor*>& Speakers, FName Spot);

    /**
     * Play one named conversation (its ConvId or row name), story table first, then the generic one. Speakers
     * are given in the row's role order: the caller knows who is who (named people keep their reserved voices),
     * so nobody is cast by sex. False when there is no such row, the speaker count differs, or a speaker is busy
     * or not calm, or nobody can hear it. Band and RequiredFlag are the caller's to judge.
     */
    UFUNCTION(BlueprintCallable, Category="Crowd|Chat")
    bool PlayConversationById(const TArray<AActor*>& Speakers, FName ConvId);

    UFUNCTION(BlueprintPure, Category="Crowd|Chat")
    bool IsInConversation(const AActor* Actor) const;

    /** End the conversation this NPC is in (its partners stop too). */
    UFUNCTION(BlueprintCallable, Category="Crowd|Chat")
    void StopConversation(const AActor* Actor);

    UFUNCTION(BlueprintPure, Category="Crowd|Chat")
    int32 GetActiveCount() const { return Active.Num(); }

    UFUNCTION(BlueprintCallable, Category="Crowd|Chat")
    FString Describe() const;

    /** Every conversation that ends, finished or interrupted. */
    UPROPERTY(BlueprintAssignable, Category="Crowd|Chat")
    FReflectionsCrowdChatFinished OnConversationFinished;

private:
    struct FActiveChat
    {
        /** Speakers in the row's role order (SpeakerIndex refers into this). */
        TArray<TWeakObjectPtr<AActor>> Roles;
        /** Which of them got a voice override from this conversation. */
        TArray<bool> bOverridden;
        /** The voice each had before (another system's override, such as a lives person's voice, is put back). */
        TArray<FName> PreviousVoice;
        TArray<bool> bHadOverride;
        FName ConvId;
        TArray<FReflectionsAmbientLine> Lines;
        int32 NextLine = 0;
        double NextLineAt = 0.0;
        TWeakObjectPtr<UAudioComponent> Playing;
        /** The conversation's waves load in the background; a line waits for its wave until LoadDeadline. */
        TSharedPtr<struct FStreamableHandle> Loading;
        double LoadDeadline = 0.0;
    };

    /** Audio's table at a CVar's path, loaded once (nullptr while it does not exist or has another row type). */
    const UDataTable* GetTable(bool bStory);
    /** Shared checks: 2-4 distinct, calm NPCs not already talking, within hearing of the player, a free slot. */
    bool CanStart(const TArray<AActor*>& Speakers) const;
    /** Roles for a row: the speakers reordered so each role's roster voice matches the speaker's sex. */
    bool CastRoles(const FReflectionsAmbientConversationRow& Row, const TArray<AActor*>& Speakers, TArray<AActor*>& OutRoles);
    void StartChat(const FReflectionsAmbientConversationRow& Row, FName RowName, const TArray<AActor*>& Roles);
    void PlayLine(FActiveChat& Chat);
    void Finish(int32 Index, bool bInterrupted);
    int32 FindChat(const AActor* Actor) const;

    UFUNCTION()
    void HandleNpcReaction(AActor* Npc, EReflectionsNpcReaction Reaction, AActor* Cause, FVector Location);

    UPROPERTY(Transient)
    TObjectPtr<const UDataTable> Table;

    UPROPERTY(Transient)
    TObjectPtr<const UDataTable> StoryTable;

    TArray<FActiveChat> Active;
    /** When each conversation last started, so the same one is not heard twice in a row. */
    TMap<FName, double> LastPlayed;
    bool bTableLoaded = false;
    bool bStoryTableLoaded = false;
    int32 Started = 0;
    int32 Interrupted = 0;
};
