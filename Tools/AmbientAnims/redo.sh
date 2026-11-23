#!/usr/bin/env bash
# redo.sh <category index>:<ClipId>,<ClipId> [...]
# Regenerates and re-bakes only the named clips after their prompts or rev changed in ambient_catalog.py:
#   snapshot current takes -> setup (writes the new prompts and seeds) -> Generate -> wait until each named clip
#   holds a new take -> bake just those clips over their old assets -> analyze the category.
# Same log, STOP file and PIE handling as run_all.sh.
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

step() {  # step <snippet> <ci> [run_in_editor args]: run with PIE retries, log the output
  for attempt in 1 2 3 4; do
    stopped
    pie_free || return 1
    out=$(python run_in_editor.py "$@" 2>&1)
    rc=$?
    log "$1 $2 rc=$rc $(echo "$out" | tr '\n' ' ' | cut -c1-600)"
    [ $rc -eq 0 ] && return 0
    echo "$out" | grep -q 'PIE running' || return 1
  done
  return 1
}

for arg in "$@"; do
  stopped
  ci="${arg%%:*}"
  only="[$(echo "${arg#*:}" | sed "s/[^,][^,]*/'&'/g")]"
  log "=== redo category $ci $only"
  step amb_snap "$ci" --set "ONLY=$only" || { log "snapshot failed for $ci"; continue; }
  step amb_setup "$ci" --wait 600 || { log "setup failed for $ci"; continue; }
  ok=0
  for attempt in 1 2 3 4; do
    step amb_generate "$ci" || break
    bash wait_generated.sh "$ci" 45 --set REDO=True > "$PROJ/Saved/KimodoAmbient/wait_$ci.log" 2>&1
    rc=$?
    log "wait $ci rc=$rc $(tail -2 "$PROJ/Saved/KimodoAmbient/wait_$ci.log" | tr '\n' ' ' | cut -c1-300)"
    [ $rc -eq 0 ] && { ok=1; break; }
    [ $rc -eq 2 ] || break
  done
  if [ $ok -eq 1 ]; then
    step amb_bake "$ci" --set "ONLY=$only" || log "bake failed for $ci"
    step amb_analyze "$ci" || log "analyze failed for $ci"
  else
    log "redo $ci: new takes did not all arrive; old assets kept"
  fi
  log "redo category $ci finished (new takes: $ok)"
done
step amb_close 0
log "redo done: $*"
