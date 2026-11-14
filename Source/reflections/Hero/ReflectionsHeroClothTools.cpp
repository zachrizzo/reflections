#include "Hero/ReflectionsHeroClothTools.h"

#include "Components/SkeletalMeshComponent.h"

#if WITH_EDITOR
#include "ClothingAsset.h"
#include "ClothingAssetFactory.h"
#include "Engine/SkeletalMesh.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "Rendering/SkeletalMeshLODModel.h"
#include "Rendering/SkeletalMeshModel.h"
#include "SkinnedAssetCompiler.h"
#endif

bool UReflectionsHeroClothTools::BuildCoatTailSimulation(USkeletalMesh* TailMesh, UPhysicsAsset* CollisionAsset)
{
#if WITH_EDITOR
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

	Lod.PointWeightMaps.RemoveAll([](const FPointWeightMap& Map)
	{
		return Map.CurrentTarget == static_cast<uint8>(EWeightMapTargetCommon::MaxDistance);
	});
	FPointWeightMap& Movement = Lod.PointWeightMaps.Emplace_GetRef(Positions.Num());
	Movement.Name = FName(TEXT("Pinned waist to free hem"));
	Movement.CurrentTarget = static_cast<uint8>(EWeightMapTargetCommon::MaxDistance);
	Movement.bEnabled = true;
	for (int32 Index = 0; Index < Positions.Num(); ++Index)
	{
		const float Depth = (Top - Positions[Index].Z) / (Top - Bottom);
		Movement.Values[Index] = 48.0f * FMath::SmoothStep(0.12f, 1.0f, Depth);
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
#else
	return false;
#endif
}

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
