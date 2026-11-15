#include "Quests/ReflectionsQuestSubsystem.h"

#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFlow/ReflectionsGameFlowSubsystem.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "NPC/ReflectionsNpcSubsystem.h"
#include "NPC/ReflectionsReputationSubsystem.h"
#include "Quests/ReflectionsQuestPack.h"
#include "Quests/ReflectionsQuestSave.h"
#include "Quests/ReflectionsQuestWorldSubsystem.h"
#include "Quests/ReflectionsStoryMarker.h"
#include "UObject/UnrealType.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "Lives/ReflectionsLivesSubsystem.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"
#include "Worlds/ReflectionsWorldLibrary.h"

#define LOCTEXT_NAMESPACE "ReflectionsQuests"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsQuest, Log, All);

namespace ReflectionsQuestBuiltins
{
    void Build(TArray<FReflectionsQuestDef>& OutQuests, TArray<FReflectionsQuestPerson>& OutPeople);
}

namespace ReflectionsQuestCVars
{
    static float HeatRefuse = 0.5f;
    static FAutoConsoleVariableRef CVarHeatRefuse(TEXT("Quest.HeatRefuse"), HeatRefuse,
        TEXT("Player heat (0..1) at which quest givers stop offering quests. Standing 25+ with a person adds 0.25, 60+ adds 0.5. 2 = never."));
    static int32 ShowTest = -1;
    static FAutoConsoleVariableRef CVarShowTest(TEXT("Quest.ShowTestQuests"), ShowTest,
        TEXT("-1: test quests only while no real side quests are loaded (default). 0: never. 1: always."));
}

namespace
{
    const FLinearColor BannerGold(0.95f, 0.72f, 0.28f, 1.0f);
    const FLinearColor BannerPaper(0.93f, 0.89f, 0.80f, 1.0f);
    const FLinearColor BannerDanger(0.92f, 0.16f, 0.10f, 1.0f);

    FText SpacedId(FName Id)
    {
        // "GiltMaren" / "ilse_varrow" -> "Gilt Maren" / "Ilse Varrow"; people without a book entry still read like names.
        const FString S = Id.ToString();
        FString Out;
        bool bWordStart = true;
        for (int32 i = 0; i < S.Len(); ++i)
        {
            if (S[i] == TEXT('_')) { Out.AppendChar(TEXT(' ')); bWordStart = true; continue; }
            if (i > 0 && FChar::IsUpper(S[i]) && !FChar::IsUpper(S[i - 1]) && S[i - 1] != TEXT('_')) Out.AppendChar(TEXT(' '));
            Out.AppendChar(bWordStart ? FChar::ToUpper(S[i]) : S[i]);
            bWordStart = false;
        }
        return FText::FromString(Out);
    }

    /** Calls a UFUNCTION by name with simple parameters (FName, bool, float, int, object), in order. */
    struct FNamedArg
    {
        enum class EKind : uint8 { Name, Bool, Float, Int, Object } Kind = EKind::Name;
        FName N; bool B = false; float F = 0.0f; int32 I = 0; UObject* O = nullptr;
        static FNamedArg Of(FName V) { FNamedArg A; A.Kind = EKind::Name; A.N = V; return A; }
        static FNamedArg Of(bool V) { FNamedArg A; A.Kind = EKind::Bool; A.B = V; return A; }
        static FNamedArg Of(float V) { FNamedArg A; A.Kind = EKind::Float; A.F = V; return A; }
        static FNamedArg Of(UObject* V) { FNamedArg A; A.Kind = EKind::Object; A.O = V; return A; }
    };

    bool CallNamed(UObject* Target, const TCHAR* Function, std::initializer_list<FNamedArg> Args, bool* OutBool = nullptr, float* OutFloat = nullptr)
    {
        UFunction* Fn = Target ? Target->FindFunction(FName(Function)) : nullptr;
        if (!Fn) return false;
        uint8* Buffer = static_cast<uint8*>(FMemory_Alloca(FMath::Max<int32>(Fn->ParmsSize, 1)));
        FMemory::Memzero(Buffer, Fn->ParmsSize);
        for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It) It->InitializeValue_InContainer(Buffer);
        const FNamedArg* Arg = Args.begin();
        for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
        {
            if (It->HasAnyPropertyFlags(CPF_ReturnParm) || (It->HasAnyPropertyFlags(CPF_OutParm) && !It->HasAnyPropertyFlags(CPF_ReferenceParm))) continue;
            if (Arg == Args.end()) break;
            void* Value = It->ContainerPtrToValuePtr<void>(Buffer);
            if (FNameProperty* NP = CastField<FNameProperty>(*It)) NP->SetPropertyValue(Value, Arg->N);
            else if (FBoolProperty* BP = CastField<FBoolProperty>(*It)) BP->SetPropertyValue(Value, Arg->B);
            else if (FFloatProperty* FP = CastField<FFloatProperty>(*It)) FP->SetPropertyValue(Value, Arg->F);
            else if (FDoubleProperty* DP = CastField<FDoubleProperty>(*It)) DP->SetPropertyValue(Value, Arg->F);
            else if (FIntProperty* IP = CastField<FIntProperty>(*It)) IP->SetPropertyValue(Value, Arg->I);
            else if (FObjectPropertyBase* OP = CastField<FObjectPropertyBase>(*It)) OP->SetObjectPropertyValue(Value, Arg->O);
            ++Arg;
        }
        Target->ProcessEvent(Fn, Buffer);
        if (OutBool)
        {
            if (FBoolProperty* Ret = CastField<FBoolProperty>(Fn->GetReturnProperty())) *OutBool = Ret->GetPropertyValue_InContainer(Buffer);
        }
        if (OutFloat)
        {
            FProperty* Ret = Fn->GetReturnProperty();
            if (FFloatProperty* FR = CastField<FFloatProperty>(Ret)) *OutFloat = FR->GetPropertyValue_InContainer(Buffer);
            else if (FDoubleProperty* DR = CastField<FDoubleProperty>(Ret)) *OutFloat = static_cast<float>(DR->GetPropertyValue_InContainer(Buffer));
            else if (FIntProperty* IR = CastField<FIntProperty>(Ret)) *OutFloat = static_cast<float>(IR->GetPropertyValue_InContainer(Buffer));
        }
        for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It) It->DestroyValue_InContainer(Buffer);
        return true;
    }

    UObject* WorldSubsystemByName(const UWorld* World, const TCHAR* ClassPath)
    {
        UClass* Class = FindObject<UClass>(nullptr, ClassPath);
        return World && Class ? World->GetSubsystemBase(Class) : nullptr;
    }

    const TCHAR* LivesClass = TEXT("/Script/reflections.ReflectionsLivesSubsystem");

    bool SplitAction(const FString& Action, FString& OutVerb, FString& OutArg)
    {
        if (!Action.Split(TEXT(":"), &OutVerb, &OutArg))
        {
            OutVerb = Action;
            OutArg.Reset();
        }
        OutVerb.TrimStartAndEndInline();
        OutArg.TrimStartAndEndInline();
        return !OutVerb.IsEmpty();
    }
}

UReflectionsQuestSubsystem* UReflectionsQuestSubsystem::Get(const UObject* WorldContext)
{
    const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    const UGameInstance* GI = World ? World->GetGameInstance() : nullptr;
    return GI ? GI->GetSubsystem<UReflectionsQuestSubsystem>() : nullptr;
}

void UReflectionsQuestSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Collection.InitializeDependency<UReflectionsGameFlowSubsystem>();
    Collection.InitializeDependency<UReflectionsWorldJumpSubsystem>();
    Super::Initialize(Collection);

    if (Packs.IsEmpty())
    {
        Packs.Add(FSoftObjectPath(TEXT("/Game/Quests/DA_QuestPack_Story.DA_QuestPack_Story")));
    }
    ReloadContent();

    if (UGameplayStatics::DoesSaveGameExist(SlotName(), 0))
    {
        if (const UReflectionsQuestSave* Save = Cast<UReflectionsQuestSave>(UGameplayStatics::LoadGameFromSlot(SlotName(), 0)))
        {
            CheckpointSnapshot = Save->Snapshot;
        }
    }

    UGameInstance* GI = GetGameInstance();
    if (UReflectionsGameFlowSubsystem* Flow = GI->GetSubsystem<UReflectionsGameFlowSubsystem>())
    {
        Flow->OnCheckpointSaved.AddDynamic(this, &UReflectionsQuestSubsystem::HandleCheckpointSaved);
    }
    if (UReflectionsWorldJumpSubsystem* Progress = GI->GetSubsystem<UReflectionsWorldJumpSubsystem>())
    {
        Progress->OnProgressRestored.AddDynamic(this, &UReflectionsQuestSubsystem::HandleProgressRestored);
    }
}

void UReflectionsQuestSubsystem::Deinitialize()
{
    LoadedPacks.Reset();
    Super::Deinitialize();
}

// ---- Content -------------------------------------------------------------------------------------------------

void UReflectionsQuestSubsystem::ReloadContent()
{
    Quests.Reset();
    People.Reset();
    ItemDefs.Reset();
    MarkerAliases.Reset();
    LoadBuiltIns();
    LoadPacks();
    EnsureStates();
    UE_LOG(LogReflectionsQuest, Log, TEXT("Quests loaded: %d quests, %d people."), Quests.Num(), People.Num());
}

void UReflectionsQuestSubsystem::LoadBuiltIns()
{
    TArray<FReflectionsQuestDef> BuiltQuests;
    TArray<FReflectionsQuestPerson> BuiltPeople;
    ReflectionsQuestBuiltins::Build(BuiltQuests, BuiltPeople);
    for (const FReflectionsQuestDef& Def : BuiltQuests) MergeQuest(Def);
    for (const FReflectionsQuestPerson& Person : BuiltPeople) MergePerson(Person);
}

void UReflectionsQuestSubsystem::LoadPacks()
{
    LoadedPacks.Reset();
    for (const FSoftObjectPath& Path : Packs)
    {
        if (Path.IsNull()) continue;
        UReflectionsQuestPack* Pack = Cast<UReflectionsQuestPack>(Path.TryLoad());
        if (!Pack) continue;
        LoadedPacks.Add(Pack);
        TArray<FReflectionsQuestDef> PackQuests = Pack->Quests;
        TArray<FReflectionsQuestPerson> PackPeople = Pack->People;
        FString Report;
        if (PackQuests.IsEmpty() && !Pack->SourceJson.IsEmpty()) UReflectionsQuestPack::ParseQuests(Pack->SourceJson, PackQuests, Report);
        if (PackPeople.IsEmpty() && !Pack->PeopleJson.IsEmpty()) UReflectionsQuestPack::ParsePeople(Pack->PeopleJson, PackPeople, Report);
        for (const FReflectionsQuestDef& Def : PackQuests) MergeQuest(Def);
        for (const FReflectionsQuestPerson& Person : PackPeople) MergePerson(Person);
        TArray<FReflectionsQuestItemDef> PackItems = Pack->Items;
        if (PackItems.IsEmpty() && !Pack->SourceJson.IsEmpty()) UReflectionsQuestPack::ParseItems(Pack->SourceJson, PackItems);
        for (const FReflectionsQuestItemDef& Item : PackItems)
        {
            ItemDefs.RemoveAll([&Item](const FReflectionsQuestItemDef& E) { return E.Id == Item.Id; });
            ItemDefs.Add(Item);
        }
        MarkerAliases.Append(Pack->MarkerAliases);
        if (Pack->MarkerAliases.IsEmpty() && !Pack->PeopleJson.IsEmpty()) UReflectionsQuestPack::ParseMarkerAliases(Pack->PeopleJson, MarkerAliases);
        UE_LOG(LogReflectionsQuest, Log, TEXT("Quest pack %s: %d quests, %d people."), *Path.ToString(), PackQuests.Num(), PackPeople.Num());
    }
}

