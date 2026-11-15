#!/usr/bin/env bash
# Shared PIE lock from the shell (house rule: Saved/PIE_LOCK.json, at most 240 s).
#   lock.sh acquire "<purpose>" [seconds]   waits for a free or expired lock, then takes it
#   lock.sh release                          deletes the lock if it is ours
LOCK="$(dirname "$0")/../../Saved/PIE_LOCK.json"
OWNER="crowd-looks (NPC appearance side session)"
case "$1" in
  acquire)
    secs=${3:-240}; [ "$secs" -gt 240 ] && secs=240
    while [ -f "$LOCK" ]; do
      exp=$(python -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8-sig')); print(int(float(d.get('expires_epoch',0))))" "$LOCK" 2>/dev/null || echo 0)
      own=$(python -c "import json,sys; print(json.load(open(sys.argv[1],encoding='utf-8-sig')).get('owner',''))" "$LOCK" 2>/dev/null)
      [ "$own" = "$OWNER" ] && break
      [ "$exp" -le "$(date +%s)" ] && break
      sleep 5
    done
    now=$(date +%s); exp=$((now+secs))
    python -c "import json,sys,time; json.dump({'owner':sys.argv[1],'purpose':sys.argv[2],'acquired_epoch':int(sys.argv[3]),'expires_epoch':int(sys.argv[4]),'expires_local':time.strftime('%H:%M:%S',time.localtime(int(sys.argv[4])))},open(sys.argv[5],'w'))" "$OWNER" "$2" "$now" "$exp" "$LOCK"
    echo "locked until $(date -d @$exp +%H:%M:%S)";;
  release)
    own=$(python -c "import json,sys; print(json.load(open(sys.argv[1],encoding='utf-8-sig')).get('owner',''))" "$LOCK" 2>/dev/null)
    [ "$own" = "$OWNER" ] && rm -f "$LOCK" && echo released;;
esac
