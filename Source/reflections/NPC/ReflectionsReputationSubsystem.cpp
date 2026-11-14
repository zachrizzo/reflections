#include "NPC/ReflectionsReputationSubsystem.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "GameFramework/Pawn.h"

void UReflectionsReputationSubsystem::OnWorldBeginPlay(UWorld& World)
{
    Super::OnWorldBeginPlay(World);
    if (UReflectionsSpellEventSubsystem* Events = World.GetSubsystem<UReflectionsSpellEventSubsystem>())
        Events->OnSpellHit.AddUniqueDynamic(this, &UReflectionsReputationSubsystem::HandleSpellHit);
}
void UReflectionsReputationSubsystem::Deinitialize()
{
    if (UWorld* World = GetWorld())
        if (UReflectionsSpellEventSubsystem* Events = World->GetSubsystem<UReflectionsSpellEventSubsystem>())
            Events->OnSpellHit.RemoveDynamic(this, &UReflectionsReputationSubsystem::HandleSpellHit);
    Scores.Empty();
    Super::Deinitialize();
}
float UReflectionsReputationSubsystem::GetReputation(AActor* Player) const
{
    if (!IsValid(Player)) return 0.0f;
    if (const float* Score = Scores.Find(Player)) return *Score;
    return 0.0f;
}
void UReflectionsReputationSubsystem::AdjustReputation(AActor* Player, float Delta)
{
    if (!IsValid(Player) || !FMath::IsFinite(Delta)) return;
    const float Old = GetReputation(Player);
    const float New = FMath::Clamp(Old + Delta, -100.0f, 100.0f);
    Scores.Add(Player, New);
    if (!FMath::IsNearlyEqual(Old, New)) OnReputationChanged.Broadcast(Player, Old, New);
}
void UReflectionsReputationSubsystem::HandleSpellHit(const FReflectionsSpellHitData& Hit)
{
    const APawn* Caster = Cast<APawn>(Hit.Caster);
    if (Caster && Caster->IsPlayerControlled() && IsValid(Hit.Target) &&
        Hit.Target->FindComponentByClass<UReflectionsNpcReactionComponent>())
        AdjustReputation(Hit.Caster, -8.0f);
}
