#include "SpellVFX/ReflectionsSpellVfxSubsystem.h"
#include "Hero/ReflectionsSpellAim.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Components/CapsuleComponent.h"
#include "Components/DecalComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
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
#include "Misc/PackageName.h"

namespace
{
    const TCHAR* SystemsFolder = TEXT("/Game/Characters/Hero/SpellVFX/Systems/");
    constexpr int32 MaxGroundMarks = 24;
    // A mark holds for GroundMarkHold seconds, then fades over GroundMarkFade (M_Spell_GroundMark reads both through
    // DecalLifetimeOpacity) and the component is destroyed.
    constexpr float GroundMarkHold = 1.5f;
    constexpr float GroundMarkFade = 3.5f;

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

    /** Tarnish (enemy magic): a black-violet core, sickly silver sparks and smoke that drinks the light. */
    const FElementStyle& TarnishStyle()
    {
        static const FElementStyle Tarnish{
            {0.30f, 0.03f, 0.55f, 1.0f}, {0.66f, 0.70f, 0.74f, 1.0f},
            22.0f, 70.0f, -120.0f, 420.0f, 3.0f, 40.0f, 0.0f, 12.0f,
            55.0f, -650.0f, 0.0f, 0.0f, {0.05f, 0.02f, 0.07f, 1.0f}, 16.0f, {0.025f, 0.01f, 0.04f, 0.82f}, 0.0f, 0.0f, 34.0f};
        return Tarnish;
    }

    const FElementStyle& FireballStyle()
    {
        static const FElementStyle Fireball{
            {1.0f, 0.16f, 0.015f, 1.0f}, {1.0f, 0.71f, 0.20f, 1.0f},
            40.0f, 165.0f, 350.0f, 460.0f, 0.0f, 0.0f, 0.0f, 27.0f,
            95.0f, -700.0f, 0.0f, 0.0f, {0.1f, 0.05f, 0.02f, 1.0f}, 17.0f,
            {0.08f, 0.065f, 0.055f, 0.65f}, 50.0f, 0.0f, 22.0f};
        return Fireball;
    }

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

