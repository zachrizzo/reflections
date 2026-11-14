#include "Worlds/ReflectionsWorldJumpComponent.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundMix.h"
#include "Components/CapsuleComponent.h"
#include "Components/MeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputTriggers.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "Sound/SoundBase.h"
#include "Camera/CameraShakeBase.h"
#include "TimerManager.h"
#include "Worlds/ReflectionsWorldHud.h"
#include "Worlds/ReflectionsWorldJumpConfig.h"
#include "Worlds/ReflectionsWorldJumpSubsystem.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsWorldJump, Log, All);

#define LOCTEXT_NAMESPACE "ReflectionsWorlds"

namespace ReflectionsWorldMagic
{
    UFunction* FindFunction(const UObject* Object, const TArray<FName>& Names)
    {
        for (const FName& Name : Names)
        {
            if (UFunction* Function = Object->FindFunction(Name))
            {
                return Function;
            }
        }
        return nullptr;
    }

    bool ReadNumber(const FProperty* Property, const void* Container, float& Out)
    {
        if (const FFloatProperty* Float = CastField<FFloatProperty>(Property))
        {
            Out = Float->GetPropertyValue_InContainer(Container);
            return true;
        }
        if (const FDoubleProperty* Double = CastField<FDoubleProperty>(Property))
        {
            Out = static_cast<float>(Double->GetPropertyValue_InContainer(Container));
            return true;
        }
        if (const FIntProperty* Int = CastField<FIntProperty>(Property))
        {
            Out = static_cast<float>(Int->GetPropertyValue_InContainer(Container));
            return true;
        }
        return false;
    }

    /** Calls Function on Object. Writes Argument into its first non-return parameter if it has one. */
    bool Call(UObject* Object, UFunction* Function, const float* Argument, float* OutNumber, bool* OutBool)
    {
        if (!Object || !Function)
        {
            return false;
        }
        uint8* Buffer = static_cast<uint8*>(FMemory_Alloca(FMath::Max<int32>(Function->ParmsSize, 16)));
        FMemory::Memzero(Buffer, FMath::Max<int32>(Function->ParmsSize, 16));
        FProperty* ArgumentProperty = nullptr;
        for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
        {
            It->InitializeValue_InContainer(Buffer);
            if (!ArgumentProperty && !It->HasAnyPropertyFlags(CPF_ReturnParm | CPF_OutParm))
            {
                ArgumentProperty = *It;
            }
        }
        bool bOk = true;
        if (Argument)
        {
            if (FFloatProperty* Float = CastField<FFloatProperty>(ArgumentProperty))
            {
                Float->SetPropertyValue_InContainer(Buffer, *Argument);
            }
            else if (FDoubleProperty* Double = CastField<FDoubleProperty>(ArgumentProperty))
            {
                Double->SetPropertyValue_InContainer(Buffer, *Argument);
            }
            else
            {
                bOk = false;
            }
        }
        if (bOk)
        {
            Object->ProcessEvent(Function, Buffer);
            const FProperty* Return = Function->GetReturnProperty();
            if (OutNumber)
            {
                bOk = Return && ReadNumber(Return, Buffer, *OutNumber);
            }
            if (OutBool)
            {
                const FBoolProperty* Bool = CastField<FBoolProperty>(Return);
                // A void spend function is taken as success.
                *OutBool = Bool ? Bool->GetPropertyValue_InContainer(Buffer) : true;
            }
        }
        for (TFieldIterator<FProperty> It(Function); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
        {
            It->DestroyValue_InContainer(Buffer);
        }
        return bOk;
    }
}

UReflectionsWorldJumpComponent::UReflectionsWorldJumpComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickInterval = 0.1f;
    bAutoActivate = true;
}

void UReflectionsWorldJumpComponent::BeginPlay()
{
    Super::BeginPlay();
    Config = const_cast<UReflectionsWorldJumpConfig*>(UReflectionsWorldJumpConfig::Get(this));
    const APawn* Pawn = Cast<APawn>(GetOwner());
    if (Pawn && Pawn->IsLocallyControlled() && Pawn->IsPlayerControlled())
    {
        Startup();
    }
}

void UReflectionsWorldJumpComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    Shutdown();
    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().ClearAllTimersForObject(this);
    }
    Super::EndPlay(Reason);
}

APlayerController* UReflectionsWorldJumpComponent::GetPlayerController() const
{
    const APawn* Pawn = Cast<APawn>(GetOwner());
    return Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
}

