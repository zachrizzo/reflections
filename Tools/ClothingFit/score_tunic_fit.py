"""Score the tailored tunic from measured geometry. Exit 1 if any wearer fails."""
import argparse
import json
from pathlib import Path


def score(frames, limits):
    poses = {f"{motion}_{pct}" for motion in ("walk", "crouch", "cast") for pct in (22, 50, 78)}
    if set(frames) != poses | {"rest"}:
        raise ValueError("Expected rest and nine animated samples")
    moving = [frames[name] for name in sorted(poses)]
    regions = frames["rest"]["directional_mm"]
    checks = {}
    for region, maximum in (("chest_front", limits.chest_mm), ("waist_front", limits.waist_mm)):
        measured = regions[region]
        checks[region] = (measured["n"] == 27 and measured["min"] >= limits.min_mm
                          and measured["max"] <= maximum)
    shoulders = [regions["shoulder_l"], regions["shoulder_r"]]
    checks["shoulder_clearance"] = all(r["n"] >= 5 and r["min"] >= 0 and r["max"] <= limits.shoulder_mm
                                        for r in shoulders)
    ease = frames["rest"]["circumference_mm"]["waist"].get("ease_mm")
    checks["waist_circumference"] = ease is not None and limits.ease_min_mm <= ease <= limits.ease_max_mm
    drift = max(f["change_in_gap_to_tracked_skin_mm"]["p95"] for f in moving)
    stretch = max(f["edge_length_ratio"]["p95"] for f in moving)
    checks["body_follow"] = drift <= limits.drift_mm and all(f["vertex_travel_cm"]["p95"] > 1 for f in moving)
    checks["edge_stretch"] = stretch <= 1 + limits.stretch / 100
    exposed = max(frames, key=lambda n: frames[n]["crossing_wholly_unmasked_body"])
    unresolved = max(f["crossing_mask_edge_or_unverified_skin"] for f in frames.values())
    confirmed = frames[exposed]["crossing_wholly_unmasked_body"]
    checks["confirmed_unmasked_contact_free"] = confirmed == 0
    checks["all_contacts_resolved"] = unresolved == 0
    verdict = "fail" if not all(v for k, v in checks.items() if k != "all_contacts_resolved") else (
        "pass" if not unresolved else "unresolved")
    return {
        "verdict": verdict, "checks": checks, "front_chest_max_mm": regions["chest_front"].get("max"),
        "front_waist_max_mm": regions["waist_front"].get("max"),
        "maximum_shoulder_mm": max((r["max"] for r in shoulders if r["n"]), default=None),
        "waist_circumference_ease_mm": ease,
        "worst_p95_skin_gap_change_mm": drift,
        "worst_p95_edge_stretch_percent": round(100 * (stretch - 1), 1),
        "most_garment_triangles_crossing_wholly_unmasked_body": confirmed, "worst_unmasked_frame": exposed,
        "most_garment_triangles_crossing_unresolved_skin": unresolved,
        "animated_poses_with_bare_body_self_contact": sum(
            r["bare_body_intersecting_pairs_separated_in_rest"] > 0 for r in moving),
        "summed_unmasked_triangle_contacts_across_animated_samples": sum(
            r["crossing_wholly_unmasked_body"] for r in moving),
        "summed_unmasked_contacts_near_bare_self_contact": sum(
            r["unmasked_cloth_contacts_within_20mm_of_bare_self_contact"] for r in moving),
    }


