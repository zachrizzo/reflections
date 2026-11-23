import sys, time, os
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
SCRATCH = Path(r"C:/Users/zachc/AppData/Local/Temp/claude/79559c54b34378d8/a4e4de80-1212-4b4c-a784-dd2da0cdd399/scratchpad")
sys.path.insert(0, str(HERE))
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spla
from scipy.sparse.csgraph import reverse_cuthill_mckee
import prep
d = np.load(SCRATCH / "v6/result.npz"); P, F = d["P0"], d["F"]
g = prep.Garment(P, F); n = g.n
rng = np.random.default_rng(0)
k = np.where(rng.random(n) < .15, 25., 0.) + .002
rhs = rng.normal(size=(n, 3))
for name, A in (("mesh+pairs", g.L + sp.diags(k)), ("mesh only", g.L_mesh + sp.diags(k))):
    A = A.tocsc()
    for spec in ("COLAMD", "MMD_AT_PLUS_A"):
        t = time.time(); lu = spla.splu(A, permc_spec=spec); tf = time.time() - t
        t = time.time(); x = lu.solve(rhs); ts = time.time() - t
        print(f"{name:11s} {spec:14s} factor {tf:6.2f} s  solve(3 rhs) {ts:5.3f} s  fill {(lu.L.nnz + lu.U.nnz) / 1e6:6.1f} M", flush=True)
    t = time.time(); perm = reverse_cuthill_mckee(A.tocsr(), symmetric_mode=True); Ap = A.tocsr()[perm][:, perm].tocsc(); lu = spla.splu(Ap, permc_spec="NATURAL", diag_pivot_thresh=0); tf = time.time() - t
    t = time.time(); x = lu.solve(rhs[perm]); ts = time.time() - t
    print(f"{name:11s} {'RCM+NATURAL':14s} factor {tf:6.2f} s  solve(3 rhs) {ts:5.3f} s  fill {(lu.L.nnz + lu.U.nnz) / 1e6:6.1f} M", flush=True)
    for drop in (1e-3, 1e-4):
        t = time.time(); ilu = spla.spilu(A, drop_tol=drop, fill_factor=20); tf = time.time() - t
        t = time.time(); x = ilu.solve(rhs); ts = time.time() - t
        print(f"{name:11s} spilu {drop:g}    factor {tf:6.2f} s  solve(3 rhs) {ts:5.3f} s  fill {(ilu.L.nnz + ilu.U.nnz) / 1e6:6.1f} M", flush=True)
