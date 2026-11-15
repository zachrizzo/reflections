# Offscreen benchmark run of a packaged Reflections build: no window, no input, nothing to steal focus.
# All scenario commands go in -ExecCmds (run on the first frame). The CSV capture runs for -Frames frames
# and the run is stopped when the CSV is written. Results are copied to Saved/PerfLab/runs/<Tag>/.
# Usage: powershell -File run_off.ps1 -Exe <...\Binaries\Win64\reflections.exe> -Tag t -Cmds "a,b" [-Frames 6000] [-ExtraArgs ".."]
param(
  [Parameter(Mandatory)] [string]$Exe, [Parameter(Mandatory)] [string]$Tag,
  [string]$Cmds = "", [int]$Frames = 6000, [string]$ExtraArgs = "",
  [int]$ResX = 1920, [int]$ResY = 1080, [int]$TimeoutSec = 400,
  [string]$OutRoot = "C:\Users\zachc\Documents\Unreal Projects\reflections\Saved\PerfLab\runs"
)
$saved = Join-Path (Split-Path (Split-Path (Split-Path $Exe))) "Saved"
$csvDir = Join-Path $saved "Profiling\CSV"
$before = @(Get-ChildItem $csvDir -Filter *.csv -ErrorAction SilentlyContinue | % FullName)
$exec = "r.GPUCsvStatsEnabled 1"  # from train #8 game flow auto-detects to High on first launch: put "scalability 3" first in -Cmds for an Epic baseline
if ($Cmds) { $exec = "$exec,$Cmds" }
$argline = "-RenderOffscreen -ResX=$ResX -ResY=$ResY -nosplash -unattended -nosound -csvGpuStats -csvCaptureFrames=$Frames -ExecCmds=`"$exec`" -ini:Engine:[ConsoleVariables]:GameFlow.Enabled=0 $ExtraArgs"
Write-Host "[$Tag] $argline"
$t0 = Get-Date
$p = Start-Process -FilePath $Exe -ArgumentList $argline -PassThru
$log = Join-Path $saved "Logs\reflections.log"
$done = $false
while (-not $p.HasExited -and ((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec) {
  Start-Sleep 2
  $new = @(Get-ChildItem $csvDir -Filter *.csv -ErrorAction SilentlyContinue | ? { $before -notcontains $_.FullName })
  if ($new.Count -gt 0 -and (Select-String -Path $log -Pattern 'Csv(Profiler)?: .*(Capture Ended|Finalized|wrote|Writing)' -Quiet -ErrorAction SilentlyContinue)) { Start-Sleep 3; $done = $true; break }
}
$secs = [int]((Get-Date) - $t0).TotalSeconds
if (-not $p.HasExited) { $p.Kill(); Start-Sleep 2 }
$out = Join-Path $OutRoot $Tag; New-Item -ItemType Directory -Force $out | Out-Null
$new = @(Get-ChildItem $csvDir -Filter *.csv -ErrorAction SilentlyContinue | ? { $before -notcontains $_.FullName })
foreach ($f in $new) { Move-Item $f.FullName (Join-Path $out "profile.csv") -Force }
Copy-Item $log (Join-Path $out "game.log") -Force
Write-Host "[$Tag] done=$done exited=$($p.HasExited) code=$($p.ExitCode) after ${secs}s -> $out"
