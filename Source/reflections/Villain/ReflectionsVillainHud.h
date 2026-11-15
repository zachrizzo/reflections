#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "ReflectionsVillainHud.generated.h"

class UBorder;
class UProgressBar;
class UTextBlock;
class UVerticalBox;

/** Boss bar (top centre), villain messages, the big banner and the Final Spell prompt (bottom centre). Built in code. */
UCLASS()
class REFLECTIONS_API UReflectionsVillainHudWidget : public UUserWidget
{
    GENERATED_BODY()

public:
    void SetBoss(const FText& Name, float Fraction, bool bVisible);
    void ShowMessage(const FText& Text, const FLinearColor& Color);
    void ShowBanner(const FText& Title, const FText& Subtitle, const FLinearColor& Color);
    void SetFinalSpell(bool bVisible, const FText& Text, bool bReady);

protected:
    virtual void NativeOnInitialized() override;
    virtual void NativeTick(const FGeometry& Geometry, float DeltaTime) override;

private:
    UTextBlock* MakeText(int32 Size, const FLinearColor& Color, bool bBold = false);

    UPROPERTY(Transient) TObjectPtr<UVerticalBox> BossBox;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> BossName;
    UPROPERTY(Transient) TObjectPtr<UProgressBar> BossBar;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> MessageLabel;
    UPROPERTY(Transient) TObjectPtr<UVerticalBox> Banner;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> BannerTitle;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> BannerSubtitle;
    UPROPERTY(Transient) TObjectPtr<UBorder> FinalBox;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> FinalLabel;

    float MessageTime = 0.0f;
    float BannerTime = 0.0f;
    float ShownFraction = 1.0f;
    float TargetFraction = 1.0f;
    float FinalPulse = 0.0f;
    bool bFinalReady = false;
    FLinearColor MessageColor = FLinearColor::White;
    FLinearColor BannerColor = FLinearColor::White;
};
