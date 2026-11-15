#include "NPC/ReflectionsNpcSubsystem.h"

#include "NPC/ReflectionsNpcCombatComponent.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsReputationSubsystem.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Worlds/ReflectionsWorldLibrary.h"
#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Components/CapsuleComponent.h"
#include "Engine/DataTable.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/Level.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/DamageType.h"
#include "GameFramework/Pawn.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/PackageName.h"
#include "Sound/SoundBase.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "TimerManager.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsNpc, Log, All);

static TAutoConsoleVariable<int32> CVarNpcHeat(TEXT("Npc.Heat"), 0,
    TEXT("1: the player's crimes against NPCs raise heat, witnesses call out and guards turn on the player. 0 (default until tested): off."));

namespace
{
    const FName TagReactive(TEXT("NPC_Reactive"));
    const FName HitProxyName(TEXT("RuntimeNpcHitProxy"));
    const FName RuntimeHealthName(TEXT("RuntimeNpcHealth"));
    const FName RuntimeBrainName(TEXT("RuntimeNpcReaction"));
    const FName RuntimeCombatName(TEXT("RuntimeNpcCombat"));
    /** Component tag on everything this system adds at runtime, so ReleaseActor can take it back. */
    const FName RuntimeComponentTag(TEXT("NpcRuntime"));
    const TCHAR* TypeTagPrefix = TEXT("NPC_Type_");
    const TCHAR* ArchetypeFolder = TEXT("/Game/NPC/Archetypes");

    /** The usual runtime name, or a fresh one when a released component of that name is still awaiting collection. */
    FName RuntimeName(AActor* Actor, UClass* Class, FName Preferred)
    {
        return StaticFindObjectFast(nullptr, Actor, Preferred) ? MakeUniqueObjectName(Actor, Class, Preferred) : Preferred;
    }

    bool IsPlayer(const AActor* Actor)
    {
        const APawn* Pawn = Cast<APawn>(Actor);
        return Pawn && Pawn->IsPlayerControlled();
    }

    /** Something a spell trace or overlap can already find on this actor. */
    bool HasSpellCollision(const AActor* Actor)
    {
        TInlineComponentArray<UPrimitiveComponent*> Primitives(Actor);
        for (const UPrimitiveComponent* Primitive : Primitives)
            if (Primitive && Primitive->IsQueryCollisionEnabled() && Primitive->GetCollisionObjectType() == ECC_Pawn) return true;
        return false;
    }

    void AddHitProxy(AActor* Actor)
    {
        if (!Actor->GetRootComponent()) return;
        TInlineComponentArray<UCapsuleComponent*> Capsules(Actor);
        for (const UCapsuleComponent* Capsule : Capsules)
            if (Capsule && Capsule->ComponentHasTag(UReflectionsNpcReactionComponent::HitProxyTag)) return;
        // Actor-only MetaHuman assemblies often have no hit collision; add a
        // query proxy without changing their saved skeletons or outfits.
        FVector Center, Extent; Actor->GetActorBounds(false, Center, Extent);
        UCapsuleComponent* Proxy = NewObject<UCapsuleComponent>(Actor, RuntimeName(Actor, UCapsuleComponent::StaticClass(), HitProxyName));
        Proxy->ComponentTags.Add(UReflectionsNpcReactionComponent::HitProxyTag);
        Proxy->ComponentTags.Add(RuntimeComponentTag);
        Proxy->SetupAttachment(Actor->GetRootComponent());
        const float Radius = FMath::Clamp(FMath::Max(Extent.X, Extent.Y) * .55f, 25.0f, 55.0f);
        Proxy->InitCapsuleSize(Radius, FMath::Clamp(Extent.Z, 70.0f, 115.0f));
        Proxy->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        Proxy->SetCollisionObjectType(ECC_Pawn);
        Proxy->SetCollisionResponseToAllChannels(ECR_Ignore);
        Proxy->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
        Proxy->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
        Proxy->RegisterComponent();
        Proxy->SetWorldLocation(Center);
    }
}

UReflectionsNpcSubsystem* UReflectionsNpcSubsystem::Get(const UObject* WorldContext)
{
    const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull) : nullptr;
    return World ? World->GetSubsystem<UReflectionsNpcSubsystem>() : nullptr;
}

bool UReflectionsNpcSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UReflectionsNpcSubsystem::OnWorldBeginPlay(UWorld& World)
{
    Super::OnWorldBeginPlay(World);
    if (UReflectionsSpellEventSubsystem* Events = World.GetSubsystem<UReflectionsSpellEventSubsystem>())
    {
        Events->OnSpellEvent.AddUniqueDynamic(this, &UReflectionsNpcSubsystem::HandleSpellEvent);
        Events->OnSpellHit.AddUniqueDynamic(this, &UReflectionsNpcSubsystem::HandleSpellHit);
    }
    SpawnedHandle = World.AddOnActorSpawnedHandler(FOnActorSpawned::FDelegate::CreateUObject(this, &UReflectionsNpcSubsystem::HandleActorSpawned));
    LevelAddedHandle = FWorldDelegates::LevelAddedToWorld.AddUObject(this, &UReflectionsNpcSubsystem::HandleLevelAdded);

    TArray<AActor*> Tagged;
    for (TActorIterator<AActor> It(&World); It; ++It)
        if (It->ActorHasTag(TagReactive)) Tagged.Add(*It);
    for (AActor* Actor : Tagged) EnrollIfTagged(Actor);
    UE_LOG(LogReflectionsNpc, Log, TEXT("NPC system: enrolled %d tagged actors in %s."), Tagged.Num(), *World.GetName());

}

void UReflectionsNpcSubsystem::Deinitialize()
{
    if (UWorld* World = GetWorld())
    {
        if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
        {
            Events->OnSpellEvent.RemoveDynamic(this, &UReflectionsNpcSubsystem::HandleSpellEvent);
            Events->OnSpellHit.RemoveDynamic(this, &UReflectionsNpcSubsystem::HandleSpellHit);
        }
        World->RemoveOnActorSpawnedHandler(SpawnedHandle);
    }
    FWorldDelegates::LevelAddedToWorld.Remove(LevelAddedHandle);
    Npcs.Empty();
    ActiveStimuli.Empty();
    Super::Deinitialize();
}

// ---- Archetypes --------------------------------------------------------------------------------------------

void UReflectionsNpcSubsystem::LoadArchetypeAssets()
{
    bAssetsLoaded = true;
    IAssetRegistry* Registry = IAssetRegistry::Get();
    if (!Registry) return;
    TArray<FAssetData> Assets;
    Registry->GetAssetsByPath(FName(ArchetypeFolder), Assets, true);
    const FTopLevelAssetPath ClassPath = UReflectionsNpcArchetype::StaticClass()->GetClassPathName();
    for (const FAssetData& Data : Assets)
    {
        if (Data.AssetClassPath != ClassPath) continue;
        UReflectionsNpcArchetype* Asset = Cast<UReflectionsNpcArchetype>(Data.GetAsset());
        if (!Asset) continue;
        const FName Id = Asset->ArchetypeId.IsNone() ? Asset->GetFName() : Asset->ArchetypeId;
        Archetypes.Add(Id, Asset);
        UE_LOG(LogReflectionsNpc, Log, TEXT("NPC archetype '%s' from %s."), *Id.ToString(), *Asset->GetPathName());
    }
}

UReflectionsNpcArchetype* UReflectionsNpcSubsystem::FindArchetype(FName Id)
{
    if (!bAssetsLoaded) LoadArchetypeAssets();
    if (const TObjectPtr<UReflectionsNpcArchetype>* Found = Archetypes.Find(Id)) return Found->Get();
    if (UReflectionsNpcArchetype* BuiltIn = UReflectionsNpcArchetype::MakeBuiltIn(this, Id))
    {
        Archetypes.Add(Id, BuiltIn);
        return BuiltIn;
    }
    return nullptr;
}

UReflectionsNpcArchetype* UReflectionsNpcSubsystem::ResolveArchetype(const AActor* Actor)
{
    if (Actor)
    {
        for (const FName& Tag : Actor->Tags)
        {
            FString Text = Tag.ToString();
            if (Text.RemoveFromStart(TypeTagPrefix))
            {
                if (UReflectionsNpcArchetype* Typed = FindArchetype(FName(*Text))) return Typed;
                UE_LOG(LogReflectionsNpc, Warning, TEXT("%s asks for NPC archetype '%s', which does not exist."), *Actor->GetName(), *Text);
            }
        }
        if (Actor->ActorHasTag(TEXT("NPC_CombatEnemy"))) return FindArchetype(TEXT("Enemy"));
        if (Actor->ActorHasTag(TEXT("NPC_Hostile"))) return FindArchetype(TEXT("Hostile"));
        if (Actor->ActorHasTag(TEXT("NPC_Guard"))) return FindArchetype(TEXT("Guard"));
        if (Actor->ActorHasTag(TEXT("NPC_Brave"))) return FindArchetype(TEXT("Brave"));
        if (Actor->ActorHasTag(TEXT("NPC_Timid"))) return FindArchetype(TEXT("Timid"));
    }
    return FindArchetype(TEXT("Civilian"));
}

