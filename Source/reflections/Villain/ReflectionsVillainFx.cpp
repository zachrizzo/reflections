#include "Villain/ReflectionsVillainFx.h"

#include "Villain/ReflectionsVillainConfig.h"
#include "Villain/ReflectionsVillainSubsystem.h"

#include "Hero/ReflectionsSpellCombat.h"
#include "Interfaces/CombatDamageable.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/DamageType.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "Sound/SoundBase.h"
#include "Sound/SoundMix.h"

namespace
{
    TAutoConsoleVariable<int32> CVarAutoStart(TEXT("Villain.AutoStart"), 1,
        TEXT("0: the villain never starts by itself. 1: starts in maps with world anchors or a villain arena. 2: every game map."));
    TAutoConsoleVariable<float> CVarStartDelay(TEXT("Villain.StartDelay"), 20.0f, TEXT("Seconds after map start before the villain takes his first host."));
    TAutoConsoleVariable<float> CVarHostLifetime(TEXT("Villain.HostLifetime"), 28.0f, TEXT("Seconds a host lasts before it burns out and he hops."));
    TAutoConsoleVariable<float> CVarInfectInterval(TEXT("Villain.InfectInterval"), 16.0f, TEXT("Seconds between infections spread by the host."));
    TAutoConsoleVariable<float> CVarInfectRadius(TEXT("Villain.InfectRadius"), 2200.0f, TEXT("How far (cm) a host reaches to infect another NPC."));
    TAutoConsoleVariable<float> CVarHopRadius(TEXT("Villain.HopRadius"), 4000.0f, TEXT("Preferred distance (cm) for a hop to a fresh host."));
    TAutoConsoleVariable<float> CVarConvertInterval(TEXT("Villain.ConvertInterval"), 85.0f,
        TEXT("Seconds between tackle conversions (the first two come at about 40% of it; each page found shortens it 10%, to 70%). "
             "About 25 minutes to a full meter if the player ignores the Tarnish."));
    TAutoConsoleVariable<float> CVarSeedRadius(TEXT("Villain.SeedRadius"), 9000.0f, TEXT("Search radius (cm) around the player when no host is near."));
    TAutoConsoleVariable<float> CVarRiftDelay(TEXT("Villain.RiftDelay"), 9.0f, TEXT("Seconds after infection before an infected NPC may be sent to another side."));
    TAutoConsoleVariable<float> CVarRiftChance(TEXT("Villain.RiftChance"), 0.6f, TEXT("Chance an infected NPC is sent to another side (world-jump maps only)."));
    TAutoConsoleVariable<int32> CVarKillHosts(TEXT("Villain.KillHostsOnBurnout"), 1, TEXT("1: a burnt-out host dies (damage). 0: it is left scorched."));
    TAutoConsoleVariable<float> CVarBossHealth(TEXT("Villain.BossHealth"), 1250.0f, TEXT("Health of his true form."));
    TAutoConsoleVariable<float> CVarFinalDamage(TEXT("Villain.FinalSpellDamage"), 125.0f, TEXT("Damage of one Final Spell hit."));
    TAutoConsoleVariable<float> CVarOtherScale(TEXT("Villain.OtherSpellScale"), 0.03f, TEXT("Fraction of damage his true form takes from anything but the Final Spell."));
    TAutoConsoleVariable<float> CVarFinalMana(TEXT("Villain.FinalSpellMana"), 20.0f, TEXT("Mana cost of the Final Spell."));
    TAutoConsoleVariable<float> CVarFinalCooldown(TEXT("Villain.FinalSpellCooldown"), 1.2f, TEXT("Cooldown of the Final Spell (s)."));
    TAutoConsoleVariable<float> CVarManifestRadius(TEXT("Villain.ManifestRadius"), 3200.0f, TEXT("He manifests when the player comes this close (cm, across the ground; capped at the arena radius + 8 m, and within 6 m of its height) to the arena."));
    TAutoConsoleVariable<float> CVarAttackDamage(TEXT("Villain.AttackDamageScale"), 0.4f, TEXT("Scales the damage of his attacks."));
    TAutoConsoleVariable<float> CVarTelegraph(TEXT("Villain.TelegraphScale"), 1.0f, TEXT("Scales every attack telegraph (bigger = easier)."));
    TAutoConsoleVariable<int32> CVarRangedSpread(TEXT("Villain.RangedSpread"), 0, TEXT("0 (default): only tackles convert (the NPC system calls BeginConversion). 1: hosts also infect at range with a wisp (test maps without the NPC hunt)."));
    TAutoConsoleVariable<int32> CVarVeinOverlay(TEXT("Villain.VeinOverlay"), 0, TEXT("1: violet veins over tarnished bodies. 0: black eyes and aura only."));
    TAutoConsoleVariable<int32> CVarMaxInfected(TEXT("Villain.MaxInfected"), 30, TEXT("He stops spreading while this many NPCs are infected."));
}

