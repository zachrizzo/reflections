"""Table of all runs: python -I report.py <runs dir> [prefix] [--settle 12]
Steady state = from --settle seconds to the end of the capture. Cold = first --settle seconds."""
import sys, os, json, subprocess, argparse
ap = argparse.ArgumentParser(); ap.add_argument('runs'); ap.add_argument('prefix', nargs='?', default='')
ap.add_argument('--settle', type=float, default=12); a = ap.parse_args()
tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'csvsum.py')
def summ(csv, t0, t1):
    out = subprocess.run([sys.executable, '-I', tool, csv, '--from', str(t0), '--to', str(t1), '--gpu', '8'], capture_output=True, text=True).stdout
    return json.loads(out)
print('| run | frames | FPS med | frame med / P95 / P99 ms | GT med / P95 | RT med / P95 | RHI med | GPU med / P95 | hitches >50 ms (steady) | cold 0-12 s: max ms, >50 ms, PSO misses | chars | RAM MB first to last | VRAM MB |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
gpus = {}
for d in sorted(os.listdir(a.runs)):
    if not d.startswith(a.prefix): continue
    csv = os.path.join(a.runs, d, 'profile.csv')
    if not os.path.exists(csv): continue
    s = summ(csv, a.settle, 1e9); c = summ(csv, 0, a.settle)
    if not s['frames']: continue
    F, G, R, H, X = s['FrameTime'], s['GameThreadTime'], s['RenderThreadTime'], s['RHIThreadTime'], s['GPUTime']
    pm = s.get('PhysicalUsedMB', {}); vm = s.get('GPUMem/LocalUsedMB', {})
    print(f"| {d} | {s['frames']} | {s['fps_med']} | {F['med']} / {F['p95']} / {F['p99']} | {G['med']} / {G['p95']} | {R['med']} / {R['p95']} | {H['med']} | {X['med']} / {X['p95']} | {s['hitches_50ms']} | {c['FrameTime']['max']}, {c['hitches_50ms']}, {c['PSO/PSOMisses'] + c['PSO/PSOComputeMisses']} | {s.get('ActorCount/Character', {}).get('med', '')} | {pm.get('first','')} to {pm.get('last','')} | {vm.get('med','')} |")
    gpus[d] = (s['gpu_passes_med'], s['gt_top_med'], s['rt_top_med'])
print()
for d, (g, gt, rt) in gpus.items():
    print(f"- **{d}** GPU: " + ', '.join(f"{k} {v:.2f}" for k, v in g.items()))
    print(f"  GT: " + ', '.join(f"{k.split('/')[-1]} {v:.2f}" for k, v in list(gt.items())[:6]))
    print(f"  RT: " + ', '.join(f"{k.split('/')[-1]} {v:.2f}" for k, v in list(rt.items())[:6]))
