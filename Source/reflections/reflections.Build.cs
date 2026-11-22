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
			"PhysicsCore",
			"GeometryCore",
			"GeometryFramework"
		});

		// NPC rebuild: removed WebSockets, AudioCaptureCore, AudioCapture and Json (used only by the old Voice code)
		PrivateDependencyModuleNames.AddRange(new string[] { "AnimGraphRuntime", "Niagara", "RenderCore" });
		if (Target.bBuildEditor)
		{
			PrivateDependencyModuleNames.AddRange(new string[] {
				"ClothingSystemEditor", "ClothingSystemEditorInterface",
				"ClothingSystemRuntimeCommon", "ClothingSystemRuntimeInterface"
			});
		}

		// NPC rebuild: removed the combat-template include paths
		PublicIncludePaths.AddRange(new string[] {
			"reflections",
		});

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });

		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
