#include "Squads/ReflectionsSquad.h"

#include "Squads/ReflectionsSquadNpcBridge.h"
#include "Squads/ReflectionsSquadRoute.h"

#include "Animation/AnimSequence.h"
#include "Components/BillboardComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DrawDebugHelpers.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "HAL/IConsoleManager.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/StaticMesh.h"
#include "Sound/SoundBase.h"
#include "Components/AudioComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/Skeleton.h"
#include "Materials/MaterialInterface.h"
#include "NavigationPath.h"
#include "NavigationSystem.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"

namespace
{
    TAutoConsoleVariable<int32> CVarSquadDebug(
        TEXT("Squads.Debug"), 0,
        TEXT("1 draws squad anchors, slots and routes; 2 also prints member states."),
        ECVF_Default);

    TAutoConsoleVariable<int32> CVarSquadBodyClips(
        TEXT("Squads.BodyClips"), 0,
        TEXT("1 plays the cast gesture on the visible MetaHuman body (single-clip mode). 0 (default, crash-safe) plays ")
        TEXT("it on the hidden walker; the body follows."),
        ECVF_Default);

    TAutoConsoleVariable<int32> CVarSquadMarchClip(
        TEXT("Squads.MarchClip"), 0,
        TEXT("1 plays the squad's march loop while in formation; 0 uses the NPC locomotion walk instead."),
        ECVF_Default);

    TAutoConsoleVariable<int32> CVarSquadPauseDriverAnim(
        TEXT("Squads.PauseDriverAnim"), 0,
        TEXT("1 stops the hidden locomotion pawn's (motion matching) animation while a soldier plays the march loop; its body does not use that pose then."),
        ECVF_Default);

    TAutoConsoleVariable<int32> CVarSquadPassive(
        TEXT("Squads.Passive"), 0,
        TEXT("1 makes squads ignore the player (sight, spells and hits) so they only march. For testing."),
        ECVF_Default);

    const FName CastHand(TEXT("hand_r"));
    const TCHAR* TelegraphPath = TEXT("/Game/Characters/Hero/SpellVFX/Systems/NS_Spell_Projectile.NS_Spell_Projectile");

    FVector Flat(const FVector& V)
    {
        return FVector(V.X, V.Y, 0.0);
    }

    FVector RightOf(const FVector& Direction)
    {
        return FVector(-Direction.Y, Direction.X, 0.0);
    }

    bool IsActive(const FReflectionsSquadMember& Member)
    {
        return IsValid(Member.Actor) && Member.State != EReflectionsSquadMemberState::Dead &&
            Member.State != EReflectionsSquadMemberState::Released;
    }

    bool IsPlayerDown(AActor* Player)
    {
        if (!IsValid(Player))
        {
            return true;
        }
        const UReflectionsHealthComponent* Health = Player->FindComponentByClass<UReflectionsHealthComponent>();
        return Health && Health->Health <= 0.0f;
    }
}

AReflectionsSquad::AReflectionsSquad()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PrePhysics;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(SceneRoot);
#if WITH_EDITORONLY_DATA
    Sprite = CreateEditorOnlyDefaultSubobject<UBillboardComponent>(TEXT("Sprite"));
    if (Sprite)
    {
        Sprite->SetupAttachment(SceneRoot);
        Sprite->bIsScreenSizeScaled = true;
    }
#endif
    // White London raiders: tattooed guard looks the NPC owner already built (no new characters).
    MeleeLooks.Add(TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_06_GuardBoldRunes.BP_WhiteLook_06_GuardBoldRunes_C"))));
    MeleeLooks.Add(TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_05_GuardRags.BP_WhiteLook_05_GuardRags_C"))));
    // Casters: the tattooed, mantled White London looks. Their IvenRook body shares the hero's skeleton, so the
    // hero's Kimodo cast clips play on them as they are.
    CasterLooks.Add(TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_04_CapMantle.BP_WhiteLook_04_CapMantle_C"))));
    CasterLooks.Add(TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_03_Mantle.BP_WhiteLook_03_Mantle_C"))));
    CasterSpells = { EHeroSpell::Fire, EHeroSpell::IceShard, EHeroSpell::ArcaneBolt };
    // Codex's Lanthorne props (ArtDirection/LanthorneAssets): real-world size, grip at the pivot, blade along +X.
    ShieldMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/LanthorneAssets/Giltside/Props/SM_Giltside_PatrolShield.SM_Giltside_PatrolShield")));
    WalkerChannelAnimation = TSoftObjectPtr<UAnimSequenceBase>(FSoftObjectPath(TEXT("/Game/Combat/Melee/AS_Melee_Wand_Channel_Walker.AS_Melee_Wand_Channel_Walker")));
    WalkerReleaseAnimation = TSoftObjectPtr<UAnimSequenceBase>(FSoftObjectPath(TEXT("/Game/Combat/Melee/AS_Melee_Wand_Flick_Walker.AS_Melee_Wand_Flick_Walker")));
    MarchLoop = TSoftObjectPtr<USoundBase>(FSoftObjectPath(TEXT("/Game/Audio/Jam/Cues/SCue_March_Loop.SCue_March_Loop")));
    ShieldHitSounds.Add(TSoftObjectPtr<USoundBase>(FSoftObjectPath(TEXT("/Game/Audio/Jam/Cues/SCue_Sword_ShieldHit.SCue_Sword_ShieldHit"))));
    ShieldHitSounds.Add(TSoftObjectPtr<USoundBase>(FSoftObjectPath(TEXT("/Game/Audio/Jam/Cues/SCue_Shield_BlockHeavy.SCue_Shield_BlockHeavy"))));
    MeleeWeapon = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/LanthorneAssets/Frostside/Props/SM_Frostside_MirrorSword.SM_Frostside_MirrorSword")));
    // User: every soldier holds a sword (casters cast from the sword hand) and a shield on the left arm.
    CasterWeapon = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/LanthorneAssets/Frostside/Props/SM_Frostside_MirrorSword.SM_Frostside_MirrorSword")));
    // Kimodo march cycle (Tools/Squads/author_march.py), one copy per soldier skeleton.
    MarchAnimations.Add(TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(TEXT("/Game/Squads/Animation/AS_Soldier_March_Iven.AS_Soldier_March_Iven"))));
    MarchAnimations.Add(TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(TEXT("/Game/Squads/Animation/AS_Soldier_March_BridgeGuard.AS_Soldier_March_BridgeGuard"))));
    CastAnimations.Add(TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(TEXT("/Game/Characters/Hero/Animation/CombatCasts/AS_Hero_CombatBoltRight.AS_Hero_CombatBoltRight"))));
    // Spell crafting's Kimodo wand set (ArtDirection/CombatMelee): channel while the spell gathers, flick to throw it.
    // One copy per body skeleton in use; ClipFor picks the one that matches each caster.
    for (const TCHAR* Body : { TEXT("IvenRook"), TEXT("BridgeGuard"), TEXT("CoinClerk") })
    {
        ChannelAnimations.Add(TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(
            FString::Printf(TEXT("/Game/Combat/Melee/AS_Melee_Wand_Channel_%s.AS_Melee_Wand_Channel_%s"), Body, Body))));
        ReleaseAnimations.Add(TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(
            FString::Printf(TEXT("/Game/Combat/Melee/AS_Melee_Wand_Flick_%s.AS_Melee_Wand_Flick_%s"), Body, Body))));
    }
}

void AReflectionsSquad::BeginPlay()
{
    Super::BeginPlay();
    SquadSeed = static_cast<int32>(GetTypeHash(GetFName()) & 0xffff);
    TelegraphSystem = LoadObject<UNiagaraSystem>(nullptr, TelegraphPath);
    if (UReflectionsSpellEventSubsystem* Events = GetWorld()->GetSubsystem<UReflectionsSpellEventSubsystem>())
    {
        Events->OnSpellEvent.AddUniqueDynamic(this, &AReflectionsSquad::HandleSpellEvent);
    }
    if (bFactionFromSide)
    {
        const FString Side = GetSide();
        if (Side == TEXT("Giltside"))
        {
            Faction = EReflectionsSquadFaction::Gilt;
        }
        else if (Side == TEXT("Frostside"))
        {
            Faction = EReflectionsSquadFaction::Frost;
        }
    }
    if (Faction == EReflectionsSquadFaction::Gilt && SightRadius < 1500.0f)
    {
        // An allied squad's sight is for the tarnished and Frost soldiers (never the player): it always looks.
        SightRadius = 2200.0f;
        AlertRadius = FMath::Max(AlertRadius, 700.0f);
    }
    // Hits, deaths and the player's crimes, from the NPC system (who did it matters for an allied squad).
    ReflectionsSquadNpc::BindNpcEvents(this, true);
    CacheRoute();
    if (bSpawnOnBeginPlay)
    {
        SpawnSquad();
    }
}

void AReflectionsSquad::EndPlay(const EEndPlayReason::Type Reason)
{
    if (UWorld* World = GetWorld())
    {
        if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
        {
            Events->OnSpellEvent.RemoveDynamic(this, &AReflectionsSquad::HandleSpellEvent);
        }
        ReflectionsSquadNpc::BindNpcEvents(this, false);
    }
    for (FReflectionsSquadMember& Member : Members)
    {
        EndCast(Member, false);
    }
    // Soldiers live in the persistent level, so they must go with the spawner when its streamed level unloads too;
    // otherwise they stay behind as unsteered NPCs. The spawner raises a fresh squad when the level streams back in.
    if (Reason == EEndPlayReason::Destroyed || Reason == EEndPlayReason::RemovedFromWorld)
    {
        DespawnSquad();
    }
    Super::EndPlay(Reason);
}

// ---- Route and trail ------------------------------------------------------------------------------------------

FVector AReflectionsSquad::GroundAt(const FVector& Location, bool* bOutHit) const
{
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(SquadGround), false, this);
    const bool bHit = GetWorld() && GetWorld()->LineTraceSingleByObjectType(Hit, Location + FVector(0.0, 0.0, 300.0),
        Location - FVector(0.0, 0.0, 2000.0), FCollisionObjectQueryParams(ECC_WorldStatic), Params);
    if (bOutHit)
    {
        *bOutHit = bHit;
    }
    return bHit ? FVector(Hit.ImpactPoint) : Location;
}

void AReflectionsSquad::CacheRoute()
{
    Waypoints.Reset();
    if (Route && Route->GetNumPoints() > 0)
    {
        for (int32 Index = 0; Index < Route->GetNumPoints(); ++Index)
        {
            Waypoints.Add(GroundAt(Route->GetPoint(Index)));
        }
    }
    else
    {
        Waypoints.Add(GroundAt(GetActorLocation()));
    }
    bUseNavigation = false;
    if (UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()))
    {
        FNavLocation Projected;
        bUseNavigation = Nav->ProjectPointToNavigation(Waypoints[0], Projected, FVector(200.0, 200.0, 300.0));
    }
    UE_LOG(LogTemp, Log, TEXT("Squad %s: %d route points, %s"), *GetName(), Waypoints.Num(),
        bUseNavigation ? TEXT("navmesh paths") : TEXT("no navmesh here, straight legs"));
}

void AReflectionsSquad::SeedTrail(const FVector& Head, float Yaw)
{
    Trail.Reset();
    const FVector Forward = FRotator(0.0, Yaw, 0.0).Vector();
    const float Length = (SquadSize + 3) * RankSpacing;
    constexpr float Step = 50.0f;
    for (float Back = Length; Back > 0.0f; Back -= Step)
    {
        Trail.Add({ Head - Forward * Back, Length - Back });
    }
    Trail.Add({ Head, Length });
    TrailHead = Length;
}

void AReflectionsSquad::PushTrail(const FVector& Head)
{
    if (Trail.Num() == 0)
    {
        SeedTrail(Head, AnchorYaw);
        return;
    }
    const float Moved = FVector::Dist2D(Head, Trail.Last().Location);
    if (Moved < 15.0f)
    {
        return;
    }
    TrailHead += Moved;
    Trail.Add({ Head, TrailHead });
    const float Keep = (SquadSize + 3) * RankSpacing + 200.0f;
    int32 Drop = 0;
    while (Drop + 1 < Trail.Num() && Trail[Drop + 1].Distance < TrailHead - Keep)
    {
        ++Drop;
    }
    if (Drop > 0)
    {
        Trail.RemoveAt(0, Drop, EAllowShrinking::No);
    }
}

