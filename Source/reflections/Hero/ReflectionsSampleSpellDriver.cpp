#include "Hero/ReflectionsSampleSpellDriver.h"
#include "HAL/IConsoleManager.h"
#include "Hero/ReflectionsHeroAnimInstance.h"
#include "Hero/ReflectionsSpellAim.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Hero/ReflectionsSpellCatalog.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimTypes.h"
#include "Components/ChildActorComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputTriggers.h"
#include "Components/CapsuleComponent.h"

namespace
{
    const TCHAR* CombatFolder = TEXT("/Game/Characters/Hero/Animation/CombatCasts/");
    TAutoConsoleVariable<int32> CVarAimHoldV1(TEXT("Spell.AimHoldV1"), 0,
        TEXT("Dev A/B: 1 = aim with the original hold pose (AS_Hero_CombatAimHold_V1) instead of the current one. Read when play starts."));

    /**
     * Short Kimodo combat casts (Tools/SpellVFX/author_combat_casts.py). Release seconds are the sampled
     * hand-speed peak plus two frames, from Intermediate/CombatCasts/bake-report.json.
     */
    struct FCombatCast
    {
        const TCHAR* Name;
        const TCHAR* Socket;  // nullptr releases between both hands. Plain strings: no FName is built during static init.
        float Release;
    };
    const FCombatCast BoltRight{TEXT("BoltRight"), TEXT("hand_r"), 0.867f};
    const FCombatCast BoltLeft{TEXT("BoltLeft"), TEXT("hand_l"), 0.5f};
    const FCombatCast HeavyPush{TEXT("HeavyPush"), nullptr, 0.8f};
    const FCombatCast Slam{TEXT("Slam"), nullptr, 1.0f};
    const FCombatCast Sweep{TEXT("Sweep"), TEXT("hand_r"), 0.733f};
    const FCombatCast HealRaise{TEXT("HealRaise"), nullptr, 0.433f};
    const FCombatCast AimHold{TEXT("AimHold"), TEXT("hand_r"), 1.4f};

    const FCombatCast* CombatCastFor(EHeroSpell Spell, int32 Count)
    {
        // Bolts alternate hands so a held trigger reads as a rhythm rather than one arm on repeat.
        const bool bOdd = (Count & 1) != 0;
        switch (Spell)
        {
        case EHeroSpell::Fire:
        case EHeroSpell::ArcaneBolt:
        case EHeroSpell::LightningBolt:
        case EHeroSpell::ChainLightning: return bOdd ? &BoltLeft : &BoltRight;
        case EHeroSpell::Water:
        case EHeroSpell::IceShard: return bOdd ? &BoltRight : &BoltLeft;
        case EHeroSpell::Firestorm:
        case EHeroSpell::WaterOrb:
        case EHeroSpell::StoneShard:
        case EHeroSpell::ForcePush: return &HeavyPush;
        case EHeroSpell::FlameBurst:
        case EHeroSpell::FrostNova:
        case EHeroSpell::ThunderWave:
        case EHeroSpell::EarthShock: return &Slam;
        case EHeroSpell::TidalSurge: return &Sweep;
        case EHeroSpell::Healing:
        case EHeroSpell::GreaterHeal:
        case EHeroSpell::HealingPulse: return &HealRaise;
        default: return nullptr;
        }
    }

    /** Release time authored as a Spell Release notify, or a negative value when the clip has none. */
    float FindReleaseNotify(const UAnimSequenceBase* Clip)
    {
        for (const FAnimNotifyEvent& Event : Clip->Notifies)
        {
            if (Event.Notify && Event.Notify->IsA<UReflectionsSpellReleaseNotify>())
            {
                return Event.GetTriggerTime();
            }
        }
        return -1.0f;
    }

    /** Real seconds from press to release for each kind of spell. */
    float WindupFor(const FReflectionsSpellSpec& Spec, float Base)
    {
        switch (Spec.Delivery)
        {
        case EReflectionsSpellDelivery::Projectile: return Spec.Radius > 0.0f ? Base + 0.08f : Base;
        case EReflectionsSpellDelivery::Area: return Base + 0.1f;
        case EReflectionsSpellDelivery::Heal: return Base + 0.16f;
        case EReflectionsSpellDelivery::Ward: return Base + 0.12f;
        default: return 0.0f;
        }
    }
}

UReflectionsSampleSpellDriver::UReflectionsSampleSpellDriver()
{
    PrimaryComponentTick.bCanEverTick = true;
}

