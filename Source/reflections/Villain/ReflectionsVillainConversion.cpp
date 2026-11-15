#include "Villain/ReflectionsVillainConversion.h"

#include "Villain/ReflectionsVillainConfig.h"
#include "Villain/ReflectionsVillainFx.h"
#include "Villain/ReflectionsVillainPossession.h"
#include "Villain/ReflectionsVillainSubsystem.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "NiagaraComponent.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

DEFINE_LOG_CATEGORY_STATIC(LogReflectionsConversion, Log, All);

namespace
{
    const FName ConversionSlot(TEXT("DefaultSlot"));
    const TCHAR* TackleFolder = TEXT("/Game/Characters/UEFN_Mannequin/Animations/Interactions/Tackle/");
    const TCHAR* GetUpFolder = TEXT("/Game/Characters/UEFN_Mannequin/Animations/Ragdoll/");
    /** Kimodo takes made for this (spell-crafting session): lying possessed + neck wrench, stiff rise, kneeling attacker. */
    const TCHAR* ConversionFolder = TEXT("/Game/Villain/Conversion/");
    constexpr float PossessedRate = 1.15f;
    constexpr float RiseRate = 1.2f;
    /** The neck wrench in the possessed clips (seconds into the clip): the wisp lands on it. */
    constexpr float WrenchTime = 1.25f;

    UAnimSequenceBase* LoadSequence(const FString& Folder, const FString& Name)
    {
        return LoadObject<UAnimSequenceBase>(nullptr, *FString::Printf(TEXT("%s%s.%s"), *Folder, *Name, *Name), nullptr, LOAD_NoWarn | LOAD_Quiet);
    }

    FTransform RootAt(const UAnimSequenceBase* Anim, double Time)
    {
        const UAnimSequence* Sequence = Cast<UAnimSequence>(Anim);
        return Sequence ? Sequence->ExtractRootTrackTransform(FAnimExtractContext(Time), nullptr) : FTransform::Identity;
    }

    /** With root motion the component follows the root, so it has to start where the root starts. */
    bool ComponentFollowsRoot(const UAnimSequenceBase* Anim)
    {
        const UAnimSequence* Sequence = Cast<UAnimSequence>(Anim);
        return Sequence && Sequence->bEnableRootMotion && Sequence->RootMotionRootLock != ERootMotionRootLock::AnimFirstFrame;
    }

    UAnimMontage* PlayOn(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Anim, float Rate, float BlendIn, float BlendOut)
    {
        UAnimInstance* Instance = Mesh ? Mesh->GetAnimInstance() : nullptr;
        if (!Instance || !Anim)
        {
            return nullptr;
        }
        return Instance->PlaySlotAnimationAsDynamicMontage(Anim, ConversionSlot, BlendIn, BlendOut, Rate, 1, -1.0f, 0.0f);
    }
}

AReflectionsVillainConversion::AReflectionsVillainConversion()
{
    PrimaryActorTick.bCanEverTick = true;
    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    RootComponent = Root;
    SetActorEnableCollision(false);
}

USkeletalMeshComponent* AReflectionsVillainConversion::Driver(const ACharacter* Character)
{
    USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : nullptr;
    return Mesh && Mesh->GetAnimInstance() ? Mesh : nullptr;
}

bool AReflectionsVillainConversion::Involves(const AActor* Actor) const
{
    return Actor && (Attacker.Get() == Actor || Victim.Get() == Actor || AttackerActor.Get() == Actor || VictimActor.Get() == Actor);
}

void AReflectionsVillainConversion::ReleaseHold(AActor* Npc)
{
    // The NPC system holds both bodies while we drive them (EndScriptedHold; called by name so it can land later).
    UReflectionsNpcSubsystem* Npcs = Npc ? UReflectionsNpcSubsystem::Get(Npc) : nullptr;
    UReflectionsNpcReactionComponent* Component = Npcs ? Npcs->FindNpc(Npc) : nullptr;
    if (UFunction* End = Component ? Component->FindFunction(TEXT("EndScriptedHold")) : nullptr)
    {
        if (End->ParmsSize == 0)
        {
            Component->ProcessEvent(End, nullptr);
        }
    }
}

