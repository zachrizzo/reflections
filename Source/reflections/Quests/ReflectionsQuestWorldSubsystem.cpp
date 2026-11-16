#include "Quests/ReflectionsQuestWorldSubsystem.h"

#include "Components/InputComponent.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFlow/ReflectionsGameFlowSubsystem.h"
#include "GameFlow/ReflectionsGameFlowWorldSubsystem.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Hero/ReflectionsHeroCharacter.h"
#include "Hero/ReflectionsSpellEventSubsystem.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "NavigationSystem.h"
#include "NPC/ReflectionsNpcArchetype.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "GameFlow/ReflectionsGameFlowSlate.h"
#include "NPC/ReflectionsNpcSubsystem.h"
#include "Lives/ReflectionsLivesSubsystem.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Quests/ReflectionsQuestItem.h"
#include "Quests/ReflectionsQuestSlate.h"
#include "Quests/ReflectionsStoryMarker.h"
#include "Voice/ReflectionsVoiceInteractionSubsystem.h"
#include "Sound/SoundBase.h"
#include "Components/AudioComponent.h"
#include "Worlds/ReflectionsSealedDoor.h"
#include "Villain/ReflectionsVillainSubsystem.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"
#include "Worlds/ReflectionsWorldPickups.h"

#define LOCTEXT_NAMESPACE "ReflectionsQuests"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsQuestWorld, Log, All);

namespace ReflectionsQuestWorldCVars
{
    static int32 Enabled = 1;
    static FAutoConsoleVariableRef CVarEnabled(TEXT("Quest.Enable"), Enabled, TEXT("0: no quest HUD, input or spawning in this session."));
    static int32 SpawnPeople = 1;
    static FAutoConsoleVariableRef CVarSpawn(TEXT("Quest.SpawnMissingPeople"), SpawnPeople,
        TEXT("1: quest givers the map lacks are spawned at their QuestGiver_<Id> marker (default)."));
    static float TalkRadius = 380.0f;
    static FAutoConsoleVariableRef CVarTalk(TEXT("Quest.TalkRadius"), TalkRadius, TEXT("How close (cm) the hero must be to open the talk card."));
}

namespace
{
    const FName StatefulKeys[] = {TEXT("PageFound"), TEXT("BookComplete"), TEXT("KeyFound"), TEXT("FinaleStarted"), TEXT("BossDefeated"),
        TEXT("Victory"), TEXT("QuestComplete"), TEXT("ItemFound"), TEXT("ShardCollected"), TEXT("DoorOpened"), TEXT("CutsceneDone"),
        TEXT("Unlocked")};

    const TCHAR* CutsceneClass = TEXT("/Script/reflections.ReflectionsCutsceneSubsystem");

    /** Calls a no-argument or one-FName UFUNCTION returning bool, by name. */
    bool CallBool(UObject* Target, const TCHAR* Function, FName Arg, bool bDefault)
    {
        UFunction* Fn = Target ? Target->FindFunction(FName(Function)) : nullptr;
        if (!Fn) return bDefault;
        uint8* Buffer = static_cast<uint8*>(FMemory_Alloca(FMath::Max<int32>(Fn->ParmsSize, 1)));
        FMemory::Memzero(Buffer, Fn->ParmsSize);
        for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
        {
            It->InitializeValue_InContainer(Buffer);
            if (FNameProperty* NP = CastField<FNameProperty>(*It); NP && !It->HasAnyPropertyFlags(CPF_ReturnParm)) NP->SetPropertyValue_InContainer(Buffer, Arg);
        }
        Target->ProcessEvent(Fn, Buffer);
        bool bResult = bDefault;
        if (FBoolProperty* Ret = CastField<FBoolProperty>(Fn->GetReturnProperty())) bResult = Ret->GetPropertyValue_InContainer(Buffer);
        for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It) It->DestroyValue_InContainer(Buffer);
        return bResult;
    }

    /** Element groups for SpellHit objectives ("Fire" matches Fire, FlameBurst and Firestorm). */
    bool SpellMatches(EHeroSpell Spell, FName Filter)
    {
        if (Filter.IsNone() || Filter == TEXT("Any")) return true;
        const FString Name = StaticEnum<EHeroSpell>()->GetNameStringByValue(static_cast<int64>(Spell));
        const FString F = Filter.ToString();
        if (Name.Equals(F, ESearchCase::IgnoreCase)) return true;
        struct FGroup { const TCHAR* Element; std::initializer_list<EHeroSpell> Spells; };
        static const FGroup Groups[] = {
            {TEXT("Fire"), {EHeroSpell::Fire, EHeroSpell::FlameBurst, EHeroSpell::Firestorm}},
            {TEXT("Ice"), {EHeroSpell::IceShard, EHeroSpell::FrostNova}},
            {TEXT("Frost"), {EHeroSpell::IceShard, EHeroSpell::FrostNova}},
            {TEXT("Water"), {EHeroSpell::Water, EHeroSpell::TidalSurge, EHeroSpell::WaterOrb}},
            {TEXT("Lightning"), {EHeroSpell::ChainLightning, EHeroSpell::LightningBolt, EHeroSpell::ThunderWave}},
            {TEXT("Earth"), {EHeroSpell::StoneShard, EHeroSpell::EarthShock}},
            {TEXT("Stone"), {EHeroSpell::StoneShard, EHeroSpell::EarthShock}},
            {TEXT("Air"), {EHeroSpell::ForcePush, EHeroSpell::Levitation}},
            {TEXT("Force"), {EHeroSpell::ForcePush}},
            {TEXT("Arcane"), {EHeroSpell::ArcaneBolt}},
            {TEXT("Life"), {EHeroSpell::Healing, EHeroSpell::GreaterHeal, EHeroSpell::HealingPulse, EHeroSpell::Shield}},
            {TEXT("Heal"), {EHeroSpell::Healing, EHeroSpell::GreaterHeal, EHeroSpell::HealingPulse}},
        };
        for (const FGroup& G : Groups)
        {
            if (F.Equals(G.Element, ESearchCase::IgnoreCase))
            {
                for (EHeroSpell S : G.Spells) if (S == Spell) return true;
                return false;
            }
        }
        return false;
    }

    bool IsHeroActor(const AActor* Actor, const APawn* Hero)
    {
        if (!Actor || !Hero) return false;
        return Actor == Hero || Actor->GetOwner() == Hero || Actor->GetInstigator() == Hero;
    }

    FText Spaced(FName Id)
    {
        FString S = Id.ToString();
        // Story marker names read as their last part: Mk_Gilt_Square_BellSquare -> "Bell Square".
        if (S.StartsWith(TEXT("Mk_")) || S.StartsWith(TEXT("Spot_")) || S.StartsWith(TEXT("Item_")) || S.StartsWith(TEXT("Tower_")))
        {
            int32 Cut = INDEX_NONE;
            if (S.FindLastChar(TEXT('_'), Cut)) S = S.Mid(Cut + 1);
        }
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
}

UReflectionsQuestWorldSubsystem* UReflectionsQuestWorldSubsystem::Get(const UObject* WorldContext)
{
    const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    return World ? World->GetSubsystem<UReflectionsQuestWorldSubsystem>() : nullptr;
}

bool UReflectionsQuestWorldSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UReflectionsQuestWorldSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsQuestWorldSubsystem, STATGROUP_Tickables);
}

void UReflectionsQuestWorldSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    bBegunPlay = true;
    if (const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        bHadCheckpoint = Flow->HasCheckpoint();
    }
    // Pages placed in this map, and which side each stands on (for "PageFound" objectives per side).
    for (TActorIterator<AReflectionsBookPagePickup> It(&InWorld); It; ++It)
    {
        const FName Id = It->PageId.IsNone() ? FName(*It->GetName()) : It->PageId;
        PageSides.Add(Id, SideOf(It->GetActorLocation()));
    }
    if (UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this))
    {
        // Side hints, so fallback markers for a person land on their own side.
        if (UReflectionsStoryMarkerSubsystem* Markers = UReflectionsStoryMarkerSubsystem::Get(this))
        {
            for (const FReflectionsQuestPerson& P : Quests->GetPeople())
            {
                EReflectionsWorld Side;
                if (ReflectionsQuest::ToWorld(P.Side, Side))
                {
                    for (const TCHAR* Kind : {TEXT("QuestGiver_"), TEXT("Home_")})
                    {
                        Markers->SetSideHint(FName(*(FString(Kind) + P.Id.ToString())), Side);
                    }
                }
            }
        }
        if (UReflectionsStoryMarkerSubsystem* Markers = UReflectionsStoryMarkerSubsystem::Get(this))
        {
            for (const TPair<FName, FName>& Alias : Quests->GetMarkerAliases()) Markers->SetAlias(Alias.Key, Alias.Value);
        }
        // Quests start on the first tick of play (see Tick): a new game clears game flow's checkpoint first, and
        // starting earlier would start the main quest twice (once here, once after the new-game reset).
    }
}

void UReflectionsQuestWorldSubsystem::Deinitialize()
{
    UnbindGame();
    RemoveWidgets();
    if (APlayerController* PC = Controller.Get())
    {
        if (Input) PC->PopInputComponent(Input);
    }
    Input = nullptr;
    Super::Deinitialize();
}

// ---- Binding -------------------------------------------------------------------------------------------------

void UReflectionsQuestWorldSubsystem::BindGame()
{
    if (bBound) return;
    UWorld* World = GetWorld();
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!World || !Quests) return;
    bBound = true;
    Quests->OnQuestEvent.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleQuestEvent);
    Quests->OnQuestsChanged.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleQuestsChanged);
    if (UReflectionsSpellEventSubsystem* Spells = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
    {
        Spells->OnSpellHit.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleSpellHit);
    }
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
    {
        Npcs->OnNpcDied.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleNpcDied);
        // OnPlayerCrime by name: bound only when the property exists and its signature matches the handler.
        if (FMulticastDelegateProperty* Crime = FindFProperty<FMulticastDelegateProperty>(Npcs->GetClass(), TEXT("OnPlayerCrime")))
        {
            UFunction* Handler = FindFunction(GET_FUNCTION_NAME_CHECKED(UReflectionsQuestWorldSubsystem, HandlePlayerCrime));
            if (Handler && Crime->SignatureFunction && Handler->IsSignatureCompatibleWith(Crime->SignatureFunction))
            {
                FScriptDelegate D;
                D.BindUFunction(this, GET_FUNCTION_NAME_CHECKED(UReflectionsQuestWorldSubsystem, HandlePlayerCrime));
                Crime->AddDelegate(MoveTemp(D), Npcs);
            }
        }
        Npcs->OnNpcInfection.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleNpcInfection);
        for (AActor* A : Npcs->GetNpcActors())
        {
            if (A && Npcs->GetInfection(A) != EReflectionsNpcInfection::None) KnownTarnished.Add(A);
        }
    }
    if (UReflectionsSpellEventSubsystem* Spells = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
    {
        Spells->OnSpellEvent.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleSpellEvent);
    }
    for (TActorIterator<AReflectionsSealedDoor> It(World); It; ++It)
    {
        It->OnOpened.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleDoorOpened);
    }
    if (UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this))
    {
        Progress->OnWorldChanged.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleWorldChanged);
        Progress->OnCoinsChanged.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleCoinsChanged);
        Progress->OnPagesChanged.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandlePagesChanged);
        Progress->OnKeyAdded.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleKeyAdded);
        Progress->OnBookComplete.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleBookComplete);
        LastCoins = Progress->GetAllCoins();
        KnownPages.Append(Progress->GetPages());
    }
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        Flow->OnVictory.AddUniqueDynamic(this, &UReflectionsQuestWorldSubsystem::HandleVictory);
    }
}

void UReflectionsQuestWorldSubsystem::UnbindGame()
{
    if (!bBound) return;
    bBound = false;
    // Game-instance objects outlive this map: always unhook from them.
    if (UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this))
    {
        Quests->OnQuestEvent.RemoveDynamic(this, &UReflectionsQuestWorldSubsystem::HandleQuestEvent);
        Quests->OnQuestsChanged.RemoveDynamic(this, &UReflectionsQuestWorldSubsystem::HandleQuestsChanged);
    }
    if (UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this))
    {
        Progress->OnWorldChanged.RemoveDynamic(this, &UReflectionsQuestWorldSubsystem::HandleWorldChanged);
        Progress->OnCoinsChanged.RemoveDynamic(this, &UReflectionsQuestWorldSubsystem::HandleCoinsChanged);
        Progress->OnPagesChanged.RemoveDynamic(this, &UReflectionsQuestWorldSubsystem::HandlePagesChanged);
        Progress->OnKeyAdded.RemoveDynamic(this, &UReflectionsQuestWorldSubsystem::HandleKeyAdded);
        Progress->OnBookComplete.RemoveDynamic(this, &UReflectionsQuestWorldSubsystem::HandleBookComplete);
    }
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        Flow->OnVictory.RemoveDynamic(this, &UReflectionsQuestWorldSubsystem::HandleVictory);
    }
}

void UReflectionsQuestWorldSubsystem::EnsureController()
{
    UWorld* World = GetWorld();
    APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
    if (!PC || !PC->IsLocalController() || PC == Controller.Get()) return;
    if (APlayerController* Old = Controller.Get())
    {
        if (Input) Old->PopInputComponent(Input);
    }
    Controller = PC;
    BindInput(PC);
}

void UReflectionsQuestWorldSubsystem::BindInput(APlayerController* PC)
{
    Input = NewObject<UInputComponent>(PC, TEXT("QuestInput"));
    Input->Priority = 15;
    Input->BindKey(EKeys::L, IE_Pressed, this, &UReflectionsQuestWorldSubsystem::OnJournalPressed).bConsumeInput = false;
    Input->BindKey(EKeys::E, IE_Pressed, this, &UReflectionsQuestWorldSubsystem::OnTalkPressed).bConsumeInput = false;
    // D-pad Down is the voice talk button; with voice on, the voice system asks us first (HandleTalkPressed).
    UClass* VoiceClass = FindObject<UClass>(nullptr, TEXT("/Script/reflections.ReflectionsVoiceInteractionSubsystem"));
    const bool bVoice = VoiceClass && GetWorld()->GetSubsystemBase(VoiceClass) != nullptr;
    if (!bVoice)
    {
        Input->BindKey(EKeys::Gamepad_DPad_Down, IE_Pressed, this, &UReflectionsQuestWorldSubsystem::OnTalkPressed).bConsumeInput = false;
        bInputBoundToPadTalk = true;
    }
    PC->PushInputComponent(Input);
}

// ---- Widgets -------------------------------------------------------------------------------------------------

void UReflectionsQuestWorldSubsystem::BuildWidgets()
{
    UWorld* World = GetWorld();
    UGameViewportClient* Viewport = World ? World->GetGameViewport() : nullptr;
    APlayerController* PC = Controller.Get();
    ULocalPlayer* Player = PC ? PC->GetLocalPlayer() : nullptr;
    if (!Viewport || !Player) return;
    SAssignNew(Hud, SReflectionsQuestHud).Owner(this);
    SAssignNew(Journal, SReflectionsQuestJournal).Owner(this);
    SAssignNew(Talk, SReflectionsQuestTalk).Owner(this);
    // Game flow's HUD is 40 and its menus 1000; ours sit just above its HUD and just below its menus.
    Viewport->AddViewportWidgetContent(Hud.ToSharedRef(), 45);
    Viewport->AddViewportWidgetContent(Talk.ToSharedRef(), 980);
    Viewport->AddViewportWidgetContent(Journal.ToSharedRef(), 990);
    WidgetPlayer = Player;
}

