#include "SpellVFX/ReflectionsSpellVfxSubsystem.h"
#include "Hero/ReflectionsSpellAim.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "Interfaces/CombatDamageable.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "TimerManager.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundBase.h"

namespace
{
    const TCHAR* SystemsFolder = TEXT("/Game/Characters/Hero/SpellVFX/Systems/");

    /** Everything that makes an element look like itself, fed to the shared systems' User.* parameters. */
    struct FElementStyle
    {
        FLinearColor Color;
        FLinearColor Color2;
        // In flight.
        float CoreSize;
        float SparkRate;
        float SparkGravity;
        float Turbulence;
        float Jitter;
        float Swirl;
        float ArcRate;
        float TrailWidth;
        // On impact.
        float SparkCount;
        float ImpactGravity;
        float DebrisCount;
        float DebrisMesh;
        FLinearColor DebrisColor;
        float SmokeCount;
        FLinearColor SmokeColor;
        float FlameCount;
        float ArcCount;
        float MoteCount;
    };

    const FElementStyle& StyleFor(EReflectionsSpellElement Element)
    {
        // Fire: embers rise, black smoke and a flame bloom.
        static const FElementStyle Fire{
            {1.0f, 0.28f, 0.04f, 1.0f}, {1.0f, 0.78f, 0.35f, 1.0f},
            36.0f, 95.0f, 190.0f, 320.0f, 0.0f, 0.0f, 0.0f, 22.0f,
            70.0f, -700.0f, 0.0f, 0.0f, {0.1f, 0.05f, 0.02f, 1.0f}, 10.0f, {0.07f, 0.06f, 0.055f, 0.6f}, 26.0f, 0.0f, 22.0f};
        // Water: a helix of droplets, heavy falling spray and pale mist.
        static const FElementStyle Water{
            {0.08f, 0.42f, 1.0f, 1.0f}, {0.6f, 0.9f, 1.0f, 1.0f},
            30.0f, 75.0f, -900.0f, 90.0f, 0.0f, 45.0f, 0.0f, 24.0f,
            95.0f, -1300.0f, 0.0f, 0.0f, {0.1f, 0.3f, 0.6f, 1.0f}, 8.0f, {0.6f, 0.75f, 0.85f, 0.32f}, 0.0f, 0.0f, 12.0f};
        // Ice: thin bright trail, frost dust and shattering crystal shards.
        static const FElementStyle Ice{
            {0.45f, 0.8f, 1.0f, 1.0f}, {0.85f, 0.97f, 1.0f, 1.0f},
            24.0f, 55.0f, -300.0f, 60.0f, 0.0f, 0.0f, 0.0f, 14.0f,
            50.0f, -900.0f, 16.0f, 1.0f, {0.55f, 0.82f, 1.0f, 1.0f}, 6.0f, {0.78f, 0.9f, 1.0f, 0.35f}, 0.0f, 0.0f, 26.0f};
        // Lightning: crackling, jittered trail with snapping arcs.
        static const FElementStyle Lightning{
            {0.42f, 0.5f, 1.0f, 1.0f}, {0.85f, 0.9f, 1.0f, 1.0f},
            26.0f, 60.0f, -250.0f, 120.0f, 14.0f, 0.0f, 170.0f, 10.0f,
            60.0f, -500.0f, 0.0f, 0.0f, {0.2f, 0.2f, 0.3f, 1.0f}, 3.0f, {0.3f, 0.32f, 0.4f, 0.3f}, 0.0f, 24.0f, 10.0f};
        // Earth: heavy dust and tumbling rock chunks.
        static const FElementStyle Earth{
            {0.85f, 0.52f, 0.22f, 1.0f}, {1.0f, 0.8f, 0.5f, 1.0f},
            30.0f, 45.0f, -1100.0f, 40.0f, 0.0f, 0.0f, 0.0f, 16.0f,
            32.0f, -1200.0f, 24.0f, 0.0f, {0.24f, 0.18f, 0.13f, 0.12f}, 12.0f, {0.34f, 0.27f, 0.2f, 0.55f}, 0.0f, 0.0f, 0.0f};
        // Arcane: swirling motes and a violet bloom.
        static const FElementStyle Arcane{
            {0.68f, 0.22f, 1.0f, 1.0f}, {0.95f, 0.72f, 1.0f, 1.0f},
            30.0f, 75.0f, 0.0f, 480.0f, 0.0f, 130.0f, 0.0f, 18.0f,
            50.0f, -200.0f, 0.0f, 0.0f, {0.3f, 0.1f, 0.4f, 1.0f}, 0.0f, {0.3f, 0.2f, 0.4f, 0.3f}, 0.0f, 0.0f, 44.0f};
        // Life and air fall back to soft gold/green.
        static const FElementStyle Life{
            {1.0f, 0.72f, 0.28f, 1.0f}, {0.35f, 1.0f, 0.5f, 1.0f},
            30.0f, 60.0f, 60.0f, 300.0f, 0.0f, 60.0f, 0.0f, 16.0f,
            40.0f, -300.0f, 0.0f, 0.0f, {0.3f, 0.3f, 0.2f, 1.0f}, 0.0f, {0.6f, 0.7f, 0.5f, 0.3f}, 0.0f, 0.0f, 36.0f};
        switch (Element)
        {
        case EReflectionsSpellElement::Fire: return Fire;
        case EReflectionsSpellElement::Water: return Water;
        case EReflectionsSpellElement::Ice: return Ice;
        case EReflectionsSpellElement::Lightning: return Lightning;
        case EReflectionsSpellElement::Earth: return Earth;
        case EReflectionsSpellElement::Arcane: return Arcane;
        default: return Life;
        }
    }