bool UReflectionsQuestSubsystem::AddContentFromJson(const FString& QuestJson, const FString& PeopleJson, FString& OutReport)
{
    bool bAny = false;
    if (!PeopleJson.IsEmpty())
    {
        TArray<FReflectionsQuestPerson> Parsed;
        if (UReflectionsQuestPack::ParsePeople(PeopleJson, Parsed, OutReport))
        {
            for (const FReflectionsQuestPerson& P : Parsed) MergePerson(P);
            bAny = true;
        }
        UReflectionsQuestPack::ParseMarkerAliases(PeopleJson, MarkerAliases);
    }
    if (!QuestJson.IsEmpty())
    {
        TArray<FReflectionsQuestItemDef> Parsed;
        UReflectionsQuestPack::ParseItems(QuestJson, Parsed);
        for (const FReflectionsQuestItemDef& Item : Parsed)
        {
            ItemDefs.RemoveAll([&Item](const FReflectionsQuestItemDef& E) { return E.Id == Item.Id; });
            ItemDefs.Add(Item);
        }
    }
    if (!QuestJson.IsEmpty())
    {
        TArray<FReflectionsQuestDef> Parsed;
        if (UReflectionsQuestPack::ParseQuests(QuestJson, Parsed, OutReport))
        {
            for (const FReflectionsQuestDef& Q : Parsed) MergeQuest(Q);
            bAny = true;
        }
    }
    if (bAny)
    {
        EnsureStates();
        RefreshAvailability();
        Changed();
    }
    return bAny;
}

void UReflectionsQuestSubsystem::EnsureStates()
{
    for (const FReflectionsQuestDef& Def : Quests)
    {
        StateFor(Def.Id);
    }
}

void UReflectionsQuestSubsystem::MergeQuest(const FReflectionsQuestDef& Def)
{
    if (Def.Id.IsNone()) return;
    // A story main quest replaces the built-in one, whatever its id.
    if (Def.bMain)
    {
        Quests.RemoveAll([&Def](const FReflectionsQuestDef& E) { return E.bMain && E.Id != Def.Id && E.Id == TEXT("main"); });
    }
    if (FReflectionsQuestDef* Existing = Quests.FindByPredicate([&Def](const FReflectionsQuestDef& E) { return E.Id == Def.Id; }))
    {
        *Existing = Def;
    }
    else
    {
        Quests.Add(Def);
    }
}

void UReflectionsQuestSubsystem::MergePerson(const FReflectionsQuestPerson& Person)
{
    if (Person.Id.IsNone()) return;
    if (FReflectionsQuestPerson* Existing = People.FindByPredicate([&Person](const FReflectionsQuestPerson& E) { return E.Id == Person.Id; }))
    {
        *Existing = Person;
    }
    else
    {
        People.Add(Person);
    }
}

const FReflectionsQuestDef* UReflectionsQuestSubsystem::FindQuest(FName QuestId) const
{
    return Quests.FindByPredicate([QuestId](const FReflectionsQuestDef& E) { return E.Id == QuestId; });
}

const FReflectionsQuestPerson* UReflectionsQuestSubsystem::FindPerson(FName PersonId) const
{
    return People.FindByPredicate([PersonId](const FReflectionsQuestPerson& E) { return E.Id == PersonId; });
}

FText UReflectionsQuestSubsystem::GetPersonName(FName PersonId) const
{
    if (PersonId.IsNone() || PersonId == TEXT("narrator")) return FText::GetEmpty();
    if (PersonId == TEXT("wren_hale")) return LOCTEXT("NameWren", "Wren");
    if (PersonId == TEXT("the_tarnish")) return LOCTEXT("NameTarnish", "The Tarnish");
    if (const FReflectionsQuestPerson* P = FindPerson(PersonId))
    {
        if (!P->DisplayName.IsEmpty()) return P->DisplayName;
    }
    // Townsfolk the people book doesn't list (gen_*, crowd_*): Lives named them from their side's name pool.
    if (const UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr)
    {
        if (const UReflectionsLivesSubsystem* Lives = World->GetSubsystem<UReflectionsLivesSubsystem>())
        {
            const FString LivesName = Lives->GetPersonName(PersonId);
            if (!LivesName.IsEmpty()) return FText::FromString(LivesName);
        }
    }
    return SpacedId(PersonId);
}

const FReflectionsQuestItemDef* UReflectionsQuestSubsystem::FindItem(FName Item) const
{
    return ItemDefs.FindByPredicate([Item](const FReflectionsQuestItemDef& E) { return E.Id == Item; });
}

FText UReflectionsQuestSubsystem::GetItemName(FName Item) const
{
    if (const FReflectionsQuestItemDef* Def = ItemDefs.FindByPredicate([Item](const FReflectionsQuestItemDef& E) { return E.Id == Item; }))
    {
        if (!Def->Name.IsEmpty()) return Def->Name;
    }
    return SpacedId(Item);
}

bool UReflectionsQuestSubsystem::IsQuestVisible(const FReflectionsQuestDef& Def) const
{
    if (!Def.bTest) return true;
    if (ReflectionsQuestCVars::ShowTest >= 0) return ReflectionsQuestCVars::ShowTest > 0;
    for (const FReflectionsQuestDef& Other : Quests)
    {
        if (!Other.bMain && !Other.bTest) return false;
    }
    return true;
}

// ---- State ---------------------------------------------------------------------------------------------------

EReflectionsQuestStatus UReflectionsQuestSubsystem::GetStatus(FName QuestId) const
{
    const FReflectionsQuestState* S = States.Find(QuestId);
    return S ? S->Status : EReflectionsQuestStatus::Unavailable;
}

const FReflectionsQuestState* UReflectionsQuestSubsystem::FindState(FName QuestId) const
{
    return States.Find(QuestId);
}

bool UReflectionsQuestSubsystem::GetQuestState(FName QuestId, FReflectionsQuestState& OutState) const
{
    if (const FReflectionsQuestState* S = States.Find(QuestId))
    {
        OutState = *S;
        return true;
    }
    return false;
}

FReflectionsQuestState& UReflectionsQuestSubsystem::StateFor(FName QuestId)
{
    FReflectionsQuestState& S = States.FindOrAdd(QuestId);
    S.QuestId = QuestId;
    return S;
}

const FReflectionsQuestStep* UReflectionsQuestSubsystem::GetCurrentStep(FName QuestId) const
{
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    const FReflectionsQuestState* S = States.Find(QuestId);
    if (!Def || !S || S->Status != EReflectionsQuestStatus::Active) return nullptr;
    return Def->FindStep(S->StepId);
}

bool UReflectionsQuestSubsystem::RequirementsMet(const FReflectionsQuestDef& Def) const
{
    for (const FName& Q : Def.RequiresQuests)
    {
        if (GetStatus(Q) != EReflectionsQuestStatus::Completed) return false;
    }
    for (const FName& U : Def.RequiresUnlocks)
    {
        if (!Unlocks.Contains(U)) return false;
    }
    return true;
}

void UReflectionsQuestSubsystem::RefreshAvailability()
{
    if (bApplying) return;
    ++ChangeDepth;
    for (const FReflectionsQuestDef& Def : Quests)
    {
        if (!IsQuestVisible(Def)) continue;
        const EReflectionsQuestStatus Status = GetStatus(Def.Id);
        if (Status != EReflectionsQuestStatus::Unavailable && Status != EReflectionsQuestStatus::Available) continue;
        if (!RequirementsMet(Def)) continue;
        if (!Def.Giver.IsNone() && DeadPeople.Contains(Def.Giver)) continue;
        if (Def.bMain || Def.bAutoStart || Def.Giver.IsNone())
        {
            AcceptQuest(Def.Id);
        }
        else if (Status == EReflectionsQuestStatus::Unavailable)
        {
            StateFor(Def.Id).Status = EReflectionsQuestStatus::Available;
        }
    }
    --ChangeDepth;
    Changed();
}

bool UReflectionsQuestSubsystem::AcceptQuest(FName QuestId)
{
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    if (!Def || Def->Steps.IsEmpty()) return false;
    FReflectionsQuestState& S = StateFor(QuestId);
    if (S.Status == EReflectionsQuestStatus::Active || S.Status == EReflectionsQuestStatus::ReadyToTurnIn || S.Status == EReflectionsQuestStatus::Completed)
    {
        return false;
    }
    S.Status = EReflectionsQuestStatus::Active;
    S.bDeclined = false;
    S.bSeen = true;
    S.Log.Reset();
    const UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
    S.StartedAt = World ? World->GetTimeSeconds() : 0.0;
    ++ChangeDepth;
    Broadcast(QuestId, NAME_None, NAME_None, EReflectionsQuestEventType::Accepted);
    PushBanner(Def->bMain ? LOCTEXT("BannerStory", "THE STORY CONTINUES") : LOCTEXT("BannerStarted", "QUEST STARTED"), Def->Title, Def->Summary, BannerGold);
    if (Tracked.IsNone() || !Def->bMain)
    {
        Tracked = QuestId;
        Broadcast(QuestId, NAME_None, NAME_None, EReflectionsQuestEventType::Tracked);
    }
    StartStep(*Def, S, 0);
    --ChangeDepth;
    Changed();
    return true;
}

bool UReflectionsQuestSubsystem::DeclineQuest(FName QuestId)
{
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    if (!Def || Def->bMain) return false;
    FReflectionsQuestState& S = StateFor(QuestId);
    if (S.Status != EReflectionsQuestStatus::Available && S.Status != EReflectionsQuestStatus::Unavailable) return false;
    S.bDeclined = true;
    S.bSeen = true;
    Broadcast(QuestId, NAME_None, NAME_None, EReflectionsQuestEventType::Declined);
    Changed();
    return true;
}

bool UReflectionsQuestSubsystem::FailQuest(FName QuestId)
{
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    FReflectionsQuestState* S = States.Find(QuestId);
    if (!Def || !S || (S->Status != EReflectionsQuestStatus::Active && S->Status != EReflectionsQuestStatus::ReadyToTurnIn)) return false;
    S->Status = EReflectionsQuestStatus::Failed;
    Broadcast(QuestId, S->StepId, NAME_None, EReflectionsQuestEventType::Failed);
    AddUnlock(FName(*FString::Printf(TEXT("QuestFailed_%s"), *QuestId.ToString())), QuestId);
    PushBanner(LOCTEXT("BannerFailed", "QUEST FAILED"), Def->Title, S->EndNote, BannerDanger);
    AutoTrack();
    Changed();
    return true;
}