    /** One impact or muzzle burst from the shared NS_Spell_Impact, styled by element (or tarnish). */
    void SpawnStyledBurst(UObject* Context, UNiagaraSystem* ImpactSystem, const FElementStyle& Style, const FVector& Location,
        const FVector& Normal, float Scale, bool bMuzzle)
    {
        if (!ImpactSystem) return;
        FVector Up = Normal.GetSafeNormal();
        if (Up.IsNearlyZero()) Up = FVector::UpVector;
        UNiagaraComponent* Burst = UNiagaraFunctionLibrary::SpawnSystemAtLocation(Context, ImpactSystem, Location, Up.Rotation(), FVector(1.0f),
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
    TarnishSystem = LoadSystem(TEXT("NS_Tarnish_Bolt"));
    TarnishBurstSystem = LoadSystem(TEXT("NS_Tarnish_Burst"));
    ShockSystem = LoadSystem(TEXT("NS_Spell_Shock"));
    BodyFxSystem = LoadSystem(TEXT("NS_Spell_BodyFx"));
    {
        auto OptionalCue = [](const TCHAR* Name) -> USoundBase*
        {
            return FPackageName::DoesPackageExist(FString::Printf(TEXT("/Game/Audio/Jam/Cues/%s"), Name)) ? JamCue(Name) : nullptr;
        };
        BodyHitCue = OptionalCue(TEXT("SCue_Spell_BodyHit"));
        BodyHitHeavyCue = OptionalCue(TEXT("SCue_Spell_BodyHit_Heavy"));
        BodyElementCues.Init(nullptr, 8);
        BodyElementCues[static_cast<int32>(EReflectionsSpellElement::Fire)] = OptionalCue(TEXT("SCue_Spell_BodyHit_Fire"));
        BodyElementCues[static_cast<int32>(EReflectionsSpellElement::Ice)] = OptionalCue(TEXT("SCue_Spell_BodyHit_Ice"));
        BodyElementCues[static_cast<int32>(EReflectionsSpellElement::Lightning)] = OptionalCue(TEXT("SCue_Spell_BodyHit_Lightning"));
        BodyElementCues[static_cast<int32>(EReflectionsSpellElement::Water)] = OptionalCue(TEXT("SCue_Spell_BodyHit_Water"));
    }
    ShockLoopCue = FPackageName::DoesPackageExist(TEXT("/Game/Audio/Jam/Cues/SCue_Shock_Loop")) ? JamCue(TEXT("SCue_Shock_Loop")) : nullptr;
    // Optional (audio session, train #12): checked first so a missing cue never logs a load failure.
    ExplosionCue = FPackageName::DoesPackageExist(TEXT("/Game/Audio/Jam/Cues/SCue_Fireball_Explode"))
        ? JamCue(TEXT("SCue_Fireball_Explode")) : nullptr;
    BloodImpact = LoadObject<UNiagaraSystem>(nullptr, TEXT("/Game/Blueprints/Combat/Blood/NS_BloodImpact.NS_BloodImpact"));
    BloodSpatter = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Blueprints/Combat/Blood/M_BloodSpatter.M_BloodSpatter"));
    GroundMarkMaterial = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/Characters/Hero/SpellVFX/Materials/M_Spell_GroundMark.M_Spell_GroundMark"));
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
    WarmUpSpellEffects(InWorld);
}

void UReflectionsSpellVfxSubsystem::WarmUpSpellEffects(UWorld& InWorld)
{
    // Precache the core spell effects by registering their Niagara components out of view.
    TArray<UNiagaraSystem*> Systems{ProjectileSystem.Get(), ImpactSystem.Get(), HealSystem.Get(), WardSystem.Get(),
        TarnishSystem.Get(), TarnishBurstSystem.Get(), ShockSystem.Get(), BodyFxSystem.Get()};
    const FVector OutOfView(0.0f, 0.0f, -200000.0f);
    TArray<TWeakObjectPtr<UNiagaraComponent>> Warm;
    for (UNiagaraSystem* System : Systems)
    {
        if (!System) continue;
        if (UNiagaraComponent* Component = UNiagaraFunctionLibrary::SpawnSystemAtLocation(&InWorld, System, OutOfView,
            FRotator::ZeroRotator, FVector(1.0f), true, true, ENCPoolMethod::None, true))
        {
            Warm.Add(Component);
        }
    }
    InWorld.GetTimerManager().SetTimer(WarmUpTimer, FTimerDelegate::CreateWeakLambda(this, [Warm]()
    {
        for (const TWeakObjectPtr<UNiagaraComponent>& Component : Warm)
        {
            if (Component.IsValid()) Component->DeactivateImmediate();
        }
    }), 0.5f, false);
    UE_LOG(LogTemp, Log, TEXT("Spell VFX: warmed up %d spell systems at map start."), Warm.Num());
}

void UReflectionsSpellVfxSubsystem::Deinitialize()
{
    if (UWorld* World = GetWorld())
    {
        if (SpawnHandle.IsValid()) World->RemoveOnActorSpawnedHandler(SpawnHandle);
        World->GetTimerManager().ClearTimer(HitStopTimer);
        World->GetTimerManager().ClearTimer(ShockTimer);
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
    if (Projectile->GetLook() != EReflectionsSpellLook::Catalog)
    {
        AttachTarnishVisual(Projectile);
        return;
    }
    const EHeroSpell Spell = Projectile->GetSpell();
    if (!ReflectionsSpellCatalog::IsValid(Spell)) return;
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    const FElementStyle& Style = Spell == EHeroSpell::Firestorm ? FireballStyle() : StyleFor(Spec.Element);
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
        // Let the trail and embers finish in the world instead of vanishing with the projectile. The riding light
        // is made of 0.1 s particles, so it goes out as soon as spawning stops.
        Visual->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
        Visual->Deactivate();
        // Backstop: nothing of a spent projectile may outlive ~2 s (the longest trail particle lives under 1 s).
        if (UWorld* World = GetWorld())
        {
            FTimerHandle Handle;
            World->GetTimerManager().SetTimer(Handle, FTimerDelegate::CreateWeakLambda(this, [Visual]()
            {
                if (Visual.IsValid() && Visual->IsActive() && !Visual->GetAttachParent())
                {
                    Visual->DeactivateImmediate();
                }
            }), 2.0f, false);
        }
    }
}

void UReflectionsSpellVfxSubsystem::AttachTarnishVisual(AReflectionsSpellProjectile* Projectile)
{
    UNiagaraSystem* System = TarnishSystem ? TarnishSystem.Get() : ProjectileSystem.Get();
    if (!System) return;
    const bool bWisp = Projectile->GetLook() == EReflectionsSpellLook::TarnishWisp;
    const FElementStyle& Style = TarnishStyle();
    UNiagaraComponent* Visual = UNiagaraFunctionLibrary::SpawnSystemAttached(System, Projectile->GetRootComponent(), NAME_None,
        FVector::ZeroVector, FRotator::ZeroRotator, EAttachLocation::KeepRelativeOffset, true, false, ENCPoolMethod::AutoRelease, true);
    if (!Visual) return;
    SetColors(Visual, Style);
    Visual->SetVariableLinearColor(TEXT("User.SmokeColor"), Style.SmokeColor);
    // The wisp is a slow, swollen orb with silver motes circling it; the bolt a tight dart with a smoke wake.
    const float Scale = bWisp ? 1.3f : 1.0f;
    Visual->SetVariableFloat(TEXT("User.Scale"), Scale);
    Visual->SetVariableFloat(TEXT("User.Wisp"), bWisp ? 1.0f : 0.0f);
    Visual->SetVariableFloat(TEXT("User.Gather"), 0.0f);
    // Stand-in parameters for NS_Spell_Projectile when NS_Tarnish_Bolt is not built yet.
    Visual->SetVariableFloat(TEXT("User.CoreSize"), Style.CoreSize);
    Visual->SetVariableFloat(TEXT("User.SparkRate"), Style.SparkRate * Scale);
    Visual->SetVariableFloat(TEXT("User.SparkGravity"), Style.SparkGravity);
    Visual->SetVariableFloat(TEXT("User.Turbulence"), Style.Turbulence);
    Visual->SetVariableFloat(TEXT("User.Jitter"), Style.Jitter);
    Visual->SetVariableFloat(TEXT("User.Swirl"), bWisp ? 160.0f : Style.Swirl);
    Visual->SetVariableFloat(TEXT("User.ArcRate"), 0.0f);
    Visual->SetVariableFloat(TEXT("User.TrailWidth"), Style.TrailWidth * Scale);
    Visual->Activate(true);
    if (USoundBase* Loop = JamCue(TEXT("SCue_Projectile_Loop")))
    {
        UGameplayStatics::SpawnSoundAttached(Loop, Projectile->GetRootComponent(), NAME_None, FVector::ZeroVector,
            EAttachLocation::KeepRelativeOffset, true, bWisp ? 0.7f : 0.9f, bWisp ? 0.6f : 0.8f);
    }
    Projectile->HideFallbackVisual();
    ProjectileTrails.Add(Projectile, Visual);
    Projectile->OnDestroyed.AddUniqueDynamic(this, &UReflectionsSpellVfxSubsystem::OnProjectileDestroyed);
}

UNiagaraComponent* UReflectionsSpellVfxSubsystem::SpawnTarnishTelegraph(USceneComponent* Parent, FName Socket)
{
    UNiagaraSystem* System = TarnishSystem ? TarnishSystem.Get() : ProjectileSystem.Get();
    if (!System || !Parent) return nullptr;
    UNiagaraComponent* Gather = UNiagaraFunctionLibrary::SpawnSystemAttached(System, Parent, Socket, FVector::ZeroVector,
        FRotator::ZeroRotator, EAttachLocation::SnapToTarget, false, true, ENCPoolMethod::None, true);
    if (!Gather) return nullptr;
    const FElementStyle& Style = TarnishStyle();
    SetColors(Gather, Style);
    Gather->SetVariableLinearColor(TEXT("User.SmokeColor"), Style.SmokeColor);
    Gather->SetVariableFloat(TEXT("User.Scale"), 0.25f);
    Gather->SetVariableFloat(TEXT("User.Gather"), 1.0f);
    Gather->SetVariableFloat(TEXT("User.Wisp"), 0.0f);
    Gather->SetVariableFloat(TEXT("User.CoreSize"), 18.0f);
    Gather->SetVariableFloat(TEXT("User.Swirl"), 90.0f);
    Gather->SetVariableFloat(TEXT("User.SparkRate"), 40.0f);
    Gather->SetVariableFloat(TEXT("User.Turbulence"), Style.Turbulence);
    return Gather;
}

UDecalComponent* UReflectionsSpellVfxSubsystem::SpawnTarnishWarning(const FVector& Center, float Radius)
{
    // Kind 7 in M_Spell_GroundMark: a violet warning ring with a smoky fill; the caster ramps Strength to 1.
    UDecalComponent* Warning = PlaceGroundMark(7.0f, 0.15f, TarnishStyle().Color, Center, FVector::UpVector, Radius, false);
    if (Warning) Warning->SortOrder = 2;
    return Warning;
}

void UReflectionsSpellVfxSubsystem::SpawnTarnishImpact(const FVector& Location, const FVector& Normal, AActor* Caster, float Scale, bool bMuzzle)
{
    FVector Up = Normal.GetSafeNormal();
    if (Up.IsNearlyZero()) Up = FVector::UpVector;
    const FElementStyle& Style = TarnishStyle();
    if (TarnishBurstSystem)
    {
        if (UNiagaraComponent* Burst = UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, TarnishBurstSystem, Location, Up.Rotation(),
            FVector(1.0f), true, false, ENCPoolMethod::AutoRelease, true))
        {
            SetColors(Burst, Style);
            Burst->SetVariableLinearColor(TEXT("User.SmokeColor"), Style.SmokeColor);
            Burst->SetVariableVec3(TEXT("User.Normal"), Up);
            Burst->SetVariableFloat(TEXT("User.Scale"), Scale);
            Burst->SetVariableFloat(TEXT("User.Amount"), bMuzzle ? 0.3f : 1.0f);
            Burst->SetVariableFloat(TEXT("User.LightScale"), bMuzzle ? 0.35f : 1.0f);
            Burst->Activate(true);
        }
    }
    else
    {
        SpawnStyledBurst(this, ImpactSystem, Style, Location, Up, Scale, bMuzzle);
    }
    if (USoundBase* Sound = JamCue(bMuzzle ? TEXT("SCue_Arcane_Cast") : TEXT("SCue_Arcane_Impact")))
    {
        // Pitched down: the same voice as the player's arcane magic, but heavier and wrong.
        UGameplayStatics::PlaySoundAtLocation(this, Sound, Location, 1.0f, 0.72f);
    }
    if (!bMuzzle)
    {
        PlaceGroundMark(6.0f, 1.0f, Style.Color, Location, Up, FMath::Clamp(40.0f + 48.0f * Scale, 60.0f, 320.0f), true);
        ShakeNear(Location, FMath::Clamp(Scale, 0.5f, 2.0f) * 0.14f);
    }
}

void UReflectionsSpellVfxSubsystem::SpawnImpact(EHeroSpell Spell, const FVector& Location, const FVector& Normal, float Scale, bool bMuzzle)
{
    if (!ReflectionsSpellCatalog::IsValid(Spell)) return;
    const FElementStyle& Style = Spell == EHeroSpell::Firestorm ? FireballStyle() : StyleFor(ReflectionsSpellCatalog::Get(Spell).Element);
    SpawnStyledBurst(this, ImpactSystem, Style, Location, Normal, Scale, bMuzzle);
}

void UReflectionsSpellVfxSubsystem::SpawnGroundMark(EHeroSpell Spell, const FVector& Location, const FVector& Normal, float Scale)
{
    UWorld* World = GetWorld();
    if (!World || !GroundMarkMaterial || !ReflectionsSpellCatalog::IsValid(Spell)) return;
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    // Kind picks the look in M_Spell_GroundMark: 0 scorch, 1 frost, 2 wet, 3 lightning burn, 4 dirt, 5 arcane rune.
    float Kind = 0.0f;
    float Strength = 1.0f;
    switch (Spec.Element)
    {
    case EReflectionsSpellElement::Fire: Kind = 0.0f; break;
    case EReflectionsSpellElement::Ice: Kind = 1.0f; break;
    case EReflectionsSpellElement::Water: Kind = 2.0f; break;
    case EReflectionsSpellElement::Lightning: Kind = 3.0f; break;
    case EReflectionsSpellElement::Earth: Kind = 4.0f; break;
    case EReflectionsSpellElement::Air: Kind = 4.0f; Strength = 0.45f; break;
    case EReflectionsSpellElement::Arcane: Kind = 5.0f; break;
    default: return;  // Heals draw their own rune circle.
    }
    const float Radius = FMath::Clamp(35.0f + 35.0f * Scale + Spec.Radius * 0.3f, 55.0f, 300.0f);
    PlaceGroundMark(Kind, Strength, StyleFor(Spec.Element).Color, Location, Normal, Radius, true);
}

UDecalComponent* UReflectionsSpellVfxSubsystem::PlaceGroundMark(float Kind, float Strength, const FLinearColor& Color,
    const FVector& Location, const FVector& Normal, float Radius, bool bFade)
{
    UWorld* World = GetWorld();
    if (!World || !GroundMarkMaterial) return nullptr;
    // Mark the surface that was hit; a hit on a character (no static surface right behind it) marks the floor below.
    FVector Up = Normal.GetSafeNormal();
    if (Up.IsNearlyZero()) Up = FVector::UpVector;
    const FCollisionObjectQueryParams Statics(ECC_TO_BITFIELD(ECC_WorldStatic));
    const FCollisionQueryParams Query(SCENE_QUERY_STAT(SpellGroundMark), false);
    FHitResult Surface;
    bool bHit = World->LineTraceSingleByObjectType(Surface, Location + Up * 30.0f, Location - Up * 60.0f, Statics, Query);
    if (!bHit)
    {
        bHit = World->LineTraceSingleByObjectType(Surface, Location + FVector(0.0f, 0.0f, 30.0f), Location - FVector(0.0f, 0.0f, 260.0f),
            Statics, Query);
    }
    if (!bHit) return nullptr;

    if (bFade)
    {
        GroundMarks.RemoveAll([](const TWeakObjectPtr<UDecalComponent>& Mark) { return !Mark.IsValid(); });
        while (GroundMarks.Num() >= MaxGroundMarks)
        {
            if (UDecalComponent* Oldest = GroundMarks[0].Get()) Oldest->DestroyComponent();
            GroundMarks.RemoveAt(0);
        }
    }

    FRotator Rotation = (-Surface.ImpactNormal).Rotation();
    Rotation.Roll = FMath::FRandRange(0.0f, 360.0f);
    UDecalComponent* Mark = UGameplayStatics::SpawnDecalAtLocation(World, GroundMarkMaterial, FVector(30.0f, Radius, Radius),
        Surface.ImpactPoint, Rotation, 0.0f);
    if (!Mark) return nullptr;
    if (UMaterialInstanceDynamic* Material = Mark->CreateDynamicMaterialInstance())
    {
        Material->SetScalarParameterValue(TEXT("Kind"), Kind);
        Material->SetScalarParameterValue(TEXT("Seed"), FMath::FRandRange(0.0f, 100.0f));
        Material->SetScalarParameterValue(TEXT("Strength"), Strength);
        Material->SetVectorParameterValue(TEXT("Color"), Color);
    }
    Mark->SetFadeScreenSize(0.0f);
    Mark->SortOrder = 1;  // Below the aim preview (10).
    if (bFade)
    {
        // The spawned decal belongs to the world settings actor, so never destroy the owner after the fade.
        Mark->SetFadeOut(GroundMarkHold, GroundMarkFade, false);
        GroundMarks.Add(Mark);
    }
    return Mark;
}

void UReflectionsSpellVfxSubsystem::OnImpactVisual(EHeroSpell Spell, FVector Location, FVector Normal, AActor* Caster, float Scale)
{
    SpawnImpact(Spell, Location, Normal, FMath::Clamp(Scale, 0.5f, 3.0f), false);
    SpawnGroundMark(Spell, Location, Normal, FMath::Clamp(Scale, 0.5f, 3.0f));
    // The fireball explodes: the audio session's explosion cue replaces the plain fire impact when it exists.
    if (Spell == EHeroSpell::Firestorm && ExplosionCue)
    {
        UGameplayStatics::PlaySoundAtLocation(this, ExplosionCue, Location);
    }
    else
    {
        PlayElementCue(this, Spell, Location, true);
    }
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
        else if (Spec.Delivery == EReflectionsSpellDelivery::Jump)
        {
            if (USoundBase* Start = JamCue(TEXT("SCue_Levitation_Start"))) UGameplayStatics::PlaySoundAtLocation(this, Start, Caster->GetActorLocation());
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

void UReflectionsSpellVfxSubsystem::HitStop(float Seconds)
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
    }), FMath::Clamp(Seconds, 0.02f, 0.12f) * Dilation, false);
}

