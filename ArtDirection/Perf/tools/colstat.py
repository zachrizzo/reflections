"""python -I colstat.py <csv> <column substring> [threshold_ms] [--from s]: median/P95/P99/max and frames over threshold, per matching column."""
import csv, sys, statistics as st
csv.field_size_limit(1 << 30)
p, sub = sys.argv[1], sys.argv[2]; thr = float(sys.argv[3]) if len(sys.argv) > 3 else 20; t0 = float(sys.argv[sys.argv.index('--from') + 1]) if '--from' in sys.argv else 12
rows = list(csv.reader(open(p, encoding='utf-8', errors='replace'))); h = rows[0]
for r in rows[1:]:
    if r and r[0] == 'EVENTS' and len(r) > len(h): h = r
ix = {c: i for i, c in enumerate(h)}; cols = [c for c in h if sub.lower() in c.lower()]
vals = {c: [] for c in cols}; t = 0
for r in rows[1:]:
    if not r or r[0] == 'EVENTS' or r[0].startswith('['): continue
    r = r + [''] * (len(h) - len(r))
    try: t += float(r[ix['FrameTime']]) / 1000
    except ValueError: continue
    if t < t0: continue
    for c in cols:
        try: vals[c].append(float(r[ix[c]]))
        except ValueError: pass
for c, v in vals.items():
    if not v: continue
    s = sorted(v)
    print(f"{c}: med {st.median(v):.2f} p95 {s[int(.95*len(s))]:.2f} p99 {s[int(.99*len(s))]:.2f} max {s[-1]:.1f} >{thr:g}: {sum(1 for x in v if x > thr)} / {len(v)}")
