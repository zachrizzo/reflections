# Development only: starts the loopback spell-recipe relay ("describe your spell" via OpenAI).
# The relay reads the OpenAI key itself from ~/.openai/api_key (or $env:REFLECTIONS_OPENAI_KEY_FILE); this script
# never touches the key, and neither the editor nor the project ever sees it.
#   -RelayOnly   run just the relay in this window, for an editor that is already open. The relay publishes its
#                per-launch token to Saved/SpellCrafting/relay-token, where dev builds find it. Ctrl+C stops it.
#   (default)    close the editor first; starts the relay hidden plus a fresh editor that gets the token through
#                the environment, and stops the relay when the editor exits.
# The NPC voice relay has its own launcher: Tools/RealtimeVoice/Start-VoiceDevelopment.ps1.
param(
    [string]$Editor = 'C:\Program Files\Epic Games\UE_5.9\Engine\Binaries\Win64\UnrealEditor.exe',
    [string]$Python = 'python',
    [switch]$RelayOnly
)
$ErrorActionPreference = 'Stop'
$relayScript = Join-Path $PSScriptRoot 'recipe_relay.py'
& $Python -c 'import websockets'
if ($LASTEXITCODE -ne 0) { throw 'Install the Python websockets package in the selected Python environment.' }
$keyFile = if ($env:REFLECTIONS_OPENAI_KEY_FILE) { $env:REFLECTIONS_OPENAI_KEY_FILE } else { Join-Path $HOME '.openai\api_key' }
if (-not (Test-Path -LiteralPath $keyFile)) { throw "No OpenAI key file at $keyFile." }

if ($RelayOnly) {
    & $Python $relayScript
    return
}

$project = (Resolve-Path (Join-Path $PSScriptRoot '..\..\reflections.uproject')).Path
if (-not (Test-Path -LiteralPath $Editor)) { throw 'Unreal Editor was not found at the configured path.' }
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) { throw 'Close Unreal Editor first, or use -RelayOnly with the open editor.' }

function New-LocalToken {
    $random = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($random) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($random)
}

# The editor and the relay inherit a random local token, never a key.
$env:REFLECTIONS_SPELL_LOCAL_TOKEN = New-LocalToken
$relays = @()
try {
    $relays += Start-Process -FilePath $Python -ArgumentList @('"' + $relayScript + '"') -WindowStyle Hidden -PassThru
    $editorProcess = Start-Process -FilePath $Editor -ArgumentList @('"' + $project + '"') -PassThru
    Wait-Process -Id $editorProcess.Id
}
finally {
    Remove-Item Env:REFLECTIONS_SPELL_LOCAL_TOKEN -ErrorAction SilentlyContinue
    foreach ($relay in $relays) { if ($relay -and -not $relay.HasExited) { Stop-Process -Id $relay.Id -ErrorAction SilentlyContinue } }
}