void UReflectionsQuestWorldSubsystem::RemoveWidgets()
{
    UWorld* World = GetWorld();
    UGameViewportClient* Viewport = World ? World->GetGameViewport() : nullptr;
    if (Viewport)
    {
        if (Hud) Viewport->RemoveViewportWidgetContent(Hud.ToSharedRef());
        if (Journal) Viewport->RemoveViewportWidgetContent(Journal.ToSharedRef());
        if (Talk) Viewport->RemoveViewportWidgetContent(Talk.ToSharedRef());
    }
    Hud.Reset();
    Journal.Reset();
    Talk.Reset();
}

bool UReflectionsQuestWorldSubsystem::ShouldShowHud() const
{
    if (!ReflectionsQuestWorldCVars::Enabled || bJournalOpen || bTalkOpen) return false;
    const UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(this);
    if (Flow && (!Flow->IsPlaying() || Flow->IsMenuOpen() || Flow->IsCraftingOpen())) return false;
    if (IsCutscenePlaying()) return false;
    return true;
}

UObject* UReflectionsQuestWorldSubsystem::CutsceneSystem() const
{
    UClass* Class = FindObject<UClass>(nullptr, CutsceneClass);
    return Class && GetWorld() ? GetWorld()->GetSubsystemBase(Class) : nullptr;
}

bool UReflectionsQuestWorldSubsystem::IsCutscenePlaying() const
{
    return CallBool(CutsceneSystem(), TEXT("IsCutscenePlaying"), NAME_None, false);
}

bool UReflectionsQuestWorldSubsystem::PlayCutscene(FName Name)
{
    UObject* Cutscenes = CutsceneSystem();
    if (!Cutscenes || Name.IsNone()) return false;
    if (CallBool(Cutscenes, TEXT("HasPlayed"), Name, false)) return false;  // each scene once
    const bool bPlayed = CallBool(Cutscenes, TEXT("PlayCutscene"), Name, false);
    UE_LOG(LogReflectionsQuestWorld, Log, TEXT("Quest cutscene %s: %s"), *Name.ToString(), bPlayed ? TEXT("playing") : TEXT("not played"));
    return bPlayed;
}

bool UReflectionsQuestWorldSubsystem::IsUsingGamepad() const
{
    const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
    return Flow && Flow->IsUsingGamepad();
}

APawn* UReflectionsQuestWorldSubsystem::GetHero() const
{
    const APlayerController* PC = Controller.Get();
    return PC ? PC->GetPawn() : nullptr;
}

void UReflectionsQuestWorldSubsystem::EnterMenuMode(TSharedPtr<SWidget> Focus, bool bPause)
{
    APlayerController* PC = Controller.Get();
    if (!PC) return;
    PC->FlushPressedKeys();
    PC->bShowMouseCursor = true;
    if (bPause)
    {
        if (!UGameplayStatics::IsGamePaused(this))
        {
            bPausedByUs = UGameplayStatics::SetGamePaused(this, true);
        }
        FInputModeUIOnly Mode;
        if (Focus.IsValid()) Mode.SetWidgetToFocus(Focus);
        Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        PC->SetInputMode(Mode);
        if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this)) Flow->bMenuInputActive = true;
    }
    else
    {
        // Talking never stops the world: the card takes its keys and buttons, everything else still reaches the game.
        FInputModeGameAndUI Mode;
        if (Focus.IsValid()) Mode.SetWidgetToFocus(Focus);
        Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        Mode.SetHideCursorDuringCapture(false);
        PC->SetInputMode(Mode);
    }
    if (FSlateApplication::IsInitialized() && Focus.IsValid())
    {
        FSlateApplication::Get().SetAllUserFocus(Focus, EFocusCause::SetDirectly);
    }
}

void UReflectionsQuestWorldSubsystem::EnterGameMode()
{
    if (bPausedByUs)
    {
        UGameplayStatics::SetGamePaused(this, false);
        bPausedByUs = false;
    }
    APlayerController* PC = Controller.Get();
    if (!PC) return;
    PC->FlushPressedKeys();
    PC->bShowMouseCursor = false;
    PC->SetInputMode(FInputModeGameOnly());
    if (FSlateApplication::IsInitialized()) FSlateApplication::Get().SetAllUserFocusToGameViewport();
    if (UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this)) Flow->bMenuInputActive = false;
}

void UReflectionsQuestWorldSubsystem::OpenJournal()
{
    if (bJournalOpen || !Journal) return;
    const UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(this);
    const bool bFromPause = Flow && Flow->GetScreen() == EReflectionsFlowScreen::Pause;
    if (Flow && Flow->IsMenuOpen() && !bFromPause) return;
    if (Flow && Flow->IsCraftingOpen()) return;
    if (bTalkOpen) CloseTalk();
    bJournalOpen = true;
    Journal->Refresh();
    EnterMenuMode(Journal);
    PlaySound(TEXT("UI_Confirm"));
    ++Revision;
}

void UReflectionsQuestWorldSubsystem::CloseJournal()
{
    if (!bJournalOpen) return;
    bJournalOpen = false;
    PlaySound(TEXT("UI_Click"));
    const UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(this);
    if (Flow && Flow->GetScreen() == EReflectionsFlowScreen::Pause)
    {
        // Opened from the pause menu: pause still owns input and the pause state; it re-shows and refocuses itself.
        bPausedByUs = false;
    }
    else
    {
        EnterGameMode();
    }
    ++Revision;
}

void UReflectionsQuestWorldSubsystem::OnJournalPressed()
{
    if (bJournalOpen) CloseJournal();
    else if (!bTalkOpen) OpenJournal();
}

void UReflectionsQuestWorldSubsystem::OnTalkPressed()
{
    if (bJournalOpen || bTalkOpen || !ShouldShowHud()) return;
    if (AActor* Target = PromptTarget.Get())
    {
        OpenTalk(Target, false);
    }
}

// ---- Talk card -----------------------------------------------------------------------------------------------

bool UReflectionsQuestWorldSubsystem::HasBusiness(AActor* Npc, TCHAR& OutGlyph) const
{
    const UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests || !Npc) return false;
    bool bAny = false;
    OutGlyph = TEXT('*');
    for (const FString& A : Quests->GetQuestActions(Npc))
    {
        if (A.StartsWith(TEXT("turn_in:"))) { OutGlyph = TEXT('?'); return true; }
        if (A.StartsWith(TEXT("offer_quest:"))) { OutGlyph = TEXT('!'); bAny = true; }
        else if (A.StartsWith(TEXT("talk:")) || A.StartsWith(TEXT("deliver:")) || A.StartsWith(TEXT("choose:")))
        {
            if (!bAny) OutGlyph = TEXT('*');
            bAny = true;
        }
    }
    return bAny;
}

bool UReflectionsQuestWorldSubsystem::OpenTalk(AActor* Npc, bool bOnlyIfBusiness)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests || !IsValid(Npc) || bJournalOpen || bTalkOpen || !Talk) return false;
    const FName Person = UReflectionsQuestSubsystem::GetPersonId(Npc);
    if (Person.IsNone()) return false;
    TCHAR Glyph;
    const bool bBusiness = HasBusiness(Npc, Glyph);
    if (bOnlyIfBusiness && !bBusiness) return false;
    const UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(this);
    if (Flow && (Flow->IsMenuOpen() || Flow->IsCraftingOpen())) return false;

    TalkNpc = Npc;
    TalkPerson = Person;
    TalkChoiceQuest = NAME_None;
    TalkLines.Reset();
    TalkLineIndex = 0;
    CuedTalkIndex = -1;
    bTalkEnding = false;
    // Open first: lines the talk triggers (a talk-to objective's lines, the next step's lines) land in the card.
    bTalkOpen = true;

    const TArray<FString> Actions = Quests->GetQuestActions(Npc);
    const FString* TalkAction = Actions.FindByPredicate([](const FString& A) { return A.StartsWith(TEXT("talk:")) || A.StartsWith(TEXT("deliver:")); });
    const FString* Choose = Actions.FindByPredicate([](const FString& A) { return A.StartsWith(TEXT("choose:")); });
    const FString* TurnIn = Actions.FindByPredicate([](const FString& A) { return A.StartsWith(TEXT("turn_in:")); });
    const FString* Offer = Actions.FindByPredicate([](const FString& A) { return A.StartsWith(TEXT("offer_quest:")); });
    const FString* Hint = Actions.FindByPredicate([](const FString& A) { return A.StartsWith(TEXT("give_hint:")); });

    if (Choose) TalkLines.Append(Quests->GetLinesFor(Npc, *Choose));
    Quests->NotifyTalkedTo(Npc);  // counts talk / delivery objectives; their lines arrive through HandleQuestEvent
    // A finished quest's after lines, once.
    for (const FReflectionsQuestDef& Def : Quests->GetQuests())
    {
        const FReflectionsQuestState* S = Quests->FindState(Def.Id);
        if (S && S->Status == EReflectionsQuestStatus::Completed && !S->bAfterSaid && !Def.AfterLines.IsEmpty() &&
            (Def.AfterLines[0].Speaker == Person || (Def.AfterLines[0].Speaker.IsNone() && Def.Giver == Person)))
        {
            TalkLines.Append(UReflectionsQuestSubsystem::ToLines(Def.AfterLines, Person));
            Quests->MarkAfterSaid(Def.Id);
        }
    }
    if (TalkLines.IsEmpty() && !TalkAction)
    {
        if (TurnIn) TalkLines = Quests->GetLinesFor(Npc, TEXT("give_hint:") + TurnIn->Mid(8));
        else if (Offer)
        {
            TalkLines = Quests->GetLinesFor(Npc, *Offer);
            FString Reason, Say;
            Quests->ExecuteQuestAction(Npc, *Offer, Reason, Say);
        }
        else if (Hint) TalkLines = Quests->GetLinesFor(Npc, *Hint);
    }
    if (TalkLines.IsEmpty()) TalkLines = Quests->GetLinesFor(Npc, FString());
    if (TalkLines.IsEmpty())
    {
        FReflectionsQuestLine L;
        L.Speaker = Person;
        L.Text = LOCTEXT("TalkDefault", "Mm? Something you need?");
        TalkLines.Add(L);
    }
    // A delivery may have made choices available: show the step's lines for them too.
    if (TalkAction && !Choose)
    {
        for (const FString& A : Quests->GetQuestActions(Npc))
        {
            if (A.StartsWith(TEXT("choose:")))
            {
                for (const FReflectionsQuestLine& L : Quests->GetLinesFor(Npc, A))
                {
                    if (!TalkLines.ContainsByPredicate([&L](const FReflectionsQuestLine& E) { return E.Text.EqualTo(L.Text); })) TalkLines.Add(L);
                }
                break;
            }
        }
    }
    TalkLineIndex = 0;
    RefreshTalkOptions();
    ++TalkRevision;
    ++Revision;
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
    {
        Npcs->PlayBark(Npc, TEXT("Greet"));
        // The person stops for the conversation (released in CloseTalk; the hold also times out by itself).
        Npcs->HoldNpc(Npc, 120.0f);
        bTalkHeld = true;
    }
    if (const APawn* Hero = GetHero())
    {
        const UReflectionsHealthComponent* Health = Hero->FindComponentByClass<UReflectionsHealthComponent>();
        TalkHeroHealth = Health ? Health->Health : -1.0f;
    }
    EnterMenuMode(Talk, false);
    PlaySound(TEXT("UI_Confirm"));
    return true;
}

bool UReflectionsQuestWorldSubsystem::OpenChoice(FName QuestId)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    const FReflectionsQuestStep* Step = Quests ? Quests->GetCurrentStep(QuestId) : nullptr;
    if (!Step || Step->Choices.IsEmpty() || bTalkOpen || bJournalOpen || !Talk) return false;
    TalkNpc.Reset();
    TalkPerson = Step->Speaker;
    TalkChoiceQuest = QuestId;
    TalkLines = UReflectionsQuestSubsystem::ToLines(Step->Lines, Step->Speaker);
    if (TalkLines.IsEmpty())
    {
        FReflectionsQuestLine L;
        L.Text = Step->Description;
        TalkLines.Add(L);
    }
    CuedTalkIndex = -1;
    TalkLineIndex = 0;
    bTalkEnding = false;
    RefreshTalkOptions();
    bTalkOpen = true;
    ++TalkRevision;
    TalkHeroHealth = -1.0f;
    EnterMenuMode(Talk, false);
    return true;
}

void UReflectionsQuestWorldSubsystem::RefreshTalkOptions()
{
    TalkOptions.Reset();
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests) return;
    if (bTalkEnding)
    {
        TalkOptions.Add({LOCTEXT("TalkGoodbye", "Goodbye"), TEXT("goodbye"), true});
        return;
    }
    if (!TalkChoiceQuest.IsNone())
    {
        if (const FReflectionsQuestStep* Step = Quests->GetCurrentStep(TalkChoiceQuest))
        {
            for (const FReflectionsQuestChoice& C : Step->Choices)
            {
                TalkOptions.Add({C.Text, FString::Printf(TEXT("choose:%s.%s"), *TalkChoiceQuest.ToString(), *C.Id.ToString()), TalkOptions.IsEmpty()});
            }
        }
        if (TalkOptions.IsEmpty()) TalkOptions.Add({LOCTEXT("TalkContinue", "Continue"), TEXT("goodbye"), true});
        return;
    }
    AActor* Npc = TalkNpc.Get();
    const TArray<FString> Actions = Npc ? Quests->GetQuestActions(Npc) : TArray<FString>();
    int32 Offers = 0;
    for (const FString& A : Actions) if (A.StartsWith(TEXT("offer_quest:"))) ++Offers;
    for (const FString& A : Actions)
    {
        FString Verb, Arg;
        A.Split(TEXT(":"), &Verb, &Arg);
        FString QuestStr = Arg, ChoiceStr;
        Arg.Split(TEXT("."), &QuestStr, &ChoiceStr);
        const FReflectionsQuestDef* Def = Quests->FindQuest(FName(*QuestStr));
        const FText Title = Def ? Def->Title : FText::FromString(QuestStr);
        if (Verb == TEXT("choose"))
        {
            const FReflectionsQuestStep* Step = Quests->GetCurrentStep(FName(*QuestStr));
            const FReflectionsQuestChoice* C = Step ? Step->Choices.FindByPredicate([&ChoiceStr](const FReflectionsQuestChoice& E) { return E.Id == FName(*ChoiceStr); }) : nullptr;
            if (C) TalkOptions.Add({C->Text, A, TalkOptions.IsEmpty()});
        }
        else if (Verb == TEXT("accept"))
        {
            TalkOptions.Add({Offers > 1 ? FText::Format(LOCTEXT("TalkAcceptNamed", "Accept: {0}"), Title) : LOCTEXT("TalkAccept", "I'll do it."), A, true});
        }
        else if (Verb == TEXT("decline"))
        {
            TalkOptions.Add({Offers > 1 ? FText::Format(LOCTEXT("TalkDeclineNamed", "Not now: {0}"), Title) : LOCTEXT("TalkDecline", "Not now."), A, false});
        }
        else if (Verb == TEXT("turn_in"))
        {
            TalkOptions.Add({FText::Format(LOCTEXT("TalkTurnIn", "Hand it over ({0})"), Title), A, true});
        }
        else if (Verb == TEXT("give_hint"))
        {
            TalkOptions.Add({FText::Format(LOCTEXT("TalkHint", "Any advice? ({0})"), Title), A, false});
        }
    }
    // Order for a controller (A presses the first button): answers and hand-overs first, then "not now", hints last.
    const auto Rank = [](const FReflectionsTalkOption& O)
    {
        if (O.Action.StartsWith(TEXT("choose:"))) return 0;
        if (O.Action.StartsWith(TEXT("accept:")) || O.Action.StartsWith(TEXT("turn_in:"))) return 1;
        if (O.Action.StartsWith(TEXT("decline:"))) return 2;
        return 3;
    };
    TalkOptions.StableSort([&Rank](const FReflectionsTalkOption& L, const FReflectionsTalkOption& R) { return Rank(L) < Rank(R); });
    for (int32 i = 0; i < TalkOptions.Num(); ++i) TalkOptions[i].bPrimary = i == 0 && Rank(TalkOptions[i]) < 3;
    // Nothing left but a hint (just accepted, or a reminder chat): Goodbye comes first so A closes the card.
    const bool bOnlyHints = !TalkOptions.ContainsByPredicate([&Rank](const FReflectionsTalkOption& O) { return Rank(O) < 3; });
    TalkOptions.Insert({LOCTEXT("TalkGoodbye", "Goodbye"), TEXT("goodbye"), bOnlyHints}, bOnlyHints ? 0 : TalkOptions.Num());
}

