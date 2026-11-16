// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class reflections : ModuleRules
{
	public reflections(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		// Jam: compile every .cpp on its own. Each session proves its files with -SingleFile, and unity blobs
		// let one file's file-scope "using namespace" leak into another (GameFlowSlate vs CutsceneSlate, train #13).
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

		PrivateDependencyModuleNames.AddRange(new string[] { "AnimGraphRuntime", "MassSpawner", "MassActors", "MassEntity", "MassCore", "MetaHumanCrowd", "Niagara", "WebSockets", "AudioCaptureCore", "AudioCapture", "Json" });
		// City crowd on Mass + ZoneGraph (Crowd/*); all plugins already enabled in the .uproject.
		PrivateDependencyModuleNames.AddRange(new string[] { "MassCommon", "MassMovement", "MassNavigation", "MassZoneGraphNavigation", "MassRepresentation", "MassLOD", "MassSignals", "MassCrowd", "ZoneGraph", "ZoneGraphAnnotations", "MassAIBehavior" });
		// Cutscene player (Cinematics/*): Level Sequences with runtime bindings and a transform origin.
		PrivateDependencyModuleNames.AddRange(new string[] { "LevelSequence", "MovieScene", "MovieSceneTracks" });
		// Game flow (GameFlow/*): the loading screen painted by the movie player while a map loads (packaged builds).
		PrivateDependencyModuleNames.Add("MoviePlayer");
		if (Target.bBuildEditor)
		{
			PrivateDependencyModuleNames.AddRange(new string[] {
				"ClothingSystemEditor", "ClothingSystemEditorInterface",
				"ClothingSystemRuntimeCommon", "ClothingSystemRuntimeInterface"
			});
		}

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