void UReflectionsQuestSubsystem::StartStep(const FReflectionsQuestDef& Def, FReflectionsQuestState& S, int32 StepIndex)
{
    if (!Def.Steps.IsValidIndex(StepIndex))
    {
        FinishQuest(Def, S);
        return;
    }
    const FReflectionsQuestStep& Step = Def.Steps[StepIndex];
    S.StepId = Step.Id;
    if (!bApplying)
    {
        for (const FName& Item : Step.GiveItems) GiveItem(Item, 1);
    }
    S.Objectives.Reset();
    for (const FReflectionsQuestObjective& O : Step.Objectives)
    {
        FReflectionsObjectiveState OS;
        OS.Id = O.Id;
        S.Objectives.Add(OS);
    }
    Broadcast(Def.Id, Step.Id, NAME_None, EReflectionsQuestEventType::StepStarted);
    // Objectives already satisfied (items held, pages found) are filled in by the world subsystem's next tick;
    // steps with nothing to do finish now.
    if (Step.Objectives.IsEmpty() && Step.Choices.IsEmpty() && Step.Cutscene.IsNone() && Step.TimeoutSeconds <= 0.0f)
    {
        FinishStep(Def, S, NAME_None);
    }
    if (Def.bMain && !bApplying && S.Status == EReflectionsQuestStatus::Active && S.StepId == Step.Id)
    {
        bool bSkipped = false;
        for (const FName& Dead : DeadPeople) bSkipped |= SkipObjectivesFor(Def, S, Dead);
        if (bSkipped) CheckStepComplete(Def, S);
    }
    Changed();
}

void UReflectionsQuestSubsystem::CheckStepComplete(const FReflectionsQuestDef& Def, FReflectionsQuestState& S)
{
    if (S.Status != EReflectionsQuestStatus::Active) return;
    const FReflectionsQuestStep* Step = Def.FindStep(S.StepId);
    if (!Step) return;
    bool bAll = true, bAny = false, bHasRequired = false;
    for (int32 i = 0; i < Step->Objectives.Num(); ++i)
    {
        if (Step->Objectives[i].bOptional) continue;
        bHasRequired = true;
        const bool bDone = S.Objectives.IsValidIndex(i) && S.Objectives[i].bDone;
        bAll &= bDone;
        bAny |= bDone;
    }
    if (!bHasRequired && (!Step->Cutscene.IsNone() || Step->TimeoutSeconds > 0.0f)) return;  // finished by CutsceneDone / the timeout
    const bool bComplete = !bHasRequired || (Step->bAnyObjective ? bAny : bAll);
    if (!bComplete) return;
    if (!Step->Choices.IsEmpty()) return;  // waits for MakeChoice
    FinishStep(Def, S, NAME_None);
}

void UReflectionsQuestSubsystem::FinishStep(const FReflectionsQuestDef& Def, FReflectionsQuestState& S, FName ForcedNext)
{
    int32 Index = INDEX_NONE;
    const FReflectionsQuestStep* Step = Def.FindStep(S.StepId, &Index);
    if (!Step) return;
    S.Log.Add(FName(*FString::Printf(TEXT("step:%s"), *Step->Id.ToString())));
    AddUnlock(FName(*FString::Printf(TEXT("Quest_%s.%s"), *Def.Id.ToString(), *Step->Id.ToString())), Def.Id);
    Broadcast(Def.Id, Step->Id, NAME_None, EReflectionsQuestEventType::StepComplete);
    if (!Step->Reward.IsEmpty())
    {
        GiveReward(Step->Reward, Def.Id);
    }
    const FName Next = !ForcedNext.IsNone() ? ForcedNext : Step->NextStep;
    if (Next == ReflectionsQuest::Fail)
    {
        FailQuest(Def.Id);
        return;
    }
    if (Next == ReflectionsQuest::End)
    {
        FinishQuest(Def, S);
        return;
    }
    int32 NextIndex = Index + 1;
    if (!Next.IsNone())
    {
        int32 Found = INDEX_NONE;
        if (Def.FindStep(Next, &Found)) NextIndex = Found;
    }
    if (!Def.Steps.IsValidIndex(NextIndex))
    {
        FinishQuest(Def, S);
        return;
    }
    if (!Def.bMain)
    {
        PushBanner(LOCTEXT("BannerUpdated", "QUEST UPDATED"), Def.Title, Def.Steps[NextIndex].Title, BannerPaper);
    }
    else
    {
        PushBanner(LOCTEXT("BannerStoryNext", "NEW OBJECTIVE"), Def.Steps[NextIndex].Title, FText::GetEmpty(), BannerGold);
    }
    StartStep(Def, S, NextIndex);
}

void UReflectionsQuestSubsystem::FinishQuest(const FReflectionsQuestDef& Def, FReflectionsQuestState& S)
{
    if (Def.bTurnIn && !Def.Giver.IsNone() && !DeadPeople.Contains(Def.Giver))
    {
        S.Status = EReflectionsQuestStatus::ReadyToTurnIn;
        S.Objectives.Reset();
        Broadcast(Def.Id, S.StepId, NAME_None, EReflectionsQuestEventType::ReadyToTurnIn);
        PushBanner(LOCTEXT("BannerReturn", "RETURN TO"), GetPersonName(Def.Giver), Def.Title, BannerGold);
        Changed();
        return;
    }
    S.Status = EReflectionsQuestStatus::Completed;
    S.Objectives.Reset();
    Broadcast(Def.Id, S.StepId, NAME_None, EReflectionsQuestEventType::Completed);
    PushBanner(Def.bMain ? LOCTEXT("BannerStoryDone", "THE STORY IS TOLD") : LOCTEXT("BannerComplete", "QUEST COMPLETE"), Def.Title,
        DescribeReward(Def.Reward), BannerGold);
    GiveReward(Def.Reward, Def.Id);
    AddUnlock(FName(*FString::Printf(TEXT("Quest_%s"), *Def.Id.ToString())), Def.Id);
    NotifyEvent(TEXT("QuestComplete"), Def.Id);
    if (!Def.Giver.IsNone())
    {
        if (UObject* Lives = WorldSubsystemByName(GetGameInstance()->GetWorld(), LivesClass))
        {
            CallNamed(Lives, TEXT("CompleteQuestFor"), {FNamedArg::Of(Def.Giver)});
        }
    }
    AutoTrack();
    RefreshAvailability();
    Changed();
}

bool UReflectionsQuestSubsystem::TurnInQuest(FName QuestId)
{
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    FReflectionsQuestState* S = States.Find(QuestId);
    if (!Def || !S || S->Status != EReflectionsQuestStatus::ReadyToTurnIn) return false;
    S->Status = EReflectionsQuestStatus::Completed;
    Broadcast(QuestId, S->StepId, NAME_None, EReflectionsQuestEventType::Completed);
    PushBanner(LOCTEXT("BannerComplete", "QUEST COMPLETE"), Def->Title, DescribeReward(Def->Reward), BannerGold);
    GiveReward(Def->Reward, QuestId);
    AddUnlock(FName(*FString::Printf(TEXT("Quest_%s"), *QuestId.ToString())), QuestId);
    NotifyEvent(TEXT("QuestComplete"), QuestId);
    // The lives system remembers that the hero helped this person.
    if (UObject* Lives = WorldSubsystemByName(GetGameInstance()->GetWorld(), LivesClass))
    {
        CallNamed(Lives, TEXT("CompleteQuestFor"), {FNamedArg::Of(Def->Giver)});
    }
    AutoTrack();
    RefreshAvailability();
    Changed();
    return true;
}

bool UReflectionsQuestSubsystem::MakeChoice(FName QuestId, FName ChoiceId)
{
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    FReflectionsQuestState* S = States.Find(QuestId);
    if (!Def || !S || S->Status != EReflectionsQuestStatus::Active) return false;
    const FReflectionsQuestStep* Step = Def->FindStep(S->StepId);
    if (!Step) return false;
    const FReflectionsQuestChoice* Choice = Step->Choices.FindByPredicate([ChoiceId](const FReflectionsQuestChoice& C) { return C.Id == ChoiceId; });
    if (!Choice) return false;
    for (int32 i = 0; i < Step->Objectives.Num(); ++i)
    {
        if (!Step->Objectives[i].bOptional && !(S->Objectives.IsValidIndex(i) && S->Objectives[i].bDone)) return false;
    }
    S->Log.Add(FName(*FString::Printf(TEXT("choice:%s:%s"), *Step->Id.ToString(), *Choice->Id.ToString())));
    Broadcast(QuestId, Step->Id, Choice->Id, EReflectionsQuestEventType::ChoiceMade);
    if (!Choice->Reward.IsEmpty()) GiveReward(Choice->Reward, QuestId);
    AddUnlock(FName(*FString::Printf(TEXT("Choice_%s_%s"), *QuestId.ToString(), *Choice->Id.ToString())), QuestId);
    FinishStep(*Def, *S, Choice->NextStep);
    Changed();
    return true;
}

FReflectionsObjectiveState* UReflectionsQuestSubsystem::FindObjectiveState(FName QuestId, FName ObjectiveId)
{
    FReflectionsQuestState* S = States.Find(QuestId);
    if (!S || S->Status != EReflectionsQuestStatus::Active) return nullptr;
    return S->Objectives.FindByPredicate([ObjectiveId](const FReflectionsObjectiveState& O) { return O.Id == ObjectiveId; });
}

void UReflectionsQuestSubsystem::SetObjectiveProgress(FName QuestId, FName ObjectiveId, int32 Progress)
{
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    FReflectionsQuestState* S = States.Find(QuestId);
    if (!Def || !S || S->Status != EReflectionsQuestStatus::Active) return;
    const FReflectionsQuestStep* Step = Def->FindStep(S->StepId);
    if (!Step) return;
    for (int32 i = 0; i < Step->Objectives.Num() && i < S->Objectives.Num(); ++i)
    {
        if (Step->Objectives[i].Id != ObjectiveId) continue;
        FReflectionsObjectiveState& OS = S->Objectives[i];
        const FReflectionsQuestObjective& O = Step->Objectives[i];
        if (OS.bDone) return;
        if (Step->bOrdered)
        {
            for (int32 k = 0; k < i; ++k)
            {
                if (!Step->Objectives[k].bOptional && S->Objectives.IsValidIndex(k) && !S->Objectives[k].bDone) return;  // not its turn yet
            }
        }
        const int32 Clamped = FMath::Clamp(Progress, 0, O.Count);
        if (Clamped <= OS.Progress) return;  // progress never goes back
        OS.Progress = Clamped;
        if (OS.Progress >= O.Count)
        {
            OS.bDone = true;
            for (const FName& Item : O.GiveItems) GiveItem(Item, 1);
            Broadcast(QuestId, Step->Id, O.Id, EReflectionsQuestEventType::ObjectiveComplete);
            if (Step->Objectives.Num() > 1)
            {
                PushBanner(LOCTEXT("BannerObjective", "OBJECTIVE COMPLETE"), FormatObjective(O, &OS), FText::GetEmpty(), BannerPaper);
            }
        }
        else
        {
            Broadcast(QuestId, Step->Id, O.Id, EReflectionsQuestEventType::ObjectiveProgress);
        }
        Changed();
        CheckStepComplete(*Def, *S);
        return;
    }
}

void UReflectionsQuestSubsystem::AdvanceObjective(FName QuestId, FName ObjectiveId, int32 Delta)
{
    if (const FReflectionsObjectiveState* OS = FindObjectiveState(QuestId, ObjectiveId))
    {
        SetObjectiveProgress(QuestId, ObjectiveId, OS->Progress + Delta);
    }
}

