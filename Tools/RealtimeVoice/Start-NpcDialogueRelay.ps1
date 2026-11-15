<#
Starts the local NPC dialogue relay for Play in Editor (no editor restart needed).

The relay reads the Gemini key itself, from GEMINI_API_KEY or ~/.gemini/api_key; this script never reads,
prints or passes the key. On start the relay writes a random per-launch token to Saved/NpcDialogue/relay.token,
which editor builds read; the token file is removed when the relay stops. Log: Saved/NpcDialogue/relay.log.

  .\Start-NpcDialogueRelay.ps1              # start in a minimized window
  .\Start-NpcDialogueRelay.ps1 -Foreground  # run in this console (Ctrl+C stops it)
  .\Start-NpcDialogueRelay.ps1 -Stop        # stop a running relay
#>
param([string]$Python = 'python', [switch]$Foreground, [switch]$Stop)
$ErrorActionPreference = 'Stop'
$relay = Join-Path $PSScriptRoot 'relay.py'
$running = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -like '*RealtimeVoice*relay.py*' }
if ($Stop) {
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
    $token = Join-Path $PSScriptRoot '..\..\Saved\NpcDialogue\relay.token'
    if (Test-Path $token) { Remove-Item $token }
    Write-Host "Stopped $(@($running).Count) relay process(es)."
    return
}
if ($running) { Write-Host 'The NPC dialogue relay is already running.'; return }
& $Python -c 'import websockets, httpx' 2>$null
if ($LASTEXITCODE -ne 0) { throw "Install the relay's packages first: $Python -m pip install -r requirements.txt" }
if ($Foreground) { & $Python $relay; return }
Start-Process -FilePath $Python -ArgumentList @('"' + $relay + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Minimized
Write-Host 'NPC dialogue relay started on ws://127.0.0.1:8765 (log: Saved/NpcDialogue/relay.log).'
