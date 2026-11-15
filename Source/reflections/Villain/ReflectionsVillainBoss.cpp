#include "Villain/ReflectionsVillainBoss.h"

#include "Villain/ReflectionsVillainConfig.h"
#include "Villain/ReflectionsVillainFx.h"
#include "Villain/ReflectionsVillainHud.h"
#include "Villain/ReflectionsVillainLook.h"
#include "Villain/ReflectionsVillainSubsystem.h"
#include "Villain/ReflectionsVillainText.h"

#include "Components/AudioComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/DamageEvents.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "NiagaraComponent.h"
#include "Sound/SoundBase.h"

#define LOCTEXT_NAMESPACE "ReflectionsVillain"

namespace
{
    constexpr float HalfHeight = 135.0f;
    constexpr float HoverHeight = 40.0f;
    constexpr float ManifestTime = 4.2f;
    constexpr float DeathTime = 3.4f;

    float Ease(float T)
    {
        T = FMath::Clamp(T, 0.0f, 1.0f);
        return T * T * (3.0f - 2.0f * T);
    }

    UMaterialInstanceDynamic* TelegraphMaterial(UObject* Outer)
    {
        UMaterialInterface* Base = ReflectionsVillainAssets::TelegraphMaterial();
        bool bFallback = false;
        if (!Base)
        {
            Base = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"), nullptr, LOAD_NoWarn | LOAD_Quiet);
            bFallback = true;
        }
        UMaterialInstanceDynamic* Dynamic = Base ? UMaterialInstanceDynamic::Create(Base, Outer) : nullptr;
        if (Dynamic)
        {
            Dynamic->SetVectorParameterValue(bFallback ? TEXT("Color") : TEXT("Color"), ReflectionsVillainColors::Violet);
        }
        return Dynamic;
    }
}

// ============================================================================================ boss

AReflectionsVillainBoss::AReflectionsVillainBoss()
{
    PrimaryActorTick.bCanEverTick = true;
    AutoPossessAI = EAutoPossessAI::Disabled;
    AIControllerClass = nullptr;
    SetCanBeDamaged(true);

    Capsule = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Capsule"));
    RootComponent = Capsule;
    Capsule->InitCapsuleSize(60.0f, HalfHeight);
    Capsule->SetCollisionProfileName(UCollisionProfile::Pawn_ProfileName);
    Capsule->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Capsule->SetCanEverAffectNavigation(false);

    Look = CreateDefaultSubobject<UReflectionsVillainLookComponent>(TEXT("Look"));
    Look->SetupAttachment(Capsule);
    Look->SetRelativeLocation(FVector(0.0f, 0.0f, -HalfHeight));
    Look->BodyScale = 1.5f;
    Look->ShroudAmount = 0.25f;
    Look->bTrueForm = true;

    Tags.Add(TEXT("Villain"));
}

FText AReflectionsVillainBoss::DisplayName()
{
    return ReflectionsVillainText::BossName();
}

void AReflectionsVillainBoss::BeginPlay()
{
    Super::BeginPlay();
    MaxHealth = ReflectionsVillainTuning::BossHealth();
    Health = MaxHealth;
    Look->SetLookVisible(false);
    Look->SetGlow(0.0f);
    if (ArenaCenter.IsZero())
    {
        ArenaCenter = ReflectionsVillainFx::Ground(GetWorld(), GetActorLocation(), this);
        Station = ArenaCenter;
    }
}

void AReflectionsVillainBoss::EndPlay(const EEndPlayReason::Type Reason)
{
    for (const TWeakObjectPtr<AActor>& Actor : Spawned)
    {
        if (AActor* Resolved = Actor.Get())
        {
            Resolved->Destroy();
        }
    }
    Spawned.Reset();
    if (Music)
    {
        Music->Stop();
    }
    if (Reason == EEndPlayReason::Destroyed)
    {
        UpdateHud(false);
    }
    Super::EndPlay(Reason);
}

void AReflectionsVillainBoss::InitArena(const FVector& GroundCenter, float Radius)
{
    ArenaCenter = GroundCenter;
    ArenaRadius = FMath::Max(400.0f, Radius);
    Station = GroundCenter;
    SetActorLocation(GroundCenter + FVector(0.0f, 0.0f, HalfHeight + HoverHeight));
}

APawn* AReflectionsVillainBoss::GetPlayer() const
{
    return ReflectionsVillainFx::PlayerPawn(GetWorld());
}

FString AReflectionsVillainBoss::DescribeState() const
{
    const UEnum* States = StaticEnum<EReflectionsVillainBossState>();
    const UEnum* Attacks = StaticEnum<EReflectionsVillainAttack>();
    return FString::Printf(TEXT("%s%s attack %s"), *States->GetNameStringByValue(static_cast<int64>(State)),
        bPhaseTwo ? TEXT(" (phase 2)") : TEXT(""), *Attacks->GetNameStringByValue(static_cast<int64>(Attack)));
}

float AReflectionsVillainBoss::TelegraphTime(float Base) const
{
    return Base * ReflectionsVillainTuning::TelegraphScale() * (bPhaseTwo ? 0.8f : 1.0f);
}

void AReflectionsVillainBoss::UpdateHud(bool bVisible)
{
    if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld()))
    {
        if (UReflectionsVillainHudWidget* Hud = bVisible ? Villain->GetOrCreateHud() : nullptr)
        {
            Hud->SetBoss(DisplayName(), MaxHealth > 0.0f ? Health / MaxHealth : 0.0f, true);
        }
        else if (!bVisible)
        {
            if (UReflectionsVillainHudWidget* Existing = Villain->GetOrCreateHud())
            {
                Existing->SetBoss(DisplayName(), 0.0f, false);
            }
        }
    }
}

