#include "Worlds/ReflectionsWorldPickups.h"

#include "Components/PointLightComponent.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"
#include "Worlds/ReflectionsWorldJumpConfig.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"

#define LOCTEXT_NAMESPACE "ReflectionsWorlds"

AReflectionsWorldPickup::AReflectionsWorldPickup()
{
    PrimaryActorTick.bCanEverTick = true;

    Trigger = CreateDefaultSubobject<USphereComponent>(TEXT("Trigger"));
    Trigger->InitSphereRadius(90.0f);
    Trigger->SetCollisionProfileName(TEXT("OverlapAllDynamic"));
    Trigger->SetGenerateOverlapEvents(true);
    SetRootComponent(Trigger);

    Spinner = CreateDefaultSubobject<USceneComponent>(TEXT("Spinner"));
    Spinner->SetupAttachment(Trigger);

    Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
    Mesh->SetupAttachment(Spinner);
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Mesh->SetGenerateOverlapEvents(false);
    Mesh->SetCastShadow(true);
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> ShapeMaterial(TEXT("/Engine/BasicShapes/BasicShapeMaterial"));
    if (ShapeMaterial.Succeeded())
    {
        Mesh->SetMaterial(0, ShapeMaterial.Object);
    }

    Glow = CreateDefaultSubobject<UPointLightComponent>(TEXT("Glow"));
    Glow->SetupAttachment(Spinner);
    Glow->SetIntensity(1800.0f);
    Glow->SetAttenuationRadius(260.0f);
    Glow->SetCastShadows(false);
}

void AReflectionsWorldPickup::BeginPlay()
{
    Super::BeginPlay();
    SpinnerBase = Spinner->GetRelativeLocation();
    Clock = FMath::FRand() * 10.0f;
    SetGlowColor(GetDefaultColor());
    Trigger->OnComponentBeginOverlap.AddDynamic(this, &AReflectionsWorldPickup::HandleOverlap);

    // A pickup dropped on top of the player still counts.
    TArray<AActor*> Overlapping;
    Trigger->GetOverlappingActors(Overlapping, APawn::StaticClass());
    for (AActor* Actor : Overlapping)
    {
        FHitResult None;
        HandleOverlap(Trigger, Actor, nullptr, 0, false, None);
    }
}

void AReflectionsWorldPickup::SetGlowColor(const FLinearColor& Color)
{
    if (!Material && Mesh)
    {
        Material = Mesh->CreateAndSetMaterialInstanceDynamic(0);
    }
    if (Material)
    {
        Material->SetVectorParameterValue(TEXT("Color"), Color);
    }
    if (Glow)
    {
        Glow->SetLightColor(Color);
    }
}

void AReflectionsWorldPickup::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    Clock += DeltaSeconds;
    Spinner->SetRelativeLocation(SpinnerBase + FVector(0.0f, 0.0f, FMath::Sin(Clock * 2.2f) * BobHeight));
    Spinner->AddRelativeRotation(FRotator(0.0f, SpinDegreesPerSecond * DeltaSeconds, 0.0f));
}

void AReflectionsWorldPickup::HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
    UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
    APawn* Pawn = Cast<APawn>(OtherActor);
    if (bCollected || !Pawn || !Pawn->IsPlayerControlled())
    {
        return;
    }
    if (GiveTo(Pawn))
    {
        bCollected = true;
        OnPickedUp.Broadcast(Pawn);
        Destroy();
    }
}

// ---- Coin ----------------------------------------------------------------------------------------------------

AReflectionsCoinPickup::AReflectionsCoinPickup()
{
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder"));
    if (Cylinder.Succeeded())
    {
        Mesh->SetStaticMesh(Cylinder.Object);
    }
    // Stand the disc on its edge so it reads as a coin while it spins.
    Mesh->SetRelativeRotation(FRotator(0.0f, 0.0f, 90.0f));
    Mesh->SetRelativeScale3D(FVector(0.42f, 0.42f, 0.06f));
    Spinner->SetRelativeLocation(FVector(0.0f, 0.0f, 20.0f));
    SpinDegreesPerSecond = 160.0f;
}

void AReflectionsCoinPickup::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    if (Mesh && Glow)
    {
        // Preview the London colour in the editor.
        Glow->SetLightColor(GetDefaultColor());
    }
}

FLinearColor AReflectionsCoinPickup::GetDefaultColor() const
{
    const UReflectionsWorldJumpConfig* Config = UReflectionsWorldJumpConfig::Get(this);
    const FReflectionsWorldInfo* Info = Config ? Config->FindWorld(CoinWorld) : nullptr;
    return Info ? Info->CoinColor : FLinearColor(1.0f, 0.8f, 0.3f);
}

bool AReflectionsCoinPickup::GiveTo(APawn* Collector)
{
    UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    if (!Progress)
    {
        return false;
    }
    Progress->AwardCoin(CoinWorld, Count);
    const UReflectionsWorldJumpConfig* Config = UReflectionsWorldJumpConfig::Get(this);
    Progress->ShowWorldMessage(FText::Format(LOCTEXT("GotCoin", "A {0} coin: it pays for one crossing into {0}."),
        Config ? Config->GetWorldName(CoinWorld) : FText::GetEmpty()));
    return true;
}

// ---- Page ----------------------------------------------------------------------------------------------------

AReflectionsBookPagePickup::AReflectionsBookPagePickup()
{
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube"));
    if (Cube.Succeeded())
    {
        Mesh->SetStaticMesh(Cube.Object);
    }
    Mesh->SetRelativeScale3D(FVector(0.02f, 0.34f, 0.46f));
    Mesh->SetRelativeRotation(FRotator(0.0f, 0.0f, 8.0f));
    Spinner->SetRelativeLocation(FVector(0.0f, 0.0f, 40.0f));
    SpinDegreesPerSecond = 45.0f;
    Glow->SetIntensity(2600.0f);
}

bool AReflectionsBookPagePickup::GiveTo(APawn* Collector)
{
    UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    if (!Progress)
    {
        return false;
    }
    const FName Id = PageId.IsNone() ? GetFName() : PageId;
    if (!Progress->AddPage(Id))
    {
        return true;
    }
    if (!Progress->IsBookComplete())
    {
        const FText Title = PageTitle.IsEmpty() ? LOCTEXT("PageDefault", "A page of the book") : PageTitle;
        Progress->ShowWorldMessage(FText::Format(LOCTEXT("GotPage", "{0}  ({1} / {2})"), Title,
            Progress->GetPageCount(), Progress->GetPagesForBook()));
    }
    return true;
}

// ---- Key -----------------------------------------------------------------------------------------------------

AReflectionsKeyPickup::AReflectionsKeyPickup()
{
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube"));
    if (Cube.Succeeded())
    {
        Mesh->SetStaticMesh(Cube.Object);
    }
    Mesh->SetRelativeScale3D(FVector(0.08f, 0.08f, 0.42f));
    Mesh->SetRelativeRotation(FRotator(0.0f, 0.0f, 35.0f));
    Spinner->SetRelativeLocation(FVector(0.0f, 0.0f, 30.0f));
    KeyName = LOCTEXT("RedTowerKeyName", "the Red Tower key");
}

bool AReflectionsKeyPickup::GiveTo(APawn* Collector)
{
    UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    if (!Progress)
    {
        return false;
    }
    Progress->AddKey(KeyId);
    Progress->ShowWorldMessage(FText::Format(LOCTEXT("GotKey", "You found {0}."), KeyName));
    return true;
}

#undef LOCTEXT_NAMESPACE
