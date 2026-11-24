"""Place a generated garment on the source body: one affine transform found by search, then limb alignment.

The generated mesh comes in the generator's own cube, upright and facing front. Registration finds
scale (kept nearly uniform so the garment keeps its designed proportions), position and a slight
forward/back lean such that the body is inside the garment: little cloth inside the skin, little
cloth far from it. Shoulders (tops) or waist and crotch (bottoms) settle the height on their own,
because cloth that sits too low is pierced by them and cloth that sits too high stands off.
Sleeves and trouser legs are then turned about the shoulder or hip joint onto the limb they wrap.
Units are actor-local centimetres (x lateral, +y front, z up). No per-garment numbers.
"""
import numpy as np
from scipy.optimize import minimize


def central_width(P, z_lo, z_hi, cell=.6):
    """Width of the piece of cloth that contains x = 0 in a height band (ignores separate sleeves or legs)."""
    band = P[(P[:, 2] >= z_lo) & (P[:, 2] < z_hi)]
    if len(band) < 20:
        return None
    filled = np.zeros(int(np.ceil((band[:, 0].max() - band[:, 0].min()) / cell)) + 3, bool)
    x0 = band[:, 0].min() - cell
    filled[((band[:, 0] - x0) / cell).astype(int)] = True
    centre = int((0 - x0) / cell)
    if not (0 <= centre < len(filled)):
        return None
    if not filled[centre]:                                   # two legs: take the gap as the centre
        near = np.flatnonzero(filled)
        centre = near[np.abs(near - centre).argmin()]
    lo = hi = centre
    gap = 0
    while lo > 0 and gap <= 2:
        lo -= 1
        gap = 0 if filled[lo] else gap + 1
    lo += gap
    gap = 0
    while hi < len(filled) - 1 and gap <= 2:
        hi += 1
        gap = 0 if filled[hi] else gap + 1
    hi -= gap
    return (hi - lo + 1) * cell


def trunk_skin(skin, joints):
    """Skin that is not the free arms."""
    keep = np.ones(len(skin), bool)
    for side in ("l", "r"):
        sh, el, wr = (np.asarray(joints[f"{n}_{side}"], float) for n in ("upperarm", "lowerarm", "hand"))
        for a, b in ((sh, el), (el, wr), (wr, wr + (wr - el) * .8)):
            ab = b - a
            t = np.clip(((skin - a) @ ab) / (ab @ ab), 0, 1)
            d = np.linalg.norm(skin - (a + t[:, None] * ab), axis=1)
            along = ((skin - sh) @ (el - sh)) / ((el - sh) @ (el - sh))
            keep &= ~((d < 8.) & (along > .3))
    return skin[keep]


def apply(P, params, pivot_z):
    s, w, d, ys, zs, lean = params
    Q = P * np.array([s * w, s * d, s])
    Q[:, 1] += ys
    Q[:, 2] += zs
    Q[:, 1] += lean * (Q[:, 2] - pivot_z)
    return Q


