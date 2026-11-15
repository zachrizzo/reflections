#!/usr/bin/env bash
# Wait for >= 5 GB free virtual memory and no build train; print the epoch to pass to wait_person.sh.
until powershell -NoProfile -c "\$os=Get-CimInstance Win32_OperatingSystem; if ((\$os.FreeVirtualMemory/1MB) -ge 5 -and -not (Get-Process UnrealBuildTool -ErrorAction SilentlyContinue)) { exit 0 } else { exit 1 }"; do sleep 15; done
date +%s
