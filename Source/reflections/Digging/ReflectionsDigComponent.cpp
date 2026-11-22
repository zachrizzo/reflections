#include "Digging/ReflectionsDigComponent.h"

#include "CollisionQueryParams.h"
#include "Components/CapsuleComponent.h"
#include "Digging/ReflectionsDigSpot.h"
#include "Digging/ReflectionsDigSubsystem.h"
#include "Digging/ReflectionsDigTypes.h"
#include "Engine/EngineTypes.h"
#include "Engine/HitResult.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/Character.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputCoreTypes.h"
#include "InputMappingContext.h"
#include "Math/Box.h"
#include "Math/UnrealMathUtility.h"
#include "Save/ReflectionsSaveGame.h"
#include "UObject/UObjectGlobals.h"

UReflectionsDigComponent::UReflectionsDigComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

UReflectionsDigComponent* UReflectionsDigComponent::EnsureOnPawn(APawn* Pawn)
{
    if (Pawn == nullptr)
    {
        return nullptr;
    }
    if (UReflectionsDigComponent* Existing = Pawn->FindComponentByClass<UReflectionsDigComponent>())
    {
        return Existing;
    }
    UReflectionsDigComponent* Added = NewObject<UReflectionsDigComponent>(Pawn,
        MakeUniqueObjectName(Pawn, StaticClass(), TEXT("DigComponent")));
    Pawn->AddInstanceComponent(Added);
    // Registering on a pawn that has already begun play also runs the component's BeginPlay.
    Added->RegisterComponent();
    return Added;
}

void UReflectionsDigComponent::ComputeReachTrace(const FVector& ViewLocation, const FVector& ViewDirection,
    const FVector& PawnLocation, float ReachCm, FVector& OutStart, FVector& OutEnd)
{
    const double Forward = FMath::Max(0.0, FVector::DotProduct(PawnLocation - ViewLocation, ViewDirection));
    OutStart = ViewLocation + ViewDirection * Forward;
    OutEnd = OutStart + ViewDirection * ReachCm;
}

bool UReflectionsDigComponent::TryDig()
{
    FHitResult Hit;
    if (!TraceReach(Hit))
    {
        return false;
    }
    AReflectionsDigSpot* Spot = Cast<AReflectionsDigSpot>(Hit.GetActor());
    if (Spot == nullptr)
    {
        // Whether the hit is diggable ground is the subsystem's call; with no terrain in the world it never is.
        UWorld* World = GetWorld();
        UReflectionsDigSubsystem* Subsystem = World != nullptr ? World->GetSubsystem<UReflectionsDigSubsystem>() : nullptr;
        return Subsystem != nullptr && Subsystem->TryStampAtHit(Hit, EReflectionsDigMode::Remove);
    }
    if (!Spot->DigOnce())
    {
        return false;
    }
    if (Spot->SpotId != NAME_None)
    {
        const FName Id = Spot->SpotId;
        const uint8 Stage = static_cast<uint8>(FMath::Clamp(Spot->GetStage(), 0, 255));
        // A refused update logs its own warning; the dig itself still happened.
        ReflectionsSave::Update([Id, Stage](UReflectionsSaveGame& Save) { Save.DigSpotStages.Add(Id, Stage); });
    }
    return true;
}

bool UReflectionsDigComponent::TryFill()
{
    FHitResult Hit;
    // A fill reaching into the pawn would bury it in solid ground.
    if (!TraceReach(Hit) || StampWouldReachPawn(Hit.ImpactPoint))
    {
        return false;
    }
    UWorld* World = GetWorld();
    UReflectionsDigSubsystem* Subsystem = World != nullptr ? World->GetSubsystem<UReflectionsDigSubsystem>() : nullptr;
    return Subsystem != nullptr && Subsystem->TryStampAtHit(Hit, EReflectionsDigMode::Add);
}

bool UReflectionsDigComponent::IsFillMapped() const
{
    const ULocalPlayer* Player = BoundPlayer.Get();
    const UEnhancedInputLocalPlayerSubsystem* Input = Player != nullptr ? Player->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
    if (Input != nullptr && FillContext != nullptr)
    {
        return Input->HasMappingContext(FillContext);
    }
    return bWorldHasTerrain;
}

