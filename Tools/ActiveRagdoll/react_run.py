"""react_run.py <out_dir> - verification run for the dormant-by-default prototype: takes the PIE lock, runs the
ev_react.py event list at time dilation 0.35 while recording the viewport, saves the state log, then always stops
PIE, restores the editor throttle and releases the lock."""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1])
os.makedirs(OUT, exist_ok=True)
VARS = os.path.join(OUT, '_vars.py')
TD = float(sys.argv[2]) if len(sys.argv) > 2 else 0.35
EVFILE = sys.argv[3] if len(sys.argv) > 3 else 'ev_react.py'
T_END = float(sys.argv[4]) if len(sys.argv) > 4 else 34.0


def ue(*files, timeout=300, **gl):
    with open(VARS, 'w', encoding='utf-8') as f:
        f.write('OUTDIR = %r\n' % OUT)
        for k, v in gl.items():
            f.write('%s = %r\n' % (k, v))
    r = subprocess.run([sys.executable, os.path.join(HERE, 'ue.py'), VARS, *[os.path.join(HERE, x) for x in files], '--max', '400000'],
                       capture_output=True, text=True, timeout=timeout)
    return (r.stdout.strip() + ('\nERR ' + r.stderr.strip() if r.stderr.strip() else '')).strip()


def lock(*a):
    return subprocess.run([sys.executable, os.path.join(HERE, 'lock.py'), *a], capture_output=True, text=True, timeout=1800).stdout.strip()


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


got = lock('take', 'active-ragdoll: ~3 min Simulate on L_TestTown, reaction recording', '240', '1500')
log('lock', got)
if not got.startswith('ACQUIRED'):
    sys.exit(1)
recording = False
try:
    log('throttle', ue('r_common.py', 'r_thr_off.py'))
    st = ue('r_common.py', 'r_start.py', SPOT=(700.0, 450.0, 8.0))  # (700, 0) has another session's Sequencer-spawned Kellan
    log('start', st[:600])
    if 'Error' in st or 'RPCERR' in st:
        raise SystemExit('start failed')
    log('rec', ue('r_common.py', 'r_td.py', EVFILE, 'r_rec_start.py', TD=TD)[:400])
    recording = True
    t0 = time.time(); last_refresh = time.time(); bad = 0; timeline = []
    while time.time() - t0 < 200:
        time.sleep(4)
        if time.time() - last_refresh > 30:
            lock('refresh', '240'); last_refresh = time.time()
        txt = ue('r_common.py', 'r_react_status.py')
        try:
            j = json.loads(txt)
        except Exception:
            bad += 1; log('status?', txt[:300])
            if bad >= 3:
                break
            continue
        timeline.append(j); log('status', j)
        if j['t'] >= T_END and j['state'] == 'DORMANT':
            break
    log('recstop', ue('r_common.py', 'r_rec_stop.py')[:800]); recording = False
    open(os.path.join(OUT, 'react_log.json'), 'w', encoding='utf-8').write(ue('r_common.py', 'r_react_log.py'))
    open(os.path.join(OUT, 'react_timeline.json'), 'w', encoding='utf-8').write(json.dumps(timeline, indent=1))
finally:
    if recording:
        log('recstop', ue('r_common.py', 'r_rec_stop.py')[:300])
    ue('r_common.py', 'r_td.py', TD=1.0)
    log('stop', ue('r_common.py', 'r_stop.py'))
    log('throttle', ue('r_common.py', 'r_thr_restore.py'))
    log('lock', lock('release'))
