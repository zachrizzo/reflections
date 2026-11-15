#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ReflectionsVillainConversion.generated.h"

class ACharacter;
class UAnimMontage;
class UAnimSequenceBase;
class UNiagaraComponent;
class UPointLightComponent;
class USkeletalMeshComponent;

/**
 * One conversion: a tarnished NPC tackles a clean one, a black wisp flows from the attacker's hand into the
 * victim's chest while it lies pinned, and the victim gets up tarnished (black eyes, black aura) and joins the
 * hunt. The paired tackle (UEFN mannequin interaction set, attacker `_A` / victim `_V`) plays on both NPCs'
 * driver meshes (ACharacter::GetMesh(), the hidden GASP mannequin their MetaHumans follow), aligned from the two
 * sequences' root tracks. The actor itself is the wisp: it flies from hand to chest carrying the smoke.
 */
UCLASS()
class REFLECTIONS_API AReflectionsVillainConversion : public AActor
{
    GENERATED_BODY()

public:
    AReflectionsVillainConversion();

    /**
     * Starts the sequence. Returns its length in seconds, or 0 if it cannot run (no driver, no animation).
     * Npc actors are what the game sees (MetaHumans); drivers are the characters that animate them.
     */
    float Begin(AActor* AttackerNpc, AActor* VictimNpc, ACharacter* InAttacker, ACharacter* InVictim);

    bool Involves(const AActor* Actor) const;
    AActor* GetAttacker() const { return AttackerActor.Get(); }
    AActor* GetVictim() const { return VictimActor.Get(); }

protected:
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    enum class EPhase : uint8 { Tackle, Down, Wisp, Turned, Rise, Done };

    bool PickTackle();
    void AlignAttacker();
    void StartDown();
    void StartWisp();
    void Turn();
    void StartRise();
    void Finish(bool bConverted);
    FVector HandLocation() const;
    FVector ChestLocation() const;
    static USkeletalMeshComponent* Driver(const ACharacter* Character);
    static void ReleaseHold(AActor* Npc);

    UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> Root;
    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> Smoke;
    UPROPERTY(Transient) TObjectPtr<UPointLightComponent> Light;
    UPROPERTY(Transient) TObjectPtr<UAnimSequenceBase> AttackerAnim;
    UPROPERTY(Transient) TObjectPtr<UAnimSequenceBase> VictimAnim;
    UPROPERTY(Transient) TObjectPtr<UAnimSequenceBase> GetUpAnim;
    UPROPERTY(Transient) TObjectPtr<UAnimMontage> GetUpMontage;
    UPROPERTY(Transient) TObjectPtr<UAnimSequenceBase> PossessedAnim;
    UPROPERTY(Transient) TObjectPtr<UAnimSequenceBase> RiseAnim;
    UPROPERTY(Transient) TObjectPtr<UAnimSequenceBase> KneelAnim;

    TWeakObjectPtr<AActor> AttackerActor;
    TWeakObjectPtr<AActor> VictimActor;
    TWeakObjectPtr<ACharacter> Attacker;
    TWeakObjectPtr<ACharacter> Victim;
    FString Variant;
    EPhase Phase = EPhase::Tackle;
    float Clock = 0.0f;
    float DownAt = 1.0f;
    float WispTime = 1.4f;
    float WispAt = 1.3f;
    float TurnAt = 2.7f;
    float RiseAt = 2.7f;
    float DoneAt = 5.0f;
    float NextTwitch = 0.0f;
    FVector WispStart = FVector::ZeroVector;
    bool bFinished = false;
};
