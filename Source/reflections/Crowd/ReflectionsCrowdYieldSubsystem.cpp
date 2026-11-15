#include "Crowd/ReflectionsCrowdYieldSubsystem.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcSubsystem.h"

#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"

DECLARE_CYCLE_STAT(TEXT("Crowd yield"), STAT_ReflectionsCrowdYield, STATGROUP_Game);

namespace
{
    TAutoConsoleVariable<int32> CVarYieldEnable(TEXT("Crowd.Yield.Enable"), 1,
        TEXT("Calm civilians step out of the path of marching squads (and a running player)."));
    TAutoConsoleVariable<float> CVarYieldLookAhead(TEXT("Crowd.Yield.LookAhead"), 550.0f,
        TEXT("How far ahead of a mover (cm) civilians start making way."));
    TAutoConsoleVariable<float> CVarYieldSoldierWidth(TEXT("Crowd.Yield.SoldierHalfWidth"), 240.0f,
        TEXT("Half-width (cm) of the lane civilians clear in front of each moving soldier."));
    TAutoConsoleVariable<int32> CVarYieldToPlayer(TEXT("Crowd.Yield.ToPlayer"), 1,
        TEXT("Civilians also make way for the player when the player runs."));
    TAutoConsoleVariable<float> CVarYieldPlayerWidth(TEXT("Crowd.Yield.PlayerHalfWidth"), 150.0f,
        TEXT("Half-width (cm) of the lane civilians clear in front of a running player."));
    TAutoConsoleVariable<float> CVarYieldPlayerMinSpeed(TEXT("Crowd.Yield.PlayerMinSpeed"), 320.0f,
        TEXT("The player counts as running above this speed (cm/s)."));
    TAutoConsoleVariable<float> CVarYieldSpeed(TEXT("Crowd.Yield.StepSpeed"), 240.0f,
        TEXT("Speed (cm/s) a civilian uses to step aside."));
    TAutoConsoleVariable<int32> CVarYieldDebug(TEXT("Crowd.Yield.Debug"), 0,
        TEXT("Draw the lanes and each civilian's step-aside direction."));

    const FName SoldierTag(TEXT("NPC_Soldier"));
    constexpr double RefreshPeriod = 0.5;
    constexpr float SoldierMinSpeed = 40.0f;
    constexpr float BehindAllowance = 120.0f;
    constexpr float HoldSeconds = 0.45f;

    bool YieldsToSquads(const UReflectionsNpcReactionComponent& Brain)
    {
        switch (Brain.Disposition)
        {
        case EReflectionsNpcDisposition::Enemy:
        case EReflectionsNpcDisposition::Infected:
        case EReflectionsNpcDisposition::VillainHost:
            return false;
        default:
            return true;
        }
    }

    struct FActiveMover
    {
        const ACharacter* Character;
        FVector Location;
        FVector Heading;
        FVector Side;
        float HalfWidth;
    };
}

bool UReflectionsCrowdYieldSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UReflectionsCrowdYieldSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsCrowdYieldSubsystem, STATGROUP_Tickables);
}

bool UReflectionsCrowdYieldSubsystem::IsYielding(const AActor* Npc) const
{
    for (const FYielder& Yielder : Yielders)
        if (Yielder.Npc.Get() == Npc) return Yielder.HoldRemaining > 0.0f;
    return false;
}

void UReflectionsCrowdYieldSubsystem::Refresh()
{
    UReflectionsNpcSubsystem* Npcs = UReflectionsNpcSubsystem::Get(this);
    Movers.Reset();
    if (!Npcs)
    {
        Yielders.Reset();
        return;
    }
    TArray<FYielder> Next;
    for (AActor* Actor : Npcs->GetNpcActors())
    {
        UReflectionsNpcReactionComponent* Brain = Npcs->FindNpc(Actor);
        if (!Brain) continue;
        if (Actor->ActorHasTag(SoldierTag))
        {
            if (ACharacter* Mover = Brain->GetMovementCharacter())
                Movers.Add({ Mover, CVarYieldSoldierWidth.GetValueOnGameThread() });
            continue;
        }
        if (!YieldsToSquads(*Brain)) continue;
        if (const FYielder* Existing = Yielders.FindByPredicate([Actor](const FYielder& Y) { return Y.Npc.Get() == Actor; }))
        {
            Next.Add(*Existing);
            continue;
        }
        FYielder& Yielder = Next.AddDefaulted_GetRef();
        Yielder.Npc = Actor;
        Yielder.Brain = Brain;
        Yielder.Seed = GetTypeHash(Actor->GetFName());
    }
    Yielders = MoveTemp(Next);
    if (CVarYieldToPlayer.GetValueOnGameThread() != 0)
    {
        if (const APlayerController* Controller = GetWorld()->GetFirstPlayerController())
            if (ACharacter* Player = Cast<ACharacter>(Controller->GetPawn()))
                Movers.Add({ Player, CVarYieldPlayerWidth.GetValueOnGameThread() });
    }
}

