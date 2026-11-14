#include "NPC/ReflectionsNpcPopulationSubsystem.h"
#include "NPC/ReflectionsNpcReactionComponent.h"
#include "NPC/ReflectionsNpcCombatComponent.h"
#include "Hero/ReflectionsSpellCombat.h"
#include "Components/CapsuleComponent.h"
#include "EngineUtils.h"

void UReflectionsNpcPopulationSubsystem::OnWorldBeginPlay(UWorld& World)
{
    Super::OnWorldBeginPlay(World);
    ReactiveActors.Reset();
    for (TActorIterator<AActor> It(&World); It; ++It)
    {
        AActor* Actor = *It;
        if (!Actor || !Actor->ActorHasTag(TEXT("NPC_Reactive"))) continue;
        ReactiveActors.Add(Actor);
        if (!Actor->FindComponentByClass<UReflectionsHealthComponent>())
        {
            UReflectionsHealthComponent* Health = NewObject<UReflectionsHealthComponent>(Actor, TEXT("RuntimeNpcHealth"));
            Health->RegisterComponent();
        }
        if (!Actor->FindComponentByClass<UReflectionsNpcReactionComponent>())
        {
            UReflectionsNpcReactionComponent* Brain = NewObject<UReflectionsNpcReactionComponent>(Actor, TEXT("RuntimeNpcReaction"));
            if (Actor->ActorHasTag(TEXT("NPC_Timid"))) Brain->Disposition = EReflectionsNpcDisposition::Timid;
            else if (Actor->ActorHasTag(TEXT("NPC_Brave"))) Brain->Disposition = EReflectionsNpcDisposition::Brave;
            else if (Actor->ActorHasTag(TEXT("NPC_Guard"))) Brain->Disposition = EReflectionsNpcDisposition::Guard;
            else if (Actor->ActorHasTag(TEXT("NPC_Hostile"))) Brain->Disposition = EReflectionsNpcDisposition::Hostile;
            Brain->bEnableRagdollOnDeath = Actor->ActorHasTag(TEXT("NPC_Ragdoll"));
            Brain->RegisterComponent();
        }
        if (Actor->ActorHasTag(TEXT("NPC_CombatEnemy")) && !Actor->FindComponentByClass<UReflectionsNpcCombatComponent>())
        {
            UReflectionsNpcCombatComponent* Combat = NewObject<UReflectionsNpcCombatComponent>(Actor, TEXT("RuntimeNpcCombat"));
            Combat->RegisterComponent();
        }
        // Actor-only MetaHuman assemblies often have no hit collision; add an opt-in
        // query proxy without changing their saved skeletons or outfits.
        if (Actor->ActorHasTag(TEXT("NPC_HitProxy")) && Actor->GetRootComponent())
        {
            FVector Center, Extent; Actor->GetActorBounds(false, Center, Extent);
            UCapsuleComponent* Proxy = NewObject<UCapsuleComponent>(Actor, TEXT("RuntimeNpcHitProxy"));
            Proxy->SetupAttachment(Actor->GetRootComponent());
            const float Radius = FMath::Clamp(FMath::Max(Extent.X, Extent.Y) * .55f, 25.0f, 55.0f);
            Proxy->InitCapsuleSize(Radius, FMath::Clamp(Extent.Z, 70.0f, 115.0f));
            Proxy->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
            Proxy->SetCollisionObjectType(ECC_Pawn);
            Proxy->SetCollisionResponseToAllChannels(ECR_Ignore);
            Proxy->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
            Proxy->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
            Proxy->RegisterComponent();
            Proxy->SetWorldLocation(Center);
        }
    }
}