// ---- Enrolment ---------------------------------------------------------------------------------------------

void UReflectionsNpcSubsystem::EnrollIfTagged(AActor* Actor)
{
    if (IsValid(Actor) && Actor->ActorHasTag(TagReactive)) EnrollActor(Actor, nullptr);
}

void UReflectionsNpcSubsystem::HandleActorSpawned(AActor* Actor)
{
    // Tags are usually set right after the spawn call returns: look on the next tick.
    UWorld* World = GetWorld();
    if (!World || !Actor) return;
    TWeakObjectPtr<AActor> Weak(Actor);
    World->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateWeakLambda(this, [this, Weak]()
    {
        if (AActor* Spawned = Weak.Get())
            if (!Spawned->FindComponentByClass<UReflectionsNpcReactionComponent>()) EnrollIfTagged(Spawned);
    }));
}

void UReflectionsNpcSubsystem::HandleLevelAdded(ULevel* Level, UWorld* World)
{
    if (!Level || World != GetWorld() || !World->HasBegunPlay()) return;
    const TArray<TObjectPtr<AActor>> Actors = Level->Actors;
    for (AActor* Actor : Actors) EnrollIfTagged(Actor);
}

UReflectionsNpcReactionComponent* UReflectionsNpcSubsystem::EnrollActor(AActor* Actor, UReflectionsNpcArchetype* Archetype)
{
    if (!IsValid(Actor) || Actor->GetWorld() != GetWorld()) return nullptr;
    UReflectionsNpcReactionComponent* Brain = Actor->FindComponentByClass<UReflectionsNpcReactionComponent>();
    UReflectionsNpcArchetype* Wanted = Archetype ? Archetype : (Brain && Brain->Archetype ? Brain->Archetype.Get() : ResolveArchetype(Actor));
    if (!Wanted) return Brain;

    if (!Actor->FindComponentByClass<UReflectionsHealthComponent>())
    {
        UReflectionsHealthComponent* Health = NewObject<UReflectionsHealthComponent>(Actor,
            RuntimeName(Actor, UReflectionsHealthComponent::StaticClass(), RuntimeHealthName));
        Health->ComponentTags.Add(RuntimeComponentTag);
        Health->MaxHealth = Wanted->MaxHealth;
        Health->RegisterComponent();
    }
    for (const FName& Tag : Wanted->GrantedTags) Actor->Tags.AddUnique(Tag);
    if (Actor->ActorHasTag(TEXT("NPC_HitProxy")) || (Wanted->bAddHitProxy && !Actor->IsA<APawn>() && !HasSpellCollision(Actor)))
        AddHitProxy(Actor);

    if (Brain)
    {
        if (Archetype) Brain->SetArchetype(Archetype);
        return Brain;
    }
    Brain = NewObject<UReflectionsNpcReactionComponent>(Actor,
        RuntimeName(Actor, UReflectionsNpcReactionComponent::StaticClass(), RuntimeBrainName));
    Brain->ComponentTags.Add(RuntimeComponentTag);
    Brain->Archetype = Wanted;
    Brain->bEnableRagdollOnDeath = Actor->ActorHasTag(TEXT("NPC_Ragdoll"));
    Brain->bUseSampleLocomotion = Actor->ActorHasTag(TEXT("NPC_SampleLocomotion"));
    Brain->RegisterComponent();

    if (Actor->ActorHasTag(TEXT("NPC_VillainHost"))) SetInfection(Actor, EReflectionsNpcInfection::VillainHost, nullptr);
    else if (Actor->ActorHasTag(TEXT("NPC_Infected"))) SetInfection(Actor, EReflectionsNpcInfection::Infected, nullptr);
    else if (Wanted->bCountsOnInfectionMeter)
    {
        Brain->bOnInfectionMeter = true;
        ReportToInfectionMeter(Actor, true);
    }
    return Brain;
}

void UReflectionsNpcSubsystem::ReleaseActor(AActor* Actor)
{
    if (!IsValid(Actor)) return;
    // The NPC component first: it stands its melee motor and locomotion pawn down as it goes.
    if (UReflectionsNpcReactionComponent* Brain = Actor->FindComponentByClass<UReflectionsNpcReactionComponent>())
        if (Brain->ComponentHasTag(RuntimeComponentTag)) Brain->DestroyComponent();
    TInlineComponentArray<UActorComponent*> Components(Actor);
    for (UActorComponent* Component : Components)
        if (Component && Component->ComponentHasTag(RuntimeComponentTag)) Component->DestroyComponent();
}

void UReflectionsNpcSubsystem::RegisterNpc(UReflectionsNpcReactionComponent* Npc)
{
    if (!Npc) return;
    Npcs.AddUnique(Npc);
    AssignVoice(Npc);
}

// ---- Spawning ----------------------------------------------------------------------------------------------

const TArray<TSoftClassPtr<AActor>>& UReflectionsNpcSubsystem::TeamLooks()
{
    // The finished cast first (the same list the archetypes' pools are cut from), counting the Blueprints that
    // are in the project when this is first asked. With fewer than two of them: the older looks below.
    static const TArray<TSoftClassPtr<AActor>> Finished = []
    {
        static const TCHAR* Cast[] = { TEXT("FrostHyeon"), TEXT("FrostSilas"), TEXT("GiltCoinClerk"), TEXT("GiltArchivist"), TEXT("GiltMaren"),
            TEXT("GiltBarnaby"), TEXT("GiltDrummer"), TEXT("GiltFerryman"), TEXT("GiltPriya"), TEXT("GiltRamon"), TEXT("GiltGlassman"),
            TEXT("GiltHaruto"), TEXT("GiltBridgeGuard"), TEXT("GiltRowena"), TEXT("FrostIven"), TEXT("FrostSaran"), TEXT("FrostNia"),
            TEXT("FrostAmara"), TEXT("FrostTobias"), TEXT("FrostWen") };
        TArray<TSoftClassPtr<AActor>> Found;
        for (const TCHAR* LookId : Cast)
        {
            const FString Package = FString::Printf(TEXT("/Game/Characters/Lanthorne/Looks/BP_Look_%s"), LookId);
            if (FPackageName::DoesPackageExist(Package))
                Found.Add(TSoftClassPtr<AActor>(FSoftObjectPath(FString::Printf(TEXT("%s.BP_Look_%s_C"), *Package, LookId))));
        }
        return Found;
    }();
    if (Finished.Num() >= 2) return Finished;
    static const TArray<TSoftClassPtr<AActor>> Looks = {
        TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/CrowdMotion/SimpleRed/CoinClerk/BP_CoinClerk_SimpleRed.BP_CoinClerk_SimpleRed_C"))),
        TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/CrowdMotion/SimpleRed/ArchiveApprentice/BP_ArchiveApprentice_SimpleRed.BP_ArchiveApprentice_SimpleRed_C"))),
        TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/CrowdMotion/SimpleRed/FestivalDrummer/BP_FestivalDrummer_SimpleRed.BP_FestivalDrummer_SimpleRed_C"))),
        TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/CrowdMotion/SimpleRed/BridgeGuard/BP_BridgeGuard_SimpleRed.BP_BridgeGuard_SimpleRed_C"))),
        TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_01_Plain.BP_WhiteLook_01_Plain_C"))),
        TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_02_Cap.BP_WhiteLook_02_Cap_C"))),
        TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_03_Mantle.BP_WhiteLook_03_Mantle_C"))),
        TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_04_CapMantle.BP_WhiteLook_04_CapMantle_C"))),
        TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_05_GuardRags.BP_WhiteLook_05_GuardRags_C"))),
        TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/Characters/WhiteLondon/CrowdPreview/BP_WhiteLook_06_GuardBoldRunes.BP_WhiteLook_06_GuardBoldRunes_C"))),
    };
    return Looks;
}

namespace
{
    const FName GiltsideName(TEXT("Giltside"));
    const FName FrostsideName(TEXT("Frostside"));
    const FName PewtersideName(TEXT("Pewterside"));

