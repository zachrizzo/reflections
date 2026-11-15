#include "Quests/ReflectionsQuestItem.h"

#include "GameFramework/Pawn.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Quests/ReflectionsQuestSubsystem.h"

#define LOCTEXT_NAMESPACE "ReflectionsQuests"

AReflectionsQuestItem::AReflectionsQuestItem()
{
    SpinDegreesPerSecond = 45.0f;
    BobHeight = 8.0f;
}

void AReflectionsQuestItem::BeginPlay()
{
    // The item's own mesh from the quest data (before the pickup sets up its glow on the mesh's material).
    if (const UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this))
    {
        if (const FReflectionsQuestItemDef* Def = Quests->FindItem(ItemId))
        {
            if (ItemName.IsEmpty()) ItemName = Def->Name;
            if (UStaticMesh* ItemMesh = Def->Mesh.IsNull() ? nullptr : Def->Mesh.LoadSynchronous())
            {
                Mesh->SetStaticMesh(ItemMesh);
                Mesh->EmptyOverrideMaterials();
                Mesh->SetRelativeRotation(FRotator::ZeroRotator);
                Mesh->SetRelativeScale3D(FVector(Def->MeshScale));
            }
        }
    }
    Super::BeginPlay();
}

bool AReflectionsQuestItem::GiveTo(APawn* Collector)
{
    if (!Collector || !Collector->IsPlayerControlled() || ItemId.IsNone())
    {
        return false;
    }
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests)
    {
        return false;
    }
    Quests->GiveItem(ItemId, 1);
    Quests->NotifyEvent(TEXT("ItemFound"), ItemId);
    const FText Name = ItemName.IsEmpty() ? FText::FromName(ItemId) : ItemName;
    Quests->PushBanner(LOCTEXT("GotQuestItemKicker", "QUEST ITEM"), Name, FText::GetEmpty(), Color);
    return true;
}

#undef LOCTEXT_NAMESPACE
