"""Automatic fit preparation for an image-generated garment.

Input: registered garment (source-body space), source body skin, layers underneath,
source body joints.
Output: the same vertices and triangles with new positions:
  1. buried panels are brought out on their own side (lifted onto the shoulder, or out
     toward the side they are attached on; never through the far wall),
  2. the displacement is relaxed over the mesh so stretch is spread out,
  3. clearance to skin and to the layer underneath is enforced.
Units are actor-local centimetres (x lateral, +y front, z up). Thresholds are derived
from the body field, the skeleton and the garment's own shell, not from one garment.
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.spatial import cKDTree

from field import SignedField
from meshops import (weld, edges_of, vertex_normals, shell_partners, graph_laplacian,
                     geodesic_from, smoothstep)
from refine import split_long_edges, mapping_check
from contact import crossing_triangles, self_crossing_pairs


class Garment:
    def __init__(self, P, F):
        self.full, self.faces_full = P, F
        self.P0, self.F, self.inv = weld(P, F)
        self.n = len(self.P0)
        self.E = edges_of(self.F)
        self.len0 = np.linalg.norm(self.P0[self.E[:, 0]] - self.P0[self.E[:, 1]], axis=1)
        self.N0 = vertex_normals(self.P0, self.F)
        a, b, c = self.P0[self.F].transpose(1, 0, 2)
        self.flip = np.einsum("ij,ij->", a - self.P0.mean(0), np.cross(b - self.P0.mean(0), c - self.P0.mean(0))) < 0
        if self.flip:
            self.N0 = -self.N0          # captures use the opposite winding; normals must leave the cloth
        self.partner = shell_partners(self.P0, self.N0)
        has = self.partner >= 0
        gaps = np.linalg.norm(self.P0[has] - self.P0[self.partner[has]], axis=1)
        self.thickness = float(np.median(gaps)) if has.any() else 0.
        pe = np.column_stack((np.flatnonzero(has), self.partner[has]))
        self.PE = np.unique(np.sort(pe, axis=1), axis=0) if len(pe) else np.zeros((0, 2), int)
        w = 1. / np.maximum(self.len0, .15) ** 2
        self.L_mesh = graph_laplacian(self.n, self.E, w / np.median(w))
        self.L_pair = graph_laplacian(self.n, self.PE, np.full(len(self.PE), 3.))
        self.L = (self.L_mesh + self.L_pair).tocsr()
        self.links = np.vstack((self.E, self.PE))
        self.link_len = np.r_[self.len0, np.full(len(self.PE), max(self.thickness, .1))]

    def expand(self, Pw):
        return Pw[self.inv]

    def normals(self, x):
        n = vertex_normals(x, self.F)
        return -n if self.flip else n


def add_layer(body, P, F, extra_clearance, reach=4., edge_spread=2.4):
    """Fold a layer worn underneath (e.g. trousers) into the obstacle field.

    The layer is an open surface, so its sign comes from the wearer: 'outside' is the
    side that faces away from the body. Free space beyond the layer's open edges is ignored.
    """
    spacing = .15
    a, b, c = P[F].transpose(1, 0, 2)
    fn = np.cross(b - a, c - a)
    area = .5 * np.linalg.norm(fn, axis=1)
    fn /= np.maximum(2 * area, 1e-12)[:, None]
    flip = np.einsum("ij,ij->i", fn, body.gradient(P[F].mean(1))) < 0
    fn[flip] *= -1
    k = np.clip(np.ceil(area / spacing ** 2).astype(int), 1, 4000)
    idx = np.repeat(np.arange(len(F)), k)
    r = np.random.default_rng(3).random((len(idx), 2))
    s = np.sqrt(r[:, 0])
    pts = a[idx] * (1 - s)[:, None] + b[idx] * (s * (1 - r[:, 1]))[:, None] + c[idx] * (s * r[:, 1])[:, None]
    nrm = fn[idx]
    tree = cKDTree(pts)
    axes = [body.origin[i] + np.arange(body.shape[i]) * body.cell for i in range(3)]
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
    d, j = tree.query(grid, distance_upper_bound=reach, workers=-1)
    ok = np.isfinite(d)
    gap = np.full(len(grid), np.inf)
    off = grid[ok] - pts[j[ok]]
    along = np.einsum("ij,ij->i", off, nrm[j[ok]])
    lateral = np.linalg.norm(off - along[:, None] * nrm[j[ok]], axis=1)
    gap[ok] = np.where(lateral < 3 * spacing + .25 * np.abs(along), np.sign(along) * d[ok], np.inf)
    gap = gap.reshape(body.shape)
    out = SignedField.__new__(SignedField)
    out.__dict__.update(body.__dict__)
    layered = np.minimum(body.grid, np.where(np.isfinite(gap), gap - extra_clearance, np.inf))
    # the layer ends at an open edge (a waistband); spread its extra thickness a little past that
    # edge so cloth pressed over it gets a slope there, not a ledge
    from scipy import ndimage
    extra = body.grid - layered
    # a thick or loose layer needs a longer slope than a thin tight one, or cloth bends sharply over its edge
    inside_box = np.all((P > body.origin + body.cell) & (P < body.origin + (np.array(body.shape) - 2) * body.cell), axis=1)
    if inside_box.any():
        edge_spread = float(np.clip(2 * np.median(body(P[inside_box])) - .1, edge_spread, 7.))
    spread = ndimage.gaussian_filter(ndimage.grey_dilation(extra, size=int(round(edge_spread / body.cell)) | 1), edge_spread / (2.5 * body.cell))
    out.grid = body.grid - np.maximum(extra, spread)
    out.layer_gap = gap
    return out


MAIN_BONES = ("pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05", "neck_01", "neck_02", "head",
              "clavicle_l", "upperarm_l", "lowerarm_l", "hand_l", "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r",
              "thigh_l", "calf_l", "foot_l", "thigh_r", "calf_r", "foot_r")


def bone_segments(joints, parents):
    """Segments (K,2,3) of the main skeleton chain; the head is extended to the crown."""
    seg = []
    for name in MAIN_BONES:
        parent = parents.get(name)
        while parent is not None and parent not in MAIN_BONES:
            parent = parents.get(parent)
        if name in joints and parent in joints:
            seg.append((joints[parent], joints[name]))
    if "head" in joints and "neck_02" in joints:
        head, neck = np.asarray(joints["head"], float), np.asarray(joints["neck_02"], float)
        seg.append((head, head + (head - neck) / np.linalg.norm(head - neck) * 14.))
    return np.asarray(seg, float)


def nearest_on_bones(p, seg):
    a, b = seg[:, 0], seg[:, 1]
    ab = b - a
    t = np.clip(np.einsum("nkj,kj->nk", p[:, None, :] - a[None], ab) / np.einsum("kj,kj->k", ab, ab)[None], 0, 1)
    q = a[None] + t[:, :, None] * ab[None]
    k = np.linalg.norm(p[:, None, :] - q, axis=2).argmin(1)
    return q[np.arange(len(p)), k]


def distance_to_segments(p, seg):
    """Distance from each point to the nearest of the segments, and that segment's index."""
    a, b = seg[:, 0], seg[:, 1]
    ab = b - a
    t = np.clip(np.einsum("nkj,kj->nk", p[:, None, :] - a[None], ab) / np.einsum("kj,kj->k", ab, ab)[None], 0, 1)
    d = np.linalg.norm(p[:, None, :] - (a[None] + t[:, :, None] * ab[None]), axis=2)
    k = d.argmin(1)
    return d[np.arange(len(p)), k], k


