# Development only: starts the loopback spell-recipe relay and a fresh editor that can reach it.
# The OpenAI key is read without echo, handed only to the relay process, and never saved. -WithVoice also starts
# Tools/RealtimeVoice/relay.py with its own token, so one editor session can use both.
param(
    [string]$Editor = 'C:\Program Files\Epic Games\UE_5.9\Engine\Binaries\Win64\UnrealEditor.exe',
    [string]$Python = 'python',
    [switch]$WithVoice
)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..\..\reflections.uproject')).Path
if (-not (Test-Path -LiteralPath $Editor)) { throw 'Unreal Editor was not found at the configured path.' }
& $Python -c 'import websockets'
if ($LASTEXITCODE -ne 0) { throw 'Install the Python websockets package in the selected Python environment.' }
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) { throw 'Close Unreal Editor before starting this development session.' }

function New-LocalToken {
    $random = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($random) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($random)
}

# The editor and the relays inherit the random local tokens; only the relays inherit the API key.
$env:REFLECTIONS_SPELL_LOCAL_TOKEN = New-LocalToken
if ($WithVoice) { $env:REFLECTIONS_VOICE_LOCAL_TOKEN = New-LocalToken }
$secureKey = Read-Host 'OpenAI API key (hidden; kept in memory for this session)' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try { $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer) }
if (-not $env:OPENAI_API_KEY) { throw 'A key is required.' }
$relays = @()
try {
    $relays += Start-Process -FilePath $Python -ArgumentList @('"' + (Join-Path $PSScriptRoot 'recipe_relay.py') + '"') -WindowStyle Hidden -PassThru
    if ($WithVoice) {
        $relays += Start-Process -FilePath $Python -ArgumentList @('"' + (Join-Path $PSScriptRoot '..\RealtimeVoice\relay.py') + '"') -WindowStyle Hidden -PassThru
    }
    Remove-Item Env:OPENAI_API_KEY
    $editorProcess = Start-Process -FilePath $Editor -ArgumentList @('"' + $project + '"') -PassThru
    Wait-Process -Id $editorProcess.Id
}
finally {
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:REFLECTIONS_SPELL_LOCAL_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:REFLECTIONS_VOICE_LOCAL_TOKEN -ErrorAction SilentlyContinue
    foreach ($relay in $relays) { if ($relay -and -not $relay.HasExited) { Stop-Process -Id $relay.Id -ErrorAction SilentlyContinue } }
}
