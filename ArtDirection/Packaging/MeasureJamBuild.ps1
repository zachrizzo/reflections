# Measure a staged jam build: compressed bytes in the IoStore container, by part, with the Gray London map broken out.
# Compressed bytes in the pak are about what the zip costs (Oodle data barely shrinks again).
# Usage: powershell -ExecutionPolicy Bypass -File ArtDirection\Packaging\MeasureJamBuild.ps1 [-Stage <...\Saved\JamBuild\Windows>] [-Zip <zip>] [-Csv <out.csv>]
param(
  [string]$Stage = (Join-Path $PSScriptRoot '..\..\Saved\JamBuild\Windows'),
  [string]$Zip = '',
  [string]$Csv = (Join-Path $env:TEMP 'ReflectionsJamPakList.csv')
)
$ErrorActionPreference = 'Stop'
$Stage = (Resolve-Path $Stage).Path
$paks = Join-Path $Stage 'reflections\Content\Paks'
$utoc = Join-Path $paks 'reflections-Windows.utoc'
$unrealPak = 'C:\Program Files\Epic Games\UE_5.9\Engine\Binaries\Win64\UnrealPak.exe'
& $unrealPak -ListContainer="$utoc" -csv="$Csv" | Out-Null
$rows = (Get-Content $Csv) -replace ', ', ',' | ConvertFrom-Csv
function MB($b) { '{0,8:N1} MB' -f ($b / 1MB) }

# Map each chunk to a /Game-style path.
foreach ($r in $rows) {
  $p = $r.Filename -replace '^\.\./\.\./\.\./reflections/Content/', '/Game/' -replace '^\.\./\.\./\.\./Engine/Content/', '/Engine/' -replace '\.(uasset|umap|ubulk|uptnl|m\.ubulk)$', ''
  if ($p -like '../../../*') { $p = '/' + $p.Substring(9) }   # plugin content, e.g. /Engine/Plugins/<...>/Content
  if (-not $p) { $p = $r.PackageName }
  $r | Add-Member -NotePropertyName P -NotePropertyValue $p
  $r | Add-Member -NotePropertyName B -NotePropertyValue ([int64]$r.CompressedSize)
}
$total = ($rows | Measure-Object B -Sum).Sum
$shader = ($rows | Where-Object { $_.ChunkType -like 'ShaderCode*' } | Measure-Object B -Sum).Sum
$assets = $rows | Where-Object { $_.ChunkType -notlike 'ShaderCode*' -and $_.ChunkType -ne 'ContainerHeader' }

"Container (compressed): $(MB $total)   shader code: $(MB $shader)   assets: $(MB ($total - $shader))"
$loose = Get-ChildItem $paks -File | Where-Object Extension -in '.pak', '.ucas'
foreach ($f in $loose) { "  file {0,-28} $(MB $f.Length)" -f $f.Name }

# Gray London by part. External actors are folded into the generated streaming cells at cook time.
$gl = $assets | Where-Object { $_.P -like '/Game/GrayLondon/*' -or $_.P -like '/Game/__External*/GrayLondon/*' -or $_.P -like '/Game/Fab/London_Street_Props*' }
function Part($p) {
  $n = ($p -split '/')[-1]
  if ($p -match '/_Generated_/|/__External(Actors|Objects)__/' -or $p -like '/Game/GrayLondon/Maps/*') { return 'World Partition cells + map' }
  if ($p -match '/Textures/' -or $n -match '^(T_|texture_)' -or $n -match '_(diff|Diffuse|nor_gl|nor_dx|Normal|rough|Rough|alpha|arm|ao|texture_\d+)(_\d+k)?$') { return 'Textures' }
  if ($n -match '^(M_|MI_|MF_)' -or $p -match '/Materials/') { return 'Materials (assets only)' }
  if ($n -like 'PCG_*') { return 'PCG graphs' }
  if ($p -like '/Game/GrayLondon/Geodata/Tiles/*') { return 'Meshes: city tiles' }
  return 'Meshes: other (landmarks, props, markings)'
}
$glTotal = ($gl | Measure-Object B -Sum).Sum
''
"Gray London (shader code not included; compare the shader total with the previous build): $(MB $glTotal)"
$gl | Group-Object { Part $_.P } | ForEach-Object { [pscustomobject]@{ Part = $_.Name; B = ($_.Group | Measure-Object B -Sum).Sum; N = ($_.Group | Select-Object -ExpandProperty P -Unique).Count } } |
  Sort-Object B -Descending | ForEach-Object { "  {0,-44} $(MB $_.B)  {1,5} packages" -f $_.Part, $_.N }

# Everything by owner folder (two levels under /Game, one under plugins and /Engine).
''
'Top 12 folders:'
$assets | Group-Object { $s = $_.P -split '/'; if ($s[1] -eq 'Game' -and $s.Count -gt 3) { '/Game/' + $s[2] + '/' + $s[3] } else { ($s[0..([Math]::Min(4, $s.Count - 2))] -join '/') } } |
  ForEach-Object { [pscustomobject]@{ F = $_.Name; B = ($_.Group | Measure-Object B -Sum).Sum } } | Sort-Object B -Descending | Select-Object -First 12 |
  ForEach-Object { "  {0,-60} $(MB $_.B)" -f $_.F }
''
'Top 10 packages:'
$assets | Group-Object P | ForEach-Object { [pscustomobject]@{ P = $_.Name; B = ($_.Group | Measure-Object B -Sum).Sum } } | Sort-Object B -Descending | Select-Object -First 10 |
  ForEach-Object { "  {0,-90} $(MB $_.B)" -f $_.P }

# Loose (UFS) files live in the .pak: check the crowd's street spots made it.
''
$pak = Join-Path $paks 'reflections-Windows.pak'
$list = & $unrealPak "$pak" -List 2>$null
$spots = $list | Select-String -SimpleMatch 'Crowd/Spots/'
if ($spots) { "Crowd spots in the pak: $($spots.Count) file(s)" } else { 'WARNING: no Crowd/Spots/*.json in the pak (street scenes will be empty).' }
if ($Zip -and (Test-Path $Zip)) { "Zip: $(MB (Get-Item $Zip).Length)  ($Zip)" }
"Staged folder: $(MB ((Get-ChildItem $Stage -Recurse -File | Measure-Object Length -Sum).Sum))"