bool AReflectionsVillainConversion::PickTackle()
{
    const USkeletalMeshComponent* AttackerMesh = Driver(Attacker.Get());
    const USkeletalMeshComponent* VictimMesh = Driver(Victim.Get());
    if (!AttackerMesh || !VictimMesh)
    {
        return false;
    }
    // Where the attacker is, seen from the victim: pick the tackle whose recorded approach matches best.
    const FVector Actual = VictimMesh->GetComponentTransform().InverseTransformPosition(AttackerMesh->GetComponentLocation()).GetSafeNormal2D();
    static const TCHAR* Directions[] = {TEXT("F"), TEXT("B"), TEXT("L"), TEXT("R")};
    static const TCHAR* Feet[] = {TEXT("Lfoot"), TEXT("Rfoot")};
    const int32 FootPick = FMath::RandRange(0, 1);
    float Best = -2.0f;
    for (const TCHAR* Direction : Directions)
    {
        for (int32 Foot = 0; Foot < 2; ++Foot)
        {
            const FString Base = FString::Printf(TEXT("M_relaxed_ragdoll_tackle_run_%s_%s"), Direction, Feet[Foot]);
            UAnimSequenceBase* A = LoadSequence(TackleFolder, Base + TEXT("_A"));
            UAnimSequenceBase* V = LoadSequence(TackleFolder, Base + TEXT("_V"));
            if (!A || !V)
            {
                continue;
            }
            const FTransform Relative = RootAt(A, 0.0).GetRelativeTransform(RootAt(V, 0.0));
            const float Score = FVector::DotProduct(Relative.GetLocation().GetSafeNormal2D(), Actual) + (Foot == FootPick ? 0.01f : 0.0f);
            if (Score > Best)
            {
                Best = Score;
                AttackerAnim = A;
                VictimAnim = V;
                Variant = Base;
            }
        }
    }
    if (!AttackerAnim || !VictimAnim)
    {
        return false;
    }
    // The possession itself (Kimodo takes, both lying on the back) and the kneeling attacker.
    PossessedAnim = LoadSequence(ConversionFolder, FMath::RandBool() ? TEXT("AS_Conversion_Victim_Possessed_A") : TEXT("AS_Conversion_Victim_Possessed_B"));
    RiseAnim = LoadSequence(ConversionFolder, FMath::RandBool() ? TEXT("AS_Conversion_Victim_Rise_E") : TEXT("AS_Conversion_Victim_Rise_F"));
    KneelAnim = LoadSequence(ConversionFolder, FMath::FRand() < 0.7f ? TEXT("AS_Conversion_Attacker_B") : TEXT("AS_Conversion_Attacker_C"));
    // Fallback without them: hold the first (lying) frame of a get-up clip.
    const bool bOnFront = Variant.Contains(TEXT("_B_"));
    GetUpAnim = LoadSequence(GetUpFolder, bOnFront ? TEXT("M_ragdoll_getup_stand_F") : TEXT("M_ragdoll_getup_stand_B"));
    return (PossessedAnim && RiseAnim) || GetUpAnim;
}

