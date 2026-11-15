#include "Villain/ReflectionsVillainConfig.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimSequenceBase.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraSystem.h"
#include "Sound/SoundBase.h"
#include "Sound/SoundMix.h"

namespace
{
    constexpr const TCHAR* ConfigPath = TEXT("/Game/Villain/DA_VillainConfig.DA_VillainConfig");

    struct FCachedLoad
    {
        TWeakObjectPtr<UObject> Object;
        double RetryAfter = 0.0;
    };

    TMap<FString, FCachedLoad>& Cache()
    {
        static TMap<FString, FCachedLoad> Map;
        return Map;
    }

    UObject* LoadCached(const TCHAR* Path, UClass* Class)
    {
        FCachedLoad& Entry = Cache().FindOrAdd(Path);
        if (UObject* Hit = Entry.Object.Get())
        {
            return Hit;
        }
        const double Now = FPlatformTime::Seconds();
        if (Now < Entry.RetryAfter)
        {
            return nullptr;
        }
        UObject* Loaded = StaticLoadObject(Class, nullptr, Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
        Entry.Object = Loaded;
        // A missing asset is retried now and then, so assets made while the editor runs are picked up.
        Entry.RetryAfter = Loaded ? 0.0 : Now + 10.0;
        return Loaded;
    }

    const UReflectionsVillainConfig* Config()
    {
        return Cast<UReflectionsVillainConfig>(LoadCached(ConfigPath, UReflectionsVillainConfig::StaticClass()));
    }

    template <typename T>
    T* Field(TObjectPtr<T> UReflectionsVillainConfig::* Member)
    {
        const UReflectionsVillainConfig* C = Config();
        return C ? (C->*Member).Get() : nullptr;
    }
}

const UReflectionsVillainConfig* UReflectionsVillainConfig::Get()
{
    return Config();
}

UObject* ReflectionsVillainAssets::Load(UObject* FromConfig, std::initializer_list<const TCHAR*> Paths, UClass* Class)
{
    if (FromConfig && (!Class || FromConfig->IsA(Class)))
    {
        return FromConfig;
    }
    for (const TCHAR* Path : Paths)
    {
        if (UObject* Loaded = LoadCached(Path, Class))
        {
            return Loaded;
        }
    }
    return nullptr;
}

#define VILLAIN_ASSET(Type, Name, ...) \
    Type* ReflectionsVillainAssets::Name() \
    { \
        return Get<Type>(Field(&UReflectionsVillainConfig::Name), {__VA_ARGS__}); \
    }

#define VILLAIN_CUE(Name) TEXT("/Game/Audio/Jam/Cues/SCue_" Name ".SCue_" Name)

VILLAIN_ASSET(USkeletalMesh, BodyMesh, TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"))
VILLAIN_ASSET(UMaterialInterface, BodyMaterial, TEXT("/Game/Villain/Materials/M_Villain_Body.M_Villain_Body"))
VILLAIN_ASSET(UStaticMesh, ShroudMesh, TEXT("/Game/Villain/Meshes/SM_Villain_Shroud.SM_Villain_Shroud"))
VILLAIN_ASSET(UMaterialInterface, ShroudMaterial, TEXT("/Game/Villain/Materials/M_Villain_Shroud.M_Villain_Shroud"),
    TEXT("/Game/Villain/Materials/M_Villain_Body.M_Villain_Body"))
VILLAIN_ASSET(UStaticMesh, HoodMesh, TEXT("/Game/Villain/Meshes/SM_Villain_Hood.SM_Villain_Hood"))
VILLAIN_ASSET(UStaticMesh, EyeMesh, TEXT("/Engine/BasicShapes/Sphere.Sphere"))
VILLAIN_ASSET(UMaterialInterface, EyeMaterial, TEXT("/Game/Villain/Materials/M_Villain_Eye.M_Villain_Eye"))
VILLAIN_ASSET(UMaterialInterface, InfectedOverlay, TEXT("/Game/Villain/Materials/M_Villain_InfectedOverlay.M_Villain_InfectedOverlay"))
VILLAIN_ASSET(UMaterialInterface, BurnedOverlay, TEXT("/Game/Villain/Materials/M_Villain_BurnedOverlay.M_Villain_BurnedOverlay"))
VILLAIN_ASSET(UMaterialInterface, TelegraphMaterial, TEXT("/Game/Villain/Materials/M_Villain_Telegraph.M_Villain_Telegraph"))
VILLAIN_ASSET(UStaticMesh, DiscMesh, TEXT("/Engine/BasicShapes/Plane.Plane"))
VILLAIN_ASSET(UAnimSequenceBase, HoverAnim, TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Fall_Loop.MM_Fall_Loop"),
    TEXT("/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle"))
VILLAIN_ASSET(UAnimSequenceBase, VolleyAnim, TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_02.MM_Attack_02"))
VILLAIN_ASSET(UAnimSequenceBase, SlamAnim, TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_ChargedAttack.MM_ChargedAttack"))
VILLAIN_ASSET(UAnimSequenceBase, WaveAnim, TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_03.MM_Attack_03"))
VILLAIN_ASSET(UAnimSequenceBase, BlinkAnim, TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Dash.MM_Dash"))
VILLAIN_ASSET(USkeletalMesh, TestHostMesh, TEXT("/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"))
VILLAIN_ASSET(UNiagaraSystem, ShroudFX, TEXT("/Game/Villain/FX/NS_Villain_Shroud.NS_Villain_Shroud"))
VILLAIN_ASSET(UNiagaraSystem, ProjectileFX, TEXT("/Game/Characters/Hero/SpellVFX/Systems/NS_Spell_Projectile.NS_Spell_Projectile"))
VILLAIN_ASSET(UNiagaraSystem, ImpactFX, TEXT("/Game/Characters/Hero/SpellVFX/Systems/NS_Spell_Impact.NS_Spell_Impact"))
VILLAIN_ASSET(USoundBase, PossessSound, VILLAIN_CUE("Villain_Possess"), VILLAIN_CUE("Infected_Growl"))
VILLAIN_ASSET(USoundBase, VoiceSound, VILLAIN_CUE("Villain_Voice"), VILLAIN_CUE("Infected_Growl"))
VILLAIN_ASSET(USoundBase, HopSound, VILLAIN_CUE("Villain_Hop"), VILLAIN_CUE("WorldJump_Whoosh"))
VILLAIN_ASSET(USoundBase, ManifestSound, VILLAIN_CUE("Villain_Manifest"), VILLAIN_CUE("WorldJump_Stinger"))
VILLAIN_ASSET(USoundBase, TelegraphSound, VILLAIN_CUE("Villain_Telegraph"), VILLAIN_CUE("Arcane_Cast"))
VILLAIN_ASSET(USoundBase, OrbSound, VILLAIN_CUE("Villain_Orb"), VILLAIN_CUE("Arcane_Impact"))
VILLAIN_ASSET(USoundBase, SlamSound, VILLAIN_CUE("Villain_Slam"), VILLAIN_CUE("Earth_Impact"))
VILLAIN_ASSET(USoundBase, HurtSound, VILLAIN_CUE("Villain_Hurt"), VILLAIN_CUE("Lightning_Impact"))
VILLAIN_ASSET(USoundBase, ResistSound, VILLAIN_CUE("Villain_Resist"), VILLAIN_CUE("Shield_Block"))
VILLAIN_ASSET(USoundBase, DeathSound, VILLAIN_CUE("Villain_Death"), VILLAIN_CUE("WorldJump_Stinger"))
VILLAIN_ASSET(USoundBase, FinalSpellSound, VILLAIN_CUE("FinalSpell_Cast"), VILLAIN_CUE("Heal_Shimmer"))
VILLAIN_ASSET(USoundBase, FightMusic, VILLAIN_CUE("MUS_Villain_Fight"), VILLAIN_CUE("MUS_Combat_Layer"))

#define VILLAIN_VO(Name) TEXT("/Game/Audio/Jam/Voice/Cues/SCue_VO_Tarnish_" Name ".SCue_VO_Tarnish_" Name)
#define VILLAIN_PATH(Type, Name, ...) \
    Type* ReflectionsVillainAssets::Name() \
    { \
        return Get<Type>(nullptr, {__VA_ARGS__}); \
    }

VILLAIN_PATH(USoundBase, VoTaunt, VILLAIN_VO("Taunt"), VILLAIN_CUE("Villain_Voice"))
VILLAIN_PATH(USoundBase, VoHop, VILLAIN_VO("Hop"), VILLAIN_CUE("Villain_Voice"))
VILLAIN_PATH(USoundBase, VoManifest, VILLAIN_VO("Manifest"), VILLAIN_CUE("Villain_Voice"))
VILLAIN_PATH(USoundBase, VoPhaseTwo, VILLAIN_VO("PhaseTwo"), VILLAIN_CUE("Villain_Voice"))
VILLAIN_PATH(USoundBase, VoHurt, VILLAIN_VO("Hurt"), VILLAIN_CUE("Villain_Hurt"))
VILLAIN_PATH(USoundBase, VoDeath, VILLAIN_VO("Death"), VILLAIN_CUE("Villain_Death"))
VILLAIN_PATH(USoundBase, VoCured, VILLAIN_VO("Cured"), VILLAIN_CUE("Villain_Voice"))
VILLAIN_PATH(USoundBase, VoTauntHead, VILLAIN_VO("Taunt_Head"), VILLAIN_VO("Taunt"), VILLAIN_CUE("Villain_Voice"))
VILLAIN_PATH(USoundBase, VoHopHead, VILLAIN_VO("Hop_Head"), VILLAIN_VO("Hop"), VILLAIN_CUE("Villain_Voice"))
VILLAIN_PATH(UStaticMesh, ShardMesh, TEXT("/Game/Villain/Meshes/SM_Villain_Shard.SM_Villain_Shard"))
VILLAIN_PATH(UMaterialInterface, MirrorMaterial, TEXT("/Game/Villain/Materials/M_Villain_Mirror.M_Villain_Mirror"),
    TEXT("/Game/Villain/Materials/M_Villain_Body.M_Villain_Body"))
VILLAIN_PATH(UMaterialInterface, HeartMaterial, TEXT("/Game/Villain/Materials/M_Villain_Heart.M_Villain_Heart"),
    TEXT("/Game/Villain/Materials/M_Villain_Eye.M_Villain_Eye"))
VILLAIN_PATH(USoundMix, StingerDuck, TEXT("/Game/Audio/Jam/Mix/SMX_Jam_StingerDuck.SMX_Jam_StingerDuck"))

#undef VILLAIN_PATH
#undef VILLAIN_VO
#undef VILLAIN_CUE
#undef VILLAIN_ASSET

USoundBase* ReflectionsVillainAssets::StoryLine(const TCHAR* Id)
{
    const FString Path = FString::Printf(TEXT("/Game/Audio/Jam/Voice/Cues/SCue_VO_%s.SCue_VO_%s"), Id, Id);
    return Cast<USoundBase>(LoadCached(*Path, USoundBase::StaticClass()));
}

UClass* ReflectionsVillainAssets::TestHostAnimClass()
{
    const UReflectionsVillainConfig* C = Config();
    if (C && C->TestHostAnimClass)
    {
        return C->TestHostAnimClass.Get();
    }
    return Cast<UClass>(LoadCached(TEXT("/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed.ABP_Unarmed_C"), UClass::StaticClass()));
}
