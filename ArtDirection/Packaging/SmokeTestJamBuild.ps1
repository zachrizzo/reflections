# Smoke test of the STAGED jam build (not the zip). About 2 minutes:
#   title -> New Game -> town loads -> frame time at spawn -> teleport to the market -> frame time there ->
#   talk prompt (E) -> pause menu open/close (P) -> quit, then the log is checked. Screenshots go to Saved\JamBuild\Logs.
# Input is synthetic (WScript.Shell SendKeys to the game window), so it needs the game window in front; don't touch the
# mouse or keyboard while it runs. The zip is never touched; the run writes <stage>\reflections\Saved\, which the zip
# script excludes. Frame times come from the engine's CSV profiler (Development builds), via the in-game console.
# Usage: powershell -ExecutionPolicy Bypass -File ArtDirection\Packaging\SmokeTestJamBuild.ps1 [-Stage ...] [-MinFreeGB 6]
param(
  [string]$Stage = (Join-Path $PSScriptRoot '..\..\Saved\JamBuild\Windows'),
  [double]$MinFreeGB = 6,
  [string]$Map = 'MedievalLondon',
  [string]$Market = '852 -471 150 0 0 0',   # crowd-spot centroid of place "market" in Content/Crowd/Spots/MedievalLondon.json
  [int]$LoadSeconds = 35,
  [int]$SampleSeconds = 10
)
$ErrorActionPreference = 'Stop'
$Stage = (Resolve-Path $Stage).Path
$exe = Join-Path $Stage 'reflections.exe'
$saved = Join-Path $Stage 'reflections\Saved'
$out = (Resolve-Path (Join-Path $PSScriptRoot '..\..\Saved\JamBuild\Logs')).Path
$free = (Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory / 1MB
if ($free -lt $MinFreeGB) { "NOT STARTED: free commit {0:N1} GB < {1} GB. Close PIE or the editor first." -f $free, $MinFreeGB; exit 2 }
if (Get-Process reflections -ErrorAction SilentlyContinue) { 'NOT STARTED: a reflections.exe is already running.'; exit 3 }
# A previous run's save would turn Enter into "Continue"; keep it aside rather than deleting it.
$saves = Join-Path $saved 'SaveGames'
if (Test-Path $saves) { $bak = "$saves.before_smoke_{0:HHmmss}" -f (Get-Date); Move-Item $saves $bak; "moved old SaveGames to $bak" }

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
function Shot($name) {
  $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
  $p = Join-Path $out $name; $bmp.Save($p, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose(); $p
}
$ws = New-Object -ComObject WScript.Shell
function Keys($k, $pause = 600) { [void]$ws.AppActivate($proc.Id); Start-Sleep -Milliseconds 250; $ws.SendKeys($k); Start-Sleep -Milliseconds $pause }
function Console($cmd) { Keys '`' 500; Keys ($cmd -replace '([+^%~(){}\[\]])', '{$1}') 200; Keys '{ENTER}' 700 }
function Alive { -not $proc.HasExited }

$t0 = Get-Date
$proc = Start-Process -FilePath $exe -ArgumentList '-windowed', '-ResX=1920', '-ResY=1080', '-log' -PassThru
"launched PID $($proc.Id), free commit {0:N1} GB" -f $free
Start-Sleep -Seconds 18
$steps = [ordered]@{}
Shot 'smoke_1_title.png' | Out-Null
Keys '{ENTER}' 1000                      # title: New Game (first item with no save)
Start-Sleep -Seconds 6; Keys '{ESC}' 500 # skip the intro cutscene, if one plays
Start-Sleep -Seconds $LoadSeconds
$steps['alive after New Game'] = Alive
Shot 'smoke_2_spawn.png' | Out-Null
Console 'CsvProfile Start'; Start-Sleep -Seconds $SampleSeconds; Console 'CsvProfile Stop'   # spawn sample
Console 'EnableCheats'; Console "BugItGo $Market"; Start-Sleep -Seconds 5
Shot 'smoke_3_market.png' | Out-Null
Console 'CsvProfile Start'; Start-Sleep -Seconds $SampleSeconds; Console 'CsvProfile Stop'   # market sample
Shot 'smoke_4_market_prompt.png' | Out-Null   # look for the "E" talk hint near a townsperson
Keys 'e' 1500; Shot 'smoke_5_after_E.png' | Out-Null; Keys '{ESC}' 800
Keys 'p' 1200; Shot 'smoke_6_pause_open.png' | Out-Null
Keys 'p' 1200; Shot 'smoke_7_pause_closed.png' | Out-Null
$steps['alive at the end'] = Alive
if (Alive) { $proc.CloseMainWindow() | Out-Null; Start-Sleep -Seconds 6; if (Alive) { Stop-Process -Id $proc.Id -Force } }

# Log check
$log = Get-ChildItem (Join-Path $saved 'Logs') -Filter 'reflections*.log' -ErrorAction SilentlyContinue | Where-Object LastWriteTime -gt $t0 | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $log) { 'FAIL: no game log written'; exit 4 }
$text = Get-Content $log.FullName
$errors = @($text | Select-String -Pattern 'Error:|Fatal error|Assertion failed|Unhandled Exception' | Where-Object { $_.Line -notmatch 'Warning:' })
$steps['map loaded'] = [bool]($text | Select-String -SimpleMatch "/Maps/$Map" | Select-Object -First 1)
$steps['crash folder'] = Test-Path (Join-Path $saved 'Crashes')
$steps['teleport ran'] = [bool]($text | Select-String -Pattern 'BugItGo|BugIt' | Select-Object -First 1)

# Frame times from the two CSV captures (oldest = spawn, newest = market)
function Stats($csv) {
  $lines = Get-Content $csv
  $head = $lines[0].Split(',')
  $i = [array]::IndexOf($head, 'FrameTime'); if ($i -lt 0) { return 'no FrameTime column' }
  $v = foreach ($l in $lines[1..($lines.Count - 1)]) { $c = $l.Split(','); $x = 0.0; if ($c.Count -gt $i -and [double]::TryParse($c[$i], [ref]$x)) { $x } }
  $v = @($v | Sort-Object); if ($v.Count -lt 5) { return 'too few frames' }
  $med = $v[[int]($v.Count * 0.5)]; $p95 = $v[[int]($v.Count * 0.95)]
  '{0} frames: median {1:N1} ms ({2:N0} fps), p95 {3:N1} ms, worst {4:N1} ms' -f $v.Count, $med, (1000 / $med), $p95, $v[-1]
}
$csvs = @(Get-ChildItem (Join-Path $saved 'Profiling\CSV') -Filter '*.csv' -ErrorAction SilentlyContinue | Where-Object LastWriteTime -gt $t0 | Sort-Object LastWriteTime)
''
foreach ($k in $steps.Keys) { "{0,-22} {1}" -f $k, $steps[$k] }
if ($csvs.Count -ge 1) { "frame time at spawn:   $(Stats $csvs[0].FullName)" } else { 'frame time at spawn:   no CSV written (console input may not have reached the game)' }
if ($csvs.Count -ge 2) { "frame time in market:  $(Stats $csvs[-1].FullName)" } else { 'frame time in market:  no second CSV' }
"log: $($log.FullName)  errors: $($errors.Count)"
$errors | Select-Object -First 8 | ForEach-Object { '  ' + $_.Line.Substring(0, [Math]::Min(200, $_.Line.Length)) }
"screenshots: $out\smoke_*.png (title, spawn, market, prompt, after E, pause open, pause closed): check them by eye"
if ($steps['alive at the end'] -and $steps['map loaded'] -and -not $steps['crash folder'] -and $errors.Count -eq 0) { 'SMOKE TEST PASS (log side; confirm the screenshots)'; exit 0 } else { 'SMOKE TEST NEEDS A LOOK'; exit 1 }