void UReflectionsSpellVfxSubsystem::ElectrifyBody(AActor* Target, float Duration, float Magnitude)
{
    UWorld* World = GetWorld();
    if (!World || !ShockSystem || !IsValid(Target) || Duration <= 0.0f) return;
    const double End = World->GetTimeSeconds() + FMath::Clamp(Duration, 0.2f, 4.0f);
    if (FBodyShock* Live = Shocks.Find(Target))
    {
        if (Live->Crackle.IsValid() && Live->Crackle->IsActive())
        {
            Live->EndTime = FMath::Max(Live->EndTime, End);
            return;
        }
    }
    USceneComponent* Parent = nullptr;
    FName Socket = NAME_None;
    UNiagaraComponent* Crackle = AttachToBody(ShockSystem, Target, Parent, Socket);
    if (!Crackle) return;
    const FElementStyle& Style = StyleFor(EReflectionsSpellElement::Lightning);
    SetColors(Crackle, Style);
    Crackle->SetVariableFloat(TEXT("User.Intensity"), FMath::Clamp(0.6f + Magnitude * 0.6f, 0.6f, 1.2f));
    Crackle->SetVariableFloat(TEXT("User.Scale"), 1.0f);
    FBodyShock& Shock = Shocks.Add(Target);
    Shock.Crackle = Crackle;
    Shock.EndTime = End;
    if (ShockLoopCue)
    {
        Shock.Loop = UGameplayStatics::SpawnSoundAttached(ShockLoopCue, Parent, Socket, FVector::ZeroVector, EAttachLocation::SnapToTarget, true);
    }
    if (!World->GetTimerManager().IsTimerActive(ShockTimer))
    {
        World->GetTimerManager().SetTimer(ShockTimer, FTimerDelegate::CreateUObject(this, &UReflectionsSpellVfxSubsystem::TickShocks), 0.1f, true);
    }
}

