"""What a covering garment hides underneath it: body skin, or another garment worn under it.

  python layer_hide.py <capture folder> <cover tag> [--base body|<tag of the layer underneath>] [--margin 2.5]
                       [--poke 5] [--shrink 0] [--out <folder>]

Rule ("meant to be covered"), the same for skin and for an under-layer:
  1. Standing: the surface point is under the cover and cannot be seen (hidden_face_map.sees_out).
  2. Every other captured pose: the point is still not seen, OR it is seen only because it has come out THROUGH the
     cover (the cover lies within `poke` cm straight behind it). A point that is seen with no cover behind it is in
     a real opening (neck, cuff, hem) and is kept.
  3. Kept as well: everything within `margin` cm (over the surface) of a kept point; for skin also hands, feet, neck.
hidden_face_map.py uses rule 1 for every pose, so it keeps exactly the skin that pokes through. This rule removes it.

EMULATION on Unreal pose captures (cloth physics off), not an Unreal build: per pose, cover triangles that cross
the base surface with all base triangles (before) and without the hidden ones (after). With --shrink the base
vertices inside the margin band are also moved in along their normal (0 at the visible edge, `shrink` cm at the
hidden edge), which is what the engine's MaxShrinkDistance does to the body.
Writes <out>/LayerHide_<base>_under_<cover>.json and .npy (hidden base triangles, capture order).
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
from audit_capture import arm_vertices, labels_of, rest_joints
from hidden_face_map import MARGIN, covered, never_hidden, outward_normals, sees_out
from meshops import edges_of, read_surface, weld

POKE = 5.0      # cm: a seen point with the cover this close straight behind it has come out through the cover
FAR = 80.0      # cm: a line of sight counts as open only if it leaves the cover altogether (loose cloth still hides)
WIDE = ((35., 6), (60., 8))   # sight lines up to 60 degrees off the normal (an 80 degree ring slips under tight cloth and out at the openings, so it keeps nearly everything)


def away_sign(W, Fw, body, bf):
    """+1 where the vertex normal points away from the body, -1 on the wall of a double-walled garment that faces it."""
    n = outward_normals(W, Fw)
    cp, _, _ = contact.closest_on_tris(W, body, bf)
    return np.where(np.einsum("ij,ij->i", W - cp, n) < 0, -1., 1.)


def base_file(folder, label, base):
    return folder / f"{label}_{base}.bin"


def meant_hidden(folder, cover, base="body", margin=MARGIN, poke=POKE, sight=FAR):
    """Per base triangle (capture order): True where the rule hides it; per welded vertex: distance (cm over the
    surface) from kept points; the weld; a summary."""
    labels, man = labels_of(folder)
    P0, F = read_surface(base_file(folder, "standing", base))
    W0, Fw, inv = weld(P0, F)
    first = np.zeros(len(W0), np.int64); first[inv[::-1]] = np.arange(len(inv))[::-1]
    if base == "body":
        sign = np.ones(len(W0))
        joints = rest_joints(man, folder) or {}
        joints = {**{k: np.asarray(v, float) for k, v in man["rest"].items()}, **joints}
        excluded = never_hidden(W0, joints)
    else:
        body0, bf = read_surface(folder / "standing_body.bin")
        sign = away_sign(W0, Fw, body0, bf)
        excluded = np.zeros(len(W0), bool)
    cloth0, cf = read_surface(folder / f"standing_{cover}.bin")
    normal0 = outward_normals(W0, Fw) * sign[:, None]
    under = np.ones(len(W0), bool)
    box = np.all((W0 >= cloth0.min(0) - 4) & (W0 <= cloth0.max(0) + 4), axis=1)
    keep = ~(under & box) | excluded
    candidates = np.flatnonzero(~keep)
    seen = sees_out(W0[candidates], normal0[candidates], cloth0, cf, sight=sight, cone=WIDE)
    keep[candidates[seen]] = True
    standing_hidden = int((~keep).sum())
    poked = np.zeros(len(W0), np.int64)
    for label in labels[1:]:
        candidates = np.flatnonzero(~keep)
        if not len(candidates):
            break
        P, _ = read_surface(base_file(folder, label, base))
        cloth, _ = read_surface(folder / f"{label}_{cover}.bin")
        posed = P[first]
        normal = outward_normals(posed, Fw) * sign[:, None]
        seen = sees_out(posed[candidates], normal[candidates], cloth, cf, sight=sight, cone=WIDE)
        out = candidates[seen]
        if len(out):
            # seen: through the cover (cover straight behind it), or in an opening?
            through = ~sees_out(posed[out], -normal[out], cloth, cf, sight=poke, cone=())
            keep[out[~through]] = True
            poked[out[through]] += 1
    e = edges_of(Fw)
    length = np.linalg.norm(W0[e[:, 0]] - W0[e[:, 1]], axis=1)
    graph = sp.coo_matrix((np.r_[length, length], (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(len(W0), len(W0))).tocsr()
    dist = dijkstra(graph, directed=False, indices=np.flatnonzero(keep), min_only=True, limit=margin * 4) if keep.any() else np.full(len(W0), np.inf)
    hide_v = ~keep & ~(dist < margin)
    hide_t = hide_v[inv][F].all(1)
    info = dict(base=base, cover=cover, poses_used=len(labels), margin_cm=margin, poke_cm=poke, sight_cm=sight, base_triangles=int(len(F)), unseen_standing_vertices=standing_hidden,
                unseen_or_through_in_every_pose_vertices=int((~keep).sum()), vertices_that_come_through_in_some_pose=int(((poked > 0) & ~keep).sum()),
                hidden_vertices=int(hide_v.sum()), hidden_triangles=int(hide_t.sum()))
    return hide_t, dict(dist=dist, inv=inv, first=first, Fw=Fw, sign=sign, keep=keep, hide_v=hide_v), info


def emulate(folder, cover, base, hide_t, geo, margin, shrink=0.):
    labels, man = labels_of(folder)
    P0, F = read_surface(base_file(folder, "standing", base))
    arm_tri = None
    if base == "body":
        arm_v = arm_vertices(P0, rest_joints(man, folder))
        arm_tri = arm_v[F].sum(1) >= 2
    weight = np.clip(geo["dist"] / margin, 0, 1)
    weight = np.where(np.isfinite(weight), weight, 1.) * ~geo["keep"]          # 0 at the visible edge, 1 at the hidden edge
    rows = []
    for label in labels:
        P, _ = read_surface(base_file(folder, label, base))
        cloth, cf = read_surface(folder / f"{label}_{cover}.bin")
        row = dict(label=label)
        for name, faces, moved in (("before", F, P), ("after", F[~hide_t], None)):
            if moved is None:
                moved = P
                if shrink > 0:
                    posed = P[geo["first"]]
                    normal = outward_normals(posed, geo["Fw"]) * geo["sign"][:, None]
                    moved = (posed - normal * (shrink * weight)[:, None])[geo["inv"]]
            lo, hi = cloth.min(0) - 2, cloth.max(0) + 2
            near = np.all((moved >= lo) & (moved <= hi), axis=1)
            pick = near[faces].any(1)
            sub = faces[pick]
            i_base, i_cloth = contact.intersections(moved, sub, cloth, cf)
            if arm_tri is None:
                row[name] = int(len(np.unique(i_cloth)))
            else:
                is_arm = (arm_tri if name == "before" else arm_tri[~hide_t])[pick]
                row[name] = int(len(np.unique(i_cloth[~is_arm[i_base]])))
                row[name + "_arm"] = int(len(np.unique(i_cloth[is_arm[i_base]])))
        rows.append(row)
    summary = {}
    for clip in ("walk", "reach"):
        r = [x for x in rows if x["label"].startswith(clip)]
        if r:
            summary[clip] = {k: dict(median=float(np.median([x[k] for x in r])), peak=max(x[k] for x in r), poses_clear=sum(x[k] == 0 for x in r), total=sum(x[k] for x in r))
                             for k in r[0] if k != "label"}
    return rows, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path)
    parser.add_argument("cover")
    parser.add_argument("--base", default="body")
    parser.add_argument("--margin", type=float, default=MARGIN)
    parser.add_argument("--poke", type=float, default=POKE)
    parser.add_argument("--shrink", type=float, default=0.)
    parser.add_argument("--sight", type=float, default=FAR)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    started = time.time()
    hide_t, geo, info = meant_hidden(args.folder, args.cover, args.base, args.margin, args.poke, args.sight)
    rows, summary = emulate(args.folder, args.cover, args.base, hide_t, geo, args.margin, args.shrink)
    out = args.out or args.folder
    out.mkdir(parents=True, exist_ok=True)
    stem = f"LayerHide_{args.base}_under_{args.cover}"
    np.save(out / f"{stem}.npy", hide_t)
    np.savez_compressed(out / f"{stem}_vertices.npz", dist=geo["dist"], keep=geo["keep"], hide=geo["hide_v"], inv=geo["inv"])
    report = dict(emulation=True, measured_in="EMULATION on Unreal pose captures (cloth physics off); not an Unreal build", body=args.folder.name,
                  shrink_cm=args.shrink, **info, standing=rows[0], summary=summary, per_pose=rows, seconds=round(time.time() - started))
    (out / f"{stem}.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "per_pose"}, indent=1))


if __name__ == "__main__":
    main()