bool UReflectionsDigComponent::StampWouldReachPawn(const FVector& Center) const
{
    const APawn* Pawn = Cast<APawn>(GetOwner());
    if (Pawn == nullptr)
    {
        return false;
    }
    const double StampRadius = ReflectionsDig::StampRadiusCm;
    const ACharacter* Character = Cast<ACharacter>(Pawn);
    if (const UCapsuleComponent* Capsule = Character != nullptr ? Character->GetCapsuleComponent() : nullptr)
    {
        // Sphere against capsule: the distance from the sphere's centre to the capsule's axis segment, against the
        // two radii added.
        const FVector Middle = Capsule->GetComponentLocation();
        const FVector AxisHalf = Capsule->GetUpVector() * Capsule->GetScaledCapsuleHalfHeight_WithoutHemisphere();
        const FVector OnAxis = FMath::ClosestPointOnSegment(Center, Middle - AxisHalf, Middle + AxisHalf);
        return FVector::Dist(Center, OnAxis) < StampRadius + Capsule->GetScaledCapsuleRadius();
    }
    // Any other pawn: sphere against the box of its colliding components. With nothing colliding there is nothing to bury.
    const FBox Bounds = Pawn->GetComponentsBoundingBox(/*bNonColliding=*/ false);
    return Bounds.IsValid && Bounds.ComputeSquaredDistanceToPoint(Center) < FMath::Square(StampRadius);
}

bool UReflectionsDigComponent::TraceReach(FHitResult& OutHit) const
{
    APawn* Pawn = Cast<APawn>(GetOwner());
    UWorld* World = GetWorld();
    if (Pawn == nullptr || World == nullptr)
    {
        return false;
    }

    FVector ViewLocation;
    FRotator ViewRotation;
    if (const AController* Controller = Pawn->GetController())
    {
        Controller->GetPlayerViewPoint(ViewLocation, ViewRotation);
    }
    else
    {
        Pawn->GetActorEyesViewPoint(ViewLocation, ViewRotation);
    }

    const FVector PawnLocation = Pawn->GetActorLocation();
    FVector Start;
    FVector End;
    ComputeReachTrace(ViewLocation, ViewRotation.Vector(), PawnLocation, ReachCm, Start, End);

    // Like the spell aim: skip the pawn and everything it carries.
    FCollisionQueryParams Params(SCENE_QUERY_STAT(ReflectionsDigTrace), /*bTraceComplex=*/ false, Pawn);
    TArray<AActor*> Attached;
    Pawn->GetAttachedActors(Attached, /*bResetArray=*/ true, /*bRecursivelyIncludeAttachedActors=*/ true);
    Params.AddIgnoredActors(Attached);
    if (!World->LineTraceSingleByChannel(OutHit, Start, End, ECC_Visibility, Params))
    {
        return false;
    }
    return FVector::Dist(OutHit.ImpactPoint, PawnLocation) <= ReachCm;
}

void UReflectionsDigComponent::BeginPlay()
{
    Super::BeginPlay();
    if (APawn* Pawn = Cast<APawn>(GetOwner()))
    {
        // Covers a pawn possessed after BeginPlay and a controller swapped later.
        Pawn->ReceiveControllerChangedDelegate.AddUniqueDynamic(this, &UReflectionsDigComponent::HandleControllerChanged);
    }
    // H is mapped only while the world has a dig terrain; the subsystem says when that changes.
    if (UWorld* World = GetWorld())
    {
        if (UReflectionsDigSubsystem* Subsystem = World->GetSubsystem<UReflectionsDigSubsystem>())
        {
            TerrainSource = Subsystem;
            TerrainChangedHandle = Subsystem->OnTerrainRegisteredChanged.AddUObject(this, &UReflectionsDigComponent::HandleTerrainRegisteredChanged);
            bWorldHasTerrain = Subsystem->HasTerrain();
        }
    }
    BindControls();
}

void UReflectionsDigComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (APawn* Pawn = Cast<APawn>(GetOwner()))
    {
        Pawn->ReceiveControllerChangedDelegate.RemoveDynamic(this, &UReflectionsDigComponent::HandleControllerChanged);
    }
    if (UReflectionsDigSubsystem* Subsystem = TerrainSource.Get())
    {
        Subsystem->OnTerrainRegisteredChanged.Remove(TerrainChangedHandle);
    }
    TerrainSource.Reset();
    TerrainChangedHandle.Reset();
    UnbindControls();
    Super::EndPlay(Reason);
}