UNiagaraComponent* UReflectionsSpellVfxSubsystem::AttachToBody(UNiagaraSystem* System, AActor* Target, USceneComponent*& OutParent, FName& OutSocket)
{
    OutParent = nullptr;
    OutSocket = NAME_None;
    if (!System || !IsValid(Target)) return nullptr;
    // Ride the visible body's pelvis when it has a posed one (so the effect follows a ragdoll), else the actor's middle.
    FVector Origin, Extent;
    Target->GetActorBounds(true, Origin, Extent);
    USceneComponent* Parent = Target->GetRootComponent();
    FName Socket = NAME_None;
    TArray<USkeletalMeshComponent*> Meshes;
    Target->GetComponents(Meshes);
    for (USkeletalMeshComponent* Mesh : Meshes)
    {
        const USkinnedMeshComponent* Pose = Mesh && Mesh->LeaderPoseComponent.IsValid() ? Mesh->LeaderPoseComponent.Get() : Mesh;
        if (Mesh && Mesh->IsRegistered() && Mesh->IsVisible() && !Mesh->bHiddenInGame && Mesh->DoesSocketExist(TEXT("pelvis"))
            && Pose && Pose->GetNumComponentSpaceTransforms() > 0)
        {
            Parent = Mesh;
            Socket = TEXT("pelvis");
            break;
        }
    }
    if (!Parent) return nullptr;
    UNiagaraComponent* Fx = Socket.IsNone()
        ? UNiagaraFunctionLibrary::SpawnSystemAttached(System, Parent, NAME_None, Origin, FRotator::ZeroRotator,
            EAttachLocation::KeepWorldPosition, false, true, ENCPoolMethod::None, true)
        : UNiagaraFunctionLibrary::SpawnSystemAttached(System, Parent, Socket, FVector(0.0f, 0.0f, 15.0f), FRotator::ZeroRotator,
            EAttachLocation::SnapToTarget, false, true, ENCPoolMethod::None, true);
    if (!Fx) return nullptr;
    // World-up capsule sized to the body (the pelvis socket's own axes are not upright).
    Fx->SetUsingAbsoluteRotation(true);
    Fx->SetWorldRotation(FRotator::ZeroRotator);
    Fx->SetVariableFloat(TEXT("User.Height"), FMath::Clamp(Extent.Z * 1.8f, 80.0f, 210.0f));
    Fx->SetVariableFloat(TEXT("User.Radius"), FMath::Clamp(FMath::Max(Extent.X, Extent.Y) * 0.5f, 16.0f, 45.0f));
    OutParent = Parent;
    OutSocket = Socket;
    return Fx;
}