    // The side a look belongs to, read from its Blueprint's path so that nothing has to be loaded: the finished
    // cast is named BP_Look_Gilt..., BP_Look_Frost..., BP_Look_Pewter...; the older sets are SimpleRed (Giltside)
    // and WhiteLook (Frostside). None: a look nobody has placed, which suits any side.
    FName SideOfLook(const TSoftClassPtr<AActor>& Look)
    {
        const FString Path = Look.ToSoftObjectPath().ToString();
        if (Path.Contains(TEXT("Look_Gilt")) || Path.Contains(TEXT("SimpleRed")) || Path.Contains(TEXT("RedLondon"))) return GiltsideName;
        if (Path.Contains(TEXT("Look_Frost")) || Path.Contains(TEXT("WhiteLook")) || Path.Contains(TEXT("WhiteLondon"))) return FrostsideName;
        if (Path.Contains(TEXT("Look_Pewter")) || Path.Contains(TEXT("GrayLondon")) || Path.Contains(TEXT("GreyLondon"))) return PewtersideName;
        return NAME_None;
    }

    // Whose looks an archetype may borrow on its own side when it has none there, nearest role first.
    TArray<FName> LookRoles(FName ArchetypeId)
    {
        static const FName Civilian(TEXT("Civilian")), Guard(TEXT("Guard")), Soldier(TEXT("Soldier")), Caster(TEXT("SoldierCaster")),
            Enemy(TEXT("Enemy")), Hostile(TEXT("Hostile")), Allied(TEXT("AlliedSoldier"));
        if (ArchetypeId == Guard) return { Guard, Allied, Soldier, Enemy, Civilian };
        if (ArchetypeId == Allied) return { Allied, Guard, Soldier, Civilian };
        if (ArchetypeId == Soldier) return { Soldier, Guard, Enemy, Caster, Civilian };
        if (ArchetypeId == Caster) return { Caster, Soldier, Guard, Civilian };
        if (ArchetypeId == Enemy || ArchetypeId == Hostile) return { ArchetypeId, Soldier, Guard, Civilian };
        return { ArchetypeId, Civilian };
    }
}

FName UReflectionsNpcSubsystem::GetSideAt(FVector Location) const
{
    switch (UReflectionsWorldLibrary::GetWorldAtLocation(this, Location))
    {
    case EReflectionsWorld::Red: return GiltsideName;
    case EReflectionsWorld::White: return FrostsideName;
    default: return PewtersideName;
    }
}

TArray<TSoftClassPtr<AActor>> UReflectionsNpcSubsystem::GetLooksAt(FName ArchetypeId, FVector Location)
{
    return GetLooksForSide(ArchetypeId, GetSideAt(Location));
}

TArray<TSoftClassPtr<AActor>> UReflectionsNpcSubsystem::GetLooksForSide(FName ArchetypeId, FName Side)
{
    TArray<TSoftClassPtr<AActor>> Found;
    const auto Collect = [&Found, Side](const TArray<TSoftClassPtr<AActor>>& Looks)
    {
        for (const TSoftClassPtr<AActor>& Look : Looks)
        {
            const FName LookSide = SideOfLook(Look);
            if (!Look.IsNull() && (LookSide.IsNone() || LookSide == Side)) Found.AddUnique(Look);
        }
    };
    // Its own role on this side, else this side's nearest role: a side's guards may wear its soldiers' looks,
    // never the other side's guards'.
    for (const FName Role : LookRoles(ArchetypeId))
    {
        if (const UReflectionsNpcArchetype* Archetype = FindArchetype(Role)) Collect(Archetype->Looks);
        if (Found.Num() > 0) return Found;
    }
    Collect(TeamLooks());
    if (Found.Num() > 0) return Found;
    // Nobody at all lives on this side yet. Pewterside borrows Giltside's people until it has its own.
    if (Side == PewtersideName)
    {
        static bool bLogged = false;
        if (!bLogged)
        {
            bLogged = true;
            UE_LOG(LogReflectionsNpc, Display, TEXT("NPC looks: Pewterside has no looks of its own yet; its NPCs wear Giltside's."));
        }
        return GetLooksForSide(ArchetypeId, GiltsideName);
    }
    UE_LOG(LogReflectionsNpc, Warning, TEXT("NPC looks: no look of side %s for archetype %s."), *Side.ToString(), *ArchetypeId.ToString());
    return Found;
}

int32 UReflectionsNpcSubsystem::GetLookUseCount(TSoftClassPtr<AActor> Look) const
{
    const FSoftObjectPath Wanted = Look.ToSoftObjectPath();
    if (Wanted.IsNull()) return 0;
    int32 Count = 0;
    for (const TWeakObjectPtr<UReflectionsNpcReactionComponent>& Weak : Npcs)
    {
        const UReflectionsNpcReactionComponent* Npc = Weak.Get();
        const AActor* Owner = Npc ? Npc->GetOwner() : nullptr;
        if (Owner && !Npc->IsIncapacitated() && FSoftObjectPath(Owner->GetClass()) == Wanted) ++Count;
    }
    return Count;
}

AActor* UReflectionsNpcSubsystem::SpawnNpc(FName ArchetypeId, FVector Location, float FacingYaw, TSubclassOf<AActor> Look)
{
    UWorld* World = GetWorld();
    UReflectionsNpcArchetype* Archetype = FindArchetype(ArchetypeId);
    if (!World || !Archetype)
    {
        UE_LOG(LogReflectionsNpc, Warning, TEXT("SpawnNpc: there is no NPC archetype '%s'."), *ArchetypeId.ToString());
        return nullptr;
    }
    UClass* LookClass = Look.Get();
    // Only the people of the side this place is in (rags stay in Frostside, red in Giltside); the archetype's
    // whole list only if the side-aware pick comes back empty.
    TArray<TSoftClassPtr<AActor>> Choices = GetLooksAt(ArchetypeId, Location);
    if (Choices.Num() == 0) Choices = Archetype->Looks.Num() > 0 ? Archetype->Looks : TeamLooks();
    // The look the fewest living NPCs wear comes first; the running counter says where the search starts, so an
    // empty street still gets a mix and equally worn looks take turns.
    int32 First = 0;
    if (Choices.Num() > 1)
    {
        const int32 Start = (NextLookIndex++ & MAX_int32) % Choices.Num();
        int32 Fewest = MAX_int32;
        for (int32 Offset = 0; Offset < Choices.Num(); ++Offset)
        {
            const int32 Index = (Start + Offset) % Choices.Num();
            const int32 Worn = GetLookUseCount(Choices[Index]);
            if (Worn < Fewest)
            {
                Fewest = Worn;
                First = Index;
            }
        }
    }
    for (int32 Try = 0; !LookClass && Try < Choices.Num(); ++Try)
        LookClass = Choices[(First + Try) % Choices.Num()].LoadSynchronous();
    if (!LookClass)
    {
        UE_LOG(LogReflectionsNpc, Warning, TEXT("SpawnNpc: no team look could be loaded for '%s'."), *ArchetypeId.ToString());
        return nullptr;
    }
    // These looks face along their own +Y: the NPC component turns them the same way when it adds the walker.
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AActor* Npc = World->SpawnActor<AActor>(LookClass, FTransform(FRotator(0.0, FacingYaw - 90.0, 0.0), Location), Params);
    if (!Npc) return nullptr;
    Npc->Tags.AddUnique(FName(TEXT("NPC_HitProxy")));
    Npc->Tags.AddUnique(FName(TEXT("NPC_SampleLocomotion")));
    EnrollActor(Npc, Archetype);
    return Npc;
}

// ---- Voice -------------------------------------------------------------------------------------------------

EReflectionsNpcSex UReflectionsNpcSubsystem::GetLookSex(const AActor* Actor)
{
    if (!Actor) return EReflectionsNpcSex::Unknown;
    if (Actor->ActorHasTag(TEXT("NPC_Voice_F"))) return EReflectionsNpcSex::Female;
    if (Actor->ActorHasTag(TEXT("NPC_Voice_M"))) return EReflectionsNpcSex::Male;
    // The team looks, by a piece of the Blueprint's class name, then by the MetaHuman body the look wears (so a
    // new outfit on a known body is classified too). More specific pieces first. White looks 05 and 06 wear the
    // Bridge Guard's body; 01 to 04 wear Iven Rook's.
    static const TArray<TPair<FString, EReflectionsNpcSex>> Table = {
        { TEXT("WhiteLook_05"), EReflectionsNpcSex::Female }, { TEXT("WhiteLook_06"), EReflectionsNpcSex::Female },
        { TEXT("WhiteLook_"), EReflectionsNpcSex::Male },
        { TEXT("BridgeGuard"), EReflectionsNpcSex::Female }, { TEXT("CoinClerk"), EReflectionsNpcSex::Female },
        { TEXT("FestivalDrummer"), EReflectionsNpcSex::Female }, { TEXT("ArchiveApprentice"), EReflectionsNpcSex::Male },
        { TEXT("IvenRook"), EReflectionsNpcSex::Male }, { TEXT("MHC_Hero"), EReflectionsNpcSex::Male },
    };
    const FString ClassName = Actor->GetClass()->GetName();
    for (const TPair<FString, EReflectionsNpcSex>& Row : Table)
        if (ClassName.Contains(Row.Key)) return Row.Value;
    TInlineComponentArray<USkeletalMeshComponent*> Meshes(Actor);
    for (const USkeletalMeshComponent* Mesh : Meshes)
        if (Mesh && Mesh->GetFName() == TEXT("Body") && Mesh->GetSkeletalMeshAsset())
        {
            const FString MeshName = Mesh->GetSkeletalMeshAsset()->GetName();
            for (const TPair<FString, EReflectionsNpcSex>& Row : Table)
                if (MeshName.Contains(Row.Key)) return Row.Value;
        }
    return EReflectionsNpcSex::Unknown;
}