bool AReflectionsSquad::SampleTrail(float Behind, FVector& OutLocation, FVector& OutDirection) const
{
    const FVector Forward = FRotator(0.0, AnchorYaw, 0.0).Vector();
    if (Trail.Num() == 0)
    {
        OutLocation = AnchorLocation - Forward * Behind;
        OutDirection = Forward;
        return false;
    }
    const float HeadDistance = TrailHead + FVector::Dist2D(AnchorLocation, Trail.Last().Location);
    const float Target = HeadDistance - Behind;
    FVector Next = AnchorLocation;
    float NextDistance = HeadDistance;
    for (int32 Index = Trail.Num() - 1; Index >= 0; --Index)
    {
        const FTrailPoint& Point = Trail[Index];
        if (Point.Distance <= Target)
        {
            const float Segment = NextDistance - Point.Distance;
            const float Alpha = Segment > KINDA_SMALL_NUMBER ? (Target - Point.Distance) / Segment : 0.0f;
            OutLocation = FMath::Lerp(Point.Location, Next, Alpha);
            OutDirection = Flat(Next - Point.Location).GetSafeNormal();
            if (OutDirection.IsNearlyZero())
            {
                OutDirection = Forward;
            }
            return true;
        }
        Next = Point.Location;
        NextDistance = Point.Distance;
    }
    FVector Direction = Trail.Num() > 1 ? Flat(Trail[1].Location - Trail[0].Location).GetSafeNormal() : Forward;
    if (Direction.IsNearlyZero())
    {
        Direction = Forward;
    }
    OutLocation = Trail[0].Location - Direction * (Trail[0].Distance - Target);
    OutDirection = Direction;
    return false;
}

void AReflectionsSquad::BuildLeg(const FVector& From)
{
    LegPoints.Reset();
    LegIndex = 0;
    if (Waypoints.Num() == 0)
    {
        return;
    }
    const FVector Goal = Waypoints[FMath::Clamp(WaypointIndex, 0, Waypoints.Num() - 1)];
    if (bUseNavigation)
    {
        if (UNavigationPath* Path = UNavigationSystemV1::FindPathToLocationSynchronously(this, From, Goal))
        {
            if (Path->IsValid() && Path->PathPoints.Num() >= 2)
            {
                for (int32 Index = 1; Index < Path->PathPoints.Num(); ++Index)
                {
                    LegPoints.Add(Path->PathPoints[Index]);
                }
                return;
            }
        }
    }
    LegPoints.Add(Goal);
}

void AReflectionsSquad::AdvanceAnchor(float DeltaSeconds, float InPace)
{
    const FVector Previous = AnchorLocation;
    if (Waypoints.Num() > 1)
    {
        if (LegPoints.Num() == 0)
        {
            BuildLeg(AnchorLocation);
        }
        float Step = MarchSpeed * InPace * DeltaSeconds;
        while (Step > 0.0f && LegIndex < LegPoints.Num())
        {
            const FVector Goal = LegPoints[LegIndex];
            const FVector To = Flat(Goal - AnchorLocation);
            const float Distance = To.Size();
            if (Distance <= Step)
            {
                AnchorLocation = Goal;
                Step -= Distance;
                ++LegIndex;
            }
            else
            {
                const float Alpha = Step / Distance;
                AnchorLocation += To * Alpha;
                AnchorLocation.Z = FMath::Lerp(AnchorLocation.Z, Goal.Z, Alpha);
                Step = 0.0f;
            }
        }
        if (LegIndex >= LegPoints.Num())
        {
            const bool bLoop = !Route || Route->bLoop;
            if (bLoop)
            {
                WaypointIndex = (WaypointIndex + 1) % Waypoints.Num();
            }
            else
            {
                if (!Waypoints.IsValidIndex(WaypointIndex + WaypointStep))
                {
                    WaypointStep = -WaypointStep;
                }
                WaypointIndex = FMath::Clamp(WaypointIndex + WaypointStep, 0, Waypoints.Num() - 1);
            }
            BuildLeg(AnchorLocation);
            if (Route && Route->HaltSeconds > 0.0f)
            {
                HaltRemaining = Route->HaltSeconds;
                SetState(EReflectionsSquadState::Halted, nullptr);
            }
        }
    }
    AnchorVelocity = DeltaSeconds > 0.0f ? Flat(AnchorLocation - Previous) / DeltaSeconds : FVector::ZeroVector;
    // Face where the column is heading next, turning at a marching rate.
    FVector Heading = AnchorVelocity;
    if (LegPoints.IsValidIndex(LegIndex))
    {
        Heading = Flat(LegPoints[LegIndex] - AnchorLocation);
    }
    if (Heading.SizeSquared() > 1.0f)
    {
        AnchorYaw = FMath::FixedTurn(AnchorYaw, Heading.Rotation().Yaw, TurnRate * DeltaSeconds);
    }
    PushTrail(AnchorLocation);
}

FVector AReflectionsSquad::ComputeSlot(int32 SlotIndex, int32 SlotCount) const
{
    FVector Location, Direction;
    switch (Formation)
    {
    case EReflectionsSquadFormation::Column:
        SampleTrail(SlotIndex * RankSpacing, Location, Direction);
        return Location;
    case EReflectionsSquadFormation::ColumnOfTwos:
    {
        if (SlotIndex == 0)
        {
            SampleTrail(0.0f, Location, Direction);
            return Location;
        }
        const int32 Rank = 1 + (SlotIndex - 1) / 2;
        float Side = ((SlotIndex - 1) % 2 == 0) ? -0.5f : 0.5f;
        if (SlotIndex == SlotCount - 1 && (SlotCount - 1) % 2 == 1)
        {
            Side = 0.0f;
        }
        SampleTrail(Rank * RankSpacing, Location, Direction);
        return Location + RightOf(Direction) * Side * FileSpacing;
    }
    case EReflectionsSquadFormation::Line:
    default:
    {
        const FVector Forward = FRotator(0.0, AnchorYaw, 0.0).Vector();
        const int32 Offset = (SlotIndex + 1) / 2;
        const float Side = SlotIndex % 2 == 1 ? 1.0f : -1.0f;
        return AnchorLocation + RightOf(Forward) * Side * Offset * FileSpacing;
    }
    }
}

// ---- Spawning ---------------------------------------------------------------------------------------------------