    UNiagaraSystem* LoadSystem(const TCHAR* Name)
    {
        return LoadObject<UNiagaraSystem>(nullptr, *FString::Printf(TEXT("%s%s.%s"), SystemsFolder, Name, Name));
    }

    void SetColors(UNiagaraComponent* Component, const FElementStyle& Style)
    {
        Component->SetVariableLinearColor(TEXT("User.Color"), Style.Color);
        Component->SetVariableLinearColor(TEXT("User.Color2"), Style.Color2);
    }

    APlayerController* LocalController(const UWorld* World)
    {
        return World ? World->GetFirstPlayerController() : nullptr;
    }

    bool IsLocalPlayer(const AActor* Actor)
    {
        const APawn* Pawn = Cast<APawn>(Actor);
        return Pawn && Pawn->IsLocallyControlled() && Pawn->IsPlayerControlled();
    }

    /** Jam SoundCues (/Game/Audio/Jam/Cues, owned by the audio session; referenced only). Rooted once so they stay loaded. */
    USoundBase* JamCue(const TCHAR* Name)
    {
        USoundBase* Sound = LoadObject<USoundBase>(nullptr, *FString::Printf(TEXT("/Game/Audio/Jam/Cues/%s.%s"), Name, Name));
        if (Sound && !Sound->IsRooted())
        {
            Sound->AddToRoot();
        }
        return Sound;
    }

    const TCHAR* ElementCue(EReflectionsSpellElement Element, bool bImpact)
    {
        switch (Element)
        {
        case EReflectionsSpellElement::Fire: return bImpact ? TEXT("SCue_Fire_Impact") : TEXT("SCue_Fire_Cast");
        case EReflectionsSpellElement::Water: return bImpact ? TEXT("SCue_Water_Impact") : TEXT("SCue_Water_Cast");
        case EReflectionsSpellElement::Ice: return bImpact ? TEXT("SCue_Ice_Impact") : TEXT("SCue_Ice_Cast");
        case EReflectionsSpellElement::Lightning: return bImpact ? TEXT("SCue_Lightning_Impact") : TEXT("SCue_Lightning_Cast");
        case EReflectionsSpellElement::Earth: return bImpact ? TEXT("SCue_Earth_Impact") : TEXT("SCue_Earth_Cast");
        case EReflectionsSpellElement::Arcane: return bImpact ? TEXT("SCue_Arcane_Impact") : TEXT("SCue_Arcane_Cast");
        default: return nullptr;
        }
    }

