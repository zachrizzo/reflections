using UnrealBuildTool;

public class ClothingFitEditor : ModuleRules
{
    public ClothingFitEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new[] { "UnrealEd", "Slate", "RenderCore" });
    }
}