void UReflectionsQuestWorldSubsystem::PushTalkLine(FName Speaker, const FText& Text, FName LineId)
{
    if (Text.IsEmpty()) return;
    FReflectionsQuestLine L;
    L.Speaker = Speaker;
    L.Text = Text;
    L.Id = LineId;
    TalkLines.Add(L);
}

void UReflectionsQuestWorldSubsystem::PlayLines(const TArray<FReflectionsQuestLine>& InLines)
{
    // The dead say nothing more.
    TArray<FReflectionsQuestLine> Lines = InLines;
    if (const UReflectionsQuestSubsystem* Q = UReflectionsQuestSubsystem::Get(this))
    {
        Lines.RemoveAll([Q](const FReflectionsQuestLine& L) { return Q->IsPersonDead(L.Speaker); });
    }
    if (Lines.IsEmpty()) return;
    if (bTalkOpen)
    {
        const int32 FirstNew = TalkLines.Num();
        for (const FReflectionsQuestLine& L : Lines)
        {
            if (!L.Id.IsNone() && TalkLines.ContainsByPredicate([&L](const FReflectionsQuestLine& E) { return E.Id == L.Id; })) continue;
            TalkLines.Add(L);
        }
        if (TalkLines.Num() > FirstNew) ++TalkRevision;
        return;
    }
    const UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    for (const FReflectionsQuestLine& L : Lines)
    {
        FSubtitle Sub;
        Sub.Speaker = Quests ? Quests->GetPersonName(L.Speaker) : FText::GetEmpty();
        Sub.SpeakerId = L.Speaker;
        Sub.Line = L.Text;
        Sub.Id = L.Id;
        Sub.Delay = L.Delay;
        Sub.Seconds = FMath::Clamp(L.Text.ToString().Len() * 0.065f, 2.5f, 7.0f);
        SubtitleQueue.Add(Sub);
    }
}

float UReflectionsQuestWorldSubsystem::PlayVoiceCue(FName LineId, FName Speaker)
{
    if (LineId.IsNone()) return 0.0f;
    const FString Name = FString::Printf(TEXT("SCue_VO_%s"), *LineId.ToString());
    const FString Path = FString::Printf(TEXT("/Game/Audio/Jam/Voice/Cues/%s.%s"), *Name, *Name);
    USoundBase* Sound = LoadObject<USoundBase>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
    if (!Sound) return 0.0f;
    if (VoiceAudio && VoiceAudio->IsPlaying()) VoiceAudio->Stop();
    // From the speaker's position when they are here (the hero speaks 2D); 2D otherwise. UI sound, so it plays while paused.
    VoiceAudio = UGameplayStatics::CreateSound2D(this, Sound, 1.0f, 1.0f, 0.0f, nullptr, false, true);
    if (VoiceAudio)
    {
        VoiceAudio->bIsUISound = true;
        if (AActor* Who = Speaker == TEXT("wren_hale") ? nullptr : FindPersonActor(Speaker))
        {
            if (APawn* Hero = GetHero(); Hero && FVector::Dist(Hero->GetActorLocation(), Who->GetActorLocation()) > 150.0f)
            {
                VoiceAudio->bAllowSpatialization = true;
                VoiceAudio->SetWorldLocation(Who->GetActorLocation() + FVector(0, 0, 160));
            }
        }
        VoiceAudio->Play();
    }
    return Sound->GetDuration() < 600.0f ? Sound->GetDuration() : 0.0f;
}

bool UReflectionsQuestWorldSubsystem::AdvanceTalk()
{
    if (bTalkOpen && !IsTalkOnLastLine())
    {
        ++TalkLineIndex;
        ++TalkRevision;
        PlaySound(TEXT("UI_Click"));
        return true;
    }
    return false;
}

void UReflectionsQuestWorldSubsystem::ChooseTalkOption(int32 Index)
{
    if (TalkOptions.IsValidIndex(Index)) ChooseTalkAction(TalkOptions[Index].Action);
}

void UReflectionsQuestWorldSubsystem::ChooseTalkAction(const FString& SelectedAction)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!bTalkOpen || !Quests || !IsTalkOnLastLine()) return;
    // Quest events raised by an action can rebuild the options synchronously.
    const FString Action = SelectedAction;
    if (!TalkOptions.ContainsByPredicate([&Action](const FReflectionsTalkOption& Option) { return Option.Action == Action; })) return;
    if (Action == TEXT("goodbye"))
    {
        CloseTalk();
        return;
    }
    const int32 FirstNew = TalkLines.Num();
    FString Reason, Say;
    bool bOk = false;
    if (!TalkChoiceQuest.IsNone())
    {
        FString Verb, Arg, QuestStr, ChoiceStr;
        Action.Split(TEXT(":"), &Verb, &Arg);
        Arg.Split(TEXT("."), &QuestStr, &ChoiceStr);
        FText Response;
        FName ResponseId;
        if (const FReflectionsQuestStep* Step = Quests->GetCurrentStep(TalkChoiceQuest))
        {
            if (const FReflectionsQuestChoice* C = Step->Choices.FindByPredicate([&ChoiceStr](const FReflectionsQuestChoice& E) { return E.Id == FName(*ChoiceStr); }))
            {
                Response = C->Response;
                ResponseId = C->ResponseId;
            }
        }
        bOk = Quests->MakeChoice(TalkChoiceQuest, FName(*ChoiceStr));
        if (bOk)
        {
            if (!Response.IsEmpty()) TalkLines.Insert(FReflectionsQuestLine{TalkPerson, Response, ResponseId}, FirstNew);
            TalkChoiceQuest = NAME_None;
            bTalkEnding = true;
        }
    }
    else if (AActor* Npc = TalkNpc.Get())
    {
        // Choice replies carry their own line id (voice cue): say them as lines, not as plain text.
        FText ChoiceResponse;
        FName ChoiceResponseId;
        if (Action.StartsWith(TEXT("choose:")))
        {
            FString Verb, Arg, QuestStr, ChoiceStr;
            Action.Split(TEXT(":"), &Verb, &Arg);
            Arg.Split(TEXT("."), &QuestStr, &ChoiceStr);
            if (const FReflectionsQuestStep* Step = Quests->GetCurrentStep(FName(*QuestStr)))
            {
                if (const FReflectionsQuestChoice* C = Step->Choices.FindByPredicate([&ChoiceStr](const FReflectionsQuestChoice& E) { return E.Id == FName(*ChoiceStr); }))
                {
                    ChoiceResponse = C->Response;
                    ChoiceResponseId = C->ResponseId;
                }
            }
        }
        const int32 LinesBefore = TalkLines.Num();
        bOk = Quests->ExecuteQuestAction(Npc, Action, Reason, Say);
        if (bOk && Action.StartsWith(TEXT("choose:")))
        {
            if (!ChoiceResponse.IsEmpty()) TalkLines.Insert(FReflectionsQuestLine{TalkPerson, ChoiceResponse, ChoiceResponseId}, LinesBefore);
            Say.Reset();
        }
        // Accept / turn in: the quest's own lines (with ids) instead of the joined text.
        if (const FReflectionsQuestDef* Def = bOk ? Quests->FindQuest(FName(*Action.Mid(Action.Find(TEXT(":")) + 1))) : nullptr)
        {
            const TArray<FReflectionsQuestLineDef>* Defs = Action.StartsWith(TEXT("accept:")) ? &Def->AcceptLines
                : Action.StartsWith(TEXT("decline:")) ? &Def->DeclineLines : Action.StartsWith(TEXT("turn_in:")) ? &Def->TurnInLines : nullptr;
            if (Defs && !Defs->IsEmpty())
            {
                TArray<FReflectionsQuestLine> Lines = UReflectionsQuestSubsystem::ToLines(*Defs, TalkPerson);
                TalkLines.Insert(Lines, LinesBefore);
                Say.Reset();
            }
        }
        if (bOk && (Action.StartsWith(TEXT("decline:")) || Action.StartsWith(TEXT("turn_in:")))) bTalkEnding = true;
        if (Action.StartsWith(TEXT("turn_in:")) && bOk)
        {
            if (const FReflectionsQuestDef* Def = Quests->FindQuest(FName(*Action.Mid(8))))
            {
                const FText Reward = Quests->DescribeReward(Def->Reward);
                if (!Say.IsEmpty()) PushTalkLine(TalkPerson, FText::FromString(Say));
                Say.Reset();
                if (!Reward.IsEmpty()) PushTalkLine(TEXT("narrator"), Reward);
            }
        }
    }
    if (bOk && !Say.IsEmpty()) PushTalkLine(TalkPerson, FText::FromString(Say));
    if (!bOk && !Reason.IsEmpty())
    {
        UE_LOG(LogReflectionsQuestWorld, Warning, TEXT("Talk action %s refused: %s"), *Action, *Reason);
    }
    if (TalkLines.Num() == FirstNew)
    {
        PushTalkLine(TalkPerson, bOk ? LOCTEXT("TalkAcknowledged", "All right.") :
            LOCTEXT("TalkUnavailable", "I can’t do that right now."));
    }
    if (TalkLines.Num() > FirstNew) TalkLineIndex = FirstNew;
    RefreshTalkOptions();
    ++TalkRevision;
    PlaySound(bOk ? TEXT("UI_Confirm") : TEXT("UI_Click"));
}

void UReflectionsQuestWorldSubsystem::CloseTalk()
{
    if (!bTalkOpen) return;
    bTalkOpen = false;
    if (bTalkHeld && TalkNpc.IsValid())
    {
        if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this)) Npcs->ReleaseNpc(TalkNpc.Get());
    }
    bTalkHeld = false;
    TalkHeroHealth = -1.0f;
    TalkNpc.Reset();
    TalkChoiceQuest = NAME_None;
    EnterGameMode();
    ++Revision;
}

FText UReflectionsQuestWorldSubsystem::GetTalkSpeaker() const
{
    const UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    const FName Speaker = TalkLines.IsValidIndex(TalkLineIndex) ? TalkLines[TalkLineIndex].Speaker : TalkPerson;
    return Quests && !Speaker.IsNone() ? Quests->GetPersonName(Speaker) : FText::GetEmpty();
}

FText UReflectionsQuestWorldSubsystem::GetTalkSpeakerTitle() const
{
    const UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    const FName Speaker = TalkLines.IsValidIndex(TalkLineIndex) ? TalkLines[TalkLineIndex].Speaker : TalkPerson;
    const FReflectionsQuestPerson* P = Quests ? Quests->FindPerson(Speaker) : nullptr;
    return P ? P->Title : FText::GetEmpty();
}

FText UReflectionsQuestWorldSubsystem::GetTalkLine() const
{
    return TalkLines.IsValidIndex(TalkLineIndex) ? TalkLines[TalkLineIndex].Text : FText::GetEmpty();
}

// ---- Tick ----------------------------------------------------------------------------------------------------

void UReflectionsQuestWorldSubsystem::TickTalk(float DeltaTime)
{
    if (!bTalkOpen) return;
    APawn* Hero = GetHero();
    if (!Hero) return;
    // A menu (pause, save, load) takes over: the card steps aside rather than fight it for input.
    if (const UReflectionsGameFlowWorldSubsystem* FlowWorld = UReflectionsGameFlowWorldSubsystem::Get(this))
    {
        if (FlowWorld->IsMenuOpen()) { CloseTalk(); return; }
    }
    // Hurt: the conversation is over.
    if (const UReflectionsHealthComponent* Health = Hero->FindComponentByClass<UReflectionsHealthComponent>())
    {
        if (TalkHeroHealth >= 0.0f && Health->Health < TalkHeroHealth - 0.5f) { CloseTalk(); return; }
        TalkHeroHealth = FMath::Max(TalkHeroHealth, Health->Health);
    }
    AActor* Npc = TalkNpc.Get();
    if (!Npc) return;
    // Walked off (5 m), or the person is gone.
    if (!IsValid(Npc) || FVector::Dist2D(Npc->GetActorLocation(), Hero->GetActorLocation()) > 500.0f) { CloseTalk(); return; }
    // The person turns to face the hero.
    const FVector To = Hero->GetActorLocation() - Npc->GetActorLocation();
    if (To.SizeSquared2D() > 1.0f)
    {
        const FRotator Want(0.0f, To.Rotation().Yaw, 0.0f);
        const FRotator Now = Npc->GetActorRotation();
        Npc->SetActorRotation(FMath::RInterpTo(FRotator(0.0f, Now.Yaw, 0.0f), Want, DeltaTime, 6.0f));
    }
}

void UReflectionsQuestWorldSubsystem::Tick(float DeltaTime)
{
    if (!bBegunPlay || !ReflectionsQuestWorldCVars::Enabled) return;
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests) return;
    Clock += DeltaTime;
    EnsureController();
    TickTalk(DeltaTime);
    if (!Hud && Controller.IsValid()) BuildWidgets();
    BindGame();

    // Start once play has begun (after the title, and after a new game has cleared the old checkpoint).
    if (!bQuestsStarted)
    {
        const UReflectionsGameFlowWorldSubsystem* FlowWorld = UReflectionsGameFlowWorldSubsystem::Get(this);
        if (FlowWorld && !FlowWorld->IsPlaying()) return;
    }
    // New game: game flow cleared its checkpoint (had one at world start or last tick, none now), so the quests start
    // over too. Checked before the first start, so a new game never begins with the last run's quests.
    if (const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this))
    {
        const bool bHas = Flow->HasCheckpoint();
        if (bHadCheckpoint && !bHas)
        {
            // Clear first: the reset restarts the main quest, whose first lines must not queue twice.
            SubtitleQueue.Reset();
            BannerQueue.Reset();
            Quests->ResetAll();
            SpawnedItems.Reset();
        }
        bHadCheckpoint = bHas;
    }
    if (!bQuestsStarted)
    {
        bQuestsStarted = true;
        Quests->RefreshAvailability();
    }

    // Banners: only while the HUD shows (not behind the title or a menu).
    if (ShouldShowHud())
    {
        if (!Quests->PendingBanners.IsEmpty())
        {
            BannerQueue.Append(Quests->PendingBanners);
            Quests->PendingBanners.Reset();
        }
        if (Clock - BannerStarted > BannerDuration + 0.4f && !BannerQueue.IsEmpty())
        {
            Banner = BannerQueue[0];
            BannerQueue.RemoveAt(0);
            BannerStarted = Clock;
            BannerDuration = Banner.Detail.IsEmpty() ? 3.2f : 4.5f;
            PlaySound(TEXT("Quest_Update"));
        }
        if (Clock - SubtitleStarted > Subtitle.Seconds)
        {
            if (SubtitleEnded < SubtitleStarted) SubtitleEnded = Clock;
            if (!SubtitleQueue.IsEmpty() && Clock - SubtitleEnded >= SubtitleQueue[0].Delay)
            {
                Subtitle = SubtitleQueue[0];
                SubtitleQueue.RemoveAt(0);
                SubtitleStarted = Clock;
                const float CueSeconds = PlayVoiceCue(Subtitle.Id, Subtitle.SpeakerId);
                if (CueSeconds > 0.0f) Subtitle.Seconds = FMath::Max(Subtitle.Seconds * 0.6f, CueSeconds + 0.35f);
            }
        }
    }
    // The talk card says each line aloud as it comes up.
    if (bTalkOpen && TalkLines.IsValidIndex(TalkLineIndex) && (CuedTalkIndex != TalkLineIndex || CuedTalkRevision != TalkRevision))
    {
        if (CuedTalkIndex != TalkLineIndex) PlayVoiceCue(TalkLines[TalkLineIndex].Id, TalkLines[TalkLineIndex].Speaker);
        CuedTalkIndex = TalkLineIndex;
        CuedTalkRevision = TalkRevision;
    }

    if (Quests->bAvailabilityDirty)
    {
        Quests->bAvailabilityDirty = false;
        Quests->RefreshAvailability();
    }
    if (!UGameplayStatics::IsGamePaused(this))
    {
        EvalAccumulator += DeltaTime;
        if (EvalAccumulator >= 0.1f)
        {
            EvaluateObjectives(EvalAccumulator);
            EvaluateCutsceneSteps();
            EvaluateAfterLines();
            EvalAccumulator = 0.0f;
        }
        if (Clock >= PeopleCheckAt)
        {
            EnsurePeople();
            PeopleCheckAt = Clock + 2.0f;
        }
    }
    UpdateTracker();
    UpdateMarks();
    UpdatePrompt();
}

