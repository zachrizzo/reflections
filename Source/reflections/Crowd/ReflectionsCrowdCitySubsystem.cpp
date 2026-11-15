#include "Crowd/ReflectionsCrowdCitySubsystem.h"
#include "Crowd/ReflectionsCrowdLookRow.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "Annotations/ZoneGraphDisturbanceAnnotation.h"
#include "Engine/LevelStreamingDynamic.h"
#include "Engine/World.h"
#include "GameFramework/DamageType.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/DataTable.h"
#include "Mass/EntityFragments.h"
#include "Mass/MetaHumanMassCrowdVisualizationTrait.h"
#include "Mass/MetaHumanMassFragments.h"
#include "MassCrowdFragments.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityQuery.h"
#include "MassEntitySubsystem.h"
#include "MassExecutionContext.h"
#include "MetaHumanCrowdStatsLibrary.h"
#include "Misc/PackageName.h"
#include "UObject/UnrealType.h"
#include "ZoneGraphAnnotationSubsystem.h"
#include "ZoneGraphTypes.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsCrowdCity, Log, All);

namespace
{
    // Off by default until the crowd's MetaHuman looks are finished (crowd-looks session); set 1 to stream it in.
    TAutoConsoleVariable<int32> CVarCrowdMassEnable(TEXT("Crowd.Mass.Enable"), 0,
        TEXT("City crowd (Mass / MetaHuman Crowd pedestrians on ZoneGraph lanes). 1 streams the crowd level in; 0 unloads it and every pedestrian."));
    TAutoConsoleVariable<FString> CVarCrowdMassHostMap(TEXT("Crowd.Mass.HostMap"), TEXT("Lvl_HeroSampleCrowd"),
        TEXT("Short name of the map the city crowd is streamed into."));
    TAutoConsoleVariable<FString> CVarCrowdMassLevel(TEXT("Crowd.Mass.Level"), TEXT("/Game/Crowd/City/Lvl_HeroSampleCrowd_City"),
        TEXT("Long package name of the crowd level (ZoneGraph lanes, annotations, Mass spawner)."));
    TAutoConsoleVariable<float> CVarCrowdMassDangerRadius(TEXT("Crowd.Mass.DangerRadius"), 1500.0f,
        TEXT("Smallest radius (cm) of the lane danger area an NPC stimulus creates."));
    TAutoConsoleVariable<float> CVarCrowdMassDangerSeconds(TEXT("Crowd.Mass.DangerSeconds"), 6.0f,
        TEXT("How long pedestrians keep escaping from a stimulus."));
    TAutoConsoleVariable<float> CVarCrowdMassPromoteRadius(TEXT("Crowd.Mass.PromoteRadius"), 700.0f,
        TEXT("Pedestrians this close (cm) to an NPC stimulus, or inside a spell's blast, become full NPC actors."));
    TAutoConsoleVariable<int32> CVarCrowdMassMaxPromoted(TEXT("Crowd.Mass.MaxPromoted"), 6,
        TEXT("Most promoted pedestrians alive and standing at once (each is a full sample character)."));
    TAutoConsoleVariable<FString> CVarCrowdMassLookTable(TEXT("Crowd.Mass.LookTable"), TEXT("/Game/Crowd/City/DT_CrowdLookMap.DT_CrowdLookMap"),
        TEXT("DataTable of FReflectionsCrowdLookRow: which full NPC look each crowd MetaHuman Instance becomes when promoted."));
    TAutoConsoleVariable<FString> CVarCrowdMassEntityConfig(TEXT("Crowd.Mass.EntityConfig"), TEXT("/Game/Crowd/City/MEC_CityPedestrian.MEC_CityPedestrian"),
        TEXT("The pedestrians' Mass entity config (its MetaHuman Crowd visualization lists the crowd's instances)."));
    TAutoConsoleVariable<float> CVarCrowdMassReleaseDistance(TEXT("Crowd.Mass.ReleaseDistance"), 3000.0f,
        TEXT("A calm promoted pedestrian this far (cm) from the player..."));
    TAutoConsoleVariable<float> CVarCrowdMassReleaseSeconds(TEXT("Crowd.Mass.ReleaseSeconds"), 20.0f,
        TEXT("...for this long walks out of the scene (its actor is removed)."));

