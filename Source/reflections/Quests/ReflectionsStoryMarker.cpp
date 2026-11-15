#include "Quests/ReflectionsStoryMarker.h"

#include "Components/ArrowComponent.h"
#include "Components/BillboardComponent.h"
#include "Components/TextRenderComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "NavigationSystem.h"
#include "NavigationPath.h"
#include "Worlds/ReflectionsWorldAnchor.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"
#include "Worlds/ReflectionsWorldPickups.h"
#include "Worlds/ReflectionsSealedDoor.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsStory, Log, All);

namespace ReflectionsStoryMarkerCVars
{
    static int32 Fallback = 1;
    static FAutoConsoleVariableRef CVarFallback(TEXT("Story.MarkerFallback"), Fallback,
        TEXT("1: a story marker the map lacks is auto-placed on a nav-reachable point near its side (default). 0: missing markers stay missing."));

    static int32 Show = 0;
    static FAutoConsoleVariableRef CVarShow(TEXT("Story.ShowMarkers"), Show, TEXT("1: draw every story marker's name and radius in game."));

    static const TCHAR* Kinds[] = {TEXT("Home"), TEXT("Work"), TEXT("Haunt"), TEXT("QuestGiver"), TEXT("CutsceneAnchor"), TEXT("Tower"), TEXT("Spot"), TEXT("Item"), TEXT("Mk")};
}

// ---- Actor ----------------------------------------------------------------------------------------------------

AReflectionsStoryMarker::AReflectionsStoryMarker()
{
    PrimaryActorTick.bCanEverTick = false;
    bIsEditorOnlyActor = false;
    SetHidden(true);
    SetCanBeDamaged(false);

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);
    Root->SetMobility(EComponentMobility::Static);

    Facing = CreateDefaultSubobject<UArrowComponent>(TEXT("Facing"));
    Facing->SetupAttachment(Root);
    Facing->ArrowColor = FColor(240, 184, 72);
    Facing->ArrowSize = 1.2f;
    Facing->bIsScreenSizeScaled = false;
    Facing->SetHiddenInGame(true);

#if WITH_EDITORONLY_DATA
    Sprite = CreateEditorOnlyDefaultSubobject<UBillboardComponent>(TEXT("Sprite"));
    if (Sprite)
    {
        Sprite->SetupAttachment(Root);
        Sprite->SetRelativeLocation(FVector(0, 0, 60));
        Sprite->bIsScreenSizeScaled = true;
    }
    Label = CreateEditorOnlyDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
    if (Label)
    {
        Label->SetupAttachment(Root);
        Label->SetRelativeLocation(FVector(0, 0, 120));
        Label->SetHorizontalAlignment(EHTA_Center);
        Label->SetWorldSize(36.0f);
        Label->SetTextRenderColor(FColor(240, 184, 72));
        Label->SetHiddenInGame(true);
        Label->bIsEditorOnly = true;
    }
#endif
}

TArray<FName> AReflectionsStoryMarker::GetNames() const
{
    TArray<FName> Names;
    if (!MarkerName.IsNone())
    {
        Names.Add(MarkerName);
    }
    for (const FName& Tag : Tags)
    {
        if (IsStoryName(Tag))
        {
            Names.AddUnique(Tag);
        }
    }
    return Names;
}

bool AReflectionsStoryMarker::HasName(FName Name) const
{
    if (Name.IsNone())
    {
        return false;
    }
    if (MarkerName == Name)
    {
        return true;
    }
    return Tags.Contains(Name);
}

EReflectionsWorld AReflectionsStoryMarker::GetResolvedSide() const
{
    switch (Side)
    {
    case EReflectionsMarkerSide::Pewterside: return EReflectionsWorld::Gray;
    case EReflectionsMarkerSide::Giltside: return EReflectionsWorld::Red;
    case EReflectionsMarkerSide::Frostside: return EReflectionsWorld::White;
    default: break;
    }
    if (const UReflectionsWorldJumpWorldSubsystem* Jump = UReflectionsWorldJumpWorldSubsystem::Get(this))
    {
        if (Jump->IsWorldJumpActive())
        {
            return Jump->GetWorldAtLocation(GetActorLocation());
        }
    }
    return EReflectionsWorld::Red;
}