bool UReflectionsQuestWorldSubsystem::IsWorldJumpActive() const
{
    const UReflectionsWorldJumpWorldSubsystem* Jump = UReflectionsWorldJumpWorldSubsystem::Get(this);
    return Jump && Jump->IsWorldJumpActive();
}

EReflectionsWorld UReflectionsQuestWorldSubsystem::SideOf(const FVector& Location) const
{
    const UReflectionsWorldJumpWorldSubsystem* Jump = UReflectionsWorldJumpWorldSubsystem::Get(this);
    return Jump && Jump->IsWorldJumpActive() ? Jump->GetWorldAtLocation(Location) : EReflectionsWorld::Red;
}

EReflectionsWorld UReflectionsQuestWorldSubsystem::HeroSide() const
{
    const APawn* Hero = GetHero();
    return Hero ? SideOf(Hero->GetActorLocation()) : EReflectionsWorld::Red;
}

FName UReflectionsQuestWorldSubsystem::SideName(EReflectionsWorld World) const
{
    switch (World)
    {
    case EReflectionsWorld::Gray: return TEXT("Pewterside");
    case EReflectionsWorld::White: return TEXT("Frostside");
    default: return TEXT("Giltside");
    }
}

bool UReflectionsQuestWorldSubsystem::IsHeroNear(const FVector& Location, float Radius, bool bSameSideOnly) const
{
    const APawn* Hero = GetHero();
    if (!Hero) return false;
    if (bSameSideOnly && IsWorldJumpActive() && SideOf(Location) != SideOf(Hero->GetActorLocation())) return false;
    const FVector Delta = Hero->GetActorLocation() - Location;
    return FVector2D(Delta.X, Delta.Y).Size() <= Radius && FMath::Abs(Delta.Z) <= FMath::Max(400.0f, Radius);
}

float UReflectionsQuestWorldSubsystem::GetSubtitleLift() const
{
    // Never overlap npc-dialogue's conversation panel: sit 20 above its top edge (0 while it shows nothing).
    const UWorld* World = GetWorld();
    const UReflectionsVoiceInteractionSubsystem* Voice = World ? World->GetSubsystem<UReflectionsVoiceInteractionSubsystem>() : nullptr;
    const float PanelTop = Voice ? Voice->GetPanelTopFromBottom() : 0.0f;
    return PanelTop > 0.0f ? FMath::Max(0.0f, PanelTop + 20.0f - 300.0f) : 0.0f;
}

int32 UReflectionsQuestWorldSubsystem::QueryEventCount(FName Key, FName Arg) const
{
    const UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    if (!Quests) return 0;
    if (Key == TEXT("PageFound"))
    {
        if (!Progress) return 0;
        if (Arg.IsNone()) return Progress->GetPageCount();
        // One London: a side's page is simply the next one (Pewterside's the first, Giltside's the second, ...).
        if (!IsWorldJumpActive())
        {
            const FString A = Arg.ToString();
            const int32 Nth = A.StartsWith(TEXT("Pew")) || A.StartsWith(TEXT("Gray")) ? 1 : A.StartsWith(TEXT("Gilt")) || A.StartsWith(TEXT("Red")) ? 2 : A.StartsWith(TEXT("Frost")) || A.StartsWith(TEXT("White")) ? 3 : 1;
            return Progress->GetPageCount() >= Nth ? 1 : 0;
        }
        int32 N = Quests->HasUnlock(FName(*FString::Printf(TEXT("PageFound_%s"), *Arg.ToString()))) ? 1 : 0;
        for (const FName& Page : Progress->GetPages())
        {
            if (const EReflectionsWorld* Side = PageSides.Find(Page))
            {
                if (SideName(*Side) == Arg) N = FMath::Max(N, 1);
            }
        }
        return N;
    }
    if (Key == TEXT("BookComplete")) return Progress && Progress->IsBookComplete() ? 1 : 0;
    if (Key == TEXT("KeyFound")) return Progress ? (Arg.IsNone() ? Progress->GetKeys().Num() : (Progress->HasKey(Arg) ? 1 : 0)) : 0;
    if (Key == TEXT("ShardCollected"))
    {
        if (!Progress) return 0;
        int32 N = 0;
        for (const TPair<EReflectionsWorld, int32>& C : Progress->GetAllCoins())
        {
            if (Arg.IsNone() || SideName(C.Key) == Arg) N += C.Value;
        }
        return N;
    }
    if (Key == TEXT("FinaleStarted"))
    {
        const UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(this);
        return Villain && Villain->IsFinale() ? 1 : 0;
    }
    if (Key == TEXT("BossDefeated") || Key == TEXT("Victory"))
    {
        const UReflectionsGameFlowSubsystem* Flow = UReflectionsGameFlowSubsystem::Get(this);
        return Flow && Flow->IsVictory() ? 1 : 0;
    }
    if (Key == TEXT("QuestComplete")) return Quests->GetStatus(Arg) == EReflectionsQuestStatus::Completed ? 1 : 0;
    if (Key == TEXT("ItemFound")) return Quests->GetItemCount(Arg);
    if (Key == TEXT("Unlocked")) return Quests->HasUnlock(Arg) ? 1 : 0;
    if (Key == TEXT("DoorOpened"))
    {
        for (TActorIterator<AReflectionsSealedDoor> It(GetWorld()); It; ++It)
        {
            if (It->IsOpen() && (Arg.IsNone() || It->RequiredKey == Arg)) return 1;
        }
        return 0;
    }
    if (Key == TEXT("CutsceneDone"))
    {
        UObject* Cutscenes = CutsceneSystem();
        if (!Cutscenes) return 1;  // no cutscene system: nothing to wait for
        return !IsCutscenePlaying() && CallBool(Cutscenes, TEXT("HasPlayed"), Arg, false) ? 1 : 0;
    }
    return 0;
}

void UReflectionsQuestWorldSubsystem::EvaluateCutsceneSteps()
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests) return;
    TArray<FName> Finish;
    for (const FReflectionsQuestDef& Def : Quests->GetQuests())
    {
        const FReflectionsQuestStep* Step = Quests->GetCurrentStep(Def.Id);
        if (!Step) continue;
        const float* StartedAt = StepStartedAt.Find(Def.Id);
        const float Age = StartedAt ? Clock - *StartedAt : 0.0f;
        const bool bOnlyOptional = !Step->Objectives.ContainsByPredicate([Step](const FReflectionsQuestObjective& O)
        {
            const bool bWaitsOnScene = O.Type == EReflectionsObjectiveType::Event && O.Target == TEXT("CutsceneDone") && (O.Spell.IsNone() || O.Spell == Step->Cutscene);
            return !O.bOptional && !bWaitsOnScene;
        });
        // A cutscene step whose scene is over (or never came: no system, refused, already seen).
        if (!Step->Cutscene.IsNone() && bOnlyOptional && Age > 1.0f && !IsCutscenePlaying())
        {
            UObject* Cutscenes = CutsceneSystem();
            if (!Cutscenes || CallBool(Cutscenes, TEXT("HasPlayed"), Step->Cutscene, true) || Age > 3.0f)
            {
                Finish.Add(Def.Id);
                continue;
            }
        }
        if (Step->TimeoutSeconds > 0.0f && Age > Step->TimeoutSeconds && !IsCutscenePlaying())
        {
            Finish.Add(Def.Id);
        }
    }
    for (const FName& Q : Finish) Quests->CompleteStep(Q);
}

void UReflectionsQuestWorldSubsystem::EvaluateAfterLines()
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests || bTalkOpen) return;
    for (const FReflectionsQuestDef& Def : Quests->GetQuests())
    {
        if (Def.AfterLines.IsEmpty()) continue;
        const FReflectionsQuestState* S = Quests->FindState(Def.Id);
        if (!S || S->Status != EReflectionsQuestStatus::Completed || S->bAfterSaid) continue;
        const FName Speaker = Def.AfterLines[0].Speaker.IsNone() ? Def.Giver : Def.AfterLines[0].Speaker;
        AActor* Who = FindPersonActor(Speaker);
        if (Who && IsHeroNear(Who->GetActorLocation(), 300.0f, false))
        {
            Quests->MarkAfterSaid(Def.Id);
            PlayLines(UReflectionsQuestSubsystem::ToLines(Def.AfterLines, Speaker));
        }
    }
}

void UReflectionsQuestWorldSubsystem::EvaluateObjectives(float DeltaTime)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests) return;

    // The story catches up with the player: when a later main-quest step's progress (a page, the key, the book, the
    // finale, the boss) has already happened, the steps before it are passed over. The world doesn't wait for the
    // story's order, so the tracker never sits on a beat the player has long left behind.
    for (const FReflectionsQuestDef& Def : Quests->GetQuests())
    {
        if (!Def.bMain || Quests->GetStatus(Def.Id) != EReflectionsQuestStatus::Active) continue;
        const FReflectionsQuestState* S = Quests->FindState(Def.Id);
        const int32 Current = S ? Def.Steps.IndexOfByPredicate([S](const FReflectionsQuestStep& St) { return St.Id == S->StepId; }) : INDEX_NONE;
        if (Current == INDEX_NONE) break;
        static const FName Progress[] = {TEXT("PageFound"), TEXT("KeyFound"), TEXT("BookComplete"), TEXT("FinaleStarted"), TEXT("BossDefeated"), TEXT("Victory")};
        int32 Target = INDEX_NONE;
        for (int32 si = Def.Steps.Num() - 1; si > Current && Target == INDEX_NONE; --si)
        {
            for (const FReflectionsQuestObjective& O : Def.Steps[si].Objectives)
            {
                if (O.bOptional || O.Type != EReflectionsObjectiveType::Event) continue;
                bool bProgress = false;
                for (const FName& K : Progress) bProgress |= K == O.Target;
                if (bProgress && QueryEventCount(O.Target, O.Spell) >= FMath::Max(O.Count, 1)) { Target = si; break; }
            }
        }
        if (Target == INDEX_NONE) break;
        UE_LOG(LogTemp, Log, TEXT("Quests: the story catches up, %s -> %s."), *S->StepId.ToString(), *Def.Steps[Target].Id.ToString());
        for (int32 Guard = 0; Guard < Def.Steps.Num(); ++Guard)
        {
            const FReflectionsQuestState* Now = Quests->FindState(Def.Id);
            if (!Now || Now->Status != EReflectionsQuestStatus::Active || Now->StepId == Def.Steps[Target].Id) break;
            Quests->CompleteStep(Def.Id);
        }
        // Not a flood of lines and banners for beats the player skipped: only the newest banner stays.
        SubtitleQueue.Reset();
        if (Quests->PendingBanners.Num() > 1) Quests->PendingBanners.RemoveAt(0, Quests->PendingBanners.Num() - 1);
        break;
    }

    // Keep the coin baseline in step with silent restores.
    if (const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this))
    {
        LastCoins = Progress->GetAllCoins();
    }
    if (const UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(this))
    {
        if (Villain->IsFinale() && !bFinaleSeen)
        {
            bFinaleSeen = true;
            Quests->NotifyEvent(TEXT("FinaleStarted"), NAME_None);
        }
    }

    struct FUpdate { FName Quest; FName Objective; int32 Progress; float Held; bool bSpawn; };
    TArray<FUpdate> Updates;
    TArray<AActor*> TalkedByProximity;
    TArray<FName> NarrationChoices;
    const bool bRefreshEncounters = FMath::FloorToInt(Clock / 2.0f) != FMath::FloorToInt((Clock - DeltaTime) / 2.0f);
    for (const FReflectionsQuestDef& Def : Quests->GetQuests())
    {
        const FReflectionsQuestState* S = Quests->FindState(Def.Id);
        if (!S || S->Status != EReflectionsQuestStatus::Active) continue;
        const FReflectionsQuestStep* Step = Def.FindStep(S->StepId);
        if (!Step) continue;
        bool bRequiredDone = true;
        for (int32 i = 0; i < Step->Objectives.Num() && i < S->Objectives.Num(); ++i)
        {
            const FReflectionsQuestObjective& O = Step->Objectives[i];
            const FReflectionsObjectiveState& OS = S->Objectives[i];
            if (!OS.bDone && !O.bOptional) bRequiredDone = false;
            if (OS.bDone) continue;
            const bool bCureEncounter = O.Type == EReflectionsObjectiveType::Event && O.Target == TEXT("NpcCured") &&
                (O.SpawnArchetype == TEXT("Infected") || O.SpawnArchetype == TEXT("Tarnished"));
            if (bCureEncounter)
            {
                // Refill missing targets on arrival and after a checkpoint reload or an NPC death.
                if (bRefreshEncounters && !IsCutscenePlaying()) Updates.Add({Def.Id, O.Id, -1, 0.0f, true});
            }
            else if (!OS.bSpawned && !O.SpawnArchetype.IsNone() && O.Type != EReflectionsObjectiveType::Protect && O.Type != EReflectionsObjectiveType::Defeat)
            {
                Updates.Add({Def.Id, O.Id, -1, 0.0f, true});
            }
            switch (O.Type)
            {
            case EReflectionsObjectiveType::GoTo:
            {
                if (O.Target == TEXT("Tower_Giltside"))
                {
                    const AReflectionsSealedDoor* Seal = nullptr;
                    for (TActorIterator<AReflectionsSealedDoor> It(GetWorld()); It; ++It)
                    {
                        if (It->RequiredKey != TEXT("GiltTowerKey")) continue;
                        Seal = *It;
                        break;
                    }
                    if (Seal)
                    {
                        if (Seal->IsOpen()) Updates.Add({Def.Id, O.Id, O.Count, 0.0f, false});
                        break;
                    }
                }
                FReflectionsQuestTarget T;
                // One London: the walks are long and the places big (a churchyard, a market), so 25 m at least.
                if (ResolveObjectiveTarget(Def, O, T) && !T.bOtherSide && IsHeroNear(T.Location, IsWorldJumpActive() ? T.Radius : FMath::Max(T.Radius, 2500.0f)))
                {
                    Updates.Add({Def.Id, O.Id, O.Count, 0.0f, false});
                }
                break;
            }
            case EReflectionsObjectiveType::Protect:
            {
                if (!OS.bSpawned && !O.SpawnArchetype.IsNone()) Updates.Add({Def.Id, O.Id, -1, 0.0f, true});
                FReflectionsQuestTarget T;
                if (ResolveObjectiveTarget(Def, O, T) && !T.bOtherSide && IsHeroNear(T.Location, T.Radius))
                {
                    Updates.Add({Def.Id, O.Id, -1, DeltaTime, false});
                }
                break;
            }
            case EReflectionsObjectiveType::Defeat:
                if (!OS.bSpawned && !O.SpawnArchetype.IsNone()) Updates.Add({Def.Id, O.Id, -1, 0.0f, true});
                break;
            case EReflectionsObjectiveType::WorldJump:
            {
                // One London (no world jumping in this map): there is nowhere to step through to, so it's done.
                // Already on the side asked for (the player is ahead of the story): done.
                EReflectionsWorld Want;
                const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
                if (!IsWorldJumpActive() || (ReflectionsQuest::ToWorld(O.Side, Want) && Progress && Progress->GetCurrentWorld() == Want))
                {
                    Updates.Add({Def.Id, O.Id, O.Count, 0.0f, false});
                }
                break;
            }
            case EReflectionsObjectiveType::TalkTo:
            {
                // Standing within 3 m of the person for 2 s counts as talking to them.
                AActor* Who = FindPersonActor(O.Target);
                float& Near = ProximityTalk.FindOrAdd(O.Target);
                if (Who && !bTalkOpen && IsHeroNear(Who->GetActorLocation(), 300.0f, false))
                {
                    Near += DeltaTime;
                    if (Near >= 2.0f)
                    {
                        Near = -1000.0f;  // once
                        TalkedByProximity.AddUnique(Who);
                    }
                }
                else if (Near > 0.0f)
                {
                    Near = 0.0f;
                }
                break;
            }
            case EReflectionsObjectiveType::Collect:
                EnsureItems(O);
                if (Quests->GetItemCount(O.Target) > OS.Progress) Updates.Add({Def.Id, O.Id, Quests->GetItemCount(O.Target), 0.0f, false});
                break;
            case EReflectionsObjectiveType::Event:
            {
                bool bStateful = false;
                for (const FName& K : StatefulKeys) bStateful |= K == O.Target;
                if (bStateful)
                {
                    const int32 N = QueryEventCount(O.Target, O.Spell);
                    if (N > OS.Progress) Updates.Add({Def.Id, O.Id, N, 0.0f, false});
                }
                break;
            }
            default:
                break;
            }
        }
        if (bRequiredDone && !Step->Choices.IsEmpty() && Step->ChoicePerson.IsNone() && Def.Giver.IsNone())
        {
            NarrationChoices.Add(Def.Id);
        }
    }
    for (const FUpdate& U : Updates)
    {
        if (U.bSpawn)
        {
            const FReflectionsQuestStep* Step = Quests->GetCurrentStep(U.Quest);
            const FReflectionsQuestObjective* O = Step ? Step->Objectives.FindByPredicate([&U](const FReflectionsQuestObjective& E) { return E.Id == U.Objective; }) : nullptr;
            if (O) SpawnFor(U.Quest, *O);
            Quests->MarkObjectiveSpawned(U.Quest, U.Objective);
        }
        else if (U.Held > 0.0f) Quests->AddHeldTime(U.Quest, U.Objective, U.Held);
        else if (U.Progress >= 0) Quests->SetObjectiveProgress(U.Quest, U.Objective, U.Progress);
    }
    for (AActor* Who : TalkedByProximity) Quests->NotifyTalkedTo(Who);
    if (!NarrationChoices.IsEmpty() && !bTalkOpen && !bJournalOpen && ShouldShowHud())
    {
        OpenChoice(NarrationChoices[0]);
    }
}