void UReflectionsNpcSubsystem::AssignVoice(UReflectionsNpcReactionComponent* Npc)
{
    AActor* Owner = Npc ? Npc->GetOwner() : nullptr;
    if (!Owner || Npc->VoiceSlotIndex != INDEX_NONE) return;
    Npc->VoiceSex = GetLookSex(Owner);
    // A look nobody has classified still gets a voice that never changes: its name decides.
    const uint32 Seed = GetTypeHash(Owner->GetFName());
    if (Npc->VoiceSex == EReflectionsNpcSex::Unknown)
        Npc->VoiceSex = (Seed >> 3) % 2 == 0 ? EReflectionsNpcSex::Female : EReflectionsNpcSex::Male;
    // Three voices per sex: take the least used among the NPCs of that sex already here, the name breaks ties.
    int32 Used[3] = { 0, 0, 0 };
    for (const TWeakObjectPtr<UReflectionsNpcReactionComponent>& Weak : Npcs)
        if (const UReflectionsNpcReactionComponent* Other = Weak.Get())
            if (Other != Npc && Other->VoiceSex == Npc->VoiceSex && Other->VoiceSlotIndex >= 0 && Other->VoiceSlotIndex < 3) ++Used[Other->VoiceSlotIndex];
    int32 Best = Seed % 3;
    for (int32 Offset = 1; Offset < 3; ++Offset)
    {
        const int32 Slot = (Seed + Offset) % 3;
        if (Used[Slot] < Used[Best]) Best = Slot;
    }
    Npc->VoiceSlotIndex = Best;
    Npc->VoiceSlot = FName(*FString::Printf(TEXT("%s%d"), Npc->VoiceSex == EReflectionsNpcSex::Male ? TEXT("M") : TEXT("F"), Best + 1));

    // Audio's roster of many voices, when the project has it: one voice id per NPC, always of its sex.
    // Different voices come first: a voice nobody here has yet beats any voice already heard. Among equally
    // used voices its kind of character counts most, then the NPC's home side; the actor's name breaks ties.
    // Without the table the slot above is the whole voice.
    LoadVoiceRoster();
    if (!VoiceRoster) return;
    const UReflectionsNpcArchetype* Kind = Npc->Archetype ? Npc->Archetype.Get() : ResolveArchetype(Owner);
    const FName Character = Kind ? Kind->VoiceCharacter : NAME_None;
    EReflectionsWorld Home = EReflectionsWorld::Gray;
    switch (Kind ? Kind->HomeWorld : EReflectionsNpcHomeWorld::FromSpawnLocation)
    {
    case EReflectionsNpcHomeWorld::Gray: Home = EReflectionsWorld::Gray; break;
    case EReflectionsNpcHomeWorld::Red: Home = EReflectionsWorld::Red; break;
    case EReflectionsNpcHomeWorld::White: Home = EReflectionsWorld::White; break;
    default: Home = UReflectionsWorldLibrary::GetWorldAtLocation(this, Owner->GetActorLocation()); break;
    }
    // A finished look says where its person is from and how old they are (the crowd-looks session's tags on
    // the look Blueprint); that beats where the NPC happens to stand.
    if (Owner->ActorHasTag(TEXT("Look_Side_Pewterside"))) Home = EReflectionsWorld::Gray;
    else if (Owner->ActorHasTag(TEXT("Look_Side_Giltside"))) Home = EReflectionsWorld::Red;
    else if (Owner->ActorHasTag(TEXT("Look_Side_Frostside"))) Home = EReflectionsWorld::White;
    const int32 LookAge = Owner->ActorHasTag(TEXT("Look_Age_Young")) ? 1 : Owner->ActorHasTag(TEXT("Look_Age_Adult")) ? 2
        : Owner->ActorHasTag(TEXT("Look_Age_Old")) ? 3 : 0;
    // The table may name a side either way: as the player knows it or as the code does.
    const FName SideName = Home == EReflectionsWorld::Gray ? TEXT("Pewterside") : Home == EReflectionsWorld::Red ? TEXT("Giltside") : TEXT("Frostside");
    const FName SideCode = Home == EReflectionsWorld::Gray ? TEXT("Gray") : Home == EReflectionsWorld::Red ? TEXT("Red") : TEXT("White");
    struct FChoice
    {
        FName Id;
        const FReflectionsNpcVoiceRow* Voice = nullptr;
    };
    TArray<FChoice> Choices;
    for (const TPair<FName, uint8*>& Row : VoiceRoster->GetRowMap())
    {
        const FReflectionsNpcVoiceRow* Voice = reinterpret_cast<const FReflectionsNpcVoiceRow*>(Row.Value);
        if (Voice && Voice->bEnabled && (Voice->Sex == EReflectionsNpcSex::Unknown || Voice->Sex == Npc->VoiceSex)) Choices.Add({ Row.Key, Voice });
    }
    if (Choices.Num() == 0) return;
    TMap<FName, int32> Heard;
    for (const TWeakObjectPtr<UReflectionsNpcReactionComponent>& Weak : Npcs)
        if (const UReflectionsNpcReactionComponent* Other = Weak.Get())
            if (Other != Npc && !Other->VoiceId.IsNone()) ++Heard.FindOrAdd(Other->VoiceId);
    // Strictly narrowing to the side first gave every unnamed woman of one side the same voice where the roster
    // had a single voice left for it (train #7), so a mismatch only costs: a repeat 100 each time the voice is
    // already heard, the wrong kind of character 150, the wrong side 3, the wrong age for the face 2 (young
    // under 30, old from 50, where both the look and the voice say). Character outweighs side because audio
    // records a voice's lines only for its own kind: a soldier given a shopkeeper's voice (train #8, the one
    // free voice of its side) would bark in one voice and answer the player in another. The scan starts at a
    // place the actor's name decides, which is what breaks ties.
    const uint32 Count = static_cast<uint32>(Choices.Num());
    int32 Pick = static_cast<int32>(Seed % Count);
    int32 PickCost = MAX_int32;
    for (uint32 Offset = 0; Offset < Count; ++Offset)
    {
        const int32 Index = static_cast<int32>((Seed + Offset) % Count);
        const FReflectionsNpcVoiceRow& Voice = *Choices[Index].Voice;
        const bool bSide = Voice.Side.IsNone() || Voice.Side == SideName || Voice.Side == SideCode;
        const bool bCharacter = Character.IsNone() || Voice.Characters.Num() == 0 || Voice.Characters.Contains(Character);
        const int32 VoiceAge = Voice.Age <= 0 ? 0 : Voice.Age < 30 ? 1 : Voice.Age < 50 ? 2 : 3;
        const bool bAge = LookAge == 0 || VoiceAge == 0 || LookAge == VoiceAge;
        // Wrong character costs more than one repeat: a third guard shares another guard's voice (and its own
        // recorded barks) rather than taking a civilian's, which would bark in the generic slot voice. Audio asked
        // for this; a second repeat still loses to a fresh voice.
        const int32 Cost = Heard.FindRef(Choices[Index].Id) * 100 + (bCharacter ? 0 : 150) + (bSide ? 0 : 3) + (bAge ? 0 : 2);
        if (Cost < PickCost)
        {
            Pick = Index;
            PickCost = Cost;
        }
    }
    Npc->VoiceId = Choices[Pick].Id;
    Npc->GeminiVoice = Choices[Pick].Voice->GeminiVoice;
}

void UReflectionsNpcSubsystem::LoadVoiceRoster()
{
    if (bRosterLoaded) return;
    bRosterLoaded = true;
    // Audio owns the table; it is only read. Absent, or built on another row type: the three slots per sex stay.
    static const TCHAR* Package = TEXT("/Game/Audio/Jam/Voice/DT_NpcVoiceRoster");
    if (!FPackageName::DoesPackageExist(Package)) return;
    UDataTable* Table = LoadObject<UDataTable>(nullptr, TEXT("/Game/Audio/Jam/Voice/DT_NpcVoiceRoster.DT_NpcVoiceRoster"));
    if (Table && Table->GetRowStruct() && Table->GetRowStruct()->IsChildOf(FReflectionsNpcVoiceRow::StaticStruct()))
    {
        VoiceRoster = Table;
        UE_LOG(LogReflectionsNpc, Log, TEXT("NPC voices: %d roster rows from %s."), Table->GetRowMap().Num(), Package);
    }
    else if (Table)
        UE_LOG(LogReflectionsNpc, Warning, TEXT("NPC voices: %s is not a table of FReflectionsNpcVoiceRow rows; it is ignored."), Package);
}