bool AReflectionsStoryMarker::SplitName(FName Name, FString& OutKind, FString& OutKey)
{
    const FString S = Name.ToString();
    int32 Index = INDEX_NONE;
    if (!S.FindChar(TEXT('_'), Index) || Index <= 0)
    {
        OutKind = S;
        OutKey.Reset();
        return false;
    }
    OutKind = S.Left(Index);
    OutKey = S.Mid(Index + 1);
    return true;
}

bool AReflectionsStoryMarker::IsStoryName(FName Name)
{
    FString Kind, Key;
    if (!SplitName(Name, Kind, Key) || Key.IsEmpty())
    {
        return false;
    }
    for (const TCHAR* Known : ReflectionsStoryMarkerCVars::Kinds)
    {
        if (Kind.Equals(Known, ESearchCase::IgnoreCase))
        {
            return true;
        }
    }
    return false;
}

void AReflectionsStoryMarker::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    RefreshLabel();
}

#if WITH_EDITOR
void AReflectionsStoryMarker::PostEditChangeProperty(FPropertyChangedEvent& Event)
{
    Super::PostEditChangeProperty(Event);
    RefreshLabel();
}
#endif

void AReflectionsStoryMarker::RefreshLabel()
{
#if WITH_EDITORONLY_DATA
    if (Label)
    {
        const TArray<FName> Names = GetNames();
        FString Text;
        for (const FName& Name : Names)
        {
            Text += (Text.IsEmpty() ? TEXT("") : TEXT("\n")) + Name.ToString();
        }
        Label->SetText(FText::FromString(Text.IsEmpty() ? TEXT("(unnamed story marker)") : Text));
    }
#endif
}

void AReflectionsStoryMarker::BeginPlay()
{
    Super::BeginPlay();
    if (UReflectionsStoryMarkerSubsystem* Markers = UReflectionsStoryMarkerSubsystem::Get(this))
    {
        Markers->Register(this);
    }
}

void AReflectionsStoryMarker::EndPlay(const EEndPlayReason::Type Reason)
{
    if (UReflectionsStoryMarkerSubsystem* Markers = UReflectionsStoryMarkerSubsystem::Get(this))
    {
        Markers->Unregister(this);
    }
    Super::EndPlay(Reason);
}

// ---- Subsystem ------------------------------------------------------------------------------------------------

UReflectionsStoryMarkerSubsystem* UReflectionsStoryMarkerSubsystem::Get(const UObject* WorldContext)
{
    const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    return World ? World->GetSubsystem<UReflectionsStoryMarkerSubsystem>() : nullptr;
}

bool UReflectionsStoryMarkerSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UReflectionsStoryMarkerSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
#if !UE_BUILD_SHIPPING
    TWeakObjectPtr<UReflectionsStoryMarkerSubsystem> Weak(this);
    DrawHandle = FWorldDelegates::OnWorldPostActorTick.AddLambda([Weak](UWorld* World, ELevelTick, float)
    {
        const UReflectionsStoryMarkerSubsystem* Self = Weak.Get();
        if (ReflectionsStoryMarkerCVars::Show == 0 || !Self || World != Self->GetWorld())
        {
            return;
        }
        for (const AReflectionsStoryMarker* M : Self->GetAllMarkers())
        {
            const FColor Color = M->bAutoPlaced ? FColor(120, 200, 255) : FColor(240, 184, 72);
            FString Names;
            for (const FName& N : M->GetNames()) Names += (Names.IsEmpty() ? TEXT("") : TEXT(" | ")) + N.ToString();
            const FVector L = M->GetActorLocation();
            DrawDebugCircle(World, L + FVector(0, 0, 5), M->Radius, 32, Color, false, -1.0f, 0, 3.0f, FVector(1, 0, 0), FVector(0, 1, 0), false);
            DrawDebugDirectionalArrow(World, L + FVector(0, 0, 40), L + FVector(0, 0, 40) + M->GetActorForwardVector() * 150.0f, 40.0f, Color, false, -1.0f, 0, 3.0f);
            DrawDebugString(World, L + FVector(0, 0, 180), Names + (M->bAutoPlaced ? TEXT(" [auto]") : TEXT("")), nullptr, Color, 0.0f, true);
        }
    });