int32 ReflectionsVillainTuning::AutoStart() { return CVarAutoStart.GetValueOnGameThread(); }
float ReflectionsVillainTuning::StartDelay() { return FMath::Max(0.0f, CVarStartDelay.GetValueOnGameThread()); }
float ReflectionsVillainTuning::HostLifetime() { return FMath::Max(3.0f, CVarHostLifetime.GetValueOnGameThread()); }
float ReflectionsVillainTuning::InfectInterval() { return FMath::Max(1.0f, CVarInfectInterval.GetValueOnGameThread()); }
float ReflectionsVillainTuning::InfectRadius() { return FMath::Max(100.0f, CVarInfectRadius.GetValueOnGameThread()); }
float ReflectionsVillainTuning::HopRadius() { return FMath::Max(100.0f, CVarHopRadius.GetValueOnGameThread()); }
float ReflectionsVillainTuning::ConvertInterval() { return FMath::Max(5.0f, CVarConvertInterval.GetValueOnGameThread()); }
float ReflectionsVillainTuning::SeedRadius() { return FMath::Max(100.0f, CVarSeedRadius.GetValueOnGameThread()); }
float ReflectionsVillainTuning::RiftDelay() { return FMath::Max(0.5f, CVarRiftDelay.GetValueOnGameThread()); }
float ReflectionsVillainTuning::RiftChance() { return FMath::Clamp(CVarRiftChance.GetValueOnGameThread(), 0.0f, 1.0f); }
bool ReflectionsVillainTuning::KillHostsOnBurnout() { return CVarKillHosts.GetValueOnGameThread() != 0; }
float ReflectionsVillainTuning::BossHealth() { return FMath::Max(1.0f, CVarBossHealth.GetValueOnGameThread()); }
float ReflectionsVillainTuning::FinalSpellDamage() { return FMath::Max(0.0f, CVarFinalDamage.GetValueOnGameThread()); }
float ReflectionsVillainTuning::OtherSpellScale() { return FMath::Clamp(CVarOtherScale.GetValueOnGameThread(), 0.0f, 1.0f); }
float ReflectionsVillainTuning::FinalSpellManaCost() { return FMath::Max(0.0f, CVarFinalMana.GetValueOnGameThread()); }
float ReflectionsVillainTuning::FinalSpellCooldown() { return FMath::Max(0.1f, CVarFinalCooldown.GetValueOnGameThread()); }
float ReflectionsVillainTuning::ManifestRadius() { return FMath::Max(200.0f, CVarManifestRadius.GetValueOnGameThread()); }
float ReflectionsVillainTuning::AttackDamageScale() { return FMath::Max(0.0f, CVarAttackDamage.GetValueOnGameThread()); }
float ReflectionsVillainTuning::TelegraphScale() { return FMath::Clamp(CVarTelegraph.GetValueOnGameThread(), 0.3f, 3.0f); }
bool ReflectionsVillainTuning::RangedSpread() { return CVarRangedSpread.GetValueOnGameThread() != 0; }
bool ReflectionsVillainTuning::VeinOverlay() { return CVarVeinOverlay.GetValueOnGameThread() != 0; }
int32 ReflectionsVillainTuning::MaxInfected() { return FMath::Max(1, CVarMaxInfected.GetValueOnGameThread()); }

UNiagaraComponent* ReflectionsVillainFx::Projectile(UWorld* World, USceneComponent* Parent, const FVector& Location,
    const FLinearColor& Color, const FLinearColor& Color2, float Scale)
{
    UNiagaraSystem* System = ReflectionsVillainAssets::ProjectileFX();
    if (!World || !System)
    {
        return nullptr;
    }
    UNiagaraComponent* Component = Parent
        ? UNiagaraFunctionLibrary::SpawnSystemAttached(System, Parent, NAME_None, FVector::ZeroVector, FRotator::ZeroRotator,
            EAttachLocation::SnapToTarget, true)
        : UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, Location, FRotator::ZeroRotator, FVector(1.0f), true);
    if (Component)
    {
        Component->SetVariableLinearColor(TEXT("User.Color"), Color);
        Component->SetVariableLinearColor(TEXT("User.Color2"), Color2);
        Component->SetVariableFloat(TEXT("User.Scale"), Scale);
        Component->SetVariableFloat(TEXT("User.CoreSize"), 34.0f);
        Component->SetVariableFloat(TEXT("User.SparkRate"), 60.0f * Scale);
        Component->SetVariableFloat(TEXT("User.SparkGravity"), 60.0f);
        Component->SetVariableFloat(TEXT("User.Turbulence"), 320.0f);
        Component->SetVariableFloat(TEXT("User.Jitter"), 4.0f);
        Component->SetVariableFloat(TEXT("User.Swirl"), 40.0f);
        Component->SetVariableFloat(TEXT("User.ArcRate"), 0.0f);
        Component->SetVariableFloat(TEXT("User.TrailWidth"), 16.0f);
    }
    return Component;
}