void UReflectionsSampleSpellDriver::BeginPlay()
{
    Super::BeginPlay();
    UClass* DefaultsClass = LoadClass<AReflectionsHeroCharacter>(nullptr, TEXT("/Game/Characters/Hero/Gameplay/BP_HeroPlayer.BP_HeroPlayer_C"));
    SpellDefaults = DefaultsClass ? DefaultsClass->GetDefaultObject<AReflectionsHeroCharacter>() : nullptr;
    TInlineComponentArray<UChildActorComponent*> Children(GetOwner());
    for (UChildActorComponent* Child : Children)
    {
        if (Child->GetFName() == TEXT("HeroVisual"))
        {
            Visual = Child;
            VisualBase = Child->GetRelativeLocation();
            if (AActor* VisualActor = Child->GetChildActor())
            {
                TInlineComponentArray<USkeletalMeshComponent*> Meshes(VisualActor);
                for (USkeletalMeshComponent* Mesh : Meshes)
                    if (Mesh->GetFName() == TEXT("Body")) { Body = Mesh; break; }
            }
            break;
        }
    }
    if (Body) RetargetClass = Body->GetAnimClass();
    Preview = NewObject<UStaticMeshComponent>(GetOwner(), TEXT("SampleSpellPreview"));
    Preview->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Preview->SetCastShadow(false);
    Preview->RegisterComponent();
    Preview->SetVisibility(false);

    Aim = GetOwner()->FindComponentByClass<UReflectionsSpellAimComponent>();
    if (!Aim)
    {
        Aim = NewObject<UReflectionsSpellAimComponent>(GetOwner(), TEXT("SpellAim"));
        Aim->RegisterComponent();
    }
    Aim->SetSelectedSpell(SelectedSpell);
    LoadCombatClips();
    Mana = MaxMana;
    // A checkpoint set before BeginPlay (game flow restoring a save) wins over the placement transform.
    if (!bRespawnTransformSet) SpawnTransform = GetOwner()->GetActorTransform();
    if (UReflectionsHealthComponent* Health = GetOwner()->FindComponentByClass<UReflectionsHealthComponent>())
    {
        Health->OnDeath.AddUniqueDynamic(this, &UReflectionsSampleSpellDriver::OnOwnerDied);
        Health->OnHealthChanged.AddUniqueDynamic(this, &UReflectionsSampleSpellDriver::OnOwnerHealthChanged);
        LastSeenHealth = Health->Health;
    }
}

void UReflectionsSampleSpellDriver::OnOwnerHealthChanged(float Health, float MaxHealth, AActor* Source)
{
    // Any loss (a hit, a fall, the Tarnish) restarts the out-of-combat timer; heals and loads do not.
    if (LastSeenHealth >= 0.0f && Health < LastSeenHealth - KINDA_SMALL_NUMBER)
    {
        LastDamageTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
        PendingRegen = 0.0f;
    }
    LastSeenHealth = Health;
}

float UReflectionsSampleSpellDriver::GetSpellManaCost(EHeroSpell Spell) const
{
    return ReflectionsSpellCatalog::IsValid(Spell) ? ReflectionsSpellCatalog::Get(Spell).ManaCost : 0.0f;
}

float UReflectionsSampleSpellDriver::GetSpellCooldownRemaining(EHeroSpell Spell) const
{
    const UWorld* World = GetWorld();
    const double* Until = CooldownUntil.Find(Spell);
    return World && Until ? FMath::Max(0.0f, static_cast<float>(*Until - World->GetTimeSeconds())) : 0.0f;
}

float UReflectionsSampleSpellDriver::GetRespawnTimeRemaining() const
{
    const UWorld* World = GetWorld();
    return bDefeated && World ? FMath::Max(0.0f, static_cast<float>(RespawnAt - World->GetTimeSeconds())) : 0.0f;
}

FString UReflectionsSampleSpellDriver::GetCastFeedback() const
{
    const UWorld* World = GetWorld();
    return World && World->GetTimeSeconds() < FeedbackUntil ? Feedback : FString();
}

void UReflectionsSampleSpellDriver::SetFeedback(const FString& Text)
{
    Feedback = Text;
    FeedbackUntil = GetWorld() ? GetWorld()->GetTimeSeconds() + 1.2 : 0.0;
}

bool UReflectionsSampleSpellDriver::CanAfford(EHeroSpell Spell)
{
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    if (const float Remaining = GetSpellCooldownRemaining(Spell); Remaining > 0.0f)
    {
        SetFeedback(FString::Printf(TEXT("%s recharging (%.1fs)"), Spec.Name, Remaining));
        return false;
    }
    if (Mana < Spec.ManaCost)
    {
        SetFeedback(FString::Printf(TEXT("Not enough mana for %s"), Spec.Name));
        return false;
    }
    return true;
}

void UReflectionsSampleSpellDriver::OnOwnerDied(AActor* Source)
{
    if (bDefeated) return;
    bDefeated = true;
    bPrimaryHeld = false;
    RespawnAt = GetWorld() ? GetWorld()->GetTimeSeconds() + RespawnDelay : 0.0;
    if (UAnimInstance* Anim = Body ? Body->GetAnimInstance() : nullptr)
    {
        Anim->Montage_Stop(0.2f, nullptr);
    }
    ActiveMontage = nullptr;
    AimMontage = nullptr;
    if (ACharacter* Character = Cast<ACharacter>(GetOwner()))
    {
        Character->GetCharacterMovement()->DisableMovement();
    }
}

void UReflectionsSampleSpellDriver::Respawn()
{
    bDefeated = false;
    bMovementLocked = false;
    SetMana(MaxMana);
    CooldownUntil.Reset();
    ExternalCooldownUntil = 0.0;
    if (ACharacter* Character = Cast<ACharacter>(GetOwner()))
    {
        Character->TeleportTo(SpawnTransform.GetLocation(), SpawnTransform.Rotator());
        Character->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    }
    if (UReflectionsHealthComponent* Health = GetOwner()->FindComponentByClass<UReflectionsHealthComponent>())
    {
        Health->ResetHealth();
    }
    OnRespawned.Broadcast();
}