def register(P, body, skin, joints, kind, ease=1.8, log=print):
    """Returns (registered positions, report). P is centred and scaled here; any input scale works."""
    P = np.asarray(P, float)
    lo, hi = P.min(0), P.max(0)
    centre = (lo + hi) / 2
    centre[2] = hi[2]                                          # work from the top of the garment
    G = P - centre
    height = hi[2] - lo[2]
    trunk = trunk_skin(skin, joints)
    pelvis, shoulder = np.asarray(joints["pelvis"], float), np.asarray(joints["upperarm_l"], float)
    neck = np.asarray(joints["neck_01"], float)
    if kind == "top":
        top_z = neck[2] + .5
        body_w = central_width(trunk, shoulder[2] - 22, shoulder[2] - 14)
        cloth_w = central_width(G, -.42 * height, -.30 * height) or (hi[0] - lo[0])
    elif kind == "cloak":
        top_z = neck[2] + 1.5
        # Scale a cloak to the wearer's shoulder yoke (trunk + deltoids), never the outstretched A-pose arms
        body_w = central_width(trunk, shoulder[2] - 6, shoulder[2] + 4) or (abs(float(joints["upperarm_l"][0] - joints["upperarm_r"][0])) + 16.0)
        cloth_w = central_width(G, -.16 * height, -.08 * height) or (hi[0] - lo[0])
        ease = max(ease, 1.8)
    else:
        top_z = pelvis[2] + 9.
        body_w = central_width(trunk, pelvis[2] - 6, pelvis[2] + 2)
        cloth_w = central_width(G, -.30 * height, -.16 * height) or (hi[0] - lo[0])
    s0 = (body_w + 2 * ease + 1.5) / cloth_w
    mid_y = float(np.median(trunk[(trunk[:, 2] > top_z - 30) & (trunk[:, 2] < top_z - 8)][:, 1].min() * .5 +
                            trunk[(trunk[:, 2] > top_z - 30) & (trunk[:, 2] < top_z - 8)][:, 1].max() * .5))
    sample = G[np.random.default_rng(5).choice(len(G), min(len(G), 6000), replace=False)]
    # stay inside the field's box
    box_lo, box_hi = body.origin + 1, body.origin + (body.shape - 2) * body.cell

    forgive = .97 if kind in ("top", "cloak") else .995       # a bottom has no neck hole: a waistband through the belly must count
    upper_cloak = (sample[:, 2] >= -.30 * height) if kind == "cloak" else None

    def cost(x):
        s, w, d, ys, zs, lean = x
        Q = apply(sample, (s, w, d, mid_y + ys, top_z + zs, lean), top_z + zs - .5 * height * s)
        outside_box = np.clip(box_lo - Q, 0, None).sum(1) + np.clip(Q - box_hi, 0, None).sum(1)
        phi = body(np.clip(Q, box_lo, box_hi))
        inside = np.sort(np.clip((1.0 if kind == "cloak" else .4) - phi, 0, None))[: int(forgive * len(phi))]
        phi_loose = phi[upper_cloak] if (upper_cloak is not None and upper_cloak.sum() > 50) else phi
        loose = np.sort(np.clip(phi_loose - (ease + 1.), 0, 10))[: int(.9 * len(phi_loose))]     # forgive flared edges and caps
        return (8. * (inside ** 2).mean() + 1.2 * (loose ** 2).mean() + 30. * (w - 1) ** 2 + 4. * (d - 1) ** 2
                + 3. * (s / s0 - 1) ** 2 + .02 * ys ** 2 + .01 * zs ** 2 + 6. * lean ** 2 + .5 * outside_box.mean())

    best = None
    for scale in (.9, 1., 1.1):
        for zs in (-4., 0., 4.):
            start = np.array([s0 * scale, 1., 1.1, 0., zs, 0.])
            res = minimize(cost, start, method="Nelder-Mead", options=dict(xatol=2e-3, fatol=1e-4, maxiter=900))
            if best is None or res.fun < best.fun:
                best = res
    s, w, d, ys, zs, lean = best.x
    params = (s, w, d, mid_y + ys, top_z + zs, lean)
    Q = apply(G, params, top_z + zs - .5 * height * s)
    phi = body(np.clip(Q, box_lo, box_hi))
    report = dict(kind=kind, scale=round(float(s), 4), width_factor=round(float(w), 3), depth_factor=round(float(d), 3),
                  y_shift_cm=round(float(ys), 2), z_shift_cm=round(float(zs), 2), lean=round(float(lean), 3), cost=round(float(best.fun), 4),
                  inside_skin_pct=round(float((phi < 0).mean() * 100), 2), clearance_cm_p50=round(float(np.median(phi)), 2),
                  top_z_cm=round(float(Q[:, 2].max()), 1), bottom_z_cm=round(float(Q[:, 2].min()), 1), width_cm=round(float(np.ptp(Q[:, 0])), 1))
    log(f"registration: {report}")
    if kind == "cloak":
        Q, drape_info = drape_cloak(Q, skin, joints, log=log)
        limbs = {"cloak_drape": drape_info}
    else:
        Q, limbs = align_limbs(Q, joints, kind, log, skin=skin)
    if kind == "bottom":
        # after the legs are on the leg bones: before that the inner leg surfaces can touch the centre line
        Q, report["crotch"] = align_crotch(Q, skin, joints, log=log)
    report["limbs"] = limbs
    return Q, report


