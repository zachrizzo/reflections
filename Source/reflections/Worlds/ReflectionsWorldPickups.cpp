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
#include "Worlds/ReflectionsWorldLibrary.h"

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

void AReflectionsWorldPickup::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    ApplyLook();
}

void AReflectionsWorldPickup::ApplyLook()
{
    const FReflectionsPickupLook* Look = GetLook();
    UStaticMesh* LookMesh = Look ? Look->Mesh.Get() : nullptr;
    if (!LookMesh || !Mesh)
    {
        return;
    }
    if (Mesh->GetStaticMesh() != LookMesh)
    {
        Mesh->SetStaticMesh(LookMesh);
    }
    // The gray box forced the basic shape material; the real mesh keeps its own.
    Mesh->EmptyOverrideMaterials();
    Material = nullptr;
    bHasLook = true;

    const FBox Bounds = LookMesh->GetBoundingBox();
    const float Longest = Bounds.GetSize().GetMax();
    const float Scale = (Look->DisplaySize > 0.0f && Longest > KINDA_SMALL_NUMBER) ? Look->DisplaySize / Longest : 1.0f;
    const FQuat Turn = Look->Rotation.Quaternion();
    Mesh->SetRelativeScale3D(FVector(Scale));
    Mesh->SetRelativeRotation(Turn);
    // Real props pivot at the bottom; centre the mesh on the spinner so it turns about its middle.
    Mesh->SetRelativeLocation(-Turn.RotateVector(Bounds.GetCenter() * Scale));
}

void AReflectionsWorldPickup::BeginPlay()
{
    Super::BeginPlay();
    ApplyLook();
    SpinnerBase = Spinner->GetRelativeLocation();
    BaseGlowIntensity = Glow ? Glow->Intensity : 0.0f;
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
    // A real mesh keeps its own colours; only the gray box is tinted.
    if (!Material && Mesh && !bHasLook)
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
    if (Glow && GlintStrength > 0.0f && BaseGlowIntensity > 0.0f)
    {
        // A short, sharp flare once per period: sin^24 is near zero most of the cycle.
        const float Wave = FMath::Max(0.0f, FMath::Sin(Clock * UE_TWO_PI / FMath::Max(GlintPeriod, 0.5f)));
        Glow->SetIntensity(BaseGlowIntensity * (1.0f + GlintStrength * FMath::Pow(Wave, 24.0f)));
    }
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

const FReflectionsPickupLook* AReflectionsCoinPickup::GetLook() const
{
    const UReflectionsWorldJumpConfig* Config = UReflectionsWorldJumpConfig::Get(this);
    const FReflectionsWorldInfo* Info = Config ? Config->FindWorld(CoinWorld) : nullptr;
    return Info ? &Info->CoinLook : nullptr;
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
    Progress->ShowWorldMessage(FText::Format(LOCTEXT("GotCoin", "A {0} shard: it lets you step through into {0} once."),
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

const FReflectionsPickupLook* AReflectionsBookPagePickup::GetLook() const
{
    const UReflectionsWorldJumpConfig* Config = UReflectionsWorldJumpConfig::Get(this);
    return Config ? &Config->PageLook : nullptr;
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
        Progress->ShowWorldMessage(FText::Format(LOCTEXT("GotPage", "{0}  ({1} / {2})"), GetDisplayTitle(),
            Progress->GetPageCount(), Progress->GetPagesForBook()));
    }
    return true;
}

FText AReflectionsBookPagePickup::GetDisplayTitle() const
{
    if (!PageTitle.IsEmpty())
    {
        return PageTitle;
    }
    const UReflectionsWorldJumpConfig* Config = UReflectionsWorldJumpConfig::Get(this);
    if (!Config)
    {
        return LOCTEXT("PageDefault", "A mirror page");
    }
    const EReflectionsWorld Side = UReflectionsWorldLibrary::GetWorldAtLocation(this, GetActorLocation());
    const FReflectionsWorldInfo* Info = Config->FindWorld(Side);
    const FText Source = (Info && !Info->PageSource.IsEmpty()) ? Info->PageSource : Config->GetWorldName(Side);
    return FText::Format(LOCTEXT("PageFrom", "A page from {0}"), Source);
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
    KeyName = LOCTEXT("RedTowerKeyName", "the Gilt Tower key");
}

const FReflectionsPickupLook* AReflectionsKeyPickup::GetLook() const
{
    const UReflectionsWorldJumpConfig* Config = UReflectionsWorldJumpConfig::Get(this);
    return Config ? &Config->KeyLook : nullptr;
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