void UReflectionsWorldJumpComponent::Startup()
{
    if (bStarted)
    {
        return;
    }
    APlayerController* PC = GetPlayerController();
    if (!PC || !PC->IsLocalController())
    {
        return;
    }
    if (!Config)
    {
        Config = const_cast<UReflectionsWorldJumpConfig*>(UReflectionsWorldJumpConfig::Get(this));
    }
    bStarted = true;

    UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    UReflectionsWorldJumpWorldSubsystem* Worlds = UReflectionsWorldJumpWorldSubsystem::Get(this);
    if (Progress)
    {
        Progress->OnWorldChanged.AddUniqueDynamic(this, &UReflectionsWorldJumpComponent::HandleWorldChanged);
        Progress->OnMessage.AddUniqueDynamic(this, &UReflectionsWorldJumpComponent::HandleMessage);
        Progress->OnBookComplete.AddUniqueDynamic(this, &UReflectionsWorldJumpComponent::HandleBookComplete);
        Progress->OnPagesChanged.AddUniqueDynamic(this, &UReflectionsWorldJumpComponent::HandlePagesChanged);
        Progress->OnCoinsChanged.AddUniqueDynamic(this, &UReflectionsWorldJumpComponent::HandleCoinsChanged);
        Progress->OnKeyAdded.AddUniqueDynamic(this, &UReflectionsWorldJumpComponent::HandleKeyAdded);
    }

    BindInput();

    if (Config && Config->bShowHud && !Hud)
    {
        Hud = CreateWidget<UReflectionsWorldHudWidget>(PC, UReflectionsWorldHudWidget::StaticClass());
        if (Hud)
        {
            Hud->AddToViewport(20);
        }
    }

    const bool bArriving = Progress && Progress->PendingArrival.bValid;
    if (bArriving)
    {
        // SeparateMaps: this map was opened by a jump. Put the hero where they left the other London.
        if (APlayerCameraManager* Camera = PC->PlayerCameraManager)
        {
            Camera->StartCameraFade(1.0f, 1.0f, 0.0f, FLinearColor::Black, false, true);
        }
        GetWorld()->GetTimerManager().SetTimer(ArrivalTimer, this, &UReflectionsWorldJumpComponent::FinishSeparateMapArrival, 0.1f, false);
    }
    else if (Progress && Worlds)
    {
        const EReflectionsWorld Here = Worlds->GetWorldAtLocation(GetOwner()->GetActorLocation());
        Progress->SetCurrentWorld(Here, false);
        ApplyCoatTint(Here);
        UpdateMusic(Here);
        if (Hud && Config)
        {
            const FReflectionsWorldInfo* Info = Config->FindWorld(Here);
            Hud->ShowBanner(Config->GetWorldName(Here), Info ? Info->ThemeColor : FLinearColor::White);
        }
    }
    RefreshHud();
}

void UReflectionsWorldJumpComponent::Shutdown()
{
    if (!bStarted)
    {
        return;
    }
    bStarted = false;
    UnbindInput();
    if (Music)
    {
        Music->Stop();
        Music = nullptr;
    }
    if (Hud)
    {
        Hud->RemoveFromParent();
        Hud = nullptr;
    }
    if (UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this))
    {
        Progress->OnWorldChanged.RemoveAll(this);
        Progress->OnMessage.RemoveAll(this);
        Progress->OnBookComplete.RemoveAll(this);
        Progress->OnPagesChanged.RemoveAll(this);
        Progress->OnCoinsChanged.RemoveAll(this);
        Progress->OnKeyAdded.RemoveAll(this);
    }
}

// ---- Input ---------------------------------------------------------------------------------------------------

