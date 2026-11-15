#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "GameFramework/DamageType.h"
#include "ReflectionsVillainConfig.generated.h"

class UAnimInstance;
class UAnimSequenceBase;
class UMaterialInterface;
class UNiagaraSystem;
class USkeletalMesh;
class USoundBase;
class USoundMix;
class UStaticMesh;

/** Damage from the Final Spell (the book's spell). The villain's true form takes full damage only from this. */
UCLASS()
class REFLECTIONS_API UReflectionsFinalSpellDamageType : public UDamageType
{
    GENERATED_BODY()
};

/**
 * Every asset the villain uses, hard-referenced so cooking /Game/Villain cooks them all.
 * Code loads /Game/Villain/DA_VillainConfig by path; any empty field falls back to a built-in default path,
 * so the villain also works before this asset exists. Tuning lives in Villain.* console variables, not here.
 */
UCLASS(BlueprintType)
class REFLECTIONS_API UReflectionsVillainConfig : public UDataAsset
{
    GENERATED_BODY()

public:
    static const UReflectionsVillainConfig* Get();

    // ---- Look ---------------------------------------------------------------------------------------------
    UPROPERTY(EditAnywhere, Category = "Look") TObjectPtr<USkeletalMesh> BodyMesh;
    UPROPERTY(EditAnywhere, Category = "Look") TObjectPtr<UMaterialInterface> BodyMaterial;
    UPROPERTY(EditAnywhere, Category = "Look") TObjectPtr<UStaticMesh> ShroudMesh;
    UPROPERTY(EditAnywhere, Category = "Look") TObjectPtr<UMaterialInterface> ShroudMaterial;
    UPROPERTY(EditAnywhere, Category = "Look") TObjectPtr<UStaticMesh> HoodMesh;
    UPROPERTY(EditAnywhere, Category = "Look") TObjectPtr<UStaticMesh> EyeMesh;
    UPROPERTY(EditAnywhere, Category = "Look") TObjectPtr<UMaterialInterface> EyeMaterial;
    UPROPERTY(EditAnywhere, Category = "Look") TObjectPtr<UMaterialInterface> InfectedOverlay;
    UPROPERTY(EditAnywhere, Category = "Look") TObjectPtr<UMaterialInterface> BurnedOverlay;
    UPROPERTY(EditAnywhere, Category = "Look") TObjectPtr<UMaterialInterface> TelegraphMaterial;
    UPROPERTY(EditAnywhere, Category = "Look") TObjectPtr<UStaticMesh> DiscMesh;

    // ---- Animation (SK_Mannequin) -------------------------------------------------------------------------
    UPROPERTY(EditAnywhere, Category = "Animation") TObjectPtr<UAnimSequenceBase> HoverAnim;
    UPROPERTY(EditAnywhere, Category = "Animation") TObjectPtr<UAnimSequenceBase> VolleyAnim;
    UPROPERTY(EditAnywhere, Category = "Animation") TObjectPtr<UAnimSequenceBase> SlamAnim;
    UPROPERTY(EditAnywhere, Category = "Animation") TObjectPtr<UAnimSequenceBase> WaveAnim;
    UPROPERTY(EditAnywhere, Category = "Animation") TObjectPtr<UAnimSequenceBase> BlinkAnim;
    /** Test hosts (Villain.SpawnTestHosts) only. */
    UPROPERTY(EditAnywhere, Category = "Animation") TObjectPtr<USkeletalMesh> TestHostMesh;
    UPROPERTY(EditAnywhere, Category = "Animation") TSubclassOf<UAnimInstance> TestHostAnimClass;

