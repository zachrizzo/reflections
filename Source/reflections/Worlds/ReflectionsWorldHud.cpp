#include "Worlds/ReflectionsWorldHud.h"

#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"

#define LOCTEXT_NAMESPACE "ReflectionsWorlds"

namespace
{
    constexpr float BannerHold = 1.6f;
    constexpr float BannerFade = 0.9f;
    constexpr float MessageHold = 2.6f;
    constexpr float MessageFade = 0.6f;

    FLinearColor WithAlpha(const FLinearColor& Color, float Alpha)
    {
        return FLinearColor(Color.R, Color.G, Color.B, Alpha);
    }

    FLinearColor Dim(const FLinearColor& Color)
    {
        return FLinearColor(Color.R * 0.45f, Color.G * 0.45f, Color.B * 0.45f, 0.85f);
    }
}

UTextBlock* UReflectionsWorldHudWidget::MakeText(int32 Size, const FLinearColor& Color, bool bBold)
{
    UTextBlock* Text = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    FSlateFontInfo Font = Text->GetFont();
    Font.Size = Size;
    if (bBold)
    {
        Font.TypefaceFontName = TEXT("Bold");
    }
    Text->SetFont(Font);
    Text->SetColorAndOpacity(FSlateColor(Color));
    Text->SetShadowOffset(FVector2D(1.0f, 1.0f));
    Text->SetShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.75f));
    return Text;
}

void UReflectionsWorldHudWidget::NativeOnInitialized()
{
    Super::NativeOnInitialized();
    if (!WidgetTree || WidgetTree->RootWidget)
    {
        return;
    }
    UCanvasPanel* Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
    WidgetTree->RootWidget = Root;
    Root->SetVisibility(ESlateVisibility::HitTestInvisible);

    // A soft dark backing keeps the panel readable over bright skies and red walls.
    UBorder* Backing = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
    Backing->SetBrushColor(FLinearColor(0.0f, 0.0f, 0.0f, 0.45f));
    Backing->SetPadding(FMargin(14.0f, 10.0f, 18.0f, 12.0f));
    UCanvasPanelSlot* PanelSlot = Root->AddChildToCanvas(Backing);
    PanelSlot->SetAnchors(FAnchors(0.0f, 0.0f));
    PanelSlot->SetPosition(FVector2D(20.0f, 18.0f));
    PanelSlot->SetAutoSize(true);
    UVerticalBox* Panel = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    Backing->SetContent(Panel);

    auto AddRow = [Panel](UWidget* Widget, float Bottom)
    {
        UVerticalBoxSlot* Slot = Panel->AddChildToVerticalBox(Widget);
        Slot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, Bottom));
    };

    WorldLabel = MakeText(24, FLinearColor::White, true);
    AddRow(WorldLabel, 4.0f);

    CoinRow = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
    AddRow(CoinRow, 2.0f);
    UTextBlock* CoinsTitle = MakeText(13, FLinearColor(0.85f, 0.82f, 0.74f));
    CoinsTitle->SetText(LOCTEXT("CoinsTitle", "Mirror shards"));
    CoinRow->AddChildToHorizontalBox(CoinsTitle)->SetPadding(FMargin(0.0f, 0.0f, 10.0f, 0.0f));

    PagesLabel = MakeText(13, FLinearColor(0.95f, 0.88f, 0.70f));
    AddRow(PagesLabel, 2.0f);
    KeysLabel = MakeText(13, FLinearColor(0.95f, 0.80f, 0.45f));
    AddRow(KeysLabel, 2.0f);
    MagicLabel = MakeText(13, FLinearColor(0.45f, 0.70f, 1.0f));
    AddRow(MagicLabel, 6.0f);
    UpLabel = MakeText(14, FLinearColor::White);
    AddRow(UpLabel, 2.0f);
    DownLabel = MakeText(14, FLinearColor::White);
    AddRow(DownLabel, 0.0f);

    Banner = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
    UCanvasPanelSlot* BannerSlot = Root->AddChildToCanvas(Banner);
    BannerSlot->SetAnchors(FAnchors(0.5f, 0.16f));
    BannerSlot->SetAlignment(FVector2D(0.5f, 0.5f));
    BannerSlot->SetAutoSize(true);
    BannerTitle = MakeText(44, FLinearColor::White, true);
    BannerTitle->SetJustification(ETextJustify::Center);
    Banner->AddChildToVerticalBox(BannerTitle)->SetHorizontalAlignment(HAlign_Center);
    BannerSubtitle = MakeText(18, FLinearColor::White);
    BannerSubtitle->SetJustification(ETextJustify::Center);
    Banner->AddChildToVerticalBox(BannerSubtitle)->SetHorizontalAlignment(HAlign_Center);
    Banner->SetVisibility(ESlateVisibility::Collapsed);

    MessageLabel = MakeText(18, FLinearColor::White);
    MessageLabel->SetJustification(ETextJustify::Center);
    UCanvasPanelSlot* MessageSlot = Root->AddChildToCanvas(MessageLabel);
    MessageSlot->SetAnchors(FAnchors(0.5f, 0.27f));
    MessageSlot->SetAlignment(FVector2D(0.5f, 0.5f));
    MessageSlot->SetAutoSize(true);
    MessageLabel->SetVisibility(ESlateVisibility::Collapsed);
}