void UReflectionsDigComponent::HandleControllerChanged(APawn* Pawn, AController* OldController, AController* NewController)
{
    UnbindControls();
    BindControls();
}

void UReflectionsDigComponent::BindControls()
{
    APawn* Pawn = Cast<APawn>(GetOwner());
    APlayerController* PC = Pawn && Pawn->IsLocallyControlled() ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
    if (PC == nullptr || BoundController.IsValid())
    {
        return;
    }
    ULocalPlayer* Player = PC->GetLocalPlayer();
    UEnhancedInputLocalPlayerSubsystem* Subsystem = Player ? Player->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
    if (Subsystem == nullptr)
    {
        return;
    }

    // Built at runtime, like the spell controls, so digging needs no input assets; priority 1 sits above IMC_Sandbox.
    if (DigContext == nullptr)
    {
        DigAction = NewObject<UInputAction>(this, TEXT("IA_Dig"));
        DigAction->ValueType = EInputActionValueType::Boolean;
        DigAction->bConsumeInput = true;
        FillAction = NewObject<UInputAction>(this, TEXT("IA_Fill"));
        FillAction->ValueType = EInputActionValueType::Boolean;
        FillAction->bConsumeInput = true;
        DigContext = NewObject<UInputMappingContext>(this, TEXT("IMC_Digging"));
        DigContext->MapKey(DigAction, EKeys::G);
        // H in a context of its own: it is added only while the world has a terrain, so no other map loses the key.
        FillContext = NewObject<UInputMappingContext>(this, TEXT("IMC_DigFill"));
        FillContext->MapKey(FillAction, EKeys::H);
    }

    DigInput = NewObject<UEnhancedInputComponent>(PC, MakeUniqueObjectName(PC, UEnhancedInputComponent::StaticClass(), TEXT("DigInput")));
    DigInput->RegisterComponent();
    DigInput->BindAction(DigAction, ETriggerEvent::Started, this, &UReflectionsDigComponent::OnDigAction);
    DigInput->BindAction(FillAction, ETriggerEvent::Started, this, &UReflectionsDigComponent::OnFillAction);
    PC->PushInputComponent(DigInput);
    Subsystem->AddMappingContext(DigContext, 1);
    BoundController = PC;
    BoundPlayer = Player;
    ApplyFillMapping();
}

void UReflectionsDigComponent::ApplyFillMapping()
{
    ULocalPlayer* Player = BoundPlayer.Get();
    UEnhancedInputLocalPlayerSubsystem* Input = Player != nullptr ? Player->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
    if (Input == nullptr || FillContext == nullptr)
    {
        return;
    }
    if (bWorldHasTerrain && !Input->HasMappingContext(FillContext))
    {
        Input->AddMappingContext(FillContext, 1);
    }
    else if (!bWorldHasTerrain && Input->HasMappingContext(FillContext))
    {
        Input->RemoveMappingContext(FillContext);
    }
}

void UReflectionsDigComponent::HandleTerrainRegisteredChanged()
{
    const UReflectionsDigSubsystem* Subsystem = TerrainSource.Get();
    bWorldHasTerrain = Subsystem != nullptr && Subsystem->HasTerrain();
    ApplyFillMapping();
}

void UReflectionsDigComponent::UnbindControls()
{
    if (APlayerController* PC = BoundController.Get())
    {
        if (DigInput != nullptr)
        {
            PC->PopInputComponent(DigInput);
        }
    }
    // Through the local player, not the controller: the context must go even if the controller was destroyed first.
    if (ULocalPlayer* Player = BoundPlayer.Get())
    {
        if (UEnhancedInputLocalPlayerSubsystem* Subsystem = Player->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
        {
            Subsystem->RemoveMappingContext(DigContext);
            if (FillContext != nullptr && Subsystem->HasMappingContext(FillContext))
            {
                Subsystem->RemoveMappingContext(FillContext);
            }
        }
    }
    if (DigInput != nullptr)
    {
        DigInput->DestroyComponent();
        DigInput = nullptr;
    }
    BoundController.Reset();
    BoundPlayer.Reset();
}

void UReflectionsDigComponent::OnDigAction(const FInputActionValue& Value)
{
    TryDig();
}

void UReflectionsDigComponent::OnFillAction(const FInputActionValue& Value)
{
    TryFill();
}
