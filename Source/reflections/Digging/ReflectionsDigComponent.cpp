#include "Digging/ReflectionsDigComponent.h"

#include "CollisionQueryParams.h"
#include "Digging/ReflectionsDigSpot.h"
#include "Engine/EngineTypes.h"
#include "Engine/HitResult.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputCoreTypes.h"
#include "InputMappingContext.h"
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
    if (Spot == nullptr || !Spot->DigOnce())
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
    BindControls();
}

void UReflectionsDigComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (APawn* Pawn = Cast<APawn>(GetOwner()))
    {
        Pawn->ReceiveControllerChangedDelegate.RemoveDynamic(this, &UReflectionsDigComponent::HandleControllerChanged);
    }
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
        DigContext = NewObject<UInputMappingContext>(this, TEXT("IMC_Digging"));
        DigContext->MapKey(DigAction, EKeys::G);
    }

    DigInput = NewObject<UEnhancedInputComponent>(PC, MakeUniqueObjectName(PC, UEnhancedInputComponent::StaticClass(), TEXT("DigInput")));
    DigInput->RegisterComponent();
    DigInput->BindAction(DigAction, ETriggerEvent::Started, this, &UReflectionsDigComponent::OnDigAction);
    PC->PushInputComponent(DigInput);
    Subsystem->AddMappingContext(DigContext, 1);
    BoundController = PC;
    BoundPlayer = Player;
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