void UReflectionsQuestSubsystem::AddHeldTime(FName QuestId, FName ObjectiveId, float Seconds)
{
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    const FReflectionsQuestStep* Step = GetCurrentStep(QuestId);
    FReflectionsObjectiveState* OS = FindObjectiveState(QuestId, ObjectiveId);
    if (!Def || !Step || !OS || OS->bDone) return;
    const FReflectionsQuestObjective* O = Step->Objectives.FindByPredicate([ObjectiveId](const FReflectionsQuestObjective& E) { return E.Id == ObjectiveId; });
    if (!O) return;
    OS->Held += Seconds;
    if (OS->Held >= FMath::Max(1.0f, O->Seconds))
    {
        SetObjectiveProgress(QuestId, ObjectiveId, O->Count);
    }
}

void UReflectionsQuestSubsystem::MarkObjectiveSpawned(FName QuestId, FName ObjectiveId)
{
    if (FReflectionsObjectiveState* OS = FindObjectiveState(QuestId, ObjectiveId)) OS->bSpawned = true;
}

bool UReflectionsQuestSubsystem::CompleteObjective(FName QuestId, FName ObjectiveId)
{
    const FReflectionsQuestStep* Step = GetCurrentStep(QuestId);
    if (!Step) return false;
    const FReflectionsQuestObjective* O = Step->Objectives.FindByPredicate([ObjectiveId](const FReflectionsQuestObjective& E) { return E.Id == ObjectiveId; });
    if (!O) return false;
    SetObjectiveProgress(QuestId, ObjectiveId, O->Count);
    return true;
}

bool UReflectionsQuestSubsystem::CompleteStepTo(FName QuestId, FName NextStep)
{
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    FReflectionsQuestState* S = States.Find(QuestId);
    if (!Def || !S || S->Status != EReflectionsQuestStatus::Active || !Def->FindStep(S->StepId)) return false;
    FinishStep(*Def, *S, NextStep);
    return true;
}

bool UReflectionsQuestSubsystem::CompleteStep(FName QuestId)
{
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    FReflectionsQuestState* S = States.Find(QuestId);
    if (!Def || !S || S->Status != EReflectionsQuestStatus::Active) return false;
    const FReflectionsQuestStep* Step = Def->FindStep(S->StepId);
    if (!Step) return false;
    if (!Step->Choices.IsEmpty())
    {
        for (int32 i = 0; i < Step->Objectives.Num(); ++i) if (S->Objectives.IsValidIndex(i)) S->Objectives[i].bDone = true;
        return MakeChoice(QuestId, Step->Choices[0].Id);
    }
    FinishStep(*Def, *S, NAME_None);
    return true;
}

void UReflectionsQuestSubsystem::NotifyEvent(FName Key, FName Arg)
{
    NotifyEventAt(Key, Arg, FVector(TNumericLimits<float>::Max()), 1);
}

void UReflectionsQuestSubsystem::NotifyEventCount(FName Key, FName Arg, int32 Count)
{
    NotifyEventAt(Key, Arg, FVector(TNumericLimits<float>::Max()), Count);
}

void UReflectionsQuestSubsystem::NotifyEventAt(FName Key, FName Arg, const FVector& Location, int32 Count)
{
    if (Key.IsNone()) return;
    Count = FMath::Max(1, Count);
    const bool bHasLocation = Location.X < TNumericLimits<float>::Max() * 0.5f;
    UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
    OnGameEvent.Broadcast(Key, Arg, Count);
    // A cutscene step finishes when its scene ends.
    if (Key == TEXT("CutsceneDone") && !Arg.IsNone())
    {
        TArray<FName> Done;
        for (const FReflectionsQuestDef& Def : Quests)
        {
            const FReflectionsQuestStep* Step = GetCurrentStep(Def.Id);
            if (Step && Step->Cutscene == Arg && !Step->Objectives.ContainsByPredicate([](const FReflectionsQuestObjective& O) { return !O.bOptional; }))
            {
                Done.Add(Def.Id);
            }
        }
        for (const FName& Q : Done) CompleteStep(Q);
    }
    TArray<TPair<FName, FName>> Hits;
    for (const FReflectionsQuestDef& Def : Quests)
    {
        const FReflectionsQuestState* S = States.Find(Def.Id);
        if (!S || S->Status != EReflectionsQuestStatus::Active) continue;
        const FReflectionsQuestStep* Step = Def.FindStep(S->StepId);
        if (!Step) continue;
        for (const FReflectionsQuestObjective& O : Step->Objectives)
        {
            if (O.Type == EReflectionsObjectiveType::Event && O.Target == Key && (O.Spell.IsNone() || O.Spell == Arg))
            {
                if (!O.Marker.IsNone() && O.Radius > 0.0f)
                {
                    // Only inside the objective's zone.
                    const AReflectionsStoryMarker* M = UReflectionsStoryMarkerSubsystem::FindMarker(World, O.Marker);
                    if (!bHasLocation || !M || FVector::Dist2D(M->GetActorLocation(), Location) > O.Radius) continue;
                }
                Hits.Add({Def.Id, O.Id});
            }
        }
    }
    for (const TPair<FName, FName>& Hit : Hits)
    {
        AdvanceObjective(Hit.Key, Hit.Value, Count);
    }
}

TArray<FReflectionsQuestLine> UReflectionsQuestSubsystem::ToLines(const TArray<FReflectionsQuestLineDef>& Defs, FName DefaultSpeaker)
{
    TArray<FReflectionsQuestLine> Out;
    for (const FReflectionsQuestLineDef& D : Defs)
    {
        if (D.Text.IsEmpty()) continue;
        FReflectionsQuestLine L;
        L.Speaker = D.Speaker.IsNone() ? DefaultSpeaker : D.Speaker;
        L.Text = D.Text;
        L.Id = D.Id;
        L.Delay = D.Delay;
        Out.Add(L);
    }
    return Out;
}

void UReflectionsQuestSubsystem::MarkAfterSaid(FName QuestId)
{
    if (FReflectionsQuestState* S = States.Find(QuestId)) S->bAfterSaid = true;
}

TArray<FReflectionsQuestLine> UReflectionsQuestSubsystem::GetStepTalkLines(FName Person) const
{
    TArray<FReflectionsQuestLine> Out;
    for (const FReflectionsQuestDef& Def : Quests)
    {
        if (const FReflectionsQuestStep* Step = GetCurrentStep(Def.Id))
        {
            for (const FReflectionsQuestTalk& T : Step->Talk)
            {
                if (T.Person == Person) Out.Append(ToLines(T.Lines, Person));
            }
        }
    }
    return Out;
}

bool UReflectionsQuestSubsystem::IsOfferAllowedByLives(FName Person) const
{
    UObject* Lives = WorldSubsystemByName(GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr, LivesClass);
    bool bAllowed = true;
    if (Lives && !CallNamed(Lives, TEXT("IsQuestAvailable"), {FNamedArg::Of(Person)}, &bAllowed)) return true;
    return bAllowed;
}

// ---- Consequences ---------------------------------------------------------------------------------------------

float UReflectionsQuestSubsystem::GetPlayerHeat() const
{
    UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
    UReflectionsNpcSubsystem* Npcs = World ? World->GetSubsystem<UReflectionsNpcSubsystem>() : nullptr;
    float Heat = 0.0f;
    if (!Npcs || !CallNamed(Npcs, TEXT("GetPlayerHeat"), {}, nullptr, &Heat)) return 0.0f;
    // Either scale: 0..1, or 0..100.
    return FMath::Clamp(Heat > 1.5f ? Heat / 100.0f : Heat, 0.0f, 1.0f);
}

bool UReflectionsQuestSubsystem::IsWaryOfHero(FName PersonId, FText* OutLine, const AActor* Npc) const
{
    if (PersonId.IsNone()) return false;
    const float With = GetStanding(PersonId);
    float Threshold = ReflectionsQuestCVars::HeatRefuse + (With >= 60.0f ? 0.5f : With >= 25.0f ? 0.25f : 0.0f);
    if (const UReflectionsNpcReactionComponent* Npcc = Npc ? Npc->FindComponentByClass<UReflectionsNpcReactionComponent>() : nullptr)
    {
        if (Npcc->Disposition == EReflectionsNpcDisposition::Timid) Threshold -= 0.15f;
        else if (Npcc->Disposition == EReflectionsNpcDisposition::Brave) Threshold += 0.15f;
    }
    const float Heat = GetPlayerHeat();
    if (Heat < Threshold) return false;
    if (OutLine)
    {
        static const FText Lines[] = {
            LOCTEXT("Wary1", "Not today. Half the street saw what you did. Come back when they've stopped talking."),
            LOCTEXT("Wary2", "I've work that needs doing, but not by someone the Watch is looking for."),
            LOCTEXT("Wary3", "Keep walking. I don't know you, and I'd like it to stay that way for a while."),
        };
        *OutLine = Lines[GetTypeHash(PersonId) % UE_ARRAY_COUNT(Lines)];
    }
    return true;
}

void UReflectionsQuestSubsystem::NotifyCrimeAgainst(FName PersonId, float Severity)
{
    if (PersonId.IsNone() || DeadPeople.Contains(PersonId)) return;
    AdjustStanding(PersonId, -20.0f * FMath::Clamp(Severity, 0.0f, 1.0f));
}

float UReflectionsQuestSubsystem::CrimeSeverity(FName Crime)
{
    const FString C = Crime.ToString();
    if (C.Equals(TEXT("Murder"), ESearchCase::IgnoreCase)) return 1.0f;
    if (C.Equals(TEXT("Assault"), ESearchCase::IgnoreCase)) return 0.5f;
    if (C.Equals(TEXT("Theft"), ESearchCase::IgnoreCase)) return 0.35f;
    return 0.2f;
}

bool UReflectionsQuestSubsystem::StillNeeds(const FReflectionsQuestDef& Def, const FReflectionsQuestState& S, FName Person) const
{
    if (Def.FailIfDies == Person) return true;
    const int32 Current = Def.Steps.IndexOfByPredicate([&S](const FReflectionsQuestStep& St) { return St.Id == S.StepId; });
    const bool bNotStarted = S.Status != EReflectionsQuestStatus::Active && S.Status != EReflectionsQuestStatus::ReadyToTurnIn;
    if (S.Status == EReflectionsQuestStatus::ReadyToTurnIn) return false;
    for (int32 si = bNotStarted ? 0 : FMath::Max(Current, 0); si < Def.Steps.Num(); ++si)
    {
        const FReflectionsQuestStep& Step = Def.Steps[si];
        for (int32 i = 0; i < Step.Objectives.Num(); ++i)
        {
            const FReflectionsQuestObjective& O = Step.Objectives[i];
            if (O.bOptional) continue;
            if (si == Current && !bNotStarted && S.Objectives.IsValidIndex(i) && S.Objectives[i].bDone) continue;
            const bool bPersonTarget = O.Type == EReflectionsObjectiveType::TalkTo || O.Type == EReflectionsObjectiveType::Deliver ||
                ((O.Type == EReflectionsObjectiveType::SpellHit || O.Type == EReflectionsObjectiveType::Protect) && FindPerson(O.Target));
            if (bPersonTarget && O.Target == Person) return true;
        }
        if (!Step.Choices.IsEmpty() && (Step.ChoicePerson == Person || (Step.ChoicePerson.IsNone() && Def.Giver == Person))) return true;
    }
    return false;
}

