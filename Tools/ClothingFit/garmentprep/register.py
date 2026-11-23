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

    forgive = .97 if kind == "top" else .995       # a bottom has no neck hole: a waistband through the belly must count

    def cost(x):
        s, w, d, ys, zs, lean = x
        Q = apply(sample, (s, w, d, mid_y + ys, top_z + zs, lean), top_z + zs - .5 * height * s)
        outside_box = np.clip(box_lo - Q, 0, None).sum(1) + np.clip(Q - box_hi, 0, None).sum(1)
        phi = body(np.clip(Q, box_lo, box_hi))
        inside = np.sort(np.clip(.4 - phi, 0, None))[: int(forgive * len(phi))]      # tops: forgive the worst 3% (a flat neck hole)
        loose = np.sort(np.clip(phi - (ease + 1.), 0, 10))[: int(.9 * len(phi))]     # forgive flared edges and caps
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
    Q, limbs = align_limbs(Q, joints, kind, log)
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


def align_limbs(Q, joints, kind, log=print):
    """Turn sleeves (tops) or legs (bottoms) about the shoulder or hip joint onto the limb's bone."""
    Q = Q.copy()
    done = {}
    chains = [("upperarm", "hand")] if kind == "top" else [("thigh", "foot")]
    for first, last in chains:
        for side in ("l", "r"):
            a, b = np.asarray(joints[f"{first}_{side}"], float), np.asarray(joints[f"{last}_{side}"], float)
            bone = (b - a) / np.linalg.norm(b - a)
            sign = np.sign(a[0]) or 1.
            rel = Q - a
            along = rel @ bone
            radial = np.linalg.norm(rel - along[:, None] * bone, axis=1)
            if kind == "top":
                # cloth beyond the shoulder joint, on its side, that is not the trunk part of the garment
                limb = (sign * Q[:, 0] > sign * a[0] + 2.) & (along > 4.) & (radial < 16.)
            else:
                limb = (sign * Q[:, 0] > 0) & (along > 12.) & (radial < 18.)
            # a sleeve or leg wraps the limb: half way down the upper bone there is cloth all the way round it
            length = np.linalg.norm(b - a) * (.5 if kind == "top" else .45)
            ring = limb & (along > .35 * length * 2 * .5 + 6.) & (along < length + 6.)
            covered = 0
            if ring.sum() > 60:
                side_axis = np.cross(bone, [0., 1., 0.]); side_axis /= np.linalg.norm(side_axis)
                up_axis = np.cross(side_axis, bone)
                off = rel[ring] - along[ring][:, None] * bone
                angle = np.degrees(np.arctan2(off @ up_axis, off @ side_axis))
                covered = len(np.unique(((angle + 180) // 30).astype(int)))
            if covered < 11:
                limb = np.zeros(len(Q), bool)
            if limb.sum() < 200:
                done[f"{first}_{side}"] = "none"
                continue
            pts = Q[limb] - a
            reach_radius = float(np.percentile(radial[limb & (along > .5 * np.linalg.norm(b - a))], 90)) if (limb & (along > .5 * np.linalg.norm(b - a))).sum() > 30 else 9.
            far = pts[along[limb] > np.percentile(along[limb], 35)]
            centre = far.mean(0)
            axis = np.linalg.svd(far - centre)[2][0]
            if axis @ bone < 0:
                axis = -axis
            # the limb's cloth axis should pass through the joint and run along the bone
            cloth_dir = centre / np.linalg.norm(centre) if np.linalg.norm(centre) > 1 else axis
            direction = .5 * axis + .5 * cloth_dir
            direction /= np.linalg.norm(direction)
            v = np.cross(direction, bone)
            sin, cos = np.linalg.norm(v), float(direction @ bone)
            angle = float(np.degrees(np.arctan2(sin, cos)))
            if sin < 1e-6 or angle < 1.:
                done[f"{first}_{side}"] = dict(turned_deg=0.)
                continue
            k = v / sin
            K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
            reach = np.clip((along - 2.) / 10., 0, 1)
            blend = (reach * reach * (3 - 2 * reach)) * (sign * Q[:, 0] > (sign * a[0] - 2. if kind == "top" else 0))
            # only the cloth that hugs the limb turns; the trunk part beside it stays
            blend = blend * np.clip((reach_radius + 4. - radial) / 4., 0, 1)
            theta = np.radians(angle) * blend
            c, s_ = np.cos(theta)[:, None], np.sin(theta)[:, None]
            rotated = rel * c + (rel @ K.T) * s_ + (rel @ k)[:, None] * k * (1 - c)
            move = blend > 0
            Q[move] = a + rotated[move]
            done[f"{first}_{side}"] = dict(turned_deg=round(angle, 1), vertices=int(limb.sum()))
    log(f"limb alignment: {done}")
    return Q, done