def align_crotch(Q, skin, joints, below=1.5, log=print):
    """Bottoms: put the crotch seam just under the body's crotch. A generated garment can have a shorter rise
    (waistband to crotch) than the body; then, with the waistband at the waist, its crotch sits inside the pelvis
    and the fit has to drag that cloth 10 cm or more. The waistband stays where registration put it, the part
    between it and the crotch is stretched upright and the legs move down with the crotch (the sleeve and leg
    rule of the fit step ends them at the ankle again). A crotch that is already low enough is left alone."""
    pelvis = np.asarray(joints["pelvis"], float)
    mid = float(np.median(skin[np.abs(skin[:, 2] - pelvis[2]) < 3, 0]))
    upper = Q[:, 2] > pelvis[2] - 40
    centre = upper & (np.abs(Q[:, 0] - mid) < 1.5)
    body_centre = (np.abs(skin[:, 0] - mid) < 1.5) & (skin[:, 2] < pelvis[2]) & (skin[:, 2] > pelvis[2] - 40)
    if centre.sum() < 20 or body_centre.sum() < 20:
        return Q, None
    crotch_cloth = float(Q[centre, 2].min())
    crotch_body = float(skin[body_centre, 2].min())
    target = crotch_body - below
    top = float(Q[:, 2].max())
    report = dict(cloth_crotch_z=round(crotch_cloth, 1), body_crotch_z=round(crotch_body, 1))
    if crotch_cloth <= target + .3 or top - crotch_cloth < 5:
        return Q, dict(report, lowered_cm=0.)
    Q = Q.copy()
    z = Q[:, 2]
    rise = z >= crotch_cloth
    z[rise] = top - (top - z[rise]) * (top - target) / (top - crotch_cloth)
    z[~rise] -= crotch_cloth - target
    log(f"crotch: the garment crotch sat {crotch_cloth - crotch_body:.1f} cm above the body's; rise stretched x{(top - target) / (top - crotch_cloth):.2f}, legs lowered {crotch_cloth - target:.1f} cm")
    return Q, dict(report, lowered_cm=round(crotch_cloth - target, 1), rise_stretch=round((top - target) / (top - crotch_cloth), 3))


def _smoothstep(x, lo, hi):
    t = np.clip((np.asarray(x, float) - lo) / (hi - lo), 0., 1.)
    return t * t * (3. - 2. * t)


def _rodrigues(rel, direction, target, blend):
    v = np.cross(direction, target)
    sin, cos = float(np.linalg.norm(v)), float(direction @ target)
    angle = float(np.degrees(np.arctan2(sin, cos)))
    if sin < 1e-6 or angle < 0.5:
        return rel, 0.0
    k = v / sin
    K = np.array([[0., -k[2], k[1]], [k[2], 0., -k[0]], [-k[1], k[0], 0.]])
    theta = np.radians(angle) * blend
    c, s_ = np.cos(theta)[:, None], np.sin(theta)[:, None]
    rot = rel * c + (rel @ K.T) * s_ + (rel @ k)[:, None] * k * (1. - c)
    return rot, angle


def _ray_distance(Q, origin, axis):
    rel = Q - origin
    along = rel @ axis
    t = np.maximum(along, 0.0)
    return np.linalg.norm(rel - t[:, None] * axis, axis=1), along


def _segments_distance(Q, segs):
    a, b = segs[:, 0], segs[:, 1]
    ab = b - a
    t = np.clip(np.einsum("nkj,kj->nk", Q[:, None, :] - a[None], ab) / np.einsum("kj,kj->k", ab, ab)[None], 0., 1.)
    return np.linalg.norm(Q[:, None, :] - (a[None] + t[:, :, None] * ab[None]), axis=2).min(1)