bool UReflectionsQuestSubsystem::SkipObjectivesFor(const FReflectionsQuestDef& Def, FReflectionsQuestState& S, FName Person)
{
    const FReflectionsQuestStep* Step = Def.FindStep(S.StepId);
    if (!Step) return false;
    bool bAny = false;
    for (int32 i = 0; i < Step->Objectives.Num() && i < S.Objectives.Num(); ++i)
    {
        const FReflectionsQuestObjective& O = Step->Objectives[i];
        if (O.Target == Person && !S.Objectives[i].bDone &&
            (O.Type == EReflectionsObjectiveType::TalkTo || O.Type == EReflectionsObjectiveType::Deliver || O.Type == EReflectionsObjectiveType::SpellHit || O.Type == EReflectionsObjectiveType::Protect))
        {
            S.Objectives[i].Progress = FMath::Max(O.Count, 1);
            S.Objectives[i].bDone = true;
            bAny = true;
        }
    }
    return bAny;
}

void UReflectionsQuestSubsystem::NotifyPersonDied(FName PersonId, bool bByHero)
{
    if (PersonId.IsNone() || DeadPeople.Contains(PersonId)) return;
    DeadPeople.Add(PersonId);
    const FText Name = GetPersonName(PersonId);
    const FText Who = Name.IsEmpty() ? SpacedId(PersonId) : Name;
    TArray<FName> Fails, Finish, Skip;
    ++ChangeDepth;
    for (const FReflectionsQuestDef& Def : Quests)
    {
        FReflectionsQuestState* S = States.Find(Def.Id);
        if (!S || S->Status == EReflectionsQuestStatus::Completed || S->Status == EReflectionsQuestStatus::Failed) continue;
        const bool bGiver = Def.Giver == PersonId;
        const bool bNeeded = StillNeeds(Def, *S, PersonId);
        if (!bGiver && !bNeeded) continue;
        if (Def.bMain)
        {
            // The story goes on: whatever beat needed them is passed over.
            if (S->Status == EReflectionsQuestStatus::Active) Skip.Add(Def.Id);
            continue;
        }
        const bool bStarted = S->Status == EReflectionsQuestStatus::Active || S->Status == EReflectionsQuestStatus::ReadyToTurnIn;
        if (!bStarted)
        {
            // Offered (or never heard of): it simply won't happen now.
            S->Status = EReflectionsQuestStatus::Failed;
            S->EndNote = FText::Format(bByHero ? LOCTEXT("DeadOfferHero", "{0} died by my hand. Whatever they wanted from me went with them.")
                : LOCTEXT("DeadOffer", "{0} is dead. Whatever they wanted from me went with them."), Who);
            AddUnlock(FName(*FString::Printf(TEXT("QuestFailed_%s"), *Def.Id.ToString())), Def.Id);
            continue;
        }
        if (bNeeded)
        {
            S->EndNote = FText::Format(bByHero ? LOCTEXT("DeadNeededHero", "{0} died by my hand. There's no finishing this now.")
                : LOCTEXT("DeadNeeded", "{0} is dead. There's no finishing this now."), Who);
            Fails.Add(Def.Id);
        }
        else
        {
            // The alternative: only the giver is gone. Finish the work anyway; there is no one to bring it back to.
            S->bGiverLost = true;
            S->EndNote = FText::Format(LOCTEXT("DeadGiver", "{0} is dead. I can still see it through, though there's no one to bring it back to."), Who);
            if (S->Status == EReflectionsQuestStatus::ReadyToTurnIn) Finish.Add(Def.Id);
            else PushBanner(LOCTEXT("BannerGiverLost", "NO ONE TO RETURN TO"), Def.Title, S->EndNote, BannerPaper);
        }
    }
    for (const FName& Id : Fails) FailQuest(Id);
    for (const FName& Id : Finish)
    {
        const FReflectionsQuestDef* Def = FindQuest(Id);
        FReflectionsQuestState* S = States.Find(Id);
        if (Def && S) { S->Status = EReflectionsQuestStatus::Active; FinishQuest(*Def, *S); }
    }
    for (const FName& Id : Skip)
    {
        const FReflectionsQuestDef* Def = FindQuest(Id);
        FReflectionsQuestState* S = States.Find(Id);
        if (Def && S) { SkipObjectivesFor(*Def, *S, PersonId); CheckStepComplete(*Def, *S); }
    }
    --ChangeDepth;
    AutoTrack();
    Changed();
}

// ---- Tracking ------------------------------------------------------------------------------------------------

void UReflectionsQuestSubsystem::SetTrackedQuest(FName QuestId)
{
    if (Tracked == QuestId) return;
    Tracked = QuestId;
    Broadcast(QuestId, NAME_None, NAME_None, EReflectionsQuestEventType::Tracked);
    Changed();
}

void UReflectionsQuestSubsystem::AutoTrack()
{
    const EReflectionsQuestStatus Current = GetStatus(Tracked);
    if (Current == EReflectionsQuestStatus::Active || Current == EReflectionsQuestStatus::ReadyToTurnIn) return;
    const TArray<FName> Journal = GetJournalQuests();
    // Prefer an unfinished side quest the hero is on, then the main story.
    FName Pick;
    for (const FName& Id : Journal)
    {
        const EReflectionsQuestStatus S = GetStatus(Id);
        const FReflectionsQuestDef* Def = FindQuest(Id);
        if (Def && !Def->bMain && (S == EReflectionsQuestStatus::Active || S == EReflectionsQuestStatus::ReadyToTurnIn)) { Pick = Id; break; }
    }
    if (Pick.IsNone())
    {
        for (const FName& Id : Journal)
        {
            const EReflectionsQuestStatus S = GetStatus(Id);
            if (S == EReflectionsQuestStatus::Active || S == EReflectionsQuestStatus::ReadyToTurnIn) { Pick = Id; break; }
        }
    }
    if (Pick != Tracked)
    {
        Tracked = Pick;
        Broadcast(Pick, NAME_None, NAME_None, EReflectionsQuestEventType::Tracked);
    }
}

TArray<FName> UReflectionsQuestSubsystem::GetJournalQuests() const
{
    struct FEntry { FName Id; int32 Group; int32 Sort; };
    TArray<FEntry> Entries;
    for (const FReflectionsQuestDef& Def : Quests)
    {
        if (!IsQuestVisible(Def)) continue;
        const EReflectionsQuestStatus S = GetStatus(Def.Id);
        int32 Group = -1;
        switch (S)
        {
        case EReflectionsQuestStatus::Active: Group = Def.bMain ? 0 : 2; break;
        case EReflectionsQuestStatus::ReadyToTurnIn: Group = 1; break;
        case EReflectionsQuestStatus::Completed: Group = Def.bMain ? 3 : 4; break;
        case EReflectionsQuestStatus::Failed: Group = (States.Contains(Def.Id) && States[Def.Id].bSeen) ? 5 : -1; break;
        default: break;
        }
        if (Group >= 0) Entries.Add({Def.Id, Group, Def.SortOrder});
    }
    Entries.StableSort([](const FEntry& A, const FEntry& B) { return A.Group != B.Group ? A.Group < B.Group : A.Sort < B.Sort; });
    TArray<FName> Out;
    for (const FEntry& E : Entries) Out.Add(E.Id);
    return Out;
}

// ---- Items, standing, unlocks --------------------------------------------------------------------------------

void UReflectionsQuestSubsystem::GiveItem(FName Item, int32 Count)
{
    if (Item.IsNone() || Count <= 0) return;
    Items.FindOrAdd(Item) += Count;
    Changed();
}

bool UReflectionsQuestSubsystem::TakeItem(FName Item, int32 Count)
{
    int32* Have = Items.Find(Item);
    if (!Have || *Have < Count) return false;
    *Have -= Count;
    if (*Have <= 0) Items.Remove(Item);
    Changed();
    return true;
}

int32 UReflectionsQuestSubsystem::GetItemCount(FName Item) const
{
    const int32* Have = Items.Find(Item);
    return Have ? *Have : 0;
}

float UReflectionsQuestSubsystem::GetStanding(FName Person) const
{
    const float* V = Standing.Find(Person);
    return V ? *V : 0.0f;
}

void UReflectionsQuestSubsystem::AdjustStanding(FName Person, float Delta)
{
    if (Person.IsNone() || FMath::IsNearlyZero(Delta)) return;
    float& V = Standing.FindOrAdd(Person);
    V = FMath::Clamp(V + Delta, -100.0f, 100.0f);
    OnStandingChanged.Broadcast(Person, V);
    Changed();
}

void UReflectionsQuestSubsystem::AddUnlock(FName Unlock, FName SourceQuest)
{
    if (Unlock.IsNone() || Unlocks.Contains(Unlock)) return;
    Unlocks.Add(Unlock);
    if (Unlock == TEXT("Silverer_RecordClean") && !bApplying)
    {
        UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
        if (UReflectionsNpcSubsystem* Npcs = World ? World->GetSubsystem<UReflectionsNpcSubsystem>() : nullptr) CallNamed(Npcs, TEXT("ClearPlayerHeat"), {});
    }
    OnUnlock.Broadcast(Unlock, SourceQuest);
    if (!bApplying)
    {
        // Story flags (Hal_Home, Bell_Lane_Lit...) live in the lives system too; it saves them and acts on them.
        if (UObject* Lives = WorldSubsystemByName(GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr, LivesClass))
        {
            CallNamed(Lives, TEXT("SetStoryFlag"), {FNamedArg::Of(Unlock), FNamedArg::Of(true)});
        }
    }
    bAvailabilityDirty = true;
}

// ---- Rewards -------------------------------------------------------------------------------------------------

void UReflectionsQuestSubsystem::GiveReward(const FReflectionsQuestReward& Reward, FName QuestId)
{
    if (bApplying) return;
    UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
    APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
    APawn* Pawn = PC ? PC->GetPawn() : nullptr;

    if (Reward.Coins > 0 && World)
    {
        EReflectionsWorld Side = UReflectionsWorldLibrary::GetCurrentWorld(World);
        ReflectionsQuest::ToWorld(Reward.CoinSide, Side);
        UReflectionsWorldLibrary::AwardCoin(World, Side, Reward.Coins);
    }
    if (Reward.Mana > 0.0f && Pawn)
    {
        // Spell driver's RestoreMana(float), by name (no compile dependency on the hero code).
        bool bDone = false;
        for (UActorComponent* Component : Pawn->GetComponents())
        {
            if (Component && CallNamed(Component, TEXT("RestoreMana"), {FNamedArg::Of(Reward.Mana)}))
            {
                bDone = true;
                break;
            }
        }
        if (!bDone)
        {
            UE_LOG(LogReflectionsQuest, Warning, TEXT("Quest %s: mana reward skipped (no RestoreMana on the hero)."), *QuestId.ToString());
        }
    }
    float Total = 0.0f;
    for (const FReflectionsReputationGrant& G : Reward.Reputation)
    {
        if (!DeadPeople.Contains(G.Person)) AdjustStanding(G.Person, G.Amount);
        Total += G.Amount;
    }
    if (!FMath::IsNearlyZero(Total) && World && Pawn)
    {
        if (UReflectionsReputationSubsystem* Rep = World->GetSubsystem<UReflectionsReputationSubsystem>())
        {
            Rep->AdjustReputation(Pawn, Total * 0.5f);
        }
    }
    for (const FName& Item : Reward.Items) GiveItem(Item, 1);
    for (const FName& Unlock : Reward.Unlocks) AddUnlock(Unlock, QuestId);
}