// ---- Targets -------------------------------------------------------------------------------------------------

AActor* UReflectionsQuestWorldSubsystem::FindPersonActor(FName PersonId) const
{
    if (PersonId.IsNone()) return nullptr;
    if (const TWeakObjectPtr<AActor>* Spawned = SpawnedPeople.Find(PersonId))
    {
        if (Spawned->IsValid() && !(*Spawned)->IsActorBeingDestroyed()) return Spawned->Get();
    }
    const FName Tag(*FString::Printf(TEXT("Person_%s"), *PersonId.ToString()));
    if (UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this))
    {
        for (AActor* A : Npcs->GetNpcActors())
        {
            if (A && (A->ActorHasTag(Tag) || UReflectionsQuestSubsystem::GetPersonId(A) == PersonId)) return A;
        }
    }
    if (UWorld* World = GetWorld())
    {
        for (TActorIterator<APawn> It(World); It; ++It)
        {
            if (It->ActorHasTag(Tag)) return *It;
        }
    }
    return nullptr;
}

AActor* UReflectionsQuestWorldSubsystem::FindSpellTarget(FName Target) const
{
    if (AActor* Person = FindPersonActor(Target)) return Person;
    return nullptr;
}

bool UReflectionsQuestWorldSubsystem::ResolveObjectiveTarget(const FReflectionsQuestDef& Def, const FReflectionsQuestObjective& O, FReflectionsQuestTarget& Out)
{
    Out = FReflectionsQuestTarget();
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    UReflectionsStoryMarkerSubsystem* Markers = UReflectionsStoryMarkerSubsystem::Get(this);
    const APawn* Hero = GetHero();
    const FVector From = Hero ? Hero->GetActorLocation() : FVector::ZeroVector;

    const auto UseLocation = [&](const FVector& L, float Radius, const FText& Label)
    {
        Out.bValid = true;
        Out.Location = L;
        Out.Radius = O.Radius > 0.0f ? O.Radius : Radius;
        Out.Label = Label;
        Out.Side = SideOf(L);
        Out.bOtherSide = IsWorldJumpActive() && Hero && Out.Side != SideOf(From);
        return true;
    };
    const auto UseMarker = [&](FName Name) -> bool
    {
        if (Name == TEXT("VillainHost"))
        {
            // The Tarnish's current host while it lives, else the nearest tarnished.
            const UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(this);
            if (AActor* HostActor = Villain ? Villain->GetHost() : nullptr) return UseLocation(HostActor->GetActorLocation(), 300.0f, LOCTEXT("TargetHost", "Burning eyes"));
            UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
            AActor* Best = nullptr;
            double BestD = TNumericLimits<double>::Max();
            for (AActor* A : Npcs ? Npcs->GetNpcActors() : TArray<AActor*>())
            {
                if (!A || Npcs->GetInfection(A) == EReflectionsNpcInfection::None) continue;
                const double D = FVector::DistSquared(From, A->GetActorLocation());
                if (D < BestD) { BestD = D; Best = A; }
            }
            if (Best) return UseLocation(Best->GetActorLocation(), 300.0f, LOCTEXT("TargetTarnished", "Tarnished"));
            return false;
        }
        if (Name == TEXT("VillainArena"))
        {
            FVector Center;
            float Radius = 0.0f;
            const UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(this);
            if (Villain && Villain->GetArena(Center, Radius) && !Center.IsNearlyZero())
            {
                return UseLocation(Center, FMath::Max(600.0f, Radius * 0.6f), LOCTEXT("TargetArena", "The Tarnish"));
            }
            Name = TEXT("Tower_Frostside");
        }
        AReflectionsStoryMarker* M = Markers ? Markers->Find(Name) : nullptr;
        return M && UseLocation(M->GetActorLocation(), M->Radius, Spaced(Name));
    };
    const auto UsePerson = [&](FName Person) -> bool
    {
        if (AActor* A = FindPersonActor(Person)) return UseLocation(A->GetActorLocation(), 250.0f, Quests ? Quests->GetPersonName(Person) : Spaced(Person));
        const FReflectionsQuestPerson* P = Quests ? Quests->FindPerson(Person) : nullptr;
        if (Markers && !Markers->Find(FName(*FString::Printf(TEXT("QuestGiver_%s"), *Person.ToString())), false) && P && !P->SpawnMarker.IsNone())
        {
            return UseMarker(P->SpawnMarker);
        }
        return UseMarker(FName(*FString::Printf(TEXT("QuestGiver_%s"), *Person.ToString())));
    };

    if (O.Type == EReflectionsObjectiveType::Event && O.Target == TEXT("ShardCollected"))
    {
        const AReflectionsCoinPickup* Nearest = nullptr;
        double NearestDistance = TNumericLimits<double>::Max();
        const bool bSameSideOnly = Hero && IsWorldJumpActive();
        const EReflectionsWorld CurrentSide = HeroSide();
        for (TActorIterator<AReflectionsCoinPickup> It(GetWorld()); It; ++It)
        {
            if (It->IsHidden() || It->IsActorBeingDestroyed() || !It->GetActorEnableCollision()) continue;
            if (!O.Spell.IsNone() && SideName(It->CoinWorld) != O.Spell) continue;
            if (bSameSideOnly && SideOf(It->GetActorLocation()) != CurrentSide) continue;
            const double Distance = FVector::DistSquared(From, It->GetActorLocation());
            if (Distance < NearestDistance)
            {
                Nearest = *It;
                NearestDistance = Distance;
            }
        }
        if (Nearest) return UseLocation(Nearest->GetActorLocation(), 150.0f, O.Text);
    }

    if (O.Type == EReflectionsObjectiveType::Event && (O.Target == TEXT("PageFound") || O.Target == TEXT("BookComplete")))
    {
        const bool bSingleCity = !IsWorldJumpActive();
        const FName Tower = O.Target == TEXT("BookComplete") ? FName(TEXT("Tower_Frostside"))
            : O.Spell.IsNone() ? NAME_None : FName(*FString::Printf(TEXT("Tower_%s"), *O.Spell.ToString()));
        const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
        const AReflectionsBookPagePickup* Nearest = nullptr;
        double NearestDistance = TNumericLimits<double>::Max();
        for (TActorIterator<AReflectionsBookPagePickup> It(GetWorld()); It; ++It)
        {
            if (It->IsHidden() || It->IsActorBeingDestroyed() || !It->GetActorEnableCollision()) continue;
            const FName Page = It->PageId.IsNone() ? It->GetFName() : It->PageId;
            if (Progress && Progress->HasPage(Page)) continue;
            if (bSingleCity && It->ActorHasTag(Tower))
            {
                return UseLocation(It->GetActorLocation(), 150.0f, It->GetDisplayTitle());
            }
            const EReflectionsWorld PageSide = SideOf(It->GetActorLocation());
            if (!bSingleCity && O.Target == TEXT("PageFound") && !O.Spell.IsNone() && SideName(PageSide) != O.Spell) continue;
            if (!bSingleCity && O.Target == TEXT("BookComplete") && Hero && PageSide != SideOf(From)) continue;
            const double Distance = FVector::DistSquared(From, It->GetActorLocation());
            if (Distance < NearestDistance)
            {
                Nearest = *It;
                NearestDistance = Distance;
            }
        }
        // In a city with world jumping, keep an authored route marker (such as the stair at the tower's foot).
        if (Nearest && (bSingleCity || O.Marker.IsNone()))
        {
            return UseLocation(Nearest->GetActorLocation(), 150.0f, Nearest->GetDisplayTitle());
        }
        if (O.Marker.IsNone() && !Tower.IsNone()) return UseMarker(Tower);
    }

    if (!O.Marker.IsNone() && O.Type != EReflectionsObjectiveType::Collect && O.Type != EReflectionsObjectiveType::Defeat)
    {
        return UseMarker(O.Marker);
    }
    switch (O.Type)
    {
    case EReflectionsObjectiveType::TalkTo:
    case EReflectionsObjectiveType::Deliver:
        return UsePerson(O.Target);
    case EReflectionsObjectiveType::GoTo:
    case EReflectionsObjectiveType::Protect:
        if (Quests && Quests->FindPerson(O.Target)) return UsePerson(O.Target);  // go to / stay with a person
        return UseMarker(O.Target);
    case EReflectionsObjectiveType::Collect:
    {
        AReflectionsQuestItem* Best = nullptr;
        double BestD = TNumericLimits<double>::Max();
        for (TActorIterator<AReflectionsQuestItem> It(GetWorld()); It; ++It)
        {
            if (It->ItemId != O.Target || It->IsHidden() || It->IsActorBeingDestroyed()) continue;
            const double D = FVector::DistSquared(From, It->GetActorLocation());
            if (D < BestD) { BestD = D; Best = *It; }
        }
        if (Best) return UseLocation(Best->GetActorLocation(), 150.0f, Spaced(O.Target));
        return UseMarker(O.Marker.IsNone() ? FName(*FString::Printf(TEXT("Item_%s"), *O.Target.ToString())) : O.Marker);
    }
    case EReflectionsObjectiveType::SpellHit:
        if (AReflectionsStoryMarker::IsStoryName(O.Target) || O.Target == TEXT("VillainArena")) return UseMarker(O.Target);
        return UsePerson(O.Target);
    case EReflectionsObjectiveType::Defeat:
    {
        UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
        AActor* Best = nullptr;
        double BestD = TNumericLimits<double>::Max();
        if (Npcs)
        {
            for (AActor* A : Npcs->GetNpcActors())
            {
                const UReflectionsNpcReactionComponent* C = A ? Npcs->FindNpc(A) : nullptr;
                if (!C || C->IsIncapacitated()) continue;
                const UReflectionsNpcArchetype* Arch = Npcs->ResolveArchetype(A);
                const FString Id = Arch ? Arch->ArchetypeId.ToString() : FString();
                const bool bMatch = O.Target.IsNone() || O.Target == TEXT("Any") ? Npcs->IsHostileToPlayer(A)
                    : (Id.StartsWith(O.Target.ToString()) || A->ActorHasTag(O.Target) ||
                       ((O.Target == TEXT("Infected") || O.Target == TEXT("Tarnished")) && Npcs->GetInfection(A) != EReflectionsNpcInfection::None) ||
                       (O.Target == TEXT("Hostile") && Npcs->IsHostileToPlayer(A)));
                if (!bMatch) continue;
                const double D = FVector::DistSquared(From, A->GetActorLocation());
                if (D < BestD) { BestD = D; Best = A; }
            }
        }
        if (Best) return UseLocation(Best->GetActorLocation(), 200.0f, Spaced(O.Target));
        return !O.Marker.IsNone() && UseMarker(O.Marker);
    }
    case EReflectionsObjectiveType::Event:
        if (O.Target == TEXT("BossDefeated") || O.Target == TEXT("FinaleStarted")) return UseMarker(TEXT("VillainArena"));
        if (O.Target == TEXT("KeyFound"))
        {
            for (TActorIterator<AReflectionsKeyPickup> It(GetWorld()); It; ++It)
            {
                if ((O.Spell.IsNone() || It->KeyId == O.Spell) && !It->IsHidden()) return UseLocation(It->GetActorLocation(), 150.0f, Spaced(It->KeyId));
            }
        }
        return false;
    default:
        return false;
    }
}

// ---- Spawning ------------------------------------------------------------------------------------------------

