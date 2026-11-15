#pragma once

#include "CoreMinimal.h"
#include "Templates/SubclassOf.h"

class AActor;
class APawn;
class UDamageType;
class UNiagaraComponent;
class UNiagaraSystem;
class USceneComponent;
class USkeletalMeshComponent;
class USoundBase;
class UWorld;

/** Villain palette: near-black body, deep violet magic, pale lilac highlights. The Final Spell is gold-white. */
namespace ReflectionsVillainColors
{
    const FLinearColor Violet(0.32f, 0.04f, 0.62f);
    const FLinearColor Lilac(0.86f, 0.74f, 1.0f);
    const FLinearColor Eye(0.92f, 0.82f, 1.0f);
    const FLinearColor Smoke(0.006f, 0.004f, 0.01f, 0.8f);
    const FLinearColor FinalGold(1.0f, 0.72f, 0.25f);
    const FLinearColor FinalWhite(1.0f, 0.96f, 0.85f);
}

/** Tuning, all live-editable as console variables (Villain.*). */
namespace ReflectionsVillainTuning
{
    int32 AutoStart();            // 0 off, 1 in world-jump / arena maps, 2 every game map
    float StartDelay();
    float HostLifetime();
    float InfectInterval();
    float InfectRadius();
    float HopRadius();
    float SeedRadius();
    /** Seconds between tackle conversions (pacing of the Tarnish meter). */
    float ConvertInterval();
    float RiftDelay();
    float RiftChance();
    bool KillHostsOnBurnout();
    float BossHealth();
    float FinalSpellDamage();
    float OtherSpellScale();
    float FinalSpellManaCost();
    float FinalSpellCooldown();
    float ManifestRadius();
    float AttackDamageScale();
    float TelegraphScale();
    int32 MaxInfected();
    /** The host also infects at range with a wisp (off once the NPC system drives tackles). */
    bool RangedSpread();
    /** Violet vein overlay on tarnished bodies (off: same clothes, same person; the aura is the read). */
    bool VeinOverlay();
}

namespace ReflectionsVillainFx
{
    /** The parametric projectile system, tinted. Attached when Parent is set, else at Location. */
    UNiagaraComponent* Projectile(UWorld* World, USceneComponent* Parent, const FVector& Location, const FLinearColor& Color,
        const FLinearColor& Color2, float Scale);
    /** One-shot parametric burst (sparks, smoke, motes, light). */
    UNiagaraComponent* Impact(UWorld* World, const FVector& Location, const FLinearColor& Color, const FLinearColor& Color2,
        float Scale, float SmokeAmount = 1.0f, const FVector& Normal = FVector::UpVector);
    /** The villain's smoke/tendril shroud. Amount 0..1+ scales the spawn rates. */
    UNiagaraComponent* Shroud(UWorld* World, USceneComponent* Parent, FName Socket, const FVector& Offset, float Scale, float Amount);
    void SetShroudAmount(UNiagaraComponent* Shroud, float Amount);

    void Sound(UWorld* World, USoundBase* Sound, const FVector& Location, float Volume = 1.0f, float Pitch = 1.0f);
    void Sound2D(UWorld* World, USoundBase* Sound, float Volume = 1.0f, float Pitch = 1.0f);
    /** The visible mesh with a head bone: the NPC system's body mesh, else the character mesh, else any visible one. */
    USkeletalMeshComponent* HeadMesh(AActor* Actor);
    /** A voice line from the speaker's head (3D, follows it; audio's attenuation decides the falloff). */
    void Voice(UWorld* World, USoundBase* Sound, AActor* Speaker, float Volume = 1.0f);
    void VoiceOn(USoundBase* Sound, USceneComponent* Head, FName Socket, float Volume = 1.0f);
    /** Dips the music under a stinger (audio's SMX_Jam_StingerDuck releases itself after 3.5 s). */
    void Duck(UWorld* World);

    /** Damage the way spells do: ICombatDamageable first, else point damage through TakeDamage. */
    void Damage(AActor* Target, float Amount, AActor* Causer, const FVector& From, float Push, TSubclassOf<UDamageType> Type);

    /** Health > 0 (UReflectionsHealthComponent), or no health component at all. */
    bool IsAlive(const AActor* Actor);

    /** The local player's pawn, or null. */
    APawn* PlayerPawn(const UWorld* World);

    /** Ground under a point (visibility trace), or the point itself. */
    FVector Ground(UWorld* World, const FVector& Point, const AActor* Ignore = nullptr, float Up = 300.0f, float Down = 3000.0f);

    /** On-screen line through the villain HUD and the world-jump message line. */
    void Message(UWorld* World, const FText& Text, const FLinearColor& Color = ReflectionsVillainColors::Lilac);
}
