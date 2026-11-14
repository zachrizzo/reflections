#include "Worlds/ReflectionsWorldAnchor.h"

#include "Components/BillboardComponent.h"
#include "Components/BoxComponent.h"
#include "Components/PostProcessComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/Texture2D.h"
#include "UObject/ConstructorHelpers.h"
#include "Worlds/ReflectionsWorldJumpConfig.h"

AReflectionsWorldAnchor::AReflectionsWorldAnchor()
{
    PrimaryActorTick.bCanEverTick = false;

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    Bounds = CreateDefaultSubobject<UBoxComponent>(TEXT("Bounds"));
    Bounds->SetupAttachment(Root);
    Bounds->SetBoxExtent(FVector(60000.0f, 60000.0f, 30000.0f), false);
    // Query-only with every channel ignored: nothing hits it, but the colour grade can test against it.
    Bounds->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Bounds->SetCollisionResponseToAllChannels(ECR_Ignore);
    Bounds->SetCanEverAffectNavigation(false);
    Bounds->SetGenerateOverlapEvents(false);
    Bounds->SetHiddenInGame(true);
    Bounds->ShapeColor = FColor(255, 200, 60);
    Bounds->SetLineThickness(20.0f);

    Grade = CreateDefaultSubobject<UPostProcessComponent>(TEXT("Grade"));
    Grade->SetupAttachment(Bounds);
    Grade->bUnbound = false;
    Grade->BlendRadius = 400.0f;
    Grade->Priority = 1.0f;

    Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
    Label->SetupAttachment(Root);
    Label->SetRelativeLocation(FVector(0.0f, 0.0f, 120.0f));
    Label->SetHorizontalAlignment(EHTA_Center);
    Label->SetWorldSize(60.0f);
    Label->SetHiddenInGame(true);

#if WITH_EDITORONLY_DATA
    Sprite = CreateEditorOnlyDefaultSubobject<UBillboardComponent>(TEXT("Sprite"));
    if (Sprite)
    {
        static ConstructorHelpers::FObjectFinder<UTexture2D> Icon(TEXT("/Engine/EditorResources/S_Note"));
        if (Icon.Succeeded())
        {
            Sprite->SetSprite(Icon.Object);
        }
        Sprite->SetupAttachment(Root);
        Sprite->bIsScreenSizeScaled = true;
    }
#endif
    RefreshLabel();
}

bool AReflectionsWorldAnchor::ContainsLocation(const FVector& Location) const
{
    if (!Bounds)
    {
        return false;
    }
    const FVector Local = Bounds->GetComponentTransform().InverseTransformPosition(Location);
    const FVector Extent = Bounds->GetUnscaledBoxExtent();
    return FMath::Abs(Local.X) <= Extent.X && FMath::Abs(Local.Y) <= Extent.Y && FMath::Abs(Local.Z) <= Extent.Z;
}

void AReflectionsWorldAnchor::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    RefreshLabel();
    RefreshGrade();
}

void AReflectionsWorldAnchor::BeginPlay()
{
    Super::BeginPlay();
    RefreshGrade();
}

void AReflectionsWorldAnchor::RefreshGrade()
{
    if (!Grade)
    {
        return;
    }
    const UReflectionsWorldJumpConfig* Config = ConfigOverride ? ConfigOverride.Get() : UReflectionsWorldJumpConfig::Get(this);
    const FReflectionsWorldInfo* Info = Config ? Config->FindWorld(World) : nullptr;
    Grade->bEnabled = bApplyWorldGrade && Info != nullptr;
    if (Info)
    {
        Grade->Settings = Info->Grade;
    }
}

#if WITH_EDITOR
void AReflectionsWorldAnchor::PostEditChangeProperty(FPropertyChangedEvent& Event)
{
    Super::PostEditChangeProperty(Event);
    RefreshLabel();
    RefreshGrade();
}
#endif

void AReflectionsWorldAnchor::RefreshLabel()
{
    if (!Label)
    {
        return;
    }
    const FText Name = StaticEnum<EReflectionsWorld>()->GetDisplayNameTextByValue(static_cast<int64>(World));
    Label->SetText(FText::Format(NSLOCTEXT("ReflectionsWorlds", "AnchorLabel", "{0} anchor"), Name));
    switch (World)
    {
    case EReflectionsWorld::Gray:  Label->SetTextRenderColor(FColor(170, 172, 180)); break;
    case EReflectionsWorld::Red:   Label->SetTextRenderColor(FColor(235, 50, 35)); break;
    case EReflectionsWorld::White: Label->SetTextRenderColor(FColor(245, 245, 255)); break;
    }
}
