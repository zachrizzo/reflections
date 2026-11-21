// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class reflections : ModuleRules
{
	public reflections(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		bUseUnity = false;

		PublicDependencyModuleNames.AddRange(new string[] {
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"AIModule",
			"NavigationSystem",
			"StateTreeModule",
			"GameplayStateTreeModule",
			"UMG",
			"Slate",
			"SlateCore",
			"PhysicsCore"
		});

		PrivateDependencyModuleNames.AddRange(new string[] { "AnimGraphRuntime", "Niagara", "WebSockets", "AudioCaptureCore", "AudioCapture", "Json" });
		if (Target.bBuildEditor)
		{
			PrivateDependencyModuleNames.AddRange(new string[] {
				"ClothingSystemEditor", "ClothingSystemEditorInterface",
				"ClothingSystemRuntimeCommon", "ClothingSystemRuntimeInterface"
			});
		}

		PublicIncludePaths.AddRange(new string[] {
			"reflections",
			"reflections/Variant_Combat",
			"reflections/Variant_Combat/AI",
			"reflections/Variant_Combat/Animation",
			"reflections/Variant_Combat/Gameplay",
			"reflections/Variant_Combat/Interfaces",
			"reflections/Variant_Combat/UI",
		});

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });

		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
