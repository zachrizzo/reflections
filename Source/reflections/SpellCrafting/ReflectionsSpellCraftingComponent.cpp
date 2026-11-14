#include "SpellCrafting/ReflectionsSpellCraftingComponent.h"

#include "SpellCrafting/ReflectionsCraftedSpell.h"
#include "SpellCrafting/ReflectionsCraftedSpellSubsystem.h"
#include "SpellCrafting/ReflectionsSpellCraftingLibrary.h"
#include "SpellCrafting/ReflectionsSpellCraftingSave.h"
#include "SpellCrafting/ReflectionsSpellCraftingScreen.h"
#include "SpellCrafting/ReflectionsSpellRecipeRelay.h"
#include "Hero/ReflectionsHeroAnimInstance.h"
#include "Hero/ReflectionsSampleSpellDriver.h"
#include "Hero/ReflectionsSpellAim.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequenceBase.h"
#include "Blueprint/UserWidget.h"
#include "Components/ChildActorComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

#include <type_traits>

/**
 * Bridge to the spell core. The crafting system asks UReflectionsSampleSpellDriver for three things: TrySpendMana,
 * CastExternal and PrimaryCastOverride. They are detected at compile time, so this file builds against the
 * driver whether or not they exist yet, and picks them up as soon as they do. Without them, crafted spells
 * still cast (own input capture and gesture playback, no mana cost) and the screen says so.
 */
namespace CraftingBridge
{
    template <typename T> concept CHasTrySpendMana = requires(T* Driver, float Amount) { Driver->TrySpendMana(Amount); };
    template <typename T> concept CHasPrimaryOverride = requires(T* Driver) { Driver->PrimaryCastOverride = TFunction<bool()>(); };
    template <typename T> concept CHasCastExternal = requires { &T::CastExternal; };

    template <typename F> struct TFirstArg;
    template <typename C, typename R, typename A> struct TFirstArg<R (C::*)(A)> { using Type = std::remove_cvref_t<A>; };
    template <typename C, typename R, typename A> struct TFirstArg<R (C::*)(A) const> { using Type = std::remove_cvref_t<A>; };

    template <typename T>
    bool SpendMana(T* Driver, float Cost, bool& bOutSupported)
    {
        if constexpr (CHasTrySpendMana<T>)
        {
            bOutSupported = true;
            return Driver->TrySpendMana(Cost);
        }
        else
        {
            bOutSupported = false;
            return true;
        }
    }

    template <typename T>
    bool InstallPrimaryOverride(T* Driver, TFunction<bool()> Override)
    {
        if constexpr (CHasPrimaryOverride<T>)
        {
            Driver->PrimaryCastOverride = MoveTemp(Override);
            return true;
        }
        else
        {
            return false;
        }
    }

    template <typename T>
    void ClearPrimaryOverride(T* Driver)
    {
        if constexpr (CHasPrimaryOverride<T>) Driver->PrimaryCastOverride = nullptr;
    }

    template <typename T>
    constexpr bool SupportsExternalCast() { return CHasCastExternal<T>; }

    template <typename T> concept CHasSelectionEvent = requires(T* Driver) { Driver->OnSelectedSpellChanged; };

    template <typename T, typename TComponent>
    void BindSelectionEvent(T* Driver, TComponent* Component)
    {
        if constexpr (CHasSelectionEvent<T>)
        {
            Driver->OnSelectedSpellChanged.AddUniqueDynamic(Component, &TComponent::OnCatalogSpellChanged);
        }
    }

    template <typename T>
    bool CastExternal(T* Driver, UAnimSequenceBase* Animation, float ReleaseTime, FName Socket, EHeroSpell AimProxy, float ManaCost, float Cooldown,
        TFunction<void(const FTransform&, const FVector&, AActor*)> OnRelease)
    {
        if constexpr (CHasCastExternal<T>)
        {
            using FCast = typename TFirstArg<decltype(&T::CastExternal)>::Type;
            FCast Cast;
            Cast.Animation = Animation;
            Cast.ReleaseTime = ReleaseTime;
            Cast.Socket = Socket;
            Cast.AimProxy = AimProxy;
            Cast.ManaCost = ManaCost;
            Cast.Cooldown = Cooldown;
            Cast.OnRelease = MoveTemp(OnRelease);
            return Driver->CastExternal(Cast);
        }
        else
        {
            return false;
        }
    }
}

