"""EMULATION, not an Unreal measurement: what would a body hidden-face map remove?

  python estimate_hidden_skin.py <capture folder of one body> <garment tag> [margin cm=2.5] [every n-th pose=2]

MetaHuman outfits can carry a hidden-face map: body triangles under the garment are removed when the
character is built, so that skin cannot show through the cloth. This script marks the body skin a garment
covers in the standing capture (not closer than `margin` to uncovered skin, measured over the skin), drops
those triangles, and counts again, per pose, the garment triangles that cross non-arm skin.
It does not write a texture and it does not prove what a built character shows.
"""
import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contact
from audit_capture import arm_vertices, labels_of, rest_joints
from meshops import edges_of, read_surface, weld


def hidden_triangles(body, bf, cloth, cf, margin, reach=3.2):
    """Body triangles fully under the garment and at least `margin` cm (over the skin) from uncovered skin."""
    W, Fw, inv = weld(body, bf)
    lo, hi = cloth.min(0) - reach, cloth.max(0) + reach
    near = np.flatnonzero(np.all((W >= lo) & (W <= hi), axis=1))
    covered = np.zeros(len(W), bool)
    cp, d, _ = contact.closest_on_tris(W[near], cloth, cf)
    normals, _ = contact.vnormals(W, Fw)
    a, b, c = W[Fw].transpose(1, 0, 2)
    if np.einsum("ij,ij->", a - W.mean(0), np.cross(b - W.mean(0), c - W.mean(0))) < 0:
        normals = -normals                                   # captures use the opposite winding
    outward = np.einsum("ij,ij->i", cp - W[near], normals[near])
    covered[near] = (d < reach) & (outward > .2 * d)
    e = edges_of(Fw)
    length = np.linalg.norm(W[e[:, 0]] - W[e[:, 1]], axis=1)
    graph = sp.coo_matrix((np.r_[length, length], (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(len(W), len(W))).tocsr()
    seeds = np.flatnonzero(~covered)
    close = np.isfinite(dijkstra(graph, directed=False, indices=seeds, min_only=True, limit=margin))
    hide_vertex = covered & ~close
    return hide_vertex[inv][bf].all(1), float(covered[near].mean())


def main():
    folder, tag = Path(sys.argv[1]), sys.argv[2]
    margin = float(sys.argv[3]) if len(sys.argv) > 3 else 2.5
    step = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    labels, man = labels_of(folder)
    body0, bf = read_surface(folder / "standing_body.bin")
    cloth0, cf = read_surface(folder / f"standing_{tag}.bin")
    hide, _ = hidden_triangles(body0, bf, cloth0, cf, margin)
    arm_v = arm_vertices(body0, rest_joints(man, folder))
    rows = []
    for label in [l for l in labels if l != "standing"][::step]:
        body, _ = read_surface(folder / f"{label}_body.bin")
        face, ff = read_surface(folder / f"{label}_face.bin")
        cloth, _ = read_surface(folder / f"{label}_{tag}.bin")
        skin = np.vstack((body, face))
        counts = {}
        for name, body_faces in (("now", bf), ("hidden", bf[~hide])):
            sf = np.vstack((body_faces, ff + len(body)))
            lo, hi = cloth.min(0) - 2, cloth.max(0) + 2
            near = np.all((skin >= lo) & (skin <= hi), axis=1)
            sub = sf[near[sf].any(1)]
            i_skin, i_cloth = contact.intersections(skin, sub, cloth, cf)
            arm_full = np.zeros(len(skin), bool); arm_full[:len(body)] = arm_v
            is_arm = arm_full[sub].sum(1) >= 2
            counts[name] = int(len(np.unique(i_cloth[~is_arm[i_skin]])))
            counts[name + "_arm"] = int(len(np.unique(i_cloth[is_arm[i_skin]])))
        rows.append(dict(label=label, **counts))
    out = dict(emulation=True, body=folder.name, garment=tag, margin_cm=margin, body_triangles=int(len(bf)), hidden_triangles=int(hide.sum()), poses=rows)
    for clip in ("walk", "reach"):
        r = [x for x in rows if x["label"].startswith(clip)]
        if r:
            out[clip] = dict(poses=len(r), non_arm_median_now=int(np.median([x["now"] for x in r])), non_arm_median_hidden=int(np.median([x["hidden"] for x in r])),
                             non_arm_peak_now=max(x["now"] for x in r), non_arm_peak_hidden=max(x["hidden"] for x in r),
                             poses_clear_now=sum(x["now"] == 0 for x in r), poses_clear_hidden=sum(x["hidden"] == 0 for x in r),
                             arm_median=int(np.median([x["now_arm"] for x in r])))
    (folder / f"HiddenSkinEstimate_{tag}.json").write_text(json.dumps(out, indent=1))
    print(folder.name, tag, "hidden body triangles", out["hidden_triangles"], "of", out["body_triangles"], {k: out[k] for k in ("walk", "reach") if k in out})


if __name__ == "__main__":
    main()