    /**
     * Which of the crowd visualization's CharacterInstances a pedestrian wears (INDEX_NONE if unknown). The
     * MetaHuman Crowd fragments are not exported from their module, so their types are looked up by name and
     * read through their layout instead of StaticStruct().
     */
    int32 PedestrianInstanceIndex(const FMassEntityManager& Manager, FMassEntityHandle Entity)
    {
        static const UScriptStruct* IdentityType = FindObject<UScriptStruct>(nullptr, TEXT("/Script/MetaHumanCrowd.MetaHumanMassIdentityFragment"));
        static const UScriptStruct* AppearanceType = FindObject<UScriptStruct>(nullptr, TEXT("/Script/MetaHumanCrowd.MetaHumanAppearanceSharedFragment"));
        if (!IdentityType || !AppearanceType || !Manager.IsEntityValid(Entity)) return INDEX_NONE;
        const FStructView Identity = Manager.GetFragmentDataStruct(Entity, IdentityType);
        const FConstStructView Appearance = Manager.GetSharedFragmentDataStruct(Entity, AppearanceType);
        if (!Identity.GetMemory() || !Appearance.GetMemory()) return INDEX_NONE;
        const uint32 AppearanceIndex = reinterpret_cast<const FMetaHumanMassIdentityFragment*>(Identity.GetMemory())->AppearanceIndex;
        // The shared list is built from CharacterInstances in order, so its position is the instance.
        return reinterpret_cast<const FMetaHumanAppearanceSharedFragment*>(Appearance.GetMemory())->AssignedAppearanceIndices.IndexOfByKey(AppearanceIndex);
    }

    constexpr double CheckPeriod = 0.5;
    /** The ZoneGraph tag the disturbance annotation puts on endangered lanes; the pedestrian StateTree flees on it. */
    constexpr uint8 DangerTagBit = 1;
    const FName PromotedTag(TEXT("Crowd_Promoted"));
}

#if WITH_EDITOR
#include "ZoneGraphSettings.h"

namespace
{
    // A fixed id, so sidewalk shapes saved with this profile still resolve it once the same profile is in config.
    const FGuid CitySidewalkProfileId(0x5C17E0A1u, 0x2B3D4E5Fu, 0x6A7B8C9Du, 0x0E1F2A3Bu);

    /** Two 150 cm lanes, one each way, tagged Default: the city crowd's sidewalk. Editor-time only. */
    bool EnsureCitySidewalkProfile()
    {
        UZoneGraphSettings* Settings = GetMutableDefault<UZoneGraphSettings>();
        FArrayProperty* Property = FindFProperty<FArrayProperty>(UZoneGraphSettings::StaticClass(), TEXT("LaneProfiles"));
        if (!Settings || !Property) return false;
        TArray<FZoneLaneProfile>& Profiles = *Property->ContainerPtrToValuePtr<TArray<FZoneLaneProfile>>(Settings);
        if (Profiles.ContainsByPredicate([](const FZoneLaneProfile& Profile) { return Profile.ID == CitySidewalkProfileId; })) return true;
        FZoneLaneProfile Profile;
        Profile.Name = TEXT("CitySidewalk");
        Profile.ID = CitySidewalkProfileId;
        FZoneLaneDesc Lane;
        Lane.Width = 150.0f;
        Lane.Tags = FZoneGraphTagMask(1);
        Lane.Direction = EZoneLaneDirection::Forward;
        Profile.Lanes.Add(Lane);
        Lane.Direction = EZoneLaneDirection::Backward;
        Profile.Lanes.Add(Lane);
        Profiles.Add(Profile);
        return true;
    }