void UReflectionsWorldJumpComponent::BindInput()
{
    APlayerController* PC = GetPlayerController();
    if (!PC || JumpInput || !Config)
    {
        return;
    }
    UpAction = Config->JumpUpAction.LoadSynchronous();
    DownAction = Config->JumpDownAction.LoadSynchronous();
    ActiveContext = Config->MappingContext.LoadSynchronous();
    if (!UpAction || !DownAction || !ActiveContext)
    {
        BuildFallbackInput();
    }

    if (const ULocalPlayer* LocalPlayer = PC->GetLocalPlayer())
    {
        if (UEnhancedInputLocalPlayerSubsystem* Input = LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
        {
            Input->AddMappingContext(ActiveContext, Config->MappingPriority);
        }
    }

    JumpInput = NewObject<UEnhancedInputComponent>(PC, TEXT("WorldJumpInput"));
    JumpInput->RegisterComponent();
    JumpInput->BindAction(UpAction, ETriggerEvent::Triggered, this, &UReflectionsWorldJumpComponent::HandleJumpUp);
    JumpInput->BindAction(DownAction, ETriggerEvent::Triggered, this, &UReflectionsWorldJumpComponent::HandleJumpDown);
    PC->PushInputComponent(JumpInput);
    InputController = PC;
}

void UReflectionsWorldJumpComponent::UnbindInput()
{
    APlayerController* PC = InputController.Get();
    if (PC && JumpInput)
    {
        PC->PopInputComponent(JumpInput);
        if (const ULocalPlayer* LocalPlayer = PC->GetLocalPlayer())
        {
            if (UEnhancedInputLocalPlayerSubsystem* Input = LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
            {
                if (ActiveContext)
                {
                    Input->RemoveMappingContext(ActiveContext);
                }
            }
        }
    }
    if (JumpInput)
    {
        JumpInput->DestroyComponent();
    }
    JumpInput = nullptr;
    InputController = nullptr;
}

void UReflectionsWorldJumpComponent::BuildFallbackInput()
{
    UE_LOG(LogReflectionsWorldJump, Log, TEXT("World jump input assets not found; building the input at runtime."));
    UpAction = NewObject<UInputAction>(this, TEXT("IA_WorldJumpUp_Runtime"));
    DownAction = NewObject<UInputAction>(this, TEXT("IA_WorldJumpDown_Runtime"));
    ActiveContext = NewObject<UInputMappingContext>(this, TEXT("IMC_WorldJump_Runtime"));
    auto MapAll = [this](UInputAction* Action, const TArray<FKey>& Keys)
    {
        for (const FKey& Key : Keys)
        {
            FEnhancedActionKeyMapping& Mapping = ActiveContext->MapKey(Action, Key);
            UInputTriggerHold* Hold = NewObject<UInputTriggerHold>(ActiveContext);
            Hold->HoldTimeThreshold = Config->FallbackHoldTime;
            Hold->bIsOneShot = true;
            Mapping.Triggers.Add(Hold);
        }
    };
    MapAll(UpAction, Config->FallbackUpKeys);
    MapAll(DownAction, Config->FallbackDownKeys);
}

void UReflectionsWorldJumpComponent::HandleJumpUp()
{
    RequestJump(EReflectionsJumpDirection::Up);
}

void UReflectionsWorldJumpComponent::HandleJumpDown()
{
    RequestJump(EReflectionsJumpDirection::Down);
}

FText UReflectionsWorldJumpComponent::GetKeysText(EReflectionsJumpDirection Direction) const
{
    const UInputAction* Action = Direction == EReflectionsJumpDirection::Up ? UpAction.Get() : DownAction.Get();
    if (!Action || !ActiveContext)
    {
        return FText::GetEmpty();
    }
    TArray<FString> Names;
    for (const FEnhancedActionKeyMapping& Mapping : ActiveContext->GetMappings())
    {
        if (Mapping.Action == Action)
        {
            FString Name;
            if (Mapping.Key == EKeys::Gamepad_LeftThumbstick) Name = TEXT("L3");
            else if (Mapping.Key == EKeys::Gamepad_RightThumbstick) Name = TEXT("R3");
            else if (Mapping.Key == EKeys::Gamepad_FaceButton_Top) Name = TEXT("Y");
            else if (Mapping.Key == EKeys::Gamepad_FaceButton_Bottom) Name = TEXT("A");
            else if (Mapping.Key == EKeys::Gamepad_FaceButton_Left) Name = TEXT("X (pad)");
            else if (Mapping.Key == EKeys::Gamepad_FaceButton_Right) Name = TEXT("B");
            else if (Mapping.Key == EKeys::Gamepad_DPad_Up) Name = TEXT("D-pad Up");
            else if (Mapping.Key == EKeys::Gamepad_DPad_Down) Name = TEXT("D-pad Down");
            else Name = Mapping.Key.GetDisplayName(false).ToString();
            Names.AddUnique(Name);
        }
    }
    return FText::FromString(FString::Join(Names, TEXT(" / ")));
}

// ---- Cost ----------------------------------------------------------------------------------------------------

UObject* UReflectionsWorldJumpComponent::FindMagicSource() const
{
    const AActor* Owner = GetOwner();
    if (!Owner || !Config)
    {
        return nullptr;
    }
    UObject* GetterOnly = nullptr;
    for (UActorComponent* Component : Owner->GetComponents())
    {
        if (!Component || Component == this)
        {
            continue;
        }
        if (ReflectionsWorldMagic::FindFunction(Component, Config->SpendMagicNames))
        {
            return Component;
        }
        if (!GetterOnly && ReflectionsWorldMagic::FindFunction(Component, Config->MagicGetterNames))
        {
            GetterOnly = Component;
        }
    }
    return GetterOnly;
}

bool UReflectionsWorldJumpComponent::GetMagic(float& Current, float& Max) const
{
    Current = 0.0f;
    Max = 0.0f;
    UObject* Source = FindMagicSource();
    if (!Source)
    {
        return false;
    }
    if (!ReflectionsWorldMagic::Call(Source, ReflectionsWorldMagic::FindFunction(Source, Config->MagicGetterNames), nullptr, &Current, nullptr))
    {
        return false;
    }
    if (!ReflectionsWorldMagic::Call(Source, ReflectionsWorldMagic::FindFunction(Source, Config->MaxMagicGetterNames), nullptr, &Max, nullptr))
    {
        for (const FName& Name : Config->MaxMagicPropertyNames)
        {
            if (const FProperty* Property = Source->GetClass()->FindPropertyByName(Name))
            {
                if (ReflectionsWorldMagic::ReadNumber(Property, Source, Max))
                {
                    break;
                }
            }
        }
    }
    if (Max <= 0.0f)
    {
        Max = FMath::Max(Current, 100.0f);
    }
    return true;
}

bool UReflectionsWorldJumpComponent::CanDrainMagic() const
{
    const UObject* Source = FindMagicSource();
    return Source && Config && ReflectionsWorldMagic::FindFunction(Source, Config->SpendMagicNames) != nullptr;
}

float UReflectionsWorldJumpComponent::GetJumpMagicCost() const
{
    float Current = 0.0f;
    float Max = 0.0f;
    if (!Config || !GetMagic(Current, Max))
    {
        return 0.0f;
    }
    return Max * Config->MagicCostFraction;
}

bool UReflectionsWorldJumpComponent::SpendMagic(float Amount)
{
    UObject* Source = FindMagicSource();
    UFunction* Spend = Source ? ReflectionsWorldMagic::FindFunction(Source, Config->SpendMagicNames) : nullptr;
    if (!Spend)
    {
        return false;
    }
    bool bSpent = false;
    return ReflectionsWorldMagic::Call(Source, Spend, &Amount, nullptr, &bSpent) && bSpent;
}

bool UReflectionsWorldJumpComponent::PickCoin(EReflectionsWorld Destination, EReflectionsWorld& OutCoin) const
{
    const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    if (!Progress || !Config)
    {
        return false;
    }
    const int32 Need = Config->CoinsPerJump;
    const EReflectionsWorld Here = GetCurrentWorld();
    TArray<EReflectionsWorld, TInlineAllocator<3>> Order;
    switch (Config->CoinRule)
    {
    case EReflectionsCoinRule::DestinationWorld: Order.Add(Destination); break;
    case EReflectionsCoinRule::CurrentWorld: Order.Add(Here); break;
    case EReflectionsCoinRule::AnyWorld:
        Order.Add(Destination);
        Order.AddUnique(Here);
        for (const FReflectionsWorldInfo& Info : Config->Worlds)
        {
            Order.AddUnique(Info.World);
        }
        break;
    }
    for (EReflectionsWorld Candidate : Order)
    {
        if (Progress->GetCoins(Candidate) >= Need)
        {
            OutCoin = Candidate;
            return true;
        }
    }
    OutCoin = Order.Num() > 0 ? Order[0] : Destination;
    return Need <= 0;
}

EReflectionsWorld UReflectionsWorldJumpComponent::GetCurrentWorld() const
{
    const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    return Progress ? Progress->GetCurrentWorld() : EReflectionsWorld::Gray;
}

// ---- Jump ----------------------------------------------------------------------------------------------------

bool UReflectionsWorldJumpComponent::CanJump(EReflectionsJumpDirection Direction, FText& OutReason, EReflectionsWorld& OutDestination) const
{
    OutReason = FText::GetEmpty();
    const UReflectionsWorldJumpWorldSubsystem* Worlds = UReflectionsWorldJumpWorldSubsystem::Get(this);
    if (!Config || !Worlds || !GetOwner())
    {
        OutReason = LOCTEXT("NoSetup", "World jumping is not set up in this map.");
        return false;
    }
    if (bJumping)
    {
        return false;
    }
    const EReflectionsWorld Here = GetCurrentWorld();
    if (!Config->GetNeighbor(Here, Direction, OutDestination))
    {
        OutReason = Direction == EReflectionsJumpDirection::Up
            ? FText::Format(LOCTEXT("NoneAbove", "There is no London above {0}."), Config->GetWorldName(Here))
            : FText::Format(LOCTEXT("NoneBelow", "There is no London below {0}."), Config->GetWorldName(Here));
        return false;
    }
    const FText DestinationName = Config->GetWorldName(OutDestination);

    EReflectionsWorld Coin;
    if (!PickCoin(OutDestination, Coin))
    {
        OutReason = FText::Format(LOCTEXT("NeedCoin", "You need a coin from {0} to cross."), Config->GetWorldName(Coin));
        return false;
    }

    float Current = 0.0f;
    float Max = 0.0f;
    if (GetMagic(Current, Max))
    {
        const float Cost = Max * Config->MagicCostFraction;
        if (Current + 0.5f < Cost)
        {
            OutReason = FText::Format(LOCTEXT("NeedMagic", "Not enough magic: the crossing takes {0}, you have {1}."),
                FText::AsNumber(FMath::RoundToInt(Cost)), FText::AsNumber(FMath::FloorToInt(Current)));
            return false;
        }
        if (!CanDrainMagic() && Config->bRequireMagicSource)
        {
            OutReason = LOCTEXT("MagicNotSpendable", "Your magic cannot be spent on a crossing yet.");
            return false;
        }
    }
    else if (Config->bRequireMagicSource)
    {
        OutReason = LOCTEXT("NoMagic", "You have no magic to cross with.");
        return false;
    }

    if (Config->Layout == EReflectionsWorldLayout::SeparateMaps)
    {
        const FReflectionsWorldInfo* Info = Config->FindWorld(OutDestination);
        if (!Info || Info->Map.IsNull())
        {
            OutReason = FText::Format(LOCTEXT("NoMap", "{0} has no map set in the world-jump config."), DestinationName);
            return false;
        }
        return true;
    }

    FVector Desired;
    if (!Worlds->TranslateBetweenWorlds(GetOwner()->GetActorLocation(), Here, OutDestination, Desired))
    {
        OutReason = FText::Format(LOCTEXT("NoAnchor", "{0} is not in this map (it has no world anchor)."), DestinationName);
        return false;
    }
    FVector Landing;
    return FindSafeLanding(Desired, Landing, OutReason, OutDestination);
}

bool UReflectionsWorldJumpComponent::RequestJump(EReflectionsJumpDirection Direction)
{
    if (!bStarted || bJumping || !Config)
    {
        return false;
    }
    const UWorld* World = GetWorld();
    if (World && World->GetTimeSeconds() - LastJumpTime < 0.4)
    {
        return false;
    }

    FText Reason;
    EReflectionsWorld Destination = EReflectionsWorld::Gray;
    if (!CanJump(Direction, Reason, Destination))
    {
        Refuse(Reason);
        return false;
    }

    // Work out the landing before paying, so a refused landing costs nothing.
    FVector Landing = FVector::ZeroVector;
    if (Config->Layout == EReflectionsWorldLayout::OffsetCopies)
    {
        const UReflectionsWorldJumpWorldSubsystem* Worlds = UReflectionsWorldJumpWorldSubsystem::Get(this);
        FVector Desired;
        if (!Worlds || !Worlds->TranslateBetweenWorlds(GetOwner()->GetActorLocation(), GetCurrentWorld(), Destination, Desired)
            || !FindSafeLanding(Desired, Landing, Reason, Destination))
        {
            Refuse(Reason);
            return false;
        }
    }

    UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    EReflectionsWorld Coin;
    if (!Progress || !PickCoin(Destination, Coin) || !Progress->SpendCoin(Coin, Config->CoinsPerJump))
    {
        Refuse(LOCTEXT("CoinGone", "You need a coin to cross."));
        return false;
    }
    float Current = 0.0f;
    float Max = 0.0f;
    if (GetMagic(Current, Max))
    {
        const float Cost = Max * Config->MagicCostFraction;
        if (CanDrainMagic())
        {
            if (!SpendMagic(FMath::Min(Cost, Current)))
            {
                Progress->AwardCoin(Coin, Config->CoinsPerJump);
                Refuse(LOCTEXT("MagicRefused", "Your magic would not answer."));
                return false;
            }
        }
        else if (!bWarnedNoMagic)
        {
            bWarnedNoMagic = true;
            UE_LOG(LogReflectionsWorldJump, Warning, TEXT("World jump: the magic component on %s has no SpendMagic(float) function, so the crossing is free."),
                *GetOwner()->GetName());
        }
    }

    BeginTransition(Destination, Landing);
    return true;
}

bool UReflectionsWorldJumpComponent::IsSpotFree(const FVector& Location) const
{
    const AActor* Owner = GetOwner();
    const ACharacter* Character = Cast<ACharacter>(Owner);
    const UCapsuleComponent* Capsule = Character ? Character->GetCapsuleComponent() : Cast<UCapsuleComponent>(Owner->GetRootComponent());
    FCollisionQueryParams Params(SCENE_QUERY_STAT(WorldJumpLanding), false, Owner);
    TArray<AActor*> Attached;
    Owner->GetAttachedActors(Attached, true, true);
    Params.AddIgnoredActors(Attached);
    if (!Capsule)
    {
        return !GetWorld()->OverlapBlockingTestByChannel(Location, FQuat::Identity, ECC_Pawn, FCollisionShape::MakeSphere(40.0f), Params);
    }
    FCollisionResponseParams Response(Capsule->GetCollisionResponseToChannels());
    const FCollisionShape Shape = FCollisionShape::MakeCapsule(
        FMath::Max(1.0f, Capsule->GetScaledCapsuleRadius() - 1.0f), FMath::Max(1.0f, Capsule->GetScaledCapsuleHalfHeight() - 1.0f));
    return !GetWorld()->OverlapBlockingTestByChannel(Location, Capsule->GetComponentQuat(), Capsule->GetCollisionObjectType(), Shape, Params, Response);
}

bool UReflectionsWorldJumpComponent::HasGroundBelow(const FVector& Location) const
{
    const AActor* Owner = GetOwner();
    const ACharacter* Character = Cast<ACharacter>(Owner);
    const UCapsuleComponent* Capsule = Character ? Character->GetCapsuleComponent() : Cast<UCapsuleComponent>(Owner->GetRootComponent());
    const float HalfHeight = Capsule ? Capsule->GetScaledCapsuleHalfHeight() : 90.0f;
    const float Radius = Capsule ? Capsule->GetScaledCapsuleRadius() * 0.5f : 20.0f;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(WorldJumpGround), false, Owner);
    TArray<AActor*> Attached;
    Owner->GetAttachedActors(Attached, true, true);
    Params.AddIgnoredActors(Attached);
    const ECollisionChannel Channel = Capsule ? Capsule->GetCollisionObjectType() : ECC_Pawn;
    FCollisionResponseParams Response = Capsule ? FCollisionResponseParams(Capsule->GetCollisionResponseToChannels()) : FCollisionResponseParams::DefaultResponseParam;
    FHitResult Hit;
    const FVector End = Location - FVector(0.0f, 0.0f, HalfHeight + Config->MaxDropDistance);
    return GetWorld()->SweepSingleByChannel(Hit, Location, End, FQuat::Identity, Channel, FCollisionShape::MakeSphere(Radius), Params, Response);
}

bool UReflectionsWorldJumpComponent::FindSafeLanding(const FVector& Desired, FVector& OutLanding, FText& OutReason, EReflectionsWorld Destination) const
{
    const FText DestinationName = Config->GetWorldName(Destination);
    const float Step = FMath::Max(5.0f, Config->NudgeStep);
    const float MaxNudge = Config->MaxNudgeDistance;

    TArray<FVector> Candidates;
    Candidates.Add(Desired);
    for (float Up = Step; Up <= MaxNudge + KINDA_SMALL_NUMBER; Up += Step)
    {
        Candidates.Add(Desired + FVector(0.0f, 0.0f, Up));
    }
    for (float Radius = Step; Radius <= MaxNudge + KINDA_SMALL_NUMBER; Radius += Step)
    {
        for (int32 Index = 0; Index < 12; ++Index)
        {
            const float Angle = Index * (UE_TWO_PI / 12.0f);
            const FVector Side(FMath::Cos(Angle) * Radius, FMath::Sin(Angle) * Radius, 0.0f);
            Candidates.Add(Desired + Side);
            Candidates.Add(Desired + Side + FVector(0.0f, 0.0f, Radius * 0.5f));
        }
    }

    bool bFoundFreeSpot = false;
    for (const FVector& Candidate : Candidates)
    {
        if (!IsSpotFree(Candidate))
        {
            continue;
        }
        bFoundFreeSpot = true;
        if (!Config->bRequireGround || HasGroundBelow(Candidate))
        {
            OutLanding = Candidate;
            return true;
        }
    }
    OutReason = bFoundFreeSpot
        ? FText::Format(LOCTEXT("NoGround", "Nothing to stand on at this spot in {0}."), DestinationName)
        : FText::Format(LOCTEXT("Blocked", "Something solid fills this spot in {0}. Move a little and try again."), DestinationName);
    return false;
}

void UReflectionsWorldJumpComponent::BeginTransition(EReflectionsWorld Destination, const FVector& Landing)
{
    bJumping = true;
    PendingWorld = Destination;
    PendingLanding = Landing;
    LastJumpTime = GetWorld()->GetTimeSeconds();

    const FReflectionsWorldInfo* Info = Config->FindWorld(Destination);
    const FLinearColor Flash = Info ? Info->ThemeColor : FLinearColor::White;
    if (APlayerController* PC = GetPlayerController())
    {
        if (PC->PlayerCameraManager)
        {
            PC->PlayerCameraManager->StartCameraFade(0.0f, 1.0f, Config->FadeOutTime, Flash, false, true);
        }
    }
    if (Config->DepartureEffect)
    {
        UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, Config->DepartureEffect, GetOwner()->GetActorLocation());
    }
    if (Config->JumpSound)
    {
        UGameplayStatics::PlaySound2D(this, Config->JumpSound);
    }
    if (Music)
    {
        Music->FadeOut(Config->MusicFadeOutTime, 0.0f);
    }
    if (Hud)
    {
        Hud->ShowMessage(FText::Format(LOCTEXT("Crossing", "Crossing into {0}..."), Config->GetWorldName(Destination)), Flash);
    }

    if (Config->FadeOutTime <= KINDA_SMALL_NUMBER)
    {
        CompleteTransition();
    }
    else
    {
        GetWorld()->GetTimerManager().SetTimer(TransitionTimer, this, &UReflectionsWorldJumpComponent::CompleteTransition, Config->FadeOutTime, false);
    }
}

