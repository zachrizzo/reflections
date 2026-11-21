#include "NPC/ReflectionsNpcSubsystem.h"

#include "NPC/ReflectionsNpcCombatComponent.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsReputationSubsystem.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Voice/ReflectionsAmbientTalk.h"
#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Components/CapsuleComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
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

static TAutoConsoleVariable<int32> CVarNpcSpawnOnFloor(TEXT("Npc.SpawnOnFloor"), 1,
    TEXT("1 (default): SpawnNpc stands the NPC on the topmost walkable surface, at least 5 m across both ways, within 50 cm above and 150 cm below the place asked for (a road sheet over the city ground, a kerb; not a bench); a smaller piece counts too when such floor lies within 30 cm under it (paving in a narrow lane). 2: the 5 m rule without that exception. 0: exactly where asked."));

static TAutoConsoleVariable<float> CVarNpcPanicRipple(TEXT("Npc.PanicRipple"), 0.2f,
    TEXT("Seconds by which each 5 m ring further from a noise, a fight, a death or a taking hears of it later, so that alarm spreads outward (never more than 0.9 s). 0: everyone at once. Alarm calls and direct hits are never delayed."));

static TAutoConsoleVariable<int32> CVarNpcHeat(TEXT("Npc.Heat"), 1,
    TEXT("1 (default): the player's crimes against NPCs raise heat, witnesses call out and guards turn on the player. 0: off."));

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

FName UReflectionsNpcSubsystem::GetSideAt(FVector Location) const
{
    return NAME_None;
}

TArray<TSoftClassPtr<AActor>> UReflectionsNpcSubsystem::GetLooksAt(FName ArchetypeId, FVector Location)
{
    return GetLooksForSide(ArchetypeId, GetSideAt(Location));
}