    FAutoConsoleCommandWithWorldAndArgs GCrowdCitySetupZoneGraph(TEXT("Crowd.City.SetupZoneGraph"),
        TEXT("Editor: register the CitySidewalk lane profile and turn on ZoneGraph build-while-editing."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
        {
            const bool bProfile = EnsureCitySidewalkProfile();
            if (FBoolProperty* Flag = FindFProperty<FBoolProperty>(UZoneGraphSettings::StaticClass(), TEXT("bBuildZoneGraphWhileEditing")))
            {
                Flag->SetPropertyValue_InContainer(GetMutableDefault<UZoneGraphSettings>(), true);
            }
            // With build-while-editing on, adding or moving a ZoneShape rebuilds that level's ZoneGraph data.
            UE_LOG(LogReflectionsCrowdCity, Display, TEXT("City crowd: sidewalk profile %s, ZoneGraph builds while editing (world %s)."),
                bProfile ? TEXT("ready") : TEXT("missing"), *GetNameSafe(World));
        }));
}
#endif // WITH_EDITOR

bool UReflectionsCrowdCitySubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UReflectionsCrowdCitySubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsCrowdCitySubsystem, STATGROUP_Tickables);
}

void UReflectionsCrowdCitySubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    // PIE worlds carry a UEDPIE_N_ prefix; compare the map's short name without it.
    const FString MapName = UWorld::RemovePIEPrefix(InWorld.GetMapName());
    bHostMap = MapName == CVarCrowdMassHostMap.GetValueOnGameThread();
    CrowdLevelPath = CVarCrowdMassLevel.GetValueOnGameThread();
    if (UReflectionsNpcSubsystem* Npcs = InWorld.GetSubsystem<UReflectionsNpcSubsystem>())
    {
        StimulusHandle = Npcs->OnStimulus().AddUObject(this, &UReflectionsCrowdCitySubsystem::HandleStimulus);
    }
}

void UReflectionsCrowdCitySubsystem::Deinitialize()
{
    if (UWorld* World = GetWorld())
    {
        UReflectionsNpcSubsystem* Npcs = World->GetSubsystem<UReflectionsNpcSubsystem>();
        if (IsValid(Npcs)) Npcs->OnStimulus().Remove(StimulusHandle);
    }
    StimulusHandle.Reset();
    CrowdLevel = nullptr;
    Super::Deinitialize();
}

bool UReflectionsCrowdCitySubsystem::IsCrowdLoaded() const
{
    return CrowdLevel && CrowdLevel->IsLevelLoaded() && CrowdLevel->IsLevelVisible();
}

void UReflectionsCrowdCitySubsystem::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    UWorld* World = GetWorld();
    if (!World || !World->HasBegunPlay() || !bHostMap) return;
    if (!PendingStimuli.IsEmpty()) ProcessPendingStimuli();
    if (!Promoted.IsEmpty()) TickPromoted(DeltaTime);

    const double Time = World->GetTimeSeconds();
    if (Time < NextCheck) return;
    NextCheck = Time + CheckPeriod;

    const bool bWanted = CVarCrowdMassEnable.GetValueOnGameThread() != 0;
    if (bWanted && !CrowdLevel) LoadCrowdLevel();
    else if (!bWanted && CrowdLevel) UnloadCrowdLevel();
    if (IsCrowdLoaded()) EnsureAnnotations();
}

void UReflectionsCrowdCitySubsystem::EnsureAnnotations()
{
    if (AnnotationActor) return;
    UWorld* World = GetWorld();
    FActorSpawnParameters Params;
    Params.ObjectFlags |= RF_Transient;
    AnnotationActor = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Params);
    if (!AnnotationActor) return;
#if WITH_EDITOR
    AnnotationActor->SetActorLabel(TEXT("CityCrowdDisturbanceAnnotation"));
#endif
    // Marks lanes near a disturbance with the danger tag and builds the escape graph the pedestrians flee along.
    UZoneGraphDisturbanceAnnotation* Disturbance = NewObject<UZoneGraphDisturbanceAnnotation>(AnnotationActor, TEXT("CityDisturbance"));
    if (FStructProperty* Property = FindFProperty<FStructProperty>(UZoneGraphDisturbanceAnnotation::StaticClass(), TEXT("DangerAnnotationTag")))
    {
        *Property->ContainerPtrToValuePtr<FZoneGraphTag>(Disturbance) = FZoneGraphTag(DangerTagBit);
    }
    Disturbance->RegisterComponent();
    UE_LOG(LogReflectionsCrowdCity, Log, TEXT("City crowd: disturbance annotation ready (danger tag %d)."), DangerTagBit);
}