void AReflectionsVillainConversion::AlignAttacker()
{
    ACharacter* A = Attacker.Get();
    USkeletalMeshComponent* AttackerMesh = Driver(A);
    USkeletalMeshComponent* VictimMesh = Driver(Victim.Get());
    if (!AttackerMesh || !VictimMesh)
    {
        return;
    }
    // Both clips were recorded in one scene. Keep the victim where it is and put the attacker where the clip pair
    // says it starts, relative to the victim.
    const FTransform VictimWorld = VictimMesh->GetComponentTransform();
    FTransform AttackerWorld = VictimWorld;
    if (ComponentFollowsRoot(AttackerAnim) && ComponentFollowsRoot(VictimAnim))
    {
        AttackerWorld = RootAt(AttackerAnim, 0.0).GetRelativeTransform(RootAt(VictimAnim, 0.0)) * VictimWorld;
    }
    const FTransform ActorWorld = AttackerMesh->GetRelativeTransform().Inverse() * AttackerWorld;
    FVector Location = ActorWorld.GetLocation();
    Location.Z = A->GetActorLocation().Z;
    const FRotator Rotation(0.0f, ActorWorld.Rotator().Yaw, 0.0f);
    ReflectionsVillainFx::Impact(GetWorld(), A->GetActorLocation(), ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 0.6f, 2.0f);
    A->SetActorLocationAndRotation(Location, Rotation, false, nullptr, ETeleportType::TeleportPhysics);
    if (AController* Controller = A->GetController())
    {
        Controller->SetControlRotation(Rotation);
    }
}

float AReflectionsVillainConversion::Begin(AActor* AttackerNpc, AActor* VictimNpc, ACharacter* InAttacker, ACharacter* InVictim)
{
    AttackerActor = AttackerNpc;
    VictimActor = VictimNpc;
    Attacker = InAttacker;
    Victim = InVictim;
    if (!PickTackle())
    {
        UE_LOG(LogReflectionsConversion, Warning, TEXT("Conversion: no driver mesh or clips for %s -> %s"), *GetNameSafe(AttackerNpc), *GetNameSafe(VictimNpc));
        return 0.0f;
    }
    for (ACharacter* Character : {InAttacker, InVictim})
    {
        if (UCharacterMovementComponent* Movement = Character->GetCharacterMovement())
        {
            Movement->StopMovementImmediately();
        }
    }
    AlignAttacker();
    UAnimMontage* AttackerMontage = PlayOn(Driver(InAttacker), AttackerAnim, 1.0f, 0.1f, 0.25f);
    UAnimMontage* VictimMontage = PlayOn(Driver(InVictim), VictimAnim, 1.0f, 0.1f, 0.0f);
    if (!AttackerMontage || !VictimMontage)
    {
        UE_LOG(LogReflectionsConversion, Warning, TEXT("Conversion: %s would not play on the driver meshes (skeleton or slot)."), *Variant);
        return 0.0f;
    }
    // The victim clip hands over to ragdoll near its end; take the possession pose a little before that instead.
    DownAt = FMath::Max(0.4f, VictimAnim->GetPlayLength() * 0.82f);
    if (PossessedAnim && RiseAnim)
    {
        WispAt = DownAt + 0.15f;
        TurnAt = DownAt + WrenchTime / PossessedRate;
        RiseAt = DownAt + PossessedAnim->GetPlayLength() / PossessedRate - 0.25f;
        DoneAt = RiseAt + RiseAnim->GetPlayLength() / RiseRate;
    }
    else
    {
        WispAt = DownAt + 0.3f;
        TurnAt = WispAt + 1.4f;
        RiseAt = TurnAt;
        DoneAt = RiseAt + GetUpAnim->GetPlayLength() / 0.85f;
    }
    WispTime = FMath::Max(0.4f, TurnAt - WispAt);
    Phase = EPhase::Tackle;
    Clock = 0.0f;
    ReflectionsVillainFx::Sound(GetWorld(), ReflectionsVillainAssets::PossessSound(), InAttacker->GetActorLocation(), 0.8f);
    UE_LOG(LogReflectionsConversion, Log, TEXT("Conversion: %s tackles %s (%s, %s)"), *GetNameSafe(AttackerNpc), *GetNameSafe(VictimNpc), *Variant,
        PossessedAnim ? *PossessedAnim->GetName() : TEXT("get-up fallback"));
    return DoneAt + 0.2f;
}

