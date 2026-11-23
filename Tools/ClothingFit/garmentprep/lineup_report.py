"""Collect the per-body audits of a lineup into one pass table.

  python lineup_report.py <lineup folder> [garment tag=jerkin]

Writes <folder>/Lineup_<tag>.json and Lineup_<tag>.md. Per body and clip (standing, walk, reach):
  clear        poses in which no garment triangle crosses skin other than the free arms
  at floor     poses in which that contact is no more than what the same garment has as a 0.6 cm
               layer glued to the skin (the body folding over itself: armpit folds, bent waist)
  worst        the worst pose: triangles, depth, where on the garment
  under        poses in which the layer worn underneath is crossed
Everything is measured on Unreal captures with cloth physics off.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from meshops import read_surface


def region_names(folder, tag, rest):
    c0, cf = read_surface(folder / f"standing_{tag}.bin")
    cen = c0[cf].mean(1)
    shoulder = np.asarray(rest["upperarm_l"], float)
    pelvis = np.asarray(rest["pelvis"], float)
    half = abs(shoulder[0])
    z, x = cen[:, 2], np.abs(cen[:, 0])
    names = np.full(len(cf), "torso", dtype=object)
    if z.max() < shoulder[2] - 20:
        # a bottom: nothing reaches the chest
        knee = float(np.asarray(rest["calf_l"], float)[2])
        names[:] = "thigh"
        names[z > pelvis[2] - 8] = "waist/seat"
        names[(z <= pelvis[2] - 8) & (z > pelvis[2] - 24) & (x < 7)] = "crotch"
        names[z < knee + 4] = "knee and below"
        return names
    names[z < pelvis[2] + 10] = "hem"
    names[(z > shoulder[2] - 28) & (z <= shoulder[2] - 2) & (x > .8 * half)] = "underarm/side"
    names[z > shoulder[2] - 2] = "neck/shoulders"
    names[x > half + 6] = "sleeve"
    return names


def body_row(folder, tag):
    audit = json.loads((folder / f"Audit_{tag}.json").read_text())
    man = json.loads((folder / "Manifest.json").read_text())
    names = region_names(folder, tag, man["rest"])
    row = {"target_body": man.get("target_body", {}).get(tag, ""), "body_state_refreshed": man.get("body_state_refreshed")}
    # the skeleton must belong to the body: the shoulder joint sits a few centimetres under the top of the
    # body mesh. A character whose body state was never committed animates on a default skeleton.
    body_top = float(read_surface(folder / "standing_body.bin")[0][:, 2].max())
    row["shoulder_below_body_top_cm"] = round(body_top - float(man["rest"]["upperarm_l"][2]), 1)
    row["skeleton_matches_body"] = bool(2. <= row["shoulder_below_body_top_cm"] <= 15.)
    for clip in ("standing", "walk", "reach"):
        poses = [p for p in audit["poses"] if p["label"].startswith(clip)]
        if not poses:
            continue
        worst = max(poses, key=lambda p: (p["other_tris"], p["other_depth_mm"]))
        where = {}
        if worst["other_tris"]:
            hit = np.load(folder / f"audit_{tag}_{worst['label']}.npz")["other"]
            keys, counts = np.unique(names[hit], return_counts=True)
            where = {str(k): int(v) for k, v in zip(keys, counts)}
        failing = [p["label"] for p in poses if p["other_tris"] > 0]
        # contact outside the armpit zone (the part of the result that is in plain view)
        open_view = {}
        for p in poses:
            if p["other_tris"]:
                hit_p = np.load(folder / f"audit_{tag}_{p['label']}.npz")["other"]
                open_view[p["label"]] = int((names[hit_p] != "underarm/side").sum())
        over_floor = [p["label"] for p in poses if p["other_tris"] > p["floor_other_tris"] * 1.15 + 10]
        row[clip] = dict(
            poses=len(poses), clear=len(poses) - len(failing), failing=failing,
            at_or_under_floor=len(poses) - len(over_floor), over_floor=over_floor,
            worst_pose=worst["label"], worst_triangles=worst["other_tris"], worst_depth_mm=worst["other_depth_mm"], worst_where=where,
            floor_triangles_in_worst_pose=worst["floor_other_tris"],
            clear_outside_underarm=len(poses) - sum(v > 0 for v in open_view.values()),
            outside_underarm_peak=max(open_view.values(), default=0),
            outside_underarm_worst_pose=max(open_view, key=open_view.get) if open_view and max(open_view.values()) else "",
            non_arm_triangles_median=int(np.median([p["other_tris"] for p in poses])),
            floor_non_arm_triangles_median=int(np.median([p["floor_other_tris"] for p in poses])),
            arm_triangles_median=int(np.median([p["arm_tris"] for p in poses])), arm_triangles_peak=max(p["arm_tris"] for p in poses),
            floor_arm_triangles_median=int(np.median([p["floor_arm_tris"] for p in poses])),
            under_layer_poses=[p["label"] for p in poses if p.get("under_tris", 0) > 0],
            under_layer_triangles_peak=max(p.get("under_tris", 0) for p in poses),
            stretch_p95_worst_pct=max(p["stretch_p95_pct"] for p in poses))
    return row


def main():
    folder = Path(sys.argv[1]); tag = sys.argv[2] if len(sys.argv) > 2 else "jerkin"
    table = {}
    for sub in sorted(p for p in folder.iterdir() if p.is_dir()):
        if (sub / f"Audit_{tag}.json").exists():
            table[sub.name] = body_row(sub, tag)
        elif (sub / "CaptureError.txt").exists():
            table[sub.name] = {"error": (sub / "CaptureError.txt").read_text()[:300]}
    (folder / f"Lineup_{tag}.json").write_text(json.dumps(table, indent=1))
    lines = [f"| body | standing clear | walk clear | walk at floor | reach clear | reach at floor | clear outside the underarm, walk / reach (peak triangles, pose) | walk triangles median (floor) | reach triangles median (floor) | "
             f"arm skin walk / reach median (floor) | worst depth mm (pose) | where (worst pose) | layer underneath crossed |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    totals = dict(bodies=0, standing_clear=0, all_at_floor=0, under_clean=0)
    for name, row in table.items():
        if "error" in row:
            lines.append(f"| {name} | capture failed | | | | | | | | | | | |")
            continue
        s, w, r = row["standing"], row["walk"], row["reach"]
        if not row["skeleton_matches_body"]:
            under = sorted(set(s["under_layer_poses"]))
            lines.append(f"| {name} | {s['clear']}/{s['poses']} | motion not valid: the skeleton does not belong to this body "
                         f"(shoulder joint {row['shoulder_below_body_top_cm']} cm under the body top) | | | | | | | | | | "
                         f"{len(under)} poses standing, peak {s['under_layer_triangles_peak']} tris |")
            totals["bodies"] += 1
            totals["standing_clear"] += s["clear"] == s["poses"]
            totals["motion_not_valid"] = totals.get("motion_not_valid", 0) + 1
            continue
        worst = max((w, r, s), key=lambda c: c["worst_depth_mm"])
        under = sorted(set(s["under_layer_poses"] + w["under_layer_poses"] + r["under_layer_poses"]))
        where = ", ".join(f"{k} {v}" for k, v in worst["worst_where"].items()) or "none"
        lines.append(f"| {name} | {s['clear']}/{s['poses']} | {w['clear']}/{w['poses']} | {w['at_or_under_floor']}/{w['poses']} | {r['clear']}/{r['poses']} | "
                     f"{r['at_or_under_floor']}/{r['poses']} | {w['clear_outside_underarm']}/{w['poses']} / {r['clear_outside_underarm']}/{r['poses']} "
                     f"({max(w['outside_underarm_peak'], r['outside_underarm_peak'])}{', ' + (w if w['outside_underarm_peak'] >= r['outside_underarm_peak'] else r)['outside_underarm_worst_pose'] if max(w['outside_underarm_peak'], r['outside_underarm_peak']) else ''}) | {w['non_arm_triangles_median']} ({w['floor_non_arm_triangles_median']}) | {r['non_arm_triangles_median']} ({r['floor_non_arm_triangles_median']}) | "
                     f"{w['arm_triangles_median']} ({w['floor_arm_triangles_median']}) / {r['arm_triangles_median']} ({r['floor_arm_triangles_median']}) | "
                     f"{worst['worst_depth_mm']:.0f} ({worst['worst_pose']}) | {where} | {len(under)} poses, peak {max(s['under_layer_triangles_peak'], w['under_layer_triangles_peak'], r['under_layer_triangles_peak'])} tris |")
        totals["bodies"] += 1
        totals["standing_clear"] += s["clear"] == s["poses"]
        totals["all_at_floor"] += (w["at_or_under_floor"] == w["poses"]) and (r["at_or_under_floor"] == r["poses"]) and s["clear"] == s["poses"]
        totals["under_clean"] += not under
        totals["clear_outside_underarm_all_poses"] = totals.get("clear_outside_underarm_all_poses", 0) + (
            w["clear_outside_underarm"] == w["poses"] and r["clear_outside_underarm"] == r["poses"] and s["clear"] == s["poses"])
    (folder / f"Lineup_{tag}.md").write_text("\n".join(lines) + "\n\n" + json.dumps(totals) + "\n")
    print("\n".join(lines))
    print(totals)


if __name__ == "__main__":
    main()
