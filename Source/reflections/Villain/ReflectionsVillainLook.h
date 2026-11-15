#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "ReflectionsVillainLook.generated.h"

class UAnimSequenceBase;
class UInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;
class UNiagaraComponent;
class UPointLightComponent;
class USkeletalMeshComponent;
class UStaticMeshComponent;

/**
 * The villain's body: an all-black mannequin with a faint violet rim, a loose shroud and hood that ripple
 * (world-position-offset cloth), two glowing eyes, and a Niagara shroud of smoke, wisps and embers.
 * The component's origin is at his feet and it faces +X. Everything is built at runtime from
 * UReflectionsVillainConfig, so the look needs no Blueprint.
 */
UCLASS(ClassGroup = (Villain), meta = (BlueprintSpawnableComponent))
class REFLECTIONS_API UReflectionsVillainLookComponent : public USceneComponent
{
    GENERATED_BODY()

public:
    UReflectionsVillainLookComponent();

    /** Overall size (1 = a tall man). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Villain")
    float BodyScale = 1.15f;

    /** The manifested Tarnish: a halo of orbiting mirror shards and a burning heart (the place to aim). Not a UPROPERTY on purpose. */
    bool bTrueForm = false;

    /** Smoke and wisps around him (0..1+). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Villain")
    float ShroudAmount = 1.0f;

    /** Builds the parts if they are not built yet. Called from BeginPlay. */
    void Build();

    void PlayAnimation(UAnimSequenceBase* Animation, bool bLoop, float PlayRate = 1.0f);
    /** Eye and rim glow, 0..1 (1 = normal, more for flashes). */
    void SetGlow(float Glow);
    /** White flash when hit, decays by itself. */
    void Flash(float Strength = 1.0f);
    void SetShroudAmount(float Amount);
    /** Shows or hides everything (manifest / death). */
    void SetLookVisible(bool bShow);

    USkeletalMeshComponent* GetBody() const { return Body; }
    FVector GetHandLocation(bool bRight) const;
    FVector GetHeadLocation() const;
    FVector GetChestLocation() const;
    /** Where to aim: the heart (true form), else the chest. */
    FVector GetHeartLocation() const;

protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
    virtual void OnUnregister() override;

private:
    UStaticMeshComponent* MakeStatic(FName Name, class UStaticMesh* Mesh, class UMaterialInterface* Material);
    void ApplyGlow();
    /** Robe to the hips, hood and eyes to the head: done once the body has a real pose (first ticks). */
    void AttachToBones();
    void BuildTrueForm();
    void TickTrueForm(float DeltaTime);

    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> Body;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> ShroudMesh;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> Hood;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Eyes;
    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> ShroudFx;
    UPROPERTY(Transient) TObjectPtr<UPointLightComponent> Light;
    UPROPERTY(Transient) TArray<TObjectPtr<UMaterialInstanceDynamic>> Dynamics;
    UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> Shards;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> Heart;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> HeartGlow;
    UPROPERTY(Transient) TObjectPtr<UPointLightComponent> HeartLight;
    /** Per shard: orbit phase, radius, height, spin rate. */
    TArray<FVector4f> ShardOrbits;

    float Glow = 1.0f;
    float FlashAmount = 0.0f;
    float Clock = 0.0f;
    bool bBuilt = false;
    bool bBonesAttached = false;
};