namespace
{
    const TCHAR* GestureFolder = TEXT("/Game/SpellCrafting/Gestures/");
    const TCHAR* CombatFolder = TEXT("/Game/Characters/Hero/Animation/CombatCasts/");

    /**
     * Fallback release seconds (hand-speed peak + 2 frames) and casting hand for every gesture a form can use.
     * A "Spell Release" notify on the clip, when present, wins over these numbers.
     */
    struct FGestureInfo { const TCHAR* Name; float Release; FName Socket; };
    const FGestureInfo GestureTable[] = {
        // Shared combat casts (Tools/SpellVFX/author_combat_casts.py).
        {TEXT("BoltRight"), 0.867f, TEXT("hand_r")},
        {TEXT("BoltLeft"), 0.50f, TEXT("hand_l")},
        {TEXT("HeavyPush"), 0.80f, NAME_None},
        {TEXT("Slam"), 1.00f, NAME_None},
        {TEXT("Sweep"), 0.733f, TEXT("hand_r")},
        {TEXT("HealRaise"), 0.433f, NAME_None},
        // Crafting gestures (Tools/SpellCrafting/author_cast_gestures.py).
        {TEXT("Conjure"), 0.667f, NAME_None},
        {TEXT("Lance"), 0.40f, TEXT("hand_r")},
        {TEXT("SkyCall"), 0.533f, TEXT("hand_r")},
        {TEXT("GroundPlant"), 0.667f, TEXT("hand_r")},
        {TEXT("Spiral"), 0.667f, NAME_None},
    };

    const FGestureInfo* FindGestureInfo(FName Name)
    {
        for (const FGestureInfo& Info : GestureTable) if (Name == Info.Name) return &Info;
        return nullptr;
    }

    float WindupFor(ECraftedSpellForm Form)
    {
        switch (Form)
        {
        case ECraftedSpellForm::Bolt: case ECraftedSpellForm::Ray: return 0.28f;
        case ECraftedSpellForm::Orb: return 0.36f;
        case ECraftedSpellForm::Nova: case ECraftedSpellForm::Wave: case ECraftedSpellForm::Rune: return 0.38f;
        default: return 0.44f;
        }
    }
}

UReflectionsSpellCraftingComponent::UReflectionsSpellCraftingComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickGroup = TG_PostPhysics;
}

void UReflectionsSpellCraftingComponent::BeginPlay()
{
    Super::BeginPlay();
    Driver = GetOwner()->FindComponentByClass<UReflectionsSampleSpellDriver>();
    CooldownUntil.Init(0.0, NumSlots);
    LoadSlots();
    if (Driver)
    {
        const bool bOverride = CraftingBridge::InstallPrimaryOverride(Driver.Get(), [WeakThis = TWeakObjectPtr<UReflectionsSpellCraftingComponent>(this)]()
        {
            return WeakThis.IsValid() && WeakThis->PrimaryOverride();
        });
        bCoreCastAvailable = bOverride && CraftingBridge::SupportsExternalCast<UReflectionsSampleSpellDriver>();
        CraftingBridge::BindSelectionEvent(Driver.Get(), this);
    }
    UE_LOG(LogTemp, Log, TEXT("Spell crafting: %d slots loaded; spell core cast %s."), Slots.Num(),
        bCoreCastAvailable ? TEXT("connected") : TEXT("not exposed yet, using the fallback cast"));
}

void UReflectionsSpellCraftingComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Driver) CraftingBridge::ClearPrimaryOverride(Driver.Get());
    if (InputController && CraftInput) InputController->PopInputComponent(CraftInput);
    if (InputController && CastCapture && bCapturePushed) InputController->PopInputComponent(CastCapture);
    if (Screen)
    {
        Screen->RemoveFromParent();
        Screen = nullptr;
    }
    if (UWorld* World = GetWorld()) World->GetTimerManager().ClearAllTimersForObject(this);
    Super::EndPlay(Reason);
}

