#!/usr/bin/env bash
# run_all.sh <category index> [...]
# Generates and bakes whole categories one after another in the shared editor:
#   setup -> Generate -> wait -> bake -> analyze, per category.
# A PIE start cancels Kimodo generation, so it waits for PIE to end and presses Generate again (up to 4 times).
# Log: Saved/KimodoAmbient/run.log. Stop it by creating Saved/KimodoAmbient/STOP (checked between steps).
cd "$(dirname "$0")"
PROJ="$(cd ../.. && pwd)"
LOG="$PROJ/Saved/KimodoAmbient/run.log"
STOP="$PROJ/Saved/KimodoAmbient/STOP"
mkdir -p "$PROJ/Saved/KimodoAmbient"
log() { echo "$(date +%H:%M:%S) $*" | tee -a "$LOG"; }
stopped() { [ -f "$STOP" ] && { log "STOP file found, exiting"; exit 3; }; }

pie_free() {  # wait (up to 30 min) until no PIE lock is held and no PIE world exists
  for _ in $(seq 1 180); do
    stopped
    local held=0
    if [ -f "$PROJ/Saved/PIE_LOCK.json" ]; then
      exp=$(grep -o '"expires_epoch": *[0-9]*' "$PROJ/Saved/PIE_LOCK.json" | grep -o '[0-9]*$')
      [ -n "$exp" ] && [ "$(date +%s)" -le "$exp" ] && held=1
    fi
    if [ $held -eq 0 ] && python run_in_editor.py amb_status 0 2>/dev/null | grep -q '"pie": false'; then
      return 0
    fi
    sleep 10
  done
  log "PIE still busy after 30 min"
  return 1
}

step() {  # step <snippet> <ci>: run with PIE retries, log the output
  for attempt in 1 2 3 4; do
    stopped
    pie_free || return 1
    out=$(python run_in_editor.py "$1" "$2" 2>&1)
    rc=$?
    log "$1 $2 rc=$rc $(echo "$out" | tr '\n' ' ' | cut -c1-600)"
    [ $rc -eq 0 ] && return 0
    echo "$out" | grep -q 'PIE running' || return 1
  done
  return 1
}

for ci in "$@"; do
  stopped
  log "=== category $ci"
  step amb_setup "$ci" || { log "setup failed for $ci"; continue; }
  ok=0
  for attempt in 1 2 3 4; do
    step amb_generate "$ci" || break
    bash wait_generated.sh "$ci" 45 > "$PROJ/Saved/KimodoAmbient/wait_$ci.log" 2>&1
    rc=$?
    log "wait $ci rc=$rc $(tail -2 "$PROJ/Saved/KimodoAmbient/wait_$ci.log" | tr '\n' ' ' | cut -c1-300)"
    [ $rc -eq 0 ] && { ok=1; break; }
    [ $rc -eq 2 ] || break   # timeout or error: bake what exists and move on
  done
  step amb_bake "$ci" || log "bake failed for $ci"
  step amb_analyze "$ci" || log "analyze failed for $ci"
  log "category $ci finished (all generated: $ok)"
done
step amb_close 0
log "run_all done: $*"
