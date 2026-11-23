#pragma once

#include "Item/MetaHumanOutfitEditorPipeline.h"
#include "AnimatedOutfitEditorPipeline.generated.h"

/** Keep fitted clothing skinned when testing body motion on an editable character. */
UCLASS(EditInlineNew)
class UAnimatedOutfitEditorPipeline : public UMetaHumanOutfitEditorPipeline
{
    GENERATED_BODY()
public:
    /** Retain the fitted render mesh and omit the simulation mesh from the assembled outfit. */
    UPROPERTY(EditAnywhere, Category="Outfit")
    bool bStripSimulationMesh = false;

    virtual UE::Tasks::TTask<FMetaHumanPaletteBuiltData> BuildItem(const FBuildItemParams& Params) const override;
};
