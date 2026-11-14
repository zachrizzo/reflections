param(
    [string]$Editor = 'C:\Program Files\Epic Games\UE_5.9\Engine\Binaries\Win64\UnrealEditor.exe',
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..\..\reflections.uproject')).Path
if (-not (Test-Path -LiteralPath $Editor)) { throw 'Unreal Editor was not found at the configured path.' }
& $Python -c 'import websockets' 
if ($LASTEXITCODE -ne 0) { throw 'Install the Python websockets package in the selected Python environment.' }
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) { throw 'Close Unreal Editor before starting this isolated voice development session.' }

# Both processes inherit the random local token; only the relay inherits the API key.
$random = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($random) } finally { $rng.Dispose() }
$env:REFLECTIONS_VOICE_LOCAL_TOKEN = [Convert]::ToBase64String($random)
$secureKey = Read-Host 'OpenAI API key (hidden; kept in memory for this session)' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try { $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer) }
if (-not $env:OPENAI_API_KEY) { throw 'A key is required.' }
$relay = $null
try {
    $relay = Start-Process -FilePath $Python -ArgumentList @('"' + (Join-Path $PSScriptRoot 'relay.py') + '"') -WindowStyle Hidden -PassThru
    Remove-Item Env:OPENAI_API_KEY
    $editorProcess = Start-Process -FilePath $Editor -ArgumentList @('"' + $project + '"') -PassThru
    Wait-Process -Id $editorProcess.Id
}
finally {
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:REFLECTIONS_VOICE_LOCAL_TOKEN -ErrorAction SilentlyContinue
    if ($relay -and -not $relay.HasExited) { Stop-Process -Id $relay.Id -ErrorAction SilentlyContinue }
}
