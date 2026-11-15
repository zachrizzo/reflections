#!/usr/bin/env bash
# build_gate.sh PID: wait for >= 6 GB free virtual memory and no build train, then take the PIE lock. Prints the start epoch.
until powershell -NoProfile -c "\$os=Get-CimInstance Win32_OperatingSystem; if ((\$os.FreeVirtualMemory/1MB) -ge 5 -and -not (Get-Process UnrealBuildTool -ErrorAction SilentlyContinue)) { exit 0 } else { exit 1 }"; do sleep 15; done
bash "$(dirname "$0")/lock.sh" acquire "crowd-looks: MetaHuman build $1 (no PIE, ~2 min)" 240 >/dev/null
date +%s > "$(dirname "$0")/../../Saved/CrowdLooks/.t0"
echo "gate open for $1 at $(date +%H:%M:%S)"