void UReflectionsQuestWorldSubsystem::EnsurePeople()
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests || !ReflectionsQuestWorldCVars::SpawnPeople) return;
    TSet<FName> Needed;
    for (const FReflectionsQuestDef& Def : Quests->GetQuests())
    {
        if (!Quests->IsQuestVisible(Def)) continue;
        const EReflectionsQuestStatus Status = Quests->GetStatus(Def.Id);
        if (!Def.Giver.IsNone() && (Status == EReflectionsQuestStatus::Available || Status == EReflectionsQuestStatus::Active || Status == EReflectionsQuestStatus::ReadyToTurnIn))
        {
            Needed.Add(Def.Giver);
        }
        if (const FReflectionsQuestStep* Step = Quests->GetCurrentStep(Def.Id))
        {
            for (const FReflectionsQuestObjective& O : Step->Objectives)
            {
                if ((O.Type == EReflectionsObjectiveType::TalkTo || O.Type == EReflectionsObjectiveType::Deliver) && !O.Target.IsNone()) Needed.Add(O.Target);
                if (O.Type == EReflectionsObjectiveType::SpellHit && Quests->FindPerson(O.Target)) Needed.Add(O.Target);
            }
            if (!Step->ChoicePerson.IsNone()) Needed.Add(Step->ChoicePerson);
        }
    }
    for (const FName& Person : Needed)
    {
        if (!Quests->IsPersonDead(Person) && !FindPersonActor(Person)) SpawnPerson(Person);
    }
}

AActor* UReflectionsQuestWorldSubsystem::SpawnPerson(FName PersonId)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    UReflectionsStoryMarkerSubsystem* Markers = UReflectionsStoryMarkerSubsystem::Get(this);
    if (!Quests || !Npcs || !Markers) return nullptr;
    const FReflectionsQuestPerson* P = Quests->FindPerson(PersonId);
    // QuestGiver_<Id> when the map has one, then the people book's work marker, then a fallback QuestGiver_<Id>.
    AReflectionsStoryMarker* Spot = Markers->Find(FName(*FString::Printf(TEXT("QuestGiver_%s"), *PersonId.ToString())), false);
    if (!Spot && P && !P->SpawnMarker.IsNone()) Spot = Markers->Find(P->SpawnMarker);
    if (!Spot) Spot = Markers->Find(FName(*FString::Printf(TEXT("QuestGiver_%s"), *PersonId.ToString())));
    if (!Spot) return nullptr;

    // Lives knows everyone: side, sex, job and the book's look, with a unique face. Ask it first.
    AActor* Actor = nullptr;
    if (UReflectionsLivesSubsystem* Lives = GetWorld()->GetSubsystem<UReflectionsLivesSubsystem>())
    {
        Actor = Lives->SpawnPerson(PersonId, Spot->GetActorLocation(), Spot->GetActorRotation().Yaw);
    }

    TSubclassOf<AActor> Look = nullptr;
    if (!Actor && P && P->Look.IsValid()) Look = P->Look.TryLoadClass<AActor>();
    if (!Actor && !Look && P && !P->Sex.IsNone())
    {
        // A team look of the right sex (the NPC system's own table), picked by id so the same person keeps it: walk the
        // list from the person's hash and stop at the first match, so only a look or two is ever loaded.
        const TArray<TSoftClassPtr<AActor>>& Looks = UReflectionsNpcSubsystem::TeamLooks();
        const EReflectionsNpcSex Want = P->Sex.ToString().StartsWith(TEXT("M")) ? EReflectionsNpcSex::Male : EReflectionsNpcSex::Female;
        const int32 Start = Looks.Num() > 0 ? static_cast<int32>(GetTypeHash(PersonId) % static_cast<uint32>(Looks.Num())) : 0;
        for (int32 n = 0; n < Looks.Num() && !Look; ++n)
        {
            // Never the other side's clothes (rags only Frostside, red only Giltside): skip a look whose name says
            // another side, before loading it.
            const FString LookName = Looks[(Start + n) % Looks.Num()].ToSoftObjectPath().GetAssetName();
            const auto Says = [&LookName](std::initializer_list<const TCHAR*> Words) { for (const TCHAR* W : Words) if (LookName.Contains(W)) return true; return false; };
            const bool bGilt = Says({TEXT("Gilt"), TEXT("Red")}), bFrost = Says({TEXT("Frost"), TEXT("White"), TEXT("Rag")}), bPew = Says({TEXT("Pew"), TEXT("Gray"), TEXT("Grey")});
            const bool bOtherSide = (P->Side == EReflectionsQuestSide::Giltside && (bFrost || bPew)) ||
                (P->Side == EReflectionsQuestSide::Frostside && (bGilt || bPew)) || (P->Side == EReflectionsQuestSide::Pewterside && (bGilt || bFrost));
            if (bOtherSide) continue;
            UClass* Class = Looks[(Start + n) % Looks.Num()].LoadSynchronous();
            if (Class && UReflectionsNpcSubsystem::GetLookSex(Class->GetDefaultObject<AActor>()) == Want) Look = Class;
        }
    }
    const FName Archetype = P && !P->Archetype.IsNone() ? P->Archetype : FName(TEXT("Civilian"));
    if (!Actor) Actor = Npcs->SpawnNpc(Archetype, Spot->GetActorLocation(), Spot->GetActorRotation().Yaw, Look);
    if (!Actor && Archetype != TEXT("Civilian"))
    {
        Actor = Npcs->SpawnNpc(TEXT("Civilian"), Spot->GetActorLocation(), Spot->GetActorRotation().Yaw, Look);
    }
    if (!Actor)
    {
        UE_LOG(LogReflectionsQuestWorld, Warning, TEXT("Could not spawn quest person %s."), *PersonId.ToString());
        return nullptr;
    }
    Actor->Tags.AddUnique(FName(*FString::Printf(TEXT("Person_%s"), *PersonId.ToString())));
    Actor->Tags.AddUnique(TEXT("QuestSpawned"));
    Actor->Tags.AddUnique(TEXT("NoVillain"));  // the Tarnish leaves quest givers alone
    SpawnedPeople.Add(PersonId, Actor);
    UE_LOG(LogReflectionsQuestWorld, Log, TEXT("Quest person %s spawned at %s (%s)."), *PersonId.ToString(), *Spot->GetActorLocation().ToCompactString(),
        Spot->bAutoPlaced ? TEXT("auto-placed marker") : TEXT("map marker"));
    return Actor;
}

void UReflectionsQuestWorldSubsystem::EnsureItems(const FReflectionsQuestObjective& O)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    UWorld* World = GetWorld();
    if (!Quests || !World || O.Target.IsNone()) return;
    const int32 Held = Quests->GetItemCount(O.Target);
    int32 Lying = 0;
    for (TActorIterator<AReflectionsQuestItem> It(World); It; ++It)
    {
        if (It->ItemId == O.Target && !It->IsHidden() && !It->IsActorBeingDestroyed()) ++Lying;
    }
    const int32 Missing = O.Count - Held - Lying;
    if (Missing <= 0) return;
    UReflectionsStoryMarkerSubsystem* Markers = UReflectionsStoryMarkerSubsystem::Get(this);
    const FName MarkerName = O.Marker.IsNone() ? FName(*FString::Printf(TEXT("Item_%s"), *O.Target.ToString())) : O.Marker;
    AReflectionsStoryMarker* Spot = Markers ? Markers->Find(MarkerName) : nullptr;
    if (!Spot) return;
    for (int32 i = 0; i < Missing; ++i)
    {
        const float Angle = (2.0f * PI * i) / FMath::Max(1, Missing);
        const FVector Offset = Missing > 1 ? FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f) * FMath::Min(Spot->Radius, 250.0f) : FVector::ZeroVector;
        const FTransform Xf(FRotator::ZeroRotator, Spot->GetActorLocation() + Offset + FVector(0, 0, 70));
        AReflectionsQuestItem* Item = World->SpawnActorDeferred<AReflectionsQuestItem>(AReflectionsQuestItem::StaticClass(), Xf, nullptr, nullptr,
            ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (!Item) continue;
        Item->ItemId = O.Target;
        Item->ItemName = Quests->GetItemName(O.Target);
        Item->bQuestSpawned = true;
        Item->FinishSpawning(Xf);
        SpawnedItems.Add(Item);
    }
}

void UReflectionsQuestWorldSubsystem::SpawnFor(FName QuestId, const FReflectionsQuestObjective& O)
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    UReflectionsStoryMarkerSubsystem* Markers = UReflectionsStoryMarkerSubsystem::Get(this);
    if (!Npcs || !Markers || O.SpawnArchetype.IsNone()) return;
    const FName MarkerName = !O.SpawnMarker.IsNone() ? O.SpawnMarker : !O.Marker.IsNone() ? O.Marker : (O.Type == EReflectionsObjectiveType::Protect ? O.Target : NAME_None);
    FVector Center;
    FReflectionsQuestTarget Special;
    const FReflectionsQuestDef* Def = UReflectionsQuestSubsystem::Get(this) ? UReflectionsQuestSubsystem::Get(this)->FindQuest(QuestId) : nullptr;
    if ((MarkerName == TEXT("VillainHost") || MarkerName == TEXT("VillainArena")) && Def)
    {
        FReflectionsQuestObjective Probe;
        Probe.Type = EReflectionsObjectiveType::GoTo;
        Probe.Target = MarkerName;
        if (ResolveObjectiveTarget(*Def, Probe, Special)) Center = Special.Location;
        else if (const APawn* Hero = GetHero()) Center = Hero->GetActorLocation() + Hero->GetActorForwardVector() * 1500.0f;
        else return;
    }
    else if (AReflectionsStoryMarker* Spot = MarkerName.IsNone() ? nullptr : Markers->Find(MarkerName))
    {
        Center = Spot->GetActorLocation();
    }
    else if (const APawn* Hero = GetHero())
    {
        Center = Hero->GetActorLocation() + Hero->GetActorForwardVector() * 1500.0f;
    }
    else
    {
        return;
    }
    int32 Count = FMath::Max(1, O.SpawnCount > 0 ? O.SpawnCount : O.Count);
    const bool bInfected = O.SpawnArchetype == TEXT("Infected") || O.SpawnArchetype == TEXT("Tarnished");
    if (bInfected)
    {
        const float Radius = O.Radius > 0.0f ? O.Radius : 4000.0f;
        if (O.Type == EReflectionsObjectiveType::Event && O.Target == TEXT("NpcCured"))
        {
            if (!IsHeroNear(Center, Radius + 800.0f)) return;
            UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
            if (const FReflectionsObjectiveState* State = Quests ? Quests->FindObjectiveState(QuestId, O.Id) : nullptr)
            {
                Count = FMath::Min(Count, O.Count - State->Progress);
            }
        }
        // Only make up the difference: tarnished already near the spot count.
        for (AActor* A : Npcs->GetNpcActors())
        {
            const UReflectionsNpcReactionComponent* Npc = A ? Npcs->FindNpc(A) : nullptr;
            if (Npc && !Npc->IsIncapacitated() && Npcs->GetInfection(A) != EReflectionsNpcInfection::None &&
                FVector::Dist2D(A->GetActorLocation(), Center) < Radius) --Count;
        }
        if (Count <= 0) return;
        // The story's rule: turn townsfolk near the spot first (they get the Tarnish look and count on the meter).
        TArray<AActor*> Near;
        for (AActor* A : Npcs->GetNpcActors())
        {
            if (!A || Npcs->GetInfection(A) != EReflectionsNpcInfection::None || Npcs->IsHostileToPlayer(A)) continue;
            if (A->ActorHasTag(TEXT("NoVillain")) || A->ActorHasTag(TEXT("QuestSpawned")) || !UReflectionsQuestSubsystem::GetPersonId(A).IsNone()) continue;
            if (FVector::Dist2D(A->GetActorLocation(), Center) < Radius) Near.Add(A);
        }
        if (Count <= 0) return;
        Near.Sort([&Center](const AActor& L, const AActor& R) { return FVector::DistSquared(L.GetActorLocation(), Center) < FVector::DistSquared(R.GetActorLocation(), Center); });
        for (int32 i = 0; i < Near.Num() && Count > 0; ++i)
        {
            if (Npcs->SetInfection(Near[i], EReflectionsNpcInfection::Infected, nullptr))
            {
                --Count;
                Near[i]->Tags.AddUnique(FName(*FString::Printf(TEXT("QuestSpawn_%s"), *QuestId.ToString())));
            }
        }
    }
    const FName Archetype = bInfected ? FName(TEXT("Civilian")) : O.SpawnArchetype;
    const UNavigationSystemV1* Nav = bInfected ? FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()) : nullptr;
    for (int32 i = 0; i < Count; ++i)
    {
        const float Angle = (2.0f * PI * i) / Count;
        FVector L = Center + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.0f) * 900.0f;
        FNavLocation Walkable;
        if (Nav && Nav->ProjectPointToNavigation(L, Walkable, FVector(850.0f, 850.0f, 300.0f)))
        {
            L = Walkable.Location;
        }
        if (AActor* A = Npcs->SpawnNpc(Archetype, L, (Center - L).Rotation().Yaw))
        {
            A->Tags.AddUnique(FName(*FString::Printf(TEXT("QuestSpawn_%s"), *QuestId.ToString())));
            if (bInfected) Npcs->SetInfection(A, EReflectionsNpcInfection::Infected, nullptr);
        }
    }
}

// ---- Listeners -----------------------------------------------------------------------------------------------

void UReflectionsQuestWorldSubsystem::HandleQuestEvent(FName QuestId, FName StepId, FName ObjectiveId, EReflectionsQuestEventType Type)
{
    ++Revision;
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    const FReflectionsQuestDef* Def = Quests ? Quests->FindQuest(QuestId) : nullptr;
    if (!Def) return;
    const FReflectionsQuestStep* Step = StepId.IsNone() ? nullptr : Def->FindStep(StepId);
    const FName DefaultSpeaker = Step && !Step->Speaker.IsNone() ? Step->Speaker : Def->Giver;
    switch (Type)
    {
    case EReflectionsQuestEventType::Accepted:
    {
        PlaySound(TEXT("Quest_Start"));
        UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
        for (const FName& Person : Def->StartsTarnished)
        {
            AActor* Who = FindPersonActor(Person);
            if (!Who) Who = SpawnPerson(Person);
            if (Who && Npcs)
            {
                Who->Tags.AddUnique(TEXT("NoVillain"));
                Npcs->SetInfection(Who, EReflectionsNpcInfection::Infected, nullptr);
                KnownTarnished.Add(Who);
            }
        }
        break;
    }
    case EReflectionsQuestEventType::Completed: PlaySound(TEXT("Quest_Complete")); break;
    case EReflectionsQuestEventType::ObjectiveComplete:
    case EReflectionsQuestEventType::ObjectiveProgress:
    {
        if (Type == EReflectionsQuestEventType::ObjectiveComplete) PlaySound(TEXT("Quest_Objective"));
        const FReflectionsQuestObjective* O = Step ? Step->Objectives.FindByPredicate([ObjectiveId](const FReflectionsQuestObjective& E) { return E.Id == ObjectiveId; }) : nullptr;
        if (!O) break;
        if (Type == EReflectionsQuestEventType::ObjectiveComplete)
        {
            PlayLines(UReflectionsQuestSubsystem::ToLines(O->CompleteLines, O->Type == EReflectionsObjectiveType::TalkTo ? O->Target : DefaultSpeaker));
        }
        else if (const FReflectionsObjectiveState* OS = Quests->FindObjectiveState(QuestId, ObjectiveId))
        {
            if (O->ProgressLines.IsValidIndex(OS->Progress - 1))
            {
                PlayLines(UReflectionsQuestSubsystem::ToLines({O->ProgressLines[OS->Progress - 1]}, DefaultSpeaker));
            }
        }
        break;
    }
    case EReflectionsQuestEventType::StepComplete:
        if (Step) PlayLines(UReflectionsQuestSubsystem::ToLines(Step->CompleteLines, DefaultSpeaker));
        if (Step && !Step->CutsceneOnComplete.IsNone()) PlayCutscene(Step->CutsceneOnComplete);
        break;
    case EReflectionsQuestEventType::StepStarted:
    {
        StepStartedAt.Add(QuestId, Clock);
        PlayStepCue(QuestId, StepId);
        if (!Step) break;
        PlayLines(UReflectionsQuestSubsystem::ToLines(Step->Lines, DefaultSpeaker));
        if (!Step->Cutscene.IsNone() && !PlayCutscene(Step->Cutscene))
        {
            // Nothing to watch: go on (next tick, outside this event).
            StepStartedAt.Add(QuestId, Clock - 10.0f);
        }
        break;
    }
    default: break;
    }
}