// ------------------------------------------------------------------------------------------------ slots
void UReflectionsSpellCraftingComponent::ResolveAll()
{
    Resolved.SetNum(NumSlots);
    for (int32 i = 0; i < NumSlots; ++i) Resolved[i] = UReflectionsSpellCraftingLibrary::Resolve(Slots[i]);
}

FCraftedSpellRecipe UReflectionsSpellCraftingComponent::GetSlotRecipe(int32 Slot) const
{
    return Slots.IsValidIndex(Slot) ? Slots[Slot] : FCraftedSpellRecipe();
}

const FCraftedSpellResolved& UReflectionsSpellCraftingComponent::GetSlotSpell(int32 Slot) const
{
    static const FCraftedSpellResolved Empty;
    return Resolved.IsValidIndex(Slot) ? Resolved[Slot] : Empty;
}

void UReflectionsSpellCraftingComponent::SetSlotRecipe(int32 Slot, const FCraftedSpellRecipe& Recipe, bool bSave)
{
    if (!Slots.IsValidIndex(Slot)) return;
    Slots[Slot] = UReflectionsSpellCraftingLibrary::Sanitize(Recipe);
    Resolved[Slot] = UReflectionsSpellCraftingLibrary::Resolve(Slots[Slot]);
    if (bSave) SaveSlots();
    if (Slot == ActiveSlot) RefreshAimProxy();
    OnSlotsChanged.Broadcast();
}

void UReflectionsSpellCraftingComponent::SaveSlots()
{
    UReflectionsSpellCraftingSave* Save = Cast<UReflectionsSpellCraftingSave>(UGameplayStatics::CreateSaveGameObject(UReflectionsSpellCraftingSave::StaticClass()));
    if (!Save) return;
    Save->Slots = Slots;
    Save->ActiveSlot = ActiveSlot;
    if (!UGameplayStatics::SaveGameToSlot(Save, UReflectionsSpellCraftingSave::SlotName(), 0))
    {
        UE_LOG(LogTemp, Warning, TEXT("Spell crafting: could not write the save slot."));
    }
}

void UReflectionsSpellCraftingComponent::LoadSlots()
{
    Slots.Reset();
    int32 SavedActive = -1;
    if (UGameplayStatics::DoesSaveGameExist(UReflectionsSpellCraftingSave::SlotName(), 0))
    {
        if (const UReflectionsSpellCraftingSave* Save = Cast<UReflectionsSpellCraftingSave>(UGameplayStatics::LoadGameFromSlot(UReflectionsSpellCraftingSave::SlotName(), 0)))
        {
            for (const FCraftedSpellRecipe& Recipe : Save->Slots) Slots.Add(UReflectionsSpellCraftingLibrary::Sanitize(Recipe));
            SavedActive = Save->ActiveSlot;
        }
    }
    // Empty or new slots start as the starter spells, so there is always something to cast and to edit.
    for (int32 i = Slots.Num(); i < NumSlots; ++i) Slots.Add(UReflectionsSpellCraftingLibrary::Preset(i));
    Slots.SetNum(NumSlots);
    ResolveAll();
    // Every session starts on the catalog spells; a crafted slot is chosen explicitly (5-8, D-pad Up, Equip).
    (void)SavedActive;
    ActiveSlot = -1;
    OnSlotsChanged.Broadcast();
}

void UReflectionsSpellCraftingComponent::SelectCraftedSlot(int32 Slot)
{
    const int32 Previous = ActiveSlot;
    ActiveSlot = Slots.IsValidIndex(Slot) ? Slot : -1;
    if (Driver) CatalogAtSelect = Driver->GetSelectedSpell();
    RefreshAimProxy();
    if (ActiveSlot >= 0) SetFeedback(GetSlotSpell(ActiveSlot).Name, 1.2f);
    UpdateCastCapture();
    if (Previous != ActiveSlot)
    {
        SaveSlots();
        OnSlotsChanged.Broadcast();
    }
}

void UReflectionsSpellCraftingComponent::RefreshAimProxy()
{
    if (!Driver) return;
    if (UReflectionsSpellAimComponent* Aim = Driver->GetAim())
    {
        Aim->SetSelectedSpell(ActiveSlot >= 0 ? UReflectionsSpellCraftingLibrary::AimProxy(Slots[ActiveSlot].Form) : Driver->GetSelectedSpell());
    }
}