void UReflectionsWorldJumpComponent::CompleteTransition()
{
    UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    AActor* Owner = GetOwner();
    if (!Owner || !Progress)
    {
        bJumping = false;
        return;
    }

    if (Config->Layout == EReflectionsWorldLayout::SeparateMaps)
    {
        const FReflectionsWorldInfo* Info = Config->FindWorld(PendingWorld);
        FReflectionsPendingArrival& Arrival = Progress->PendingArrival;
        Arrival.bValid = true;
        Arrival.World = PendingWorld;
        Arrival.Location = Owner->GetActorLocation();
        Arrival.Rotation = Owner->GetActorRotation();
        Arrival.Velocity = Owner->GetVelocity();
        if (const APlayerController* PC = GetPlayerController())
        {
            Arrival.ControlRotation = PC->GetControlRotation();
        }
        Progress->SetCurrentWorld(PendingWorld, false);
        UGameplayStatics::OpenLevelBySoftObjectPtr(this, Info->Map);
        return;
    }

    // The hero kept moving during the fade-out; land at their spot now if it is still safe.
    FVector Landing = PendingLanding;
    if (const UReflectionsWorldJumpWorldSubsystem* Worlds = UReflectionsWorldJumpWorldSubsystem::Get(this))
    {
        FVector Desired;
        FVector Fresh;
        FText Ignored;
        if (Worlds->TranslateBetweenWorlds(Owner->GetActorLocation(), Progress->GetCurrentWorld(), PendingWorld, Desired)
            && FindSafeLanding(Desired, Fresh, Ignored, PendingWorld))
        {
            Landing = Fresh;
        }
    }
    ArriveAt(Landing, PendingWorld);
}

