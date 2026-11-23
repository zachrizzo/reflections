"""EMULATION, not an Unreal measurement: what a body hidden-face map changes on captured poses.

  python emulate_hidden_faces.py <capture folder of one body> <garment tag> <map.png> [<map.png> ...] [--workers 4]

The body triangles the engine removes are found with a port of the engine's own rule (hidden_face_map.engine_hidden:
UV0, red channel, a triangle goes only if every pixel touching it is <= MaxCullValue) on the given PNGs (several maps
are combined like the engine does: a triangle goes if any map removes it). Then, per pose, as in audit_capture.py:
garment triangles crossing non-arm skin and arm skin, with all body triangles (before) and with the removed ones
dropped (after). Also per pose: removed triangles with a corner the garment does not cover in that pose on this body
(a proxy for a hole that could be seen; --cover names every garment layer worn). Writes <folder>/HiddenFaceEmulation_<tag>.json.
"""
import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contact
from audit_capture import arm_vertices, labels_of, rest_joints
from body_uv import corner_uvs
from hidden_face_map import covered, engine_hidden
from meshops import read_surface, weld


def removed_by(maps, bf):
    from PIL import Image
    uv = corner_uvs(bf)
    out = np.zeros(len(bf), bool)
    for path in maps:
        image = np.asarray(Image.open(path).convert("RGB"))[:, :, 0]
        out |= engine_hidden(uv, image)
    return out


def pose(args):
    folder, label, tag, removed, cover_tags = args
    folder = Path(folder)
    body0, bf = read_surface(folder / "standing_body.bin")
    _, man = labels_of(folder)
    arm_v = arm_vertices(body0, rest_joints(man, folder))
    body, _ = read_surface(folder / f"{label}_body.bin")
    face, ff = read_surface(folder / f"{label}_face.bin")
    cloth, cf = read_surface(folder / f"{label}_{tag}.bin")
    skin = np.vstack((body, face))
    arm_full = np.zeros(len(skin), bool); arm_full[:len(body)] = arm_v
    row = dict(label=label)
    for name, body_faces in (("before", bf), ("after", bf[~removed])):
        sf = np.vstack((body_faces, ff + len(body)))
        lo, hi = cloth.min(0) - 2, cloth.max(0) + 2
        near = np.all((skin >= lo) & (skin <= hi), axis=1)
        sub = sf[near[sf].any(1)]
        i_skin, i_cloth = contact.intersections(skin, sub, cloth, cf)
        is_arm = arm_full[sub].sum(1) >= 2
        row[name] = int(len(np.unique(i_cloth[~is_arm[i_skin]])))
        row[name + "_arm"] = int(len(np.unique(i_cloth[is_arm[i_skin]])))
    W, Fw, inv = weld(body, bf)
    cov = np.zeros(len(W), bool)
    for t in cover_tags:
        layer, lf = read_surface(folder / f"{label}_{t}.bin")
        cov |= covered(W, Fw, layer, lf)
    row["removed_with_uncovered_corner"] = int((removed & ~cov[inv][bf].all(1)).sum())
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("tag")
    parser.add_argument("maps", nargs="+", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--cover", nargs="*", help="garment tags worn whose cover counts for the hole check (default: the garment tag)")
    args = parser.parse_args()
    labels, _ = labels_of(args.folder)
    _, bf = read_surface(args.folder / "standing_body.bin")
    removed = removed_by(args.maps, bf)
    with Pool(min(args.workers, 4)) as pool:
        rows = pool.map(pose, [(str(args.folder), l, args.tag, removed, args.cover or [args.tag]) for l in labels])
    motion = [r for r in rows if r["label"] != "standing"]
    summary = {}
    for clip in ("walk", "reach"):
        r = [x for x in motion if x["label"].startswith(clip)]
        summary[clip] = dict(poses=len(r), non_arm_sum_before=sum(x["before"] for x in r), non_arm_sum_after=sum(x["after"] for x in r),
                             non_arm_median_before=float(np.median([x["before"] for x in r])), non_arm_median_after=float(np.median([x["after"] for x in r])),
                             non_arm_peak_before=max(x["before"] for x in r), non_arm_peak_after=max(x["after"] for x in r),
                             poses_clear_before=sum(x["before"] == 0 for x in r), poses_clear_after=sum(x["after"] == 0 for x in r),
                             arm_sum_before=sum(x["before_arm"] for x in r), arm_sum_after=sum(x["after_arm"] for x in r),
                             removed_with_uncovered_corner_peak=max(x["removed_with_uncovered_corner"] for x in r))
    total_b = sum(x["before"] for x in motion); total_a = sum(x["after"] for x in motion)
    out = dict(emulation=True, measured_in="EMULATION of the engine's hidden-face rule on Unreal pose captures (cloth physics off); not an Unreal build",
               body=args.folder.name, garment=args.tag, maps=[str(m) for m in args.maps], removed_triangles=int(removed.sum()),
               motion_poses=len(motion), non_arm_total_before=total_b, non_arm_total_after=total_a,
               non_arm_reduction_pct=round(100 * (1 - total_a / total_b), 1) if total_b else None, standing=rows[0], summary=summary, poses=rows)
    (args.folder / f"HiddenFaceEmulation_{args.tag}.json").write_text(json.dumps(out, indent=1))
    print(args.folder.name, args.tag, "removed", out["removed_triangles"], "non-arm crossings (50 poses) before", total_b, "after", total_a,
          f"({out['non_arm_reduction_pct']}% less)", {k: (v["non_arm_median_before"], v["non_arm_median_after"], v["poses_clear_before"], v["poses_clear_after"], v["removed_with_uncovered_corner_peak"]) for k, v in summary.items()})


if __name__ == "__main__":
    main()
