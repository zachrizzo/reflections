#include "ReflectionsHeroAnimInstance.h"

#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"

#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"

const FName UReflectionsHeroAnimInstance::SpellSlot(TEXT("DefaultSlot"));

namespace
{
    class FReflectionsHeroAnimProxy final : public FAnimInstanceProxy
    {
    public:
        explicit FReflectionsHeroAnimProxy(UAnimInstance* Instance)
            : FAnimInstanceProxy(Instance)
        {
        }

        virtual void Initialize(UAnimInstance* Instance) override
        {
            FAnimInstanceProxy::Initialize(Instance);
            const UReflectionsHeroAnimInstance* Hero = CastChecked<UReflectionsHeroAnimInstance>(Instance);
            Idle = Hero->Idle;
            Walk = Hero->Walk;
            Jog = Hero->Jog;
            CrouchIdle = Hero->CrouchIdle;
            CrouchWalk = Hero->CrouchWalk;
            Takeoff = Hero->Takeoff;
            Fall = Hero->Fall;
            Land = Hero->Land;
            RegisterSlotNodeWithAnimInstance(UReflectionsHeroAnimInstance::SpellSlot);
        }

        virtual void PreUpdate(UAnimInstance* Instance, float DeltaSeconds) override
        {
            FAnimInstanceProxy::PreUpdate(Instance, DeltaSeconds);

            const AActor* Owner = Instance->GetOwningActor();
            const ACharacter* Character = Owner ? Cast<ACharacter>(Owner->GetParentActor()) : nullptr;
            const UCharacterMovementComponent* Movement = Character ? Character->GetCharacterMovement() : nullptr;
            Speed = Movement ? Movement->Velocity.Size2D() : 0.0f;
            bFalling = Movement && Movement->IsFalling();
            bCrouching = Character && Character->bIsCrouched && CrouchIdle && CrouchWalk;
        }

        virtual void UpdateAnimationNode(const FAnimationUpdateContext& Context) override
        {
            const float DeltaSeconds = Context.GetDeltaTime();
            BlendedSpeed = FMath::FInterpTo(BlendedSpeed, Speed, DeltaSeconds, 9.0f);
            IdleTime += DeltaSeconds;
            const float RelativeCadence = FMath::GetMappedRangeValueClamped(
                FVector2f(0.0f, 595.0f), FVector2f(0.0f, 1.75f), BlendedSpeed);
            StridePhase = FMath::Fmod(StridePhase + RelativeCadence * DeltaSeconds, 1.0f);
            CrouchWeight = FMath::FInterpConstantTo(CrouchWeight, bCrouching ? 1.0f : 0.0f, DeltaSeconds, 7.0f);
            if (bFalling)
            {
                AirTime = bWasFalling ? AirTime + DeltaSeconds : 0.0f;
                LandTime = -1.0f;
            }
            else if (bWasFalling)
            {
                LandTime = 0.0f;
            }
            else if (LandTime >= 0.0f)
            {
                LandTime += DeltaSeconds;
            }
            bWasFalling = bFalling;

            GetSlotWeight(UReflectionsHeroAnimInstance::SpellSlot, SlotWeight, SourceWeight, TotalWeight);
            UpdateSlotNodeWeight(UReflectionsHeroAnimInstance::SpellSlot, SlotWeight, Context.GetFinalBlendWeight());
        }

        virtual bool Evaluate(FPoseContext& Output) override
        {
            if (SlotWeight <= ZERO_ANIMWEIGHT_THRESH)
            {
                EvaluateLocomotion(Output);
            }
            else
            {
                FPoseContext SourceContext(Output);
                if (SourceWeight > ZERO_ANIMWEIGHT_THRESH)
                {
                    EvaluateLocomotion(SourceContext);
                }
                else
                {
                    SourceContext.ResetToRefPose();
                }
                const FAnimationPoseData Source(SourceContext);
                FAnimationPoseData Destination(Output);
                SlotEvaluatePose(UReflectionsHeroAnimInstance::SpellSlot, Source, SourceWeight, Destination, SlotWeight, TotalWeight);
            }
            return true;
        }