void UReflectionsSampleSpellDriver::SetRespawnTransform(const FTransform& Transform)
{
    SpawnTransform = Transform;
    bRespawnTransformSet = true;
}

void UReflectionsSampleSpellDriver::LoadCombatClips()
{
    for (const FCombatCast* Entry : {&BoltRight, &BoltLeft, &HeavyPush, &Slam, &Sweep, &HealRaise, &AimHold})
    {
        FString Name = FString::Printf(TEXT("AS_Hero_Combat%s"), Entry->Name);
        if (Entry == &AimHold && CVarAimHoldV1.GetValueOnGameThread() != 0) Name += TEXT("_V1");
        if (UAnimSequenceBase* Clip = LoadObject<UAnimSequenceBase>(nullptr, *FString::Printf(TEXT("%s%s.%s"), CombatFolder, *Name, *Name)))
        {
            CombatClips.Add(Entry->Name, Clip);
        }
    }
    UE_CLOG(CombatClips.Num() == 0, LogTemp, Log, TEXT("Spell driver: no combat casts found; using the trimmed original clips."));
}

void UReflectionsSampleSpellDriver::EndPlay(const EEndPlayReason::Type Reason)
{
    if (const APawn* Pawn = Cast<APawn>(GetOwner()))
        if (APlayerController* PC = Cast<APlayerController>(Pawn->GetController()))
        {
            if (SpellInput) PC->PopInputComponent(SpellInput);
            if (ULocalPlayer* Player = PC->GetLocalPlayer())
                if (UEnhancedInputLocalPlayerSubsystem* Subsystem = Player->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
                    if (SpellContext) Subsystem->RemoveMappingContext(SpellContext);
        }
    Super::EndPlay(Reason);
}

void UReflectionsSampleSpellDriver::BindControls()
{
    APawn* Pawn = Cast<APawn>(GetOwner());
    APlayerController* PC = Pawn && Pawn->IsLocallyControlled() ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
    if (!PC || SpellInput) return;
    ULocalPlayer* Player = PC->GetLocalPlayer();
    UEnhancedInputLocalPlayerSubsystem* Subsystem = Player ? Player->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
    if (!Subsystem) return;

    // Built at runtime so the spell controls need no extra assets to cook; priority 1 sits above IMC_Sandbox.
    SpellContext = NewObject<UInputMappingContext>(this, TEXT("IMC_Spells"));
    auto MakeAction = [this](const TCHAR* Name, bool bConsume)
    {
        UInputAction* Action = NewObject<UInputAction>(this, Name);
        Action->ValueType = EInputActionValueType::Boolean;
        Action->bConsumeInput = bConsume;
        SpellActions.Add(Action);
        return Action;
    };
    UInputAction* CastAction = MakeAction(TEXT("IA_SpellCast"), true);
    UInputAction* NextAction = MakeAction(TEXT("IA_SpellNext"), true);
    UInputAction* PreviousAction = MakeAction(TEXT("IA_SpellPrevious"), true);
    UInputAction* ShiftAction = MakeAction(TEXT("IA_SpellShift"), false);
    UInputAction* PageNextAction = MakeAction(TEXT("IA_SpellPageNext"), true);
    // Jam build: the GASP sample's IA_NextPawn (N) and IA_NextVisualOverride (F8) cycle the hero into third-party
    // characters. This higher-priority context claims those keys with a consuming no-op so the sample actions never
    // fire. IMC_Sandbox maps them on the keyboard only; no gamepad buttons.
    UInputAction* BlockAction = MakeAction(TEXT("IA_SpellBlockSampleDebug"), true);
    UInputAction* PagePreviousAction = MakeAction(TEXT("IA_SpellPagePrevious"), true);
    UInputAction* SlotActions[4] = {MakeAction(TEXT("IA_SpellSlot1"), true), MakeAction(TEXT("IA_SpellSlot2"), true),
        MakeAction(TEXT("IA_SpellSlot3"), true), MakeAction(TEXT("IA_SpellSlot4"), true)};

    SpellContext->MapKey(CastAction, EKeys::LeftMouseButton);
    SpellContext->MapKey(CastAction, EKeys::Gamepad_RightTrigger);
    SpellContext->MapKey(CastAction, EKeys::Q);
    SpellContext->MapKey(BlockAction, EKeys::N);
    SpellContext->MapKey(BlockAction, EKeys::F8);
    SpellContext->MapKey(ShiftAction, EKeys::LeftShift);
    {
        // Tab cycles forward unless Shift is held; Shift+Tab cycles back.
        FEnhancedActionKeyMapping& Forward = SpellContext->MapKey(NextAction, EKeys::Tab);
        UInputTriggerChordBlocker* Blocker = NewObject<UInputTriggerChordBlocker>(SpellContext);
        Blocker->ChordAction = ShiftAction;
        Forward.Triggers.Add(Blocker);
        FEnhancedActionKeyMapping& Back = SpellContext->MapKey(PreviousAction, EKeys::Tab);
        UInputTriggerChordAction* Chord = NewObject<UInputTriggerChordAction>(SpellContext);
        Chord->ChordAction = ShiftAction;
        Back.Triggers.Add(Chord);
    }
    SpellContext->MapKey(NextAction, EKeys::Gamepad_RightShoulder);
    SpellContext->MapKey(PreviousAction, EKeys::Gamepad_LeftShoulder);
    SpellContext->MapKey(PageNextAction, EKeys::RightBracket);
    SpellContext->MapKey(PageNextAction, EKeys::Gamepad_DPad_Right);
    SpellContext->MapKey(PagePreviousAction, EKeys::LeftBracket);
    SpellContext->MapKey(PagePreviousAction, EKeys::Gamepad_DPad_Left);
    const FKey SlotKeys[4] = {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four};
    for (int32 Index = 0; Index < 4; ++Index)
    {
        SpellContext->MapKey(SlotActions[Index], SlotKeys[Index]);
    }
    // LB now cycles spells, so gamepad sprint moves to the left stick click.
    if (UInputAction* Sprint = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/IA_Sprint.IA_Sprint")))
    {
        SpellContext->MapKey(Sprint, EKeys::Gamepad_LeftThumbstick);
    }

    SpellInput = NewObject<UEnhancedInputComponent>(PC, TEXT("SampleSpellInput"));
    SpellInput->RegisterComponent();
    SpellInput->BindAction(CastAction, ETriggerEvent::Started, this, &UReflectionsSampleSpellDriver::OnCastAction);
    SpellInput->BindAction(BlockAction, ETriggerEvent::Triggered, this, &UReflectionsSampleSpellDriver::IgnoreInput);
    SpellInput->BindAction(CastAction, ETriggerEvent::Completed, this, &UReflectionsSampleSpellDriver::OnCastReleased);
    SpellInput->BindAction(CastAction, ETriggerEvent::Canceled, this, &UReflectionsSampleSpellDriver::OnCastReleased);
    SpellInput->BindAction(NextAction, ETriggerEvent::Started, this, &UReflectionsSampleSpellDriver::NextSpell);
    SpellInput->BindAction(PreviousAction, ETriggerEvent::Started, this, &UReflectionsSampleSpellDriver::PreviousSpell);
    SpellInput->BindAction(PageNextAction, ETriggerEvent::Started, this, &UReflectionsSampleSpellDriver::NextPage);
    SpellInput->BindAction(PagePreviousAction, ETriggerEvent::Started, this, &UReflectionsSampleSpellDriver::PreviousPage);
    SpellInput->BindAction(SlotActions[0], ETriggerEvent::Started, this, &UReflectionsSampleSpellDriver::SelectFirstSlot);
    SpellInput->BindAction(SlotActions[1], ETriggerEvent::Started, this, &UReflectionsSampleSpellDriver::SelectSecondSlot);
    SpellInput->BindAction(SlotActions[2], ETriggerEvent::Started, this, &UReflectionsSampleSpellDriver::SelectThirdSlot);
    SpellInput->BindAction(SlotActions[3], ETriggerEvent::Started, this, &UReflectionsSampleSpellDriver::SelectFourthSlot);
    PC->PushInputComponent(SpellInput);
    Subsystem->AddMappingContext(SpellContext, 1);
}

void UReflectionsSampleSpellDriver::OnCastAction(const FInputActionValue& Value) { PrimaryPressed(); }
void UReflectionsSampleSpellDriver::OnCastReleased(const FInputActionValue& Value) { PrimaryReleased(); }

void UReflectionsSampleSpellDriver::UpdateInputDevice(APlayerController* PC)
{
    if (!PC) return;
    static const FKey PadKeys[] = {EKeys::Gamepad_FaceButton_Bottom, EKeys::Gamepad_FaceButton_Right, EKeys::Gamepad_FaceButton_Left,
        EKeys::Gamepad_FaceButton_Top, EKeys::Gamepad_LeftShoulder, EKeys::Gamepad_RightShoulder, EKeys::Gamepad_LeftTrigger,
        EKeys::Gamepad_RightTrigger, EKeys::Gamepad_DPad_Up, EKeys::Gamepad_DPad_Down, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_DPad_Right,
        EKeys::Gamepad_LeftThumbstick, EKeys::Gamepad_RightThumbstick, EKeys::Gamepad_Special_Left, EKeys::Gamepad_Special_Right};
    static const FKey PadAxes[] = {EKeys::Gamepad_LeftX, EKeys::Gamepad_LeftY, EKeys::Gamepad_RightX, EKeys::Gamepad_RightY};
    static const FKey DesktopKeys[] = {EKeys::LeftMouseButton, EKeys::RightMouseButton, EKeys::W, EKeys::A, EKeys::S, EKeys::D, EKeys::Q, EKeys::Tab};
    bool bPad = false;
    for (const FKey& Key : PadKeys)
    {
        bPad |= PC->IsInputKeyDown(Key);
    }
    for (const FKey& Axis : PadAxes)
    {
        bPad |= FMath::Abs(PC->GetInputAnalogKeyState(Axis)) > 0.3f;
    }
    float MouseX = 0.0f, MouseY = 0.0f;
    PC->GetInputMouseDelta(MouseX, MouseY);
    bool bDesktop = FMath::Abs(MouseX) + FMath::Abs(MouseY) > 0.5f;
    for (const FKey& Key : DesktopKeys)
    {
        bDesktop |= PC->IsInputKeyDown(Key);
    }
    if (bPad) bUsingGamepad = true;
    else if (bDesktop) bUsingGamepad = false;
    if (Aim) Aim->SetUsingGamepad(bUsingGamepad);
}

void UReflectionsSampleSpellDriver::SetMana(float Value)
{
    const float Clamped = FMath::Clamp(Value, 0.0f, MaxMana);
    if (!FMath::IsNearlyEqual(Clamped, Mana))
    {
        Mana = Clamped;
        OnManaChanged.Broadcast(Mana, MaxMana);
    }
}

bool UReflectionsSampleSpellDriver::SpendMagic(float Amount)
{
    if (Amount <= 0.0f) return true;
    if (bDefeated || Mana < Amount) return false;
    SetMana(Mana - Amount);
    if (const UWorld* World = GetWorld()) LastCastTime = World->GetTimeSeconds();
    return true;
}

bool UReflectionsSampleSpellDriver::TrySpendMana(float Amount)
{
    if (SpendMagic(Amount)) return true;
    SetFeedback(TEXT("Not enough mana"));
    return false;
}

bool UReflectionsSampleSpellDriver::CastExternal(const FReflectionsExternalCast& External)
{
    ACharacter* Character = Cast<ACharacter>(GetOwner());
    UWorld* World = GetWorld();
    if (bDefeated || !World || !Character || !Body || !RetargetClass || !External.OnRelease || !ReadyForNextCast(false)) return false;
    if (World->GetTimeSeconds() < ExternalCooldownUntil)
    {
        SetFeedback(FString::Printf(TEXT("Recharging (%.1fs)"), ExternalCooldownUntil - World->GetTimeSeconds()));
        return false;
    }
    if (Mana < External.ManaCost)
    {
        SetFeedback(TEXT("Not enough mana"));
        return false;
    }
    FHeroSpellDefinition Definition;
    bool bBoth = false;
    if (UAnimSequenceBase* Clip = External.Animation.Get())
    {
        Definition.Animation = Clip;
        Definition.ReleaseTime = External.ReleaseTime;
        Definition.ProjectileSocket = External.Socket;
        bBoth = External.Socket.IsNone();
    }
    else if (!ResolveCast(External.AimProxy, CastCounts.FindRef(External.AimProxy), Definition, bBoth))
    {
        return false;
    }
    if (!PlayCast(External.AimProxy, Definition, bBoth)) return false;
    SetMana(Mana - External.ManaCost);
    LastCastTime = World->GetTimeSeconds();
    ExternalCooldownUntil = LastCastTime + FMath::Max(0.0f, External.Cooldown);
    CastCounts.Add(External.AimProxy, CastCounts.FindRef(External.AimProxy) + 1);
    ActiveExternal = External;
    return true;
}

void UReflectionsSampleSpellDriver::SetSelectedSpell(EHeroSpell Spell)
{
    if (ReflectionsSpellCatalog::IsValid(Spell))
    {
        SelectedSpell = Spell;
        SpellPage = static_cast<uint8>(Spell) / ReflectionsSpellCatalog::PageSize;
        if (Aim) Aim->SetSelectedSpell(Spell);
    }
}
void UReflectionsSampleSpellDriver::ChangeSpellPage(int32 Delta)
{
    constexpr int32 Pages = (ReflectionsSpellCatalog::Count + ReflectionsSpellCatalog::PageSize - 1) / ReflectionsSpellCatalog::PageSize;
    SpellPage = ((SpellPage + Delta) % Pages + Pages) % Pages;
    SetSelectedSpell(static_cast<EHeroSpell>(SpellPage * ReflectionsSpellCatalog::PageSize));
}
void UReflectionsSampleSpellDriver::SelectSpellSlot(int32 Slot)
{
    if (Slot >= 0 && Slot < ReflectionsSpellCatalog::PageSize)
        SetSelectedSpell(static_cast<EHeroSpell>(SpellPage * ReflectionsSpellCatalog::PageSize + Slot));
}
FString UReflectionsSampleSpellDriver::GetSpellSlotName(int32 Slot) const
{
    const EHeroSpell Spell = static_cast<EHeroSpell>(SpellPage * ReflectionsSpellCatalog::PageSize + Slot);
    return Slot >= 0 && Slot < ReflectionsSpellCatalog::PageSize && ReflectionsSpellCatalog::IsValid(Spell)
        ? FString(ReflectionsSpellCatalog::Get(Spell).Name) : FString();
}
void UReflectionsSampleSpellDriver::SelectFirstSlot() { SelectSpellSlot(0); }
void UReflectionsSampleSpellDriver::SelectSecondSlot() { SelectSpellSlot(1); }
void UReflectionsSampleSpellDriver::SelectThirdSlot() { SelectSpellSlot(2); }
void UReflectionsSampleSpellDriver::SelectFourthSlot() { SelectSpellSlot(3); }
void UReflectionsSampleSpellDriver::PreviousPage() { ChangeSpellPage(-1); }
void UReflectionsSampleSpellDriver::NextPage() { ChangeSpellPage(1); }
void UReflectionsSampleSpellDriver::PreviousSpell()
{
    const int32 Previous = (static_cast<int32>(SelectedSpell) + ReflectionsSpellCatalog::Count - 1) % ReflectionsSpellCatalog::Count;
    SetSelectedSpell(static_cast<EHeroSpell>(Previous));
}
void UReflectionsSampleSpellDriver::NextSpell()
{
    const int32 Next = (static_cast<int32>(SelectedSpell) + 1) % ReflectionsSpellCatalog::Count;
    SetSelectedSpell(static_cast<EHeroSpell>(Next));
}
void UReflectionsSampleSpellDriver::CastSelected() { CastSelectedSpell(); }

void UReflectionsSampleSpellDriver::PrimaryPressed()
{
    const APawn* Pawn = Cast<APawn>(GetOwner());
    const APlayerController* PC = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
    // The HUD's mouse mode (hold right Alt) uses left click for its buttons.
    if (PC && PC->bShowMouseCursor) return;
    bPrimaryHeld = true;
    if (PrimaryCastOverride && PrimaryCastOverride()) return;
    CastSelectedSpell();
}

void UReflectionsSampleSpellDriver::PrimaryReleased()
{
    bPrimaryHeld = false;
}

bool UReflectionsSampleSpellDriver::ReadyForNextCast(bool bRepeat) const
{
    if (!ActiveMontage) return !bRestorePending || bUseLayeredCasting;
    // A fresh press may cut the follow-through sooner than a held trigger repeats.
    const float Window = bRepeat ? FMath::Max(CancelWindow, FollowThrough * 0.6f) : CancelWindow;
    return bReleased && !bMovementLocked && CastClock - ReleaseClock >= Window;
}

bool UReflectionsSampleSpellDriver::ResolveCast(EHeroSpell Spell, int32 Count, FHeroSpellDefinition& Out, bool& bOutBothHands) const
{
    bOutBothHands = false;
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    const EHeroSpell Family = Spec.AnimationFamily;
    const FHeroSpellDefinition* Exact = SpellDefaults ? SpellDefaults->FindSpellDefinition(Spell) : nullptr;
    const FHeroSpellDefinition* Definition = Exact && Exact->Animation ? Exact : (SpellDefaults ? SpellDefaults->FindSpellDefinition(Family) : nullptr);
    if (Definition) Out = *Definition;

    if (const FCombatCast* Combat = bUseLayeredCasting ? CombatCastFor(Spell, Count) : nullptr)
    {
        if (const TObjectPtr<UAnimSequenceBase>* Clip = CombatClips.Find(Combat->Name))
        {
            Out.Animation = *Clip;
            const float Notified = FindReleaseNotify(*Clip);
            Out.ReleaseTime = Notified >= 0.0f ? Notified : FMath::Min(Combat->Release, (*Clip)->GetPlayLength() * 0.8f);
            Out.ProjectileSocket = Combat->Socket ? FName(Combat->Socket) : NAME_None;
            bOutBothHands = Combat->Socket == nullptr;
            return true;
        }
    }
    if (!Definition || !Definition->Animation) return false;
    if ((Spell == Family || Definition != Exact) && (Count & 1) != 0)
    {
        if (const FHeroSpellDefinition* Alternate = AlternateSpells.Find(Family))
        {
            if (Alternate->Animation)
            {
                Out.Animation = Alternate->Animation;
                Out.ReleaseTime = Alternate->ReleaseTime;
            }
        }
    }
    return true;
}

bool UReflectionsSampleSpellDriver::CastSpell(EHeroSpell Spell)
{
    ACharacter* Character = Cast<ACharacter>(GetOwner());
    if (bDefeated || !ReflectionsSpellCatalog::IsValid(Spell) || !Character || !Body || !RetargetClass || !ReadyForNextCast(false)) return false;
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    if (!CanAfford(Spell)) return false;
    const bool bHover = Spec.Delivery == EReflectionsSpellDelivery::Hover;
    // Levitation still needs the full body and solid ground; everything else casts on the move.
    const bool bFullBody = !bUseLayeredCasting || bHover;
    if (bFullBody && (!Character->GetCharacterMovement()->IsMovingOnGround() || Character->bIsCrouched)) return false;

    const int32 Count = CastCounts.FindRef(Spell);
    FHeroSpellDefinition Definition;
    bool bBoth = false;
    if (!ResolveCast(Spell, Count, Definition, bBoth)) return false;
    if (!PlayCast(Spell, Definition, bBoth)) return false;
    SetMana(Mana - Spec.ManaCost);
    LastCastTime = GetWorld()->GetTimeSeconds();
    if (Spec.Cooldown > 0.0f) CooldownUntil.Add(Spell, LastCastTime + Spec.Cooldown);
    CastCounts.Add(Spell, Count + 1);
    ActiveExternal.Reset();
    return true;
}

bool UReflectionsSampleSpellDriver::PlayCast(EHeroSpell Spell, const FHeroSpellDefinition& Definition, bool bBoth)
{
    ACharacter* Character = Cast<ACharacter>(GetOwner());
    if (!Character || !Body || !Definition.Animation) return false;
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(Spell);
    const bool bFullBody = !bUseLayeredCasting || Spec.Delivery == EReflectionsSpellDelivery::Hover;

    // Start late in long wind-ups and speed them up so release lands CastWindup seconds after the press.
    const float Windup = WindupFor(Spec, CastWindup);
    float PlayRate = 1.0f;
    float StartAt = 0.0f;
    if (Windup > 0.0f && Definition.ReleaseTime > Windup)
    {
        PlayRate = FMath::Clamp(Definition.ReleaseTime / Windup, 1.0f, MaxPlayRate);
        StartAt = FMath::Max(0.0f, Definition.ReleaseTime - Windup * PlayRate);
    }

    UAnimInstance* Anim = Body->GetAnimInstance();
    if (bFullBody && !bUseLayeredCasting)
    {
        UClass* CastClass = LoadClass<UAnimInstance>(nullptr, TEXT("/Game/Characters/Hero/Gameplay/BP_HeroAnimation.BP_HeroAnimation_C"));
        if (!CastClass) return false;
        Body->SetAnimInstanceClass(CastClass);
        Anim = Body->GetAnimInstance();
    }
    if (!Anim) return false;
    if (ActiveMontage)
    {
        // Cancelling the previous cast's follow-through keeps chained casts snappy.
        Anim->Montage_Stop(0.1f, ActiveMontage);
        ActiveMontage = nullptr;
    }
    AimMontage = nullptr;
    UAnimMontage* Montage = Anim->PlaySlotAnimationAsDynamicMontage(Definition.Animation, UReflectionsHeroAnimInstance::SpellSlot,
        0.08f, 0.22f, PlayRate, 1, -1.0f, StartAt);
    if (!Montage)
    {
        if (bFullBody && !bUseLayeredCasting) Body->SetAnimInstanceClass(RetargetClass);
        return false;
    }
    ActiveMontage = Montage;
    ActiveDefinition = Definition;
    bBothHands = bBoth;
    ActiveSpell = Spell;
    bReleased = false;
    bStopping = false;
    bRestorePending = false;
    CastClock = 0.0f;
    ReleaseClock = 0.0f;
    bMovementLocked = bFullBody;
    if (bMovementLocked)
    {
        Character->GetCharacterMovement()->StopMovementImmediately();
        Character->GetCharacterMovement()->DisableMovement();
    }
    FOnMontageEnded Ended;
    Ended.BindUObject(this, &UReflectionsSampleSpellDriver::FinishCast);
    Anim->Montage_SetEndDelegate(Ended, ActiveMontage);
    return true;
}

FVector UReflectionsSampleSpellDriver::ReleaseLocation() const
{
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(ActiveSpell);
    const bool bAimed = Spec.Delivery == EReflectionsSpellDelivery::Projectile || Spec.Delivery == EReflectionsSpellDelivery::Area;
    if (!bAimed || !Body) return GetOwner()->GetActorLocation();
    if (bBothHands)
    {
        return (Body->GetSocketLocation(TEXT("hand_l")) + Body->GetSocketLocation(TEXT("hand_r"))) * 0.5f;
    }
    const FName DefaultSocket = Spec.AnimationFamily == EHeroSpell::Water ? TEXT("hand_l") : TEXT("hand_r");
    return Body->GetSocketLocation(ActiveDefinition.ProjectileSocket.IsNone() ? DefaultSocket : ActiveDefinition.ProjectileSocket);
}

void UReflectionsSampleSpellDriver::Release()
{
    const FHeroSpellDefinition* Definition = &ActiveDefinition;
    const FReflectionsSpellSpec& Spec = ReflectionsSpellCatalog::Get(ActiveSpell);
    const FVector Location = ReleaseLocation();
    FRotator AimRotation = GetOwner()->GetActorRotation();
    FVector Target = Location + AimRotation.Vector() * FMath::Max(Spec.Range, 1000.0f);
    AActor* AimTarget = nullptr;
    if (Aim)
    {
        Target = Aim->ResolveTarget(ActiveSpell, Location, AimTarget);
        const FVector Direction = (Target - Location).GetSafeNormal();
        if (!Direction.IsNearlyZero()) AimRotation = Direction.Rotation();
    }
    const FTransform Origin(AimRotation, Location);
    if (ActiveExternal.IsSet())
    {
        // Crafted spells release through their own callback; the catalog spell is not cast.
        const FReflectionsExternalCast External = ActiveExternal.GetValue();
        ActiveExternal.Reset();
        if (External.OnRelease) External.OnRelease(Origin, Target, AimTarget);
        return;
    }
    if (UReflectionsSpellCombatComponent* Combat = GetOwner()->FindComponentByClass<UReflectionsSpellCombatComponent>())
        Combat->ReleaseSpellAt(ActiveSpell, Origin, Target, AimTarget);
    if (Spec.Delivery == EReflectionsSpellDelivery::Hover && Preview && Definition && Definition->PreviewMesh)
    {
        Preview->SetStaticMesh(Definition->PreviewMesh);
        Preview->SetMaterial(0, Definition->PreviewMaterial);
        Preview->SetWorldTransform(FTransform(GetOwner()->GetActorRotation(), GetOwner()->GetActorLocation()));
        Preview->SetVisibility(true);
        PreviewTime = ActiveSpell == EHeroSpell::Levitation ? 2.4f : .7f;
    }
}

void UReflectionsSampleSpellDriver::FinishCast(UAnimMontage* Montage, bool bInterrupted)
{
    if (Montage != ActiveMontage) return;
    ActiveMontage = nullptr;
    bRestorePending = true;
}

void UReflectionsSampleSpellDriver::UpdateAimPose()
{
    UAnimInstance* Anim = Body ? Body->GetAnimInstance() : nullptr;
    if (!Anim || !Aim || !bUseLayeredCasting || ActiveMontage) return;
    const bool bWant = Aim->IsAiming();
    if (bWant && (!AimMontage || !Anim->Montage_IsPlaying(AimMontage)))
    {
        // Prefer the generated aim loop; otherwise freeze a bolt throw at its release pose.
        if (const TObjectPtr<UAnimSequenceBase>* Hold = CombatClips.Find(AimHold.Name))
        {
            AimMontage = Anim->PlaySlotAnimationAsDynamicMontage(*Hold, UReflectionsHeroAnimInstance::SpellSlot, 0.18f, 0.2f, 1.0f, 1000, -1.0f, 0.3f);
        }
        else if (const TObjectPtr<UAnimSequenceBase>* Bolt = CombatClips.Find(BoltRight.Name))
        {
            AimMontage = Anim->PlaySlotAnimationAsDynamicMontage(*Bolt, UReflectionsHeroAnimInstance::SpellSlot, 0.18f, 0.2f, 0.001f, 1, -1.0f,
                FMath::Min((FindReleaseNotify(*Bolt) >= 0.0f ? FindReleaseNotify(*Bolt) : BoltRight.Release) + 0.05f, (*Bolt)->GetPlayLength() * 0.8f));
        }
    }
    else if (!bWant && AimMontage)
    {
        Anim->Montage_Stop(0.2f, AimMontage);
        AimMontage = nullptr;
    }
}

void UReflectionsSampleSpellDriver::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaTime, TickType, TickFunction);
    BindControls();
    if (const UWorld* World = GetWorld())
    {
        if (bDefeated)
        {
            if (World->GetTimeSeconds() >= RespawnAt) Respawn();
            return;
        }
        // Health comes back slowly out of combat, in half-point steps so listeners aren't told every frame.
        if (HealthRegenPerSecond > 0.0f && World->GetTimeSeconds() - LastDamageTime >= HealthRegenDelay)
        {
            if (UReflectionsHealthComponent* Health = GetOwner()->FindComponentByClass<UReflectionsHealthComponent>())
            {
                if (Health->Health > 0.0f && Health->Health < Health->MaxHealth)
                {
                    PendingRegen += HealthRegenPerSecond * DeltaTime;
                    if (PendingRegen >= 0.5f)
                    {
                        Health->Heal(PendingRegen, GetOwner());
                        PendingRegen = 0.0f;
                    }
                }
                else
                {
                    PendingRegen = 0.0f;
                }
            }
        }
        if (World->GetTimeSeconds() - LastCastTime >= ManaRegenDelay && Mana < MaxMana)
        {
            SetMana(Mana + ManaRegenPerSecond * DeltaTime);
        }
        if (const APawn* Pawn = Cast<APawn>(GetOwner())) UpdateInputDevice(Cast<APlayerController>(Pawn->GetController()));
    }
    if (bRestorePending)
    {
        bRestorePending = false;
        if (Visual) Visual->SetRelativeLocation(VisualBase);
        if (!bUseLayeredCasting && Body && RetargetClass) Body->SetAnimInstanceClass(RetargetClass);
        if (bMovementLocked)
        {
            bMovementLocked = false;
            if (ACharacter* Character = Cast<ACharacter>(GetOwner())) Character->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
        }
        if (Preview) Preview->SetVisibility(false);
        PreviewTime = 0.0f;
    }
    if (ActiveMontage && Body && Body->GetAnimInstance())
    {
        UAnimInstance* Anim = Body->GetAnimInstance();
        CastClock += DeltaTime;
        const float Position = Anim->Montage_GetPosition(ActiveMontage);
        if (!bReleased && Position >= ActiveDefinition.ReleaseTime)
        {
            bReleased = true;
            ReleaseClock = CastClock;
            Release();
        }
        // Trim the long tails of generated clips: hold the follow-through briefly, then blend back to locomotion.
        if (bReleased && !bStopping && !bMovementLocked && CastClock - ReleaseClock >= FollowThrough)
        {
            bStopping = true;
            Anim->Montage_Stop(0.25f, ActiveMontage);
        }
        if (ActiveSpell == EHeroSpell::Levitation && Visual)
        {
            const float Lift = 65.0f * (FMath::SmoothStep(.5f, 46.f/30.f, Position) - FMath::SmoothStep(81.f/30.f, 112.f/30.f, Position));
            Visual->SetRelativeLocation(VisualBase + FVector(0, 0, Lift));
        }
    }
    if (bPrimaryHeld && ReadyForNextCast(true))
    {
        if (!PrimaryCastOverride || !PrimaryCastOverride()) CastSelectedSpell();
    }
    UpdateAimPose();
    if (PreviewTime > 0.0f && Preview)
    {
        PreviewTime -= DeltaTime;
        Preview->AddLocalRotation(FRotator(0,120.f*DeltaTime,0));
        if (PreviewTime <= 0.0f) Preview->SetVisibility(false);
    }
}