void AReflectionsSquad::SpawnSquad()
{
    DespawnSquad();
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }
    // Loaded here (not only at begin play) so clips assigned at runtime apply to the next spawn.
    auto LoadClips = [this](const TArray<TSoftObjectPtr<UAnimSequence>>& Soft, TArray<TObjectPtr<UAnimSequence>>& Out)
    {
        Out.Reset();
        for (const TSoftObjectPtr<UAnimSequence>& Clip : Soft)
        {
            if (UAnimSequence* Loaded = Clip.IsNull() ? nullptr : Clip.LoadSynchronous())
            {
                Out.Add(Loaded);
            }
            else if (!Clip.IsNull())
            {
                UE_LOG(LogTemp, Warning, TEXT("Squad %s: animation %s is missing"), *GetName(), *Clip.ToString());
            }
        }
    };
    ReflectionsSquadNpc::FCasterTuning Tuning;
    if (bUseArchetypeCasterTuning && ReflectionsSquadNpc::GetCasterTuning(this, Tuning,
            Faction == EReflectionsSquadFaction::Gilt ? FName(TEXT("AlliedSoldierCaster")) : FName(TEXT("SoldierCaster"))))
    {
        CasterDamageScale = Tuning.DamageScale;
        CasterMinRange = Tuning.MinRange;
        CasterMaxRange = Tuning.MaxRange;
        CastCooldown = Tuning.Cooldown;
        CastWindup = Tuning.Windup;
        if (CasterSpells.Num() == 0)
        {
            CasterSpells = Tuning.Spells;
        }
        if (!Tuning.CastAnimation.IsNull() && !CastAnimations.Contains(Tuning.CastAnimation))
        {
            CastAnimations.Insert(Tuning.CastAnimation, 0);
        }
    }
    LoadClips(CastAnimations, LoadedCastAnimations);
    LoadClips(MarchAnimations, LoadedMarchAnimations);
    LoadClips(ChannelAnimations, LoadedChannelAnimations);
    LoadClips(ReleaseAnimations, LoadedReleaseAnimations);
    LoadedWalkerChannel = WalkerChannelAnimation.IsNull() ? nullptr : WalkerChannelAnimation.LoadSynchronous();
    LoadedWalkerRelease = WalkerReleaseAnimation.IsNull() ? nullptr : WalkerReleaseAnimation.LoadSynchronous();
    ChannelEnds.Reset();
    for (const UAnimSequence* Channel : LoadedChannelAnimations)
    {
        for (const UAnimSequence* Release : LoadedReleaseAnimations)
        {
            if (Channel && Release && Channel->GetSkeleton() == Release->GetSkeleton())
            {
                ChannelEnds.Add(Channel, MatchChannelEnd(Channel, Release));
                break;
            }
        }
    }
    if (Waypoints.Num() == 0)
    {
        CacheRoute();
    }
    AnchorLocation = Waypoints[0];
    WaypointIndex = Waypoints.Num() > 1 ? 1 : 0;
    WaypointStep = 1;
    const FVector FirstHeading = Waypoints.Num() > 1 ? Flat(Waypoints[1] - Waypoints[0]) : GetActorForwardVector();
    AnchorYaw = FirstHeading.IsNearlyZero() ? GetActorRotation().Yaw : FirstHeading.Rotation().Yaw;
    SeedTrail(AnchorLocation, AnchorYaw);
    BuildLeg(AnchorLocation);
    Pace = 1.0f;

    const int32 Count = FMath::Clamp(SquadSize, 1, 8);
    if (Formation != EReflectionsSquadFormation::Line && Waypoints.Num() > 1)
    {
        // Walk the anchor up the route by the column's depth first, so the rear ranks start on the route
        // rather than behind its first point (which may be off the walkable ground).
        const float Depth = (Count - 1) * RankSpacing;
        constexpr float Step = 0.05f;
        for (float Moved = 0.0f; Moved < Depth; Moved += FMath::Max(MarchSpeed, 50.0f) * Step)
        {
            AdvanceAnchor(Step, 1.0f);
        }
        AnchorVelocity = FVector::ZeroVector;
        HaltRemaining = 0.0f;
    }
    const int32 Casters = FMath::Clamp(CasterCount, 0, FMath::Max(0, Count - 1));
    int32 MeleeSpawned = 0;
    int32 CastersSpawned = 0;
    // Looks: the NPC system's soldier archetypes first (the crowd looks owner keeps them filled), else this spawner's
    // lists. Each list is used in turn from a per-squad starting point: no face repeats inside a squad while the list
    // is long enough, and squads side by side start on different faces. A look that fails to load is skipped.
    // User rule: the red people stay in the red world and the rag-clad in the white; never mix them. A squad on a
    // side only wears that side's looks; a Giltside squad with no Gilt soldier look yet wears Gilt guards.
    const FString Side = GetSide();
    const bool bAllied = Faction == EReflectionsSquadFaction::Gilt;
    TArray<TSoftClassPtr<AActor>> ArchetypeMelee;
    TArray<TSoftClassPtr<AActor>> ArchetypeCasters;
    if (bUseArchetypeLooks)
    {
        // A squad off the side levels (the sample map) dresses as its faction: Frost in rags, Gilt in red.
        const FString LookSide = !Side.IsEmpty() ? Side : bAllied ? FString(TEXT("Giltside")) : FString(TEXT("Frostside"));
        ReflectionsSquadNpc::GetSideLooks(this, bAllied ? FName(TEXT("AlliedSoldier")) : FName(TEXT("Soldier")), AnchorLocation, LookSide, ArchetypeMelee);
        ReflectionsSquadNpc::GetSideLooks(this, bAllied ? FName(TEXT("AlliedSoldierCaster")) : FName(TEXT("SoldierCaster")), AnchorLocation, LookSide, ArchetypeCasters);
    }
    TArray<TSoftClassPtr<AActor>> GiltGuards;
    if (Side == TEXT("Giltside") || bAllied)
    {
        GiltGuards.Add(TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/Lanthorne/Looks/BP_Look_GiltBridgeGuard.BP_Look_GiltBridgeGuard_C"))));
        GiltGuards.Add(TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/Lanthorne/Looks/BP_Look_GiltRowena.BP_Look_GiltRowena_C"))));
    }
    const TArray<TSoftClassPtr<AActor>>& MeleeList = ArchetypeMelee.Num() > 0 ? ArchetypeMelee : GiltGuards.Num() > 0 ? GiltGuards : MeleeLooks;
    const TArray<TSoftClassPtr<AActor>>& CasterList = ArchetypeCasters.Num() > 0 ? ArchetypeCasters : GiltGuards.Num() > 0 ? GiltGuards : CasterLooks;
    int32 MeleeCursor = SquadSeed;
    int32 CasterCursor = SquadSeed;
    for (int32 Slot = 0; Slot < Count; ++Slot)
    {
        // Leader and melee soldiers in front, casters march at the rear.
        const bool bCaster = Slot >= Count - Casters;
        const bool bCasterList = bCaster && CasterList.Num() > 0;
        const TArray<TSoftClassPtr<AActor>>& Looks = bCasterList ? CasterList : MeleeList;
        if (Looks.Num() == 0)
        {
            UE_LOG(LogTemp, Warning, TEXT("Squad %s has no soldier looks set"), *GetName());
            break;
        }
        int32& Cursor = bCasterList ? CasterCursor : MeleeCursor;
        UClass* LookClass = nullptr;
        for (int32 Try = 0; Try < Looks.Num() && !LookClass; ++Try)
        {
            const TSoftClassPtr<AActor>& Look = Looks[(Cursor++ & 0x7fffffff) % Looks.Num()];
            LookClass = Look.LoadSynchronous();
            if (!LookClass)
            {
                UE_LOG(LogTemp, Warning, TEXT("Squad %s: soldier look %s failed to load"), *GetName(), *Look.ToString());
            }
        }
        if (!LookClass)
        {
            continue;
        }
        const FVector Ground = GroundAt(ComputeSlot(Slot, Count));
        // MetaHuman assemblies face +Y; the NPC system's driver faces actor yaw + 90.
        const FRotator Facing(0.0, AnchorYaw - 90.0, 0.0);
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        Params.Owner = this;
        AActor* Soldier = World->SpawnActor<AActor>(LookClass, Ground, Facing, Params);
        if (!Soldier)
        {
            continue;
        }
        if (bStripFineGrooms)
        {
            TInlineComponentArray<UPrimitiveComponent*> Primitives(Soldier);
            for (UPrimitiveComponent* Primitive : Primitives)
            {
                const FString Name = Primitive ? Primitive->GetName() : FString();
                if (Name.StartsWith(TEXT("Fuzz")) || Name.StartsWith(TEXT("Eyelashes")))
                {
                    Primitive->SetVisibility(false);
                    Primitive->SetComponentTickEnabled(false);
                }
            }
        }
        ReflectionsSquadNpc::FSoldierSpec Spec;
        Spec.Role = bCaster ? EReflectionsSquadRole::Caster : EReflectionsSquadRole::Melee;
        Spec.bAllied = bAllied;
        Spec.MaxHealth = SoldierHealth;
        Spec.MeleeDamage = MeleeDamage;
        ReflectionsSquadNpc::Enrol(Soldier, Spec);
        AttachWeapon(Soldier, bCaster);
        AttachShield(Soldier);

        FReflectionsSquadMember& Member = Members.AddDefaulted_GetRef();
        Member.Actor = Soldier;
        Member.Role = Spec.Role;
        Member.State = EReflectionsSquadMemberState::Pending;
        Member.LastHealth = ReflectionsSquadNpc::GetHealth(Soldier);
        Member.StrafeSign = (Slot % 2 == 0) ? 1.0f : -1.0f;
        if (bCaster)
        {
            Member.Spell = CasterSpells.Num() > 0 ? CasterSpells[CastersSpawned % CasterSpells.Num()] : EHeroSpell::Fire;
            Member.CastCooldown = 0.8f + CastersSpawned * 0.9f;
            if (!Soldier->FindComponentByClass<UReflectionsSpellCombatComponent>())
            {
                // Gives impacts the usual NPC-reaction broadcast and supplies the fallback projectile meshes.
                UReflectionsSpellCombatComponent* Spells = NewObject<UReflectionsSpellCombatComponent>(Soldier, TEXT("SoldierSpells"));
                Spells->RegisterComponent();
            }
            ++CastersSpawned;
        }
        else
        {
            ++MeleeSpawned;
        }
    }
    LastSquadCast = -100.0f;
    SetState(Members.Num() > 0 ? EReflectionsSquadState::Marching : EReflectionsSquadState::Inactive, nullptr);
}

void AReflectionsSquad::DespawnSquad()
{
    for (FReflectionsSquadMember& Member : Members)
    {
        EndCast(Member, false);
        if (IsValid(Member.Actor))
        {
            Member.Actor->Destroy();
        }
    }
    Members.Reset();
    Foe.Reset();
    if (State != EReflectionsSquadState::Inactive)
    {
        SetState(EReflectionsSquadState::Inactive, nullptr);
    }
}

void AReflectionsSquad::SetState(EReflectionsSquadState Next, AActor* Cause)
{
    if (State == Next)
    {
        return;
    }
    UE_LOG(LogTemp, Log, TEXT("Squad %s: %s -> %s"), *GetName(), *UEnum::GetValueAsString(State), *UEnum::GetValueAsString(Next));
    State = Next;
    OnSquadStateChanged.Broadcast(State, Cause);
}

int32 AReflectionsSquad::GetAliveCount() const
{
    int32 Count = 0;
    for (const FReflectionsSquadMember& Member : Members)
    {
        Count += Member.State != EReflectionsSquadMemberState::Dead && IsValid(Member.Actor) ? 1 : 0;
    }
    return Count;
}

// ---- Tick ---------------------------------------------------------------------------------------------------------

void AReflectionsSquad::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (State == EReflectionsSquadState::Inactive)
    {
        return;
    }
    if (State == EReflectionsSquadState::Destroyed)
    {
        if (RespawnDelay > 0.0f)
        {
            RespawnTimer -= DeltaSeconds;
            if (RespawnTimer <= 0.0f)
            {
                SpawnSquad();
            }
        }
        return;
    }
    AggravationGrace = FMath::Max(0.0f, AggravationGrace - DeltaSeconds);
    RefreshMembers();
    UpdateMarchSound();
    if (GetAliveCount() == 0)
    {
        RespawnTimer = RespawnDelay;
        SetState(EReflectionsSquadState::Destroyed, nullptr);
        return;
    }
    switch (State)
    {
    case EReflectionsSquadState::Marching:
    case EReflectionsSquadState::Halted:
        TickAwareness(DeltaSeconds);
        if (State != EReflectionsSquadState::Engaged)
        {
            TickFormation(DeltaSeconds, false);
        }
        break;
    case EReflectionsSquadState::Reforming:
        TickAwareness(DeltaSeconds);
        if (State != EReflectionsSquadState::Engaged)
        {
            TickFormation(DeltaSeconds, true);
        }
        break;
    case EReflectionsSquadState::Engaged:
        TickCombat(DeltaSeconds);
        break;
    default:
        break;
    }
    if (CVarSquadDebug.GetValueOnGameThread() > 0)
    {
        DrawDebug();
    }
}

void AReflectionsSquad::RefreshMembers()
{
    bool bHit = false;
    bool bAllyDown = false;
    for (FReflectionsSquadMember& Member : Members)
    {
        if (Member.State == EReflectionsSquadMemberState::Dead)
        {
            continue;
        }
        if (Member.State == EReflectionsSquadMemberState::Released)
        {
            // A soldier that ran is the NPC system's until it calms down; then it falls back in.
            if (!ReflectionsSquadNpc::IsAlive(Member.Actor))
            {
                Member.State = EReflectionsSquadMemberState::Dead;
            }
            else if (!ReflectionsSquadNpc::WantsToFlee(Member.Actor))
            {
                const bool bFighting = State == EReflectionsSquadState::Engaged;
                Member.State = bFighting ? EReflectionsSquadMemberState::Fighting : EReflectionsSquadMemberState::InFormation;
                Member.LastHealth = ReflectionsSquadNpc::GetHealth(Member.Actor);
                if (bFighting && Member.Role == EReflectionsSquadRole::Melee)
                {
                    ReflectionsSquadNpc::SetMeleeTarget(Member.Actor, Foe.Get());
                }
                else
                {
                    ReflectionsSquadNpc::SetSteered(Member.Actor, true);
                }
            }
            continue;
        }
        if (!ReflectionsSquadNpc::IsAlive(Member.Actor))
        {
            // The NPC system ragdolls the body; just let go of it. A comrade killed (even in one blow) is an attack.
            bHit = true;
            bAllyDown = true;
            EndCast(Member, false);
            Member.bMarchClipActive = false;
            Member.SavedAnimClass = nullptr;
            Member.State = EReflectionsSquadMemberState::Dead;
            continue;
        }
        const float Health = ReflectionsSquadNpc::GetHealth(Member.Actor);
        if (!Member.bShieldPlaced && Member.State != EReflectionsSquadMemberState::Pending)
        {
            // Fit only once the body animates (hands below the chest): a grip fitted to a T-posed arm would be wrong
            // for every real pose. Give up after ~10 s and leave the shield hidden.
            Member.bShieldPlaced = PlaceShield(Member) || ++Member.ShieldTries > 600;
        }
        if (Member.LastHealth >= 0.0f && Health < Member.LastHealth - 0.01f)
        {
            bHit = true;
            if (ShieldHitSounds.Num() > 0 && HasShield(Member.Actor))
            {
                if (USoundBase* Sound = ShieldHitSounds[FMath::RandHelper(ShieldHitSounds.Num())].LoadSynchronous())
                {
                    UGameplayStatics::PlaySoundAtLocation(this, Sound, Member.Actor->GetActorLocation() + FVector(0.0, 0.0, 110.0));
                }
            }
        }
        Member.LastHealth = Health;
        // The NPC system heard magic or got hit and wants to fight: the whole squad breaks formation.
        bHit |= Faction != EReflectionsSquadFaction::Gilt && State != EReflectionsSquadState::Engaged && AggravationGrace <= 0.0f &&
            ReflectionsSquadNpc::IsAggravated(Member.Actor);
        if (ReflectionsSquadNpc::WantsToFlee(Member.Actor))
        {
            EndCast(Member, true);
            UpdateMarchAnimation(Member, false);
            ReflectionsSquadNpc::Release(Member.Actor);
            Member.State = EReflectionsSquadMemberState::Released;
            continue;
        }
        if (Member.State == EReflectionsSquadMemberState::Pending && ReflectionsSquadNpc::GetDriver(Member.Actor))
        {
            const bool bFighting = State == EReflectionsSquadState::Engaged;
            Member.State = bFighting ? EReflectionsSquadMemberState::Fighting : EReflectionsSquadMemberState::InFormation;
            if (bFighting && Member.Role == EReflectionsSquadRole::Melee)
            {
                ReflectionsSquadNpc::SetMeleeTarget(Member.Actor, Foe.Get());
            }
        }
    }
    if (bAllyDown)
    {
        BarkEvent(FirstActiveSoldier(), TEXT("Soldier_AllyDown"));
    }
    if (bHit && State != EReflectionsSquadState::Engaged && CVarSquadPassive.GetValueOnGameThread() == 0)
    {
        // Frost: any hit means the player. Gilt: the NPC events say who it was (OnMemberAttacked); a hit from nobody
        // known turns the squad on whatever enemy it can see.
        if (Faction == EReflectionsSquadFaction::Gilt)
        {
            if (AActor* Hostile = FindHostileInSight())
            {
                Engage(Hostile);
            }
        }
        else
        {
            Engage(GetPlayer());
        }
    }
}