def nearest_wall(body, p, clearance, rounds=8):
    q = p.copy()
    for _ in range(rounds):
        miss = clearance - body(q)
        if not (miss > 1e-3).any():
            break
        q += body.gradient(q) * np.maximum(miss, 0)[:, None]
    return q


def pierced_triangles(g, spine):
    """Garment triangles that a spine, neck or head bone passes through, and the side the bone leaves by.

    Bones go through a garment's openings (neck hole, waist), never through its cloth. Cloth
    that is pierced is on the wrong side of the body there: the flat neck hole of a garment
    made from a front-view image, whose back neckline cuts straight through the neck.
    """
    from contact import _seg_tri
    T = g.P0[g.F]
    hit = np.zeros(len(g.F), bool)
    out = np.zeros(3)
    for a, b in spine:
        lo, hi = np.minimum(a, b) - .01, np.maximum(a, b) + .01
        near = np.flatnonzero(np.all((T.max(1) >= lo) & (T.min(1) <= hi), axis=1))
        if len(near):
            p = np.tile(a, (len(near), 1)); q = np.tile(b, (len(near), 1))
            found = near[_seg_tri(p, q, T[near, 0], T[near, 1], T[near, 2])]
            hit[found] = True
            n = np.cross(T[found, 1] - T[found, 0], T[found, 2] - T[found, 0])
            n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
            out += (n * np.sign(n @ (b - a))[:, None]).sum(0)      # the face the bone comes out of
    return np.flatnonzero(hit), out / max(np.linalg.norm(out), 1e-9)