def _angular_coverage(pts_rel, axis, lo, hi, max_r):
    if len(pts_rel) < 60:
        return 0
    along = pts_rel @ axis
    off = pts_rel - along[:, None] * axis
    rad = np.linalg.norm(off, axis=1)
    ring = (along > lo) & (along < hi) & (rad < max_r)
    if ring.sum() < 60:
        return 0
    ref = np.array([0., 1., 0.]) if abs(axis[1]) < 0.9 else np.array([1., 0., 0.])
    u = np.cross(axis, ref); u /= np.linalg.norm(u)
    v = np.cross(u, axis)
    ang = np.degrees(np.arctan2(off[ring] @ v, off[ring] @ u))
    return len(np.unique(((ang + 180.) // 30.).astype(int)))


def _centroid_axis(Q, origin, init_dir, al_lo, al_hi, max_r, d_other):
    """Iterative centroid ray from `origin` through a distal cross-section of a sleeve/leg tube."""
    axis = init_dir / np.linalg.norm(init_dir)
    rel = Q - origin
    for _ in range(3):
        d, al = _ray_distance(Q, origin, axis)
        ring = (al >= al_lo) & (al <= al_hi) & (d < max_r) & (d < d_other)
        if ring.sum() < 50:
            break
        ctr = rel[ring].mean(0)
        n = float(np.linalg.norm(ctr))
        if n < 1e-6:
            break
        axis = ctr / n
    return axis


def _arm_skin_masks(skin, joints):
    """Split body skin into trunk skin and each free arm's skin (same cylinder rule as trunk_skin)."""
    trunk_mask = np.ones(len(skin), bool)
    arm_masks = {}
    for side in ("l", "r"):
        sh, el, wr = (np.asarray(joints[f"{n}_{side}"], float) for n in ("upperarm", "lowerarm", "hand"))
        is_arm = np.zeros(len(skin), bool)
        along_up = ((skin - sh) @ (el - sh)) / ((el - sh) @ (el - sh))
        for a, b in ((sh, el), (el, wr), (wr, wr + (wr - el) * .8)):
            ab = b - a
            t = np.clip(((skin - a) @ ab) / (ab @ ab), 0., 1.)
            d = np.linalg.norm(skin - (a + t[:, None] * ab), axis=1)
            is_arm |= (d < 8.) & (along_up > .3)
        arm_masks[side] = is_arm
        trunk_mask &= ~is_arm
    return trunk_mask, arm_masks


def drape_cloak(Q, skin, joints, log=print):
    """Drape the hanging curtain of a cloak smoothly behind the A-pose arms and back below the shoulder yoke.

    A studio front-view cloak hangs straight down over where A-pose arms extend sideways, which would skewer
    the side curtains on the upper arms/elbows and push the back wall into the glutes. Keeping the collar and
    shoulder yoke fixed on the neck/shoulders, this applies a smooth C1 backward drape below shoulder height so
    the arms sit completely free in front and the back curtain clears the back and glutes cleanly.
    """
    Q = Q.copy()
    tmask, amasks = _arm_skin_masks(skin, joints)
    trunk = skin[tmask]
    sh_z = 0.5 * (float(joints["upperarm_l"][2]) + float(joints["upperarm_r"][2]))
    pel_z = float(joints["pelvis"][2])

    # Back-most surface of trunk (shoulder blades / glutes) and back-most surface of arms below shoulders
    back_band = trunk[(trunk[:, 2] <= sh_z) & (trunk[:, 2] >= pel_z - 12.0)]
    trunk_back_y = float(np.percentile(back_band[:, 1], 1)) if len(back_band) else -12.0
    arm_pts = np.vstack([skin[m] for m in amasks.values() if m.any()])
    arm_upper = arm_pts[(arm_pts[:, 2] <= sh_z - 2.0) & (arm_pts[:, 2] >= pel_z)]
    arm_back_y = float(np.percentile(arm_upper[:, 1], 3)) if len(arm_upper) else -8.0

    # Strictly monotonic affine Y-map below the shoulder yoke: preserves front-to-back ordering everywhere
    # (dy_new/dy >= 0.45 > 0, so inner/outer cloak walls never collapse or self-cross) while sweeping the
    # hanging curtain cleanly behind both the A-pose arms and the back/glutes.
    below = Q[:, 2] < sh_z - 12.0
    if not below.any():
        return Q, {"shifted_cm": 0.0}
    y_lo_src = float(np.percentile(Q[below, 1], 2))
    y_hi_src = float(np.percentile(Q[below, 1], 98))
    span_src = max(y_hi_src - y_lo_src, 4.0)
    y_hi_tgt = min(y_hi_src, arm_back_y - 2.8)
    min_depth = max(9.5, 0.45 * span_src)
    y_lo_tgt = min(trunk_back_y - 4.5, y_hi_tgt - min_depth)
    if y_hi_tgt - y_lo_tgt < min_depth:
        y_lo_tgt = y_hi_tgt - min_depth

    w_z = _smoothstep(sh_z - Q[:, 2], 0.0, 22.0)
    y_mapped = y_lo_tgt + (Q[:, 1] - y_lo_src) * ((y_hi_tgt - y_lo_tgt) / span_src)
    Q[:, 1] = (1.0 - w_z) * Q[:, 1] + w_z * y_mapped
    # Gentle downward-back drape flare below pelvis so the hem clears striding thighs/calves
    w_hem = _smoothstep(pel_z - Q[:, 2], 0.0, 50.0)
    Q[:, 1] -= 3.5 * w_hem
    info = dict(src_y=[round(y_lo_src, 1), round(y_hi_src, 1)], tgt_y=[round(y_lo_tgt, 1), round(y_hi_tgt, 1)],
                depth_scale=round((y_hi_tgt - y_lo_tgt) / span_src, 2),
                trunk_back_y=round(trunk_back_y, 1), arm_back_y=round(arm_back_y, 1))
    log(f"cloak drape: {info}")
    return Q, info


def align_limbs(Q, joints, kind, log=print, skin=None):
    """Turn sleeves (tops: two-segment shoulder + elbow alignment) or legs (bottoms) onto the limb bones.

    Tops use the real upper-arm bone (upperarm -> lowerarm) at the shoulder and, when the sleeve reaches
    past the elbow, bend the forearm segment about the elbow joint (lowerarm -> hand). All transition
    weights are smooth C1 ramps gated by real trunk-skin vs. arm-skin Voronoi distance (when `skin` is
    supplied) so straight/wide ribcages and flared hems never move with the sleeves and chest armholes
    never shear.
    """
    from scipy.spatial import cKDTree

    Q = Q.copy()
    done = {}
    if kind == "top":
        trunk_tree = None
        arm_trees = {}
        if skin is not None and len(skin):
            tmask, amasks = _arm_skin_masks(skin, joints)
            if tmask.any():
                trunk_tree = cKDTree(skin[tmask])
            for side, am in amasks.items():
                if am.any():
                    arm_trees[side] = cKDTree(skin[am])
        pairs = [("pelvis", "spine_01"), ("spine_01", "spine_02"), ("spine_02", "spine_03"),
                 ("spine_03", "spine_04"), ("spine_04", "spine_05"), ("spine_05", "neck_01"),
                 ("pelvis", "thigh_l"), ("thigh_l", "calf_l"), ("pelvis", "thigh_r"), ("thigh_r", "calf_r")]
        body_segs = np.asarray([(joints[a], joints[b]) for a, b in pairs if a in joints and b in joints], float)
        pelvis_z = float(joints["pelvis"][2])
        for side in ("l", "r"):
            sh = np.asarray(joints[f"upperarm_{side}"], float)
            el = np.asarray(joints[f"lowerarm_{side}"], float)
            wr = np.asarray(joints[f"hand_{side}"], float)
            u_up = (el - sh) / np.linalg.norm(el - sh)
            L_up = float(np.linalg.norm(el - sh))
            u_lo = (wr - el) / np.linalg.norm(wr - el)
            L_lo = float(np.linalg.norm(wr - el))
            sign = np.sign(sh[0]) or 1.

            rel = Q - sh
            lat = sign * (Q[:, 0] - sh[0])
            d_u, al_u = _ray_distance(Q, sh, u_up)

            if trunk_tree is not None and side in arm_trees:
                d_tr_skin = trunk_tree.query(Q, workers=-1)[0]
                d_ar_skin = arm_trees[side].query(Q, workers=-1)[0]
                # Strict skin-to-skin separation: ribs/waist/hips sit 0-3 cm from trunk skin and 8-30 cm from arm skin
                is_arm_side = d_ar_skin < d_tr_skin - 0.5
                d_other_for_axis = d_tr_skin + 6.0  # only used alongside is_arm_side
            else:
                d_body = _segments_distance(Q, body_segs)
                d_tr_skin, d_ar_skin = d_body, d_u
                is_arm_side = d_u < d_body
                d_other_for_axis = d_body

            # Detect a real sleeve extending laterally past the shoulder (rejects sleeveless vests)
            detect = is_arm_side & (lat > 3.5) & (al_u > 4.0) & (al_u < L_up + 5.0) & (d_u < 22.0) & (Q[:, 2] > pelvis_z + 10.0)
            if detect.sum() < 150 or float(np.percentile(lat[detect], 90)) < 8.0:
                done[f"upperarm_{side}"] = "none"
                continue

            al_max_u = min(L_up + 2.0, float(al_u[detect].max()) - 1.0)
            # Restrict axis estimation strictly to arm-side points so wide ribcages never bias cloth_dir downward
            axis_d_other = np.where(is_arm_side, d_other_for_axis, -1.0)
            cloth_dir = _centroid_axis(Q, sh, u_up, max(8.0, 0.55 * al_max_u), max(al_max_u, 14.0), 15.0, axis_d_other)
            cov = _angular_coverage(rel[is_arm_side], cloth_dir, 7.0, max(al_max_u, 14.0), 13.5)
            if cov < 11:
                done[f"upperarm_{side}"] = "none"
                continue

            d_c, al_c = _ray_distance(Q, sh, cloth_dir)
            on_upper = is_arm_side & (lat > 2.5) & (al_c > 7.0) & (al_c < L_up + 4.0) & (d_c < 14.5)
            sleeve_r = float(np.percentile(d_c[on_upper], 95)) if on_upper.sum() > 50 else 9.0

            if trunk_tree is not None and side in arm_trees:
                # 0.0 on ribs/chest/waist/hips (d_tr_skin < d_ar_skin), smoothly 1.0 across the sleeve
                w_vor = _smoothstep(d_tr_skin - d_ar_skin, -1.0, 4.0)
            else:
                w_vor = _smoothstep(d_tr_skin - d_c, 0.0, 6.0)
            w_sh = (w_vor
                    * _smoothstep(lat, -2.0, 4.5)
                    * _smoothstep(al_c, 0.0, 10.0)
                    * (1.0 - _smoothstep(d_c, sleeve_r + 4.0, sleeve_r + 10.0)))
            rot, ang_sh = _rodrigues(rel, cloth_dir, u_up, w_sh)
            move = w_sh > 0
            Q[move] = sh + rot[move]
            info = dict(turned_deg=round(ang_sh, 1), sleeve_r_cm=round(sleeve_r, 1), vertices=int(on_upper.sum()))

            # Forearm bend about the elbow joint when the sleeve extends well past the elbow
            if trunk_tree is not None and side in arm_trees:
                d_tr2 = trunk_tree.query(Q, workers=-1)[0]
                d_ar2 = arm_trees[side].query(Q, workers=-1)[0]
                is_arm2 = d_ar2 < d_tr2 - 1.5
                axis_d2 = np.where(is_arm2, d_tr2 + 6.0, -1.0)
            else:
                d_tr2 = _segments_distance(Q, body_segs)
                d_ar2 = None
                is_arm2 = np.ones(len(Q), bool)
                axis_d2 = d_tr2
            rel_el = Q - el
            d_el_u, al_el_u = _ray_distance(Q, el, u_up)
            fore_cand = is_arm2 & (d_el_u < d_tr2 - 3.0 if d_ar2 is None else True) & (al_el_u > 6.0) & (d_el_u < 22.0)
            if fore_cand.sum() > 250 and float(al_el_u[fore_cand].max()) > 14.0:
                fore_max = min(L_lo + 4.0, float(al_el_u[fore_cand].max()) - 1.0)
                fore_dir = _centroid_axis(Q, el, u_up, max(6.0, 0.45 * fore_max), fore_max, 18.0, axis_d2)
                if _angular_coverage(rel_el[is_arm2], fore_dir, 0.20 * L_lo, 0.65 * L_lo, 15.0) >= 11:
                    d_f, al_f = _ray_distance(Q, el, fore_dir)
                    fore = is_arm2 & (al_f > 3.0) & (d_f < max(sleeve_r + 5.0, 14.0))
                    fore_r = float(np.percentile(d_f[fore], 98)) if fore.sum() > 50 else sleeve_r
                    w_vor2 = _smoothstep(d_tr2 - d_ar2, 0.0, 5.0) if d_ar2 is not None else _smoothstep(d_tr2 - d_f, 2.0, 10.0)
                    w_el = (w_vor2
                            * _smoothstep(al_f, -6.0, 6.0)
                            * (1.0 - _smoothstep(d_f, fore_r + 3.0, fore_r + 9.0)))
                    rot_el, ang_el = _rodrigues(rel_el, fore_dir, u_lo, w_el)
                    move_el = w_el > 0
                    Q[move_el] = el + rot_el[move_el]
                    info.update(forearm_turned_deg=round(ang_el, 1), forearm_vertices=int(fore.sum()))
            done[f"upperarm_{side}"] = info
    else:
        for side in ("l", "r"):
            a, b = np.asarray(joints[f"thigh_{side}"], float), np.asarray(joints[f"foot_{side}"], float)
            bone = (b - a) / np.linalg.norm(b - a)
            sign = np.sign(a[0]) or 1.
            rel = Q - a
            d_b, along = _ray_distance(Q, a, bone)
            limb = (sign * Q[:, 0] > 0) & (along > 12.) & (d_b < 18.)
            length = float(np.linalg.norm(b - a)) * 0.45
            cov = _angular_coverage(rel[limb], bone, 0.35 * length + 6., length + 6., 18.)
            if cov < 11 or limb.sum() < 200:
                done[f"thigh_{side}"] = "none"
                continue
            pts = Q[limb] - a
            far = pts[along[limb] > np.percentile(along[limb], 35)]
            centre = far.mean(0)
            axis = np.linalg.svd(far - centre)[2][0]
            if axis @ bone < 0:
                axis = -axis
            cloth_dir = centre / np.linalg.norm(centre) if np.linalg.norm(centre) > 1 else axis
            direction = 0.5 * axis + 0.5 * cloth_dir
            direction /= np.linalg.norm(direction)
            d_c, al_c = _ray_distance(Q, a, direction)
            leg_r = float(np.percentile(d_c[limb], 95))
            blend = (_smoothstep(al_c, 2.0, 12.0)
                     * _smoothstep(sign * Q[:, 0], 0.0, 3.0)
                     * (1.0 - _smoothstep(d_c, leg_r + 2.0, leg_r + 7.0)))
            rotated, angle = _rodrigues(rel, direction, bone, blend)
            move = blend > 0
            Q[move] = a + rotated[move]
            done[f"thigh_{side}"] = dict(turned_deg=round(angle, 1), vertices=int(limb.sum()))
    log(f"limb alignment: {done}")
    return Q, done