void AReflectionsVillainBoss::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    StateClock += DeltaSeconds;
    HoverClock += DeltaSeconds;
    switch (State)
    {
    case EReflectionsVillainBossState::Dormant:
        if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld()); Villain && !Villain->CanManifest())
        {
            break;
        }
        if (const APawn* Player = GetPlayer())
        {
            // He rises when the player reaches the arena floor: close across the ground and near its height, so a
            // tower-top arena waits for the top of the ramps instead of firing from the streets below.
            const FVector Offset = Player->GetActorLocation() - ArenaCenter;
            const float Reach = FMath::Min(ReflectionsVillainTuning::ManifestRadius(), ArenaRadius + 800.0f);
            if (Offset.Size2D() <= Reach && FMath::Abs(Offset.Z) <= 600.0f)
            {
                Manifest();
            }
        }
        break;
    case EReflectionsVillainBossState::Manifesting:
        TickManifest(DeltaSeconds);
        break;
    case EReflectionsVillainBossState::Fighting:
        TickFight(DeltaSeconds);
        break;
    case EReflectionsVillainBossState::Dying:
        TickDying(DeltaSeconds);
        break;
    default:
        break;
    }
}

// ---------------------------------------------------------------------------------------------- manifest

void AReflectionsVillainBoss::Manifest()
{
    if (State != EReflectionsVillainBossState::Dormant)
    {
        return;
    }
    State = EReflectionsVillainBossState::Manifesting;
    StateClock = 0.0f;
    UWorld* World = GetWorld();
    if (const APawn* Player = GetPlayer())
    {
        FVector Away = (ArenaCenter - Player->GetActorLocation()).GetSafeNormal2D();
        if (Away.IsNearlyZero())
        {
            Away = -Player->GetActorForwardVector().GetSafeNormal2D();
        }
        const FVector Spot = ArenaCenter + Away * ArenaRadius * 0.55f;
        Station = ReflectionsVillainFx::Ground(World, Spot, this, 300.0f, 1500.0f);
        SetActorLocation(Station + FVector(0.0f, 0.0f, HalfHeight + HoverHeight), false, nullptr, ETeleportType::TeleportPhysics);
    }
    Look->SetLookVisible(true);
    Look->SetRelativeScale3D(FVector(0.05f));
    Look->SetGlow(0.0f);
    Column = ReflectionsVillainFx::Shroud(World, nullptr, NAME_None, ArenaCenter + FVector(0.0f, 0.0f, 10.0f), 3.0f, 3.0f);
    ReflectionsVillainFx::Sound2D(World, ReflectionsVillainAssets::ManifestSound());
    ReflectionsVillainFx::Duck(World);
    if (USoundBase* Theme = ReflectionsVillainAssets::FightMusic())
    {
        Music = UGameplayStatics::SpawnSound2D(this, Theme, 0.9f, 1.0f, 0.0f, nullptr, false, false);
        if (Music)
        {
            Music->FadeIn(2.5f, 0.9f);
        }
    }
    if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(World))
    {
        if (UReflectionsVillainHudWidget* Hud = Villain->GetOrCreateHud())
        {
            Hud->ShowBanner(DisplayName(), ReflectionsVillainText::BossSubtitle(
                UReflectionsVillainSubsystem::ArenaSideName(World)), ReflectionsVillainColors::Lilac);
        }
    }
}

void AReflectionsVillainBoss::TickManifest(float DeltaSeconds)
{
    const float T = StateClock / ManifestTime;
    const float Grow = Ease(T / 0.75f);
    Look->SetRelativeScale3D(FVector(FMath::Lerp(0.05f, 1.0f, Grow)));
    Look->SetRelativeLocation(FVector(0.0f, 0.0f, -HalfHeight - (1.0f - Grow) * 140.0f));
    Look->SetGlow(FMath::Clamp((T - 0.55f) / 0.3f, 0.0f, 1.0f));
    if (T >= 0.8f && T - DeltaSeconds / ManifestTime < 0.8f)
    {
        Look->Flash(2.5f);
        ReflectionsVillainFx::Impact(GetWorld(), Look->GetChestLocation(), ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 2.6f, 4.0f);
        ReflectionsVillainFx::VoiceOn(ReflectionsVillainAssets::VoManifest(), Look->GetBody(), TEXT("head"), 1.2f);
    }
    Hover(DeltaSeconds, 0.0f);
    FacePlayer(DeltaSeconds);
    if (T < 1.0f)
    {
        return;
    }
    State = EReflectionsVillainBossState::Fighting;
    StateClock = 0.0f;
    NextAttack = 1.2f;
    NextTaunt = 9.0f;
    Look->SetRelativeScale3D(FVector(1.0f));
    Look->SetRelativeLocation(FVector(0.0f, 0.0f, -HalfHeight));
    Capsule->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    if (Column)
    {
        Column->Deactivate();
        Column = nullptr;
    }
    UpdateHud(true);
    ReflectionsVillainFx::Message(GetWorld(), ReflectionsVillainText::Hint());
}

// ---------------------------------------------------------------------------------------------- fight

void AReflectionsVillainBoss::Hover(float DeltaSeconds, float ExtraHeight)
{
    Rise = FMath::FInterpTo(Rise, ExtraHeight, DeltaSeconds, 3.0f);
    const FVector Target = Station + FVector(0.0f, 0.0f, HalfHeight + HoverHeight + Rise + FMath::Sin(HoverClock * 1.4f) * 14.0f);
    SetActorLocation(FMath::VInterpTo(GetActorLocation(), Target, DeltaSeconds, 2.5f));
}

