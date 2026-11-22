#include "ClothingFitLibrary.h"
#include "Components/SkinnedMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "HAL/FileManager.h"
#include "Modules/ModuleManager.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Rendering/SkinWeightVertexBuffer.h"

IMPLEMENT_MODULE(FDefaultModuleImpl, ClothingFitEditor)

void UClothingFitLibrary::RefreshSamplePose(USkeletalMeshComponent* Body)
{
    if (IsValid(Body) && Body->IsRegistered())
    {
        Body->TickAnimation(0.0f, false);
        Body->RefreshBoneTransforms();
        Body->RefreshFollowerComponents();
        Body->MarkRenderDynamicDataDirty();
    }
}

bool UClothingFitLibrary::WritePosedSurface(USkinnedMeshComponent* Component, const FString& Filename)
{
    if (!IsValid(Component) || !Component->GetSkinnedAsset() || !Component->IsRegistered())
    {
        return false;
    }
    const FSkeletalMeshRenderData* RenderData = Component->GetSkeletalMeshRenderData();
    if (!RenderData || RenderData->LODRenderData.IsEmpty()) { return false; }
    const FSkeletalMeshLODRenderData& LOD = RenderData->LODRenderData[0];
    const FSkinWeightVertexBuffer* Weights = Component->GetSkinWeightBuffer(0);
    if (!Weights || !Weights->GetNumVertices() || Weights->GetNumVertices() != LOD.GetNumVertices()) { return false; }
    TArray<FMatrix44f> Matrices;
    Component->GetCurrentRefToLocalMatrices(Matrices, 0);
    if (Matrices.IsEmpty()) { return false; }
    TArray<FVector3f> Positions;
    USkinnedMeshComponent::ComputeSkinnedPositions(Component, Positions, Matrices, LOD, *Weights);
    TArray<uint32> Indices;
    LOD.MultiSizeIndexContainer.GetIndexBuffer(Indices);
    if (Indices.IsEmpty() || Positions.IsEmpty()) { return false; }
    // Both surfaces share the same actor-local coordinates in centimeters, including component offsets.
    const FTransform Relative = Component->GetComponentTransform().GetRelativeTransform(Component->GetOwner()->GetActorTransform());
    for (FVector3f& P : Positions)
    {
        P = FVector3f(Relative.TransformPosition(FVector(P)));
        if (P.ContainsNaN()) { return false; }
    }
    TUniquePtr<FArchive> Writer(IFileManager::Get().CreateFileWriter(*Filename));
    if (!Writer) { return false; }
    uint32 VertexCount = Positions.Num(), IndexCount = Indices.Num();
    *Writer << VertexCount << IndexCount;
    Writer->Serialize(Positions.GetData(), Positions.Num() * sizeof(FVector3f));
    Writer->Serialize(Indices.GetData(), Indices.Num() * sizeof(uint32));
    return Writer->Close();
}
