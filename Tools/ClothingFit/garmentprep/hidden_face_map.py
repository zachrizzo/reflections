"""Body hidden-face map for a garment: which MetaHuman body triangles the garment hides, painted in body UV space.

  python hidden_face_map.py <capture folder of the source body> <garment tag> <out folder> [--name <Name>] [--margin 2.5]

Input: the Unreal pose captures of the garment on the source body (standing + every walk/reach frame of the test).
Rule (the same for every garment, nothing per garment):
  1. In every captured pose, a body vertex counts as covered only when it cannot be seen: every line of sight in a
     wide cone around its outward normal (straight out, and rings tilted 35 and 60 degrees) meets the garment within
     SIGHT cm. Skin inside a narrow opening (a neck slit, a vent) therefore stays visible. A quick distance test
     (garment within REACH cm and over the skin) only narrows down which vertices get that test.
  2. A vertex is hidden only if it is covered in every pose AND at least `margin` cm (measured over the skin) away from
     any vertex that is uncovered in any pose. That margin is kept in from every opening (neck, armholes, cuffs, hem).
  3. Hands (past the wrist), feet (below the ankle) and the neck above neck_01 are never hidden; the head is a
     separate mesh and gets no map.
  4. A body triangle is meant to be hidden when its three corners are hidden.
The map is painted in the engine's own pixel space (UV0, red channel, Wrap(uv * Res, 0, Res - 1) as in
MetaHumanGeometryRemoval.cpp) and then checked with a port of the engine's ShouldHideTriangle: black = remove,
white = keep. Triangles the engine would remove are never more than the ones meant to be hidden (asserted).
Writes <out>/BodyHiddenFaceMap.png and <out>/BodyHiddenFaceMap.json.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contact
from audit_capture import labels_of, rest_joints
from body_uv import DEFAULT as UV_DUMP, corner_uvs
from meshops import edges_of, read_surface, weld

REACH = 4.0          # cm: garment further from the skin than this does not count as covering it
CONTACT = 1.0        # cm: garment this close counts as covering whatever its direction (touching or entering)
MARGIN = 2.5         # cm over the skin, kept from any skin that is uncovered in any pose
SIGHT = 8.0          # cm: a line of sight that meets no garment within this distance counts as open
CONE = ((35., 6), (60., 8))    # rings of sight lines around the normal: tilt in degrees, how many
RESOLUTION = 2048
MAX_CULL = 0.1       # FHiddenFaceMapSettings defaults
EPS = np.float32(1e-4)  # UE_KINDA_SMALL_NUMBER, added to every UV by RemoveAndShrinkGeometry


# ---------------------------------------------------------------- geometry: what the garment covers
def outward_normals(W, Fw):
    normals, _ = contact.vnormals(W, Fw)
    a, b, c = W[Fw].transpose(1, 0, 2)
    m = W.mean(0)
    if np.einsum("ij,ij->", a - m, np.cross(b - m, c - m)) < 0:
        normals = -normals                       # captures use the opposite winding
    return normals


def covered(W, Fw, cloth, cf, reach=REACH, touch=CONTACT):
    lo, hi = cloth.min(0) - reach, cloth.max(0) + reach
    near = np.flatnonzero(np.all((W >= lo) & (W <= hi), axis=1))
    out = np.zeros(len(W), bool)
    if not len(near):
        return out
    cp, d, _ = contact.closest_on_tris(W[near], cloth, cf)
    n = outward_normals(W, Fw)[near]
    up = np.einsum("ij,ij->i", cp - W[near], n)
    out[near] = (d < reach) & ((up > .5 * d) | (d < touch))
    return out


def sees_out(points, normals, cloth, cf, sight=SIGHT, cone=CONE, step=1.2):
    """True for a skin point that can be seen from outside: some line of sight in a wide cone around its
    normal leaves without meeting the garment. Errs toward True (a missed hit keeps the skin)."""
    from scipy.spatial import cKDTree
    if not len(points):
        return np.zeros(0, bool)
    helper = np.where(np.abs(normals[:, :1]) < .9, np.array([[1., 0., 0.]]), np.array([[0., 1., 0.]]))
    u = np.cross(normals, helper); u /= np.maximum(np.linalg.norm(u, axis=1), 1e-12)[:, None]
    v = np.cross(normals, u)
    directions = [normals]
    for tilt, count in cone:
        t = np.radians(tilt)
        for k in range(count):
            a = 2 * np.pi * k / count
            directions.append(np.cos(t) * normals + np.sin(t) * (np.cos(a) * u + np.sin(a) * v))
    A, B, C = cloth[cf].transpose(1, 0, 2)
    centre = (A + B + C) / 3
    radius = float(np.percentile(np.linalg.norm(A - centre, axis=1), 97))      # larger triangles can be missed: that keeps skin
    tree = cKDTree(centre)
    start = points + .05 * normals
    open_ = np.zeros(len(points), bool)
    reach_box = radius + step
    box_lo, box_hi = cloth.min(0) - reach_box, cloth.max(0) + reach_box
    for d in directions:
        alive = np.flatnonzero(~open_)
        if not len(alive):
            break
        p0, dirs = start[alive], d[alive]
        p1 = p0 + sight * dirs
        hit = np.zeros(len(alive), bool)
        gone = np.zeros(len(alive), bool)                  # left the garment's box: nothing more to meet
        for along in np.arange(step / 2, sight, step):
            todo = np.flatnonzero(~hit & ~gone)
            if not len(todo):
                break
            sample = p0[todo] + along * dirs[todo]
            outside = np.any((sample < box_lo) | (sample > box_hi), axis=1)
            gone[todo[outside]] = True
            todo = todo[~outside]
            if not len(todo):
                continue
            found = tree.query_ball_point(p0[todo] + along * dirs[todo], radius + step / 2 + .02)
            counts = np.fromiter((len(f) for f in found), np.int64, len(found))
            if not counts.sum():
                continue
            ray = np.repeat(todo, counts)
            tri = np.concatenate([np.asarray(f, np.int64) for f in found if len(f)])
            crossed = contact._seg_tri(p0[ray], p1[ray], A[tri], B[tri], C[tri])
            hit[np.unique(ray[crossed])] = True
        open_[alive[~hit]] = True
    return open_


def never_hidden(W, joints):
    """Hands past the wrist, feet below the ankle, neck above neck_01."""
    keep = W[:, 2] > joints["neck_01"][2]
    # every vertex belongs to its nearest bone segment; the hand segments reach from the wrist 18 cm on
    chain = [("pelvis", "spine_01"), ("spine_01", "spine_03"), ("spine_03", "spine_05"), ("spine_05", "neck_01"), ("neck_01", "head")]
    hands = []
    for side in ("l", "r"):
        chain += [(f"clavicle_{side}", f"upperarm_{side}"), (f"upperarm_{side}", f"lowerarm_{side}"), (f"lowerarm_{side}", f"hand_{side}"),
                  ("pelvis", f"thigh_{side}"), (f"thigh_{side}", f"calf_{side}"), (f"calf_{side}", f"foot_{side}")]
        hands.append(len(chain))
        chain.append(None)
    dist = []
    for seg in chain:
        if seg is None:
            side = "l" if len(hands) and len(dist) == hands[0] else "r"
            a = joints[f"hand_{side}"]
            d = a - joints[f"lowerarm_{side}"]
            b = a + 18. * d / np.linalg.norm(d)
        else:
            a, b = joints[seg[0]], joints[seg[1]]
        t = np.clip(((W - a) @ (b - a)) / max((b - a) @ (b - a), 1e-9), 0, 1)
        dist.append(np.linalg.norm(W - (a + t[:, None] * (b - a)), axis=1))
    nearest = np.argmin(np.stack(dist, 1), 1)
    keep |= np.isin(nearest, hands)
    keep |= W[:, 2] < min(joints["foot_l"][2], joints["foot_r"][2]) + 1.
    return keep


def intended(folder, tag, margin=MARGIN, standing_only=False):
    """Per body triangle of the capture: True where the rule hides it. Also returns a summary."""
    labels, man = labels_of(folder)
    body0, bf = read_surface(folder / "standing_body.bin")
    W0, Fw, inv = weld(body0, bf)
    first = np.zeros(len(W0), np.int64); first[inv[::-1]] = np.arange(len(inv))[::-1]
    always = np.ones(len(W0), bool)
    per_pose = []
    for label in labels[:1] if standing_only else labels:
        body, _ = read_surface(folder / f"{label}_body.bin")
        cloth, cf = read_surface(folder / f"{label}_{tag}.bin")
        c = covered(body[first], Fw, cloth, cf)
        always &= c
        per_pose.append(int(c.sum()))
    joints = rest_joints(man, folder) or {k: np.asarray(v, float) for k, v in man["rest"].items()}
    joints = {**{k: np.asarray(v, float) for k, v in man["rest"].items()}, **joints}
    excluded = never_hidden(W0, joints)
    # the decisive test, on the vertices that are still candidates: can the skin be seen in any pose?
    near_garment = int(always.sum())
    candidates = np.flatnonzero(always & ~excluded)
    for label in labels[:1] if standing_only else labels:
        if not len(candidates):
            break
        body, _ = read_surface(folder / f"{label}_body.bin")
        cloth, cf = read_surface(folder / f"{label}_{tag}.bin")
        posed = body[first]
        seen = sees_out(posed[candidates], outward_normals(posed, Fw)[candidates], cloth, cf)
        always[candidates[seen]] = False
        candidates = candidates[~seen]
    e = edges_of(Fw)
    length = np.linalg.norm(W0[e[:, 0]] - W0[e[:, 1]], axis=1)
    graph = sp.coo_matrix((np.r_[length, length], (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(len(W0), len(W0))).tocsr()
    seeds = np.flatnonzero(~always | excluded)
    close = np.isfinite(dijkstra(graph, directed=False, indices=seeds, min_only=True, limit=margin))
    hide_v = always & ~excluded & ~close
    hide_t = hide_v[inv][bf].all(1)
    info = dict(poses=len(labels), near_garment_in_every_pose_vertices=near_garment, covered_in_every_pose_vertices=int(always.sum()), covered_vertices_per_pose_min_max=[min(per_pose), max(per_pose)],
                excluded_vertices=int(excluded.sum()), intended_vertices=int(hide_v.sum()), intended_triangles=int(hide_t.sum()))
    return hide_t, bf, info


# ---------------------------------------------------------------- the engine's pixel rule (MetaHumanGeometryRemoval.cpp)
def wrap(x, lo, hi):
    """FMath::Wrap in float32."""
    x = np.asarray(x, np.float32); lo = np.float32(lo); hi = np.float32(hi)
    size = hi - lo
    out = x.copy()
    below, above = x < lo, x > hi
    mod_b = np.fmod(lo - x, size); mod_a = np.fmod(x - hi, size)
    out = np.where(below, np.where(mod_b != 0, hi - mod_b, lo), out)
    out = np.where(above, np.where(mod_a != 0, lo + mod_a, hi), out)
    return out


def engine_pixels(uv, res):
    """Pixel coordinates the engine uses for each triangle corner (ShouldHideTriangle, with the +KINDA_SMALL_NUMBER)."""
    u = (uv.astype(np.float32) + EPS) * np.float32(res)
    px = np.floor(wrap(u[..., 0], 0, res - 1)).astype(np.int64)
    py = np.floor(wrap(u[..., 1], 0, res - 1)).astype(np.int64)
    return np.stack((px, py), -1)


def _seg(a0, a1, b0, b1):
    va, vb = a1 - a0, b1 - b0
    den = -vb[0] * va[1] + va[0] * vb[1]
    if den == 0:
        return False
    s = (-va[1] * (a0[0] - b0[0]) + va[0] * (a0[1] - b0[1])) / den
    t = (vb[0] * (a0[1] - b0[1]) - vb[1] * (a0[0] - b0[0])) / den
    return 0 <= s <= 1 and 0 <= t <= 1


def tri_touches_pixel(tri, x, y):
    """TriangleStripHelper::IntersectTriangleAndAABB for integer corners and the pixel box [x, x+1] x [y, y+1]."""
    bmin, bmax = np.array([x, y], float), np.array([x + 1, y + 1], float)
    tmin, tmax = tri.min(0), tri.max(0)
    if tmin[0] >= bmax[0] or bmin[0] >= tmax[0] or tmin[1] >= bmax[1] or bmin[1] >= tmax[1]:
        return False
    for p in tri:
        if bmin[0] <= p[0] <= bmax[0] and bmin[1] <= p[1] <= bmax[1]:
            return True
    extent = 2. * np.linalg.norm(bmax - bmin) + 2. * np.linalg.norm(tmax - tmin)
    for q in (bmin, bmax, np.array([bmin[0], bmax[1]]), np.array([bmax[0], bmin[1]])):
        hits = sum(_seg(tri[i], tri[(i + 1) % 3], q, q + extent) for i in range(3))
        if hits == 1:
            return True
    corners = [(bmin, np.array([bmin[0], bmax[1]])), (bmax, np.array([bmin[0], bmax[1]])), (bmax, np.array([bmax[0], bmin[1]])), (bmin, np.array([bmax[0], bmin[1]]))]
    for i in range(3):
        if any(_seg(tri[i], tri[(i + 1) % 3], c0, c1) for c0, c1 in corners):
            return True
    return False


def engine_hidden(uv, image, max_cull=MAX_CULL):
    """Port of ShouldHideTriangle for every triangle: True where the engine removes it."""
    res_y, res_x = image.shape
    assert res_x == res_y
    culled = image.astype(np.float32) / 255. <= max_cull           # SampleHiddenFaceMap reads R; G8 gives R = value
    pix = engine_pixels(uv, res_x)
    lo, hi = pix.min(1), pix.max(1)
    out = np.zeros(len(uv), bool)
    # integral image of kept pixels: a bbox with no kept pixel is removed without detailed tests
    kept = np.pad((~culled).astype(np.int64).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    n_kept = kept[hi[:, 1] + 1, hi[:, 0] + 1] - kept[lo[:, 1], hi[:, 0] + 1] - kept[hi[:, 1] + 1, lo[:, 0]] + kept[lo[:, 1], lo[:, 0]]
    flat = (lo[:, 0] == hi[:, 0]) | (lo[:, 1] == hi[:, 1])
    out[flat] = culled[lo[flat, 1], lo[flat, 0]]
    full = ~flat & (n_kept == 0)
    out[full] = True
    for t in np.flatnonzero(~flat & (n_kept > 0)):
        tri = pix[t].astype(float)
        hidden = True
        for y in range(lo[t, 1], hi[t, 1] + 1):
            for x in range(lo[t, 0], hi[t, 0] + 1):
                if not culled[y, x] and tri_touches_pixel(tri, x, y):
                    hidden = False
                    break
            if not hidden:
                break
        out[t] = hidden
    return out


def paint(uv, hide, res=RESOLUTION, grey=None):
    """White image; the pixel box of every triangle meant to be hidden black; then the pixel box of every other
    triangle white again, so no kept triangle can lose a pixel to a hidden neighbour. `grey` (per triangle, 0..255,
    255 = untouched) paints the kept triangles of the shrink band in their own value on top."""
    image = np.full((res, res), 255, np.uint8)
    pix = engine_pixels(uv, res)
    lo, hi = pix.min(1), pix.max(1)
    for t in np.flatnonzero(hide):
        image[lo[t, 1]:hi[t, 1] + 1, lo[t, 0]:hi[t, 0] + 1] = 0
    for t in np.flatnonzero(~hide):
        image[lo[t, 1]:hi[t, 1] + 1, lo[t, 0]:hi[t, 0] + 1] = 255
    if grey is not None:
        from PIL import Image, ImageDraw
        canvas = Image.fromarray(image, "L")
        draw = ImageDraw.Draw(canvas)
        for t in np.flatnonzero(~hide & (grey < 255)):
            value = int(grey[t])
            draw.polygon([(int(x), int(y)) for x, y in pix[t]], fill=value, outline=value)
        image = np.asarray(canvas).copy()
    return image


GREY_KEEP, GREY_CULL = 229, 28      # just inside MinKeepValue 0.9 and just above MaxCullValue 0.1


def build(folder, tag, out, name=None, margin=MARGIN, res=RESOLUTION, standing_only=False, rule="sight", shrink=0.):
    """rule "sight" (default): layer_hide.meant_hidden, skin that cannot be seen from outside the garment in any pose
    (a line of sight counts only if it leaves the garment altogether; skin that comes out through the cloth is hidden).
    rule "near": the first, cautious rule (`intended`: garment within REACH cm and no open line of sight within SIGHT cm).
    shrink > 0 paints the kept band next to the hidden skin grey, for the engine's MaxShrinkDistance."""
    from PIL import Image
    started = time.time()
    grey = None
    if rule == "sight":
        import layer_hide
        hide, geo, info = layer_hide.meant_hidden(Path(folder), tag, "body", margin)
        _, bf = read_surface(Path(folder) / "standing_body.bin")
        info = dict(info, intended_triangles=info["hidden_triangles"])
        rule_text = layer_hide.__doc__.split("Rule (")[1].split("hidden_face_map.py uses")[0].strip()
        if shrink > 0:
            weight = np.clip(geo["dist"] / margin, 0, 1)
            weight = np.where(np.isfinite(weight), weight, 1.) * ~geo["keep"]
            per_triangle = weight[geo["inv"]][bf].mean(1)
            grey = np.where(per_triangle > 0, np.round(GREY_KEEP - per_triangle * (GREY_KEEP - GREY_CULL)), 255).astype(np.int64)
    else:
        hide, bf, info = intended(Path(folder), tag, margin, standing_only)
        rule_text = __doc__.split("Rule (")[1].split("The map is")[0].strip()
    info["poses_used"] = "standing only (comparison, not the pipeline rule)" if standing_only else "standing and every captured motion frame"
    uv = corner_uvs(bf)
    image = paint(uv, hide, res, grey)
    removed = engine_hidden(uv, image)
    assert not (removed & ~hide).any(), "the painted map would remove a triangle the rule keeps"
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image, "L").save(out / "BodyHiddenFaceMap.png")
    report = dict(garment=name or tag, capture=str(folder), tag=tag, rule_name=rule, rule=rule_text,
                  reach_cm=REACH, sight_cm=SIGHT, sight_cone=[list(c) for c in CONE], margin_cm=margin, resolution=res, uv_channel=0,
                  settings=dict(MaxCullValue=MAX_CULL, MinKeepValue=.9, MaxShrinkDistance=float(shrink)),
                  body_triangles=int(len(bf)), engine_removed_triangles=int(removed.sum()), uv_layout=str(UV_DUMP),
                  note="engine_removed_triangles is the port of the engine's ShouldHideTriangle on this PNG; a triangle that shares a "
                       "corner pixel with a kept triangle is kept, so about one ring of the intended set stays.")
    report.update(info)
    report["seconds"] = round(time.time() - started)
    np.save(out / "BodyHiddenFaceMap_removed.npy", removed)
    (out / "BodyHiddenFaceMap.json").write_text(json.dumps(report, indent=1))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path)
    parser.add_argument("tag")
    parser.add_argument("out", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--margin", type=float, default=MARGIN)
    parser.add_argument("--resolution", type=int, default=RESOLUTION)
    parser.add_argument("--standing-only", action="store_true", help="comparison only: coverage from the standing capture alone")
    parser.add_argument("--rule", choices=("sight", "near"), default="sight")
    parser.add_argument("--shrink", type=float, default=0., help="cm; MaxShrinkDistance for the kept band next to hidden skin (0 = off)")
    args = parser.parse_args()
    report = build(args.folder, args.tag, args.out, args.name, args.margin, args.resolution, args.standing_only, args.rule, args.shrink)
    print(json.dumps({k: v for k, v in report.items() if k not in ("rule", "note")}, indent=1))


if __name__ == "__main__":
    main()