    void PlayElementCue(const UObject* WorldContext, EHeroSpell Spell, const FVector& Location, bool bImpact)
    {
        if (!ReflectionsSpellCatalog::IsValid(Spell)) return;
        if (const TCHAR* Name = ElementCue(ReflectionsSpellCatalog::Get(Spell).Element, bImpact))
        {
            if (USoundBase* Sound = JamCue(Name))
            {
                UGameplayStatics::PlaySoundAtLocation(WorldContext, Sound, Location);
            }
        }
    }

    /** Attached loop that fades out on its own after Seconds. */
    void PlayTimedLoop(UObject* WorldContext, const TCHAR* Name, USceneComponent* Attach, float Seconds)
    {
        UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
        USoundBase* Sound = JamCue(Name);
        if (!World || !Sound || !Attach) return;
        if (UAudioComponent* Loop = UGameplayStatics::SpawnSoundAttached(Sound, Attach))
        {
            TWeakObjectPtr<UAudioComponent> Weak(Loop);
            FTimerHandle Handle;
            World->GetTimerManager().SetTimer(Handle, FTimerDelegate::CreateWeakLambda(WorldContext, [Weak]()
            {
                if (Weak.IsValid()) Weak->FadeOut(0.3f, 0.0f);
            }), FMath::Max(0.1f, Seconds), false);
        }
    }
}

bool UReflectionsSpellVfxSubsystem::DoesSupportWorldType(EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UReflectionsSpellVfxSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    if (InWorld.GetNetMode() == NM_DedicatedServer) return;
    ProjectileSystem = LoadSystem(TEXT("NS_Spell_Projectile"));
    ImpactSystem = LoadSystem(TEXT("NS_Spell_Impact"));
    HealSystem = LoadSystem(TEXT("NS_Spell_Heal"));
    WardSystem = LoadSystem(TEXT("NS_Spell_Ward"));
    BloodImpact = LoadObject<UNiagaraSystem>(nullptr, TEXT("/Game/Blueprints/Combat/Blood/NS_BloodImpact.NS_BloodImpact"));
    BloodSpatter = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Blueprints/Combat/Blood/M_BloodSpatter.M_BloodSpatter"));
    UE_CLOG(!ProjectileSystem || !ImpactSystem || !HealSystem, LogTemp, Warning,
        TEXT("Spell VFX: run Tools/SpellVFX/build_spell_niagara.py; some systems under %s are missing."), SystemsFolder);
    if (UReflectionsSpellEventSubsystem* Events = InWorld.GetSubsystem<UReflectionsSpellEventSubsystem>())
    {
        Events->OnSpellHit.AddUniqueDynamic(this, &UReflectionsSpellVfxSubsystem::OnSpellHit);
        Events->OnSupportSpellVisual.AddUniqueDynamic(this, &UReflectionsSpellVfxSubsystem::OnSupportVisual);
        Events->OnDirectionalSpellVisual.AddUniqueDynamic(this, &UReflectionsSpellVfxSubsystem::OnDirectionalVisual);
        Events->OnSpellImpactVisual.AddUniqueDynamic(this, &UReflectionsSpellVfxSubsystem::OnImpactVisual);
        Events->OnSpellReleaseVisual.AddUniqueDynamic(this, &UReflectionsSpellVfxSubsystem::OnReleaseVisual);
    }
    SpawnHandle = InWorld.AddOnActorSpawnedHandler(FOnActorSpawned::FDelegate::CreateUObject(this, &UReflectionsSpellVfxSubsystem::OnActorSpawned));
}

void UReflectionsSpellVfxSubsystem::Deinitialize()
{
    if (UWorld* World = GetWorld())
    {
        if (SpawnHandle.IsValid()) World->RemoveOnActorSpawnedHandler(SpawnHandle);
        World->GetTimerManager().ClearTimer(HitStopTimer);
        if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
        {
            Events->OnSpellHit.RemoveDynamic(this, &UReflectionsSpellVfxSubsystem::OnSpellHit);
            Events->OnSupportSpellVisual.RemoveDynamic(this, &UReflectionsSpellVfxSubsystem::OnSupportVisual);
            Events->OnDirectionalSpellVisual.RemoveDynamic(this, &UReflectionsSpellVfxSubsystem::OnDirectionalVisual);
            Events->OnSpellImpactVisual.RemoveDynamic(this, &UReflectionsSpellVfxSubsystem::OnImpactVisual);
            Events->OnSpellReleaseVisual.RemoveDynamic(this, &UReflectionsSpellVfxSubsystem::OnReleaseVisual);
        }
    }
    Super::Deinitialize();
}

