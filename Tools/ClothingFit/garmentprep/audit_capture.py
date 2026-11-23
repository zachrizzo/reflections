"""Audit an Unreal pose capture of one garment on one body (exact triangle tests, no emulation).

usage: python audit_capture.py <capture folder> [garment tag=jerkin] [under-layer tag=bottom] [workers=8]

Per pose it reports garment triangles that cross
  - skin that is NOT the free arm (neck, shoulders, torso, legs)   -> must be 0
  - free-arm skin (arms pressing on the garment)
  - the layer worn underneath                                      -> must be 0
and, for context, what the body does to itself in that pose:
  - floor: the same garment as a thin layer glued to the skin (0.6 cm above the skin point nearest to
    each vertex, carried by the skin). What still crosses it is the body folding over itself; no
    skinned garment with this coverage can have less contact. Reported for non-arm and arm skin.
Arm skin is found from the captured joints (capsules along the arm bones), so the same rule
works on every body. Writes <folder>/Audit_<tag>.json and prints a summary.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contact
from corridor import ArmCorridor, _segment
from meshops import read_surface, vertex_normals, tri_area, edges_of


def labels_of(folder):
    man = json.loads((folder / "Manifest.json").read_text())
    return ["standing"] + [f["label"] for c in man["clips"].values() for f in c["frames"]], man


def rest_joints(man, folder):
    override = Path(folder) / "joints_local.json"      # older captures did not record the arm joints
    if override.exists():
        return {k: np.asarray(v, float) for k, v in json.loads(override.read_text()).items()}
    rest = man["rest"]
    if "upperarm_l" in rest and "lowerarm_l" in rest:
        return {k: np.asarray(v, float) for k, v in rest.items()}
    return None


def arm_vertices(body, joints):
    """Free-arm skin of the standing body: inside the arm capsules, past the shoulder."""
    arms = ArmCorridor(body, joints, hang_deg=(), swing_deg=())
    near = arms.at_rest(body) < 1.2
    past = np.zeros(len(body), bool)
    for side in ("l", "r"):
        sh, el = joints[f"upperarm_{side}"], joints[f"lowerarm_{side}"]
        along = ((body - sh) @ (el - sh)) / ((el - sh) @ (el - sh))
        same_side = np.sign(body[:, 0]) == np.sign(sh[0])
        past |= same_side & (along > .30)
    return near & past


def depth_inside(points, skin, faces, sign):
    if not len(points) or not len(faces):
        return 0.
    cp, d, f = contact.closest_on_tris(points, skin, faces)
    _, fn = contact.vnormals(skin, faces)
    inside = np.einsum("ij,ij->i", points - cp, fn[f]) * sign < 0
    return float(d[inside].max() * 10) if inside.any() else 0.


def audit_pose(args):
    folder, label, tag, under, floor_offset = args
    folder = Path(folder)
    body0, bf = read_surface(folder / "standing_body.bin")
    man = json.loads((folder / "Manifest.json").read_text())
    joints = rest_joints(man, folder)
    arm_v = arm_vertices(body0, joints)
    body, _ = read_surface(folder / f"{label}_body.bin")
    face, ff = read_surface(folder / f"{label}_face.bin")
    cloth, cf = read_surface(folder / f"{label}_{tag}.bin")
    cloth0, _ = read_surface(folder / f"standing_{tag}.bin")
    skin = np.vstack((body, face)); sf = np.vstack((bf, ff + len(body)))
    a, b, c = skin[sf].transpose(1, 0, 2)
    sign = 1 if np.einsum("ij,ij->", a, np.cross(b, c)) > 0 else -1
    lo, hi = cloth.min(0) - 2, cloth.max(0) + 2
    near = np.all((skin >= lo) & (skin <= hi), axis=1)
    sub = sf[near[sf].any(1)]
    i_skin, i_cloth = contact.intersections(skin, sub, cloth, cf)
    arm_full = np.zeros(len(skin), bool); arm_full[:len(body)] = arm_v
    is_arm = arm_full[sub].sum(1) >= 2
    g_arm = np.unique(i_cloth[is_arm[i_skin]]); g_other = np.unique(i_cloth[~is_arm[i_skin]])
    area_arm = tri_area(skin, sub[np.unique(i_skin[is_arm[i_skin]])]).sum()
    area_other = tri_area(skin, sub[np.unique(i_skin[~is_arm[i_skin]])]).sum()
    depth = 0.
    if len(g_other):
        pts = np.vstack((cloth[np.unique(cf[g_other])], cloth[cf[g_other]].mean(1)))
        depth = depth_inside(pts, skin, sub[~is_arm], sign)
    row = dict(label=label, other_tris=int(len(g_other)), other_area_cm2=round(float(area_other), 2), other_depth_mm=round(depth, 2),
               arm_tris=int(len(g_arm)), arm_area_cm2=round(float(area_arm), 2))
    if len(g_other):
        cen = cloth0[cf[g_other]].mean(1)
        row["other_where_cm"] = dict(z=[round(float(cen[:, 2].min()), 1), round(float(cen[:, 2].max()), 1)],
                                     x_abs=[round(float(np.abs(cen[:, 0]).min()), 1), round(float(np.abs(cen[:, 0]).max()), 1)],
                                     y=[round(float(cen[:, 1].min()), 1), round(float(cen[:, 1].max()), 1)])
    under_file = folder / f"{label}_{under}.bin"
    if under and under_file.exists():
        layer, lf = read_surface(under_file)
        _, t_cloth = contact.intersections(layer, lf, cloth, cf)
        row["under_tris"] = int(len(np.unique(t_cloth)))
    e = edges_of(cf)
    l0 = np.linalg.norm(cloth0[e[:, 0]] - cloth0[e[:, 1]], axis=1); l1 = np.linalg.norm(cloth[e[:, 0]] - cloth[e[:, 1]], axis=1)
    ok = l0 > .05
    row["stretch_p95_pct"] = round(float(np.percentile((l1[ok] / l0[ok] - 1) * 100, 95)), 2)
    # ---- the floor no skinned garment with this coverage can beat: the same garment as a thin layer
    # glued to the skin. Every garment vertex is put `floor_offset` cm above the skin point nearest to
    # it at standing and carried by that skin triangle into the pose. Whatever crosses this layer is the
    # body folding over itself (armpit folds, a forearm across the belly), not a fault of the fit.
    near0 = bf[np.all((body0[bf] >= cloth0.min(0) - 8) & (body0[bf] <= cloth0.max(0) + 8), axis=(1, 2))]
    cp, _, f = contact.closest_on_tris(cloth0, body0, near0, k=12)
    tri = near0[f]
    a0, b0_, c0_ = body0[tri[:, 0]], body0[tri[:, 1]], body0[tri[:, 2]]
    v0, v1, v2 = b0_ - a0, c0_ - a0, cp - a0
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    den = np.where(np.abs(d00 * d11 - d01 * d01) < 1e-14, 1e-14, d00 * d11 - d01 * d01)
    wv = (d11 * d20 - d01 * d21) / den
    ww = (d00 * d21 - d01 * d20) / den
    a1, b1_, c1_ = body[tri[:, 0]], body[tri[:, 1]], body[tri[:, 2]]
    on_skin = a1 + wv[:, None] * (b1_ - a1) + ww[:, None] * (c1_ - a1)
    n1 = np.cross(b1_ - a1, c1_ - a1)
    n1 /= np.maximum(np.linalg.norm(n1, axis=1), 1e-12)[:, None]
    glued = on_skin + n1 * sign * floor_offset
    j_skin, j_cloth = contact.intersections(skin, sub, glued, cf)
    row["floor_other_tris"] = int(len(np.unique(j_cloth[~is_arm[j_skin]])))
    row["floor_arm_tris"] = int(len(np.unique(j_cloth[is_arm[j_skin]])))
    np.savez_compressed(folder / f"audit_{tag}_{label}.npz", arm=g_arm, other=g_other)
    return row


def summarize(rows):
    out = {}
    for name in ("standing", "walk", "reach"):
        r = [x for x in rows if x["label"].startswith(name)]
        if not r:
            continue
        failing = [x["label"] for x in r if x["other_tris"] > 0]
        out[name] = dict(
            poses=len(r), poses_clear_of_non_arm_skin=len(r) - len(failing), failing_poses=failing,
            non_arm_tris_peak=max(x["other_tris"] for x in r), non_arm_area_peak_cm2=max(x["other_area_cm2"] for x in r),
            non_arm_depth_peak_mm=max(x["other_depth_mm"] for x in r),
            poses_with_arm_contact=sum(x["arm_tris"] > 0 for x in r), arm_tris_median=int(np.median([x["arm_tris"] for x in r])),
            arm_tris_peak=max(x["arm_tris"] for x in r), arm_area_peak_cm2=max(x["arm_area_cm2"] for x in r),
            poses_with_under_layer_contact=sum(x.get("under_tris", 0) > 0 for x in r),
            stretch_p95_worst_pct=max(x["stretch_p95_pct"] for x in r),
floor_non_arm_tris_median=int(np.median([x["floor_other_tris"] for x in r])), floor_non_arm_tris_peak=max(x["floor_other_tris"] for x in r),
            floor_arm_tris_median=int(np.median([x["floor_arm_tris"] for x in r])), floor_arm_tris_peak=max(x["floor_arm_tris"] for x in r),
            non_arm_tris_median=int(np.median([x["other_tris"] for x in r])),
            poses_within_floor=sum(x["other_tris"] <= x["floor_other_tris"] * 1.15 + 10 for x in r))
    return out


def run(folder, tag="jerkin", under="bottom", workers=8, floor_offset=.6):
    from multiprocessing import Pool
    folder = Path(folder)
    labels, man = labels_of(folder)
    with Pool(workers) as pool:
        rows = pool.map(audit_pose, [(str(folder), l, tag, under, floor_offset) for l in labels])
    summary = summarize(rows)
    (folder / f"Audit_{tag}.json").write_text(json.dumps(dict(measured_in="Unreal capture, cloth physics off", garment=tag, floor_layer_offset_cm=floor_offset,
                                                       summary=summary, poses=rows), indent=1))
    return summary, rows


if __name__ == "__main__":
    t = time.time()
    summary, rows = run(sys.argv[1], *(sys.argv[2:4]), workers=int(sys.argv[4]) if len(sys.argv) > 4 else 8)
    print(json.dumps(summary, indent=1))
    print("audit", round(time.time() - t), "s")