void AReflectionsVillainBoss::FacePlayer(float DeltaSeconds)
{
    const APawn* Player = GetPlayer();
    if (!Player)
    {
        return;
    }
    const FVector To = (Player->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
    if (To.IsNearlyZero())
    {
        return;
    }
    const FRotator Want(0.0f, To.Rotation().Yaw, 0.0f);
    SetActorRotation(FMath::RInterpTo(GetActorRotation(), Want, DeltaSeconds, 4.0f));
}

void AReflectionsVillainBoss::TickFight(float DeltaSeconds)
{
    const bool bRising = Attack == EReflectionsVillainAttack::Wave && AttackClock < Telegraph;
    Hover(DeltaSeconds, bRising ? 150.0f : 0.0f);
    FacePlayer(DeltaSeconds);
    const APawn* Player = GetPlayer();
    const bool bEngaged = Player && ReflectionsVillainFx::IsAlive(Player)
        && FVector::Dist2D(Player->GetActorLocation(), ArenaCenter) < ArenaRadius + 2500.0f;
    if (Attack != EReflectionsVillainAttack::None)
    {
        TickAttack(DeltaSeconds);
    }
    else if (bEngaged && StateClock >= NextAttack)
    {
        ChooseAttack();
    }
    UWorld* LineWorld = GetWorld();
    if (!(StoryLines & 1) && StateClock >= 4.0f)
    {
        StoryLines |= 1;
        ReflectionsVillainFx::VoiceOn(ReflectionsVillainAssets::StoryLine(TEXT("MQ09_01")), Look->GetBody(), TEXT("head"), 1.1f);
        NextTaunt = FMath::Max(NextTaunt, StateClock + 8.0f);
    }
    if (PhaseTwoAt >= 0.0f && !(StoryLines & 2) && StateClock >= PhaseTwoAt + 3.0f)
    {
        StoryLines |= 2;
        ReflectionsVillainFx::VoiceOn(ReflectionsVillainAssets::StoryLine(TEXT("MQ09_03")), Look->GetBody(), TEXT("head"), 1.1f);
        NextTaunt = FMath::Max(NextTaunt, StateClock + 10.0f);
    }
    if (PhaseTwoAt >= 0.0f && !(StoryLines & 4) && StateClock >= PhaseTwoAt + 7.5f)
    {
        StoryLines |= 4;
        ReflectionsVillainFx::Voice(LineWorld, ReflectionsVillainAssets::StoryLine(TEXT("MQ09_04")), GetPlayer());
    }
    if (StateClock >= NextTaunt)
    {
        NextTaunt = StateClock + FMath::FRandRange(9.0f, 15.0f);
        ReflectionsVillainFx::VoiceOn(ReflectionsVillainAssets::VoTaunt(), Look->GetBody(), TEXT("head"), 1.0f);
    }
}

void AReflectionsVillainBoss::ChooseAttack()
{
    if (bBlinkFirst || (bPhaseTwo && FMath::FRand() < 0.45f))
    {
        bBlinkFirst = false;
        Blink();
    }
    struct FWeighted
    {
        EReflectionsVillainAttack Attack;
        float Weight;
    };
    const FWeighted Options[] = {
        {EReflectionsVillainAttack::Volley, 0.4f},
        {EReflectionsVillainAttack::Grasp, 0.35f},
        {EReflectionsVillainAttack::Wave, bPhaseTwo ? 0.35f : 0.25f},
    };
    float Total = 0.0f;
    for (const FWeighted& Option : Options)
    {
        Total += Option.Attack == LastAttack ? 0.0f : Option.Weight;
    }
    float Roll = FMath::FRand() * Total;
    EReflectionsVillainAttack Pick = EReflectionsVillainAttack::Volley;
    for (const FWeighted& Option : Options)
    {
        if (Option.Attack == LastAttack)
        {
            continue;
        }
        Pick = Option.Attack;
        Roll -= Option.Weight;
        if (Roll <= 0.0f)
        {
            break;
        }
    }
    StartAttack(Pick);
}

void AReflectionsVillainBoss::StartAttack(EReflectionsVillainAttack NewAttack)
{
    Attack = NewAttack;
    LastAttack = NewAttack;
    AttackClock = 0.0f;
    OrbsFired = 0;
    WavesFired = 0;
    bHazardsSpawned = false;
    UWorld* World = GetWorld();
    ReflectionsVillainFx::Sound(World, ReflectionsVillainAssets::TelegraphSound(), GetActorLocation(), 1.0f, 0.7f);
    Look->Flash(0.6f);
    switch (NewAttack)
    {
    case EReflectionsVillainAttack::Volley:
    {
        Telegraph = TelegraphTime(1.25f);
        OrbCount = bPhaseTwo ? 5 : 3;
        ClearCharge();
        for (int32 Index = 0; Index < OrbCount; ++Index)
        {
            const float Alpha = OrbCount > 1 ? static_cast<float>(Index) / (OrbCount - 1) : 0.5f;
            const float Angle = FMath::DegreesToRadians(FMath::Lerp(-55.0f, 55.0f, Alpha));
            UNiagaraComponent* Orb = ReflectionsVillainFx::Projectile(World, Capsule, FVector::ZeroVector, ReflectionsVillainColors::Violet,
                ReflectionsVillainColors::Lilac, 0.3f);
            if (Orb)
            {
                Orb->SetRelativeLocation(FVector(50.0f, FMath::Sin(Angle) * 130.0f, 150.0f + FMath::Cos(Angle) * 70.0f));
            }
            ChargeOrbs.Add(Orb);
        }
        Look->PlayAnimation(ReflectionsVillainAssets::VolleyAnim(), false, 0.7f);
        break;
    }
    case EReflectionsVillainAttack::Grasp:
        Telegraph = TelegraphTime(1.6f);
        SpawnHazards();
        Look->PlayAnimation(ReflectionsVillainAssets::SlamAnim(), false, 0.9f);
        break;
    case EReflectionsVillainAttack::Wave:
    {
        Telegraph = TelegraphTime(1.35f);
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        const FVector Ground(GetActorLocation().X, GetActorLocation().Y, ArenaCenter.Z + 3.0f);
        if (AReflectionsVillainHazard* Ring = World->SpawnActor<AReflectionsVillainHazard>(AReflectionsVillainHazard::StaticClass(), Ground,
            FRotator::ZeroRotator, Params))
        {
            Ring->Setup(380.0f, 0.0f, 0.0f, this, Telegraph);
            Spawned.Add(Ring);
        }
        Look->PlayAnimation(ReflectionsVillainAssets::WaveAnim(), false, 0.75f);
        Look->SetShroudAmount(0.7f);
        break;
    }
    default:
        break;
    }
}

void AReflectionsVillainBoss::TickAttack(float DeltaSeconds)
{
    AttackClock += DeltaSeconds;
    UWorld* World = GetWorld();
    // Every attack winds up on his body too: rim, cracks, eyes and heart brighten toward the strike (dodge on the peak).
    Look->SetGlow(AttackClock < Telegraph ? 1.0f + 2.5f * Ease(AttackClock / FMath::Max(0.1f, Telegraph)) : 1.0f);
    switch (Attack)
    {
    case EReflectionsVillainAttack::Volley:
    {
        const float Charge = FMath::Lerp(0.3f, 1.35f, Ease(AttackClock / Telegraph));
        for (UNiagaraComponent* Orb : ChargeOrbs)
        {
            if (Orb)
            {
                Orb->SetVariableFloat(TEXT("User.Scale"), Charge);
            }
        }
        if (OrbsFired < OrbCount && AttackClock >= Telegraph + OrbsFired * 0.32f)
        {
            FireOrb(OrbsFired++);
        }
        if (OrbsFired >= OrbCount && AttackClock >= Telegraph + OrbCount * 0.32f + 0.5f)
        {
            EndAttack();
        }
        break;
    }
    case EReflectionsVillainAttack::Grasp:
        if (!bHazardsSpawned && AttackClock >= Telegraph)
        {
            bHazardsSpawned = true;
            Look->Flash(0.9f);
        }
        if (AttackClock >= Telegraph + 0.9f)
        {
            EndAttack();
        }
        break;
    case EReflectionsVillainAttack::Wave:
        if (WavesFired == 0 && AttackClock >= Telegraph)
        {
            WavesFired = 1;
            SpawnWave();
        }
        if (bPhaseTwo && WavesFired == 1 && AttackClock >= Telegraph + 0.95f)
        {
            WavesFired = 2;
            SpawnWave();
        }
        if (AttackClock >= Telegraph + (bPhaseTwo ? 2.3f : 1.5f))
        {
            Look->SetShroudAmount(bPhaseTwo ? 0.45f : 0.25f);
            EndAttack();
        }
        break;
    default:
        EndAttack();
        break;
    }
}

void AReflectionsVillainBoss::EndAttack()
{
    Attack = EReflectionsVillainAttack::None;
    ClearCharge();
    NextAttack = StateClock + (bPhaseTwo ? 1.3f : 2.1f) * FMath::FRandRange(0.85f, 1.2f);
    Look->PlayAnimation(ReflectionsVillainAssets::HoverAnim(), true, 0.6f);
}

void AReflectionsVillainBoss::ClearCharge()
{
    for (UNiagaraComponent* Orb : ChargeOrbs)
    {
        if (Orb)
        {
            Orb->DestroyComponent();
        }
    }
    ChargeOrbs.Reset();
}

void AReflectionsVillainBoss::FireOrb(int32 Index)
{
    UWorld* World = GetWorld();
    FVector From = Look->GetChestLocation() + GetActorForwardVector() * 60.0f;
    if (ChargeOrbs.IsValidIndex(Index) && ChargeOrbs[Index])
    {
        From = ChargeOrbs[Index]->GetComponentLocation();
        ChargeOrbs[Index]->DestroyComponent();
        ChargeOrbs[Index] = nullptr;
    }
    const APawn* Player = GetPlayer();
    if (!World || !Player)
    {
        return;
    }
    // Partial lead: standing still is punished, strafing steadily is safe.
    const FVector Aim = Player->GetActorLocation() + FVector(0.0f, 0.0f, 20.0f) + Player->GetVelocity() * 0.3f * FMath::FRand();
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Params.Instigator = this;
    if (AReflectionsVillainOrb* Orb = World->SpawnActor<AReflectionsVillainOrb>(AReflectionsVillainOrb::StaticClass(), From,
        FRotator::ZeroRotator, Params))
    {
        Orb->Fire((Aim - From).GetSafeNormal(), bPhaseTwo ? 1750.0f : 1450.0f, 10.0f * ReflectionsVillainTuning::AttackDamageScale(), this);
        Spawned.Add(Orb);
    }
    ReflectionsVillainFx::Sound(World, ReflectionsVillainAssets::OrbSound(), From, 0.6f, 0.75f);
}

void AReflectionsVillainBoss::SpawnHazards()
{
    UWorld* World = GetWorld();
    APawn* Player = GetPlayer();
    if (!World || !Player)
    {
        return;
    }
    const FVector Feet = ReflectionsVillainFx::Ground(World, Player->GetActorLocation(), Player);
    TArray<FVector> Points = {Feet};
    const int32 Extra = bPhaseTwo ? 4 : 2;
    const float Start = FMath::FRandRange(0.0f, 2.0f * PI);
    for (int32 Index = 0; Index < Extra; ++Index)
    {
        const float Angle = Start + Index * 2.0f * PI / Extra;
        const FVector Offset = FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f)
            * FMath::FRandRange(FMath::Min(300.0f, ArenaRadius * 0.35f), FMath::Min(540.0f, ArenaRadius * 0.6f));
        Points.Add(ReflectionsVillainFx::Ground(World, Feet + Offset, Player));
    }
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    for (const FVector& Point : Points)
    {
        if (AReflectionsVillainHazard* Hazard = World->SpawnActor<AReflectionsVillainHazard>(AReflectionsVillainHazard::StaticClass(),
            Point + FVector(0.0f, 0.0f, 3.0f), FRotator::ZeroRotator, Params))
        {
            Hazard->Setup(FMath::Min(240.0f, ArenaRadius * 0.4f), Telegraph, 18.0f * ReflectionsVillainTuning::AttackDamageScale(), this);
            Spawned.Add(Hazard);
        }
    }
}

