#include "ClothingFitLibrary.h"
#include "ClothingHemWeightNode.h"
#include "ChaosClothAsset/ClothComponent.h"
#include "ChaosClothAsset/ClothSimulationProxy.h"
#include "ChaosClothAsset/CollectionClothFacade.h"
#include "ChaosOutfitAsset/Outfit.h"
#include "ChaosOutfitAsset/OutfitAsset.h"
#include "ClothingSystemRuntimeTypes.h"
#include "Components/SkinnedMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Dataflow/DataflowNodeFactory.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "Modules/ModuleManager.h"
#include "PhysicsAssetUtils.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "Engine/SkeletalMesh.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Rendering/SkinWeightVertexBuffer.h"
#include "SkeletalRenderPublic.h"

class FClothingFitEditorModule : public FDefaultModuleImpl
{
    virtual void StartupModule() override
    {
        DATAFLOW_NODE_REGISTER_CREATION_FACTORY(FClothingHemWeightNode);
    }
};
IMPLEMENT_MODULE(FClothingFitEditorModule, ClothingFitEditor)

FClothingHemWeightNode::FClothingHemWeightNode(const UE::Dataflow::FNodeParameters& Parameters, FGuid Guid)
    : FDataflowNode(Parameters, Guid)
{
    RegisterInputConnection(&Collection);
    RegisterOutputConnection(&Collection, &Collection);
}

void FClothingHemWeightNode::Evaluate(UE::Dataflow::FContext& Context, const FDataflowOutput* Out) const
{
    if (!Out->IsA(&Collection)) { return; }
    const TSharedRef<FManagedArrayCollection> Data = MakeShared<FManagedArrayCollection>(GetValue(Context, &Collection));
    UE::Chaos::ClothAsset::FCollectionClothFacade Cloth(Data);
    if (Cloth.IsValid() && PinAboveCm > FreeBelowCm)
    {
        Cloth.AddWeightMap(TEXT("HemTravel"));
        const TArrayView<FVector3f> Points = Cloth.GetSimPosition3D();
        TArrayView<float> Weights = Cloth.GetWeightMap(TEXT("HemTravel"));
        for (int32 Index = 0; Index < Points.Num(); ++Index)
        {
            Weights[Index] = 1.f - FMath::SmoothStep(FreeBelowCm, PinAboveCm, Points[Index].Z);
        }
    }
    SetValue(Context, MoveTemp(*Data), &Collection);
}

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