void UReflectionsSpellCraftingComponent::SelectSlot1() { SelectCraftedSlot(ActiveSlot == 0 ? -1 : 0); }
void UReflectionsSpellCraftingComponent::SelectSlot2() { SelectCraftedSlot(ActiveSlot == 1 ? -1 : 1); }
void UReflectionsSpellCraftingComponent::SelectSlot3() { SelectCraftedSlot(ActiveSlot == 2 ? -1 : 2); }
void UReflectionsSpellCraftingComponent::SelectSlot4() { SelectCraftedSlot(ActiveSlot == 3 ? -1 : 3); }
void UReflectionsSpellCraftingComponent::CycleSlot() { SelectCraftedSlot(ActiveSlot + 1 >= NumSlots ? -1 : ActiveSlot + 1); }

float UReflectionsSpellCraftingComponent::GetCooldownRemaining(int32 Slot) const
{
    const UWorld* World = GetWorld();
    return World && CooldownUntil.IsValidIndex(Slot) ? FMath::Max(0.0f, float(CooldownUntil[Slot] - World->GetTimeSeconds())) : 0.0f;
}

void UReflectionsSpellCraftingComponent::SetFeedback(const FString& Text, float Seconds)
{
    Feedback = Text;
    FeedbackUntil = GetWorld() ? GetWorld()->GetTimeSeconds() + Seconds : 0.0;
}

FString UReflectionsSpellCraftingComponent::GetFeedback() const
{
    const UWorld* World = GetWorld();
    return World && World->GetTimeSeconds() < FeedbackUntil ? Feedback : FString();
}

// ------------------------------------------------------------------------------------------------ input
void UReflectionsSpellCraftingComponent::BindControls()
{
    if (bBound) return;
    APawn* Pawn = Cast<APawn>(GetOwner());
    APlayerController* PC = Pawn && Pawn->IsLocallyControlled() ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
    if (!PC) return;
    bBound = true;
    InputController = PC;
    CraftInput = NewObject<UInputComponent>(PC, TEXT("SpellCraftingInput"));
    CraftInput->Priority = 5;
    CraftInput->BindKey(EKeys::K, IE_Pressed, this, &UReflectionsSpellCraftingComponent::ToggleCraftingScreen);
    CraftInput->BindKey(EKeys::Gamepad_Special_Left, IE_Pressed, this, &UReflectionsSpellCraftingComponent::ToggleCraftingScreen);
    CraftInput->BindKey(EKeys::Five, IE_Pressed, this, &UReflectionsSpellCraftingComponent::SelectSlot1);
    CraftInput->BindKey(EKeys::Six, IE_Pressed, this, &UReflectionsSpellCraftingComponent::SelectSlot2);
    CraftInput->BindKey(EKeys::Seven, IE_Pressed, this, &UReflectionsSpellCraftingComponent::SelectSlot3);
    CraftInput->BindKey(EKeys::Eight, IE_Pressed, this, &UReflectionsSpellCraftingComponent::SelectSlot4);
    {
        // D-pad Up is free in the sandbox mapping (Down is Interact, Left/Right page the catalog).
        FInputKeyBinding& Cycle = CraftInput->BindKey(EKeys::Gamepad_DPad_Up, IE_Pressed, this, &UReflectionsSpellCraftingComponent::CycleSlot);
        Cycle.bConsumeInput = false;
    }
    // Picking a catalog spell (1-4, Tab, RB/LB, page keys) returns to the catalog; the driver still receives those keys.
    for (const FKey& Key : {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Tab, EKeys::LeftBracket, EKeys::RightBracket,
        EKeys::Gamepad_LeftShoulder, EKeys::Gamepad_RightShoulder, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_DPad_Right})
    {
        FInputKeyBinding Binding(FInputChord(Key), IE_Pressed);
        Binding.bConsumeInput = false;
        Binding.KeyDelegate.GetDelegateForManualSet().BindWeakLambda(this, [this]() { if (ActiveSlot >= 0) SelectCraftedSlot(-1); });
        CraftInput->KeyBindings.Emplace(MoveTemp(Binding));
    }
    PC->PushInputComponent(CraftInput);

    // Fallback only (the spell core has no PrimaryCastOverride yet): while a crafted slot is active this component
    // sits above the driver's input and takes the primary cast.
    CastCapture = NewObject<UInputComponent>(PC, TEXT("SpellCraftingCastCapture"));
    CastCapture->Priority = 6;
    for (const FKey& Key : {EKeys::LeftMouseButton, EKeys::Gamepad_RightTrigger})
    {
        CastCapture->BindKey(Key, IE_Pressed, this, &UReflectionsSpellCraftingComponent::PrimaryPressed);
        CastCapture->BindKey(Key, IE_Released, this, &UReflectionsSpellCraftingComponent::PrimaryReleased);
    }
    UpdateCastCapture();
}