def plan_exits(g, body, bones, clearance, deep, log=print, spine=None, reach=30.):
    """Decide once which way a pierced, buried patch leaves the body.

    Only a buried patch whose cloth a spine / neck / head bone passes through gets a plan. It
    belongs on the side the bone comes out of it. All its vertices go the same way, so the order
    of the cloth is kept: lifted if straight up is short, otherwise out horizontally toward that
    side. Everything else (a sleeve around an arm, a tight belly) simply leaves by the nearest wall.
    """
    from scipy.sparse.csgraph import connected_components, dijkstra
    phi = body(g.P0)
    is_deep = phi < -deep
    direction = np.zeros((g.n, 3))
    planned = np.zeros(g.n, bool)
    report = []
    if not is_deep.any():
        return planned, direction, report
    pierced, bone_side = pierced_triangles(g, bones if spine is None else spine)
    if not len(pierced):
        return planned, direction, report
    edges = g.links
    inside = phi < 0
    keep = inside[edges[:, 0]] & inside[edges[:, 1]]
    graph = sp.coo_matrix((np.ones(keep.sum()), (edges[keep, 0], edges[keep, 1])), shape=(g.n, g.n))
    _, comp = connected_components(graph, directed=False)
    adjacency = sp.coo_matrix((np.ones(len(edges) * 2), (np.r_[edges[:, 0], edges[:, 1]], np.r_[edges[:, 1], edges[:, 0]])),
                              shape=(g.n, g.n)).tocsr()
    seeds = np.unique(g.F[pierced])
    seeds = seeds[inside[seeds]]
    # a tight garment can be buried all the way round the body; only the cloth near the piercing is
    # on the wrong side, so the plan covers the buried patch within reach of it
    inner = sp.coo_matrix((np.r_[g.link_len[keep], g.link_len[keep]],
                           (np.r_[edges[keep, 0], edges[keep, 1]], np.r_[edges[keep, 1], edges[keep, 0]])), shape=(g.n, g.n)).tocsr()
    home = bone_side
    for label in np.unique(comp[seeds]):
        close = np.isfinite(dijkstra(inner, directed=False, indices=seeds[comp[seeds] == label], min_only=True, limit=reach))
        members = np.flatnonzero(inside & (comp == label) & close)
        if (is_deep[members]).sum() < 3:
            continue
        offset = g.P0[members] - nearest_on_bones(g.P0[members], bones)
        wrong = members[np.einsum("ij,j->i", offset, home) < 0]
        entry = dict(vertices=int(len(members)), deepest_cm=round(float(-phi[members].min()), 2), home=home.round(2).tolist(),
                     wrong_side=int(len(wrong)), pierced_triangles=int(len(pierced)))
        side = home * [1, 1, 0]
        flat = np.linalg.norm(side)
        p = g.P0[members]
        up = np.tile([0., 0., 1.], (len(members), 1))
        t_up = body.exit_distance(p, up, clearance[members])
        if flat > .25:
            side = np.tile(side / flat, (len(members), 1))
            t_side = body.exit_distance(p, side, clearance[members])
        else:
            side, t_side = up, np.full(len(members), np.inf)
        use_up = t_up <= t_side
        ok = np.isfinite(np.where(use_up, t_up, t_side))
        direction[members[ok]] = np.where(use_up[:, None], up, side)[ok]
        planned[members[ok]] = True
        entry.update(lifted=int((use_up & ok).sum()), sent_sideways=int((~use_up & ok).sum()))
        report.append(entry)
        log(f"  buried patch: {entry}")
    return planned, direction, report