void UReflectionsSpellVfxSubsystem::OnActorSpawned(AActor* Actor)
{
    AReflectionsSpellProjectile* Projectile = Cast<AReflectionsSpellProjectile>(Actor);
    if (!Projectile || !GetWorld()) return;
    // Deferred-spawned projectiles receive their spell after the spawn notification.
    TWeakObjectPtr<AReflectionsSpellProjectile> WeakProjectile(Projectile);
    GetWorld()->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateWeakLambda(this, [this, WeakProjectile]()
    {
        AttachProjectileVisual(WeakProjectile);
    }));
}

void UReflectionsSpellVfxSubsystem::AttachProjectileVisual(TWeakObjectPtr<AReflectionsSpellProjectile> WeakProjectile)
{
    AReflectionsSpellProjectile* Projectile = WeakProjectile.Get();
    if (!Projectile || !ProjectileSystem || !Projectile->GetRootComponent()) return;
    const EHeroSpell Spell = Projectile->GetSpell();
    if (!ReflectionsSpellCatalog::IsValid(Spell)) return;
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    const FElementStyle& Style = StyleFor(Spec.Element);
    UNiagaraComponent* Visual = UNiagaraFunctionLibrary::SpawnSystemAttached(ProjectileSystem, Projectile->GetRootComponent(), NAME_None,
        FVector::ZeroVector, FRotator::ZeroRotator, EAttachLocation::KeepRelativeOffset, true, false, ENCPoolMethod::AutoRelease, true);
    if (!Visual) return;
    // Blast projectiles (fireball, orb, chain lightning) read bigger in flight.
    const float Scale = FMath::Clamp(0.85f + Spec.Radius / 320.0f, 0.85f, 1.6f);
    SetColors(Visual, Style);
    Visual->SetVariableFloat(TEXT("User.Scale"), Scale);
    Visual->SetVariableFloat(TEXT("User.CoreSize"), Style.CoreSize);
    Visual->SetVariableFloat(TEXT("User.SparkRate"), Style.SparkRate * Scale);
    Visual->SetVariableFloat(TEXT("User.SparkGravity"), Style.SparkGravity);
    Visual->SetVariableFloat(TEXT("User.Turbulence"), Style.Turbulence);
    Visual->SetVariableFloat(TEXT("User.Jitter"), Style.Jitter);
    Visual->SetVariableFloat(TEXT("User.Swirl"), Style.Swirl);
    Visual->SetVariableFloat(TEXT("User.ArcRate"), Style.ArcRate);
    Visual->SetVariableFloat(TEXT("User.TrailWidth"), Style.TrailWidth);
    Visual->Activate(true);
    if (USoundBase* Loop = JamCue(TEXT("SCue_Projectile_Loop")))
    {
        UGameplayStatics::SpawnSoundAttached(Loop, Projectile->GetRootComponent(), NAME_None, FVector::ZeroVector,
            EAttachLocation::KeepRelativeOffset, true);
    }
    Projectile->HideFallbackVisual();
    ProjectileTrails.Add(Projectile, Visual);
    Projectile->OnDestroyed.AddUniqueDynamic(this, &UReflectionsSpellVfxSubsystem::OnProjectileDestroyed);
}

void UReflectionsSpellVfxSubsystem::OnProjectileDestroyed(AActor* Projectile)
{
    TWeakObjectPtr<UNiagaraComponent> Visual;
    if (ProjectileTrails.RemoveAndCopyValue(Projectile, Visual) && Visual.IsValid())
    {
        // Let the trail and embers finish in the world instead of vanishing with the projectile.
        Visual->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
        Visual->Deactivate();
    }
}