void UReflectionsSpellCraftingComponent::UpdateCastCapture()
{
    if (!InputController || !CastCapture) return;
    const bool bWant = !bCoreCastAvailable && ActiveSlot >= 0;
    if (bWant == bCapturePushed) return;
    bCapturePushed = bWant;
    if (bWant) InputController->PushInputComponent(CastCapture);
    else InputController->PopInputComponent(CastCapture);
}

void UReflectionsSpellCraftingComponent::OnCatalogSpellChanged(EHeroSpell Spell)
{
    if (ActiveSlot >= 0) SelectCraftedSlot(-1);
}

bool UReflectionsSpellCraftingComponent::CatalogSelectionMoved() const
{
    return Driver && ActiveSlot >= 0 && Driver->GetSelectedSpell() != CatalogAtSelect;
}

bool UReflectionsSpellCraftingComponent::PrimaryOverride()
{
    if (CatalogSelectionMoved()) SelectCraftedSlot(-1);
    if (ActiveSlot < 0 || IsCraftingScreenOpen()) return false;
    CastActive();
    // Handled either way: with a crafted slot active the catalog spell must not fire.
    return true;
}

void UReflectionsSpellCraftingComponent::PrimaryPressed()
{
    if (ActiveSlot < 0 || IsCraftingScreenOpen()) return;
    if (InputController && InputController->bShowMouseCursor) return;
    bPrimaryHeld = true;
    CastActive();
}

void UReflectionsSpellCraftingComponent::PrimaryReleased()
{
    bPrimaryHeld = false;
}

// ------------------------------------------------------------------------------------------------ screen
void UReflectionsSpellCraftingComponent::OpenCraftingScreen()
{
    if (!Screen || !InputController) return;
    Screen->Open(this);
}

void UReflectionsSpellCraftingComponent::CloseCraftingScreen()
{
    if (Screen) Screen->Close();
}

void UReflectionsSpellCraftingComponent::ToggleCraftingScreen()
{
    if (IsCraftingScreenOpen()) CloseCraftingScreen();
    else OpenCraftingScreen();
}

bool UReflectionsSpellCraftingComponent::IsCraftingScreenOpen() const
{
    return Screen && Screen->IsOpen();
}

void UReflectionsSpellCraftingComponent::DescribeSpell(const FString& Text, TFunction<void(bool, const FCraftedSpellRecipe&, const FString&)> Done)
{
    auto Offline = [Text, Done]()
    {
        FCraftedSpellRecipe Recipe;
        const bool bOk = UReflectionsSpellCraftingLibrary::ParseDescription(Text, Recipe);
        Done(bOk, Recipe, bOk ? TEXT("Interpreted offline.") : TEXT("No spell words recognised. Try: \"a slow orb of lightning that pulls enemies in\"."));
    };
    if (!UReflectionsSpellRecipeRelay::IsConfigured())
    {
        Offline();
        return;
    }
    if (!Relay) Relay = NewObject<UReflectionsSpellRecipeRelay>(this);
    Relay->Request(Text, [Offline, Done](bool bOk, const FCraftedSpellRecipe& Recipe, const FString& Message)
    {
        if (bOk) Done(true, Recipe, Message);
        else Offline();
    });
}

