#!/usr/bin/env bash
# wait_person.sh PID SINCE_EPOCH: wait until person_sync wrote PID's row after SINCE, release the lock, print the row.
P="$(dirname "$0")/../../Saved/CrowdLooks/pipeline.json"
until [ -f "$P" ] && [ "$(stat -c %Y "$P")" -ge "$2" ] && python -c "import json,sys; sys.exit(0 if 'secs' in json.load(open(sys.argv[1])).get(sys.argv[2],{}) else 1)" "$P" "$1"; do sleep 5; done
bash "$(dirname "$0")/lock.sh" release
python -c "import json,sys; r=json.load(open(sys.argv[1]))[sys.argv[2]]; print(sys.argv[2], 'ok' if r.get('ok') else 'ERR '+r.get('err',''), r.get('secs'), (r.get('look') or {}).get('set'))" "$P" "$1"
