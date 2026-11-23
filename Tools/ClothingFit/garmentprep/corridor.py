"""The arm corridor: space beside the torso that the arms pass through when they hang and swing.

A skinned garment cannot be pushed aside by an arm, so cloth that stands in that space gets
clipped by the arm in motion. The corridor is derived from the source body only: the arm is
modelled as tapered capsules along its bones (radii measured from the skin), and swept from
the A-pose down to hanging, with a fore/aft swing. Cloth found inside the swept space is
pulled toward the trunk until it is clear of it, or until it rests at skin clearance.
The lower armhole edge is also kept off the resting arm so that it follows the trunk.
"""
import numpy as np


def _rotation(a, b):
    """Smallest rotation matrix taking unit vector a to unit vector b."""
    v = np.cross(a, b)
    s, c = np.linalg.norm(v), float(a @ b)
    if s < 1e-9:
        return np.eye(3)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]]) / s
    return np.eye(3) + s * k + (1 - c) * (k @ k)


def _segment(p, a, b):
    ab = b - a
    t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
    return t, np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


class ArmCorridor:
    def __init__(self, skin, joints, hang_deg=(10., 18., 26.), swing_deg=(-25., -12., 0., 12., 25.), bins=6, hand=False):
        self.segments = []          # (a, b, radii at bin centres, bin centres)
        self.rest = []
        self.upper = []             # the resting upper arms only
        for side, sign in (("l", 1.), ("r", -1.)):
            sh, el, wr = (np.asarray(joints[f"{n}_{side}"], float) for n in ("upperarm", "lowerarm", "hand"))
            if np.sign(sh[0]) != sign:
                sign = float(np.sign(sh[0]))
            tip = wr + (wr - el) / np.linalg.norm(wr - el) * 19.
            chain = [(sh, el), (el, wr), (wr, tip)] if hand else [(sh, el), (el, wr)]
            near = skin[(np.abs(skin[:, 0] - sh[0]) < 80) & (sign * skin[:, 0] > sign * sh[0] - 12)]
            dist = np.stack([_segment(near, a, b)[1] for a, b in chain], 1)
            owner = dist.argmin(1)
            shapes = []
            trunk_side = np.array([-sign, 0., 0.])           # the trunk lies this way from the arm
            for k, (a, b) in enumerate(chain):
                ab = b - a
                t, d = _segment(near, a, b)
                offset = near - (a + t[:, None] * ab)
                # measure the radius on the outer half only, where no trunk skin can be mistaken for arm
                outer = (offset @ trunk_side) < -.25 * d
                mine = (owner == k) & (d < 11) & outer
                centres = (np.arange(bins) + .5) / bins
                radius = np.full(bins, np.nan)
                for i in range(bins):
                    sel = mine & (t >= i / bins) & (t < (i + 1) / bins)
                    if sel.sum() > 12:
                        radius[i] = np.percentile(d[sel], 80)
                if k == 0:                       # near the shoulder the skin belongs to the trunk
                    radius[centres < .3] = np.nan
                good = np.isfinite(radius)
                radius = np.interp(centres, centres[good], radius[good]) if good.any() else np.full(bins, 4.5)
                shapes.append((radius, centres))
            self.rest += [(a, b, r, c) for (a, b), (r, c) in zip(chain, shapes)]
            self.upper.append((chain[0][0], chain[0][1], shapes[0][0], shapes[0][1]))
            d0 = (el - sh) / np.linalg.norm(el - sh)
            for hang in hang_deg:
                for swing in swing_deg:
                    h, s = np.radians(hang), np.radians(swing)
                    aim = np.array([sign * np.sin(h), np.sin(s) * np.cos(h), -np.cos(s) * np.cos(h)])
                    R = _rotation(d0, aim / np.linalg.norm(aim))
                    for (a, b), (r, c) in zip(chain, shapes):
                        self.segments.append((sh + (a - sh) @ R.T, sh + (b - sh) @ R.T, r, c))

    @staticmethod
    def _signed(p, segments):
        out = np.full(len(p), np.inf)
        for a, b, radius, centres in segments:
            t, d = _segment(p, a, b)
            out = np.minimum(out, d - np.interp(t, centres, radius))
        return out

    def swept(self, p):
        """Signed distance (cm) to the space the arms sweep; negative inside."""
        return self._signed(p, self.segments)

    def at_rest(self, p):
        return self._signed(p, self.rest)