// ------------------------------------------------------------------------------------------------ casting
void UReflectionsSpellCraftingComponent::FindBody()
{
    if (Body) return;
    TInlineComponentArray<UChildActorComponent*> Children(GetOwner());
    for (UChildActorComponent* Child : Children)
    {
        if (Child->GetFName() != TEXT("HeroVisual") || !Child->GetChildActor()) continue;
        TInlineComponentArray<USkeletalMeshComponent*> Meshes(Child->GetChildActor());
        for (USkeletalMeshComponent* Mesh : Meshes)
        {
            if (Mesh->GetFName() == TEXT("Body")) { Body = Mesh; return; }
        }
    }
}

FVector UReflectionsSpellCraftingComponent::HandLocation(FName Socket) const
{
    if (!Body) return GetOwner()->GetActorLocation() + GetOwner()->GetActorForwardVector() * 50.0f + FVector(0, 0, 40.0f);
    if (Socket.IsNone()) return (Body->GetSocketLocation(TEXT("hand_l")) + Body->GetSocketLocation(TEXT("hand_r"))) * 0.5f;
    return Body->GetSocketLocation(Socket);
}

UReflectionsSpellCraftingComponent::FGesture UReflectionsSpellCraftingComponent::ResolveGesture(ECraftedSpellForm Form)
{
    TArray<FName> Names;
    UReflectionsSpellCraftingLibrary::GestureCandidates(Form, CastCount, Names);
    for (const FName& Name : Names)
    {
        UAnimSequenceBase* Clip = nullptr;
        if (const TObjectPtr<UAnimSequenceBase>* Cached = GestureCache.Find(Name))
        {
            Clip = *Cached;
        }
        else
        {
            const FString N = Name.ToString();
            Clip = LoadObject<UAnimSequenceBase>(nullptr, *FString::Printf(TEXT("%sAS_Hero_Gesture%s.AS_Hero_Gesture%s"), GestureFolder, *N, *N), nullptr, LOAD_NoWarn | LOAD_Quiet);
            if (!Clip) Clip = LoadObject<UAnimSequenceBase>(nullptr, *FString::Printf(TEXT("%sAS_Hero_Combat%s.AS_Hero_Combat%s"), CombatFolder, *N, *N), nullptr, LOAD_NoWarn | LOAD_Quiet);
            GestureCache.Add(Name, Clip);
        }
        if (!Clip) continue;
        FGesture Gesture;
        Gesture.Animation = Clip;
        const FGestureInfo* Info = FindGestureInfo(Name);
        Gesture.ReleaseTime = FMath::Min(Info ? Info->Release : 0.5f, Clip->GetPlayLength() * 0.8f);
        for (const FAnimNotifyEvent& Event : Clip->Notifies)
        {
            if (Event.Notify && Event.Notify->IsA<UReflectionsSpellReleaseNotify>())
            {
                Gesture.ReleaseTime = Event.GetTriggerTime();
                break;
            }
        }
        Gesture.Socket = Info ? Info->Socket : NAME_None;
        return Gesture;
    }
    FGesture None;
    None.Socket = Form == ECraftedSpellForm::Bolt || Form == ECraftedSpellForm::Ray ? FName(TEXT("hand_r")) : NAME_None;
    return None;
}

bool UReflectionsSpellCraftingComponent::SpendMana(float Cost)
{
    bool bSupported = false;
    const bool bOk = Driver ? CraftingBridge::SpendMana(Driver.Get(), Cost, bSupported) : true;
    return bOk;
}

bool UReflectionsSpellCraftingComponent::CastActive()
{
    if (!Resolved.IsValidIndex(ActiveSlot)) return false;
    return CastResolved(Resolved[ActiveSlot], ActiveSlot);
}

