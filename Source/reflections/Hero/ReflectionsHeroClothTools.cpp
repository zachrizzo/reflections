#include "Hero/ReflectionsHeroClothTools.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"

#if WITH_EDITOR
#include "ClothingAsset.h"
#include "ClothingAssetFactory.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "Rendering/SkeletalMeshLODModel.h"
#include "Rendering/SkeletalMeshModel.h"
#include "SkinnedAssetCompiler.h"
#endif

#if WITH_EDITOR
namespace
{
	struct FCoatClothProfile
	{
		// The original tail profile: 48 cm * SmoothStep(0.12, 1, depth), no backstop maps touched.
		bool bLegacyTailProfile = true;
		float PinnedDepth = 0.12f;
		float MaxDistanceAtHem = 48.0f;
		float GradientExponent = 1.0f;
		float BackstopDistance = 0.0f;
		float BackstopRadius = 0.0f;
	};

	float ProfileMaxDistance(const FCoatClothProfile& Profile, float Depth)
	{
		if (Profile.bLegacyTailProfile)
		{
			return Profile.MaxDistanceAtHem * FMath::SmoothStep(Profile.PinnedDepth, 1.0f, Depth);
		}
		if (Depth <= Profile.PinnedDepth)
		{
			return 0.0f;
		}
		// Continuous from zero at the pinned band to the full distance at the hem: no hard pinned/free edge.
		const float Span = FMath::Max(1.0f - Profile.PinnedDepth, KINDA_SMALL_NUMBER);
		const float T = FMath::Clamp((Depth - Profile.PinnedDepth) / Span, 0.0f, 1.0f);
		return Profile.MaxDistanceAtHem * FMath::Pow(T, FMath::Max(Profile.GradientExponent, 0.1f));
	}

	FPointWeightMap& ReplaceWeightMap(FClothLODDataCommon& Lod, EWeightMapTargetCommon Target, const TCHAR* Name, int32 NumPoints)
	{
		Lod.PointWeightMaps.RemoveAll([Target](const FPointWeightMap& Map)
		{
			return Map.CurrentTarget == static_cast<uint8>(Target);
		});
		FPointWeightMap& Map = Lod.PointWeightMaps.Emplace_GetRef(NumPoints);
		Map.Name = FName(Name);
		Map.CurrentTarget = static_cast<uint8>(Target);
		Map.bEnabled = true;
		return Map;
	}

	bool BuildCoatCloth(USkeletalMesh* TailMesh, UPhysicsAsset* CollisionAsset, const FCoatClothProfile& Profile);
}
#endif

bool UReflectionsHeroClothTools::BuildCoatTailSimulation(USkeletalMesh* TailMesh, UPhysicsAsset* CollisionAsset)
{
#if WITH_EDITOR
	return BuildCoatCloth(TailMesh, CollisionAsset, FCoatClothProfile());
#else
	return false;
#endif
}

bool UReflectionsHeroClothTools::BuildCoatClothProfile(USkeletalMesh* CoatMesh, UPhysicsAsset* CollisionAsset,
	float PinnedDepth, float MaxDistanceAtHem, float GradientExponent, float BackstopDistance, float BackstopRadius)
{
#if WITH_EDITOR
	FCoatClothProfile Profile;
	Profile.bLegacyTailProfile = false;
	Profile.PinnedDepth = FMath::Clamp(PinnedDepth, 0.0f, 0.95f);
	Profile.MaxDistanceAtHem = FMath::Max(MaxDistanceAtHem, 0.0f);
	Profile.GradientExponent = GradientExponent;
	Profile.BackstopDistance = BackstopDistance;
	Profile.BackstopRadius = FMath::Max(BackstopRadius, 0.0f);
	return BuildCoatCloth(CoatMesh, CollisionAsset, Profile);
#else
	return false;
#endif
}