void UReflectionsCrowdCitySubsystem::LoadCrowdLevel()
{
    if (CrowdLevelPath.IsEmpty()) return;
    if (!FPackageName::DoesPackageExist(CrowdLevelPath))
    {
        if (!bWarnedMissing)
        {
            UE_LOG(LogReflectionsCrowdCity, Warning, TEXT("City crowd: level %s does not exist; no pedestrians."), *CrowdLevelPath);
            bWarnedMissing = true;
        }
        return;
    }
    const FString ObjectPath = CrowdLevelPath + TEXT(".") + FPackageName::GetShortName(CrowdLevelPath);
    bool bSuccess = false;
    CrowdLevel = ULevelStreamingDynamic::LoadLevelInstanceBySoftObjectPtr(this, TSoftObjectPtr<UWorld>(FSoftObjectPath(ObjectPath)),
        FTransform::Identity, bSuccess, TEXT("CityCrowd"));
    UE_LOG(LogReflectionsCrowdCity, Log, TEXT("City crowd: streaming in %s (%s)."), *CrowdLevelPath, bSuccess ? TEXT("ok") : TEXT("failed"));
    if (!bSuccess) CrowdLevel = nullptr;
}

void UReflectionsCrowdCitySubsystem::UnloadCrowdLevel()
{
    if (CrowdLevel)
    {
        // Unloading the level ends its Mass spawner, which despawns its pedestrians.
        CrowdLevel->SetIsRequestingUnloadAndRemoval(true);
        UE_LOG(LogReflectionsCrowdCity, Log, TEXT("City crowd: unloading %s."), *CrowdLevelPath);
    }
    CrowdLevel = nullptr;
    if (AnnotationActor) AnnotationActor->Destroy();
    AnnotationActor = nullptr;
    PendingStimuli.Reset();
}

void UReflectionsCrowdCitySubsystem::SendDisturbance(FVector Location, float Radius, float Duration)
{
    UWorld* World = GetWorld();
    UZoneGraphAnnotationSubsystem* Annotations = World ? World->GetSubsystem<UZoneGraphAnnotationSubsystem>() : nullptr;
    if (!Annotations) return;
    FZoneGraphDisturbanceArea Danger;
    Danger.Position = Location;
    Danger.Radius = FMath::Max(1.0f, Radius);
    Danger.Duration = FMath::Max(0.1f, Duration);
    // Events from one instigator are merged by the annotation; one id per rounded location keeps separate blasts apart.
    Danger.InstigatorID = GetTypeHash(FIntVector(Location / 200.0f)) | 1u;
    Annotations->SendEvent(Danger);
    ++DisturbancesSent;
}

void UReflectionsCrowdCitySubsystem::HandleStimulus(const FReflectionsNpcStimulus& Stimulus)
{
    if (!IsCrowdLoaded()) return;
    SendDisturbance(Stimulus.Location, FMath::Max(Stimulus.Radius, CVarCrowdMassDangerRadius.GetValueOnGameThread()),
        CVarCrowdMassDangerSeconds.GetValueOnGameThread());
    // A call for help frightens nobody; everything else may pull nearby pedestrians into the NPC system.
    // Promotion waits for the next tick, outside whichever event is broadcasting this stimulus.
    if (Stimulus.Kind != EReflectionsNpcStimulusKind::Alarm) PendingStimuli.Add(Stimulus);
}

int32 UReflectionsCrowdCitySubsystem::CountActivePromoted() const
{
    const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    int32 Count = 0;
    for (const FPromoted& Entry : Promoted)
    {
        const AActor* Actor = Entry.Actor.Get();
        const UReflectionsNpcReactionComponent* Brain = Actor && Npcs ? Npcs->FindNpc(Actor) : nullptr;
        if (Brain && !Brain->IsIncapacitated()) ++Count;
    }
    return Count;
}

