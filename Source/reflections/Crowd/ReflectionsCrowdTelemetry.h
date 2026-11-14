#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ReflectionsCrowdTelemetry.generated.h"

/** Frame-time and real MetaHuman Crowd representation counts for isolated playtests. */
UCLASS()
class REFLECTIONS_API AReflectionsCrowdTelemetry : public AActor
{
    GENERATED_BODY()
public:
    AReflectionsCrowdTelemetry();
    virtual void Tick(float DeltaSeconds) override;
    UPROPERTY(EditAnywhere, Category="Crowd Benchmark", meta=(ClampMin="0.0", Units="s")) float WarmupSeconds = 10.0f;
    UPROPERTY(EditAnywhere, Category="Crowd Benchmark", meta=(ClampMin="1.0", Units="s")) float CaptureSeconds = 30.0f;
protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
private:
    void SaveCapture();
    FString Rows;
    double StartTime = 0.0;
    double PreviousTime = 0.0;
    bool bSaved = false;
    int32 Samples = 0;
    double NextStatsTime = 0.0;
    int32 Entities = 0, Visible = 0, Actors = 0, Instanced = 0;
};