void AReflectionsSquad::TickFormation(float DeltaSeconds, bool bReforming)
{
    TArray<int32, TInlineAllocator<8>> Active;
    for (int32 Index = 0; Index < Members.Num(); ++Index)
    {
        if (IsActive(Members[Index]))
        {
            Active.Add(Index);
        }
    }
    const int32 SlotCount = Active.Num();
    float Worst = 0.0f;
    for (int32 Slot = 0; Slot < SlotCount; ++Slot)
    {
        FReflectionsSquadMember& Member = Members[Active[Slot]];
        if (ACharacter* Driver = ReflectionsSquadNpc::GetDriver(Member.Actor))
        {
            Member.SlotError = FVector::Dist2D(Driver->GetActorLocation(), ComputeSlot(Slot, SlotCount));
            Worst = FMath::Max(Worst, Member.SlotError);
        }
    }

    if (bReforming)
    {
        ReformTimer += DeltaSeconds;
        AnchorVelocity = FVector::ZeroVector;
        if (Worst < 90.0f || ReformTimer > 9.0f)
        {
            Pace = 0.0f;
            SetState(EReflectionsSquadState::Marching, nullptr);
        }
    }
    else if (State == EReflectionsSquadState::Halted)
    {
        AnchorVelocity = FVector::ZeroVector;
        HaltRemaining -= DeltaSeconds;
        if (HaltRemaining <= 0.0f)
        {
            SetState(EReflectionsSquadState::Marching, nullptr);
        }
    }
    else
    {
        // Wait for stragglers instead of stretching the formation.
        float Target = FMath::Clamp(1.0f - (Worst - 160.0f) / 300.0f, 0.0f, 1.0f);
        if (Formation == EReflectionsSquadFormation::Line && LegPoints.IsValidIndex(LegIndex))
        {
            // A line slows down while it wheels so the outer files keep up.
            const FVector Heading = Flat(LegPoints[LegIndex] - AnchorLocation);
            if (!Heading.IsNearlyZero())
            {
                const float Error = FMath::Abs(FMath::FindDeltaAngleDegrees(AnchorYaw, Heading.Rotation().Yaw));
                Target *= FMath::Clamp(1.0f - Error / 110.0f, 0.2f, 1.0f);
            }
        }
        Pace = FMath::FInterpTo(Pace, Target, DeltaSeconds, 2.5f);
        AdvanceAnchor(DeltaSeconds, Pace);
    }

    const float AnchorSpeed = AnchorVelocity.Size();
    const float MaxSpeed = MarchSpeed * (bReforming ? 2.2f : CatchUpFactor);
    for (int32 Slot = 0; Slot < SlotCount; ++Slot)
    {
        FReflectionsSquadMember& Member = Members[Active[Slot]];
        ACharacter* Driver = ReflectionsSquadNpc::GetDriver(Member.Actor);
        if (!Driver)
        {
            continue;
        }
        FVector SlotDirection = FRotator(0.0, AnchorYaw, 0.0).Vector();
        FVector Goal;
        if (Formation == EReflectionsSquadFormation::Line)
        {
            Goal = ComputeSlot(Slot, SlotCount);
        }
        else
        {
            FVector Unused;
            Goal = ComputeSlot(Slot, SlotCount);
            const int32 Rank = Formation == EReflectionsSquadFormation::Column ? Slot : (Slot == 0 ? 0 : 1 + (Slot - 1) / 2);
            SampleTrail(Rank * RankSpacing, Unused, SlotDirection);
        }
        SteerTo(Member, Goal, SlotDirection * AnchorSpeed, MaxSpeed, DeltaSeconds);
        if (AnchorSpeed < 5.0f && Member.SlotError < 40.0f)
        {
            FaceYaw(Driver, SlotDirection.Rotation().Yaw, DeltaSeconds);
        }
        UpdateMarchAnimation(Member, true);
    }
}

void AReflectionsSquad::SteerTo(FReflectionsSquadMember& Member, const FVector& Goal, const FVector& FlowVelocity, float MaxSpeed, float DeltaSeconds)
{
    ACharacter* Driver = ReflectionsSquadNpc::GetDriver(Member.Actor);
    if (!Driver)
    {
        return;
    }
    const FVector To = Flat(Goal - Driver->GetActorLocation());
    const float Distance = To.Size();
    FVector Desired = FlowVelocity + To * 1.6f;
    if (Distance > 400.0f)
    {
        Desired = To.GetSafeNormal() * MaxSpeed;
    }
    float Speed = Desired.Size();
    if (Speed < 20.0f && Distance < 35.0f)
    {
        return;
    }
    Speed = FMath::Min(Speed, MaxSpeed);
    UCharacterMovementComponent* Movement = Driver->GetCharacterMovement();
    const float Scale = FMath::Clamp(Speed / FMath::Max(1.0f, Movement->GetMaxSpeed()), 0.05f, 1.0f);
    Driver->AddMovementInput(Desired.GetSafeNormal(), Scale, true);
}

void AReflectionsSquad::FaceYaw(ACharacter* Driver, float Yaw, float DeltaSeconds)
{
    if (!Driver)
    {
        return;
    }
    const float Current = Driver->GetActorRotation().Yaw;
    if (FMath::Abs(FMath::FindDeltaAngleDegrees(Current, Yaw)) < 2.0f)
    {
        return;
    }
    Driver->SetActorRotation(FRotator(0.0, FMath::FixedTurn(Current, Yaw, 240.0f * DeltaSeconds), 0.0));
}

UAnimSequence* AReflectionsSquad::ClipFor(const TArray<TObjectPtr<UAnimSequence>>& Clips, const USkeletalMeshComponent* Body)
{
    const USkeleton* Skeleton = Body && Body->GetSkeletalMeshAsset() ? Body->GetSkeletalMeshAsset()->GetSkeleton() : nullptr;
    for (UAnimSequence* Clip : Clips)
    {
        if (Clip && Skeleton && Clip->GetSkeleton() == Skeleton)
        {
            return Clip;
        }
    }
    return nullptr;
}

void AReflectionsSquad::AttachWeapon(AActor* Soldier, bool bCaster)
{
    // One owner per hand: when the NPC system's archetype already gives this soldier a weapon, it attaches (and
    // swaps) it itself; the squad's props are the fallback for archetypes without one.
    if (ReflectionsSquadNpc::NpcCarriesWeapon(Soldier))
    {
        return;
    }
    const TSoftObjectPtr<UStaticMesh>& Soft = bCaster ? CasterWeapon : MeleeWeapon;
    USkeletalMeshComponent* Body = ReflectionsSquadNpc::GetBody(Soldier);
    UStaticMesh* Mesh = Soft.IsNull() ? nullptr : Soft.LoadSynchronous();
    if (!Mesh || !Body)
    {
        if (!Soft.IsNull() && !Mesh)
        {
            UE_LOG(LogTemp, Warning, TEXT("Squad %s: weapon %s failed to load"), *GetName(), *Soft.ToString());
        }
        return;
    }
    // Spell crafting's weapon_r socket when the body has it; otherwise the same grip on the hand bone.
    const bool bSocket = !WeaponSocket.IsNone() && Body->DoesSocketExist(WeaponSocket);
    const FName Parent = bSocket ? WeaponSocket : FName(TEXT("hand_r"));
    if (!Body->DoesSocketExist(Parent))
    {
        return;
    }
    AttachProp(Soldier, Mesh, Parent, bSocket ? FTransform::Identity : WeaponGrip, TEXT("SquadWeapon"));
}

void AReflectionsSquad::AttachShield(AActor* Soldier)
{
    // One owner per hand: the NPC system's own shield (Combat.ShieldProp) wins when the archetype has one.
    if (ReflectionsSquadNpc::NpcCarriesShield(Soldier))
    {
        return;
    }
    // Exactly one shield per soldier: the look's own (the Gilt guards' skinned round shield) or the NPC system's
    // (npc-unify owns the hands from train #14) always wins over the squad's.
    if (HasOtherShield(Soldier))
    {
        return;
    }
    USkeletalMeshComponent* Body = ReflectionsSquadNpc::GetBody(Soldier);
    UStaticMesh* Mesh = ShieldMesh.IsNull() ? nullptr : ShieldMesh.LoadSynchronous();
    if (Mesh && Body && Body->DoesSocketExist(ShieldBone))
    {
        if (UStaticMeshComponent* Shield = AttachProp(Soldier, Mesh, ShieldBone, ShieldGrip, TEXT("SquadShield")))
        {
            // Shown once PlaceShield has fitted it to the animating hand.
            Shield->SetVisibility(false);
        }
    }
}

bool AReflectionsSquad::PlaceShield(FReflectionsSquadMember& Member)
{
    UStaticMeshComponent* Shield = Member.Actor ? Member.Actor->FindComponentByTag<UStaticMeshComponent>(TEXT("SquadShield")) : nullptr;
    USkeletalMeshComponent* Body = ReflectionsSquadNpc::GetBody(Member.Actor);
    ACharacter* Driver = ReflectionsSquadNpc::GetDriver(Member.Actor);
    if (!Shield || !Body || !Driver)
    {
        return true;
    }
    if (HasOtherShield(Member.Actor) || ReflectionsSquadNpc::NpcCarriesShield(Member.Actor))
    {
        // The NPC system (or the look) brought its own after the squad attached one: step aside.
        Shield->DestroyComponent();
        return true;
    }
    const FName Chest = Body->DoesSocketExist(TEXT("clavicle_l")) ? FName(TEXT("clavicle_l")) : FName(TEXT("spine_04"));
    if (ShieldGrip.Equals(FTransform::Identity) && Body->DoesSocketExist(Chest) &&
        Body->GetSocketLocation(ShieldBone).Z > Body->GetSocketLocation(Chest).Z - 25.0f)
    {
        return false;
    }
    if (!ShieldGrip.Equals(FTransform::Identity))
    {
        Shield->SetRelativeTransform(ShieldGrip);
    }
    else
    {
        // Fit it on the live hand: the face (the side of the pivot most of the mesh lies on) out to the soldier's
        // left, upright, the grip at the pivot. It then rides on the hand through the march and the fight.
        const FTransform Hand = Body->GetSocketTransform(ShieldBone, RTS_World);
        const FVector Out = -Flat(Driver->GetActorRightVector()).GetSafeNormal();
        const UStaticMesh* Mesh = Shield->GetStaticMesh();
        const double Front = Mesh && Mesh->GetBounds().Origin.X < -0.5 ? -1.0 : 1.0;
        const FRotator Facing = FRotationMatrix::MakeFromXZ(Out * Front, FVector::UpVector).Rotator();
        const FTransform World(Facing, Hand.GetLocation() + Out * 3.0);
        Shield->SetRelativeTransform(World.GetRelativeTransform(Hand));
    }
    Shield->SetVisibility(true);
    return true;
}

UStaticMeshComponent* AReflectionsSquad::AttachProp(AActor* Soldier, UStaticMesh* Mesh, FName Parent, const FTransform& Relative, FName Tag)
{
    USkeletalMeshComponent* Body = ReflectionsSquadNpc::GetBody(Soldier);
    if (!Soldier || !Mesh || !Body)
    {
        return nullptr;
    }
    UStaticMeshComponent* Prop = NewObject<UStaticMeshComponent>(Soldier, NAME_None, RF_Transient);
    Prop->SetMobility(EComponentMobility::Movable);
    Prop->SetStaticMesh(Mesh);
    Prop->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Prop->SetGenerateOverlapEvents(false);
    Prop->SetCanEverAffectNavigation(false);
    Prop->ComponentTags.Add(Tag);
    Soldier->AddInstanceComponent(Prop);
    Prop->RegisterComponent();
    Prop->AttachToComponent(Body, FAttachmentTransformRules::SnapToTargetNotIncludingScale, Parent);
    Prop->SetRelativeTransform(Relative);
    return Prop;
}

float AReflectionsSquad::MatchChannelEnd(const UAnimSequence* Channel, const UAnimSequence* Release)
{
    const USkeleton* Skeleton = Channel ? Channel->GetSkeleton() : nullptr;
    if (!Skeleton || !Release || Channel->GetPlayLength() <= 0.0f)
    {
        return 0.0f;
    }
    // Local rotations of the bones that read in a cast. Both clips share the skeleton, so local poses compare directly.
    static const FName Bones[] = { TEXT("spine_04"), TEXT("spine_05"), TEXT("clavicle_r"), TEXT("upperarm_r"),
        TEXT("lowerarm_r"), TEXT("hand_r"), TEXT("clavicle_l"), TEXT("upperarm_l"), TEXT("lowerarm_l"), TEXT("hand_l") };
    const FReferenceSkeleton& Ref = Skeleton->GetReferenceSkeleton();
    TArray<int32, TInlineAllocator<10>> Indices;
    TArray<FQuat, TInlineAllocator<10>> Target;
    for (const FName Bone : Bones)
    {
        const int32 Index = Ref.FindBoneIndex(Bone);
        if (Index != INDEX_NONE)
        {
            FTransform Pose;
            Release->GetBoneTransform(Pose, FSkeletonPoseBoneIndex(Index), FAnimExtractContext(0.0), false);
            Indices.Add(Index);
            Target.Add(Pose.GetRotation());
        }
    }
    if (Indices.Num() == 0)
    {
        return 0.0f;
    }
    float BestTime = 0.0f;
    double BestScore = TNumericLimits<double>::Max();
    const float Length = Channel->GetPlayLength();
    for (float Time = 0.0f; Time < Length; Time += 1.0f / 30.0f)
    {
        double Score = 0.0;
        for (int32 i = 0; i < Indices.Num(); ++i)
        {
            FTransform Pose;
            Channel->GetBoneTransform(Pose, FSkeletonPoseBoneIndex(Indices[i]), FAnimExtractContext(static_cast<double>(Time)), false);
            Score += Pose.GetRotation().AngularDistance(Target[i]);
        }
        if (Score < BestScore)
        {
            BestScore = Score;
            BestTime = Time;
        }
    }
    return BestTime;
}