FText UReflectionsQuestSubsystem::DescribeReward(const FReflectionsQuestReward& Reward) const
{
    TArray<FText> Parts;
    if (Reward.Coins > 0)
    {
        Parts.Add(FText::Format(LOCTEXT("RewardShards", "+{0} {0}|plural(one=mirror shard,other=mirror shards)"), Reward.Coins));
    }
    if (Reward.Mana > 0.0f)
    {
        Parts.Add(FText::Format(LOCTEXT("RewardMana", "+{0} mana"), FMath::RoundToInt(Reward.Mana)));
    }
    for (const FReflectionsReputationGrant& G : Reward.Reputation)
    {
        Parts.Add(FText::Format(G.Amount >= 0 ? LOCTEXT("RewardRepUp", "{0} trusts you more") : LOCTEXT("RewardRepDown", "{0} trusts you less"), GetPersonName(G.Person)));
    }
    return FText::Join(FText::FromString(TEXT("   ")), Parts);
}

FText UReflectionsQuestSubsystem::FormatObjective(const FReflectionsQuestObjective& O, const FReflectionsObjectiveState* OS) const
{
    FText Base = O.Text;
    if (Base.IsEmpty())
    {
        switch (O.Type)
        {
        case EReflectionsObjectiveType::TalkTo: Base = FText::Format(LOCTEXT("ObjTalk", "Speak with {0}"), GetPersonName(O.Target)); break;
        case EReflectionsObjectiveType::GoTo: Base = FText::Format(LOCTEXT("ObjGo", "Go to {0}"), SpacedId(O.Target)); break;
        case EReflectionsObjectiveType::Collect: Base = FText::Format(LOCTEXT("ObjCollect", "Find {0}"), GetItemName(O.Target)); break;
        case EReflectionsObjectiveType::Deliver: Base = FText::Format(LOCTEXT("ObjDeliver", "Bring {0} to {1}"), GetItemName(O.Item), GetPersonName(O.Target)); break;
        case EReflectionsObjectiveType::Defeat: Base = FText::Format(LOCTEXT("ObjDefeat", "Defeat {0}"), SpacedId(O.Target)); break;
        case EReflectionsObjectiveType::SpellHit: Base = FText::Format(LOCTEXT("ObjHit", "Strike {0} with {1}"), SpacedId(O.Target), SpacedId(O.Spell)); break;
        case EReflectionsObjectiveType::WorldJump: Base = LOCTEXT("ObjJump", "Step through to another side"); break;
        case EReflectionsObjectiveType::Protect: Base = FText::Format(LOCTEXT("ObjProtect", "Hold {0}"), SpacedId(O.Target)); break;
        case EReflectionsObjectiveType::Event: Base = SpacedId(O.Target); break;
        }
    }
    const int32 Progress = OS ? OS->Progress : 0;
    FFormatNamedArguments Args;
    Args.Add(TEXT("count"), Progress);
    Args.Add(TEXT("total"), O.Count);
    Base = FText::Format(Base, Args);
    if (O.Type == EReflectionsObjectiveType::Protect && OS && !OS->bDone && O.Seconds > 0.0f && OS->Held > 0.0f)
    {
        return FText::Format(LOCTEXT("ObjProtectTime", "{0}  {1}s"), Base, FMath::Max(0, FMath::CeilToInt(O.Seconds - OS->Held)));
    }
    if (O.Count > 1 && !O.Text.ToString().Contains(TEXT("{count}")))
    {
        return FText::Format(LOCTEXT("ObjCount", "{0}  {1}/{2}"), Base, Progress, O.Count);
    }
    return Base;
}

FText UReflectionsQuestSubsystem::TakeHint(FName QuestId)
{
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    FReflectionsQuestState* S = States.Find(QuestId);
    if (!Def || !S) return FText::GetEmpty();
    if (S->Status == EReflectionsQuestStatus::ReadyToTurnIn)
    {
        return FText::Format(LOCTEXT("HintTurnIn", "Take it back to {0}."), GetPersonName(Def->Giver));
    }
    const FReflectionsQuestStep* Step = Def->FindStep(S->StepId);
    if (!Step) return FText::GetEmpty();
    for (int32 i = 0; i < Step->Objectives.Num() && i < S->Objectives.Num(); ++i)
    {
        FReflectionsObjectiveState& OS = S->Objectives[i];
        const FReflectionsQuestObjective& O = Step->Objectives[i];
        if (OS.bDone || O.bOptional) continue;
        if (O.Hints.IsEmpty()) return FormatObjective(O, &OS);
        const FText Hint = O.Hints[FMath::Min(OS.HintsGiven, O.Hints.Num() - 1)];
        OS.HintsGiven = FMath::Min(OS.HintsGiven + 1, O.Hints.Num());
        return Hint;
    }
    return Step->Description;
}

// ---- Talking -------------------------------------------------------------------------------------------------

FName UReflectionsQuestSubsystem::GetPersonId(const AActor* Actor)
{
    if (!Actor) return NAME_None;
    static const FString Prefix(TEXT("Person_"));
    for (const FName& Tag : Actor->Tags)
    {
        const FString S = Tag.ToString();
        if (S.StartsWith(Prefix, ESearchCase::IgnoreCase) && S.Len() > Prefix.Len()) return FName(*S.Mid(Prefix.Len()));
    }
    // A person's own archetype (NPC_Type_<PersonId>) also counts, so a unique NPC needs no extra tag.
    if (const UReflectionsQuestSubsystem* Self = Get(Actor))
    {
        if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Actor))
        {
            if (const UReflectionsNpcArchetype* Arch = Npcs->ResolveArchetype(Actor))
            {
                if (Self->FindPerson(Arch->ArchetypeId)) return Arch->ArchetypeId;
            }
        }
    }
    return NAME_None;
}

TArray<FString> UReflectionsQuestSubsystem::GetQuestActions(AActor* Npc) const
{
    TArray<FString> Out;
    const FName Person = GetPersonId(Npc);
    if (Person.IsNone()) return Out;
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(Npc))
    {
        if (Npcs->IsHostileToPlayer(Npc)) return Out;
    }
    for (const FReflectionsQuestDef& Def : Quests)
    {
        if (!IsQuestVisible(Def)) continue;
        const FString Q = Def.Id.ToString();
        const EReflectionsQuestStatus Status = GetStatus(Def.Id);
        if (Def.Giver == Person)
        {
            if (Status == EReflectionsQuestStatus::Available && RequirementsMet(Def) && IsOfferAllowedByLives(Person) && (Def.bMain || !IsWaryOfHero(Person, nullptr, Npc)) &&
                (Def.WantedLines.IsEmpty() || GetPlayerHeat() < 0.5f))
            {
                Out.Add(TEXT("offer_quest:") + Q);
                Out.Add(TEXT("accept:") + Q);
                if (!Def.bMain) Out.Add(TEXT("decline:") + Q);
            }
            else if (Status == EReflectionsQuestStatus::ReadyToTurnIn)
            {
                Out.Add(TEXT("turn_in:") + Q);
            }
            else if (Status == EReflectionsQuestStatus::Active)
            {
                Out.Add(TEXT("give_hint:") + Q);
            }
        }
        if (Status != EReflectionsQuestStatus::Active) continue;
        const FReflectionsQuestState* S = States.Find(Def.Id);
        const FReflectionsQuestStep* Step = Def.FindStep(S->StepId);
        if (!Step) continue;
        bool bRequiredDone = true;
        for (int32 i = 0; i < Step->Objectives.Num(); ++i)
        {
            const FReflectionsQuestObjective& O = Step->Objectives[i];
            const bool bDone = S->Objectives.IsValidIndex(i) && S->Objectives[i].bDone;
            if (!O.bOptional && !bDone) bRequiredDone = false;
            if (bDone || O.Target != Person) continue;
            if (O.Type == EReflectionsObjectiveType::TalkTo) Out.AddUnique(TEXT("talk:") + Q);
            if (O.Type == EReflectionsObjectiveType::Deliver && GetItemCount(O.Item) > 0) Out.AddUnique(TEXT("deliver:") + Q);
        }
        if (bRequiredDone && !Step->Choices.IsEmpty() && (Step->ChoicePerson == Person || (Step->ChoicePerson.IsNone() && Def.Giver == Person)))
        {
            for (const FReflectionsQuestChoice& C : Step->Choices) Out.Add(FString::Printf(TEXT("choose:%s.%s"), *Q, *C.Id.ToString()));
        }
    }
    return Out;
}

bool UReflectionsQuestSubsystem::ExecuteQuestAction(AActor* Npc, const FString& Action, FString& OutReason, FString& OutSay)
{
    OutReason.Reset();
    OutSay.Reset();
    if (!GetQuestActions(Npc).Contains(Action))
    {
        const FName Who = GetPersonId(Npc);
        OutReason = IsPersonDead(Who) ? TEXT("this person is dead")
            : (Action.StartsWith(TEXT("offer_quest:")) || Action.StartsWith(TEXT("accept:"))) && IsWaryOfHero(Who, nullptr, Npc)
                ? TEXT("wary of the hero: too much trouble follows them (player heat); won't offer work until it cools")
                : TEXT("not possible right now");
        return false;
    }
    FString Verb, Arg;
    SplitAction(Action, Verb, Arg);
    if (Verb == TEXT("choose"))
    {
        FString QuestStr, ChoiceStr;
        Arg.Split(TEXT("."), &QuestStr, &ChoiceStr);
        const FReflectionsQuestStep* Step = GetCurrentStep(FName(*QuestStr));
        const FReflectionsQuestChoice* C = Step ? Step->Choices.FindByPredicate([&ChoiceStr](const FReflectionsQuestChoice& E) { return E.Id == FName(*ChoiceStr); }) : nullptr;
        if (C) OutSay = C->Response.ToString();
        NotifyTalkedTo(Npc);
        return MakeChoice(FName(*QuestStr), FName(*ChoiceStr)) || (OutReason = TEXT("choice refused"), false);
    }
    const FName QuestId(*Arg);
    const FReflectionsQuestDef* Def = FindQuest(QuestId);
    if (!Def)
    {
        OutReason = TEXT("unknown quest");
        return false;
    }
    const auto Join = [](const TArray<FReflectionsQuestLineDef>& Lines)
    {
        FString S;
        for (const FReflectionsQuestLineDef& L : Lines) S += (S.IsEmpty() ? TEXT("") : TEXT(" ")) + L.Text.ToString();
        return S;
    };
    if (Verb == TEXT("offer_quest"))
    {
        StateFor(QuestId).bSeen = true;
        OutSay = Join(Def->OfferLines);
        if (OutSay.IsEmpty()) OutSay = Def->Summary.ToString();
        Broadcast(QuestId, NAME_None, NAME_None, EReflectionsQuestEventType::Offered);
        return true;
    }
    if (Verb == TEXT("accept"))
    {
        OutSay = Join(Def->AcceptLines);
        NotifyTalkedTo(Npc);
        return AcceptQuest(QuestId) || (OutReason = TEXT("could not start"), false);
    }
    if (Verb == TEXT("decline"))
    {
        OutSay = Join(Def->DeclineLines);
        return DeclineQuest(QuestId) || (OutReason = TEXT("cannot decline"), false);
    }
    if (Verb == TEXT("turn_in"))
    {
        OutSay = Join(Def->TurnInLines);
        return TurnInQuest(QuestId) || (OutReason = TEXT("not finished"), false);
    }
    if (Verb == TEXT("give_hint"))
    {
        OutSay = TakeHint(QuestId).ToString();
        return !OutSay.IsEmpty() || (OutReason = TEXT("no hint"), false);
    }
    if (Verb == TEXT("talk") || Verb == TEXT("deliver"))
    {
        NotifyTalkedTo(Npc);
        return true;
    }
    OutReason = TEXT("unknown action");
    return false;
}