void AReflectionsVillainConversion::StartDown()
{
    Phase = EPhase::Down;
    USkeletalMeshComponent* VictimMesh = Driver(Victim.Get());
    if (PossessedAnim)
    {
        // Pinned on its back: the body jerks, then the neck wrenches as the dark goes in.
        PlayOn(VictimMesh, PossessedAnim, PossessedRate, 0.3f, 0.25f);
        // The attacker kneels over it, arm out, pouring the wisp in.
        if (KneelAnim)
        {
            PlayOn(Driver(Attacker.Get()), KneelAnim, 1.0f, 0.35f, 0.5f);
        }
    }
    else
    {
        GetUpMontage = PlayOn(VictimMesh, GetUpAnim, 1.0f, 0.3f, 0.3f);
        if (GetUpMontage)
        {
            VictimMesh->GetAnimInstance()->Montage_Pause(GetUpMontage);
        }
    }
    ReflectionsVillainFx::Sound(GetWorld(), ReflectionsVillainAssets::SlamSound(), ChestLocation(), 0.6f, 1.2f);
}

FVector AReflectionsVillainConversion::HandLocation() const
{
    const USkeletalMeshComponent* Mesh = Driver(Attacker.Get());
    if (Mesh && Mesh->GetBoneIndex(TEXT("hand_r")) != INDEX_NONE)
    {
        return Mesh->GetSocketLocation(TEXT("hand_r"));
    }
    return Attacker.IsValid() ? Attacker->GetActorLocation() + FVector(0.0f, 0.0f, 40.0f) : GetActorLocation();
}

FVector AReflectionsVillainConversion::ChestLocation() const
{
    const USkeletalMeshComponent* Mesh = Driver(Victim.Get());
    if (Mesh && Mesh->GetBoneIndex(TEXT("spine_05")) != INDEX_NONE)
    {
        return Mesh->GetSocketLocation(TEXT("spine_05"));
    }
    return Victim.IsValid() ? Victim->GetActorLocation() : GetActorLocation();
}

void AReflectionsVillainConversion::StartWisp()
{
    Phase = EPhase::Wisp;
    WispStart = HandLocation();
    SetActorLocation(WispStart);
    UWorld* World = GetWorld();
    // A black stream: the shroud's smoke and torn wisps, packed tight, with a faint violet heart.
    Smoke = ReflectionsVillainFx::Shroud(World, Root, NAME_None, FVector(0.0f, 0.0f, -30.0f), 0.35f, 3.0f);
    Light = NewObject<UPointLightComponent>(this, TEXT("WispLight"));
    Light->SetupAttachment(Root);
    Light->SetLightColor(ReflectionsVillainColors::Violet);
    Light->SetIntensity(1500.0f);
    Light->SetAttenuationRadius(260.0f);
    Light->SetCastShadows(false);
    Light->RegisterComponent();
    ReflectionsVillainFx::Sound(World, ReflectionsVillainAssets::VoiceSound(), WispStart, 0.7f);
}

void AReflectionsVillainConversion::Turn()
{
    if (!VictimActor.IsValid())
    {
        Finish(false);
        return;
    }
    if (Smoke)
    {
        Smoke->Deactivate();
    }
    if (Light)
    {
        Light->SetIntensity(0.0f);
    }
    ReflectionsVillainFx::Impact(GetWorld(), ChestLocation(), ReflectionsVillainColors::Violet, ReflectionsVillainColors::Lilac, 0.9f, 3.0f);
    // Black eyes, black aura, and the NPC system turns it into an enemy (archetype Infected).
    UReflectionsVillainPossessionComponent::Apply(VictimActor.Get(), EReflectionsVillainInfection::Infected, AttackerActor.Get());
    if (PossessedAnim)
    {
        // The possessed clip plays on (it settles after the wrench); the rise follows at RiseAt.
        Phase = EPhase::Turned;
        return;
    }
    Phase = EPhase::Rise;
    if (UAnimInstance* Instance = Driver(Victim.Get()) ? Driver(Victim.Get())->GetAnimInstance() : nullptr)
    {
        if (GetUpMontage)
        {
            Instance->Montage_SetPosition(GetUpMontage, 0.0f);
            Instance->Montage_SetPlayRate(GetUpMontage, 0.85f);
            Instance->Montage_Resume(GetUpMontage);
        }
    }
}

