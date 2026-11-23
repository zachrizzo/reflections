#include "AnimatedOutfitEditorPipeline.h"
#include "Engine/SkeletalMesh.h"
#include "MetaHumanCharacterEditorPipelineSpecification.h"
#include "Modules/ModuleManager.h"

IMPLEMENT_MODULE(FDefaultModuleImpl, MetaHumanWardrobeEditor)

UE::Tasks::TTask<FMetaHumanPaletteBuiltData> UAnimatedOutfitEditorPipeline::BuildItem(const FBuildItemParams& Params) const
{
    // The stock preview binds clothing to root while a face rig is pending.
    // A combined body with skin weights can already drive a body-only motion review.
    const bool bPreview = Params.Quality == EMetaHumanCharacterPaletteBuildQuality::Preview;
    if ((!bPreview && !bStripSimulationMesh) ||
        Params.BuildInput.GetScriptStruct() != GetSpecification()->BuildInputStruct)
    {
        return Super::BuildItem(Params);
    }

    FBuildItemParams Preview = Params;
    auto* Input = reinterpret_cast<FMetaHumanOutfitPipelineBuildInput*>(Preview.BuildInput.GetMutableMemory());
    if (Input)
    {
        for (auto& Pair : Input->CharacterData)
        {
            if (bStripSimulationMesh)
            {
                Pair.Value.bStripSimMesh = true;
            }
            if (bPreview && Pair.Value.MergedHeadAndBody && Pair.Value.MergedHeadAndBody->GetRefSkeleton().GetNum() > 1)
            {
                Pair.Value.bTransferSkinWeights = true;
            }
        }
    }
    return Super::BuildItem(Preview);
}
