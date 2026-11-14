#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "ReflectionsWorldHud.generated.h"

class UHorizontalBox;
class UTextBlock;
class UVerticalBox;

struct FReflectionsWorldHudCoin
{
    FText Name;
    FLinearColor Color = FLinearColor::White;
    int32 Count = 0;
};

struct FReflectionsWorldHudJump
{
    bool bExists = false;
    FText Keys;
    FText Destination;
    FLinearColor Color = FLinearColor::White;
    bool bHasCoin = false;
    FText CoinName;
    bool bHasMagic = true;
};

struct FReflectionsWorldHudState
{
    FText WorldName;
    FLinearColor WorldColor = FLinearColor::White;
    TArray<FReflectionsWorldHudCoin> Coins;
    int32 Pages = 0;
    int32 PagesForBook = 3;
    bool bBookComplete = false;
    TArray<FName> Keys;
    bool bHasMagic = false;
    bool bMagicDrains = false;
    float Magic = 0.0f;
    float MaxMagic = 0.0f;
    float MagicCost = 0.0f;
    FReflectionsWorldHudJump Up;
    FReflectionsWorldHudJump Down;
    bool bJumping = false;
};

/** Top-left world-jump panel (London, coins, pages, keys, jump prompts) plus arrival banner and messages. */
UCLASS()
class REFLECTIONS_API UReflectionsWorldHudWidget : public UUserWidget
{
    GENERATED_BODY()

public:
    void SetState(const FReflectionsWorldHudState& State);
    void ShowBanner(const FText& Title, const FLinearColor& Color, const FText& Subtitle = FText::GetEmpty());
    void ShowMessage(const FText& Message, const FLinearColor& Color);

protected:
    virtual void NativeOnInitialized() override;
    virtual void NativeTick(const FGeometry& Geometry, float DeltaTime) override;

private:
    UTextBlock* MakeText(int32 Size, const FLinearColor& Color, bool bBold = false);
    static FString KeyLabel(FName KeyId);

    UPROPERTY(Transient) TObjectPtr<UTextBlock> WorldLabel;
    UPROPERTY(Transient) TObjectPtr<UHorizontalBox> CoinRow;
    UPROPERTY(Transient) TArray<TObjectPtr<UTextBlock>> CoinLabels;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> PagesLabel;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> KeysLabel;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> MagicLabel;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> UpLabel;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> DownLabel;
    UPROPERTY(Transient) TObjectPtr<UVerticalBox> Banner;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> BannerTitle;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> BannerSubtitle;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> MessageLabel;

    float BannerTime = 0.0f;
    float MessageTime = 0.0f;
    FLinearColor BannerColor = FLinearColor::White;
    FLinearColor MessageColor = FLinearColor::White;
};