void UReflectionsSpellVfxSubsystem::SpawnImpact(EHeroSpell Spell, const FVector& Location, const FVector& Normal, float Scale, bool bMuzzle)
{
    if (!ImpactSystem || !ReflectionsSpellCatalog::IsValid(Spell)) return;
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    const FElementStyle& Style = StyleFor(Spec.Element);
    FVector Up = Normal.GetSafeNormal();
    if (Up.IsNearlyZero()) Up = FVector::UpVector;
    UNiagaraComponent* Burst = UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, ImpactSystem, Location, Up.Rotation(), FVector(1.0f),
        true, false, ENCPoolMethod::AutoRelease, true);
    if (!Burst) return;
    SetColors(Burst, Style);
    Burst->SetVariableVec3(TEXT("User.Normal"), Up);
    Burst->SetVariableFloat(TEXT("User.Scale"), Scale);
    Burst->SetVariableFloat(TEXT("User.Turbulence"), Style.Turbulence);
    Burst->SetVariableFloat(TEXT("User.SparkGravity"), Style.ImpactGravity);
    // A muzzle flash is the same burst without the heavy parts.
    const float Amount = bMuzzle ? 0.25f : 1.0f;
    Burst->SetVariableFloat(TEXT("User.SparkCount"), FMath::RoundToFloat(Style.SparkCount * Amount * FMath::Sqrt(FMath::Max(Scale, 0.3f))));
    Burst->SetVariableFloat(TEXT("User.DebrisCount"), bMuzzle ? 0.0f : FMath::RoundToFloat(Style.DebrisCount * FMath::Min(Scale, 2.0f)));
    Burst->SetVariableFloat(TEXT("User.DebrisMesh"), Style.DebrisMesh);
    Burst->SetVariableLinearColor(TEXT("User.DebrisColor"), Style.DebrisColor);
    Burst->SetVariableFloat(TEXT("User.SmokeCount"), bMuzzle ? 0.0f : FMath::RoundToFloat(Style.SmokeCount * FMath::Min(Scale, 2.5f)));
    Burst->SetVariableLinearColor(TEXT("User.SmokeColor"), Style.SmokeColor);
    Burst->SetVariableFloat(TEXT("User.FlameCount"), FMath::RoundToFloat(Style.FlameCount * Amount * FMath::Min(Scale, 2.5f)));
    Burst->SetVariableFloat(TEXT("User.ArcCount"), FMath::RoundToFloat(Style.ArcCount * Amount * FMath::Min(Scale, 2.0f)));
    Burst->SetVariableFloat(TEXT("User.MoteCount"), FMath::RoundToFloat(Style.MoteCount * Amount));
    Burst->SetVariableFloat(TEXT("User.LightScale"), bMuzzle ? 0.35f : 1.0f);
    Burst->Activate(true);
}

void UReflectionsSpellVfxSubsystem::OnImpactVisual(EHeroSpell Spell, FVector Location, FVector Normal, AActor* Caster, float Scale)
{
    SpawnImpact(Spell, Location, Normal, FMath::Clamp(Scale, 0.5f, 3.0f), false);
    PlayElementCue(this, Spell, Location, true);
    ShakeNear(Location, FMath::Clamp(Scale, 0.5f, 2.0f) * (IsLocalPlayer(Caster) ? 0.2f : 0.12f));
}

void UReflectionsSpellVfxSubsystem::OnReleaseVisual(EHeroSpell Spell, FVector Location, FVector Direction, AActor* Caster, float Scale)
{
    // Keep the hand flash small: it sits right in front of the over-the-shoulder camera.
    SpawnImpact(Spell, Location, Direction, FMath::Min(Scale, 0.35f), true);
    PlayElementCue(this, Spell, Location, false);
    if (IsLocalPlayer(Caster))
    {
        if (UReflectionsSpellAimComponent* Aim = Caster->FindComponentByClass<UReflectionsSpellAimComponent>())
        {
            Aim->NotifyCast();
        }
    }
}