def _upper_arm_frame(corridor, p, trunk_bones):
    """For points near an upper arm: signed gap to the resting arm, unit direction away from its
    axis, and how much the point sits on the trunk-facing (underarm) side of the arm (0..1)."""
    from prep import nearest_on_bones
    gap = np.full(len(p), np.inf)
    away = np.zeros((len(p), 3))
    under = np.zeros(len(p))
    for a, b, radius, centres in corridor.upper:
        ab = b - a
        t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
        foot = a + t[:, None] * ab
        off = p - foot
        dist = np.linalg.norm(off, axis=1)
        g = dist - np.interp(t, centres, radius)
        radial = off / np.maximum(dist, 1e-9)[:, None]
        mid = .5 * (a + b)
        toward = nearest_on_bones(mid[None], trunk_bones)[0] - mid
        toward -= (toward @ ab) / (ab @ ab) * ab
        toward /= np.linalg.norm(toward)
        side = np.clip((radial @ toward) / .5, 0, 1)
        side = side * side * (3 - 2 * side)
        # only along the arm itself, fading out at the shoulder joint where the cloth wraps the shoulder
        along = np.clip((t - .12) / .15, 0, 1)
        take = g < gap
        gap[take], away[take], under[take] = g[take], radial[take], (side * along)[take]
    return gap, away, under


def corridor_plan(g, corridor, body, trunk_bones, clearance, margin=.3, strength=2., reach=6., step=.1, blur=6.,
                  armhole_room=2.2):
    """Fixed soft targets that keep the cloth out of the way of the arms, decided once on the starting shape.

    1. Armhole relief: cloth on the underarm side of the resting arm keeps `armhole_room` cm from
       it. It moves straight away from the arm, and along the trunk once it rests on the trunk,
       so the lower armhole edge ends up on the ribs below the armpit, nearer the trunk than the arm.
    2. Swept space: cloth beside the trunk leaves the space the hanging, swinging arm passes through.
    The travel is blurred over the mesh so there is no step between moved and untouched cloth.
    Returns (stiffness per vertex, target positions, info).
    """
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla
    from prep import nearest_on_bones
    p = g.P0.copy()
    floor = clearance + .05
    # ---- 1. armhole relief
    gap, away, under = _upper_arm_frame(corridor, p, trunk_bones)
    live = (gap < armhole_room * under) & (under > .05)
    relief = int(live.sum())
    for _ in range(int(9. / step)):
        idx = np.flatnonzero(live)
        if not len(idx):
            break
        gap_i, away_i, under_i = _upper_arm_frame(corridor, p[idx], trunk_bones)
        done = gap_i >= armhole_room * under_i
        here = p[idx]
        q = here + away_i * step
        blocked = body(q) < floor[idx]
        if blocked.any():                 # resting on the trunk: carry on along its surface
            n = body.gradient(here[blocked])
            tangent = away_i[blocked] - np.einsum("ij,ij->i", away_i[blocked], n)[:, None] * n
            length = np.linalg.norm(tangent, axis=1)
            slid = here[blocked] + tangent / np.maximum(length, 1e-9)[:, None] * step
            stuck = (body(slid) < floor[idx][blocked] - .1) | (length < .2)
            slid[stuck] = here[blocked][stuck]
            q[blocked] = slid
        p[idx[~done]] = q[~done]
        live[idx[done]] = False
    # ---- 2. swept arm space
    swept, rest = corridor.swept(p), corridor.at_rest(p)
    idx = np.flatnonzero((swept < margin) & (rest > swept + .5))
    inward = nearest_on_bones(p, trunk_bones) - p
    inward[:, 2] = 0
    inward /= np.maximum(np.linalg.norm(inward, axis=1), 1e-9)[:, None]
    if len(idx):
        moved = np.zeros(len(idx))
        live = np.ones(len(idx), bool)
        for _ in range(int(reach / step)):
            if not live.any():
                break
            sel = np.flatnonzero(live)
            q = p[idx[sel]] + inward[idx[sel]] * (moved[sel] + step)[:, None]
            stop = body(q) < floor[idx[sel]]
            clear = corridor.swept(q) >= margin
            moved[sel[~stop]] += step
            live[sel[stop | clear]] = False
        p[idx] += inward[idx] * moved[:, None]
    travel = p - g.P0
    if blur > 0 and np.abs(travel).max() > 0:
        solve = spla.factorized((sp.identity(g.n) + blur * g.L).tocsc())
        smooth = np.column_stack([solve(travel[:, a]) for a in range(3)])
        # keep the full travel where it was asked for; the blur only spreads it to the neighbours
        mix = np.clip(np.linalg.norm(travel, axis=1) / .6, 0, 1)[:, None]
        travel = mix * travel + (1 - mix) * smooth
    size = np.linalg.norm(travel, axis=1)
    k = strength * np.clip(size / .4, 0, 1)
    info = dict(armhole_relief_vertices=relief, swept_vertices=int(len(idx)),
                travel_cm_p50_p95_max=np.percentile(size[size > .05], [50, 95, 100]).round(2).tolist() if (size > .05).any() else [0, 0, 0])
    return k, g.P0 + travel, info