void AReflectionsSquad::UpdateMarchAnimation(FReflectionsSquadMember& Member, bool bMarching)
{
    if (!ReflectionsSquadNpc::IsAlive(Member.Actor))
    {
        // Never touch a dead (ragdolling) body's animation.
        Member.bMarchClipActive = false;
        Member.SavedAnimClass = nullptr;
        return;
    }
    if (LoadedMarchAnimations.Num() == 0 || (CVarSquadMarchClip.GetValueOnGameThread() == 0 && !Member.bMarchClipActive))
    {
        return;
    }
    USkeletalMeshComponent* Body = ReflectionsSquadNpc::GetBody(Member.Actor);
    ACharacter* Driver = ReflectionsSquadNpc::GetDriver(Member.Actor);
    UAnimSequence* March = ClipFor(LoadedMarchAnimations, Body);
    if (!Body || !Driver || (!March && !Member.bMarchClipActive))
    {
        return;
    }
    const float Speed = Flat(Driver->GetVelocity()).Size();
    const bool bWant = bMarching && CVarSquadMarchClip.GetValueOnGameThread() != 0 && (Member.bMarchClipActive ? Speed > 25.0f : Speed > 60.0f);
    if (bWant && !Member.bMarchClipActive && Member.CastPhase == EReflectionsSquadCastPhase::Ready)
    {
        if (!Member.SavedAnimClass)
        {
            Member.SavedAnimClass = Body->GetAnimClass();
        }
        Body->PlayAnimation(March, true);
        Member.bMarchClipActive = true;
        if (CVarSquadPauseDriverAnim.GetValueOnGameThread() > 0 && Driver->GetMesh())
        {
            // Saves the motion-matching evaluation of every marching soldier; movement itself is CharacterMovement.
            Driver->GetMesh()->SetComponentTickEnabled(false);
        }
    }
    else if (!bWant && Member.bMarchClipActive)
    {
        Member.bMarchClipActive = false;
        if (Driver->GetMesh())
        {
            Driver->GetMesh()->SetComponentTickEnabled(true);
        }
        if (Member.SavedAnimClass)
        {
            Body->SetAnimInstanceClass(Member.SavedAnimClass);
            Member.SavedAnimClass = nullptr;
        }
    }
    if (Member.bMarchClipActive)
    {
        Body->SetPlayRate(FMath::Clamp(Speed / FMath::Max(1.0f, MarchAnimationSpeed), 0.3f, 2.0f));
    }
}

// ---- Awareness and combat ------------------------------------------------------------------------------------------

AActor* AReflectionsSquad::GetPlayer() const
{
    return UGameplayStatics::GetPlayerPawn(this, 0);
}

bool AReflectionsSquad::HasLineOfSight(AActor* From, AActor* To) const
{
    ACharacter* Driver = ReflectionsSquadNpc::GetDriver(From);
    if (!From || !To || !Driver || !GetWorld())
    {
        return false;
    }
    FCollisionQueryParams Params(SCENE_QUERY_STAT(SquadSight), false, this);
    for (const FReflectionsSquadMember& Member : Members)
    {
        if (IsValid(Member.Actor))
        {
            Params.AddIgnoredActor(Member.Actor);
            if (ACharacter* MemberDriver = ReflectionsSquadNpc::GetDriver(Member.Actor))
            {
                Params.AddIgnoredActor(MemberDriver);
            }
        }
    }
    const FVector Start = Driver->GetActorLocation() + FVector(0.0, 0.0, 60.0);
    const FVector End = To->GetActorLocation() + FVector(0.0, 0.0, 30.0);
    FHitResult Hit;
    if (!GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params))
    {
        return true;
    }
    AActor* HitActor = Hit.GetActor();
    // An NPC target's visible body rides on its hidden walker: a hit on either counts as seeing it.
    return HitActor == To || (HitActor && (HitActor->IsAttachedTo(To) || To->IsAttachedTo(HitActor)));
}

void AReflectionsSquad::TickAwareness(float DeltaSeconds)
{
    AwarenessTimer -= DeltaSeconds;
    if (AwarenessTimer > 0.0f)
    {
        return;
    }
    AwarenessTimer = 0.25f;
    if (CVarSquadPassive.GetValueOnGameThread() > 0)
    {
        return;
    }
    if (Faction == EReflectionsSquadFaction::Gilt)
    {
        // Allied: the tarnished and Frost soldiers on sight; the player only once provoked (FindHostileInSight).
        if (AActor* Hostile = FindHostileInSight())
        {
            Engage(Hostile);
        }
        return;
    }
    AActor* Player = GetPlayer();
    if (IsPlayerDown(Player))
    {
        if (AActor* Hostile = FindHostileInSight())
        {
            Engage(Hostile);
        }
        return;
    }
    const float CosHalfAngle = FMath::Cos(FMath::DegreesToRadians(SightHalfAngle));
    for (const FReflectionsSquadMember& Member : Members)
    {
        ACharacter* Driver = IsActive(Member) ? ReflectionsSquadNpc::GetDriver(Member.Actor) : nullptr;
        if (!Driver)
        {
            continue;
        }
        const FVector To = Flat(Player->GetActorLocation() - Driver->GetActorLocation());
        const float Distance = To.Size();
        if (Distance > SightRadius)
        {
            continue;
        }
        const bool bInView = Distance < AlertRadius ||
            FVector::DotProduct(To / FMath::Max(Distance, 1.0f), Flat(Driver->GetActorForwardVector()).GetSafeNormal()) >= CosHalfAngle;
        if (bInView && HasLineOfSight(Member.Actor, Player))
        {
            Engage(Player);
            return;
        }
    }
    // Frost raiders also go for Gilt guards they see.
    if (AActor* Hostile = FindHostileInSight())
    {
        Engage(Hostile);
    }
}

AActor* AReflectionsSquad::FindHostileInSight()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return nullptr;
    }
    TArray<AActor*, TInlineAllocator<32>> Candidates;
    for (TActorIterator<AReflectionsSquad> It(World); It; ++It)
    {
        if (*It != this && It->Faction != Faction)
        {
            for (const FReflectionsSquadMember& Member : It->Members)
            {
                if (IsActive(Member))
                {
                    Candidates.Add(Member.Actor);
                }
            }
        }
    }
    if (Faction == EReflectionsSquadFaction::Gilt)
    {
        for (AActor* Npc : ReflectionsSquadNpc::GetNpcActors(this))
        {
            if (IsValid(Npc) && !IsMember(Npc) && ReflectionsSquadNpc::IsTarnished(Npc) && ReflectionsSquadNpc::IsAlive(Npc))
            {
                Candidates.Add(Npc);
            }
        }
        AActor* Player = GetPlayer();
        if (bProvokedByPlayer && !IsPlayerDown(Player))
        {
            Candidates.Add(Player);
        }
    }
    if (Candidates.Num() == 0)
    {
        return nullptr;
    }
    const float CosHalfAngle = FMath::Cos(FMath::DegreesToRadians(SightHalfAngle));
    AActor* Best = nullptr;
    float BestDistance = SightRadius;
    for (const FReflectionsSquadMember& Member : Members)
    {
        ACharacter* Driver = IsActive(Member) ? ReflectionsSquadNpc::GetDriver(Member.Actor) : nullptr;
        if (!Driver)
        {
            continue;
        }
        const FVector Forward = Flat(Driver->GetActorForwardVector()).GetSafeNormal();
        for (AActor* Candidate : Candidates)
        {
            const FVector To = Flat(Candidate->GetActorLocation() - Driver->GetActorLocation());
            const float Distance = To.Size();
            if (Distance >= BestDistance)
            {
                continue;
            }
            const bool bInView = Distance < AlertRadius || FVector::DotProduct(To / FMath::Max(Distance, 1.0f), Forward) >= CosHalfAngle;
            if (bInView && HasLineOfSight(Member.Actor, Candidate))
            {
                Best = Candidate;
                BestDistance = Distance;
            }
        }
    }
    return Best;
}

bool AReflectionsSquad::IsMember(const AActor* Actor) const
{
    if (!Actor)
    {
        return false;
    }
    for (const FReflectionsSquadMember& Member : Members)
    {
        if (Member.Actor == Actor)
        {
            return true;
        }
    }
    return false;
}

bool AReflectionsSquad::IsHostileTarget(const AActor* Actor) const
{
    if (!IsValid(Actor) || IsMember(Actor))
    {
        return false;
    }
    if (Actor == GetPlayer())
    {
        return Faction == EReflectionsSquadFaction::Frost || bProvokedByPlayer;
    }
    if (UWorld* World = GetWorld())
    {
        for (TActorIterator<AReflectionsSquad> It(World); It; ++It)
        {
            if (It->IsMember(Actor))
            {
                return It->Faction != Faction;
            }
        }
    }
    return Faction == EReflectionsSquadFaction::Gilt && ReflectionsSquadNpc::IsTarnished(Actor);
}

void AReflectionsSquad::OnMemberAttacked(AActor* Attacker)
{
    if (CVarSquadPassive.GetValueOnGameThread() > 0 || State == EReflectionsSquadState::Inactive || State == EReflectionsSquadState::Destroyed)
    {
        return;
    }
    AActor* Player = GetPlayer();
    AActor* Who = Attacker;
    if (Who && Player && (Who == Player || Who->GetInstigator() == Player || Who->GetOwner() == Player))
    {
        Who = Player;
    }
    if (Who && Who == Player)
    {
        // Anyone who attacks a soldier is the enemy, allies included: the whole squad turns on the player. Except
        // a stray spell while allies fight a common enemy (a tarnished, Frost soldiers): that is friendly fire.
        const AActor* Current = Foe.Get();
        const bool bFriendlyFire = Faction == EReflectionsSquadFaction::Gilt && State == EReflectionsSquadState::Engaged &&
            Current && Current != Player && !IsPlayerDown(const_cast<AActor*>(Current));
        if (!bFriendlyFire)
        {
            bProvokedByPlayer = true;
            Engage(Player);
        }
    }
    else if (Who && IsHostileTarget(Who) && State != EReflectionsSquadState::Engaged)
    {
        Engage(Who);
    }
}

void AReflectionsSquad::HandleNpcSpellHit(AActor* Npc, const FReflectionsSpellHitData& Hit)
{
    if (IsMember(Npc))
    {
        OnMemberAttacked(Hit.Caster);
    }
}

void AReflectionsSquad::HandleNpcDied(AActor* Npc, AActor* Killer)
{
    if (IsMember(Npc))
    {
        OnMemberAttacked(Killer);
    }
}

void AReflectionsSquad::HandlePlayerCrime(AActor* Victim, FName Crime, AActor* Witness, FVector Location, float Heat)
{
    if (CVarSquadPassive.GetValueOnGameThread() > 0 || State == EReflectionsSquadState::Inactive || State == EReflectionsSquadState::Destroyed)
    {
        return;
    }
    // Killing the squad's own enemies is no crime to it.
    if (Victim && !IsMember(Victim) && IsHostileTarget(Victim) && Victim != GetPlayer())
    {
        return;
    }
    if (IsMember(Witness) || IsMember(Victim) || HasMemberWithin(Location, CrimeAlarmRadius))
    {
        bProvokedByPlayer = true;
        Engage(GetPlayer());
    }
}

void AReflectionsSquad::RetargetMelee(AActor* Target)
{
    for (FReflectionsSquadMember& Member : Members)
    {
        if (IsActive(Member) && Member.Role == EReflectionsSquadRole::Melee && Member.State == EReflectionsSquadMemberState::Fighting &&
            !Member.bCharging)
        {
            ReflectionsSquadNpc::SetMeleeTarget(Member.Actor, Target);
        }
    }
}

void AReflectionsSquad::HandleSpellEvent(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity)
{
    if (Faction == EReflectionsSquadFaction::Gilt ||
        State == EReflectionsSquadState::Engaged || State == EReflectionsSquadState::Inactive ||
        State == EReflectionsSquadState::Destroyed || !IsValid(Caster) || Caster != GetPlayer() ||
        CVarSquadPassive.GetValueOnGameThread() > 0)
    {
        return;
    }
    for (const FReflectionsSquadMember& Member : Members)
    {
        if (IsActive(Member) && FVector::Dist(Member.Actor->GetActorLocation(), Location) < 1100.0f)
        {
            Engage(Caster);
            return;
        }
    }
}

void AReflectionsSquad::Engage(AActor* Target)
{
    EngageInternal(Target, true);
}