void UReflectionsQuestWorldSubsystem::HandleQuestsChanged()
{
    ++Revision;
    if (bTalkOpen && TalkChoiceQuest.IsNone())
    {
        const TArray<FReflectionsTalkOption> Previous = TalkOptions;
        RefreshTalkOptions();
        if (Previous.Num() != TalkOptions.Num())
        {
            ++TalkRevision;
        }
        else
        {
            for (int32 Index = 0; Index < TalkOptions.Num(); ++Index)
            {
                if (Previous[Index].Action == TalkOptions[Index].Action && Previous[Index].bPrimary == TalkOptions[Index].bPrimary &&
                    Previous[Index].Label.EqualTo(TalkOptions[Index].Label)) continue;
                ++TalkRevision;
                break;
            }
        }
    }
}

void UReflectionsQuestWorldSubsystem::HandleSpellHit(const FReflectionsSpellHitData& Hit)
{
    if (!IsHeroActor(Hit.Caster, GetHero())) return;
    CountSpellAt(Hit.Spell, Hit.Location, Hit.Target, false);
}

void UReflectionsQuestWorldSubsystem::HandleSpellEvent(EHeroSpell Spell, FVector Location, AActor* Caster, float Intensity)
{
    APawn* Hero = GetHero();
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests || !IsHeroActor(Caster, Hero)) return;
    static const UEnum* SpellEnum = StaticEnum<EHeroSpell>();
    Quests->NotifyEventAt(TEXT("SpellCast"), FName(*SpellEnum->GetNameStringByValue(static_cast<int64>(Spell))), Hero->GetActorLocation());
    CountSpellAt(Spell, Location, nullptr, true);
}

void UReflectionsQuestWorldSubsystem::HandleDoorOpened()
{
    if (UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this))
    {
        for (TActorIterator<AReflectionsSealedDoor> It(GetWorld()); It; ++It)
        {
            if (It->IsOpen()) Quests->NotifyEventAt(TEXT("DoorOpened"), It->RequiredKey, It->GetActorLocation());
            if (It->IsOpen() && It->RequiredKey == TEXT("GiltTowerKey")) PlayCutscene(TEXT("GiltTower"));
        }
    }
}

void UReflectionsQuestWorldSubsystem::HandleNpcInfection(AActor* Npc, EReflectionsNpcInfection State, AActor* Source)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests || !Npc) return;
    const FName Person = UReflectionsQuestSubsystem::GetPersonId(Npc);
    const FVector Where = Npc->GetActorLocation();
    if (State == EReflectionsNpcInfection::None)
    {
        if (KnownTarnished.Remove(Npc) > 0) Quests->NotifyEventAt(TEXT("NpcCured"), Person, Where);
        return;
    }
    const bool bNew = !KnownTarnished.Contains(Npc);
    KnownTarnished.Add(Npc);
    if (State == EReflectionsNpcInfection::VillainHost) Quests->NotifyEventAt(TEXT("VillainHost"), Person, Where);
    if (bNew && State == EReflectionsNpcInfection::Infected)
    {
        Quests->NotifyEventAt(TEXT("NpcTarnished"), Person, Where);
        const APawn* Hero = GetHero();
        if (Source && Hero && FVector::Dist(Hero->GetActorLocation(), Where) < 4000.0f) Quests->NotifyEventAt(TEXT("Conversion"), Person, Where);
    }
}

void UReflectionsQuestWorldSubsystem::CountSpellAt(EHeroSpell Spell, const FVector& Location, AActor* HitActor, bool bFromCast)
{
    struct FHitData { EHeroSpell Spell; FVector Location; TObjectPtr<AActor> Target; };
    const FHitData Hit{Spell, Location, HitActor};
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    APawn* Hero = GetHero();
    if (!Quests || !Hero) return;
    const double Now = FPlatformTime::Seconds();
    UReflectionsStoryMarkerSubsystem* Markers = UReflectionsStoryMarkerSubsystem::Get(this);
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    TArray<TPair<FName, FName>> Hits;
    for (const FReflectionsQuestDef& Def : Quests->GetQuests())
    {
        const FReflectionsQuestState* S = Quests->FindState(Def.Id);
        const FReflectionsQuestStep* Step = S && S->Status == EReflectionsQuestStatus::Active ? Def.FindStep(S->StepId) : nullptr;
        if (!Step) continue;
        for (int32 i = 0; i < Step->Objectives.Num() && i < S->Objectives.Num(); ++i)
        {
            const FReflectionsQuestObjective& O = Step->Objectives[i];
            if (O.Type != EReflectionsObjectiveType::SpellHit || S->Objectives[i].bDone || !SpellMatches(Hit.Spell, O.Spell)) continue;
            if (IsWorldJumpActive() && !ReflectionsQuest::Matches(O.Side, SideOf(Hit.Location))) continue;
            bool bTarget = false;
            if (O.Target.IsNone() || O.Target == TEXT("Any"))
            {
                bTarget = true;
            }
            else if (AReflectionsStoryMarker::IsStoryName(O.Target) || O.Target == TEXT("VillainArena"))
            {
                AReflectionsStoryMarker* M = Markers ? Markers->Find(O.Target) : nullptr;
                if (M)
                {
                    const float R = O.Radius > 0.0f ? O.Radius : M->Radius;
                    bTarget = FVector::Dist(Hit.Location, M->GetActorLocation()) <= R ||
                        (bFromCast && FVector::Dist2D(Hero->GetActorLocation(), M->GetActorLocation()) <= FMath::Max(R, 300.0f));
                }
            }
            else if (bFromCast)
            {
                bTarget = false;  // people and tags need a real hit
            }
            else if (AActor* Person = FindPersonActor(O.Target))
            {
                bTarget = Hit.Target == Person || (Hit.Target && Hit.Target->GetOwner() == Person) || FVector::Dist(Hit.Location, Person->GetActorLocation()) < 120.0f;
            }
            else if (Hit.Target)
            {
                bTarget = Hit.Target->ActorHasTag(O.Target) ||
                    ((O.Target == TEXT("Infected") || O.Target == TEXT("Tarnished")) && Npcs && Npcs->GetInfection(Hit.Target) != EReflectionsNpcInfection::None);
                if (!bTarget && Npcs)
                {
                    const UReflectionsNpcArchetype* Arch = Npcs->ResolveArchetype(Hit.Target);
                    bTarget = Arch && Arch->ArchetypeId.ToString().StartsWith(O.Target.ToString());
                }
            }
            if (!bTarget) continue;
            // One cast is one hit: the cast event and its impact both arrive.
            const FName Key(*FString::Printf(TEXT("%s.%s"), *Def.Id.ToString(), *O.Id.ToString()));
            double& Last = SpellCooldown.FindOrAdd(Key);
            if (Now - Last < 1.0) continue;
            Last = Now;
            Hits.Add({Def.Id, O.Id});
        }
    }
    for (const TPair<FName, FName>& H : Hits) Quests->AdvanceObjective(H.Key, H.Value, 1);
}

void UReflectionsQuestWorldSubsystem::HandleNpcDied(AActor* Npc, AActor* Killer)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    APawn* Hero = GetHero();
    if (!Quests || !Npc || !Hero) return;
    const FName DeadPerson = UReflectionsQuestSubsystem::GetPersonId(Npc);
    if (!DeadPerson.IsNone()) Quests->NotifyEventAt(TEXT("PersonDied"), DeadPerson, Npc->GetActorLocation());
    const bool bByHero = IsHeroActor(Killer, Hero) || (!Killer && FVector::Dist(Npc->GetActorLocation(), Hero->GetActorLocation()) < 3000.0f);
    if (!bByHero && DeadPerson.IsNone()) return;
    const UReflectionsNpcArchetype* Arch = Npcs ? Npcs->ResolveArchetype(Npc) : nullptr;
    const FString Id = Arch ? Arch->ArchetypeId.ToString() : FString();
    const bool bInfected = Npcs && Npcs->GetInfection(Npc) != EReflectionsNpcInfection::None;
    const bool bHostile = Npcs && Npcs->IsHostileToPlayer(Npc);
    const FName Person = UReflectionsQuestSubsystem::GetPersonId(Npc);
    // A cure step whose tarnished target the hero killed instead branches (ifKilledNext); the kill then counts there.
    if (bByHero && bInfected)
    {
        TArray<TPair<FName, FName>> Branches;
        UReflectionsStoryMarkerSubsystem* BranchMarkers = UReflectionsStoryMarkerSubsystem::Get(this);
        for (const FReflectionsQuestDef& Def : Quests->GetQuests())
        {
            const FReflectionsQuestStep* Step = Quests->GetStatus(Def.Id) == EReflectionsQuestStatus::Active ? Quests->GetCurrentStep(Def.Id) : nullptr;
            if (!Step || Step->IfKilledNext.IsNone()) continue;
            bool bNear = true;
            for (const FReflectionsQuestObjective& O : Step->Objectives)
            {
                AReflectionsStoryMarker* M = O.Marker.IsNone() || !BranchMarkers ? nullptr : BranchMarkers->Find(O.Marker);
                if (M) bNear = FVector::Dist(M->GetActorLocation(), Npc->GetActorLocation()) <= FMath::Max(O.Radius, 1500.0f);
            }
            if (bNear) Branches.Add({Def.Id, Step->IfKilledNext});
        }
        for (const TPair<FName, FName>& B : Branches) Quests->CompleteStepTo(B.Key, B.Value);
    }
    TArray<TPair<FName, FName>> Kills;
    for (const FReflectionsQuestDef& Def : Quests->GetQuests())
    {
        if (!bByHero) break;
    {
        const FReflectionsQuestState* S = Quests->FindState(Def.Id);
        const FReflectionsQuestStep* Step = S && S->Status == EReflectionsQuestStatus::Active ? Def.FindStep(S->StepId) : nullptr;
        if (!Step) continue;
        for (int32 i = 0; i < Step->Objectives.Num() && i < S->Objectives.Num(); ++i)
        {
            const FReflectionsQuestObjective& O = Step->Objectives[i];
            if (O.Type != EReflectionsObjectiveType::Defeat || S->Objectives[i].bDone) continue;
            if (IsWorldJumpActive() && !ReflectionsQuest::Matches(O.Side, SideOf(Npc->GetActorLocation()))) continue;
            const FString T = O.Target.ToString();
            const bool bMatch = O.Target.IsNone() || O.Target == TEXT("Any") ? bHostile || bInfected
                : (Id.StartsWith(T) || Npc->ActorHasTag(O.Target) || Person == O.Target ||
                   ((O.Target == TEXT("Infected") || O.Target == TEXT("Tarnished")) && bInfected) || (O.Target == TEXT("Hostile") && bHostile));
            if (bMatch) Kills.Add({Def.Id, O.Id});
        }
    }
    }
    for (const TPair<FName, FName>& K : Kills) Quests->AdvanceObjective(K.Key, K.Value, 1);
    if (!Person.IsNone() && !Quests->IsPersonDead(Person))
    {
        TArray<FName> WasOpen;
        for (const FReflectionsQuestDef& Def : Quests->GetQuests())
        {
            const EReflectionsQuestStatus St = Quests->GetStatus(Def.Id);
            if (St == EReflectionsQuestStatus::Active || St == EReflectionsQuestStatus::ReadyToTurnIn) WasOpen.Add(Def.Id);
        }
        Quests->NotifyPersonDied(Person, bByHero);
        // The failed quests' fail lines (the dead don't speak: PlayLines drops their lines).
        for (const FName& F : WasOpen)
        {
            const FReflectionsQuestDef* Def = Quests->FindQuest(F);
            if (Def && Quests->GetStatus(F) == EReflectionsQuestStatus::Failed) PlayLines(UReflectionsQuestSubsystem::ToLines(Def->FailLines, Def->Giver));
        }
    }
    Quests->NotifyEventAt(TEXT("Defeated"), Arch ? Arch->ArchetypeId : NAME_None, Npc->GetActorLocation());
}

void UReflectionsQuestWorldSubsystem::HandlePlayerCrime(AActor* Victim, FName Crime, AActor* Witness, FVector Location, float Heat)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    const UWorld* World = GetWorld();
    if (!Quests || !World) return;
    const FName VictimId = UReflectionsQuestSubsystem::GetPersonId(Victim);
    const FString Key = FString::Printf(TEXT("%s|%s|%s|%d|%d"), *GetNameSafe(Victim), *VictimId.ToString(), *Crime.ToString(),
        static_cast<int32>(FMath::RoundToInt(Location.X / 300.0)), static_cast<int32>(FMath::RoundToInt(Location.Y / 300.0)));
    const double Now = World->GetTimeSeconds();
    const float Severity = UReflectionsQuestSubsystem::CrimeSeverity(Crime);
    // The victim's standing drops once per crime, however many saw it.
    const double* Last = CountedCrimes.Find(Key);
    if (!Last || Now - *Last > 10.0)
    {
        CountedCrimes.Add(Key, Now);
        if (!VictimId.IsNone()) Quests->NotifyCrimeAgainst(VictimId, Severity);
    }
    // A person who saw it thinks less of the hero too (a quarter), once per crime each.
    const FName WitnessId = UReflectionsQuestSubsystem::GetPersonId(Witness);
    if (!WitnessId.IsNone() && WitnessId != VictimId)
    {
        bool bSeen = false;
        CrimeWitnesses.Add(Key + TEXT("@") + WitnessId.ToString(), &bSeen);
        if (!bSeen) Quests->NotifyCrimeAgainst(WitnessId, Severity * 0.25f);
    }
    if (CountedCrimes.Num() > 64) { CountedCrimes.Reset(); CrimeWitnesses.Reset(); }
}

void UReflectionsQuestWorldSubsystem::HandleWorldChanged(EReflectionsWorld From, EReflectionsWorld To)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    if (!Quests || From == To) return;
    // A checkpoint restore also sets the side; it is not a jump.
    const UReflectionsGameFlowWorldSubsystem* Flow = UReflectionsGameFlowWorldSubsystem::Get(this);
    if (Flow && !Flow->IsPlaying()) return;
    TArray<TPair<FName, FName>> Jumps;
    for (const FReflectionsQuestDef& Def : Quests->GetQuests())
    {
        const FReflectionsQuestState* S = Quests->FindState(Def.Id);
        const FReflectionsQuestStep* Step = S && S->Status == EReflectionsQuestStatus::Active ? Def.FindStep(S->StepId) : nullptr;
        if (!Step) continue;
        for (int32 i = 0; i < Step->Objectives.Num() && i < S->Objectives.Num(); ++i)
        {
            const FReflectionsQuestObjective& O = Step->Objectives[i];
            if (O.Type == EReflectionsObjectiveType::WorldJump && !S->Objectives[i].bDone && ReflectionsQuest::Matches(O.Side, To)) Jumps.Add({Def.Id, O.Id});
        }
    }
    for (const TPair<FName, FName>& J : Jumps) Quests->AdvanceObjective(J.Key, J.Value, 1);
    Quests->NotifyEvent(TEXT("WorldJump"), SideName(To));
}