void UReflectionsCrowdCitySubsystem::ProcessPendingStimuli(int32 BudgetOverride)
{
    UWorld* World = GetWorld();
    UMassEntitySubsystem* Entities = World ? World->GetSubsystem<UMassEntitySubsystem>() : nullptr;
    if (!Entities)
    {
        PendingStimuli.Reset();
        return;
    }
    FMassEntityManager& Manager = Entities->GetMutableEntityManager();
    if (Manager.IsProcessing()) return; // try again next frame

    const TArray<FReflectionsNpcStimulus> Work = MoveTemp(PendingStimuli);
    PendingStimuli.Reset();
    int32 Budget = BudgetOverride >= 0 ? BudgetOverride : CVarCrowdMassMaxPromoted.GetValueOnGameThread() - CountActivePromoted();
    if (Budget <= 0) return;

    struct FCandidate { FMassEntityHandle Entity; FTransform Transform; bool bTaken = false; };
    TArray<FCandidate> Pedestrians;
    FMassEntityQuery Query(Manager.AsShared());
    Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddTagRequirement<FMassCrowdTag>(EMassFragmentPresence::All);
    FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
    Query.ForEachEntityChunk(Context, [&Pedestrians](FMassExecutionContext& Chunk)
    {
        const TConstArrayView<FTransformFragment> Transforms = Chunk.GetFragmentView<FTransformFragment>();
        for (int32 Index = 0; Index < Chunk.GetNumEntities(); ++Index)
        {
            Pedestrians.Add({ Chunk.GetEntity(Index), Transforms[Index].GetTransform() });
        }
    });
    if (Pedestrians.IsEmpty()) return;

    const float BaseRadius = CVarCrowdMassPromoteRadius.GetValueOnGameThread();
    for (const FReflectionsNpcStimulus& Stimulus : Work)
    {
        float Radius = FMath::Max(BaseRadius, Stimulus.Radius > 0.0f ? FMath::Min(Stimulus.Radius, BaseRadius * 1.5f) : 0.0f);
        if (Stimulus.Kind == EReflectionsNpcStimulusKind::SpellNoise)
        {
            Radius = FMath::Max(Radius, ReflectionsSpellCatalog::Get(Stimulus.Spell).Radius);
        }
        Pedestrians.Sort([&Stimulus](const FCandidate& A, const FCandidate& B)
        {
            return FVector::DistSquared2D(A.Transform.GetLocation(), Stimulus.Location) < FVector::DistSquared2D(B.Transform.GetLocation(), Stimulus.Location);
        });
        for (FCandidate& Candidate : Pedestrians)
        {
            if (Budget <= 0) return;
            if (Candidate.bTaken || !Manager.IsEntityValid(Candidate.Entity)) continue;
            if (FVector::Dist2D(Candidate.Transform.GetLocation(), Stimulus.Location) > Radius) break;
            if (PromoteEntityAt(Candidate.Transform, &Stimulus, PedestrianInstanceIndex(Manager, Candidate.Entity)))
            {
                Manager.DestroyEntity(Candidate.Entity);
                Candidate.bTaken = true;
                --Budget;
            }
        }
    }
}

int32 UReflectionsCrowdCitySubsystem::PromoteNear(FVector Location, float Radius, int32 MaxCount)
{
    FReflectionsNpcStimulus Stimulus;
    Stimulus.Kind = EReflectionsNpcStimulusKind::Alarm; // test promotion: no blast damage, no fear
    Stimulus.Location = Location;
    Stimulus.Radius = Radius;
    const int32 Before = PromotedTotal;
    PendingStimuli.Add(Stimulus);
    ProcessPendingStimuli(FMath::Max(0, MaxCount));
    return PromotedTotal - Before;
}