void UReflectionsSpellVfxSubsystem::AfflictBody(AActor* Target, int32 Kind, float Duration, float Magnitude, float MaxDuration)
{
    UWorld* World = GetWorld();
    if (!World || !BodyFxSystem || !IsValid(Target) || Duration <= 0.0f) return;
    const double End = World->GetTimeSeconds() + FMath::Clamp(Duration, 0.3f, MaxDuration);
    if (FBodyShock* Live = Afflictions.Find(Target))
    {
        if (Live->Kind == Kind && Live->Crackle.IsValid() && Live->Crackle->IsActive())
        {
            Live->EndTime = FMath::Max(Live->EndTime, End);
            return;
        }
        // A new element replaces the old one (water puts out a burn, fire thaws frost).
        if (Live->Crackle.IsValid()) Live->Crackle->Deactivate();
    }
    USceneComponent* Parent = nullptr;
    FName Socket = NAME_None;
    UNiagaraComponent* Fx = AttachToBody(BodyFxSystem, Target, Parent, Socket);
    if (!Fx) return;
    const EReflectionsSpellElement Element = Kind == 0 ? EReflectionsSpellElement::Fire
        : Kind == 1 ? EReflectionsSpellElement::Ice : EReflectionsSpellElement::Water;
    SetColors(Fx, StyleFor(Element));
    Fx->SetVariableLinearColor(TEXT("User.SmokeColor"), StyleFor(EReflectionsSpellElement::Fire).SmokeColor);
    Fx->SetVariableFloat(TEXT("User.EmberRate"), Kind == 0 ? 55.0f : 0.0f);
    Fx->SetVariableFloat(TEXT("User.SmokeRate"), Kind == 0 ? 16.0f : 0.0f);
    Fx->SetVariableFloat(TEXT("User.FrostRate"), Kind == 1 ? 36.0f : 0.0f);
    Fx->SetVariableFloat(TEXT("User.DripRate"), Kind == 2 ? 45.0f : 0.0f);
    Fx->SetVariableFloat(TEXT("User.Intensity"), FMath::Clamp(0.7f + Magnitude * 0.5f, 0.7f, 1.2f));
    FBodyShock& Affliction = Afflictions.Add(Target);
    Affliction.Crackle = Fx;
    Affliction.EndTime = End;
    Affliction.Kind = Kind;
    if (!World->GetTimerManager().IsTimerActive(ShockTimer))
    {
        World->GetTimerManager().SetTimer(ShockTimer, FTimerDelegate::CreateUObject(this, &UReflectionsSpellVfxSubsystem::TickShocks), 0.1f, true);
    }
}