void AReflectionsVillainBoss::SpawnWave()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }
    const FVector Ground(GetActorLocation().X, GetActorLocation().Y, ArenaCenter.Z + 2.0f);
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    if (AReflectionsVillainWave* Wave = World->SpawnActor<AReflectionsVillainWave>(AReflectionsVillainWave::StaticClass(), Ground,
        FRotator::ZeroRotator, Params))
    {
        Wave->Setup(bPhaseTwo ? 850.0f : 720.0f, ArenaRadius + 900.0f, 14.0f * ReflectionsVillainTuning::AttackDamageScale(), this);
        Spawned.Add(Wave);
    }
    ReflectionsVillainFx::Impact(World, Ground + FVector(0.0f, 0.0f, 20.0f), ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 2.6f, 3.0f);
    ReflectionsVillainFx::Sound(World, ReflectionsVillainAssets::SlamSound(), Ground, 1.0f, 0.8f);
    Look->Flash(0.8f);
}

void AReflectionsVillainBoss::Blink()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }
    const FVector From = GetActorLocation();
    ReflectionsVillainFx::Impact(World, From, ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 1.8f, 3.0f);
    ReflectionsVillainFx::Sound(World, ReflectionsVillainAssets::HopSound(), From);
    const APawn* Player = GetPlayer();
    FVector Pick = ArenaCenter;
    for (int32 Try = 0; Try < 8; ++Try)
    {
        const float Angle = FMath::FRandRange(0.0f, 2.0f * PI);
        const FVector Candidate = ArenaCenter + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f) * FMath::FRandRange(250.0f, ArenaRadius * 0.55f);
        if (!Player || FVector::Dist2D(Candidate, Player->GetActorLocation()) > 500.0f)
        {
            Pick = Candidate;
            break;
        }
    }
    Station = ReflectionsVillainFx::Ground(World, Pick, this, 400.0f, 1500.0f);
    SetActorLocation(Station + FVector(0.0f, 0.0f, HalfHeight + HoverHeight), false, nullptr, ETeleportType::TeleportPhysics);
    ReflectionsVillainFx::Impact(World, GetActorLocation(), ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 1.8f, 3.0f);
    Look->PlayAnimation(ReflectionsVillainAssets::BlinkAnim(), false, 1.0f);
}