void UReflectionsQuestWorldSubsystem::HandleCoinsChanged(EReflectionsWorld World, int32 Count)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    const int32 Before = LastCoins.FindRef(World);
    LastCoins.Add(World, Count);
    if (Quests && Count > Before) Quests->NotifyEventCount(TEXT("ShardCollected"), SideName(World), Count - Before);
}

void UReflectionsQuestWorldSubsystem::HandlePagesChanged(int32 Pages, int32 PagesForBook)
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    if (!Quests || !Progress) return;
    for (const FName& Page : Progress->GetPages())
    {
        if (KnownPages.Contains(Page)) continue;
        KnownPages.Add(Page);
        const EReflectionsWorld* Cached = PageSides.Find(Page);
        const FName Side = SideName(Cached ? *Cached : HeroSide());
        Quests->AddUnlock(FName(*FString::Printf(TEXT("PageFound_%s"), *Side.ToString())), NAME_None);
        Quests->NotifyEvent(TEXT("PageFound"), Side);
    }
    // The story's event-driven scenes play when the event happens, whatever the main quest's step
    // (pages come in any order); the quest's own cutscene steps then see them played and go on.
    if (Pages == 1) PlayCutscene(TEXT("FirstPage"));
}

void UReflectionsQuestWorldSubsystem::HandleKeyAdded(FName KeyId)
{
    if (UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this)) Quests->NotifyEvent(TEXT("KeyFound"), KeyId);
}

void UReflectionsQuestWorldSubsystem::HandleBookComplete()
{
    // MirrorWhole is played by the villain's OnBookComplete handler (one owner); the quest's step waits for it.
    if (UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this)) Quests->NotifyEvent(TEXT("BookComplete"), NAME_None);
}

void UReflectionsQuestWorldSubsystem::HandleVictory()
{
    if (UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this))
    {
        Quests->NotifyEvent(TEXT("BossDefeated"), NAME_None);
        Quests->NotifyEvent(TEXT("Victory"), NAME_None);
    }
}

// ---- HUD state -----------------------------------------------------------------------------------------------

void UReflectionsQuestWorldSubsystem::UpdateTracker()
{
    UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    TrackerLines.Reset();
    TrackedTarget = FReflectionsQuestTarget();
    TrackedTitle = FText::GetEmpty();
    if (!Quests) return;
    const FName Id = Quests->GetTrackedQuest();
    const FReflectionsQuestDef* Def = Quests->FindQuest(Id);
    const FReflectionsQuestState* S = Quests->FindState(Id);
    if (!Def || !S) return;
    TrackedTitle = Def->Title;
    if (S->Status == EReflectionsQuestStatus::ReadyToTurnIn)
    {
        TrackerLines.Add({FText::Format(LOCTEXT("TrackReturn", "Return to {0}"), Quests->GetPersonName(Def->Giver)), false, false});
        FReflectionsQuestObjective Back;
        Back.Type = EReflectionsObjectiveType::TalkTo;
        Back.Target = Def->Giver;
        ResolveObjectiveTarget(*Def, Back, TrackedTarget);
        return;
    }
    if (S->Status != EReflectionsQuestStatus::Active) return;
    const FReflectionsQuestStep* Step = Def->FindStep(S->StepId);
    if (!Step) return;
    bool bRequiredDone = true;
    for (int32 i = 0; i < Step->Objectives.Num(); ++i)
    {
        const FReflectionsQuestObjective& O = Step->Objectives[i];
        const FReflectionsObjectiveState* OS = S->Objectives.IsValidIndex(i) ? &S->Objectives[i] : nullptr;
        const bool bDone = OS && OS->bDone;
        if (!O.bHidden) TrackerLines.Add({Quests->FormatObjective(O, OS), bDone, O.bOptional});
        if (!bDone && !O.bOptional) bRequiredDone = false;
        if (Step->bOrdered && !bDone && !O.bOptional)
        {
            if (!TrackedTarget.bValid) ResolveObjectiveTarget(*Def, O, TrackedTarget);
            break;  // later objectives show once this one is done
        }
        if (!bDone && !TrackedTarget.bValid && !O.bOptional && !O.bHidden) ResolveObjectiveTarget(*Def, O, TrackedTarget);
    }
    if (!TrackedTarget.bValid)
    {
        // Only optional objectives left to point at.
        for (int32 i = 0; i < Step->Objectives.Num() && !TrackedTarget.bValid; ++i)
        {
            const bool bDone = S->Objectives.IsValidIndex(i) && S->Objectives[i].bDone;
            if (!bDone) ResolveObjectiveTarget(*Def, Step->Objectives[i], TrackedTarget);
        }
    }
    if (bRequiredDone && !Step->Choices.IsEmpty())
    {
        const FName Who = !Step->ChoicePerson.IsNone() ? Step->ChoicePerson : Def->Giver;
        if (!Who.IsNone())
        {
            TrackerLines.Add({FText::Format(LOCTEXT("TrackDecide", "Give {0} your answer"), Quests->GetPersonName(Who)), false, false});
            FReflectionsQuestObjective Ask;
            Ask.Type = EReflectionsObjectiveType::TalkTo;
            Ask.Target = Who;
            ResolveObjectiveTarget(*Def, Ask, TrackedTarget);
        }
    }
}

void UReflectionsQuestWorldSubsystem::UpdateMarks()
{
    Marks.Reset();
    const APawn* Hero = GetHero();
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Hero || !Npcs) return;
    for (AActor* A : Npcs->GetNpcActors())
    {
        if (!A || FVector::DistSquared(A->GetActorLocation(), Hero->GetActorLocation()) > FMath::Square(4000.0f)) continue;
        if (UReflectionsQuestSubsystem::GetPersonId(A).IsNone()) continue;
        TCHAR Glyph;
        if (HasBusiness(A, Glyph))
        {
            FReflectionsQuestMark Mark;
            Mark.Actor = A;
            Mark.Glyph = Glyph;
            Marks.Add(Mark);
        }
    }
}

void UReflectionsQuestWorldSubsystem::UpdatePrompt()
{
    PromptTarget.Reset();
    const APawn* Hero = GetHero();
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    if (!Hero || !Npcs || !ShouldShowHud()) return;
    FVector View = Hero->GetControlRotation().Vector();
    View.Z = 0.0;
    View = View.GetSafeNormal();
    double Best = TNumericLimits<double>::Max();
    for (AActor* A : Npcs->GetNpcActors())
    {
        if (!A || UReflectionsQuestSubsystem::GetPersonId(A).IsNone()) continue;
        const UReflectionsNpcReactionComponent* C = Npcs->FindNpc(A);
        if (C && C->IsIncapacitated()) continue;
        FVector Offset = A->GetActorLocation() - Hero->GetActorLocation();
        const double Distance = Offset.Size();
        if (Distance > ReflectionsQuestWorldCVars::TalkRadius) continue;
        Offset.Z = 0.0;
        const double Facing = View.IsNearlyZero() ? 0.0 : FVector::DotProduct(View, Offset.GetSafeNormal());
        const double Score = Distance * (1.6 - Facing);
        if (Score < Best) { Best = Score; PromptTarget = A; }
    }
    for (FReflectionsQuestMark& M : Marks) M.bPrompt = M.Actor == PromptTarget;
}

FText UReflectionsQuestWorldSubsystem::GetPromptText() const
{
    const UReflectionsQuestSubsystem* Quests = UReflectionsQuestSubsystem::Get(this);
    AActor* Target = PromptTarget.Get();
    if (!Quests || !Target) return FText::GetEmpty();
    const FText Name = Quests->GetPersonName(UReflectionsQuestSubsystem::GetPersonId(Target));
    TCHAR Glyph;
    const bool bBusiness = HasBusiness(Target, Glyph);
    if (IsUsingGamepad())
    {
        // Without quest business the pad button goes to live voice, so only offer the card when there is business.
        if (!bBusiness && !bInputBoundToPadTalk) return FText::GetEmpty();
        return FText::Format(LOCTEXT("PromptPad", "D-pad ↓   Speak with {0}"), Name);
    }
    return FText::Format(LOCTEXT("PromptKey", "E   Speak with {0}"), Name);
}

bool UReflectionsQuestWorldSubsystem::GetBanner(FText& OutKicker, FText& OutTitle, FText& OutDetail, FLinearColor& OutColor, float& OutAlpha) const
{
    const float T = Clock - BannerStarted;
    if (T < 0.0f || T > BannerDuration) return false;
    OutKicker = Banner.Kicker;
    OutTitle = Banner.Title;
    OutDetail = Banner.Detail;
    OutColor = Banner.Color;
    OutAlpha = FMath::Clamp(FMath::Min(T / 0.25f, (BannerDuration - T) / 0.6f), 0.0f, 1.0f);
    return true;
}

bool UReflectionsQuestWorldSubsystem::GetSubtitle(FText& OutSpeaker, FText& OutLine, float& OutAlpha) const
{
    const float T = Clock - SubtitleStarted;
    if (T < 0.0f || T > Subtitle.Seconds) return false;
    OutSpeaker = Subtitle.Speaker;
    OutLine = Subtitle.Line;
    OutAlpha = FMath::Clamp(FMath::Min(T / 0.2f, (Subtitle.Seconds - T) / 0.4f), 0.0f, 1.0f);
    return true;
}

// ---- Sound ---------------------------------------------------------------------------------------------------

void UReflectionsQuestWorldSubsystem::PlaySound(const TCHAR* Cue)
{
    const FName Key(Cue);
    TObjectPtr<USoundBase>* Found = Sounds.Find(Key);
    if (!Found)
    {
        const FString Path = FString::Printf(TEXT("/Game/Audio/Jam/Cues/SCue_%s.SCue_%s"), Cue, Cue);
        USoundBase* Sound = LoadObject<USoundBase>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
        if (!Sound && FCString::Strncmp(Cue, TEXT("Quest_"), 6) == 0)
        {
            // Until audio makes quest cues, use the UI confirm.
            Sound = LoadObject<USoundBase>(nullptr, TEXT("/Game/Audio/Jam/Cues/SCue_UI_Confirm.SCue_UI_Confirm"), nullptr, LOAD_NoWarn | LOAD_Quiet);
        }
        Found = &Sounds.Add(Key, Sound);
    }
    if (*Found) UGameplayStatics::PlaySound2D(this, *Found, 1.0f, 1.0f, 0.0f, nullptr, nullptr, true);
}

void UReflectionsQuestWorldSubsystem::PlayStepCue(FName QuestId, FName StepId)
{
    const FString Name = FString::Printf(TEXT("SCue_VO_Quest_%s_%s"), *QuestId.ToString(), *StepId.ToString());
    const FString Path = FString::Printf(TEXT("/Game/Audio/Jam/Voice/Cues/Quest/%s.%s"), *Name, *Name);
    if (USoundBase* Sound = LoadObject<USoundBase>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet))
    {
        UGameplayStatics::PlaySound2D(this, Sound, 1.0f, 1.0f, 0.0f, nullptr, nullptr, true);
    }
}

// ---- Tests ---------------------------------------------------------------------------------------------------

FString UReflectionsQuestWorldSubsystem::DescribeUi() const
{
    FString Out = FString::Printf(TEXT("HUD %s | journal %s | talk %s\n"), ShouldShowHud() ? TEXT("shown") : TEXT("hidden"),
        bJournalOpen ? TEXT("open") : TEXT("closed"), bTalkOpen ? TEXT("open") : TEXT("closed"));
    Out += FString::Printf(TEXT("Tracked: %s\n"), *TrackedTitle.ToString());
    for (const FReflectionsTrackerLine& L : TrackerLines)
    {
        Out += FString::Printf(TEXT("  %s %s%s\n"), L.bDone ? TEXT("[x]") : TEXT("[ ]"), *L.Text.ToString(), L.bOptional ? TEXT(" (optional)") : TEXT(""));
    }
    if (TrackedTarget.bValid)
    {
        const APawn* Hero = GetHero();
        Out += FString::Printf(TEXT("Pointer: %s at %s, %.0f m%s\n"), *TrackedTarget.Label.ToString(), *TrackedTarget.Location.ToCompactString(),
            Hero ? FVector::Dist(Hero->GetActorLocation(), TrackedTarget.Location) / 100.0f : -1.0f, TrackedTarget.bOtherSide ? TEXT(" (other side)") : TEXT(""));
    }
    Out += FString::Printf(TEXT("Marks: %d, prompt: %s\n"), Marks.Num(), *GetPromptText().ToString());
    if (bTalkOpen)
    {
        Out += FString::Printf(TEXT("Talk: %s: \"%s\" (%d/%d)\n"), *GetTalkSpeaker().ToString(), *GetTalkLine().ToString(), TalkLineIndex + 1, TalkLines.Num());
        for (const FReflectionsTalkOption& O : TalkOptions) Out += FString::Printf(TEXT("  > %s [%s]\n"), *O.Label.ToString(), *O.Action);
    }
    return Out;
}

bool UReflectionsQuestWorldSubsystem::SimulateKey(const FString& KeyName)
{
    const FKey Key(*KeyName);
    if (!Key.IsValid() || !FSlateApplication::IsInitialized()) return false;
    FSlateApplication& Slate = FSlateApplication::Get();
    const FKeyEvent Event(Key, FModifierKeysState(), 0, false, 0, 0);
    const bool bHandled = Slate.ProcessKeyDownEvent(Event);
    Slate.ProcessKeyUpEvent(Event);
    return bHandled;
}

#if !UE_BUILD_SHIPPING
static FAutoConsoleCommandWithWorld GQuestUiCmd(TEXT("Quest.Ui"), TEXT("Print what the quest HUD, journal and talk card show."),
    FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
    {
        if (const UReflectionsQuestWorldSubsystem* Q = UReflectionsQuestWorldSubsystem::Get(World)) UE_LOG(LogReflectionsQuestWorld, Display, TEXT("%s"), *Q->DescribeUi());
    }));

static FAutoConsoleCommandWithWorld GQuestJournalCmd(TEXT("Quest.Journal"), TEXT("Open or close the journal."),
    FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
    {
        if (UReflectionsQuestWorldSubsystem* Q = UReflectionsQuestWorldSubsystem::Get(World)) { if (Q->IsJournalOpen()) Q->CloseJournal(); else Q->OpenJournal(); }
    }));

static FAutoConsoleCommandWithWorldAndArgs GQuestTalkCmd(TEXT("Quest.Talk"), TEXT("Quest.Talk <PersonId>: open the talk card with a person (teleports nothing)."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        UReflectionsQuestWorldSubsystem* Q = UReflectionsQuestWorldSubsystem::Get(World);
        if (!Q || Args.Num() < 1) return;
        if (AActor* A = Q->FindPersonActor(FName(*Args[0]))) Q->OpenTalk(A, false);
    }));

static FAutoConsoleCommandWithWorldAndArgs GQuestOptionCmd(TEXT("Quest.TalkOption"), TEXT("Quest.TalkOption <Index>: press a talk card button (-1: next line)."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        UReflectionsQuestWorldSubsystem* Q = UReflectionsQuestWorldSubsystem::Get(World);
        if (!Q || Args.Num() < 1) return;
        const int32 Index = FCString::Atoi(*Args[0]);
        if (Index < 0) Q->AdvanceTalk(); else Q->ChooseTalkOption(Index);
    }));
#endif

#undef LOCTEXT_NAMESPACE
