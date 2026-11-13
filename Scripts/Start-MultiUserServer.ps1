[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ipaddress]$ListenAddress,

    [ValidateRange(1, 65535)]
    [int]$Port = 55059
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$project = Get-Content -LiteralPath (Join-Path $projectRoot 'reflections.uproject') -Raw | ConvertFrom-Json
$engineBuilds = 'HKCU:\Software\Epic Games\Unreal Engine\Builds'
$engineRoot = Get-ItemPropertyValue -LiteralPath $engineBuilds -Name $project.EngineAssociation
$serverPath = Join-Path $engineRoot 'Engine\Binaries\Win64\UnrealMultiUserServer.exe'

if (-not (Test-Path -LiteralPath $serverPath -PathType Leaf)) {
    throw "The Multi-User server executable was not found at $serverPath."
}

$address = $ListenAddress.IPAddressToString
$adapterAddress = Get-NetIPAddress -IPAddress $address -AddressFamily IPv4 -ErrorAction SilentlyContinue
if (-not $adapterAddress -or $ListenAddress.Equals([ipaddress]::Loopback)) {
    throw "Use the IPv4 address of this PC's LAN adapter. $address is not a LAN adapter address on this PC."
}

$serverName = 'Reflections LAN'
$endpoint = "${address}:${Port}"
$serverData = Join-Path $projectRoot 'Saved\MultiUserServer'
$workingDirectory = Join-Path $serverData 'Sessions'
$archiveDirectory = Join-Path $serverData 'Archives'
$logPath = Join-Path $serverData 'Server.log'

$existingEndpoint = Get-NetUDPEndpoint -LocalAddress $address -LocalPort $Port -ErrorAction SilentlyContinue
if ($existingEndpoint) {
    $existingServer = Get-CimInstance Win32_Process -Filter "ProcessId=$($existingEndpoint.OwningProcess)"
    if ($existingServer.ExecutablePath -ieq $serverPath -and $existingServer.CommandLine.Contains($workingDirectory)) {
        Write-Output "$serverName is already running at $endpoint. Log file: $logPath"
        return
    }
    throw "UDP $endpoint is already in use by process $($existingEndpoint.OwningProcess)."
}

New-Item -ItemType Directory -Path $serverData -Force | Out-Null
$serverArguments = @(
    "-CONCERTSERVER=`"$serverName`""
    "-CONCERTWORKINGDIR=`"$workingDirectory`""
    "-CONCERTSAVEDDIR=`"$archiveDirectory`""
    "-abslog=`"$logPath`""
    "-UDPMESSAGING_TRANSPORT_UNICAST=$endpoint"
    '-unattended'
)
$server = Start-Process -FilePath $serverPath -ArgumentList $serverArguments -WindowStyle Hidden -PassThru
Write-Output "Started $serverName at $endpoint (PID $($server.Id)). Log file: $logPath"