void UReflectionsWorldJumpComponent::ArriveAt(const FVector& Landing, EReflectionsWorld Destination)
{
    AActor* Owner = GetOwner();
    UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    const FVector Velocity = Owner->GetVelocity();

    Owner->SetActorLocation(Landing, false, nullptr, ETeleportType::TeleportPhysics);
    if (ACharacter* Character = Cast<ACharacter>(Owner))
    {
        if (UCharacterMovementComponent* Movement = Character->GetCharacterMovement())
        {
            Movement->Velocity = Config->bKeepVelocity ? Velocity : FVector::ZeroVector;
        }
    }

    // Cloth and other simulated meshes would stretch across the jump; reset them in place.
    TArray<AActor*> Actors;
    Owner->GetAttachedActors(Actors, true, true);
    Actors.Add(Owner);
    for (AActor* Actor : Actors)
    {
        TInlineComponentArray<USkeletalMeshComponent*> Meshes(Actor);
        for (USkeletalMeshComponent* Mesh : Meshes)
        {
            Mesh->ForceClothNextUpdateTeleportAndReset();
        }
    }

    const FReflectionsWorldInfo* Info = Config->FindWorld(Destination);
    const FLinearColor Flash = Info ? Info->ThemeColor : FLinearColor::White;
    if (APlayerController* PC = GetPlayerController())
    {
        if (APlayerCameraManager* Camera = PC->PlayerCameraManager)
        {
            Camera->SetGameCameraCutThisFrame();
            Camera->StartCameraFade(1.0f, 0.0f, Config->FadeInTime, Flash, false, false);
        }
        if (Config->ArrivalCameraShake)
        {
            PC->ClientStartCameraShake(Config->ArrivalCameraShake);
        }
    }
    if (Config->ArrivalEffect)
    {
        UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, Config->ArrivalEffect, Landing);
    }
    if (Config->ArrivalSound)
    {
        UGameplayStatics::PlaySound2D(this, Config->ArrivalSound);
    }
    if (Config->ArrivalSoundMix)
    {
        UGameplayStatics::PushSoundMixModifier(this, Config->ArrivalSoundMix);
    }

    bJumping = false;
    if (Progress)
    {
        Progress->SetCurrentWorld(Destination, true);
    }
    UE_LOG(LogReflectionsWorldJump, Log, TEXT("Jumped to %s at %s."),
        *Config->GetWorldName(Destination).ToString(), *Landing.ToCompactString());
}