    // ---- Effects ------------------------------------------------------------------------------------------
    /** Smoke, cloth-like tendrils and embers around the villain (also on hosts at a smaller scale). */
    UPROPERTY(EditAnywhere, Category = "Effects") TObjectPtr<UNiagaraSystem> ShroudFX;
    /** Parametric projectile (User.Color, User.Color2, User.Scale): the hop wisp, his orbs and the Final Spell. */
    UPROPERTY(EditAnywhere, Category = "Effects") TObjectPtr<UNiagaraSystem> ProjectileFX;
    /** Parametric impact (User.Color, User.Color2, User.Scale, User.SmokeColor...): eruptions, hits, death. */
    UPROPERTY(EditAnywhere, Category = "Effects") TObjectPtr<UNiagaraSystem> ImpactFX;

    // ---- Sound --------------------------------------------------------------------------------------------
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> PossessSound;
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> VoiceSound;
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> HopSound;
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> ManifestSound;
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> TelegraphSound;
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> OrbSound;
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> SlamSound;
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> HurtSound;
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> ResistSound;
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> DeathSound;
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> FinalSpellSound;
    UPROPERTY(EditAnywhere, Category = "Sound") TObjectPtr<USoundBase> FightMusic;
};

/** Resolves a villain asset: the config's field if set, else the first path that loads. Results are cached. */
namespace ReflectionsVillainAssets
{
    REFLECTIONS_API UObject* Load(UObject* FromConfig, std::initializer_list<const TCHAR*> Paths, UClass* Class);

    template <typename T>
    T* Get(T* FromConfig, std::initializer_list<const TCHAR*> Paths)
    {
        return Cast<T>(Load(FromConfig, Paths, T::StaticClass()));
    }

    USkeletalMesh* BodyMesh();
    UMaterialInterface* BodyMaterial();
    UStaticMesh* ShroudMesh();
    UMaterialInterface* ShroudMaterial();
    UStaticMesh* HoodMesh();
    UStaticMesh* EyeMesh();
    UMaterialInterface* EyeMaterial();
    UMaterialInterface* InfectedOverlay();
    UMaterialInterface* BurnedOverlay();
    UMaterialInterface* TelegraphMaterial();
    UStaticMesh* DiscMesh();
    UAnimSequenceBase* HoverAnim();
    UAnimSequenceBase* VolleyAnim();
    UAnimSequenceBase* SlamAnim();
    UAnimSequenceBase* WaveAnim();
    UAnimSequenceBase* BlinkAnim();
    USkeletalMesh* TestHostMesh();
    UClass* TestHostAnimClass();
    UNiagaraSystem* ShroudFX();
    UNiagaraSystem* ProjectileFX();
    UNiagaraSystem* ImpactFX();
    USoundBase* PossessSound();
    USoundBase* VoiceSound();
    USoundBase* HopSound();
    USoundBase* ManifestSound();
    USoundBase* TelegraphSound();
    USoundBase* OrbSound();
    USoundBase* SlamSound();
    USoundBase* HurtSound();
    USoundBase* ResistSound();
    USoundBase* DeathSound();
    USoundBase* FinalSpellSound();
    USoundBase* FightMusic();

    // Voice lines (audio session, /Game/Audio/Jam/Voice/Cues, string-loaded from an always-cooked folder).
    // Each falls back to the matching SCue_Villain_* effect until the line exists.
    USoundBase* VoTaunt();
    USoundBase* VoHop();
    USoundBase* VoManifest();
    USoundBase* VoPhaseTwo();
    USoundBase* VoHurt();
    USoundBase* VoDeath();
    USoundBase* VoCured();
    /** 2D "inside your head" variants (no attenuation). */
    USoundBase* VoTauntHead();
    USoundBase* VoHopHead();
    /** A story line by id (ArtDirection/Story/main-quest.md), /Game/Audio/Jam/Voice/Cues/SCue_VO_<Id>; null until audio makes it. */
    USoundBase* StoryLine(const TCHAR* Id);
    // True-form extras (by path).
    UStaticMesh* ShardMesh();
    UMaterialInterface* MirrorMaterial();
    UMaterialInterface* HeartMaterial();
    /** Ducks the music under a stinger (releases itself). */
    USoundMix* StingerDuck();
}