FReflectionsNpcVoiceProfile UReflectionsNpcSubsystem::GetVoiceProfile(const AActor* Actor) const
{
    FReflectionsNpcVoiceProfile Profile;
    const UReflectionsNpcReactionComponent* Npc = FindNpc(Actor);
    if (!Npc)
    {
        Profile.Sex = GetLookSex(Actor);
        return Profile;
    }
    const UReflectionsNpcArchetype* Archetype = Npc->GetActiveArchetype();
    Profile.Sex = Npc->VoiceSex;
    Profile.Slot = FMath::Clamp(Npc->VoiceSlotIndex, 0, 2);
    Profile.Character = Archetype ? Archetype->VoiceCharacter : NAME_None;
    Profile.ArchetypeId = Archetype ? Archetype->ArchetypeId : NAME_None;
    Profile.CueSuffix = FString::Printf(TEXT("%s%d"), Profile.Sex == EReflectionsNpcSex::Male ? TEXT("M") : TEXT("F"), Profile.Slot + 1);
    Profile.VoiceId = Npc->VoiceId;
    Profile.GeminiVoice = Npc->GeminiVoice;
    return Profile;
}

USoundBase* UReflectionsNpcSubsystem::FindBarkCue(const FString& Name)
{
    if (const TObjectPtr<USoundBase>* Known = BarkCues.Find(Name)) return Known->Get();
    // Audio owns these cues; they are only referenced. A cue that is not there yet is simply not played.
    // A bare name is a voice cue; a name with a folder (Cues/SCue_Infected_Growl) is relative to /Game/Audio/Jam.
    const FString Package = Name.Contains(TEXT("/")) ? FString::Printf(TEXT("/Game/Audio/Jam/%s"), *Name)
        : FString::Printf(TEXT("/Game/Audio/Jam/Voice/Cues/%s"), *Name);
    USoundBase* Cue = FPackageName::DoesPackageExist(Package)
        ? LoadObject<USoundBase>(nullptr, *FString::Printf(TEXT("%s.%s"), *Package, *FPackageName::GetShortName(Package))) : nullptr;
    BarkCues.Add(Name, Cue);
    return Cue;
}

bool UReflectionsNpcSubsystem::FindVoiceRow(FName VoiceId, FReflectionsNpcVoiceRow& OutRow)
{
    LoadVoiceRoster();
    const FReflectionsNpcVoiceRow* Row = VoiceRoster && !VoiceId.IsNone() ? VoiceRoster->FindRow<FReflectionsNpcVoiceRow>(VoiceId, TEXT("NPC voice"), false) : nullptr;
    if (!Row) return false;
    OutRow = *Row;
    return true;
}

USoundBase* UReflectionsNpcSubsystem::FindVoiceCue(const AActor* Actor, FName Group)
{
    if (Group.IsNone()) return nullptr;
    const FReflectionsNpcVoiceProfile Profile = GetVoiceProfile(Actor);
    const FString Name = Group.ToString();
    USoundBase* Cue = nullptr;
    // Most personal first: the roster voice's own take (audio keeps those in a folder per group), then the
    // nearest of the six slot voices, then the line everybody shares.
    if (!Profile.VoiceId.IsNone()) Cue = FindBarkCue(FString::Printf(TEXT("Voice/Cues/%s/SCue_VO_%s_%s"), *Name, *Name, *Profile.VoiceId.ToString()));
    if (!Cue && !Profile.CueSuffix.IsEmpty()) Cue = FindBarkCue(FString::Printf(TEXT("SCue_VO_%s_%s"), *Name, *Profile.CueSuffix));
    if (!Cue) Cue = FindBarkCue(FString::Printf(TEXT("SCue_VO_%s"), *Name));
    return Cue;
}

void UReflectionsNpcSubsystem::PlayBark(AActor* Actor, FName Group)
{
    UReflectionsNpcReactionComponent* Npc = FindNpc(Actor);
    AActor* Owner = Npc ? Npc->GetOwner() : nullptr;
    const UWorld* World = GetWorld();
    if (!Owner || !World || Group.IsNone() || !Owner->GetRootComponent() || World->GetTimeSeconds() < Npc->NextBarkTime) return;
    // The tarnished do not always talk: about two times in five they only growl (audio asked for the mix).
    USoundBase* Cue = Group == TEXT("Tarnished_Mutter") && FMath::FRand() < 0.4f ? FindBarkCue(TEXT("Cues/SCue_Infected_Growl")) : nullptr;
    if (!Cue) Cue = FindVoiceCue(Owner, Group);
    if (!Cue) return;
    Npc->NextBarkTime = World->GetTimeSeconds() + 4.0f;
    PlayCueFromHead(Npc, Cue);
}

void UReflectionsNpcSubsystem::PlayCueFromHead(UReflectionsNpcReactionComponent* Npc, USoundBase* Cue)
{
    AActor* Owner = Npc ? Npc->GetOwner() : nullptr;
    if (!Owner || !Cue || !Owner->GetRootComponent()) return;
    // Speech comes from the speaker's head (audio's cues are spatialised); the root, raised to head height, when
    // the body has no readable head bone.
    USkeletalMeshComponent* Body = Npc->GetBodyMesh();
    const bool bHead = Body && Body->IsRegistered() && Body->GetBoneIndex(TEXT("head")) != INDEX_NONE &&
        (Body->LeaderPoseComponent.IsValid() || Body->GetNumComponentSpaceTransforms() > Body->GetBoneIndex(TEXT("head")));
    if (bHead) UGameplayStatics::SpawnSoundAttached(Cue, Body, TEXT("head"), FVector::ZeroVector, EAttachLocation::SnapToTarget, true);
    else UGameplayStatics::SpawnSoundAttached(Cue, Owner->GetRootComponent(), NAME_None, FVector(0.0, 0.0, 160.0), EAttachLocation::KeepRelativeOffset, true);
}

bool UReflectionsNpcSubsystem::TryPlayRemark(UReflectionsNpcReactionComponent* Npc)
{
    AActor* Owner = Npc ? Npc->GetOwner() : nullptr;
    const UWorld* World = GetWorld();
    if (!Owner || !World) return false;
    const float Now = World->GetTimeSeconds();
    // One remark at a time across the map, and never on top of the NPC's own bark.
    if (Now < RemarkBusyUntil || Now < Npc->NextBarkTime) return false;
    USoundBase* Cue = FindVoiceCue(Owner, TEXT("Remark"));
    if (!Cue) return false;
    // The line's own length, with a breath after it (a cue that reports no length counts as three seconds).
    const float Length = Cue->GetDuration();
    RemarkBusyUntil = Now + (Length > 0.2f && Length < 15.0f ? Length : 3.0f) + 1.0f;
    Npc->NextBarkTime = Now + 4.0f;
    PlayCueFromHead(Npc, Cue);
    return true;
}

void UReflectionsNpcSubsystem::UnregisterNpc(UReflectionsNpcReactionComponent* Npc)
{
    Npcs.Remove(Npc);
}

UReflectionsNpcReactionComponent* UReflectionsNpcSubsystem::FindNpc(const AActor* Actor) const
{
    if (!IsValid(Actor)) return nullptr;
    if (UReflectionsNpcReactionComponent* Direct = Actor->FindComponentByClass<UReflectionsNpcReactionComponent>()) return Direct;
    if (!Actor->IsA<ACharacter>()) return nullptr;
    for (const TWeakObjectPtr<UReflectionsNpcReactionComponent>& Weak : Npcs)
        if (UReflectionsNpcReactionComponent* Npc = Weak.Get())
            if (Npc->GetLocomotionDriver() == Actor) return Npc;
    return nullptr;
}

TArray<AActor*> UReflectionsNpcSubsystem::GetNpcActors() const
{
    TArray<AActor*> Actors;
    for (const TWeakObjectPtr<UReflectionsNpcReactionComponent>& Weak : Npcs)
        if (const UReflectionsNpcReactionComponent* Npc = Weak.Get())
            if (AActor* Owner = Npc->GetOwner()) Actors.Add(Owner);
    return Actors;
}

// ---- Allegiance --------------------------------------------------------------------------------------------

bool UReflectionsNpcSubsystem::IsHostileToPlayer(const AActor* Actor) const
{
    const UReflectionsNpcReactionComponent* Npc = FindNpc(Actor);
    if (!Npc || Npc->IsIncapacitated()) return false;
    if (UReflectionsNpcArchetype::IsHostileDisposition(Npc->Disposition)) return true;
    return Npc->Reaction == EReflectionsNpcReaction::Attacking && IsPlayer(Npc->GetFocusActor());
}