void UReflectionsSpellVfxSubsystem::OnDirectionalVisual(EHeroSpell Spell, FVector Location, FVector Direction, AActor* Caster, float Intensity)
{
    if (Spell != EHeroSpell::TidalSurge && Spell != EHeroSpell::ForcePush) return;
    UWorld* World = GetWorld();
    Direction = Direction.GetSafeNormal2D();
    if (!World || Direction.IsNearlyZero()) return;
    // A travelling wave: forward-facing bursts that march out over a fifth of a second.
    const float Radius = ReflectionsSpellCatalog::Get(Spell).Radius;
    const FVector Base = Location - FVector(0.0f, 0.0f, 50.0f);
    for (int32 Step = 0; Step < 4; ++Step)
    {
        const FVector Point = Base + Direction * Radius * (0.25f + 0.22f * Step);
        const float Scale = 0.75f + 0.18f * Step;
        auto Fire = [this, Spell, Point, Direction, Scale]() { SpawnImpact(Spell, Point, Direction, Scale, false); };
        if (Step == 0)
        {
            Fire();
            continue;
        }
        FTimerHandle Handle;
        World->GetTimerManager().SetTimer(Handle, FTimerDelegate::CreateWeakLambda(this, Fire), 0.06f * Step, false);
    }
    PlayElementCue(this, Spell, Base + Direction * Radius * 0.4f, true);
    ShakeNear(Location, IsLocalPlayer(Caster) ? 0.35f : 0.2f);
}

void UReflectionsSpellVfxSubsystem::OnSupportVisual(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity)
{
    if (!Caster || !ReflectionsSpellCatalog::IsValid(Spell)) return;
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    if (USceneComponent* SoundRoot = Caster->GetRootComponent())
    {
        if (Spec.Delivery == EReflectionsSpellDelivery::Heal)
        {
            if (USoundBase* Shimmer = JamCue(TEXT("SCue_Heal_Shimmer"))) UGameplayStatics::PlaySoundAtLocation(this, Shimmer, Caster->GetActorLocation());
        }
        else if (Spec.Delivery == EReflectionsSpellDelivery::Ward)
        {
            if (USoundBase* Up = JamCue(TEXT("SCue_Shield_Up"))) UGameplayStatics::PlaySoundAtLocation(this, Up, Caster->GetActorLocation());
            PlayTimedLoop(this, TEXT("SCue_Shield_Loop"), SoundRoot, 8.0f);  // UReflectionsHealthComponent shields last 8 s.
        }
        else if (Spec.Delivery == EReflectionsSpellDelivery::Hover)
        {
            if (USoundBase* Start = JamCue(TEXT("SCue_Levitation_Start"))) UGameplayStatics::PlaySoundAtLocation(this, Start, Caster->GetActorLocation());
            PlayTimedLoop(this, TEXT("SCue_Levitation_Loop"), SoundRoot, 2.4f);  // Hover lasts to frame 112 of the 30 fps clip.
        }
    }
    UNiagaraSystem* System = Spec.Delivery == EReflectionsSpellDelivery::Ward ? WardSystem.Get()
        : Spec.Delivery == EReflectionsSpellDelivery::Heal ? HealSystem.Get() : nullptr;
    USceneComponent* Root = Caster->GetRootComponent();
    if (!System || !Root) return;
    float FeetOffset = 90.0f;
    if (const ACharacter* Character = Cast<ACharacter>(Caster))
    {
        FeetOffset = Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
    }
    UNiagaraComponent* Aura = UNiagaraFunctionLibrary::SpawnSystemAttached(System, Root, NAME_None, FVector(0.0f, 0.0f, -FeetOffset),
        FRotator::ZeroRotator, EAttachLocation::KeepRelativeOffset, true, false, ENCPoolMethod::AutoRelease, true);
    if (!Aura) return;
    if (Spec.Delivery == EReflectionsSpellDelivery::Heal)
    {
        // Greater Heal is a taller, denser column; Healing Pulse throws a wide ring to its full radius.
        const float Scale = Spec.Radius > 0.0f ? 1.3f : Spec.Power >= 60.0f ? 1.6f : 1.0f;
        Aura->SetVariableFloat(TEXT("User.Scale"), Scale);
        Aura->SetVariableFloat(TEXT("User.Radius"), Spec.Radius);
        SetColors(Aura, StyleFor(EReflectionsSpellElement::Life));
    }
    else
    {
        Aura->SetVariableFloat(TEXT("User.Scale"), 1.0f);
        Aura->SetVariableLinearColor(TEXT("User.Color"), FLinearColor(0.55f, 0.3f, 1.0f));
        Aura->SetVariableLinearColor(TEXT("User.Color2"), FLinearColor(0.6f, 0.85f, 1.0f));
    }
    Aura->Activate(true);
}