float AReflectionsVillainBoss::TakeDamage(float DamageAmount, FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser)
{
    Super::TakeDamage(DamageAmount, DamageEvent, EventInstigator, DamageCauser);
    if (State != EReflectionsVillainBossState::Fighting || DamageAmount <= 0.0f)
    {
        return 0.0f;
    }
    const bool bFinal = DamageEvent.DamageTypeClass && DamageEvent.DamageTypeClass->IsChildOf(UReflectionsFinalSpellDamageType::StaticClass());
    const float Applied = bFinal ? DamageAmount : DamageAmount * ReflectionsVillainTuning::OtherSpellScale();
    const bool bWasPhaseOne = !bPhaseTwo;
    Health = FMath::Max(0.0f, Health - Applied);
    UWorld* World = GetWorld();
    if (bFinal)
    {
        Look->Flash(1.6f);
        ReflectionsVillainFx::Sound(World, ReflectionsVillainAssets::HurtSound(), GetActorLocation(), 1.0f, 0.8f);
        if (!bFirstFinalHit)
        {
            // Story MQ09_02, the hero: "That's for Jory."
            bFirstFinalHit = true;
            ReflectionsVillainFx::Voice(World, ReflectionsVillainAssets::StoryLine(TEXT("MQ09_02")), GetPlayer());
        }
        if (StateClock - LastHurtVoice > 6.0f && Health > 0.0f)
        {
            LastHurtVoice = StateClock;
            ReflectionsVillainFx::VoiceOn(ReflectionsVillainAssets::VoHurt(), Look->GetBody(), TEXT("head"), 1.0f);
        }
    }
    else
    {
        Look->Flash(0.2f);
        ReflectionsVillainFx::Sound(World, ReflectionsVillainAssets::ResistSound(), GetActorLocation(), 0.5f, 0.7f);
        if (StateClock - LastResistMessage > 7.0f)
        {
            LastResistMessage = StateClock;
            ReflectionsVillainFx::Message(World, ReflectionsVillainText::Resist());
        }
    }
    if (bWasPhaseOne && Health <= MaxHealth * 0.5f && Health > 0.0f)
    {
        bPhaseTwo = true;
        bBlinkFirst = true;
        PhaseTwoAt = StateClock;
        Look->SetShroudAmount(0.45f);
        Look->Flash(2.0f);
        ReflectionsVillainFx::Message(World, ReflectionsVillainText::PhaseTwo(), ReflectionsVillainColors::Lilac);
        ReflectionsVillainFx::VoiceOn(ReflectionsVillainAssets::VoPhaseTwo(), Look->GetBody(), TEXT("head"), 1.1f);
    }
    UpdateHud(true);
    if (Health <= 0.0f)
    {
        Die();
    }
    return Applied;
}

