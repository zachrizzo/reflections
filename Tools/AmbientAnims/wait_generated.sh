#!/usr/bin/env bash
# wait_generated.sh <category index> <max minutes> [run_in_editor args, e.g. --set REDO=True]
# Polls the category's generation status every 30 s. Exit 0 when every clip is generated, 2 when no new clip has
# finished for 6 minutes (Kimodo was likely cancelled: press Generate again), 1 when time runs out.
# A Simulate/PIE session alone is not a failure: on 2026-11-22 generation kept running through a Simulate run.
cd "$(dirname "$0")"
end=$(( $(date +%s) + $2 * 60 ))
last=-1
since=$(date +%s)
while [ "$(date +%s)" -lt "$end" ]; do
  s=$(python run_in_editor.py amb_status "$1" "${@:3}" 2>&1 | tail -1)
  echo "$(date +%H:%M:%S) $s"
  case "$s" in *'"missing": []'*) echo DONE; exit 0 ;; esac
  n=$(echo "$s" | grep -o '"done": [0-9]*' | grep -o '[0-9]*$')
  if [ -n "$n" ] && [ "$n" != "$last" ]; then last=$n; since=$(date +%s); fi
  if [ $(( $(date +%s) - since )) -gt 360 ]; then echo STALLED; exit 2; fi
  sleep 30
done
echo TIMEOUT
exit 1