void UReflectionsWorldJumpComponent::FinishSeparateMapArrival()
{
    UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    if (!Progress || !Progress->PendingArrival.bValid)
    {
        return;
    }
    const FReflectionsPendingArrival Arrival = Progress->PendingArrival;
    Progress->PendingArrival = FReflectionsPendingArrival();

    FVector Landing = Arrival.Location;
    FText Reason;
    if (!FindSafeLanding(Arrival.Location, Landing, Reason, Arrival.World))
    {
        // Nowhere safe at the old spot: keep the map's own spawn point.
        Landing = GetOwner()->GetActorLocation();
        Progress->ShowWorldMessage(Reason);
    }
    GetOwner()->SetActorRotation(Arrival.Rotation);
    if (APlayerController* PC = GetPlayerController())
    {
        PC->SetControlRotation(Arrival.ControlRotation);
    }
    ArriveAt(Landing, Arrival.World);
}

void UReflectionsWorldJumpComponent::Refuse(const FText& Reason)
{
    if (Reason.IsEmpty())
    {
        return;
    }
    if (Config && Config->RefusedSound)
    {
        UGameplayStatics::PlaySound2D(this, Config->RefusedSound);
    }
    if (UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this))
    {
        Progress->ShowWorldMessage(Reason);
    }
}

