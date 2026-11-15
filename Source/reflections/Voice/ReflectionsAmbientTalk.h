#pragma once

#include "CoreMinimal.h"

class AActor;
class UAudioComponent;
class UWorld;

/**
 * When NPCs may talk on their own: barks, greetings, passing remarks and NPC-to-NPC street conversations.
 *
 * Ambient talk starts only near the player (Npc.AmbientTalk.Radius, 13 m) from a speaker on screen (or right next to
 * the player), at most Npc.AmbientTalk.MaxVoices at once, and not while the player is in a live conversation.
 * It fades out once the player is past Npc.AmbientTalk.StopRadius (18 m). Combat talk (an NPC that is not calm:
 * fighting, fleeing, hurt) carries to Npc.AmbientTalk.CombatRadius (30 m) and is not counted against the cap.
 * Player-started conversations (UReflectionsVoiceInteractionSubsystem) do not go through here.
 * Nothing here makes a network request: ambient lines are baked audio.
 */
namespace ReflectionsAmbientTalk
{
    /** May this NPC start a line now? bCombat: a fight or pain line (wider radius, no cap, no on-screen check). */
    REFLECTIONS_API bool MayStart(const AActor* Speaker, bool bCombat);

    /** A group conversation: its centre must be within reach, one speaker on screen, and a voice free. */
    REFLECTIONS_API bool MayStartGroup(const TArray<AActor*>& Speakers);

    /** True while the player is still close enough to hear this NPC's ambient talk (StopRadius, or CombatRadius). */
    REFLECTIONS_API bool IsWithinHearing(const AActor* Speaker, bool bCombat);
    REFLECTIONS_API bool IsPlaceWithinHearing(const UWorld* World, const FVector& Location, bool bCombat);

    /** Track a line that just started, so it counts against the cap and fades out when the player walks away. */
    REFLECTIONS_API void Track(UAudioComponent* Audio, const AActor* Speaker, bool bCombat);

    /** Fades out tracked lines whose speaker the player has left behind (called every frame for this world). */
    REFLECTIONS_API void Tick(UWorld* World);

    /** Ambient lines playing now in this world (the cap counts these). */
    REFLECTIONS_API int32 CountPlaying(const UWorld* World);
}