void UReflectionsQuestSubsystem::NotifyTalkedTo(AActor* Npc)
{
    const FName Person = GetPersonId(Npc);
    if (Person.IsNone()) return;
    TArray<TPair<FName, FName>> Talks;
    TArray<TTuple<FName, FName, FName, int32>> Deliveries;
    for (const FReflectionsQuestDef& Def : Quests)
    {
        const FReflectionsQuestState* S = States.Find(Def.Id);
        if (!S || S->Status != EReflectionsQuestStatus::Active) continue;
        const FReflectionsQuestStep* Step = Def.FindStep(S->StepId);
        if (!Step) continue;
        for (int32 i = 0; i < Step->Objectives.Num(); ++i)
        {
            const FReflectionsQuestObjective& O = Step->Objectives[i];
            if (O.Target != Person || (S->Objectives.IsValidIndex(i) && S->Objectives[i].bDone)) continue;
            if (O.Type == EReflectionsObjectiveType::TalkTo) Talks.Add({Def.Id, O.Id});
            if (O.Type == EReflectionsObjectiveType::Deliver) Deliveries.Add(MakeTuple(Def.Id, O.Id, O.Item, O.Count));
        }
    }
    for (const TTuple<FName, FName, FName, int32>& D : Deliveries)
    {
        const FReflectionsObjectiveState* OS = FindObjectiveState(D.Get<0>(), D.Get<1>());
        const int32 Need = D.Get<3>() - (OS ? OS->Progress : 0);
        const int32 Give = FMath::Min(Need, GetItemCount(D.Get<2>()));
        if (Give > 0 && TakeItem(D.Get<2>(), Give))
        {
            AdvanceObjective(D.Get<0>(), D.Get<1>(), Give);
        }
    }
    for (const TPair<FName, FName>& T : Talks)
    {
        AdvanceObjective(T.Key, T.Value, 1);
    }
    NotifyEvent(TEXT("Talked"), Person);
}

TArray<FReflectionsQuestLine> UReflectionsQuestSubsystem::GetLinesFor(AActor* Npc, const FString& Action) const
{
    TArray<FReflectionsQuestLine> Out;
    const FName Person = GetPersonId(Npc);
    FString Verb, Arg;
    SplitAction(Action, Verb, Arg);
    FString QuestStr = Arg, ChoiceStr;
    Arg.Split(TEXT("."), &QuestStr, &ChoiceStr);
    const FReflectionsQuestDef* Def = FindQuest(FName(*QuestStr));
    const auto Add = [&Out, Person](const TArray<FReflectionsQuestLineDef>& Lines, FName Speaker)
    {
        Out.Append(ToLines(Lines, Speaker.IsNone() ? Person : Speaker));
    };
    if (!Def)
    {
        Out = GetStepTalkLines(Person);
        if (!Out.IsEmpty()) return Out;
        if (GetPlayerHeat() >= 0.5f)
        {
            for (const FReflectionsQuestDef& D : Quests)
            {
                if (D.Giver == Person && !D.WantedLines.IsEmpty() && GetStatus(D.Id) == EReflectionsQuestStatus::Available && RequirementsMet(D))
                {
                    return ToLines(D.WantedLines, Person);
                }
            }
        }
        FText Wary;
        if (IsWaryOfHero(Person, &Wary, Npc) && Quests.ContainsByPredicate([this, Person](const FReflectionsQuestDef& D)
            { return D.Giver == Person && !D.bMain && GetStatus(D.Id) == EReflectionsQuestStatus::Available && RequirementsMet(D); }))
        {
            FReflectionsQuestLine L;
            L.Speaker = Person;
            L.Text = Wary;
            Out.Add(L);
            return Out;
        }
        if (const FReflectionsQuestPerson* P = FindPerson(Person))
        {
            if (!P->IdleLines.IsEmpty())
            {
                FReflectionsQuestLine L;
                L.Speaker = Person;
                L.Text = P->IdleLines[FMath::RandRange(0, P->IdleLines.Num() - 1)];
                Out.Add(L);
            }
        }
        return Out;
    }
    if (Verb == TEXT("offer_quest") || Verb == TEXT("accept"))
    {
        Add(Def->OfferLines, NAME_None);
        if (Out.IsEmpty() && !Def->Summary.IsEmpty())
        {
            FReflectionsQuestLine L;
            L.Speaker = Person;
            L.Text = Def->Summary;
            Out.Add(L);
        }
    }
    else if (Verb == TEXT("turn_in")) Add(Def->TurnInLines, NAME_None);
    else if (Verb == TEXT("give_hint")) Add(Def->ReminderLines, NAME_None);
    else if (Verb == TEXT("choose"))
    {
        if (const FReflectionsQuestStep* Step = GetCurrentStep(Def->Id))
        {
            Add(Step->Lines, Step->Speaker.IsNone() ? Def->Giver : Step->Speaker);
        }
    }
    return Out;
}

FString UReflectionsQuestSubsystem::GetQuestContext(AActor* Npc) const
{
    const FName Person = GetPersonId(Npc);
    TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("person"), Person.ToString());
    if (const FReflectionsQuestPerson* P = FindPerson(Person))
    {
        Root->SetStringField(TEXT("name"), P->DisplayName.ToString());
        Root->SetStringField(TEXT("title"), P->Title.ToString());
    }
    Root->SetNumberField(TEXT("standing"), GetStanding(Person));
    FText WaryLine;
    if (IsWaryOfHero(Person, &WaryLine, Npc))
    {
        Root->SetBoolField(TEXT("wary_of_hero"), true);
        Root->SetStringField(TEXT("wary_reason"), TEXT("Too much trouble follows the hero right now (player heat). Refuse new work, in character, e.g.: ") + WaryLine.ToString());
    }
    TArray<TSharedPtr<FJsonValue>> List;
    const TArray<FString> Actions = GetQuestActions(Npc);
    for (const FReflectionsQuestDef& Def : Quests)
    {
        if (!IsQuestVisible(Def)) continue;
        const FReflectionsQuestState* S = States.Find(Def.Id);
        const bool bGiver = Def.Giver == Person;
        bool bInvolved = bGiver;
        const FReflectionsQuestStep* Step = GetCurrentStep(Def.Id);
        if (Step)
        {
            for (const FReflectionsQuestObjective& O : Step->Objectives) bInvolved |= O.Target == Person;
            bInvolved |= Step->ChoicePerson == Person;
        }
        if (!bInvolved) continue;
        TSharedRef<FJsonObject> Q = MakeShared<FJsonObject>();
        Q->SetStringField(TEXT("id"), Def.Id.ToString());
        Q->SetStringField(TEXT("title"), Def.Title.ToString());
        Q->SetStringField(TEXT("summary"), Def.Summary.ToString());
        Q->SetBoolField(TEXT("you_are_giver"), bGiver);
        const EReflectionsQuestStatus Status = S ? S->Status : EReflectionsQuestStatus::Unavailable;
        Q->SetStringField(TEXT("status"), StaticEnum<EReflectionsQuestStatus>()->GetNameStringByValue(static_cast<int64>(Status)));
        if (bGiver && !Def.OfferLines.IsEmpty() && Status == EReflectionsQuestStatus::Available)
        {
            FString Pitch;
            for (const FReflectionsQuestLineDef& L : Def.OfferLines) Pitch += L.Text.ToString() + TEXT(" ");
            Q->SetStringField(TEXT("pitch"), Pitch.TrimEnd());
        }
        if (Step)
        {
            Q->SetStringField(TEXT("current_step"), Step->Title.ToString());
            FString Objectives;
            for (int32 i = 0; i < Step->Objectives.Num(); ++i)
            {
                const FReflectionsObjectiveState* OS = S && S->Objectives.IsValidIndex(i) ? &S->Objectives[i] : nullptr;
                if (OS && OS->bDone) continue;
                Objectives += FormatObjective(Step->Objectives[i], OS).ToString() + TEXT("; ");
            }
            Q->SetStringField(TEXT("open_objectives"), Objectives);
        }
        List.Add(MakeShared<FJsonValueObject>(Q));
    }
    Root->SetArrayField(TEXT("quests"), List);
    TArray<TSharedPtr<FJsonValue>> ActionValues;
    for (const FString& A : Actions) ActionValues.Add(MakeShared<FJsonValueString>(A));
    Root->SetArrayField(TEXT("quest_actions"), ActionValues);
    FString Out;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
    FJsonSerializer::Serialize(Root, Writer);
    return Out;
}

bool UReflectionsQuestSubsystem::HandleTalkPressed(AActor* Npc)
{
    UReflectionsQuestWorldSubsystem* WorldQuests = UReflectionsQuestWorldSubsystem::Get(Npc);
    return WorldQuests && WorldQuests->OpenTalk(Npc, true);
}

void UReflectionsQuestSubsystem::OpenJournal()
{
    if (UReflectionsQuestWorldSubsystem* WorldQuests = UReflectionsQuestWorldSubsystem::Get(GetGameInstance()->GetWorld()))
    {
        WorldQuests->OpenJournal();
    }
}

bool UReflectionsQuestSubsystem::IsJournalOpen() const
{
    const UReflectionsQuestWorldSubsystem* WorldQuests = UReflectionsQuestWorldSubsystem::Get(GetGameInstance()->GetWorld());
    return WorldQuests && WorldQuests->IsJournalOpen();
}

// ---- Events --------------------------------------------------------------------------------------------------

void UReflectionsQuestSubsystem::Broadcast(FName QuestId, FName StepId, FName ObjectiveId, EReflectionsQuestEventType Type)
{
    if (bApplying) return;
    UE_LOG(LogReflectionsQuest, Log, TEXT("Quest %s: %s %s %s"), *QuestId.ToString(),
        *StaticEnum<EReflectionsQuestEventType>()->GetNameStringByValue(static_cast<int64>(Type)), *StepId.ToString(), *ObjectiveId.ToString());
    OnQuestEvent.Broadcast(QuestId, StepId, ObjectiveId, Type);
}

void UReflectionsQuestSubsystem::Changed()
{
    if (ChangeDepth > 0 || bApplying) return;
    OnQuestsChanged.Broadcast();
}

void UReflectionsQuestSubsystem::PushBanner(const FText& Kicker, const FText& Title, const FText& Detail, const FLinearColor& Color)
{
    if (bApplying) return;
    if (PendingBanners.Num() > 6) PendingBanners.RemoveAt(0);
    PendingBanners.Add({Kicker, Title, Detail, Color});
}

// ---- Save ----------------------------------------------------------------------------------------------------