// ---- Coat ----------------------------------------------------------------------------------------------------

void UReflectionsWorldJumpComponent::GatherCoatMeshes(TArray<UMeshComponent*>& Out) const
{
    if (!Config || !GetOwner())
    {
        return;
    }
    TArray<AActor*> Actors;
    GetOwner()->GetAttachedActors(Actors, true, true);
    Actors.Insert(GetOwner(), 0);
    for (AActor* Actor : Actors)
    {
        TInlineComponentArray<UMeshComponent*> Meshes(Actor);
        for (UMeshComponent* Mesh : Meshes)
        {
            if (Config->CoatComponentNames.Contains(Mesh->GetFName()))
            {
                Out.Add(Mesh);
            }
        }
    }
}

void UReflectionsWorldJumpComponent::ApplyCoatTint(EReflectionsWorld World)
{
    const FReflectionsWorldInfo* Info = Config ? Config->FindWorld(World) : nullptr;
    if (!Info)
    {
        return;
    }
    TArray<UMeshComponent*> Meshes;
    GatherCoatMeshes(Meshes);
    if (Meshes.Num() == 0)
    {
        // The coat lives on a child actor that may spawn a moment after the pawn.
        TintRetryWorld = World;
        if (TintRetries++ < 20 && GetWorld())
        {
            GetWorld()->GetTimerManager().SetTimer(TintRetryTimer, this, &UReflectionsWorldJumpComponent::RetryCoatTint, 0.25f, false);
        }
        return;
    }
    TintRetries = 0;

    for (UMeshComponent* Mesh : Meshes)
    {
        bool bTinted = false;
        for (int32 Slot = 0; Slot < Mesh->GetNumMaterials(); ++Slot)
        {
            if (Config->TintMaterialSlots.Num() > 0 && !Config->TintMaterialSlots.Contains(Slot))
            {
                continue;
            }
            UMaterialInterface* Material = Mesh->GetMaterial(Slot);
            if (!Material)
            {
                continue;
            }
            for (const FName& Parameter : Config->TintParameterNames)
            {
                FLinearColor Existing;
                if (!Material->GetVectorParameterValue(FHashedMaterialParameterInfo(Parameter), Existing))
                {
                    continue;
                }
                UMaterialInstanceDynamic* Dynamic = Cast<UMaterialInstanceDynamic>(Material);
                if (!Dynamic)
                {
                    Dynamic = Mesh->CreateAndSetMaterialInstanceDynamicFromMaterial(Slot, Material);
                }
                if (Dynamic)
                {
                    Dynamic->SetVectorParameterValue(Parameter, Info->CoatTint);
                    bTinted = true;
                }
                break;
            }
        }
        if (!bTinted && Config->bUseOverlayWhenNoParameter)
        {
            UMaterialInstanceDynamic* Overlay = OverlayTints.FindRef(Mesh);
            if (!Overlay)
            {
                if (UMaterialInterface* Base = Config->OverlayTintMaterial.LoadSynchronous())
                {
                    Overlay = UMaterialInstanceDynamic::Create(Base, this);
                    OverlayTints.Add(Mesh, Overlay);
                }
            }
            if (Overlay)
            {
                Overlay->SetVectorParameterValue(TEXT("Tint"), Info->CoatTint);
                Mesh->SetOverlayMaterial(Overlay);
            }
        }
    }
}

void UReflectionsWorldJumpComponent::RetryCoatTint()
{
    ApplyCoatTint(TintRetryWorld);
}

// ---- HUD and events ------------------------------------------------------------------------------------------

void UReflectionsWorldJumpComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaTime, TickType, TickFunction);
    if (!bStarted)
    {
        return;
    }
    // Respawns and scripted teleports can move the hero between copies; follow them.
    if (!bJumping && Config && Config->Layout == EReflectionsWorldLayout::OffsetCopies)
    {
        UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
        const UReflectionsWorldJumpWorldSubsystem* Worlds = UReflectionsWorldJumpWorldSubsystem::Get(this);
        if (Progress && Worlds)
        {
            const EReflectionsWorld Here = Worlds->GetWorldAtLocation(GetOwner()->GetActorLocation());
            if (Here != Progress->GetCurrentWorld())
            {
                Progress->SetCurrentWorld(Here, true);
            }
        }
    }
    RefreshHud();
}