#endif
}

void UReflectionsStoryMarkerSubsystem::Deinitialize()
{
    if (DrawHandle.IsValid())
    {
        FWorldDelegates::OnWorldPostActorTick.Remove(DrawHandle);
        DrawHandle.Reset();
    }
    Super::Deinitialize();
}

AReflectionsStoryMarker* UReflectionsStoryMarkerSubsystem::FindMarker(const UObject* WorldContext, FName Name, bool bAllowFallback)
{
    UReflectionsStoryMarkerSubsystem* Self = Get(WorldContext);
    return Self ? Self->Find(Name, bAllowFallback) : nullptr;
}

bool UReflectionsStoryMarkerSubsystem::GetMarkerTransform(const UObject* WorldContext, FName Name, FTransform& OutTransform, bool bAllowFallback)
{
    if (const AReflectionsStoryMarker* Marker = FindMarker(WorldContext, Name, bAllowFallback))
    {
        OutTransform = Marker->GetActorTransform();
        return true;
    }
    return false;
}

void UReflectionsStoryMarkerSubsystem::Register(AReflectionsStoryMarker* Marker)
{
    if (!IsValid(Marker))
    {
        return;
    }
    for (const TWeakObjectPtr<AReflectionsStoryMarker>& Existing : Markers)
    {
        if (Existing.Get() == Marker)
        {
            return;
        }
    }
    Markers.Add(Marker);
    for (const FName& Name : Marker->GetNames())
    {
        OnMarkerPlaced.Broadcast(Name, Marker, Marker->bAutoPlaced);
    }
}

void UReflectionsStoryMarkerSubsystem::Unregister(AReflectionsStoryMarker* Marker)
{
    Markers.RemoveAll([Marker](const TWeakObjectPtr<AReflectionsStoryMarker>& Weak) { return !Weak.IsValid() || Weak.Get() == Marker; });
}