def write_table(path, rows, counts, verdicts, limits):
    def number(value):
        return f"{value:.1f}" if value is not None else "unmeasured"
    total = len(rows)
    lines = [
        "# Wayfarer’s Tunic fit scorecard", "",
        f"{verdicts['pass']} of {total} wearers passed every check. "
        f"{verdicts['fail']} failed at least one measured limit. "
        f"{verdicts['unresolved']} had unresolved coverage as their only remaining issue.", "",
        "Working limits for this tunic are expressed in millimeters unless stated otherwise. "
        "They are design choices for this garment.", "",
        "| Check | Limit | Wearers passing |", "| --- | --- | ---: |",
        f"| Front chest clearance at rest | All 27 rays between {limits.min_mm:g} and {limits.chest_mm:g} mm | {counts['chest_front']}/{total} |",
        f"| Front waist clearance at rest | All 27 rays between {limits.min_mm:g} and {limits.waist_mm:g} mm | {counts['waist_front']}/{total} |",
        f"| Extra circumference at the waist | Closed 128-ray garment and body rings, difference {limits.ease_min_mm:g}–{limits.ease_max_mm:g} mm | {counts['waist_circumference']}/{total} |",
        f"| Top of each shoulder at rest | At least 5 of 9 rays hit matching surfaces, each between 0 and {limits.shoulder_mm:g} mm | {counts['shoulder_clearance']}/{total} |",
        f"| Following the body | Per-pose 95th percentile change in gap to tracked skin ≤ {limits.drift_mm:g} mm, garment travel at the 95th percentile > 1 cm in all nine moving samples | {counts['body_follow']}/{total} |",
        f"| Fabric edge stretch | 95th percentile edge elongation ≤ {limits.stretch:g}% in each moving sample | {counts['edge_stretch']}/{total} |",
        f"| Contact with wholly unmasked body triangles | Zero garment triangles crossing them in all ten samples | {counts['confirmed_unmasked_contact_free']}/{total} |",
        f"| Contacts at mask boundaries or on unverified skin | All crossings classified | {counts['all_contacts_resolved']}/{total} |",
        "", "## Individual results", "",
        "| Wearer | Chest max (mm) | Waist max (mm) | Extra waist circumference (mm) | Shoulder max (mm) | Skin tracking, worst p95 (mm) | Edge stretch, worst p95 | Most triangles crossing wholly unmasked skin in one pose | Pose | Verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for name, row in rows.items():
        lines.append(f"| {name} | {number(row['front_chest_max_mm'])} | {number(row['front_waist_max_mm'])} "
                     f"| {number(row['waist_circumference_ease_mm'])} | {number(row['maximum_shoulder_mm'])} | {row['worst_p95_skin_gap_change_mm']:.2f} "
                     f"| {row['worst_p95_edge_stretch_percent']:.0f}% "
                     f"| {row['most_garment_triangles_crossing_wholly_unmasked_body']} "
                     f"| {row['worst_unmasked_frame']} | {row['verdict']} |")
    contacts = sum(r["summed_unmasked_triangle_contacts_across_animated_samples"] for r in rows.values())
    close = sum(r["summed_unmasked_contacts_near_bare_self_contact"] for r in rows.values())
    bare = sum(r["animated_poses_with_bare_body_self_contact"] for r in rows.values())
    lines += ["", "## How to interpret the contact counts", "",
              "The audit intersects the actual fitted garment and skin triangles in each pose. A body triangle "
              "counts as unmasked when its entire UV bounding box, including a filtering margin, samples white "
              "in the assigned mask. The report separates fully masked areas from mixed areas and face geometry. "
              "A raw triangle count measures contact and depends on mesh density.", "",
              f"The bare body also had self-intersections in {bare} of {9 * total} moving samples. "
              f"Of {contacts} garment triangle contacts with wholly unmasked body triangles across those samples, "
              f"{close} were within 20 mm of a bare-body contact, measured between triangle centers. "
              "This test counts intersections between disjoint body triangles whose centers were at least 40 mm "
              "apart in the neutral pose. The same garment triangle can be counted in different frames.", "",
              "The measurements cover the editor’s skinned LOD 0 mesh in the neutral pose, walk, crouch walk "
              "and healing cast. The full sample file includes percentiles, sample counts and additional regions "
              "around the back and hem. [Full measurements](FitSamples.json)", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("input", type=Path)
    cli.add_argument("output", type=Path)
    cli.add_argument("--markdown", type=Path)
    cli.add_argument("--min-mm", type=float, default=3)
    cli.add_argument("--chest-mm", type=float, default=40)
    cli.add_argument("--waist-mm", type=float, default=30)
    cli.add_argument("--shoulder-mm", type=float, default=30)
    cli.add_argument("--ease-min-mm", type=float, default=30)
    cli.add_argument("--ease-max-mm", type=float, default=80)
    cli.add_argument("--drift-mm", type=float, default=3)
    cli.add_argument("--stretch", type=float, default=20)
    args = cli.parse_args()
    captures = json.loads(args.input.read_text())
    if not captures:
        cli.error("No captured characters")
    rows = {name: score(frames, args) for name, frames in sorted(captures.items())}
    counts = {key: sum(r["checks"][key] for r in rows.values()) for key in next(iter(rows.values()))["checks"]}
    verdicts = {v: sum(r["verdict"] == v for r in rows.values()) for v in ("pass", "fail", "unresolved")}
    args.output.write_text(json.dumps({
        "limits": {k: v for k, v in vars(args).items() if k not in ("input", "output", "markdown")},
        "wearers": len(rows), "pass_counts": counts, "verdicts": verdicts, "characters": rows,
    }, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        write_table(args.markdown, rows, counts, verdicts, args)
    print(json.dumps({"wearers": len(rows), "pass_counts": counts, "verdicts": verdicts}))
    return 0 if verdicts["pass"] == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
