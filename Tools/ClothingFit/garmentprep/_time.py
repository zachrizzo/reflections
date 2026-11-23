import sys, time, pickle, os, json
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
SCRATCH = Path(r"C:/Users/zachc/AppData/Local/Temp/claude/79559c54b34378d8/a4e4de80-1212-4b4c-a784-dd2da0cdd399/scratchpad")
sys.path.insert(0, str(HERE))
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spla
import prep, refine
dump = np.load(SCRATCH / "refine/jerkin_dump.npz"); P, F, UV = dump["P"], dump["F"], dump["UV"]
t = time.time(); g0 = prep.Garment(P, F); print("coarse garment", g0.n, round(time.time() - t, 1), "thickness", g0.thickness, "partners", len(g0.PE))
limit = np.full(len(P), 2.5); limit[(P[:, 2] > 138)] = 1.0
t = time.time(); P1, F1, UV1, _, parent = refine.split_long_edges(P, F, UV, limit); print("refined", len(P1), len(F1), round(time.time() - t, 1), refine.mapping_check(P, F, UV, P1, F1, UV1, parent))
L = np.linalg.norm(P1[F1] - P1[F1[:, [1, 2, 0]]], axis=2); print("longest edge after", L.max())
t = time.time(); g = prep.Garment(P1, F1); print("fine garment", g.n, round(time.time() - t, 1))
free = np.flatnonzero(g.P0[:, 2] > 120); nf = len(free); print("free", nf)
hold = np.full(g.n, .01)
for name, A in (("membrane", g.L + sp.diags(hold)),):
    A = A.tocsr()[free][:, free]
    A3 = sp.kron(A, sp.identity(3), format="csr")
    rng = np.random.default_rng(0); n = rng.normal(size=(nf, 3)); n /= np.linalg.norm(n, axis=1)[:, None]
    k = np.where(rng.random(nf) < .1, 25., 0.)
    blocks = k[:, None, None] * np.einsum("ni,nj->nij", n, n) + (.02 * k)[:, None, None] * np.eye(3)
    D = sp.bsr_matrix((blocks, np.arange(nf), np.arange(nf + 1)), shape=(3 * nf, 3 * nf))
    M = (A3 + D).tocsc(); rhs = rng.normal(size=3 * nf)
    for spec in ("MMD_AT_PLUS_A",):
        t = time.time(); lu = spla.splu(M, permc_spec=spec); x = lu.solve(rhs); print(name, spec, "splu 3n", round(time.time() - t, 2), "s nnz", M.nnz, "fill", lu.L.nnz + lu.U.nnz)
    t = time.time(); lu1 = spla.splu((A + sp.diags(k)).tocsc(), permc_spec="MMD_AT_PLUS_A"); print(name, "scalar splu", round(time.time() - t, 2))
    # PCG with the scalar factor as preconditioner
    def pre(v):
        return np.column_stack([lu1.solve(v.reshape(-1, 3)[:, a]) for a in range(3)]).ravel()
    it = [0]
    def cb(_): it[0] += 1
    t = time.time(); y, info = spla.cg(M, rhs, M=spla.LinearOperator(M.shape, pre), rtol=1e-6, maxiter=400, callback=cb); print(name, "pcg", round(time.time() - t, 2), "s iters", it[0], "info", info, "err", np.abs(y - x).max())
