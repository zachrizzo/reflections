// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class reflections : ModuleRules
{
	public reflections(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] {
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"AIModule",
			"StateTreeModule",
			"GameplayStateTreeModule",
			"UMG",
			"Slate"
		});

		PrivateDependencyModuleNames.AddRange(new string[] { });

		PublicIncludePaths.AddRange(new string[] {
			"reflections",
			"reflections/Variant_Platforming",
			"reflections/Variant_Platforming/Animation",
			"reflections/Variant_Combat",
			"reflections/Variant_Combat/AI",
			"reflections/Variant_Combat/Animation",
			"reflections/Variant_Combat/Gameplay",
			"reflections/Variant_Combat/Interfaces",
			"reflections/Variant_Combat/UI",
			"reflections/Variant_SideScrolling",
			"reflections/Variant_SideScrolling/AI",
			"reflections/Variant_SideScrolling/Gameplay",
			"reflections/Variant_SideScrolling/Interfaces",
			"reflections/Variant_SideScrolling/UI"
		});

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });

		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
