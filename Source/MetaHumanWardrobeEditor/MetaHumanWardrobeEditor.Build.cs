using UnrealBuildTool;

public class MetaHumanWardrobeEditor : ModuleRules
{
    public MetaHumanWardrobeEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PublicDependencyModuleNames.AddRange(new[] {
            "Core", "CoreUObject", "Engine", "MetaHumanCharacterPalette", "MetaHumanDefaultEditorPipeline"
        });
    }
}
