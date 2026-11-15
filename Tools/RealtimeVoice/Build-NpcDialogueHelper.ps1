<#
Builds the NPC dialogue helper that ships with the game: dist\NpcDialogueRelay\NpcDialogueRelay.exe (PyInstaller,
one-folder layout) plus voices.json, an optional starter reply cache (seed\) and the audio roster (roster.json).

The game starts it from <Game>\reflections\Content\NpcDialogue\Relay\ when keys.json is present there; packaging
copies this folder into the staged build (see ArtDirection/NpcDialogue/README.md). NO KEYS are ever put in the output:
the user drops keys.json in afterwards (keys.json.example shows the format). The helper needs ONE key: a Gemini
API key from the Google Cloud project that holds the audio session's designed voices. No OpenAI key is used.

  .\Build-NpcDialogueHelper.ps1                 # build
  .\Build-NpcDialogueHelper.ps1 -NoSeed         # without the starter cache
#>
param([string]$Python = 'python', [switch]$NoSeed,
      [string]$Roster = (Join-Path $PSScriptRoot '..\..\ArtDirection\Audio\data\voice_roster_dialogue.json'))
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $here '..\..')).Path
Push-Location $here
try {
    $ErrorActionPreference = 'Continue'  # PyInstaller logs to stderr; judge it by its exit code
    & $Python -m PyInstaller --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Install PyInstaller first: $Python -m pip install pyinstaller" }
    & $Python -m PyInstaller --noconfirm --clean --onedir --console --name NpcDialogueRelay `
        --add-data "voices.json;." --hidden-import pipeline --hidden-import tts --hidden-import actions `
        --hidden-import gemini --hidden-import composing --hidden-import api_keys `
        --exclude-module tkinter --exclude-module unittest --exclude-module numpy --exclude-module PIL --exclude-module yaml `
        --exclude-module zstandard --exclude-module matplotlib --exclude-module pandas relay.py 2>&1 | Where-Object { "$_" -match 'ERROR|WARNING: lib' }
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
    $ErrorActionPreference = 'Stop'
    $out = Join-Path $here 'dist\NpcDialogueRelay'
    if (Test-Path (Join-Path $out 'keys.json')) { Remove-Item (Join-Path $out 'keys.json') }  # never ship keys
    @'
{
  "gemini_api_key": "AIza... (from the Google Cloud project that holds the designed voices; restrict it to the Generative Language API and cap its quota; see ArtDirection/NpcDialogue/README.md)"
}
'@ | Set-Content -Encoding utf8 (Join-Path $out 'keys.json.example')
    $seedSource = Join-Path $repo 'Saved\NpcDialogue\cache'
    if (-not $NoSeed -and (Test-Path (Join-Path $seedSource 'index.json'))) {
        Copy-Item -Recurse -Force $seedSource (Join-Path $out 'seed')
    }
    if ($Roster -and (Test-Path $Roster)) { Copy-Item -Force $Roster (Join-Path $out 'roster.json') }
    $bytes = (Get-ChildItem -Recurse -File $out | Measure-Object -Sum Length).Sum
    "Built $out ({0:N1} MB, {1} files)" -f ($bytes / 1MB), (Get-ChildItem -Recurse -File $out).Count
}
finally { Pop-Location }