// ---------------------------------------------------------------------------------------------- death

void AReflectionsVillainBoss::Die()
{
    if (State == EReflectionsVillainBossState::Dying || State == EReflectionsVillainBossState::Dead)
    {
        return;
    }
    State = EReflectionsVillainBossState::Dying;
    StateClock = 0.0f;
    NextBurst = 0.0f;
    Attack = EReflectionsVillainAttack::None;
    ClearCharge();
    for (const TWeakObjectPtr<AActor>& Actor : Spawned)
    {
        if (AActor* Resolved = Actor.Get())
        {
            Resolved->Destroy();
        }
    }
    Spawned.Reset();
    Capsule->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    if (Music)
    {
        Music->FadeOut(2.5f, 0.0f);
    }
    UWorld* World = GetWorld();
    ReflectionsVillainFx::Sound2D(World, ReflectionsVillainAssets::DeathSound());
    USoundBase* FinalBlow = ReflectionsVillainAssets::StoryLine(TEXT("MQ09_05"));
    ReflectionsVillainFx::VoiceOn(FinalBlow ? FinalBlow : ReflectionsVillainAssets::VoDeath(), Look->GetBody(), TEXT("head"), 1.2f);
    bDeathLine = FinalBlow == nullptr;
    ReflectionsVillainFx::Duck(World);
    Look->PlayAnimation(ReflectionsVillainAssets::SlamAnim(), false, 0.4f);
    ReflectionsVillainFx::Message(World, ReflectionsVillainText::Unmade(), ReflectionsVillainColors::FinalGold);
}

void AReflectionsVillainBoss::TickDying(float DeltaSeconds)
{
    const float T = StateClock / DeathTime;
    UWorld* World = GetWorld();
    const FVector Jitter(FMath::FRandRange(-1.0f, 1.0f), FMath::FRandRange(-1.0f, 1.0f), 0.0f);
    Look->SetRelativeLocation(FVector(0.0f, 0.0f, -HalfHeight + T * 70.0f) + Jitter * 7.0f * T);
    Look->SetRelativeScale3D(FVector(FMath::Lerp(1.0f, 0.05f, Ease((T - 0.55f) / 0.45f))));
    Look->Flash(1.0f + T * 2.0f);
    Look->SetShroudAmount(2.0f);
    if (!bDeathLine && StateClock >= 2.2f)
    {
        bDeathLine = true;
        ReflectionsVillainFx::VoiceOn(ReflectionsVillainAssets::VoDeath(), Look->GetBody(), TEXT("head"), 1.2f);
    }
    if (StateClock >= NextBurst)
    {
        NextBurst = StateClock + 0.3f;
        const bool bGold = FMath::RandBool();
        const FVector Point = Look->GetChestLocation() + FMath::VRand() * FMath::FRandRange(20.0f, 90.0f);
        ReflectionsVillainFx::Impact(World, Point, bGold ? ReflectionsVillainColors::FinalGold : ReflectionsVillainColors::Violet,
            ReflectionsVillainColors::FinalWhite, FMath::FRandRange(1.0f, 1.7f), 1.5f);
    }
    if (StateClock > 1.0f && StateClock - DeltaSeconds <= 1.0f)
    {
        UpdateHud(false);
    }
    if (T < 1.0f)
    {
        return;
    }
    ReflectionsVillainFx::Impact(World, Look->GetChestLocation(), ReflectionsVillainColors::FinalGold, ReflectionsVillainColors::FinalWhite, 4.5f, 4.0f);
    Look->SetLookVisible(false);
    State = EReflectionsVillainBossState::Dead;
    UpdateHud(false);
    if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(World))
    {
        Villain->NotifyBossDefeated(this);
    }
    SetLifeSpan(5.0f);
}

// ============================================================================================ orb

AReflectionsVillainOrb::AReflectionsVillainOrb()
{
    PrimaryActorTick.bCanEverTick = true;
    InitialLifeSpan = 5.0f;
    Collision = CreateDefaultSubobject<USphereComponent>(TEXT("Collision"));
    RootComponent = Collision;
    Collision->InitSphereRadius(26.0f);
    Collision->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Collision->SetCollisionObjectType(ECC_WorldDynamic);
    Collision->SetCollisionResponseToAllChannels(ECR_Ignore);
    Collision->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    Collision->SetCanEverAffectNavigation(false);
    Collision->OnComponentHit.AddDynamic(this, &AReflectionsVillainOrb::HandleHit);
    Movement = CreateDefaultSubobject<UProjectileMovementComponent>(TEXT("Movement"));
    Movement->UpdatedComponent = Collision;
    Movement->ProjectileGravityScale = 0.0f;
    Movement->InitialSpeed = 0.0f;
    Movement->bInitialVelocityInLocalSpace = false;
    Movement->bRotationFollowsVelocity = true;
    Movement->bShouldBounce = false;
}

