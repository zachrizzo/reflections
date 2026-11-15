# Batch 1: scenarios x presets x feature toggles on one build (offscreen, sequential).
param([string]$Exe = "C:\Users\zachc\Documents\Unreal Projects\reflections\Saved\PerfLab\train5\Windows\reflections\Binaries\Win64\reflections.exe",
      [string]$Prefix = "t5", [string]$Only = "")
$here = Split-Path $MyInvocation.MyCommand.Path
$combat = "Crafting.Dummies 6 900 mixed,Squads.SpawnTest 2,Squads.Engage,Villain.Start,Villain.SpawnTestHosts 4,Crafting.Cast"
$finale = "Villain.Finale,Villain.BossHere,Squads.SpawnTest 2,Squads.Engage"
$runs = [ordered]@{
  "idle_epic"      = @("", 6000, "")
  "combat_epic"    = @($combat, 7000, "")
  "finale_epic"    = @($finale, 7000, "")
  "combat_high"    = @("scalability 2,$combat", 7000, "")
  "combat_med"     = @("scalability 1,$combat", 7000, "")
  "combat_low"     = @("scalability 0,$combat", 7000, "")
  "combat_epic_1440" = @($combat, 6000, "-ResX=2560 -ResY=1440")
  "combat_epic_4k"   = @($combat, 5000, "-ResX=3840 -ResY=2160")
  "combat_nohair"  = @("r.HairStrands.Enable 0,$combat", 7000, "")
  "combat_nocloth" = @("p.ClothPhysics 0,$combat", 7000, "")
  "combat_novsm"   = @("r.Shadow.Virtual.Enable 0,$combat", 7000, "")
  "combat_nohwrt"  = @("r.Lumen.HardwareRayTracing 0,r.RayTracing.Shadows 0,$combat", 7000, "")
  "combat_nolumen" = @("r.DynamicGlobalIlluminationMethod 0,r.ReflectionMethod 2,$combat", 7000, "")
  "combat_noanimthrottle" = @("Crowd.Lod.Enable 0,$combat", 7000, "")
}
foreach ($k in $runs.Keys) {
  if ($Only -and ($k -notmatch $Only)) { continue }
  $r = @($runs[$k])
  if ($r[0] -notmatch "scalability") { $r[0] = ("scalability 3," + $r[0]).TrimEnd(",") }  # pin Epic: the game auto-detects from train #8
  $extra = $r[2]
  $res = ""
  if ($extra -match 'ResX=(\d+) -ResY=(\d+)') { & "$here\run_off.ps1" -Exe $Exe -Tag "${Prefix}_$k" -Cmds $r[0] -Frames $r[1] -ResX $matches[1] -ResY $matches[2] }
  else { & "$here\run_off.ps1" -Exe $Exe -Tag "${Prefix}_$k" -Cmds $r[0] -Frames $r[1] }
}
Write-Host "BATCH DONE"