FString UReflectionsWorldHudWidget::KeyLabel(FName KeyId)
{
    // "RedTowerKey" -> "Red Tower Key"
    return FName::NameToDisplayString(KeyId.ToString(), false);
}

void UReflectionsWorldHudWidget::SetState(const FReflectionsWorldHudState& State)
{
    if (!WorldLabel)
    {
        return;
    }
    WorldLabel->SetText(FText::FromString(State.WorldName.ToString().ToUpper()));
    WorldLabel->SetColorAndOpacity(FSlateColor(State.WorldColor));

    while (CoinLabels.Num() < State.Coins.Num())
    {
        UTextBlock* Label = MakeText(13, FLinearColor::White, true);
        CoinRow->AddChildToHorizontalBox(Label)->SetPadding(FMargin(0.0f, 0.0f, 12.0f, 0.0f));
        CoinLabels.Add(Label);
    }
    for (int32 Index = 0; Index < CoinLabels.Num(); ++Index)
    {
        if (!State.Coins.IsValidIndex(Index))
        {
            CoinLabels[Index]->SetText(FText::GetEmpty());
            continue;
        }
        const FReflectionsWorldHudCoin& Coin = State.Coins[Index];
        // "Gray London" -> "Gray"
        FString Short = Coin.Name.ToString();
        Short.Split(TEXT(" "), &Short, nullptr);
        CoinLabels[Index]->SetText(FText::FromString(FString::Printf(TEXT("%s %d"), *Short, Coin.Count)));
        CoinLabels[Index]->SetColorAndOpacity(FSlateColor(Coin.Count > 0 ? Coin.Color : Dim(Coin.Color)));
    }

    PagesLabel->SetText(State.bBookComplete
        ? FText::Format(LOCTEXT("PagesDone", "Mirror pages {0} / {1}  -  the spell is ready"), State.Pages, State.PagesForBook)
        : FText::Format(LOCTEXT("Pages", "Mirror pages {0} / {1}"), State.Pages, State.PagesForBook));

    if (State.Keys.Num() > 0)
    {
        TArray<FString> Names;
        for (const FName& Key : State.Keys)
        {
            Names.Add(KeyLabel(Key));
        }
        KeysLabel->SetText(FText::FromString(FString::Printf(TEXT("Keys: %s"), *FString::Join(Names, TEXT(", ")))));
        KeysLabel->SetVisibility(ESlateVisibility::HitTestInvisible);
    }
    else
    {
        KeysLabel->SetVisibility(ESlateVisibility::Collapsed);
    }

    if (State.bHasMagic)
    {
        MagicLabel->SetText(FText::Format(State.bMagicDrains
                ? LOCTEXT("Magic", "Magic {0} / {1}  -  stepping through takes {2}")
                : LOCTEXT("MagicNoDrain", "Magic {0} / {1}  -  stepping through takes {2} (not drained yet)"),
            FText::AsNumber(FMath::FloorToInt(State.Magic)), FText::AsNumber(FMath::RoundToInt(State.MaxMagic)),
            FText::AsNumber(FMath::RoundToInt(State.MagicCost))));
    }
    else
    {
        MagicLabel->SetText(LOCTEXT("NoMagicSource", "Magic: no magic bar on this hero (stepping through is free)"));
    }

    auto SetJump = [](UTextBlock* Label, const FReflectionsWorldHudJump& Jump, const FText& Verb)
    {
        if (!Jump.bExists)
        {
            Label->SetVisibility(ESlateVisibility::Collapsed);
            return;
        }
        Label->SetVisibility(ESlateVisibility::HitTestInvisible);
        FText Need;
        if (!Jump.bHasCoin)
        {
            Need = FText::Format(LOCTEXT("NeedsCoin", "  (needs a {0} shard)"), Jump.CoinName);
        }
        else if (!Jump.bHasMagic)
        {
            Need = LOCTEXT("NeedsMagic", "  (needs more magic)");
        }
        Label->SetText(FText::Format(LOCTEXT("JumpPrompt", "Hold [{0}]  {1} {2}{3}"), Jump.Keys, Verb, Jump.Destination, Need));
        Label->SetColorAndOpacity(FSlateColor(Jump.bHasCoin && Jump.bHasMagic ? Jump.Color : Dim(Jump.Color)));
    };
    SetJump(UpLabel, State.Up, LOCTEXT("RiseTo", "step up into"));
    SetJump(DownLabel, State.Down, LOCTEXT("SinkTo", "step down into"));
}

