#include "Worlds/ReflectionsCityTileReplacementSubsystem.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsCityTileReplacementTransformTest,
    "Reflections.Worlds.CityTileReplacement.SourceTransform",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FReflectionsCityTileReplacementTransformTest::RunTest(const FString& Parameters)
{
    const FTransform Source(FQuat::Identity, FVector(300000., 0., 0.), FVector::OneVector);
    const auto Match = [&](const FTransform& Candidate)
    {
        return UReflectionsCityTileReplacementSubsystem::TransformsMatch(Source, Candidate);
    };
    TestTrue(TEXT("Same transform is accepted"), Match(Source));
    TestTrue(TEXT("Serialization noise below half a millimetre is accepted"),
        Match(FTransform(FQuat::Identity, FVector(300000.01, 0., 0.), FVector::OneVector)));
    TestFalse(TEXT("A shifted instance cannot claim the source"),
        Match(FTransform(FQuat::Identity, FVector(300000.25, 0., 0.), FVector::OneVector)));
    TestFalse(TEXT("A rotated instance cannot claim the source"),
        Match(FTransform(FRotator(0., 90., 0.), Source.GetLocation(), FVector::OneVector)));
    TestFalse(TEXT("A mirrored instance cannot claim the source"),
        Match(FTransform(FQuat::Identity, Source.GetLocation(), FVector(-1., 1., 1.))));
    const FQuat EquivalentRotation(0., 0., 0., -1.);
    TestTrue(TEXT("Equivalent quaternion signs are accepted"),
        Match(FTransform(EquivalentRotation, Source.GetLocation(), FVector::OneVector)));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FReflectionsCityTileReplacementClaimTest,
    "Reflections.Worlds.CityTileReplacement.ClaimRetry",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FReflectionsCityTileReplacementClaimTest::RunTest(const FString& Parameters)
{
    using FSubsystem = UReflectionsCityTileReplacementSubsystem;
    using EClaim = FSubsystem::EClaim;
    TestTrue(TEXT("No claim remains pending"), FSubsystem::EvaluateClaim(0, false) == EClaim::Retry);
    TestTrue(TEXT("Two independently ready replacements remain pending"),
        FSubsystem::EvaluateClaim(2, false) == EClaim::Retry);
    TestTrue(TEXT("A second ready replacement does not keep an ambiguous pair"),
        FSubsystem::EvaluateClaim(2, true) == EClaim::Retry);
    TestTrue(TEXT("Removing the duplicate permits a fresh activation"),
        FSubsystem::EvaluateClaim(1, false) == EClaim::Activate);
    TestTrue(TEXT("A unique active pair stays active"), FSubsystem::EvaluateClaim(1, true) == EClaim::KeepActive);
    return true;
}
#endif