TArray<TSoftClassPtr<AActor>> UReflectionsNpcSubsystem::GetLooksForSide(FName ArchetypeId, FName Side)
{
    const UReflectionsNpcArchetype* Archetype = FindArchetype(ArchetypeId);
    return Archetype ? Archetype->Looks : TArray<TSoftClassPtr<AActor>>();
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
    const TArray<TSoftClassPtr<AActor>>& Choices = Archetype->Looks;
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
    // On the floor that is really there. A street can be a thin sheet above the ground the caller measured from
    // (Gray London's roads lie 18 cm over the city ground): asked for the lower one, the NPC stood with its feet in
    // the road. The topmost walkable surface near the place asked for wins; small things (a bench, a crate) do not
    // count as floor.
    if (CVarNpcSpawnOnFloor.GetValueOnGameThread() != 0)
    {
        TArray<FHitResult> Floors;
        const FCollisionQueryParams FloorQuery(SCENE_QUERY_STAT(NpcSpawnFloor), true);
        World->LineTraceMultiByObjectType(Floors, Location + FVector(0.0, 0.0, 50.0), Location - FVector(0.0, 0.0, 150.0),
            FCollisionObjectQueryParams(ECC_WorldStatic), FloorQuery);
        // The topmost small walkable piece met on the way down: it is the floor after all when broad floor lies
        // just under it (paving pieces on the ground slab of a narrow lane; a bench seat is 45 cm up and is not).
        const bool bPavingCounts = CVarNpcSpawnOnFloor.GetValueOnGameThread() != 2;
        bool bSmallPiece = false;
        double SmallPieceTop = 0.0;
        for (const FHitResult& Floor : Floors)
        {
            const UPrimitiveComponent* Surface = Floor.GetComponent();
            if (!Surface || Floor.ImpactNormal.Z <= 0.7f) continue;
            // Broad in both directions on the ground (a railing or a kerb strip is long and thin). Street furniture
            // is instanced, many pieces in one component: there it is the piece that was hit that is measured.
            FVector HalfSize = Surface->Bounds.BoxExtent;
            if (const UInstancedStaticMeshComponent* Instanced = Cast<UInstancedStaticMeshComponent>(Surface))
            {
                FTransform PieceToWorld;
                const UStaticMesh* Piece = Instanced->GetStaticMesh();
                if (!Piece || !Instanced->GetInstanceTransform(Floor.Item, PieceToWorld, true)) continue;
                HalfSize = Piece->GetBounds().TransformBy(PieceToWorld).BoxExtent;
            }
            if (FMath::Min(HalfSize.X, HalfSize.Y) < 250.0)
            {
                if (!bSmallPiece)
                {
                    bSmallPiece = true;
                    SmallPieceTop = Floor.ImpactPoint.Z;
                }
                continue;
            }
            const bool bOnPaving = bPavingCounts && bSmallPiece && SmallPieceTop >= Floor.ImpactPoint.Z &&
                SmallPieceTop - Floor.ImpactPoint.Z <= 30.0;
            Location.Z = bOnPaving ? SmallPieceTop : Floor.ImpactPoint.Z;
            break;
        }
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
    EReflectionsNpcHomeWorld Home = Kind ? Kind->HomeWorld : EReflectionsNpcHomeWorld::FromSpawnLocation;
    if (Owner->ActorHasTag(TEXT("Look_Side_Pewterside"))) Home = EReflectionsNpcHomeWorld::Gray;
    else if (Owner->ActorHasTag(TEXT("Look_Side_Giltside"))) Home = EReflectionsNpcHomeWorld::Red;
    else if (Owner->ActorHasTag(TEXT("Look_Side_Frostside"))) Home = EReflectionsNpcHomeWorld::White;
    const int32 LookAge = Owner->ActorHasTag(TEXT("Look_Age_Young")) ? 1 : Owner->ActorHasTag(TEXT("Look_Age_Adult")) ? 2
        : Owner->ActorHasTag(TEXT("Look_Age_Old")) ? 3 : 0;
    // The table may name a side either way: as the player knows it or as the code does.
    const FName SideName = Home == EReflectionsNpcHomeWorld::Gray ? FName(TEXT("Pewterside")) : Home == EReflectionsNpcHomeWorld::Red ? FName(TEXT("Giltside")) : Home == EReflectionsNpcHomeWorld::White ? FName(TEXT("Frostside")) : NAME_None;
    const FName SideCode = Home == EReflectionsNpcHomeWorld::Gray ? FName(TEXT("Gray")) : Home == EReflectionsNpcHomeWorld::Red ? FName(TEXT("Red")) : Home == EReflectionsNpcHomeWorld::White ? FName(TEXT("White")) : NAME_None;
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
    // Only near the player, on screen, and a voice free (ReflectionsAmbientTalk); a fight or fear line carries farther.
    if (!ReflectionsAmbientTalk::MayStart(Owner, Npc->Reaction != EReflectionsNpcReaction::Calm)) return;
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
    UAudioComponent* Audio = bHead
        ? UGameplayStatics::SpawnSoundAttached(Cue, Body, TEXT("head"), FVector::ZeroVector, EAttachLocation::SnapToTarget, true)
        : UGameplayStatics::SpawnSoundAttached(Cue, Owner->GetRootComponent(), NAME_None, FVector(0.0, 0.0, 160.0), EAttachLocation::KeepRelativeOffset, true);
    // Counted against the ambient cap, and faded out when the player walks away.
    ReflectionsAmbientTalk::Track(Audio, Owner, Npc->Reaction != EReflectionsNpcReaction::Calm);
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
    if (!Cue || !ReflectionsAmbientTalk::MayStart(Owner, false)) return false;
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

    const bool bCall = Stamped.Kind == EReflectionsNpcStimulusKind::Alarm;
    if (!bCall)
    {
        const double Now = Stamped.WorldTime;
        RecentViolence.RemoveAll([Now](const TPair<FVector, double>& Old) { return Now - Old.Value > 120.0; });
        if (RecentViolence.Num() >= 32) RecentViolence.RemoveAt(0);
        RecentViolence.Emplace(Stamped.Location, Now);
    }

    const float Reputation = GetReputation(Stamped.Instigator.Get());
    // Alarm spreads: each 5 m ring further out hears of it a little later. A call for help is heard at once.
    const float PerRing = bCall ? 0.0f : CVarNpcPanicRipple.GetValueOnGameThread();
    // A reaction can enrol or remove NPCs: walk a copy.
    const TArray<TWeakObjectPtr<UReflectionsNpcReactionComponent>> Listeners = Npcs;
    for (const TWeakObjectPtr<UReflectionsNpcReactionComponent>& Weak : Listeners)
    {
        UReflectionsNpcReactionComponent* Npc = Weak.Get();
        const AActor* Listener = Npc ? Npc->GetOwner() : nullptr;
        if (!Listener) continue;
        const float Delay = PerRing > 0.0f
            ? FMath::Min(FMath::FloorToFloat(FVector::Dist2D(Listener->GetActorLocation(), Stamped.Location) / 500.0f) * PerRing, 0.9f) : 0.0f;
        if (Delay > 0.0f) Npc->QueueStimulus(Stamped, Reputation, Delay);
        else Npc->ReceiveStimulus(Stamped, Reputation);
    }
}

float UReflectionsNpcSubsystem::GetSecondsSinceViolence(FVector Near, float Radius) const
{
    const UWorld* World = GetWorld();
    const double Now = World ? World->GetTimeSeconds() : 0.0;
    double Latest = -1.0e9;
    for (const TPair<FVector, double>& Event : RecentViolence)
        if (Radius <= 0.0f || FVector::DistSquared2D(Event.Key, Near) <= FMath::Square(Radius)) Latest = FMath::Max(Latest, Event.Value);
    return static_cast<float>(FMath::Min(Now - Latest, 1.0e6));
}

bool UReflectionsNpcSubsystem::BeginNpcScene(AActor* Actor, UAnimSequenceBase* Loop, bool bPinned, float BlendIn)
{
    UReflectionsNpcReactionComponent* Npc = FindNpc(Actor);
    return Npc && Npc->BeginScene(Loop, bPinned, BlendIn);
}

bool UReflectionsNpcSubsystem::PlayNpcSceneClip(AActor* Actor, UAnimSequenceBase* Clip, float BlendIn, float BlendOut, bool bThenEnd)
{
    UReflectionsNpcReactionComponent* Npc = FindNpc(Actor);
    return Npc && Npc->PlaySceneClip(Clip, BlendIn, BlendOut, bThenEnd);
}

void UReflectionsNpcSubsystem::EndNpcScene(AActor* Actor, float BlendOut)
{
    if (UReflectionsNpcReactionComponent* Npc = FindNpc(Actor)) Npc->EndScene(false, FMath::Clamp(BlendOut, 0.0f, 2.0f));
}

bool UReflectionsNpcSubsystem::IsNpcInScene(const AActor* Actor) const
{
    const UReflectionsNpcReactionComponent* Npc = FindNpc(Actor);
    return Npc && Npc->IsInScene();
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
    if (!Cue || !ReflectionsAmbientTalk::MayStart(Npc->GetOwner(), true)) return;
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

    if (Npc->bOnInfectionMeter && Archetype->bCuredOnDeath)
    {
        Npc->bOnInfectionMeter = false;
    }

    FReflectionsNpcStimulus Stimulus;
    Stimulus.Kind = EReflectionsNpcStimulusKind::Death;
    Stimulus.Location = Owner->GetActorLocation();
    Stimulus.Instigator = Killer;
    ReportStimulus(Stimulus);
    OnNpcDied.Broadcast(Owner, Killer);
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

void UReflectionsNpcSubsystem::TurnNpcTowards(AActor* Actor, FVector Point, float DeltaTime)
{
    if (UReflectionsNpcReactionComponent* Npc = FindNpc(Actor)) Npc->FacePoint(Point, DeltaTime);
}

EReflectionsNpcInfection UReflectionsNpcSubsystem::GetInfection(const AActor* Actor) const
{
    const UReflectionsNpcReactionComponent* Npc = FindNpc(Actor);
    return Npc ? Npc->GetInfection() : EReflectionsNpcInfection::None;
}