UClass* UReflectionsCrowdCitySubsystem::ResolvePromotedLook(int32 InstanceIndex)
{
    // Which MetaHuman Instance this pedestrian wears, from the crowd's entity config.
    const UMassEntityConfigAsset* Config = Cast<UMassEntityConfigAsset>(
        FSoftObjectPath(CVarCrowdMassEntityConfig.GetValueOnGameThread()).TryLoad());
    const UMetaHumanMassCrowdVisualizationTrait* Visual = Config
        ? Cast<UMetaHumanMassCrowdVisualizationTrait>(Config->FindTrait(UMetaHumanMassCrowdVisualizationTrait::StaticClass()))
        : nullptr;
    const FString InstancePathName = Visual && Visual->CharacterInstances.IsValidIndex(InstanceIndex) && Visual->CharacterInstances[InstanceIndex]
        ? Visual->CharacterInstances[InstanceIndex].GetPathName() : FString();

    // The full NPC look of the same person, from the crowd look table.
    const UDataTable* Table = Cast<UDataTable>(FSoftObjectPath(CVarCrowdMassLookTable.GetValueOnGameThread()).TryLoad());
    if (!InstancePathName.IsEmpty() && Table && Table->GetRowStruct() == FReflectionsCrowdLookRow::StaticStruct())
    {
        const FSoftObjectPath InstancePath(InstancePathName);
        for (const TPair<FName, uint8*>& Row : Table->GetRowMap())
        {
            const FReflectionsCrowdLookRow* Look = reinterpret_cast<const FReflectionsCrowdLookRow*>(Row.Value);
            if (Look && Look->CrowdInstance.ToSoftObjectPath() == InstancePath)
            {
                if (UClass* Class = Look->ActorClass.LoadSynchronous()) return Class;
            }
        }
    }
    // No mapping: the NPC system picks from the Civilian archetype's looks (the finished civilian looks).
    const FString Key = !InstancePathName.IsEmpty() ? InstancePathName : FString::Printf(TEXT("instance index %d"), InstanceIndex);
    if (!WarnedLooks.Contains(Key))
    {
        WarnedLooks.Add(Key);
        UE_LOG(LogReflectionsCrowdCity, Log, TEXT("City crowd: no look mapping for %s in %s; the promoted pedestrian gets a Civilian look."),
            *Key, *CVarCrowdMassLookTable.GetValueOnGameThread());
    }
    return nullptr;
}

TArray<FVector> UReflectionsCrowdCitySubsystem::GetPedestrianLocations(FVector Center, float Radius)
{
    TArray<FVector> Locations;
    UWorld* World = GetWorld();
    UMassEntitySubsystem* Entities = World ? World->GetSubsystem<UMassEntitySubsystem>() : nullptr;
    if (!Entities) return Locations;
    FMassEntityManager& Manager = Entities->GetMutableEntityManager();
    if (Manager.IsProcessing()) return Locations;
    FMassEntityQuery Query(Manager.AsShared());
    Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddTagRequirement<FMassCrowdTag>(EMassFragmentPresence::All);
    FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
    const float RadiusSq = Radius > 0.0f ? FMath::Square(Radius) : TNumericLimits<float>::Max();
    Query.ForEachEntityChunk(Context, [&Locations, Center, RadiusSq](FMassExecutionContext& Chunk)
    {
        const TConstArrayView<FTransformFragment> Transforms = Chunk.GetFragmentView<FTransformFragment>();
        for (int32 Index = 0; Index < Chunk.GetNumEntities(); ++Index)
        {
            const FVector Location = Transforms[Index].GetTransform().GetLocation();
            if (FVector::DistSquared2D(Location, Center) <= RadiusSq) Locations.Add(Location);
        }
    });
    return Locations;
}