class Relaxer:
    """Smooth-displacement solve with sliding contact against the obstacle field.

    Unknown: displacement of every free welded vertex (3 values). Energy: membrane +
    thin plate on the displacement (walls of the shell coupled), a hold toward the
    original place, and contact springs. A vertex in contact is only held along the
    surface normal, so it can slide along the skin and the stretch evens out.
    """

    def __init__(self, g, obstacle, cfg, hold, free, planned, exit_dir, log=print, ceiling_field=None):
        self.g, self.body, self.cfg, self.log = g, obstacle, cfg, log
        self.above = ceiling_field or obstacle
        self.free, self.planned, self.exit_dir = free, planned, exit_dir
        self.hold = hold
        self.active = np.zeros(g.n, bool)
        self.history = []
        self.u = np.zeros((len(free), 3))
        self.stiffen(1.)

    def stiffen(self, factor):
        """Set how stiffly the displacement is smoothed. A high factor moves the cloth as a sheet
        (large corrections keep seams, buttons and relief); 1 lets it settle locally."""
        g, cfg, free = self.g, self.cfg, self.free
        membrane = (factor * cfg["smooth"] * g.L + sp.diags(self.hold)).tocsr()[free][:, free].tocsr()
        self.A_pre = membrane                      # cheap to factor; used as the preconditioner
        self.A = membrane
        if cfg["plate"] > 0:
            Lf = g.L_mesh.tocsr()[free][:, free]
            self.A = (membrane + factor * cfg["plate"] * (Lf @ Lf)).tocsr()
        self._lu, self._lu_k = None, None

    def _solve(self, k_iso, k_n, normal, rhs):
        """Solve (A (x) I3 + contact blocks) u = rhs by conjugate gradients.

        The preconditioner is a scalar factorization with an isotropic stand-in for the
        contact springs; it is rebuilt only when the contact set has changed noticeably.
        """
        nf = len(self.free)
        k_pre = k_iso + .5 * k_n
        if self._lu is None or np.abs(k_pre - self._lu_k).sum() > .05 * max(self._lu_k.sum(), 1.):
            self._lu = spla.splu((self.A_pre + sp.diags(k_pre)).tocsc(), permc_spec="COLAMD")
            self._lu_k = k_pre.copy()
        A, lu = self.A, self._lu

        def matvec(v):
            V = v.reshape(nf, 3)
            out = A @ V + k_iso[:, None] * V + (k_n * np.einsum("ij,ij->i", normal, V))[:, None] * normal
            return out.ravel()

        def precond(v):
            return lu.solve(v.reshape(nf, 3)).ravel()
        op = spla.LinearOperator((3 * nf, 3 * nf), matvec=matvec)
        pre = spla.LinearOperator((3 * nf, 3 * nf), matvec=precond)
        count = [0]

        def tick(_):
            count[0] += 1
        sol, info = spla.cg(op, rhs.ravel(), x0=self.u.ravel(), M=pre, rtol=self.cfg["cg_tol"], maxiter=self.cfg["cg_iters"], callback=tick)
        self.cg_iterations = count[0]
        self.u = sol.reshape(nf, 3)
        return self.u

    def run(self, x, c, rounds, attract=None, tol=.004, ceiling=None):
        import time
        g, body, cfg, free = self.g, self.body, self.cfg, self.free
        for it in range(rounds):
            t0 = time.time()
            phi = body(x)
            bad = phi < c
            self.active = (self.active | bad) & (phi < c + cfg["release"])
            if ceiling is not None:
                # (only where there is a ceiling; everywhere else contact stays sticky, or pressed cloth ripples)
                self.active &= ~(np.isfinite(ceiling) & ~bad & (self.above(x) < ceiling - cfg["release"]) & (phi > c + .02))
            target = x.copy()
            along = bad & self.planned & (phi < -.3)
            if along.any():
                idx = np.flatnonzero(along)
                t = body.exit_distance(x[idx], self.exit_dir[idx], c[idx])
                found = np.isfinite(t)
                target[idx[found]] = x[idx[found]] + self.exit_dir[idx[found]] * t[found, None]
                along[idx[~found]] = False
            near = bad & ~along
            if near.any():
                target[near] = nearest_wall(body, x[near], c[near])
            if ceiling is not None:
                # cloth that has to lie close to the body is also held from above
                high = (self.above(x) > ceiling) & ~bad
                if high.any():
                    q = x[high].copy()
                    for _ in range(6):
                        q -= self.above.gradient(q) * np.maximum(self.above(q) - ceiling[high], 0)[:, None]
                    target[high] = q
                    self.active |= high
            normal = body.gradient(target[free])
            k_iso = np.where(along, cfg["contact"], np.where(self.active, cfg["contact"] * cfg["friction"], 0.))[free]
            k_n = np.where(self.active & ~along, cfg["contact"], 0.)[free]
            goal = (target - g.P0)[free]
            rhs = k_iso[:, None] * goal + (k_n * np.einsum("ij,ij->i", normal, goal))[:, None] * normal
            t1 = time.time()
            if attract is not None:
                ka, ta = attract(g, x)
                k_iso = k_iso + ka[free]
                rhs = rhs + ka[free, None] * (ta - g.P0)[free]
            t2 = time.time()
            u = np.zeros((g.n, 3))
            u[free] = self._solve(k_iso, k_n, normal, rhs)
            self.timing = (round(t1 - t0, 2), round(t2 - t1, 2), round(time.time() - t2, 2))
            x_new = g.P0 + u
            move = float(np.linalg.norm(x_new - x, axis=1).max())
            x = x_new
            self.history.append((int(bad.sum()), int((phi < -cfg["deep"]).sum()), move))
            if it % cfg.get('log_every', 5) == 0 or it == rounds - 1:
                self.log(f"  round {it:3d}: below clearance {int(bad.sum()):5d}, deep {self.history[-1][1]:4d}, largest move {move:.3f} cm, cg {self.cg_iterations}, s {self.timing}")
            if move < tol and it > 6:
                break
        return x

    def settle(self, x, c):
        """Put every vertex that is still under its clearance exactly on the clearance surface."""
        for _ in range(4):
            bad = self.body(x) < c
            if not bad.any():
                break
            x[bad] = nearest_wall(self.body, x[bad], c[bad] + .02)
        return x