void UReflectionsWorldHudWidget::ShowBanner(const FText& Title, const FLinearColor& Color, const FText& Subtitle)
{
    if (!Banner)
    {
        return;
    }
    BannerColor = Color;
    BannerTitle->SetText(FText::FromString(Title.ToString().ToUpper()));
    BannerSubtitle->SetText(Subtitle);
    BannerSubtitle->SetVisibility(Subtitle.IsEmpty() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
    BannerTime = BannerHold + BannerFade;
    Banner->SetVisibility(ESlateVisibility::HitTestInvisible);
}

void UReflectionsWorldHudWidget::ShowMessage(const FText& Message, const FLinearColor& Color)
{
    if (!MessageLabel)
    {
        return;
    }
    MessageColor = Color;
    MessageLabel->SetText(Message);
    MessageTime = MessageHold + MessageFade;
    MessageLabel->SetVisibility(ESlateVisibility::HitTestInvisible);
}

void UReflectionsWorldHudWidget::NativeTick(const FGeometry& Geometry, float DeltaTime)
{
    Super::NativeTick(Geometry, DeltaTime);
    if (Banner && BannerTime > 0.0f)
    {
        BannerTime -= DeltaTime;
        const float Alpha = FMath::Clamp(BannerTime / BannerFade, 0.0f, 1.0f);
        BannerTitle->SetColorAndOpacity(FSlateColor(WithAlpha(BannerColor, Alpha)));
        BannerSubtitle->SetColorAndOpacity(FSlateColor(WithAlpha(FLinearColor(0.95f, 0.92f, 0.85f), Alpha)));
        if (BannerTime <= 0.0f)
        {
            Banner->SetVisibility(ESlateVisibility::Collapsed);
        }
    }
    if (MessageLabel && MessageTime > 0.0f)
    {
        MessageTime -= DeltaTime;
        const float Alpha = FMath::Clamp(MessageTime / MessageFade, 0.0f, 1.0f);
        MessageLabel->SetColorAndOpacity(FSlateColor(WithAlpha(MessageColor, Alpha)));
        if (MessageTime <= 0.0f)
        {
            MessageLabel->SetVisibility(ESlateVisibility::Collapsed);
        }
    }
}

#undef LOCTEXT_NAMESPACE
