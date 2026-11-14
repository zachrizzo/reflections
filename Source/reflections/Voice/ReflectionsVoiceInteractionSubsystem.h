#pragma once
#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "ReflectionsVoiceInteractionSubsystem.generated.h"

class UInputComponent;
class UReflectionsRealtimeVoiceComponent;

/** Local test-map interaction; press and hold T near a tagged NPC to speak. */
UCLASS()
class REFLECTIONS_API UReflectionsVoiceInteractionSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override { RETURN_QUICK_DECLARE_CYCLE_STAT(UReflectionsVoiceInteractionSubsystem, STATGROUP_Tickables); }
    virtual bool IsTickable() const override;
    virtual void Deinitialize() override;
private:
    void OnTalkPressed();
    void OnTalkReleased();
    UFUNCTION() void OnStatus(const FString& Status);
    UPROPERTY(Transient) TObjectPtr<UInputComponent> Input;
    UPROPERTY(Transient) TObjectPtr<UReflectionsRealtimeVoiceComponent> Voice;
    TWeakObjectPtr<class APlayerController> Controller;
    bool bHeld = false;
};
