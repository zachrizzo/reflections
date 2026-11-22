#pragma once

#include "Item/MetaHumanOutfitEditorPipeline.h"
#include "AnimatedOutfitEditorPipeline.generated.h"

/** Keep fitted clothing skinned when testing body motion on an editable character. */
UCLASS(EditInlineNew)
class UAnimatedOutfitEditorPipeline : public UMetaHumanOutfitEditorPipeline
{
    GENERATED_BODY()
public:
    virtual UE::Tasks::TTask<FMetaHumanPaletteBuiltData> BuildItem(const FBuildItemParams& Params) const override;
};