bool UReflectionsNpcSubsystem::IsAllyOf(const AActor* Target, const AActor* Caster) const
{
    if (!IsValid(Target) || !IsValid(Caster)) return false;
    if (Target == Caster) return true;
    const bool bCasterWithPlayer = IsPlayer(Caster) || (FindNpc(Caster) && !IsHostileToPlayer(Caster));
    if (IsPlayer(Target)) return bCasterWithPlayer;
    if (FindNpc(Target)) return bCasterWithPlayer != IsHostileToPlayer(Target);
    // Not an NPC of this system (a prop, a summoned helper): the Friendly tag is all there is to go on.
    return bCasterWithPlayer && Target->ActorHasTag(TEXT("Friendly"));
}

bool UReflectionsNpcSubsystem::CanBeHarmedBy(const AActor* Target, const AActor* Caster) const
{
    if (!IsValid(Target) || Target == Caster) return false;
    return IsPlayer(Caster) || !IsAllyOf(Target, Caster);
}

// ---- Events in ---------------------------------------------------------------------------------------------

float UReflectionsNpcSubsystem::GetReputation(AActor* Instigator) const
{
    const UWorld* World = GetWorld();
    const UReflectionsReputationSubsystem* Reputation = World ? World->GetSubsystem<UReflectionsReputationSubsystem>() : nullptr;
    return Reputation && IsValid(Instigator) ? Reputation->GetReputation(Instigator) : 0.0f;
}

void UReflectionsNpcSubsystem::PruneStimuli()
{
    const UWorld* World = GetWorld();
    const double Now = World ? World->GetTimeSeconds() : 0.0;
    ActiveStimuli.RemoveAll([Now](const FReflectionsNpcStimulus& Old) { return Now - Old.WorldTime > StimulusMemorySeconds; });
}

const TArray<FReflectionsNpcStimulus>& UReflectionsNpcSubsystem::GetActiveStimuli()
{
    PruneStimuli();
    return ActiveStimuli;
}

void UReflectionsNpcSubsystem::ReportStimulus(const FReflectionsNpcStimulus& Stimulus)
{
    const UWorld* World = GetWorld();
    if (!World) return;
    FReflectionsNpcStimulus Stamped = Stimulus;
    Stamped.Intensity = FMath::Max(0.0f, Stamped.Intensity);
    Stamped.WorldTime = World->GetTimeSeconds();
    PruneStimuli();
    ActiveStimuli.Add(Stamped);
    StimulusEvent.Broadcast(Stamped);

    const float Reputation = GetReputation(Stamped.Instigator.Get());
    // A reaction can enrol or remove NPCs: walk a copy.
    const TArray<TWeakObjectPtr<UReflectionsNpcReactionComponent>> Listeners = Npcs;
    for (const TWeakObjectPtr<UReflectionsNpcReactionComponent>& Weak : Listeners)
        if (UReflectionsNpcReactionComponent* Npc = Weak.Get()) Npc->ReceiveStimulus(Stamped, Reputation);
}

void UReflectionsNpcSubsystem::HandleSpellEvent(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity)
{
    FReflectionsNpcStimulus Stimulus;
    Stimulus.Kind = EReflectionsNpcStimulusKind::SpellNoise;
    Stimulus.Location = Location;
    Stimulus.Intensity = Intensity;
    Stimulus.Instigator = Caster;
    Stimulus.Spell = Spell;
    ReportStimulus(Stimulus);
}

void UReflectionsNpcSubsystem::HandleSpellHit(const FReflectionsSpellHitData& Hit)
{
    ReportSpellHit(Hit);
}

void UReflectionsNpcSubsystem::ReportSpellHit(const FReflectionsSpellHitData& Hit)
{
    UReflectionsNpcReactionComponent* Npc = FindNpc(Hit.Target);
    if (!Npc) return;
    const UReflectionsNpcArchetype* Archetype = Npc->GetActiveArchetype();
    const bool bWasDown = Npc->IsIncapacitated();
    Npc->ReceiveSpellHit(Hit);
    // The killing hit still counts against the caster; kicking a body that was already down does not.
    const bool bCounts = !bWasDown || Npc->ConsumeFreshDeath();
    if (bCounts && Archetype && IsPlayer(Hit.Caster) && !FMath::IsNearlyZero(Archetype->ReputationOnPlayerHit))
        if (UReflectionsReputationSubsystem* Reputation = GetWorld()->GetSubsystem<UReflectionsReputationSubsystem>())
            Reputation->AdjustReputation(Hit.Caster, Archetype->ReputationOnPlayerHit);
    // Hurting someone who was not already against the player is a crime (the kill itself is reported from
    // NotifyDied). One report per victim every few seconds: a spell that keeps burning is one assault.
    if (bCounts && Archetype && IsPlayer(Hit.Caster) && !Hit.bRepeat && !Npc->IsIncapacitated() &&
        !UReflectionsNpcArchetype::IsHostileDisposition(Archetype->Disposition))
    {
        const float Now = GetWorld()->GetTimeSeconds();
        if (Now - Npc->LastAssaultTime > 3.0f)
        {
            Npc->LastAssaultTime = Now;
            ReportPlayerCrime(Npc->GetOwner(), TEXT("Assault"), Hit.Location);
        }
    }
    OnNpcSpellHit.Broadcast(Npc->GetOwner(), Hit);
}

float UReflectionsNpcSubsystem::GetPlayerHeat() const
{
    const UWorld* World = GetWorld();
    if (!World || PlayerHeat <= 0.0f) return 0.0f;
    // Cools at a steady rate once nobody who is after the player has seen them for a while: one to zero in 25 s.
    return FMath::Clamp(PlayerHeat - 0.04f * FMath::Max(0.0f, World->GetTimeSeconds() - HeatCoolsFrom), 0.0f, 1.0f);
}

void UReflectionsNpcSubsystem::NoteHeatSeen()
{
    const UWorld* World = GetWorld();
    if (!World) return;
    // Keep what has not cooled yet, and start the clock again from a few seconds on.
    PlayerHeat = GetPlayerHeat();
    HeatCoolsFrom = World->GetTimeSeconds() + 6.0f;
}

void UReflectionsNpcSubsystem::ClearPlayerHeat()
{
    PlayerHeat = 0.0f;
    HeatCoolsFrom = 0.0f;
    for (const TWeakObjectPtr<UReflectionsNpcReactionComponent>& Weak : Npcs)
        if (UReflectionsNpcReactionComponent* Npc = Weak.Get()) Npc->ForgivePlayer();
    UE_LOG(LogReflectionsNpc, Log, TEXT("Heat cleared: the player's record is wiped."));
}

void UReflectionsNpcSubsystem::ReportPlayerCrime(AActor* Victim, FName Crime, FVector Location)
{
    UWorld* World = GetWorld();
    if (!World || Crime.IsNone() || CVarNpcHeat.GetValueOnGameThread() == 0) return;
    // Who saw it: the living NPCs within their own awareness of the place, with nothing solid in between. A
    // victim who is still standing has seen it too.
    TArray<AActor*> Witnesses;
    for (const TWeakObjectPtr<UReflectionsNpcReactionComponent>& Weak : Npcs)
    {
        const UReflectionsNpcReactionComponent* Npc = Weak.Get();
        AActor* Owner = Npc ? Npc->GetOwner() : nullptr;
        const UReflectionsNpcArchetype* Archetype = Npc ? Npc->GetActiveArchetype() : nullptr;
        if (!Owner || !Archetype || Npc->IsIncapacitated() || Npc->IsScripted()) continue;
        // Those already against the player are no witnesses: nobody hears it from them.
        if (UReflectionsNpcArchetype::IsHostileDisposition(Npc->Disposition)) continue;
        if (Owner != Victim)
        {
            if (FVector::DistSquared(Owner->GetActorLocation(), Location) > FMath::Square(Archetype->Reaction.AwarenessRadius)) continue;
            FCollisionQueryParams Params(SCENE_QUERY_STAT(NpcWitness), false, Owner);
            if (Victim) Params.AddIgnoredActor(Victim);
            FHitResult Blocked;
            if (World->LineTraceSingleByObjectType(Blocked, Owner->GetActorLocation() + FVector(0.0, 0.0, 150.0), Location + FVector(0.0, 0.0, 80.0),
                    FCollisionObjectQueryParams(ECC_WorldStatic), Params)) continue;
        }
        Witnesses.Add(Owner);
    }
    if (Witnesses.Num() > 0)
    {
        static const FName Murder(TEXT("Murder")), Assault(TEXT("Assault"));
        PlayerHeat = FMath::Min(1.0f, GetPlayerHeat() + (Crime == Murder ? 0.6f : Crime == Assault ? 0.34f : 0.25f));
        HeatCoolsFrom = World->GetTimeSeconds() + 8.0f;
    }
    const float Heat = GetPlayerHeat();
    UE_LOG(LogReflectionsNpc, Log, TEXT("Crime: %s on %s, %d witness(es), heat %.2f."), *Crime.ToString(), *GetNameSafe(Victim), Witnesses.Num(), Heat);
    if (Witnesses.Num() == 0)
    {
        OnPlayerCrime.Broadcast(Victim, Crime, nullptr, Location, Heat);
        return;
    }
    // One of the townspeople who saw it shouts for the guards.
    for (AActor* Witness : Witnesses)
    {
        const UReflectionsNpcReactionComponent* Npc = Witness != Victim ? FindNpc(Witness) : nullptr;
        const UReflectionsNpcArchetype* Archetype = Npc ? Npc->GetActiveArchetype() : nullptr;
        if (Archetype && Archetype->VoiceCharacter == TEXT("Civilian"))
        {
            PlayReaction(Witness, TEXT("Heat_CallGuards"));
            break;
        }
    }
    for (AActor* Witness : Witnesses) OnPlayerCrime.Broadcast(Victim, Crime, Witness, Location, Heat);
}