void AReflectionsVillainOrb::BeginPlay()
{
    Super::BeginPlay();
    Visual = ReflectionsVillainFx::Projectile(GetWorld(), Collision, FVector::ZeroVector, ReflectionsVillainColors::Violet,
        ReflectionsVillainColors::Lilac, 1.35f);
}

void AReflectionsVillainOrb::Fire(const FVector& Direction, float Speed, float InDamage, AActor* InBoss)
{
    Boss = InBoss;
    Damage = InDamage;
    if (InBoss)
    {
        Collision->IgnoreActorWhenMoving(InBoss, true);
    }
    Movement->Velocity = Direction.GetSafeNormal() * Speed;
    Movement->MaxSpeed = Speed;
}

void AReflectionsVillainOrb::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (bDone)
    {
        return;
    }
    // Contact by distance so the orb never depends on the player's collision profile.
    if (APawn* Player = ReflectionsVillainFx::PlayerPawn(GetWorld()))
    {
        float Radius = 40.0f, Half = 90.0f;
        Player->GetSimpleCollisionCylinder(Radius, Half);
        const FVector Delta = GetActorLocation() - Player->GetActorLocation();
        if (FMath::Abs(Delta.Z) < Half + 26.0f && Delta.Size2D() < Radius + 30.0f)
        {
            Explode(Player);
        }
    }
}

void AReflectionsVillainOrb::HandleHit(UPrimitiveComponent* HitComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, FVector NormalImpulse,
    const FHitResult& Hit)
{
    if (!bDone && OtherActor != Boss.Get())
    {
        Explode(nullptr);
    }
}

void AReflectionsVillainOrb::Explode(AActor* Victim)
{
    bDone = true;
    UWorld* World = GetWorld();
    const FVector Point = GetActorLocation();
    if (Victim)
    {
        ReflectionsVillainFx::Damage(Victim, Damage, Boss.Get() ? Boss.Get() : this, Point - Movement->Velocity.GetSafeNormal() * 50.0f, 260.0f, nullptr);
    }
    ReflectionsVillainFx::Impact(World, Point, ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 1.0f, 1.2f);
    ReflectionsVillainFx::Sound(World, ReflectionsVillainAssets::OrbSound(), Point, 0.7f, 0.65f);
    Movement->StopMovementImmediately();
    Collision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    if (Visual)
    {
        Visual->Deactivate();
    }
    SetLifeSpan(1.0f);
}

// ============================================================================================ hazard

AReflectionsVillainHazard::AReflectionsVillainHazard()
{
    PrimaryActorTick.bCanEverTick = true;
    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    RootComponent = Root;
    Disc = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Disc"));
    Disc->SetupAttachment(Root);
    Disc->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Disc->SetGenerateOverlapEvents(false);
    Disc->SetCanEverAffectNavigation(false);
    Disc->SetCastShadow(false);
    Disc->bReceivesDecals = false;
    SetActorEnableCollision(false);
}

void AReflectionsVillainHazard::Setup(float InRadius, float InDelay, float InDamage, AActor* InBoss, float FadeAfter)
{
    Radius = InRadius;
    Delay = InDelay;
    Damage = InDamage;
    Boss = InBoss;
    bWarningOnly = InDelay <= 0.0f;
    Life = bWarningOnly ? FMath::Max(0.2f, FadeAfter) : InDelay;
    Disc->SetStaticMesh(ReflectionsVillainAssets::DiscMesh());
    Disc->SetRelativeScale3D(FVector(Radius / 50.0f, Radius / 50.0f, 1.0f));
    Material = TelegraphMaterial(this);
    if (Material)
    {
        Material->SetScalarParameterValue(TEXT("Progress"), 0.0f);
        Material->SetScalarParameterValue(TEXT("Band"), bWarningOnly ? 0.12f : 0.07f);
        Material->SetScalarParameterValue(TEXT("Opacity"), 1.0f);
        Disc->SetMaterial(0, Material);
    }
}

void AReflectionsVillainHazard::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    Clock += DeltaSeconds;
    if (!bErupted)
    {
        const float T = FMath::Clamp(Clock / Life, 0.0f, 1.0f);
        if (Material)
        {
            Material->SetScalarParameterValue(TEXT("Progress"), bWarningOnly ? 0.0f : T);
            Material->SetScalarParameterValue(TEXT("Opacity"), bWarningOnly ? 0.6f + 0.4f * FMath::Sin(Clock * 18.0f) : 1.0f);
        }
        if (T >= 1.0f)
        {
            if (bWarningOnly)
            {
                Destroy();
            }
            else
            {
                Erupt();
            }
        }
        return;
    }
    const float Fade = 1.0f - Clock / 0.5f;
    if (Material)
    {
        Material->SetScalarParameterValue(TEXT("Opacity"), FMath::Max(0.0f, Fade));
    }
    if (Fade <= 0.0f)
    {
        Destroy();
    }
}

void AReflectionsVillainHazard::Erupt()
{
    bErupted = true;
    Clock = 0.0f;
    UWorld* World = GetWorld();
    const FVector Point = GetActorLocation();
    ReflectionsVillainFx::Impact(World, Point + FVector(0.0f, 0.0f, 15.0f), ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac,
        Radius / 110.0f, 3.0f);
    ReflectionsVillainFx::Impact(World, Point + FVector(0.0f, 0.0f, 120.0f), ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac,
        Radius / 160.0f, 2.0f);
    ReflectionsVillainFx::Sound(World, ReflectionsVillainAssets::SlamSound(), Point, 0.8f, 0.9f);
    if (APawn* Player = ReflectionsVillainFx::PlayerPawn(World))
    {
        const FVector Delta = Player->GetActorLocation() - Point;
        if (Delta.Size2D() < Radius + 25.0f && Delta.Z < 260.0f && Delta.Z > -100.0f)
        {
            ReflectionsVillainFx::Damage(Player, Damage, Boss.Get() ? Boss.Get() : this, Point - FVector(0.0f, 0.0f, 80.0f), 380.0f, nullptr);
        }
    }
}