UNiagaraComponent* ReflectionsVillainFx::Impact(UWorld* World, const FVector& Location, const FLinearColor& Color,
    const FLinearColor& Color2, float Scale, float SmokeAmount, const FVector& Normal)
{
    UNiagaraSystem* System = ReflectionsVillainAssets::ImpactFX();
    if (!World || !System)
    {
        return nullptr;
    }
    UNiagaraComponent* Burst = UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, Location, FRotator::ZeroRotator,
        FVector(1.0f), true);
    if (Burst)
    {
        Burst->SetVariableLinearColor(TEXT("User.Color"), Color);
        Burst->SetVariableLinearColor(TEXT("User.Color2"), Color2);
        Burst->SetVariableVec3(TEXT("User.Normal"), Normal.GetSafeNormal());
        Burst->SetVariableFloat(TEXT("User.Scale"), Scale);
        Burst->SetVariableFloat(TEXT("User.Turbulence"), 300.0f);
        Burst->SetVariableFloat(TEXT("User.SparkGravity"), -400.0f);
        Burst->SetVariableFloat(TEXT("User.SparkCount"), FMath::RoundToFloat(40.0f * FMath::Sqrt(Scale)));
        Burst->SetVariableFloat(TEXT("User.DebrisCount"), 0.0f);
        Burst->SetVariableFloat(TEXT("User.DebrisMesh"), 0.0f);
        Burst->SetVariableLinearColor(TEXT("User.DebrisColor"), FLinearColor(0.02f, 0.02f, 0.03f));
        Burst->SetVariableFloat(TEXT("User.SmokeCount"), FMath::RoundToFloat(14.0f * SmokeAmount * FMath::Min(Scale, 3.0f)));
        Burst->SetVariableLinearColor(TEXT("User.SmokeColor"), ReflectionsVillainColors::Smoke);
        Burst->SetVariableFloat(TEXT("User.FlameCount"), 0.0f);
        Burst->SetVariableFloat(TEXT("User.ArcCount"), 0.0f);
        Burst->SetVariableFloat(TEXT("User.MoteCount"), FMath::RoundToFloat(30.0f * FMath::Sqrt(Scale)));
        Burst->SetVariableFloat(TEXT("User.LightScale"), 1.0f);
    }
    return Burst;
}

UNiagaraComponent* ReflectionsVillainFx::Shroud(UWorld* World, USceneComponent* Parent, FName Socket, const FVector& Offset,
    float Scale, float Amount)
{
    UNiagaraSystem* System = ReflectionsVillainAssets::ShroudFX();
    if (!World || !System)
    {
        return nullptr;
    }
    UNiagaraComponent* Component = Parent
        ? UNiagaraFunctionLibrary::SpawnSystemAttached(System, Parent, Socket, Offset, FRotator::ZeroRotator,
            EAttachLocation::KeepRelativeOffset, false)
        : UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, Offset, FRotator::ZeroRotator, FVector(1.0f), true);
    if (Component)
    {
        Component->SetVariableFloat(TEXT("User.Scale"), Scale);
        Component->SetVariableLinearColor(TEXT("User.Color"), ReflectionsVillainColors::Violet);
        SetShroudAmount(Component, Amount);
    }
    return Component;
}

void ReflectionsVillainFx::SetShroudAmount(UNiagaraComponent* Shroud, float Amount)
{
    if (Shroud)
    {
        Shroud->SetVariableFloat(TEXT("User.Amount"), FMath::Max(0.0f, Amount));
    }
}

void ReflectionsVillainFx::Sound(UWorld* World, USoundBase* Sound, const FVector& Location, float Volume, float Pitch)
{
    if (World && Sound)
    {
        UGameplayStatics::PlaySoundAtLocation(World, Sound, Location, Volume, Pitch);
    }
}

void ReflectionsVillainFx::Sound2D(UWorld* World, USoundBase* Sound, float Volume, float Pitch)
{
    if (World && Sound)
    {
        UGameplayStatics::PlaySound2D(World, Sound, Volume, Pitch);
    }
}