void AReflectionsSquad::EngageInternal(AActor* Target, bool bRaiseAlarm)
{
    if (!IsValid(Target) || State == EReflectionsSquadState::Destroyed || State == EReflectionsSquadState::Inactive)
    {
        return;
    }
    AActor* Previous = Foe.Get();
    Foe = Target;
    LostTimer = 0.0f;
    bFoeInSight = true;
    SightCheckTimer = 0.0f;
    if (State == EReflectionsSquadState::Engaged)
    {
        if (Previous != Target)
        {
            RetargetMelee(Target);
        }
        return;
    }
    int32 CasterIndex = 0;
    int32 MeleeCount = 0;
    for (const FReflectionsSquadMember& Member : Members)
    {
        MeleeCount += IsActive(Member) && Member.Role == EReflectionsSquadRole::Melee ? 1 : 0;
    }
    int32 MeleeIndex = 0;
    for (FReflectionsSquadMember& Member : Members)
    {
        if (!IsActive(Member) || !ReflectionsSquadNpc::IsAlive(Member.Actor))
        {
            continue;
        }
        UpdateMarchAnimation(Member, false);
        if (Member.State == EReflectionsSquadMemberState::InFormation)
        {
            Member.State = EReflectionsSquadMemberState::Fighting;
        }
        if (Member.Role == EReflectionsSquadRole::Melee)
        {
            // Break ranks and charge: each runs at its own side of the target (fanned out so the back rank is not
            // stuck behind the front), and the NPC system's melee motor takes over up close (TickCombat).
            Member.FlankAngle = (MeleeIndex - (MeleeCount - 1) * 0.5f) * 45.0f;
            Member.DeployTime = 0.0f;
            Member.bCharging = Member.State == EReflectionsSquadMemberState::Fighting;
            Member.RepathTimer = 0.0f;
            ++MeleeIndex;
        }
        else
        {
            Member.CastCooldown = FMath::Max(Member.CastCooldown, 0.5f + CasterIndex * 0.9f);
            ++CasterIndex;
        }
    }
    SetState(EReflectionsSquadState::Engaged, Target);
    // The alarm: the leader calls the charge (an allied squad turning on the player raises the heat alarm).
    BarkEvent(FirstActiveSoldier(), Target == GetPlayer() && Faction == EReflectionsSquadFaction::Gilt ? FName(TEXT("Heat_Alarm")) : FName(TEXT("Soldier_Charge")), true);
    BarkTimer = FMath::FRandRange(BarkInterval.X, FMath::Max(BarkInterval.X, BarkInterval.Y));
    if (bRaiseAlarm && GetWorld())
    {
        // The alarm: squads close by join in. They do not pass it on, so it cannot sweep the whole city.
        for (TActorIterator<AReflectionsSquad> It(GetWorld()); It; ++It)
        {
            AReflectionsSquad* Other = *It;
            if (Other == this || Other->Faction != Faction || Other->State == EReflectionsSquadState::Engaged ||
                Other->State == EReflectionsSquadState::Inactive ||
                Other->State == EReflectionsSquadState::Destroyed)
            {
                continue;
            }
            for (const FReflectionsSquadMember& Member : Members)
            {
                if (IsActive(Member) && Other->HasMemberWithin(Member.Actor->GetActorLocation(), AlarmRadius))
                {
                    Other->EngageInternal(Target, false);
                    break;
                }
            }
        }
    }
}

FString AReflectionsSquad::GetSide() const
{
    const auto SideOfLevel = [](const ULevel* Level) -> FString
    {
        const FString Name = Level && Level->GetOuter() ? Level->GetOuter()->GetName() : FString();
        for (const TCHAR* Side : { TEXT("Giltside"), TEXT("Frostside"), TEXT("Pewterside") })
        {
            if (Name.Contains(Side))
            {
                return Side;
            }
        }
        return FString();
    };
    FString Side = SideOfLevel(GetLevel());
    if (!Side.IsEmpty() || !GetWorld())
    {
        return Side;
    }
    // Spawned at runtime (the start patrol, tests): the side of the nearest placed squad within 600 m.
    double Best = FMath::Square(60000.0);
    for (TActorIterator<AReflectionsSquad> It(GetWorld()); It; ++It)
    {
        const FString Other = *It != this ? SideOfLevel(It->GetLevel()) : FString();
        const double Distance = FVector::DistSquared2D(It->GetActorLocation(), GetActorLocation());
        if (!Other.IsEmpty() && Distance < Best)
        {
            Best = Distance;
            Side = Other;
        }
    }
    return Side;
}

bool AReflectionsSquad::HasMemberWithin(const FVector& Location, float Radius) const
{
    for (const FReflectionsSquadMember& Member : Members)
    {
        if (IsActive(Member) && FVector::DistSquared2D(Member.Actor->GetActorLocation(), Location) < FMath::Square(Radius))
        {
            return true;
        }
    }
    return false;
}

void AReflectionsSquad::HandleCrime(AActor* Offender, const FVector& Location)
{
    if (!IsValid(Offender) || Offender != GetPlayer() || CVarSquadPassive.GetValueOnGameThread() > 0 ||
        State == EReflectionsSquadState::Engaged || State == EReflectionsSquadState::Inactive || State == EReflectionsSquadState::Destroyed)
    {
        return;
    }
    if (HasMemberWithin(Location, CrimeAlarmRadius))
    {
        Engage(Offender);
    }
}

FVector AReflectionsSquad::NextPathPoint(const FVector& From, const FVector& Goal) const
{
    if (bUseNavigation)
    {
        if (const UNavigationPath* Path = UNavigationSystemV1::FindPathToLocationSynchronously(GetWorld(), From, Goal))
        {
            for (const FVector& Point : Path->PathPoints)
            {
                if (FVector::DistSquared2D(Point, From) > FMath::Square(120.0f))
                {
                    return Point;
                }
            }
        }
    }
    return Goal;
}

void AReflectionsSquad::BarkEvent(AActor* Speaker, FName Group, bool bFallback)
{
    if (!bBarkOrders || !Speaker)
    {
        return;
    }
    if (!ReflectionsSquadNpc::PlayBark(Speaker, Group) && bFallback)
    {
        Bark(Speaker);
    }
}

bool AReflectionsSquad::HasOtherShield(const AActor* Soldier)
{
    if (!Soldier)
    {
        return false;
    }
    TInlineComponentArray<UPrimitiveComponent*> Parts(Soldier);
    for (const UPrimitiveComponent* Part : Parts)
    {
        if (!Part || Part->ComponentHasTag(TEXT("SquadShield")))
        {
            continue;
        }
        if (Part->GetName().Contains(TEXT("Shield")))
        {
            return true;
        }
        for (const FName& Tag : Part->ComponentTags)
        {
            if (Tag.ToString().Contains(TEXT("Shield")))
            {
                return true;
            }
        }
    }
    return false;
}

bool AReflectionsSquad::HasShield(const AActor* Soldier)
{
    if (!Soldier)
    {
        return false;
    }
    TInlineComponentArray<UPrimitiveComponent*> Parts(Soldier);
    for (const UPrimitiveComponent* Part : Parts)
    {
        if (Part && (Part->GetName().Contains(TEXT("Shield")) || Part->ComponentHasTag(TEXT("SquadShield"))))
        {
            return true;
        }
    }
    return false;
}

void AReflectionsSquad::UpdateMarchSound()
{
    const bool bWant = State == EReflectionsSquadState::Marching || State == EReflectionsSquadState::Reforming;
    AActor* Carrier = bWant ? FirstActiveSoldier() : nullptr;
    if (!Carrier || Carrier != MarchAudioCarrier.Get())
    {
        if (MarchAudio)
        {
            MarchAudio->FadeOut(0.4f, 0.0f);
            MarchAudio = nullptr;
        }
        MarchAudioCarrier.Reset();
    }
    if (!Carrier || MarchAudio)
    {
        return;
    }
    USoundBase* Loop = MarchLoop.IsNull() ? nullptr : MarchLoop.LoadSynchronous();
    USceneComponent* Attach = Carrier->GetAttachParentActor() ? Carrier->GetAttachParentActor()->GetRootComponent() : Carrier->GetRootComponent();
    if (Loop && Attach)
    {
        // Louder the fuller the squad; the loop itself is a loose group of five.
        const float Volume = FMath::Clamp(static_cast<float>(GetAliveCount()) / 5.0f, 0.4f, 1.2f);
        MarchAudio = UGameplayStatics::SpawnSoundAttached(Loop, Attach, NAME_None, FVector::ZeroVector, EAttachLocation::SnapToTarget, true,
            Volume, 1.0f, 0.0f, nullptr, nullptr, false);
        if (MarchAudio)
        {
            MarchAudio->FadeIn(0.5f, Volume);
        }
        MarchAudioCarrier = Carrier;
    }
}

AActor* AReflectionsSquad::FirstActiveSoldier() const
{
    for (const FReflectionsSquadMember& Member : Members)
    {
        if (IsActive(Member))
        {
            return Member.Actor;
        }
    }
    return nullptr;
}

void AReflectionsSquad::Bark(AActor* Speaker)
{
    USkeletalMeshComponent* Body = bBarkOrders ? ReflectionsSquadNpc::GetBody(Speaker) : nullptr;
    if (!Body)
    {
        return;
    }
    // Each soldier keeps the voice slot the NPC system gave it (F1..F3 / M1..M3); the slotless cue is the fallback.
    const FString Suffix = ReflectionsSquadNpc::GetVoiceSuffix(Speaker);
    USoundBase* Cue = nullptr;
    if (!Suffix.IsEmpty())
    {
        const FString Name = TEXT("SCue_VO_Soldier_Command_") + Suffix;
        Cue = LoadObject<USoundBase>(nullptr, *FString::Printf(TEXT("/Game/Audio/Jam/Voice/Cues/%s.%s"), *Name, *Name), nullptr, LOAD_NoWarn | LOAD_Quiet);
    }
    if (!Cue)
    {
        Cue = LoadObject<USoundBase>(nullptr, TEXT("/Game/Audio/Jam/Voice/Cues/SCue_VO_Soldier_Command.SCue_VO_Soldier_Command"), nullptr, LOAD_NoWarn | LOAD_Quiet);
    }
    if (Cue)
    {
        UGameplayStatics::SpawnSoundAttached(Cue, Body, TEXT("head"), FVector::ZeroVector, EAttachLocation::SnapToTarget, true);
    }
}

void AReflectionsSquad::Reform()
{
    Foe.Reset();
    FVector Centroid = FVector::ZeroVector;
    int32 Count = 0;
    for (FReflectionsSquadMember& Member : Members)
    {
        if (!IsActive(Member))
        {
            continue;
        }
        EndCast(Member, true);
        Member.DeployTime = 0.0f;
        Member.bCharging = false;
        if (Member.Role == EReflectionsSquadRole::Melee)
        {
            ReflectionsSquadNpc::SetMeleeTarget(Member.Actor, nullptr);
        }
        if (Member.State == EReflectionsSquadMemberState::Fighting)
        {
            Member.State = EReflectionsSquadMemberState::InFormation;
        }
        if (ACharacter* Driver = ReflectionsSquadNpc::GetDriver(Member.Actor))
        {
            Centroid += Driver->GetActorLocation();
            ++Count;
        }
    }
    if (Count > 0 && Waypoints.Num() > 0)
    {
        Centroid = GroundAt(Centroid / Count);
        int32 Nearest = 0;
        float Best = TNumericLimits<float>::Max();
        for (int32 Index = 0; Index < Waypoints.Num(); ++Index)
        {
            const float Distance = FVector::DistSquared2D(Waypoints[Index], Centroid);
            if (Distance < Best)
            {
                Best = Distance;
                Nearest = Index;
            }
        }
        if (Best < FMath::Square(150.0f) && Waypoints.Num() > 1)
        {
            Nearest = (Nearest + 1) % Waypoints.Num();
        }
        AnchorLocation = Centroid;
        WaypointIndex = Nearest;
        const FVector Heading = Flat(Waypoints[Nearest] - Centroid);
        AnchorYaw = Heading.IsNearlyZero() ? AnchorYaw : Heading.Rotation().Yaw;
        SeedTrail(AnchorLocation, AnchorYaw);
        BuildLeg(AnchorLocation);
    }
    ReformTimer = 0.0f;
    Pace = 0.0f;
    AggravationGrace = 8.0f;
    bProvokedByPlayer = false;
    SetState(EReflectionsSquadState::Reforming, nullptr);
}

