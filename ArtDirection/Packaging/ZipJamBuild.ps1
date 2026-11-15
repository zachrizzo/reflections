# Zip a staged jam build for upload, EXCLUDING anything a test run leaves behind:
# any Saved/ folder (logs, SaveGames/*.sav, crash-reporter config), *.sav, *.log, and keys.json.
# Usage: powershell -ExecutionPolicy Bypass -File ArtDirection\Packaging\ZipJamBuild.ps1 -Source <...\Saved\JamBuild\Windows> -Dest <...\TeamName_Reflections.zip>
param([Parameter(Mandatory)][string]$Source, [Parameter(Mandatory)][string]$Dest)
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
$Source = (Resolve-Path $Source).Path.TrimEnd('\')
$root = Split-Path $Source -Leaf                      # top folder name inside the zip
$tmp = "$Dest.partial"
if (Test-Path $tmp) { Remove-Item $tmp -Force }
$zip = [System.IO.Compression.ZipFile]::Open($tmp, [System.IO.Compression.ZipArchiveMode]::Create)
$added = 0; $skipped = @()
try {
  foreach ($f in Get-ChildItem $Source -Recurse -File) {
    $rel = $f.FullName.Substring($Source.Length + 1)
    $parts = $rel -split '\\'
    if ($parts -contains 'Saved' -or $f.Extension -in '.sav', '.log' -or $f.Name -ieq 'keys.json') { $skipped += $rel; continue }
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f.FullName, "$root/" + ($rel -replace '\\', '/'), [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    $added++
  }
} finally { $zip.Dispose() }
Move-Item $tmp $Dest -Force
"files zipped: $added; excluded: $($skipped.Count)"
$skipped | Select-Object -First 10 | ForEach-Object { "  excluded: $_" }
"zip: $Dest  ({0:N1} MB, {1} bytes)" -f ((Get-Item $Dest).Length / 1MB), (Get-Item $Dest).Length