bool UReflectionsSpellCraftingComponent::CastResolved(const FCraftedSpellResolved& Spell, int32 SlotForCooldown)
{
    UWorld* World = GetWorld();
    if (!World || (Driver && Driver->IsDefeated())) return false;
    FindBody();
    if (GetCooldownRemaining(SlotForCooldown) > 0.0f)
    {
        SetFeedback(FString::Printf(TEXT("%s recharging (%.1f s)"), *Spell.Name, GetCooldownRemaining(SlotForCooldown)), 0.8f);
        return false;
    }
    const FGesture Gesture = ResolveGesture(Spell.Recipe.Form);
    const EHeroSpell AimProxy = UReflectionsSpellCraftingLibrary::AimProxy(Spell.Recipe.Form);

    if (bCoreCastAvailable && Driver)
    {
        TWeakObjectPtr<UReflectionsSpellCraftingComponent> WeakThis(this);
        const FCraftedSpellResolved Copy = Spell;
        const bool bStarted = CraftingBridge::CastExternal(Driver.Get(), Gesture.Animation, Gesture.ReleaseTime, Gesture.Socket, AimProxy,
            Spell.ManaCost, 0.0f, [WeakThis, Copy](const FTransform& Origin, const FVector& Target, AActor* AimTarget)
            {
                if (WeakThis.IsValid()) WeakThis->ReleaseNow(Copy, Origin, Target, AimTarget);
            });
        if (bStarted)
        {
            ++CastCount;
            if (CooldownUntil.IsValidIndex(SlotForCooldown)) CooldownUntil[SlotForCooldown] = World->GetTimeSeconds() + Spell.Cooldown;
        }
        return bStarted;
    }

    // Fallback cast: own gesture playback. Never while one is pending, and a short global recovery between casts.
    if (bPendingRelease || World->GetTimeSeconds() - LastCastTime < 0.25) return false;
    if (!SpendMana(Spell.ManaCost))
    {
        SetFeedback(TEXT("Not enough mana"), 0.8f);
        return false;
    }
    ++CastCount;
    LastCastTime = World->GetTimeSeconds();
    if (CooldownUntil.IsValidIndex(SlotForCooldown)) CooldownUntil[SlotForCooldown] = World->GetTimeSeconds() + Spell.Cooldown;
    PendingSpell = Spell;
    PendingGesture = Gesture;
    const UReflectionsSpellAimComponent* Aim = Driver ? Driver->GetAim() : nullptr;
    UAnimInstance* Anim = Body ? Body->GetAnimInstance() : nullptr;
    // While aiming the driver owns the arm pose, so the fallback releases straight from the hand.
    if (Gesture.Animation && Anim && !(Aim && Aim->IsAiming()))
    {
        const float Windup = WindupFor(Spell.Recipe.Form);
        float Rate = 1.0f;
        float StartAt = 0.0f;
        if (Gesture.ReleaseTime > Windup)
        {
            Rate = FMath::Clamp(Gesture.ReleaseTime / Windup, 1.0f, 1.9f);
            StartAt = FMath::Max(0.0f, Gesture.ReleaseTime - Windup * Rate);
        }
        FallbackMontage = Anim->PlaySlotAnimationAsDynamicMontage(Gesture.Animation, UReflectionsHeroAnimInstance::SpellSlot, 0.08f, 0.22f, Rate, 1, -1.0f, StartAt);
        if (FallbackMontage)
        {
            bPendingRelease = true;
            PendingStarted = World->GetTimeSeconds();
            return true;
        }
    }
    AActor* AimTarget = nullptr;
    const FVector Origin = HandLocation(Gesture.Socket);
    const FVector Target = Aim ? Aim->ResolveTarget(AimProxy, Origin, AimTarget) : Origin + GetOwner()->GetActorForwardVector() * Spell.Range;
    ReleaseNow(Spell, FTransform((Target - Origin).Rotation(), Origin), Target, AimTarget);
    return true;
}

