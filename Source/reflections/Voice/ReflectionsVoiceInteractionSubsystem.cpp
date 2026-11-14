#include "Voice/ReflectionsVoiceInteractionSubsystem.h"
#include "Voice/ReflectionsRealtimeVoiceComponent.h"
#include "Components/InputComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "InputCoreTypes.h"

bool UReflectionsVoiceInteractionSubsystem::IsTickable() const
{
    return GetWorld() && GetWorld()->IsGameWorld() && !HasAnyFlags(RF_ClassDefaultObject);
}
void UReflectionsVoiceInteractionSubsystem::Tick(float)
{
    if (Input || !GetWorld()) return;
    APlayerController* PC = GetWorld()->GetFirstPlayerController();
    if (!PC || !PC->IsLocalController() || !PC->GetPawn()) return;
    Controller = PC;
    Voice = NewObject<UReflectionsRealtimeVoiceComponent>(PC);
    Voice->RegisterComponent();
    Voice->OnVoiceStatus.AddDynamic(this, &UReflectionsVoiceInteractionSubsystem::OnStatus);
    Input = NewObject<UInputComponent>(PC);
    Input->RegisterComponent();
    Input->BindKey(EKeys::T, IE_Pressed, this, &UReflectionsVoiceInteractionSubsystem::OnTalkPressed).bConsumeInput = false;
    Input->BindKey(EKeys::T, IE_Released, this, &UReflectionsVoiceInteractionSubsystem::OnTalkReleased).bConsumeInput = false;
    PC->PushInputComponent(Input);
}
void UReflectionsVoiceInteractionSubsystem::OnTalkPressed()
{
    bHeld = true;
    APlayerController* PC = Controller.Get();
    if (!PC || !PC->GetPawn() || !Voice) return;
    AActor* Closest = nullptr;
    float BestDistance = FMath::Square(400.0f);
    for (TActorIterator<AActor> It(GetWorld()); It; ++It)
    {
        AActor* Candidate = *It;
        if (!Candidate || !Candidate->ActorHasTag(TEXT("NPC_Reactive"))) continue;
        const float Distance = FVector::DistSquared(PC->GetPawn()->GetActorLocation(), Candidate->GetActorLocation());
        if (Distance < BestDistance) { Closest = Candidate; BestDistance = Distance; }
    }
    if (!Closest) { OnStatus(TEXT("Move closer to a character to talk.")); return; }
    if (Voice->GetVoiceNpc() != Closest || !Voice->IsVoiceReady()) Voice->ConnectToNpc(Closest);
    else Voice->BeginPushToTalk();
}
void UReflectionsVoiceInteractionSubsystem::OnTalkReleased()
{
    bHeld = false;
    if (Voice) Voice->EndPushToTalk();
}
void UReflectionsVoiceInteractionSubsystem::OnStatus(const FString& Status)
{
    if (GEngine) GEngine->AddOnScreenDebugMessage(553214, 4.0f, FColor::Cyan, FString(TEXT("AI voice: ")) + Status);
    if (bHeld && Voice && Voice->IsVoiceReady() && Status.StartsWith(TEXT("AI voice ready"))) Voice->BeginPushToTalk();
}
void UReflectionsVoiceInteractionSubsystem::Deinitialize()
{
    if (APlayerController* PC = Controller.Get()) { if (Input) PC->PopInputComponent(Input); }
    if (Input) Input->DestroyComponent();
    if (Voice) { Voice->DisconnectVoice(); Voice->DestroyComponent(); }
    Input = nullptr; Voice = nullptr;
    Super::Deinitialize();
}