void UReflectionsSpellVfxSubsystem::TickShocks()
{
    UWorld* World = GetWorld();
    const double Now = World ? World->GetTimeSeconds() : 0.0;
    for (auto It = Shocks.CreateIterator(); It; ++It)
    {
        FBodyShock& Shock = It.Value();
        if (It.Key().IsValid() && Shock.Crackle.IsValid() && Now < Shock.EndTime) continue;
        // Spawning stops; the 0.1-0.45 s particles finish on their own.
        if (Shock.Crackle.IsValid()) Shock.Crackle->Deactivate();
        if (Shock.Loop.IsValid()) Shock.Loop->FadeOut(0.2f, 0.0f);
        It.RemoveCurrent();
    }
    for (auto It = Afflictions.CreateIterator(); It; ++It)
    {
        FBodyShock& Affliction = It.Value();
        if (It.Key().IsValid() && Affliction.Crackle.IsValid() && Now < Affliction.EndTime) continue;
        if (Affliction.Crackle.IsValid()) Affliction.Crackle->Deactivate();
        It.RemoveCurrent();
    }
    if (Shocks.Num() == 0 && Afflictions.Num() == 0 && World) World->GetTimerManager().ClearTimer(ShockTimer);
}

void UReflectionsSpellVfxSubsystem::OnSpellHit(const FReflectionsSpellHitData& Hit)
{
    FVector Direction = Hit.ImpactNormal.GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = -Hit.Impulse.GetSafeNormal();
    if (Direction.IsNearlyZero()) Direction = FVector::UpVector;
    // Walls and floors report hits too; body effects, feedback and sounds are for living targets only.
    const bool bLiving = IsValid(Hit.Target) && (Hit.Target->IsA<APawn>() || Hit.Target->Implements<UCombatDamageable>()
        || Hit.Target->FindComponentByClass<UReflectionsHealthComponent>());
    if (bLiving)
    {
        switch (Hit.Reaction)
        {
        case EReflectionsSpellReaction::Electrify: ElectrifyBody(Hit.Target, Hit.Duration, Hit.Magnitude); break;
        case EReflectionsSpellReaction::Burn: AfflictBody(Hit.Target, 0, Hit.Duration, Hit.Magnitude); break;
        case EReflectionsSpellReaction::Freeze:
            AfflictBody(Hit.Target, 1, Hit.Duration, Hit.Magnitude,
                Hit.Spell == EHeroSpell::Freeze ? ReflectionsSpellCatalog::FreezeDuration : 5.0f);
            break;
        case EReflectionsSpellReaction::Push:
            if (ReflectionsSpellCatalog::IsValid(Hit.Spell) && ReflectionsSpellCatalog::Get(Hit.Spell).Element == EReflectionsSpellElement::Water)
            {
                AfflictBody(Hit.Target, 2, 1.6f, Hit.Magnitude);
            }
            break;
        default: break;
        }
    }

    // Impact feel. Strong hits (Magnitude 0.6+, blasts, knockdowns) freeze time for 50-80 ms by strength; every hit
    // shakes by strength and distance, rate-limited so area spells don't stack it. The player being hit feels it too.
    const float Strength = FMath::Clamp(Hit.Magnitude, 0.0f, 1.0f);
    const bool bStrong = Hit.Magnitude >= 0.6f || Hit.Reaction == EReflectionsSpellReaction::Explosion
        || Hit.Reaction == EReflectionsSpellReaction::Knockdown;
    const double Now = FPlatformTime::Seconds();
    if (IsLocalPlayer(Hit.Caster) && bLiving && Hit.Spell != EHeroSpell::ForcePush && !Hit.bRepeat)
    {
        const UReflectionsHealthComponent* Health = Hit.Target->FindComponentByClass<UReflectionsHealthComponent>();
        if (UReflectionsSpellAimComponent* Aim = Hit.Caster->FindComponentByClass<UReflectionsSpellAimComponent>())
        {
            Aim->NotifyHit(Health && Health->Health <= 0.0f);
        }
        if (bStrong) HitStop(FMath::Lerp(0.05f, 0.08f, FMath::Clamp((Hit.Magnitude - 0.6f) / 0.4f, 0.0f, 1.0f)));
        if (Now - LastHitShake > 0.1)
        {
            LastHitShake = Now;
            ShakeNear(Hit.Location, 0.06f + 0.28f * Strength);
        }
    }
    else if (bLiving && !Hit.bRepeat && IsLocalPlayer(Hit.Target) && Now - LastHitShake > 0.1)
    {
        LastHitShake = Now;
        ShakeNear(Hit.Location, 0.12f + 0.3f * Strength);
    }
    if (bLiving && !Hit.bRepeat && ReflectionsSpellCatalog::IsValid(Hit.Spell))
    {
        const EReflectionsSpellElement Element = ReflectionsSpellCatalog::Get(Hit.Spell).Element;
        // Punch-through: a light spray out along the hit's direction at the exact hit point (blasts have their own).
        const FVector Through = Hit.Impulse.GetSafeNormal();
        if (Hit.Reaction != EReflectionsSpellReaction::Explosion && !Through.IsNearlyZero())
        {
            SpawnStyledBurst(this, ImpactSystem, StyleFor(Element), Hit.Location, Through, 0.4f + 0.7f * Strength, true);
        }
        if (USoundBase* Thud = bStrong && BodyHitHeavyCue ? BodyHitHeavyCue.Get() : BodyHitCue.Get())
        {
            UGameplayStatics::PlaySoundAtLocation(this, Thud, Hit.Location, 0.9f);
        }
        const int32 Index = static_cast<int32>(Element);
        if (BodyElementCues.IsValidIndex(Index) && BodyElementCues[Index])
        {
            UGameplayStatics::PlaySoundAtLocation(this, BodyElementCues[Index], Hit.Location, 0.8f);
        }
    }

    // Blood is opt-in: a generic damageable object or character is not evidence of exposed flesh.
    if (Hit.bRepeat || !BloodImpact || !IsValid(Hit.Target) || !Hit.Target->ActorHasTag(FName(TEXT("Flesh")))) return;
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