AReflectionsStoryMarker* UReflectionsStoryMarkerSubsystem::Find(FName Name, bool bAllowFallback)
{
    if (Name.IsNone())
    {
        return nullptr;
    }
    AReflectionsStoryMarker* AutoFound = nullptr;
    for (const TWeakObjectPtr<AReflectionsStoryMarker>& Weak : Markers)
    {
        AReflectionsStoryMarker* Marker = Weak.Get();
        if (Marker && Marker->HasName(Name))
        {
            if (!Marker->bAutoPlaced)
            {
                return Marker;  // hand-placed always wins
            }
            AutoFound = Marker;
        }
    }
    if (AutoFound)
    {
        return AutoFound;
    }
    // Markers placed before this subsystem knew about them (streamed levels that began play early).
    if (UWorld* World = GetWorld())
    {
        for (TActorIterator<AReflectionsStoryMarker> It(World); It; ++It)
        {
            if (It->HasName(Name))
            {
                Register(*It);
                return *It;
            }
        }
        // Any other actor carrying the name as a tag (the story's Mk_ tags may sit on a Target Point): adopt it.
        if (!World->HasBegunPlay())
        {
            return nullptr;
        }
        // The map may use the people book's tag for this place (Spot_BellSquare <- Mk_Gilt_Square_BellSquare).
        if (const FName* Alias = Aliases.Find(Name))
        {
            if (AReflectionsStoryMarker* Found = Find(*Alias, false))
            {
                return Adopt(Name, Found, false);
            }
        }
        for (TActorIterator<AActor> It(World); It; ++It)
        {
            if (It->ActorHasTag(Name) && !It->IsA<AReflectionsStoryMarker>())
            {
                return Adopt(Name, *It, false);
            }
        }
        // Mk_<Side>_<Kind>_<Name>: the same kind of place on the same side stands in (the story's fallback rule).
        FString Kind, Key;
        AReflectionsStoryMarker::SplitName(Name, Kind, Key);
        TArray<FString> Parts;
        Key.ParseIntoArray(Parts, TEXT("_"));
        if (Kind.Equals(TEXT("Mk"), ESearchCase::IgnoreCase) && Parts.Num() >= 3 && bAllowFallback)
        {
            const FString Generic = FString::Printf(TEXT("Mk_%s_%s"), *Parts[0], *Parts[1]);
            for (const TWeakObjectPtr<AReflectionsStoryMarker>& Weak : Markers)
            {
                if (!Weak.IsValid() || Weak->bAutoPlaced) continue;
                for (const FName& Other : Weak->GetNames())
                {
                    if (Other.ToString().StartsWith(Generic, ESearchCase::IgnoreCase)) return Adopt(Name, Weak.Get(), true);
                }
            }
            for (TActorIterator<AActor> It(World); It; ++It)
            {
                for (const FName& Tag : It->Tags)
                {
                    if (Tag.ToString().StartsWith(Generic, ESearchCase::IgnoreCase)) return Adopt(Name, *It, true);
                }
            }
        }
    }
    if (!bAllowFallback || ReflectionsStoryMarkerCVars::Fallback == 0 || FailedFallbacks.Contains(Name))
    {
        return nullptr;
    }
    return PlaceFallback(Name);
}

AReflectionsStoryMarker* UReflectionsStoryMarkerSubsystem::Adopt(FName Name, AActor* Source, bool bStandIn)
{
    UWorld* World = GetWorld();
    if (!World || !Source) return nullptr;
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AReflectionsStoryMarker* Marker = World->SpawnActor<AReflectionsStoryMarker>(AReflectionsStoryMarker::StaticClass(),
        Source->GetActorLocation(), FRotator(0.0f, Source->GetActorRotation().Yaw, 0.0f), Params);
    if (!Marker) return nullptr;
    Marker->MarkerName = Name;
    // A stand-in for another place of the same kind counts as auto-placed (the map still lacks the real one).
    Marker->bAutoPlaced = bStandIn;
    if (const AReflectionsStoryMarker* From = Cast<AReflectionsStoryMarker>(Source)) Marker->Radius = From->Radius;
    Marker->Notes = FString::Printf(TEXT("%s %s"), bStandIn ? TEXT("Stand-in at") : TEXT("Adopted from"), *Source->GetName());
    UE_LOG(LogReflectionsStory, Log, TEXT("Story marker %s %s %s."), *Name.ToString(), bStandIn ? TEXT("stands in at") : TEXT("is the tagged actor"), *Source->GetName());
    Register(Marker);
    return Marker;
}

TArray<AReflectionsStoryMarker*> UReflectionsStoryMarkerSubsystem::FindByKind(const FString& Kind) const
{
    TArray<AReflectionsStoryMarker*> Out;
    for (const TWeakObjectPtr<AReflectionsStoryMarker>& Weak : Markers)
    {
        AReflectionsStoryMarker* Marker = Weak.Get();
        if (!Marker)
        {
            continue;
        }
        for (const FName& Name : Marker->GetNames())
        {
            FString K, Key;
            AReflectionsStoryMarker::SplitName(Name, K, Key);
            if (K.Equals(Kind, ESearchCase::IgnoreCase))
            {
                Out.AddUnique(Marker);
                break;
            }
        }
    }
    return Out;
}