void UReflectionsCrowdYieldSubsystem::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    YieldingCount = 0;
    UWorld* World = GetWorld();
    if (!World || !World->HasBegunPlay() || CVarYieldEnable.GetValueOnGameThread() == 0)
    {
        return;
    }
    SCOPE_CYCLE_COUNTER(STAT_ReflectionsCrowdYield);
    if (World->GetTimeSeconds() >= NextRefresh)
    {
        NextRefresh = World->GetTimeSeconds() + RefreshPeriod;
        Refresh();
    }
    if (Yielders.IsEmpty())
    {
        return;
    }

    // Movers that are actually moving, once per frame.
    TArray<FActiveMover, TInlineAllocator<16>> Active;
    const APawn* PlayerPawn = World->GetFirstPlayerController() ? World->GetFirstPlayerController()->GetPawn() : nullptr;
    const float PlayerMinSpeed = CVarYieldPlayerMinSpeed.GetValueOnGameThread();
    for (const FMover& Mover : Movers)
    {
        const ACharacter* Character = Mover.Character.Get();
        if (!Character) continue;
        const FVector Velocity(Character->GetVelocity().X, Character->GetVelocity().Y, 0.0);
        const float Speed = Velocity.Size();
        if (Speed < (Character == PlayerPawn ? PlayerMinSpeed : SoldierMinSpeed)) continue;
        const FVector Heading = Velocity / Speed;
        Active.Add({ Character, Character->GetActorLocation(), Heading, FVector(-Heading.Y, Heading.X, 0.0), Mover.HalfWidth });
    }

    const float LookAhead = FMath::Max(100.0f, CVarYieldLookAhead.GetValueOnGameThread());
    const float StepSpeed = CVarYieldSpeed.GetValueOnGameThread();
    const bool bDebug = CVarYieldDebug.GetValueOnGameThread() != 0;
    for (FYielder& Yielder : Yielders)
    {
        UReflectionsNpcReactionComponent* Brain = Yielder.Brain.Get();
        ACharacter* Walker = Brain ? Brain->GetMovementCharacter() : nullptr;
        // Only calm or merely alert NPCs make way; fleeing, investigating, fighting or downed NPCs belong to the brain.
        const bool bFree = Walker && (Brain->Reaction == EReflectionsNpcReaction::Calm || Brain->Reaction == EReflectionsNpcReaction::Alert);
        if (!bFree || !Walker->GetCharacterMovement() || !Walker->GetCharacterMovement()->IsMovingOnGround())
        {
            Yielder.HoldRemaining = 0.0f;
            continue;
        }
        const FVector Here = Walker->GetActorLocation();
        FVector Push = FVector::ZeroVector;
        float Urgency = 0.0f;
        for (const FActiveMover& Mover : Active)
        {
            if (Mover.Character == Walker) continue;
            const FVector Offset(Here.X - Mover.Location.X, Here.Y - Mover.Location.Y, 0.0);
            const float Along = FVector::DotProduct(Offset, Mover.Heading);
            if (Along < -BehindAllowance || Along > LookAhead) continue;
            const float Lateral = FVector::DotProduct(Offset, Mover.Side);
            // A little hysteresis so a civilian at the lane edge does not dither in and out of it.
            const float HalfWidth = Mover.HalfWidth + (Yielder.HoldRemaining > 0.0f ? 60.0f : 0.0f);
            if (FMath::Abs(Lateral) > HalfWidth) continue;
            const float SideSign = FMath::Abs(Lateral) > 15.0f ? FMath::Sign(Lateral) : ((Yielder.Seed & 1) ? 1.0f : -1.0f);
            const float Closeness = 1.0f - FMath::Clamp(Along / LookAhead, 0.0f, 1.0f);
            // Step sideways out of the lane, and a little further along it when the mover is close.
            Push += (Mover.Side * SideSign + Mover.Heading * 0.3f * Closeness) * (0.5f + Closeness);
            Urgency = FMath::Max(Urgency, Closeness);
            if (bDebug)
            {
                DrawDebugLine(World, Mover.Location, Mover.Location + Mover.Heading * LookAhead, FColor::Orange, false, 0.0f, 0, 2.0f);
            }
        }
        if (!Push.IsNearlyZero())
        {
            Yielder.LastDirection = Push.GetSafeNormal2D();
            Yielder.HoldRemaining = HoldSeconds;
        }
        else if (Yielder.HoldRemaining > 0.0f)
        {
            Yielder.HoldRemaining -= DeltaTime;
            Urgency = 0.3f;
        }
        if (Yielder.HoldRemaining <= 0.0f || Yielder.LastDirection.IsNearlyZero()) continue;

        // Added on top of the NPC's own movement input this frame; CharacterMovement sums and clamps them.
        UCharacterMovementComponent* Movement = Walker->GetCharacterMovement();
        const float Scale = FMath::Clamp(StepSpeed * FMath::Lerp(0.7f, 1.0f, Urgency) / FMath::Max(1.0f, Movement->GetMaxSpeed()), 0.1f, 1.0f);
        Walker->AddMovementInput(Yielder.LastDirection, Scale, true);
        ++YieldingCount;
        if (bDebug)
        {
            DrawDebugDirectionalArrow(World, Here, Here + Yielder.LastDirection * 150.0f, 30.0f, FColor::Cyan, false, 0.0f, 0, 3.0f);
        }
    }
    if (YieldingCount > 0) ++YieldFrames;
}