    private:
        void EvaluateLocomotion(FPoseContext& Output)
        {
            if (BlendedSpeed <= 170.0f || !Jog)
            {
                SamplePose(Output, Idle, IdleTime, true);
                if (Walk)
                {
                    BlendSequence(Output, Walk, StridePhase * Walk->GetPlayLength(),
                        FMath::Clamp(BlendedSpeed / 170.0f, 0.0f, 1.0f));
                }
            }
            else
            {
                SamplePose(Output, Walk, Walk ? StridePhase * Walk->GetPlayLength() : 0.0f, true);
                BlendSequence(Output, Jog, StridePhase * Jog->GetPlayLength(),
                    FMath::Clamp((BlendedSpeed - 170.0f) / 230.0f, 0.0f, 1.0f));
            }
            if (CrouchWeight > ZERO_ANIMWEIGHT_THRESH && CrouchIdle && CrouchWalk)
            {
                FPoseContext Crouched(Output);
                SamplePose(Crouched, CrouchIdle, IdleTime, true);
                BlendSequence(Crouched, CrouchWalk, StridePhase * CrouchWalk->GetPlayLength(),
                    FMath::Clamp(BlendedSpeed / 140.0f, 0.0f, 1.0f));
                FAnimationPoseData BasePose(Output);
                const FAnimationPoseData CrouchedPose(Crouched);
                FAnimationRuntime::BlendTwoPosesTogetherInPlace(BasePose, CrouchedPose, 1.0f - CrouchWeight);
            }
            if (bFalling)
            {
                const float TakeoffTime = Takeoff ? FMath::Min(0.27f, Takeoff->GetPlayLength()) : 0.0f;
                const float FallWeight = FMath::Clamp((AirTime - TakeoffTime + 0.12f) / 0.12f, 0.0f, 1.0f);
                if (Takeoff && FallWeight < 1.0f)
                {
                    BlendSequence(Output, Takeoff, AirTime, FMath::Clamp((AirTime + 0.025f) / 0.09f, 0.0f, 1.0f));
                }
                if (Fall && FallWeight > ZERO_ANIMWEIGHT_THRESH)
                {
                    BlendSequence(Output, Fall, FMath::Fmod(FMath::Max(0.0f, AirTime - TakeoffTime), Fall->GetPlayLength()), FallWeight);
                }
            }
            else if (Land && LandTime >= 0.0f)
            {
                const float Blend = FMath::Min(FMath::Clamp((LandTime + 0.025f) / 0.08f, 0.0f, 1.0f),
                    FMath::Clamp((Land->GetPlayLength() - LandTime) / 0.21f, 0.0f, 1.0f));
                BlendSequence(Output, Land, LandTime, Blend);
            }
        }

        static void SamplePose(FPoseContext& Output, const UAnimSequence* Sequence, float Time, bool bLoop)
        {
            if (Sequence && Sequence->GetPlayLength() > SMALL_NUMBER)
            {
                FAnimationPoseData Pose(Output);
                const float Position = bLoop
                    ? FMath::Fmod(Time, Sequence->GetPlayLength()) : FMath::Min(Time, Sequence->GetPlayLength());
                Sequence->GetAnimationPose(Pose, FAnimExtractContext(Position, false, FDeltaTimeRecord(), bLoop));
            }
            else
            {
                Output.ResetToRefPose();
            }
        }

        static void BlendSequence(FPoseContext& Output, const UAnimSequence* Sequence, float Time, float Weight)
        {
            if (Weight <= ZERO_ANIMWEIGHT_THRESH)
            {
                return;
            }
            FPoseContext Sample(Output);
            SamplePose(Sample, Sequence, Time, false);
            const FAnimationPoseData AdditivePose(Sample);
            FAnimationPoseData BasePose(Output);
            FAnimationRuntime::BlendTwoPosesTogetherInPlace(BasePose, AdditivePose, 1.0f - Weight);
        }

        const UAnimSequence* Idle = nullptr;
        const UAnimSequence* Walk = nullptr;
        const UAnimSequence* Jog = nullptr;
        const UAnimSequence* CrouchIdle = nullptr;
        const UAnimSequence* CrouchWalk = nullptr;
        const UAnimSequence* Takeoff = nullptr;
        const UAnimSequence* Fall = nullptr;
        const UAnimSequence* Land = nullptr;
        float AirTime = 0.0f;
        float LandTime = -1.0f;
        float Speed = 0.0f;
        float BlendedSpeed = 0.0f;
        float StridePhase = 0.0f;
        float IdleTime = 0.0f;
        float CrouchWeight = 0.0f;
        float SlotWeight = 0.0f;
        float SourceWeight = 1.0f;
        float TotalWeight = 0.0f;
        bool bFalling = false;
        bool bWasFalling = false;
        bool bCrouching = false;
    };
}

FAnimInstanceProxy* UReflectionsHeroAnimInstance::CreateAnimInstanceProxy()
{
    return new FReflectionsHeroAnimProxy(this);
}

void UReflectionsHeroAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy)
{
    delete Proxy;
}