void UReflectionsNpcSubsystem::PlayReaction(AActor* Actor, FName Group)
{
    UReflectionsNpcReactionComponent* Npc = FindNpc(Actor);
    const UWorld* World = GetWorld();
    if (!Npc || !World || Group.IsNone()) return;
    USoundBase* Cue = FindVoiceCue(Npc->GetOwner(), Group);
    if (!Cue) return;
    // It has just spoken: an ordinary bark waits a moment, a second reaction does not.
    Npc->NextBarkTime = World->GetTimeSeconds() + 2.0f;
    PlayCueFromHead(Npc, Cue);
}

void UReflectionsNpcSubsystem::ReportAnonymousDeath(FVector Location, FName ArchetypeId, AActor* Killer)
{
    UReflectionsNpcArchetype* Archetype = FindArchetype(ArchetypeId);
    if (!Archetype) Archetype = FindArchetype(TEXT("Civilian"));
    if (Archetype)
    {
        if (IsPlayer(Killer) && !FMath::IsNearlyZero(Archetype->ReputationOnPlayerKill))
            if (UReflectionsReputationSubsystem* Reputation = GetWorld()->GetSubsystem<UReflectionsReputationSubsystem>())
                Reputation->AdjustReputation(Killer, Archetype->ReputationOnPlayerKill);
        RewardCoin(*Archetype, Location, Location, nullptr);
    }
    FReflectionsNpcStimulus Stimulus;
    Stimulus.Kind = EReflectionsNpcStimulusKind::Death;
    Stimulus.Location = Location;
    Stimulus.Instigator = Killer;
    ReportStimulus(Stimulus);
}

// ---- Consequences ------------------------------------------------------------------------------------------

void UReflectionsNpcSubsystem::NotifyReaction(UReflectionsNpcReactionComponent* Npc, EReflectionsNpcReaction Reaction, AActor* Cause, const FVector& Location)
{
    if (!Npc) return;
    if (const UReflectionsNpcArchetype* Archetype = Npc->GetActiveArchetype())
    {
        // What it says as it starts to run, looks up or goes to look, and turns to fight.
        FName Group = NAME_None;
        if (Reaction == EReflectionsNpcReaction::Fleeing) Group = Archetype->BarkOnFear;
        else if (Reaction == EReflectionsNpcReaction::Alert || Reaction == EReflectionsNpcReaction::Investigating) Group = Archetype->BarkOnAlert;
        else if (Reaction == EReflectionsNpcReaction::Attacking) Group = Archetype->BarkOnAttack;
        PlayBark(Npc->GetOwner(), Group);
    }
    OnNpcReaction.Broadcast(Npc->GetOwner(), Reaction, Cause, Location);
}

#if !UE_BUILD_SHIPPING
// Npc.Spawn <ArchetypeId> [Count] [Distance]: team-look NPCs in front of the player, for tests.
static FAutoConsoleCommandWithWorldAndArgs GReflectionsNpcSpawnCommand(
    TEXT("Npc.Spawn"), TEXT("Npc.Spawn <ArchetypeId> [Count=1] [Distance=600]: spawn NPCs of an archetype with team MetaHuman looks in front of the player."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        UReflectionsNpcSubsystem* Npcs = World ? World->GetSubsystem<UReflectionsNpcSubsystem>() : nullptr;
        const APawn* Player = World ? UGameplayStatics::GetPlayerPawn(World, 0) : nullptr;
        if (!Npcs || !Player || Args.Num() < 1) return;
        const int32 Count = Args.Num() > 1 ? FMath::Clamp(FCString::Atoi(*Args[1]), 1, 12) : 1;
        const float Distance = Args.Num() > 2 ? FCString::Atof(*Args[2]) : 600.0f;
        const FVector Forward = Player->GetActorForwardVector().GetSafeNormal2D();
        const FVector Right = FVector::CrossProduct(FVector::UpVector, Forward);
        const FVector Feet = Player->GetActorLocation() - FVector(0.0, 0.0, Player->GetSimpleCollisionHalfHeight());
        for (int32 Index = 0; Index < Count; ++Index)
            Npcs->SpawnNpc(FName(*Args[0]), Feet + Forward * Distance + Right * (Index - (Count - 1) * 0.5f) * 160.0f, (-Forward).Rotation().Yaw);
    }));

// Npc.Weaken [Health]: for kill tests. One spell then kills through the normal hit path.
static FAutoConsoleCommandWithWorldAndArgs GReflectionsNpcWeakenCommand(
    TEXT("Npc.Weaken"), TEXT("Npc.Weaken [Health=5]: hold the living NPC nearest in front of the player still for 15 s and leave it with that much health, so one spell kills it. NPCs cast as a named person are taken only if nobody else is there."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        UReflectionsNpcSubsystem* Npcs = World ? World->GetSubsystem<UReflectionsNpcSubsystem>() : nullptr;
        const APawn* Player = World ? UGameplayStatics::GetPlayerPawn(World, 0) : nullptr;
        if (!Npcs || !Player) return;
        const float Wanted = Args.Num() > 0 ? FMath::Max(1.0f, FCString::Atof(*Args[0])) : 5.0f;
        const FVector Here = Player->GetActorLocation();
        const FVector Forward = Player->GetControlRotation().Vector().GetSafeNormal2D();
        AActor* Best = nullptr;
        float BestScore = TNumericLimits<float>::Max();
        for (AActor* Actor : Npcs->GetNpcActors())
        {
            const UReflectionsNpcReactionComponent* Npc = Npcs->FindNpc(Actor);
            if (!Npc || Npc->IsIncapacitated()) continue;
            const FVector To = Actor->GetActorLocation() - Here;
            const float Distance = To.Size2D();
            if (Distance > 2500.0f || FVector::DotProduct(To.GetSafeNormal2D(), Forward) < 0.5f) continue;
            // Named people last: a test should not kill someone the story keeps.
            const float Score = Distance + (Npc->HasVoiceOverride() ? 100000.0f : 0.0f);
            if (Score < BestScore)
            {
                Best = Actor;
                BestScore = Score;
            }
        }
        if (!Best)
        {
            UE_LOG(LogReflectionsNpc, Display, TEXT("Npc.Weaken: no living NPC within 25 m in front of the player."));
            return;
        }
        Npcs->HoldNpc(Best, 15.0f);
        UReflectionsHealthComponent* Health = Best->FindComponentByClass<UReflectionsHealthComponent>();
        if (Health && Health->Health > Wanted)
            UGameplayStatics::ApplyDamage(Best, Health->Health - Wanted, nullptr, nullptr, UDamageType::StaticClass());
        UE_LOG(LogReflectionsNpc, Display, TEXT("Npc.Weaken: %s has %.0f health and is held still for 15 s."), *Best->GetName(), Health ? Health->Health : 0.0f);
    }));
#endif

void UReflectionsNpcSubsystem::NotifyHealed(UReflectionsNpcReactionComponent* Npc, AActor* Healer, float Amount)
{
    const UReflectionsNpcArchetype* Archetype = Npc ? Npc->GetActiveArchetype() : nullptr;
    if (!Archetype || Amount <= 0.0f || !IsPlayer(Healer)) return;
    const float Delta = FMath::Min(Archetype->MaxReputationPerHeal, Amount * Archetype->ReputationPerHealedPoint);
    if (Delta > 0.0f)
        if (UReflectionsReputationSubsystem* Reputation = GetWorld()->GetSubsystem<UReflectionsReputationSubsystem>())
            Reputation->AdjustReputation(Healer, Delta);
}

