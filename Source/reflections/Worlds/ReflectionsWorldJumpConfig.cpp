#include "Worlds/ReflectionsWorldJumpConfig.h"

#include "Engine/World.h"
#include "EngineUtils.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "Materials/MaterialInterface.h"
#include "Misc/PackageName.h"
#include "Worlds/ReflectionsWorldAnchor.h"

const TCHAR* UReflectionsWorldJumpConfig::DefaultAssetPath = TEXT("/Game/Worlds/DA_WorldJumpConfig.DA_WorldJumpConfig");

namespace
{
    FReflectionsWorldInfo MakeWorld(EReflectionsWorld World, const TCHAR* Name, const TCHAR* PageSource, const FLinearColor& Coat,
        const FLinearColor& Theme, const FLinearColor& Coin)
    {
        FReflectionsWorldInfo Info;
        Info.World = World;
        Info.DisplayName = FText::FromString(Name);
        Info.PageSource = FText::FromString(PageSource);
        Info.CoatTint = Coat;
        Info.ThemeColor = Theme;
        Info.CoinColor = Coin;
        return Info;
    }
}

UReflectionsWorldJumpConfig::UReflectionsWorldJumpConfig()
{
    Worlds.Add(MakeWorld(EReflectionsWorld::Gray, TEXT("Pewterside"), TEXT("Pewterside's high spot"),
        FLinearColor(0.16f, 0.16f, 0.17f), FLinearColor(0.62f, 0.64f, 0.68f), FLinearColor(0.55f, 0.57f, 0.60f)));
    Worlds.Add(MakeWorld(EReflectionsWorld::Red, TEXT("Giltside"), TEXT("the Gilt Tower"),
        FLinearColor(0.42f, 0.02f, 0.02f), FLinearColor(0.95f, 0.18f, 0.12f), FLinearColor(0.95f, 0.12f, 0.05f)));
    Worlds.Add(MakeWorld(EReflectionsWorld::White, TEXT("Frostside"), TEXT("the Frost Tower"),
        FLinearColor(0.80f, 0.80f, 0.76f), FLinearColor(0.93f, 0.95f, 1.00f), FLinearColor(0.97f, 0.97f, 1.00f)));

    // Gray: drained of colour. Red: warm and red. White: bleached, pale and bright.
    FPostProcessSettings& GrayGrade = Worlds[0].Grade;
    GrayGrade.bOverride_ColorSaturation = true;
    GrayGrade.ColorSaturation = FVector4(1.0f, 1.0f, 1.0f, 0.3f);
    GrayGrade.bOverride_ColorContrast = true;
    GrayGrade.ColorContrast = FVector4(1.0f, 1.0f, 1.0f, 0.95f);

    FPostProcessSettings& RedGrade = Worlds[1].Grade;
    RedGrade.bOverride_SceneColorTint = true;
    RedGrade.SceneColorTint = FLinearColor(1.0f, 0.78f, 0.72f);
    RedGrade.bOverride_ColorSaturation = true;
    RedGrade.ColorSaturation = FVector4(1.0f, 1.0f, 1.0f, 1.15f);

    FPostProcessSettings& WhiteGrade = Worlds[2].Grade;
    WhiteGrade.bOverride_ColorSaturation = true;
    WhiteGrade.ColorSaturation = FVector4(1.0f, 1.0f, 1.0f, 0.15f);
    WhiteGrade.bOverride_SceneColorTint = true;
    WhiteGrade.SceneColorTint = FLinearColor(0.92f, 0.96f, 1.0f);
    WhiteGrade.bOverride_AutoExposureBias = true;
    WhiteGrade.AutoExposureBias = 0.6f;
    WhiteGrade.bOverride_BloomIntensity = true;
    WhiteGrade.BloomIntensity = 1.2f;

    MagicGetterNames = { TEXT("GetMagic"), TEXT("GetCurrentMagic"), TEXT("GetMana") };
    MaxMagicGetterNames = { TEXT("GetMaxMagic"), TEXT("GetMaxMana") };
    MaxMagicPropertyNames = { TEXT("MaxMagic"), TEXT("MaxMana") };
    SpendMagicNames = { TEXT("SpendMagic"), TEXT("TrySpendMagic"), TEXT("ConsumeMagic"), TEXT("SpendMana") };

    FallbackUpKeys = { EKeys::X, EKeys::Gamepad_FaceButton_Top };
    FallbackDownKeys = { EKeys::Z, EKeys::Gamepad_RightThumbstick };

    MappingContext = TSoftObjectPtr<UInputMappingContext>(FSoftObjectPath(TEXT("/Game/Worlds/Input/IMC_WorldJump.IMC_WorldJump")));
    JumpUpAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(TEXT("/Game/Worlds/Input/IA_WorldJumpUp.IA_WorldJumpUp")));
    JumpDownAction = TSoftObjectPtr<UInputAction>(FSoftObjectPath(TEXT("/Game/Worlds/Input/IA_WorldJumpDown.IA_WorldJumpDown")));
    OverlayTintMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/Worlds/Materials/M_WorldCoatTintOverlay.M_WorldCoatTintOverlay")));

    CoatComponentNames = { TEXT("TravelDrape"), TEXT("HeroCoat"), TEXT("HeroTails") };
    TintParameterNames = { TEXT("WorldTint"), TEXT("CoatTint"), TEXT("Tint"), TEXT("Color"), TEXT("BaseColorTint") };
}