static bool WriteSurface(USkinnedMeshComponent* Component, const FString& Filename, bool bUseCloth,
    UChaosClothComponent* Simulated = nullptr)
{
    if (!IsValid(Component) || !Component->GetSkinnedAsset() || !Component->IsRegistered())
    {
        return false;
    }
    const FSkeletalMeshRenderData* RenderData = Component->GetSkeletalMeshRenderData();
    if (!RenderData || RenderData->LODRenderData.IsEmpty()) { return false; }
    const FSkeletalMeshLODRenderData& LOD = RenderData->LODRenderData[0];
    TArray<FVector3f> Positions;
    if (bUseCloth)
    {
        TArray<FFinalSkinVertex> RenderVertices;
        Component->GetCPUSkinnedVertices(RenderVertices, 0);
        if (RenderVertices.Num() != LOD.GetNumVertices()) { return false; }
        Positions.Reserve(RenderVertices.Num());
        for (const FFinalSkinVertex& Vertex : RenderVertices)
        {
            Positions.Add(Vertex.Position);
        }
    }
    else
    {
        const FSkinWeightVertexBuffer* Weights = Component->GetSkinWeightBuffer(0);
        if (!Weights || !Weights->GetNumVertices() || Weights->GetNumVertices() != LOD.GetNumVertices()) { return false; }
        TArray<FMatrix44f> Matrices;
        Component->GetCurrentRefToLocalMatrices(Matrices, 0);
        if (Matrices.IsEmpty()) { return false; }
        USkinnedMeshComponent::ComputeSkinnedPositions(Component, Positions, Matrices, LOD, *Weights);
    }
    if (Simulated)
    {
        Simulated->WaitForExistingParallelClothSimulation_GameThread();
        TMap<int32, FClothSimulData> Simulation;
        FMatrix LocalToWorld;
        float Blend = 0.f;
        static_cast<const IClothSimulationDataProvider&>(*Simulated)
            .GetUpdateClothSimulationData_AnyThread(Simulation, LocalToWorld, Blend);
        if (Blend <= 0.f || Simulation.IsEmpty()) { return false; }
        const FMatrix WorldToLocal = LocalToWorld.Inverse();
        const FVector Scale = Simulated->GetComponentTransform().GetScale3D().GetAbs();
        for (const FSkelMeshRenderSection& Section : LOD.RenderSections)
        {
            const FClothSimulData* Data = Simulation.Find(Section.CorrespondClothAssetIndex);
            if (!Data || Data->LODIndex != 0 || !Section.HasClothingData()) { continue; }
            const TArray<FMeshToMeshVertData>& Mapping = Section.ClothMappingDataLODs[0];
            // The fitted tunic uses exactly one triangle influence per render vertex.
            if (Mapping.Num() != static_cast<int32>(Section.NumVertices)) { return false; }
            for (int32 Index = 0; Index < Mapping.Num(); ++Index)
            {
                const FMeshToMeshVertData& Vertex = Mapping[Index];
                if (Vertex.SourceMeshVertIndices[3] == MAX_uint16) { continue; }
                FVector WorldPosition = FVector::ZeroVector;
                for (int32 Corner = 0; Corner < 3; ++Corner)
                {
                    const int32 Particle = Vertex.SourceMeshVertIndices[Corner];
                    if (!Data->Positions.IsValidIndex(Particle) || !Data->Normals.IsValidIndex(Particle)) { return false; }
                    const FVector P = Data->Transform.TransformPosition(FVector(Data->Positions[Particle]));
                    const FVector N = Data->Transform.TransformVector(FVector(Data->Normals[Particle]));
                    const auto& Weight = Vertex.PositionBaryCoordsAndDist;
                    WorldPosition += Weight[Corner] * (P + N * Weight.W * Scale[Corner]);
                }
                FVector3f& Position = Positions[Section.BaseVertexIndex + Index];
                const float Weight = Blend * (1.f - static_cast<float>(Vertex.SourceMeshVertIndices[3]) / MAX_uint16);
                const FVector4 LocalPosition = WorldToLocal.TransformPosition(WorldPosition);
                Position = FMath::Lerp(Position, FVector3f(FVector(LocalPosition)), Weight);
            }
        }
    }
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

bool UClothingFitLibrary::WritePosedSurface(USkinnedMeshComponent* Component, const FString& Filename)
{
    return WriteSurface(Component, Filename, false);
}

bool UClothingFitLibrary::WriteSimulatedSurface(USkinnedMeshComponent* Component, const FString& Filename)
{
    return WriteSurface(Component, Filename, true);
}

int32 UClothingFitLibrary::GetDynamicClothParticleCount(USkinnedMeshComponent* Component)
{
    const UChaosClothComponent* Cloth = Cast<UChaosClothComponent>(Component);
    const auto* Proxy = Cloth ? Cloth->GetClothSimulationProxy() : nullptr;
    return Proxy && Cloth->IsSimulationEnabled() ? Proxy->GetNumDynamicParticles() : 0;
}

AActor* UClothingFitLibrary::SpawnBenchActor(AActor* WorldContext, FVector Location, FRotator Rotation)
{
    UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    return World && World->IsGameWorld() ? World->SpawnActor<AActor>(Location, Rotation) : nullptr;
}

int32 UClothingFitLibrary::FitTriangleCollider(UChaosClothComponent* Cloth, USkeletalMeshComponent* Body)
{
    USkeletalMesh* Mesh = Body ? Body->GetSkeletalMeshAsset() : nullptr;
    const UChaosOutfitAsset* FittedAsset = Cloth ? Cast<UChaosOutfitAsset>(Cloth->GetAsset()) : nullptr;
    if (!Mesh || !FittedAsset || !FittedAsset->GetOutfit() || Mesh->GetLODNum() < 1) { return INDEX_NONE; }

    UChaosOutfitAsset* NewAsset = NewObject<UChaosOutfitAsset>(Cloth, NAME_None, RF_Transient);
    UPhysicsAsset* Collider = NewObject<UPhysicsAsset>(NewAsset, NAME_None, RF_Transient);
    int32 LOD = FMath::Min(2, Mesh->GetLODNum() - 1);
    FText Error;
    const FPhysAssetCreateParams Params;
    if (FPhysicsAssetUtils::GenerateSkinnedTriangleMesh(Collider, Mesh, LOD, Params, Error, false) == INDEX_NONE)
    {
        UE_LOG(LogTemp, Warning, TEXT("Tunic body collider for %s: %s"), *Mesh->GetName(), *Error.ToString());
        return INDEX_NONE;
    }
    UChaosOutfit* Outfit = NewObject<UChaosOutfit>(NewAsset, NAME_None, RF_Transient);
    Outfit->Append(*FittedAsset->GetOutfit());
    for (FChaosOutfitPiece& Piece : Outfit->GetPieces())
    {
        Piece.PhysicsAsset = Collider;
    }
    NewAsset->Build(Outfit);
    Cloth->SetAsset(NewAsset);
    return LOD;
}

bool UClothingFitLibrary::WriteClothFrame(UChaosClothComponent* Cloth, const FString& Filename)
{
    return Cloth && WriteSurface(Cloth, Filename, false, Cloth);
}