AActor* UReflectionsCrowdCitySubsystem::PromoteEntityAt(const FTransform& Transform, const FReflectionsNpcStimulus* Cause, int32 InstanceIndex)
{
    UWorld* World = GetWorld();
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!World || !Npcs) return nullptr;

    // Spawned and enrolled by the NPC system like any civilian: sample locomotion pawn, hit capsule, Civilian archetype.
    AActor* Actor = Npcs->SpawnNpc(TEXT("Civilian"), Transform.GetLocation(), Transform.Rotator().Yaw, ResolvePromotedLook(InstanceIndex));
    UReflectionsNpcReactionComponent* Brain = Actor ? Npcs->FindNpc(Actor) : nullptr;
    if (!Brain)
    {
        if (Actor) Actor->Destroy();
        return nullptr;
    }
    // A city civilian: heals with allies, and remembered as a former crowd member.
    Actor->Tags.AddUnique(TEXT("Friendly"));
    Actor->Tags.AddUnique(PromotedTag);
    Promoted.Add({ Actor, 0.0f });
    ++PromotedTotal;

    if (Cause && Cause->Kind != EReflectionsNpcStimulusKind::Alarm)
    {
        AActor* Instigator = Cause->Instigator.Get();
        const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Cause->Spell);
        const FVector Here = Actor->GetActorLocation();
        const bool bInsideBlast = Cause->Kind == EReflectionsNpcStimulusKind::SpellNoise && IsValid(Instigator)
            && Spec.Radius > 0.0f && Spec.Power > 0.0f && FVector::Dist2D(Here, Cause->Location) <= Spec.Radius;
        if (bInsideBlast)
        {
            // It stood inside the blast the spell already resolved: the same damage and hit the placed NPCs got.
            const APawn* Pawn = Cast<APawn>(Instigator);
            UGameplayStatics::ApplyDamage(Actor, Spec.Power, Pawn ? Pawn->GetController() : nullptr, Instigator, UDamageType::StaticClass());
            FReflectionsSpellHitData Hit;
            Hit.Spell = Cause->Spell;
            Hit.Caster = Instigator;
            Hit.Target = Actor;
            Hit.Location = Here + FVector(0.0f, 0.0f, 90.0f);
            const FVector Away = (Here - Cause->Location).GetSafeNormal2D();
            Hit.Impulse = Away * Spec.Impulse;
            Hit.ImpactNormal = -Away;
            Npcs->ReportSpellHit(Hit);
        }
        else
        {
            Brain->ReceiveStimulus(*Cause, Npcs->GetReputation(Instigator));
        }
    }
    return Actor;
}

void UReflectionsCrowdCitySubsystem::TickPromoted(float DeltaTime)
{
    const UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    const APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
    const float ReleaseDistance = CVarCrowdMassReleaseDistance.GetValueOnGameThread();
    const float ReleaseSeconds = CVarCrowdMassReleaseSeconds.GetValueOnGameThread();
    for (int32 Index = Promoted.Num() - 1; Index >= 0; --Index)
    {
        FPromoted& Entry = Promoted[Index];
        AActor* Actor = Entry.Actor.Get();
        if (!Actor)
        {
            Promoted.RemoveAtSwap(Index);
            continue;
        }
        const UReflectionsNpcReactionComponent* Brain = Npcs ? Npcs->FindNpc(Actor) : nullptr;
        // The fallen stay where they fell (the NPC system owns the body).
        if (!Brain || Brain->IsIncapacitated()) continue;
        const bool bCalm = Brain->Reaction == EReflectionsNpcReaction::Calm;
        const bool bFar = !Player || FVector::Dist2D(Player->GetActorLocation(), Actor->GetActorLocation()) > ReleaseDistance;
        Entry.CalmFarSeconds = bCalm && bFar ? Entry.CalmFarSeconds + DeltaTime : 0.0f;
        if (Entry.CalmFarSeconds > ReleaseSeconds)
        {
            Actor->Destroy();
            Promoted.RemoveAtSwap(Index);
        }
    }
}

FString UReflectionsCrowdCitySubsystem::Describe() const
{
    const FMetaHumanCrowdStats Stats = UMetaHumanCrowdStatsLibrary::GatherMetaHumanCrowdStats(const_cast<UReflectionsCrowdCitySubsystem*>(this));
    return FString::Printf(TEXT("City crowd: host %d, loaded %d, entities %d, visible %d, actors %d, instanced %d, disturbances %d, promoted %d (%d active), annotation %d"),
        bHostMap, IsCrowdLoaded(), Stats.NumEntities, Stats.NumVisible, Stats.NumActors, Stats.NumISKMs, DisturbancesSent,
        PromotedTotal, CountActivePromoted(), AnnotationActor != nullptr);
}