DEFAULTS = dict(
    skin_clearance=.6,      # cm, target distance from skin
    deep=1.0,               # cm inside the skin beyond which a patch gets an exit plan
    smooth=1.0,             # membrane weight (spreads displacement)
    plate=.05,              # thin-plate weight (keeps the blend free of creases)
    hold_near=.0005,        # how strongly vertices near a problem are held to their original place
    hold_far=.03,           # ... and far from any problem
    hold_from=4., hold_to=14.,  # cm of surface distance over which the hold ramps up (around a moved patch)
    local_from=1., local_to=5., # ... and around small clearance fixes
    contact=25.,            # stiffness of the clearance constraint during relaxation
    friction=.02,           # share of that stiffness that also resists sliding
    release=.2,             # cm above clearance at which a resting vertex is let go
    stages=((40., 14), (8., 12)),   # (stiffness factor, rounds) of the sheet-like passes before settling
    rounds=24,
    wall_gap=1.0, wall_rounds=26,  # outer wall rests this share of the shell thickness further out
    relief_keep=.2, relief_blur=6.,    # cm of surface relief kept when cloth is pressed onto the body
    flat_lift=3., flat_ease=5.,    # a once-buried patch may stand off by flat_lift cm at its border, 0 beyond flat_ease cm inside
    cg_tol=1e-4, cg_iters=120,
    edge_everywhere=3.0,    # cm, no triangle edge may stay longer than this anywhere
    edge_moved=1.5,         # cm, ... and near a patch that has to move a long way
    edge_reach=6.,          # cm of surface distance around such a patch that gets the finer limit
    exact_passes=10, exact_step=.3, exact_rounds=12,
    armhole_room=2.0,       # cm kept between the resting upper arm (trunk-facing side) and the cloth
    side_ease=.3,           # cm of extra looseness allowed where the hanging, swinging arm passes (None = leave the sides)
    side_ramp=2.5, side_free=6.,   # looseness grows to side_free cm over side_ramp cm outside that space
    limb_ease=1.5,                 # a sleeve or trouser leg stands at most this far (cm) above its clearance (None = off)
    limb_free=6., limb_from=.15, limb_to=.5,   # ... easing in from limb_free at the shoulder / hip, along the upper bone
    limb_radius=12.,               # skin further than this from the limb's bone is not that limb's skin
)