void UReflectionsWorldJumpComponent::RefreshHud()
{
    if (!Hud || !Config)
    {
        return;
    }
    const UReflectionsWorldJumpSubsystem* Progress = UReflectionsWorldJumpSubsystem::Get(this);
    if (!Progress)
    {
        return;
    }
    FReflectionsWorldHudState State;
    const EReflectionsWorld Here = Progress->GetCurrentWorld();
    const FReflectionsWorldInfo* HereInfo = Config->FindWorld(Here);
    State.WorldName = Config->GetWorldName(Here);
    State.WorldColor = HereInfo ? HereInfo->ThemeColor : FLinearColor::White;
    for (const FReflectionsWorldInfo& Info : Config->Worlds)
    {
        FReflectionsWorldHudCoin Coin;
        Coin.Name = Config->GetWorldName(Info.World);
        Coin.Color = Info.CoinColor;
        Coin.Count = Progress->GetCoins(Info.World);
        State.Coins.Add(Coin);
    }
    State.Pages = Progress->GetPageCount();
    State.PagesForBook = Progress->GetPagesForBook();
    State.bBookComplete = Progress->IsBookComplete();
    State.Keys = Progress->GetKeys();
    State.bHasMagic = GetMagic(State.Magic, State.MaxMagic);
    State.MagicCost = State.MaxMagic * Config->MagicCostFraction;
    State.bMagicDrains = CanDrainMagic();

    for (EReflectionsJumpDirection Direction : { EReflectionsJumpDirection::Up, EReflectionsJumpDirection::Down })
    {
        FReflectionsWorldHudJump& Jump = Direction == EReflectionsJumpDirection::Up ? State.Up : State.Down;
        EReflectionsWorld Destination;
        if (!Config->GetNeighbor(Here, Direction, Destination))
        {
            Jump.bExists = false;
            continue;
        }
        Jump.bExists = true;
        Jump.Keys = GetKeysText(Direction);
        Jump.Destination = Config->GetWorldName(Destination);
        const FReflectionsWorldInfo* Info = Config->FindWorld(Destination);
        Jump.Color = Info ? Info->ThemeColor : FLinearColor::White;
        EReflectionsWorld Coin;
        Jump.bHasCoin = PickCoin(Destination, Coin);
        Jump.CoinName = Config->GetWorldName(Coin);
        Jump.bHasMagic = !State.bHasMagic || State.Magic + 0.5f >= State.MagicCost;
    }
    State.bJumping = bJumping;
    Hud->SetState(State);
}

void UReflectionsWorldJumpComponent::PlayUiSound(USoundBase* Sound, USoundBase* Fallback)
{
    if (USoundBase* ToPlay = Sound ? Sound : Fallback)
    {
        UGameplayStatics::PlaySound2D(this, ToPlay);
    }
}

void UReflectionsWorldJumpComponent::UpdateMusic(EReflectionsWorld World)
{
    const FReflectionsWorldInfo* Info = Config ? Config->FindWorld(World) : nullptr;
    USoundBase* Loop = (Config && Config->bPlayWorldMusic && Info) ? Info->Music.Get() : nullptr;
    if (Music && Loop && Music->GetSound() == Loop && Music->IsPlaying())
    {
        Music->AdjustVolume(0.0f, 1.0f);
        return;
    }
    if (Music)
    {
        Music->FadeOut(Config ? Config->MusicFadeOutTime : 0.5f, 0.0f);
        Music = nullptr;
    }
    if (Loop)
    {
        Music = UGameplayStatics::CreateSound2D(this, Loop, 1.0f, 1.0f, 0.0f, nullptr, false, true);
        if (Music)
        {
            Music->FadeIn(Config->MusicFadeInTime, 1.0f);
        }
    }
}

void UReflectionsWorldJumpComponent::HandleWorldChanged(EReflectionsWorld From, EReflectionsWorld To)
{
    ApplyCoatTint(To);
    UpdateMusic(To);
    if (Hud && Config)
    {
        const FReflectionsWorldInfo* Info = Config->FindWorld(To);
        Hud->ShowBanner(Config->GetWorldName(To), Info ? Info->ThemeColor : FLinearColor::White);
    }
    RefreshHud();
}

void UReflectionsWorldJumpComponent::HandleMessage(const FText& Message)
{
    if (Hud)
    {
        Hud->ShowMessage(Message, FLinearColor(1.0f, 0.82f, 0.55f));
    }
}

void UReflectionsWorldJumpComponent::HandleBookComplete()
{
    if (Hud)
    {
        Hud->ShowBanner(LOCTEXT("BookComplete", "The book is whole"), FLinearColor(1.0f, 0.85f, 0.4f),
            LOCTEXT("BookCompleteSub", "Three pages, one spell. Now stop him."));
    }
}

void UReflectionsWorldJumpComponent::HandlePagesChanged(int32 Pages, int32 PagesForBook)
{
    if (Config)
    {
        PlayUiSound(Config->PageSound, Config->PickupSound);
    }
    RefreshHud();
}

void UReflectionsWorldJumpComponent::HandleCoinsChanged(EReflectionsWorld World, int32 Count)
{
    // Only a gain plays the pickup sound; spending a coin on a jump is covered by the jump sound.
    const int32 Before = SeenCoins.FindRef(World);
    SeenCoins.Add(World, Count);
    if (Config && Count > Before)
    {
        PlayUiSound(Config->PickupSound);
    }
    RefreshHud();
}

void UReflectionsWorldJumpComponent::HandleKeyAdded(FName KeyId)
{
    if (Config)
    {
        PlayUiSound(Config->KeySound, Config->PickupSound);
    }
    RefreshHud();
}

#undef LOCTEXT_NAMESPACE
