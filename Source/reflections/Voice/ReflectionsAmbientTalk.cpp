#include "Voice/ReflectionsAmbientTalk.h"
#include "Voice/ReflectionsVoiceInteractionSubsystem.h"
#include "Components/AudioComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"

namespace
{
    TAutoConsoleVariable<float> CVarRadius(TEXT("Npc.AmbientTalk.Radius"), 1300.0f,
        TEXT("NPCs start barks, greetings, remarks and street conversations only while the player is this close (cm)."));
    TAutoConsoleVariable<float> CVarStopRadius(TEXT("Npc.AmbientTalk.StopRadius"), 1800.0f,
        TEXT("Ambient talk fades out once the player is farther than this (cm) from the speaker."));
    TAutoConsoleVariable<float> CVarCombatRadius(TEXT("Npc.AmbientTalk.CombatRadius"), 3000.0f,
        TEXT("Fight, fear and pain lines start within this distance (cm) of the player and fade 20% beyond it."));
    TAutoConsoleVariable<float> CVarCloseRadius(TEXT("Npc.AmbientTalk.CloseRadius"), 500.0f,
        TEXT("Within this distance (cm) an NPC may talk even when it is off screen (just behind the player)."));
    TAutoConsoleVariable<int32> CVarMaxVoices(TEXT("Npc.AmbientTalk.MaxVoices"), 3,
        TEXT("Most ambient lines playing at once (fight and pain lines are not counted)."));

    struct FTracked
    {
        TWeakObjectPtr<UAudioComponent> Audio;
        TWeakObjectPtr<const AActor> Speaker;
        bool bCombat = false;
        bool bFading = false;
    };
    TArray<FTracked> GTracked;

    const APawn* PlayerIn(const UWorld* World)
    {
        return World ? UGameplayStatics::GetPlayerPawn(World, 0) : nullptr;
    }

    bool PlayerInLiveConversation(const UWorld* World)
    {
        const UReflectionsVoiceInteractionSubsystem* Dialogue = World ? World->GetSubsystem<UReflectionsVoiceInteractionSubsystem>() : nullptr;
        return Dialogue && Dialogue->IsNpcBusy();
    }

    bool VoiceFree(const UWorld* World)
    {
        return ReflectionsAmbientTalk::CountPlaying(World) < FMath::Max(0, CVarMaxVoices.GetValueOnGameThread());
    }
}

bool ReflectionsAmbientTalk::MayStart(const AActor* Speaker, bool bCombat)
{
    if (!IsValid(Speaker)) return false;
    const UWorld* World = Speaker->GetWorld();
    const APawn* Player = PlayerIn(World);
    if (!Player) return true;  // no player (a tool or editor preview): the caller decides
    const double Distance = FVector::Dist(Speaker->GetActorLocation(), Player->GetActorLocation());
    if (bCombat) return Distance <= CVarCombatRadius.GetValueOnGameThread();
    if (Distance > CVarRadius.GetValueOnGameThread()) return false;
    if (Distance > CVarCloseRadius.GetValueOnGameThread() && !Speaker->WasRecentlyRendered(0.5f)) return false;
    // The player's own conversation is heard clearly: nobody nearby starts chatting over it.
    if (PlayerInLiveConversation(World)) return false;
    return VoiceFree(World);
}

bool ReflectionsAmbientTalk::MayStartGroup(const TArray<AActor*>& Speakers)
{
    FVector Centre = FVector::ZeroVector;
    int32 Count = 0;
    const UWorld* World = nullptr;
    for (const AActor* Speaker : Speakers)
    {
        if (!IsValid(Speaker)) continue;
        Centre += Speaker->GetActorLocation();
        World = Speaker->GetWorld();
        ++Count;
    }
    if (Count == 0) return false;
    Centre /= Count;
    const APawn* Player = PlayerIn(World);
    if (!Player) return true;
    const FVector PlayerAt = Player->GetActorLocation();
    if (FVector::Dist(Centre, PlayerAt) > CVarRadius.GetValueOnGameThread()) return false;
    // Someone in the group must be in view (or right next to the player).
    bool bSeen = false;
    for (const AActor* Speaker : Speakers)
    {
        bSeen |= IsValid(Speaker) && (Speaker->WasRecentlyRendered(0.5f) ||
            FVector::Dist(Speaker->GetActorLocation(), PlayerAt) <= CVarCloseRadius.GetValueOnGameThread());
    }
    if (!bSeen || PlayerInLiveConversation(World)) return false;
    return VoiceFree(World);
}

bool ReflectionsAmbientTalk::IsWithinHearing(const AActor* Speaker, bool bCombat)
{
    if (!IsValid(Speaker)) return false;
    return IsPlaceWithinHearing(Speaker->GetWorld(), Speaker->GetActorLocation(), bCombat);
}

bool ReflectionsAmbientTalk::IsPlaceWithinHearing(const UWorld* World, const FVector& Location, bool bCombat)
{
    const APawn* Player = PlayerIn(World);
    if (!Player) return true;
    const float Limit = bCombat ? CVarCombatRadius.GetValueOnGameThread() * 1.2f : CVarStopRadius.GetValueOnGameThread();
    return FVector::Dist(Location, Player->GetActorLocation()) <= Limit;
}

void ReflectionsAmbientTalk::Track(UAudioComponent* Audio, const AActor* Speaker, bool bCombat)
{
    if (!Audio) return;
    GTracked.RemoveAllSwap([](const FTracked& Old) { return !Old.Audio.IsValid(); });
    FTracked& Entry = GTracked.AddDefaulted_GetRef();
    Entry.Audio = Audio;
    Entry.Speaker = Speaker;
    Entry.bCombat = bCombat;
}

void ReflectionsAmbientTalk::Tick(UWorld* World)
{
    for (int32 Index = GTracked.Num() - 1; Index >= 0; --Index)
    {
        FTracked& Entry = GTracked[Index];
        UAudioComponent* Audio = Entry.Audio.Get();
        if (!Audio || !Audio->IsPlaying())
        {
            GTracked.RemoveAtSwap(Index);
            continue;
        }
        if (Entry.bFading || Audio->GetWorld() != World) continue;
        const AActor* Speaker = Entry.Speaker.Get();
        if (!Speaker || !IsWithinHearing(Speaker, Entry.bCombat))
        {
            Audio->FadeOut(0.8f, 0.0f);
            Entry.bFading = true;
        }
    }
}

int32 ReflectionsAmbientTalk::CountPlaying(const UWorld* World)
{
    int32 Count = 0;
    for (const FTracked& Entry : GTracked)
    {
        const UAudioComponent* Audio = Entry.Audio.Get();
        Count += Audio && !Entry.bCombat && !Entry.bFading && Audio->GetWorld() == World && Audio->IsPlaying() ? 1 : 0;
    }
    return Count;
}
