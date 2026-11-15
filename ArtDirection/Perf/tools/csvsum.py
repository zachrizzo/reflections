"""Summarise an Unreal CSV profile.  python -I csvsum.py <file.csv> [--from SEC] [--to SEC] [--gpu N] [--json out]
Segments by time since capture start (sum of FrameTime)."""
import csv, sys, json, statistics as st, argparse
csv.field_size_limit(1 << 30)
ap = argparse.ArgumentParser(); ap.add_argument('csv'); ap.add_argument('--from', dest='t0', type=float, default=0)
ap.add_argument('--to', dest='t1', type=float, default=1e9); ap.add_argument('--gpu', type=int, default=14)
ap.add_argument('--json'); ap.add_argument('--label', default='')
ap.add_argument('--events', action='store_true')
ap.add_argument('--seg', action='store_true', help='one summary row per SEG_<name> console marker')
ap.add_argument('--settle', type=float, default=2.0)
a = ap.parse_args()
import re
rows = list(csv.reader(open(a.csv, newline='', encoding='utf-8', errors='replace')))
h = rows[0]
for r in rows[1:]:
    if r and r[0] == 'EVENTS' and len(r) > len(h): h = r   # full header written at the end on csvprofile stop
idx = {c: i for i, c in enumerate(h)}
data = []; t = 0.0; events = []
for r in rows[1:]:
    if not r or r[0].startswith('[') or r[0] == 'EVENTS': continue
    if len(r) < len(h): r = r + [''] * (len(h) - len(r))
    try: ft = float(r[idx['FrameTime']])
    except ValueError: continue
    t += ft / 1000.0
    if r[0]: events.append((round(t, 1), r[0][:120]))
    if a.t0 <= t <= a.t1: data.append(r)
def col(name):
    i = idx.get(name)
    if i is None: return []
    out = []
    for r in data:
        try: out.append(float(r[i]))
        except ValueError: pass
    return out
def pct(v, p):
    if not v: return float('nan')
    s = sorted(v); return s[min(len(s) - 1, int(p / 100 * len(s)))]
ft = col('FrameTime')
res = {'label': a.label, 'frames': len(ft), 'seconds': round(sum(ft) / 1000, 1)}
for c in ['FrameTime', 'GameThreadTime', 'RenderThreadTime', 'RHIThreadTime', 'GPUTime']:
    v = col(c); res[c] = {'med': round(pct(v, 50), 2), 'p95': round(pct(v, 95), 2), 'p99': round(pct(v, 99), 2), 'max': round(max(v), 1) if v else None}
res['fps_med'] = round(1000 / res['FrameTime']['med'], 1) if ft else None
res['hitches_50ms'] = sum(1 for x in ft if x > 50); res['hitches_100ms'] = sum(1 for x in ft if x > 100)
for c in ['PSO/PSOMisses', 'PSO/PSOMissesOnHitch', 'PSO/PSOComputeMisses']:
    res[c] = int(sum(col(c)))
for c in ['PhysicalUsedMB', 'GPUMem/LocalUsedMB', 'GPUMem/LocalBudgetMB', 'MassActors/NumSpawned', 'ActorCount/TotalActorCount', 'ActorCount/Character', 'RHI/DrawCalls', 'RHI/PrimitivesDrawn', 'LightCount/All', 'Ticks/Total', 'TextureStreaming/StreamingPool', 'TextureStreaming/WantedMips', 'Ticks/GroomComponent', 'Ticks/SkeletalMeshComponent']:
    v = col(c)
    if v: res[c] = {'first': round(v[0]), 'med': round(pct(v, 50)), 'last': round(v[-1]), 'max': round(max(v))}
gpu = {c[4:]: round(st.median(col(c)), 3) for c in h if c.startswith('GPU/') and col(c)}
res['gpu_passes_med'] = dict(sorted(gpu.items(), key=lambda kv: -kv[1])[:a.gpu])
gt = {c: round(st.median(col(c)), 3) for c in h if c.startswith('Exclusive/GameThread/') and col(c)}
res['gt_top_med'] = dict(sorted(gt.items(), key=lambda kv: -kv[1])[:10])
rt = {c: round(st.median(col(c)), 3) for c in h if c.startswith('Exclusive/RenderThread/') and col(c)}
res['rt_top_med'] = dict(sorted(rt.items(), key=lambda kv: -kv[1])[:8])
if a.events: res['events'] = events
if not a.seg: print(json.dumps(res, indent=1))
if a.json: json.dump(res, open(a.json, 'w'), indent=1)

if a.seg:
    marks = []
    for tt, ev in events:
        for m in re.finditer(r'Cmd: (SEG_[A-Za-z0-9_]+)', ev): marks.append((tt, m.group(1)[4:]))
    total = t
    print('| segment | s | med ms | P95 ms | P99 ms | fps med | GT med/P95 | RT med/P95 | RHI med | GPU med/P95 | >50ms | PSO miss | chars | top GPU passes (ms) |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    import subprocess, sys as _s
    for i, (tt, name) in enumerate(marks):
        t1 = marks[i + 1][0] if i + 1 < len(marks) else total
        sub = subprocess.run([_s.executable, '-I', __file__, a.csv, '--from', str(tt + a.settle), '--to', str(t1 - 0.5), '--gpu', '6', '--json', a.csv + '.' + name + '.json'], capture_output=True, text=True)
        d = json.loads(sub.stdout)
        if not d['frames']: continue
        F = d['FrameTime']; G = d['GameThreadTime']; R = d['RenderThreadTime']; X = d['GPUTime']; H = d['RHIThreadTime']
        ch = d.get('ActorCount/Character', {}).get('med', '')
        gp = ', '.join(f"{k} {v:.2f}" for k, v in d['gpu_passes_med'].items())
        print(f"| {name} | {d['seconds']} | {F['med']} | {F['p95']} | {F['p99']} | {d['fps_med']} | {G['med']}/{G['p95']} | {R['med']}/{R['p95']} | {H['med']} | {X['med']}/{X['p95']} | {d['hitches_50ms']} | {d['PSO/PSOMisses']} | {ch} | {gp} |")