// ============================================================================================ wave

AReflectionsVillainWave::AReflectionsVillainWave()
{
    PrimaryActorTick.bCanEverTick = true;
    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    RootComponent = Root;
    Spikes = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Spikes"));
    Spikes->SetupAttachment(Root);
    Spikes->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Spikes->SetGenerateOverlapEvents(false);
    Spikes->SetCanEverAffectNavigation(false);
    Spikes->SetCastShadow(false);
    Band = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Band"));
    Band->SetupAttachment(Root);
    Band->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Band->SetGenerateOverlapEvents(false);
    Band->SetCanEverAffectNavigation(false);
    Band->SetCastShadow(false);
    Band->bReceivesDecals = false;
    SetActorEnableCollision(false);
}

void AReflectionsVillainWave::Setup(float InSpeed, float InMaxRadius, float InDamage, AActor* InBoss)
{
    Speed = InSpeed;
    MaxRadius = InMaxRadius;
    Damage = InDamage;
    Boss = InBoss;
    if (UStaticMesh* Cone = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cone.Cone"), nullptr, LOAD_NoWarn | LOAD_Quiet))
    {
        Spikes->SetStaticMesh(Cone);
    }
    if (UMaterialInterface* Black = ReflectionsVillainAssets::BodyMaterial())
    {
        UMaterialInstanceDynamic* Dynamic = UMaterialInstanceDynamic::Create(Black, this);
        Dynamic->SetScalarParameterValue(TEXT("Glow"), 2.5f);
        Spikes->SetMaterial(0, Dynamic);
    }
    constexpr int32 Count = 64;
    Phases.SetNum(Count);
    for (int32 Index = 0; Index < Count; ++Index)
    {
        Phases[Index] = FMath::FRandRange(0.0f, 2.0f * PI);
        Spikes->AddInstance(FTransform::Identity);
    }
    Band->SetStaticMesh(ReflectionsVillainAssets::DiscMesh());
    BandMaterial = TelegraphMaterial(this);
    if (BandMaterial)
    {
        BandMaterial->SetScalarParameterValue(TEXT("Progress"), 0.0f);
        BandMaterial->SetScalarParameterValue(TEXT("Opacity"), 1.0f);
        Band->SetMaterial(0, BandMaterial);
    }
}

void AReflectionsVillainWave::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    Clock += DeltaSeconds;
    Radius += Speed * DeltaSeconds;
    const float Fade = 1.0f - FMath::Clamp((Radius / MaxRadius - 0.85f) / 0.15f, 0.0f, 1.0f);

    // Spikes stand on their base whatever the cone mesh's pivot.
    float BaseOffset = 50.0f;
    if (const UStaticMesh* Mesh = Spikes->GetStaticMesh())
    {
        BaseOffset = -Mesh->GetBoundingBox().Min.Z;
    }
    const int32 Count = Phases.Num();
    TArray<FTransform> Transforms;
    Transforms.Reserve(Count);
    for (int32 Index = 0; Index < Count; ++Index)
    {
        const float Angle = Index * 2.0f * PI / FMath::Max(1, Count);
        const float Height = (0.7f + 0.35f * FMath::Sin(Clock * 9.0f + Phases[Index])) * Fade;
        const FVector Scale(0.3f, 0.3f, FMath::Max(0.01f, Height));
        const FVector Position = FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f) * Radius + FVector(0.0f, 0.0f, BaseOffset * Scale.Z);
        Transforms.Add(FTransform(FRotator::ZeroRotator, Position, Scale));
    }
    Spikes->BatchUpdateInstancesTransforms(0, Transforms, false, true, true);
    Band->SetRelativeScale3D(FVector((Radius + 60.0f) / 50.0f, (Radius + 60.0f) / 50.0f, 1.0f));
    if (BandMaterial)
    {
        BandMaterial->SetScalarParameterValue(TEXT("Band"), FMath::Clamp(120.0f / (Radius + 60.0f), 0.01f, 0.6f));
        BandMaterial->SetScalarParameterValue(TEXT("Opacity"), Fade);
    }

    if (!bHit)
    {
        if (APawn* Player = ReflectionsVillainFx::PlayerPawn(GetWorld()))
        {
            const float Distance = FVector::Dist2D(Player->GetActorLocation(), GetActorLocation());
            const ACharacter* Character = Cast<ACharacter>(Player);
            const bool bAirborne = Character && Character->GetCharacterMovement() && Character->GetCharacterMovement()->IsFalling()
                && Player->GetActorLocation().Z - Player->GetSimpleCollisionHalfHeight() > GetActorLocation().Z + 25.0f;
            const float Height = Player->GetActorLocation().Z - GetActorLocation().Z;
            if (FMath::Abs(Distance - Radius) < 75.0f && !bAirborne && Height < 300.0f && Height > -150.0f)
            {
                bHit = true;
                ReflectionsVillainFx::Damage(Player, Damage, Boss.Get() ? Boss.Get() : this, GetActorLocation(), 520.0f, nullptr);
            }
        }
    }
    if (Radius >= MaxRadius)
    {
        Destroy();
    }
}

#undef LOCTEXT_NAMESPACE