void AReflectionsVillainConversion::StartRise()
{
    Phase = EPhase::Rise;
    PlayOn(Driver(Victim.Get()), RiseAnim, RiseRate, 0.25f, 0.3f);
    if (UAnimInstance* Instance = Driver(Attacker.Get()) ? Driver(Attacker.Get())->GetAnimInstance() : nullptr)
    {
        Instance->Montage_Stop(0.5f);
    }
}

void AReflectionsVillainConversion::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (bFinished)
    {
        return;
    }
    ACharacter* A = Attacker.Get();
    ACharacter* V = Victim.Get();
    const bool bTaken = Phase == EPhase::Turned || Phase == EPhase::Rise;
    // Abort if either dies or vanishes: the victim stays clean unless the wisp already landed.
    if (!IsValid(A) || !IsValid(V) || !VictimActor.IsValid() || !ReflectionsVillainFx::IsAlive(VictimActor.Get())
        || (!bTaken && (!AttackerActor.IsValid() || !ReflectionsVillainFx::IsAlive(AttackerActor.Get()))))
    {
        Finish(bTaken);
        return;
    }
    Clock += DeltaSeconds;
    switch (Phase)
    {
    case EPhase::Tackle:
        if (Clock >= DownAt)
        {
            StartDown();
        }
        break;
    case EPhase::Down:
        if (Clock >= WispAt)
        {
            StartWisp();
        }
        break;
    case EPhase::Wisp:
    {
        const float T = FMath::Clamp((Clock - WispAt) / WispTime, 0.0f, 1.0f);
        const float Eased = T * T * (3.0f - 2.0f * T);
        SetActorLocation(FMath::Lerp(WispStart, ChestLocation(), Eased) + FVector(0.0f, 0.0f, FMath::Sin(T * PI) * 45.0f));
        // Fallback only: without the possessed clip, the pinned body convulses by scrubbing the held frame.
        if (!PossessedAnim && GetUpMontage && Clock >= NextTwitch)
        {
            NextTwitch = Clock + FMath::FRandRange(0.06f, 0.16f);
            if (UAnimInstance* Instance = Driver(V)->GetAnimInstance())
            {
                Instance->Montage_SetPosition(GetUpMontage, FMath::FRandRange(0.0f, 0.06f + 0.08f * T));
            }
        }
        if (T >= 1.0f)
        {
            Turn();
        }
        break;
    }
    case EPhase::Turned:
        if (Clock >= RiseAt)
        {
            StartRise();
        }
        break;
    case EPhase::Rise:
        if (Clock >= DoneAt)
        {
            Finish(true);
        }
        break;
    default:
        break;
    }
}

void AReflectionsVillainConversion::Finish(bool bConverted)
{
    if (bFinished)
    {
        return;
    }
    bFinished = true;
    Phase = EPhase::Done;
    if (!bConverted)
    {
        ReleaseHold(AttackerActor.Get());
        ReleaseHold(VictimActor.Get());
        // Let both bodies go: stop our clips so their own animation takes over again.
        for (ACharacter* Character : {Attacker.Get(), Victim.Get()})
        {
            if (UAnimInstance* Instance = Driver(Character) ? Driver(Character)->GetAnimInstance() : nullptr)
            {
                Instance->Montage_Stop(0.25f);
            }
        }
    }
    if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld()))
    {
        Villain->ConversionFinished(this, bConverted);
    }
    if (Smoke)
    {
        Smoke->Deactivate();
    }
    SetLifeSpan(1.5f);
}

void AReflectionsVillainConversion::EndPlay(const EEndPlayReason::Type Reason)
{
    if (!bFinished)
    {
        bFinished = true;
        if (UReflectionsVillainSubsystem* Villain = UReflectionsVillainSubsystem::Get(GetWorld()))
        {
            Villain->ConversionFinished(this, false);
        }
    }
    Super::EndPlay(Reason);
}