def with_arm_room(field, arms, trunk_bones, room):
    """Obstacle field in which the resting upper arms are padded by `room` cm on their trunk-facing side.

    Cloth resting against this padding ends up nearer the trunk than the arm, so the lower armhole
    edge sits on the ribs below the armpit and takes its motion from the trunk.
    """
    from corridor import _upper_arm_frame
    axes = [field.origin[i] + np.arange(field.shape[i]) * field.cell for i in range(3)]
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
    padded = np.full(len(grid), np.inf)
    for lo in range(0, len(grid), 400000):
        gap, _, under = _upper_arm_frame(arms, grid[lo:lo + 400000], trunk_bones)
        padded[lo:lo + 400000] = np.where(under > .02, gap - room * under, np.inf)
    out = SignedField.__new__(SignedField)
    out.__dict__.update(field.__dict__)
    out.grid = np.minimum(field.grid, padded.reshape(field.shape))
    return out


def prepare(P, F, UV, skin_field, bones, skin, layers=(), params=None, log=print, arms=None, trunk_bones=None, spine=None, limbs=None, pierce=True):
    """Prepare a registered garment. Returns a dict with the refined mesh and its new positions.

    P, F, UV: welded positions (cm), triangles, per-corner UVs. skin_field: SignedField of the skin
    plus layers worn underneath. bones: skeleton segments. skin / layers: (points, triangles) for
    the exact final checks. arms: ArmCorridor of the source body (None = no arm handling).
    """
    cfg = dict(DEFAULTS, **(params or {}))
    report = {}
    obstacle = skin_field
    if arms is not None and cfg["armhole_room"] > 0:
        obstacle = with_arm_room(skin_field, arms, trunk_bones, cfg["armhole_room"])
    # ---- plan on the mesh as it is, then split long edges where the cloth will have to bend
    coarse = Garment(P, F)
    c = np.full(coarse.n, cfg["skin_clearance"])
    planned, _, _ = plan_exits(coarse, skin_field, bones, c, cfg["deep"], lambda *_: None, spine=spine if pierce else np.zeros((0, 2, 3)))
    limit = np.full(len(P), cfg["edge_everywhere"])
    if planned.any():
        near = geodesic_from(coarse.n, coarse.links, coarse.link_len, np.flatnonzero(planned), limit=cfg["edge_reach"])
        limit[np.isfinite(near)[coarse.inv]] = cfg["edge_moved"]
    P1, F1, UV1, _, parent = split_long_edges(P, F, UV, limit)
    report["refinement"] = mapping_check(P, F, UV, P1, F1, UV1, parent)
    log(f"refinement: {report['refinement']}")
    g = Garment(P1, F1)
    c = np.full(g.n, cfg["skin_clearance"])
    phi0 = obstacle(g.P0)
    problem = phi0 < c
    log(f"welded vertices {g.n}, shell thickness {g.thickness:.2f} cm, below clearance {int(problem.sum())}, "
        f"deep {int((phi0 < -cfg['deep']).sum())}, deepest {-phi0.min():.2f} cm")
    planned, exit_dir, patches = plan_exits(g, skin_field, bones, c, cfg["deep"], log, spine=spine if pierce else np.zeros((0, 2, 3)))
    report["patches"] = patches
    # ---- how loose the cloth may be: beside the trunk, where the arms hang and swing, it has to lie close
    loose = np.full(g.n, np.inf)
    if arms is not None and cfg["side_ease"] is not None:
        swept, rest = arms.swept(g.P0), arms.at_rest(g.P0)
        trunk_side = rest > skin_field(g.P0) + .5             # nearest skin is the trunk, not the arm
        loose = np.where(trunk_side, cfg["side_ease"] + cfg["side_free"] * smoothstep(swept, 0., cfg["side_ramp"]), np.inf)
        loose[swept > cfg["side_ramp"]] = np.inf
        report["side"] = dict(vertices_in_arm_space=int((swept < 0).sum()), vertices_limited=int(np.isfinite(loose).sum()))
        log(f"side fit: {report['side']}")
    # ---- sleeves and trouser legs hug the limb: cloth that wraps a limb may stand no further off the skin
    #      than limb_ease, easing in from the shoulder or hip so the join to the trunk part stays soft
    if limbs and spine is not None and cfg["limb_ease"] is not None:
        # judged at the skin point under each vertex: that skin has to be the limb's own (near its bone,
        # nearer to it than to the spine), so trunk cloth that merely hangs beside an arm is left alone
        under = g.P0 - skin_field(g.P0)[:, None] * skin_field.gradient(g.P0)
        d_trunk, _ = distance_to_segments(under, np.asarray(spine))
        hugged = 0
        for chain in limbs:
            chain = np.asarray(chain, float)
            d_limb, _ = distance_to_segments(under, chain)
            own = d_limb < np.minimum(d_trunk, cfg["limb_radius"])
            first = chain[0, 1] - chain[0, 0]
            along = np.clip(((g.P0 - chain[0, 0]) @ first) / (first @ first), 0, 1)
            ease = cfg["limb_free"] + (cfg["limb_ease"] - cfg["limb_free"]) * smoothstep(along, cfg["limb_from"], cfg["limb_to"])
            on = own
            loose[on] = np.minimum(loose[on], ease[on])
            hugged += int((on & (skin_field(g.P0) > c + ease)).sum())
        report["limbs"] = dict(wrapped=len(limbs), vertices_pulled_in=hugged)
        log(f"limb fit: {report['limbs']}")
    too_loose = skin_field(g.P0) > c + loose
    # ---- big moves spread over a wide area; small clearance fixes stay local
    far, near = cfg["hold_to"] + 4, cfg["local_to"] + 2

    def reach_of(seed, limit_cm):
        if not seed.any():
            return np.full(g.n, np.inf)
        return geodesic_from(g.n, g.links, g.link_len, np.flatnonzero(seed), limit=limit_cm)
    d_big = reach_of(planned, far)
    d_small = reach_of((problem & ~planned) | too_loose, near)
    relief = np.maximum(1 - smoothstep(d_big, cfg["hold_from"], cfg["hold_to"]),
                        1 - smoothstep(d_small, cfg["local_from"], cfg["local_to"]))
    hold = cfg["hold_far"] + (cfg["hold_near"] - cfg["hold_far"]) * relief
    free = np.flatnonzero((d_big < far) | (d_small < near))
    log(f"free vertices {len(free)}")
    relax = Relaxer(g, obstacle, cfg, hold, free, planned, exit_dir, log, ceiling_field=skin_field)

    def ceiling_now(extra=None):
        top = c + loose
        if extra is not None:
            top = np.minimum(top, extra)
        return top if np.isfinite(top).any() else None
    x = g.P0.copy()
    # ---- large corrections first, with the cloth moving as a stiff sheet; then let it settle
    for factor, rounds in cfg["stages"]:
        relax.stiffen(factor)
        x = relax.run(x, c, rounds, ceiling=ceiling_now())
    relax.stiffen(1.)
    x = relax.run(x, c, cfg["rounds"], ceiling=ceiling_now())
    x = relax.settle(x, c)
    flat = None
    if g.thickness > 0:
        # ---- stack the two walls of the shell: the outer wall rests further out than the inner one,
        #      so cloth pressed onto the body stays two clean layers instead of interleaving
        facing = np.einsum("ij,ij->i", g.normals(x), skin_field.gradient(x))
        wall = .5 + .5 * np.clip(facing / .6, -1, 1)
        ring = sp.coo_matrix((np.ones(len(g.E) * 2), (np.r_[g.E[:, 0], g.E[:, 1]], np.r_[g.E[:, 1], g.E[:, 0]])), shape=(g.n, g.n)).tocsr()
        degree = np.maximum(np.asarray(ring.sum(1)).ravel(), 1)
        for _ in range(4):
            wall = .5 * wall + .5 * (ring @ wall) / degree
        c = c + wall * cfg["wall_gap"] * g.thickness
        # pressed cloth keeps its surface relief: the smoothed surface rests at clearance and each
        # vertex stays as far above or below it as it was (within relief_keep)
        if cfg["relief_keep"] > 0:
            base = spla.factorized((sp.identity(g.n) + cfg["relief_blur"] * g.L_mesh).tocsc())
            smooth_p0 = np.column_stack([base(g.P0[:, a]) for a in range(3)])
            height = np.einsum("ij,ij->i", g.P0 - smooth_p0, g.N0) * (2 * wall - 1)
            c = c + cfg["relief_keep"] + np.clip(height, -cfg["relief_keep"], cfg["relief_keep"])
        # a patch that was buried in the body was never seen and is usually crumpled: lay it flat on
        # the body in its two layers, easing off toward the cloth around it
        if planned.any():
            inside_patch = geodesic_from(g.n, g.links, g.link_len, np.flatnonzero(~planned), limit=cfg["flat_ease"] + 1)
            inside_patch = np.where(np.isfinite(inside_patch), inside_patch, cfg["flat_ease"] + 1)
            flat = np.where(planned, c + .05 + cfg["flat_lift"] * (1 - smoothstep(inside_patch, 0, cfg["flat_ease"])), np.inf)
        x = relax.run(x, c, cfg["wall_rounds"], ceiling=ceiling_now(flat))
        x = relax.settle(x, c)
    # ---- exact check: where a triangle still crosses, its corners need more room
    surfaces = [skin] + list(layers)
    hit = np.zeros(len(F1), bool)
    for attempt in range(cfg["exact_passes"]):
        full = g.expand(x)
        hit = np.zeros(len(F1), bool)
        for Ps, Fs in surfaces:
            tris, _ = crossing_triangles(Ps, Fs, full, F1)
            hit[tris] = True
        log(f"  exact check {attempt}: {int(hit.sum())} triangles cross")
        if not hit.any():
            break
        verts = np.unique(g.inv[F1[hit]])
        if len(g.PE):
            # both walls of the cloth get the extra room, or the inner wall is pushed through the outer one
            marked = np.zeros(g.n, bool)
            marked[verts] = True
            pair = g.PE[marked[g.PE[:, 0]] | marked[g.PE[:, 1]]]
            verts = np.unique(np.r_[verts, pair.ravel()])
        step = cfg["exact_step"]
        c[verts] = c[verts] + step
        if flat is not None:
            # a once-buried patch is held flat on the body; where it still crosses, that hold has to give way too
            flat[verts] = np.where(np.isfinite(flat[verts]), flat[verts] + step, flat[verts])
        x = relax.run(x, c, cfg["exact_rounds"], ceiling=ceiling_now(flat))
        x = relax.settle(x, c)
    report["crossing_triangles"] = int(hit.sum())
    report["history"] = relax.history
    return dict(P0=P1, F=F1, UV=UV1, P=g.expand(x), parent=parent, garment=g, x=x, clearance=c, hold=hold,
                planned=planned, free=free, report=report)