TArray<AReflectionsStoryMarker*> UReflectionsStoryMarkerSubsystem::GetAllMarkers() const
{
    TArray<AReflectionsStoryMarker*> Out;
    for (const TWeakObjectPtr<AReflectionsStoryMarker>& Weak : Markers)
    {
        if (Weak.IsValid())
        {
            Out.Add(Weak.Get());
        }
    }
    return Out;
}

TArray<FName> UReflectionsStoryMarkerSubsystem::GetAutoPlacedNames() const
{
    TArray<FName> Out;
    for (const TWeakObjectPtr<AReflectionsStoryMarker>& Weak : Markers)
    {
        if (Weak.IsValid() && Weak->bAutoPlaced)
        {
            Out.Append(Weak->GetNames());
        }
    }
    return Out;
}

bool UReflectionsStoryMarkerSubsystem::SideFromKey(const FString& Key, EReflectionsWorld& Out) const
{
    const FString K = Key.ToLower();
    if (K.Contains(TEXT("pewter")) || K.StartsWith(TEXT("pew_")) || K == TEXT("pew") || K == TEXT("gray") || K == TEXT("grey")) { Out = EReflectionsWorld::Gray; return true; }
    if (K.Contains(TEXT("gilt")) || K == TEXT("red")) { Out = EReflectionsWorld::Red; return true; }
    if (K.Contains(TEXT("frost")) || K == TEXT("white")) { Out = EReflectionsWorld::White; return true; }
    return false;
}

FVector UReflectionsStoryMarkerSubsystem::OriginForSide(EReflectionsWorld Side) const
{
    UWorld* World = GetWorld();
    FVector Origin = FVector::ZeroVector;
    bool bHave = false;
    if (World)
    {
        for (TActorIterator<APlayerStart> It(World); It; ++It)
        {
            Origin = It->GetActorLocation();
            bHave = true;
            break;
        }
        if (!bHave)
        {
            if (APlayerController* PC = World->GetFirstPlayerController())
            {
                if (APawn* Pawn = PC->GetPawn())
                {
                    Origin = Pawn->GetActorLocation();
                    bHave = true;
                }
            }
        }
    }
    const UReflectionsWorldJumpWorldSubsystem* Jump = UReflectionsWorldJumpWorldSubsystem::Get(this);
    if (Jump && Jump->IsWorldJumpActive())
    {
        const EReflectionsWorld From = Jump->GetWorldAtLocation(Origin);
        FVector Moved;
        if (From != Side && Jump->TranslateBetweenWorlds(Origin, From, Side, Moved))
        {
            Origin = Moved;
        }
    }
    return Origin;
}