USkeletalMeshComponent* ReflectionsVillainFx::HeadMesh(AActor* Actor)
{
    static const FName Head(TEXT("head"));
    if (!IsValid(Actor))
    {
        return nullptr;
    }
    auto Usable = [](USkeletalMeshComponent* Mesh)
    {
        return Mesh && Mesh->GetSkinnedAsset() && Mesh->IsVisible() && !Mesh->bHiddenInGame && Mesh->GetBoneIndex(Head) != INDEX_NONE;
    };
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Actor))
    {
        if (UReflectionsNpcReactionComponent* Npc = Npcs->FindNpc(Actor))
        {
            if (USkeletalMeshComponent* Body = Npc->GetBodyMesh(); Usable(Body))
            {
                return Body;
            }
        }
    }
    if (ACharacter* Character = Cast<ACharacter>(Actor))
    {
        if (Usable(Character->GetMesh()))
        {
            return Character->GetMesh();
        }
    }
    TArray<USkeletalMeshComponent*> Meshes;
    Actor->GetComponents<USkeletalMeshComponent>(Meshes);
    for (USkeletalMeshComponent* Mesh : Meshes)
    {
        if (Usable(Mesh))
        {
            return Mesh;
        }
    }
    return nullptr;
}

void ReflectionsVillainFx::VoiceOn(USoundBase* Sound, USceneComponent* Head, FName Socket, float Volume)
{
    if (Sound && Head)
    {
        UGameplayStatics::SpawnSoundAttached(Sound, Head, Socket, FVector::ZeroVector, EAttachLocation::SnapToTarget, true, Volume);
    }
}

void ReflectionsVillainFx::Voice(UWorld* World, USoundBase* Sound, AActor* Speaker, float Volume)
{
    if (!World || !Sound || !IsValid(Speaker))
    {
        return;
    }
    if (USkeletalMeshComponent* Head = HeadMesh(Speaker))
    {
        VoiceOn(Sound, Head, TEXT("head"), Volume);
    }
    else
    {
        VoiceOn(Sound, Speaker->GetRootComponent(), NAME_None, Volume);
    }
}

void ReflectionsVillainFx::Duck(UWorld* World)
{
    if (USoundMix* Mix = World ? ReflectionsVillainAssets::StingerDuck() : nullptr)
    {
        UGameplayStatics::PushSoundMixModifier(World, Mix);
    }
}

void ReflectionsVillainFx::Damage(AActor* Target, float Amount, AActor* Causer, const FVector& From, float Push,
    TSubclassOf<UDamageType> Type)
{
    if (!IsValid(Target) || Amount <= 0.0f)
    {
        return;
    }
    const FVector Direction = (Target->GetActorLocation() - From).GetSafeNormal();
    if (ICombatDamageable* Damageable = Cast<ICombatDamageable>(Target))
    {
        Damageable->ApplyDamage(Amount, Causer, Target->GetActorLocation(), Direction * Push);
    }
    else
    {
        FHitResult Hit(Target, Cast<UPrimitiveComponent>(Target->GetRootComponent()), Target->GetActorLocation(), -Direction);
        UGameplayStatics::ApplyPointDamage(Target, Amount, Direction, Hit, nullptr, Causer,
            Type ? Type : TSubclassOf<UDamageType>(UDamageType::StaticClass()));
    }
    if (Push > 0.0f)
    {
        if (ACharacter* Character = Cast<ACharacter>(Target))
        {
            Character->LaunchCharacter(Direction.GetSafeNormal2D() * Push + FVector(0.0f, 0.0f, Push * 0.35f), true, true);
        }
    }
}

bool ReflectionsVillainFx::IsAlive(const AActor* Actor)
{
    if (!IsValid(Actor))
    {
        return false;
    }
    if (const UReflectionsHealthComponent* Health = Actor->FindComponentByClass<UReflectionsHealthComponent>())
    {
        return Health->Health > 0.0f;
    }
    return true;
}

APawn* ReflectionsVillainFx::PlayerPawn(const UWorld* World)
{
    if (!World)
    {
        return nullptr;
    }
    const APlayerController* PC = World->GetFirstPlayerController();
    return PC ? PC->GetPawn() : nullptr;
}

FVector ReflectionsVillainFx::Ground(UWorld* World, const FVector& Point, const AActor* Ignore, float Up, float Down)
{
    if (!World)
    {
        return Point;
    }
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(VillainGround), false, Ignore);
    if (APawn* Player = PlayerPawn(World))
    {
        Params.AddIgnoredActor(Player);
    }
    if (World->LineTraceSingleByChannel(Hit, Point + FVector(0.0f, 0.0f, Up), Point - FVector(0.0f, 0.0f, Down), ECC_Visibility, Params))
    {
        return Hit.ImpactPoint;
    }
    return Point;
}

void ReflectionsVillainFx::Message(UWorld* World, const FText& Text, const FLinearColor& Color)
{
    if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(World))
    {
        Villain->ShowMessage(Text, Color);
    }
}