const UReflectionsWorldJumpConfig* UReflectionsWorldJumpConfig::Get(const UObject* WorldContext)
{
    if (const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr)
    {
        for (TActorIterator<AReflectionsWorldAnchor> It(const_cast<UWorld*>(World)); It; ++It)
        {
            if (It->ConfigOverride)
            {
                return It->ConfigOverride;
            }
        }
    }

    static TWeakObjectPtr<UReflectionsWorldJumpConfig> ProjectConfig;
    if (!ProjectConfig.IsValid())
    {
        const FSoftObjectPath Path(DefaultAssetPath);
        UReflectionsWorldJumpConfig* Loaded = Cast<UReflectionsWorldJumpConfig>(Path.ResolveObject());
        if (!Loaded && FPackageName::DoesPackageExist(Path.GetLongPackageName()))
        {
            Loaded = Cast<UReflectionsWorldJumpConfig>(Path.TryLoad());
        }
        ProjectConfig = Loaded;
    }
    return ProjectConfig.IsValid() ? ProjectConfig.Get() : GetDefault<UReflectionsWorldJumpConfig>();
}

const FReflectionsWorldInfo* UReflectionsWorldJumpConfig::FindWorld(EReflectionsWorld World) const
{
    return Worlds.FindByPredicate([World](const FReflectionsWorldInfo& Info) { return Info.World == World; });
}

int32 UReflectionsWorldJumpConfig::IndexOfWorld(EReflectionsWorld World) const
{
    return Worlds.IndexOfByPredicate([World](const FReflectionsWorldInfo& Info) { return Info.World == World; });
}

bool UReflectionsWorldJumpConfig::GetNeighbor(EReflectionsWorld From, EReflectionsJumpDirection Direction, EReflectionsWorld& Out) const
{
    const int32 Index = IndexOfWorld(From);
    if (Index == INDEX_NONE)
    {
        return false;
    }
    const int32 Next = Index + (Direction == EReflectionsJumpDirection::Up ? 1 : -1);
    if (!Worlds.IsValidIndex(Next))
    {
        return false;
    }
    Out = Worlds[Next].World;
    return true;
}

FText UReflectionsWorldJumpConfig::GetWorldName(EReflectionsWorld World) const
{
    if (const FReflectionsWorldInfo* Info = FindWorld(World))
    {
        if (!Info->DisplayName.IsEmpty())
        {
            return Info->DisplayName;
        }
    }
    return StaticEnum<EReflectionsWorld>()->GetDisplayNameTextByValue(static_cast<int64>(World));
}