void UReflectionsSpellCraftingComponent::ReleaseNow(const FCraftedSpellResolved& Spell, const FTransform& Origin, const FVector& Target, AActor* AimTarget)
{
    UWorld* World = GetWorld();
    AActor* Owner = GetOwner();
    if (!World || !Owner) return;
    AReflectionsCraftedSpell::CastSpell(World, Spell, Owner, Origin.GetLocation(), Target, AimTarget, 1.0f);
    if (UReflectionsCraftedSpellSubsystem* S = UReflectionsCraftedSpellSubsystem::Get(this))
    {
        FCraftedSpellLook Flash = Spell.Look;
        Flash.Size = FMath::Min(Flash.Size, 40.0f);
        S->SpawnFx(ECraftedFx::Burst, Flash, Origin.GetLocation(), Origin.Rotator(), nullptr, 0.25f);
        S->PlayCastCue(Spell, Origin.GetLocation());
    }
    if (Driver)
    {
        if (UReflectionsSpellAimComponent* Aim = Driver->GetAim()) Aim->NotifyCast();
    }
    if (InputController)
    {
        if (UReflectionsSpellCameraModifier* Modifier = UReflectionsSpellCameraModifier::Get(InputController)) Modifier->AddKick(Spell.IsField() ? 0.25f : 0.35f);
    }
    // Echo: the spell recasts itself from the same place, weaker each time.
    for (int32 i = 1; i <= Spell.EchoCount; ++i)
    {
        FTimerHandle Handle;
        const FVector From = Origin.GetLocation();
        TWeakObjectPtr<AActor> WeakTarget(AimTarget);
        const float EchoScale = FMath::Pow(0.6f, float(i));
        World->GetTimerManager().SetTimer(Handle, FTimerDelegate::CreateWeakLambda(this, [this, Spell, From, Target, WeakTarget, EchoScale]()
        {
            if (UWorld* W = GetWorld()) AReflectionsCraftedSpell::CastSpell(W, Spell, GetOwner(), From, Target, WeakTarget.Get(), EchoScale);
        }), Spell.EchoDelay * i, false);
    }
}

void UReflectionsSpellCraftingComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaTime, TickType, TickFunction);
    BindControls();
    if (!Screen && InputController)
    {
        Screen = CreateWidget<UReflectionsSpellCraftingScreen>(InputController.Get(), UReflectionsSpellCraftingScreen::StaticClass());
        if (Screen)
        {
            Screen->AddToViewport(20);
            Screen->Bind(this);
        }
    }
    // A catalog pick since the crafted slot was chosen hands the cast button back to the catalog.
    if (CatalogSelectionMoved()) SelectCraftedSlot(-1);
    // Keep the aim preview on the crafted spell's shape; the driver resets it when its own selection changes.
    if (ActiveSlot >= 0) RefreshAimProxy();

    if (bPendingRelease)
    {
        UAnimInstance* Anim = Body ? Body->GetAnimInstance() : nullptr;
        const bool bPlaying = Anim && FallbackMontage && Anim->Montage_IsPlaying(FallbackMontage);
        const float Position = bPlaying ? Anim->Montage_GetPosition(FallbackMontage) : TNumericLimits<float>::Max();
        if (Position >= PendingGesture.ReleaseTime || GetWorld()->GetTimeSeconds() - PendingStarted > 1.2)
        {
            bPendingRelease = false;
            const UReflectionsSpellAimComponent* Aim = Driver ? Driver->GetAim() : nullptr;
            AActor* AimTarget = nullptr;
            const FVector Origin = HandLocation(PendingGesture.Socket);
            const EHeroSpell AimProxy = UReflectionsSpellCraftingLibrary::AimProxy(PendingSpell.Recipe.Form);
            const FVector Target = Aim ? Aim->ResolveTarget(AimProxy, Origin, AimTarget) : Origin + GetOwner()->GetActorForwardVector() * PendingSpell.Range;
            ReleaseNow(PendingSpell, FTransform((Target - Origin).Rotation(), Origin), Target, AimTarget);
            if (bPlaying)
            {
                // Hold the follow-through briefly, then hand the arms back to locomotion.
                FTimerHandle Handle;
                TWeakObjectPtr<UAnimMontage> Montage(FallbackMontage.Get());
                GetWorld()->GetTimerManager().SetTimer(Handle, FTimerDelegate::CreateWeakLambda(this, [this, Montage]()
                {
                    if (UAnimInstance* A = Body ? Body->GetAnimInstance() : nullptr) if (Montage.IsValid()) A->Montage_Stop(0.25f, Montage.Get());
                }), 0.3f, false);
            }
        }
    }
    // Held trigger repeats cheap bolts; heavier forms need a fresh press.
    if (!bCoreCastAvailable && bPrimaryHeld && ActiveSlot >= 0 && !bPendingRelease)
    {
        const ECraftedSpellForm Form = Slots[ActiveSlot].Form;
        if ((Form == ECraftedSpellForm::Bolt || Form == ECraftedSpellForm::Ray) && GetWorld()->GetTimeSeconds() - LastCastTime > 0.45) CastActive();
    }
}
