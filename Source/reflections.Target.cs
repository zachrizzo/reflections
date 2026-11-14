// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;
using System.Collections.Generic;

public class reflectionsTarget : TargetRules
{
	public reflectionsTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V8;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_9;
		ExtraModuleNames.Add("reflections");

		// A machine-wide BuildConfiguration.xml sets bWithLiveCoding=false. Epic's precompiled
		// game libs are built with live coding, and the mismatch crashes the packaged exe at
		// static init (UObject registration). Force it on for the game target only.
		bWithLiveCoding = true;
		bOverrideBuildEnvironment = true;
	}
}