bool UReflectionsStoryMarkerSubsystem::FindFallbackPoint(FName Name, const FString& Kind, const FString& Key, EReflectionsWorld Side,
    FVector& OutPoint, FVector& OutFaceToward) const
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return false;
    }
    const UReflectionsWorldJumpWorldSubsystem* Jump = UReflectionsWorldJumpWorldSubsystem::Get(this);
    const bool bJump = Jump && Jump->IsWorldJumpActive();
    const auto InSide = [&](const FVector& L) { return !bJump || Jump->GetWorldAtLocation(L) == Side; };

    FVector Origin = OriginForSide(Side);

    // Towers: the side's mirror page sits at the top of its tower; the Gilt Tower also has the sealed door.
    if (Kind.Equals(TEXT("Tower"), ESearchCase::IgnoreCase))
    {
        bool bFound = false;
        if (Side == EReflectionsWorld::Red)
        {
            for (TActorIterator<AReflectionsSealedDoor> It(World); It && !bFound; ++It)
            {
                if (InSide(It->GetActorLocation())) { Origin = It->GetActorLocation(); bFound = true; }
            }
        }
        for (TActorIterator<AReflectionsBookPagePickup> It(World); It && !bFound; ++It)
        {
            if (InSide(It->GetActorLocation())) { Origin = It->GetActorLocation(); bFound = true; }
        }
        if (bFound)
        {
            OutPoint = Origin;
            OutFaceToward = OriginForSide(Side);
            return true;
        }
    }

    float MinDist = 1500.0f, MaxDist = 3500.0f;
    if (Kind.Equals(TEXT("QuestGiver"), ESearchCase::IgnoreCase)) { MinDist = 600.0f; MaxDist = 1400.0f; }
    else if (Kind.Equals(TEXT("Home"), ESearchCase::IgnoreCase)) { MinDist = 2500.0f; MaxDist = 4500.0f; }
    else if (Kind.Equals(TEXT("Haunt"), ESearchCase::IgnoreCase)) { MinDist = 2000.0f; MaxDist = 5000.0f; }
    else if (Kind.Equals(TEXT("CutsceneAnchor"), ESearchCase::IgnoreCase)) { MinDist = 800.0f; MaxDist = 2000.0f; }
    else if (Kind.Equals(TEXT("Item"), ESearchCase::IgnoreCase)) { MinDist = 1500.0f; MaxDist = 3000.0f; }

    // Deterministic per name: the same map always gets the same fallback spots.
    const uint32 Hash = GetTypeHash(Name.ToString().ToLower());
    FRandomStream Stream(static_cast<int32>(Hash));
    UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
    FNavLocation OriginNav;
    const bool bOriginOnNav = Nav && Nav->ProjectPointToNavigation(Origin, OriginNav, FVector(500, 500, 1000));

    for (int32 Attempt = 0; Attempt < 24; ++Attempt)
    {
        const float Angle = Stream.FRandRange(0.0f, 2.0f * PI);
        const float Dist = FMath::Lerp(MinDist, MaxDist, Stream.FRand()) * (Attempt < 12 ? 1.0f : 0.5f);
        const FVector Candidate = Origin + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f) * Dist;
        if (!InSide(Candidate))
        {
            continue;
        }
        if (bOriginOnNav)
        {
            FNavLocation Projected;
            if (!Nav->ProjectPointToNavigation(Candidate, Projected, FVector(400, 400, 2000)))
            {
                continue;
            }
            UNavigationPath* Path = Nav->FindPathToLocationSynchronously(World, OriginNav.Location, Projected.Location);
            if (!Path || !Path->IsValid() || Path->IsPartial())
            {
                continue;
            }
            OutPoint = Projected.Location;
            OutFaceToward = Origin;
            return true;
        }
        // No navmesh: drop onto the ground.
        FHitResult Hit;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(StoryMarkerFallback), false);
        if (World->LineTraceSingleByChannel(Hit, Candidate + FVector(0, 0, 3000), Candidate - FVector(0, 0, 5000), ECC_Visibility, Params) &&
            Hit.ImpactNormal.Z > 0.7f)
        {
            OutPoint = Hit.ImpactPoint;
            OutFaceToward = Origin;
            return true;
        }
    }
    // Last resort: the origin itself, nudged so several fallbacks don't stack.
    OutPoint = Origin + FVector(Stream.FRandRange(-200, 200), Stream.FRandRange(-200, 200), 0);
    OutFaceToward = Origin + FVector(500, 0, 0);
    return bOriginOnNav || !Origin.IsZero();
}

