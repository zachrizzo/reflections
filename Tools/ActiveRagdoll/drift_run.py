"""drift_run.py <out_dir> - take the PIE lock, run drift_test in a short Simulate session, save results and stills,
then stop PIE, restore the editor throttle and release the lock (always, even on failure)."""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1])
PHASESET = sys.argv[2] if len(sys.argv) > 2 else 'base'
GO, GET = {'plain': ('r_plain_go.py', 'r_plain_get.py'), 'rel': ('r_rel_go.py', 'r_rel_get.py'), 'relab': ('r_relab_go.py', 'r_relab_get.py'), 'who': ('r_who_go.py', 'r_who_get.py')}.get(PHASESET, ('r_drift_go.py', 'r_drift_get.py'))
os.makedirs(OUT, exist_ok=True)
VARS = os.path.join(OUT, '_vars.py')


def ue(*files, timeout=300, **gl):
    with open(VARS, 'w', encoding='utf-8') as f:
        f.write('OUTDIR = %r\n' % OUT)
        for k, v in gl.items():
            f.write('%s = %r\n' % (k, v))
    paths = [VARS] + [os.path.join(HERE, x) for x in files]
    r = subprocess.run([sys.executable, os.path.join(HERE, 'ue.py'), *paths, '--max', '400000'],
                       capture_output=True, text=True, timeout=timeout)
    return (r.stdout.strip() + ('\nERR ' + r.stderr.strip() if r.stderr.strip() else '')).strip()


def lock(*a):
    r = subprocess.run([sys.executable, os.path.join(HERE, 'lock.py'), *a], capture_output=True, text=True, timeout=1800)
    return r.stdout.strip()


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


got = lock('take', 'active-ragdoll: ~2 min Simulate on L_TestTown, pose-drift measurement', '240', '1500')
log('lock', got)
if not got.startswith('ACQUIRED'):
    sys.exit(1)
try:
    log('throttle', ue('r_common.py', 'r_thr_off.py'))
    st = ue('r_common.py', 'r_start.py', GO, PHASESET=PHASESET)
    log('start', st[:1500])
    t0 = time.time(); last_refresh = time.time(); res = None
    failed = 'Error' in st or 'RPCERR' in st
    while not failed and time.time() - t0 < 150:
        time.sleep(5)
        if time.time() - last_refresh > 30:
            lock('refresh', '240'); last_refresh = time.time()
        txt = ue('r_common.py', GET)
        try:
            j = json.loads(txt)
        except Exception:
            log('get?', txt[:400])
            bad = locals().get('bad', 0) + 1
            if bad >= 3:
                log('giving up after 3 failed reads'); break
            continue
        log('phase', j.get('i'), '/', j.get('n'), 'err', j.get('error'))
        if j.get('done'):
            res = j; break
    if res:
        open(os.path.join(OUT, 'drift_results.json'), 'w', encoding='utf-8').write(json.dumps(res, indent=1))
        log('results saved; error', res.get('error'))
        if not res.get('error') and PHASESET not in ('ab', 'body', 'ctrl', 'plain', 'rel', 'relab', 'arms', 'relax', 'coll', 'sync', 'who'):
            for grav, views in ((1.0, ('front', 'side_proto', 'side_ref')), (0.0, ('side_proto',))):
                log('prep', ue('r_common.py', 'r_drift_prep.py', GRAV=grav))
                time.sleep(3.0)
                for v in views:
                    ue('r_common.py', 'r_drift_cam.py', VIEW=v)
                    time.sleep(0.8)
                    shot = v + ('' if grav == 1.0 else '_nograv')
                    log('shot', ue('r_common.py', 'r_drift_cap.py', SHOT=shot)[-200:])
    else:
        log('no results (timeout)')
finally:
    log('stop', ue('r_common.py', 'r_stop.py'))
    log('throttle', ue('r_common.py', 'r_thr_restore.py'))
    log('lock', lock('release'))