#if WITH_EDITOR
namespace
{
bool BuildCoatCloth(USkeletalMesh* TailMesh, UPhysicsAsset* CollisionAsset, const FCoatClothProfile& Profile)
{
	if (!TailMesh || !CollisionAsset)
	{
		return false;
	}

	USkinnedAsset* PendingMeshes[] = {TailMesh};
	FSkinnedAssetCompilingManager::Get().FinishCompilation(PendingMeshes);
	FScopedSkeletalMeshPostEditChange Edit(TailMesh);
	FSkeletalMeshModel* Model = TailMesh->GetImportedModel();
	if (!Model || !Model->LODModels.IsValidIndex(0) || Model->LODModels[0].Sections.Num() != 1)
	{
		return false;
	}

	TailMesh->Modify();
	UClothingAssetCommon* Cloth = nullptr;
	for (UClothingAssetBase* Asset : TailMesh->GetMeshClothingAssets())
	{
		Cloth = Cast<UClothingAssetCommon>(Asset);
		if (Cloth && Cloth->GetFName() == FName(TEXT("HeroCoatTails")))
		{
			break;
		}
		Cloth = nullptr;
	}
	const bool bNewCloth = !Cloth;
	if (bNewCloth)
	{
		FSkeletalMeshClothBuildParams Params;
		Params.AssetName = TEXT("HeroCoatTails");
		Params.LodIndex = 0;
		Params.SourceSection = 0;
		Params.bRemoveFromMesh = false;
		Params.PhysicsAsset = CollisionAsset;
		Cloth = Cast<UClothingAssetCommon>(NewObject<UClothingAssetFactory>()->CreateFromSkeletalMesh(TailMesh, Params));
	}
	if (!Cloth || Cloth->LodData.IsEmpty())
	{
		return false;
	}

	Cloth->Modify();
	Cloth->PhysicsAsset = CollisionAsset;
	FClothLODDataCommon& Lod = Cloth->LodData[0];
	const TArray<FVector3f>& Positions = Lod.PhysicalMeshData.Vertices;
	if (Positions.IsEmpty())
	{
		return false;
	}

	float Bottom = Positions[0].Z;
	float Top = Bottom;
	for (const FVector3f& Position : Positions)
	{
		Bottom = FMath::Min(Bottom, Position.Z);
		Top = FMath::Max(Top, Position.Z);
	}
	if (Top - Bottom < 25.0f)
	{
		return false;
	}

	FPointWeightMap& Movement = ReplaceWeightMap(Lod, EWeightMapTargetCommon::MaxDistance,
		Profile.bLegacyTailProfile ? TEXT("Pinned waist to free hem") : TEXT("Collar to hem gradient"), Positions.Num());
	for (int32 Index = 0; Index < Positions.Num(); ++Index)
	{
		const float Depth = (Top - Positions[Index].Z) / (Top - Bottom);
		Movement.Values[Index] = ProfileMaxDistance(Profile, Depth);
	}
	if (!Profile.bLegacyTailProfile)
	{
		// Non-legacy Chaos backstop: each particle may move at most BackstopDistance inward (against the
		// animated normal) from its skinned position. A zero radius removes the backstop entirely.
		if (Profile.BackstopRadius > 0.0f)
		{
			// Fill each map before adding the next: ReplaceWeightMap may reallocate PointWeightMaps.
			{
				FPointWeightMap& Distance = ReplaceWeightMap(Lod, EWeightMapTargetCommon::BackstopDistance,
					TEXT("Backstop distance"), Positions.Num());
				for (float& Value : Distance.Values)
				{
					Value = Profile.BackstopDistance;
				}
			}
			{
				FPointWeightMap& Radius = ReplaceWeightMap(Lod, EWeightMapTargetCommon::BackstopRadius,
					TEXT("Backstop radius"), Positions.Num());
				for (float& Value : Radius.Values)
				{
					Value = Profile.BackstopRadius;
				}
			}
		}
		else
		{
			Lod.PointWeightMaps.RemoveAll([](const FPointWeightMap& Map)
			{
				return Map.CurrentTarget == static_cast<uint8>(EWeightMapTargetCommon::BackstopDistance)
					|| Map.CurrentTarget == static_cast<uint8>(EWeightMapTargetCommon::BackstopRadius);
			});
		}
	}
	Lod.bSmoothTransition = true;
	if (bNewCloth)
	{
		TailMesh->AddClothingAsset(Cloth);
	}
	FSkeletalMeshLODModel& LodModel = Model->LODModels[0];
	FSkelMeshSection& Section = LodModel.Sections[0];
	if (Section.HasClothingData() && Section.ClothingData.AssetGuid != Cloth->GetAssetGuid())
	{
		return false;
	}
	const bool bHasBinding = Section.HasClothingData();
	Cloth->ApplyParameterMasks(bHasBinding);
	if (!bHasBinding)
	{
		// A previous mesh build may have dropped section data while retaining the cloth LOD map.
		Cloth->LodMap.Reset();
		if (!Cloth->BindToSkeletalMesh(TailMesh, 0, 0, 0))
		{
			if (bNewCloth)
			{
				TailMesh->GetMeshClothingAssets().Remove(Cloth);
			}
			return false;
		}
	}
	FSkelMeshSourceSectionUserData& UserSection =
		FSkelMeshSourceSectionUserData::GetSourceSectionUserData(LodModel.UserSectionsData, Section);
	UserSection.CorrespondClothAssetIndex = Section.CorrespondClothAssetIndex;
	UserSection.ClothingData = Section.ClothingData;
	TailMesh->MarkPackageDirty();
	return true;
}
}
#endif

FString UReflectionsHeroClothTools::InspectCoatTailSimulation(USkeletalMeshComponent* TailComponent)
{
	if (!TailComponent || !TailComponent->GetSkeletalMeshAsset())
	{
		return TEXT("missing coat tails");
	}
	const USkeletalMesh* TailMesh = TailComponent->GetSkeletalMeshAsset();
	return FString::Printf(TEXT("Asset=%s Bound=%d Instances=%d Suspended=%d"), *TailMesh->GetName(),
		TailMesh->HasActiveClothingAssets(), TailComponent->GetClothingSimulationInstances().Num(),
		TailComponent->IsClothingSimulationSuspended());
}