AReflectionsStoryMarker* UReflectionsStoryMarkerSubsystem::PlaceFallback(FName Name)
{
    UWorld* World = GetWorld();
    if (!World || !World->HasBegunPlay())
    {
        return nullptr;
    }
    FString Kind, Key;
    AReflectionsStoryMarker::SplitName(Name, Kind, Key);

    EReflectionsWorld Side = EReflectionsWorld::Red;
    if (const EReflectionsWorld* Hint = SideHints.Find(Name))
    {
        Side = *Hint;
    }
    else if (!SideFromKey(Key, Side))
    {
        if (const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this))
        {
            Side = Progress->GetCurrentWorld();
        }
        if (const UReflectionsWorldJumpWorldSubsystem* Jump = UReflectionsWorldJumpWorldSubsystem::Get(this))
        {
            if (!Jump->IsWorldJumpActive())
            {
                Side = EReflectionsWorld::Red;
            }
        }
    }

    FVector Point, FaceToward;
    if (!FindFallbackPoint(Name, Kind, Key, Side, Point, FaceToward))
    {
        FailedFallbacks.Add(Name);
        UE_LOG(LogReflectionsStory, Warning, TEXT("Story marker %s is missing and no fallback spot was found."), *Name.ToString());
        return nullptr;
    }
    FVector Facing = FaceToward - Point;
    Facing.Z = 0.0;
    const FRotator Rotation = Facing.IsNearlyZero() ? FRotator::ZeroRotator : Facing.Rotation();

    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Params.Name = MakeUniqueObjectName(World->PersistentLevel, AReflectionsStoryMarker::StaticClass(), FName(*FString::Printf(TEXT("AutoMarker_%s"), *Name.ToString())));
    AReflectionsStoryMarker* Marker = World->SpawnActor<AReflectionsStoryMarker>(AReflectionsStoryMarker::StaticClass(), Point, Rotation, Params);
    if (!Marker)
    {
        FailedFallbacks.Add(Name);
        return nullptr;
    }
    Marker->MarkerName = Name;
    Marker->bAutoPlaced = true;
    Marker->Side = Side == EReflectionsWorld::Gray ? EReflectionsMarkerSide::Pewterside
        : Side == EReflectionsWorld::White ? EReflectionsMarkerSide::Frostside : EReflectionsMarkerSide::Giltside;
    UE_LOG(LogReflectionsStory, Log, TEXT("Story marker %s auto-placed at %s (the map has none; drop a Reflections Story Marker named %s to fix)."),
        *Name.ToString(), *Point.ToCompactString(), *Name.ToString());
    Register(Marker);  // BeginPlay already ran inside SpawnActor, before the name was set
    return Marker;
}

FString UReflectionsStoryMarkerSubsystem::Describe() const
{
    FString Out = FString::Printf(TEXT("%d story markers (fallback %s):\n"), Markers.Num(), ReflectionsStoryMarkerCVars::Fallback ? TEXT("on") : TEXT("off"));
    for (const TWeakObjectPtr<AReflectionsStoryMarker>& Weak : Markers)
    {
        const AReflectionsStoryMarker* M = Weak.Get();
        if (!M)
        {
            continue;
        }
        FString Names;
        for (const FName& N : M->GetNames())
        {
            Names += (Names.IsEmpty() ? TEXT("") : TEXT(", ")) + N.ToString();
        }
        Out += FString::Printf(TEXT("  %s%s at %s\n"), *Names, M->bAutoPlaced ? TEXT(" [auto]") : TEXT(""), *M->GetActorLocation().ToCompactString());
    }
    return Out;
}

// ---- Console --------------------------------------------------------------------------------------------------

#if !UE_BUILD_SHIPPING
static FAutoConsoleCommandWithWorld GStoryMarkersCmd(TEXT("Story.Markers"), TEXT("List every story marker in the map."),
    FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
    {
        if (const UReflectionsStoryMarkerSubsystem* Markers = UReflectionsStoryMarkerSubsystem::Get(World))
        {
            UE_LOG(LogReflectionsStory, Display, TEXT("%s"), *Markers->Describe());
        }
    }));

static FAutoConsoleCommandWithWorldAndArgs GStoryMarkerFindCmd(TEXT("Story.FindMarker"), TEXT("Story.FindMarker <Name>: find (or auto-place) a marker."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (Args.Num() < 1) return;
        if (UReflectionsStoryMarkerSubsystem* Markers = UReflectionsStoryMarkerSubsystem::Get(World))
        {
            const AReflectionsStoryMarker* M = Markers->Find(FName(*Args[0]));
            UE_LOG(LogReflectionsStory, Display, TEXT("%s -> %s"), *Args[0], M ? *M->GetActorLocation().ToCompactString() : TEXT("(none)"));
        }
    }));

#endif