void AReflectionsSquad::TickCombat(float DeltaSeconds)
{
    AActor* Player = Foe.Get();
    if (Player != GetPlayer() && IsPlayerDown(Player))
    {
        // The target (a tarnished, an enemy soldier) is down: the next enemy in sight, or stand down.
        if (AActor* Next = FindHostileInSight())
        {
            BarkEvent(FirstActiveSoldier(), TEXT("Soldier_EnemyDown"));
            Foe = Next;
            RetargetMelee(Next);
            Player = Next;
        }
        else
        {
            BarkEvent(FirstActiveSoldier(), TEXT("Soldier_Victory"));
            Reform();
            return;
        }
    }
    // The fight goes on while any soldier still sees the player; out of sight for LoseSightTime, they reform.
    SightCheckTimer -= DeltaSeconds;
    if (SightCheckTimer <= 0.0f)
    {
        SightCheckTimer = 0.4f;
        bFoeInSight = false;
        if (!IsPlayerDown(Player))
        {
            for (const FReflectionsSquadMember& Member : Members)
            {
                if (IsActive(Member) && FVector::Dist2D(Member.Actor->GetActorLocation(), Player->GetActorLocation()) <= LoseRadius &&
                    HasLineOfSight(Member.Actor, Player))
                {
                    bFoeInSight = true;
                    break;
                }
            }
        }
    }
    LostTimer = bFoeInSight ? 0.0f : LostTimer + DeltaSeconds;
    if (LostTimer > LoseSightTime)
    {
        BarkEvent(FirstActiveSoldier(), TEXT("Soldier_Retreat"));
        Reform();
        return;
    }
    if (IsPlayerDown(Player))
    {
        // Let in-flight casts finish, then stand down.
        for (FReflectionsSquadMember& Member : Members)
        {
            if (IsActive(Member) && Member.CastPhase != EReflectionsSquadCastPhase::Ready)
            {
                TickCaster(Member, Player, DeltaSeconds);
            }
        }
        return;
    }
    BarkTimer -= DeltaSeconds;
    if (BarkTimer <= 0.0f)
    {
        BarkTimer = FMath::FRandRange(BarkInterval.X, FMath::Max(BarkInterval.X, BarkInterval.Y));
        TArray<AActor*, TInlineAllocator<8>> Speakers;
        for (const FReflectionsSquadMember& Member : Members)
        {
            if (IsActive(Member))
            {
                Speakers.Add(Member.Actor);
            }
        }
        if (Speakers.Num() > 0)
        {
            Bark(Speakers[FMath::RandHelper(Speakers.Num())]);
        }
    }
    for (FReflectionsSquadMember& Member : Members)
    {
        if (!IsActive(Member) || !ReflectionsSquadNpc::GetDriver(Member.Actor))
        {
            continue;
        }
        if (Member.Role == EReflectionsSquadRole::Caster)
        {
            TickCaster(Member, Player, DeltaSeconds);
        }
        else
        {
            // Melee: the squad runs each soldier down to the player (navmesh path when there is one), and the NPC
            // melee motor strikes once it is close. If the player gets away from the motor, run it down again.
            ACharacter* Driver = ReflectionsSquadNpc::GetDriver(Member.Actor);
            const FVector ToMember = Flat(Driver->GetActorLocation() - Player->GetActorLocation());
            const float Distance = ToMember.Size();
            if (!Member.bCharging && Distance > MeleeHandOverRange * 2.5f)
            {
                Member.bCharging = true;
                Member.RepathTimer = 0.0f;
                ReflectionsSquadNpc::SetMeleeTarget(Member.Actor, nullptr);
            }
            if (Member.bCharging)
            {
                if (Distance < MeleeHandOverRange)
                {
                    Member.bCharging = false;
                    ReflectionsSquadNpc::SetMeleeTarget(Member.Actor, Player);
                }
                else
                {
                    const FVector Out = ToMember.IsNearlyZero() ? FVector::ForwardVector : ToMember.GetSafeNormal();
                    const FVector Flank = Player->GetActorLocation() + Out.RotateAngleAxis(Member.FlankAngle, FVector::UpVector) * 260.0f;
                    Member.RepathTimer -= DeltaSeconds;
                    if (Member.RepathTimer <= 0.0f)
                    {
                        Member.RepathTimer = 0.5f;
                        Member.ChargeWaypoint = NextPathPoint(Driver->GetActorLocation(), Flank);
                    }
                    SteerTo(Member, Member.ChargeWaypoint, FVector::ZeroVector, 650.0f, DeltaSeconds);
                }
            }
        }
    }
}

void AReflectionsSquad::TickCaster(FReflectionsSquadMember& Member, AActor* Player, float DeltaSeconds)
{
    ACharacter* Driver = ReflectionsSquadNpc::GetDriver(Member.Actor);
    if (!Driver)
    {
        return;
    }
    if (Member.CastPhase != EReflectionsSquadCastPhase::Ready)
    {
        Member.CastTime += DeltaSeconds;
        if (IsValid(Player) && Member.CastPhase == EReflectionsSquadCastPhase::Windup)
        {
            FaceYaw(Driver, Flat(Player->GetActorLocation() - Driver->GetActorLocation()).Rotation().Yaw, DeltaSeconds * 2.0f);
        }
        if (Member.CastPhase == EReflectionsSquadCastPhase::Windup)
        {
            const float Alpha = FMath::Clamp(Member.CastTime / FMath::Max(0.05f, Member.CastReleaseAt), 0.0f, 1.0f);
            if (Member.TelegraphLight)
            {
                Member.TelegraphLight->SetIntensity(FMath::Lerp(500.0f, 9000.0f, Alpha * Alpha));
            }
            if (Member.Telegraph)
            {
                Member.Telegraph->SetVariableFloat(TEXT("User.Scale"), FMath::Lerp(0.15f, 0.55f, Alpha));
            }
            if (Member.ReleaseClipAt >= 0.0f && Member.CastTime >= Member.ReleaseClipAt && Member.bWalkerGesture)
            {
                if (ReflectionsSquadNpc::IsAlive(Member.Actor))
                {
                    ReflectionsSquadNpc::PlayOnWalker(Member.Actor, LoadedWalkerRelease, Member.ReleaseRate);
                }
                Member.ReleaseClipAt = -1.0f;
            }
            if (Member.ReleaseClipAt >= 0.0f && Member.CastTime >= Member.ReleaseClipAt)
            {
                UAnimSequence* Release = Member.ReleaseClip.Get();
                USkeletalMeshComponent* Body = ReflectionsSquadNpc::GetBody(Member.Actor);
                if (Release && Body && ReflectionsSquadNpc::IsAlive(Member.Actor))
                {
                    Body->PlayAnimation(Release, false);
                    Body->SetPlayRate(Member.ReleaseRate);
                }
                Member.ReleaseClip = nullptr;
                Member.ReleaseClipAt = -1.0f;
            }
            if (Member.CastTime >= Member.CastReleaseAt)
            {
                if (IsValid(Player))
                {
                    ReleaseCast(Member, Player);
                }
                Member.CastPhase = EReflectionsSquadCastPhase::Recover;
            }
        }
        if (Member.CastPhase == EReflectionsSquadCastPhase::Recover && Member.CastTime >= Member.CastEnd)
        {
            EndCast(Member, true);
            Member.CastCooldown = FMath::FRandRange(CastCooldown.X, FMath::Max(CastCooldown.X, CastCooldown.Y));
        }
        return;
    }
    if (!IsValid(Player))
    {
        return;
    }

    const FVector ToPlayer = Flat(Player->GetActorLocation() - Driver->GetActorLocation());
    const float Distance = ToPlayer.Size();
    Member.SightTimer -= DeltaSeconds;
    if (Member.SightTimer <= 0.0f)
    {
        Member.SightTimer = FMath::FRandRange(0.25f, 0.4f);
        Member.bHasSight = HasLineOfSight(Member.Actor, Player);
    }
    Member.CastCooldown -= DeltaSeconds;
    const float Now = GetWorld()->GetTimeSeconds();
    if (Member.CastCooldown <= 0.0f && Member.bHasSight && Distance <= CastRange && Now - LastSquadCast >= SquadCastSpacing)
    {
        LastSquadCast = Now;
        StartCast(Member, Player);
        return;
    }

    // Keep range: back off when rushed, close in when out of range or blocked, otherwise drift sideways.
    const FVector Away = -ToPlayer.GetSafeNormal();
    Member.StrafeTimer -= DeltaSeconds;
    if (Member.StrafeTimer <= 0.0f)
    {
        Member.StrafeTimer = FMath::FRandRange(2.0f, 4.0f);
        Member.StrafeSign = FMath::RandBool() ? 1.0f : -1.0f;
    }
    const FVector Side = RightOf(Away) * Member.StrafeSign;
    FVector Desired;
    if (Distance < CasterMinRange)
    {
        Desired = Away * 240.0f + Side * 60.0f;
    }
    else if (!Member.bHasSight)
    {
        // No shot: circle the target to find a gap (no navmesh needed), closing in slowly if far.
        Desired = Side * 230.0f + (Distance > CasterMaxRange ? -Away * 120.0f : FVector::ZeroVector);
    }
    else if (Distance > CasterMaxRange)
    {
        Desired = -Away * 210.0f;
    }
    else
    {
        Desired = Side * 90.0f;
    }
    for (const FReflectionsSquadMember& Other : Members)
    {
        if (&Other == &Member || !IsActive(Other))
        {
            continue;
        }
        const FVector Offset = Flat(Member.Actor->GetActorLocation() - Other.Actor->GetActorLocation());
        const float Gap = Offset.Size();
        if (Gap > 1.0f && Gap < 220.0f)
        {
            Desired += Offset / Gap * (220.0f - Gap) * 1.5f;
        }
    }
    const float Speed = FMath::Min(Desired.Size(), 260.0f);
    if (Speed > 20.0f)
    {
        const float Scale = FMath::Clamp(Speed / FMath::Max(1.0f, Driver->GetCharacterMovement()->GetMaxSpeed()), 0.05f, 1.0f);
        Driver->AddMovementInput(Desired.GetSafeNormal(), Scale, true);
    }
    else
    {
        FaceYaw(Driver, ToPlayer.Rotation().Yaw, DeltaSeconds);
    }
}