void UReflectionsNpcSubsystem::NotifyDied(UReflectionsNpcReactionComponent* Npc, AActor* Killer)
{
    AActor* Owner = Npc ? Npc->GetOwner() : nullptr;
    const UReflectionsNpcArchetype* Archetype = Npc ? Npc->GetActiveArchetype() : nullptr;
    if (!Owner || !Archetype) return;

    if (IsPlayer(Killer) && !FMath::IsNearlyZero(Archetype->ReputationOnPlayerKill))
        if (UReflectionsReputationSubsystem* Reputation = GetWorld()->GetSubsystem<UReflectionsReputationSubsystem>())
            Reputation->AdjustReputation(Killer, Archetype->ReputationOnPlayerKill);

    if (IsPlayer(Killer) && !UReflectionsNpcArchetype::IsHostileDisposition(Archetype->Disposition))
        ReportPlayerCrime(Owner, TEXT("Murder"), Owner->GetActorLocation());

    // An actor that already carries world jump's own native component pays its coin itself.
    if (!Owner->FindComponentByClass<UReflectionsWorldNativeComponent>())
        RewardCoin(*Archetype, Npc->GetHomeLocation(), Owner->GetActorLocation(), Owner);

    if (Npc->bOnInfectionMeter && Archetype->bCuredOnDeath)
    {
        Npc->bOnInfectionMeter = false;
        ReportToInfectionMeter(Owner, false);
    }

    FReflectionsNpcStimulus Stimulus;
    Stimulus.Kind = EReflectionsNpcStimulusKind::Death;
    Stimulus.Location = Owner->GetActorLocation();
    Stimulus.Instigator = Killer;
    ReportStimulus(Stimulus);
    OnNpcDied.Broadcast(Owner, Killer);
}

void UReflectionsNpcSubsystem::RewardCoin(const UReflectionsNpcArchetype& Archetype, const FVector& HomeLocation, const FVector& DeathLocation, AActor* Owner)
{
    if (Archetype.CoinReward == EReflectionsNpcCoinReward::None) return;
    EReflectionsWorld Home = EReflectionsWorld::Gray;
    switch (Archetype.HomeWorld)
    {
    case EReflectionsNpcHomeWorld::Gray: Home = EReflectionsWorld::Gray; break;
    case EReflectionsNpcHomeWorld::Red: Home = EReflectionsWorld::Red; break;
    case EReflectionsNpcHomeWorld::White: Home = EReflectionsWorld::White; break;
    default: Home = UReflectionsWorldLibrary::GetWorldAtLocation(this, HomeLocation); break;
    }
    if (Archetype.CoinReward == EReflectionsNpcCoinReward::Pickup) UReflectionsWorldLibrary::DropCoin(this, Home, DeathLocation);
    else UReflectionsWorldLibrary::AwardCoin(this, Home, 1);
    UE_LOG(LogReflectionsNpc, Log, TEXT("NPC %s paid one %s coin."), Owner ? *Owner->GetName() : TEXT("(crowd)"),
        *StaticEnum<EReflectionsWorld>()->GetNameStringByValue(static_cast<int64>(Home)));
}

// ---- Infection ---------------------------------------------------------------------------------------------

void UReflectionsNpcSubsystem::ReportToInfectionMeter(AActor* Host, bool bInfected) const
{
    // Game flow is called by name, as its header offers, so NPC code does not depend on its headers.
    const UWorld* World = GetWorld();
    UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
    UClass* FlowClass = FindObject<UClass>(nullptr, TEXT("/Script/reflections.ReflectionsGameFlowSubsystem"));
    if (!GameInstance || !FlowClass || !FlowClass->IsChildOf(UGameInstanceSubsystem::StaticClass())) return;
    UGameInstanceSubsystem* Flow = GameInstance->GetSubsystemBase(FlowClass);
    UFunction* Function = Flow ? Flow->FindFunction(bInfected ? TEXT("ReportInfected") : TEXT("ReportCured")) : nullptr;
    if (!Function || Function->ParmsSize != static_cast<int32>(sizeof(AActor*))) return;
    struct { AActor* Host; } Params{ Host };
    Flow->ProcessEvent(Function, &Params);
}

bool UReflectionsNpcSubsystem::SetInfection(AActor* Actor, EReflectionsNpcInfection State, AActor* Source)
{
    if (!IsValid(Actor)) return false;
    UReflectionsNpcReactionComponent* Npc = FindNpc(Actor);
    if (!Npc) Npc = EnrollActor(Actor, nullptr);
    if (!Npc) return false;
    AActor* NpcActor = Npc->GetOwner();

    UReflectionsNpcArchetype* Taken = nullptr;
    if (State == EReflectionsNpcInfection::Infected) Taken = FindArchetype(TEXT("Infected"));
    else if (State == EReflectionsNpcInfection::VillainHost) Taken = FindArchetype(TEXT("VillainHost"));
    // The end of a conversion sequence: both of its NPCs are let go, whatever the new state is.
    Npc->EndScriptedHold();
    if (UReflectionsNpcReactionComponent* SourceNpc = FindNpc(Source)) SourceNpc->EndScriptedHold();
    if (!Npc->ApplyInfection(State, Taken)) return false;

    const UReflectionsNpcArchetype* Active = Npc->GetActiveArchetype();
    const bool bCount = Active && Active->bCountsOnInfectionMeter && !(Npc->IsIncapacitated() && Active->bCuredOnDeath);
    if (bCount != Npc->bOnInfectionMeter)
    {
        Npc->bOnInfectionMeter = bCount;
        ReportToInfectionMeter(NpcActor, bCount);
    }
    if (Taken)
    {
        FReflectionsNpcStimulus Stimulus;
        Stimulus.Kind = EReflectionsNpcStimulusKind::Infection;
        Stimulus.Location = NpcActor->GetActorLocation();
        Stimulus.Instigator = NpcActor;
        ReportStimulus(Stimulus);
    }
    OnNpcInfection.Broadcast(NpcActor, State, Source);
    return true;
}

void UReflectionsNpcSubsystem::HoldNpc(AActor* Actor, float Seconds)
{
    if (UReflectionsNpcReactionComponent* Npc = FindNpc(Actor)) Npc->BeginScriptedHold(Seconds);
}

void UReflectionsNpcSubsystem::ReleaseNpc(AActor* Actor)
{
    if (UReflectionsNpcReactionComponent* Npc = FindNpc(Actor)) Npc->EndScriptedHold();
}

bool UReflectionsNpcSubsystem::TryBeginConversion(UReflectionsNpcReactionComponent* Attacker, AActor* Victim)
{
    UReflectionsNpcReactionComponent* VictimNpc = FindNpc(Victim);
    UWorld* World = GetWorld();
    if (!World || !Attacker || !VictimNpc || VictimNpc == Attacker || VictimNpc->IsIncapacitated() || VictimNpc->IsScripted()) return false;
    // The villain system is called by name (its header keeps changing): float BeginConversion(AActor* Attacker, AActor* Victim).
    UClass* VillainClass = FindObject<UClass>(nullptr, TEXT("/Script/reflections.ReflectionsVillainSubsystem"));
    if (!VillainClass || !VillainClass->IsChildOf(UWorldSubsystem::StaticClass())) return false;
    UWorldSubsystem* Villain = World->GetSubsystemBase(VillainClass);
    UFunction* Function = Villain ? Villain->FindFunction(TEXT("BeginConversion")) : nullptr;
    struct FConversionParams
    {
        AActor* Attacker = nullptr;
        AActor* Victim = nullptr;
        float ReturnValue = 0.0f;
    };
    // Two actors in, a float out. The reflected size is unpadded (20 bytes), so it only has to fit the struct.
    if (!Function || Function->NumParms != 3 || Function->ParmsSize > static_cast<int32>(sizeof(FConversionParams)) ||
        !CastField<FFloatProperty>(Function->GetReturnProperty())) return false;
    FConversionParams Params;
    Params.Attacker = Attacker->GetOwner();
    Params.Victim = VictimNpc->GetOwner();
    Villain->ProcessEvent(Function, &Params);
    if (Params.ReturnValue <= 0.0f) return false;
    // Both are the villain's for the length of the sequence, with a second of slack as a safety timeout.
    Attacker->BeginScriptedHold(Params.ReturnValue + 1.0f);
    VictimNpc->BeginScriptedHold(Params.ReturnValue + 1.0f);
    UE_LOG(LogReflectionsNpc, Log, TEXT("Conversion: %s on %s, held for %.1f s."), *GetNameSafe(Params.Attacker), *GetNameSafe(Params.Victim), Params.ReturnValue);
    return true;
}

EReflectionsNpcInfection UReflectionsNpcSubsystem::GetInfection(const AActor* Actor) const
{
    const UReflectionsNpcReactionComponent* Npc = FindNpc(Actor);
    return Npc ? Npc->GetInfection() : EReflectionsNpcInfection::None;
}
