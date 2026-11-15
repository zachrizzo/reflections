#include "Lives/ReflectionsLivesMemory.h"

#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFlow/ReflectionsGameFlowSubsystem.h"
#include "Kismet/GameplayStatics.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsLivesMemory, Log, All);

UReflectionsLivesMemory* UReflectionsLivesMemory::Get(const UObject* WorldContext)
{
    const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    UGameInstance* GI = World ? World->GetGameInstance() : nullptr;
    return GI ? GI->GetSubsystem<UReflectionsLivesMemory>() : nullptr;
}

void UReflectionsLivesMemory::Initialize(FSubsystemCollectionBase& Collection)
{
    Collection.InitializeDependency<UReflectionsGameFlowSubsystem>();
    Super::Initialize(Collection);
    BindToGameFlow();
}

void UReflectionsLivesMemory::BindToGameFlow()
{
    if (bBound) return;
    if (UReflectionsGameFlowSubsystem* Flow = GetGameInstance() ? GetGameInstance()->GetSubsystem<UReflectionsGameFlowSubsystem>() : nullptr)
    {
        Flow->OnCheckpointSaved.AddUniqueDynamic(this, &UReflectionsLivesMemory::HandleCheckpointSaved);
        bBound = true;
    }
}

FReflectionsPersonState& UReflectionsLivesMemory::FindOrAdd(FName PersonId)
{
    FReflectionsPersonState& State = People.FindOrAdd(PersonId);
    State.Id = PersonId;
    return State;
}

void UReflectionsLivesMemory::SyncWithCheckpoint(bool bHasCheckpoint)
{
    if (!bHasCheckpoint)
    {
        // A fresh game: nobody remembers anything yet. Keep the clock if it is running this session.
        People.Reset();
        StoryFlags.Reset();
        return;
    }
    if (!LoadSnapshot())
        UE_LOG(LogReflectionsLivesMemory, Log, TEXT("Checkpoint without a Lives snapshot: keeping what people know now"));
}

void UReflectionsLivesMemory::HandleCheckpointSaved(const FReflectionsCheckpoint& Checkpoint)
{
    SaveSnapshot();
}

bool UReflectionsLivesMemory::SaveSnapshot()
{
    UReflectionsLivesSave* Save = Cast<UReflectionsLivesSave>(UGameplayStatics::CreateSaveGameObject(UReflectionsLivesSave::StaticClass()));
    if (!Save) return false;
    Save->Version = UReflectionsLivesSave::CurrentVersion;
    Save->GameHours = GameHours;
    People.GenerateValueArray(Save->People);
    Save->StoryFlags = StoryFlags.Array();
    const bool bOk = UGameplayStatics::SaveGameToSlot(Save, SlotName(), 0);
    UE_LOG(LogReflectionsLivesMemory, Log, TEXT("Lives snapshot %s: %d people, hour %.2f"), bOk ? TEXT("saved") : TEXT("FAILED"), Save->People.Num(), GameHours);
    return bOk;
}

bool UReflectionsLivesMemory::LoadSnapshot()
{
    if (!UGameplayStatics::DoesSaveGameExist(SlotName(), 0)) return false;
    const UReflectionsLivesSave* Save = Cast<UReflectionsLivesSave>(UGameplayStatics::LoadGameFromSlot(SlotName(), 0));
    if (!Save || Save->Version > UReflectionsLivesSave::CurrentVersion) return false;
    People.Reset();
    for (const FReflectionsPersonState& State : Save->People)
        if (!State.Id.IsNone()) People.Add(State.Id, State);
    if (Save->GameHours >= 0.0) GameHours = Save->GameHours;
    StoryFlags = TSet<FName>(Save->StoryFlags);
    UE_LOG(LogReflectionsLivesMemory, Log, TEXT("Lives snapshot loaded: %d people, hour %.2f"), People.Num(), GameHours);
    return true;
}

void UReflectionsLivesMemory::ForgetEverything()
{
    People.Reset();
    StoryFlags.Reset();
    GameHours = -1.0;
    ++Generation;
    UGameplayStatics::DeleteGameInSlot(SlotName(), 0);
}
