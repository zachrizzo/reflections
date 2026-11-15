#include "Worlds/ReflectionsSealedDoor.h"

#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"
#include "Worlds/ReflectionsWorldJumpConfig.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"

#define LOCTEXT_NAMESPACE "ReflectionsWorlds"

AReflectionsSealedDoor::AReflectionsSealedDoor()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = false;

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    Panel = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Panel"));
    Panel->SetupAttachment(Root);
    Panel->SetCollisionProfileName(TEXT("BlockAll"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube"));
    if (Cube.Succeeded())
    {
        Panel->SetStaticMesh(Cube.Object);
    }
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> ShapeMaterial(TEXT("/Engine/BasicShapes/BasicShapeMaterial"));
    if (ShapeMaterial.Succeeded())
    {
        Panel->SetMaterial(0, ShapeMaterial.Object);
    }

    Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
    Trigger->SetupAttachment(Root);
    Trigger->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
    Trigger->SetGenerateOverlapEvents(true);

    SealLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("SealLight"));
    SealLight->SetupAttachment(Root);
    SealLight->SetIntensity(2500.0f);
    SealLight->SetAttenuationRadius(420.0f);
    SealLight->SetLightColor(FLinearColor(1.0f, 0.12f, 0.06f));
    SealLight->SetCastShadows(false);

    LockedMessage = LOCTEXT("DoorLocked", "Sealed. Its key is hidden somewhere in Giltside.");
    OpenedMessage = LOCTEXT("DoorOpened", "The seal breaks.");
}

void AReflectionsSealedDoor::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    Panel->SetRelativeScale3D(DoorSize / 100.0f);
    Panel->SetRelativeLocation(FVector(0.0f, 0.0f, DoorSize.Z * 0.5f));
    Trigger->SetBoxExtent(FVector(DoorSize.X * 0.5f + 160.0f, DoorSize.Y * 0.5f + 40.0f, DoorSize.Z * 0.5f), false);
    Trigger->SetRelativeLocation(FVector(0.0f, 0.0f, DoorSize.Z * 0.5f));
    SealLight->SetRelativeLocation(FVector(DoorSize.X * 0.5f + 60.0f, 0.0f, DoorSize.Z * 0.6f));
}

void AReflectionsSealedDoor::BeginPlay()
{
    Super::BeginPlay();
    PanelMaterial = Panel->CreateAndSetMaterialInstanceDynamic(0);
    if (PanelMaterial)
    {
        PanelMaterial->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.20f, 0.03f, 0.03f));
    }
    Trigger->OnComponentBeginOverlap.AddDynamic(this, &AReflectionsSealedDoor::HandleOverlap);
}

void AReflectionsSealedDoor::HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
    UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
    const APawn* Pawn = Cast<APawn>(OtherActor);
    if (bOpen || !Pawn || !Pawn->IsPlayerControlled())
    {
        return;
    }
    UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    if (!Progress)
    {
        return;
    }
    if (RequiredKey.IsNone() || Progress->HasKey(RequiredKey))
    {
        Open();
        Progress->ShowWorldMessage(OpenedMessage);
        return;
    }
    const double Now = GetWorld()->GetTimeSeconds();
    if (Now - LastLockedMessageTime > 2.0)
    {
        LastLockedMessageTime = Now;
        Progress->ShowWorldMessage(LockedMessage);
    }
}

void AReflectionsSealedDoor::Open()
{
    if (bOpen)
    {
        return;
    }
    bOpen = true;
    Panel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    SealLight->SetLightColor(FLinearColor(1.0f, 0.75f, 0.35f));
    if (PanelMaterial)
    {
        PanelMaterial->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.55f, 0.32f, 0.12f));
    }
    SetActorTickEnabled(true);
    if (const UReflectionsWorldJumpConfig* Config = UReflectionsWorldJumpConfig::Get(this))
    {
        if (Config->DoorUnsealSound)
        {
            UGameplayStatics::PlaySoundAtLocation(this, Config->DoorUnsealSound, GetActorLocation() + FVector(0.0f, 0.0f, DoorSize.Z * 0.5f));
        }
    }
    OnOpened.Broadcast();
}

void AReflectionsSealedDoor::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    OpenAlpha = FMath::Min(1.0f, OpenAlpha + DeltaSeconds / OpenTime);
    const float Eased = FMath::InterpEaseInOut(0.0f, 1.0f, OpenAlpha, 2.0f);
    Panel->SetRelativeLocation(FVector(0.0f, 0.0f, DoorSize.Z * 0.5f + Eased * (DoorSize.Z + 10.0f)));
    if (OpenAlpha >= 1.0f)
    {
        SetActorTickEnabled(false);
    }
}

#undef LOCTEXT_NAMESPACE