void UReflectionsSpellVfxSubsystem::ShakeNear(const FVector& Location, float Strength)
{
    APlayerController* Controller = LocalController(GetWorld());
    const APawn* Pawn = Controller ? Controller->GetPawn() : nullptr;
    UReflectionsSpellCameraModifier* Camera = UReflectionsSpellCameraModifier::Get(Controller);
    if (!Pawn || !Camera) return;
    const float Falloff = FMath::Clamp(1.0f - FVector::Dist(Pawn->GetActorLocation(), Location) / 3000.0f, 0.0f, 1.0f);
    Camera->AddTrauma(Strength * Falloff);
}

void UReflectionsSpellVfxSubsystem::HitStop()
{
    UWorld* World = GetWorld();
    const double Now = FPlatformTime::Seconds();
    if (!World || Now - LastHitStop < 0.15) return;
    LastHitStop = Now;
    constexpr float Dilation = 0.06f;
    UGameplayStatics::SetGlobalTimeDilation(World, Dilation);
    // Timers run in dilated time, so ~60 ms of real time is Dilation times that in game time.
    World->GetTimerManager().SetTimer(HitStopTimer, FTimerDelegate::CreateWeakLambda(this, [this]()
    {
        if (UWorld* W = GetWorld()) UGameplayStatics::SetGlobalTimeDilation(W, 1.0f);
    }), 0.06f * Dilation, false);
}

void UReflectionsSpellVfxSubsystem::OnSpellHit(const FReflectionsSpellHitData& Hit)
{
    FVector Direction = Hit.ImpactNormal.GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = -Hit.Impulse.GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = FVector::UpVector;

    // Feedback for the local caster: hit marker, a short freeze on living targets and a little shake.
    const bool bLiving = IsValid(Hit.Target) && (Hit.Target->IsA<APawn>() || Hit.Target->Implements<UCombatDamageable>()
        || Hit.Target->FindComponentByClass<UReflectionsHealthComponent>());
    if (IsLocalPlayer(Hit.Caster) && bLiving && Hit.Spell != EHeroSpell::ForcePush)
    {
        const UReflectionsHealthComponent* Health = Hit.Target->FindComponentByClass<UReflectionsHealthComponent>();
        if (UReflectionsSpellAimComponent* Aim = Hit.Caster->FindComponentByClass<UReflectionsSpellAimComponent>())
        {
            Aim->NotifyHit(Health && Health->Health <= 0.0f);
        }
        // Area spells report one hit per target; only the rate-limited hit-stop gets a shake, so they don't stack.
        const double Before = LastHitStop;
        HitStop();
        if (LastHitStop != Before) ShakeNear(Hit.Location, 0.18f);
    }

    // Blood is opt-in: a generic damageable object or character is not evidence of exposed flesh.
    if (!BloodImpact || !IsValid(Hit.Target) || !Hit.Target->ActorHasTag(FName(TEXT("Flesh")))) return;
    UNiagaraComponent* Spray = UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, BloodImpact, Hit.Location,
        Direction.Rotation(), FVector(0.35f), true, false, ENCPoolMethod::AutoRelease, true);
    if (Spray)
    {
        Spray->SetVariableFloat(TEXT("User.Intensity"), 0.65f);
        Spray->Activate(true);
    }
    // The ground spatter is transient and projected onto actual geometry, not the NPC's clothes.
    if (BloodSpatter && GetWorld())
    {
        FHitResult Ground;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(SpellBloodGround), false, Hit.Target);
        Query.AddIgnoredActor(Hit.Caster);
        if (GetWorld()->LineTraceSingleByChannel(Ground, Hit.Location + FVector(0, 0, 8), Hit.Location - FVector(0, 0, 350), ECC_Visibility, Query))
        {
            const FRotator Rotation = (-Ground.ImpactNormal).Rotation();
            UGameplayStatics::SpawnDecalAtLocation(GetWorld(), BloodSpatter, FVector(10, 28, 28), Ground.ImpactPoint + Ground.ImpactNormal * 0.5f,
                Rotation, 12.0f);
        }
    }
}