void AReflectionsSquad::StartCast(FReflectionsSquadMember& Member, AActor* Player)
{
    ACharacter* Driver = ReflectionsSquadNpc::GetDriver(Member.Actor);
    USkeletalMeshComponent* Body = ReflectionsSquadNpc::GetBody(Member.Actor);
    if (!Driver)
    {
        return;
    }
    Driver->GetCharacterMovement()->StopMovementImmediately();
    UpdateMarchAnimation(Member, false);
    Member.CastPhase = EReflectionsSquadCastPhase::Windup;
    Member.CastTime = 0.0f;
    Member.CastReleaseAt = FMath::Max(0.2f, CastWindup);
    Member.CastEnd = Member.CastReleaseAt + 0.45f;
    Member.ReleaseClip = nullptr;
    Member.ReleaseClipAt = -1.0f;
    Member.bWalkerGesture = false;
    if (CVarSquadBodyClips.GetValueOnGameThread() == 0)
    {
        // Crash-safe: channel, then the flick timed so its strike (0.27 s) lands on the release, as montages on the
        // hidden walker. The visible body's animation mode is never switched.
        if (LoadedWalkerRelease && ReflectionsSquadNpc::GetDriver(Member.Actor))
        {
            const float Strike = FMath::Clamp(ReleaseAnimationStrike, 0.05f, LoadedWalkerRelease->GetPlayLength());
            Member.ReleaseRate = FMath::Clamp(Strike / Member.CastReleaseAt, 1.0f, 1.8f);
            Member.ReleaseClipAt = FMath::Max(0.0f, Member.CastReleaseAt - Strike / Member.ReleaseRate);
            Member.CastEnd = Member.CastReleaseAt + FMath::Max(0.3f, (LoadedWalkerRelease->GetPlayLength() - Strike) / Member.ReleaseRate * 0.9f);
            Member.bWalkerGesture = true;
            if (Member.ReleaseClipAt > 0.1f)
            {
                ReflectionsSquadNpc::PlayOnWalker(Member.Actor, LoadedWalkerChannel, 1.0f);
            }
        }
    }
    else
    {
        UAnimSequence* ReleaseClip = ClipFor(LoadedReleaseAnimations, Body);
        UAnimSequence* ChannelClip = ReleaseClip ? ClipFor(LoadedChannelAnimations, Body) : nullptr;
        UAnimSequence* CastClip = ReleaseClip ? nullptr : ClipFor(LoadedCastAnimations, Body);
        if (!ReleaseClip && !CastClip && Body && LoadedCastAnimations.Num() + LoadedReleaseAnimations.Num() > 0 && !bWarnedCastClip)
        {
            bWarnedCastClip = true;
            UE_LOG(LogTemp, Warning, TEXT("Squad %s: no cast clip matches %s's skeleton; it casts without a gesture"),
                *GetName(), *GetNameSafe(Member.Actor));
        }
        if (Body && (ReleaseClip || CastClip) && !Member.SavedAnimClass)
        {
            Member.SavedAnimClass = Body->GetAnimClass();
        }
        if (ReleaseClip && Body)
        {
            // Channel while the spell gathers, then cut to the release clip so its strike lands on the release. The
            // telegraph keeps its full length; only a very short windup speeds the release clip up.
            const float Strike = FMath::Clamp(ReleaseAnimationStrike, 0.05f, ReleaseClip->GetPlayLength());
            Member.ReleaseRate = FMath::Clamp(Strike / Member.CastReleaseAt, 1.0f, 1.8f);
            Member.ReleaseClipAt = FMath::Max(0.0f, Member.CastReleaseAt - Strike / Member.ReleaseRate);
            Member.ReleaseClip = ReleaseClip;
            Member.CastEnd = Member.CastReleaseAt + FMath::Max(0.3f, (ReleaseClip->GetPlayLength() - Strike) / Member.ReleaseRate * 0.9f);
            if (ChannelClip && Member.ReleaseClipAt > 0.1f)
            {
                const float Length = FMath::Max(0.1f, ChannelClip->GetPlayLength());
                const float* End = ChannelEnds.Find(ChannelClip);
                const float Start = FMath::Fmod((End ? *End : 0.0f) - Member.ReleaseClipAt + Length * 4.0f, Length);
                Body->PlayAnimation(ChannelClip, true);
                Body->SetPlayRate(1.0f);
                Body->SetPosition(Start, false);
            }
            else if (Member.ReleaseClipAt <= 0.0f)
            {
                Body->PlayAnimation(ReleaseClip, false);
                Body->SetPlayRate(Member.ReleaseRate);
                Member.ReleaseClip = nullptr;
            }
        }
        else if (CastClip && Body)
        {
            const float Rate = FMath::Clamp(CastAnimationRelease / Member.CastReleaseAt, 0.6f, 1.8f);
            Body->PlayAnimation(CastClip, false);
            Body->SetPlayRate(Rate);
            Member.CastReleaseAt = CastAnimationRelease / Rate;
            Member.CastEnd = FMath::Max(Member.CastReleaseAt + 0.3f, CastClip->GetPlayLength() / Rate * 0.82f);
        }
    }
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Member.Spell);
    const FLinearColor Color = ReflectionsSpellCatalog::ElementColor(Spec.Element);
    USceneComponent* HandParent = Body ? static_cast<USceneComponent*>(Body) : Driver->GetRootComponent();
    const FName Socket = Body && Body->DoesSocketExist(CastHand) ? CastHand : NAME_None;
    if (TelegraphSystem)
    {
        Member.Telegraph = UNiagaraFunctionLibrary::SpawnSystemAttached(TelegraphSystem, HandParent, Socket,
            FVector::ZeroVector, FRotator::ZeroRotator, EAttachLocation::SnapToTarget, false, true, ENCPoolMethod::None, true);
        if (Member.Telegraph)
        {
            Member.Telegraph->SetVariableLinearColor(TEXT("User.Color"), Color);
            Member.Telegraph->SetVariableLinearColor(TEXT("User.Color2"), Color * 0.6f);
            Member.Telegraph->SetVariableFloat(TEXT("User.Scale"), 0.15f);
            Member.Telegraph->SetVariableFloat(TEXT("User.CoreSize"), 18.0f);
        }
    }
    UPointLightComponent* Light = NewObject<UPointLightComponent>(Member.Actor, NAME_None, RF_Transient);
    Light->SetMobility(EComponentMobility::Movable);
    Light->SetCastShadows(false);
    Light->SetLightColor(Color);
    Light->SetIntensity(500.0f);
    Light->SetAttenuationRadius(420.0f);
    Light->RegisterComponent();
    Light->AttachToComponent(HandParent, FAttachmentTransformRules::SnapToTargetNotIncludingScale, Socket);
    Member.TelegraphLight = Light;
}

void AReflectionsSquad::ReleaseCast(FReflectionsSquadMember& Member, AActor* Player)
{
    UWorld* World = GetWorld();
    ACharacter* Driver = ReflectionsSquadNpc::GetDriver(Member.Actor);
    if (!World || !Driver || !IsValid(Player))
    {
        return;
    }
    USkeletalMeshComponent* Body = ReflectionsSquadNpc::GetBody(Member.Actor);
    const FVector Forward = Flat(Player->GetActorLocation() - Driver->GetActorLocation()).GetSafeNormal();
    FVector Hand = Body && Body->DoesSocketExist(CastHand) ? Body->GetSocketLocation(CastHand) : Driver->GetActorLocation() + FVector(0.0, 0.0, 50.0);
    Hand += Forward * 35.0f;

    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Member.Spell);
    const float Speed = FMath::Max(100.0f, Spec.Speed);
    FVector Aim = Player->GetActorLocation() + FVector(0.0, 0.0, 25.0);
    const float Flight = FVector::Dist(Aim, Hand) / Speed;
    Aim += Flat(Player->GetVelocity()) * Flight * AimLead;
    Aim += FMath::VRand() * FMath::FRandRange(0.0f, 45.0f);
    FVector Direction = (Aim - Hand).GetSafeNormal();
    if (Direction.IsNearlyZero())
    {
        Direction = Forward;
    }

    const FTransform Launch(Direction.Rotation(), Hand);
    AReflectionsSpellProjectile* Projectile = World->SpawnActorDeferred<AReflectionsSpellProjectile>(
        AReflectionsSpellProjectile::StaticClass(), Launch, Member.Actor, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (Projectile)
    {
        const UReflectionsSpellCombatComponent* Spells = Member.Actor->FindComponentByClass<UReflectionsSpellCombatComponent>();
        const bool bWater = Spec.Element == EReflectionsSpellElement::Water || Spec.Element == EReflectionsSpellElement::Ice;
        UStaticMesh* Mesh = Spells ? (bWater ? Spells->WaterMesh.Get() : Spells->FireMesh.Get()) : nullptr;
        UMaterialInterface* Material = Spells ? (bWater ? Spells->WaterMaterial.Get() : Spells->FireMaterial.Get()) : nullptr;
        Projectile->Initialize(Member.Spell, Spec.Power * CasterDamageScale, Speed, FMath::Max(Spec.Range, CastRange + 400.0f), Mesh, Material);
        Projectile->FinishSpawning(Launch);
        if (UPrimitiveComponent* Collision = Cast<UPrimitiveComponent>(Projectile->GetRootComponent()))
        {
            // No friendly fire inside the squad.
            for (const FReflectionsSquadMember& Other : Members)
            {
                if (IsValid(Other.Actor))
                {
                    Collision->IgnoreActorWhenMoving(Other.Actor, true);
                    if (ACharacter* OtherDriver = ReflectionsSquadNpc::GetDriver(Other.Actor))
                    {
                        Collision->IgnoreActorWhenMoving(OtherDriver, true);
                    }
                }
            }
        }
    }
    if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
    {
        // Same muzzle flash and cast sound as the player's release.
        Events->OnSpellReleaseVisual.Broadcast(Member.Spell, Hand, Direction, Member.Actor, 0.35f + Spec.Radius / 600.0f);
    }
    ++Member.CastsReleased;
    if (Member.Telegraph)
    {
        Member.Telegraph->DestroyComponent();
        Member.Telegraph = nullptr;
    }
    if (Member.TelegraphLight)
    {
        Member.TelegraphLight->DestroyComponent();
        Member.TelegraphLight = nullptr;
    }
}

void AReflectionsSquad::EndCast(FReflectionsSquadMember& Member, bool bRestoreAnimation)
{
    if (Member.Telegraph)
    {
        Member.Telegraph->DestroyComponent();
        Member.Telegraph = nullptr;
    }
    if (Member.TelegraphLight)
    {
        Member.TelegraphLight->DestroyComponent();
        Member.TelegraphLight = nullptr;
    }
    const bool bWasCasting = Member.CastPhase != EReflectionsSquadCastPhase::Ready;
    Member.CastPhase = EReflectionsSquadCastPhase::Ready;
    Member.ReleaseClip = nullptr;
    Member.ReleaseClipAt = -1.0f;
    if (bWasCasting && Member.SavedAnimClass && !Member.bMarchClipActive)
    {
        if (bRestoreAnimation && ReflectionsSquadNpc::IsAlive(Member.Actor))
        {
            if (USkeletalMeshComponent* Body = ReflectionsSquadNpc::GetBody(Member.Actor))
            {
                Body->SetAnimInstanceClass(Member.SavedAnimClass);
            }
        }
        Member.SavedAnimClass = nullptr;
    }
}

// ---- Test helpers ----------------------------------------------------------------------------------------------------

bool AReflectionsSquad::DebugForceCast()
{
    AActor* Player = GetPlayer();
    if (IsPlayerDown(Player))
    {
        return false;
    }
    if (State != EReflectionsSquadState::Engaged)
    {
        Engage(Player);
    }
    for (FReflectionsSquadMember& Member : Members)
    {
        if (IsActive(Member) && Member.Role == EReflectionsSquadRole::Caster &&
            Member.CastPhase == EReflectionsSquadCastPhase::Ready && ReflectionsSquadNpc::GetDriver(Member.Actor))
        {
            LastSquadCast = GetWorld()->GetTimeSeconds();
            StartCast(Member, Player);
            return true;
        }
    }
    return false;
}

void AReflectionsSquad::DebugKillAll()
{
    for (FReflectionsSquadMember& Member : Members)
    {
        if (IsActive(Member))
        {
            ReflectionsSquadNpc::Kill(Member.Actor, GetPlayer());
        }
    }
}

void AReflectionsSquad::DrawDebug() const
{
#if ENABLE_DRAW_DEBUG
    UWorld* World = GetWorld();
    for (int32 Index = 0; Index < Waypoints.Num(); ++Index)
    {
        DrawDebugSphere(World, Waypoints[Index] + FVector(0, 0, 20), 30.0f, 8, FColor::Yellow, false, -1.0f);
        if (Index + 1 < Waypoints.Num() || !Route || Route->bLoop)
        {
            DrawDebugLine(World, Waypoints[Index] + FVector(0, 0, 20), Waypoints[(Index + 1) % Waypoints.Num()] + FVector(0, 0, 20), FColor::Yellow, false, -1.0f, 0, 2.0f);
        }
    }
    DrawDebugSphere(World, AnchorLocation + FVector(0, 0, 40), 25.0f, 8, FColor::Cyan, false, -1.0f);
    DrawDebugDirectionalArrow(World, AnchorLocation + FVector(0, 0, 40), AnchorLocation + FVector(0, 0, 40) + FRotator(0, AnchorYaw, 0).Vector() * 150.0f, 40.0f, FColor::Cyan, false, -1.0f, 0, 3.0f);
    int32 Slot = 0;
    int32 SlotCount = 0;
    for (const FReflectionsSquadMember& Member : Members)
    {
        SlotCount += IsActive(Member) ? 1 : 0;
    }
    for (const FReflectionsSquadMember& Member : Members)
    {
        if (!IsActive(Member))
        {
            continue;
        }
        const FVector Goal = ComputeSlot(Slot++, SlotCount) + FVector(0, 0, 10);
        DrawDebugCircle(World, Goal, 30.0f, 16, Member.Role == EReflectionsSquadRole::Caster ? FColor::Purple : FColor::Green, false, -1.0f, 0, 2.0f, FVector(1, 0, 0), FVector(0, 1, 0), false);
        if (const ACharacter* Driver = ReflectionsSquadNpc::GetDriver(Member.Actor))
        {
            DrawDebugLine(World, Driver->GetActorLocation(), Goal, FColor::White, false, -1.0f, 0, 1.0f);
            if (CVarSquadDebug.GetValueOnGameThread() > 1)
            {
                DrawDebugString(World, Driver->GetActorLocation() + FVector(0, 0, 120), FString::Printf(TEXT("%s %s"),
                    *UEnum::GetDisplayValueAsText(Member.State).ToString(), *UEnum::GetDisplayValueAsText(Member.CastPhase).ToString()), nullptr, FColor::White, 0.0f);
            }
        }
    }
    DrawDebugString(World, AnchorLocation + FVector(0, 0, 220), UEnum::GetDisplayValueAsText(State).ToString(), nullptr, FColor::Cyan, 0.0f);
#endif
}