FReflectionsQuestSnapshot UReflectionsQuestSubsystem::Capture() const
{
    FReflectionsQuestSnapshot Snap;
    Snap.bValid = true;
    for (const TPair<FName, FReflectionsQuestState>& Pair : States) Snap.Quests.Add(Pair.Value);
    for (const TPair<FName, int32>& Pair : Items) Snap.Items.Add({Pair.Key, Pair.Value});
    for (const TPair<FName, float>& Pair : Standing) Snap.Standing.Add({Pair.Key, Pair.Value});
    Snap.Unlocks = Unlocks.Array();
    Snap.Tracked = Tracked;
    Snap.Dead = DeadPeople.Array();
    return Snap;
}

void UReflectionsQuestSubsystem::Apply(const FReflectionsQuestSnapshot& Snap)
{
    bApplying = true;
    States.Reset();
    Items.Reset();
    Standing.Reset();
    Unlocks.Reset();
    for (const FReflectionsQuestState& S : Snap.Quests) States.Add(S.QuestId, S);
    for (const FReflectionsQuestItemCount& I : Snap.Items) Items.Add(I.Item, I.Count);
    for (const FReflectionsPersonStanding& P : Snap.Standing) Standing.Add(P.Person, P.Value);
    Unlocks.Append(Snap.Unlocks);
    Tracked = Snap.Tracked;
    DeadPeople.Reset();
    DeadPeople.Append(Snap.Dead);
    PendingBanners.Reset();
    EnsureStates();
    bApplying = false;
    RefreshAvailability();
    OnQuestsChanged.Broadcast();
}

void UReflectionsQuestSubsystem::ResetAll()
{
    bApplying = true;
    States.Reset();
    Items.Reset();
    Standing.Reset();
    Unlocks.Reset();
    DeadPeople.Reset();
    Tracked = NAME_None;
    PendingBanners.Reset();
    CheckpointSnapshot = FReflectionsQuestSnapshot();
    EnsureStates();
    bApplying = false;
    UGameplayStatics::DeleteGameInSlot(SlotName(), 0);
    RefreshAvailability();
    OnQuestsChanged.Broadcast();
}

void UReflectionsQuestSubsystem::WriteSlot(const FReflectionsQuestSnapshot& Snapshot) const
{
    UReflectionsQuestSave* Save = Cast<UReflectionsQuestSave>(UGameplayStatics::CreateSaveGameObject(UReflectionsQuestSave::StaticClass()));
    if (!Save) return;
    Save->Snapshot = Snapshot;
    UGameplayStatics::SaveGameToSlot(Save, SlotName(), 0);
}

void UReflectionsQuestSubsystem::HandleCheckpointSaved(const FReflectionsCheckpoint& Checkpoint)
{
    CheckpointSnapshot = Capture();
    CheckpointSnapshot.CheckpointSavedAt = Checkpoint.SavedAt;
    WriteSlot(CheckpointSnapshot);
}

void UReflectionsQuestSubsystem::HandleProgressRestored()
{
    const UReflectionsGameFlowSubsystem* Flow = GetGameInstance()->GetSubsystem<UReflectionsGameFlowSubsystem>();
    if (!Flow || !Flow->HasCheckpoint()) return;
    if (!CheckpointSnapshot.bValid || Flow->GetCheckpoint().SavedAt != CheckpointSnapshot.CheckpointSavedAt)
    {
        // A loaded save slot: game flow wrote that save's quest bytes back to our slot. Read it again once.
        if (const UReflectionsQuestSave* Save = Cast<UReflectionsQuestSave>(UGameplayStatics::LoadGameFromSlot(SlotName(), 0)))
        {
            CheckpointSnapshot = Save->Snapshot;
        }
    }
    if (!CheckpointSnapshot.bValid || Flow->GetCheckpoint().SavedAt != CheckpointSnapshot.CheckpointSavedAt)
    {
        UE_LOG(LogReflectionsQuest, Warning, TEXT("Checkpoint restored, but the quest save belongs to another checkpoint; quests keep their current state."));
        return;
    }
    Apply(CheckpointSnapshot);
    UE_LOG(LogReflectionsQuest, Log, TEXT("Quests restored to the checkpoint (%d quests)."), CheckpointSnapshot.Quests.Num());
}

FString UReflectionsQuestSubsystem::DescribeStatus() const
{
    FString Out = FString::Printf(TEXT("Quests: %d defined, %d people, tracked %s\n"), Quests.Num(), People.Num(), *Tracked.ToString());
    for (const FReflectionsQuestDef& Def : Quests)
    {
        const FReflectionsQuestState* S = States.Find(Def.Id);
        const EReflectionsQuestStatus Status = S ? S->Status : EReflectionsQuestStatus::Unavailable;
        Out += FString::Printf(TEXT("  %s%s [%s] step %s%s\n"), *Def.Id.ToString(), Def.bMain ? TEXT(" (main)") : TEXT(""),
            *StaticEnum<EReflectionsQuestStatus>()->GetNameStringByValue(static_cast<int64>(Status)), S ? *S->StepId.ToString() : TEXT("-"),
            IsQuestVisible(Def) ? TEXT("") : TEXT(" (hidden test)"));
        if (S && S->Status == EReflectionsQuestStatus::Active)
        {
            if (const FReflectionsQuestStep* Step = Def.FindStep(S->StepId))
            {
                for (int32 i = 0; i < Step->Objectives.Num(); ++i)
                {
                    const FReflectionsObjectiveState* OS = S->Objectives.IsValidIndex(i) ? &S->Objectives[i] : nullptr;
                    Out += FString::Printf(TEXT("      %s %s\n"), OS && OS->bDone ? TEXT("[x]") : TEXT("[ ]"), *FormatObjective(Step->Objectives[i], OS).ToString());
                }
            }
        }
    }
    FString ItemList;
    for (const TPair<FName, int32>& I : Items) ItemList += FString::Printf(TEXT("%s x%d, "), *I.Key.ToString(), I.Value);
    FString UnlockList;
    for (const FName& U : Unlocks) UnlockList += U.ToString() + TEXT(", ");
    Out += FString::Printf(TEXT("  items: %s\n  unlocks: %s\n"), *ItemList, *UnlockList);
    return Out;
}

// ---- Console -------------------------------------------------------------------------------------------------

#if !UE_BUILD_SHIPPING
namespace
{
    UReflectionsQuestSubsystem* QuestsOf(UWorld* World) { return UReflectionsQuestSubsystem::Get(World); }
}

static FAutoConsoleCommandWithWorld GQuestStatusCmd(TEXT("Quest.Status"), TEXT("Print every quest and the tracked objective."),
    FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
    {
        if (UReflectionsQuestSubsystem* Q = QuestsOf(World)) UE_LOG(LogReflectionsQuest, Display, TEXT("%s"), *Q->DescribeStatus());
    }));

static FAutoConsoleCommandWithWorldAndArgs GQuestAcceptCmd(TEXT("Quest.Accept"), TEXT("Quest.Accept <QuestId>"),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (UReflectionsQuestSubsystem* Q = QuestsOf(World); Q && Args.Num() > 0) Q->AcceptQuest(FName(*Args[0]));
    }));

static FAutoConsoleCommandWithWorldAndArgs GQuestStepCmd(TEXT("Quest.CompleteStep"), TEXT("Quest.CompleteStep <QuestId>: finish the current step."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (UReflectionsQuestSubsystem* Q = QuestsOf(World); Q && Args.Num() > 0) Q->CompleteStep(FName(*Args[0]));
    }));

static FAutoConsoleCommandWithWorldAndArgs GQuestObjectiveCmd(TEXT("Quest.CompleteObjective"), TEXT("Quest.CompleteObjective <QuestId> <ObjectiveId>"),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (UReflectionsQuestSubsystem* Q = QuestsOf(World); Q && Args.Num() > 1) Q->CompleteObjective(FName(*Args[0]), FName(*Args[1]));
    }));

static FAutoConsoleCommandWithWorldAndArgs GQuestTurnInCmd(TEXT("Quest.TurnIn"), TEXT("Quest.TurnIn <QuestId>"),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (UReflectionsQuestSubsystem* Q = QuestsOf(World); Q && Args.Num() > 0) Q->TurnInQuest(FName(*Args[0]));
    }));

static FAutoConsoleCommandWithWorldAndArgs GQuestChooseCmd(TEXT("Quest.Choose"), TEXT("Quest.Choose <QuestId> <ChoiceId>"),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (UReflectionsQuestSubsystem* Q = QuestsOf(World); Q && Args.Num() > 1) Q->MakeChoice(FName(*Args[0]), FName(*Args[1]));
    }));

static FAutoConsoleCommandWithWorldAndArgs GQuestEventCmd(TEXT("Quest.Event"), TEXT("Quest.Event <Key> [Arg] [Count]"),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (UReflectionsQuestSubsystem* Q = QuestsOf(World); Q && Args.Num() > 0)
            Q->NotifyEventCount(FName(*Args[0]), Args.Num() > 1 ? FName(*Args[1]) : NAME_None, Args.Num() > 2 ? FCString::Atoi(*Args[2]) : 1);
    }));

static FAutoConsoleCommandWithWorldAndArgs GQuestTrackCmd(TEXT("Quest.Track"), TEXT("Quest.Track <QuestId>"),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (UReflectionsQuestSubsystem* Q = QuestsOf(World); Q && Args.Num() > 0) Q->SetTrackedQuest(FName(*Args[0]));
    }));

static FAutoConsoleCommandWithWorldAndArgs GQuestGiveCmd(TEXT("Quest.GiveItem"), TEXT("Quest.GiveItem <ItemId> [Count]"),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (UReflectionsQuestSubsystem* Q = QuestsOf(World); Q && Args.Num() > 0) Q->GiveItem(FName(*Args[0]), Args.Num() > 1 ? FCString::Atoi(*Args[1]) : 1);
    }));

static FAutoConsoleCommandWithWorld GQuestResetCmd(TEXT("Quest.Reset"), TEXT("Forget all quest progress (and delete the quest save)."),
    FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
    {
        if (UReflectionsQuestSubsystem* Q = QuestsOf(World)) Q->ResetAll();
    }));

static FAutoConsoleCommandWithWorld GQuestReloadCmd(TEXT("Quest.Reload"), TEXT("Reload built-in quests and quest packs."),
    FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
    {
        if (UReflectionsQuestSubsystem* Q = QuestsOf(World)) { Q->ReloadContent(); Q->RefreshAvailability(); }
    }));

static FAutoConsoleCommandWithWorldAndArgs GQuestLoadJsonCmd(TEXT("Quest.LoadJson"),
    TEXT("Quest.LoadJson <quests.json> [people.json]: add quests from files (paths relative to the project)."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        UReflectionsQuestSubsystem* Q = QuestsOf(World);
        if (!Q || Args.Num() < 1) return;
        const auto ReadFile = [](const FString& In)
        {
            FString Text;
            const FString Path = FPaths::IsRelative(In) ? FPaths::Combine(FPaths::ProjectDir(), In) : In;
            FFileHelper::LoadFileToString(Text, *Path);
            return Text;
        };
        FString Report;
        Q->AddContentFromJson(ReadFile(Args[0]), Args.Num() > 1 ? ReadFile(Args[1]) : FString(), Report);
        UE_LOG(LogReflectionsQuest, Display, TEXT("Quest.LoadJson: %s"), *Report);
    }));
#endif

#undef LOCTEXT_NAMESPACE
