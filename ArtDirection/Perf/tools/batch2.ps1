# Batch 2: per-character cost levers and the proposed preset CVars, combat scene, offscreen.
param([string]$Exe = "C:\Users\zachc\Documents\Unreal Projects\reflections\Saved\PerfLab\train5\Windows\reflections\Binaries\Win64\reflections.exe",
      [string]$Prefix = "t5", [string]$Only = "")
$here = Split-Path $MyInvocation.MyCommand.Path
$combat = "Crafting.Dummies 6 900 mixed,Squads.SpawnTest 2,Squads.Engage,Villain.Start,Villain.SpawnTestHosts 4,Crafting.Cast"
$runs = [ordered]@{
  "combat_lodbias1"  = "r.SkeletalMeshLODBias 1,$combat"
  "combat_lodbias2"  = "r.SkeletalMeshLODBias 2,$combat"
  "combat_nortskel"  = "r.RayTracing.Geometry.SkeletalMeshes 0,$combat"
  "combat_noskincachert" = "r.Lumen.HardwareRayTracing 0,r.RayTracing.Geometry.SkeletalMeshes 0,$combat"
  "combat_urofast"   = "a.URO.ForceInterpolation 1,a.URO.ForceAnimRate 2,$combat"
  "combat_nogroom"   = "r.HairStrands.Enable 0,r.HairStrands.Visibility 0,$combat"
  "combat_epic_rerun" = "$combat"
  # npc-unify A/B levers (staged for train #9+; the CVars exist only from that build)
  "combat_walkerfoley_on"  = "Npc.WalkerFoley 1,$combat"
  "combat_walkerfoley_off" = "Npc.WalkerFoley 0,$combat"
  "combat_leanfollow_on"   = "Npc.LeanFollowerParts 1,$combat"
  "combat_leanfollow_off"  = "Npc.LeanFollowerParts 0,$combat"
  "combat_crowdlod_quietcams_off" = "Crowd.Lod.QuietDriverCameras 0,$combat"
}
foreach ($k in $runs.Keys) {
  if ($Only -and ($k -notmatch $Only)) { continue }
  & "$here\run_off.ps1" -Exe $Exe -Tag "${Prefix}_$k" -Cmds ("scalability 3," + $runs[$k]) -Frames 7000
}
Write-Host "BATCH2 DONE"
