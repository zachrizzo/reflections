"""From a real Unreal capture: does the crossed cloth follow the skin under it, and which skin crosses it?"""
import sys, json
from pathlib import Path
HERE = Path(r"C:/Users/zachc/Documents/Unreal Projects/reflections/Tools/ClothingFit/garmentprep")
sys.path.insert(0, str(HERE))
import numpy as np
from scipy.spatial import cKDTree
import contact
from meshops import read_surface, tri_area
from audit_capture import arm_vertices, rest_joints
np.set_printoptions(linewidth=220, suppress=True)
folder = Path(sys.argv[1]); tag = sys.argv[2] if len(sys.argv) > 2 else "jerkin"
man = json.loads((folder / "Manifest.json").read_text())
b0, bf = read_surface(folder / "standing_body.bin"); c0, cf = read_surface(folder / f"standing_{tag}.bin")
joints = rest_joints(man, folder); arm_v = arm_vertices(b0, joints)
tree = cKDTree(b0); dist0, near = tree.query(c0)
sh = {s: joints[f"upperarm_{s}"] for s in "lr"}; el = {s: joints[f"lowerarm_{s}"] for s in "lr"}
for label in sys.argv[3:] or ["walk_09", "reach_09"]:
    b1, _ = read_surface(folder / f"{label}_body.bin"); c1, _ = read_surface(folder / f"{label}_{tag}.bin")
    z = np.load(folder / f"audit_{label}.npz"); gt = z["other"]
    gv = np.unique(cf[gt])
    cloth_move = c1[gv] - c0[gv]; skin_move = b1[near[gv]] - b0[near[gv]]
    diff = np.linalg.norm(cloth_move - skin_move, axis=1)
    print(f"{label}: {len(gt)} garment triangles cross non-arm skin; their {len(gv)} vertices sit {np.median(dist0[gv]):.2f} cm (median) from the nearest skin vertex at standing")
    print(f"   cloth moved {np.median(np.linalg.norm(cloth_move, axis=1)):.1f} cm, the skin under it moved {np.median(np.linalg.norm(skin_move, axis=1)):.1f} cm, difference median {np.median(diff):.2f} p90 {np.percentile(diff, 90):.2f} cm")
    # which skin crosses those triangles
    lo, hi = c1.min(0) - 2, c1.max(0) + 2
    act = np.all((b1 >= lo) & (b1 <= hi), axis=1); sub = bf[act[bf].any(1)]
    isk, icl = contact.intersections(b1, sub, c1, cf)
    keep = np.isin(icl, gt); st = np.unique(isk[keep])
    sv = np.unique(sub[st])
    along = {}
    for s in "lr":
        t = ((b0[sv] - sh[s]) @ (el[s] - sh[s])) / ((el[s] - sh[s]) @ (el[s] - sh[s]))
        side = np.sign(b0[sv][:, 0]) == np.sign(sh[s][0])
        along[s] = t[side]
    t_all = np.concatenate(list(along.values()))
    radial = []
    for s in "lr":
        side = np.sign(b0[sv][:, 0]) == np.sign(sh[s][0]); p = b0[sv][side]; ab = el[s] - sh[s]
        t = np.clip(((p - sh[s]) @ ab) / (ab @ ab), 0, 1); radial.append(np.linalg.norm(p - (sh[s] + t[:, None] * ab), axis=1))
    radial = np.concatenate(radial)
    print(f"   skin that crosses them: {len(sv)} vertices; standing |x| {np.percentile(np.abs(b0[sv][:, 0]), [5, 50, 95]).round(1)} z {np.percentile(b0[sv][:, 2], [5, 50, 95]).round(1)}; position along the upper arm (0 shoulder, 1 elbow) {np.percentile(t_all, [5, 50, 95]).round(2)}; distance from the arm bone {np.percentile(radial, [5, 50, 95]).round(1)} cm; counted as arm by the audit: {int(arm_v[sv].sum())}")
    print(f"   that skin moved {np.median(np.linalg.norm(b1[sv] - b0[sv], axis=1)):.1f} cm (median) between standing and this pose")
